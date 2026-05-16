"""
api/chat.py — RAG Chat Endpoint (Phase C — REAL IMPLEMENTATION)
================================================================
🎓 LEARNING: This endpoint implements the full RAG pipeline at query time:

  User Question
       │
       ▼  embed_query()
  Query Vector (768 floats)
       │
       ▼  retrieve_chunks()
  Top-15 Candidates from ChromaDB (cosine similarity)
       │
       ▼  rerank_chunks()
  Top-5 Most Relevant Chunks (cross-encoder scored)
       │
       ▼  build_rag_prompt()
  Grounded Prompt (question + context pasted in)
       │
       ▼  Gemini 1.5 Flash (streaming)
  Response tokens streaming via SSE
       │
       ▼  parse JSON citation block
  Source page numbers → sent to frontend for highlighting

SSE STREAMING:
  We stream the response word-by-word using Server-Sent Events.
  The frontend uses the EventSource API to receive tokens in real time.
  At the very end, we send a special "done" event with the source pages.
"""

import json
import re
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.retrieval.retriever import retrieve_chunks
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.core.llm_client import llm_client  # Groq rotating client
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    doc_id: str
    question: str
    chat_history: list = []  # Reserved for multi-turn conversations (Phase D)


@router.post("/chat")
async def chat_with_paper(request: ChatRequest):
    """
    Full RAG pipeline: retrieve → re-rank → generate (streaming).
    Returns an SSE stream of tokens, ending with a sources JSON event.
    """
    logger.info(f"[CHAT] doc_id={request.doc_id} | question='{request.question[:60]}...'")
    
    return StreamingResponse(
        _rag_stream(request.doc_id, request.question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Prevents nginx from buffering (important in prod!)
        }
    )


async def _rag_stream(doc_id: str, question: str):
    """
    The core RAG generator — yields SSE-formatted strings.
    
    🎓 LEARNING: This is a Python "async generator" — a function that
    uses `yield` inside an `async def`. FastAPI's StreamingResponse
    consumes this generator and sends each yielded string to the browser.
    
    SSE format:  "data: {json_string}\\n\\n"
    The double \\n\\n is the SSE event separator — the browser splits on it.
    """
    
    # ── STEP 1: Check if document is indexed ────────────────────────────
    from app.core.chromadb_client import get_or_create_collection
    collection = get_or_create_collection(doc_id)
    
    if collection.count() == 0:
        # 🎓 LEARNING: Instead of a dead-end error, we emit a special event type
        # "needs_indexing". The frontend can catch this and auto-trigger ingestion,
        # giving the user a clear path forward instead of a confusing error.
        # This is the "graceful degradation" pattern — always give the user
        # something actionable, never a silent failure.
        yield _event("needs_indexing", {
            "content": "📄 This paper hasn't been indexed yet. Starting indexing now — this takes about 60 seconds for a typical paper.",
            "doc_id": doc_id,
        })
        return
    
    # ── STEP 2: Retrieve top-K similar chunks from ChromaDB ─────────────
    try:
        candidates = retrieve_chunks(doc_id, question)
    except Exception as e:
        logger.error(f"[CHAT] Retrieval error: {e}")
        yield _event("error", {"content": "Failed to search the document. Please try again."})
        return
    
    if not candidates:
        yield _event("error", {"content": "No relevant content found for your question."})
        return
    
    # ── STEP 3: Re-rank with cross-encoder ──────────────────────────────
    top_chunks = rerank_chunks(question, candidates)
    
    # ── STEP 4: Build the grounded prompt ───────────────────────────────
    prompt = build_rag_prompt(question, top_chunks)
    
    # ── STEP 5: Call Groq and stream the response ───────────────────────
    # 🎓 LEARNING: Groq's streaming API works differently from Gemini:
    # - We send a list of {"role": ..., "content": ...} messages
    # - The stream yields chunk objects with chunk.choices[0].delta.content
    # - Our GroqRotatingClient handles key switching transparently
    messages = [
        {
            "role": "system",
            "content": "You are an expert academic research assistant. Answer questions strictly from the provided paper excerpts."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    full_response = ""  # Accumulate full response to parse citations at the end
    
    try:
        stream = llm_client.stream(messages)
        
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                full_response += token
                yield _event("token", {"content": token})
        
    except RuntimeError as e:
        # All keys exhausted
        logger.error(f"[CHAT] LLM exhausted: {e}")
        yield _event("error", {"content": str(e)})
        return
    except Exception as e:
        logger.error(f"[CHAT] Generation error: {e}")
        yield _event("error", {"content": f"AI generation failed: {str(e)}"})
        return
    
    # ── STEP 6: Parse citation JSON and send source metadata ─────────────
    # 🎓 LEARNING: We instructed Gemini to include a JSON block at the end
    # of its response. We parse that block to extract which excerpts it used,
    # then map those excerpt indices → actual page numbers from our chunks.
    # This is what the frontend uses to scroll to and highlight the source!
    sources = _extract_sources(full_response, top_chunks)
    
    yield _event("done", {"sources": sources})


def _event(event_type: str, data: dict) -> str:
    """
    Formats a Server-Sent Events message.
    
    🎓 LEARNING: The SSE spec (RFC 8895) requires:
      - Lines starting with "data: "
      - Events terminated by a blank line (\\n\\n)
    The browser's EventSource API automatically parses this format.
    """
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


def _extract_sources(full_response: str, chunks: list) -> list[dict]:
    """
    Parses the JSON citation block from Gemini's response.
    Maps excerpt indices → real page numbers from our chunk metadata.
    
    🎓 LEARNING: We use a regex to find the JSON block in the response.
    We look for everything between triple-backticks (```json ... ```).
    This is more robust than assuming the JSON is always at the very end.
    """
    sources = []
    
    try:
        # Find ```json { ... } ``` block in the response
        match = re.search(r'```json\s*(\{.*?\})\s*```', full_response, re.DOTALL)
        if not match:
            # Fallback: try to find a raw JSON object
            match = re.search(r'\{"sources":\s*\[.*?\]\}', full_response, re.DOTALL)
        
        if match:
            citation_data = json.loads(match.group(1) if '```' in full_response else match.group(0))
            
            for citation in citation_data.get("sources", []):
                idx = citation.get("excerpt_index", -1)
                if 0 <= idx < len(chunks):
                    chunk = chunks[idx]
                    sources.append({
                        "page": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "excerpt_index": idx,
                    })
    
    except (json.JSONDecodeError, AttributeError) as e:
        # Non-critical: if parsing fails, we just return no sources
        logger.warning(f"[CHAT] Could not parse citation JSON: {e}")
        # Fall back to returning all used chunks as sources
        sources = [{"page": c.page_number, "chunk_index": c.chunk_index} for c in chunks[:3]]
    
    return sources

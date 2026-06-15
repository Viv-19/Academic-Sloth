"""
api/chat.py — RAG Chat Endpoint (Production — LangGraph Agent Pipeline)
=========================================================================
This is the upgraded chat endpoint that uses the LangGraph agent pipeline
instead of the old manual retrieve → rerank → generate flow.

WHAT CHANGED:
  - Old: Manual _rag_stream() with hardcoded retrieve → rerank → generate
  - New: LangGraph agent pipeline with router → specialized agent →
         grounding guard → citation agent

  - Old: No conversation memory
  - New: Sliding window memory for follow-up questions

  - Old: No input validation
  - New: Question length limits, sanitization

  - Old: Fragile regex citation parsing
  - New: Robust citation agent with fallback attribution

SSE FORMAT (UNCHANGED — frontend stays compatible):
  token         → A text token to append
  agent_step    → NEW: Optional agent progress indicator
  done          → Streaming complete with sources + metadata
  needs_indexing→ Paper not indexed yet
  error         → Fatal error
"""

import json
import logging
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.services.agents.graph import run_agent_pipeline
from app.services.rag.conversation_memory import conversation_manager
from app.services.retrieval.query_processor import preprocess_query
from app.observability.logger import set_correlation_id
from app.observability.metrics import metrics_collector, RequestMetrics, Timer

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    doc_id: str
    question: str
    chat_history: list = []


@router.post("/chat")
async def chat_with_paper(request: ChatRequest):
    """
    Full agentic RAG pipeline: route → retrieve → re-rank → generate → ground → cite.
    Returns an SSE stream of tokens, ending with a sources JSON event.
    """
    # Generate correlation ID for request tracing
    cid = set_correlation_id()
    logger.info(f"[CHAT] doc_id={request.doc_id} | question='{request.question[:60]}...'")

    # Input validation
    if len(request.question) > settings.MAX_QUESTION_LENGTH:
        return StreamingResponse(
            _error_stream(f"Question too long. Maximum {settings.MAX_QUESTION_LENGTH} characters."),
            media_type="text/event-stream",
        )

    if not request.question.strip():
        return StreamingResponse(
            _error_stream("Please enter a question."),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _agent_stream(request.doc_id, request.question, request.chat_history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def _agent_stream(doc_id: str, question: str, chat_history: list):
    """
    The core agent-powered RAG generator — yields SSE-formatted strings.

    Flow:
        1. Check if document is indexed
        2. Load conversation memory
        3. Preprocess query
        4. Run LangGraph agent pipeline (non-streaming)
        5. Stream the response token-by-token to the frontend
        6. Send sources and metadata
    """
    with Timer() as total_timer:

        # ── STEP 1: Check if document is indexed ──────────────────
        from app.core.chromadb_client import get_or_create_collection
        collection = get_or_create_collection(doc_id)

        if collection.count() == 0:
            yield _event("needs_indexing", {
                "content": "📄 This paper hasn't been indexed yet. Starting indexing now — this takes about 60 seconds for a typical paper.",
                "doc_id": doc_id,
            })
            return

        # ── STEP 2: Load conversation memory ─────────────────────
        session = conversation_manager.get_session(doc_id)

        # Sync incoming chat_history with our memory
        if chat_history and session.is_empty():
            for msg in chat_history[-10:]:
                if msg.get("role") == "user":
                    session.add_user_message(msg["content"])
                elif msg.get("role") == "assistant":
                    session.add_assistant_message(msg["content"])

        conversation_context = session.get_context_string()

        # ── STEP 3: Preprocess query ─────────────────────────────
        query_info = preprocess_query(question, session.get_history())
        processed_question = query_info["primary_query"]

        # ── STEP 4: Emit agent step event ─────────────────────────
        yield _event("agent_step", {"step": "analyzing", "content": "Analyzing your question..."})

        # ── STEP 5: Run the LangGraph agent pipeline ─────────────
        from app.services.agents.graph import get_compiled_graph
        graph = get_compiled_graph()
        
        initial_state = {
            "question": processed_question,
            "doc_id": doc_id,
            "chat_history": session.get_history(),
            "conversation_context": conversation_context,
            "steps_completed": [],
            "error": None,
        }

        result = initial_state
        try:
            with Timer() as pipeline_timer:
                for event in graph.stream(initial_state):
                    for node_name, state_update in event.items():
                        # Update the accumulated result state
                        result.update(state_update)
                        
                        # Emit a UI event for the user
                        if node_name == "router":
                            intent = state_update.get("intent", "factual")
                            yield _event("agent_step", {"step": "routing", "content": f"Router analyzed intent: {intent}"})
                        elif node_name.endswith("_agent") and node_name != "citation_agent":
                            agent_name = state_update.get("agent_name", node_name)
                            yield _event("agent_step", {"step": "generating", "content": f"{agent_name.replace('_', ' ').title()} is reading the paper..."})
                        elif node_name == "grounding_guard":
                            score = state_update.get("grounding_score", 0.0)
                            yield _event("agent_step", {"step": "grounding", "content": f"Verifying facts (Score: {score:.2f})..."})
                        elif node_name == "citation_agent":
                            yield _event("agent_step", {"step": "citation", "content": "Extracting sources..."})

        except Exception as e:
            logger.error(f"[CHAT] Agent pipeline error: {e}", exc_info=True)
            yield _event("error", {"content": f"AI processing failed: {str(e)}"})
            return

        # Check for errors in the pipeline
        if result.get("error"):
            yield _event("error", {"content": result["error"]})
            return

        # ── STEP 6: Stream the response token-by-token ───────────
        # The agent pipeline returns the full response (non-streaming).
        # We simulate streaming by sending it in chunks for the UI effect.
        response_text = result.get("response_clean", result.get("response", ""))

        if not response_text:
            yield _event("error", {"content": "No response generated."})
            return

        # Emit agent info
        agent_name = result.get("agent_name", "unknown")
        intent = result.get("intent", "unknown")
        yield _event("agent_step", {
            "step": "generating",
            "agent": agent_name,
            "intent": intent,
            "content": f"Using {agent_name} agent..."
        })

        # Stream response in small chunks for a natural typing effect
        chunk_size = 12  # Characters per SSE event
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield _event("token", {"content": chunk})

        # ── STEP 7: Save to conversation memory ──────────────────
        session.add_user_message(question)
        session.add_assistant_message(response_text[:500])  # Truncate for memory

        # ── STEP 8: Send completion event with sources + metadata ─
        sources = result.get("sources", [])
        grounding_score = result.get("grounding_score", 0.0)

        yield _event("done", {
            "sources": sources,
            "metadata": {
                "agent": agent_name,
                "intent": intent,
                "grounding_score": round(grounding_score, 2),
                "is_grounded": result.get("is_grounded", False),
                "chunks_used": len(result.get("reranked_chunks", [])),
                "retrieval_method": result.get("retrieval_method", "unknown"),
            }
        })

    # ── STEP 9: Record metrics ────────────────────────────────
    metrics = RequestMetrics(
        doc_id=doc_id,
        question_length=len(question),
        intent=result.get("intent", "unknown"),
        total_latency_ms=total_timer.elapsed_ms,
        chunks_retrieved=len(result.get("retrieved_chunks", [])),
        chunks_after_rerank=len(result.get("reranked_chunks", [])),
        grounding_score=grounding_score,
        agent_name=agent_name,
        success=True,
    )
    metrics_collector.record(metrics)


async def _error_stream(message: str):
    """Yields a single error event."""
    yield _event("error", {"content": message})


def _event(event_type: str, data: dict) -> str:
    """Formats a Server-Sent Events message."""
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"

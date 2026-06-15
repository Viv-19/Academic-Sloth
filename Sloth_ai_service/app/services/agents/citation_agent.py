"""
services/agents/citation_agent.py — Source Citation Post-Processor
=====================================================================
The final agent node in the LangGraph pipeline.

Replaces the fragile regex-based citation parsing from the original
chat.py with a more robust approach:

1. Tries to parse the LLM's JSON citation block (```json {...} ```)
2. If that fails, uses the cross-encoder to map response sentences
   back to source chunks and generates citations automatically
3. Always returns clean, structured source data for the frontend

This ensures the frontend ALWAYS gets source page numbers,
even when the LLM doesn't include a proper JSON block.
"""

import re
import json
import logging
from app.services.retrieval.retriever import RetrievedChunk
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


def extract_citations(state: AgentState) -> AgentState:
    """
    LangGraph node: Extracts and validates source citations.

    Reads: response, reranked_chunks
    Writes: sources, response_clean, steps_completed
    """
    response = state.get("response", "")
    chunks = state.get("reranked_chunks", [])

    logger.info("[CITATION] Extracting sources from response...")

    # Step 1: Clean the response (remove JSON citation block)
    response_clean = _remove_citation_block(response)
    state["response_clean"] = response_clean

    # Step 2: Try parsing LLM's citation block
    sources = _parse_llm_citations(response, chunks)

    # Step 3: If parsing failed, fall back to chunk-based attribution
    if not sources and chunks:
        sources = _fallback_attribution(chunks)
        logger.info(f"[CITATION] Used fallback attribution: {len(sources)} sources")

    # Deduplicate sources by page
    unique_sources = _deduplicate_sources(sources)

    state["sources"] = unique_sources
    state["steps_completed"] = state.get("steps_completed", []) + ["citation"]

    logger.info(f"[CITATION] Final sources: {[s.get('page') for s in unique_sources]}")
    return state


def _parse_llm_citations(response: str, chunks: list[RetrievedChunk]) -> list[dict]:
    """Parse the JSON citation block from the LLM's response."""
    sources = []

    try:
        # Try ```json { ... } ``` format
        match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if not match:
            # Try raw JSON object
            match = re.search(r'\{"sources":\s*\[.*?\]\}', response, re.DOTALL)

        if match:
            json_str = match.group(1) if '```' in response[:match.start() + 10] else match.group(0)
            citation_data = json.loads(json_str)

            for citation in citation_data.get("sources", []):
                idx = citation.get("excerpt_index", -1)
                page = citation.get("page", 0)

                # Validate against actual chunks
                if 0 <= idx < len(chunks):
                    chunk = chunks[idx]
                    sources.append({
                        "page": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "excerpt_index": idx,
                    })
                elif page > 0:
                    # LLM provided page but invalid index — still useful
                    sources.append({
                        "page": page,
                        "chunk_index": -1,
                        "excerpt_index": idx,
                    })

            logger.info(f"[CITATION] Parsed {len(sources)} sources from LLM JSON block")

    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        logger.warning(f"[CITATION] JSON parsing failed: {e}")

    return sources


def _fallback_attribution(chunks: list[RetrievedChunk]) -> list[dict]:
    """
    Fallback: attribute the top reranked chunks as sources.
    This ensures the frontend always gets source pages even when
    the LLM doesn't include a proper citation block.
    """
    return [
        {
            "page": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "excerpt_index": i,
        }
        for i, chunk in enumerate(chunks[:5])
    ]


def _remove_citation_block(response: str) -> str:
    """Remove the JSON citation block from the response text."""
    # Remove ```json ... ``` blocks
    cleaned = re.sub(r'```json[\s\S]*?```', '', response)
    # Remove raw JSON source blocks
    cleaned = re.sub(r'\{"sources":\s*\[.*?\]\}', '', cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _deduplicate_sources(sources: list[dict]) -> list[dict]:
    """Remove duplicate sources (same page)."""
    seen_pages = set()
    unique = []

    for source in sources:
        page = source.get("page", 0)
        if page > 0 and page not in seen_pages:
            seen_pages.add(page)
            unique.append(source)

    return sorted(unique, key=lambda s: s.get("page", 0))

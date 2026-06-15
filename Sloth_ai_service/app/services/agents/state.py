"""
services/agents/state.py — LangGraph State Definition
========================================================
Defines the shared state that flows through the LangGraph
state machine. Every node reads and writes to this state.

This is the "data contract" between all agents in the graph.
"""

from typing import TypedDict, Annotated
from app.services.retrieval.retriever import RetrievedChunk


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through the LangGraph agent pipeline.

    Each agent node reads what it needs and writes its outputs.
    LangGraph automatically manages state transitions between nodes.
    """

    # ── Input (set at the start) ──────────────────────────────────────
    question: str                           # Original user question
    doc_id: str                             # Document being queried
    chat_history: list[dict]                # Previous conversation turns
    conversation_context: str               # Formatted history string

    # ── Router Output ─────────────────────────────────────────────────
    intent: str                             # Classified intent: factual/summary/deep_dive/compare/critique
    intent_confidence: float                # Router's confidence in classification (0-1)

    # ── Retrieval Output ──────────────────────────────────────────────
    retrieved_chunks: list[RetrievedChunk]  # Raw retrieval results
    reranked_chunks: list[RetrievedChunk]   # After cross-encoder re-ranking
    retrieval_method: str                   # "hybrid" or "vector"

    # ── Agent Output ──────────────────────────────────────────────────
    agent_name: str                         # Which specialized agent ran
    response: str                           # Full LLM response text
    response_clean: str                     # Response without JSON citation block

    # ── Grounding Output ──────────────────────────────────────────────
    grounding_score: float                  # 0.0-1.0 grounding quality
    is_grounded: bool                       # Whether response passed grounding check
    grounding_report: dict                  # Detailed grounding analysis

    # ── Citation Output ───────────────────────────────────────────────
    sources: list[dict]                     # Parsed source citations [{page, chunk_index, ...}]

    # ── Metadata ──────────────────────────────────────────────────────
    error: str | None                       # Error message if any step failed
    steps_completed: list[str]              # List of completed agent steps

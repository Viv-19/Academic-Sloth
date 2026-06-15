"""
services/agents/graph.py — LangGraph Compiled State Machine
==============================================================
This is the brain of the agentic system. It defines and compiles
the LangGraph StateGraph that orchestrates all agents.

GRAPH STRUCTURE:
    START
      ↓
    router_agent  →  Classify intent
      ↓ (conditional routing)
    ┌────────────────────────────────────────┐
    │ factual / summary / deep_dive /        │
    │ compare / critique                     │
    │ (one of the specialized agents runs)   │
    └────────────────────────────────────────┘
      ↓
    grounding_guard  →  Verify claims are grounded
      ↓
    citation_agent   →  Extract and validate sources
      ↓
    END

The graph is compiled ONCE at module load and reused for all requests.
LangGraph handles state transitions automatically — each node
reads what it needs from state and writes its outputs back.
"""

import logging
from langgraph.graph import StateGraph, END

from app.services.agents.state import AgentState
from app.services.agents.router_agent import route_query
from app.services.agents.factual_agent import run_factual_agent
from app.services.agents.summary_agent import run_summary_agent
from app.services.agents.deep_dive_agent import run_deep_dive_agent
from app.services.agents.compare_agent import run_compare_agent
from app.services.agents.critique_agent import run_critique_agent
from app.services.agents.conversational_agent import run_conversational_agent
from app.services.agents.citation_agent import extract_citations
from app.services.rag.grounding_guard import check_grounding
from app.core.config import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Grounding Guard Node
# ══════════════════════════════════════════════════════════════════

def run_grounding_guard(state: AgentState) -> AgentState:
    """
    LangGraph node: Checks if the generated response is grounded
    in the source chunks. Adds grounding metadata to the state.
    """
    # Conversational intent skips grounding
    if state.get("intent") == "conversational":
        return state

    response = state.get("response", "")
    chunks = state.get("reranked_chunks", [])

    if not response or not chunks:
        state["grounding_score"] = 0.0
        state["is_grounded"] = False
        state["grounding_report"] = {}
        state["steps_completed"] = state.get("steps_completed", []) + ["grounding"]
        return state

    result = check_grounding(response, chunks)

    state["grounding_score"] = result.grounding_score
    state["is_grounded"] = result.is_grounded
    state["grounding_report"] = {
        "total_claims": result.total_claims,
        "grounded_claims": result.grounded_claims,
        "flagged_claims": result.flagged_claims,
    }
    state["steps_completed"] = state.get("steps_completed", []) + ["grounding"]

    logger.info(
        f"[GRAPH] Grounding: {result.grounding_score:.2f} "
        f"({result.grounded_claims}/{result.total_claims} grounded)"
    )
    return state


# ══════════════════════════════════════════════════════════════════
# Conditional Routing Function
# ══════════════════════════════════════════════════════════════════

def route_to_agent(state: AgentState) -> str:
    """
    Conditional edge function: routes to the appropriate
    specialized agent based on the router's intent classification.
    """
    intent = state.get("intent", "factual")

    routing_map = {
        "factual": "factual_agent",
        "summary": "summary_agent",
        "deep_dive": "deep_dive_agent",
        "compare": "compare_agent",
        "critique": "critique_agent",
        "conversational": "conversational_agent",
    }

    target = routing_map.get(intent, "factual_agent")
    logger.info(f"[GRAPH] Routing to: {target} (intent={intent})")
    return target


# ══════════════════════════════════════════════════════════════════
# Build and Compile the Graph
# ══════════════════════════════════════════════════════════════════

def _build_graph() -> StateGraph:
    """
    Constructs the LangGraph StateGraph.
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ─────────────────────────────────────────────────
    graph.add_node("router", route_query)
    graph.add_node("factual_agent", run_factual_agent)
    graph.add_node("summary_agent", run_summary_agent)
    graph.add_node("deep_dive_agent", run_deep_dive_agent)
    graph.add_node("compare_agent", run_compare_agent)
    graph.add_node("critique_agent", run_critique_agent)
    graph.add_node("conversational_agent", run_conversational_agent)
    graph.add_node("grounding_guard", run_grounding_guard)
    graph.add_node("citation_agent", extract_citations)

    # ── Set Entry Point ───────────────────────────────────────────
    graph.set_entry_point("router")

    # ── Conditional Edge: Router → Specialized Agent ──────────────
    graph.add_conditional_edges(
        "router",
        route_to_agent,
        {
            "factual_agent": "factual_agent",
            "summary_agent": "summary_agent",
            "deep_dive_agent": "deep_dive_agent",
            "compare_agent": "compare_agent",
            "critique_agent": "critique_agent",
            "conversational_agent": "conversational_agent",
        },
    )

    # ── Linear Edges: Agent → Grounding → Citation → END ─────────
    for agent_node in ["factual_agent", "summary_agent", "deep_dive_agent", "compare_agent", "critique_agent"]:
        graph.add_edge(agent_node, "grounding_guard")

    # Conversational agent skips grounding and citations entirely!
    graph.add_edge("conversational_agent", END)

    graph.add_edge("grounding_guard", "citation_agent")
    graph.add_edge("citation_agent", END)

    return graph


def get_compiled_graph():
    """
    Returns the compiled LangGraph, building it if necessary.

    The graph is compiled once and cached. Compilation validates
    the graph structure (no dangling edges, valid state types, etc.)
    """
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("[GRAPH] Building and compiling LangGraph agent pipeline...")
        graph = _build_graph()
        _compiled_graph = graph.compile()
        logger.info("[GRAPH] ✅ Graph compiled successfully.")
    return _compiled_graph


# Module-level cache
_compiled_graph = None


def run_agent_pipeline(
    question: str,
    doc_id: str,
    chat_history: list[dict] | None = None,
    conversation_context: str = "",
) -> AgentState:
    """
    High-level entry point: runs the full agent pipeline for a question.

    This is what the chat endpoint calls instead of the old manual
    retrieve → rerank → generate flow.

    Args:
        question:             User's question
        doc_id:               Document ID
        chat_history:         Previous conversation turns
        conversation_context: Formatted history string

    Returns:
        Completed AgentState with response, sources, grounding score, etc.
    """
    graph = get_compiled_graph()

    initial_state: AgentState = {
        "question": question,
        "doc_id": doc_id,
        "chat_history": chat_history or [],
        "conversation_context": conversation_context,
        "steps_completed": [],
        "error": None,
    }

    logger.info(f"[GRAPH] ▶ Starting agent pipeline for doc={doc_id}")

    try:
        final_state = graph.invoke(initial_state)
        logger.info(
            f"[GRAPH] ✅ Pipeline complete. "
            f"Agent: {final_state.get('agent_name', '?')} | "
            f"Intent: {final_state.get('intent', '?')} | "
            f"Grounding: {final_state.get('grounding_score', 0):.2f} | "
            f"Sources: {len(final_state.get('sources', []))}"
        )
        return final_state

    except Exception as e:
        logger.error(f"[GRAPH] ❌ Pipeline failed: {e}", exc_info=True)
        return {
            **initial_state,
            "error": str(e),
            "response": f"An error occurred while processing your question: {str(e)}",
            "response_clean": f"An error occurred while processing your question: {str(e)}",
            "sources": [],
            "grounding_score": 0.0,
            "is_grounded": False,
        }

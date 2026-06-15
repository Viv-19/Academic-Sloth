"""
services/agents/compare_agent.py — Comparison/Contrast Agent
===============================================================
Handles comparison questions:
- "How does this compare to BERT?"
- "What's the difference between the proposed method and baseline?"
- "Advantages over previous approaches?"

This agent searches specifically for comparative content:
tables, benchmarks, baselines, ablation studies.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_llm
from app.services.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


def run_compare_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Generates structured comparisons.

    Uses targeted retrieval for comparison-related content
    (results tables, baselines, ablation studies).

    Reads: question, doc_id, conversation_context
    Writes: retrieved_chunks, reranked_chunks, response, agent_name, steps_completed
    """
    question = state["question"]
    doc_id = state["doc_id"]
    logger.info(f"[COMPARE] Processing: '{question[:60]}...'")

    # Multi-angle retrieval for comparisons
    queries = [
        question,
        f"comparison results baseline {question}",
        "experimental results comparison table benchmark performance",
    ]

    all_candidates = []
    seen_ids = set()

    for query in queries:
        candidates = hybrid_retrieve(doc_id, query)
        for chunk in candidates:
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                all_candidates.append(chunk)

    state["retrieved_chunks"] = all_candidates
    state["retrieval_method"] = "hybrid_comparison"

    if not all_candidates:
        state["response"] = "No comparison or benchmark data found in the paper."
        state["reranked_chunks"] = []
        state["agent_name"] = "compare"
        state["steps_completed"] = state.get("steps_completed", []) + ["compare_agent"]
        return state

    top_chunks = rerank_chunks(question, all_candidates)
    state["reranked_chunks"] = top_chunks

    # Generate comparison response
    conversation_context = state.get("conversation_context", "")
    prompt = build_rag_prompt(question, top_chunks, conversation_context, agent_type="compare")

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=(
            "You are an expert academic research assistant. Provide a clear, "
            "structured comparison. Use bullet points or a table format to "
            "highlight differences and similarities. Be specific with numbers "
            "and metrics when available."
        )),
        HumanMessage(content=prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "compare"
    state["steps_completed"] = state.get("steps_completed", []) + ["compare_agent"]

    logger.info(f"[COMPARE] Generated {len(response.content)} chars comparison")
    return state

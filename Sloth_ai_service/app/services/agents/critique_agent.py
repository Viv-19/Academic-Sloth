"""
services/agents/critique_agent.py — Critical Analysis Agent
===============================================================
Handles critical analysis questions:
- "What are the limitations of this paper?"
- "What could be improved?"
- "Any weaknesses in the methodology?"
- "What is the future work?"

Searches specifically for limitations, future work, and
discussion sections where authors typically acknowledge weaknesses.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_llm
from app.services.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


def run_critique_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Provides critical analysis of the paper.

    Targets limitation/discussion/conclusion sections specifically.

    Reads: question, doc_id, conversation_context
    Writes: retrieved_chunks, reranked_chunks, response, agent_name, steps_completed
    """
    question = state["question"]
    doc_id = state["doc_id"]
    logger.info(f"[CRITIQUE] Processing: '{question[:60]}...'")

    # Targeted retrieval for critical content
    queries = [
        question,
        "limitations weaknesses drawbacks of the proposed approach",
        "future work improvements potential extensions",
        "discussion challenges remaining issues",
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
    state["retrieval_method"] = "hybrid_critique"

    if not all_candidates:
        state["response"] = "No information about limitations or potential improvements was found in the paper."
        state["reranked_chunks"] = []
        state["agent_name"] = "critique"
        state["steps_completed"] = state.get("steps_completed", []) + ["critique_agent"]
        return state

    top_chunks = rerank_chunks(question, all_candidates)
    state["reranked_chunks"] = top_chunks

    # Generate critique response
    conversation_context = state.get("conversation_context", "")
    prompt = build_rag_prompt(question, top_chunks, conversation_context, agent_type="critique")

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=(
            "You are an expert academic research assistant providing critical analysis. "
            "Identify and explain: (1) Limitations explicitly mentioned by the authors, "
            "(2) Potential weaknesses in methodology, (3) Areas for improvement, "
            "(4) Future research directions. Be balanced and constructive."
        )),
        HumanMessage(content=prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "critique"
    state["steps_completed"] = state.get("steps_completed", []) + ["critique_agent"]

    logger.info(f"[CRITIQUE] Generated {len(response.content)} chars critical analysis")
    return state

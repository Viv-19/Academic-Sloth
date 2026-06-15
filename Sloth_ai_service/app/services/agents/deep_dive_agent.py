"""
services/agents/deep_dive_agent.py — Methodology Deep Dive Agent
===================================================================
Handles detailed technical questions:
- "Explain the attention mechanism in detail"
- "How does the training process work?"
- "Describe the model architecture"

This agent performs TWO-STAGE retrieval:
1. First retrieves broad context about the topic
2. Then drills into the specific details mentioned in those chunks

This gives more comprehensive technical explanations.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_llm
from app.services.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


def run_deep_dive_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Provides detailed technical explanations.

    Uses two-stage retrieval for depth:
    1. Broad retrieval with the original question
    2. Targeted follow-up retrieval on key concepts found in stage 1

    Reads: question, doc_id, conversation_context
    Writes: retrieved_chunks, reranked_chunks, response, agent_name, steps_completed
    """
    question = state["question"]
    doc_id = state["doc_id"]
    logger.info(f"[DEEP_DIVE] Processing: '{question[:60]}...'")

    # Stage 1: Broad retrieval
    candidates = hybrid_retrieve(doc_id, question)

    if not candidates:
        state["response"] = "No relevant technical content found in the paper."
        state["retrieved_chunks"] = []
        state["reranked_chunks"] = []
        state["agent_name"] = "deep_dive"
        state["steps_completed"] = state.get("steps_completed", []) + ["deep_dive_agent"]
        return state

    # Stage 2: Extract key terms from top results and do targeted retrieval
    top_initial = rerank_chunks(question, candidates)

    # Generate a follow-up query based on what we found
    key_terms = _extract_key_terms(top_initial[:3])
    if key_terms:
        follow_up_query = f"{question} {key_terms}"
        additional = hybrid_retrieve(doc_id, follow_up_query)

        # Merge results (deduplicate by chunk_id)
        seen_ids = {c.chunk_id for c in candidates}
        for chunk in additional:
            if chunk.chunk_id not in seen_ids:
                candidates.append(chunk)
                seen_ids.add(chunk.chunk_id)

    state["retrieved_chunks"] = candidates
    state["retrieval_method"] = "hybrid_two_stage"

    # Re-rank the expanded candidate set. We MUST include the key terms in the
    # rerank query, otherwise the Cross-Encoder will throw away highly technical 
    # chunks because they don't exactly match the user's simple question!
    rerank_query = f"{question} {key_terms} technical details architecture" if key_terms else f"{question} technical details architecture"
    top_chunks = rerank_chunks(rerank_query, candidates)

    # Deep dives get more chunks for comprehensive explanations
    extended_top_k = min(12, len(candidates))
    if len(top_chunks) < extended_top_k:
        remaining = [c for c in candidates if c not in top_chunks]
        top_chunks.extend(remaining[:extended_top_k - len(top_chunks)])

    state["reranked_chunks"] = top_chunks

    # Generate response
    conversation_context = state.get("conversation_context", "")
    prompt = build_rag_prompt(question, top_chunks, conversation_context, agent_type="deep_dive")

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=(
            "You are an expert academic research assistant. Provide a detailed, "
            "technical explanation of the topic. Be thorough and use precise "
            "terminology. Explain how things work step by step."
        )),
        HumanMessage(content=prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "deep_dive"
    state["steps_completed"] = state.get("steps_completed", []) + ["deep_dive_agent"]

    logger.info(f"[DEEP_DIVE] Generated {len(response.content)} chars from {len(top_chunks)} chunks (2-stage)")
    return state


def _extract_key_terms(chunks: list) -> str:
    """
    Extracts key technical terms from top chunks to use
    as follow-up search terms for stage 2 retrieval.
    """
    # Simple approach: extract capitalized multi-word terms and acronyms
    import re
    terms = set()

    for chunk in chunks:
        # Find acronyms (2+ uppercase letters)
        acronyms = re.findall(r'\b[A-Z]{2,}\b', chunk.text)
        terms.update(acronyms[:5])

        # Find capitalized phrases (likely proper nouns / technical terms)
        capitalized = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', chunk.text)
        terms.update(capitalized[:3])

    return " ".join(list(terms)[:8])

"""
services/agents/factual_agent.py — Factual Q&A Agent
=======================================================
Handles specific factual questions about the paper:
- "What accuracy did the model achieve?"
- "How many parameters does the model have?"
- "What dataset was used?"

This agent retrieves narrowly and answers precisely.
It always cites specific numbers, names, or findings.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_llm
from app.services.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.services.agents.state import AgentState

logger = logging.getLogger(__name__)


def run_factual_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Answers specific factual questions.

    Reads: question, doc_id, conversation_context
    Writes: retrieved_chunks, reranked_chunks, response, agent_name, steps_completed
    """
    question = state["question"]
    doc_id = state["doc_id"]
    logger.info(f"[FACTUAL] Processing: '{question[:60]}...'")

    # Retrieve relevant chunks
    candidates = hybrid_retrieve(doc_id, question)
    state["retrieved_chunks"] = candidates
    state["retrieval_method"] = "hybrid"

    if not candidates:
        state["response"] = "No relevant content found in the paper for your question."
        state["reranked_chunks"] = []
        state["agent_name"] = "factual"
        state["steps_completed"] = state.get("steps_completed", []) + ["factual_agent"]
        return state

    # Re-rank for precision
    top_chunks = rerank_chunks(question, candidates)
    state["reranked_chunks"] = top_chunks

    # Build prompt and generate response
    conversation_context = state.get("conversation_context", "")
    prompt = build_rag_prompt(question, top_chunks, conversation_context, agent_type="factual")

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="You are an expert academic research assistant. Answer factual questions precisely from the provided excerpts."),
        HumanMessage(content=prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "factual"
    state["steps_completed"] = state.get("steps_completed", []) + ["factual_agent"]

    logger.info(f"[FACTUAL] Generated {len(response.content)} chars response")
    return state

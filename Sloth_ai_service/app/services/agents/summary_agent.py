"""
services/agents/summary_agent.py — Paper Summarization Agent
================================================================
Handles summary and overview requests:
- "Summarize this paper"
- "What is this paper about?"
- "What are the key findings?"

This agent uses BROADER retrieval — it pulls from abstract,
introduction, and conclusion sections to build a comprehensive
overview rather than answering a narrow question.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.langchain_llm import get_llm
from app.services.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.reranking.reranker import rerank_chunks
from app.prompts.rag_prompt import build_rag_prompt
from app.services.agents.state import AgentState
from app.core.config import settings

logger = logging.getLogger(__name__)

# For summaries, we expand the retrieval to get broader coverage
SUMMARY_QUERIES = [
    "What is the main objective and contribution of this paper?",
    "What methodology and approach did the authors use?",
    "What are the key results and findings?",
    "What are the conclusions and future work?",
]


def run_summary_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: Generates a structured paper summary.

    Uses multi-query retrieval to cover all major sections.

    Reads: question, doc_id, conversation_context
    Writes: retrieved_chunks, reranked_chunks, response, agent_name, steps_completed
    """
    question = state["question"]
    doc_id = state["doc_id"]
    logger.info(f"[SUMMARY] Processing: '{question[:60]}...'")

    # Multi-query retrieval: search with multiple perspectives
    all_candidates = []
    seen_ids = set()

    for query in SUMMARY_QUERIES:
        candidates = hybrid_retrieve(doc_id, query)
        for chunk in candidates:
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                all_candidates.append(chunk)

    state["retrieved_chunks"] = all_candidates
    state["retrieval_method"] = "hybrid_multi_query"

    # Explicitly fetch Abstract (page 1, 2) and Conclusion (last page) to ensure full summary context
    try:
        from app.core.chromadb_client import get_or_create_collection
        from app.services.retrieval.retriever import RetrievedChunk
        collection = get_or_create_collection(doc_id)
        
        # Get all metadatas to find the max page
        all_data = collection.get(include=["metadatas"])
        if all_data["metadatas"]:
            max_page = max([m.get("page_number", 1) for m in all_data["metadatas"]])
            
            # Fetch chunks for page 1, 2, and max_page
            boundary_results = collection.get(
                where={"page_number": {"$in": [1, 2, max_page]}},
                include=["documents", "metadatas"]
            )
            
            if boundary_results and boundary_results["ids"]:
                for i in range(len(boundary_results["ids"])):
                    chunk_id = boundary_results["ids"][i]
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        all_candidates.append(RetrievedChunk(
                            chunk_id=chunk_id,
                            text=boundary_results["documents"][i],
                            page_number=boundary_results["metadatas"][i].get("page_number", 1),
                            chunk_index=boundary_results["metadatas"][i].get("chunk_index", 0),
                            similarity_score=0.8, # Artificial score to ensure it survives re-ranking
                        ))
                logger.info(f"[SUMMARY] Explicitly added boundary pages (1, 2, {max_page}). Total candidates: {len(all_candidates)}")
    except Exception as e:
        logger.warning(f"[SUMMARY] Failed to explicitly fetch boundary pages: {e}")

    if not all_candidates:
        state["response"] = "No content found in the paper for summarization."
        state["reranked_chunks"] = []
        state["agent_name"] = "summary"
        state["steps_completed"] = state.get("steps_completed", []) + ["summary_agent"]
        return state

    # For summaries, we DO NOT use the cross-encoder reranker because:
    # 1. It is too slow for 40+ chunks.
    # 2. Summaries need broad context, not highly precise narrow context.
    # We simply take the boundary pages (already appended) and the top hybrid results.
    
    # Sort candidates to ensure boundary pages (score=0.8) and top hybrid results are prioritized
    # We'll take up to 10 chunks to avoid blowing up the token budget.
    all_candidates.sort(key=lambda c: c.similarity_score, reverse=True)
    top_chunks = all_candidates[:10]

    state["reranked_chunks"] = top_chunks

    # Build prompt with summary-specific instructions
    conversation_context = state.get("conversation_context", "")
    prompt = build_rag_prompt(question, top_chunks, conversation_context, agent_type="summary")

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=(
            "You are an expert academic research assistant. Provide a comprehensive, "
            "well-structured summary of the research paper. Organize your response into: "
            "(1) Main Objective, (2) Methodology, (3) Key Results, (4) Conclusions."
        )),
        HumanMessage(content=prompt),
    ])

    state["response"] = response.content
    state["agent_name"] = "summary"
    state["steps_completed"] = state.get("steps_completed", []) + ["summary_agent"]

    logger.info(f"[SUMMARY] Generated {len(response.content)} chars response from {len(top_chunks)} chunks")
    return state

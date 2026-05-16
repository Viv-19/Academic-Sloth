"""
services/reranking/reranker.py — Phase C Step 2: Cross-Encoder Re-Ranking
===========================================================================
🎓 LEARNING: This is the step that separates basic RAG from production RAG.

WHY DO WE NEED RE-RANKING?
The vector similarity search (retriever.py) finds chunks that are 
*topically similar* to the question. But "similar topic" is not the same
as "directly answers the question".

Example:
  Question: "What BLEU score did the model achieve?"
  
  Bi-encoder retrieval might return chunks about:
  - [Score: 0.81] "We trained on WMT 2014 data..." (same topic, wrong answer)
  - [Score: 0.78] "Our model achieves 28.4 BLEU on English-German..." (the answer!)
  - [Score: 0.76] "Existing models score 26.3 BLEU..." (related but not the answer)

The bi-encoder doesn't compare the question and chunk TOGETHER —
it just checks if they're in the same neighborhood of vector space.

A CROSS-ENCODER re-ranker takes (question, chunk) as a PAIR and asks:
"Given this specific question, how relevant is this specific chunk?"
It reads both together and gives a much more accurate relevance score.

Result after re-ranking:
  - [Score: 0.94] "Our model achieves 28.4 BLEU..." ← now ranked #1!
  - [Score: 0.61] "Existing models score 26.3 BLEU..."
  - [Score: 0.23] "We trained on WMT 2014 data..."

The cross-encoder is slower (can't be pre-computed), but because we
only run it on ~15 candidates (not all chunks), it's fast enough.

MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
  - 22M parameters — tiny and fast
  - Runs fully locally — NO API KEY NEEDED
  - Trained on Microsoft's MS MARCO dataset (200M real search queries)
"""

import logging
from functools import lru_cache
from sentence_transformers import CrossEncoder
from app.services.retrieval.retriever import RetrievedChunk
from app.core.config import settings

logger = logging.getLogger(__name__)

# Name of the cross-encoder model to download from HuggingFace
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    """
    Loads the cross-encoder model (downloaded once, cached for all future calls).
    
    🎓 LEARNING: @lru_cache(maxsize=1) means this function's return value is
    cached after the first call. Every subsequent call returns the same model
    object without reloading it from disk. This is crucial — loading a ML model
    takes 2-5 seconds. We only want to pay that cost once at startup.
    
    This is the same singleton pattern we use for ChromaDB.
    """
    logger.info(f"[RERANKER] Loading cross-encoder model: {RERANKER_MODEL}")
    model = CrossEncoder(RERANKER_MODEL, max_length=512)
    logger.info("[RERANKER] Model loaded and cached.")
    return model


def rerank_chunks(question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """
    Re-scores and re-orders chunks using a cross-encoder model.
    Returns the top-K most relevant chunks (configured by TOP_K_RERANK in .env).
    
    Args:
        question: The user's question
        chunks:   Candidates from the bi-encoder retrieval step
    
    Returns:
        Top-K chunks re-ordered by cross-encoder relevance score (best first)
    """
    if not chunks:
        return []
    
    logger.info(f"[RERANKER] Re-ranking {len(chunks)} candidates for query: '{question[:50]}...'")
    
    reranker = _get_reranker()
    
    # Cross-encoder expects (question, passage) pairs
    # 🎓 LEARNING: This is called "pairwise" scoring — the model sees both
    # the question and each candidate together and scores their relevance.
    sentence_pairs = [(question, chunk.text) for chunk in chunks]
    
    # Predict returns a list of floats (raw logit scores, not 0-1 range)
    scores = reranker.predict(sentence_pairs)
    
    # Attach the new reranker score to each chunk and sort descending
    reranked = sorted(
        zip(scores, chunks),
        key=lambda x: x[0],
        reverse=True,
    )
    
    # Take only the top-K (e.g. top 5 out of 15)
    top_k = settings.TOP_K_RERANK
    top_chunks = [chunk for _, chunk in reranked[:top_k]]
    
    logger.info(
        f"[RERANKER] Kept top {len(top_chunks)} of {len(chunks)} chunks. "
        f"Best pages: {[c.page_number for c in top_chunks]}"
    )
    
    return top_chunks

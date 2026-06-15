"""
services/retrieval/hybrid_retriever.py — Hybrid BM25 + Vector Retrieval
=========================================================================
Production RAG improvement: Combines keyword-based (BM25) and
semantic (vector) retrieval using Reciprocal Rank Fusion (RRF).

WHY HYBRID?
- Pure vector search misses exact keyword matches
  ("BLEU score" might not surface the chunk containing that exact term)
- Pure keyword search misses semantic matches
  ("model performance" and "accuracy results" are the same meaning)
- Hybrid combines both strengths — this is what Pinecone, Cohere,
  and Weaviate all recommend for production RAG.

RECIPROCAL RANK FUSION (RRF):
- Each retriever returns a ranked list of results
- RRF score = Σ 1/(k + rank_i) across all retrievers
- k=60 is the standard constant (from the original RRF paper)
- This naturally balances results even when score scales differ
"""

import logging
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from app.core.chromadb_client import get_or_create_collection
from app.services.embeddings.embedder import embed_query
from app.services.retrieval.retriever import RetrievedChunk
from app.core.config import settings

logger = logging.getLogger(__name__)

# RRF constant (from the original paper by Cormack, Clarke & Büttner)
RRF_K = 60


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return text.lower().split()


def hybrid_retrieve(doc_id: str, question: str) -> list[RetrievedChunk]:
    """
    Performs hybrid retrieval: vector similarity + BM25 keyword search,
    fused using Reciprocal Rank Fusion (RRF).

    Flow:
        1. Vector search → top-K candidates (cosine similarity)
        2. BM25 keyword search → top-K candidates (term frequency)
        3. RRF fusion → combined ranked list
        4. Return top HYBRID_TOP_K candidates

    Args:
        doc_id:   Which paper's collection to search
        question: The user's raw question

    Returns:
        List of RetrievedChunk ordered by hybrid score (best first)
    """
    logger.info(f"[HYBRID] Starting hybrid retrieval for doc {doc_id}")

    collection = get_or_create_collection(doc_id)

    if collection.count() == 0:
        logger.warning(f"[HYBRID] Collection for doc {doc_id} is empty")
        return []

    # ── STEP 1: Vector retrieval ──────────────────────────────────────
    query_vector = embed_query(question)
    n_results = min(settings.TOP_K_RETRIEVE, collection.count())

    vector_results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    # Build vector chunks with rank
    vector_chunks: list[RetrievedChunk] = []
    for i in range(len(vector_results["ids"][0])):
        distance = vector_results["distances"][0][i]
        similarity = max(0.0, 1.0 - (distance / 2.0))

        vector_chunks.append(RetrievedChunk(
            chunk_id=vector_results["ids"][0][i],
            text=vector_results["documents"][0][i],
            page_number=vector_results["metadatas"][0][i].get("page_number", 0),
            chunk_index=vector_results["metadatas"][0][i].get("chunk_index", i),
            similarity_score=similarity,
        ))

    # ── STEP 2: BM25 keyword retrieval ────────────────────────────────
    # Fetch ALL documents from the collection for BM25 indexing
    # (ChromaDB doesn't support text search natively)
    all_docs = collection.get(include=["documents", "metadatas"])

    if not all_docs["documents"]:
        logger.warning("[HYBRID] No documents in collection for BM25")
        return vector_chunks[:settings.HYBRID_TOP_K]

    # Build BM25 index
    tokenized_corpus = [_tokenize(doc) for doc in all_docs["documents"]]
    bm25 = BM25Okapi(tokenized_corpus)

    # Score all documents
    query_tokens = _tokenize(question)
    bm25_scores = bm25.get_scores(query_tokens)

    # Build BM25 ranked list (sorted by score descending)
    bm25_ranked = sorted(
        enumerate(bm25_scores),
        key=lambda x: x[1],
        reverse=True,
    )[:n_results]

    bm25_chunks: list[RetrievedChunk] = []
    for idx, score in bm25_ranked:
        if score <= 0:
            continue
        metadata = all_docs["metadatas"][idx] if all_docs["metadatas"] else {}
        bm25_chunks.append(RetrievedChunk(
            chunk_id=all_docs["ids"][idx],
            text=all_docs["documents"][idx],
            page_number=metadata.get("page_number", 0),
            chunk_index=metadata.get("chunk_index", idx),
            similarity_score=score,  # BM25 score (not directly comparable to cosine)
        ))

    # ── STEP 3: Reciprocal Rank Fusion ────────────────────────────────
    fused = _reciprocal_rank_fusion(vector_chunks, bm25_chunks)

    logger.info(
        f"[HYBRID] Vector: {len(vector_chunks)} results, "
        f"BM25: {len(bm25_chunks)} results → "
        f"Fused: {len(fused)} candidates"
    )

    return fused[:settings.HYBRID_TOP_K]


def _reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """
    Fuses two ranked lists using Reciprocal Rank Fusion (RRF).

    RRF score for each document = Σ 1/(k + rank) across all lists.
    Higher RRF score = more relevant.

    We weight vector and BM25 results according to config.
    """
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}

    vector_weight = settings.VECTOR_WEIGHT
    bm25_weight = settings.BM25_WEIGHT

    # Score vector results
    for rank, chunk in enumerate(vector_results):
        score = vector_weight * (1.0 / (RRF_K + rank + 1))
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + score
        chunk_map[chunk.chunk_id] = chunk

    # Score BM25 results
    for rank, chunk in enumerate(bm25_results):
        score = bm25_weight * (1.0 / (RRF_K + rank + 1))
        rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0) + score
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    # Update similarity_score to the fused RRF score
    fused = []
    for cid in sorted_ids:
        chunk = chunk_map[cid]
        chunk.similarity_score = rrf_scores[cid]
        fused.append(chunk)

    return fused

"""
services/retrieval/retriever.py — Phase C Step 1: Vector Search
================================================================
🎓 LEARNING: This is where the magic of RAG begins at query time.

The flow:
  1. User asks: "What is the attention mechanism?"
  2. We convert that question to a 384-dimension vector (BGE model)
  3. ChromaDB finds the K chunks whose vectors are closest (cosine similarity)
  4. We return those chunks + their metadata (especially page_number!)

COSINE SIMILARITY:
  - Two identical texts → similarity = 1.0
  - Completely unrelated texts → similarity ≈ 0.0
  - ChromaDB returns distances (lower = more similar), we convert to scores.

The result of this step feeds directly into the re-ranker.
"""

import logging
from dataclasses import dataclass
from app.core.chromadb_client import get_or_create_collection
from app.services.embeddings.embedder import embed_query
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk retrieved from ChromaDB, ready for re-ranking."""
    chunk_id: str
    text: str
    page_number: int
    chunk_index: int
    similarity_score: float   # 0.0 to 1.0 (higher = more relevant)


def retrieve_chunks(doc_id: str, question: str) -> list[RetrievedChunk]:
    """
    Finds the top-K most semantically similar chunks to a question.
    
    🎓 LEARNING: This is called Approximate Nearest Neighbor (ANN) search.
    ChromaDB uses the HNSW (Hierarchical Navigable Small World) algorithm
    internally — it's like a graph-based shortcut system that finds similar
    vectors much faster than comparing against every single stored vector.
    This is why ChromaDB can search millions of vectors in milliseconds!
    
    Args:
        doc_id:   Which paper's collection to search
        question: The user's raw question
    
    Returns:
        List of RetrievedChunk ordered by similarity (best first)
    """
    logger.info(f"[RETRIEVER] Searching for '{question[:50]}...' in doc {doc_id}")
    
    # Step 1: Embed the question (must use same model as ingestion!)
    query_vector = embed_query(question)
    
    # Step 2: Get the ChromaDB collection for this document
    collection = get_or_create_collection(doc_id)
    
    if collection.count() == 0:
        logger.warning(f"[RETRIEVER] Collection for doc {doc_id} is empty — not yet indexed!")
        return []
    
    # Step 3: Query ChromaDB for top-K similar chunks
    # 🎓 LEARNING: n_results controls how many candidates we fetch.
    # We fetch MORE than we need (TOP_K_RETRIEVE=15) because the
    # re-ranker will then narrow it down to the best 5.
    # This "over-fetch then re-rank" pattern is key to production RAG quality.
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(settings.TOP_K_RETRIEVE, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    
    # Step 4: Convert ChromaDB results into our RetrievedChunk format
    chunks = []
    for i in range(len(results["ids"][0])):
        chunk_id = results["ids"][0][i]
        text = results["documents"][0][i]
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to a 0-1 similarity score: score = 1 - (distance / 2)
        similarity_score = max(0.0, 1.0 - (distance / 2.0))
        
        chunks.append(RetrievedChunk(
            chunk_id=chunk_id,
            text=text,
            page_number=metadata.get("page_number", 0),
            chunk_index=metadata.get("chunk_index", i),
            similarity_score=similarity_score,
        ))
    
    logger.info(
        f"[RETRIEVER] Found {len(chunks)} candidates. "
        f"Top score: {chunks[0].similarity_score:.3f}" if chunks else "[RETRIEVER] No results."
    )
    
    return chunks

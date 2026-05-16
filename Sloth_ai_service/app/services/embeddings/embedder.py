"""
services/embeddings/embedder.py — Local Embedding with sentence-transformers
=============================================================================
🎓 LEARNING: We switched from Google's embedding API to a LOCAL model.
Here's why this is actually BETTER for your use case:

BEFORE (Google text-embedding-004):
  ❌ Requires API key
  ❌ Network call for every embedding request (~200ms latency per batch)
  ❌ Rate limits (hits quota on large papers)
  ❌ Costs money at scale
  ✅ High quality 768-dim vectors

AFTER (BAAI/bge-small-en-v1.5, local):
  ✅ No API key needed
  ✅ Runs on your CPU in milliseconds (no network)
  ✅ No rate limits — embed as fast as your CPU allows
  ✅ Completely free forever
  ✅ 384-dim vectors — optimised for retrieval tasks (our exact use case)
  ✅ First run downloads ~130MB from HuggingFace, then cached forever

WHY BAAI/bge-small-en-v1.5?
  BGE = "BAAI General Embedding" by Beijing Academy of AI
  "small" = 384 dimensions (vs "large" = 1024 dims)
  It consistently ranks top-3 on MTEB (Massive Text Embedding Benchmark)
  for retrieval tasks, beating many larger models including some from OpenAI.

IMPORTANT NOTE ON SWITCHING MODELS:
  ⚠️ If you already indexed papers with the Google embedding model (768-dim),
  those ChromaDB collections are INCOMPATIBLE with this model (384-dim).
  You must delete the chroma_db folder and re-index your papers.
  Path: Sloth_ai_service/data/chroma_db/ — delete this folder.
  New embeddings will be created automatically when you open each paper.

ASYMMETRIC EMBEDDING:
  BGE is trained with asymmetric embeddings:
  - Documents: prefix with "Represent this passage for searching: "
  - Queries:   NO prefix (or use "Represent this question: ")
  This small difference can improve retrieval quality by ~3-5%.
"""

import logging
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logger = logging.getLogger(__name__)

# Batch size for local embedding — larger = faster but more RAM usage
# 32 is a safe default that works on machines with 8GB RAM
LOCAL_EMBEDDING_BATCH_SIZE = 32

# Prefix for document chunks (BGE asymmetric embedding pattern)
DOCUMENT_PREFIX = "Represent this passage for searching: "


@lru_cache(maxsize=1)
def _get_embedding_model() -> SentenceTransformer:
    """
    Loads the sentence-transformer model (downloaded once, cached forever).
    
    🎓 LEARNING: @lru_cache(maxsize=1) is the singleton pattern.
    Loading a ML model takes 2-5 seconds — we only pay this cost ONCE
    at startup. Every subsequent call returns the same already-loaded model.
    
    First ever run: downloads model from HuggingFace (~130MB)
    All subsequent runs: loads from local cache (~2 seconds)
    """
    logger.info(f"[EMBEDDER] Loading local embedding model: {settings.EMBEDDING_MODEL}")
    
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    dimension = model.get_sentence_embedding_dimension()
    logger.info(f"[EMBEDDER] ✅ Model loaded. Output dimension: {dimension}")
    
    return model


def embed_chunks(chunks: list) -> list[list[float]]:
    """
    Generates embedding vectors for a list of TextChunk objects.
    Runs entirely on local CPU — no API calls, no rate limits.
    
    🎓 LEARNING: SentenceTransformer.encode() is highly optimised:
    - Processes all texts in one efficient batch operation
    - Uses numpy for fast matrix operations
    - Returns numpy arrays, which we convert to Python lists for ChromaDB
    
    Args:
        chunks: List of TextChunk objects from the chunker
    
    Returns:
        List of embedding vectors (each is a list of 384 floats)
    """
    if not chunks:
        return []
    
    model = _get_embedding_model()
    
    # Apply the BGE document prefix for better retrieval performance
    texts = [DOCUMENT_PREFIX + chunk.text for chunk in chunks]
    
    logger.info(f"[EMBEDDER] Embedding {len(texts)} chunks locally (batch_size={LOCAL_EMBEDDING_BATCH_SIZE})...")
    
    # encode() returns a numpy array of shape (num_chunks, 384)
    # normalize_embeddings=True is recommended for cosine similarity search
    embeddings_np = model.encode(
        texts,
        batch_size=LOCAL_EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,    # Normalise to unit length for cosine similarity
        show_progress_bar=len(texts) > 50,  # Show progress bar only for large batches
    )
    
    # Convert numpy arrays to Python lists (ChromaDB requirement)
    embeddings = embeddings_np.tolist()
    
    logger.info(f"[EMBEDDER] ✅ Done. {len(embeddings)} vectors of dim={len(embeddings[0])}")
    return embeddings


def embed_query(question: str) -> list[float]:
    """
    Embeds a single user query for similarity search.
    No prefix for queries in BGE's asymmetric embedding design.
    
    🎓 LEARNING: Asymmetric embeddings = documents and queries are embedded
    differently (different prefixes). The model was trained this way, which
    makes query vectors optimised to "attract" relevant document vectors,
    even if they're phrased very differently.
    
    Returns:
        A single embedding vector (list of 384 floats)
    """
    model = _get_embedding_model()
    
    # Queries use no prefix (BGE asymmetric design)
    query_embedding = model.encode(
        question,
        normalize_embeddings=True,
    )
    
    return query_embedding.tolist()

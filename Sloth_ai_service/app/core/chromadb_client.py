"""
core/chromadb_client.py — Vector Database Connection
======================================================
🎓 LEARNING: ChromaDB is our vector database. Think of it like
MongoDB but instead of storing regular JSON documents, it stores
vectors (lists of floating-point numbers) and lets you search them
by mathematical similarity (cosine distance).

We create ONE client instance shared across the entire app.
This is important — creating a new DB connection on every request
would be slow and wasteful (same reason you don't re-require
Prisma on every Express request).
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from functools import lru_cache
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_chroma_client() -> chromadb.PersistentClient:
    """
    Returns a persistent ChromaDB client.
    
    🎓 LEARNING: PersistentClient saves data to disk, so your
    indexed documents survive server restarts. Compare this to
    chromadb.Client() which is in-memory only (data lost on restart).
    
    The path is set in your .env as CHROMA_PERSIST_DIR.
    """
    logger.info(f"Connecting to ChromaDB at: {settings.CHROMA_PERSIST_DIR}")
    
    client = chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=ChromaSettings(
            anonymized_telemetry=False  # Don't send usage data to Chroma
        )
    )
    return client


def get_or_create_collection(doc_id: str) -> chromadb.Collection:
    """
    Gets (or creates) a ChromaDB collection for a specific document.
    
    🎓 LEARNING: In ChromaDB, a "Collection" is a namespace for
    vectors. We create one collection per document, named by its
    database ID. This means when a user asks a question about
    Paper A, we ONLY search Paper A's collection, not all papers.
    This is called "namespace isolation" and keeps results relevant.
    
    Collection name format: "doc_{doc_id}" (e.g. "doc_cm4abc123")
    """
    client = get_chroma_client()
    collection_name = f"doc_{doc_id}".replace("-", "_")  # ChromaDB doesn't allow hyphens
    
    collection = client.get_or_create_collection(
        name=collection_name,
        # cosine is the standard similarity metric for text embeddings.
        # It measures the angle between two vectors (direction, not magnitude).
        metadata={"hnsw:space": "cosine"}
    )
    
    logger.info(f"Collection '{collection_name}' has {collection.count()} chunks.")
    return collection


def delete_collection(doc_id: str):
    """Deletes all vectors for a document. Used when a paper is removed."""
    client = get_chroma_client()
    collection_name = f"doc_{doc_id}".replace("-", "_")
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted collection for doc: {doc_id}")
    except Exception as e:
        logger.warning(f"Could not delete collection {collection_name}: {e}")

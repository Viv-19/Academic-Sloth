"""
pipelines/ingestion_pipeline.py — Full Ingestion Orchestrator
==============================================================
🎓 LEARNING: Two critical production engineering concepts here:

1. IDEMPOTENCY
   An operation is "idempotent" if calling it multiple times has the
   same effect as calling it once. Our ingestion endpoint is called:
   - When a user uploads a paper
   - If the frontend retries after a failure
   - Accidentally via double-click or network retry

   BAD (original code): always delete → chunk → embed → store
   ✅ GOOD (fixed code):  check if already indexed → skip if yes

   Skipping saves: 30+ seconds of Gemini API calls + API costs + latency.

2. SEPARATION OF CONCERNS
   Each function does exactly ONE thing:
     run_ingestion_pipeline()  — orchestrates the pipeline flow
     _is_already_indexed()     — checks ChromaDB (pure query, no side effects)
     _store_in_chromadb()      — handles ChromaDB write (isolated storage logic)
     _update_document_status() — handles the Node.js HTTP callback

   This mirrors the same pattern as our Node.js backend:
     controller = orchestrator (like run_ingestion_pipeline)
     service    = isolated logic (like _store_in_chromadb, _update_document_status)

   🎓 LEARNING: In Python FastAPI projects, you'll often see this split
   described as "router → service → repository" (same as route → controller → service).
   We don't add a separate "controller" layer because FastAPI's @router decorators
   are already minimal and readable — splitting further adds indirection without benefit.
"""

import logging
import httpx
from app.services.ingestion.pdf_extractor import extract_pdf
from app.services.chunking.semantic_chunker import chunk_document
from app.services.embeddings.embedder import embed_chunks
from app.core.chromadb_client import get_or_create_collection, delete_collection
from app.core.config import settings

logger = logging.getLogger(__name__)


async def run_ingestion_pipeline(doc_id: str, file_path: str, title: str) -> dict:
    """
    Runs the full ingestion pipeline for a single PDF document.

    ✅ IDEMPOTENT: If the document is already indexed in ChromaDB,
    we skip all expensive steps and return immediately.

    Flow:
        Check ChromaDB → already indexed? → return early (fast path)
                                           → not indexed? → extract → chunk → embed → store → notify
    """
    logger.info(f"[PIPELINE] ▶ Starting ingestion for doc_id={doc_id}, title='{title}'")

    try:
        # ─────────────────────────────────────────────────────────
        # GUARD CLAUSE: Check if this document is already indexed.
        #
        # 🎓 LEARNING: A "guard clause" exits a function early when
        # a precondition is met. This avoids deeply nested if-else blocks
        # and makes the "happy path" (the real logic) easier to read.
        #
        # This is the FIX for your observation:
        # We check ChromaDB FIRST — before any API calls or file I/O.
        # ChromaDB.count() is a simple local disk read — near-zero latency.
        # ─────────────────────────────────────────────────────────
        if _is_already_indexed(doc_id):
            logger.info(
                f"[PIPELINE] ⚡ Skipping — '{title}' is already indexed in ChromaDB. "
                f"No API calls made."
            )
            # Make sure Node.js status is in sync too (idempotent update)
            await _update_document_status(doc_id, "indexed")
            return {"status": "already_indexed", "doc_id": doc_id}

        # ─────────────────────────────────────────────
        # STEP 1: Extract text from PDF (page by page)
        # ─────────────────────────────────────────────
        logger.info("[PIPELINE] Step 1/4: Extracting PDF text...")
        extraction = extract_pdf(file_path, doc_id, title)
        logger.info(f"[PIPELINE] Step 1 done: {extraction.total_pages} pages extracted")

        # ─────────────────────────────────────────────
        # STEP 2: Split into semantic chunks
        # ─────────────────────────────────────────────
        logger.info("[PIPELINE] Step 2/4: Chunking text...")
        chunks = chunk_document(extraction)

        if not chunks:
            raise ValueError("No text chunks produced — PDF may be image-only or corrupt.")

        logger.info(f"[PIPELINE] Step 2 done: {len(chunks)} chunks created")

        # ─────────────────────────────────────────────
        # STEP 3: Generate embeddings for all chunks
        # (this is the expensive step — ~30s for a 15-page paper)
        # ─────────────────────────────────────────────
        logger.info("[PIPELINE] Step 3/4: Generating embeddings (local model)...")
        embeddings = embed_chunks(chunks)
        logger.info(f"[PIPELINE] Step 3 done: {len(embeddings)} embedding vectors generated")

        # ─────────────────────────────────────────────
        # STEP 4: Store everything in ChromaDB
        # ─────────────────────────────────────────────
        logger.info("[PIPELINE] Step 4/4: Storing vectors in ChromaDB...")
        chunk_count = _store_in_chromadb(doc_id, chunks, embeddings)
        logger.info(
            f"[PIPELINE] ✅ Ingestion complete for '{title}': "
            f"{chunk_count} chunks stored across {extraction.total_pages} pages"
        )

        # ─────────────────────────────────────────────
        # STEP 5: Notify Node.js to update document status
        # ─────────────────────────────────────────────
        await _update_document_status(doc_id, "indexed")

        return {
            "status": "success",
            "doc_id": doc_id,
            "chunk_count": chunk_count,
            "page_count": extraction.total_pages,
        }

    except Exception as e:
        logger.error(f"[PIPELINE] ❌ Ingestion failed for doc_id={doc_id}: {e}", exc_info=True)
        await _update_document_status(doc_id, "failed")
        raise


# ══════════════════════════════════════════════════════════════════
# PRIVATE HELPER FUNCTIONS
# Named with _ prefix to signal they are internal to this module.
# 🎓 LEARNING: This is Python's convention for "private" functions
# (there's no private keyword in Python — the underscore is a signal
# to other developers: "don't call this from outside this module").
# ══════════════════════════════════════════════════════════════════

def _is_already_indexed(doc_id: str) -> bool:
    """
    Checks if a document already has vectors in ChromaDB.

    🎓 LEARNING: collection.count() is a cheap local disk read —
    it does NOT call any API or load vectors into memory.
    It just reads the stored count from ChromaDB's metadata file.

    Returns True if the document has been indexed, False otherwise.
    """
    collection = get_or_create_collection(doc_id)
    count = collection.count()
    logger.info(f"[PIPELINE] ChromaDB check: doc {doc_id} has {count} existing chunks")
    return count > 0


def _store_in_chromadb(doc_id: str, chunks: list, embeddings: list) -> int:
    """
    Stores all chunk vectors in ChromaDB in a single batch write.

    🎓 LEARNING: We isolated this into its own function because:
    1. It has one clear job: write to storage
    2. It can be unit-tested independently
    3. If we ever swap ChromaDB for another vector DB (e.g. Pinecone),
       we only change THIS function — nothing else in the pipeline

    This is the "Repository Pattern" — abstracting storage behind a function.
    Same reason Node.js has a `documentService.js` instead of putting
    Prisma calls directly in the controller.

    Returns the number of chunks stored.
    """
    collection = get_or_create_collection(doc_id)

    # Prepare the 4 parallel lists ChromaDB requires in a single efficient pass
    ids = [chunk.chunk_id for chunk in chunks]
    documents = [chunk.text for chunk in chunks]
    metadatas = [
        {
            "doc_id": chunk.doc_id,
            "page_number": chunk.page_number,   # ← Key for frontend page highlighting!
            "chunk_index": chunk.chunk_index,
            "char_count": chunk.char_count,
        }
        for chunk in chunks
    ]

    # Single batch write — much faster than adding one chunk at a time
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    return len(chunks)


async def _update_document_status(doc_id: str, status: str):
    """
    Calls the Node.js backend to update the document status in Postgres.

    🎓 LEARNING: The Python service does NOT have direct DB access.
    It communicates back to Node.js via HTTP. This keeps each service's
    responsibility clean:
      - Node.js owns: database, authentication, file serving
      - Python owns:  AI/ML, embeddings, vector search

    Status transitions: 'pending' → 'indexed' ✅ | 'failed' ❌
    """
    url = f"{settings.BACKEND_URL}/api/documents/{doc_id}/status"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(url, json={"status": status})
        logger.info(f"[PIPELINE] Status updated to '{status}' for doc {doc_id}")
    except Exception as e:
        # Non-critical — ingestion succeeded even if the status callback fails
        logger.warning(f"[PIPELINE] Could not notify Node.js of status update: {e}")

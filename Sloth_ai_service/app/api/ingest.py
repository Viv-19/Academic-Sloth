"""
api/ingest.py — Document Ingestion Endpoint (Phase B — REAL IMPLEMENTATION)
=============================================================================
🎓 LEARNING: The endpoint pattern here is "Accept → Background → Notify".
This is the standard production pattern for long-running tasks:

  1. Client POSTs → we immediately return 202 Accepted ("I got it")
  2. The real work runs in a background thread (non-blocking)
  3. When done, the background task calls back to Node.js to update status

This means the user sees instant feedback ("indexing started") and the
heavy lifting happens silently in the background.
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
import logging

from app.pipelines.ingestion_pipeline import run_ingestion_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestRequest(BaseModel):
    doc_id: str       # The document's Postgres ID
    file_path: str    # Absolute path to the PDF on disk (e.g. C:\...\uploads\file.pdf)
    title: str        # Paper title (for logging)


class IngestResponse(BaseModel):
    status: str
    message: str
    doc_id: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Starts the ingestion pipeline for a PDF in the background.
    Returns immediately with 202 Accepted while processing continues.
    """
    logger.info(f"[INGEST] ▶ Queuing ingestion: doc_id={request.doc_id}, title='{request.title}'")
    
    # 🎓 LEARNING: BackgroundTasks.add_task() schedules the function to run
    # AFTER the HTTP response has been sent. The client gets their 202 response
    # instantly, and the pipeline runs in the background.
    # This is different from asyncio.create_task() which runs concurrently
    # with the current request handler — BackgroundTasks run after response.
    background_tasks.add_task(
        run_ingestion_pipeline,
        doc_id=request.doc_id,
        file_path=request.file_path,
        title=request.title,
    )
    
    return IngestResponse(
        status="accepted",
        message=f"Ingestion started for '{request.title}'. The paper will be ready to chat with shortly.",
        doc_id=request.doc_id,
    )

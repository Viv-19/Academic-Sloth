"""
api/health.py — Health Check Endpoint
=======================================
🎓 LEARNING: A /health endpoint is standard in EVERY production
service. It lets:
- Load balancers verify the service is alive
- Docker/Kubernetes know when to restart a crashed pod
- Developers quickly verify the service is running

Our Node.js backend will call this before routing any AI requests.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from app.core.chromadb_client import get_chroma_client
from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """
    🎓 LEARNING: Pydantic models define the SHAPE of our API responses.
    FastAPI uses them to auto-validate output AND auto-generate docs.
    """
    status: str
    message: str
    timestamp: str
    chromadb_connected: bool
    models: dict


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Returns the health status of the AI service and its dependencies.
    Visit http://localhost:8000/docs to see this in the auto-generated UI!
    """
    # Check if ChromaDB is reachable
    chroma_ok = False
    try:
        client = get_chroma_client()
        client.heartbeat()
        chroma_ok = True
    except Exception:
        chroma_ok = False

    return HealthResponse(
        status="healthy" if chroma_ok else "degraded",
        message="Academic Sloth AI Service is running.",
        timestamp=datetime.utcnow().isoformat(),
        chromadb_connected=chroma_ok,
        models={
            "llm_primary": settings.GROQ_PRIMARY_MODEL,
            "llm_fallback": settings.GROQ_FALLBACK_MODEL,
            "llm_keys": len(settings.groq_keys_list),
            "embedding": settings.EMBEDDING_MODEL,
        }
    )

"""
main.py — FastAPI Application Entry Point
==========================================
🎓 LEARNING: This is the heart of our Python service. It:
1. Creates the FastAPI app instance
2. Registers all route handlers (API endpoints)
3. Configures CORS so Node.js can call it
4. Starts up ChromaDB on app start

Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Import our route modules (we'll build these in Phase B and C)
from app.api import health, ingest, chat
from app.core.config import settings
from app.core.chromadb_client import get_chroma_client

# ============================================================
# Configure logging
# 🎓 LEARNING: Python's built-in logging module is how you
# print structured, level-filtered messages to the console.
# In production you'd send these to a service like Datadog.
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Lifespan Context Manager
# 🎓 LEARNING: FastAPI's `lifespan` replaces the old
# @app.on_event("startup") pattern. Code before `yield` runs
# on startup; code after `yield` runs on shutdown.
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info("🚀 Starting Academic Sloth AI Service...")

    # Verify ChromaDB
    client = get_chroma_client()
    logger.info(f"✅ ChromaDB connected. Heartbeat: {client.heartbeat()}")

    # Verify Groq key configuration
    key_count = len(settings.groq_keys_list)
    if key_count == 0:
        logger.error("❌ No Groq API keys configured! Add GROQ_API_KEYS to .env")
    else:
        logger.info(f"✅ Groq configured: {key_count} key(s) loaded")
        logger.info(f"✅ Primary model : {settings.GROQ_PRIMARY_MODEL}")
        logger.info(f"✅ Fallback model: {settings.GROQ_FALLBACK_MODEL}")

    logger.info(f"✅ Embedding model: {settings.EMBEDDING_MODEL} (local CPU)")
    logger.info(f"✅ Service running on http://{settings.AI_SERVICE_HOST}:{settings.AI_SERVICE_PORT}")
    logger.info("📖 Swagger docs at: http://localhost:8000/docs")
    yield
    # SHUTDOWN
    logger.info("🛑 Shutting down AI Service...")


# ============================================================
# Create the FastAPI Application
# ============================================================
app = FastAPI(
    title="Academic Sloth AI Service",
    description="Production-grade RAG pipeline for research paper analysis.",
    version="1.0.0",
    lifespan=lifespan,
    # Swagger UI is auto-generated at http://localhost:8000/docs
    # This is one of FastAPI's biggest advantages over Flask!
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================
# CORS Middleware
# 🎓 LEARNING: CORS (Cross-Origin Resource Sharing) controls
# which origins can call this API. We allow our Node.js backend
# (localhost:3000) to make requests. In production, you'd
# restrict this to your specific domain.
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Node.js backend
        "http://localhost:5500",   # VS Code Live Server (frontend dev)
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Mount Route Modules
# 🎓 LEARNING: `include_router` is FastAPI's way of splitting
# your API into separate files (like Express Router in Node.js).
# Each router has a prefix so the endpoints are namespaced.
# ============================================================
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(chat.router, prefix="/api", tags=["Chat / RAG"])

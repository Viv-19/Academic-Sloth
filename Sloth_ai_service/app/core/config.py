"""
core/config.py — Centralised Configuration
============================================
🎓 LEARNING: Pydantic's BaseSettings reads values from environment
variables and the .env file. Gives us:
1. Type safety — wrong types crash loudly on startup, not silently at runtime
2. A single source of truth — `settings` imported anywhere in the app
3. Easy switching between dev/staging/prod by swapping the .env file
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Groq LLM (free API, multiple keys for rotation) ---
    # Stored as a comma-separated string: "key1,key2,key3"
    # We parse this into a list in the property below.
    GROQ_API_KEYS: str = ""
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"

    # --- Local Embedding Model (no API key needed, runs on CPU) ---
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # --- Service Config ---
    AI_SERVICE_PORT: int = 8000
    AI_SERVICE_HOST: str = "0.0.0.0"

    # --- ChromaDB (local disk, zero cost) ---
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"

    # --- Backend ---
    BACKEND_URL: str = "http://localhost:3000"

    # --- RAG Tuning ---
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    TOP_K_RETRIEVE: int = 15
    TOP_K_RERANK: int = 5

    # --- Hybrid Retrieval (BM25 + Vector Fusion) ---
    BM25_WEIGHT: float = 0.4        # Weight for keyword-based BM25 retrieval
    VECTOR_WEIGHT: float = 0.6      # Weight for vector similarity retrieval
    HYBRID_TOP_K: int = 20          # Total candidates from hybrid retrieval before rerank

    # --- Conversation Memory ---
    CONVERSATION_WINDOW_SIZE: int = 10   # Number of turns to keep in sliding window

    # --- Grounding Guard ---
    GROUNDING_THRESHOLD: float = 0.3     # Min cross-encoder score for a claim to be "grounded"
    GROUNDING_ENABLED: bool = True       # Toggle grounding checks on/off

    # --- Agent Configuration (LangGraph) ---
    ROUTER_MODEL: str = ""               # Model for router agent (empty = use fallback model)
    AGENT_MODEL: str = ""                # Model for specialized agents (empty = use primary model)
    AGENT_MAX_STEPS: int = 5             # Max steps in the LangGraph state machine
    AGENT_ENABLED: bool = True           # Toggle agentic pipeline on/off (False = basic RAG)

    # --- Token Budgets ---
    MAX_CONTEXT_TOKENS: int = 4096       # Max tokens for context chunks in prompt
    MAX_QUESTION_LENGTH: int = 2000      # Max characters for user question

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def groq_keys_list(self) -> list[str]:
        """
        Parses the comma-separated GROQ_API_KEYS string into a clean list.
        Filters out empty strings in case of trailing commas.
        
        🎓 LEARNING: @property turns a method into an attribute you can
        access without calling it: settings.groq_keys_list (not settings.groq_keys_list())
        """
        return [k.strip() for k in self.GROQ_API_KEYS.split(",") if k.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

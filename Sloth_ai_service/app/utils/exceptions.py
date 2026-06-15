"""
utils/exceptions.py — Custom Exception Hierarchy
===================================================
Production-grade error handling with structured error codes.

Hierarchy:
    AcademicSlothError (base)
    ├── IngestionError     — PDF extraction, chunking, embedding failures
    ├── RetrievalError     — ChromaDB search, BM25 failures
    ├── LLMError           — Groq API, rate limits, generation failures
    ├── GroundingError     — Hallucination detected, grounding check failed
    ├── AgentError         — LangGraph agent routing/execution failures
    └── ConfigError        — Missing config, invalid settings
"""


class AcademicSlothError(Exception):
    """Base exception for all Academic Sloth AI service errors."""

    def __init__(self, message: str, error_code: str = "UNKNOWN", details: dict | None = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class IngestionError(AcademicSlothError):
    """Raised when the document ingestion pipeline fails."""

    def __init__(self, message: str, doc_id: str = "", details: dict | None = None):
        super().__init__(
            message=message,
            error_code="INGESTION_FAILED",
            details={"doc_id": doc_id, **(details or {})},
        )


class RetrievalError(AcademicSlothError):
    """Raised when chunk retrieval from the vector store fails."""

    def __init__(self, message: str, doc_id: str = "", details: dict | None = None):
        super().__init__(
            message=message,
            error_code="RETRIEVAL_FAILED",
            details={"doc_id": doc_id, **(details or {})},
        )


class LLMError(AcademicSlothError):
    """Raised when LLM generation fails (all keys exhausted, etc.)."""

    def __init__(self, message: str, model: str = "", details: dict | None = None):
        super().__init__(
            message=message,
            error_code="LLM_FAILED",
            details={"model": model, **(details or {})},
        )


class GroundingError(AcademicSlothError):
    """Raised when the grounding guard detects hallucinated content."""

    def __init__(self, message: str, confidence: float = 0.0, details: dict | None = None):
        super().__init__(
            message=message,
            error_code="GROUNDING_FAILED",
            details={"confidence": confidence, **(details or {})},
        )


class AgentError(AcademicSlothError):
    """Raised when a LangGraph agent fails to execute."""

    def __init__(self, message: str, agent_name: str = "", details: dict | None = None):
        super().__init__(
            message=message,
            error_code="AGENT_FAILED",
            details={"agent_name": agent_name, **(details or {})},
        )


class ConfigError(AcademicSlothError):
    """Raised when configuration is missing or invalid."""

    def __init__(self, message: str, param: str = "", details: dict | None = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details={"param": param, **(details or {})},
        )

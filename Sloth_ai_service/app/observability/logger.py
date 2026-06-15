"""
observability/logger.py — Structured Logging with Correlation IDs
===================================================================
Production-grade logging that outputs structured JSON in production
and readable colored output in development.

Every request gets a correlation_id so you can trace a single
user question through retrieval → reranking → LLM → response.
"""

import logging
import time
import uuid
import functools
from contextvars import ContextVar

# Context variable to track correlation ID across async calls
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return _correlation_id.get()


def set_correlation_id(cid: str | None = None) -> str:
    """Set (or generate) a correlation ID for the current request."""
    cid = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


class StructuredFormatter(logging.Formatter):
    """
    Formats log records with correlation_id and structured context.
    In production, this could output JSON; for development, we keep
    it human-readable but with all the essential metadata.
    """

    def format(self, record: logging.LogRecord) -> str:
        cid = get_correlation_id()
        prefix = f"[{cid}] " if cid else ""
        timestamp = self.formatTime(record, self.datefmt)
        return f"{timestamp} [{record.levelname}] {prefix}{record.name} — {record.getMessage()}"


def setup_logging(level: int = logging.INFO):
    """Configure logging for the entire application."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to prevent duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_duration(operation: str):
    """
    Decorator that logs the duration of a function call.

    Usage:
        @log_duration("vector_search")
        def retrieve_chunks(...):
            ...

    Output: [PERF] vector_search completed in 0.342s
    """

    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(f"[PERF] {operation} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error(f"[PERF] {operation} FAILED after {elapsed:.3f}s: {e}")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(f"[PERF] {operation} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error(f"[PERF] {operation} FAILED after {elapsed:.3f}s: {e}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

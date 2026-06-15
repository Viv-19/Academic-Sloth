"""
utils/retry.py — Retry Decorator + Circuit Breaker
=====================================================
Production patterns for resilient service calls.

RETRY: Automatically retries a function on transient failures
with exponential backoff (wait 1s, 2s, 4s, ...).

CIRCUIT BREAKER: After N consecutive failures, "opens" the circuit
and immediately raises for a cooldown period, preventing cascading
failures and wasted API calls.
"""

import time
import logging
import functools
from app.utils.exceptions import AcademicSlothError

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_retries:          Maximum number of retry attempts
        base_delay:           Initial delay in seconds (doubles each retry)
        max_delay:            Maximum delay cap in seconds
        retryable_exceptions: Tuple of exception types that trigger a retry

    Usage:
        @retry_with_backoff(max_retries=3, retryable_exceptions=(ConnectionError,))
        def call_external_service():
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): "
                            f"{e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


def async_retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
):
    """Async version of retry_with_backoff for async functions."""
    import asyncio

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): "
                            f"{e}. Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
        CLOSED  → Normal operation. Failures increment counter.
        OPEN    → Circuit tripped. All calls fail immediately for cooldown_seconds.
        HALF_OPEN → After cooldown, allows one test call. Success → CLOSED, Failure → OPEN.

    Usage:
        chroma_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=60)

        try:
            with chroma_breaker:
                result = chromadb_query(...)
        except CircuitBreakerOpen:
            return fallback_response()
    """

    class CircuitBreakerOpen(AcademicSlothError):
        def __init__(self, service_name: str, retry_after: float):
            super().__init__(
                message=f"Circuit breaker OPEN for '{service_name}'. Retry after {retry_after:.0f}s.",
                error_code="CIRCUIT_OPEN",
                details={"service_name": service_name, "retry_after": retry_after},
            )

    def __init__(self, service_name: str = "unknown", failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN

    def __enter__(self):
        if self._state == "OPEN":
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                # Try half-open
                self._state = "HALF_OPEN"
                logger.info(f"[CIRCUIT] {self.service_name}: HALF_OPEN — testing one call...")
            else:
                raise self.CircuitBreakerOpen(self.service_name, self.cooldown_seconds - elapsed)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success
            if self._state == "HALF_OPEN":
                logger.info(f"[CIRCUIT] {self.service_name}: CLOSED — service recovered.")
            self._state = "CLOSED"
            self._failure_count = 0
        else:
            # Failure
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
                logger.error(
                    f"[CIRCUIT] {self.service_name}: OPEN — {self._failure_count} consecutive failures. "
                    f"Blocking calls for {self.cooldown_seconds}s."
                )
            elif self._state == "HALF_OPEN":
                self._state = "OPEN"
                logger.warning(
                    f"[CIRCUIT] {self.service_name}: OPEN again — half-open test failed."
                )

        return False  # Don't suppress the exception

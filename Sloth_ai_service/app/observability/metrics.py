"""
observability/metrics.py — In-Memory Performance & Quality Metrics
====================================================================
Tracks key metrics for RAG pipeline health monitoring.
These metrics are exposed via the /api/health endpoint and logged
at the end of each request for production observability.

In a production deployment, these would be sent to Prometheus/Datadog.
For this project, we keep them in-memory and expose via health check.
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics captured for a single RAG request."""
    correlation_id: str = ""
    doc_id: str = ""
    question_length: int = 0
    intent: str = "unknown"
    retrieval_latency_ms: float = 0.0
    reranking_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    chunks_retrieved: int = 0
    chunks_after_rerank: int = 0
    tokens_used: int = 0
    grounding_score: float = 0.0
    agent_name: str = ""
    success: bool = True
    error: str = ""


class MetricsCollector:
    """
    Thread-safe metrics collector that maintains a sliding window
    of recent request metrics for health monitoring.
    """

    def __init__(self, window_size: int = 100):
        self._recent_requests: deque[RequestMetrics] = deque(maxlen=window_size)
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._lock = threading.Lock()

    def record(self, metrics: RequestMetrics):
        """Record metrics for a completed request."""
        with self._lock:
            self._recent_requests.append(metrics)
            self._total_requests += 1
            if not metrics.success:
                self._total_errors += 1

        logger.info(
            f"[METRICS] intent={metrics.intent} agent={metrics.agent_name} "
            f"retrieval={metrics.retrieval_latency_ms:.0f}ms "
            f"rerank={metrics.reranking_latency_ms:.0f}ms "
            f"llm={metrics.llm_latency_ms:.0f}ms "
            f"total={metrics.total_latency_ms:.0f}ms "
            f"chunks={metrics.chunks_retrieved}→{metrics.chunks_after_rerank} "
            f"grounding={metrics.grounding_score:.2f} "
            f"success={metrics.success}"
        )

    def get_summary(self) -> dict:
        """Returns a summary of recent performance metrics."""
        with self._lock:
            recent = list(self._recent_requests)

        if not recent:
            return {
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "recent_window": 0,
            }

        successful = [r for r in recent if r.success]
        avg_total = sum(r.total_latency_ms for r in successful) / len(successful) if successful else 0
        avg_retrieval = sum(r.retrieval_latency_ms for r in successful) / len(successful) if successful else 0
        avg_llm = sum(r.llm_latency_ms for r in successful) / len(successful) if successful else 0
        avg_grounding = sum(r.grounding_score for r in successful) / len(successful) if successful else 0

        # Intent distribution
        intent_counts = {}
        for r in recent:
            intent_counts[r.intent] = intent_counts.get(r.intent, 0) + 1

        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / max(self._total_requests, 1),
            "recent_window": len(recent),
            "avg_total_latency_ms": round(avg_total, 1),
            "avg_retrieval_latency_ms": round(avg_retrieval, 1),
            "avg_llm_latency_ms": round(avg_llm, 1),
            "avg_grounding_score": round(avg_grounding, 3),
            "intent_distribution": intent_counts,
        }


class Timer:
    """
    Simple context manager for timing operations.

    Usage:
        with Timer() as t:
            do_something()
        print(f"Took {t.elapsed_ms:.1f}ms")
    """

    def __init__(self):
        self.start_time = 0.0
        self.end_time = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000


# Module-level singleton
metrics_collector = MetricsCollector()

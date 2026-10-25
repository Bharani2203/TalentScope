"""Lightweight production Firestore read efficiency guard and instrumentation.

Tracks Firestore read operations, alerts/guards against broad/unbounded collection scans,
and records calculation reuse metrics without logging credentials or secrets.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Iterator

_request_reads: ContextVar[dict[str, int] | None] = ContextVar("firestore_request_reads", default=None)


class UnboundedFirestoreReadWarning(RuntimeWarning):
    """Raised/warned when an unbounded or broad full collection scan is attempted."""


class UnboundedFirestoreReadBlockedError(RuntimeError):
    """Raised when an unbounded collection scan is strictly blocked by guard configuration."""


@dataclass
class ReadMetrics:
    total_document_reads: int = 0
    reads_by_collection: dict[str, int] = field(default_factory=dict)
    targeted_queries: int = 0
    broad_scans_attempted: int = 0
    calculation_records_reused: int = 0
    cache_hits: int = 0


class FirestoreReadGuard:
    """Thread-safe instrumentation and safety guard for Firestore reads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics = ReadMetrics()
        self._guard_disabled = False

    @property
    def is_strict_guard_active(self) -> bool:
        """When STRICT_FIRESTORE_READ_GUARD is enabled, broad scans raise an error instead of warning."""
        return os.getenv("STRICT_FIRESTORE_READ_GUARD", "").lower() in {"1", "true", "yes"}

    def record_read(self, collection: str, count: int = 1, query_type: str = "targeted") -> None:
        """Single read-count wrapper used by Firestore stores and request logging."""
        if count <= 0:
            return
        with self._lock:
            self._metrics.total_document_reads += count
            self._metrics.reads_by_collection[collection] = (
                self._metrics.reads_by_collection.get(collection, 0) + count
            )
            if query_type.startswith("targeted"):
                self._metrics.targeted_queries += 1
        request_reads = _request_reads.get()
        if request_reads is not None:
            request_reads[collection] = request_reads.get(collection, 0) + count

    @contextmanager
    def track_request(self, route: str) -> Iterator[None]:
        """Aggregate wrapper-reported reads and log them only when explicitly enabled."""
        enabled = os.getenv("FIRESTORE_READ_LOG", "") == "1"
        if not enabled:
            yield
            return
        reads: dict[str, int] = {}
        token: Token[dict[str, int] | None] = _request_reads.set(reads)
        try:
            yield
        finally:
            if not reads:
                collection_label = "none"
                document_count = 0
            else:
                collection_label = ",".join(sorted(reads))
                document_count = sum(reads.values())
            print(
                f"firestore_request_reads route={route} collection={collection_label} documents_read={document_count}",
                flush=True,
            )
            _request_reads.reset(token)

    def record_cache_hit(self) -> None:
        with self._lock:
            self._metrics.cache_hits += 1

    def record_calculation_reuse(self) -> None:
        with self._lock:
            self._metrics.calculation_records_reused += 1

    def check_and_record_scan(self, collection: str, operation_name: str) -> None:
        """Invoked before full/unbounded collection scans to alert or block."""
        if self._guard_disabled:
            return
        with self._lock:
            self._metrics.broad_scans_attempted += 1

        msg = (
            f"[FIRESTORE_READ_GUARD] Broad/unbounded scan detected on collection '{collection}' "
            f"via operation '{operation_name}'. Target this query by skill_id, series_id, or range."
        )
        if self.is_strict_guard_active:
            raise UnboundedFirestoreReadBlockedError(msg)
        else:
            logger.warning(msg)

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_document_reads": self._metrics.total_document_reads,
                "reads_by_collection": dict(self._metrics.reads_by_collection),
                "targeted_queries": self._metrics.targeted_queries,
                "broad_scans_attempted": self._metrics.broad_scans_attempted,
                "calculation_records_reused": self._metrics.calculation_records_reused,
                "cache_hits": self._metrics.cache_hits,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._metrics = ReadMetrics()

    @contextmanager
    def bypass(self) -> Iterator[None]:
        """Temporarily bypass strict guard for authorized admin/reconciliation scripts."""
        prior = self._guard_disabled
        self._guard_disabled = True
        try:
            yield
        finally:
            self._guard_disabled = prior


# Global singleton instance
read_guard = FirestoreReadGuard()

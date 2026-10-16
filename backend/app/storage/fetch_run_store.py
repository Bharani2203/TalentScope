"""Firestore persistence for per-provider collection observability with caching and read efficiency."""

from __future__ import annotations

import os
import time
from typing import Any

from app.core.firebase import get_firestore_client
from app.storage.firestore_read_guard import read_guard
from firebase_admin import firestore


class FirestoreFetchRunStore:
    collection_name = "fetch_runs"

    def __init__(self, client: Any | None = None, ttl_seconds: float = 60.0):
        self.client = client
        self.ttl_seconds = ttl_seconds
        self._summary_cache: tuple[float, dict[str, Any]] | None = None
        self._run_cache: dict[str, dict[str, Any]] = {}

    def _collection(self):
        client = self.client
        if client is None:
            if os.getenv("RUN_LIVE_FIRESTORE_TESTS") != "1" and os.getenv("PYTEST_CURRENT_TEST"):
                from app.storage.mock_firestore_hub import get_mock_firestore_client
                client = get_mock_firestore_client()
            else:
                client = get_firestore_client()
        return client.collection(self.collection_name)

    def start(self, run_id: str, record: dict[str, Any]) -> None:
        self._collection().document(run_id).create(record)
        self._run_cache[run_id] = dict(record)
        self._summary_cache = None

    def finish(self, run_id: str, record: dict[str, Any]) -> None:
        self._collection().document(run_id).update(record)
        if run_id in self._run_cache:
            self._run_cache[run_id].update(record)
        else:
            self._run_cache[run_id] = dict(record)
        self._summary_cache = None

    def get(self, run_id: str) -> dict[str, Any] | None:
        if run_id in self._run_cache:
            read_guard.record_cache_hit()
            return dict(self._run_cache[run_id])

        snapshot = self._collection().document(run_id).get()
        read_guard.record_read(self.collection_name, 1, query_type="targeted")
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        if isinstance(data, dict):
            self._run_cache[run_id] = dict(data)
        return data

    def collection_summary(self, *, limit: int = 100) -> dict[str, Any]:
        """Summarize latest per-provider runs with short-lived TTL caching."""
        now_ts = time.time()
        if self._summary_cache is not None:
            ts, cached_summary = self._summary_cache
            if now_ts - ts < self.ttl_seconds:
                read_guard.record_cache_hit()
                return dict(cached_summary)

        snapshots = list(
            self._collection()
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(max(1, min(limit, 500)))
            .stream()
        )
        read_guard.record_read(self.collection_name, len(snapshots), query_type="targeted_summary")

        latest_by_source: dict[str, dict[str, Any]] = {}
        for snapshot in snapshots:
            record = snapshot.to_dict() or {}
            source = str(record.get("source") or "").casefold()
            if source and source not in latest_by_source:
                latest_by_source[source] = record

        statuses = {source: record.get("status") for source, record in latest_by_source.items()}
        latest_records = list(latest_by_source.values())
        latest_activity = max(
            (record.get("completed_at") or record.get("started_at") for record in latest_records),
            default=None,
        )
        status_values = set(statuses.values())
        if not status_values:
            aggregate = None
        elif "running" in status_values:
            aggregate = "running"
        elif status_values == {"failed"}:
            aggregate = "failed"
        elif "failed" in status_values or "partial" in status_values:
            aggregate = "partial"
        else:
            aggregate = "success"

        result = {
            "last_collection": {
                "status": aggregate,
                "latest_activity": latest_activity,
                "provider_statuses": statuses,
                "providers": latest_by_source,
            } if latest_by_source else None,
        }
        self._summary_cache = (now_ts, result)
        return result

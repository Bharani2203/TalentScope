"""Firestore persistence for per-provider collection observability with caching and read efficiency."""

from __future__ import annotations

import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.firebase import get_firestore_client
from app.storage.firestore_read_guard import read_guard
from firebase_admin import firestore


class SQLiteFetchRunStore:
    """Additive local run ledger sharing the existing skill-intelligence SQLite DB."""

    def __init__(self, database_path: str | Path):
        from app.storage.market_store import MarketDataStore

        self.market_store = MarketDataStore(database_path)

    @staticmethod
    def _iso(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

    @staticmethod
    def _dumps(value: dict[str, Any]) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
        )

    def start(self, run_id: str, record: dict[str, Any]) -> None:
        payload = dict(record)
        payload["started_at"] = self._iso(payload.get("started_at"))
        with self.market_store._connect() as connection:
            connection.execute(
                "INSERT INTO market_fetch_runs "
                "(run_id, collection_run_id, source, started_at, status, record_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id, str(payload.get("collection_run_id") or ""),
                    str(payload.get("source") or "").casefold(),
                    payload["started_at"], str(payload.get("status") or "running"),
                    self._dumps(payload),
                ),
            )

    def finish(self, run_id: str, record: dict[str, Any]) -> None:
        with self.market_store._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM market_fetch_runs WHERE run_id = ?", (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("Fetch run does not exist.")
            payload = json.loads(row["record_json"])
            payload.update(record)
            payload["completed_at"] = self._iso(payload.get("completed_at"))
            cursor = connection.execute(
                "UPDATE market_fetch_runs SET completed_at = ?, status = ?, record_json = ? "
                "WHERE run_id = ?",
                (
                    payload["completed_at"], str(payload.get("status") or "failed"),
                    self._dumps(payload), run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("Fetch run completion was not persisted.")

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.market_store._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM market_fetch_runs WHERE run_id = ?", (run_id,),
            ).fetchone()
        return json.loads(row["record_json"]) if row else None

    def collection_summary(self, *, limit: int = 100) -> dict[str, Any]:
        with self.market_store._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM market_fetch_runs ORDER BY started_at DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        latest_by_source: dict[str, dict[str, Any]] = {}
        for row in rows:
            record = json.loads(row["record_json"])
            source = str(record.get("source") or "").casefold()
            if source and source not in latest_by_source:
                latest_by_source[source] = record
        return {"last_collection": {"providers": latest_by_source} if latest_by_source else None}


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
            client = get_firestore_client()
        return client.collection(self.collection_name)

    def start(self, run_id: str, record: dict[str, Any]) -> None:
        document = self._collection().document(run_id)
        document.create(record)
        from app.intelligence_v2.source_registry import invalidate_platform_counts_cache
        invalidate_platform_counts_cache()
        snapshot = document.get()
        read_guard.record_read(self.collection_name, 1, query_type="targeted_readback")
        stored = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        if not isinstance(stored, dict) or any(stored.get(key) != value for key, value in record.items()):
            raise RuntimeError("Fetch-run start read-back verification failed.")
        self._run_cache[run_id] = dict(record)
        self._summary_cache = None

    def finish(self, run_id: str, record: dict[str, Any]) -> None:
        document = self._collection().document(run_id)
        document.update(record)
        from app.intelligence_v2.source_registry import invalidate_platform_counts_cache
        invalidate_platform_counts_cache()
        snapshot = document.get()
        read_guard.record_read(self.collection_name, 1, query_type="targeted_readback")
        stored = snapshot.to_dict() if getattr(snapshot, "exists", False) else None
        if not isinstance(stored, dict) or any(stored.get(key) != value for key, value in record.items()):
            raise RuntimeError("Fetch-run completion read-back verification failed.")
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
        elif "blocked" in status_values:
            aggregate = "failed"
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

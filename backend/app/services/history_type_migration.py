"""Auditable, idempotent history_type normalization for existing Firestore rows."""

from __future__ import annotations

from typing import Any

from app.core.firebase import get_firestore_client

OBSERVATION_COLLECTION = "skill_market_signals"
ALLOWED_HISTORY_TYPES = {"backfill", "platform_collected", "snapshot", "static_dataset"}
LEGACY_ALIASES = {"adoption_snapshot", "observed_signal"}


def deterministic_history_type(record: dict[str, Any]) -> str | None:
    current = record.get("history_type")
    source = str(record.get("source") or "").casefold()
    signal = record.get("signal_type")
    if current == "adoption_snapshot" and signal == "adoption":
        return "snapshot"
    if current == "observed_signal":
        if signal == "adoption":
            return "snapshot"
        if source in {"jsearch", "adzuna"} and signal == "demand":
            return "platform_collected"
        if source in {"stack_exchange", "stackexchange"} and signal == "interest":
            return "backfill"
    return None


def normalize_history_types(*, apply: bool = False, client=None) -> dict[str, int]:
    stats = {
        "total_scanned": 0,
        "already_normalized": 0,
        "legacy_aliases_found": 0,
        "normalized": 0,
        "would_normalize": 0,
        "withheld": 0,
        "unknown": 0,
        "failed": 0,
        "skipped": 0,
    }
    collection = (client or get_firestore_client()).collection(OBSERVATION_COLLECTION)
    try:
        documents = collection.stream()
        for snapshot in documents:
            stats["total_scanned"] += 1
            try:
                record = snapshot.to_dict() or {}
                current = record.get("history_type")
                if not record.get("source") or not record.get("signal_type") or not record.get("observed_at"):
                    stats["skipped"] += 1
                    continue
                if current in ALLOWED_HISTORY_TYPES:
                    stats["already_normalized"] += 1
                    continue
                if current in LEGACY_ALIASES:
                    stats["legacy_aliases_found"] += 1
                if not current:
                    stats["withheld"] += 1
                    continue
                target = deterministic_history_type(record)
                if target is None:
                    if current in LEGACY_ALIASES:
                        stats["withheld"] += 1
                    else:
                        stats["unknown"] += 1
                    continue
                stats["would_normalize"] += 1
                if apply:
                    collection.document(snapshot.id).update({"history_type": target})
                    stats["normalized"] += 1
            except Exception:
                stats["failed"] += 1
    except Exception:
        stats["failed"] += 1
    return stats

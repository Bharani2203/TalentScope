"""Read-after-write checks for the existing market persistence stores."""

from __future__ import annotations

import inspect
from datetime import timedelta, timezone
from typing import Any, Iterable

from app.analytics.skill_registry import canonical_skill_id, normalize_skill
from app.models.skill_intelligence import MarketObservation
from app.storage.observation_identity import stable_observation_id


class PersistenceVerificationError(RuntimeError):
    """Raised when a successful write cannot be confirmed through the reader."""


def verify_observation_readback(
    store: Any,
    observations: Iterable[MarketObservation],
) -> int:
    """Return verified stable record count or fail closed on incomplete readback."""
    rows = list(observations)
    if not rows:
        return 0
    reader = getattr(store, "get_observations", None)
    if not callable(reader):
        raise PersistenceVerificationError("Observation store has no read-back operation.")

    def signature(row: MarketObservation) -> tuple[Any, ...]:
        location = row.location.strip().casefold() if row.location else None
        skill_id = canonical_skill_id(row.skill) or normalize_skill(row.skill).casefold()
        return (
            row.source.casefold(), row.signal_type, row.period, location, row.scope,
            skill_id, row.posting_id, row.value, row.unit, row.denominator,
            row.denominator_unit, row.history_type, row.data_origin, row.series_id,
            row.query_id, row.panel_version,
        )

    expected: dict[str, tuple[Any, ...]] = {}
    for row in rows:
        record_id = stable_observation_id(row)
        record_signature = signature(row)
        if record_id in expected and expected[record_id] != record_signature:
            raise PersistenceVerificationError("Conflicting input records share a stable observation ID.")
        expected[record_id] = record_signature
    by_skill: dict[str, list[MarketObservation]] = {}
    for row in rows:
        by_skill.setdefault(row.skill, []).append(row)

    parameters = inspect.signature(reader).parameters
    verified: dict[str, tuple[Any, ...]] = {}
    for skill, skill_rows in by_skill.items():
        earliest = min(
            row.observed_at.replace(tzinfo=timezone.utc)
            if row.observed_at.tzinfo is None
            else row.observed_at.astimezone(timezone.utc)
            for row in skill_rows
        )
        kwargs: dict[str, Any] = {
            "skill": skill,
            "cutoff": earliest - timedelta(seconds=1),
        }
        if "use_cache" in parameters:
            kwargs["use_cache"] = False
        if "include_test" in parameters and any(
            row.data_origin == "test" for row in skill_rows
        ):
            kwargs["include_test"] = True
        stored_rows = reader(**kwargs)
        verified.update({
            stable_observation_id(item): signature(item)
            for item in stored_rows
            if isinstance(item, MarketObservation)
        })

    missing = set(expected) - set(verified)
    mismatched = {
        record_id for record_id in set(expected).intersection(verified)
        if expected[record_id] != verified[record_id]
    }
    if missing or mismatched:
        raise PersistenceVerificationError(
            "Observation read-back did not match the submitted stable records "
            f"(missing={len(missing)}, mismatched={len(mismatched)})."
        )
    return len(expected)

"""Central freshness policy for signals with a scheduled collection cadence.

The repository's documented collector cadence is once daily at 03:15 UTC.
Platform collected signals therefore receive a 48 hour freshness allowance:
one daily interval plus a full interval of operational grace for a missed or
delayed run. Backfills and non-periodically refreshed evidence are not aged by
this policy.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.models.skill_intelligence import MarketObservation

FRESHNESS_MAX_AGE = {
    ("demand", "platform_collected"): timedelta(hours=48),
    ("adoption", "snapshot"): timedelta(hours=48),
}


@dataclass(frozen=True)
class FreshnessAssessment:
    state: str
    fresh_count: int
    stale_count: int
    unknown_count: int
    excluded_count: int


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def assess_freshness(
    observations: Iterable[MarketObservation],
    *,
    now: datetime | None = None,
    collection_times_by_run: dict[str, datetime] | None = None,
) -> FreshnessAssessment:
    """Assess only evidence whose signal/history pair has a refresh cadence.

    Collection time (`created_at`) is preferred because provider publication
    dates can be old when a posting is collected. For legacy rows without it,
    Missing collection timestamps remain unknown; provider publication dates
    are not a safe substitute for collection time.
    """
    now_utc = _utc(now or datetime.now(timezone.utc))
    fresh = stale = unknown = excluded = 0
    applicable = 0
    for item in observations:
        max_age = FRESHNESS_MAX_AGE.get((item.signal_type, item.history_type))
        if max_age is None:
            excluded += 1
            continue
        applicable += 1
        timestamp = item.created_at or (collection_times_by_run or {}).get(item.fetch_run_id or "")
        if timestamp is None:
            unknown += 1
            continue
        age = now_utc - _utc(timestamp)
        if age <= max_age:
            fresh += 1
        else:
            stale += 1

    if not applicable:
        state = "insufficient_data"
    elif fresh and (stale or unknown):
        state = "partial"
    elif fresh:
        state = "ready"
    elif stale and not unknown:
        state = "stale"
    else:
        state = "building"
    return FreshnessAssessment(state, fresh, stale, unknown, excluded)

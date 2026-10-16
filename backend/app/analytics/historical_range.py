"""Shared upper bound for historical observation reads."""

from datetime import datetime, timedelta, timezone

MAX_HISTORICAL_RANGE_DAYS = 1825


def historical_cutoff(now: datetime, days: int) -> datetime:
    """Return a UTC cutoff for a caller-validated bounded history window."""
    if days < 1 or days > MAX_HISTORICAL_RANGE_DAYS:
        raise ValueError(f"Historical range must be between 1 and {MAX_HISTORICAL_RANGE_DAYS} days.")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc) - timedelta(days=days)

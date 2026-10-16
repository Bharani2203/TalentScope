"""Canonical parsing and display helpers for monthly observation periods."""
from __future__ import annotations

from datetime import date, datetime, timezone


def normalize_month_period(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    parts = text.split("-")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("Observation period must be YYYY-MM or legacy MM-YYYY.")
    if len(parts[0]) == 4:
        year, month = int(parts[0]), int(parts[1])
    elif len(parts[1]) == 4:
        month, year = int(parts[0]), int(parts[1])
    else:
        raise ValueError("Observation period must include a four-digit year.")
    if year < 1 or not 1 <= month <= 12:
        raise ValueError("Observation period contains an invalid year or month.")
    return f"{year:04d}-{month:02d}"


def is_completed_month(period: str, *, as_of: date | datetime | None = None) -> bool:
    canonical = normalize_month_period(period)
    if canonical is None:
        return False
    if as_of is None:
        as_of = datetime.now(timezone.utc).date()
    elif isinstance(as_of, datetime):
        as_of = as_of.date()
    current = f"{as_of.year:04d}-{as_of.month:02d}"
    return canonical < current


def format_month_period(period: str | None) -> str:
    canonical = normalize_month_period(period)
    if canonical is None:
        return "Unavailable"
    year, month = map(int, canonical.split("-"))
    return date(year, month, 1).strftime("%b %Y")

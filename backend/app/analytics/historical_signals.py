"""Source and eligibility helpers for the Historical Skill Signals feature."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


COUNTRY_CODES = {
    "india": "IN", "in": "IN", "united states": "US", "usa": "US", "us": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "gb": "GB",
    "canada": "CA", "ca": "CA", "australia": "AU", "au": "AU",
    "germany": "DE", "de": "DE", "france": "FR", "fr": "FR", "brazil": "BR", "br": "BR",
}

SOURCE_PATTERNS = (
    ("github_innovation_graph", re.compile(r"\b(?:github|innovation graph)\b", re.IGNORECASE)),
    ("stackexchange", re.compile(r"\b(?:stack\s*exchange|stackoverflow|stack\s*overflow)\b", re.IGNORECASE)),
    ("wikipedia", re.compile(r"\b(?:wikipedia|pageviews?)\b", re.IGNORECASE)),
    ("jsearch", re.compile(r"\bjsearch\b", re.IGNORECASE)),
    ("adzuna", re.compile(r"\badzuna\b", re.IGNORECASE)),
)

# Historical series are source contracts. Job providers currently store posting
# snapshots; they do not expose a stable, source-aggregated history series.
HISTORICAL_SOURCES = {
    "stackexchange": ("interest", "monthly", "questions"),
    "wikipedia": ("interest", "monthly", "pageviews"),
    "github_innovation_graph": ("adoption", "quarterly", None),
}


def historical_signal_context(
    message: str,
    *,
    location: str | None = None,
    filters: dict[str, Any] | None = None,
    selected_source: str | None = None,
) -> dict[str, str | None]:
    """Resolve explicit historical source/signal/geography without guessing a provider."""
    filters = filters or {}
    source = selected_source or filters.get("source") or filters.get("provider")
    ambiguous_source = False
    if not isinstance(source, str) or not source.strip():
        mentions = [name for name, pattern in SOURCE_PATTERNS if pattern.search(message)]
        ambiguous_source = len(mentions) > 1
        source = mentions[0] if len(mentions) == 1 else None
        if source is None and not ambiguous_source and re.search(
            r"\bdeveloper[\s-]+(?:adoption|activity)\b", message, re.IGNORECASE
        ):
            # This is the metric description used by the GitHub Innovation
            # Graph dataset. It is distinct from employer hiring demand.
            source = "github_innovation_graph"
    else:
        normalized = source.casefold().replace(" ", "").replace("_", "")
        aliases = {
            "github": "github_innovation_graph", "githubinnovationgraph": "github_innovation_graph",
            "stackoverflow": "stackexchange", "stackexchange": "stackexchange",
            "wikipedia": "wikipedia", "pageviews": "wikipedia",
            "jsearch": "jsearch", "adzuna": "adzuna",
        }
        source = aliases.get(normalized, source.strip().casefold())

    if source == "github_innovation_graph":
        signal_type = "adoption"
    elif source in {"stackexchange", "wikipedia"}:
        signal_type = "interest"
    elif source in {"jsearch", "adzuna"}:
        # Stored postings are point-in-time records, not a comparable historical
        # demand series. Keep the source identity so the answer can explain why.
        signal_type = "demand"
    else:
        signal_type = str(filters.get("signal_type") or "") or None
        if not signal_type:
            if re.search(r"\b(?:community|stackoverflow|stack\s*exchange|wikipedia|pageviews?)\b", message, re.IGNORECASE):
                signal_type = "interest"
            elif re.search(r"\b(?:hiring|job\s+postings?|demand)\b", message, re.IGNORECASE):
                signal_type = "demand"

    country = filters.get("country")
    location_value = location or filters.get("location")
    if not country and isinstance(location_value, str):
        country = COUNTRY_CODES.get(location_value.strip().casefold())
    if not country:
        for candidate, code in COUNTRY_CODES.items():
            if len(candidate) > 2 and re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", message, re.IGNORECASE):
                country = code
                break
    country = str(country).strip().upper() if country else None
    return {"source": source, "signal_type": signal_type, "country": country,
            "ambiguous_source": "true" if ambiguous_source else None}


def observation_is_eligible_history(observation: Any, *, now: datetime | None = None) -> bool:
    """Keep real, completed historical periods; reject snapshots and partial data."""
    if observation.history_type not in {"backfill", "backfilled", "platform_collected"}:
        return False
    if observation.data_origin != "real" or not observation.period:
        return False
    period = str(observation.period)
    current = now or datetime.now(timezone.utc)
    month = re.fullmatch(r"(\d{4})-(\d{2})", period)
    if month:
        year, month_number = (int(value) for value in month.groups())
        if month_number < 1 or month_number > 12 or (year, month_number) >= (current.year, current.month):
            return False
    else:
        quarter = re.fullmatch(r"(\d{4})-Q([1-4])", period)
        if not quarter:
            return False
        year, quarter_number = (int(value) for value in quarter.groups())
        current_quarter = (current.month - 1) // 3 + 1
        if (year, quarter_number) >= (current.year, current_quarter):
            return False

    quality = observation.quality
    if isinstance(quality, dict):
        if quality.get("collection_complete") is False or quality.get("pagination_complete") is False:
            return False
        if str(quality.get("coverage") or "").casefold() in {"incomplete", "partial", "unknown"}:
            return False
    expected = HISTORICAL_SOURCES.get(str(observation.source).casefold())
    if not expected or observation.signal_type != expected[0] or period_grain(period) != expected[1]:
        return False
    if expected[2] and observation.unit != expected[2]:
        return False
    return observation.value is not None


def period_grain(period: str | None) -> str | None:
    if isinstance(period, str) and re.fullmatch(r"\d{4}-\d{2}", period):
        return "monthly"
    if isinstance(period, str) and re.fullmatch(r"\d{4}-Q[1-4]", period):
        return "quarterly"
    return None


def historical_series_identity(observation: Any) -> tuple[str, ...]:
    """Identity fields that must agree before observations form one series."""
    return (
        str(observation.source).casefold(), str(observation.signal_type),
        str(observation.series_id or ""), str(observation.unit or ""),
        str(observation.query_id or ""), str(observation.panel_version or ""),
        str(observation.scope or ""), str(observation.location or "").casefold(),
        period_grain(observation.period) or "unknown",
    )


def missing_periods(observations: list[Any]) -> list[str]:
    """List gaps in one compatible monthly or quarterly observation sequence."""
    if not observations or len({historical_series_identity(item) for item in observations}) != 1:
        return []
    grain = period_grain(observations[0].period)
    if grain not in {"monthly", "quarterly"}:
        return []
    def index(period: str) -> int:
        if grain == "monthly":
            year, month = (int(value) for value in period.split("-"))
            return year * 12 + month - 1
        year, quarter = (int(value) for value in re.fullmatch(r"(\d{4})-Q([1-4])", period).groups())
        return year * 4 + quarter - 1
    def label(value: int) -> str:
        return f"{value // 12:04d}-{value % 12 + 1:02d}" if grain == "monthly" else f"{value // 4:04d}-Q{value % 4 + 1}"
    indexes = sorted({index(str(item.period)) for item in observations})
    return [label(value) for start, end in zip(indexes, indexes[1:]) for value in range(start + 1, end)]

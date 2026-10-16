from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.skill_intelligence import MarketObservation, MarketPosting


@dataclass(frozen=True)
class PostingFetchResult:
    postings: list[MarketPosting]
    records_fetched: int
    records_rejected: int = 0
    records_filtered: int = 0


@dataclass(frozen=True)
class ObservationFetchResult:
    observations: list[MarketObservation]
    records_fetched: int
    records_normalized: int
    records_rejected: int = 0
    http_status: int | None = None
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    rate_limit_reset: str | None = None
    authentication_status: str | None = None
    coverage_complete: bool = True


class MarketDataProvider(Protocol):
    name: str
    historical_backfill_supported: bool = False

    async def fetch_market_postings(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
    ) -> list[MarketPosting]:
        """Fetch source-specific postings and normalize them to a safe internal shape."""


class MarketObservationCollector(Protocol):
    name: str
    historical_backfill_supported: bool = False

    async def collect_observations(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
    ) -> list[MarketObservation]:
        """Return normalized observations without calculating market trends."""


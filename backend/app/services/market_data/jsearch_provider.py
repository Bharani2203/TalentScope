import hashlib
from datetime import datetime
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.models.skill_intelligence import MarketPosting, MarketObservation
from app.services.external_apis.jsearch_service import JSearchService
from app.services.market_data.base import MarketObservationCollector, PostingFetchResult
from app.services.market_data.job_observations import observations_from_postings


class JSearchProvider(MarketObservationCollector):
    name = "jsearch"
    historical_backfill_supported: bool = False

    def __init__(self, service: JSearchService | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.service = service or JSearchService(self.settings)

    async def fetch_market_postings(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
        fetch_run_id: str | None = None,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> list[MarketPosting]:
        result = await self.fetch_market_postings_with_stats(
            location=location,
            country=country,
            collected_at=collected_at,
            fetch_run_id=fetch_run_id,
            archive_response=archive_response,
        )
        return result.postings

    async def fetch_market_postings_with_stats(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
        fetch_run_id: str | None = None,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> PostingFetchResult:
        query = "software developer"
        if location:
            query = f"{query} in {location.strip()}"
        effective_country = country or self.settings.adzuna_country
        search_options = {
            "query": query,
            "country": effective_country,
            "num_pages": 1,
            "date_posted": "month",
        }
        if archive_response is not None:
            search_options["raw_response_callback"] = archive_response
        jobs, _ = await self.service.search_jobs(
            **search_options,
        )
        postings: list[MarketPosting] = []
        seen: set[str] = set()
        rejected = 0
        filtered = 0
        for job in jobs:
            posting_id = job.job_id or _fallback_id(job.model_dump(mode="json"))
            if not job.title:
                rejected += 1
                continue
            if posting_id in seen:
                filtered += 1
                continue
            seen.add(posting_id)
            postings.append(
                MarketPosting(
                    source=self.name,
                    posting_id=posting_id,
                    provider_job_id=job.job_id,
                    title=job.title,
                    description=job.description,
                    location=job.location or location,
                    skills=job.skills_raw or [],
                    company_name=job.company_name,
                    city=job.city,
                    region=job.region,
                    country=job.country,
                    country_code=(effective_country).lower(),
                    category=job.category,
                    source_url=job.source_url,
                    posted_at=job.posted_at,
                )
            )
        return PostingFetchResult(
            postings,
            records_fetched=len(jobs),
            records_rejected=rejected,
            records_filtered=filtered,
        )

    async def collect_observations(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
    ) -> list[MarketObservation]:
        postings = await self.fetch_market_postings(
            location=location,
            country=country,
            collected_at=collected_at,
        )
        return observations_from_postings(
            postings,
            location=location,
            country=country or self.settings.adzuna_country,
            collected_at=collected_at,
        )


def _fallback_id(record: dict[str, Any]) -> str:
    content = "|".join(str(record.get(key) or "") for key in ("title", "company_name", "posted_at"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

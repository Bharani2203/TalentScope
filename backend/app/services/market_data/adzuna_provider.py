import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any, Callable

import httpx

from app.core.config import Settings, get_settings
from app.services.external_apis.retry_after import safe_retry_after_seconds
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.market_data.base import MarketObservationCollector, PostingFetchResult
from app.services.market_data.job_observations import observations_from_postings


class AdzunaError(Exception):
    """Safe provider error without response payloads or credentials."""

    def __init__(self, message: str, *, category: str = "provider", retry_after: str | None = None):
        super().__init__(message)
        self.category = category
        self.retry_after = retry_after


class AdzunaProvider(MarketObservationCollector):
    name = "adzuna"
    historical_backfill_supported: bool = False
    base_url = "https://api.adzuna.com/v1/api/jobs"

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport

    async def fetch_market_postings(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
        fetch_run_id: str | None = None,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> list[MarketPosting]:
        return (await self.fetch_market_postings_with_stats(
            location=location, country=country, collected_at=collected_at,
        )).postings

    async def fetch_market_postings_with_stats(
        self,
        *,
        location: str | None,
        country: str | None,
        collected_at: datetime,
        fetch_run_id: str | None = None,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> PostingFetchResult:
        app_id = (self.settings.adzuna_app_id or "").strip()
        app_key = (self.settings.adzuna_app_key or "").strip()
        if not app_id or not app_key:
            raise AdzunaError("Adzuna is not configured.")
        country_code = (country or self.settings.adzuna_country).strip().lower()
        if not re.fullmatch(r"[a-z]{2}", country_code):
            raise AdzunaError("Adzuna requires a valid two-letter country code.")
        params: dict[str, str | int] = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 50,
            "what": "software developer",
            "content-type": "application/json",
        }
        if location:
            params["where"] = location.strip()
        timeout = httpx.Timeout(self.settings.adzuna_timeout_seconds)
        attempts = max(0, self.settings.adzuna_max_retries) + 1
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(
                        f"{self.base_url}/{country_code}/search/1",
                        params=params,
                    )
                except httpx.TimeoutException:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                        continue
                    raise AdzunaError("Adzuna request timed out.", category="network") from None
                except httpx.RequestError:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                        continue
                    raise AdzunaError("Adzuna could not be reached.", category="network") from None
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    retry_after = safe_retry_after_seconds(retry_after)
                    raise AdzunaError("Adzuna rate limit reached.", category="rate_limit", retry_after=retry_after)
                if (
                    response.status_code in {500, 502, 503, 504}
                    and not response.headers.get("Retry-After")
                    and attempt + 1 < attempts
                ):
                    await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                    continue
                if response.status_code in {401, 403}:
                    raise AdzunaError("Adzuna rejected the configured credentials.", category="authentication")
                if response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    retry_after = safe_retry_after_seconds(retry_after)
                    raise AdzunaError(
                        "Adzuna is temporarily unavailable.", category="server", retry_after=retry_after,
                    )
                if not response.is_success:
                    raise AdzunaError("Adzuna rejected the collection request.", category="http")
                break

        try:
            payload = response.json()
        except ValueError:
            raise AdzunaError("Adzuna returned invalid data.", category="schema") from None
        if archive_response is not None:
            archive_response(payload, response.headers.get("content-type"))
        records = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise AdzunaError("Adzuna returned an unexpected response structure.", category="schema")

        postings = []
        seen: set[str] = set()
        rejected = 0
        filtered = 0
        for record in records:
            if not isinstance(record, dict) or not _text(record.get("title")):
                rejected += 1
                continue
            posting_id = _text(record.get("id")) or _fallback_id(record)
            if posting_id in seen:
                filtered += 1
                continue
            seen.add(posting_id)
            location_record = record.get("location")
            area = location_record.get("area") if isinstance(location_record, dict) else None
            job_location = ", ".join(part for part in area if isinstance(part, str)) if isinstance(area, list) else None
            postings.append(MarketPosting(
                source=self.name,
                posting_id=posting_id,
                provider_job_id=_text(record.get("id")),
                title=_text(record.get("title")),
                description=_text(record.get("description")),
                location=job_location or location,
                skills=record.get("skills") if isinstance(record.get("skills"), list) else [],
                company_name=(record.get("company") or {}).get("display_name") if isinstance(record.get("company"), dict) else None,
                country=country_code.upper(),
                country_code=country_code,
                category=(record.get("category") or {}).get("label") if isinstance(record.get("category"), dict) else None,
                source_url=_text(record.get("redirect_url")),
                posted_at=_text(record.get("created")),
            ))
        return PostingFetchResult(
            postings, records_fetched=len(records), records_rejected=rejected, records_filtered=filtered,
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


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else str(value) if isinstance(value, int) else None


def _fallback_id(record: dict[str, Any]) -> str:
    job_location = record.get("location")
    location = ""
    if isinstance(job_location, dict) and isinstance(job_location.get("display_name"), str):
        location = job_location["display_name"]
    signature = "|".join((
        str(record.get("title") or ""),
        str(record.get("company", {}).get("display_name", "") if isinstance(record.get("company"), dict) else ""),
        location,
        str(record.get("created") or ""),
    ))
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()

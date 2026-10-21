"""Opt-in, bounded on-demand job search using the existing provider adapters."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.core.config import Settings, get_settings
from app.models.skill_intelligence import MarketPosting


@dataclass
class VerifiedJobSearchResult:
    status: str
    postings: list[MarketPosting] = field(default_factory=list)
    providers: dict[str, str] = field(default_factory=dict)
    rejected_count: int = 0
    unapplied_filters: list[str] = field(default_factory=list)
    error_categories: dict[str, str] = field(default_factory=dict)


def _provider_url_is_valid(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def search_configured_job_providers(
    *, query: str, country: str | None, location: str | None,
    date_posted: str | None = None, settings: Settings | None = None,
    providers: dict[str, Any] | None = None,
) -> VerifiedJobSearchResult:
    """Search only explicitly configured providers; tests must inject mocks.

    Results are transient and returned directly. Existing collection and
    Firestore persistence remain the separate scheduled/admin path.
    """
    if settings is None:
        if os.getenv("PYTEST_CURRENT_TEST") and not providers:
            return VerifiedJobSearchResult(status="unavailable", error_categories={"search": "offline_test_guard"})
        settings = get_settings()
    if not settings.job_search_live_enabled and not providers:
        return VerifiedJobSearchResult(status="unavailable", error_categories={"search": "disabled"})

    selected: dict[str, Any] = dict(providers or {})
    if not providers:
        if (settings.jsearch_api_key or "").strip():
            from app.services.market_data.jsearch_provider import JSearchProvider
            selected["jsearch"] = JSearchProvider(settings=settings)
        if (settings.adzuna_app_id or "").strip() and (settings.adzuna_app_key or "").strip():
            from app.services.market_data.adzuna_provider import AdzunaProvider
            selected["adzuna"] = AdzunaProvider(settings=settings)
    if not selected:
        return VerifiedJobSearchResult(status="unavailable", error_categories={"search": "not_configured"})

    async def fetch_all() -> VerifiedJobSearchResult:
        return await _fetch_providers(
            providers=selected, query=query, country=country, location=location,
            date_posted=date_posted, settings=settings,
        )

    return asyncio.run(fetch_all())


async def _fetch_providers(*, providers, query, country, location, date_posted, settings):
    now = datetime.now(timezone.utc)
    postings: list[MarketPosting] = []
    provider_statuses: dict[str, str] = {}
    errors: dict[str, str] = {}
    rejected = 0
    seen: set[tuple[str, str]] = set()
    unapplied: list[str] = []
    if date_posted and date_posted != "month":
        unapplied.append("date_posted (JSearch adapter is configured for month; Adzuna adapter has no date filter)")

    for name, provider in providers.items():
        key = name.casefold()
        try:
            kwargs = {"query": query, "country": country, "location": location, "collected_at": now}
            if key == "jsearch":
                kwargs["date_posted"] = "month"
            elif key == "adzuna":
                kwargs["result_limit"] = 50
            fetched = await provider.fetch_market_postings_with_stats(**kwargs)
            provider_statuses[key] = "success"
            for posting in fetched.postings:
                posting_id = posting.provider_job_id or posting.posting_id
                if not posting.title or not posting_id or not _provider_url_is_valid(posting.source_url):
                    rejected += 1
                    continue
                identity = (key, posting_id)
                if identity in seen:
                    continue
                seen.add(identity)
                postings.append(posting)
        except Exception as exc:
            provider_statuses[key] = "failed"
            category = getattr(exc, "category", None) or "provider"
            errors[key] = str(category)[:40]

    succeeded = sum(value == "success" for value in provider_statuses.values())
    failed = len(provider_statuses) - succeeded
    if succeeded and failed:
        status = "partial"
    elif failed:
        status = "unavailable"
    elif postings:
        status = "ready"
    else:
        status = "empty"
    return VerifiedJobSearchResult(
        status=status, postings=postings, providers=provider_statuses,
        rejected_count=rejected, unapplied_filters=unapplied,
        error_categories=errors,
    )

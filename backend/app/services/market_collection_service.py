import asyncio
import hashlib
import inspect
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.analytics.skill_registry import SKILL_REGISTRY_VERSION, canonical_skill_id
from app.core.config import Settings, get_settings
from app.models.skill_intelligence import (
    MarketCollectionResponse,
    MarketCollectionStatusResponse,
    MarketPosting,
    ProviderCollectionResult,
    ProviderCollectionStatus,
)
from app.services.market_data.adzuna_provider import AdzunaProvider
from app.services.market_data.base import MarketObservationCollector
from app.services.market_data.job_observations import EXTRACTOR_VERSION, observations_from_postings
from app.services.market_data.jsearch_provider import JSearchProvider
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.base import ObservationFetchResult, PostingFetchResult
from app.services.external_apis.github_service import GitHubError
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore
from app.storage.observation_identity import stable_observation_id
from app.storage.raw_response_archive import FirestoreRawResponseArchive
from app.services.job_storage_service import store_collected_market_jobs
from app.services.market_intelligence.persistence_verification import verify_observation_readback

KNOWN_PROVIDERS = ("JSearch", "Adzuna", "GitHub", "Stack Exchange", "Hacker News", "npm", "PyPI", "ILOSTAT")
PANEL_VERSION = "job-demand-v1"
RATE_LIMIT_COOLDOWN_FALLBACK_SECONDS = 60
logger = logging.getLogger(__name__)
OBSERVATION_CONTRACTS = {
    "jsearch": ("demand", "job_postings", "platform_collected"),
    "adzuna": ("demand", "job_postings", "platform_collected"),
    "github": ("adoption", "repositories", "snapshot"),
}
SUPPORTED_MARKET_PROVIDERS = frozenset(OBSERVATION_CONTRACTS)


class _ProviderCooldown(Exception):
    def __init__(self, provider_name: str, seconds: int):
        display_name = {"jsearch": "JSearch", "adzuna": "Adzuna", "github": "GitHub"}.get(
            provider_name.casefold(), provider_name,
        )
        super().__init__(f"{display_name} rate-limit cooldown is active.")
        self.category = "rate_limit"
        self.retry_after = str(seconds)


class _DryRunSink:
    """No-op persistence surface used to keep dry runs write-free."""

    def start(self, *_args, **_kwargs) -> None:
        return None

    def finish(self, *_args, **_kwargs) -> None:
        return None

    def insert_observations(self, *_args, **_kwargs) -> int:
        return 0

    def archive(self, *_args, **_kwargs) -> None:
        return None


class OfflineFixtureProvider:
    """Safe offline provider that returns local fixture postings without network access."""

    def __init__(self, name: str = "adzuna"):
        self.name = name
        self.historical_backfill_supported = False

    async def fetch_market_postings_with_stats(
        self,
        *,
        location: str | None = None,
        country: str | None = None,
        collected_at: datetime | None = None,
        fetch_run_id: str | None = None,
        archive_response: Any = None,
        query: str = "software developer",
        result_limit: int | None = None,
    ) -> PostingFetchResult:
        now = collected_at or datetime.now(timezone.utc)
        postings = [
            MarketPosting(
                source=self.name,
                posting_id=f"offline-fixture-{self.name}-1",
                provider_job_id=f"offline-fixture-{self.name}-1",
                title="Senior Python Backend Engineer",
                description="Experience with Python, FastAPI, and PostgreSQL required.",
                company_name="Synthetic Test Corp",
                location=location or "Chennai",
                country=country or "in",
                skills=["Python", "FastAPI", "PostgreSQL"],
                posted_at=(now - timedelta(days=2)).isoformat(),
            ),
            MarketPosting(
                source=self.name,
                posting_id=f"offline-fixture-{self.name}-2",
                provider_job_id=f"offline-fixture-{self.name}-2",
                title="Fullstack React Developer",
                description="Frontend development using React, TypeScript, and Node.js.",
                company_name="Synthetic Test Corp",
                location=location or "Chennai",
                country=country or "in",
                skills=["React", "TypeScript", "JavaScript"],
                posted_at=(now - timedelta(days=5)).isoformat(),
            ),
        ]
        if archive_response and callable(archive_response):
            archive_response({"offline_fixture": True, "count": len(postings)})
        return PostingFetchResult(
            postings=postings,
            records_fetched=len(postings),
            records_rejected=0,
            records_filtered=0,
            requested_page_count=1,
            page_size_limit=result_limit or 10,
            provider_total_count=len(postings),
            pagination_complete=True,
            zero_results_verified=False,
            sampling_frame="offline_mock_fixture",
        )


def configured_market_providers(
    settings: Settings | None = None,
) -> list[MarketObservationCollector]:
    settings = settings or get_settings()
    enabled = {
        name.strip().casefold()
        for name in settings.market_collection_enabled_providers
    }
    unsupported = sorted(enabled - SUPPORTED_MARKET_PROVIDERS)
    if unsupported:
        raise ValueError(
            "Unsupported market collection provider(s): " + ", ".join(unsupported)
        )

    providers: list[MarketObservationCollector] = []
    if "jsearch" in enabled and (settings.jsearch_api_key or "").strip():
        providers.append(JSearchProvider(settings=settings))
    if (
        "adzuna" in enabled
        and (settings.adzuna_app_id or "").strip()
        and (settings.adzuna_app_key or "").strip()
    ):
        providers.append(AdzunaProvider(settings=settings))
    if "github" in enabled and (settings.github_token or "").strip():
        providers.append(GitHubProvider(settings=settings))
    return providers


def pending_market_sources(settings: Settings | None = None) -> list[str]:
    configured = {provider.name for provider in configured_market_providers(settings)}
    return [name for name in KNOWN_PROVIDERS if name.casefold() not in configured]


def _safe_provider_error(provider_name: str, error: Exception) -> str:
    display_name = {"jsearch": "JSearch", "adzuna": "Adzuna", "github": "GitHub"}.get(
        provider_name.casefold(),
        provider_name,
    )
    return f"{display_name} collection failed."


def _observation_backend_name(store: Any, *, dry_run: bool) -> str:
    if dry_run:
        return "dry_run"
    if isinstance(store, MarketDataStore):
        return "sqlite"
    if isinstance(store, FirestoreObservationStore):
        return "firestore"
    return "injected"


def _query_id(
    provider: MarketObservationCollector, location: str | None, country: str | None,
    query: str = "software developer", result_limit: int | None = None,
    panel_version: str | None = None,
) -> str:
    provider_settings = getattr(provider, "settings", None)
    is_github = provider.name.casefold() == "github"
    effective_country = None if is_github else country or getattr(provider_settings, "adzuna_country", None)
    query_descriptor = (
        {
            "topic": getattr(provider_settings, "github_topic", "python"),
            "metric": "repository-topic-count",
            "pagination": "single_snapshot",
        }
        if provider.name.casefold() == "github"
        else {
            "query": query.strip().casefold(),
            "period": "month",
            "pagination": (
                {"strategy": "single_page", "page": 1, "page_size": result_limit or 50}
                if provider.name.casefold() == "adzuna"
                else {"strategy": "single_page", "page": 1, "date_posted": "month"}
            ),
            "sorting": "provider_default",
            "date_basis": "provider_current_search_window",
            "deduplication": "provider_id_or_stable_posting_identity-v1",
            "skill_registry_version": SKILL_REGISTRY_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "metric_definition": "per_posting_canonical_skill_match-v1",
            "period_granularity": "calendar_month_utc",
        }
    )
    descriptor = json.dumps({
        "source": provider.name.casefold(),
        "panel_version": panel_version or PANEL_VERSION,
        **query_descriptor,
        "location": location.strip().casefold() if location and not is_github else None,
        "country": effective_country.casefold() if effective_country else None,
    }, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()[:20]
    return f"{provider.name.casefold()}:{digest}"


def _skill_posting_counts(observations: list[Any]) -> dict[str, int]:
    """Count distinct matched postings for each canonical skill in one provider run."""
    postings_by_skill: dict[str, set[str]] = {}
    for observation in observations:
        skill_id = observation.skill_id or canonical_skill_id(observation.skill)
        if not skill_id or not observation.posting_id:
            continue
        postings_by_skill.setdefault(skill_id, set()).add(observation.posting_id)
    return {skill_id: len(posting_ids) for skill_id, posting_ids in sorted(postings_by_skill.items())}


def _cooldown_remaining(run: dict | None, now: datetime) -> int:
    if not run or run.get("error_category") != "rate_limit":
        return 0
    try:
        seconds = int(run.get("retry_after_seconds"))
        completed_at = run.get("completed_at") or run.get("started_at")
    except (TypeError, ValueError):
        return 0
    if not isinstance(completed_at, datetime):
        return 0
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    retry_at = completed_at.astimezone(timezone.utc) + timedelta(seconds=max(0, min(seconds, 86400)))
    return max(0, int((retry_at - now).total_seconds() + 0.999))


async def _collect_provider(
    provider, *, location, country, collected_at, fetch_run_id=None, query_id=None,
    panel_version=None, archive_response=None, query="software developer", result_limit=None,
):
    fetch_with_stats = getattr(provider, "fetch_market_postings_with_stats", None)
    if callable(fetch_with_stats):
        fetch_kwargs = dict(
            location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, archive_response=archive_response,
        )
        parameters = inspect.signature(fetch_with_stats).parameters
        accepts_extra = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if provider.name.casefold() in {"jsearch", "adzuna"} and ("query" in parameters or accepts_extra):
            fetch_kwargs["query"] = query
            if result_limit is not None and provider.name.casefold() == "adzuna" and (
                "result_limit" in parameters or accepts_extra
            ):
                fetch_kwargs["result_limit"] = result_limit
        batch: PostingFetchResult = await fetch_with_stats(**fetch_kwargs)
        observations = observations_from_postings(
            batch.postings, location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, query_id=query_id, panel_version=panel_version,
        )
        return (batch.records_fetched, len(batch.postings), batch.records_rejected, batch.records_filtered,
                batch.postings, observations, True, {
                    "requested_page_count": batch.requested_page_count,
                    "page_size_limit": batch.page_size_limit,
                    "provider_total_count": batch.provider_total_count,
                    "pagination_complete": batch.pagination_complete,
                    "zero_results_verified": batch.zero_results_verified,
                    "sampling_frame": batch.sampling_frame,
                })
    fetch_postings = getattr(provider, "fetch_market_postings", None)
    if callable(fetch_postings):
        postings = await fetch_postings(
            location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, archive_response=archive_response,
        )
        observations = observations_from_postings(
            postings, location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, query_id=query_id, panel_version=panel_version,
        )
        return len(postings), len(postings), 0, 0, postings, observations, True, {}
    collect_with_stats = getattr(provider, "collect_observations_with_stats", None)
    if callable(collect_with_stats):
        batch: ObservationFetchResult = await collect_with_stats(
            location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, query_id=query_id, panel_version=panel_version,
            archive_response=archive_response,
        )
        return (batch.records_fetched, batch.records_normalized, batch.records_rejected, 0,
                batch.observations, batch.observations, False, {
                    "http_status": batch.http_status,
                    "rate_limit_remaining": batch.rate_limit_remaining,
                    "rate_limit_limit": batch.rate_limit_limit,
                    "rate_limit_reset": batch.rate_limit_reset,
                    "authentication_status": batch.authentication_status,
                    "coverage_complete": batch.coverage_complete,
                })
    observations = await provider.collect_observations(
        location=location, country=country, collected_at=collected_at,
        fetch_run_id=fetch_run_id, archive_response=archive_response,
    )
    return len(observations), len(observations), 0, 0, observations, observations, False, {}


async def collect_market_data(
    *,
    location: str | None = None,
    country: str | None = None,
    settings: Settings | None = None,
    store=None,
    providers: list[MarketObservationCollector] | None = None,
    fetch_run_store: FirestoreFetchRunStore | None = None,
    observation_store: FirestoreObservationStore | None = None,
    raw_response_archive: FirestoreRawResponseArchive | None = None,
    dry_run: bool = False,
    offline_test: bool = False,
    fixture_mode: bool = False,
    preview_only: bool = False,
    provider_name: str | None = None,
    query: str | None = None,
    result_limit: int | None = None,
    posting_persister=None,
    trigger_type: str = "application",
    scheduler_run_id: str | None = None,
    scheduler_attempt: int | None = None,
) -> MarketCollectionResponse:
    settings = settings or get_settings()
    query = (query or settings.market_collection_query or "software developer").strip()
    if offline_test:
        dry_run = True
        if providers is None:
            providers = [OfflineFixtureProvider(provider_name or "adzuna")]
    elif preview_only or (dry_run and providers is None):
        preview_only = True
        dry_run = True

    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    collection_period = started_at.strftime("%Y-%m")
    window_start = datetime(started_at.year, started_at.month, 1, tzinfo=timezone.utc)
    # Dry runs validate provider results without constructing or touching stores.
    if dry_run:
        fetch_run_store = _DryRunSink()
        observation_store = _DryRunSink()
        raw_response_archive = _DryRunSink()
    else:
        fetch_run_store = fetch_run_store or FirestoreFetchRunStore()
        if observation_store is None:
            if getattr(settings, "skill_intelligence_read_backend", "firestore") == "sqlite":
                observation_store = store or MarketDataStore(settings.database_path)
            else:
                observation_store = FirestoreObservationStore()
        raw_response_archive = raw_response_archive or FirestoreRawResponseArchive()
    observation_backend = _observation_backend_name(observation_store, dry_run=dry_run)
    pending = pending_market_sources(settings)

    if preview_only:
        target_names = [provider_name] if provider_name else [
            p for p in ["adzuna", "jsearch"] if p in (settings.market_collection_enabled_providers or [])
        ]
        if not target_names:
            target_names = [provider_name or "adzuna"]
        preview_results = []
        for name in target_names:
            preview_results.append(
                ProviderCollectionResult(
                    fetch_run_id=f"preview-{name.lower()}-{run_id[:8]}",
                    provider=name,
                    status="preview",
                    records_fetched=0,
                    records_validated=0,
                    records_rejected=0,
                    records_duplicate=0,
                    records_filtered=0,
                    records_unmatched=0,
                    observations_created=0,
                    period=collection_period,
                    data_origin="test",
                    lifecycle_state="completed",
                    coverage_status="preview",
                    requested_page_count=1,
                    page_size_limit=result_limit if name.casefold() == "adzuna" else None,
                    sampling_frame="preview_only_no_network",
                    status_reasons=["preview_mode_zero_network_calls", "zero_database_writes"],
                )
            )
        return MarketCollectionResponse(
            run_id=run_id,
            status="dry_run",
            dry_run=True,
            location=location,
            country=country,
            observations_inserted=0,
            observations_validated=0,
            postings_validated=0,
            postings_duplicate_count=0,
            postings_persistence_status="not_attempted",
            observations_persistence_status="not_attempted",
            observation_storage_backend=observation_backend,
            status_reasons=["preview_mode_zero_network_calls", "zero_database_writes"],
            sources_succeeded=[p.provider for p in preview_results],
            sources_failed={},
            sources_pending=pending,
            providers=preview_results,
            period=collection_period,
            data_origin="test",
            history_type="platform_collected",
        )

    providers = configured_market_providers(settings) if providers is None else providers
    if provider_name:
        requested_provider = provider_name.strip().casefold()
        providers = [provider for provider in providers if provider.name.casefold() == requested_provider]
    if not providers:
        current_period = started_at.strftime("%Y-%m")
        return MarketCollectionResponse(
            run_id=run_id,
            status="dry_run" if dry_run else "pending_source_data",
            dry_run=dry_run,
            location=location,
            country=country,
            sources_pending=pending,
            providers=[],
            period=current_period,
            data_origin="test" if dry_run else "real",
            history_type="platform_collected",
            observation_storage_backend=observation_backend,
            observations_persistence_status="not_attempted",
            status_reasons=["no_configured_provider"],
        )

    observations = []
    observation_provenance = {}
    provider_results: list[ProviderCollectionResult] = []
    succeeded: list[str] = []
    failed: dict[str, str] = {}
    partial_coverage: set[str] = set()
    posting_persistence_confirmed = False
    posting_persistence_unknown = False
    postings_persisted_total = 0
    postings_readback_verified_total = 0
    postings_persistence_unconfirmed_total = 0
    run_status_reasons: list[str] = ["offline_test", "zero_database_writes"] if offline_test else []
    latest_provider_runs = {}
    summary_reader = getattr(fetch_run_store, "collection_summary", None) if not dry_run else None
    postings_validated = 0
    postings_duplicate_count = 0
    if callable(summary_reader):
        try:
            latest_provider_runs = (
                summary_reader().get("last_collection") or {}
            ).get("providers", {})
        except Exception:
            # Avoid logging SDK details; collection remains isolated if status reads fail.
            logger.error("fetch_run_cooldown_read_failed")
    for provider in providers:
        provider_run_id = uuid.uuid4().hex
        provider_started_at = datetime.now(timezone.utc)
        provider_panel_version = getattr(
            provider, "panel_version", settings.market_collection_panel_version or PANEL_VERSION,
        )
        query_id = _query_id(
            provider, location, country, query, result_limit, provider_panel_version,
        )
        run_record = {
            "run_id": provider_run_id,
            "collection_run_id": run_id,
            "trigger_type": trigger_type,
            "workflow_run_id": scheduler_run_id,
            "workflow_attempt": scheduler_attempt,
            "source": provider.name,
            "query_id": query_id,
            "panel_version": provider_panel_version,
            "extractor_version": EXTRACTOR_VERSION,
            "collection_schedule": settings.market_collection_cron,
            "data_origin": "test" if fixture_mode else "real",
            "execution_mode": "fixture" if fixture_mode else "provider",
            "job_storage_backend": "fixture_sqlite" if fixture_mode else "firestore",
            "observation_storage_backend": observation_backend,
            "search_query": query.strip(),
            "geography": {
                "location": location,
                "country": (country or getattr(getattr(provider, "settings", None), "adzuna_country", None)),
                "scope": "city" if location else "country" if country else "global",
            },
            "collection_period": collection_period,
            "collection_window_start": window_start,
            "collection_window_end": started_at,
            "source_window": (
                "JSearch date_posted=month" if provider.name.casefold() == "jsearch"
                else f"Adzuna current listings, page 1, result limit {result_limit if result_limit is not None else 50}"
                if provider.name.casefold() == "adzuna"
                else "provider current-results window unspecified"
            ),
            "started_at": provider_started_at,
            "completed_at": None,
            "status": "running",
            "lifecycle_state": "started",
            "records_fetched": None,
            "records_normalized": None,
            "records_validated": None,
            "records_processed": None,
            "records_persisted": None,
            "records_persistence_status": "not_attempted",
            "records_persistence_unconfirmed_count": None,
            "records_rejected": None,
            "records_filtered": None,
            "records_unmatched": None,
            "status_reasons": [],
            "error": None,
            "error_category": None,
            "retry_after_seconds": None,
            "http_status": None,
            "rate_limit_remaining": None,
            "rate_limit_limit": None,
            "rate_limit_reset": None,
            "authentication_status": None,
            "coverage_status": "pending",
            "raw_response_archive": None,
        }
        run_logging_error = False
        archive_metadata = None
        provider_diagnostics: dict[str, Any] = {}
        provider_observations = []
        fetched_count = normalized_count = rejected_count = filtered_count = None
        duplicate_count = None
        processed_count = unmatched_count = None
        provider_status_reasons: list[str] = []
        postings_persisted_count: int | None = None
        postings_persistence_unconfirmed_count: int | None = None
        postings_persistence_status = "not_attempted"
        if not dry_run:
            try:
                fetch_run_store.start(provider_run_id, run_record)
            except Exception:
                # Do not log exception text: Firestore errors may contain project details.
                run_logging_error = True
                logger.error("fetch_run_start_failed source=%s run_id=%s", provider.name, provider_run_id)
        try:
            if run_logging_error:
                raise RuntimeError("Fetch-run provenance could not be recorded.")
            cooldown = _cooldown_remaining(
                latest_provider_runs.get(provider.name.casefold()), datetime.now(timezone.utc),
            )
            if cooldown:
                raise _ProviderCooldown(provider.name, cooldown)
            def archive_response(payload, content_type=None):
                nonlocal archive_metadata
                if dry_run:
                    return None
                archive_metadata = raw_response_archive.archive(
                    provider=provider.name,
                    fetch_run_id=provider_run_id,
                    collected_at=provider_started_at,
                    payload=payload,
                    content_type=content_type,
                )
                return archive_metadata

            fetched_count, normalized_count, rejected_count, filtered_count, fetched_records, provider_observations, fetched_postings, provider_diagnostics = await _collect_provider(
                provider,
                location=location,
                country=country,
                collected_at=started_at,
                fetch_run_id=provider_run_id,
                query_id=query_id,
                panel_version=provider_panel_version,
                archive_response=archive_response,
                query=query,
                result_limit=result_limit,
            )
            if fixture_mode:
                for observation in provider_observations:
                    observation.data_origin = "test"
            if fetched_postings:
                posting_keys = [
                    (item.source.casefold(), item.provider_job_id or item.posting_id)
                    for item in fetched_records
                    if item.provider_job_id or item.posting_id
                ]
                duplicate_count = len(posting_keys) - len(set(posting_keys))
                postings_duplicate_count += duplicate_count
            if any(
                (
                    observation.observed_at.replace(tzinfo=timezone.utc)
                    if observation.observed_at.tzinfo is None
                    else observation.observed_at.astimezone(timezone.utc)
                ) > started_at
                for observation in provider_observations
            ):
                raise ValueError("Provider returned a future-dated observation.")
            safe_error = None
            error_category = None
            expected = OBSERVATION_CONTRACTS.get(provider.name.casefold())
            for observation in provider_observations:
                if observation.source.casefold() != provider.name.casefold():
                    raise ValueError("Provider returned an observation with a mismatched source.")
                canonical_id = canonical_skill_id(observation.skill)
                if not canonical_id or observation.skill_id != canonical_id:
                    raise ValueError("Provider returned an observation without a canonical skill ID.")
                if not observation.unit or not observation.unit.strip():
                    raise ValueError("Provider returned an observation without an explicit unit.")
                if not observation.history_type or observation.data_origin != ("test" if fixture_mode else "real"):
                    raise ValueError("Provider returned an observation without real-data history provenance.")
                if expected and (
                    observation.signal_type,
                    observation.unit,
                    observation.history_type,
                ) != expected:
                    raise ValueError("Provider returned an observation with an incompatible signal contract.")
                observation.fetch_run_id = provider_run_id
                observation.query_id = observation.query_id or query_id
                observation.panel_version = observation.panel_version or provider_panel_version
            observations.extend(provider_observations)
            if fetched_postings:
                postings_validated += len(fetched_records)
            job_storage_error = False
            if fetched_postings and not dry_run:
                if not fetched_records:
                    postings_persisted_count = 0
                    postings_persistence_status = "confirmed"
                    posting_persistence_confirmed = True
                else:
                    try:
                        persist_postings = posting_persister or store_collected_market_jobs
                        postings_persisted_count = persist_postings(
                            fetched_records, fetched_at=started_at, fetch_run_id=provider_run_id,
                        )
                        postings_persistence_status = "confirmed"
                        posting_persistence_confirmed = True
                        postings_persisted_total += postings_persisted_count
                        postings_readback_verified_total += postings_persisted_count
                        expected_persistable = len(set(posting_keys))
                        if postings_persisted_count != expected_persistable:
                            job_storage_error = True
                            provider_status_reasons.append("posting_persistence_count_mismatch")
                            failed[f"{provider.name}_jobs"] = (
                                "Persisted job count did not match the validated posting count."
                            )
                    except Exception:
                        postings_persisted_count = None
                        postings_persistence_unconfirmed_count = len(fetched_records)
                        postings_persistence_unconfirmed_total += len(fetched_records)
                        postings_persistence_status = "unknown"
                        posting_persistence_unknown = True
                        failed[f"{provider.name}_jobs"] = "Collected job persistence could not be confirmed."
                        provider_status_reasons.append("job_persistence_unconfirmed")
                        job_storage_error = True
            elif fetched_postings:
                postings_persistence_status = "not_attempted"
            for observation in provider_observations:
                observation_id = stable_observation_id(observation)
                observation_provenance[observation_id] = {
                    "query_id": query_id,
                    "panel_version": provider_panel_version,
                    "fetch_run_id": provider_run_id,
                }
            succeeded.append(provider.name)
            processed_ids = {item.posting_id for item in provider_observations if item.posting_id}
            processed_count = len(processed_ids) if fetched_postings else len(provider_observations)
            unmatched_count = (
                max(0, normalized_count - processed_count)
                if fetched_postings else 0
            )
            incomplete_result = provider_diagnostics.get("coverage_complete") is False
            if provider_diagnostics.get("pagination_complete") is False:
                incomplete_result = True
                provider_status_reasons.append("pagination_incomplete")
            if provider_diagnostics.get("coverage_complete") is False:
                provider_status_reasons.append("source_coverage_incomplete")
            if (
                fetched_postings
                and normalized_count == 0
                and not provider_diagnostics.get("zero_results_verified", False)
            ) or (
                not fetched_postings
                and not provider_observations
                and not provider_diagnostics.get("zero_results_verified", False)
            ):
                incomplete_result = True
                provider_status_reasons.append("empty_result_not_verified")
            if rejected_count:
                provider_status_reasons.append("records_rejected")
            # A valid posting with no registry-recognized skills is still a valid
            # collection record. Track it as unmatched, but do not call the source
            # collection incomplete or turn the posting into a failed run.
            incomplete_result = incomplete_result or bool(rejected_count)
            sampling_frame = provider_diagnostics.get("sampling_frame")
            collection_complete = not incomplete_result
            for observation in provider_observations:
                quality = dict(observation.quality) if isinstance(observation.quality, dict) else {}
                quality.update({
                    "collection_complete": collection_complete,
                    "pagination_complete": provider_diagnostics.get("pagination_complete", True),
                    "zero_results_verified": provider_diagnostics.get("zero_results_verified", False),
                    "sampling_frame": sampling_frame,
                })
                observation.quality = quality
            provider_status = (
                "partial"
                if rejected_count or incomplete_result or job_storage_error
                else "success"
            )
            coverage_status = (
                "partial" if rejected_count or incomplete_result
                else "verified_zero" if provider_diagnostics.get("zero_results_verified")
                else "sampled_complete" if sampling_frame
                else "complete"
            )
            if incomplete_result:
                coverage_status = "partial"
            if job_storage_error:
                coverage_status = "partial"
                safe_error = (
                    "Persisted job count did not match the validated posting count."
                    if "posting_persistence_count_mismatch" in provider_status_reasons
                    else "Collected job persistence could not be confirmed."
                )
                error_category = "storage"
            if provider_status == "partial":
                partial_coverage.add(provider.name)
            retry_after_seconds = None
            http_status = provider_diagnostics.get("http_status")
            rate_limit_remaining = provider_diagnostics.get("rate_limit_remaining")
            rate_limit_limit = provider_diagnostics.get("rate_limit_limit")
            rate_limit_reset = provider_diagnostics.get("rate_limit_reset")
            authentication_status = provider_diagnostics.get("authentication_status")
        except Exception as error:
            safe_error = (
                "Fetch-run provenance could not be recorded."
                if run_logging_error
                else _safe_provider_error(provider.name, error)
            )
            failed[provider.name] = safe_error
            provider_status_reasons.append(
                "fetch_run_start_unconfirmed" if run_logging_error else "provider_collection_failed"
            )
            provider_status = "failed"
            coverage_status = "unavailable"
            error_category = "storage" if run_logging_error else getattr(error, "category", None)
            http_status = getattr(error, "http_status", None)
            rate_limit_remaining = getattr(error, "rate_limit_remaining", None)
            rate_limit_limit = getattr(error, "rate_limit_limit", None)
            rate_limit_reset = getattr(error, "rate_limit_reset", None)
            authentication_status = "rejected" if error_category == "authentication" else None
            retry_after = getattr(error, "retry_after", None)
            retry_after_seconds = str(min(int(retry_after), 86400)) if isinstance(retry_after, str) and retry_after.isdigit() else None
            if error_category == "rate_limit" and retry_after_seconds is None:
                if isinstance(rate_limit_reset, str) and rate_limit_reset.isdigit():
                    retry_after_seconds = str(max(
                        1, min(int(rate_limit_reset) - int(datetime.now(timezone.utc).timestamp()), 86400),
                    ))
                else:
                    retry_after_seconds = str(RATE_LIMIT_COOLDOWN_FALLBACK_SECONDS)
            if error_category is None:
                error_category = "network" if "timed out" in str(error).casefold() or "reached" in str(error).casefold() else "provider"
        try:
            fetch_run_store.finish(provider_run_id, {
                "completed_at": datetime.now(timezone.utc),
                "status": provider_status,
                "lifecycle_state": (
                    "blocked" if run_logging_error else
                    "failed" if provider_status == "failed" else
                    "partial" if provider_status == "partial" else "completed"
                ),
                "records_fetched": fetched_count,
                "records_normalized": normalized_count,
                "records_validated": normalized_count,
                "records_processed": processed_count,
                "records_with_recognized_skills": processed_count,
                "skill_posting_counts": _skill_posting_counts(provider_observations),
                "extractor_version": EXTRACTOR_VERSION,
                "records_persisted": postings_persisted_count,
                "records_persistence_status": postings_persistence_status,
                "records_persistence_unconfirmed_count": postings_persistence_unconfirmed_count,
                "records_rejected": rejected_count,
                "records_duplicate": duplicate_count,
                "records_filtered": filtered_count,
                "records_unmatched": unmatched_count,
                "observation_storage_backend": observation_backend,
                "status_reasons": list(dict.fromkeys(provider_status_reasons)),
                "error": safe_error if not run_logging_error else (safe_error or "Fetch run logging failed."),
                "error_category": error_category,
                "retry_after_seconds": retry_after_seconds,
                "http_status": http_status,
                "rate_limit_remaining": rate_limit_remaining,
                "rate_limit_limit": rate_limit_limit,
                "rate_limit_reset": rate_limit_reset,
                "authentication_status": authentication_status,
                "coverage_status": coverage_status,
                "requested_page_count": provider_diagnostics.get("requested_page_count"),
                "page_size_limit": provider_diagnostics.get("page_size_limit"),
                "provider_total_count": provider_diagnostics.get("provider_total_count"),
                "pagination_complete": provider_diagnostics.get("pagination_complete"),
                "zero_results_verified": provider_diagnostics.get("zero_results_verified", False),
                "sampling_frame": provider_diagnostics.get("sampling_frame"),
                "collection_schedule": settings.market_collection_cron,
                "raw_response_archive": archive_metadata,
            })
        except Exception:
            # Keep provider collection independent if observability storage is unavailable.
            logger.error("fetch_run_finish_failed source=%s run_id=%s", provider.name, provider_run_id)
            if provider_status in {"success", "partial"}:
                provider_status = "partial"
                error_category = "storage"
                safe_error = "Fetch-run completion could not be recorded."
                failed[f"{provider.name}_fetch_run"] = safe_error
                partial_coverage.add(provider.name)
                provider_status_reasons.append("fetch_run_completion_unconfirmed")
                for observation in provider_observations:
                    quality = dict(observation.quality) if isinstance(observation.quality, dict) else {}
                    quality["collection_complete"] = False
                    quality["completion_recorded"] = False
                    observation.quality = quality

        provider_history_type = (
            "platform_collected"
            if provider.name.casefold() in {"jsearch", "adzuna"}
            else "snapshot"
        )
        provider_results.append(
            ProviderCollectionResult(
                fetch_run_id=provider_run_id,
                provider=provider.name,
                status=provider_status,
                records_fetched=fetched_count,
                records_validated=normalized_count,
                records_rejected=rejected_count,
                records_duplicate=duplicate_count,
                records_filtered=filtered_count,
                records_unmatched=unmatched_count,
                postings_persisted_count=postings_persisted_count,
                postings_persistence_unconfirmed_count=postings_persistence_unconfirmed_count,
                postings_persistence_status=postings_persistence_status,
                status_reasons=list(dict.fromkeys(provider_status_reasons)),
                observations_created=(
                    len(provider_observations)
                    if provider_status != "failed" and not dry_run
                    else 0
                ),
                period=started_at.strftime("%Y-%m"),
                data_origin="test" if dry_run or fixture_mode else "real",
                history_type=provider_history_type,
                error=safe_error,
                error_category=error_category,
                lifecycle_state=(
                    "blocked" if run_logging_error else
                    "failed" if provider_status == "failed" else
                    "partial" if provider_status == "partial" else "completed"
                ),
                coverage_status=coverage_status,
                requested_page_count=provider_diagnostics.get("requested_page_count"),
                page_size_limit=provider_diagnostics.get("page_size_limit"),
                sampling_frame=provider_diagnostics.get("sampling_frame"),
                zero_results_verified=bool(provider_diagnostics.get("zero_results_verified")),
            )
        )

    inserted = 0
    observations_persisted_count: int | None = None
    observations_readback_verified_count: int | None = None
    observations_persistence_unconfirmed_count: int | None = None
    observations_persistence_status = "not_attempted" if dry_run else "unknown"
    observation_storage_name = {
        "sqlite": "local SQLite",
        "firestore": "Firestore",
        "injected": "injected observation store",
        "dry_run": "dry-run sink",
    }[observation_backend]
    observation_storage_failure_key = {
        "sqlite": "sqlite_storage",
        "firestore": "firestore_storage",
        "injected": "injected_storage",
        "dry_run": "dry_run_storage",
    }[observation_backend]
    try:
        inserted = observation_store.insert_observations(
            observations,
            provenance_by_observation_id=observation_provenance,
        )
        if not dry_run:
            observations_readback_verified_count = verify_observation_readback(
                observation_store, observations,
            )
            observations_persisted_count = inserted
            observations_persistence_status = "confirmed"
    except Exception:
        storage_error = f"Market observations could not be stored in {observation_storage_name}."
        observations_persisted_count = None
        observations_persistence_unconfirmed_count = len(observations)
        observations_persistence_status = "unknown"
        failed[observation_storage_failure_key] = storage_error
        run_status_reasons.append("observation_persistence_unconfirmed")
        failed_sources = {
            observation.source.casefold()
            for observation in observations
        }
        for provider_result in provider_results:
            provider_key = provider_result.provider.casefold()
            if provider_key not in failed_sources or provider_result.status == "failed":
                continue
            provider_result.status = "failed"
            provider_result.error = storage_error
            provider_result.error_category = "storage"
            provider_result.status_reasons = list(dict.fromkeys(
                [*provider_result.status_reasons, "observation_persistence_unconfirmed"]
            ))
            failed[provider_result.provider] = storage_error
            if provider_result.provider in succeeded:
                succeeded.remove(provider_result.provider)
            try:
                fetch_run_store.finish(provider_result.fetch_run_id, {
                    "completed_at": datetime.now(timezone.utc),
                    "status": "failed",
                    "lifecycle_state": "failed",
                    "error": storage_error,
                    "error_category": "storage",
                    "coverage_status": "unavailable",
                })
            except Exception:
                logger.error(
                    "fetch_run_storage_failure_update_failed source=%s run_id=%s",
                    provider_result.provider,
                    provider_result.fetch_run_id,
                )
    if not dry_run:
        for provider_result in provider_results:
            try:
                fetch_run_store.finish(provider_result.fetch_run_id, {
                    "observation_storage_backend": observation_backend,
                    "collection_observations_inserted_count": observations_persisted_count,
                    "collection_observations_persistence_status": observations_persistence_status,
                    "collection_observations_persistence_unconfirmed_count": observations_persistence_unconfirmed_count,
                })
            except Exception:
                reason = "fetch_run_persistence_confirmation_unconfirmed"
                run_status_reasons.append(reason)
                provider_result.status_reasons = list(dict.fromkeys(
                    [*provider_result.status_reasons, reason]
                ))
                if provider_result.status != "failed":
                    provider_result.status = "partial"
                    # Preserve a more specific earlier failure (for example, the
                    # fetch-run completion write itself) when this follow-up
                    # metadata write also fails.
                    if provider_result.error is None:
                        provider_result.error_category = "storage"
                        provider_result.error = "Collection persistence status could not be recorded."
                    partial_coverage.add(provider_result.provider)
                    failed.setdefault(
                        f"{provider_result.provider}_fetch_run",
                        provider_result.error,
                    )
    status_reasons = list(run_status_reasons)
    for provider_result in provider_results:
        status_reasons.extend(
            f"{provider_result.provider}:{reason}"
            for reason in provider_result.status_reasons
        )
    for failure_key in failed:
        if failure_key.endswith("_fetch_run"):
            status_reasons.append(f"{failure_key}:fetch_run_write_unconfirmed")
    status_reasons = list(dict.fromkeys(status_reasons))
    run_status = "dry_run" if dry_run else (
        "partial_failure" if succeeded and (failed or partial_coverage)
        else "success" if succeeded
        else "error"
    )
    current_period = started_at.strftime("%Y-%m")
    return MarketCollectionResponse(
        run_id=run_id,
        status=run_status,
        dry_run=dry_run,
        location=location,
        country=country,
        observations_inserted=inserted,
        observations_validated=len(observations),
        postings_validated=postings_validated,
        postings_duplicate_count=postings_duplicate_count,
        postings_persisted_count=(
            None if dry_run or posting_persistence_unknown
            else postings_persisted_total if posting_persistence_confirmed
            else None
        ),
        postings_readback_verified_count=(
            None if dry_run or posting_persistence_unknown
            else postings_readback_verified_total if posting_persistence_confirmed
            else None
        ),
        postings_persistence_unconfirmed_count=(
            None if dry_run else postings_persistence_unconfirmed_total
        ),
        postings_persistence_status=(
            "not_attempted" if dry_run or not posting_persistence_confirmed and not posting_persistence_unknown
            else "unknown" if posting_persistence_unknown
            else "confirmed"
        ),
        observations_persisted_count=observations_persisted_count,
        observations_readback_verified_count=observations_readback_verified_count,
        observations_persistence_unconfirmed_count=observations_persistence_unconfirmed_count,
        observations_persistence_status=observations_persistence_status,
        observation_storage_backend=observation_backend,
        status_reasons=status_reasons,
        sources_succeeded=succeeded,
        sources_failed=failed,
        sources_pending=pending,
        providers=provider_results,
        period=current_period,
        data_origin="test" if dry_run or fixture_mode else "real",
        history_type="platform_collected",
    )


def get_collection_status(
    fetch_run_store: FirestoreFetchRunStore | None = None,
    settings: Settings | None = None,
    observation_store: Any | None = None,
) -> MarketCollectionStatusResponse:
    settings = settings or get_settings()
    fetch_run_store = fetch_run_store or FirestoreFetchRunStore()
    summary_reader = getattr(fetch_run_store, "collection_summary", None)
    summary = summary_reader() if callable(summary_reader) else {}
    last_collection = summary.get("last_collection") or {}
    provider_runs = last_collection.get("providers") or {}

    provider_quality: dict[str, str] = {}
    provider_readiness: dict[str, str] = {}
    observation_history_incomplete = False
    observation_read_failed = False
    try:
        if observation_store is not None:
            obs_store = observation_store
        elif getattr(settings, "skill_intelligence_read_backend", "firestore") == "sqlite":
            obs_store = MarketDataStore(settings.database_path)
        else:
            obs_store = FirestoreObservationStore()
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        all_obs = obs_store.get_observations(cutoff=cutoff)
        observation_history_incomplete = bool(getattr(all_obs, "truncated", False))
        if all_obs and not observation_history_incomplete:
            from app.analytics.series_validation import validate_series_observations, summarize_quality
            from app.analytics.analytical_readiness import assess_analytical_readiness, summarize_readiness

            by_prov: dict[str, list] = {}
            for o in all_obs:
                by_prov.setdefault(o.source.casefold().strip(), []).append(o)

            for p_name, p_obs in by_prov.items():
                p_q_reports = validate_series_observations(p_obs)
                if p_q_reports:
                    p_q_sum = summarize_quality(p_q_reports)
                    provider_quality[p_name] = p_q_sum.overall_quality_state
                    p_r_reports = assess_analytical_readiness(p_obs, quality_reports=p_q_reports)
                    if p_r_reports:
                        p_r_sum = summarize_readiness(p_r_reports)
                        provider_readiness[p_name] = p_r_sum.overall_readiness_state
    except Exception as exc:
        observation_read_failed = True
        logger.error("collection_status_observation_read_failed (%s)", type(exc).__name__)

    statuses: list[ProviderCollectionStatus] = []
    configured_names = [p.name.casefold() for p in configured_market_providers(settings)]
    providers_to_check: list[str] = list(configured_names)
    for src in provider_runs:
        if src not in providers_to_check:
            providers_to_check.append(src)

    latest_times = []
    has_success = False
    has_failed = False
    has_partial = False
    has_running = False

    from app.models.provider_capability import get_provider_capability

    for provider_name in providers_to_check:
        run = provider_runs.get(provider_name)
        cap = get_provider_capability(provider_name)
        q_stat = (
            "unavailable" if observation_read_failed
            else "incomplete" if observation_history_incomplete
            else provider_quality.get(provider_name)
        )
        r_stat = (
            "unavailable" if observation_read_failed
            else "incomplete" if observation_history_incomplete
            else provider_readiness.get(provider_name)
        )
        if run:
            completed_at = run.get("completed_at") or run.get("started_at")
            if completed_at:
                latest_times.append(completed_at)
            run_status = run.get("status")
            if run_status == "running" or run.get("lifecycle_state") == "started":
                has_running = True
                latest_successful = None
                latest_failed = None
            elif run_status == "success" and run.get("lifecycle_state", "completed") == "completed":
                has_success = True
                latest_successful = completed_at
                latest_failed = None
            if run_status != "running" and run.get("lifecycle_state") != "started" and not (
                run_status == "success" and run.get("lifecycle_state", "completed") == "completed"
            ):
                has_partial = has_partial or run_status == "partial"
                has_failed = True
                latest_successful = None
                latest_failed = completed_at
            started = run.get("started_at")
            period = started.strftime("%Y-%m") if isinstance(started, datetime) else None
            obs_count = run.get("records_processed") or run.get("records_normalized") or 0
            statuses.append(
                ProviderCollectionStatus(
                    provider=provider_name,
                    latest_successful_collection=latest_successful,
                    last_failed_collection=latest_failed,
                    latest_period=period,
                    fetch_run_id=run.get("run_id"),
                    observation_count=obs_count,
                    failure_status=run_status if run_status in {"failed", "partial"} else None,
                    last_error_category=run.get("error_category"),
                    query_id=run.get("query_id"),
                    series_id=run.get("series_id"),
                    provider_capability=cap.collection_type if cap else None,
                    history_type=cap.history_type if cap else None,
                    data_origin="real",
                    quality_status=q_stat,
                    readiness_status=r_stat,
                    lifecycle_state=run.get("lifecycle_state"),
                    coverage_status=run.get("coverage_status"),
                    collection_window_start=run.get("collection_window_start"),
                    collection_window_end=run.get("collection_window_end"),
                    geography=run.get("geography"),
                    requested_page_count=run.get("requested_page_count"),
                    page_size_limit=run.get("page_size_limit"),
                    sampling_frame=run.get("sampling_frame"),
                    zero_results_verified=bool(run.get("zero_results_verified", False)),
                )
            )
        else:
            statuses.append(
                ProviderCollectionStatus(
                    provider=provider_name,
                    latest_successful_collection=None,
                    last_failed_collection=None,
                    latest_period=None,
                    fetch_run_id=None,
                    observation_count=0,
                    failure_status=None,
                    last_error_category=None,
                    query_id=None,
                    series_id=None,
                    provider_capability=cap.collection_type if cap else None,
                    history_type=cap.history_type if cap else None,
                    data_origin="real" if cap else None,
                    quality_status=q_stat,
                    readiness_status=r_stat,
                )
            )

    if not provider_runs:
        overall = "idle"
    elif (has_success and has_failed) or has_partial:
        overall = "partial_failure"
    elif has_running:
        overall = "pending"
    elif has_success:
        overall = "success"
    else:
        overall = "failed"

    latest_collection_time = max(latest_times, default=None)
    return MarketCollectionStatusResponse(
        overall_status=overall,
        latest_collection=latest_collection_time,
        providers=statuses,
    )


def run_collection(**kwargs) -> MarketCollectionResponse:
    return asyncio.run(collect_market_data(**kwargs))

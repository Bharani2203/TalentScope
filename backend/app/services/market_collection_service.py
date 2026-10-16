import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.analytics.skill_registry import canonical_skill_id
from app.core.config import Settings, get_settings
from app.models.skill_intelligence import (
    MarketCollectionResponse,
    MarketCollectionStatusResponse,
    ProviderCollectionResult,
    ProviderCollectionStatus,
)
from app.services.market_data.adzuna_provider import AdzunaProvider
from app.services.market_data.base import MarketObservationCollector
from app.services.market_data.job_observations import observations_from_postings
from app.services.market_data.jsearch_provider import JSearchProvider
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.base import ObservationFetchResult, PostingFetchResult
from app.services.external_apis.github_service import GitHubError
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.observation_identity import stable_observation_id
from app.storage.raw_response_archive import FirestoreRawResponseArchive
from app.services.job_storage_service import store_collected_market_jobs

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


def _query_id(provider: MarketObservationCollector, location: str | None, country: str | None) -> str:
    provider_settings = getattr(provider, "settings", None)
    is_github = provider.name.casefold() == "github"
    effective_country = None if is_github else country or getattr(provider_settings, "adzuna_country", None)
    query_descriptor = (
        {"topic": getattr(provider_settings, "github_topic", "python"), "metric": "repository-topic-count"}
        if provider.name.casefold() == "github"
        else {"query": "software-developer", "period": "month"}
    )
    descriptor = json.dumps({
        "source": provider.name.casefold(),
        **query_descriptor,
        "location": location.strip().casefold() if location and not is_github else None,
        "country": effective_country.casefold() if effective_country else None,
    }, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()[:20]
    return f"{provider.name.casefold()}:{digest}"


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
    panel_version=None, archive_response=None,
):
    fetch_with_stats = getattr(provider, "fetch_market_postings_with_stats", None)
    if callable(fetch_with_stats):
        batch: PostingFetchResult = await fetch_with_stats(
            location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, archive_response=archive_response,
        )
        observations = observations_from_postings(
            batch.postings, location=location, country=country, collected_at=collected_at,
            fetch_run_id=fetch_run_id, query_id=query_id, panel_version=panel_version,
        )
        return (batch.records_fetched, len(batch.postings), batch.records_rejected, batch.records_filtered,
                batch.postings, observations, True, {})
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
) -> MarketCollectionResponse:
    settings = settings or get_settings()
    providers = configured_market_providers(settings) if providers is None else providers
    pending = pending_market_sources(settings)
    started_at = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex
    fetch_run_store = fetch_run_store or FirestoreFetchRunStore()
    observation_store = observation_store or FirestoreObservationStore()
    raw_response_archive = raw_response_archive or FirestoreRawResponseArchive()
    if not providers:
        current_period = started_at.strftime("%Y-%m")
        return MarketCollectionResponse(
            run_id=run_id,
            status="pending_source_data",
            location=location,
            country=country,
            sources_pending=pending,
            providers=[],
            period=current_period,
            data_origin="real",
            history_type="platform_collected",
        )

    observations = []
    observation_provenance = {}
    provider_results: list[ProviderCollectionResult] = []
    succeeded: list[str] = []
    failed: dict[str, str] = {}
    partial_coverage: set[str] = set()
    latest_provider_runs = {}
    summary_reader = getattr(fetch_run_store, "collection_summary", None)
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
        query_id = _query_id(provider, location, country)
        provider_panel_version = getattr(provider, "panel_version", PANEL_VERSION)
        run_record = {
            "run_id": provider_run_id,
            "collection_run_id": run_id,
            "source": provider.name,
            "query_id": query_id,
            "panel_version": provider_panel_version,
            "started_at": provider_started_at,
            "completed_at": None,
            "status": "running",
            "records_fetched": 0,
            "records_normalized": 0,
            "records_processed": 0,
            "records_rejected": 0,
            "records_filtered": 0,
            "records_unmatched": 0,
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
            )
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
                if not observation.history_type or observation.data_origin != "real":
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
            job_storage_error = False
            if fetched_postings and fetched_records:
                try:
                    store_collected_market_jobs(
                        fetched_records,
                        fetched_at=started_at,
                        fetch_run_id=provider_run_id,
                    )
                except Exception:
                    failed[f"{provider.name}_jobs"] = "Collected job records could not be stored."
                    job_storage_error = True
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
            unmatched_count = max(0, normalized_count - processed_count) if fetched_postings else 0
            incomplete_result = provider_diagnostics.get("coverage_complete") is False
            provider_status = (
                "partial"
                if rejected_count or unmatched_count or incomplete_result or job_storage_error
                else "success"
            )
            coverage_status = "partial" if rejected_count or unmatched_count else "complete" if fetched_count > 0 else "no_data"
            if incomplete_result:
                coverage_status = "partial"
            if job_storage_error:
                coverage_status = "partial"
                safe_error = "Collected job records could not be stored."
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
            fetched_count = normalized_count = processed_count = rejected_count = filtered_count = unmatched_count = 0
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
                "records_fetched": fetched_count,
                "records_normalized": normalized_count,
                "records_processed": processed_count,
                "records_rejected": rejected_count,
                "records_filtered": filtered_count,
                "records_unmatched": unmatched_count,
                "error": safe_error if not run_logging_error else (safe_error or "Fetch run logging failed."),
                "error_category": error_category,
                "retry_after_seconds": retry_after_seconds,
                "http_status": http_status,
                "rate_limit_remaining": rate_limit_remaining,
                "rate_limit_limit": rate_limit_limit,
                "rate_limit_reset": rate_limit_reset,
                "authentication_status": authentication_status,
                "coverage_status": coverage_status,
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
                records_rejected=rejected_count,
                observations_created=len(provider_observations) if provider_status != "failed" else 0,
                period=started_at.strftime("%Y-%m"),
                data_origin="real",
                history_type=provider_history_type,
                error=safe_error,
                error_category=error_category,
            )
        )

    inserted = 0
    try:
        inserted = observation_store.insert_observations(
            observations,
            provenance_by_observation_id=observation_provenance,
        )
    except Exception:
        failed["firestore_storage"] = "Market observations could not be stored in Firestore."
        storage_error = failed["firestore_storage"]
        failed_sources = {
            observation.source.casefold()
            for observation in observations
        }
        for provider_result in provider_results:
            provider_key = provider_result.provider.casefold()
            if provider_key not in failed_sources or provider_result.status == "failed":
                continue
            provider_result.status = "failed"
            provider_result.observations_created = 0
            provider_result.error = storage_error
            provider_result.error_category = "storage"
            failed[provider_result.provider] = storage_error
            if provider_result.provider in succeeded:
                succeeded.remove(provider_result.provider)
            try:
                fetch_run_store.finish(provider_result.fetch_run_id, {
                    "completed_at": datetime.now(timezone.utc),
                    "status": "failed",
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
    run_status = (
        "partial_failure" if succeeded and (failed or partial_coverage)
        else "success" if succeeded
        else "error"
    )
    current_period = started_at.strftime("%Y-%m")
    return MarketCollectionResponse(
        run_id=run_id,
        status=run_status,
        location=location,
        country=country,
        observations_inserted=inserted,
        sources_succeeded=succeeded,
        sources_failed=failed,
        sources_pending=pending,
        providers=provider_results,
        period=current_period,
        data_origin="real",
        history_type="platform_collected",
    )


def get_collection_status(
    fetch_run_store: FirestoreFetchRunStore | None = None,
    settings: Settings | None = None,
    observation_store: Any | None = None,
) -> MarketCollectionStatusResponse:
    fetch_run_store = fetch_run_store or FirestoreFetchRunStore()
    settings = settings or get_settings()
    summary_reader = getattr(fetch_run_store, "collection_summary", None)
    summary = summary_reader() if callable(summary_reader) else {}
    last_collection = summary.get("last_collection") or {}
    provider_runs = last_collection.get("providers") or {}

    provider_quality: dict[str, str] = {}
    provider_readiness: dict[str, str] = {}
    try:
        obs_store = observation_store if observation_store is not None else FirestoreObservationStore()
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        all_obs = obs_store.get_observations(cutoff=cutoff)
        if all_obs:
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
    except Exception:
        pass

    statuses: list[ProviderCollectionStatus] = []
    configured_names = [p.name.casefold() for p in configured_market_providers(settings)]
    providers_to_check: list[str] = list(configured_names)
    for src in provider_runs:
        if src not in providers_to_check:
            providers_to_check.append(src)

    latest_times = []
    has_success = False
    has_failed = False

    from app.models.provider_capability import get_provider_capability

    for provider_name in providers_to_check:
        run = provider_runs.get(provider_name)
        cap = get_provider_capability(provider_name)
        q_stat = provider_quality.get(provider_name)
        r_stat = provider_readiness.get(provider_name)
        if run:
            completed_at = run.get("completed_at") or run.get("started_at")
            if completed_at:
                latest_times.append(completed_at)
            run_status = run.get("status")
            if run_status in {"success", "partial"}:
                has_success = True
                latest_successful = completed_at
                latest_failed = None
            else:
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
    elif has_success and has_failed:
        overall = "partial_failure"
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

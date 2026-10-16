"""Controlled, idempotent Firestore backfill orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.market_data.stack_exchange_historical_provider import (
    PANEL_VERSION,
    StackExchangeHistoricalProvider,
    _definition_for_skill,
    _month_periods,
)
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.observation_identity import stable_observation_id
from app.storage.raw_response_archive import FirestoreRawResponseArchive


def backfill(
    *,
    source: str,
    skills: list[str],
    start_period: str,
    end_period: str,
    dry_run: bool = True,
    provider: StackExchangeHistoricalProvider | None = None,
    fetch_run_store: FirestoreFetchRunStore | None = None,
    observation_store: FirestoreObservationStore | None = None,
    raw_response_archive: FirestoreRawResponseArchive | None = None,
) -> dict[str, Any]:
    """Run the explicitly selected source backfill without touching SQLite."""
    import asyncio

    if source.casefold() != "stackexchange":
        raise ValueError("Only the verified stackexchange historical source is currently supported.")
    if not skills or any(not isinstance(skill, str) or not skill.strip() for skill in skills):
        raise ValueError("At least one canonical registry skill is required.")
    periods = _month_periods(start_period, end_period)
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
    if periods[-1] >= current_period:
        raise ValueError("Historical backfill must end before the current UTC month.")

    provider = provider or StackExchangeHistoricalProvider()
    fetch_run_store = fetch_run_store or FirestoreFetchRunStore()
    observation_store = observation_store or FirestoreObservationStore()
    raw_response_archive = raw_response_archive or FirestoreRawResponseArchive()
    results = asyncio.run(_run(
        provider=provider,
        fetch_run_store=fetch_run_store,
        observation_store=observation_store,
        raw_response_archive=raw_response_archive,
        skills=skills,
        periods=periods,
        dry_run=dry_run,
    ))
    return {
        "source": "stackexchange",
        "start_period": periods[0],
        "end_period": periods[-1],
        "dry_run": dry_run,
        "series": results,
        "status": "failed" if results and all(item["status"] == "failed" for item in results)
        else "partial" if any(item["status"] != "success" for item in results)
        else "success",
    }


async def _run(*, provider, fetch_run_store, observation_store, raw_response_archive, skills, periods, dry_run):
    results: list[dict[str, Any]] = []
    for skill in skills:
        definition = _definition_for_skill(skill)
        run_id = uuid.uuid4().hex
        started_at = datetime.now(timezone.utc)
        query_id = (
            f"stackexchange:stackoverflow:tag:{definition.stack_exchange_tags[0]}:v1"
            if len(definition.stack_exchange_tags) == 1
            else f"stackexchange:stackoverflow:skill:{definition.skill_id}:tags-v1"
        )
        run_record = {
            "run_id": run_id,
            "source": "stackexchange",
            "query_id": query_id,
            "panel_version": PANEL_VERSION,
            "started_at": started_at,
            "completed_at": None,
            "status": "running",
            "records_fetched": 0,
            "records_normalized": 0,
            "records_processed": 0,
            "records_rejected": 0,
            "records_filtered": 0,
            "records_unmatched": 0,
            "error": None,
            "coverage_status": "pending",
            "backfill": True,
            "dry_run": dry_run,
            "requested_start_period": periods[0],
            "requested_end_period": periods[-1],
            "skill_id": definition.skill_id,
            "tags": list(definition.stack_exchange_tags),
            "raw_response_archive": None,
        }
        try:
            fetch_run_store.start(run_id, run_record)
        except Exception:
            results.append({"run_id": run_id, "skill": skill, "status": "failed", "error": "fetch_run_write"})
            continue

        series_results = []
        provider_error = None
        archive_count = 0
        first_archive = None
        try:
            def archive_response(payload, content_type=None):
                nonlocal archive_count, first_archive
                reference = raw_response_archive.archive(
                    provider="stackexchange",
                    fetch_run_id=run_id,
                    collected_at=started_at,
                    payload=payload,
                    content_type=content_type,
                    response_index=archive_count,
                )
                if first_archive is None:
                    first_archive = reference
                archive_count += 1
                return reference

            series_results = await provider.backfill_series(
                skill=skill, start_period=periods[0], end_period=periods[-1],
                archive_response=archive_response if not dry_run else None,
            )
        except Exception:
            provider_error = "Historical source request failed."
        observations = [observation for series in series_results for observation in series.observations]
        inserted_by_series: dict[str, int] = {}
        storage_failed_series: set[str] = set()
        if not dry_run:
            current_period = datetime.now(timezone.utc).strftime("%Y-%m")
            for series in series_results:
                try:
                    for observation in series.observations:
                        observation.fetch_run_id = run_id
                        if first_archive and "raw_archive_id" not in observation.metadata:
                            observation.metadata["raw_archive_id"] = first_archive.get("archive_reference")

                        # Production Safety Verification (G1.13 Section 8)
                        if observation.source != "stackexchange":
                            raise ValueError(f"Invalid observation source: {observation.source}")
                        if observation.signal_type != "interest":
                            raise ValueError(f"Invalid observation signal_type: {observation.signal_type}")
                        if observation.data_origin != "real":
                            raise ValueError(f"Invalid observation data_origin: {observation.data_origin}")
                        if observation.history_type not in {"backfill", "backfilled"}:
                            raise ValueError(f"Invalid observation history_type: {observation.history_type}")
                        if not observation.period or observation.period >= current_period:
                            raise ValueError(f"Invalid or current/future observation period: {observation.period}")
                        if not observation.series_id or not observation.series_id.startswith("stackexchange:"):
                            raise ValueError(f"Invalid observation series_id: {observation.series_id}")
                        if not observation.query_id or not observation.query_id.startswith("stackexchange:"):
                            raise ValueError(f"Invalid observation query_id: {observation.query_id}")
                        if not observation.fetch_run_id:
                            raise ValueError("Missing fetch_run_id provenance on observation.")

                    run_provenance = {
                        stable_observation_id(observation): {
                            "query_id": observation.query_id or series.query_id,
                            "panel_version": observation.panel_version or PANEL_VERSION,
                            "fetch_run_id": run_id,
                        }
                        for observation in series.observations
                    }
                    inserted_by_series[series.series_id] = observation_store.insert_observations(
                        series.observations,
                        provenance_by_observation_id=run_provenance,
                    )
                except Exception:
                    storage_failed_series.add(series.series_id)
        inserted = sum(inserted_by_series.values())
        storage_error = bool(storage_failed_series)

        gaps = sorted({period for series in series_results for period in series.coverage_gaps})
        found = sorted({period for series in series_results for period in series.periods_found})
        data_periods = sorted({period for series in series_results for period in series.periods_with_records})
        all_storage_failed = bool(series_results) and len(storage_failed_series) == len(series_results)
        status = "failed" if not found or all_storage_failed else "partial" if provider_error or storage_error or gaps else "success"
        error = provider_error or ("Historical observations could not be stored in Firestore." if storage_error else None) or ("Historical source coverage was incomplete." if gaps else None)
        coverage_status = "unavailable" if status == "failed" and not found else "partial" if gaps else "complete"
        finished = {
            "completed_at": datetime.now(timezone.utc),
            "status": status,
            "records_fetched": sum(item.records_fetched for item in series_results),
            "records_normalized": sum(item.records_normalized for item in series_results),
            "records_processed": sum(item.records_processed for item in series_results),
            "records_rejected": sum(item.records_rejected for item in series_results),
            "records_filtered": sum(item.records_filtered for item in series_results),
            "records_unmatched": 0,
            "error": error,
            "error_category": next((item.error_category for item in series_results if item.error_category), None),
            "retry_after_seconds": max((item.retry_after_seconds or 0 for item in series_results), default=0) or None,
            "coverage_status": coverage_status,
            "requested_periods": periods,
            "periods_found": found,
            "coverage_gaps": gaps or ([period for period in periods if not found] if provider_error else []),
            "series_ids": [item.series_id for item in series_results],
            "available_start_period": data_periods[0] if data_periods else None,
            "available_end_period": data_periods[-1] if data_periods else None,
            "covered_start_period": found[0] if found else None,
            "covered_end_period": found[-1] if found else None,
            "api_requests": sum(item.requests_made for item in series_results),
            "quota_remaining": min((item.quota_remaining for item in series_results if item.quota_remaining is not None), default=None),
            "quota_max": min((item.quota_max for item in series_results if item.quota_max is not None), default=None),
            "observations_expected": len(observations),
            "observations_inserted": inserted,
            "raw_response_archive": ({
                "provider": "stackexchange",
                "fetch_run_id": run_id,
                "archive_reference": first_archive.get("archive_reference"),
                "archive_prefix": f"raw_response_archives/stackexchange__{run_id}__",
                "response_count": archive_count,
                "content_type": first_archive.get("content_type"),
            } if first_archive else None),
        }
        try:
            fetch_run_store.finish(run_id, finished)
        except Exception:
            status = "failed"
            error = "Historical fetch run could not be finalized."
        if series_results:
            for series in series_results:
                series_status = (
                    "failed" if series.series_id in storage_failed_series or provider_error or not series.periods_found
                    else "partial" if series.coverage_gaps
                    else "success"
                )
                series_error = ("Historical observations could not be stored in Firestore." if series.series_id in storage_failed_series else None) or provider_error or (
                    "Historical source coverage was incomplete." if series.coverage_gaps else None
                )
                results.append(_summary(
                    series, run_id, series_status, series_error,
                    inserted_by_series.get(series.series_id, 0), dry_run,
                ))
        else:
            results.append({"run_id": run_id, "skill": skill, "status": status, "error": error})
    return results


def _summary(series, run_id, status, error, inserted=0, dry_run=True):
    return {
        "run_id": run_id,
        "skill_id": series.skill_id,
        "skill": series.skill,
        "tag": series.tag,
        "query_id": series.query_id,
        "series_id": series.series_id,
        "status": status,
        "dry_run": dry_run,
        "periods_found": series.periods_found,
        "period_values": series.period_values,
        "periods_with_records": series.periods_with_records,
        "available_start_period": series.periods_with_records[0] if series.periods_with_records else None,
        "available_end_period": series.periods_with_records[-1] if series.periods_with_records else None,
        "coverage_gaps": series.coverage_gaps,
        "records_fetched": series.records_fetched,
        "records_normalized": series.records_normalized,
        "records_processed": series.records_processed,
        "records_rejected": series.records_rejected,
        "records_filtered": series.records_filtered,
        "observations_expected": len(series.observations),
        "observations_inserted": inserted,
        "api_requests": series.requests_made,
        "quota_remaining": series.quota_remaining,
        "quota_max": series.quota_max,
        "error_category": series.error_category,
        "error": error,
    }

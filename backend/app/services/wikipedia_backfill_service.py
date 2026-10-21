"""Orchestration service for backfilling genuine Wikipedia pageview observations into local SQLite.

Guarantees:
1. Operates strictly on local SQLite (MarketDataStore).
2. Zero Firebase / Firestore operations.
3. Checks existing SQLite observations to prevent redundant network requests.
4. Preserves deterministic IDs and atomic, idempotent insertion.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.market_data.wikipedia_provider import (
    WikipediaPageviewsProvider,
    get_completed_month_range,
    resolve_wikipedia_article_for_skill,
)
from app.storage.market_store import MarketDataStore
from app.storage.fetch_run_store import SQLiteFetchRunStore

logger = logging.getLogger(__name__)


def get_existing_wikipedia_periods_in_sqlite(
    store: MarketDataStore,
    skill_name: str,
    start_period: str,
    end_period: str,
) -> set[str]:
    """Check which monthly periods are already stored in local SQLite for this skill."""
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT period FROM market_observations
            WHERE lower(source) = 'wikipedia'
              AND lower(skill) = lower(?)
              AND period >= ?
              AND period <= ?
            """,
            (skill_name, start_period, end_period),
        ).fetchall()
        return {row["period"] for row in rows}


async def run_wikipedia_backfill(
    *,
    skills: list[str],
    start_period: str | None = None,
    end_period: str | None = None,
    db_path: str | Path,
    dry_run: bool = True,
    provider: WikipediaPageviewsProvider | None = None,
) -> dict[str, Any]:
    """Execute or plan a date-bounded Wikipedia technical-interest backfill.
    
    Args:
        skills: List of canonical skill names or IDs to backfill.
        start_period: Optional inclusive start month (YYYY-MM). Defaults to 12 months back.
        end_period: Optional inclusive end month (YYYY-MM). Defaults to last complete month.
        db_path: Path to the local SQLite database.
        dry_run: If True, plans the operation without making network calls or inserting data.
        provider: Optional custom provider instance (used for dependency injection / mocked tests).
    """
    if not skills:
        raise ValueError("At least one skill must be specified for Wikipedia backfill.")

    resolved_start, resolved_end, target_periods = get_completed_month_range(start_period, end_period)
    store = MarketDataStore(db_path)
    provider = provider or WikipediaPageviewsProvider()
    run_id = f"wikipedia-backfill-{uuid.uuid4().hex}"
    started_at = datetime.now(timezone.utc)
    run_store = SQLiteFetchRunStore(db_path)
    if not dry_run:
        run_store.start(run_id, {
            "source": "wikipedia",
            "collection_run_id": run_id,
            "status": "running",
            "started_at": started_at,
            "source_period_start": resolved_start,
            "source_period_end": resolved_end,
            "panel_version": provider.panel_version,
            "extractor_version": provider.extractor_version,
            "collection_scope": "global canonical skill allowlist",
        })

    results: list[dict[str, Any]] = []
    total_new_observations = 0
    total_skipped_existing = 0

    for skill_input in skills:
        try:
            definition, article = resolve_wikipedia_article_for_skill(skill_input)
        except ValueError as err:
            results.append({
                "skill": skill_input,
                "status": "unmapped",
                "article": None,
                "error": str(err),
            })
            continue

        existing_periods = get_existing_wikipedia_periods_in_sqlite(
            store, definition.name, resolved_start, resolved_end,
        )
        missing_periods = [p for p in target_periods if p not in existing_periods]

        if not missing_periods:
            results.append({
                "skill": definition.name,
                "skill_id": definition.skill_id,
                "article": article,
                "status": "already_complete",
                "target_periods_count": len(target_periods),
                "existing_periods_count": len(existing_periods),
                "observations_inserted": 0,
            })
            total_skipped_existing += len(existing_periods)
            continue

        if dry_run:
            results.append({
                "skill": definition.name,
                "skill_id": definition.skill_id,
                "article": article,
                "status": "dry_run",
                "target_periods": target_periods,
                "existing_periods": sorted(existing_periods),
                "periods_to_fetch": missing_periods,
                "observations_to_insert": len(missing_periods),
            })
            continue

        # Execute genuine API retrieval
        try:
            observations = await provider.fetch_observations_for_skill(
                definition.skill_id, resolved_start, resolved_end,
            )
            collected_at = datetime.now(timezone.utc)
            observations = [obs.model_copy(update={
                "fetch_run_id": run_id,
                "created_at": collected_at,
                "metadata": {
                    **(obs.metadata or {}),
                    "collection_timestamp_utc": collected_at.isoformat(),
                },
            }) for obs in observations]
            inserted = store.insert_observations(observations)
            total_new_observations += inserted
            results.append({
                "skill": definition.name,
                "skill_id": definition.skill_id,
                "article": article,
                "status": "success",
                "observations_fetched": len(observations),
                "observations_inserted": inserted,
                "periods_covered": [obs.period for obs in observations],
                "fetch_run_id": run_id,
            })
        except Exception as err:
            results.append({
                "skill": definition.name,
                "skill_id": definition.skill_id,
                "article": article,
                "status": "failed",
                "error": str(err),
            })

    failed_results = [item for item in results if item["status"] in {"failed", "unmapped"}]
    successful_results = [item for item in results if item["status"] in {"success", "already_complete"}]
    run_status = (
        "planned" if dry_run else
        "partial" if failed_results and successful_results else
        "failed" if failed_results else
        "success"
    )
    if not dry_run:
        run_store.finish(run_id, {
            "status": run_status,
            "completed_at": datetime.now(timezone.utc),
            "observations_inserted": total_new_observations,
            "results": results,
        })
    return {
        "source": "wikipedia",
        "signal_type": "interest",
        "start_period": resolved_start,
        "end_period": resolved_end,
        "target_periods_count": len(target_periods),
        "dry_run": dry_run,
        "db_path": str(db_path),
        "total_new_observations": total_new_observations,
        "total_skipped_existing": total_skipped_existing,
        "fetch_run_id": run_id,
        "collection_status": run_status,
        "results": results,
    }

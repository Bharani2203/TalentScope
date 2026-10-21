"""Offline Loader 2: Wikipedia Pageviews History Loader from August 2015 (Idempotent & Dry-Run Capable).

Purpose:
- Loads monthly Wikipedia article pageviews from `2015-08` onward using an explicit canonical
  skill allowlist (mapping canonical skills to unambiguous English Wikipedia article titles).
- Enforces denominator & raw-count rules:
  - If monthly total pageview denominators for the tracked technology panel or Wikimedia
    aggregate are provided for the same period, computes `normalized_share`.
  - Otherwise, stores raw pageview counts with `denominator=None` and attaches the warning
    `"raw count; platform volume changes may affect it"`.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from app.analytics.skill_normalization import canonical_skill_id, normalize_skill
from app.models.skill_intelligence import MarketObservation

WIKIPEDIA_MIN_PERIOD = "2015-08"
MAX_EXECUTE_OBSERVATIONS = 450
WIKIPEDIA_PROVIDER_PANEL_VERSION = "wikipedia-pageviews-v1"
WIKIPEDIA_PROVIDER_EXTRACTOR_VERSION = "wikimedia-pageviews-monthly-v1"

# Unambiguous canonical skill -> Wikipedia article allowlist
CANONICAL_WIKIPEDIA_ALLOWLIST: dict[str, str] = {
    "Python": "Python_(programming_language)",
    "Java": "Java_(programming_language)",
    "JavaScript": "JavaScript",
    "TypeScript": "TypeScript",
    "React": "React_(software)",
    "C#": "C_Sharp_(programming_language)",
    "SQL": "SQL",
    "Docker": "Docker_(software)",
    "Kubernetes": "Kubernetes",
    "Machine Learning": "Machine_learning",
    "Generative AI": "Generative_artificial_intelligence",
    "AWS": "Amazon_Web_Services",
    "Azure": "Microsoft_Azure",
    "FastAPI": "FastAPI",
    "PyTorch": "PyTorch",
    "TensorFlow": "TensorFlow",
}


def deterministic_wikipedia_obs_id(period: str, canon_id: str) -> str:
    digest = hashlib.sha256(f"wikipedia:en.wikipedia:{period}:{canon_id}".encode("utf-8")).hexdigest()[:16]
    return f"obs-wiki-{period}-{canon_id}-{digest}"


def parse_wikipedia_pageview_records(
    records: Sequence[dict[str, Any]],
    *,
    fetch_run_id: str = "offline-wikipedia-loader",
) -> tuple[list[MarketObservation], dict[tuple[str, str, str], float], list[str]]:
    """Validate and convert offline Wikipedia monthly pageview records from 2015-08 onward."""
    observations: list[MarketObservation] = []
    denominators: dict[tuple[str, str, str], float] = {}
    warnings: list[str] = []

    for rec in records:
        raw_skill = str(rec.get("skill") or "").strip()
        period = str(rec.get("period") or "").strip()
        if not raw_skill or not period:
            continue
        period_match = re.fullmatch(r"(\d{4})-(\d{2})", period)
        if not period_match or not 1 <= int(period_match.group(2)) <= 12:
            warnings.append(f"Skipped {raw_skill}: invalid monthly period '{period}'.")
            continue
        if period < WIKIPEDIA_MIN_PERIOD:
            warnings.append(f"Skipped {raw_skill} ({period}): precedes Wikimedia REST API start ({WIKIPEDIA_MIN_PERIOD}).")
            continue

        canon_name = normalize_skill(raw_skill)
        if canon_name not in CANONICAL_WIKIPEDIA_ALLOWLIST:
            warnings.append(f"Skipped '{raw_skill}': not in canonical Wikipedia article allowlist.")
            continue

        canon_id = canonical_skill_id(canon_name)
        if canon_id is None:
            warnings.append(f"Skipped '{raw_skill}': no canonical skill ID is registered.")
            continue
        article = CANONICAL_WIKIPEDIA_ALLOWLIST[canon_name]
        raw_views = rec.get("views")
        if raw_views is None:
            raw_views = rec.get("value")
        if raw_views is None or raw_views == "":
            warnings.append(f"Skipped {raw_skill} ({period}): pageview count is missing.")
            continue
        try:
            views = float(raw_views)
        except (TypeError, ValueError):
            warnings.append(f"Skipped {raw_skill} ({period}): pageview count is not numeric.")
            continue
        if not math.isfinite(views) or views < 0:
            warnings.append(f"Skipped {raw_skill} ({period}): pageview count must be a finite non-negative value.")
            continue
        denom = rec.get("denominator")
        if denom is None:
            denom = rec.get("panel_total_views")

        denom_val: float | None = None
        if denom not in (None, ""):
            try:
                parsed_denominator = float(denom)
            except (TypeError, ValueError):
                parsed_denominator = 0
                warnings.append(f"Period {period} ({canon_name}): invalid denominator; raw pageview count retained.")
            if math.isfinite(parsed_denominator) and parsed_denominator > 0:
                denom_val = parsed_denominator
                denominators[("wikipedia", "interest", period)] = denom_val
            elif parsed_denominator == 0:
                warnings.append(f"Period {period} ({canon_name}): denominator must be positive; raw pageview count retained.")
        if denom_val is None:
            msg = f"Period {period} ({canon_name}): raw count; platform volume changes may affect it"
            if msg not in warnings:
                warnings.append(msg)

        year, month = (int(x) for x in period.split("-", maxsplit=1))
        obs_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        period_end = calendar.monthrange(year, month)[1]
        obs_id = deterministic_wikipedia_obs_id(period, canon_id)

        observations.append(MarketObservation(
            id=obs_id,
            source="wikipedia",
            skill=canon_name,
            signal_type="interest",
            observed_at=obs_dt,
            period=period,
            posting_id=f"wiki:en:{article}:{period}",
            value=views,
            unit="pageviews",
            source_url=rec.get("evidence_url") or rec.get("source_url"),
            denominator_unit="pageviews" if denom_val is not None else None,
            denominator=denom_val,
            skill_id=canon_id,
            history_type="backfill",
            data_origin="real",
            fetch_run_id=fetch_run_id,
            series_id=f"wikipedia:en:interest:{canon_id}:v1",
            panel_version="allowlist_v1",
            scope="global",
            metadata={
                "article": article,
                "min_supported_period": WIKIPEDIA_MIN_PERIOD,
                "source_family": "encyclopedia_pageviews",
                "metric": "pageviews",
                "unit": "pageviews per calendar month",
                "denominator_unit": "tracked panel pageviews per calendar month",
                "period_start": f"{period}-01",
                "period_end": f"{year:04d}-{month:02d}-{period_end:02d}",
                "evidence_reference": rec.get("evidence_url") or rec.get("source_url") or "https://www.mediawiki.org/wiki/REST_API#Pageviews_data",
                "readiness": "share_ready" if denom_val is not None else "raw_count_only",
                "warning": None if denom_val else "raw count; platform volume changes may affect it",
            },
        ))

    return observations, denominators, warnings


def run_loader(
    input_path: Path,
    *,
    dry_run: bool = True,
    max_observations: int = MAX_EXECUTE_OBSERVATIONS,
    fetch_run_id: str | None = None,
    observation_store: Any | None = None,
) -> dict[str, Any]:
    if not 1 <= max_observations <= MAX_EXECUTE_OBSERVATIONS:
        raise ValueError(f"max_observations must be between 1 and {MAX_EXECUTE_OBSERVATIONS}.")
    if not input_path.exists():
        return {
            "status": "blocked",
            "reason": f"Offline Wikipedia pageview file not found at {input_path}.",
            "dry_run": dry_run,
            "loaded_count": 0,
        }
    raw_input = input_path.read_bytes()
    payload = json.loads(raw_input.decode("utf-8"))
    records = payload if isinstance(payload, list) else payload.get("records", [])
    content_hash = hashlib.sha256(raw_input).hexdigest()
    run_id = fetch_run_id or f"wikipedia-offline-{content_hash[:20]}"
    obs, denoms, warnings = parse_wikipedia_pageview_records(records, fetch_run_id=run_id)
    for observation in obs:
        observation.metadata["input_file"] = input_path.name
        observation.metadata["input_sha256"] = content_hash
    if not dry_run and len(obs) > max_observations:
        return {
            "status": "blocked",
            "reason": f"Execution limit is {max_observations} observations; input contains {len(obs)}. Split the input into reviewed smaller ranges.",
            "dry_run": False,
            "observation_count": len(obs),
            "inserted_count": 0,
            "fetch_run_id": run_id,
        }
    inserted = 0
    if not dry_run:
        if observation_store is None:
            from app.storage.firestore_observation_store import FirestoreObservationStore
            observation_store = FirestoreObservationStore()
        inserted = observation_store.insert_observations(obs)
    return {
        "status": "ready",
        "dry_run": dry_run,
        "observation_count": len(obs),
        "inserted_count": inserted,
        "periods_with_valid_denominator": len(denoms),
        "fetch_run_id": run_id,
        "input_sha256": content_hash,
        "warnings": warnings,
    }


def transfer_reviewed_wikipedia_sqlite_observations(
    *,
    database_path: str | Path,
    observation_store: Any,
    review_approved: bool = False,
    skill: str | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Copy validated provider backfill rows from SQLite to the approved store.

    This is deliberately an explicit library operation: callers must provide an
    observation store (there is no implicit Firebase client fallback) and attest
    that the bounded input was reviewed. SQLite is opened read-only. Existing
    SQLite rows and stable observation IDs are never rewritten.
    """
    if not review_approved:
        raise ValueError("Explicit review approval is required before SQLite transfer.")
    if observation_store is None:
        raise ValueError("An explicitly injected observation store is required.")
    if getattr(observation_store, "client", object()) is None:
        raise ValueError("Injected Firestore repository must have an explicit client; implicit initialization is disabled.")

    from app.services.market_data.wikipedia_provider import resolve_wikipedia_article_for_skill
    from app.storage.market_store import MarketDataStore

    clock = as_of or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("as_of must include a timezone.")
    clock = clock.astimezone(timezone.utc)
    requested_definition = None
    if skill:
        requested_definition, _ = resolve_wikipedia_article_for_skill(skill)

    source_store = MarketDataStore(database_path, read_only=True)
    rows = source_store.get_observations(
        skill=requested_definition.name if requested_definition else None,
        include_test=True,
    )
    candidates = [item for item in rows if item.source.casefold() == "wikipedia"]
    if requested_definition:
        candidates = [item for item in candidates if item.skill_id == requested_definition.skill_id]

    approved: list[MarketObservation] = []
    rejected: list[dict[str, str]] = []
    seen_periods: set[tuple[str, str]] = set()
    for item in candidates:
        label = item.id or f"{item.skill_id}:{item.period}"
        try:
            definition, article = resolve_wikipedia_article_for_skill(item.skill_id or item.skill)
            metadata = item.metadata or {}
            quality = item.quality or {}
            raw_collected_at = metadata.get("collection_timestamp_utc")
            collected_at = datetime.fromisoformat(raw_collected_at) if isinstance(raw_collected_at, str) else None
            period_match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", item.period or "")
            if (
                item.signal_type != "interest" or item.data_origin != "real"
                or item.history_type != "backfill" or item.scope != "global" or item.location
                or not period_match or item.period >= clock.strftime("%Y-%m")
                or item.observed_at.tzinfo is None
                or item.observed_at.astimezone(timezone.utc).strftime("%Y-%m") != item.period
                or collected_at is None or collected_at.tzinfo is None or collected_at > clock
                or item.created_at is None or item.created_at.tzinfo is None
                or item.created_at.astimezone(timezone.utc) != collected_at.astimezone(timezone.utc)
                or item.unit != "pageviews" or item.panel_version != WIKIPEDIA_PROVIDER_PANEL_VERSION
                or item.extractor_version != WIKIPEDIA_PROVIDER_EXTRACTOR_VERSION
                or item.series_id != f"wikipedia:pageviews:{definition.skill_id}:v1"
                or not item.fetch_run_id or not item.query_id or not item.id or not item.source_url
                or metadata.get("metric") != "wikipedia_monthly_pageviews"
                or metadata.get("project") != "en.wikipedia"
                or metadata.get("access") != "all-access" or metadata.get("agent") != "user"
                or metadata.get("granularity") != "monthly" or metadata.get("article") != article
                or quality.get("measure") != "Wikimedia pageviews REST API"
                or quality.get("verified_article") != article
                or urlparse(item.source_url).hostname not in {"wikimedia.org", "www.wikimedia.org"}
                or not math.isfinite(float(item.value)) or item.value < 0
            ):
                raise ValueError("row does not match the completed Wikimedia monthly backfill contract")
            if item.denominator is not None and (
                not math.isfinite(float(item.denominator)) or item.denominator <= 0
                or item.denominator_unit != "pageviews"
            ):
                raise ValueError("row has an invalid pageview denominator")
            period_key = (definition.skill_id, item.period)
            if period_key in seen_periods:
                raise ValueError("duplicate skill-period row in SQLite input")
            seen_periods.add(period_key)
            reviewed_metadata = dict(metadata)
            reviewed_metadata["sqlite_transfer_review"] = {
                "status": "approved",
                "reviewed_at": clock.isoformat(),
                "review_scope": "Wikimedia monthly pageviews provider provenance and completed-period schema",
            }
            approved.append(item.model_copy(update={"metadata": reviewed_metadata}))
        except (TypeError, ValueError, OverflowError) as exc:
            rejected.append({"observation_id": label, "reason": str(exc)})

    # Refuse a partial series transfer: a single rejected Wikipedia row means
    # the SQLite selection needs review before it can become V2-readable.
    if rejected:
        return {
            "status": "rejected", "review_approved": True,
            "candidate_count": len(candidates), "accepted_count": 0,
            "rejected": rejected, "inserted_count": 0,
        }

    if not approved:
        return {
            "status": "no_data", "review_approved": True,
            "candidate_count": 0, "accepted_count": 0,
            "rejected": [], "inserted_count": 0,
        }

    readback: dict[str, MarketObservation] = {}
    for skill_name in sorted({item.skill for item in approved}):
        for item in observation_store.get_observations_by_skill(
            skill_name, cutoff=datetime(2000, 1, 1, tzinfo=timezone.utc),
            source="wikipedia", signal_type="interest",
        ):
            if item.id:
                readback[item.id] = item
    preexisting_unreviewed = [
        item.id for item in approved
        if item.id in readback
        and (readback[item.id].metadata or {}).get("sqlite_transfer_review", {}).get("status") != "approved"
    ]
    if preexisting_unreviewed:
        return {
            "status": "rejected", "review_approved": True,
            "candidate_count": len(candidates), "accepted_count": 0,
            "rejected": [{"observation_id": item_id, "reason": "stable ID already exists without reviewed-transfer provenance"}
                         for item_id in preexisting_unreviewed],
            "inserted_count": 0,
        }

    inserted = observation_store.insert_observations(approved)
    readback = {}
    for skill_name in sorted({item.skill for item in approved}):
        for item in observation_store.get_observations_by_skill(
            skill_name, cutoff=datetime(2000, 1, 1, tzinfo=timezone.utc),
            source="wikipedia", signal_type="interest",
        ):
            if item.id:
                readback[item.id] = item
    missing = [item.id for item in approved if item.id not in readback]
    unmarked = [
        item.id for item in approved
        if item.id in readback
        and (readback[item.id].metadata or {}).get("sqlite_transfer_review", {}).get("status") != "approved"
    ]
    if missing or unmarked:
        raise RuntimeError("Approved-store read-back verification failed for the reviewed Wikipedia transfer.")
    return {
        "status": "ready", "review_approved": True,
        "candidate_count": len(candidates), "accepted_count": len(approved),
        "inserted_count": inserted, "rejected": [],
        "observation_ids": [item.id for item in approved],
        "readback_verified": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline Wikipedia pageviews loader (from 2015-08).")
    parser.add_argument("--input", type=Path, required=True, help="Path to offline JSON records.")
    parser.add_argument("--execute", action="store_true", help="Persist reviewed offline observations to Firestore.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing (the default).")
    parser.add_argument("--max-observations", type=int, default=MAX_EXECUTE_OBSERVATIONS, help="Per-run write cap (maximum 450).")
    parser.add_argument("--fetch-run-id", help="Optional provenance ID for this import run.")
    args = parser.parse_args()
    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run cannot be used together.")
    print(json.dumps(run_loader(args.input, dry_run=not args.execute, max_observations=args.max_observations, fetch_run_id=args.fetch_run_id), indent=2))

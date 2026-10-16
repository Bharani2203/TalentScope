"""Offline Loader 1: Stack Exchange Share Series Loader (Idempotent & Dry-Run Capable).

Purpose:
- Loads monthly Stack Exchange question counts per canonical skill AND total monthly question
  denominators from an offline Stack Exchange dump or pre-exported JSON/CSV archive.
- Enforces the denominator rule:
  - If valid monthly total question denominators are present for the same period, stores
    `denominator` so `normalized_share = skill_questions / total_questions` is computed.
  - If no monthly total question denominator is present (as with the live Stack Exchange REST
    API `/2.3/questions` filter total when tag-scoped only), records `denominator=None` and
    attaches the warning `"raw count; platform volume changes may affect it"`.
- Never fabricates missing denominators or executes live network backfills during automated tests.
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

from app.analytics.skill_normalization import canonical_skill_id, normalize_skill
from app.models.skill_intelligence import MarketObservation

MAX_EXECUTE_OBSERVATIONS = 450


def deterministic_stackexchange_obs_id(period: str, canon_id: str, site: str = "stackoverflow") -> str:
    digest = hashlib.sha256(f"stackexchange:{site}:{period}:{canon_id}".encode("utf-8")).hexdigest()[:16]
    return f"obs-se-{site}-{period}-{canon_id}-{digest}"


def parse_stackexchange_share_records(
    records: Sequence[dict[str, Any]],
    *,
    fetch_run_id: str = "offline-se-share-loader",
    site: str = "stackoverflow",
) -> tuple[list[MarketObservation], dict[tuple[str, str, str], float], list[str]]:
    """Convert offline Stack Exchange monthly records into validated MarketObservation objects."""
    observations: list[MarketObservation] = []
    denominators: dict[tuple[str, str, str], float] = {}
    warnings: list[str] = []

    for rec in records:
        raw_skill = str(rec.get("skill") or rec.get("tag") or "").strip()
        period = str(rec.get("period") or "").strip()
        if not raw_skill or not period:
            continue
        period_match = re.fullmatch(r"(\d{4})-(\d{2})", period)
        if not period_match or not 1 <= int(period_match.group(2)) <= 12:
            warnings.append(f"Skipped {raw_skill}: invalid monthly period '{period}'.")
            continue
        raw_count = rec.get("question_count")
        if raw_count is None:
            raw_count = rec.get("value")
        if raw_count is None or raw_count == "":
            warnings.append(f"Skipped {raw_skill} ({period}): question_count is missing.")
            continue
        try:
            question_count = float(raw_count)
        except (TypeError, ValueError):
            warnings.append(f"Skipped {raw_skill} ({period}): question_count is not numeric.")
            continue
        if not math.isfinite(question_count) or question_count < 0:
            warnings.append(f"Skipped {raw_skill} ({period}): question_count must be a finite non-negative value.")
            continue
        canon_id = canonical_skill_id(raw_skill)
        if canon_id is None:
            warnings.append(f"Skipped '{raw_skill}': no canonical skill ID is registered.")
            continue
        total_questions = rec.get("total_site_questions")
        if total_questions is None:
            total_questions = rec.get("denominator")
        canon_name = normalize_skill(raw_skill)

        denom_val: float | None = None
        if total_questions not in (None, ""):
            try:
                parsed_denominator = float(total_questions)
            except (TypeError, ValueError):
                parsed_denominator = 0
                warnings.append(f"Period {period} ({canon_name}): invalid denominator; raw question count retained.")
            if math.isfinite(parsed_denominator) and parsed_denominator > 0:
                denom_val = parsed_denominator
                denominators[("stackexchange", "interest", period)] = denom_val
            elif parsed_denominator == 0:
                warnings.append(f"Period {period} ({canon_name}): denominator must be positive; raw question count retained.")
        if denom_val is None:
            msg = f"Period {period} ({canon_name}): raw count; platform volume changes may affect it"
            if msg not in warnings:
                warnings.append(msg)

        obs_id = deterministic_stackexchange_obs_id(period, canon_id, site=site)
        year, month = (int(x) for x in period.split("-", maxsplit=1))
        obs_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        period_end = calendar.monthrange(year, month)[1]

        observations.append(MarketObservation(
            id=obs_id,
            source="stackexchange",
            skill=canon_name,
            signal_type="interest",
            observed_at=obs_dt,
            period=period,
            posting_id=f"se:{site}:{period}:{canon_id}",
            value=question_count,
            unit="questions",
            source_url=rec.get("evidence_url") or rec.get("source_url") or f"https://api.stackexchange.com/2.3/questions?site={site}",
            denominator_unit="questions" if denom_val is not None else None,
            denominator=denom_val,
            skill_id=canon_id,
            history_type="backfill",
            data_origin="real",
            fetch_run_id=fetch_run_id,
            series_id=f"stackexchange:{site}:interest:{canon_id}:v1",
            panel_version="v1",
            scope="global",
            metadata={
                "site": site,
                "raw_tag": raw_skill,
                "total_site_questions": denom_val,
                "source_family": "community_question_activity",
                "metric": "question_count",
                "unit": "questions per calendar month",
                "denominator_unit": "site questions per calendar month",
                "period_start": f"{period}-01",
                "period_end": f"{year:04d}-{month:02d}-{period_end:02d}",
                "evidence_reference": rec.get("evidence_url") or rec.get("source_url") or f"https://api.stackexchange.com/2.3/questions?site={site}",
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
            "reason": f"Offline dump file not found at {input_path}. Provide a verified Stack Exchange monthly dump JSON.",
            "dry_run": dry_run,
            "loaded_count": 0,
        }
    raw_input = input_path.read_bytes()
    payload = json.loads(raw_input.decode("utf-8"))
    records = payload if isinstance(payload, list) else payload.get("records", [])
    content_hash = hashlib.sha256(raw_input).hexdigest()
    run_id = fetch_run_id or f"se-offline-{content_hash[:20]}"
    obs, denoms, warnings = parse_stackexchange_share_records(records, fetch_run_id=run_id)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline Stack Exchange share series loader.")
    parser.add_argument("--input", type=Path, required=True, help="Path to offline JSON records.")
    parser.add_argument("--execute", action="store_true", help="Persist reviewed offline observations to Firestore.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing (the default).")
    parser.add_argument("--max-observations", type=int, default=MAX_EXECUTE_OBSERVATIONS, help="Per-run write cap (maximum 450).")
    parser.add_argument("--fetch-run-id", help="Optional provenance ID for this import run.")
    args = parser.parse_args()
    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run cannot be used together.")
    print(json.dumps(run_loader(args.input, dry_run=not args.execute, max_observations=args.max_observations, fetch_run_id=args.fetch_run_id), indent=2))

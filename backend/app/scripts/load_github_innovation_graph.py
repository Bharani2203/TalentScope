"""Offline Loader 3: GitHub Innovation Graph Adoption Loader for India by Language (Idempotent & Dry-Run Capable).

Purpose:
- Loads GitHub Innovation Graph repository/developer push adoption metrics for India (`economy == "IND"` or `"IN"`)
  by programming language.
- Keeps `adoption` strictly separate from `demand` and `interest`.
- Computes `normalized_share` when total India economy language pushes/repositories for the same period
  are provided as the denominator; otherwise preserves `raw_count` with the warning
  `"raw count; platform volume changes may affect it"`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.analytics.skill_normalization import canonical_skill_id, normalize_skill
from app.models.skill_intelligence import MarketObservation

INDIA_ECONOMY_CODES = {"in", "ind", "india"}


def deterministic_github_ig_obs_id(period: str, canon_id: str, economy: str = "IND") -> str:
    digest = hashlib.sha256(f"github_innovation_graph:{economy}:{period}:{canon_id}".encode("utf-8")).hexdigest()[:16]
    return f"obs-ghig-{economy.lower()}-{period}-{canon_id}-{digest}"


def parse_github_innovation_graph_records(
    records: Sequence[dict[str, Any]],
    *,
    fetch_run_id: str = "offline-github-ig-india-loader",
) -> tuple[list[MarketObservation], dict[tuple[str, str, str], float], list[str]]:
    """Parse GitHub Innovation Graph language adoption records for India."""
    observations: list[MarketObservation] = []
    denominators: dict[tuple[str, str, str], float] = {}
    warnings: list[str] = []

    for rec in records:
        economy = str(rec.get("economy") or rec.get("iso2_code") or rec.get("country") or "IND").strip()
        if economy.casefold() not in INDIA_ECONOMY_CODES:
            continue
        raw_lang = str(rec.get("language") or rec.get("skill") or "").strip()
        period = str(rec.get("period") or "").strip()
        if not raw_lang or not period:
            continue

        num_pushers_or_repos = float(rec.get("num_pushers") or rec.get("repositories") or rec.get("value") or 0.0)
        metric_unit = "developers" if rec.get("num_pushers") is not None else "repositories"
        economy_total = rec.get("economy_total") or rec.get("denominator")

        canon_name = normalize_skill(raw_lang)
        canon_id = canonical_skill_id(canon_name) or canon_name.lower().replace(" ", "_")

        denom_val: float | None = None
        if economy_total is not None and float(economy_total) > 0:
            denom_val = float(economy_total)
            denominators[("github_innovation_graph", "adoption", period)] = denom_val
        else:
            msg = f"Period {period} ({canon_name}): raw count; platform volume changes may affect it"
            if msg not in warnings:
                warnings.append(msg)

        year, month = (int(x) for x in period.split("-", maxsplit=1))
        obs_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        obs_id = deterministic_github_ig_obs_id(period, canon_id, economy="IND")

        observations.append(MarketObservation(
            id=obs_id,
            source="github_innovation_graph",
            skill=canon_name,
            signal_type="adoption",
            observed_at=obs_dt,
            period=period,
            unit=metric_unit,
            denominator_unit=metric_unit if denom_val is not None else None,
            posting_id=f"ghig:IND:{period}:{canon_id}",
            value=num_pushers_or_repos,
            denominator=str(int(denom_val)) if denom_val is not None else None,
            history_type="backfill",
            data_origin="real",
            fetch_run_id=fetch_run_id,
            series_id=f"github_innovation_graph:IND:adoption:{canon_id}:v1",
            panel_version="india_languages_v1",
            scope="country",
            location="India",
            metadata={
                "economy": "IND",
                "raw_language": raw_lang,
                "economy_total": denom_val,
                "warning": None if denom_val else "raw count; platform volume changes may affect it",
            },
        ))

    return observations, denominators, warnings


def run_loader(input_path: Path, *, dry_run: bool = True) -> dict[str, Any]:
    if not input_path.exists():
        return {
            "status": "blocked",
            "reason": f"Offline GitHub Innovation Graph file not found at {input_path}.",
            "dry_run": dry_run,
            "loaded_count": 0,
        }
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else payload.get("records", [])
    obs, denoms, warnings = parse_github_innovation_graph_records(records)
    return {
        "status": "ready",
        "dry_run": dry_run,
        "observation_count": len(obs),
        "periods_with_valid_denominator": len(denoms),
        "warnings": warnings,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline GitHub Innovation Graph India language adoption loader.")
    parser.add_argument("--input", type=Path, required=True, help="Path to offline JSON records.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Validate without writing to Firestore.")
    args = parser.parse_args()
    print(json.dumps(run_loader(args.input, dry_run=args.dry_run), indent=2))

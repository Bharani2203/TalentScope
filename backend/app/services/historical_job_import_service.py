"""Historical Job Postings Import Service for TalentScope.ai.

Ingests public historical job postings (e.g. Fliarbi CC BY-NC 4.0 India & US dataset)
into local SQLite storage idempotently with full data provenance, analytical
denominators, and strict country isolation.

Guarantees:
1. CC BY-NC 4.0 attribution and non-commercial provenance metadata attached to all observations.
2. Strict country partitioning: India ('IN') and US ('US') postings are never merged.
3. Strict deduplication by (source, posting_id) and (company, title, period, country).
4. Analytical readiness compliance: 6 months of data enables 4-month trend gate,
   while strictly keeping 24-month forecast gate and 36-month half-life gate as insufficient_data.
5. Zero network calls or external API calls during import or testing.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.models.skill_intelligence import MarketObservation
from app.storage.market_store import MarketDataStore

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "fliarbi"
DEFAULT_DATASET = "job-postings-2026"
DEFAULT_LICENSE = "CC BY-NC 4.0"
DEFAULT_PANEL_VERSION = "job-demand-v1"
DEFAULT_EXTRACTOR_VERSION = "skill-extractor-v1"
ALLOWED_COUNTRIES = frozenset({"IN", "US"})
VALID_DATE_RANGE = ("2026-01-01", "2026-06-30")


def normalize_country_code(country_raw: str | None) -> str | None:
    """Normalize input country text to ISO-2 uppercase code."""
    if not country_raw:
        return None
    code = country_raw.strip().upper()
    if code in ("IN", "INDIA"):
        return "IN"
    if code in ("US", "USA", "UNITED STATES"):
        return "US"
    return code if len(code) == 2 else None


def parse_and_validate_date(date_str: str | None, min_date: str = "2026-01-01", max_date: str = "2026-06-30") -> tuple[bool, str | None, datetime | None]:
    """Validate date string format YYYY-MM-DD within allowed historical boundaries."""
    if not date_str:
        return False, None, None
    text = date_str.strip()
    try:
        dt = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return False, None, None
    if not (min_date <= text <= max_date):
        return False, None, None
    return True, text[:7], dt


def parse_posting_skills(skills_raw: str | None) -> list[str]:
    """Extract individual skill strings from raw CSV skills field."""
    if not skills_raw:
        return []
    text = skills_raw.strip()
    if not text:
        return []
    # Pipe delimiter takes precedence
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
    elif "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
    else:
        parts = [text]
    return [p for p in parts if len(p) >= 2]


class HistoricalJobImportService:
    """Idempotent importer for historical job-demand datasets into local SQLite."""

    def __init__(self, store: MarketDataStore | None = None) -> None:
        self.store = store or MarketDataStore()

    def import_from_csv(
        self,
        file_path: str | Path,
        *,
        target_country: str = "IN",
        dry_run: bool = False,
        limit_rows: int | None = None,
        min_date: str = VALID_DATE_RANGE[0],
        max_date: str = VALID_DATE_RANGE[1],
        batch_size: int = 5000,
    ) -> dict[str, Any]:
        """Ingest job postings from CSV file into SQLite.
        
        Args:
            file_path: Path to dataset CSV file.
            target_country: 'IN' or 'US'. Countries are never merged.
            dry_run: If True, validates and calculates stats without DB writes.
            limit_rows: Optional row count limit for tests.
            min_date: Minimum posted date (YYYY-MM-DD).
            max_date: Maximum posted date (YYYY-MM-DD).
            batch_size: DB batch commit chunk size.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Historical dataset file not found: {path}")

        target_c = normalize_country_code(target_country)
        if not target_c or target_c not in ALLOWED_COUNTRIES:
            raise ValueError(f"Target country must be one of {sorted(ALLOWED_COUNTRIES)}; got '{target_country}'")

        stats = {
            "source": DEFAULT_SOURCE,
            "dataset": DEFAULT_DATASET,
            "license": DEFAULT_LICENSE,
            "country": target_c,
            "dry_run": dry_run,
            "total_rows_read": 0,
            "rows_matched_country": 0,
            "valid_postings": 0,
            "rejected_invalid_date": 0,
            "rejected_missing_skills": 0,
            "rejected_duplicates": 0,
            "postings_by_period": {},
            "observations_generated": 0,
            "observations_inserted": 0,
            "postings_inserted": 0,
            "distinct_skills_tracked": 0,
            "readiness_summary": {},
        }

        seen_posting_ids: set[str] = set()
        seen_duplicates: set[tuple[str, str, str, str]] = set()
        valid_postings: list[dict[str, Any]] = []
        postings_per_period: dict[str, int] = {}

        # 1. First Pass: Read, validate, filter by country and deduplicate
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["total_rows_read"] += 1
                if limit_rows and stats["total_rows_read"] > limit_rows:
                    break

                row_country = normalize_country_code(row.get("country"))
                if row_country != target_c:
                    continue
                stats["rows_matched_country"] += 1

                posting_id = str(row.get("posting_id") or "").strip()
                if not posting_id or posting_id in seen_posting_ids:
                    stats["rejected_duplicates"] += 1
                    continue

                posted_date_str = str(row.get("posted_date") or "").strip()
                is_valid_date, period, posted_dt = parse_and_validate_date(
                    posted_date_str, min_date=min_date, max_date=max_date
                )
                if not is_valid_date or not period or not posted_dt:
                    stats["rejected_invalid_date"] += 1
                    continue

                company = str(row.get("company") or "").strip()
                title = str(row.get("title") or "").strip()
                dedup_key = (company.lower(), title.lower(), period, target_c)
                if dedup_key in seen_duplicates:
                    stats["rejected_duplicates"] += 1
                    continue

                raw_skills = parse_posting_skills(row.get("skills"))
                if not raw_skills:
                    stats["rejected_missing_skills"] += 1
                    continue

                seen_posting_ids.add(posting_id)
                seen_duplicates.add(dedup_key)

                # Collect normalized skills for this posting
                cleaned_skills: list[str] = []
                for s in raw_skills:
                    norm = normalize_skill(s)
                    if norm and len(norm) >= 2 and norm not in cleaned_skills:
                        cleaned_skills.append(norm)

                if not cleaned_skills:
                    stats["rejected_missing_skills"] += 1
                    continue

                postings_per_period[period] = postings_per_period.get(period, 0) + 1

                salary = None
                try:
                    sal_val = row.get("salary_annual_usd")
                    if sal_val and str(sal_val).strip() not in ("nan", ""):
                        salary = float(sal_val)
                except (ValueError, TypeError):
                    salary = None

                valid_postings.append({
                    "posting_id": posting_id,
                    "posted_date": posted_date_str,
                    "period": period,
                    "posted_dt": posted_dt,
                    "title": title,
                    "company": company,
                    "role": row.get("role"),
                    "category": row.get("category"),
                    "city": row.get("city"),
                    "region": row.get("region"),
                    "country": target_c,
                    "skills": cleaned_skills,
                    "salary_annual_usd": salary,
                    "source": DEFAULT_SOURCE,
                })

        stats["valid_postings"] = len(valid_postings)
        stats["postings_by_period"] = dict(sorted(postings_per_period.items()))

        # 2. Second Pass: Generate MarketObservation records with analytical denominators
        all_observations: list[MarketObservation] = []
        distinct_skills: set[str] = set()

        for p in valid_postings:
            period = p["period"]
            total_period_postings = float(postings_per_period.get(period, 1))
            observed_at = datetime(
                p["posted_dt"].year,
                p["posted_dt"].month,
                15,
                12,
                0,
                0,
                tzinfo=timezone.utc,
            )

            for skill in p["skills"]:
                distinct_skills.add(skill)
                c_id = canonical_skill_id(skill)
                skill_slug = c_id or skill.lower().replace(" ", "-")

                stable_key = f"{DEFAULT_SOURCE}|{p['posting_id']}|{skill.lower()}|{period}|{target_c}"
                obs_id = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()

                series_id = f"{DEFAULT_SOURCE}:{DEFAULT_PANEL_VERSION}:job-demand:{skill_slug}:{DEFAULT_EXTRACTOR_VERSION}"

                obs = MarketObservation(
                    id=obs_id,
                    source=DEFAULT_SOURCE,
                    skill=skill,
                    skill_id=c_id,
                    location=target_c,
                    scope="country",
                    observed_at=observed_at,
                    provider_posted_at=p["posted_dt"],
                    period=period,
                    posting_id=p["posting_id"],
                    signal_type="demand",
                    history_type="backfill",
                    data_origin="real",
                    value=1.0,
                    unit="job_postings",
                    denominator=total_period_postings,
                    denominator_unit="job_postings",
                    observation_count=1,
                    panel_version=DEFAULT_PANEL_VERSION,
                    query_id="historical-sample",
                    extractor_version=DEFAULT_EXTRACTOR_VERSION,
                    series_id=series_id,
                    metadata={
                        "source": DEFAULT_SOURCE,
                        "license": DEFAULT_LICENSE,
                        "dataset": DEFAULT_DATASET,
                        "is_sample": True,
                        "company": p["company"],
                        "title": p["title"],
                        "city": p["city"],
                        "country": target_c,
                        "period_total_postings": int(total_period_postings),
                    },
                )
                all_observations.append(obs)

        stats["observations_generated"] = len(all_observations)
        stats["distinct_skills_tracked"] = len(distinct_skills)

        # 3. Third Pass: Idempotent Database Write (if not dry_run)
        if not dry_run:
            # Insert postings into historical_job_postings
            inserted_postings = self.store.insert_historical_postings(valid_postings)
            stats["postings_inserted"] = inserted_postings

            # Insert observations in chunks
            total_obs_inserted = 0
            for i in range(0, len(all_observations), batch_size):
                chunk = all_observations[i : i + batch_size]
                total_obs_inserted += self.store.insert_observations(chunk)
            stats["observations_inserted"] = total_obs_inserted
        else:
            stats["postings_inserted"] = 0
            stats["observations_inserted"] = 0

        # 4. Assess Analytical Readiness
        num_periods = len(postings_per_period)
        stats["readiness_summary"] = {
            "completed_months_available": num_periods,
            "trend_ready": num_periods >= 4,
            "forecast_ready": num_periods >= 24,
            "half_life_ready": num_periods >= 36,
            "note": (
                f"Historical demand observations cover {num_periods} consecutive completed months ({sorted(postings_per_period.keys())}). "
                "Satisfies trend gate (>=4 months). Strictly insufficient for forecast (>=24 months) and half-life (>=36 months)."
            ),
        }

        return stats

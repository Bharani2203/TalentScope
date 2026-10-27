"""Indian Market Dataset Ingestion & Live API Pull Script for TalentScope.ai.

Combines:
  Task A: Historical CSV ingestion from backend/data/raw/indian_tech_career_intelligence_2026.csv
  Task B: Capped live API pull from TheirStack & Fliar (Radar) APIs

CLI Usage:
  python backend/scripts/ingest_indian_market_data.py --dry-run
  python backend/scripts/ingest_indian_market_data.py --ingest
  python backend/scripts/ingest_indian_market_data.py --probe
  python backend/scripts/ingest_indian_market_data.py --fetch-live
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dotenv
import httpx

# Ensure backend root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Mandatory Firestore emulator environment variables
os.environ.setdefault("TALENTSCOPE_FIREBASE_MODE", "emulator")
os.environ.setdefault("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
os.environ.setdefault("ENVIRONMENT", "local-test")
os.environ.setdefault("FIREBASE_PROJECT_ID", "demo-talentscope-local")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from app.core.firebase import get_firestore_client
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.intelligence_v2.occupation_names import resolve_role_alias
from app.services.job_storage_service import _normalize_city

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_indian_market_data")

DEFAULT_PANEL_VERSION = "job-demand-v1"
DEFAULT_EXTRACTOR_VERSION = "skill-extractor-v1"
FIRESTORE_BATCH_LIMIT = 400

# Task B Strict Circuit-Breaker Maximums
MAX_THEIRSTACK_JOBS = 90
MAX_FLIAR_REQUESTS = 180
LIVE_GATE_BOUNDARY = datetime(2026, 10, 15, tzinfo=timezone.utc)


def load_api_credentials() -> dict[str, str]:
    """Load API credentials safely using dotenv without printing or exposing values."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.is_file():
        env_file = Path("backend/.env")
    
    vals = dotenv.dotenv_values(str(env_file)) if env_file.is_file() else {}
    return {
        "FLIAR_API_KEY": str(vals.get("FLIAR_API_KEY") or "").strip(),
        "RADAR_API_URL": str(vals.get("RADAR_API_URL") or "").strip(),
        "THEIRSTACK_API_KEY": str(vals.get("THEIRSTACK_API_KEY") or "").strip(),
        "THEIRSTACK_API_URL": str(vals.get("THEIRSTACK_API_URL") or "").strip(),
    }


def parse_date(date_str: str | None) -> tuple[datetime | None, str | None]:
    """Parse date string into UTC datetime and YYYY-MM period."""
    if not date_str:
        return None, None
    text = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(text[:19] if "T" in text else text, fmt[:19] if "T" in fmt else fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt, dt.strftime("%Y-%m")
        except ValueError:
            continue
    return None, None


def parse_skills(raw_skills: Any) -> list[str]:
    """Extract and normalize skills from string or list format."""
    if not raw_skills:
        return []
    if isinstance(raw_skills, list):
        items = [str(s) for s in raw_skills]
    else:
        items = re.split(r"[,|;]+", str(raw_skills).strip())
    
    cleaned: list[str] = []
    for p in items:
        token = p.strip()
        if len(token) >= 2:
            norm = normalize_skill(token)
            if norm and norm not in cleaned:
                cleaned.append(norm)
    return cleaned


def generate_stable_id(prefix: str, *parts: str) -> str:
    """Generate deterministic sha256 document identifier."""
    content = "|".join(str(p).strip().casefold() for p in parts)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"


# ============================================================================
# Task A: CSV Dataset Ingestion
# ============================================================================

class IndianMarketDataIngestor:
    """Handles parsing and ingestion of historical Indian tech job postings."""

    def __init__(self, raw_data_dir: Path | None = None) -> None:
        self.raw_data_dir = raw_data_dir or RAW_DATA_DIR
        self.tech_csv_path = self.raw_data_dir / "indian_tech_career_intelligence_2026.csv"

    def process_tech_csv(
        self,
        *,
        limit: int | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Process tech career CSV file and batch write to Firestore emulator."""
        if not self.tech_csv_path.is_file():
            raise FileNotFoundError(f"Missing raw CSV file: {self.tech_csv_path}")

        logger.info("Opening %s (dry_run=%s, limit=%s)", self.tech_csv_path.name, dry_run, limit)

        stats = {
            "total_rows_read": 0,
            "jobs_parsed": 0,
            "distinct_skills_seen": set(),
            "skill_observations_generated": 0,
            "batches_committed": 0,
            "dry_run": dry_run,
        }

        db = None if dry_run else get_firestore_client()
        current_batch = db.batch() if db else None
        pending_ops = 0

        def commit_batch():
            nonlocal current_batch, pending_ops
            if current_batch and pending_ops > 0:
                current_batch.commit()
                stats["batches_committed"] += 1
                current_batch = db.batch()
                pending_ops = 0

        start_time = time.time()

        with open(self.tech_csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["total_rows_read"] += 1
                if limit and stats["jobs_parsed"] >= limit:
                    break

                raw_title = str(row.get("job_title") or "").strip()
                if not raw_title:
                    continue

                canonical_role, is_aliased = resolve_role_alias(raw_title)
                standardized_title = canonical_role if is_aliased else raw_title

                company = str(row.get("company_name") or "Unknown").strip()
                raw_city = str(row.get("location_city") or "").strip()
                norm_city = _normalize_city(raw_city) or raw_city or "Bengaluru"
                location_str = f"{raw_city}, India" if raw_city else "India"

                posted_date_str = str(row.get("posted_date") or "").strip()
                posted_dt, period = parse_date(posted_date_str)
                if not posted_dt or not period:
                    posted_dt = datetime.now(timezone.utc)
                    period = posted_dt.strftime("%Y-%m")

                skills = parse_skills(row.get("skills_extracted"))
                if not skills:
                    continue

                for s in skills:
                    stats["distinct_skills_seen"].add(s)

                job_uid = generate_stable_id("in-tech", company, raw_title, posted_date_str, str(stats["jobs_parsed"]))

                job_payload = {
                    "job_id": job_uid,
                    "source_job_id": job_uid,
                    "title": standardized_title,
                    "company_name": company,
                    "location": location_str,
                    "city": norm_city,
                    "country": "India",
                    "country_code": "in",
                    "description": str(row.get("job_description") or ""),
                    "employment_type": str(row.get("employment_type") or "Full-time"),
                    "category": str(row.get("job_category") or ""),
                    "source": "jsearch",
                    "source_url": None,
                    "source_type": "imported_historical",
                    "skills_raw": skills,
                    "posted_at": posted_dt.isoformat(),
                    "fetched_at": posted_dt,
                }

                stats["jobs_parsed"] += 1

                # Generate skill observations
                observations: list[dict[str, Any]] = []
                for skill_name in skills:
                    c_id = canonical_skill_id(skill_name)
                    skill_slug = c_id or skill_name.lower().replace(" ", "-")
                    obs_id = generate_stable_id("obs", "imported_historical", job_uid, skill_name, period)
                    series_id = f"imported_historical:{DEFAULT_PANEL_VERSION}:job-demand:{skill_slug}:{DEFAULT_EXTRACTOR_VERSION}"

                    obs_payload = {
                        "observation_id": obs_id,
                        "source": "jsearch",
                        "source_type": "imported_historical",
                        "signal_type": "demand",
                        "skill": skill_name,
                        "skill_id": c_id,
                        "value": 1.0,
                        "unit": "job_postings",
                        "period": period,
                        "location": "India",
                        "scope": "country",
                        "posting_id": job_uid,
                        "observed_at": posted_dt,
                        "provider_posted_at": posted_dt,
                        "created_at": datetime.now(timezone.utc),
                        "history_type": "backfill",
                        "data_origin": "real",
                        "observation_count": 1,
                        "panel_version": DEFAULT_PANEL_VERSION,
                        "query_id": "imported-historical:india",
                        "extractor_version": DEFAULT_EXTRACTOR_VERSION,
                        "series_id": series_id,
                        "metadata": {
                            "source_type": "imported_historical",
                            "original_title": raw_title,
                            "standardized_title": standardized_title,
                            "company": company,
                            "city": norm_city,
                            "country": "India",
                        },
                    }
                    observations.append(obs_payload)
                    stats["skill_observations_generated"] += 1

                if not dry_run and db:
                    job_doc_ref = db.collection("jobs").document(f"jsearch:{job_uid}")
                    current_batch.set(job_doc_ref, job_payload, merge=True)
                    pending_ops += 1

                    for obs in observations:
                        obs_ref_signals = db.collection("skill_market_signals").document(obs["observation_id"])
                        obs_ref_obs = db.collection("skill_observations").document(obs["observation_id"])

                        current_batch.set(obs_ref_signals, obs, merge=True)
                        current_batch.set(obs_ref_obs, obs, merge=True)
                        pending_ops += 2

                        if pending_ops >= FIRESTORE_BATCH_LIMIT:
                            commit_batch()

                    if pending_ops >= FIRESTORE_BATCH_LIMIT:
                        commit_batch()

                if dry_run and stats["jobs_parsed"] <= 3:
                    logger.info("Sample Parsed Job:\n  Title: %s (Original: %s)\n  Company: %s\n  City: %s\n  Skills (%d): %s\n  Observations Generated: %d",
                                standardized_title, raw_title, company, norm_city, len(skills), skills[:5], len(observations))

        if not dry_run and current_batch and pending_ops > 0:
            commit_batch()

        elapsed = time.time() - start_time
        distinct_count = len(stats["distinct_skills_seen"])
        stats["distinct_skills_count"] = distinct_count
        del stats["distinct_skills_seen"]

        logger.info(
            "Completed in %.2fs: %d rows read, %d jobs parsed, %d distinct skills, %d observations generated (dry_run=%s, committed_batches=%d)",
            elapsed, stats["total_rows_read"], stats["jobs_parsed"], distinct_count,
            stats["skill_observations_generated"], dry_run, stats["batches_committed"],
        )
        return stats


# ============================================================================
# Task B: Live API Pull (TheirStack & Fliar / Radar)
# ============================================================================

def _parse_job_records_from_api(
    records: list[dict[str, Any]],
    source_name: str,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Parse raw API records into unified (job_payload, observations) pairs."""
    results = []
    for item in records:
        raw_title = str(item.get("job_title") or item.get("title") or "").strip()
        if not raw_title:
            continue

        canonical_role, is_aliased = resolve_role_alias(raw_title)
        standardized_title = canonical_role if is_aliased else raw_title

        company = str(item.get("company_name") or item.get("company") or "Unknown").strip()
        city_raw = str(item.get("job_city") or item.get("city") or item.get("location") or "").strip()
        norm_city = _normalize_city(city_raw) or city_raw or "Bengaluru"

        raw_date = str(item.get("date_posted") or item.get("posted_at") or item.get("created_at") or "").strip()
        posted_dt, period = parse_date(raw_date)
        if not posted_dt or not period:
            posted_dt = datetime.now(timezone.utc)
            period = posted_dt.strftime("%Y-%m")

        # Determine gate tag based on demo cutoff boundary (mid-October 2026)
        if posted_dt < LIVE_GATE_BOUNDARY:
            source_type = "imported_historical"
            history_type = "backfill"
        else:
            source_type = "live_platform"
            history_type = "platform_collected"

        skills = parse_skills(item.get("technologies") or item.get("technology_slugs") or item.get("skills"))
        job_id = str(item.get("id") or item.get("job_id") or generate_stable_id(source_name[:3], company, raw_title, str(posted_dt)))

        job_payload = {
            "job_id": job_id,
            "source_job_id": job_id,
            "title": standardized_title,
            "company_name": company,
            "location": f"{norm_city}, India",
            "city": norm_city,
            "country": "India",
            "country_code": "in",
            "description": str(item.get("job_description") or item.get("description") or ""),
            "employment_type": str(item.get("employment_type") or "Full-time"),
            "category": str(item.get("category") or "Engineering"),
            "source": "jsearch",  # Supported Job model source Literal
            "source_url": item.get("url") or item.get("job_url"),
            "source_type": source_type,
            "skills_raw": skills,
            "posted_at": posted_dt.isoformat(),
            "fetched_at": datetime.now(timezone.utc),
        }

        observations = []
        for s in skills:
            c_id = canonical_skill_id(s)
            skill_slug = c_id or s.lower().replace(" ", "-")
            obs_id = generate_stable_id("obs", source_name, job_id, s, period)
            series_id = f"{source_name}:{DEFAULT_PANEL_VERSION}:job-demand:{skill_slug}:{DEFAULT_EXTRACTOR_VERSION}"

            obs_payload = {
                "observation_id": obs_id,
                "source": "jsearch",
                "source_type": source_type,
                "signal_type": "demand",
                "skill": s,
                "skill_id": c_id,
                "value": 1.0,
                "unit": "job_postings",
                "period": period,
                "location": "India",
                "scope": "country",
                "posting_id": job_id,
                "observed_at": posted_dt,
                "provider_posted_at": posted_dt,
                "created_at": datetime.now(timezone.utc),
                "history_type": history_type,
                "data_origin": "real",
                "observation_count": 1,
                "panel_version": DEFAULT_PANEL_VERSION,
                "query_id": f"{source_name}:india",
                "extractor_version": DEFAULT_EXTRACTOR_VERSION,
                "series_id": series_id,
                "metadata": {
                    "source_type": source_type,
                    "original_title": raw_title,
                    "standardized_title": standardized_title,
                    "company": company,
                    "city": norm_city,
                    "country": "India",
                },
            }
            observations.append(obs_payload)

        results.append((job_payload, observations))
    return results


def fetch_live_api_data(probe_mode: bool = False) -> dict[str, Any]:
    """Execute live API pull from TheirStack and Fliar with strict circuit breakers."""
    creds = load_api_credentials()
    theirstack_url = creds["THEIRSTACK_API_URL"]
    theirstack_key = creds["THEIRSTACK_API_KEY"]
    radar_url = creds["RADAR_API_URL"]
    fliar_key = creds["FLIAR_API_KEY"]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stats: dict[str, Any] = {
        "probe_mode": probe_mode,
        "theirstack_jobs_fetched": 0,
        "theirstack_requests_made": 0,
        "fliar_requests_made": 0,
        "fliar_jobs_fetched": 0,
        "stored_jobs": 0,
        "stored_observations": 0,
    }

    headers_theirstack = {
        "Authorization": f"Bearer {theirstack_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers_fliar = {
        "Authorization": f"Bearer {fliar_key}",
        "X-API-Key": fliar_key,
        "Accept": "application/json",
    }

    with httpx.Client(timeout=20.0) as client:
        # --------------------------------------------------------------------
        # 1. PROBE MODE (limit=1, no DB write, writes probe_schema.json)
        # --------------------------------------------------------------------
        if probe_mode:
            logger.info("=== Executing API Probe (limit=1) ===")
            probe_results: dict[str, Any] = {"probed_at": datetime.now(timezone.utc).isoformat()}

            # Probe TheirStack
            if theirstack_url and theirstack_key:
                try:
                    stats["theirstack_requests_made"] += 1
                    resp = client.post(
                        theirstack_url,
                        headers=headers_theirstack,
                        json={"page": 0, "limit": 1, "job_country_code_or": ["IN"]},
                    )
                    probe_results["theirstack"] = {
                        "status_code": resp.status_code,
                        "body": resp.json() if resp.status_code == 200 else resp.text[:500],
                    }
                    logger.info("TheirStack probe status: %d", resp.status_code)
                except Exception as exc:
                    logger.warning("TheirStack probe error: %s", type(exc).__name__)
                    probe_results["theirstack"] = {"error": str(exc)}
            else:
                probe_results["theirstack"] = {"status": "credentials_unconfigured"}

            # Probe Fliar / Radar
            if radar_url and fliar_key:
                try:
                    stats["fliar_requests_made"] += 1
                    resp = client.get(
                        radar_url,
                        headers=headers_fliar,
                        params={"limit": 1, "country": "IN"},
                    )
                    probe_results["fliar"] = {
                        "status_code": resp.status_code,
                        "body": resp.json() if resp.status_code == 200 else resp.text[:500],
                    }
                    logger.info("Fliar probe status: %d", resp.status_code)
                except Exception as exc:
                    logger.warning("Fliar probe error: %s", type(exc).__name__)
                    probe_results["fliar"] = {"error": str(exc)}
            else:
                probe_results["fliar"] = {"status": "credentials_unconfigured"}

            out_path = DATA_DIR / "probe_schema.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(probe_results, f, indent=2)
            logger.info("Probe schema saved to %s", out_path)
            return stats

        # --------------------------------------------------------------------
        # 2. FULL LIVE PULL (Capped: max 90 TheirStack, max 180 Fliar)
        # --------------------------------------------------------------------
        logger.info("=== Executing Capped Live API Pull (TheirStack max 90, Fliar max 180) ===")
        theirstack_records: list[dict[str, Any]] = []
        fliar_records: list[dict[str, Any]] = []

        # Pull TheirStack: 45 for Sept 2026, 45 for Oct 2026 (Circuit Breaker: <= 90 jobs)
        if theirstack_url and theirstack_key:
            for month_name, date_range in [
                ("September 2026", ("2026-09-01", "2026-09-30")),
                ("October 2026", ("2026-10-01", "2026-10-31")),
            ]:
                if len(theirstack_records) >= MAX_THEIRSTACK_JOBS:
                    logger.warning("Circuit breaker triggered: TheirStack reached max %d jobs.", MAX_THEIRSTACK_JOBS)
                    break

                quota_left = min(45, MAX_THEIRSTACK_JOBS - len(theirstack_records))
                try:
                    stats["theirstack_requests_made"] += 1
                    resp = client.post(
                        theirstack_url,
                        headers=headers_theirstack,
                        json={
                            "page": 0,
                            "limit": quota_left,
                            "job_country_code_or": ["IN"],
                            "posted_at_gte": date_range[0],
                            "posted_at_lte": date_range[1],
                        },
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        items = payload.get("data") or payload.get("jobs") or (payload if isinstance(payload, list) else [])
                        theirstack_records.extend(items[:quota_left])
                        logger.info("Pulled %d jobs from TheirStack for %s", len(items[:quota_left]), month_name)
                    else:
                        logger.warning("TheirStack returned status %d for %s", resp.status_code, month_name)
                except Exception as exc:
                    logger.error("TheirStack request failed for %s: %s", month_name, exc)

        stats["theirstack_jobs_fetched"] = len(theirstack_records)

        # Pull Fliar (Radar): Up to 180 requests circuit breaker
        if radar_url and fliar_key:
            for month_name, date_range in [
                ("September 2026", ("2026-09-01", "2026-09-30")),
                ("October 2026", ("2026-10-01", "2026-10-31")),
            ]:
                if stats["fliar_requests_made"] >= MAX_FLIAR_REQUESTS:
                    logger.warning("Circuit breaker triggered: Fliar reached max %d requests.", MAX_FLIAR_REQUESTS)
                    break

                try:
                    stats["fliar_requests_made"] += 1
                    resp = client.get(
                        radar_url,
                        headers=headers_fliar,
                        params={
                            "country": "IN",
                            "from_date": date_range[0],
                            "to_date": date_range[1],
                            "limit": 50,
                        },
                    )
                    if resp.status_code == 200:
                        payload = resp.json()
                        items = payload.get("data") or payload.get("jobs") or (payload if isinstance(payload, list) else [])
                        fliar_records.extend(items)
                        logger.info("Pulled %d records from Fliar for %s", len(items), month_name)
                    else:
                        logger.warning("Fliar returned status %d for %s", resp.status_code, month_name)
                except Exception as exc:
                    logger.error("Fliar request failed for %s: %s", month_name, exc)

        stats["fliar_jobs_fetched"] = len(fliar_records)

        # Save raw fetched responses to backend/data/
        ts_out = DATA_DIR / "theirstack_sep_oct_2026.json"
        fl_out = DATA_DIR / "fliar_sep_oct_2026.json"
        with open(ts_out, "w", encoding="utf-8") as f:
            json.dump(theirstack_records, f, indent=2)
        with open(fl_out, "w", encoding="utf-8") as f:
            json.dump(fliar_records, f, indent=2)
        logger.info("Saved raw JSON dumps to %s and %s", ts_out.name, fl_out.name)

        # Batch write parsed records into Firestore emulator
        db = get_firestore_client()
        batch = db.batch()
        ops_count = 0

        parsed_pairs = (
            _parse_job_records_from_api(theirstack_records, "theirstack")
            + _parse_job_records_from_api(fliar_records, "fliar")
        )

        for job_payload, obs_list in parsed_pairs:
            job_ref = db.collection("jobs").document(f"jsearch:{job_payload['job_id']}")
            batch.set(job_ref, job_payload, merge=True)
            ops_count += 1
            stats["stored_jobs"] += 1

            for obs in obs_list:
                ref_signals = db.collection("skill_market_signals").document(obs["observation_id"])
                ref_obs = db.collection("skill_observations").document(obs["observation_id"])

                batch.set(ref_signals, obs, merge=True)
                batch.set(ref_obs, obs, merge=True)
                ops_count += 2
                stats["stored_observations"] += 1

                if ops_count >= FIRESTORE_BATCH_LIMIT:
                    batch.commit()
                    batch = db.batch()
                    ops_count = 0

        if ops_count > 0:
            batch.commit()

        logger.info(
            "Live ingestion complete: %d jobs stored, %d observations stored in emulator",
            stats["stored_jobs"], stats["stored_observations"]
        )
        return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest historical Indian market datasets & pull live API data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Process first 50 CSV rows, print sample stats, no DB writes.")
    group.add_argument("--ingest", action="store_true", help="Perform full batch ingestion from CSV into Firestore emulator.")
    group.add_argument("--probe", action="store_true", help="Run 1-item test against TheirStack and Fliar and save probe_schema.json.")
    group.add_argument("--fetch-live", action="store_true", help="Run capped live API pull (max 90 TheirStack, max 180 Fliar) and write to emulator.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for CSV processing.")
    args = parser.parse_args()

    if args.probe:
        stats = fetch_live_api_data(probe_mode=True)
        print("\n--- Probe Execution Summary ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    elif args.fetch_live:
        stats = fetch_live_api_data(probe_mode=False)
        print("\n--- Live API Ingestion Summary ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    elif args.dry_run:
        ingestor = IndianMarketDataIngestor()
        limit = args.limit or 50
        logger.info("=== RUNNING CSV DRY RUN (limit=%d) ===", limit)
        stats = ingestor.process_tech_csv(limit=limit, dry_run=True)
        print("\n--- Dry Run Statistics ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    elif args.ingest:
        ingestor = IndianMarketDataIngestor()
        logger.info("=== RUNNING FULL CSV INGESTION (limit=%s) ===", args.limit)
        stats = ingestor.process_tech_csv(limit=args.limit, dry_run=False)
        print("\n--- Ingestion Statistics ---")
        for k, v in stats.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

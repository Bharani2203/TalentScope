"""Historical CSV Ingestion ETL Script for TalentScope.ai Skill Intelligence (Phase 3).

Ingests historical job postings and skill observations into PostgreSQL:
  - Database: talentscope_intelligence
  - Target Tables: raw_job_postings, raw_skill_observations
  - Method: High-speed bulk ingestion via pandas and psycopg2.extras.execute_values
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Iterable, Sequence

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# ==============================================================================
# Configurable Parameters
# ==============================================================================
CSV_FILE_PATH = "data/raw/indian_tech_career_intelligence_2026.csv"
BATCH_SIZE = 2500

DB_CONFIG = {
    "dbname": "talentscope_intelligence",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
}

# ==============================================================================
# Mandatory Firestore emulator environment variables (Section 6 Constraints)
# ==============================================================================
os.environ.setdefault("TALENTSCOPE_FIREBASE_MODE", "emulator")
os.environ.setdefault("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
os.environ.setdefault("ENVIRONMENT", "local-test")
os.environ.setdefault("FIREBASE_PROJECT_ID", "demo-talentscope-local")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("ingest_historical_csv")


def resolve_csv_path(target_path_str: str) -> Path:
    """Resolve the CSV path across common project root and data directory layouts."""
    p = Path(target_path_str)
    if p.is_file():
        return p.resolve()

    script_dir = Path(__file__).resolve().parent
    candidates = [
        Path.cwd() / p,
        script_dir.parent / p,
        script_dir.parent.parent / p,
        script_dir.parent / "data" / p.name,
        script_dir.parent / "data" / "raw" / p.name,
        Path("D:/project/Data set") / p.name,
    ]

    for cand in candidates:
        if cand.is_file():
            return cand.resolve()

    return (Path.cwd() / p).resolve()


def chunk_iterable(iterable: Sequence[Any], chunk_size: int) -> Generator[Sequence[Any], None, None]:
    """Yield successive chunks from sequence."""
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i : i + chunk_size]


def ingest_historical_csv(csv_path_str: str = CSV_FILE_PATH) -> int:
    """Load, clean, normalize, and bulk-insert historical job postings & skill observations."""
    resolved_path = resolve_csv_path(csv_path_str)

    if not resolved_path.exists():
        logger.error(
            "Target CSV file not found at: %s\n"
            "Please ensure 'indian_tech_career_intelligence_2026.csv' is placed in '%s' or at the project 'data/' folder.",
            resolved_path,
            CSV_FILE_PATH,
        )
        return 1

    logger.info("Found dataset at: %s", resolved_path)
    logger.info("Reading CSV dataset with pandas...")

    # Step a: Read CSV keeping only required columns
    required_cols = [
        "job_title",
        "company_name",
        "location_city",
        "skills_extracted",
        "posted_date",
    ]

    try:
        df = pd.read_csv(resolved_path, usecols=required_cols, dtype=str)
    except Exception as exc:
        logger.error("Failed to read CSV: %s", exc)
        return 1

    total_raw_rows = len(df)
    logger.info("Loaded %d raw rows from CSV.", total_raw_rows)

    # Drop rows missing titles or dates
    df = df.dropna(subset=["job_title", "posted_date"])
    df = df[df["job_title"].str.strip().ne("") & df["posted_date"].str.strip().ne("")]
    logger.info("Retained %d rows after dropping missing titles and dates.", len(df))

    # Step b: Normalize posted_date from DD/MM/YYYY or DD-MM-YYYY to YYYY-MM-DD
    logger.info("Normalizing posted_date...")
    df["posted_date_clean"] = pd.to_datetime(
        df["posted_date"].str.strip(),
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )
    df = df.dropna(subset=["posted_date_clean"])
    df["posted_date_str"] = df["posted_date_clean"].dt.strftime("%Y-%m-%d")
    df["period_month"] = df["posted_date_clean"].dt.strftime("%Y-%m")
    logger.info("Normalized %d valid dated rows.", len(df))

    # Step c: Generate unique job_id for each job
    logger.info("Generating unique job_id for each record...")
    df["job_id"] = [uuid.uuid4().hex for _ in range(len(df))]

    # Fill optional string columns with defaults
    df["company_name"] = df["company_name"].fillna("Unknown").str.strip()
    df["location_city"] = df["location_city"].fillna("Unknown").str.strip()
    df["skills_extracted"] = df["skills_extracted"].fillna("")

    # Step d: Prepare records for raw_job_postings
    logger.info("Preparing records for raw_job_postings...")
    job_records = [
        (
            row.job_id,
            row.job_id,
            row.job_title.strip(),
            row.company_name,
            row.location_city,
            row.posted_date_str,
            row.period_month,
            row.period_month,
            "indian_tech_2026",
            "imported_historical",
            "indian_tech_2026",
            "imported_historical",
        )
        for row in df.itertuples(index=False)
    ]

    # Step e: Explode skills_extracted and prepare records for raw_skill_observations
    logger.info("Exploding skills and preparing raw_skill_observations...")
    skill_records = []
    for row in df.itertuples(index=False):
        raw_skills = row.skills_extracted
        if not raw_skills:
            continue

        tokens = [s.strip() for s in str(raw_skills).split(",") if s.strip()]
        for token in tokens:
            skill_name = token.lower()
            obs_id = uuid.uuid4().hex
            skill_records.append(
                (
                    obs_id,
                    row.job_id,
                    row.job_id,
                    skill_name,
                    token,
                    skill_name,
                    row.period_month,
                    row.period_month,
                    row.posted_date_str,
                    "imported_historical",
                    "indian_tech_2026",
                    "imported_historical",
                    "historical",
                )
            )

    logger.info(
        "Prepared %d job posting records and %d skill observation records.",
        len(job_records),
        len(skill_records),
    )

    # Step f: High-speed bulk insertion via execute_values with batching
    logger.info("Connecting to PostgreSQL '%s' on %s:%s...", DB_CONFIG["dbname"], DB_CONFIG["host"], DB_CONFIG["port"])
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    job_insert_sql = """
        INSERT INTO raw_job_postings (
            job_id,
            posting_id,
            job_title,
            company_name,
            location_city,
            posted_date,
            period_month,
            period,
            source_dataset,
            source_type,
            source,
            data_origin
        ) VALUES %s
        ON CONFLICT (job_id) DO NOTHING;
    """

    skill_insert_sql = """
        INSERT INTO raw_skill_observations (
            observation_id,
            job_id,
            posting_id,
            skill_name,
            display_skill,
            skill_id,
            period_month,
            period,
            posted_date,
            source_type,
            source,
            data_origin,
            history_type
        ) VALUES %s
        ON CONFLICT (observation_id) DO NOTHING;
    """

    try:
        # Insert raw_job_postings in batches
        logger.info("Bulk inserting %d job postings (batch size: %d)...", len(job_records), BATCH_SIZE)
        inserted_jobs = 0
        for chunk in chunk_iterable(job_records, BATCH_SIZE):
            execute_values(cur, job_insert_sql, chunk, page_size=BATCH_SIZE)
            conn.commit()
            inserted_jobs += len(chunk)
            if inserted_jobs % 10000 == 0 or inserted_jobs == len(job_records):
                logger.info("Inserted %d / %d job postings...", inserted_jobs, len(job_records))

        # Insert raw_skill_observations in batches
        logger.info("Bulk inserting %d skill observations (batch size: %d)...", len(skill_records), BATCH_SIZE)
        inserted_skills = 0
        for chunk in chunk_iterable(skill_records, BATCH_SIZE):
            execute_values(cur, skill_insert_sql, chunk, page_size=BATCH_SIZE)
            conn.commit()
            inserted_skills += len(chunk)
            if inserted_skills % 50000 == 0 or inserted_skills == len(skill_records):
                logger.info("Inserted %d / %d skill observations...", inserted_skills, len(skill_records))

        # Verification counts
        cur.execute("SELECT count(*) FROM raw_job_postings WHERE source_dataset = 'indian_tech_2026';")
        total_jobs_in_db = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw_skill_observations WHERE source = 'indian_tech_2026';")
        total_skills_in_db = cur.fetchone()[0]

        print("\n" + "=" * 70)
        print("TALENTSCOPE.AI HISTORICAL INGESTION REPORT (PHASE 3)")
        print("=" * 70)
        print(f"Dataset File:             {resolved_path}")
        print(f"Total CSV Rows Processed: {len(df)}")
        print(f"Job Postings in DB:       {total_jobs_in_db}")
        print(f"Skill Observations in DB: {total_skills_in_db}")
        print("=" * 70)
        print("[Verified] Phase 3 Historical Ingestion Completed Successfully.\n")
        return 0

    except Exception as exc:
        conn.rollback()
        logger.error("Bulk insertion failed: %s", exc, exc_info=True)
        return 1
    finally:
        cur.close()
        conn.close()


def main() -> int:
    return ingest_historical_csv(CSV_FILE_PATH)


if __name__ == "__main__":
    sys.exit(main())

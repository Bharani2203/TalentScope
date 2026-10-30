"""Secondary CSV & Excel Ingestion ETL Script for TalentScope.ai Skill Intelligence.

Ingests secondary job postings datasets into PostgreSQL:
  - Database: talentscope_intelligence
  - Target Tables: raw_job_postings, raw_skill_observations
  - Datasets Supported:
      1. all_job.csv (or all_jobs.csv) -> tagged with source_dataset = 'all_job_2026'
      2. indian-job-market-dataset.xlsx (or .csv) -> tagged with source_dataset = 'indian_job_market_2026'
  - Relative Date Parsing: Converts relative strings ("6 days ago", "2 months ago", "few hours ago", "just now")
    into absolute datetime objects using scraped_date or a fallback anchor date (2026-06-01).
  - High-speed bulk insertion via pandas, openpyxl, and psycopg2.extras.execute_values.
  - Strict Truth-in-Data: Sets source_type = 'imported_historical' for all records.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Sequence

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

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
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("JSEARCH_API_KEY", "")
os.environ.setdefault("RAPIDAPI_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# ==============================================================================
# Database Configuration & Configurable Parameters
# ==============================================================================
DB_CONFIG = {
    "dbname": "talentscope_intelligence",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
}

BATCH_SIZE = 2500
DEFAULT_ANCHOR_DATE = datetime(2026, 6, 1)

# Default paths relative to repository root or data directory
DEFAULT_ALL_JOB_PATH = "data/raw/all_job.csv"
DEFAULT_INDIAN_JOB_MARKET_PATH = "data/raw/indian-job-market-dataset.xlsx"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("ingest_secondary_csvs")


# ==============================================================================
# 1. Path Resolution & Helpers
# ==============================================================================
def resolve_dataset_path(target_filename: str, fallback_filenames: list[str] | None = None) -> Path | None:
    """Resolve a dataset path across project root, backend, and data/raw locations.
    
    Checks both primary target_filename and any alternative/plural forms.
    """
    candidates_names = [target_filename] + (fallback_filenames or [])
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    search_roots = [
        Path.cwd(),
        repo_root,
        script_dir.parent,
        Path("D:/project/New folder/New folder/S7_PROJECT_SKILL_1-main/S7_PROJECT_SKILL_1-main"),
        Path("D:/project/Data set"),
    ]

    for root in search_roots:
        for name in candidates_names:
            p = Path(name)
            if p.is_file():
                return p.resolve()

            potential_paths = [
                root / p,
                root / "data" / "raw" / p.name,
                root / "data" / p.name,
                root / "backend" / "data" / "raw" / p.name,
                root / "backend" / "data" / p.name,
            ]
            for candidate in potential_paths:
                if candidate.is_file():
                    return candidate.resolve()

    return (repo_root / "data" / "raw" / Path(target_filename).name).resolve()


def chunk_iterable(iterable: Sequence[Any], chunk_size: int) -> Generator[Sequence[Any], None, None]:
    """Yield successive chunks from sequence."""
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i : i + chunk_size]


# ==============================================================================
# 2. Robust Date Parsing Function
# ==============================================================================
def parse_relative_or_absolute_date(
    date_val: Any,
    anchor_val: Any = None,
    fallback_anchor: datetime = DEFAULT_ANCHOR_DATE,
) -> tuple[datetime, str, str] | None:
    """Parse relative date strings or standard date formats into absolute datetime objects.
    
    Handles:
      - "just now", "today", "few hours ago", "X mins ago" -> anchor date
      - "yesterday", "1 day ago", "X days ago", "X+ days ago" -> anchor - X days
      - "1 week ago", "X weeks ago", "X+ weeks ago" -> anchor - (X * 7) days
      - "1 month ago", "X months ago", "X+ months ago" -> anchor - (X * 30) days
      - "1 year ago", "X years ago" -> anchor - (X * 365) days
      - Absolute strings: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, etc.
    
    Returns:
      (datetime_obj, posted_date_str [YYYY-MM-DD], period_month [YYYY-MM]) or None if unparseable.
    """
    if date_val is None or pd.isna(date_val):
        return None

    raw_str = str(date_val).strip()
    if not raw_str or raw_str.lower() in ["nan", "none", "null"]:
        return None

    # Determine anchor datetime
    anchor = fallback_anchor
    if anchor_val is not None and not pd.isna(anchor_val):
        try:
            if isinstance(anchor_val, (datetime, pd.Timestamp)):
                anchor = datetime(anchor_val.year, anchor_val.month, anchor_val.day)
            elif isinstance(anchor_val, date):
                anchor = datetime(anchor_val.year, anchor_val.month, anchor_val.day)
            else:
                parsed_anchor = pd.to_datetime(str(anchor_val).strip(), errors="coerce")
                if not pd.isna(parsed_anchor) and parsed_anchor is not None:
                    anchor = datetime(parsed_anchor.year, parsed_anchor.month, parsed_anchor.day)
        except Exception:
            anchor = fallback_anchor

    s_lower = raw_str.lower()
    resolved_dt: datetime | None = None

    # 1. Immediate / same-day patterns
    if any(k in s_lower for k in ["just now", "today", "few hours", "hour ago", "hours ago", "minute", "mins ago"]):
        resolved_dt = anchor

    # 2. Yesterday
    elif "yesterday" in s_lower:
        resolved_dt = anchor - timedelta(days=1)

    # 3. Few days ago
    elif "few days ago" in s_lower:
        resolved_dt = anchor - timedelta(days=3)

    # 4. Starts in / within expressions
    elif "starts in" in s_lower or "starts within" in s_lower:
        resolved_dt = anchor

    # 5. Regex for "X(+) day(s)/week(s)/month(s)/year(s) ago"
    else:
        match = re.search(r"(\d+)\s*\+?\s*(day|week|month|year)s?\s*ago", s_lower)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                resolved_dt = anchor - timedelta(days=num)
            elif unit == "week":
                resolved_dt = anchor - timedelta(days=num * 7)
            elif unit == "month":
                resolved_dt = anchor - timedelta(days=num * 30)
            elif unit == "year":
                resolved_dt = anchor - timedelta(days=num * 365)
        else:
            # 6. Fallback: Parse as standard absolute date
            try:
                parsed = pd.to_datetime(raw_str, format="mixed", dayfirst=True, errors="coerce")
                if not pd.isna(parsed) and parsed is not None:
                    resolved_dt = datetime(parsed.year, parsed.month, parsed.day)
            except Exception:
                resolved_dt = None

    if resolved_dt is None:
        return None

    posted_date_str = resolved_dt.strftime("%Y-%m-%d")
    period_month = resolved_dt.strftime("%Y-%m")
    return resolved_dt, posted_date_str, period_month


# ==============================================================================
# 3. Robust Skill Extraction Helper
# ==============================================================================
def extract_skill_tokens(raw_skills: Any) -> list[str]:
    """Extract individual skill names from comma, pipe, semicolon, or list-formatted skill fields."""
    if raw_skills is None or pd.isna(raw_skills):
        return []

    s = str(raw_skills).strip()
    if not s or s.lower() in ["nan", "none", "[]", "{}"]:
        return []

    # Check for string representation of lists
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        import ast
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple, set)):
                return [str(item).strip().strip("'\"") for item in parsed if str(item).strip()]
        except Exception:
            s = s[1:-1]

    # Standardize delimiters
    s = s.replace("|", ",").replace(";", ",")
    tokens = [t.strip().strip("'\"") for t in s.split(",") if t.strip()]
    return [t for t in tokens if t and t.lower() not in ["none", "nan", "null"]]


# ==============================================================================
# 4. Ingestion Processors
# ==============================================================================
def process_all_job_dataset(csv_path: Path) -> tuple[list[tuple], list[tuple]]:
    """Process all_job.csv dataset:
      - title -> job_title
      - company -> company_name
      - location -> location_city
      - skills -> skills_extracted
      - date_posted -> parsed with scraped_date anchor
      - source_dataset -> 'all_job_2026'
    """
    logger.info("Processing 'all_job.csv' dataset from: %s", csv_path)
    df = pd.read_csv(csv_path, dtype=str)
    logger.info("Read %d raw records from %s", len(df), csv_path.name)

    # Column mapping & defaults
    title_col = "title" if "title" in df.columns else "job_title"
    company_col = "company" if "company" in df.columns else "company_name"
    location_col = "location" if "location" in df.columns else "location_city"
    skills_col = "skills" if "skills" in df.columns else "skills_extracted"
    date_col = "date_posted" if "date_posted" in df.columns else "posted_date"
    anchor_col = "scraped_date" if "scraped_date" in df.columns else None

    # Filter out missing titles
    df = df.dropna(subset=[title_col])
    df = df[df[title_col].astype(str).str.strip().ne("")]

    titles = df[title_col].astype(str).str.strip().tolist()
    companies = (df[company_col].fillna("Unknown").astype(str).str.strip().tolist()
                 if company_col in df.columns else ["Unknown"] * len(df))
    locations = (df[location_col].fillna("Unknown").astype(str).str.strip().tolist()
                 if location_col in df.columns else ["Unknown"] * len(df))
    skills = (df[skills_col].fillna("").astype(str).tolist()
              if skills_col in df.columns else [""] * len(df))
    dates = df[date_col].tolist() if date_col in df.columns else [None] * len(df)
    anchors = df[anchor_col].tolist() if anchor_col and anchor_col in df.columns else [None] * len(df)

    job_records = []
    skill_records = []

    for title, company, location, raw_skills, raw_date, anchor_val in zip(
        titles, companies, locations, skills, dates, anchors
    ):
        parsed_date = parse_relative_or_absolute_date(raw_date, anchor_val=anchor_val)
        if not parsed_date:
            continue

        _, posted_date_str, period_month = parsed_date
        job_id = uuid.uuid4().hex

        # raw_job_postings record (ensure safe string bounds)
        job_records.append((
            job_id,
            job_id,                      # posting_id
            title[:255],                 # job_title
            company[:255],               # company_name
            location[:250],              # location_city
            posted_date_str,             # posted_date
            period_month,                # period
            period_month,                # period_month
            "all_job_2026",              # source_dataset
            "imported_historical",       # source_type
            "all_job_2026",              # source
            "imported_historical",       # data_origin
        ))

        # raw_skill_observations records
        tokens = extract_skill_tokens(raw_skills)
        for token in tokens:
            skill_name = token.lower()[:255]
            display_skill = token[:255]
            skill_id = skill_name[:100]
            obs_id = uuid.uuid4().hex
            skill_records.append((
                obs_id,
                job_id,
                job_id,
                skill_name,
                display_skill,
                skill_id,
                period_month,                # period_month
                period_month,                # period
                posted_date_str,             # posted_date
                "imported_historical",       # source_type
                "all_job_2026",              # source
                "imported_historical",       # data_origin
                "historical",                # history_type
            ))

    logger.info("Prepared %d job postings and %d skill observations from '%s'.", len(job_records), len(skill_records), csv_path.name)
    return job_records, skill_records


def process_indian_job_market_dataset(file_path: Path) -> tuple[list[tuple], list[tuple]]:
    """Process indian-job-market-dataset (.xlsx or .csv):
      - title -> job_title
      - companyName -> company_name
      - location -> location_city
      - tagsAndSkills -> skills_extracted
      - jobUploaded -> parsed relative date string
      - source_dataset -> 'indian_job_market_2026'
    """
    logger.info("Processing 'indian-job-market-dataset' from: %s", file_path)
    
    use_cols = ["title", "companyName", "location", "tagsAndSkills", "jobUploaded"]

    if file_path.suffix.lower() == ".xlsx":
        logger.info("Loading Excel dataset via openpyxl engine: %s", file_path)
        df = pd.read_excel(file_path, engine="openpyxl", usecols=use_cols)
    else:
        logger.info("Loading CSV dataset: %s", file_path)
        df = pd.read_csv(file_path, dtype=str)

    logger.info("Read %d raw records from %s", len(df), file_path.name)

    title_col = "title" if "title" in df.columns else "job_title"
    company_col = "companyName" if "companyName" in df.columns else ("company" if "company" in df.columns else "company_name")
    location_col = "location" if "location" in df.columns else "location_city"
    skills_col = "tagsAndSkills" if "tagsAndSkills" in df.columns else ("skills" if "skills" in df.columns else "skills_extracted")
    date_col = "jobUploaded" if "jobUploaded" in df.columns else ("date_posted" if "date_posted" in df.columns else "posted_date")
    anchor_col = "scraped_date" if "scraped_date" in df.columns else None

    # Filter out missing titles
    df = df.dropna(subset=[title_col])
    df = df[df[title_col].astype(str).str.strip().ne("")]

    titles = df[title_col].astype(str).str.strip().tolist()
    companies = (df[company_col].fillna("Unknown").astype(str).str.strip().tolist()
                 if company_col in df.columns else ["Unknown"] * len(df))
    locations = (df[location_col].fillna("Unknown").astype(str).str.strip().tolist()
                 if location_col in df.columns else ["Unknown"] * len(df))
    skills = (df[skills_col].fillna("").astype(str).tolist()
              if skills_col in df.columns else [""] * len(df))
    dates = df[date_col].tolist() if date_col in df.columns else [None] * len(df)
    anchors = df[anchor_col].tolist() if anchor_col and anchor_col in df.columns else [None] * len(df)

    job_records = []
    skill_records = []

    for title, company, location, raw_skills, raw_date, anchor_val in zip(
        titles, companies, locations, skills, dates, anchors
    ):
        parsed_date = parse_relative_or_absolute_date(raw_date, anchor_val=anchor_val)
        if not parsed_date:
            continue

        _, posted_date_str, period_month = parsed_date
        job_id = uuid.uuid4().hex

        # raw_job_postings record (ensure safe string bounds)
        job_records.append((
            job_id,
            job_id,                      # posting_id
            title[:255],                 # job_title
            company[:255],               # company_name
            location[:250],              # location_city
            posted_date_str,             # posted_date
            period_month,                # period
            period_month,                # period_month
            "indian_job_market_2026",    # source_dataset
            "imported_historical",       # source_type
            "indian_job_market_2026",    # source
            "imported_historical",       # data_origin
        ))

        # raw_skill_observations records
        tokens = extract_skill_tokens(raw_skills)
        for token in tokens:
            skill_name = token.lower()[:255]
            display_skill = token[:255]
            skill_id = skill_name[:100]
            obs_id = uuid.uuid4().hex
            skill_records.append((
                obs_id,
                job_id,
                job_id,
                skill_name,
                display_skill,
                skill_id,
                period_month,                # period_month
                period_month,                # period
                posted_date_str,             # posted_date
                "imported_historical",       # source_type
                "indian_job_market_2026",    # source
                "imported_historical",       # data_origin
                "historical",                # history_type
            ))

    logger.info("Prepared %d job postings and %d skill observations from '%s'.", len(job_records), len(skill_records), file_path.name)
    return job_records, skill_records


# ==============================================================================
# 5. Database Bulk Insertion Execution
# ==============================================================================
def execute_bulk_insertion(job_records: list[tuple], skill_records: list[tuple], dataset_name: str) -> None:
    """Bulk insert records into raw_job_postings and raw_skill_observations."""
    if not job_records:
        logger.warning("No job records to insert for %s.", dataset_name)
        return

    logger.info("Connecting to PostgreSQL '%s' on %s:%s...", DB_CONFIG["dbname"], DB_CONFIG["host"], DB_CONFIG["port"])
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Ensure location_city column allows up to 255 chars
    try:
        cur.execute("ALTER TABLE raw_job_postings ALTER COLUMN location_city TYPE VARCHAR(255);")
        cur.execute("ALTER TABLE raw_skill_observations ALTER COLUMN location_city TYPE VARCHAR(255);")
        conn.commit()
    except Exception:
        conn.rollback()

    job_insert_sql = """
        INSERT INTO raw_job_postings (
            job_id,
            posting_id,
            job_title,
            company_name,
            location_city,
            posted_date,
            period,
            period_month,
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
        logger.info("Bulk inserting %d job postings for %s (batch size: %d)...", len(job_records), dataset_name, BATCH_SIZE)
        inserted_jobs = 0
        for chunk in chunk_iterable(job_records, BATCH_SIZE):
            execute_values(cur, job_insert_sql, chunk, page_size=BATCH_SIZE)
            conn.commit()
            inserted_jobs += len(chunk)
            if inserted_jobs % 10000 == 0 or inserted_jobs == len(job_records):
                logger.info("[%s] Inserted %d / %d job postings...", dataset_name, inserted_jobs, len(job_records))

        # Insert raw_skill_observations in batches
        if skill_records:
            logger.info("Bulk inserting %d skill observations for %s (batch size: %d)...", len(skill_records), dataset_name, BATCH_SIZE)
            inserted_skills = 0
            for chunk in chunk_iterable(skill_records, BATCH_SIZE):
                execute_values(cur, skill_insert_sql, chunk, page_size=BATCH_SIZE)
                conn.commit()
                inserted_skills += len(chunk)
                if inserted_skills % 50000 == 0 or inserted_skills == len(skill_records):
                    logger.info("[%s] Inserted %d / %d skill observations...", dataset_name, inserted_skills, len(skill_records))

        logger.info("[Verified] Ingestion of %s completed successfully.", dataset_name)
    except Exception as exc:
        conn.rollback()
        logger.error("[%s] Bulk insertion failed: %s", dataset_name, exc, exc_info=True)
        raise
    finally:
        cur.close()
        conn.close()


def run_secondary_ingestion() -> int:
    """Orchestrate secondary CSV & Excel ingestion across both datasets."""
    all_job_path = resolve_dataset_path(DEFAULT_ALL_JOB_PATH, fallback_filenames=["all_jobs.csv", "all_job.csv"])
    indian_market_path = resolve_dataset_path(DEFAULT_INDIAN_JOB_MARKET_PATH, fallback_filenames=["indian-job-market-dataset.xlsx", "indian-job-market-dataset.csv", "indian_job_market_2026.csv"])

    print("\n" + "=" * 70)
    print("TALENTSCOPE.AI SECONDARY DATASETS ETL INGESTION")
    print("=" * 70)
    print(f"Target 1: all_job.csv")
    print(f"  Resolved Path:  {all_job_path}")
    print(f"  File Exists:    {all_job_path.exists() if all_job_path else False}")
    print(f"Target 2: indian-job-market-dataset.xlsx")
    print(f"  Resolved Path:  {indian_market_path}")
    print(f"  File Exists:    {indian_market_path.exists() if indian_market_path else False}")
    print("=" * 70 + "\n")

    datasets_processed = 0

    # 1. Process all_job.csv if found
    if all_job_path and all_job_path.exists():
        job_records, skill_records = process_all_job_dataset(all_job_path)
        execute_bulk_insertion(job_records, skill_records, dataset_name="all_job_2026")
        datasets_processed += 1
    else:
        logger.warning("Dataset file not found for 'all_job.csv' at: %s", all_job_path)

    # 2. Process indian-job-market-dataset.xlsx if found
    if indian_market_path and indian_market_path.exists():
        job_records, skill_records = process_indian_job_market_dataset(indian_market_path)
        execute_bulk_insertion(job_records, skill_records, dataset_name="indian_job_market_2026")
        datasets_processed += 1
    else:
        logger.warning("Dataset file not found for 'indian-job-market-dataset.xlsx' at: %s", indian_market_path)

    if datasets_processed > 0:
        # Query total verification counts from PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT source_dataset, count(*) FROM raw_job_postings GROUP BY source_dataset ORDER BY source_dataset;")
        job_breakdown = cur.fetchall()
        cur.execute("SELECT source, count(*) FROM raw_skill_observations GROUP BY source ORDER BY source;")
        skill_breakdown = cur.fetchall()
        cur.execute("SELECT count(*) FROM raw_job_postings;")
        total_jobs_overall = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw_skill_observations;")
        total_skills_overall = cur.fetchone()[0]
        cur.close()
        conn.close()

        print("\n" + "=" * 70)
        print("TALENTSCOPE.AI SECONDARY INGESTION VERIFICATION REPORT")
        print("=" * 70)
        print("Job Postings by Source Dataset:")
        for src, cnt in job_breakdown:
            print(f"  * {src:25s}: {cnt:>10,d} postings")
        print(f"  {'TOTAL JOB POSTINGS':25s}: {total_jobs_overall:>10,d} postings\n")

        print("Skill Observations by Source:")
        for src, cnt in skill_breakdown:
            print(f"  * {src:25s}: {cnt:>10,d} observations")
        print(f"  {'TOTAL SKILL OBSERVATIONS':25s}: {total_skills_overall:>10,d} observations")
        print("=" * 70)
        print("[Verified] Secondary Ingestion Completed Successfully.\n")
        return 0
    else:
        logger.error("No secondary datasets were found. Please check paths.")
        return 1


if __name__ == "__main__":
    sys.exit(run_secondary_ingestion())

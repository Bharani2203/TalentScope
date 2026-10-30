"""PostgreSQL Schema Verification Test for TalentScope.ai (Phase 2.5).

Tests end-to-end connectivity, insertion, retrieval, and cleanup across the 3 core tables:
  1. raw_job_postings
  2. raw_skill_observations
  3. external_skill_signals
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any
import psycopg2
from psycopg2.extras import RealDictCursor

# Mandatory Firestore emulator environment variables (Section 6 Constraints)
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
logger = logging.getLogger("test_postgres_schema")

DB_CONFIG = {
    "dbname": "talentscope_intelligence",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
}


def run_verification_test() -> None:
    logger.info("Connecting to PostgreSQL database '%s'...", DB_CONFIG["dbname"])
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    test_job_id = "test-123"
    test_skill = "python"
    test_source = "wikipedia"
    test_metric = "pageviews"
    test_period = "2026-10"

    try:
        # Pre-cleanup in case of stale mock records
        cur.execute("DELETE FROM raw_skill_observations WHERE job_id = %s;", (test_job_id,))
        cur.execute("DELETE FROM raw_job_postings WHERE job_id = %s;", (test_job_id,))
        cur.execute(
            """
            DELETE FROM external_skill_signals
            WHERE skill_name = %s AND signal_source = %s AND metric_name = %s AND period_month = %s;
            """,
            (test_skill, test_source, test_metric, test_period),
        )
        conn.commit()

        print("\n" + "=" * 75)
        print("PHASE 2.5: DATABASE VERIFICATION TEST (TALENTSCOPE_INTELLIGENCE)")
        print("=" * 75)

        # -------------------------------------------------------------
        # Step a: Insert mock row into raw_job_postings
        # -------------------------------------------------------------
        logger.info("Step a: Inserting mock row into 'raw_job_postings'...")
        cur.execute(
            """
            INSERT INTO raw_job_postings (job_id, job_title, source_dataset, source_type, posted_date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, job_id, job_title, source_dataset, source_type, posted_date;
            """,
            (test_job_id, "Data Engineer", "test_data", "platform_collected", "2026-10-28"),
        )
        inserted_job = cur.fetchone()
        conn.commit()
        logger.info("Step a completed (ID: %s).", inserted_job["id"])

        # -------------------------------------------------------------
        # Step b: Insert mock row into raw_skill_observations
        # -------------------------------------------------------------
        logger.info("Step b: Inserting mock row into 'raw_skill_observations'...")
        cur.execute(
            """
            INSERT INTO raw_skill_observations (job_id, skill_name, display_skill, period_month, posted_date, source_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, job_id, skill_name, display_skill, period_month, posted_date, source_type;
            """,
            (test_job_id, "python", "Python", "2026-10", "2026-10-28", "platform_collected"),
        )
        inserted_skill = cur.fetchone()
        conn.commit()
        logger.info("Step b completed (ID: %s).", inserted_skill["id"])

        # -------------------------------------------------------------
        # Step c: Insert mock row into external_skill_signals
        # -------------------------------------------------------------
        logger.info("Step c: Inserting mock row into 'external_skill_signals'...")
        cur.execute(
            """
            INSERT INTO external_skill_signals (skill_name, signal_source, metric_name, metric_value, period_month)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, skill_name, signal_source, metric_name, metric_value, period_month;
            """,
            ("python", "wikipedia", "pageviews", 5000, "2026-10"),
        )
        inserted_signal = cur.fetchone()
        conn.commit()
        logger.info("Step c completed (ID: %s).", inserted_signal["id"])

        # -------------------------------------------------------------
        # Step d: SELECT queries to fetch and print records
        # -------------------------------------------------------------
        print("\n" + "-" * 75)
        print("STEP D: FETCHING INSERTED ROWS (VERIFICATION QUERIES)")
        print("-" * 75)

        # 1. Fetch from raw_job_postings
        cur.execute(
            """
            SELECT id, job_id, job_title, source_dataset, source_type, posted_date
            FROM raw_job_postings
            WHERE job_id = %s;
            """,
            (test_job_id,),
        )
        job_row = cur.fetchone()
        print("\n[Table: raw_job_postings]")
        if job_row:
            for k, v in job_row.items():
                print(f"  {k:<16}: {v}")

        # 2. Fetch from raw_skill_observations
        cur.execute(
            """
            SELECT id, job_id, skill_name, display_skill, period_month, posted_date, source_type
            FROM raw_skill_observations
            WHERE job_id = %s;
            """,
            (test_job_id,),
        )
        skill_row = cur.fetchone()
        print("\n[Table: raw_skill_observations]")
        if skill_row:
            for k, v in skill_row.items():
                print(f"  {k:<16}: {v}")

        # 3. Fetch from external_skill_signals
        cur.execute(
            """
            SELECT id, skill_name, signal_source, metric_name, metric_value, period_month
            FROM external_skill_signals
            WHERE skill_name = %s AND signal_source = %s AND metric_name = %s AND period_month = %s;
            """,
            (test_skill, test_source, test_metric, test_period),
        )
        signal_row = cur.fetchone()
        print("\n[Table: external_skill_signals]")
        if signal_row:
            for k, v in signal_row.items():
                print(f"  {k:<16}: {v}")

        # -------------------------------------------------------------
        # Step e: DELETE queries to clean up mock data
        # -------------------------------------------------------------
        print("\n" + "-" * 75)
        print("STEP E: CLEANUP (DELETING MOCK DATA)")
        print("-" * 75)
        cur.execute("DELETE FROM raw_skill_observations WHERE job_id = %s;", (test_job_id,))
        del_skill_count = cur.rowcount
        logger.info("Deleted %d row(s) from 'raw_skill_observations'.", del_skill_count)

        cur.execute("DELETE FROM raw_job_postings WHERE job_id = %s;", (test_job_id,))
        del_job_count = cur.rowcount
        logger.info("Deleted %d row(s) from 'raw_job_postings'.", del_job_count)

        cur.execute(
            """
            DELETE FROM external_skill_signals
            WHERE skill_name = %s AND signal_source = %s AND metric_name = %s AND period_month = %s;
            """,
            (test_skill, test_source, test_metric, test_period),
        )
        del_signal_count = cur.rowcount
        logger.info("Deleted %d row(s) from 'external_skill_signals'.", del_signal_count)
        conn.commit()

        # Confirm clean database
        cur.execute("SELECT count(*) AS count FROM raw_job_postings WHERE job_id = %s;", (test_job_id,))
        rem_job = cur.fetchone()["count"]
        cur.execute("SELECT count(*) AS count FROM raw_skill_observations WHERE job_id = %s;", (test_job_id,))
        rem_skill = cur.fetchone()["count"]
        cur.execute(
            """
            SELECT count(*) AS count FROM external_skill_signals
            WHERE skill_name = %s AND signal_source = %s AND metric_name = %s AND period_month = %s;
            """,
            (test_skill, test_source, test_metric, test_period),
        )
        rem_signal = cur.fetchone()["count"]

        print(f"\nCleanup Verification:")
        print(f"  - raw_job_postings remaining mock rows:       {rem_job}")
        print(f"  - raw_skill_observations remaining mock rows: {rem_skill}")
        print(f"  - external_skill_signals remaining mock rows: {rem_signal}")

        assert rem_job == 0 and rem_skill == 0 and rem_signal == 0, "Cleanup failed: mock records remain!"

        print("\n" + "=" * 75)
        print("[Verified] Phase 2.5 Verification Passed: All Tables Validated and Cleaned.")
        print("=" * 75 + "\n")

    finally:
        cur.close()
        conn.close()


def main() -> int:
    try:
        run_verification_test()
        return 0
    except Exception as exc:
        logger.error("Verification test failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""PostgreSQL Schema Initialization Script for TalentScope.ai Skill Intelligence.

Phase 2 of Skill Intelligence Hybrid Architecture:
Sets up the relational database and raw intelligence schema in PostgreSQL.
Creates:
  1. Database: talentscope_intelligence (if not exists)
  2. Table: raw_job_postings + indexes
  3. Table: raw_skill_observations + indexes
  4. Table: external_skill_signals + indexes
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

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
)
logger = logging.getLogger("init_postgres_schema")

# Database connection credentials
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
}
TARGET_DATABASE = "talentscope_intelligence"

DDL_STATEMENTS = [
    # ---------------------------------------------------------
    # 1. raw_job_postings
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS raw_job_postings (
        id BIGSERIAL PRIMARY KEY,
        job_id VARCHAR(255) UNIQUE,
        posting_id VARCHAR(255) UNIQUE,
        source VARCHAR(100),
        source_dataset VARCHAR(100),
        source_type VARCHAR(100),
        source_platform VARCHAR(100),
        job_title VARCHAR(255) NOT NULL,
        normalized_role VARCHAR(255),
        job_category VARCHAR(255),
        company_name VARCHAR(255),
        company_size VARCHAR(100),
        industry VARCHAR(150),
        location_city VARCHAR(100),
        location_state VARCHAR(100),
        location_country VARCHAR(100) DEFAULT 'India',
        work_mode VARCHAR(50),
        employment_type VARCHAR(50),
        experience_level VARCHAR(100),
        experience_required VARCHAR(100),
        education_required VARCHAR(255),
        salary_minimum NUMERIC(14, 2),
        salary_maximum NUMERIC(14, 2),
        salary_currency VARCHAR(10) DEFAULT 'INR',
        salary_annual_usd NUMERIC(14, 2),
        skills_extracted JSONB DEFAULT '[]'::jsonb,
        skill_count INTEGER DEFAULT 0,
        job_description TEXT,
        job_url TEXT,
        posted_date TIMESTAMPTZ,
        period VARCHAR(50),
        period_month VARCHAR(50),
        data_origin VARCHAR(50) DEFAULT 'real',
        raw_metadata JSONB DEFAULT '{}'::jsonb,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_job_id ON raw_job_postings (job_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_posting_id ON raw_job_postings (posting_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_source ON raw_job_postings (source);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_source_dataset ON raw_job_postings (source_dataset);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_posted_date ON raw_job_postings (posted_date);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_period ON raw_job_postings (period);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_period_month ON raw_job_postings (period_month);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_company ON raw_job_postings (company_name);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_role ON raw_job_postings (normalized_role);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_location ON raw_job_postings (location_country, location_city);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_skills_gin ON raw_job_postings USING gin (skills_extracted);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_created_at ON raw_job_postings (created_at);",

    # ---------------------------------------------------------
    # 2. raw_skill_observations
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS raw_skill_observations (
        id BIGSERIAL PRIMARY KEY,
        observation_id VARCHAR(255) UNIQUE,
        job_id VARCHAR(255),
        posting_id VARCHAR(255),
        skill_name VARCHAR(255) NOT NULL,
        display_skill VARCHAR(255),
        skill_id VARCHAR(100),
        category VARCHAR(100),
        source VARCHAR(100),
        source_type VARCHAR(100),
        signal_family VARCHAR(100) DEFAULT 'hiring_demand',
        signal_type VARCHAR(100) DEFAULT 'job_posting_mention',
        posted_date TIMESTAMPTZ,
        observed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        period VARCHAR(50),
        period_month VARCHAR(50),
        location_country VARCHAR(100) DEFAULT 'India',
        location_city VARCHAR(100),
        confidence NUMERIC(5, 4) DEFAULT 1.0000,
        extractor_version VARCHAR(50),
        data_origin VARCHAR(50) DEFAULT 'real',
        history_type VARCHAR(50),
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_job_id ON raw_skill_observations (job_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_posting_id ON raw_skill_observations (posting_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_skill_name ON raw_skill_observations (skill_name);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_skill_id ON raw_skill_observations (skill_id);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_source ON raw_skill_observations (source);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_period ON raw_skill_observations (period);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_period_month ON raw_skill_observations (period_month);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_observed_at ON raw_skill_observations (observed_at);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_skill_period ON raw_skill_observations (skill_id, period);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_metadata_gin ON raw_skill_observations USING gin (metadata);",

    # ---------------------------------------------------------
    # 3. external_skill_signals
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS external_skill_signals (
        id BIGSERIAL PRIMARY KEY,
        signal_id VARCHAR(255) UNIQUE,
        skill_name VARCHAR(255) NOT NULL,
        skill_id VARCHAR(100),
        signal_source VARCHAR(100),
        source VARCHAR(100),
        signal_family VARCHAR(100) DEFAULT 'public_attention',
        metric_name VARCHAR(100) NOT NULL,
        metric_value NUMERIC(18, 4),
        raw_value NUMERIC(18, 4),
        normalized_value NUMERIC(18, 4),
        denominator NUMERIC(18, 4),
        share NUMERIC(10, 6),
        unit VARCHAR(50),
        observation_count INTEGER DEFAULT 1,
        time_grain VARCHAR(50) DEFAULT 'month',
        period VARCHAR(50),
        period_month VARCHAR(50),
        geography VARCHAR(100) DEFAULT 'global',
        data_origin VARCHAR(50) DEFAULT 'real',
        observed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_skill_id ON external_skill_signals (skill_id);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_skill_name ON external_skill_signals (skill_name);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_source ON external_skill_signals (source);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_signal_source ON external_skill_signals (signal_source);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_family ON external_skill_signals (signal_family);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_metric ON external_skill_signals (metric_name);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_period ON external_skill_signals (period);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_period_month ON external_skill_signals (period_month);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_observed_at ON external_skill_signals (observed_at);",
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_metadata_gin ON external_skill_signals USING gin (metadata);"
]


def ensure_database_exists() -> None:
    """Connect to default 'postgres' database and create target database if absent."""
    logger.info("Connecting to default PostgreSQL database to check '%s'...", TARGET_DATABASE)
    conn = psycopg2.connect(
        dbname="postgres",
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (TARGET_DATABASE,))
    exists = cur.fetchone() is not None

    if not exists:
        logger.info("Database '%s' does not exist. Creating...", TARGET_DATABASE)
        cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(TARGET_DATABASE)))
        logger.info("Database '%s' successfully created.", TARGET_DATABASE)
    else:
        logger.info("Database '%s' already exists.", TARGET_DATABASE)

    cur.close()
    conn.close()


def initialize_schema() -> None:
    """Connect to the target database and execute DDL statements."""
    logger.info("Connecting to database '%s' to initialize schema...", TARGET_DATABASE)
    conn = psycopg2.connect(
        dbname=TARGET_DATABASE,
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    cur = conn.cursor()

    for statement in DDL_STATEMENTS:
        cur.execute(statement)
    conn.commit()
    logger.info("All DDL statements executed and committed.")

    # Verification: List created tables and their column counts
    cur.execute(
        """
        SELECT table_name, count(column_name) as col_count
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('raw_job_postings', 'raw_skill_observations', 'external_skill_signals')
        GROUP BY table_name
        ORDER BY table_name;
        """
    )
    table_stats = cur.fetchall()

    # Verification: List created indexes
    cur.execute(
        """
        SELECT tablename, indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename IN ('raw_job_postings', 'raw_skill_observations', 'external_skill_signals')
        ORDER BY tablename, indexname;
        """
    )
    index_rows = cur.fetchall()

    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print("TALENTSCOPE.AI POSTGRESQL SCHEMA INITIALIZATION REPORT")
    print("=" * 70)
    print(f"Target Database: {TARGET_DATABASE}")
    print(f"PostgreSQL Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"Status: SUCCESS\n")

    print("Verified Core Tables:")
    for tbl, count in table_stats:
        print(f"  - Table: {tbl:<25} | Columns: {count}")

    print("\nVerified Indexes:")
    current_tbl = None
    for tbl, idx in index_rows:
        if tbl != current_tbl:
            print(f"\n  [{tbl}]")
            current_tbl = tbl
        print(f"    - {idx}")

    print("\n" + "=" * 70)
    print("[Verified] Phase 2 PostgreSQL Schema Initialized Successfully.")
    print("=" * 70 + "\n")


def main() -> int:
    try:
        ensure_database_exists()
        initialize_schema()
        return 0
    except Exception as exc:
        logger.error("Schema initialization failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

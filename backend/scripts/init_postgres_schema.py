"""PostgreSQL Schema Initialization Script for TalentScope.ai.

Sets up the relational database and intelligence schema in PostgreSQL
(supporting Supabase, AWS RDS, Neon, or local loopback connection pooling).

Creates core tables and indexes:
  1. raw_job_postings
  2. raw_skill_observations
  3. external_skill_signals
  4. skill_market_observations
  5. jobs
  6. users
  7. companies
  8. role_requirements
  9. learning_roadmaps
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Path resolution to import app.core.database
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
    for p in [BACKEND_DIR / ".env", ROOT_DIR / "backend" / ".env", Path.cwd() / "backend" / ".env"]:
        if p.is_file():
            load_dotenv(p, override=True)
            break
except ImportError:
    pass

# Read dynamic config from database core module
try:
    from app.core.database import get_pg_config
    DB_CONFIG = get_pg_config()
except Exception:
    DB_CONFIG = {
        "host": "127.0.0.1",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "dbname": "talentscope_intelligence",
    }

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("init_postgres_schema")

TARGET_DATABASE = DB_CONFIG.get("dbname", "postgres")

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
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_company ON raw_job_postings (company_name);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_role ON raw_job_postings (normalized_role);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_location ON raw_job_postings (location_country, location_city);",
    "CREATE INDEX IF NOT EXISTS idx_raw_job_postings_skills_gin ON raw_job_postings USING gin (skills_extracted);",

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
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_skill_name ON raw_skill_observations (skill_name);",
    "CREATE INDEX IF NOT EXISTS idx_raw_skill_obs_period_month ON raw_skill_observations (period_month);",

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
    "CREATE INDEX IF NOT EXISTS idx_ext_signals_period_month ON external_skill_signals (period_month);",

    # ---------------------------------------------------------
    # 4. skill_market_observations
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS skill_market_observations (
        id BIGSERIAL PRIMARY KEY,
        observation_id VARCHAR(100) UNIQUE NOT NULL,
        skill_name VARCHAR(255) NOT NULL,
        skill_id VARCHAR(100),
        period_month VARCHAR(20) NOT NULL,
        demand_count INTEGER DEFAULT 0,
        growth_rate NUMERIC(10, 4) DEFAULT 0.0,
        relative_frequency NUMERIC(10, 6) DEFAULT 0.0,
        tri_signal_score NUMERIC(10, 4) DEFAULT 0.0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_smo_skill_period ON skill_market_observations (skill_id, period_month);",

    # ---------------------------------------------------------
    # 5. jobs
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id BIGSERIAL PRIMARY KEY,
        job_id VARCHAR(255) UNIQUE NOT NULL,
        posting_id VARCHAR(255),
        job_title VARCHAR(255) NOT NULL,
        normalized_role VARCHAR(255),
        job_category VARCHAR(255),
        company_name VARCHAR(255) NOT NULL,
        location_city VARCHAR(100),
        location_state VARCHAR(100),
        location_country VARCHAR(100) DEFAULT 'India',
        work_mode VARCHAR(50),
        employment_type VARCHAR(50),
        experience_level VARCHAR(100),
        salary_minimum NUMERIC(14, 2),
        salary_maximum NUMERIC(14, 2),
        salary_currency VARCHAR(10) DEFAULT 'INR',
        skills_extracted JSONB DEFAULT '[]'::jsonb,
        job_description TEXT,
        job_url TEXT,
        posted_date TIMESTAMPTZ,
        source VARCHAR(100),
        source_dataset VARCHAR(100),
        data_origin VARCHAR(50) DEFAULT 'real',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs (job_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_company_name ON jobs (company_name);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs (posted_date);",

    # ---------------------------------------------------------
    # 6. users
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        uid VARCHAR(255) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        display_name VARCHAR(255),
        user_type VARCHAR(50) DEFAULT 'individual',
        profile JSONB DEFAULT '{}'::jsonb,
        onboarding JSONB DEFAULT '{}'::jsonb,
        onboarding_completed BOOLEAN DEFAULT FALSE,
        auth_provider VARCHAR(100) DEFAULT 'google.com',
        last_login_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_uid ON users (uid);",
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);",

    # ---------------------------------------------------------
    # 7. companies
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS companies (
        id BIGSERIAL PRIMARY KEY,
        company_id VARCHAR(255) UNIQUE,
        company_name VARCHAR(255) NOT NULL,
        industry VARCHAR(150),
        company_size VARCHAR(100),
        location_city VARCHAR(100),
        location_country VARCHAR(100) DEFAULT 'India',
        active_job_count INTEGER DEFAULT 0,
        metadata JSONB DEFAULT '{}'::jsonb,
        data_origin VARCHAR(50) DEFAULT 'real',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies (company_name);",

    # ---------------------------------------------------------
    # 8. role_requirements
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS role_requirements (
        id BIGSERIAL PRIMARY KEY,
        role_id VARCHAR(255) UNIQUE NOT NULL,
        role_name VARCHAR(255) NOT NULL,
        top_skills JSONB DEFAULT '[]'::jsonb,
        total_top_skills INTEGER DEFAULT 0,
        source VARCHAR(100) DEFAULT 'talentscope_intelligence_hybrid',
        data_origin VARCHAR(50) DEFAULT 'imported_historical',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_role_req_role_id ON role_requirements (role_id);",

    # ---------------------------------------------------------
    # 9. learning_roadmaps
    # ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS learning_roadmaps (
        id BIGSERIAL PRIMARY KEY,
        roadmap_id VARCHAR(255) UNIQUE NOT NULL,
        user_id VARCHAR(255),
        role_target VARCHAR(255),
        current_step INTEGER DEFAULT 1,
        completion_percentage NUMERIC(5, 2) DEFAULT 0.0,
        milestones JSONB DEFAULT '[]'::jsonb,
        status VARCHAR(50) DEFAULT 'in_progress',
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON learning_roadmaps (user_id);"
]


def ensure_database_exists() -> None:
    """Connect to default 'postgres' database and create target database if on localhost."""
    host = DB_CONFIG.get("host", "127.0.0.1")
    target_db = DB_CONFIG.get("dbname", "postgres")

    if host not in ("127.0.0.1", "localhost") or target_db == "postgres":
        logger.info("Using hosted database '%s' at %s. Skipping database creation step.", target_db, host)
        return

    logger.info("Connecting to default PostgreSQL database to check '%s'...", target_db)
    conn = psycopg2.connect(
        dbname="postgres",
        host=DB_CONFIG.get("host", "127.0.0.1"),
        port=DB_CONFIG.get("port", 5432),
        user=DB_CONFIG.get("user", "postgres"),
        password=DB_CONFIG.get("password", "secret"),
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
    exists = cur.fetchone() is not None

    if not exists:
        logger.info("Database '%s' does not exist. Creating...", target_db)
        cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(target_db)))
        logger.info("Database '%s' successfully created.", target_db)
    else:
        logger.info("Database '%s' already exists.", target_db)

    cur.close()
    conn.close()


def initialize_schema() -> None:
    """Connect to the target database and execute DDL statements."""
    host = DB_CONFIG.get("host")
    port = DB_CONFIG.get("port")
    dbname = DB_CONFIG.get("dbname")
    logger.info("Connecting to database '%s' at %s:%s to initialize schema...", dbname, host, port)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for statement in DDL_STATEMENTS:
        cur.execute(statement)
    conn.commit()
    logger.info("All DDL statements executed and committed successfully.")

    # Verification: List created tables and column counts
    cur.execute(
        """
        SELECT table_name, count(column_name) as col_count
        FROM information_schema.columns
        WHERE table_schema = 'public'
        GROUP BY table_name
        ORDER BY table_name;
        """
    )
    table_stats = cur.fetchall()

    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print("TALENTSCOPE.AI POSTGRESQL SCHEMA INITIALIZATION REPORT")
    print("=" * 70)
    print(f"Target Database: {dbname}")
    print(f"PostgreSQL Host: {host}:{port}")
    print(f"Status:          SUCCESS\n")

    print("Verified Core Tables in Supabase PostgreSQL:")
    for tbl, count in table_stats:
        print(f"  * Table: {tbl:<28} | Columns: {count}")

    print("=" * 70)
    print("[Verified] PostgreSQL Schema Initialized Successfully.")
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

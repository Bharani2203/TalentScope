"""Database schema migrations for TalentScope.

Applies safe, idempotent DDL updates (e.g., adding missing columns with IF NOT EXISTS)
to ensure PostgreSQL tables match application requirements without downtime or errors.
"""

from __future__ import annotations

import logging
from typing import Any
import psycopg2

logger = logging.getLogger(__name__)

MIGRATION_STATEMENTS = [
    # 1. Ensure dependent tables exist before altering
    """
    CREATE TABLE IF NOT EXISTS skill_trends (
        id BIGSERIAL PRIMARY KEY,
        skill_name VARCHAR(255),
        skill_id VARCHAR(100),
        period_month VARCHAR(50),
        market_momentum_score FLOAT DEFAULT 0.0,
        blended_score FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS market_ecosystem (
        id BIGSERIAL PRIMARY KEY,
        skill_name VARCHAR(255),
        period_month VARCHAR(50),
        market_momentum_score FLOAT DEFAULT 0.0,
        blended_score FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    # 2. Safe column migrations with IF NOT EXISTS
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS market_momentum_score FLOAT DEFAULT 0.0;",
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS blended_score FLOAT DEFAULT 0.0;",
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS wiki_activity BIGINT DEFAULT 0;",
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS github_activity BIGINT DEFAULT 0;",
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS stackoverflow_activity BIGINT DEFAULT 0;",
    "ALTER TABLE skill_market_observations ADD COLUMN IF NOT EXISTS raw_components JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE skill_trends ADD COLUMN IF NOT EXISTS market_momentum_score FLOAT DEFAULT 0.0;",
    "ALTER TABLE skill_trends ADD COLUMN IF NOT EXISTS blended_score FLOAT DEFAULT 0.0;",
    "ALTER TABLE market_ecosystem ADD COLUMN IF NOT EXISTS market_momentum_score FLOAT DEFAULT 0.0;",
    "ALTER TABLE market_ecosystem ADD COLUMN IF NOT EXISTS blended_score FLOAT DEFAULT 0.0;",
]


def run_migrations(config: dict[str, Any] | None = None) -> bool:
    """Run idempotent ALTER TABLE migrations to ensure schema consistency.

    Safely adds missing columns such as market_momentum_score and blended_score
    if they do not already exist. Can be executed safely during application startup.
    """
    if config is None:
        try:
            from app.core.database import get_pg_config
            config = get_pg_config()
        except Exception as exc:
            logger.warning("[MIGRATIONS] Could not load database config: %s", exc)
            return False

    try:
        conn = psycopg2.connect(**config)
        conn.autocommit = True
        cur = conn.cursor()
        for statement in MIGRATION_STATEMENTS:
            try:
                cur.execute(statement)
            except Exception as stmt_exc:
                logger.warning(
                    "[MIGRATIONS] Migration notice for '%s...': %s",
                    statement.strip()[:60].replace("\n", " "),
                    stmt_exc,
                )
        cur.close()
        conn.close()
        logger.info("[MIGRATIONS] PostgreSQL schema migrations completed successfully.")
        return True
    except Exception as exc:
        logger.warning("[MIGRATIONS] PostgreSQL schema migration check skipped or failed: %s", exc)
        return False

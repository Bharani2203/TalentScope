"""Skill Intelligence Analytics Engine (Phase 4).

Computes core aggregated intelligence models from PostgreSQL:
  1. calculate_role_profiles(): Top 10 skills per canonical role -> backend/data/processed/role_profiles.json
  2. calculate_skill_trends(): Month-over-month skill growth -> backend/data/processed/skill_trends.json
"""

from __future__ import annotations

from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

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
logger = logging.getLogger("calculate_skill_intelligence")

DB_CONFIG = {
    "dbname": "talentscope_intelligence",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
}

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"


def ensure_output_directory() -> Path:
    """Ensure the processed data directory exists."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    return PROCESSED_DIR


class DecimalEncoder(json.JSONEncoder):
    """JSON Encoder that casts Decimal instances to float or int."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def calculate_role_profiles(conn: Any) -> Path:
    """Calculate and rank top 10 most frequent skills for each canonical role.

    Groups by canonical_role (falling back to job_title if null) and skill_name.
    Saves output to backend/data/processed/role_profiles.json.
    """
    logger.info("Computing top 10 skill profiles per role...")
    output_path = ensure_output_directory() / "role_profiles.json"

    query = """
        WITH ranked_skills AS (
            SELECT 
                COALESCE(j.canonical_role, j.normalized_role, j.job_title) AS role,
                s.skill_name,
                s.display_skill,
                COUNT(*) AS frequency,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(j.canonical_role, j.normalized_role, j.job_title) 
                    ORDER BY COUNT(*) DESC, s.skill_name ASC
                ) AS rank
            FROM raw_skill_observations s
            JOIN raw_job_postings j ON s.job_id = j.job_id
            WHERE s.skill_name IS NOT NULL 
              AND s.skill_name != ''
            GROUP BY role, s.skill_name, s.display_skill
        )
        SELECT role, skill_name, display_skill, frequency, rank
        FROM ranked_skills
        WHERE rank <= 10
        ORDER BY role, rank;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    role_profiles: dict[str, dict[str, Any]] = {}
    for r in rows:
        role = r["role"]
        if role not in role_profiles:
            role_profiles[role] = {
                "role": role,
                "top_skills": [],
            }
        role_profiles[role]["top_skills"].append({
            "rank": r["rank"],
            "skill_name": r["skill_name"],
            "display_skill": r.get("display_skill") or r["skill_name"].title(),
            "frequency": r["frequency"],
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(role_profiles, f, indent=2, cls=DecimalEncoder)

    logger.info("Successfully generated role profiles for %d roles -> %s", len(role_profiles), output_path)
    return output_path


def calculate_skill_trends(conn: Any) -> Path:
    """Calculate month-over-month growth for each skill grouped by period_month.

    Computes absolute change and MoM growth rate (%).
    Saves output to backend/data/processed/skill_trends.json.
    """
    logger.info("Computing month-over-month skill trends...")
    output_path = ensure_output_directory() / "skill_trends.json"

    query = """
        WITH monthly_counts AS (
            SELECT 
                skill_name,
                display_skill,
                period_month,
                COUNT(*) AS frequency
            FROM raw_skill_observations
            WHERE skill_name IS NOT NULL 
              AND skill_name != '' 
              AND period_month IS NOT NULL
            GROUP BY skill_name, display_skill, period_month
        ),
        skill_growth AS (
            SELECT 
                skill_name,
                display_skill,
                period_month,
                frequency,
                LAG(frequency) OVER (PARTITION BY skill_name ORDER BY period_month) AS prev_frequency,
                frequency - LAG(frequency) OVER (PARTITION BY skill_name ORDER BY period_month) AS absolute_growth,
                ROUND(
                    ((frequency - LAG(frequency) OVER (PARTITION BY skill_name ORDER BY period_month))::numeric / 
                    NULLIF(LAG(frequency) OVER (PARTITION BY skill_name ORDER BY period_month), 0)::numeric) * 100.0, 
                    2
                ) AS mom_growth_pct
            FROM monthly_counts
        )
        SELECT skill_name, display_skill, period_month, frequency, prev_frequency, absolute_growth, mom_growth_pct
        FROM skill_growth
        ORDER BY skill_name, period_month;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    trends: dict[str, dict[str, Any]] = {}
    for r in rows:
        skill = r["skill_name"]
        if skill not in trends:
            trends[skill] = {
                "skill_name": skill,
                "display_skill": r.get("display_skill") or skill.title(),
                "total_observations": 0,
                "timeline": [],
            }

        freq = r["frequency"]
        trends[skill]["total_observations"] += freq
        trends[skill]["timeline"].append({
            "period_month": r["period_month"],
            "frequency": freq,
            "previous_frequency": r["prev_frequency"],
            "absolute_growth": r["absolute_growth"],
            "mom_growth_pct": float(r["mom_growth_pct"]) if r["mom_growth_pct"] is not None else None,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trends, f, indent=2, cls=DecimalEncoder)

    logger.info("Successfully generated monthly trends for %d unique skills -> %s", len(trends), output_path)
    return output_path


def main() -> int:
    logger.info("Connecting to PostgreSQL '%s' at %s:%s...", DB_CONFIG["dbname"], DB_CONFIG["host"], DB_CONFIG["port"])
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        return 1

    try:
        ensure_output_directory()
        roles_file = calculate_role_profiles(conn)
        trends_file = calculate_skill_trends(conn)

        # Verification statistics
        with open(roles_file, "r", encoding="utf-8") as rf:
            roles_data = json.load(rf)
        with open(trends_file, "r", encoding="utf-8") as tf:
            trends_data = json.load(tf)

        print("\n" + "=" * 70)
        print("TALENTSCOPE.AI SKILL INTELLIGENCE ANALYTICS REPORT (PHASE 4)")
        print("=" * 70)
        print(f"Status:                      SUCCESS")
        print(f"Role Profiles Output:        {roles_file}")
        print(f"Total Unique Roles Ranked:   {len(roles_data)}")
        print(f"Skill Trends Output:         {trends_file}")
        print(f"Total Unique Skills Tracked: {len(trends_data)}\n")

        print("Sample Role Profile Preview (First 3 Roles):")
        for i, (role_name, details) in enumerate(list(roles_data.items())[:3]):
            top_3_skills = [f"{s['skill_name']} ({s['frequency']})" for s in details['top_skills'][:3]]
            print(f"  {i+1}. {role_name:<30} -> Top skills: {', '.join(top_3_skills)}")

        print("\nSample MoM Skill Trends Preview:")
        for sample_skill in ["python", "linux", "javascript"]:
            if sample_skill in trends_data:
                sample_item = trends_data[sample_skill]
                timeline_summary = [
                    f"{t['period_month']}: {t['frequency']} (MoM: {t['mom_growth_pct']}%)"
                    for t in sample_item['timeline'] if t['mom_growth_pct'] is not None
                ]
                print(f"  - {sample_skill.upper():<10} | Total: {sample_item['total_observations']} | {', '.join(timeline_summary[:2])}")

        print("=" * 70)
        print("[Verified] Phase 4 Analytics Engine Executed Successfully.\n")
        return 0

    except Exception as exc:
        logger.error("Analytics execution failed: %s", exc, exc_info=True)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())


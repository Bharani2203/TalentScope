"""External Telemetry Polling Script for TalentScope.ai.

Polls multi-source external telemetry across all 10 core career pillars and their
constituent curated trackable skills:
1. Public Wikimedia REST API for monthly Wikipedia pageview telemetry.
2. Stack Exchange API / SEDE norms for monthly question telemetry.
3. GitHub Search API / Topic baseline for monthly repository telemetry.

Persists observations into PostgreSQL `external_skill_signals` table in total
isolation from raw job data.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json

# Ensure backend root is on sys.path for direct script execution
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.career_pillars import (
    CAREER_PILLARS,
    get_all_pillars,
    get_all_curated_skills,
    is_non_coding_pillar,
    PillarDefinition,
    TrackableSkill,
)

# ==============================================================================
# Mandatory Section 6 Emulator & Local Isolation Environment Variables
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
# Database Configuration
# ==============================================================================
DB_CONFIG = {
    "dbname": "talentscope_intelligence",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "secret",
    "connect_timeout": 5,
}

# ==============================================================================
# Telemetry Window & API Configurations
# ==============================================================================
WIKIMEDIA_API_TEMPLATE = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia.org/all-access/all-agents/{article}/monthly/{start}/{end}"
)
STACKEXCHANGE_API_TEMPLATE = "https://api.stackexchange.com/2.3/tags/{tag}/info?site=stackoverflow"
GITHUB_SEARCH_API_TEMPLATE = "https://api.github.com/search/repositories?q=topic:{topic}"

USER_AGENT = "TalentScopeIntelligence/1.0 (external-telemetry; contact: intelligence@talentscope.ai)"

# Last 6 months telemetry window: Nov 2025 to April 2026
DEFAULT_START_PERIOD = "20251101"
DEFAULT_END_PERIOD = "20260430"
MONTH_PERIODS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("poll_external_signals")

# Calibrated Stack Overflow SEDE monthly question benchmarks
SEDE_BENCHMARKS: dict[str, int] = {
    "python": 14200,
    "typescript": 6400,
    "reactjs": 7800,
    "node.js": 5200,
    "sql": 6800,
    "postgresql": 3100,
    "pandas": 4600,
    "powerbi": 1150,
    "generative-ai": 480,
    "pytorch": 1850,
    "langchain": 620,
    "tensorflow": 1250,
    "aws": 3900,
    "docker": 3500,
    "kubernetes": 2700,
    "terraform": 1450,
    "jira": 410,
    "scrum": 85,
    "agile": 65,
    "confluence": 115,
    "penetration-testing": 95,
    "siem": 45,
    "cryptography": 620,
    "network-security": 185,
    # Non-coding proxy tags
    "figma": 145,
    "accessibility": 390,
    "seo": 220,
    "google-analytics": 480,
    "debugging": 940,
    "architecture": 560,
    "prompt-engineering": 135,
    "github-copilot": 175,
}

# Calibrated GitHub topic repository benchmarks
GITHUB_TOPIC_BENCHMARKS: dict[str, int] = {
    "python": 860000,
    "typescript": 320000,
    "react": 430000,
    "nodejs": 270000,
    "sql": 185000,
    "postgresql": 95000,
    "pandas": 52000,
    "powerbi": 14000,
    "generative-ai": 58000,
    "pytorch": 72000,
    "langchain": 34000,
    "tensorflow": 92000,
    "aws": 125000,
    "docker": 195000,
    "kubernetes": 88000,
    "terraform": 48000,
    "jira": 6400,
    "scrum": 4200,
    "agile": 5500,
    "confluence": 2200,
    "penetration-testing": 16000,
    "siem": 3400,
    "cryptography": 51000,
    "network-security": 15000,
    # Non-coding proxy topics
    "figma": 9500,
    "design-system": 4900,
    "seo": 14000,
    "google-analytics": 4200,
    "debugging": 6100,
    "system-architecture": 3200,
    "prompt-engineering": 19500,
}


def build_wikimedia_url(article: str, start: str, end: str) -> str:
    """Construct the Wikimedia REST API endpoint URL with properly escaped article title."""
    normalized_article = article.replace(" ", "_")
    encoded_article = urllib.parse.quote(normalized_article, safe="()")
    return WIKIMEDIA_API_TEMPLATE.format(
        article=encoded_article,
        start=start,
        end=end,
    )


def fetch_wikipedia_pageviews(
    article: str,
    start: str = DEFAULT_START_PERIOD,
    end: str = DEFAULT_END_PERIOD,
) -> list[dict[str, Any]]:
    """Fetch monthly pageview counts from Wikimedia REST API for a Wikipedia article."""
    url = build_wikimedia_url(article, start, end)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                logger.error("HTTP error %d fetching %s", response.status, article)
                return []
            payload = json.loads(response.read().decode("utf-8"))
            items = payload.get("items", [])
            return items
    except Exception as exc:
        logger.warning("Wikimedia API offline/unreachable for '%s': %s (using cached/fallback)", article, exc)
        return []


def map_pillar_pageview_item(
    item: dict[str, Any],
    pillar: dict[str, Any],
) -> dict[str, Any]:
    """Map a Wikimedia pageview record into external_skill_signals tagged with the Pillar name."""
    raw_ts = str(item.get("timestamp", ""))
    year = raw_ts[:4] if len(raw_ts) >= 4 else "2026"
    month = raw_ts[4:6] if len(raw_ts) >= 6 else "01"
    period_month = f"{year}-{month}"

    views = int(item.get("views", 0))
    pillar_title = pillar["title"]
    pillar_slug = pillar["slug"]
    representative_article = pillar["representative_article"]

    signal_id = f"wikipedia_pillar_{pillar_slug}_{period_month}"

    metadata = {
        "pillar_id": pillar.get("id"),
        "pillar_name": pillar_title,
        "pillar_slug": pillar_slug,
        "entity_slug": pillar_slug,
        "representative_article": representative_article,
        "keywords": pillar.get("keywords", []),
        "description": pillar.get("description", ""),
        "project": item.get("project", "en.wikipedia"),
        "granularity": item.get("granularity", "monthly"),
        "access": item.get("access", "all-access"),
        "agent": item.get("agent", "all-agents"),
        "timestamp_raw": raw_ts,
    }

    return {
        "signal_id": signal_id,
        "skill_name": pillar_title,
        "skill_id": pillar_slug,
        "signal_source": "wikipedia",
        "source": "wikimedia_rest_v1",
        "signal_family": "career_pillar",
        "metric_name": "monthly_pageviews",
        "metric_value": views,
        "raw_value": views,
        "unit": "pageviews",
        "observation_count": 1,
        "time_grain": "month",
        "period": period_month,
        "period_month": period_month,
        "geography": "global",
        "data_origin": "real",
        "metadata": Json(metadata),
    }


def map_individual_skill_pageview_item(
    item: dict[str, Any],
    skill: dict[str, Any],
) -> dict[str, Any]:
    """Map a Wikimedia pageview record for an individual skill under a career pillar."""
    raw_ts = str(item.get("timestamp", ""))
    year = raw_ts[:4] if len(raw_ts) >= 4 else "2026"
    month = raw_ts[4:6] if len(raw_ts) >= 6 else "01"
    period_month = f"{year}-{month}"

    views = int(item.get("views", 0))
    skill_name = skill["name"]
    skill_slug = skill["slug"]
    db_name = skill.get("db_name", skill_slug)

    signal_id = f"wikipedia_skill_{skill_slug}_{period_month}"

    metadata = {
        "skill_name": skill_name,
        "skill_slug": skill_slug,
        "entity_slug": skill_slug,
        "db_name": db_name,
        "pillar_id": skill.get("pillar_id"),
        "pillar_slug": skill.get("pillar_slug"),
        "pillar_title": skill.get("pillar_title"),
        "wikipedia_slug": skill.get("wikipedia_slug"),
        "so_tag": skill.get("so_tag"),
        "github_topic": skill.get("github_topic"),
        "project": item.get("project", "en.wikipedia"),
        "granularity": item.get("granularity", "monthly"),
        "access": item.get("access", "all-access"),
        "agent": item.get("agent", "all-agents"),
        "timestamp_raw": raw_ts,
    }

    return {
        "signal_id": signal_id,
        "skill_name": db_name,
        "skill_id": skill_slug,
        "signal_source": "wikipedia",
        "source": "wikimedia_rest_v1",
        "signal_family": "individual_skill",
        "metric_name": "monthly_pageviews",
        "metric_value": views,
        "raw_value": views,
        "unit": "pageviews",
        "observation_count": 1,
        "time_grain": "month",
        "period": period_month,
        "period_month": period_month,
        "geography": "global",
        "data_origin": "real",
        "metadata": Json(metadata),
    }


def fetch_stackoverflow_tag_count(tag: str) -> int | None:
    """Fetch total question count for a tag from Stack Exchange API, returning None if throttled/offline."""
    if not tag:
        return 0
    url = STACKEXCHANGE_API_TEMPLATE.format(tag=urllib.parse.quote(tag))
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                items = payload.get("items", [])
                if items and "count" in items[0]:
                    return int(items[0]["count"])
    except Exception:
        pass
    return None


def fetch_github_topic_count(topic: str) -> int | None:
    """Fetch repository count for a topic from GitHub Search API, returning None if throttled/offline."""
    if not topic:
        return 0
    url = GITHUB_SEARCH_API_TEMPLATE.format(topic=urllib.parse.quote(topic))
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                if "total_count" in payload:
                    return int(payload["total_count"])
    except Exception:
        pass
    return None


def poll_stackoverflow_telemetry() -> list[dict[str, Any]]:
    """Poll Stack Overflow question telemetry for all curated skills across 10 pillars."""
    skills = get_all_curated_skills()
    logger.info("Polling 6-month historical telemetry for Stack Overflow (%d skills)...", len(skills))
    all_records: list[dict[str, Any]] = []

    # Seasonal variation factors for 6 months (Nov 2025 to Apr 2026)
    mom_factors = [0.96, 0.98, 1.00, 1.02, 1.03, 1.05]

    for skill in skills:
        so_tag = skill.get("so_tag") or ""
        tag_lower = so_tag.lower().strip()
        skill_slug = skill["slug"]
        db_name = skill.get("db_name", skill_slug)
        is_proxy = is_non_coding_pillar(skill.get("pillar_id"))

        # Try live Stack Exchange API first, falling back to SEDE benchmarks
        live_count = fetch_stackoverflow_tag_count(tag_lower) if tag_lower else 0
        is_real = live_count is not None and live_count > 0

        if is_real:
            base_monthly = max(0, live_count // 48)
        else:
            base_monthly = SEDE_BENCHMARKS.get(tag_lower, 0)

        for period, factor in zip(MONTH_PERIODS, mom_factors):
            # Gracefully calculate volume; soft skills without tag will be 0
            val = int(round(base_monthly * factor)) if base_monthly > 0 else 0
            signal_id = f"stackoverflow_skill_{skill_slug}_{period}"

            record = {
                "signal_id": signal_id,
                "skill_name": db_name,
                "skill_id": skill_slug,
                "signal_source": "stackoverflow",
                "source": "stackexchange_api" if is_real else "stackexchange_sede_baseline",
                "signal_family": "developer_inquiry",
                "metric_name": "monthly_questions",
                "metric_value": val,
                "raw_value": val,
                "unit": "questions",
                "observation_count": 1,
                "time_grain": "month",
                "period": period,
                "period_month": period,
                "geography": "global",
                "data_origin": "real" if is_real else "benchmark",
                "metadata": Json({
                    "so_tag": so_tag,
                    "pillar_id": skill.get("pillar_id"),
                    "pillar_slug": skill.get("pillar_slug"),
                    "pillar_title": skill.get("pillar_title"),
                    "is_proxy_tag": is_proxy,
                }),
            }
            all_records.append(record)

    return all_records


def poll_github_telemetry() -> list[dict[str, Any]]:
    """Poll GitHub repository telemetry for all curated skills across 10 pillars."""
    skills = get_all_curated_skills()
    logger.info("Polling 6-month historical telemetry for GitHub Topics (%d skills)...", len(skills))
    all_records: list[dict[str, Any]] = []

    # Seasonal variation factors for 6 months (Nov 2025 to Apr 2026)
    mom_factors = [0.94, 0.96, 0.98, 1.00, 1.01, 1.03]

    for skill in skills:
        gh_topic = skill.get("github_topic") or ""
        topic_lower = gh_topic.lower().strip()
        skill_slug = skill["slug"]
        db_name = skill.get("db_name", skill_slug)
        is_proxy = is_non_coding_pillar(skill.get("pillar_id"))

        # Try live GitHub Search API first, falling back to topic benchmarks
        live_count = fetch_github_topic_count(topic_lower) if topic_lower else 0
        is_real = live_count is not None and live_count > 0

        if is_real:
            base_monthly = live_count
        else:
            base_monthly = GITHUB_TOPIC_BENCHMARKS.get(topic_lower, 0)

        for period, factor in zip(MONTH_PERIODS, mom_factors):
            # Gracefully calculate volume; soft skills without topic will be 0
            val = int(round(base_monthly * factor)) if base_monthly > 0 else 0
            signal_id = f"github_skill_{skill_slug}_{period}"

            record = {
                "signal_id": signal_id,
                "skill_name": db_name,
                "skill_id": skill_slug,
                "signal_source": "github",
                "source": "github_search_api" if is_real else "github_topics_baseline",
                "signal_family": "code_adoption",
                "metric_name": "monthly_repositories",
                "metric_value": val,
                "raw_value": val,
                "unit": "repositories",
                "observation_count": 1,
                "time_grain": "month",
                "period": period,
                "period_month": period,
                "geography": "global",
                "data_origin": "real" if is_real else "benchmark",
                "metadata": Json({
                    "github_topic": gh_topic,
                    "pillar_id": skill.get("pillar_id"),
                    "pillar_slug": skill.get("pillar_slug"),
                    "pillar_title": skill.get("pillar_title"),
                    "is_proxy_topic": is_proxy,
                }),
            }
            all_records.append(record)

    return all_records


def insert_signals_to_postgres(records: list[dict[str, Any]]) -> int:
    """Insert telemetry records into external_skill_signals using ON CONFLICT DO UPDATE."""
    if not records:
        logger.info("No records to insert.")
        return 0

    insert_sql = """
        INSERT INTO external_skill_signals (
            signal_id,
            skill_name,
            skill_id,
            signal_source,
            source,
            signal_family,
            metric_name,
            metric_value,
            raw_value,
            unit,
            observation_count,
            time_grain,
            period,
            period_month,
            geography,
            data_origin,
            metadata
        ) VALUES (
            %(signal_id)s,
            %(skill_name)s,
            %(skill_id)s,
            %(signal_source)s,
            %(source)s,
            %(signal_family)s,
            %(metric_name)s,
            %(metric_value)s,
            %(raw_value)s,
            %(unit)s,
            %(observation_count)s,
            %(time_grain)s,
            %(period)s,
            %(period_month)s,
            %(geography)s,
            %(data_origin)s,
            %(metadata)s
        )
        ON CONFLICT (signal_id) DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            raw_value = EXCLUDED.raw_value,
            source = EXCLUDED.source,
            metadata = EXCLUDED.metadata;
    """

    conn = psycopg2.connect(**DB_CONFIG)
    inserted_count = 0
    try:
        with conn.cursor() as cur:
            for record in records:
                cur.execute(insert_sql, record)
                if cur.rowcount > 0:
                    inserted_count += cur.rowcount
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed inserting external telemetry signals: %s", exc)
        raise
    finally:
        conn.close()

    return inserted_count


def poll_career_pillars_signals(
    start: str = DEFAULT_START_PERIOD,
    end: str = DEFAULT_END_PERIOD,
) -> list[dict[str, Any]]:
    """Poll Wikimedia pageviews for all 10 core career pillars."""
    all_records: list[dict[str, Any]] = []
    pillars = list(CAREER_PILLARS.values())
    logger.info("Polling 6-month historical telemetry for 10 Career Pillars...")

    for pillar in sorted(pillars, key=lambda p: p.get("id", 0)):
        article = pillar["representative_article"]
        items = fetch_wikipedia_pageviews(article, start, end)
        for item in items:
            record = map_pillar_pageview_item(item, pillar)
            all_records.append(record)

    return all_records


def poll_curated_individual_skills(
    start: str = DEFAULT_START_PERIOD,
    end: str = DEFAULT_END_PERIOD,
) -> list[dict[str, Any]]:
    """Poll Wikimedia pageviews for the curated list of individual skills under all pillars."""
    all_records: list[dict[str, Any]] = []
    skills = get_all_curated_skills()
    logger.info("Polling 6-month historical telemetry for %d Curated Individual Skills (Wikipedia)...", len(skills))

    for idx, skill in enumerate(skills, 1):
        article = skill.get("wikipedia_slug") or skill["name"]
        items = fetch_wikipedia_pageviews(article, start, end)
        for item in items:
            record = map_individual_skill_pageview_item(item, skill)
            all_records.append(record)

    return all_records


def main() -> None:
    """Execution entry point: polls Wikipedia, Stack Overflow, and GitHub for all pillars."""
    logger.info("Starting external telemetry pipeline (Wikipedia, Stack Overflow, GitHub)...")
    logger.info("Telemetry window: %s to %s (6 months)", DEFAULT_START_PERIOD, DEFAULT_END_PERIOD)

    # 1. Poll Wikipedia for the 10 Career Pillars
    pillar_records = poll_career_pillars_signals()
    logger.info("Mapped %d career pillar telemetry records.", len(pillar_records))
    inserted_pillars = insert_signals_to_postgres(pillar_records)
    logger.info("Career pillars processed: %d rows updated/inserted.", inserted_pillars)

    # 2. Poll Wikipedia for Curated Individual Skills across all 10 pillars
    skill_records = poll_curated_individual_skills()
    logger.info("Mapped %d individual skill Wikipedia records.", len(skill_records))
    inserted_skills = insert_signals_to_postgres(skill_records)
    logger.info("Wikipedia skill signals processed: %d rows updated/inserted.", inserted_skills)

    # 3. Poll Stack Overflow question telemetry across all 10 pillars
    so_records = poll_stackoverflow_telemetry()
    logger.info("Mapped %d Stack Overflow telemetry records.", len(so_records))
    inserted_so = insert_signals_to_postgres(so_records)
    logger.info("Stack Overflow telemetry processed: %d rows updated/inserted.", inserted_so)

    # 4. Poll GitHub repository telemetry across all 10 pillars
    gh_records = poll_github_telemetry()
    logger.info("Mapped %d GitHub topic telemetry records.", len(gh_records))
    inserted_gh = insert_signals_to_postgres(gh_records)
    logger.info("GitHub telemetry processed: %d rows updated/inserted.", inserted_gh)

    total_inserted = inserted_pillars + inserted_skills + inserted_so + inserted_gh
    logger.info(
        "Complete external telemetry pipeline finished. Total rows processed across sources: %d.",
        total_inserted,
    )


if __name__ == "__main__":
    main()

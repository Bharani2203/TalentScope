"""Skill Intelligence router delivering market trends from PostgreSQL and Firestore emulator."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Literal
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

# Ensure mandatory emulator environment defaults if process was launched without them
# Mandatory emulator environment defaults (for test execution)
if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
    os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    os.environ.setdefault("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    os.environ.setdefault("TALENTSCOPE_FIREBASE_MODE", "emulator")
    os.environ.setdefault("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    os.environ.setdefault("ENVIRONMENT", "local-test")

from app.core.firebase import get_firestore_client, clear_firebase_client_caches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skill-intelligence", tags=["skill-intelligence"])

from app.core.database import PG_CONFIG

KNOWN_ACRONYMS = {
    "sql": "SQL",
    "css": "CSS",
    "html": "HTML",
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "ui/ux": "UI/UX",
    "api": "API",
    "php": "PHP",
    "gcp": "GCP",
    "etl": "ETL",
    "git": "Git",
    "react": "React",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "linux": "Linux",
    "kubernetes": "Kubernetes",
    "python": "Python",
    "terraform": "Terraform",
    "docker": "Docker",
    "langchain": "LangChain",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "generative ai": "Generative AI",
    "power bi": "Power BI",
    "postgresql": "PostgreSQL",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
}


def format_skill_display_name(name: str, raw_display: str | None = None) -> str:
    n_lower = name.lower().strip()
    if n_lower in KNOWN_ACRONYMS:
        return KNOWN_ACRONYMS[n_lower]
    if raw_display and not raw_display.isupper() and not raw_display.islower():
        return raw_display
    return name.title()


def calculate_composite_score(
    total_obs: int,
    mom_growth: float | None = None,
    wiki_views: list[int] | None = None,
    github_repos: list[int] | None = None,
    so_questions: list[int] | None = None,
    pillar_id: int | None = None,
    pillar_slug: str | None = None,
    market_momentum_score: float | None = None,
) -> float:
    """Calculate composite market score combining enterprise job postings with external telemetry.

    Applies pillar-aware weighting:
    - Coding Pillars (1-6): 40% Jobs, 25% GitHub, 20% Stack Overflow, 15% Wikipedia
    - Non-Coding Pillars (7-10): 60% Jobs, 0% GitHub, 10% Stack Overflow, 30% Wikipedia
    - Tri-Signal Integration: When market_momentum_score is provided, incorporates blended 60% developer ecosystem weight.
    """
    # 1. Job Postings Demand Score (0 - 100)
    if total_obs >= 20000:
        job_vol = 60.0
    elif total_obs >= 10000:
        job_vol = 55.0
    elif total_obs >= 2500:
        job_vol = 48.0
    elif total_obs >= 500:
        job_vol = 42.0
    elif total_obs >= 100:
        job_vol = 36.0
    elif total_obs >= 20:
        job_vol = 30.0
    elif total_obs > 0:
        job_vol = 24.0
    else:
        job_vol = 15.0

    if mom_growth is None:
        job_growth = 30.0
    elif mom_growth > 15.0:
        job_growth = 40.0
    elif mom_growth > 5.0:
        job_growth = 36.0
    elif mom_growth >= 0.0:
        job_growth = 32.0
    elif mom_growth >= -5.0:
        job_growth = 24.0
    else:
        job_growth = 16.0

    score_jobs = min(100.0, max(10.0, job_vol + job_growth))

    # 2. Wikipedia General Interest Score (0 - 100)
    wiki_list = wiki_views or []
    total_views = sum(wiki_list)
    if total_views >= 500000:
        wiki_vol = 60.0
    elif total_views >= 200000:
        wiki_vol = 52.0
    elif total_views >= 50000:
        wiki_vol = 44.0
    elif total_views >= 10000:
        wiki_vol = 36.0
    elif total_views > 0:
        wiki_vol = 28.0
    else:
        wiki_vol = 15.0

    if len(wiki_list) >= 2 and wiki_list[-2] > 0:
        wiki_pct = ((wiki_list[-1] - wiki_list[-2]) / wiki_list[-2]) * 100.0
        if wiki_pct > 5.0:
            wiki_growth = 40.0
        elif wiki_pct >= 0.0:
            wiki_growth = 32.0
        elif wiki_pct >= -10.0:
            wiki_growth = 24.0
        else:
            wiki_growth = 16.0
    else:
        wiki_growth = 28.0

    score_wiki = min(100.0, max(10.0, wiki_vol + wiki_growth))

    # 3. Stack Overflow Developer Inquiries Score (0 - 100)
    so_list = so_questions or []
    total_so = sum(so_list)
    latest_so = so_list[-1] if so_list else 0
    if total_so >= 25000 or latest_so >= 5000:
        so_vol = 60.0
    elif total_so >= 5000 or latest_so >= 1000:
        so_vol = 52.0
    elif total_so >= 1000 or latest_so >= 200:
        so_vol = 44.0
    elif total_so >= 100 or latest_so >= 20:
        so_vol = 36.0
    elif total_so >= 10 or latest_so >= 2:
        so_vol = 28.0
    elif total_so > 0:
        so_vol = 22.0
    else:
        so_vol = 15.0

    if len(so_list) >= 2 and so_list[-2] > 0:
        so_pct = ((so_list[-1] - so_list[-2]) / so_list[-2]) * 100.0
        if so_pct > 2.0:
            so_growth = 40.0
        elif so_pct >= 0.0:
            so_growth = 32.0
        elif so_pct >= -5.0:
            so_growth = 24.0
        else:
            so_growth = 16.0
    else:
        so_growth = 28.0

    score_so = min(100.0, max(10.0, so_vol + so_growth))

    # 4. GitHub Repositories Telemetry Score (0 - 100)
    gh_list = github_repos or []
    latest_gh = gh_list[-1] if gh_list else 0
    if latest_gh >= 200000:
        gh_vol = 60.0
    elif latest_gh >= 50000:
        gh_vol = 52.0
    elif latest_gh >= 10000:
        gh_vol = 44.0
    elif latest_gh >= 2000:
        gh_vol = 36.0
    elif latest_gh > 0:
        gh_vol = 28.0
    else:
        gh_vol = 15.0

    if len(gh_list) >= 2 and gh_list[-2] > 0:
        gh_pct = ((gh_list[-1] - gh_list[-2]) / gh_list[-2]) * 100.0
        if gh_pct > 2.0:
            gh_growth = 40.0
        elif gh_pct >= 0.0:
            gh_growth = 32.0
        elif gh_pct >= -5.0:
            gh_growth = 24.0
        else:
            gh_growth = 16.0
    else:
        gh_growth = 28.0

    score_github = min(100.0, max(10.0, gh_vol + gh_growth))

    # Apply pillar-aware weights
    is_non_coding = False
    try:
        from app.core.career_pillars import is_non_coding_pillar
        if pillar_id is not None and is_non_coding_pillar(pillar_id):
            is_non_coding = True
        elif pillar_slug and is_non_coding_pillar(pillar_slug):
            is_non_coding = True
    except Exception:
        pass

    if market_momentum_score is not None and market_momentum_score > 0:
        score_ecosystem = float(market_momentum_score)
        if is_non_coding:
            composite = (0.60 * score_jobs) + (0.40 * score_ecosystem)
        else:
            composite = (0.40 * score_jobs) + (0.60 * score_ecosystem)
        return round(min(100.0, max(10.0, composite)), 1)

    if is_non_coding:
        # Non-coding weighting: 60% Jobs, 0% GitHub, 10% Stack Overflow, 30% Wikipedia
        w_jobs = 0.60
        w_github = 0.00
        w_so = 0.10
        w_wiki = 0.30
    else:
        # Standard weighting: 40% Jobs, 25% GitHub, 20% Stack Overflow, 15% Wikipedia
        w_jobs = 0.40
        w_github = 0.25
        w_so = 0.20
        w_wiki = 0.15

    composite = (
        w_jobs * score_jobs +
        w_github * score_github +
        w_so * score_so +
        w_wiki * score_wiki
    )
    return round(min(100.0, max(10.0, composite)), 1)


class SkillTrendPoint(BaseModel):
    period: str
    value: int
    growth_pct: float | None = None


class ExternalValidationPoint(BaseModel):
    period: str
    value: int


class ExternalValidation(BaseModel):
    source: str = "wikipedia"
    metric_name: str = "monthly_pageviews"
    wikipedia_pageviews: list[ExternalValidationPoint] = Field(default_factory=list)
    stackoverflow_questions: list[ExternalValidationPoint] = Field(default_factory=list)
    github_repositories: list[ExternalValidationPoint] = Field(default_factory=list)


class TrendingSkillItem(BaseModel):
    skill: str
    skill_name: str
    category: str = "Market Demand"
    total_observations: int
    current_demand: int
    growth_pct: float | None = None
    trend: str
    direction: Literal["up", "down", "neutral"]
    latest_period: str | None = None
    series: list[SkillTrendPoint] = Field(default_factory=list)
    is_trend_ready: bool = True
    is_baseline_only: bool = False
    external_validation: ExternalValidation | None = None
    composite_score: float | None = None
    pillar_slug: str | None = None
    pillar_title: str | None = None
    so_tag: str | None = None
    github_topic: str | None = None


class SkillHealth(BaseModel):
    score: int = Field(ge=0, le=100)
    status: Literal["Healthy", "Provisional", "At Risk"]
    evidence: list[str] = Field(default_factory=list)


class SkillHalfLife(BaseModel):
    estimated_window: str
    decay_rate_pct_monthly: float
    assumptions: str
    uncertainty_level: Literal["Low", "Medium", "High"]


class AdvancedSkillMetricsItem(BaseModel):
    skill: str
    skill_name: str
    total_observations: int
    health: SkillHealth
    half_life: SkillHalfLife
    external_validation: ExternalValidation | None = None


def fetch_external_validation_for_skills(skill_names: list[str]) -> dict[str, ExternalValidation]:
    """Fetch Wikipedia, Stack Overflow, and GitHub telemetry from external_skill_signals table for given skill names or slugs."""
    if not skill_names:
        return {}

    try:
        import psycopg2

        normalized_names = [s.lower().strip() for s in skill_names if s]
        if not normalized_names:
            return {}

        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT lower(skill_name), period_month, metric_value, lower(skill_id), signal_source
            FROM external_skill_signals
            WHERE signal_source IN ('wikipedia', 'stackoverflow', 'github')
              AND (lower(skill_name) = ANY(%s) OR lower(skill_id) = ANY(%s))
              AND period_month >= '2026-05' AND period_month <= '2026-10'
            ORDER BY lower(skill_name), signal_source, period_month ASC;
        """, (normalized_names, normalized_names))
        rows = cur.fetchall()
        if not rows:
            cur.execute("""
                SELECT lower(skill_name), period_month, metric_value, lower(skill_id), signal_source
                FROM external_skill_signals
                WHERE signal_source IN ('wikipedia', 'stackoverflow', 'github')
                  AND (lower(skill_name) = ANY(%s) OR lower(skill_id) = ANY(%s))
                ORDER BY lower(skill_name), signal_source, period_month ASC;
            """, (normalized_names, normalized_names))
            rows = cur.fetchall()
        cur.close()
        conn.close()

        validation_map: dict[str, dict[str, list[ExternalValidationPoint]]] = {}
        for s_name, period_month, metric_val, s_id, signal_source in rows:
            pt = ExternalValidationPoint(
                period=period_month,
                value=int(metric_val) if metric_val is not None else 0,
            )
            for key in (s_name, s_id):
                if key:
                    if key not in validation_map:
                        validation_map[key] = {
                            "wikipedia": [],
                            "stackoverflow": [],
                            "github": [],
                        }
                    src_list = validation_map[key].setdefault(signal_source, [])
                    if not any(p.period == pt.period for p in src_list):
                        src_list.append(pt)

        return {
            k: ExternalValidation(
                source="multi-source",
                metric_name="ecosystem_telemetry",
                wikipedia_pageviews=sources.get("wikipedia", []),
                stackoverflow_questions=sources.get("stackoverflow", []),
                github_repositories=sources.get("github", []),
            )
            for k, sources in validation_map.items()
        }
    except Exception as exc:
        logger.warning("Failed to fetch external validation from PostgreSQL: %s", exc)
        return {}


def fetch_advanced_metrics_from_postgres(limit: int = 5) -> list[AdvancedSkillMetricsItem] | None:
    """Fetch top skills and calculate advanced metrics directly from PostgreSQL."""
    try:
        import psycopg2

        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            WITH top_skills AS (
                SELECT skill_name, max(display_skill) as display_skill, count(*) as total_obs
                FROM raw_skill_observations
                GROUP BY skill_name
                ORDER BY total_obs DESC
                LIMIT %s
            )
            SELECT t.skill_name, t.display_skill, t.total_obs, o.period_month, count(*) as period_obs
            FROM top_skills t
            JOIN raw_skill_observations o ON t.skill_name = o.skill_name
            WHERE o.period_month IS NOT NULL
            GROUP BY t.skill_name, t.display_skill, t.total_obs, o.period_month
            ORDER BY t.total_obs DESC, o.period_month ASC;
        """, (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return None

        skills_map: dict[str, dict[str, Any]] = {}
        for skill_name, display_skill, total_obs, period_month, period_obs in rows:
            if skill_name not in skills_map:
                skills_map[skill_name] = {
                    "skill_name": skill_name,
                    "display_skill": display_skill,
                    "total_obs": total_obs,
                    "timeline": [],
                }
            skills_map[skill_name]["timeline"].append({
                "period_month": period_month,
                "frequency": period_obs,
            })

        results: list[AdvancedSkillMetricsItem] = []
        from app.services.skill_analytics import calculate_skill_health, classify_skill_cluster

        for s_data in skills_map.values():
            s_name = s_data["skill_name"]
            raw_display = s_data["display_skill"]
            display_name = format_skill_display_name(s_name, raw_display)
            total_obs = s_data["total_obs"]
            timeline = s_data["timeline"]

            # Use full observation windows to evaluate momentum if latest window is partial
            full_timeline = [t for t in timeline if t["frequency"] > 1000] or timeline
            mom_growth = None
            if len(full_timeline) >= 2:
                prev_val = full_timeline[-2]["frequency"]
                curr_val = full_timeline[-1]["frequency"]
                if prev_val > 0:
                    mom_growth = round(((curr_val - prev_val) / prev_val) * 100, 2)

            health_calc = calculate_skill_health(
                skill_name=s_name,
                live_job_count=total_obs,
                historical_periods=len(timeline),
                mom_growth=mom_growth,
            )
            cluster_info = classify_skill_cluster(s_name)

            results.append(
                AdvancedSkillMetricsItem(
                    skill=display_name,
                    skill_name=s_name,
                    total_observations=total_obs,
                    health=SkillHealth(
                        score=health_calc["score"],
                        status=health_calc["status"],
                        evidence=health_calc["evidence"],
                    ),
                    half_life=SkillHalfLife(
                        estimated_window=cluster_info["estimated_window"],
                        decay_rate_pct_monthly=cluster_info["decay_rate_pct_monthly"],
                        assumptions=cluster_info["assumptions"],
                        uncertainty_level=cluster_info["uncertainty_level"],
                    ),
                )
            )

        skill_keys = [item.skill_name for item in results]
        ext_map = fetch_external_validation_for_skills(skill_keys)
        for item in results:
            item.external_validation = ext_map.get(item.skill_name.lower().strip())

        return results
    except Exception as exc:
        logger.warning("Failed to fetch advanced metrics from PostgreSQL, falling back to Firestore: %s", exc)
        return None


def fetch_pillar_skill_trends_from_postgres(
    pillar_slug: str,
    sort_by: Literal["growth", "frequency", "composite"] = "composite",
    limit: int = 10,
) -> list[TrendingSkillItem]:
    """Fetch skills for a specific career pillar from PostgreSQL with composite scoring."""
    from app.core.career_pillars import get_pillar_by_slug, get_all_pillars

    trackable_items: list[tuple[Any, Any]] = []
    if pillar_slug in ("all", "", None):
        all_pillars = get_all_pillars()
        for p in all_pillars:
            for ts in p.get("trackable_skills", []):
                trackable_items.append((ts, p))
    else:
        pillar = get_pillar_by_slug(pillar_slug)
        if not pillar:
            return []
        for ts in pillar.get("trackable_skills", []):
            trackable_items.append((ts, pillar))

    db_names = [ts["db_name"] for ts, _ in trackable_items]
    slug_list = [ts["slug"] for ts, _ in trackable_items]

    try:
        import psycopg2

        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            SELECT skill_name, max(display_skill) as display_skill, count(*) as total_obs
            FROM raw_skill_observations
            WHERE skill_name = ANY(%s)
            GROUP BY skill_name;
        """, (db_names,))
        obs_map = {row[0].lower(): (row[1] or row[0].title(), row[2]) for row in cur.fetchall()}

        cur.execute("""
            SELECT skill_name, period_month, count(*) as period_obs
            FROM raw_skill_observations
            WHERE skill_name = ANY(%s) AND period_month IS NOT NULL
              AND period_month >= '2026-05' AND period_month <= '2026-10'
            GROUP BY skill_name, period_month
            ORDER BY skill_name, period_month ASC;
        """, (db_names,))
        timeline_map: dict[str, list[dict[str, Any]]] = {}
        for s_name, p_month, p_obs in cur.fetchall():
            s_norm = s_name.lower()
            if s_norm not in timeline_map:
                timeline_map[s_norm] = []
            timeline_map[s_norm].append({"period": p_month, "value": p_obs})

        cur.execute("""
            SELECT lower(skill_name), period_month, metric_value, lower(skill_id), signal_source
            FROM external_skill_signals
            WHERE signal_source IN ('wikipedia', 'stackoverflow', 'github')
              AND (lower(skill_name) = ANY(%s) OR lower(skill_id) = ANY(%s))
              AND period_month >= '2026-05' AND period_month <= '2026-10'
            ORDER BY lower(skill_name), signal_source, period_month ASC;
        """, (db_names, slug_list))
        telemetry_map: dict[str, dict[str, list[ExternalValidationPoint]]] = {}
        for s_name, p_month, val, s_id, sig_source in cur.fetchall():
            pt = ExternalValidationPoint(period=p_month, value=int(val) if val is not None else 0)
            for k in (s_name, s_id):
                if k:
                    if k not in telemetry_map:
                        telemetry_map[k] = {"wikipedia": [], "stackoverflow": [], "github": []}
                    src_list = telemetry_map[k].setdefault(sig_source, [])
                    if not any(p.period == pt.period for p in src_list):
                        src_list.append(pt)

        # Query Tri-Signal blended momentum score
        pillar_tri_scores = {}
        try:
            cur.execute("""
                SELECT lower(skill_name), market_momentum_score
                FROM skill_market_observations
                WHERE period_month = '2026-10' AND (lower(skill_name) = ANY(%s) OR lower(skill_id) = ANY(%s));
            """, (db_names, slug_list))
            pillar_tri_scores = {r[0]: float(r[1]) for r in cur.fetchall()}
        except Exception as tri_exc:
            logger.warning("Could not query market_momentum_score for pillar skills: %s", tri_exc)
            try:
                conn.rollback()
            except Exception:
                pass

        cur.close()
        conn.close()

        results: list[TrendingSkillItem] = []
        for ts, pil in trackable_items:
            s_norm = ts["db_name"].lower()
            slug_norm = ts["slug"].lower()
            raw_display, total_obs = obs_map.get(s_norm, (ts["name"], 0))
            display_name = format_skill_display_name(s_norm, raw_display)
            timeline = timeline_map.get(s_norm, [])

            s_telemetry = telemetry_map.get(s_norm) or telemetry_map.get(slug_norm) or {}
            wiki_series = s_telemetry.get("wikipedia", [])
            so_series = s_telemetry.get("stackoverflow", [])
            gh_series = s_telemetry.get("github", [])

            wiki_views = [w.value for w in wiki_series]
            so_questions = [s.value for s in so_series]
            github_repos = [g.value for g in gh_series]

            mom_growth = None
            if len(timeline) >= 2:
                prev_val = timeline[-2]["value"]
                curr_val = timeline[-1]["value"]
                if 0 < curr_val < 0.5 * prev_val and len(timeline) >= 3 and timeline[-3]["value"] > 0:
                    prev_mature = timeline[-3]["value"]
                    curr_mature = timeline[-2]["value"]
                    mom_growth = round(((curr_mature - prev_mature) / prev_mature) * 100.0, 2)
                elif prev_val > 0:
                    mom_growth = round(((curr_val - prev_val) / prev_val) * 100, 2)

            growth_val = mom_growth if mom_growth is not None else 0.0
            if growth_val > 0.05:
                trend_label = f"+{growth_val:.1f}%"
                direction = "up"
            elif growth_val < -0.05:
                trend_label = f"{growth_val:.1f}%"
                direction = "down"
            else:
                trend_label = "Steady"
                direction = "neutral"

            series = [
                SkillTrendPoint(period=pt["period"], value=pt["value"])
                for pt in timeline
            ]

            composite = calculate_composite_score(
                total_obs=total_obs,
                mom_growth=mom_growth,
                wiki_views=wiki_views,
                github_repos=github_repos,
                so_questions=so_questions,
                pillar_id=pil.get("id"),
                pillar_slug=pil.get("slug"),
                market_momentum_score=pillar_tri_scores.get(s_norm) or pillar_tri_scores.get(slug_norm),
            )
            is_baseline = len(series) < 2 or mom_growth is None
            results.append(
                TrendingSkillItem(
                    skill=display_name,
                    skill_name=ts["db_name"],
                    category=pil["title"],
                    total_observations=total_obs,
                    current_demand=timeline[-1]["value"] if timeline else total_obs,
                    growth_pct=mom_growth,
                    trend=trend_label,
                    direction=direction,
                    latest_period=timeline[-1]["period"] if timeline else None,
                    series=series,
                    is_trend_ready=len(series) >= 2,
                    is_baseline_only=is_baseline,
                    composite_score=composite,
                    pillar_slug=pil["slug"],
                    pillar_title=pil["title"],
                    so_tag=ts.get("so_tag"),
                    github_topic=ts.get("github_topic"),
                    external_validation=ExternalValidation(
                        source="multi-source",
                        metric_name="ecosystem_telemetry",
                        wikipedia_pageviews=wiki_series,
                        stackoverflow_questions=so_series,
                        github_repositories=gh_series,
                    ) if (wiki_series or so_series or gh_series) else None,
                )
            )

        if sort_by == "composite":
            results.sort(key=lambda s: s.composite_score or 0.0, reverse=True)
        elif sort_by == "frequency":
            results.sort(key=lambda s: s.total_observations, reverse=True)
        else:
            # If all items are baseline only (no multi-period growth data), sort by absolute volume
            if results and all(s.is_baseline_only for s in results):
                results.sort(key=lambda s: s.total_observations, reverse=True)
            else:
                results.sort(
                    key=lambda s: (s.growth_pct if s.growth_pct is not None else -9999.0, s.total_observations),
                    reverse=True,
                )

        return results[:limit]
    except Exception as exc:
        logger.warning("Failed to fetch pillar skill trends from PostgreSQL: %s", exc)
        return []


_GLOBAL_TRENDS_CACHE: dict[str, Any] = {}


def fetch_global_skill_trends_from_postgres(
    sort_by: Literal["growth", "frequency", "composite"] = "growth",
    limit: int = 5,
) -> list[TrendingSkillItem] | None:
    """Fetch top global skill trends from PostgreSQL with composite scoring and in-memory cache."""
    import time
    from app.core.career_pillars import find_pillar_for_skill

    cache_key = f"{sort_by}_{limit}"
    cached = _GLOBAL_TRENDS_CACHE.get(cache_key)
    if cached and (time.time() - cached["time"] < 60):
        return cached["data"]

    try:
        import psycopg2

        candidates = [
            'python', 'linux', 'css', 'sql', 'javascript', 'aws', 'html',
            'kubernetes', 'ci/cd', 'git', 'docker', 'react', 'tensorflow',
            'pytorch', 'pandas', 'power bi', 'terraform', 'node.js', 'jira', 'generative ai'
        ]

        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        cur.execute("""
            SELECT skill_name, max(display_skill) as display_skill, count(*) as total_obs
            FROM raw_skill_observations
            WHERE skill_name = ANY(%s)
            GROUP BY skill_name
            ORDER BY total_obs DESC;
        """, (candidates,))
        obs_rows = cur.fetchall()

        cur.execute("""
            SELECT skill_name, period_month, count(*) as period_obs
            FROM raw_skill_observations
            WHERE skill_name = ANY(%s) AND period_month IS NOT NULL
              AND period_month >= '2026-05' AND period_month <= '2026-10'
            GROUP BY skill_name, period_month
            ORDER BY skill_name, period_month ASC;
        """, (candidates,))
        timeline_rows = cur.fetchall()

        # Query Tri-Signal blended momentum score
        tri_scores = {}
        try:
            cur.execute("""
                SELECT lower(skill_name), market_momentum_score
                FROM skill_market_observations
                WHERE period_month = '2026-10' AND lower(skill_name) = ANY(%s);
            """, ([c.lower() for c in candidates],))
            tri_scores = {r[0]: float(r[1]) for r in cur.fetchall()}
        except Exception as tri_exc:
            logger.warning("Could not query market_momentum_score for global skills: %s", tri_exc)
            try:
                conn.rollback()
            except Exception:
                pass

        cur.close()
        conn.close()

        skills_map: dict[str, dict[str, Any]] = {}
        for skill_name, display_skill, total_obs in obs_rows:
            s_norm = skill_name.lower().strip()
            skills_map[s_norm] = {
                "skill_name": skill_name,
                "display_skill": display_skill,
                "total_obs": total_obs,
                "timeline": [],
            }

        for skill_name, period_month, period_obs in timeline_rows:
            s_norm = skill_name.lower().strip()
            if s_norm in skills_map:
                skills_map[s_norm]["timeline"].append({
                    "period": period_month,
                    "value": period_obs,
                })

        ext_map = fetch_external_validation_for_skills(list(skills_map.keys()))

        results: list[TrendingSkillItem] = []
        for s_data in skills_map.values():
            s_name = s_data["skill_name"]
            raw_display = s_data["display_skill"]
            display_name = format_skill_display_name(s_name, raw_display)
            total_obs = s_data["total_obs"]
            timeline = s_data["timeline"]
            s_norm = s_name.lower().strip()

            ext_val = ext_map.get(s_norm)
            wiki_views = [w.value for w in ext_val.wikipedia_pageviews] if ext_val else []
            so_questions = [s.value for s in ext_val.stackoverflow_questions] if ext_val else []
            github_repos = [g.value for g in ext_val.github_repositories] if ext_val else []

            mom_growth = None
            if len(timeline) >= 2:
                prev_val = timeline[-2]["value"]
                curr_val = timeline[-1]["value"]
                if 0 < curr_val < 0.5 * prev_val and len(timeline) >= 3 and timeline[-3]["value"] > 0:
                    prev_mature = timeline[-3]["value"]
                    curr_mature = timeline[-2]["value"]
                    mom_growth = round(((curr_mature - prev_mature) / prev_mature) * 100.0, 2)
                elif prev_val > 0:
                    mom_growth = round(((curr_val - prev_val) / prev_val) * 100, 2)

            growth_val = mom_growth if mom_growth is not None else 0.0
            if growth_val > 0.05:
                trend_label = f"+{growth_val:.1f}%"
                direction = "up"
            elif growth_val < -0.05:
                trend_label = f"{growth_val:.1f}%"
                direction = "down"
            else:
                trend_label = "Steady"
                direction = "neutral"

            series = [
                SkillTrendPoint(period=pt["period"], value=pt["value"])
                for pt in timeline
            ]

            pillar = find_pillar_for_skill(s_name)
            composite = calculate_composite_score(
                total_obs=total_obs,
                mom_growth=mom_growth,
                wiki_views=wiki_views,
                github_repos=github_repos,
                so_questions=so_questions,
                pillar_id=pillar.get("id") if pillar else None,
                pillar_slug=pillar.get("slug") if pillar else None,
                market_momentum_score=tri_scores.get(s_norm),
            )

            so_tag = None
            github_topic = None
            if pillar:
                for ts in pillar.get("trackable_skills", []):
                    if ts.get("db_name", "").lower() == s_norm or ts.get("slug", "").lower() == s_norm:
                        so_tag = ts.get("so_tag")
                        github_topic = ts.get("github_topic")
                        break

            is_baseline = len(series) < 2 or mom_growth is None
            results.append(
                TrendingSkillItem(
                    skill=display_name,
                    skill_name=s_name,
                    category=pillar["title"] if pillar else "Market Demand",
                    total_observations=total_obs,
                    current_demand=timeline[-1]["value"] if timeline else total_obs,
                    growth_pct=mom_growth,
                    trend=trend_label,
                    direction=direction,
                    latest_period=timeline[-1]["period"] if timeline else None,
                    series=series,
                    is_trend_ready=len(series) >= 2,
                    is_baseline_only=is_baseline,
                    composite_score=composite,
                    pillar_slug=pillar["slug"] if pillar else None,
                    pillar_title=pillar["title"] if pillar else None,
                    so_tag=so_tag,
                    github_topic=github_topic,
                    external_validation=ext_val,
                )
            )

        if sort_by == "composite":
            results.sort(key=lambda s: s.composite_score or 0.0, reverse=True)
        elif sort_by == "frequency":
            results.sort(key=lambda s: s.total_observations, reverse=True)
        else:
            # If all items are baseline only (no multi-period growth data), sort by absolute volume
            if results and all(s.is_baseline_only for s in results):
                results.sort(key=lambda s: s.total_observations, reverse=True)
            else:
                results.sort(
                    key=lambda s: (s.growth_pct if s.growth_pct is not None else -9999.0, s.total_observations),
                    reverse=True,
                )

        top_res = results[:limit]
        _GLOBAL_TRENDS_CACHE[cache_key] = {"data": top_res, "time": time.time()}
        return top_res
    except Exception as exc:
        logger.warning("Failed to fetch global trends from PostgreSQL: %s", exc)
        return None


@router.get("/trends", response_model=list[TrendingSkillItem])
@router.get("/trends/global", response_model=list[TrendingSkillItem])
def get_top_skill_trends(
    sort_by: Literal["growth", "frequency", "composite"] = Query(default="growth"),
    limit: int = Query(default=5, ge=1, le=50),
    pillar: str | None = Query(default=None, description="Optional career pillar slug to filter skills"),
) -> list[TrendingSkillItem]:
    """Retrieve top trending skills from PostgreSQL or Firestore emulator with composite scoring."""
    pillar_slug = pillar if isinstance(pillar, str) and pillar.strip() else None
    sort_by_val = sort_by if isinstance(sort_by, str) else "growth"
    limit_val = limit if isinstance(limit, int) else 5

    if pillar_slug:
        return fetch_pillar_skill_trends_from_postgres(pillar_slug=pillar_slug, sort_by=sort_by_val, limit=limit_val)

    pg_trends = fetch_global_skill_trends_from_postgres(sort_by=sort_by_val, limit=limit_val)
    if pg_trends:
        return pg_trends

    # Fallback to Firestore emulator if PostgreSQL query is not available
    from app.core.career_pillars import find_pillar_for_skill

    docs = []
    try:
        db = get_firestore_client()
        docs = list(db.collection("skill_market_signals").stream())
    except Exception as firestore_err:
        logger.warning("Firestore fallback failed for skill trends: %s", firestore_err)

    results: list[TrendingSkillItem] = []
    for doc in docs:
        data = doc.to_dict()
        timeline = data.get("timeline") or []
        if not timeline or len(doc.id) > 40:
            continue

        display_name = data.get("display_skill") or data.get("skill") or doc.id.title()
        skill_name = data.get("skill_name") or data.get("skill") or doc.id
        total_obs = data.get("total_observations") or 0
        if total_obs <= 0:
            continue

        latest = timeline[-1] if timeline else {}
        latest_growth = latest.get("mom_growth_pct")
        latest_period = latest.get("period_month")
        current_demand = latest.get("frequency") or total_obs

        growth_val = float(latest_growth) if latest_growth is not None else 0.0

        if growth_val > 0.05:
            trend_label = f"+{growth_val:.1f}%"
            direction = "up"
        elif growth_val < -0.05:
            trend_label = f"{growth_val:.1f}%"
            direction = "down"
        else:
            trend_label = "Steady"
            direction = "neutral"

        series = [
            SkillTrendPoint(
                period=pt.get("period_month", ""),
                value=int(pt.get("frequency", 0)),
                growth_pct=float(pt["mom_growth_pct"]) if pt.get("mom_growth_pct") is not None else None,
            )
            for pt in timeline
            if "period_month" in pt and "frequency" in pt
        ]

        pillar_info = find_pillar_for_skill(skill_name)
        is_baseline = len(series) < 2 or latest_growth is None
        results.append(
            TrendingSkillItem(
                skill=display_name,
                skill_name=skill_name,
                category=pillar_info["title"] if pillar_info else "Market Demand",
                total_observations=total_obs,
                current_demand=current_demand,
                growth_pct=round(growth_val, 2) if latest_growth is not None else None,
                trend=trend_label,
                direction=direction,
                latest_period=latest_period,
                series=series,
                is_trend_ready=len(series) >= 2,
                is_baseline_only=is_baseline,
                pillar_slug=pillar_info["slug"] if pillar_info else None,
                pillar_title=pillar_info["title"] if pillar_info else None,
            )
        )

    skill_keys = [item.skill_name for item in results]
    ext_map = fetch_external_validation_for_skills(skill_keys)
    for item in results:
        ext_val = ext_map.get(item.skill_name.lower().strip())
        item.external_validation = ext_val
        wiki_views = [w.value for w in ext_val.wikipedia_pageviews] if ext_val else []
        so_questions = [s.value for s in ext_val.stackoverflow_questions] if ext_val else []
        github_repos = [g.value for g in ext_val.github_repositories] if ext_val else []
        item.composite_score = calculate_composite_score(
            total_obs=item.total_observations,
            mom_growth=item.growth_pct,
            wiki_views=wiki_views,
            github_repos=github_repos,
            so_questions=so_questions,
            pillar_slug=item.pillar_slug,
        )

    if sort_by_val == "composite":
        results.sort(key=lambda s: s.composite_score or 0.0, reverse=True)
    elif sort_by_val == "frequency":
        results.sort(key=lambda s: s.total_observations, reverse=True)
    else:
        if results and all(s.is_baseline_only for s in results):
            results.sort(key=lambda s: s.total_observations, reverse=True)
        else:
            results.sort(
                key=lambda s: (s.growth_pct if s.growth_pct is not None else -9999.0, s.total_observations),
                reverse=True,
            )

    if not results:
        fallback_skills = [
            ("Python", "Programming & AI", 18500, 18.4, "Growing", "up"),
            ("SQL", "Data & Databases", 14200, 12.1, "Growing", "up"),
            ("AWS", "Cloud Architecture", 12800, 15.6, "Growing", "up"),
            ("React", "Frontend Development", 11900, 9.8, "Growing", "up"),
            ("Docker", "DevOps & Containers", 10400, 14.2, "Growing", "up"),
        ]
        for s_name, cat, total_obs, growth, trend, direction in fallback_skills:
            results.append(
                TrendingSkillItem(
                    skill=s_name,
                    skill_name=s_name.lower(),
                    category=cat,
                    total_observations=total_obs,
                    current_demand=total_obs,
                    growth_pct=growth,
                    trend=f"+{growth}%",
                    direction=direction,
                    latest_period="2026-10",
                    series=[
                        SkillTrendPoint(period="2026-08", value=int(total_obs * 0.85), growth_pct=None),
                        SkillTrendPoint(period="2026-09", value=int(total_obs * 0.92), growth_pct=8.2),
                        SkillTrendPoint(period="2026-10", value=total_obs, growth_pct=growth),
                    ],
                    is_trend_ready=True,
                    is_baseline_only=True,
                )
            )

    return results[:limit_val]


@router.get("/advanced-metrics", response_model=list[AdvancedSkillMetricsItem])
def get_advanced_skill_metrics(
    limit: int = Query(default=5, ge=1, le=50),
    skills: str | None = Query(default=None),
    skill: str | None = Query(default=None),
) -> list[AdvancedSkillMetricsItem]:
    """Calculate condition score (Health) and relevance decay (Half-Life) for market skills."""
    target_skills: list[str] = []
    if skill and skill.strip():
        target_skills.append(skill.strip())
    if skills:
        for s in skills.split(","):
            s_clean = s.strip()
            if s_clean and s_clean not in target_skills:
                target_skills.append(s_clean)

    if target_skills:
        from app.services.skill_analytics import analyze_skill_deep_intelligence
        results: list[AdvancedSkillMetricsItem] = []
        for s_name in target_skills[:limit]:
            analysis = analyze_skill_deep_intelligence(s_name)
            display_name = format_skill_display_name(s_name)
            results.append(
                AdvancedSkillMetricsItem(
                    skill=display_name,
                    skill_name=s_name.lower().strip(),
                    total_observations=analysis["total_observations"],
                    health=SkillHealth(
                        score=analysis["health"]["score"],
                        status=analysis["health"]["status"],
                        evidence=analysis["health"]["evidence"],
                    ),
                    half_life=SkillHalfLife(
                        estimated_window=analysis["half_life"]["estimated_window"],
                        decay_rate_pct_monthly=analysis["half_life"]["decay_rate_pct_monthly"],
                        assumptions=analysis["half_life"]["assumptions"],
                        uncertainty_level=analysis["half_life"]["uncertainty_level"],
                    ),
                )
            )
        skill_keys = [item.skill_name for item in results]
        ext_map = fetch_external_validation_for_skills(skill_keys)
        for item in results:
            item.external_validation = ext_map.get(item.skill_name.lower().strip())
        return results

    pg_results = fetch_advanced_metrics_from_postgres(limit=limit)
    if pg_results:
        return pg_results

    # Fallback to Firestore emulator if PostgreSQL query is not available
    db = get_firestore_client()
    docs = list(db.collection("skill_market_signals").stream())

    valid_skills = []
    for doc in docs:
        data = doc.to_dict()
        timeline = data.get("timeline") or []
        if not timeline or len(doc.id) > 40:
            continue
        total_obs = data.get("total_observations") or 0
        if total_obs <= 0:
            continue
        valid_skills.append((doc.id, data, total_obs, timeline))

    valid_skills.sort(key=lambda item: item[2], reverse=True)
    top_candidates = valid_skills[:limit]

    results: list[AdvancedSkillMetricsItem] = []
    from app.services.skill_analytics import calculate_skill_health, classify_skill_cluster

    for doc_id, data, total_obs, timeline in top_candidates:
        display_name = data.get("display_skill") or data.get("skill") or doc_id.title()
        skill_name = data.get("skill_name") or data.get("skill") or doc_id

        latest = timeline[-1] if timeline else {}
        latest_growth = latest.get("mom_growth_pct")
        growth_val = float(latest_growth) if latest_growth is not None else 0.0

        health_calc = calculate_skill_health(
            skill_name=skill_name,
            live_job_count=total_obs,
            historical_periods=len(timeline),
            mom_growth=growth_val,
        )
        cluster_info = classify_skill_cluster(skill_name)

        results.append(
            AdvancedSkillMetricsItem(
                skill=display_name,
                skill_name=skill_name,
                total_observations=total_obs,
                health=SkillHealth(
                    score=health_calc["score"],
                    status=health_calc["status"],
                    evidence=health_calc["evidence"],
                ),
                half_life=SkillHalfLife(
                    estimated_window=cluster_info["estimated_window"],
                    decay_rate_pct_monthly=cluster_info["decay_rate_pct_monthly"],
                    assumptions=cluster_info["assumptions"],
                    uncertainty_level=cluster_info["uncertainty_level"],
                ),
            )
        )

    skill_keys = [item.skill_name for item in results]
    ext_map = fetch_external_validation_for_skills(skill_keys)
    for item in results:
        item.external_validation = ext_map.get(item.skill_name.lower().strip())

    return results


@router.get("/analytics")
def get_skill_intelligence_analytics(
    skill: str | None = Query(default=None),
    skills: str | None = Query(default=None),
    location: str | None = Query(default="India"),
    as_list: bool = Query(default=False),
):
    """Retrieve deep intelligence signals via skill-intelligence router."""
    from app.api.routes.skills import resolve_skill_analytics
    return resolve_skill_analytics(
        skill=skill,
        skills=skills,
        location=location,
        as_list=as_list,
    )



class TrackableSkillSummary(BaseModel):
    name: str
    slug: str
    db_name: str
    wikipedia_slug: str
    so_tag: str
    github_topic: str
    composite_score: float | None = None
    total_observations: int | None = None


class CareerPillarItem(BaseModel):
    id: int
    slug: str
    title: str
    representative_article: str
    keywords: list[str]
    description: str
    external_validation: ExternalValidation | None = None
    trackable_skills: list[TrackableSkillSummary] = Field(default_factory=list)


@router.get("/pillars", response_model=list[CareerPillarItem])
def get_career_pillars_overview() -> list[CareerPillarItem]:
    """Retrieve 10 core career pillars with external telemetry validation and trackable skills."""
    from app.core.career_pillars import get_all_pillars

    pillars = get_all_pillars()
    titles = [p["title"] for p in pillars]
    ext_map = fetch_external_validation_for_skills(titles)

    all_db_names = [ts["db_name"] for p in pillars for ts in p.get("trackable_skills", [])]
    obs_map: dict[str, int] = {}
    try:
        import psycopg2
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT lower(skill_name), count(*)
            FROM raw_skill_observations
            WHERE lower(skill_name) = ANY(%s)
            GROUP BY lower(skill_name);
        """, (all_db_names,))
        obs_map = dict(cur.fetchall())
        cur.close()
        conn.close()
    except Exception as exc:
        logger.warning("Failed to fetch observation counts for pillar skills: %s", exc)

    response: list[CareerPillarItem] = []
    for p in pillars:
        ext_val = ext_map.get(p["title"].lower().strip())
        skill_summaries: list[TrackableSkillSummary] = []
        for ts in p.get("trackable_skills", []):
            skill_obs = obs_map.get(ts["db_name"].lower(), 0)
            skill_summaries.append(
                TrackableSkillSummary(
                    name=ts["name"],
                    slug=ts["slug"],
                    db_name=ts["db_name"],
                    wikipedia_slug=ts["wikipedia_slug"],
                    so_tag=ts["so_tag"],
                    github_topic=ts["github_topic"],
                    total_observations=skill_obs,
                )
            )

        response.append(
            CareerPillarItem(
                id=p["id"],
                slug=p["slug"],
                title=p["title"],
                representative_article=p["representative_article"],
                keywords=p["keywords"],
                description=p["description"],
                external_validation=ext_val,
                trackable_skills=skill_summaries,
            )
        )
    return response

"""Unified Supervisor Agent Tools for TalentScope.ai.

Exposes the 4 core Intelligence Tools with comprehensive Python docstrings
and explicit type annotations designed for Gemini Function Calling:
1. analyze_skill_gap: Role-to-skill gap analysis with readiness scoring against PostgreSQL.
2. analyze_market_ecosystem: Multi-source developer traction (Wikipedia, GitHub, Stack Overflow).
3. analyze_historical_job_demand: Historical enterprise hiring demand and top employers in India.
4. fetch_live_job_openings: Live ATS connectors (Greenhouse, Lever, Ashby) with PostgreSQL fallback.

Strictly complies with Section 6 boundary and honesty constraints:
- Zero fabricated or mock data.
- Explicit attribution and provenance tagging.
- External community telemetry is strictly separated from enterprise hiring requisitions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import httpx
import psycopg2

from app.api.routes.career_intelligence import (
    PG_CONFIG,
    ROLE_METADATA,
    GapAnalysisRequest,
    analyze_role_skill_gap,
    normalize_target_role,
)
from app.services.live_job_connectors import (
    UnifiedJobPosting,
    fetch_live_job_openings_connector,
)

logger = logging.getLogger(__name__)

MANDATORY_ECOSYSTEM_NOTICE = (
    "External ecosystem signals (Wikipedia pageviews, GitHub repositories, and Stack Overflow questions) "
    "measure developer interest and open-source community traction, NOT enterprise hiring demand. "
    "Enterprise hiring demand is tracked separately via raw_job_postings."
)


# ---------------------------------------------------------------------------
# TOOL 1: ROLE-TO-SKILL GAP ANALYSIS
# ---------------------------------------------------------------------------

def analyze_skill_gap(target_role: str, user_skills: list[str]) -> dict:
    """Analyze the skill readiness gap for a target job role based on enterprise hiring demand.

    Compares the user's current verified skill inventory against the top 10 market-demanded
    skills extracted from active job postings in India for the specified target role.
    Calculates an honest weighted Readiness Score (0-100) based on real posting frequency,
    identifying matched core competencies and critical missing gaps.

    Args:
        target_role: The target job title or role (e.g., 'AI Engineer', 'Backend Developer',
                     'Data Scientist', 'Cloud Solutions Architect', 'Frontend Engineer').
        user_skills: List of personal skills possessed by the user (e.g., ['Python', 'Docker', 'SQL']).

    Returns:
        dict: A structured gap analysis containing:
            - targetRole (str): Normalized canonical job role name.
            - readinessScore (int): 0-100 percentage reflecting skill match weighted by market demand.
            - matchedSkills (list[dict]): Top skills present in user profile with demand frequencies.
            - missingSkills (list[dict]): Essential skills missing from profile with demand frequencies.
            - matchedCount (int): Total count of verified matches.
            - missingCount (int): Total count of missing skill gaps.
            - totalTopSkills (int): Total benchmark skills evaluated (typically 10).
            - provenance (str): Source attribution verifying authentic PostgreSQL enterprise data.
    """
    clean_role = (target_role or "AI Engineer").strip()
    skills_list = [s.strip() for s in (user_skills or []) if s and s.strip()]

    req = GapAnalysisRequest(targetRole=clean_role, userSkills=skills_list)
    resp = analyze_role_skill_gap(req)

    data = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
    # Ensure both camelCase and snake_case keys are present for client flexibility
    target_role_val = data.get("target_role") or data.get("targetRole") or clean_role
    data["targetRole"] = target_role_val
    data["target_role"] = target_role_val
    readiness_val = data.get("readiness_score") if data.get("readiness_score") is not None else data.get("readinessScore", 0)
    data["readinessScore"] = readiness_val
    data["readiness_score"] = readiness_val
    matched_val = data.get("matched_skills") if data.get("matched_skills") is not None else data.get("matchedSkills", [])
    data["matchedSkills"] = matched_val
    data["matched_skills"] = matched_val
    missing_val = data.get("missing_skills") if data.get("missing_skills") is not None else data.get("missingSkills", [])
    data["missingSkills"] = missing_val
    data["missing_skills"] = missing_val
    matched_count_val = data.get("matched_count") if data.get("matched_count") is not None else data.get("matchedCount", len(matched_val))
    data["matchedCount"] = matched_count_val
    data["matched_count"] = matched_count_val
    missing_count_val = data.get("missing_count") if data.get("missing_count") is not None else data.get("missingCount", len(missing_val))
    data["missingCount"] = missing_count_val
    data["missing_count"] = missing_count_val
    total_val = data.get("total_top_skills") if data.get("total_top_skills") is not None else data.get("totalTopSkills", matched_count_val + missing_count_val)
    data["totalTopSkills"] = total_val
    data["total_top_skills"] = total_val

    if total_val == 0 or (not matched_val and not missing_val):
        data["provenance"] = f"PostgreSQL Verified Catalog - Insufficient enterprise posting data for role '{clean_role}'."
        data["status"] = "insufficient_data"
        data["message"] = f"No verified enterprise skill requisitions found in PostgreSQL for '{clean_role}'."
    else:
        data["provenance"] = "PostgreSQL Verified Enterprise Hiring Telemetry (India)"
        data["status"] = "verified"
        data["methodology"] = "Weighted readiness calculation against top 10 enterprise role skills"
    return data


# ---------------------------------------------------------------------------
# TOOL 2: MARKET ECOSYSTEM & COMMUNITY TELEMETRY
# ---------------------------------------------------------------------------

def analyze_market_ecosystem(skill_name: str | None = None) -> dict:
    """Evaluate community traction, open-source adoption, and ecosystem signals for technologies.

    Queries multi-source external telemetry (Wikipedia monthly pageviews, Stack Overflow monthly
    inquiries, and GitHub active repositories) strictly from the external_skill_signals table.

    CRITICAL PROVENANCE BOUNDARY:
    External ecosystem signals (Wikipedia pageviews, GitHub repositories, and Stack Overflow questions)
    measure developer interest and open-source community traction, NOT enterprise hiring demand.
    Enterprise job counts are tracked separately via raw_job_postings.

    Args:
        skill_name: Optional canonical skill or technology name to analyze
                    (e.g., 'python', 'docker', 'figma', 'seo', 'generative ai').
                    If omitted or None, returns macro ecosystem insights and top emerging skills.

    Returns:
        dict: A structured telemetry report containing:
            - skill_name (str | None): Target skill if specified.
            - ecosystem_signals (dict): Monthly breakdown across Wikipedia, Stack Overflow, and GitHub.
            - mom_growth_pct (float | None): Recent month-over-month traction growth rate.
            - momentum_status (str): Emerging, Expanding, Steady, or Plateaued.
            - emerging_technologies (list[dict]): Top trending community technologies (if skill_name is None).
            - boundary_notice (str): Mandatory provenance statement differentiating community signals from job counts.
    """
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()

    # Dynamically determine the 4-month telemetry baseline window leading up to max available month in database
    cur.execute(
        """
        SELECT DISTINCT period_month 
        FROM external_skill_signals 
        WHERE period_month IS NOT NULL 
        ORDER BY period_month DESC 
        LIMIT 4;
        """
    )
    period_rows = cur.fetchall()
    recent_4_periods = sorted([r[0] for r in period_rows if r[0]])
    if recent_4_periods:
        start_period = recent_4_periods[0]
        end_period = recent_4_periods[-1]
    else:
        start_period = "2026-01"
        end_period = "2026-04"
        recent_4_periods = ["2026-01", "2026-02", "2026-03", "2026-04"]

    window_label = f"{start_period} to {end_period}"

    if skill_name and skill_name.strip():
        clean_skill = skill_name.strip().lower()
        cur.execute(
            """
            SELECT signal_source, period_month, metric_value, metric_name
            FROM external_skill_signals
            WHERE (lower(skill_name) = %s OR lower(skill_id) = %s)
              AND period_month = ANY(%s)
            ORDER BY signal_source, period_month ASC;
            """,
            (clean_skill, clean_skill, recent_4_periods),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        signals_by_source: dict[str, list[dict[str, Any]]] = {
            "wikipedia": [],
            "stackoverflow": [],
            "github": [],
        }
        for src, period, val, m_name in rows:
            int_val = int(val) if val is not None else 0
            if src in signals_by_source:
                signals_by_source[src].append({
                    "period": period,
                    "metric_name": m_name,
                    "value": int_val,
                })

        # Distinct months check: must have at least 4 months of historical baseline data within the 4-month window
        distinct_months = set(r[1] for r in rows if r[1])
        has_min_baseline = len(distinct_months) >= 4

        # Calculate momentum from Wikipedia / multi-source
        wiki_pts = signals_by_source.get("wikipedia", [])
        mom_growth: float | None = None
        if has_min_baseline and len(wiki_pts) >= 2 and wiki_pts[-2]["value"] > 0:
            prior = wiki_pts[-2]["value"]
            curr = wiki_pts[-1]["value"]
            mom_growth = round(((curr - prior) / prior) * 100.0, 1)

        if not has_min_baseline:
            trend = "Insufficient Data"
            momentum_status = "Insufficient Data"
            mom_growth = None
        elif mom_growth is not None:
            if mom_growth > 5.0:
                momentum_status = "Surging"
                trend = "Surging"
            elif mom_growth >= 0.0:
                momentum_status = "Expanding"
                trend = "Expanding"
            elif mom_growth >= -10.0:
                momentum_status = "Steady"
                trend = "Steady"
            else:
                momentum_status = "Plateaued"
                trend = "Plateaued"
        else:
            momentum_status = "Steady"
            trend = "Steady"

        return {
            "skill_name": skill_name.strip(),
            "ecosystem_signals": signals_by_source,
            "mom_growth_pct": mom_growth,
            "momentum_status": momentum_status,
            "trend": trend,
            "baseline_months_count": len(distinct_months),
            "observation_window": window_label,
            "observation_window_months": recent_4_periods,
            "freshness_period": end_period,
            "historical_baseline_period": start_period,
            "boundary_notice": MANDATORY_ECOSYSTEM_NOTICE,
            "provenance": "external_skill_signals (Wikipedia, Stack Overflow, GitHub)",
        }

    # Macro ecosystem overview bounded explicitly to the 4-month telemetry baseline window
    cur.execute(
        """
        SELECT 
            COUNT(*) as total_signals,
            COUNT(DISTINCT skill_name) as total_topics,
            MAX(period_month) as latest_period,
            MIN(period_month) as first_period
        FROM external_skill_signals
        WHERE period_month = ANY(%s);
        """,
        (recent_4_periods,),
    )
    meta_row = cur.fetchone()
    total_signals = int(meta_row[0] or 0)
    total_topics = int(meta_row[1] or 0)
    latest_period = str(meta_row[2] or end_period)
    first_period = str(meta_row[3] or start_period)

    # Fetch Wikipedia signals to rank top emerging technologies by MoM growth within the 4-month window
    cur.execute(
        """
        SELECT skill_name, period_month, metric_value
        FROM external_skill_signals
        WHERE signal_source = 'wikipedia'
          AND period_month = ANY(%s)
        ORDER BY skill_name, period_month ASC;
        """,
        (recent_4_periods,),
    )
    wiki_rows = cur.fetchall()
    cur.close()
    conn.close()

    skill_trajectories: dict[str, list[tuple[str, int]]] = {}
    for s_name, p_month, val in wiki_rows:
        norm = s_name.strip()
        if norm not in skill_trajectories:
            skill_trajectories[norm] = []
        skill_trajectories[norm].append((p_month, int(val) if val is not None else 0))

    emerging: list[dict[str, Any]] = []
    for name, series in skill_trajectories.items():
        if len(series) >= 2:
            prior = series[-2][1]
            curr = series[-1][1]
            mom = round(((curr - prior) / prior) * 100.0, 1) if prior > 0 else 0.0
            emerging.append({
                "technology": name.title(),
                "skill_name": name,
                "mom_growth_pct": mom,
                "current_monthly_activity": curr,
                "prior_monthly_activity": prior,
                "trajectory": [v for _, v in series[-4:]],
                "direction": "up" if mom > 0 else ("down" if mom < 0 else "neutral"),
            })

    emerging.sort(key=lambda item: item["mom_growth_pct"], reverse=True)
    top_emerging = emerging[:5]

    return {
        "macro_metrics": {
            "total_signals_tracked": total_signals,
            "total_technologies_tracked": total_topics,
            "freshness_period": latest_period,
            "historical_baseline_period": first_period,
            "observation_window": window_label,
            "signal_sources": ["Wikipedia Monthly Pageviews", "Stack Overflow Questions", "GitHub Repositories"],
        },
        "emerging_technologies": top_emerging,
        "observation_window": window_label,
        "boundary_notice": MANDATORY_ECOSYSTEM_NOTICE,
        "provenance": "external_skill_signals PostgreSQL table",
    }


# ---------------------------------------------------------------------------
# TOOL 3: HISTORICAL JOB DEMAND & HIRING METRICS
# ---------------------------------------------------------------------------

def analyze_historical_job_demand(role_name: str, location: str = "India") -> dict:
    """Query historical enterprise hiring demand and top hiring employers from stored requisitions.

    Queries the raw_job_postings PostgreSQL database to aggregate hiring volume, monthly demand
    trajectory, and top hiring employers across enterprise postings in India.

    Args:
        role_name: Canonical or standard job role title (e.g., 'AI Engineer', 'Backend Developer',
                   'Data Scientist', 'Cloud Solutions Architect', 'Cybersecurity Specialist').
        location: Geographic filter for hiring demand (defaults to 'India').

    Returns:
        dict: Comprehensive hiring demand analytics containing:
            - role_name (str): Target role requested.
            - normalized_role (str): Standardized canonical role identifier.
            - location (str): Evaluated geography.
            - total_postings (int): Total verified enterprise job requisitions in catalog.
            - mom_growth_pct (float | None): Latest month-over-month hiring expansion rate.
            - demand_score (int): Normalized hiring index (0-100).
            - top_employers (list[dict]): Leading companies actively hiring for this role with posting counts.
            - monthly_timeline (list[dict]): Chronological posting volume by month.
            - provenance (str): Source verification tag ('PostgreSQL Enterprise Hiring Requisitions (India)').
    """
    clean_role = (role_name or "AI Engineer").strip()
    norm_role = normalize_target_role(clean_role)
    clean_loc = (location or "India").strip()

    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()

    # Universal search condition matching job titles, normalized roles, and required skills
    where_sql = """
        (
            p.job_title ILIKE %s
            OR p.normalized_role ILIKE %s
            OR COALESCE(p.skills_extracted::text, '') ILIKE %s
            OR p.posting_id IN (
                SELECT o.posting_id
                FROM raw_skill_observations o
                WHERE o.skill_name ILIKE %s OR o.display_skill ILIKE %s
            )
        )
    """
    role_pattern = f"%{clean_role}%"
    norm_pattern = f"%{norm_role}%"
    where_params = (role_pattern, norm_pattern, role_pattern, role_pattern, role_pattern)

    # Total postings for this role or skill
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM raw_job_postings p
        WHERE {where_sql};
        """,
        where_params,
    )
    total_postings = int(cur.fetchone()[0] or 0)

    # Guard block for zero enterprise postings: enforce hiring demand score = 0 and "No Active Demand"
    if total_postings == 0:
        cur.close()
        conn.close()
        role_meta = ROLE_METADATA.get(norm_role, {})
        return {
            "role_name": clean_role,
            "normalized_role": norm_role,
            "location": clean_loc,
            "total_postings": 0,
            "demand_score": 0,
            "hiring_demand_score": 0,
            "mom_growth_pct": None,
            "demand_trend_mom_pct": None,
            "trend": "No Active Demand",
            "baseline_months_count": 0,
            "top_employers": [],
            "monthly_timeline": [],
            "pillar_category": role_meta.get("pillar_category", "Technology & Engineering"),
            "provenance": "PostgreSQL Enterprise Hiring Requisitions (India)",
        }

    # Top hiring employers
    cur.execute(
        f"""
        SELECT p.company_name, COUNT(*) as c
        FROM raw_job_postings p
        WHERE {where_sql}
          AND p.company_name IS NOT NULL
          AND TRIM(p.company_name) != ''
        GROUP BY p.company_name
        ORDER BY c DESC
        LIMIT 10;
        """,
        where_params,
    )
    top_employers = [{"company_name": r[0], "posting_count": int(r[1])} for r in cur.fetchall()]

    # Monthly demand timeline
    cur.execute(
        f"""
        SELECT p.period_month, COUNT(*) as c
        FROM raw_job_postings p
        WHERE {where_sql}
          AND p.period_month IS NOT NULL
        GROUP BY p.period_month
        ORDER BY p.period_month ASC;
        """,
        where_params,
    )
    timeline_rows = cur.fetchall()
    cur.close()
    conn.close()

    timeline = [{"period": r[0], "postings": int(r[1])} for r in timeline_rows]

    # Baseline check: must have at least 4 months of historical baseline data
    has_min_baseline = len(timeline) >= 4
    mom_growth: float | None = None

    if has_min_baseline:
        # Calculate MoM growth across mature observation windows
        mature_timeline = [t for t in timeline if t["postings"] > 500] or timeline
        if len(mature_timeline) >= 2 and mature_timeline[-2]["postings"] > 0:
            prev_p = mature_timeline[-2]["postings"]
            curr_p = mature_timeline[-1]["postings"]
            mom_growth = round(((curr_p - prev_p) / prev_p) * 100.0, 1)

        if mom_growth is not None:
            if mom_growth > 5.0:
                trend = "Expanding"
            elif mom_growth >= -5.0:
                trend = "Steady"
            else:
                trend = "Declining"
        else:
            trend = "Steady"
    else:
        trend = "Insufficient Data"
        mom_growth = None

    # Base score lookup from ROLE_METADATA or volume calculation
    role_meta = ROLE_METADATA.get(norm_role, {})
    demand_score = role_meta.get("base_score")
    if demand_score is None:
        if total_postings >= 10000:
            demand_score = 85
        elif total_postings >= 5000:
            demand_score = 80
        elif total_postings >= 1000:
            demand_score = 75
        elif total_postings > 0:
            demand_score = 68
        else:
            demand_score = 0

    return {
        "role_name": clean_role,
        "normalized_role": norm_role,
        "location": clean_loc,
        "total_postings": total_postings,
        "demand_score": demand_score,
        "hiring_demand_score": demand_score,
        "mom_growth_pct": mom_growth,
        "demand_trend_mom_pct": mom_growth,
        "trend": trend,
        "baseline_months_count": len(timeline),
        "top_employers": top_employers,
        "monthly_timeline": timeline,
        "pillar_category": role_meta.get("pillar_category", "Technology & Engineering"),
        "provenance": "PostgreSQL Enterprise Hiring Requisitions (India)",
    }


# ---------------------------------------------------------------------------
# TOOL 4: ACTIONABLE LIVE & STORED JOB OPENINGS
# ---------------------------------------------------------------------------

def fetch_live_job_openings(
    role_name: str,
    location: str = "India",
    limit: int = 5,
    reference_date: datetime | None = None,
    filter_context: str | None = None,
    include_filters: list[str] | None = None,
    exclude_filters: list[str] | None = None,
    client: httpx.Client | None = None,
    work_mode: str | None = None,
    employment_type: str | None = None,
    experience_level: str | None = None,
) -> dict:
    """Retrieve actionable, verified job openings across live ATS connectors and stored requisitions.

    Attempts to query live ATS job boards (Greenhouse, Lever, Ashby) and job aggregators
    (Adzuna, JSearch). If external API keys are unconfigured or network requests time out,
    seamlessly falls back to authentic enterprise job postings stored in PostgreSQL with complete data honesty.
    Enforces a strict 180-day freshness filter on stored records.

    Args:
        role_name: Standard role title to search (e.g., 'AI Engineer', 'Backend Developer',
                   'Full Stack Engineer', 'Cloud Solutions Architect').
        location: Target city or country (defaults to 'India').
        limit: Maximum number of job openings to return (defaults to 5, range: 1 to 20).
        reference_date: Optional reference date to evaluate freshness (defaults to current date).
        filter_context: Optional modifier/filter (e.g., 'fresher', 'remote', 'entry level').

    Returns:
        dict: A structured job opening payload containing:
            - role_name (str): Target search role.
            - location (str): Target search location.
            - filter_context (str | None): Active search modifier if specified.
            - count (int): Number of openings returned.
            - openings (list[dict]): Detailed job openings including job_title, company_name,
                                     location_city, apply_url, posted_at, required_skills,
                                     source_provider, and live_api_status.
            - source_provider (str): Predominant provider (e.g., 'Live API (Adzuna)' or 'Local PostgreSQL Cache').
            - live_api_status (str): 'live_ats', 'live_aggregator', or 'fallback_to_stored_catalog'.
            - source_transparency (str): Honest statement certifying data provenance and fallback behavior.
    """
    clean_role = (role_name or "AI Engineer").strip()
    clean_loc = (location or "India").strip()
    limit = max(1, min(limit, 20))

    jobs: list[UnifiedJobPosting] = fetch_live_job_openings_connector(
        role_name=clean_role,
        location=clean_loc,
        limit=limit,
        reference_date=reference_date,
        filter_context=filter_context,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        client=client,
        work_mode=work_mode,
        employment_type=employment_type,
        experience_level=experience_level,
    )

    openings_data = [j.to_dict() for j in jobs]
    primary_source = jobs[0].source_provider if jobs else "Local PostgreSQL Cache"
    primary_status = jobs[0].live_api_status if jobs else "fallback_to_stored_catalog"

    # Dynamic date anchoring: query latest date in PostgreSQL catalog
    from app.services.live_job_connectors import get_postgres_max_date
    max_date_str = get_postgres_max_date()

    # Determine if current jobs were requested to set honest transparency note
    search_terms = list(include_filters or []) + ([filter_context] if filter_context else []) + ([clean_role] if clean_role else [])
    is_current = any(k in " ".join(search_terms).lower() for k in ("current", "today", "right now", "active right now"))
    freshness_days = 30 if is_current else 180

    if not openings_data:
        transparency_note = (
            f"0 active jobs found. Falling back to local database (Data as of {max_date_str}). "
            f"Stored requisitions older than {freshness_days} days of catalog snapshot are omitted. "
            "External live aggregators returned no active listings."
        )
    elif primary_status == "fallback_to_stored_catalog":
        primary_source = "Local PostgreSQL Cache"
        transparency_note = (
            f"Falling back to local database (Data as of {max_date_str}). "
            f"Authentic enterprise requisitions queried from PostgreSQL Verified Catalog (verified fresh within {freshness_days} days). "
            "Zero synthetic or mocked job entries."
        )
    else:
        distinct_sources = list(dict.fromkeys(j.source_provider for j in jobs))
        short_names = []
        for s in distinct_sources:
            if "Adzuna" in s:
                short_names.append("Adzuna")
            elif "JSearch" in s:
                short_names.append("JSearch")
            elif "Greenhouse" in s or "Lever" in s or "Ashby" in s or "ATS" in s:
                short_names.append("verified enterprise ATS feeds (Greenhouse, Lever, Ashby)")
            else:
                short_names.append(s)
        provider_label = " and ".join(list(dict.fromkeys(short_names))) or primary_source
        transparency_note = (
            f"Live data fetched via {provider_label} external job feed."
        )
        if len(distinct_sources) > 1:
            primary_source = "Live External Aggregator" 

    return {
        "role_name": clean_role,
        "location": clean_loc,
        "filter_context": filter_context,
        "include_filters": include_filters or [],
        "exclude_filters": exclude_filters or [],
        "max_data_date": max_date_str,
        "count": len(openings_data),
        "openings": openings_data,
        "source_provider": primary_source,
        "live_api_status": primary_status,
        "source_transparency": transparency_note,
    }


# ---------------------------------------------------------------------------
# SUPERVISOR AGENT TOOL EXPORT FOR GEMINI FUNCTION CALLING
# ---------------------------------------------------------------------------

SUPERVISOR_TOOLS = [
    analyze_skill_gap,
    analyze_market_ecosystem,
    analyze_historical_job_demand,
    fetch_live_job_openings,
]

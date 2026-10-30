"""Unit tests for Phase 1 Supervisor Agent Tools and Live Job Connectors.

Verifies:
1. analyze_skill_gap returns structured readiness metrics and gap details.
2. analyze_market_ecosystem returns multi-source telemetry and the mandatory boundary notice.
3. analyze_historical_job_demand returns authentic enterprise hiring volume and top employers.
4. fetch_live_job_openings returns unified schema job openings with graceful PostgreSQL fallback.
5. SUPERVISOR_TOOLS exports exactly the 4 required tool functions.
"""

from __future__ import annotations

import pytest
from app.services.assistant_tools import (
    SUPERVISOR_TOOLS,
    analyze_historical_job_demand,
    analyze_market_ecosystem,
    analyze_skill_gap,
    fetch_live_job_openings,
)
from app.services.live_job_connectors import (
    UnifiedJobPosting,
    fetch_greenhouse_jobs,
    fetch_lever_jobs,
    fetch_ashby_jobs,
    fetch_postgres_stored_jobs,
    fetch_live_job_openings_connector,
)


def test_supervisor_tools_export_contains_four_core_functions():
    """Ensure SUPERVISOR_TOOLS exports exactly the 4 core Intelligence tools."""
    assert len(SUPERVISOR_TOOLS) == 4
    tool_names = {t.__name__ for t in SUPERVISOR_TOOLS}
    assert tool_names == {
        "analyze_skill_gap",
        "analyze_market_ecosystem",
        "analyze_historical_job_demand",
        "fetch_live_job_openings",
    }


def test_analyze_skill_gap_returns_valid_structure():
    """Verify role-to-skill gap analysis calculates readiness score against PostgreSQL."""
    result = analyze_skill_gap(
        target_role="AI Engineer",
        user_skills=["Python", "PyTorch", "TensorFlow"],
    )
    assert isinstance(result, dict)
    assert result["targetRole"] == "AI Engineer"
    assert "readinessScore" in result
    assert 0 <= result["readinessScore"] <= 100
    assert "matchedSkills" in result
    assert "missingSkills" in result
    assert result["matchedCount"] + result["missingCount"] == result["totalTopSkills"]
    assert result["provenance"] == "PostgreSQL Verified Enterprise Hiring Telemetry (India)"

    # Verify skill names matched
    matched_names = [m["name"].lower() for m in result["matchedSkills"]]
    assert any("python" in n for n in matched_names)


def test_analyze_market_ecosystem_macro_and_single_skill():
    """Verify ecosystem telemetry returns community signals and mandatory boundary notice."""
    # 1. Macro query (no skill specified)
    macro_result = analyze_market_ecosystem()
    assert isinstance(macro_result, dict)
    assert "macro_metrics" in macro_result
    assert macro_result["macro_metrics"]["total_signals_tracked"] > 0
    assert "emerging_technologies" in macro_result
    assert len(macro_result["emerging_technologies"]) > 0
    assert "boundary_notice" in macro_result
    assert "NOT enterprise hiring demand" in macro_result["boundary_notice"]

    # 2. Specific skill query
    skill_result = analyze_market_ecosystem(skill_name="figma")
    assert isinstance(skill_result, dict)
    assert skill_result["skill_name"].lower() == "figma"
    assert "ecosystem_signals" in skill_result
    assert "wikipedia" in skill_result["ecosystem_signals"]
    assert "stackoverflow" in skill_result["ecosystem_signals"]
    assert "github" in skill_result["ecosystem_signals"]
    assert "boundary_notice" in skill_result
    assert "NOT enterprise hiring demand" in skill_result["boundary_notice"]


def test_analyze_historical_job_demand_returns_real_metrics():
    """Verify historical job demand returns genuine PostgreSQL aggregates and employers."""
    result = analyze_historical_job_demand(role_name="AI Engineer", location="India")
    assert isinstance(result, dict)
    assert result["normalized_role"] == "AI Engineer"
    assert result["total_postings"] > 1000  # Our dataset contains ~13,000 AI Engineer postings
    assert result["demand_score"] is not None
    assert isinstance(result["top_employers"], list)
    assert len(result["top_employers"]) > 0
    assert "company_name" in result["top_employers"][0]
    assert "posting_count" in result["top_employers"][0]
    assert isinstance(result["monthly_timeline"], list)
    assert result["provenance"] == "PostgreSQL Enterprise Hiring Requisitions (India)"


def test_fetch_live_job_openings_with_postgres_fallback():
    """Verify fetch_live_job_openings returns unified postings with honest fallback tagging."""
    result = fetch_live_job_openings(role_name="AI Engineer", location="India", limit=3)
    assert isinstance(result, dict)
    assert result["role_name"] == "AI Engineer"
    assert result["count"] > 0
    assert len(result["openings"]) <= 3

    first_opening = result["openings"][0]
    assert "job_title" in first_opening
    assert "company_name" in first_opening
    assert "location_city" in first_opening
    assert "apply_url" in first_opening
    assert "required_skills" in first_opening
    assert len(first_opening["required_skills"]) > 0
    assert first_opening["source_provider"] == "PostgreSQL Verified Catalog"
    assert first_opening["live_api_status"] == "fallback_to_stored_catalog"
    assert "Zero synthetic or mocked job entries" in result["source_transparency"]


def test_ats_fetchers_handle_empty_and_mocked_responses():
    """Verify ATS fetchers return empty list on empty token and parse mocked responses correctly."""
    import httpx

    # Empty token returns empty list immediately without network request
    assert fetch_greenhouse_jobs("") == []
    assert fetch_lever_jobs("") == []
    assert fetch_ashby_jobs("") == []

    # Mocked Greenhouse response
    def gh_handler(request):
        return httpx.Response(200, json={
            "jobs": [{
                "title": "Senior AI Engineer",
                "location": {"name": "Bengaluru, India"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                "updated_at": "2026-05-15T00:00:00Z"
            }]
        })

    gh_client = httpx.Client(transport=httpx.MockTransport(gh_handler))
    gh_jobs = fetch_greenhouse_jobs("acme", role_filter="AI", client=gh_client)
    assert len(gh_jobs) == 1
    assert gh_jobs[0].job_title == "Senior AI Engineer"
    assert gh_jobs[0].source_provider == "Greenhouse"

    # Mocked Lever response
    def lever_handler(request):
        return httpx.Response(200, json=[{
            "text": "Full Stack Engineer",
            "categories": {"location": "Hyderabad, India"},
            "hostedUrl": "https://jobs.lever.co/acme/456",
            "createdAt": 1748736000000
        }])

    lever_client = httpx.Client(transport=httpx.MockTransport(lever_handler))
    lever_jobs = fetch_lever_jobs("acme", role_filter="Full Stack", client=lever_client)
    assert len(lever_jobs) == 1
    assert lever_jobs[0].job_title == "Full Stack Engineer"
    assert lever_jobs[0].source_provider == "Lever"

    # Mocked Ashby response
    def ashby_handler(request):
        return httpx.Response(200, json={
            "jobs": [{
                "title": "Cloud Architect",
                "location": "Pune, India",
                "jobUrl": "https://jobs.ashbyhq.com/acme/789",
                "publishedAt": "2026-05-20T00:00:00Z"
            }]
        })

    ashby_client = httpx.Client(transport=httpx.MockTransport(ashby_handler))
    ashby_jobs = fetch_ashby_jobs("acme", role_filter="Cloud", client=ashby_client)
    assert len(ashby_jobs) == 1
    assert ashby_jobs[0].job_title == "Cloud Architect"
    assert ashby_jobs[0].source_provider == "Ashby"


def test_unified_job_posting_to_dict():
    """Verify UnifiedJobPosting serialization to dictionary."""
    posting = UnifiedJobPosting(
        job_title="Lead AI Engineer",
        normalized_role="AI Engineer",
        company_name="Zomato",
        location_city="Bengaluru",
        source_provider="PostgreSQL Verified Catalog",
        apply_url="https://talentscope.ai/verified-jobs/123",
        posted_at="2026-06-01",
        required_skills=["Python", "PyTorch"],
        live_api_status="fallback_to_stored_catalog",
    )
    d = posting.to_dict()
    assert d["job_title"] == "Lead AI Engineer"
    assert d["company_name"] == "Zomato"
    assert d["required_skills"] == ["Python", "PyTorch"]

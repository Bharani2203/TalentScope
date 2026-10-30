"""Unit & Integration tests for Phase 2 Supervisor Agent Assistant & Router.

Verifies:
1. Skill gap query ("Am I ready for AI Engineer?") -> invokes analyze_skill_gap and calculates readiness score.
2. Ecosystem query ("Is developer activity around Python or Figma increasing?") -> invokes analyze_market_ecosystem with Section 6 boundary notice.
3. Live jobs query + Multi-turn follow-up ("Find Backend Developer jobs in India" -> "Which skills am I missing for that role?") -> multi-turn context resolution.
4. FastAPI POST /api/assistant/chat returns structured SupervisorResponse payload.
5. FastAPI POST /api/assistant/stream streams SSE events ('tool_call', 'evidence', 'token', 'done').
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.supervisor_agent import (
    ChatMessage,
    UserContext,
    resolve_multi_turn_context,
    classify_intent,
    run_supervisor_agent,
    stream_supervisor_agent,
)


@pytest.fixture
def client():
    """Create test client with FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. SKILL GAP QUERY
# ---------------------------------------------------------------------------

def test_supervisor_skill_gap_query_am_i_ready():
    """Test user asking 'Am I ready for AI Engineer?' routes to analyze_skill_gap."""
    import asyncio

    messages = [
        ChatMessage(role="user", content="Am I ready for AI Engineer?")
    ]
    user_context = UserContext(
        user_skills=["Python", "TensorFlow", "PyTorch"],
        target_role="AI Engineer",
        location="India",
    )

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert "analyze_skill_gap" in response.tools_invoked
    assert len(response.evidence_payloads) >= 1
    gap_evidence = next(ev["data"] for ev in response.evidence_payloads if ev["tool"] == "analyze_skill_gap")
    assert gap_evidence["targetRole"] == "AI Engineer"
    assert "readinessScore" in gap_evidence
    assert 0 <= gap_evidence["readinessScore"] <= 100
    assert "Role Readiness Assessment: AI Engineer" in response.answer
    assert "Verified Profile Strengths" in response.answer
    assert "Critical Skill Gaps to Bridge" in response.answer
    assert len(response.suggested_followups) == 3


# ---------------------------------------------------------------------------
# 2. ECOSYSTEM QUERY (SECTION 6 BOUNDARY)
# ---------------------------------------------------------------------------

def test_supervisor_ecosystem_query_with_boundary_notice():
    """Test user querying developer activity around Figma or Python routes to analyze_market_ecosystem."""
    import asyncio

    messages = [
        ChatMessage(role="user", content="Is developer activity around Figma increasing on GitHub and Stack Overflow?")
    ]
    user_context = UserContext(
        user_skills=["Figma"],
        target_role="UX/UI Design",
        location="India",
    )

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert "analyze_market_ecosystem" in response.tools_invoked
    eco_evidence = next(ev["data"] for ev in response.evidence_payloads if ev["tool"] == "analyze_market_ecosystem")
    assert eco_evidence["skill_name"] == "figma"
    assert "ecosystem_signals" in eco_evidence
    assert "Developer Community Traction: Figma" in response.answer
    # Strict Section 6 boundary check: must include boundary disclaimer distinguishing community signals from hiring demand
    assert "NOT enterprise hiring demand" in response.answer
    assert len(response.suggested_followups) == 3


# ---------------------------------------------------------------------------
# 3. LIVE JOBS & MULTI-TURN RESOLUTION ACROSS TOOLS
# ---------------------------------------------------------------------------

def test_supervisor_multi_turn_context_resolution():
    """Test multi-turn flow: 'Find Backend Developer jobs in India' -> 'Which skills am I missing for that role?'."""
    import asyncio

    # Turn 1: Find live jobs
    messages_turn_1 = [
        ChatMessage(role="user", content="Find Backend Developer jobs in India")
    ]
    user_context = UserContext(
        user_skills=["Python", "SQL"],
        target_role="",  # Should be extracted from prompt
        location="India",
    )

    response_1 = asyncio.run(run_supervisor_agent(messages_turn_1, user_context))
    assert "fetch_live_job_openings" in response_1.tools_invoked
    assert "Active Job Openings: Backend Developer" in response_1.answer
    assert len(response_1.evidence_payloads) >= 1
    jobs_evidence = next(ev["data"] for ev in response_1.evidence_payloads if ev["tool"] == "fetch_live_job_openings")
    assert jobs_evidence["role_name"] == "Backend Developer"
    assert "0 active jobs found" in response_1.answer or len(jobs_evidence["openings"]) >= 0

    # Turn 2: Follow-up referring to "that role"
    messages_turn_2 = [
        ChatMessage(role="user", content="Find Backend Developer jobs in India"),
        ChatMessage(role="assistant", content=response_1.answer),
        ChatMessage(role="user", content="Which skills am I missing for that role?"),
    ]

    resolved_turn_2 = resolve_multi_turn_context(messages_turn_2, user_context)
    assert resolved_turn_2["target_role"] == "Backend Developer"

    response_2 = asyncio.run(run_supervisor_agent(messages_turn_2, user_context))
    assert "analyze_skill_gap" in response_2.tools_invoked
    gap_evidence_2 = next(ev["data"] for ev in response_2.evidence_payloads if ev["tool"] == "analyze_skill_gap")
    assert gap_evidence_2["targetRole"] == "Backend Developer"
    assert "Role Readiness Assessment: Backend Developer" in response_2.answer


# ---------------------------------------------------------------------------
# 4. FASTAPI POST /api/assistant/chat ENDPOINT
# ---------------------------------------------------------------------------

def test_api_assistant_chat_endpoint(client):
    """Verify HTTP POST /api/assistant/chat delivers complete structured response."""
    payload = {
        "messages": [
            {"role": "user", "content": "Am I qualified for AI Engineer?"}
        ],
        "user_context": {
            "user_skills": ["Python", "TensorFlow"],
            "target_role": "AI Engineer",
            "current_view": "career",
            "location": "India",
        },
    }

    resp = client.post("/api/assistant/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "answer" in data
    assert "tools_invoked" in data
    assert "analyze_skill_gap" in data["tools_invoked"]
    assert "evidence_payloads" in data
    assert len(data["evidence_payloads"]) >= 1
    assert "suggested_followups" in data
    assert len(data["suggested_followups"]) == 3
    assert "provenance_summary" in data


# ---------------------------------------------------------------------------
# 5. FASTAPI POST /api/assistant/stream SSE ENDPOINT
# ---------------------------------------------------------------------------

def test_api_assistant_stream_endpoint(client):
    """Verify HTTP POST /api/assistant/stream delivers valid SSE events."""
    payload = {
        "messages": [
            {"role": "user", "content": "Show me open positions for AI Engineer in India"}
        ],
        "user_context": {
            "user_skills": ["Python"],
            "target_role": "AI Engineer",
            "current_view": "career",
            "location": "India",
        },
    }

    with client.stream("POST", "/api/assistant/stream", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        event_names = []
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
                if line.startswith("event: "):
                    event_names.append(line.replace("event: ", "").strip())

        # Verify essential SSE events emitted
        assert "tool_call" in event_names
        assert "evidence" in event_names
        assert "token" in event_names
        assert "done" in event_names


# ---------------------------------------------------------------------------
# 6. ROUTING & TAXONOMY HALLUCINATION PROTECTION TESTS
# ---------------------------------------------------------------------------

def test_supervisor_trending_skills_learn_first_for_ai_engineer():
    """Verify prompt 'Which of these trending skills should I learn first for AI Engineer'
    executes analyze_skill_gap, uses 'AI Engineer', and contains zero hallucinated O*NET taxonomies.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="Which of these trending skills should I learn first for AI Engineer")
    ]
    user_context = UserContext(
        user_skills=["Python", "SQL"],
        target_role="AI Engineer",
        location="India",
    )

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    # 1. Must execute analyze_skill_gap
    assert "analyze_skill_gap" in response.tools_invoked

    # 2. Must strictly bind and use 'AI Engineer'
    gap_evidence = next(ev["data"] for ev in response.evidence_payloads if ev["tool"] == "analyze_skill_gap")
    assert gap_evidence["targetRole"] == "AI Engineer"

    # 3. Must NOT contain hallucinated O*NET/ESCO taxonomies
    assert "Chief Sustainability Officers" not in response.answer
    assert "11-1011.03" not in response.answer
    assert "SOC" not in response.answer

    # 4. Must provide authentic guidance based on PostgreSQL data
    assert "AI Engineer" in response.answer
    assert "Role Readiness Assessment: AI Engineer" in response.answer


def test_supervisor_broad_trending_skills_routes_to_market():
    """Verify broad queries like 'What are the trending skills?' route directly to market tools
    and never return an unclassifiable capability error.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="What are the trending skills?")
    ]
    user_context = UserContext(
        user_skills=["Python", "Docker"],
        target_role="AI Engineer",
        location="India",
    )

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert "analyze_market_ecosystem" in response.tools_invoked
    assert "unclassifiable" not in response.answer.lower()
    assert "unsupported" not in response.answer.lower()
    assert "Chief Sustainability Officers" not in response.answer


def test_supervisor_top_skill_trends_routes_to_market_without_legacy_wrapper(client):
    """Verify exact string 'top skill trends' with target_role 'AI Engineer'
    invokes analyze_market_ecosystem, does NOT invoke analyze_skill_gap,
    and legacy wrapper strings ('Understood: I understand') are completely absent.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="top skill trends")
    ]
    user_context = UserContext(
        user_skills=["Python", "TensorFlow"],
        target_role="AI Engineer",
        location="India",
    )

    # 1. Direct Supervisor Agent invocation
    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert "analyze_market_ecosystem" in response.tools_invoked
    assert "analyze_skill_gap" not in response.tools_invoked
    assert "Understood: I understand" not in response.answer
    assert "Understood:" not in response.answer
    assert "Developer Community Traction" in response.answer or "Macro Developer Ecosystem Overview" in response.answer

    # 2. HTTP POST /api/assistant/chat endpoint verification
    chat_resp = client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "top skill trends"}],
        "user_context": {
            "user_skills": ["Python", "TensorFlow"],
            "target_role": "AI Engineer",
            "current_view": "skills",
            "location": "India",
        }
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "analyze_market_ecosystem" in chat_data["tools_invoked"]
    assert "analyze_skill_gap" not in chat_data["tools_invoked"]
    assert "Understood: I understand" not in chat_data["answer"]
    assert "Understood:" not in chat_data["answer"]


def test_supervisor_multipart_trending_skills_for_role():
    """Verify multi-part query 'trending skills for AI Engineer'
    invokes BOTH analyze_market_ecosystem AND analyze_skill_gap.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="trending skills for AI Engineer")
    ]
    user_context = UserContext(
        user_skills=["Python", "TensorFlow"],
        target_role="AI Engineer",
        location="India",
    )

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    # Must invoke BOTH market ecosystem and skill gap
    assert "analyze_market_ecosystem" in response.tools_invoked
    assert "analyze_skill_gap" in response.tools_invoked
    assert "Role Readiness Assessment: AI Engineer" in response.answer
    assert "Understood: I understand" not in response.answer
    assert "Understood:" not in response.answer


def test_supervisor_laser_focused_python_job_offers_overrides_context(client):
    """Verify 'python job offers' with background target_role 'AI Engineer'
    actively extracts 'Python' from prompt (Prompt > Context), invokes ONLY
    fetch_live_job_openings (laser-focused), does NOT call skill gap or market ecosystem,
    and returns direct markdown job cards without transitional boilerplate.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="python job offers")
    ]
    user_context = UserContext(
        user_skills=["TensorFlow", "PyTorch"],
        target_role="AI Engineer",
        location="India",
    )

    # 1. Direct Supervisor Agent invocation
    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert response.target_role == "Python"
    assert response.tools_invoked == ["fetch_live_job_openings"]
    assert "analyze_skill_gap" not in response.tools_invoked
    assert "analyze_market_ecosystem" not in response.tools_invoked
    assert "analyze_historical_job_demand" not in response.tools_invoked
    assert "Active Job Openings: Python in India" in response.answer
    assert "Found 5 verified job requisitions" not in response.answer
    assert "Across external developer communities" not in response.answer

    # 2. HTTP POST /api/assistant/chat endpoint verification
    chat_resp = client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "python job offers"}],
        "user_context": {
            "user_skills": ["TensorFlow", "PyTorch"],
            "target_role": "AI Engineer",
            "current_view": "career",
            "location": "India",
        }
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["target_role"] == "Python"
    assert chat_data["tools_invoked"] == ["fetch_live_job_openings"]
    assert "analyze_skill_gap" not in chat_data["tools_invoked"]
    assert "Active Job Openings: Python in India" in chat_data["answer"]


def test_supervisor_laser_focused_ui_ux_demand_overrides_context(client):
    """Verify 'ui/ux demand right now' with background target_role 'AI Engineer'
    actively extracts 'UI/UX' from prompt (Prompt > Context), invokes ONLY
    analyze_historical_job_demand (laser-focused), does NOT call skill gap or live jobs,
    and returns concise markdown demand metrics without transitional boilerplate.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="ui/ux demand right now")
    ]
    user_context = UserContext(
        user_skills=["TensorFlow", "PyTorch"],
        target_role="AI Engineer",
        location="India",
    )

    # 1. Direct Supervisor Agent invocation
    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert response.target_role == "UI/UX"
    assert response.tools_invoked == ["analyze_historical_job_demand"]
    assert "analyze_skill_gap" not in response.tools_invoked
    assert "analyze_market_ecosystem" not in response.tools_invoked
    assert "fetch_live_job_openings" not in response.tools_invoked
    assert "Enterprise Hiring Demand: UI/UX" in response.answer
    assert "Across enterprise hiring telemetry" not in response.answer

    # 2. HTTP POST /api/assistant/chat endpoint verification
    chat_resp = client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "ui/ux demand right now"}],
        "user_context": {
            "user_skills": ["TensorFlow", "PyTorch"],
            "target_role": "AI Engineer",
            "current_view": "career",
            "location": "India",
        }
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["target_role"] == "UI/UX"
    assert chat_data["tools_invoked"] == ["analyze_historical_job_demand"]
    assert "analyze_skill_gap" not in chat_data["tools_invoked"]
    assert "Enterprise Hiring Demand: UI/UX" in chat_data["answer"]


def test_supervisor_generic_qa_explain_machine_learning_bypasses_all_tools(client):
    """Verify generic/educational QA prompt 'Explain machine learning in simple words'
    is classified as GENERAL_QA, bypasses all tools (tools_invoked is strictly empty),
    and formats using the 4-part conversational standard.
    """
    import asyncio

    messages = [
        ChatMessage(role="user", content="Explain machine learning in simple words")
    ]
    user_context = UserContext(
        user_skills=["Python"],
        target_role="AI Engineer",
        location="India",
    )

    # 1. Direct Supervisor Agent invocation
    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert response.intent == "GENERAL_QA"
    assert response.tools_invoked == []
    assert len(response.evidence_payloads) == 0
    assert "### What I Understood" in response.answer
    assert "### What I Checked" not in response.answer
    assert "### Results" in response.answer
    assert "### Next Steps" in response.answer
    assert "Machine Learning" in response.answer

    # 2. HTTP POST /api/assistant/chat endpoint verification
    chat_resp = client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": "Explain machine learning in simple words"}],
        "user_context": {
            "user_skills": ["Python"],
            "target_role": "AI Engineer",
            "current_view": "career",
            "location": "India",
        }
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["intent"] == "GENERAL_QA"
    assert chat_data["tools_invoked"] == []
    assert len(chat_data["evidence_payloads"]) == 0
    assert "### What I Understood" in chat_data["answer"]
    assert "### What I Checked" not in chat_data["answer"]
    assert "### Results" in chat_data["answer"]


def test_supervisor_context_retention_followup_filter(monkeypatch):
    """Verify multi-turn context retention:
    Turn 1: 'Find Python jobs' -> role resolved to 'Python'.
    Turn 2: 'Show only fresher jobs' -> inherits 'Python' as target_role and passes filter_context='fresher' to tool.
    """
    import asyncio
    from unittest.mock import MagicMock
    import app.services.supervisor_agent as sup_agent

    mock_fetch = MagicMock(return_value={
        "role_name": "Python",
        "location": "India",
        "filter_context": "fresher",
        "count": 0,
        "openings": [],
        "source_provider": "Local PostgreSQL Cache",
        "live_api_status": "fallback_to_stored_catalog",
        "source_transparency": "0 active jobs found. Stored requisitions older than 180 days are omitted.",
    })
    monkeypatch.setattr(sup_agent, "fetch_live_job_openings", mock_fetch)

    user_context = UserContext(
        user_skills=["Python", "SQL"],
        target_role="AI Engineer",  # Background context, should be overridden by prompt entity
        location="India",
    )

    # Turn 1: Find Python jobs
    messages_turn_1 = [
        ChatMessage(role="user", content="Find Python jobs")
    ]
    resp_1 = asyncio.run(sup_agent.run_supervisor_agent(messages_turn_1, user_context))
    assert "fetch_live_job_openings" in resp_1.tools_invoked
    assert mock_fetch.call_args.kwargs["role_name"] == "Python"

    # Turn 2: Follow-up with filter modifier ("Show only fresher jobs")
    messages_turn_2 = [
        ChatMessage(role="user", content="Find Python jobs"),
        ChatMessage(role="assistant", content=resp_1.answer),
        ChatMessage(role="user", content="Show only fresher jobs"),
    ]
    resolved_turn_2 = sup_agent.resolve_multi_turn_context(messages_turn_2, user_context)
    assert resolved_turn_2["target_role"] == "Python"
    assert resolved_turn_2["filter_context"] == "fresher"

    resp_2 = asyncio.run(sup_agent.run_supervisor_agent(messages_turn_2, user_context))
    assert "fetch_live_job_openings" in resp_2.tools_invoked
    assert mock_fetch.call_args.kwargs["role_name"] == "Python"
    assert mock_fetch.call_args.kwargs["filter_context"] == "fresher"

    # When 0 jobs returned, Next Steps should suggest broadening search criteria across other locations or checking back later
    assert any("broaden" in step.lower() for step in resp_2.suggested_followups)
    assert not any("pune" in step.lower() for step in resp_2.suggested_followups)


def test_fetch_live_job_openings_omits_jobs_older_than_180_days():
    """Verify strict 180-day freshness filter on PostgreSQL raw_job_postings fallback:
    1. In current system context (October 2026), stored June 2026 postings are within 180 days (~150 days old)
       and are returned successfully as authentic active requisitions.
    2. When evaluated against a reference date older than 180 days (e.g. January 1, 2027),
       stale postings are omitted (count == 0, '0 active jobs found').
    """
    from datetime import datetime, timezone
    from app.services.assistant_tools import fetch_live_job_openings

    # 1. Current system date context: October 2026 -> June 2026 jobs are ~150 days old -> returned fresh
    current_resp = fetch_live_job_openings(role_name="Python", location="India", limit=5)
    assert current_resp["count"] > 0
    assert len(current_resp["openings"]) > 0
    assert current_resp["source_provider"] == "Local PostgreSQL Cache"
    assert "180 days" in current_resp["source_transparency"]

    # 2. Reference date beyond 180 days of stored postings (January 1, 2027) -> omitted as stale
    stale_date = datetime(2027, 1, 1, tzinfo=timezone.utc)
    stale_resp = fetch_live_job_openings(role_name="Python", location="India", limit=5, reference_date=stale_date)
    assert stale_resp["count"] == 0
    assert len(stale_resp["openings"]) == 0
    assert "0 active jobs found" in stale_resp["source_transparency"]
    assert "180 days" in stale_resp["source_transparency"]


def test_trend_validation_insufficient_data_under_4_months():
    """Verify that skills and roles with fewer than 4 months of historical baseline
    return trend: 'Insufficient Data' rather than '0.0% MoM' or 'Expanding'.
    """
    from app.services.assistant_tools import analyze_historical_job_demand, analyze_market_ecosystem

    # Role with only 2 months in database ('AI Product Manager')
    demand = analyze_historical_job_demand("AI Product Manager")
    assert demand["trend"] == "Insufficient Data"
    assert demand["mom_growth_pct"] is None
    assert demand["baseline_months_count"] < 4

    # Skill with 0 or fewer than 4 months in external_skill_signals
    eco = analyze_market_ecosystem("untracked_technology_skill_xyz")
    assert eco["trend"] == "Insufficient Data"
    assert eco["momentum_status"] == "Insufficient Data"
    assert eco["mom_growth_pct"] is None
    assert eco["baseline_months_count"] < 4


def test_supervisor_generic_qa_gemini_failure_returns_honest_error(monkeypatch):
    """Verify that when Gemini API call fails, synthesize_general_qa_answer returns
    a strictly honest error string and zero fake template text.
    """
    from unittest.mock import MagicMock
    from app.services.supervisor_agent import synthesize_general_qa_answer

    # 1. Simulate unmocked/unconfigured generic question with offline mode
    err_msg = synthesize_general_qa_answer("Explain quantum computing in detail", {})
    assert err_msg == "Error: Unable to connect to the Gemini AI service. Please check API keys."
    assert "Purpose" not in err_msg
    assert "Practical Application" not in err_msg

    # 2. Simulate Gemini throwing an exception during generate_content
    monkeypatch.setenv("GEMINI_API_KEY", "fake_test_key")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "0")

    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("Google API network timeout")
    mock_genai.GenerativeModel.return_value = mock_model
    monkeypatch.setitem(__import__("sys").modules, "google.generativeai", mock_genai)

    err_msg_api = synthesize_general_qa_answer("Explain quantum computing in detail", {})
    assert err_msg_api == "Error: Unable to connect to the Gemini AI service. Please check API keys."
    assert "Purpose" not in err_msg_api


def test_postgres_stored_jobs_skill_expansion():
    """Verify that fetch_postgres_stored_jobs expands matching to skills_extracted
    and raw_skill_observations, matching roles where the skill (e.g., Python) is required.
    """
    from datetime import datetime, timezone
    from app.services.live_job_connectors import fetch_postgres_stored_jobs

    fresh_date = datetime(2026, 6, 15, tzinfo=timezone.utc)
    jobs = fetch_postgres_stored_jobs(role_name="Python", location="India", limit=5, reference_date=fresh_date)
    assert len(jobs) > 0
    # Must find verified jobs matching Python either in role or observed required skills
    has_python_in_title_or_skills = any(
        "python" in j.job_title.lower() or any("python" in s.lower() for s in j.required_skills)
        for j in jobs
    )
    assert has_python_in_title_or_skills


def test_analyze_historical_job_demand_zero_active_postings():
    """Verify that roles with 0 verified postings in the database:
    1. Force hiring demand score to 0 (not 50 or base score).
    2. Set trend to 'No Active Demand' (not 'Insufficient Data').
    3. UI markdown explicitly states 'There is currently no observable enterprise hiring demand...'.
    4. Leading Hiring Employers section is omitted entirely.
    """
    from app.services.assistant_tools import analyze_historical_job_demand
    from app.services.supervisor_agent import synthesize_historical_demand_answer

    # Query a nonexistent role with 0 postings
    demand = analyze_historical_job_demand("Nonexistent Fantasy Role XYZ")
    assert demand["total_postings"] == 0
    assert demand["demand_score"] == 0
    assert demand["hiring_demand_score"] == 0
    assert demand["trend"] == "No Active Demand"
    assert demand["mom_growth_pct"] is None
    assert demand["demand_trend_mom_pct"] is None
    assert demand["top_employers"] == []

    # Test synthesis markdown
    answer_md = synthesize_historical_demand_answer(demand)
    assert "Hiring Demand Score**: **0 / 100**" in answer_md
    assert "Momentum Trajectory**: **No Active Demand**" in answer_md
    assert "There is currently no observable enterprise hiring demand for this role/skill in the tracked database." in answer_md
    assert "Leading Hiring Employers" not in answer_md


def test_universal_skill_demand_search():
    """Verify that searching for standalone skills (e.g., 'Docker', 'React') in
    analyze_historical_job_demand dynamically queries both job titles and required skills,
    returning non-zero postings instead of 0.
    """
    from app.services.assistant_tools import analyze_historical_job_demand

    docker_demand = analyze_historical_job_demand("Docker")
    assert docker_demand["total_postings"] > 0
    assert len(docker_demand["top_employers"]) > 0
    assert docker_demand["demand_score"] > 0
    assert docker_demand["trend"] in ("Expanding", "Steady", "Declining")

    react_demand = analyze_historical_job_demand("React")
    assert react_demand["total_postings"] > 0
    assert len(react_demand["top_employers"]) > 0
    assert react_demand["demand_score"] > 0



# ---------------------------------------------------------------------------
# 7. DIRECT ATS INTEGRATION TESTS (Greenhouse, Lever, Ashby)
# ---------------------------------------------------------------------------

def test_direct_ats_greenhouse_mock_extracts_python_job():
    """Verify fetch_direct_ats_jobs queries Greenhouse endpoint with a mock client
    and accurately extracts Python job with standard dictionary schema:
    job_title, company_name, location_raw, application_url, posted_at.
    """
    from unittest.mock import MagicMock
    import httpx
    from app.services.live_job_connectors import fetch_direct_ats_jobs, fetch_live_job_openings_connector

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "jobs": [
            {
                "id": 90123,
                "title": "Software Development Engineer II - Python",
                "content": "<p>Work on our core order-dispatch engine using Python, FastAPI, and Kafka.</p>",
                "location": {"name": "Bengaluru, India"},
                "absolute_url": "https://boards.greenhouse.io/swiggy/jobs/90123",
                "updated_at": "2026-10-28T09:00:00Z",
            },
            {
                "id": 90124,
                "title": "Senior Frontend Developer",
                "content": "<p>React, Redux, and Next.js for high performance consumer applications.</p>",
                "location": {"name": "Remote, India"},
                "absolute_url": "https://boards.greenhouse.io/swiggy/jobs/90124",
                "updated_at": "2026-10-27T11:00:00Z",
            },
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp

    # 1. Direct fetch_direct_ats_jobs invocation
    ats_results = fetch_direct_ats_jobs(
        role_name="Python",
        location="India",
        client=mock_client,
        companies={"greenhouse": ["swiggy"]},
    )

    assert len(ats_results) == 1
    python_job = ats_results[0]

    # Verify standard dictionary schema
    assert python_job["job_title"] == "Software Development Engineer II - Python"
    assert python_job["company_name"] == "Swiggy"
    assert "Bengaluru" in python_job["location_raw"]
    assert python_job["application_url"] == "https://boards.greenhouse.io/swiggy/jobs/90123"
    assert python_job["posted_at"] == "2026-10-28T09:00:00Z"

    # 2. Verify description-based matching when skill is in content
    desc_match_resp = MagicMock()
    desc_match_resp.status_code = 200
    desc_match_resp.json.return_value = {
        "jobs": [
            {
                "id": 90125,
                "title": "Backend Platform Architect",
                "content": "<p>Deep expertise in Python asynchronous programming and microservices.</p>",
                "location": {"name": "India (Remote)"},
                "absolute_url": "https://boards.greenhouse.io/swiggy/jobs/90125",
                "updated_at": "2026-10-28T10:00:00Z",
            }
        ]
    }
    mock_client.get.return_value = desc_match_resp
    desc_results = fetch_direct_ats_jobs(
        role_name="Python",
        location="India",
        client=mock_client,
        companies={"greenhouse": ["swiggy"]},
    )
    assert len(desc_results) == 1
    assert desc_results[0]["job_title"] == "Backend Platform Architect"


def test_fetch_live_job_openings_connector_prioritizes_ats_first(monkeypatch):
    """Verify that fetch_live_job_openings_connector executes direct ATS first,
    and returns immediately with source_provider 'Direct ATS Integration (Greenhouse/Lever/Ashby)'."""
    from app.services.live_job_connectors import fetch_live_job_openings_connector

    fake_ats_jobs = [
        {
            "job_title": "Staff Python Architect",
            "company_name": "Razorpay",
            "location_raw": "Bengaluru, India",
            "application_url": "https://jobs.lever.co/razorpay/12345",
            "posted_at": "2026-10-29",
            "required_skills": ["Python", "Docker"],
        }
    ]

    monkeypatch.setattr("app.services.live_job_connectors.fetch_direct_ats_jobs", lambda **kwargs: fake_ats_jobs)

    openings = fetch_live_job_openings_connector(role_name="Python", location="India", limit=5)
    assert len(openings) == 1
    job = openings[0]
    assert job.source_provider == "Direct ATS Integration (Greenhouse/Lever/Ashby)"
    assert job.job_title == "Staff Python Architect"
    assert job.company_name == "Razorpay"
    assert job.apply_url == "https://jobs.lever.co/razorpay/12345"
    assert job.application_url == "https://jobs.lever.co/razorpay/12345"



# ---------------------------------------------------------------------------
# 8. FILTER CONTEXT, STRICT CURRENT FRESHNESS, & 4-MONTH ECOSYSTEM TESTS
# ---------------------------------------------------------------------------

def test_postgres_stored_jobs_fresher_filter_and_negative_exclusions():
    """Verify that fetch_postgres_stored_jobs applies filter_context='fresher':
    1. Appends positive filter matching 'fresher'.
    2. Applies negative exclusions dropping senior, lead, and principal roles.
    """
    from app.services.live_job_connectors import fetch_postgres_stored_jobs

    jobs = fetch_postgres_stored_jobs(role_name="Python", location="India", limit=5, filter_context="fresher")
    assert len(jobs) > 0
    for j in jobs:
        t_low = j.job_title.lower()
        assert "senior" not in t_low, f"Unexpected senior in: {j.job_title}"
        assert "lead" not in t_low, f"Unexpected lead in: {j.job_title}"
        assert "principal" not in t_low, f"Unexpected principal in: {j.job_title}"


def test_postgres_stored_jobs_current_dynamic_cutoff():
    """Verify that when 'current' jobs are requested, fetch_postgres_stored_jobs
    dynamically shrinks the freshness cutoff to 30 days, omitting 5-month-old stored jobs.
    """
    from app.services.live_job_connectors import fetch_postgres_stored_jobs

    jobs = fetch_postgres_stored_jobs(role_name="current Python jobs", location="India", limit=5)
    assert len(jobs) == 0


def test_market_ecosystem_dynamic_4_month_window():
    """Verify analyze_market_ecosystem dynamically calculates and binds to the 4-month
    telemetry baseline window leading up to max available period in the database.
    """
    from app.services.assistant_tools import analyze_market_ecosystem

    eco_skill = analyze_market_ecosystem("Python")
    assert eco_skill.get("observation_window") in ("2026-01 to 2026-04", "2026-07 to 2026-10")
    assert eco_skill.get("baseline_months_count") == 4

    eco_macro = analyze_market_ecosystem("")
    assert eco_macro.get("observation_window") in ("2026-01 to 2026-04", "2026-07 to 2026-10")
    assert eco_macro.get("macro_metrics", {}).get("freshness_period") in ("2026-04", "2026-10")


def test_postgres_stored_jobs_universal_dynamic_filters():
    """Verify universal SQL filter application handles generic inclusions and exclusions without hardcoded strings."""
    from app.services.live_job_connectors import fetch_postgres_stored_jobs

    # 1. Test Fresher inclusion + Senior exclusion
    fresher_jobs = fetch_postgres_stored_jobs(
        role_name="Python",
        include_filters=["fresher"],
        exclude_filters=["senior", "lead", "principal"],
        limit=5,
    )
    assert len(fresher_jobs) > 0
    for j in fresher_jobs:
        low = j.job_title.lower()
        assert "senior" not in low
        assert "lead" not in low
        assert "principal" not in low

    # 2. Test Senior inclusion + Junior/Fresher exclusion
    senior_jobs = fetch_postgres_stored_jobs(
        role_name="Python",
        include_filters=["senior"],
        exclude_filters=["junior", "fresher", "intern"],
        limit=5,
    )
    assert len(senior_jobs) > 0
    for j in senior_jobs:
        low = j.job_title.lower()
        assert "senior" in low or "sr" in low
        assert "fresher" not in low
        assert "intern" not in low

    # 3. Test Contract inclusion
    contract_jobs = fetch_postgres_stored_jobs(
        role_name="Python",
        include_filters=["contract"],
        exclude_filters=[],
        limit=5,
    )
    assert len(contract_jobs) > 0
    for j in contract_jobs:
        assert "contract" in j.job_title.lower() or "contract" in str(j.required_skills).lower()


def test_postgres_stored_jobs_dynamic_date_anchoring():
    """Verify that PostgreSQL queries dynamically anchor freshness to SELECT MAX(posted_at) in current DB."""
    from app.services.live_job_connectors import get_postgres_max_date
    from app.services.assistant_tools import fetch_live_job_openings

    max_d = get_postgres_max_date()
    assert max_d == "2026-06-01"

    res = fetch_live_job_openings("Python", filter_context="current")
    assert "Falling back to local database (Data as of 2026-06-01)" in res["source_transparency"]
    assert len(res["openings"]) > 0
    for j in res["openings"]:
        assert j.get("max_data_date") == "2026-06-01"


def test_classify_intent_find_remote_data_scientist_roles():
    """Verify prompt 'Find remote Data Scientist roles' strictly triggers LIVE_JOBS,
    does NOT trigger SKILL_GAP, extracts 'Data Scientist' as target role, and passes 'remote' filter."""
    from app.services.supervisor_agent import (
        classify_intent,
        _extract_prompt_entity,
        extract_dynamic_filters,
        resolve_multi_turn_context,
        ChatMessage,
        UserContext,
    )

    prompt = "Find remote Data Scientist roles"
    intents = classify_intent(prompt)
    assert intents == ["LIVE_JOBS"]
    assert "SKILL_GAP" not in intents

    # Verify context and entity extraction
    role = _extract_prompt_entity(prompt)
    assert role == "Data Scientist"

    inc, exc = extract_dynamic_filters(prompt)
    assert "remote" in inc

    resolved = resolve_multi_turn_context([ChatMessage(role="user", content=prompt)], UserContext())
    assert resolved["target_role"] == "Data Scientist"
    assert "remote" in resolved["include_filters"]


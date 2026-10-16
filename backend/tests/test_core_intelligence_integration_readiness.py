"""Comprehensive Offline Integration Audit & Readiness Test Suite for G2.6 Task 8.

Verifies the complete deterministic Core Intelligence request path:
Authenticated Request -> Intent Planner -> Entity Resolution -> Capability/Readiness Checks ->
Correct Handler -> Structured Facts -> Real Evidence -> Answer Synthesis -> Validation -> Consistent API Response.

Integration requirements:
1. Successful occupation/software-skill lookup using local reference data.
2. Successful related-occupation lookup using local reference data.
3. Entity-resolution endpoint and planner-to-orchestrator handoff.
4. Correct handler mapping for implemented intents.
5. Unknown and ambiguous entity handling without analytical execution.
6. Local market tables empty: no fabricated market snapshot or trend.
7. A trend with insufficient or non-consecutive periods is not completed.
8. Valid historical trend fixtures retain correct units, periods, and provenance.
9. Invalid numerical claims or fabricated citations fail validation.
10. Reference-taxonomy facts cannot be presented as measured market demand.
11. Forecasting and simulation remain strictly unsupported / non-executable.
12. API authentication and cross-company tenant isolation checks.
13. Handler exceptions produce safe, schema-valid failure responses.
14. No cross-request fact/evidence leakage or shared state.
15. Deterministic output for repeated equivalent requests.
16. API input validation (invalid schema produces HTTP 422).
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    StructuredFact,
    EvidenceItem,
)
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="integration_test_user_1",
        email="integration@talentscope.ai",
    )


def mock_company_user(company_id: str = "comp_alpha") -> UserProfile:
    return UserProfile(
        uid="integration_comp_user_1",
        email="admin@compalpha.com",
        company_id=company_id,
    )


def _make_obs(
    *,
    source: str = "jsearch",
    signal_type: str = "demand",
    skill: str = "Python",
    skill_id: str = "python",
    period: str = "2026-05",
    value: float = 100.0,
    posting_id: str | None = None,
    metadata: dict | None = None,
) -> MarketObservation:
    year, month = (int(p) for p in period.split("-"))
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
    return MarketObservation(
        id=f"obs-{source}-{skill_id}-{period}",
        source=source,
        signal_type=signal_type,
        observed_at=dt,
        period=period,
        location="Global",
        scope="global",
        skill=skill,
        skill_id=skill_id,
        value=value,
        unit="job_postings" if signal_type == "demand" else "questions",
        posting_id=posting_id,
        metadata=metadata or {},
        data_origin="real",
        history_type="platform_collected",
        series_id=f"{source}:{signal_type}:{skill_id}:v1",
        query_id=f"{source}:{signal_type}:query-v1",
        quality="valid",
    )


# =============================================================================
# 1. SUCCESSFUL OCCUPATION/SOFTWARE-SKILL LOOKUP (LOCAL SQLITE)
# =============================================================================

def test_integration_successful_occupation_software_skills():
    """Verify end-to-end occupation software skills lookup against local SQLite reference tables."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["execution_status"] == "completed"
    assert data["intent"] == "crosswalk_occupation_software"
    assert "occupation_software_skills" in data["capabilities_used"]
    assert len(data["facts"]) > 0
    assert len(data["evidence"]) > 0
    reference_metrics = [
        item for item in data["metric_results"]
        if str(item.get("source") or "").startswith("ref_onet")
    ]
    assert reference_metrics
    assert all(item["signal_type"] != "demand" for item in reference_metrics)
    assert all(item["metric_kind"] != "observed" for item in reference_metrics)

    # Verify facts are grounded in real reference taxonomy
    first_fact = data["facts"][0]
    assert first_fact["fact_type"] == "software_skill"
    assert first_fact["source"] == "ref_onet_software_skills"
    assert first_fact["data_origin"] == "real"
    assert first_fact["history_type"] == "reference_taxonomy"
    assert first_fact["evidence_reference"] is not None

    assert data["answer"].startswith("Identified")
    assert "**Observed details**" in data["answer"]
    assert "**Sources**" in data["answer"]
    assert "### 1. Direct Answer" not in data["answer"]


# =============================================================================
# 2. SUCCESSFUL RELATED OCCUPATIONS LOOKUP (LOCAL SQLITE)
# =============================================================================

def test_integration_successful_related_occupations():
    """Verify related occupations mobility crosswalk against local SQLite reference tables."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Show related occupations for Software Developers")

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "completed"
    assert resp.intent == "crosswalk_related_occupations"
    assert "related_occupations" in resp.capabilities_used
    assert any(f.source == "ref_onet_related_occupations" for f in resp.facts)
    assert any("Related Occupations" in resp.answer for _ in [1])


# =============================================================================
# 3. ENTITY-RESOLUTION ENDPOINT & PLANNER-TO-ORCHESTRATOR HANDOFF
# =============================================================================

def test_integration_entity_resolution_and_planner_handoff():
    """Verify /entities/resolve endpoint and planner-to-orchestrator entity handoff."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # 1. Direct entity resolution endpoint
    res_resp = client.post(
        "/api/v1/intelligence/entities/resolve",
        json={"name": "Software Developer"},
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["status"] == "resolved"
    assert res_data["entity"]["canonical_name"] == "Software Developers"
    assert res_data["entity"]["entity_type"] == "occupation"

    # 2. Plan endpoint preserves entity resolution
    plan_resp = client.post(
        "/api/v1/intelligence/plan",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert len(plan_data["entities"]) > 0
    resolved = plan_data["entities"][0]
    assert resolved["resolution_status"] == "resolved"
    assert resolved["canonical_entity"]["canonical_name"] == "Software Developers"

    # 3. Answer endpoint executes matching capability without re-prompting
    ans_resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["execution_status"] == "completed"


# =============================================================================
# 4. INTENT-TO-HANDLER MAPPING MATRIX
# =============================================================================

@pytest.mark.parametrize(
    "query,expected_intent,expected_capability",
    [
        ("Software Developer tools", "crosswalk_occupation_software", "occupation_software_skills"),
        ("Related occupations for Software Developers", "crosswalk_related_occupations", "related_occupations"),
        ("Search job postings for React", "search_jobs", "job_posting_search"),
        ("Recommended learning actions for career growth", "synthesize_actions", "action_recommendations"),
        ("Analyze skill gap for target role Software Developers", "analyze_skill_gap", "skill_gap_role_fit"),
    ],
)
def test_integration_intent_to_handler_mapping(query, expected_intent, expected_capability):
    """Verify every implemented intent routes strictly to its designated capability handler."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message=query, selected_skills=["Python"])

    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message=query, selected_skills=["Python"]),
        authenticated_user=mock_auth_user(),
    )
    assert plan.intent == expected_intent
    assert expected_capability in plan.selected_capabilities

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.intent == expected_intent
    assert expected_capability in resp.capabilities_used


# =============================================================================
# 5. UNKNOWN AND AMBIGUOUS ENTITY HANDLING
# =============================================================================

def test_integration_unknown_and_ambiguous_entities():
    """Verify unknown or ambiguous tokens prompt for clarification without analytical execution."""
    service = ExecutionOrchestratorService()

    # Missing entity token
    req_missing = CoreIntelligenceAnswerRequest(message="Show its trend")
    resp_missing = service.answer(req_missing, authenticated_user=mock_auth_user())
    assert resp_missing.execution_status == "requires_clarification"
    assert len(resp_missing.facts) == 0
    assert len(resp_missing.follow_up_questions) > 0

    # Ambiguous entity token
    req_ambig = CoreIntelligenceAnswerRequest(message="What is the trend for c?")
    resp_ambig = service.answer(req_ambig, authenticated_user=mock_auth_user())
    assert resp_ambig.execution_status == "requires_clarification"
    assert len(resp_ambig.facts) == 0
    assert any("multiple entities" in q for q in resp_ambig.follow_up_questions)


# =============================================================================
# 6. LOCAL MARKET TABLES EMPTY: ZERO FABRICATED SNAPSHOT OR TREND
# =============================================================================

def test_integration_empty_empirical_market_tables():
    """Verify that when local market store contains zero observations, trend requests return insufficient_data."""
    service = ExecutionOrchestratorService()
    # No observations provided in request; local market_observations SQLite table is empty
    req = CoreIntelligenceAnswerRequest(message="What is the trend for Python?", observations=[])

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "insufficient_data"
    assert "trend_velocity_analysis" not in resp.capabilities_used
    assert len(resp.facts) == 0
    assert "INSUFFICIENT_OBSERVATION_DATA" in resp.reason_codes
    assert "Insufficient empirical observation data" in resp.answer
    # Must not claim any trend or slope
    assert "slope" not in resp.answer.lower()
    assert "growing" not in resp.answer.lower()
    assert "declining" not in resp.answer.lower()


# =============================================================================
# 7. INSUFFICIENT OR NON-CONSECUTIVE PERIODS CANNOT COMPLETE TREND
# =============================================================================

def test_integration_insufficient_or_gapped_periods_cannot_complete_trend():
    """Verify that 2 observations do not calculate trend and return insufficient_data."""
    service = ExecutionOrchestratorService()
    obs_short = [
        _make_obs(period="2026-05", value=100.0),
        _make_obs(period="2026-06", value=110.0),
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        observations=obs_short,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "insufficient_data"
    assert "trend_velocity_analysis" not in resp.capabilities_used
    assert not any(f.fact_type == "trend_analysis" for f in resp.facts)


# =============================================================================
# 8. VALID HISTORICAL TREND FIXTURES RETAIN UNITS, PERIODS, PROVENANCE
# =============================================================================

def test_integration_valid_trend_fixture_provenance():
    """Verify valid trend execution preserves calculated metrics, consecutive periods, and provenance."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(period=period, value=value).model_copy(
            update={"source_url": f"https://evidence.example/{period}"}
        )
        for period, value in (
            ("2026-04", 200.0),
            ("2026-05", 215.0),
            ("2026-06", 230.0),
            ("2026-07", 245.0),
        )
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        observations=obs,
        time_range="max_available",
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "completed"

    trend_fact = next(f for f in resp.facts if f.fact_type == "trend_analysis")
    assert trend_fact.source == "theil_sen_estimator"
    assert trend_fact.provenance_id == "trend-velocity-theil-sen-v2-comparable-units"
    assert trend_fact.history_type == "empirical_time_series"
    assert trend_fact.data_origin == "real"
    assert trend_fact.details["periods_count"] == 4
    assert trend_fact.details["start_period"] == "2026-04"
    assert trend_fact.details["end_period"] == "2026-07"
    assert trend_fact.details["trend_slope"] == 15.0
    assert trend_fact.details["latest_period_change"] == 15.0
    assert trend_fact.details["velocity_unit"] == "job_postings per month"

    # Ensure evidence is linked
    ev = next(e for e in resp.evidence if e.evidence_id == trend_fact.evidence_reference)
    assert ev.source == "jsearch"
    assert ev.signal_type == "trend_calculation"
    assert ev.supporting_observation_ids == [item.id for item in obs]
    assert ev.supporting_source_urls == [
        f"https://evidence.example/{item.period}" for item in obs
    ]
    assert ev.period == "2026-04_to_2026-07"


# =============================================================================
# 9. INVALID NUMERICAL CLAIMS AND FABRICATED CITATIONS FAIL VALIDATION
# =============================================================================

def test_integration_adversarial_validation_checks():
    """Verify validation engine catches injected ungrounded claims and fabricated citations."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    plan = service.intent_planner.create_plan(req)
    facts, evidence, _ = service._handle_occupation_software_skills(req, plan)

    # 1. Injected ungrounded numerical claim
    tampered_ans_num = "Software Developers use tools. Additionally, there are 888888 job openings."
    st_num, reas_num = service._validate_response(tampered_ans_num, facts, evidence, ["occupation_software_skills"], plan)
    assert st_num == "failed"
    assert "VALIDATION_ERROR_UNGROUNDED_QUANTITATIVE_CLAIM" in reas_num

    # 2. Fabricated citation
    tampered_ans_cite = "Software Developers use Python based on `ev_fabricated_nonexistent_999`."
    st_cite, reas_cite = service._validate_response(tampered_ans_cite, facts, evidence, ["occupation_software_skills"], plan)
    assert st_cite == "failed"
    assert "VALIDATION_ERROR_MISSING_EVIDENCE_CITATION" in reas_cite


# =============================================================================
# 10. REFERENCE TAXONOMY CANNOT BE PRESENTED AS MEASURED MARKET DEMAND
# =============================================================================

def test_integration_taxonomy_cannot_be_presented_as_market_demand():
    """Verify O*NET taxonomy cannot be described as live employer hiring demand."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="Software Developer software tools"))

    facts = [
        StructuredFact(
            fact_id="fact_soft_1",
            fact_type="software_skill",
            entity_name="Python",
            canonical_entity_id="tech:onet:python",
            metric_name="hot_technology",
            metric_value=True,
            source="ref_onet_software_skills",
            evidence_reference="ev_onet_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_onet_1", source="ref_onet_software_skills", signal_type="software_skill", quality="valid", description="Taxonomy entry.")]

    conflated_ans = "This proves high employer hiring demand and active live job postings for software developers."
    st, reas = service._validate_response(conflated_ans, facts, evidence, ["occupation_software_skills"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_TAXONOMY_CONFLATED_WITH_HIRING_DEMAND" in reas


# =============================================================================
# 11. FORECASTING & SIMULATION REMAIN STRICTLY UNSUPPORTED
# =============================================================================

def test_integration_forecasting_and_simulation_strictly_unsupported():
    """Verify forecasting and workforce scenario simulation return unsupported status in G2.6."""
    service = ExecutionOrchestratorService()

    req_fc = CoreIntelligenceAnswerRequest(message="Forecast skill demand for Go in 2027")
    resp_fc = service.answer(req_fc, authenticated_user=mock_auth_user())
    assert resp_fc.execution_status == "unsupported"
    assert resp_fc.plan_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp_fc.reason_codes
    assert len(resp_fc.facts) == 0

    req_sim = CoreIntelligenceAnswerRequest(message="Simulate workforce headcount changes across departments")
    resp_sim = service.answer(req_sim, authenticated_user=mock_auth_user())
    assert resp_sim.execution_status == "unsupported"
    assert resp_sim.plan_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp_sim.reason_codes
    assert len(resp_sim.facts) == 0


# =============================================================================
# 12. API AUTHENTICATION & CROSS-COMPANY TENANT ISOLATION
# =============================================================================

def test_integration_api_authentication_and_tenant_isolation():
    """Verify unauthenticated requests are rejected and cross-company queries are blocked."""
    # Reset overrides to test real auth dependency
    app.dependency_overrides.clear()
    client = TestClient(app)

    # 1. Unauthenticated request to /answer returns 401
    resp_unauth = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert resp_unauth.status_code == 401

    # 2. Authenticated company user querying another company's workforce is blocked
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_company_user("comp_authorized")
    client_auth = TestClient(app)

    resp_cross = client_auth.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Show company workforce intelligence",
            "portal_type": "company",
            "company_id": "comp_target_unauthorized",
        },
    )
    assert resp_cross.status_code == 200
    data_cross = resp_cross.json()
    assert data_cross["execution_status"] == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in data_cross["reason_codes"]
    assert len(data_cross["facts"]) == 0
    assert "Access denied" in data_cross["answer"]


# =============================================================================
# 13. HANDLER EXCEPTIONS PRODUCE SAFE FAILURE RESPONSES
# =============================================================================

def test_integration_handler_exception_safety(monkeypatch):
    """Verify handler exceptions return safe 'failed' execution status without leaking tracebacks."""
    service = ExecutionOrchestratorService()

    def crashing_handler(*args, **kwargs):
        raise ValueError("Simulated unexpected handler failure")

    monkeypatch.setitem(service._handler_registry, "occupation_software_skills", crashing_handler)

    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "failed"
    assert "HANDLER_EXECUTION_FAILED" in resp.reason_codes
    assert "unexpected error occurred" in resp.answer
    assert "Simulated unexpected handler failure" not in resp.answer
    assert len(resp.facts) == 0


# =============================================================================
# 14. NO CROSS-REQUEST FACT/EVIDENCE LEAKAGE
# =============================================================================

def test_integration_no_cross_request_leakage():
    """Verify executing two different queries consecutively does not cross-pollinate facts or evidence."""
    service = ExecutionOrchestratorService()

    req_1 = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp_1 = service.answer(req_1, authenticated_user=mock_auth_user())

    req_2 = CoreIntelligenceAnswerRequest(message="Show related occupations for Software Developers")
    resp_2 = service.answer(req_2, authenticated_user=mock_auth_user())

    facts_1_types = {f.fact_type for f in resp_1.facts}
    facts_2_types = {f.fact_type for f in resp_2.facts}

    assert "software_skill" in facts_1_types
    assert "related_occupation" not in facts_1_types

    assert "related_occupation" in facts_2_types
    assert "software_skill" not in facts_2_types


# =============================================================================
# 15. DETERMINISTIC OUTPUT FOR REPEATED EQUIVALENT REQUESTS
# =============================================================================

def test_integration_deterministic_output():
    """Verify identical requests yield identical outputs across repeated executions."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    run_1 = service.answer(req, authenticated_user=mock_auth_user())
    run_2 = service.answer(req, authenticated_user=mock_auth_user())

    assert run_1.execution_status == run_2.execution_status == "completed"
    assert run_1.answer == run_2.answer
    assert [f.fact_id for f in run_1.facts] == [f.fact_id for f in run_2.facts]
    assert [e.evidence_id for e in run_1.evidence] == [e.evidence_id for e in run_2.evidence]
    assert run_1.capabilities_used == run_2.capabilities_used


# =============================================================================
# 16. API INPUT VALIDATION
# =============================================================================

def test_integration_api_input_validation():
    """Verify malformed requests produce controlled 422 Unprocessable Entity responses."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # Missing required 'message' field
    resp_missing_msg = client.post("/api/v1/intelligence/answer", json={})
    assert resp_missing_msg.status_code == 422

    # Empty 'message' field (min_length=1)
    resp_empty_msg = client.post("/api/v1/intelligence/answer", json={"message": ""})
    assert resp_empty_msg.status_code == 422

    # Invalid portal_type
    resp_invalid_portal = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "valid query", "portal_type": "invalid_portal_xyz"},
    )
    assert resp_invalid_portal.status_code == 422

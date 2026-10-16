"""G2.6 Task 9: Core Intelligence Product Completeness Test Suite.

End-to-end verification covering all 22 required operational use-case scenarios
specified in the G2.6 Task 9 completion criteria.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile
from app.models.entity_registry import EntityResolutionRequest
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    StructuredFact,
    EvidenceItem,
)
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.models.skill_intelligence import MarketObservation
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

def mock_auth_user(uid: str = "test_user_task9", email: str = "test@talentscope.ai") -> AuthenticatedUser:
    return AuthenticatedUser(uid=uid, email=email)


def mock_company_user(company_id: str = "comp_cyberdyne", uid: str = "emp_john_connor") -> UserProfile:
    return UserProfile(
        uid=uid,
        email="john@cyberdyne.com",
        company_id=company_id,
        user_type="company",
    )


def create_synthetic_observations(skill: str, periods: list[str]) -> list[MarketObservation]:
    """Helper creating memory-only MarketObservation objects for testing (never persisted to DB)."""
    obs_list = []
    for idx, p in enumerate(periods, 1):
        obs_list.append(
            MarketObservation(
                id=f"obs_test_{skill}_{p}",
                skill=skill,
                skill_id=f"skill:{skill.lower()}",
                period=p,
                source="jsearch",
                signal_type="demand",
                value=100.0 + idx * 10.0,
                location="US",
                observed_at=f"{p}-15T00:00:00Z",
                denominator=1000,
                fetch_run_id=f"run_test_{p}",
                data_origin="real",
                history_type="snapshot",
                series_id=f"series_{skill}_US_demand",
                quality="valid",
                confidence=0.95,
                metadata={"job_title": f"{skill} Engineer", "company": "Tech Corp"},
                posting_id=f"post_{skill}_{p}",
            )
        )
    return obs_list


# =============================================================================
# SCENARIOS 1-22
# =============================================================================

# Scenario 1: Resolve known tech & aliases
def test_scenario_01_resolve_known_tech_and_aliases():
    """Verify Entity Registry resolves known tech and aliases with high confidence and provenance."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # 1. Primary canonical name
    r1 = client.post("/api/v1/intelligence/entities/resolve", json={"name": "Python"})
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "resolved"
    assert d1["entity"]["canonical_name"] == "Python"
    assert d1["confidence"] >= 0.95
    assert d1["entity"]["source_record_id"] is not None
    assert "source" in d1["source_provenance"]

    # 2. Known alias 'golang'
    r2 = client.post("/api/v1/intelligence/entities/resolve", json={"name": "golang"})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "resolved"
    assert d2["entity"]["canonical_name"] == "Go"

    # 3. Known alias 'JS'
    r3 = client.post("/api/v1/intelligence/entities/resolve", json={"name": "JS"})
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["status"] == "resolved"
    assert d3["entity"]["canonical_name"] == "JavaScript"


# Scenario 2: Occupation software tools
def test_scenario_02_occupation_software_tools():
    """Verify crosswalk of occupation software tools returns tools from O*NET taxonomy with evidence."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "crosswalk_occupation_software"
    assert "occupation_software_skills" in data["capabilities_used"]
    assert data["execution_status"] == "completed"
    assert len(data["facts"]) > 0
    assert len(data["evidence"]) > 0
    # Assert tools exist in facts
    tool_names = [f["entity_name"] for f in data["facts"] if f["fact_type"] == "software_skill"]
    assert len(tool_names) > 0
    assert any(f["source"] == "ref_onet_software_skills" for f in data["facts"])
    assert "Software Developers" in data["answer"]


# Scenario 3: Related occupations
def test_scenario_03_related_occupations():
    """Verify related occupations crosswalk returns related roles and career pathways."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What are related occupations for Software Developers?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "crosswalk_related_occupations"
    assert "related_occupations" in data["capabilities_used"]
    assert data["execution_status"] == "completed"
    assert len(data["facts"]) > 0
    assert any(f["fact_type"] == "related_occupation" for f in data["facts"])
    assert any(e["signal_type"] == "mobility_crosswalk" for e in data["evidence"])


# Scenario 4: Occupation title lookup
def test_scenario_04_occupation_title_lookup():
    """Verify occupation title and SOC code lookup retrieves standardized O*NET definition."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Tell me about the role of Database Administrators"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "lookup_occupation"
    assert "occupation_lookup" in data["capabilities_used"]
    assert data["execution_status"] == "completed"
    assert any(f["metric_name"] == "soc_code" for f in data["facts"])
    assert any(e["source"] == "ref_onet_occupations" for e in data["evidence"])


# Scenario 5: Available market snapshot
def test_scenario_05_available_market_snapshot():
    """Verify market snapshot extracts latest empirical metrics when observations exist."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("Python", ["2026-01", "2026-02"])

    req = CoreIntelligenceAnswerRequest(
        message="Show current market snapshot for Python",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "completed"
    assert "market_snapshot" in res.capabilities_used
    assert any(f.fact_type == "market_snapshot" for f in res.facts)
    assert any(f.metric_name == "observed_metric_value" for f in res.facts)


# Scenario 6: Stored historical observations
def test_scenario_06_stored_historical_observations():
    """Verify retrieval of stored historical observation series without interpolation."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("Python", ["2025-11", "2025-12", "2026-01"])

    req = CoreIntelligenceAnswerRequest(
        message="Show historical observations for Python over time",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "completed"
    assert "historical_signal_retrieval" in res.capabilities_used
    assert len(res.facts) >= 3
    assert any(f.fact_type == "historical_observation" for f in res.facts)


# Scenario 7: Trend with >=4 valid consecutive periods
def test_scenario_07_trend_with_at_least_4_consecutive_periods():
    """Verify Theil-Sen trend calculation succeeds when >=4 consecutive periods are available."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("Python", ["2025-10", "2025-11", "2025-12", "2026-01"])

    req = CoreIntelligenceAnswerRequest(
        message="Show Python's growth trend and velocity",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "completed"
    assert "trend_velocity_analysis" in res.capabilities_used
    trend_facts = [f for f in res.facts if f.fact_type == "trend_analysis"]
    assert len(trend_facts) == 1
    assert trend_facts[0].source == "theil_sen_estimator"
    assert "trend_slope" in trend_facts[0].details
    assert "monthly_velocity" in trend_facts[0].details
    assert any(e.signal_type == "trend_calculation" for e in res.evidence)


# Scenario 8: Trend with 0 observations (insufficient data)
def test_scenario_08_trend_with_zero_observations_insufficient_data():
    """Verify trend request with 0 observations returns honest insufficient_data status without hallucinating."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Show Python's historical trend and velocity."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "analyze_trend"
    assert data["execution_status"] == "insufficient_data"
    assert "INSUFFICIENT_OBSERVATION_DATA" in data["reason_codes"]
    assert len(data["facts"]) == 0
    assert len(data["evidence"]) == 0
    assert "Insufficient empirical observation data" in data["answer"]
    assert any("consecutive" in lim.lower() for lim in data["limitations"])


# Scenario 9: Trend with missing periods/incompatible series
def test_scenario_09_trend_with_missing_periods_incompatible_series():
    """Verify trend request with only 2 periods (<4 required) rejects execution with insufficient_data."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("Python", ["2026-01", "2026-02"])  # Only 2 periods

    req = CoreIntelligenceAnswerRequest(
        message="Show Python's trend",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "insufficient_data"
    assert "INSUFFICIENT_OBSERVATION_DATA" in res.reason_codes
    assert len(res.facts) == 0


# Scenario 10: Evidence and provenance retrieval
def test_scenario_10_evidence_provenance_retrieval():
    """Verify retrieval of evidence and citations for analytical provenance."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("Python", ["2026-01"])

    req = CoreIntelligenceAnswerRequest(
        message="What evidence and citations support Python?",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "completed"
    assert "evidence_provenance_retrieval" in res.capabilities_used
    assert len(res.evidence) >= 1
    assert any(f.fact_type == "evidence_summary" for f in res.facts)


# Scenario 11: Search stored job postings
def test_scenario_11_search_stored_job_postings():
    """Verify search across stored job postings returns matching counts and posting citations."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()
    obs = create_synthetic_observations("React", ["2026-01", "2026-02"])

    req = CoreIntelligenceAnswerRequest(
        message="Find stored job postings for React",
        observations=obs,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.execution_status == "completed"
    assert "job_posting_search" in res.capabilities_used
    assert any(f.metric_name == "stored_postings_found" for f in res.facts)
    assert any(e.signal_type == "stored_posting" for e in res.evidence)


# Scenario 12: Job search when 0 postings stored
def test_scenario_12_job_search_when_zero_postings_stored():
    """Verify job search when 0 postings stored returns 0 count and honest answer without fabricating vacancies."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Find stored job postings for React in US."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "search_jobs"
    assert data["execution_status"] == "completed"
    assert any(f["metric_name"] == "stored_postings_found" and f["metric_value"] == 0 for f in data["facts"])
    assert any("Results are postings found strictly in the stored collection" in lim for lim in data["limitations"])


# Scenario 13: Action recommendations
def test_scenario_13_action_recommendations():
    """Verify generation of deterministic, grounded next actions for learning and upskilling."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Recommend learning actions for my current skills."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "synthesize_actions"
    assert "action_recommendations" in data["capabilities_used"]
    assert data["execution_status"] == "completed"
    assert len(data["facts"]) >= 3
    assert any(f["fact_type"] == "action_recommendation" for f in data["facts"])
    assert any(e["signal_type"] == "action_synthesis" for e in data["evidence"])


# Scenario 14: Ambiguous question -> clarification
def test_scenario_14_ambiguous_question_requires_clarification():
    """Verify ambiguous entity or prompt triggers requires_clarification with disambiguation options."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Tell me about go"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_status"] == "requires_clarification"
    assert "REQUIRES_CLARIFICATION" in data["reason_codes"]
    assert len(data["follow_up_questions"]) > 0
    assert "go" in data["follow_up_questions"][0].lower()


# Scenario 15: Unknown entity
def test_scenario_15_unknown_entity_handled_honestly():
    """Verify unrecognized entities return insufficient_data or honest limitation without fabrication."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is NonExistentHyperToolXYZ9999?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_status"] == "insufficient_data"
    assert "INSUFFICIENT_OBSERVATION_DATA" in data["reason_codes"]
    assert len(data["facts"]) == 0
    assert "NonExistentHyperToolXYZ9999" in data["answer"]


# Scenario 16: Future demand forecasting -> unsupported in G2.6
def test_scenario_16_future_demand_forecasting_unsupported_in_g2_6():
    """Verify forward-looking demand forecasting is rejected as unsupported in G2.6 with zero facts/evidence."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What will Python demand look like next year in 2027?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "forecast_future_demand"
    assert data["execution_status"] == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in data["reason_codes"]
    assert len(data["facts"]) == 0
    assert len(data["evidence"]) == 0
    assert "explicitly inactive and unsupported in milestone G2.6" in data["answer"]


# Scenario 17: Workforce simulation -> unsupported in G2.6
def test_scenario_17_workforce_simulation_unsupported_in_g2_6():
    """Verify workforce what-if simulation is rejected as unsupported in G2.6 with zero facts/evidence."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Simulate workforce reskilling scenario for our team."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "simulate_workforce_scenarios"
    assert data["execution_status"] == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in data["reason_codes"]
    assert len(data["facts"]) == 0
    assert len(data["evidence"]) == 0
    assert "explicitly inactive and unsupported in milestone G2.6" in data["answer"]


# Scenario 18: Unauthorized company workforce access
def test_scenario_18_unauthorized_company_workforce_access():
    """Verify cross-company intelligence queries are blocked with UNAUTHORIZED_CROSS_COMPANY_ACCESS."""
    app.dependency_overrides[dependencies.get_current_user] = mock_company_user  # Belonging to comp_cyberdyne
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Analyze company workforce skills",
            "portal_type": "company",
            "company_id": "comp_skynet_rival",  # Cross-tenant target
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_status"] == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in data["reason_codes"]
    assert "Access denied" in data["answer"]


# Scenario 19: Company question from individual portal
def test_scenario_19_company_question_from_individual_portal():
    """Verify individual portal user querying internal workforce intelligence requires company auth/clarification."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user  # Individual user without company
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Analyze our company workforce inventory",
            "portal_type": "individual",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Expect requires_clarification or blocked requiring company identifier
    assert data["execution_status"] in {"requires_clarification", "blocked"}
    if data["execution_status"] == "requires_clarification":
        assert any("company" in q.lower() for q in data["follow_up_questions"])
    else:
        assert "UNAUTHORIZED_PORTAL_ACCESS" in data["reason_codes"]


# Scenario 20: Question with different selected skills (question remains authoritative)
def test_scenario_20_question_authoritative_over_conflicting_selected_skills():
    """Verify question's explicit role takes precedence over conflicting selected_skills context."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    resp = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What software tools does a Data Scientist use?",
            "selected_skills": ["Photoshop", "Cooking"],  # Conflicting skills
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "crosswalk_occupation_software"
    assert data["execution_status"] == "completed"
    # Ensure answer/facts are grounded in Data Scientists, not cooking/photoshop
    assert any("Data Scientists" in (f.get("details", {}).get("occupation_title") or "") for f in data["facts"])
    assert "Data Scientists" in data["answer"]


# Scenario 21: Malformed, empty, excessive inputs
def test_scenario_21_malformed_empty_excessive_inputs():
    """Verify malformed, empty, or excessively long requests are rejected safely without crashes."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # 1. Empty message
    r_empty = client.post("/api/v1/intelligence/answer", json={"message": ""})
    assert r_empty.status_code == 422

    # 2. Whitespace only message
    r_spaces = client.post("/api/v1/intelligence/answer", json={"message": "   "})
    assert r_spaces.status_code == 422

    # 3. Disallowed extra injected fields
    r_extra = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is Python?", "injected_backdoor": True},
    )
    assert r_extra.status_code == 422

    # 4. Excessive input length (> 50,000 characters)
    r_long = client.post("/api/v1/intelligence/answer", json={"message": "Python " * 10000})
    # Pydantic or handler safely rejects or trims without unhandled server exception
    assert r_long.status_code in {200, 422}
    if r_long.status_code == 200:
        assert r_long.json()["execution_status"] in {"completed", "requires_clarification", "insufficient_data"}


# Scenario 22: Evidence isolation between requests
def test_scenario_22_evidence_isolation_between_requests():
    """Verify evidence and structured facts are strictly isolated across sequential requests."""
    orchestrator = ExecutionOrchestratorService()
    user = mock_auth_user()

    obs_py = create_synthetic_observations("Python", ["2026-01"])
    obs_java = create_synthetic_observations("Java", ["2026-01"])

    req_py = CoreIntelligenceAnswerRequest(
        message="Show current market snapshot for Python",
        observations=obs_py,
    )
    res_py = orchestrator.answer(req_py, authenticated_user=user)

    req_java = CoreIntelligenceAnswerRequest(
        message="Show current market snapshot for Java",
        observations=obs_java,
    )
    res_java = orchestrator.answer(req_java, authenticated_user=user)

    # Assert Python response has zero Java facts/evidence
    assert all("java" not in f.entity_name.lower() for f in res_py.facts)
    assert all("java" not in e.description.lower() for e in res_py.evidence)

    # Assert Java response has zero Python facts/evidence
    assert all("python" not in f.entity_name.lower() for f in res_java.facts)
    assert all("python" not in e.description.lower() for e in res_java.evidence)

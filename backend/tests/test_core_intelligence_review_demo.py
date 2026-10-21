"""Pytest suite verifying the 9 Core Intelligence Demonstration scenarios.

Validates:
1. Entity resolution for known technology (Python)
2. Software skills for known occupation (Software Developers)
3. Multi-turn follow-up with anaphora resolution
4. Evidence and provenance retrieval
5. Trend analysis: honest insufficient-data and rejection of client-supplied observations
6. Stored job-posting search with transparent scope limitations
7. Action recommendations grounded in real skill taxonomy
8. Rejection of forecasting and workforce simulation as unsupported
9. Authorization, user isolation, and company tenant isolation
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile, UserType

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")

USER_INDIVIDUAL = AuthenticatedUser(uid="demo_pytest_indiv", email="indiv@talentscope.ai")
USER_CORP_NVIDIA = UserProfile(uid="demo_pytest_nvidia", email="admin@nvidia.com", company_id="nvidia", role="company_admin")
USER_ATTACKER = AuthenticatedUser(uid="demo_pytest_attacker", email="attacker@external.com")


@pytest.fixture
def client():
    return TestClient(app)


def test_scenario_1_resolve_known_technology(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/entities/resolve", json={"name": "Python", "entity_type": "technology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["entity"]["canonical_name"] == "Python"
        assert data["entity"]["entity_id"] == "tech:python"
        assert data["confidence"] == 1.0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_scenario_2_software_skills_for_known_occupation(client, local_reference_database):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "What software tools does a Software Developer use?",
            "portal_type": "individual",
            "location": "Bangalore"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "completed"
        assert any(e["source"].startswith("ref_onet") for e in data["evidence"])
        assert "EXECUTION_COMPLETED_SUCCESSFULLY" in data["reason_codes"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_scenario_3_follow_up_with_anaphora_resolution(client, local_reference_database):
    conv_id = f"pytest_conv_{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        # Turn 1
        r1 = client.post("/api/v1/intelligence/answer", json={
            "message": "What software tools does a Software Developer use?",
            "portal_type": "individual",
            "conversation_id": conv_id,
        })
        assert r1.status_code == 200
        assert r1.json()["execution_status"] == "completed"

        # Turn 2: resolves pronoun "its" to "Software Developers"
        r2 = client.post("/api/v1/intelligence/answer", json={
            "message": "What are its related occupations?",
            "portal_type": "individual",
            "conversation_id": conv_id,
        })
        assert r2.status_code == 200
        data = r2.json()
        assert data["conversation_id"] == conv_id
        assert data["execution_status"] == "completed"
        assert len(data["facts"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_scenario_4_evidence_and_provenance_retrieval(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "Show evidence and provenance for Python",
            "portal_type": "individual",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "insufficient_data"
        assert data["status"] == "insufficient_data"
        assert data["reason_codes"] == ["NO_VERIFIED_EVIDENCE"]
        assert data["evidence"] == []
        summary = next(f for f in data["facts"] if f["fact_type"] == "evidence_summary")
        assert summary["metric_value"] == 0
        assert summary["data_origin"] == "unavailable"
        assert summary["readiness_state"] == "insufficient_data"
        assert "No matching stored observation" in summary["details"]["reason"]
    finally:
        app.dependency_overrides.clear()


def test_scenario_5_trend_insufficient_and_client_observations_rejected(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        # Part A: With 0 observations in local DB, honestly returns insufficient_data
        r_unavail = client.post("/api/v1/intelligence/answer", json={
            "message": "Show Python's historical market demand trend",
            "portal_type": "individual",
        })
        assert r_unavail.status_code == 200
        d_unavail = r_unavail.json()
        assert d_unavail["execution_status"] == "insufficient_data"
        assert "NO_OBSERVATIONS_FOR_SERIES" in d_unavail["reason_codes"]

        # Observation evidence must come from configured backend sources, not request JSON.
        sample_obs = [
            {"id": "obs-1", "skill": "Python", "skill_id": "skill:python", "source": "jsearch", "signal_type": "demand", "period": "2026-05", "value": 100.0, "observed_at": "2026-05-01T00:00:00Z", "history_type": "snapshot", "series_id": "series_py_us", "data_origin": "real"},
            {"id": "obs-2", "skill": "Python", "skill_id": "skill:python", "source": "jsearch", "signal_type": "demand", "period": "2026-06", "value": 120.0, "observed_at": "2026-06-01T00:00:00Z", "history_type": "snapshot", "series_id": "series_py_us", "data_origin": "real"},
            {"id": "obs-3", "skill": "Python", "skill_id": "skill:python", "source": "jsearch", "signal_type": "demand", "period": "2026-07", "value": 140.0, "observed_at": "2026-07-01T00:00:00Z", "history_type": "snapshot", "series_id": "series_py_us", "data_origin": "real"},
            {"id": "obs-4", "skill": "Python", "skill_id": "skill:python", "source": "jsearch", "signal_type": "demand", "period": "2026-08", "value": 160.0, "observed_at": "2026-08-01T00:00:00Z", "history_type": "snapshot", "series_id": "series_py_us", "data_origin": "real"},
        ]
        r_avail = client.post("/api/v1/intelligence/answer", json={
            "message": "Show Python's historical market demand trend",
            "portal_type": "individual",
            "observations": sample_obs
        })
        assert r_avail.status_code == 422
        assert "cannot be supplied by clients" in r_avail.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_scenario_6_search_stored_job_postings(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "Search stored job postings for Python in Bangalore",
            "portal_type": "individual",
            "location": "Bangalore"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "completed"
        assert any("stored collection" in lim.lower() for lim in data["limitations"])
    finally:
        app.dependency_overrides.clear()


def test_scenario_7_action_recommendations_require_skill_labels_supported_by_role_relationships(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        resp = client.post("/api/v1/intelligence/answer", json={
            "message": "What should I learn next for Cloud Architect?",
            "portal_type": "individual",
            "target_role": "Cloud Architect",
            "selected_skills": ["Python", "Docker"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "insufficient_data"
        assert data["status"] == "insufficient_data"
        assert not any(
            fact["fact_type"] == "action_recommendation"
            for fact in data["facts"]
        )
        assert "do not match" in data["answer"].lower()
        assert any(
            fact["fact_type"] == "learning_recommendation_readiness"
            and fact["details"]["reason_code"] == "UNRESOLVED_USER_SKILL"
            for fact in data["facts"]
        )
    finally:
        app.dependency_overrides.clear()


def test_scenario_8_unsupported_forecasting_and_simulation(client):
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    try:
        # Forecast
        r_fc = client.post("/api/v1/intelligence/answer", json={
            "message": "Forecast future demand for Python over the next 2 years",
            "portal_type": "individual",
        })
        assert r_fc.status_code == 200
        d_fc = r_fc.json()
        assert d_fc["execution_status"] in {"unsupported", "insufficient_data"}
        assert len(d_fc["facts"]) == 0

        # Simulation
        r_sim = client.post("/api/v1/intelligence/answer", json={
            "message": "Simulate what happens if 50% of workforce shifts to AI",
            "portal_type": "company",
            "company_id": "nvidia"
        })
        assert r_sim.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_scenario_9_authorization_and_tenant_isolation(client, approve_company_membership):
    # A. Unauthenticated -> 401
    app.dependency_overrides.clear()
    r_unauth = client.post("/api/v1/intelligence/answer", json={"message": "What is Python?"})
    assert r_unauth.status_code == 401

    # B. Individual user querying company workforce -> Blocked
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_INDIVIDUAL
    r_indiv_corp = client.post("/api/v1/intelligence/answer", json={
        "message": "What is our company workforce capability?",
        "portal_type": "company",
        "company_id": "nvidia"
    })
    assert r_indiv_corp.status_code == 403

    # C. Cross-company access -> Blocked
    approve_company_membership["owner"](USER_CORP_NVIDIA.uid, "nvidia")
    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_CORP_NVIDIA
    r_cross = client.post("/api/v1/intelligence/answer", json={
        "message": "What is our company workforce capability?",
        "portal_type": "company",
        "company_id": "google"
    })
    assert r_cross.status_code == 403

    # D. Conversation hijacking -> Blocked
    conv_id = f"priv_conv_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/intelligence/answer", json={
        "message": "Company confidential prompt",
        "portal_type": "company",
        "company_id": "nvidia",
        "conversation_id": conv_id
    })

    app.dependency_overrides[dependencies.get_current_user] = lambda: USER_ATTACKER
    r_hijack = client.post("/api/v1/intelligence/answer", json={
        "message": "What did we just discuss?",
        "conversation_id": conv_id
    })
    assert r_hijack.status_code == 200
    assert r_hijack.json()["execution_status"] == "blocked"
    assert "UNAUTHORIZED_CONVERSATION_ACCESS" in r_hijack.json()["reason_codes"]

    app.dependency_overrides.clear()

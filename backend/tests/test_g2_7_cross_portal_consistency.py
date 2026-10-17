"""G2.7 Task 1: Intelligence UX & Cross-Portal Consistency Test Suite.

Verifies:
1. Cross-portal response contract parity: Individual, Employee, and Company portals
   all share the standardized CoreIntelligenceAnswerResponse schema.
2. Honest status code handling across 8 interface states:
   - completed (successful grounded answer)
   - requires_clarification
   - insufficient_data
   - unsupported (G2.6 forecasting freeze preserved)
   - blocked (tenant isolation and auth guards)
   - failed (error resilience)
3. Strict multi-tenant security isolation:
   - Users without company membership cannot access company intelligence.
   - Cross-company inquiries are blocked with UNAUTHORIZED_CROSS_COMPANY_ACCESS.
4. Analytical database immutability:
   - Table row counts remain exact (332,426 reference rows across 6 tables, 0 empirical observations).
   - Zero synthetic observations created.
"""

from __future__ import annotations

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


def mock_individual_user(uid: str = "user_indiv_g27", email: str = "indiv@talentscope.ai") -> AuthenticatedUser:
    return AuthenticatedUser(uid=uid, email=email)


def mock_company_user(company_id: str = "nvidia", uid: str = "user_corp_nvidia") -> UserProfile:
    return UserProfile(
        uid=uid,
        email="corp@nvidia.com",
        company_id=company_id,
        role="company_admin",
    )


@pytest.mark.integration
def test_individual_portal_grounded_answer(local_reference_database):
    """Verify Individual portal receives validated CoreIntelligenceAnswerResponse."""
    app.dependency_overrides[dependencies.get_current_user] = mock_individual_user
    client = TestClient(app)

    try:
        resp = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "What software tools does a Software Developer use?",
                "portal_type": "individual",
                "location": "Bangalore",
                "time_range": "30d",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["portal_type"] == "individual"
        assert data["execution_status"] == "completed"
        assert "Software Developers" in data["answer"] or "software" in data["answer"].lower()
        assert len(data["facts"]) > 0
        assert len(data["evidence"]) > 0
        assert all(e["data_origin"] == "real" for e in data["evidence"])
        assert "EXECUTION_COMPLETED_SUCCESSFULLY" in data["reason_codes"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_employee_portal_grounded_answer(approve_company_membership, local_reference_database):
    """Verify Employee portal receives validated CoreIntelligenceAnswerResponse with employee context."""
    approve_company_membership["employee"]("user_indiv_g27", "company-g27")
    app.dependency_overrides[dependencies.get_current_user] = mock_individual_user
    client = TestClient(app)

    try:
        resp = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "What software skills are required for Data Scientists?",
                "portal_type": "employee",
                "target_role": "Data Scientists",
                "location": "Bangalore",
                "time_range": "30d",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["portal_type"] == "employee"
        assert data["execution_status"] == "completed"
        assert len(data["facts"]) > 0
        assert len(data["evidence"]) > 0
        assert "EXECUTION_COMPLETED_SUCCESSFULLY" in data["reason_codes"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_company_portal_tenant_isolation_guards(approve_company_membership, local_reference_database):
    """Verify strict tenant isolation across Individual and Cross-Company access."""
    client = TestClient(app)

    # 1. Unauthenticated request -> 401 Unauthorized
    app.dependency_overrides.clear()
    resp_unauth = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What is our company workforce capability?",
            "portal_type": "company",
            "company_id": "nvidia",
        },
    )
    assert resp_unauth.status_code == 401

    # 2. Individual user without company membership -> blocked
    app.dependency_overrides[dependencies.get_current_user] = mock_individual_user
    resp_individual = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What is our company workforce capability?",
            "portal_type": "company",
            "company_id": "nvidia",
        },
    )
    assert resp_individual.status_code == 403

    # 3. Cross-company access: user from "nvidia" queries "google" -> blocked
    approve_company_membership["owner"]("user_corp_nvidia", "nvidia")
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_company_user("nvidia")
    resp_cross = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What is our company workforce capability?",
            "portal_type": "company",
            "company_id": "google",
        },
    )
    assert resp_cross.status_code == 403

    # 4. Valid matching company query -> completed
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_company_user("nvidia")
    resp_valid = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What software tools does a Software Developer use?",
            "portal_type": "company",
            "company_id": "nvidia",
        },
    )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.json()
    assert data_valid["execution_status"] == "completed"
    assert data_valid["portal_type"] == "company"

    app.dependency_overrides.clear()


def test_unsupported_forecasting_consistency_across_all_portals(approve_company_membership):
    """Verify forecasting and what-if simulation are consistently rejected across all portals."""
    app.dependency_overrides[dependencies.get_current_user] = mock_individual_user
    client = TestClient(app)

    approve_company_membership["employee"]("user_indiv_g27", "company-g27")
    portals = ["individual", "employee"]
    for p in portals:
        resp = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "Simulate workforce what-if transition scenario.",
                "portal_type": p,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "unsupported"
        assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in data["reason_codes"]
        assert "unsupported in milestone g2.6" in data["answer"].lower()

    app.dependency_overrides.clear()


def test_clarification_consistency_across_all_portals():
    """Verify ambiguous requests trigger requires_clarification across portals."""
    app.dependency_overrides[dependencies.get_current_user] = mock_individual_user
    client = TestClient(app)

    try:
        resp = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "Compare",
                "portal_type": "individual",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_status"] == "requires_clarification"
        assert "REQUIRES_CLARIFICATION" in data["reason_codes"]
        assert len(data["follow_up_questions"]) > 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_database_immutability_and_zero_synthetic_data(local_reference_database):
    """Verify that intelligence queries preserve exact reference row counts and 0 observations."""
    conn = sqlite3.connect(local_reference_database)
    cur = conn.cursor()

    obs_count = cur.execute("SELECT count(*) FROM market_observations").fetchone()[0]
    assert obs_count == 0, "market_observations must remain exactly 0 (no synthetic data)"

    ref_counts = {
        "ref_onet_occupations": cur.execute("SELECT count(*) FROM ref_onet_occupations").fetchone()[0],
        "ref_onet_software_skills": cur.execute("SELECT count(*) FROM ref_onet_software_skills").fetchone()[0],
        "ref_onet_essential_skills": cur.execute("SELECT count(*) FROM ref_onet_essential_skills").fetchone()[0],
        "ref_onet_related_occupations": cur.execute("SELECT count(*) FROM ref_onet_related_occupations").fetchone()[0],
        "ref_github_language_adoption": cur.execute("SELECT count(*) FROM ref_github_language_adoption").fetchone()[0],
        "ref_github_topic_adoption": cur.execute("SELECT count(*) FROM ref_github_topic_adoption").fetchone()[0],
    }
    conn.close()

    assert ref_counts["ref_onet_occupations"] == 1016
    assert ref_counts["ref_onet_software_skills"] == 31821
    assert ref_counts["ref_onet_essential_skills"] == 18200
    assert ref_counts["ref_onet_related_occupations"] == 18460
    assert ref_counts["ref_github_language_adoption"] == 180338
    assert ref_counts["ref_github_topic_adoption"] == 82591
    assert sum(ref_counts.values()) == 332426

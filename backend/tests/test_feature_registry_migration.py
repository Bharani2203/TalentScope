"""Tests for Phase 1 Feature Registry Migration.

Verifies:
1. The registry contains exactly seven active features.
2. Skill has exactly three approved features.
3. Market has exactly two approved features.
4. Job has exactly two approved features.
5. Every feature has a unique ID and correct domain.
6. Required inputs and data sources are declared.
7. Valid feature IDs pass validation.
8. Unknown or mismatched feature IDs are handled safely.
9. Orchestrator returns pending implementation status without fabricating metrics.
10. Existing authentication and endpoints are preserved.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.services.capability_registry_service import (
    CAPABILITY_CATALOG,
    CAPABILITY_DOMAINS,
    CapabilityRegistryService,
)
from app.intelligence_v2.capability_registry import (
    APPROVED_CAPABILITY_IDS,
    CAPABILITIES,
    V2CapabilityRegistry,
    canonical_capability_id,
)
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES, get_feature_answer_policy
from app.intelligence_v2.orchestrator import V2Orchestrator


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_user_phase1",
        email="phase1@talentscope.ai",
        user_type="individual",
        claims={"user_type": "individual"},
    )


# =============================================================================
# 1. EXACT SEVEN FEATURES IN REGISTRY
# =============================================================================

EXPECTED_SEVEN_FEATURES = {
    "skill_future_relevance_score": {
        "domain": "skill",
        "name": "Skill Future Relevance Score",
        "v2_domain": "skill_intelligence",
    },
    "skill_change_alert": {
        "domain": "skill",
        "name": "Skill Change Alert",
        "v2_domain": "skill_intelligence",
    },
    "adaptive_skill_roadmap": {
        "domain": "skill",
        "name": "Adaptive Skill Roadmap",
        "v2_domain": "skill_intelligence",
    },
    "technology_adoption_shift_detector": {
        "domain": "market",
        "name": "Technology Adoption Shift Detector",
        "v2_domain": "market_intelligence",
    },
    "technology_impact_explorer": {
        "domain": "market",
        "name": "Technology Impact Explorer",
        "v2_domain": "market_intelligence",
    },
    "skill_based_job_match": {
        "domain": "job",
        "name": "Skill-Based Job Match",
        "v2_domain": "job_intelligence",
    },
    "career_transition_opportunity": {
        "domain": "job",
        "name": "Career Transition Opportunity",
        "v2_domain": "job_intelligence",
    },
}


def test_registry_contains_exactly_seven_features():
    """Verify the capability catalog contains exactly 7 features."""
    service = CapabilityRegistryService()
    catalog = service.get_catalog()

    assert catalog.total_capabilities == 7
    assert len(catalog.capabilities) == 7
    assert len(CAPABILITY_CATALOG) == 7
    assert set(CAPABILITY_CATALOG.keys()) == set(EXPECTED_SEVEN_FEATURES.keys())
    assert APPROVED_CAPABILITY_IDS == set(EXPECTED_SEVEN_FEATURES.keys())
    assert set(CAPABILITIES.keys()) == set(EXPECTED_SEVEN_FEATURES.keys())


def test_domain_breakdown_counts():
    """Verify Skill has 3, Market has 2, Job has 2 approved features."""
    skill_features = [c for c in CAPABILITY_CATALOG.values() if "skill" in c.supported_domains]
    market_features = [c for c in CAPABILITY_CATALOG.values() if "market" in c.supported_domains]
    job_features = [c for c in CAPABILITY_CATALOG.values() if "job" in c.supported_domains]

    assert len(skill_features) == 3, f"Expected 3 skill features, got {len(skill_features)}"
    assert len(market_features) == 2, f"Expected 2 market features, got {len(market_features)}"
    assert len(job_features) == 2, f"Expected 2 job features, got {len(job_features)}"

    assert {c.capability_id for c in skill_features} == {
        "skill_future_relevance_score",
        "skill_change_alert",
        "adaptive_skill_roadmap",
    }
    assert {c.capability_id for c in market_features} == {
        "technology_adoption_shift_detector",
        "technology_impact_explorer",
    }
    assert {c.capability_id for c in job_features} == {
        "skill_based_job_match",
        "career_transition_opportunity",
    }


def test_features_have_unique_ids_and_correct_metadata():
    """Verify each feature has a unique ID, valid metadata, and declared sources."""
    service = CapabilityRegistryService()
    catalog = service.get_catalog()
    seen_ids = set()

    for cap in catalog.capabilities:
        assert cap.capability_id not in seen_ids, f"Duplicate ID: {cap.capability_id}"
        seen_ids.add(cap.capability_id)

        expected = EXPECTED_SEVEN_FEATURES[cap.capability_id]
        assert cap.name == expected["name"]
        assert expected["domain"] in cap.supported_domains
        assert len(cap.description) > 20
        assert len(cap.required_inputs) > 0
        assert len(cap.required_sources) > 0
        assert cap.global_status == "available"
        assert cap.implementation_status == "pending"
        assert cap.handler is None  # Pending implementation in Phase 2; no phantom module reference


def test_canonical_capability_id_resolution_and_no_obsolete_aliases():
    """Verify canonical_capability_id accepts only approved IDs and does not alias obsolete ones."""
    for cap_id in EXPECTED_SEVEN_FEATURES:
        assert canonical_capability_id(cap_id) == cap_id

    # Obsolete capabilities should not be aliased
    obsolete_ids = [
        "trend_velocity_analysis",
        "historical_signal_retrieval",
        "skill_gap_role_fit",
        "market_snapshot",
        "job_posting_search",
        "role_preparation_actions",
        "skill_health_analysis",
    ]
    for obs in obsolete_ids:
        # Does not return an approved capability alias
        resolved = canonical_capability_id(obs)
        assert resolved not in APPROVED_CAPABILITY_IDS or resolved == obs


def test_v2_capability_registry():
    """Verify V2CapabilityRegistry returns exactly the 7 features."""
    reg = V2CapabilityRegistry()
    assert len(reg.list_capabilities()) == 7
    assert len(reg.list_capabilities("skill_intelligence")) == 3
    assert len(reg.list_capabilities("market_intelligence")) == 2
    assert len(reg.list_capabilities("job_intelligence")) == 2

    for cap_id in EXPECTED_SEVEN_FEATURES:
        assert reg.get_capability(cap_id) is not None


def test_feature_answer_policies():
    """Verify feature answer policies exist for all 7 features."""
    for cap_id, exp in EXPECTED_SEVEN_FEATURES.items():
        policy = get_feature_answer_policy(cap_id, exp["domain"])
        assert policy is not None
        assert policy.domain == exp["domain"]


# =============================================================================
# 2. RUNTIME EVALUATION & SAFE STATUS HANDLING
# =============================================================================

def test_capabilities_pending_implementation_in_phase1():
    """Verify execution of registered features reports pending implementation truthfully."""
    orchestrator = V2Orchestrator()

    req = CoreIntelligenceAnswerRequest(
        message="Assess Python future relevance",
        domain="skill",
        capability_id="skill_future_relevance_score",
        selected_skills=["Python"],
    )

    resp = orchestrator.execute_request(req, authenticated_user=mock_auth_user())
    assert resp.status == "unavailable"
    assert resp.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp.reason_codes
    assert "pending implementation in Phase 2" in resp.answer
    assert resp.executed_primary_capability == "skill_future_relevance_score"


def test_domain_mismatch_rejection():
    """Verify orchestrator safely rejects feature domain mismatch."""
    orchestrator = V2Orchestrator()

    # skill_future_relevance_score belongs to skill, but requested under market
    req = CoreIntelligenceAnswerRequest(
        message="What is Python relevance?",
        domain="market",
        capability_id="skill_future_relevance_score",
    )

    resp = orchestrator.execute_request(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "unsupported"
    assert "CAPABILITY_DOMAIN_MISMATCH" in resp.reason_codes
    assert "belongs to the 'skill' domain, but was invoked under the 'market' domain" in resp.answer


def test_unknown_capability_rejection():
    """Verify orchestrator safely rejects unknown capability IDs."""
    orchestrator = V2Orchestrator()

    req = CoreIntelligenceAnswerRequest(
        message="Analyze something",
        domain="skill",
        capability_id="totally_fake_capability",
    )

    resp = orchestrator.execute_request(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED" in resp.reason_codes


# =============================================================================
# 3. HTTP API ENDPOINTS CONTRACT
# =============================================================================

def test_capabilities_catalog_api_endpoint():
    """Verify GET /api/v1/intelligence/capabilities returns the 7 approved features."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    try:
        resp = client.get("/api/v1/intelligence/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_capabilities"] == 7
        assert data["available_count"] == 7
        returned_ids = {c["capability_id"] for c in data["capabilities"]}
        assert returned_ids == set(EXPECTED_SEVEN_FEATURES.keys())
        for c in data["capabilities"]:
            assert c["global_status"] == "available"
            assert c["implementation_status"] == "pending"
            assert c["handler"] is None
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# =============================================================================
# 4. PHASE 1.1 INPUT CONTRACT & ORCHESTRATOR EXECUTION TESTS
# =============================================================================

def test_technology_impact_explorer_orchestrator_requests():
    """Verify orchestrator accepts technology or skill input for technology_impact_explorer."""
    orchestrator = V2Orchestrator()
    user = mock_auth_user()

    # 1. With technology input
    req_tech = CoreIntelligenceAnswerRequest(
        message="explore impact of Kubernetes",
        domain="market",
        capability_id="technology_impact_explorer",
        technology="Kubernetes",
    )
    resp_tech = orchestrator.execute_request(req_tech, authenticated_user=user)
    assert resp_tech.status == "unavailable"
    assert resp_tech.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_tech.reason_codes

    # 2. With skill input
    req_skill = CoreIntelligenceAnswerRequest(
        message="explore impact of Docker",
        domain="market",
        capability_id="technology_impact_explorer",
        selected_skills=["Docker"],
    )
    resp_skill = orchestrator.execute_request(req_skill, authenticated_user=user)
    assert resp_skill.status == "unavailable"
    assert resp_skill.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_skill.reason_codes

    # 3. With optional occupation input
    req_occ = CoreIntelligenceAnswerRequest(
        message="explore impact of Generative AI on Data Scientist",
        domain="market",
        capability_id="technology_impact_explorer",
        technology="Generative AI",
        occupation="Data Scientist",
    )
    resp_occ = orchestrator.execute_request(req_occ, authenticated_user=user)
    assert resp_occ.status == "unavailable"
    assert resp_occ.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_occ.reason_codes


def test_career_transition_opportunity_orchestrator_requests():
    """Verify orchestrator accepts current_role or target_role for career_transition_opportunity."""
    orchestrator = V2Orchestrator()
    user = mock_auth_user()

    # 1. With current_role
    req_current = CoreIntelligenceAnswerRequest(
        message="career transition from QA Engineer",
        domain="job",
        capability_id="career_transition_opportunity",
        current_role="QA Engineer",
    )
    resp_current = orchestrator.execute_request(req_current, authenticated_user=user)
    assert resp_current.status == "unavailable"
    assert resp_current.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_current.reason_codes

    # 2. With target_role
    req_target = CoreIntelligenceAnswerRequest(
        message="career transition to DevOps Engineer",
        domain="job",
        capability_id="career_transition_opportunity",
        target_role="DevOps Engineer",
    )
    resp_target = orchestrator.execute_request(req_target, authenticated_user=user)
    assert resp_target.status == "unavailable"
    assert resp_target.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_target.reason_codes

    # 3. With optional current skills
    req_skills = CoreIntelligenceAnswerRequest(
        message="career transition from QA Engineer",
        domain="job",
        capability_id="career_transition_opportunity",
        current_role="QA Engineer",
        selected_skills=["Python", "Selenium"],
    )
    resp_skills = orchestrator.execute_request(req_skills, authenticated_user=user)
    assert resp_skills.status == "unavailable"
    assert resp_skills.execution_status == "blocked"
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in resp_skills.reason_codes


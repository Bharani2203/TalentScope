"""Offline tests for Capability Registry after Phase 1 Migration.

Verifies:
- 7 approved capabilities properly cataloged with available status.
- Zero Firestore imports or network requests.
- Runtime evaluation reflects pending Phase 2 implementation.
- Unknown capability handling.
- Deterministic evaluation output without fabricated metrics.
- API endpoints contract verification.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import (
    CapabilityCatalogResponse,
    CapabilityEvaluationRequest,
    CapabilityEvaluationResponse,
    CapabilityRecord,
)
from app.services.capability_registry_service import (
    CAPABILITY_CATALOG,
    CapabilityRegistryService,
)


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_user_123",
        email="test@example.com",
        user_type="individual",
        claims={"user_type": "individual"},
    )


# =============================================================================
# 1. ARCHITECTURE & READ SAFETY TESTS
# =============================================================================

def test_no_firestore_imports_in_capability_service():
    """Verify CapabilityRegistryService does not import or depend directly on Firestore."""
    import app.services.capability_registry_service as mod

    source = inspect.getsource(mod)
    assert "firebase_admin" not in source, "capability_registry_service must not import firebase_admin"
    assert "get_firestore_client" not in source, "capability_registry_service must not call get_firestore_client"
    assert "google.cloud.firestore" not in source, "capability_registry_service must not import google.cloud.firestore"


# =============================================================================
# 2. CAPABILITY CATALOG AUDIT TESTS
# =============================================================================

def test_capability_catalog_completeness_and_states():
    """Verify exactly 7 capabilities are registered with available status."""
    service = CapabilityRegistryService()
    catalog = service.get_catalog()

    assert catalog.total_capabilities == 7
    assert len(catalog.capabilities) == 7

    # Check breakdown
    assert catalog.available_count == 7
    assert catalog.partial_count == 0
    assert catalog.building_count == 0
    assert catalog.insufficient_data_count == 0
    assert catalog.blocked_count == 0

    assert set(CAPABILITY_CATALOG.keys()) == {
        "skill_future_relevance_score",
        "skill_change_alert",
        "adaptive_skill_roadmap",
        "technology_adoption_shift_detector",
        "technology_impact_explorer",
        "skill_based_job_match",
        "career_transition_opportunity",
    }


def test_capability_records_have_complete_contracts():
    """Verify all capability records have stable IDs, descriptions, inputs, limitations, and provenance."""
    service = CapabilityRegistryService()
    catalog = service.get_catalog()

    for cap in catalog.capabilities:
        assert cap.capability_id in CAPABILITY_CATALOG
        assert len(cap.name) > 3
        assert len(cap.description) > 10
        assert cap.supported_intent
        assert len(cap.supported_entity_types) > 0
        assert len(cap.required_inputs) > 0
        assert len(cap.limitations) > 0, f"Capability {cap.capability_id} missing explicit limitations"
        assert len(cap.provenance_requirements) > 0, f"Capability {cap.capability_id} missing provenance requirements"
        assert cap.global_status == "available"
        assert cap.implementation_status == "pending"
        assert cap.handler is None  # Pending implementation in Phase 2; no phantom module reference


# =============================================================================
# 3. PENDING IMPLEMENTATION EVALUATION TESTS
# =============================================================================

def test_pending_capabilities_evaluation():
    """Verify Phase 1 features return pending implementation status upon evaluation."""
    service = CapabilityRegistryService()

    for cap_id in CAPABILITY_CATALOG:
        req = CapabilityEvaluationRequest(
            capability_id=cap_id,
            entity_name="python",
            portal_type="individual",
        )
        resp = service.evaluate(req)
        assert len(resp.results) == 1
        res = resp.results[0]
        assert res.global_status == "available"
        assert res.can_execute is False
        assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
        assert len(res.missing_requirements) > 0


def test_unknown_capability_evaluation():
    """Verify unknown capability IDs return UNKNOWN_CAPABILITY_ID error."""
    service = CapabilityRegistryService()

    resp = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="non_existent_capability",
            entity_name="python",
            portal_type="individual",
        )
    )
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.can_execute is False
    assert "UNKNOWN_CAPABILITY_ID" in res.reason_codes


# =============================================================================
# 4. DETERMINISM TEST
# =============================================================================

def test_deterministic_evaluation():
    """Verify identical inputs yield identical deterministic evaluation results."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        entity_name="python",
        portal_type="individual",
        selected_skills=["python"],
        target_role="Software Developer",
    )

    resp1 = service.evaluate(req)
    resp2 = service.evaluate(req)

    assert len(resp1.results) == len(resp2.results)
    for r1, r2 in zip(resp1.results, resp2.results):
        assert r1.capability_id == r2.capability_id
        assert r1.global_status == r2.global_status
        assert r1.runtime_status == r2.runtime_status
        assert r1.can_execute == r2.can_execute
        assert r1.reason_codes == r2.reason_codes
        assert r1.missing_requirements == r2.missing_requirements


# =============================================================================
# 5. API ENDPOINTS INTEGRATION TESTS
# =============================================================================

def test_capabilities_api_endpoints():
    """Verify GET /capabilities and POST /capabilities/evaluate HTTP endpoints."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    try:
        # 1. GET /api/v1/intelligence/capabilities
        cat_resp = client.get("/api/v1/intelligence/capabilities")
        assert cat_resp.status_code == 200
        cat_data = cat_resp.json()
        assert cat_data["total_capabilities"] == 7
        assert cat_data["available_count"] == 7
        assert len(cat_data["capabilities"]) == 7

        # 2. POST /api/v1/intelligence/capabilities/evaluate
        eval_resp = client.post(
            "/api/v1/intelligence/capabilities/evaluate",
            json={
                "capability_id": "skill_future_relevance_score",
                "entity_name": "python",
                "portal_type": "individual",
            },
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert len(eval_data["results"]) == 1
        res = eval_data["results"][0]
        assert res["capability_id"] == "skill_future_relevance_score"
        assert res["global_status"] == "available"
        assert res["implementation_status"] == "pending"
        assert res["can_execute"] is False
        assert "CAPABILITY_PENDING_IMPLEMENTATION" in res["reason_codes"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# =============================================================================
# 6. INPUT CONTRACT & METADATA TESTS (PHASE 1.1)
# =============================================================================

def test_technology_impact_explorer_with_technology_input():
    """Verify technology_impact_explorer accepts a technology as primary input."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="technology_impact_explorer",
        technology="Kubernetes",
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.global_status == "available"
    assert res.implementation_status == "pending"
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("primary_input:technology" in p for p in res.provenance_references)


def test_technology_impact_explorer_with_skill_input():
    """Verify technology_impact_explorer accepts a skill as primary input without requiring technology."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="technology_impact_explorer",
        selected_skills=["Docker"],
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.global_status == "available"
    assert res.implementation_status == "pending"
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("primary_input:skill" in p for p in res.provenance_references)


def test_technology_impact_explorer_with_optional_occupation():
    """Verify technology_impact_explorer accepts optional occupation input."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="technology_impact_explorer",
        technology="Generative AI",
        occupation="Data Scientist",
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("optional_input:occupation" in p for p in res.provenance_references)


def test_technology_impact_explorer_missing_primary_input():
    """Verify technology_impact_explorer safely rejects evaluation when neither technology nor skill is provided."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="technology_impact_explorer",
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.can_execute is False
    assert "MISSING_TECHNOLOGY_OR_SKILL_INPUT" in res.reason_codes
    assert "technology_or_skill" in res.missing_requirements


def test_career_transition_opportunity_with_current_role():
    """Verify career_transition_opportunity accepts current_role as primary input."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="career_transition_opportunity",
        current_role="QA Engineer",
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.global_status == "available"
    assert res.implementation_status == "pending"
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("role_input:current_role" in p for p in res.provenance_references)


def test_career_transition_opportunity_with_target_role():
    """Verify career_transition_opportunity accepts target_role without requiring current_role exclusively."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="career_transition_opportunity",
        target_role="DevOps Engineer",
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.global_status == "available"
    assert res.implementation_status == "pending"
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("role_input:target_role" in p for p in res.provenance_references)


def test_career_transition_opportunity_with_skills():
    """Verify career_transition_opportunity accepts optional current skills."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="career_transition_opportunity",
        current_role="QA Engineer",
        selected_skills=["Python", "Selenium"],
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.can_execute is False
    assert "CAPABILITY_PENDING_IMPLEMENTATION" in res.reason_codes
    assert any("optional_input:current_skills" in p for p in res.provenance_references)


def test_career_transition_opportunity_missing_role_input():
    """Verify career_transition_opportunity safely rejects evaluation when neither acceptable role input is supplied."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="career_transition_opportunity",
        selected_skills=["Python"],  # Only skills, no current or target role
        portal_type="individual",
    )
    resp = service.evaluate(req)
    assert len(resp.results) == 1
    res = resp.results[0]
    assert res.can_execute is False
    assert "MISSING_ROLE_INPUT" in res.reason_codes
    assert "current_role_or_target_role" in res.missing_requirements


def test_safe_validation_invalid_input_types():
    """Verify safe validation and rejection when invalid entity types are supplied."""
    service = CapabilityRegistryService()
    # 1. Invalid entity_type for technology_impact_explorer (e.g. company)
    req1 = CapabilityEvaluationRequest(
        capability_id="technology_impact_explorer",
        entity_name="Acme Corp",
        entity_type="company",
        portal_type="individual",
    )
    resp1 = service.evaluate(req1)
    assert resp1.results[0].can_execute is False
    assert "UNSUPPORTED_ENTITY_TYPE" in resp1.results[0].reason_codes

    # 2. Invalid entity_type for career_transition_opportunity (e.g. company)
    req2 = CapabilityEvaluationRequest(
        capability_id="career_transition_opportunity",
        entity_name="Acme Corp",
        entity_type="company",
        portal_type="individual",
    )
    resp2 = service.evaluate(req2)
    assert resp2.results[0].can_execute is False
    assert "UNSUPPORTED_ENTITY_TYPE" in resp2.results[0].reason_codes

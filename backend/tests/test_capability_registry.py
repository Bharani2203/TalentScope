"""Offline tests for G2.6 Capability Registry.

Verifies:
- 15 candidate capabilities properly cataloged with explicit global statuses.
- Zero Firestore imports or network requests.
- Implemented vs planned capabilities (building features cannot execute).
- Runtime readiness evaluation vs global implementation state.
- Analytical readiness gate reuse (consecutive periods, coverage gaps, drift).
- Ambiguous and unresolvable entity handling.
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
from app.models.skill_intelligence import MarketObservation
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
    """Verify exactly 15 candidate capabilities are registered with valid states."""
    service = CapabilityRegistryService()
    catalog = service.get_catalog()

    assert catalog.total_capabilities == 15
    assert len(catalog.capabilities) == 15

    # Check breakdown
    assert catalog.available_count == 10
    assert catalog.partial_count == 3
    assert catalog.building_count == 2
    assert catalog.insufficient_data_count == 0
    assert catalog.blocked_count == 0

    # Verify building capabilities
    building_ids = {c.capability_id for c in catalog.capabilities if c.global_status == "building"}
    assert building_ids == {"skill_forecasting_half_life", "workforce_what_if_simulation"}

    # Verify partial capabilities
    partial_ids = {c.capability_id for c in catalog.capabilities if c.global_status == "partial"}
    assert partial_ids == {
        "skill_gap_role_fit",
        "job_posting_search",
        "company_intelligence",
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
        if cap.global_status in {"available", "partial"}:
            assert cap.handler is not None, f"Implemented capability {cap.capability_id} must declare a handler"
        else:
            assert cap.handler is None, f"Building capability {cap.capability_id} must have handler=None"


# =============================================================================
# 3. PLANNED CAPABILITIES GATING TESTS
# =============================================================================

def test_planned_capabilities_cannot_execute():
    """Verify planned/building capabilities always return can_execute=False and runtime_status=building."""
    service = CapabilityRegistryService()

    for cap_id in ["skill_forecasting_half_life", "workforce_what_if_simulation"]:
        req = CapabilityEvaluationRequest(
            capability_id=cap_id,
            entity_name="python",
            portal_type="individual",
        )
        resp = service.evaluate(req)
        assert len(resp.results) == 1
        res = resp.results[0]
        assert res.global_status == "building"
        assert res.runtime_status == "building"
        assert res.can_execute is False
        assert "FEATURE_NOT_IMPLEMENTED" in res.reason_codes
        assert len(res.missing_requirements) > 0


# =============================================================================
# 4. ENTITY RESOLUTION RUNTIME EVALUATION TESTS
# =============================================================================

def test_entity_resolution_runtime_evaluation():
    """Verify entity_resolution evaluation reflects exact, ambiguous, unknown, and missing inputs."""
    service = CapabilityRegistryService()

    # Exact valid entity
    res_exact = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="entity_resolution",
            entity_name="python",
        )
    ).results[0]
    assert res_exact.runtime_status == "available"
    assert res_exact.can_execute is True
    assert "ENTITY_RESOLVED" in res_exact.reason_codes

    # Ambiguous token without context
    res_ambig = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="entity_resolution",
            entity_name="c",
        )
    ).results[0]
    assert res_ambig.runtime_status == "partial"
    assert res_ambig.can_execute is True
    assert "AMBIGUOUS_ENTITY_CANDIDATES_AVAILABLE" in res_ambig.reason_codes

    # Unknown entity (no fabrication)
    res_unknown = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="entity_resolution",
            entity_name="nonexistent_xyz_framework_999",
        )
    ).results[0]
    assert res_unknown.runtime_status == "insufficient_data"
    assert res_unknown.can_execute is False
    assert "ENTITY_NOT_FOUND" in res_unknown.reason_codes

    # Missing entity name
    res_missing = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="entity_resolution",
            entity_name="",
        )
    ).results[0]
    assert res_missing.runtime_status == "insufficient_data"
    assert res_missing.can_execute is False
    assert "MISSING_REQUIRED_INPUT" in res_missing.reason_codes


# =============================================================================
# 5. REFERENCE TAXONOMY & OCCUPATION LOOKUP TESTS
# =============================================================================

def test_occupation_and_crosswalk_runtime_evaluation():
    """Verify occupation lookup, software crosswalk, and related occupations evaluate real O*NET data."""
    service = CapabilityRegistryService()

    # Software Developers SOC
    soc = "15-1252.00"

    # 1. Occupation lookup
    res_occ = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="occupation_lookup",
            entity_name=soc,
        )
    ).results[0]
    assert res_occ.runtime_status == "available"
    assert res_occ.can_execute is True
    assert "OCCUPATION_FOUND" in res_occ.reason_codes

    # 2. Software skills crosswalk
    res_sw = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="occupation_software_skills",
            entity_name=soc,
        )
    ).results[0]
    assert res_sw.runtime_status == "available"
    assert res_sw.can_execute is True
    assert "CROSSWALK_AVAILABLE" in res_sw.reason_codes

    # 3. Related occupations crosswalk
    res_rel = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="related_occupations",
            entity_name=soc,
        )
    ).results[0]
    assert res_rel.runtime_status == "available"
    assert res_rel.can_execute is True
    assert "RELATED_OCCUPATIONS_AVAILABLE" in res_rel.reason_codes

    # 4. Nonexistent SOC
    res_bad = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="occupation_lookup",
            entity_name="99-9999.99",
        )
    ).results[0]
    assert res_bad.runtime_status == "insufficient_data"
    assert res_bad.can_execute is False


# =============================================================================
# 6. ANALYTICAL READINESS & TREND GATE REUSE TESTS
# =============================================================================

def _build_observation(skill: str, period: str, value: float, obs_id: str) -> MarketObservation:
    dt = datetime.strptime(f"{period}-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return MarketObservation(
        id=obs_id,
        skill=skill,
        source="jsearch",
        signal_type="demand",
        value=value,
        observed_at=dt,
        period=period,
        scope="country",
        panel_version="job-demand-v1",
        data_origin="real",
        history_type="platform_collected",
    )


def test_trend_velocity_gate_reuse_and_continuity():
    """Verify trend_velocity_analysis strictly enforces >=4 consecutive periods and blocks gaps/drift."""
    service = CapabilityRegistryService()

    # Case A: 4 strictly consecutive valid periods -> available
    obs_4 = [
        _build_observation("python", "2026-01", 100.0, "obs_1"),
        _build_observation("python", "2026-02", 110.0, "obs_2"),
        _build_observation("python", "2026-03", 120.0, "obs_3"),
        _build_observation("python", "2026-04", 130.0, "obs_4"),
    ]
    res_trend_ready = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="trend_velocity_analysis",
            entity_name="python",
            observations=obs_4,
        )
    ).results[0]
    assert res_trend_ready.runtime_status == "available"
    assert res_trend_ready.can_execute is True
    assert "READY_FOR_TREND" in res_trend_ready.reason_codes
    assert res_trend_ready.readiness_state == "ready_for_trend"

    # Case B: Only 2 periods -> insufficient_data
    obs_2 = [
        _build_observation("python", "2026-01", 100.0, "obs_1"),
        _build_observation("python", "2026-02", 110.0, "obs_2"),
    ]
    res_insufficient = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="trend_velocity_analysis",
            entity_name="python",
            observations=obs_2,
        )
    ).results[0]
    assert res_insufficient.runtime_status == "insufficient_data"
    assert res_insufficient.can_execute is False
    assert "INSUFFICIENT_PERIODS_FOR_TREND" in res_insufficient.reason_codes

    # Case C: Discontinuous series with a gap (2026-01 and 2026-03, missing 2026-02) -> blocked
    obs_gap = [
        _build_observation("python", "2026-01", 100.0, "obs_1"),
        _build_observation("python", "2026-03", 120.0, "obs_3"),
    ]
    res_blocked = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="trend_velocity_analysis",
            entity_name="python",
            observations=obs_gap,
        )
    ).results[0]
    assert res_blocked.runtime_status == "blocked"
    assert res_blocked.can_execute is False
    assert "BLOCKED_BY_READINESS_GATE" in res_blocked.reason_codes
    assert res_blocked.readiness_state == "blocked_missing_period"

    # Case D: Zero observations -> insufficient_data
    res_empty = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="trend_velocity_analysis",
            entity_name="python",
            observations=[],
        )
    ).results[0]
    assert res_empty.runtime_status == "insufficient_data"
    assert res_empty.can_execute is False
    assert "NO_OBSERVATIONS_FOR_SERIES" in res_empty.reason_codes


def test_globally_available_capability_unready_for_entity():
    """Verify a globally available capability is distinguished from entity-level unreadiness."""
    service = CapabilityRegistryService()

    # Trend velocity analysis is globally 'available'
    cap_record = service.get_capability("trend_velocity_analysis")
    assert cap_record is not None
    assert cap_record.global_status == "available"

    # But evaluated for an entity with 0 observations, runtime_status is 'insufficient_data'
    eval_resp = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="trend_velocity_analysis",
            entity_name="quantum_computing",
            observations=[],
        )
    )
    result = eval_resp.results[0]
    assert result.global_status == "available"
    assert result.runtime_status == "insufficient_data"
    assert result.can_execute is False


# =============================================================================
# 7. PARTIAL CAPABILITY EVALUATION TESTS
# =============================================================================

def test_partial_capabilities_evaluation():
    """Verify partial capabilities evaluate scope limitations accurately."""
    service = CapabilityRegistryService()

    # Skill gap analysis with complete context
    res_gap_ok = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="skill_gap_role_fit",
            target_role="Software Developer",
            selected_skills=["python", "docker"],
        )
    ).results[0]
    assert res_gap_ok.global_status == "partial"
    assert res_gap_ok.runtime_status == "partial"
    assert res_gap_ok.can_execute is True
    assert "HEURISTIC_GAP_ANALYSIS_READY" in res_gap_ok.reason_codes

    # Skill gap analysis missing selected_skills
    res_gap_missing = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="skill_gap_role_fit",
            target_role="Software Developer",
            selected_skills=[],
        )
    ).results[0]
    assert res_gap_missing.runtime_status == "partial"
    assert res_gap_missing.can_execute is False
    assert "selected_skills" in res_gap_missing.missing_requirements

    # Job postings search with valid query
    res_job_ok = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="job_posting_search",
            entity_name="python",
        )
    ).results[0]
    assert res_job_ok.runtime_status == "available"
    assert res_job_ok.can_execute is True

    # Job postings search with 1-character query (too short)
    res_job_short = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="job_posting_search",
            entity_name="p",
        )
    ).results[0]
    assert res_job_short.runtime_status == "blocked"
    assert res_job_short.can_execute is False
    assert "QUERY_TOO_SHORT" in res_job_short.reason_codes

    # Company intelligence with company portal
    res_comp_ok = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="company_intelligence",
            portal_type="company",
            context_override={"company_id": "org_456"},
        )
    ).results[0]
    assert res_comp_ok.runtime_status == "partial"
    assert res_comp_ok.can_execute is True

    # Company intelligence in individual portal without company context
    res_comp_missing = service.evaluate(
        CapabilityEvaluationRequest(
            capability_id="company_intelligence",
            portal_type="individual",
        )
    ).results[0]
    assert res_comp_missing.runtime_status == "insufficient_data"
    assert res_comp_missing.can_execute is False


# =============================================================================
# 8. DETERMINISM TEST
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
# 9. API ENDPOINTS INTEGRATION TESTS
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
        assert cat_data["total_capabilities"] == 15
        assert cat_data["available_count"] == 10
        assert cat_data["partial_count"] == 3
        assert cat_data["building_count"] == 2
        assert len(cat_data["capabilities"]) == 15

        # 2. POST /api/v1/intelligence/capabilities/evaluate
        eval_resp = client.post(
            "/api/v1/intelligence/capabilities/evaluate",
            json={
                "capability_id": "entity_resolution",
                "entity_name": "python",
                "portal_type": "individual",
            },
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert len(eval_data["results"]) == 1
        res = eval_data["results"][0]
        assert res["capability_id"] == "entity_resolution"
        assert res["runtime_status"] == "available"
        assert res["can_execute"] is True
        assert "ENTITY_RESOLVED" in res["reason_codes"]

        # 3. POST evaluate building capability
        eval_build = client.post(
            "/api/v1/intelligence/capabilities/evaluate",
            json={
                "capability_id": "skill_forecasting_half_life",
                "entity_name": "python",
            },
        )
        assert eval_build.status_code == 200
        build_data = eval_build.json()["results"][0]
        assert build_data["global_status"] == "building"
        assert build_data["runtime_status"] == "building"
        assert build_data["can_execute"] is False
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)

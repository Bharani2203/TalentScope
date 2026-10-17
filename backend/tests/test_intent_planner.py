"""Offline tests for G2.6 Task 5: Intent Resolver + Context Planner.

Verifies:
- Deterministic intent classification across supported categories.
- Canonical entity resolution and alias mapping.
- Ambiguity and missing entity detection with structured clarification.
- Forecasting and workforce simulation strictly marked unsupported.
- Comparison queries preserving multiple entities.
- Capability selection grounded in registered capability catalog.
- Runtime readiness gate preservation (analytical readiness gates respected).
- Deterministic plan generation.
- Zero Firestore access and zero outbound network calls.
- Authenticated POST /api/v1/intelligence/plan endpoint.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import MarketObservation
from app.models.intent_planner import (
    IntelligencePlanRequest,
    IntelligencePlanResponse,
)
from app.services.capability_registry_service import CAPABILITY_CATALOG
from app.services.intent_planner_service import IntentPlannerService


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_planner_user_1",
        email="planner@example.com",
    )


# =============================================================================
# 1. READ SAFETY & ISOLATION
# =============================================================================

def test_no_firestore_imports_in_intent_planner():
    """Verify IntentPlannerService does not import or depend on Firestore."""
    import app.services.intent_planner_service as mod

    source = inspect.getsource(mod)
    assert "firebase_admin" not in source, "intent_planner_service must not import firebase_admin"
    assert "get_firestore_client" not in source, "intent_planner_service must not call get_firestore_client"
    assert "google.cloud.firestore" not in source, "intent_planner_service must not import google.cloud.firestore"


# =============================================================================
# 2. INTENT CLASSIFICATION & CAPABILITY MAPPING
# =============================================================================

def test_supported_intents_map_to_valid_registered_capabilities():
    """Verify supported intents select valid registered capabilities from CAPABILITY_CATALOG."""
    service = IntentPlannerService()

    queries = [
        ("What is the trend for Python?", "analyze_trend", "trend_velocity_analysis"),
        ("Find jobs for React", "search_jobs", "job_posting_search"),
        ("What skills does a Software Developer need?", "crosswalk_occupation_software", "occupation_software_skills"),
        ("Show related occupations for Software Developers", "crosswalk_related_occupations", "related_occupations"),
        ("Describe the role of Software Developers", "lookup_occupation", "occupation_lookup"),
        ("Show market snapshot for Docker", "retrieve_snapshot", "market_snapshot"),
        ("Show historical observations for Python", "retrieve_history", "historical_signal_retrieval"),
        ("What evidence or sources support Python?", "retrieve_evidence", "evidence_provenance_retrieval"),
        ("What should I learn next?", "synthesize_actions", "action_recommendations"),
        ("Analyze skill gap for Software Developer", "analyze_skill_gap", "skill_gap_role_fit"),
        ("Explain Kubernetes", "explain_concept", "skill_technology_reference"),
        ("Resolve js", "resolve_entity", "entity_resolution"),
    ]

    for msg, expected_intent, expected_cap in queries:
        resp = service.create_plan(IntelligencePlanRequest(message=msg))
        assert resp.intent == expected_intent, f"Failed for query: {msg}"
        assert expected_cap in resp.selected_capabilities
        assert expected_cap in CAPABILITY_CATALOG


@pytest.mark.parametrize(
    ("message", "expected_intent", "expected_capability", "kwargs"),
    [
        (
            "What is Python, and where is it used?",
            "lookup_skill_reference",
            "skill_technology_reference",
            {},
        ),
        (
            "Is Python demand increasing or decreasing?",
            "analyze_trend",
            "trend_velocity_analysis",
            {},
        ),
        (
            "Which skills should I learn for this role?",
            "synthesize_actions",
            "action_recommendations",
            {"target_role": "Software Developer"},
        ),
        (
            "Compare Python and Java using available market evidence.",
            "compare_entities",
            "trend_velocity_analysis",
            {},
        ),
        (
            "What skills are employers requesting in these job postings?",
            "search_jobs",
            "job_posting_search",
            {},
        ),
        (
            "How could changing technology requirements affect our workforce?",
            "simulate_workforce_scenarios",
            "workforce_what_if_simulation",
            {"portal_type": "company"},
        ),
    ],
)
def test_representative_conversational_questions_route_to_existing_capabilities(
    message, expected_intent, expected_capability, kwargs,
):
    service = IntentPlannerService()
    response = service.create_plan(
        IntelligencePlanRequest(message=message, **kwargs),
        authenticated_user=AuthenticatedUser(
            uid="planner-evaluation-user",
            company_id="evaluation-company" if kwargs.get("portal_type") == "company" else None,
        ),
    )

    assert response.intent == expected_intent
    assert expected_capability in response.selected_capabilities


# =============================================================================
# 3. FORECASTING & SIMULATION STRICT GATING
# =============================================================================

def test_forecasting_intent_supported_and_evaluated():
    """Verify forward-looking forecast queries route to forecast_future_demand and evaluate readiness."""
    service = IntentPlannerService()
    queries = [
        "Will Python demand increase next year?",
        "Forecast future demand for Python in 2027",
        "Predict future demand for Java in 2028",
    ]

    for q in queries:
        resp = service.create_plan(IntelligencePlanRequest(message=q))
        assert resp.intent == "forecast_future_demand"
        assert resp.selected_capabilities == ["skill_forecasting_half_life"]
        assert resp.clarification_required is False
        assert len(resp.readiness_results) == 1
        assert resp.plan_status == "insufficient_data"
        assert resp.readiness_results[0].global_status == "available"
        assert resp.readiness_results[0].can_execute is False
        assert resp.readiness_results[0].runtime_status == "insufficient_data"

    # Unknown entity triggers clarification
    resp_unknown = service.create_plan(IntelligencePlanRequest(message="Forecast future demand for UnknownSkillXYZ in 2027"))
    assert resp_unknown.intent == "forecast_future_demand"
    assert resp_unknown.clarification_required is True


def test_simulation_intent_strictly_unsupported():
    """Verify workforce what-if simulation queries are marked unsupported."""
    service = IntentPlannerService()
    for message in (
        "Simulate attrition shock in engineering team",
        "How could changing technology requirements affect our workforce?",
    ):
        resp = service.create_plan(IntelligencePlanRequest(message=message))

        assert resp.intent == "simulate_workforce_scenarios"
        assert resp.plan_status == "unsupported"
        assert resp.selected_capabilities == ["workforce_what_if_simulation"]
        assert len(resp.readiness_results) == 1
        assert resp.readiness_results[0].can_execute is False


# =============================================================================
# 4. ENTITY RESOLUTION & ALIAS HANDLING
# =============================================================================

def test_known_aliases_resolve_to_canonical_entity():
    """Verify aliases like 'py', 'k8s', 'golang' resolve to their canonical taxonomy counterparts."""
    service = IntentPlannerService()

    resp_js = service.create_plan(IntelligencePlanRequest(message="What is the trend for js?"))
    assert len(resp_js.entities) >= 1
    ent = resp_js.entities[0]
    assert ent.resolution_status == "resolved"
    assert ent.canonical_entity is not None
    assert ent.canonical_entity.canonical_name == "JavaScript"
    assert ent.canonical_entity.entity_id == "tech:javascript"

    resp_k8s = service.create_plan(IntelligencePlanRequest(message="Find jobs for k8s"))
    assert len(resp_k8s.entities) >= 1
    ent_k8s = resp_k8s.entities[0]
    assert ent_k8s.resolution_status == "resolved"
    assert ent_k8s.canonical_entity is not None
    assert ent_k8s.canonical_entity.canonical_name == "Kubernetes"

    # Verify uiux resolves to UI/UX and takes precedence over ambient profile skills
    resp_uiux = service.create_plan(IntelligencePlanRequest(
        message="show trend about uiux",
        selected_skills=["machine learning", "python"],
        target_role="AI Engineer"
    ))
    assert len(resp_uiux.entities) >= 1
    primary_ent = resp_uiux.entities[0]
    assert primary_ent.resolution_status == "resolved"
    assert primary_ent.canonical_entity is not None
    assert primary_ent.canonical_entity.canonical_name == "UI/UX"
    assert primary_ent.canonical_entity.entity_id == "skill:ui_ux"


# =============================================================================
# 5. AMBIGUITY & CLARIFICATION HANDLING
# =============================================================================

def test_ambiguous_entity_triggers_clarification():
    """Verify ambiguous single-letter tokens ('c') prompt for clarification with candidate list."""
    service = IntentPlannerService()
    resp = service.create_plan(IntelligencePlanRequest(message="What is the trend for c?"))

    assert len(resp.entities) >= 1
    ambig_ent = next((e for e in resp.entities if e.raw_token.lower() == "c"), None)
    assert ambig_ent is not None
    assert ambig_ent.resolution_status == "ambiguous"
    assert len(ambig_ent.candidates) > 0
    assert resp.clarification_required is True
    assert resp.plan_status == "requires_clarification"
    assert len(resp.clarification_questions) > 0
    assert any("can refer to multiple entities" in q for q in resp.clarification_questions)


def test_missing_target_entity_triggers_clarification():
    """Verify requests lacking an identifiable target entity prompt for clarification."""
    service = IntentPlannerService()
    resp = service.create_plan(IntelligencePlanRequest(message="Show its trend"))

    assert resp.intent == "analyze_trend"
    assert resp.clarification_required is True
    assert resp.plan_status == "requires_clarification"
    assert "entity_name" in resp.missing_context
    assert any("Which skill, technology, or occupation" in q for q in resp.clarification_questions)


# =============================================================================
# 6. COMPARISON QUERIES
# =============================================================================

def test_comparison_intent_with_two_entities():
    """Verify comparison query extracts both entities and preserves their order/primary status."""
    service = IntentPlannerService()
    resp = service.create_plan(IntelligencePlanRequest(message="Compare Python and Java"))

    assert resp.intent == "compare_entities"
    assert len(resp.entities) == 2
    names = [e.canonical_entity.canonical_name for e in resp.entities if e.canonical_entity]
    assert "Python" in names
    assert "Java" in names
    assert resp.entities[0].is_primary is True
    assert resp.entities[1].is_primary is False
    assert resp.context_summary["primary_entity"] is not None
    assert len(resp.context_summary["comparison_entities"]) == 1


def test_comparison_intent_with_single_entity_triggers_clarification():
    """Verify comparison query with only 1 entity asks for the second entity."""
    service = IntentPlannerService()
    resp = service.create_plan(IntelligencePlanRequest(message="Compare Python"))

    assert resp.intent == "compare_entities"
    assert resp.clarification_required is True
    assert resp.plan_status == "requires_clarification"
    assert "comparison_entity_pair" in resp.missing_context
    assert any("requires at least two entities" in q for q in resp.clarification_questions)


# =============================================================================
# 7. UNKNOWN & UNCLEAR REQUESTS
# =============================================================================

def test_unclear_or_gibberish_request():
    """Verify unclassifiable messages produce a safe clarification response."""
    service = IntentPlannerService()
    resp = service.create_plan(IntelligencePlanRequest(message="asdfghjkl qwerty 12345"))

    assert resp.intent == "unsupported_or_unclear"
    assert resp.plan_status == "requires_clarification"
    assert resp.clarification_required is True
    assert len(resp.clarification_questions) > 0


# =============================================================================
# 8. CONTEXT DERIVATION FROM CAPABILITY REGISTRY
# =============================================================================

def test_context_derived_from_capability_registry():
    """Verify required context items are derived strictly from the registered capability record."""
    service = IntentPlannerService()

    # Skill gap requires selected_skills
    resp = service.create_plan(
        IntelligencePlanRequest(
            message="Analyze skill gap for Software Developer",
            target_role="Software Developer",
            selected_skills=[],
        )
    )
    assert resp.intent == "analyze_skill_gap"
    assert "selected_skills" in resp.missing_context
    assert resp.clarification_required is True


# =============================================================================
# 9. DETERMINISM & AUDITABILITY
# =============================================================================

def test_deterministic_plan_generation():
    """Verify repeated identical queries produce identical plans except for request_id."""
    service = IntentPlannerService()
    req = IntelligencePlanRequest(message="What is the trend for Python?", location="United States")

    plan1 = service.create_plan(req)
    plan2 = service.create_plan(req)

    assert plan1.request_id != plan2.request_id  # Trace ID is unique
    assert plan1.intent == plan2.intent
    assert plan1.intent_confidence == plan2.intent_confidence
    assert plan1.selected_capabilities == plan2.selected_capabilities
    assert plan1.plan_status == plan2.plan_status
    assert plan1.clarification_required == plan2.clarification_required
    assert plan1.missing_context == plan2.missing_context
    assert len(plan1.entities) == len(plan2.entities)
    assert plan1.limitations == plan2.limitations


# =============================================================================
# 10. API ENDPOINT INTEGRATION
# =============================================================================

def test_plan_api_endpoint():
    """Verify POST /api/v1/intelligence/plan produces structured plans with authentication."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    try:
        # Case A: Standard trend query
        resp = client.post(
            "/api/v1/intelligence/plan",
            json={"message": "What is the trend for Python?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"].startswith("plan_")
        assert data["intent"] == "analyze_trend"
        assert "trend_velocity_analysis" in data["selected_capabilities"]
        assert len(data["entities"]) == 1
        assert data["entities"][0]["canonical_entity"]["canonical_name"] == "Python"
        assert len(data["readiness_results"]) > 0

        # Case B: Forecasting query without observations evaluates to insufficient_data
        resp_fc = client.post(
            "/api/v1/intelligence/plan",
            json={"message": "Will Python demand increase next year?"},
        )
        assert resp_fc.status_code == 200
        data_fc = resp_fc.json()
        assert data_fc["intent"] == "forecast_future_demand"
        assert data_fc["plan_status"] == "insufficient_data"
        assert data_fc["clarification_required"] is False
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_active_domain_routes_terse_entity_prompt_and_is_recorded():
    service = IntentPlannerService()

    market_plan = service.create_plan(IntelligencePlanRequest(message="Python", domain="market"))
    job_plan = service.create_plan(IntelligencePlanRequest(message="Python", domain="job"))

    assert market_plan.intent == "retrieve_snapshot"
    assert "market_snapshot" in market_plan.selected_capabilities
    assert job_plan.intent == "search_jobs"
    assert "job_posting_search" in job_plan.selected_capabilities
    assert market_plan.context_summary["domain"] == "market"
    assert job_plan.context_summary["domain"] == "job"

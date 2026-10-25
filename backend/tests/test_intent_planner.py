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
from app.api.routes import core_intelligence
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import MarketObservation
from app.models.intent_planner import (
    IntelligencePlanRequest,
    IntelligencePlanResponse,
)
from app.services.capability_registry_service import CAPABILITY_CATALOG
from app.services.intent_planner_service import IntentPlannerService
from app.intelligence_v2.intent_planner import V2IntentPlanner


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


def test_selected_feature_executes_when_question_matches():
    response = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message="What demand trend is observed for Python?",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ))
    assert response.intent == "analyze_trend"
    assert response.selected_capabilities == ["trend_velocity_analysis"]
    assert response.primary_capability == "trend_velocity_analysis"
    assert response.dependency_capabilities == []
    assert not response.clarification_required


@pytest.mark.parametrize("domain", ["skill", "auto"])
def test_selected_feature_is_used_when_question_intent_is_ambiguous(domain):
    response = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message="Can you look at Python?",
        domain=domain,
        capability_id="trend_velocity_analysis",
    ))
    assert response.selected_capabilities == ["trend_velocity_analysis"]
    assert response.primary_capability == "trend_velocity_analysis"
    assert not response.clarification_required


@pytest.mark.parametrize(
    ("message", "domain", "selected"),
    [
        ("Show the canonical definition and category for Python.", "skill", "trend_velocity_analysis"),
        ("What demand trend is observed for Python?", "skill", "skill_technology_reference"),
        ("Which companies are hiring Python developers?", "job", "trend_velocity_analysis"),
        ("What are the latest UI/UX design trends?", "skill", "trend_velocity_analysis"),
    ],
)
def test_conflicting_question_clarifies_without_substituting_selected_feature(message, domain, selected):
    response = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message=message,
        domain=domain,
        capability_id=selected,
    ))
    assert response.intent == "unsupported_or_unclear"
    assert response.selected_capabilities == []
    assert response.primary_capability is None
    assert response.clarification_required
    assert response.plan_status == "requires_clarification"


@pytest.mark.usefixtures("injected_empty_firestore")
def test_explicit_entity_switch_does_not_reuse_prior_entity_context():
    from app.storage.conversation_store import ConversationStore

    store = ConversationStore.get_instance()
    conversation_id = "r1-entity-switch-test"
    user_id = "r1-entity-switch-user"
    try:
        store.create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            portal_type="individual",
            domain="skill",
        )
        store.save_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            portal_type="individual",
            domain="skill",
            user_message="What demand trend is observed for Python?",
            intent="analyze_trend",
            primary_entity="Python",
            resolved_entities=["Python"],
            comparison_entities=[],
            target_role=None,
            time_range="max_available",
            selected_skills=[],
            selected_companies=[],
            filters={},
            execution_status="completed",
            answer_summary="Prior Python result",
        )

        switched_domain = store.resolve_follow_up(
            "What about this?",
            conversation_id,
            user_id=user_id,
            domain="job",
            portal_type="individual",
        )
        assert switched_domain == (None, [], None, None)

        response = IntentPlannerService().create_plan(IntelligencePlanRequest(
            message="What demand trend is observed for Java?",
            conversation_id=conversation_id,
            domain="skill",
        ), authenticated_user=AuthenticatedUser(uid=user_id, email="r1@example.com"))

        names = [item.canonical_entity.canonical_name for item in response.entities if item.canonical_entity]
        assert "Java" in names
        assert response.context_summary.get("primary_entity") != "Python"
    finally:
        with store._access_lock:
            store._conversations.pop(conversation_id, None)


def test_explicit_employer_question_outside_skill_domain_requests_clarification():
    response = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message="Which companies are hiring Python developers?",
        domain="skill",
        capability_id="skill_health_analysis",
    ))
    assert response.plan_status == "requires_clarification"
    assert response.selected_capabilities == []
    assert response.clarification_questions


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
        # /plan now reports the canonical V2 capability so it matches /answer.
        assert "skill_demand_trends" in data["selected_capabilities"]
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


def test_plan_api_returns_legacy_plan_when_v2_canonicalization_fails(monkeypatch, caplog):
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user

    def fail_v2_plan(*_args, **_kwargs):
        raise RuntimeError("mock planner failure detail")

    monkeypatch.setattr(core_intelligence._V2_INTENT_PLANNER, "plan", fail_v2_plan)
    client = TestClient(app)
    try:
        with caplog.at_level("WARNING", logger="app.api.routes.core_intelligence"):
            response = client.post(
                "/api/v1/intelligence/plan",
                json={"message": "What is the trend for Python?"},
            )
        assert response.status_code == 200
        plan = response.json()
        assert plan["intent"] == "analyze_trend"
        assert plan["primary_capability"] == "trend_velocity_analysis"
        assert "trend_velocity_analysis" in plan["selected_capabilities"]
        assert "RuntimeError" in caplog.text
        assert "mock planner failure detail" not in caplog.text
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


@pytest.mark.parametrize(
    ("message", "workspace_domain", "expected_capability"),
    [
        ("Find data engineer jobs in Bangalore", "skill", "job_verified_postings"),
        ("Is Python becoming more popular?", "job", "skill_demand_trends"),
        ("What does a data engineer do?", "market", "skill_lookup"),
        ("role of a data engineer", "skill", "skill_lookup"),
        ("responsibilities of a backend developer", "market", "skill_lookup"),
        ("What does a data analyst do?", "job", "skill_lookup"),
        ("What skills does a data engineer need?", "market", "job_role_requirements"),
        ("Find python developer jobs in Chennai", "skill", "job_verified_postings"),
        ("Is React growing?", "job", "skill_demand_trends"),
        ("Compare Python and Java", "market", None),
    ],
)
def test_v2_routing_uses_question_with_mismatched_workspace_domain(
    message: str,
    workspace_domain: str,
    expected_capability: str | None,
):
    plan = V2IntentPlanner().plan(message, context={"domain": workspace_domain})
    assert plan.capability_id == expected_capability

    if message == "Compare Python and Java":
        assert "not supported yet" in plan.reason.casefold()
        assert "separate trend lookups for python and java" in plan.reason.casefold()

    if message.startswith("Find data engineer jobs"):
        intent_plan = IntentPlannerService().create_plan(
            IntelligencePlanRequest(message=message, domain=workspace_domain)
        )
        assert intent_plan.intent == "search_jobs"


@pytest.mark.parametrize("message", ["asdfghjkl qwerty 12345", "what is the weather"])
def test_v2_unrecognized_question_requests_clarification_without_data_capability(message: str):
    plan = V2IntentPlanner().plan(message, context={"domain": "market"})
    assert plan.capability_id is None
    assert plan.reason == "Would you like help with skills, jobs, market signals, or role information?"


def test_workspace_domain_does_not_change_routing_for_terse_prompt():
    service = IntentPlannerService()

    market_plan = service.create_plan(IntelligencePlanRequest(message="Python", domain="market"))
    job_plan = service.create_plan(IntelligencePlanRequest(message="Python", domain="job"))

    assert market_plan.intent == job_plan.intent == "lookup_skill_reference"
    assert market_plan.selected_capabilities == job_plan.selected_capabilities == ["skill_technology_reference"]
    assert market_plan.context_summary["domain"] is None
    assert job_plan.context_summary["domain"] is None


@pytest.mark.parametrize(
    ("message", "domain", "intent", "capability"),
    [
        ("What is Python used for?", "skill", "general_explanation", None),
        ("Explain UI/UX trends in simple terms", "skill", "aggregate_posting_skills", "collected_posting_skills"),
        ("What is the difference between Java and Python?", "skill", "general_explanation", None),
        ("Show the canonical definition and category for Python", "skill", "lookup_skill_reference", "skill_technology_reference"),
        ("What demand trend is observed for Python?", "skill", "analyze_trend", "trend_velocity_analysis"),
        ("Which companies are hiring Python developers?", "skill", "search_jobs", "job_posting_search"),
        ("What skills should I learn for a backend developer role?", "skill", "synthesize_actions", "action_recommendations"),
        ("Which skills am I missing for a backend developer job?", "skill", "analyze_skill_gap", "skill_gap_role_fit"),
        ("Create a learning path for Python backend development", "skill", "synthesize_actions", "action_recommendations"),
    ],
)
def test_r1_4_intent_paraphrases(message, domain, intent, capability):
    plan = IntentPlannerService().create_plan(IntelligencePlanRequest(message=message, domain=domain))
    assert plan.intent == intent
    if capability:
        assert capability in plan.selected_capabilities
    if message.startswith("Which companies"):
        assert not any("Switch to the Job domain" in q for q in plan.clarification_questions)


def test_learning_intent_conflicts_with_selected_trend_feature_and_clarifies():
    plan = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message="What skills should I learn for a backend developer role?",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ))
    assert plan.intent == "unsupported_or_unclear"
    assert plan.selected_capabilities == []
    assert plan.clarification_required


@pytest.mark.usefixtures("injected_empty_firestore")
def test_explicit_learning_intent_conflicts_with_selected_trend_after_prior_context():
    from app.storage.conversation_store import ConversationStore

    store = ConversationStore.get_instance()
    conversation_id = "r14-learning-after-trend"
    user_id = "r14-learning-user"
    try:
        store.create_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            portal_type="individual",
            domain="skill",
        )
        store.save_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            portal_type="individual",
            domain="skill",
            user_message="What demand trend is observed for Python?",
            intent="analyze_trend",
            primary_entity="Python",
            resolved_entities=["Python"],
            comparison_entities=[],
            target_role=None,
            time_range="max",
            selected_skills=[],
            selected_companies=[],
            filters={},
            execution_status="completed",
            answer_summary="Prior trend result",
        )
        plan = IntentPlannerService().create_plan(IntelligencePlanRequest(
            message="What skills should I learn for a backend developer role?",
            conversation_id=conversation_id,
            domain="skill",
            capability_id="trend_velocity_analysis",
        ), authenticated_user=AuthenticatedUser(uid=user_id, email="r14@example.com"))
        assert plan.intent == "unsupported_or_unclear"
        assert plan.selected_capabilities == []
        assert plan.clarification_required
        assert plan.context_summary.get("primary_entity") != "Python"
    finally:
        with store._access_lock:
            store._conversations.pop(conversation_id, None)

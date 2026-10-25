"""Focused tests for the backend conversational orchestration contract."""

from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)
from app.models.intent_planner import IntelligencePlanRequest
from app.services.assistant_feature_registry import EXECUTABLE_FEATURES, HANDLER_METHODS
from app.services.capability_registry_service import CAPABILITY_CATALOG, CapabilityRegistryService
from app.services.execution_orchestrator_service import (
    ExecutionOrchestratorService,
    _answer_idempotency_key,
)
from app.services.intent_planner_service import IntentPlannerService


class MockGemini:
    def __init__(self, result=None, error=None):
        self.result = result
        self.last_error_class = error
        self.calls = 0

    def generate_structured_json(self, **_kwargs):
        self.calls += 1
        return self.result


def _structured(**overrides):
    result = {
        "intent": "search_jobs",
        "secondary_intents": ["analyze_skill_gap"],
        "features": ["job_posting_search"],
        "skills": ["Python"],
        "technologies": [],
        "role": "Data Engineer",
        "location": "Bengaluru",
    }
    result.update(overrides)
    return result


def test_structured_intent_uses_valid_registered_handler_and_entities():
    gemini = MockGemini(_structured())
    planner = IntentPlannerService(llm_service=gemini)
    plan = planner.create_plan(IntelligencePlanRequest(
        message="Can you find some roles for me?", domain="skill"
    ))

    assert gemini.calls == 1
    assert plan.intent == "search_jobs"
    assert plan.selected_capabilities == ["job_posting_search"]
    assert plan.context_summary["target_role"] == "Data Engineer"
    assert plan.secondary_intents == ["analyze_skill_gap"]
    assert plan.features_used == ["job_posting_search"]
    assert plan.understood
    assert plan.degraded is False


def test_invalid_gemini_feature_falls_back_to_rule_planner_and_degrades():
    gemini = MockGemini(_structured(features=["not_a_real_handler"]))
    planner = IntentPlannerService(llm_service=gemini)
    plan = planner.create_plan(IntelligencePlanRequest(
        message="What demand trend is observed for Python?", domain="market"
    ))

    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert plan.degraded is True
    assert plan.degraded_reason == "provider_error"


def test_unrecognized_provider_error_class_maps_to_contract_reason():
    gemini = MockGemini(error="AttributeError")
    planner = IntentPlannerService(llm_service=gemini)
    plan = planner.create_plan(IntelligencePlanRequest(message="What is Python used for?"))
    assert plan.degraded is True
    assert plan.degraded_reason == "provider_error"


def test_workspace_domain_does_not_change_feature_routing():
    outputs = []
    for domain in ("skill", "market", "job"):
        planner = IntentPlannerService(llm_service=MockGemini(error="unavailable"))
        outputs.append(planner.create_plan(IntelligencePlanRequest(
            message="What demand trend is observed for Python?", domain=domain
        )))

    assert {(item.intent, tuple(item.selected_capabilities)) for item in outputs} == {
        ("analyze_trend", ("trend_velocity_analysis",))
    }


def test_planned_future_relevance_and_full_roadmap_are_unavailable():
    for question, feature in (
        ("Give me a Future Relevance Score for Python", "skill_future_relevance_score"),
        ("Build a complete prerequisite roadmap for Data Engineer", "roadmap_prerequisite_full"),
    ):
        planner = IntentPlannerService(llm_service=MockGemini(error="unavailable"))
        plan = planner.create_plan(IntelligencePlanRequest(message=question))
        assert plan.plan_status == "unsupported"
        assert plan.selected_capabilities == [feature]
        assert any("not available yet" in item for item in plan.limitations)


def test_capability_catalog_only_marks_registered_handlers_available():
    catalog = CapabilityRegistryService().get_catalog()
    for capability in catalog.capabilities:
        assert bool(capability.handler) == (capability.capability_id in HANDLER_METHODS)
        assert (capability.global_status == "available") == bool(capability.handler)
    assert CAPABILITY_CATALOG["skill_future_relevance_score"].global_status == "building"
    assert CAPABILITY_CATALOG["workforce_what_if_simulation"].global_status == "building"
    assert "job_posting_search" in EXECUTABLE_FEATURES


def test_idempotency_key_includes_normalized_question():
    same_a = _answer_idempotency_key("u", "c", "m", "Find Python jobs")
    same_b = _answer_idempotency_key("u", "c", "m", "  FIND   PYTHON jobs ")
    different = _answer_idempotency_key("u", "c", "m", "Find Java jobs")
    assert same_a == same_b
    assert same_a != different


def test_answer_response_contract_uses_real_evidence_and_execution_metadata():
    service = object.__new__(ExecutionOrchestratorService)
    service.llm_service = MockGemini(error="unavailable")
    request = CoreIntelligenceAnswerRequest(message="Show job postings for Python")
    # The production helper receives the normal model shape; retain only fields
    # needed to verify metadata projection here.
    response = CoreIntelligenceAnswerResponse(
        request_id="test", user_message=request.message, portal_type="individual",
        intent="search_jobs", plan_status="ready_to_execute", execution_status="completed",
        status="ready", answer="Two postings were retrieved.",
        facts=[{"fact_type": "stored_job_postings", "metric_name": "posting_count", "metric_value": 2, "source": "JSearch"}],
        evidence=[{"evidence_id": "ev1", "source": "JSearch", "signal_type": "job_posting", "description": "Verified posting record."}],
        capabilities_used=["job_posting_search"], answer_origin="deterministic",
    )
    updated = service.apply_assistant_response_contract(response, request)

    assert updated.understood
    assert updated.enough_data is True
    assert updated.features_used == ["job_posting_search"]
    assert updated.sources[0].type == "job_posting"
    assert updated.degraded is True
    assert updated.degraded_reason == "unavailable"

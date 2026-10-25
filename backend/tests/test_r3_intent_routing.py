"""Offline regression coverage for the R3 natural-language routing scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.intent_planner import IntelligencePlanRequest
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import _offline_general_explanation
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationState, ConversationStore


@pytest.fixture
def offline_planner(tmp_path: Path) -> IntentPlannerService:
    # Entity resolution only reads a configured reference database when it exists.
    # Supplying an absent path and a reference-store sentinel prevents SQLite writes.
    entity_service = EntityRegistryService(db_path=tmp_path / "absent-reference.sqlite3")
    capability_service = CapabilityRegistryService(
        entity_service=entity_service,
        reference_store=object(),
    )
    return IntentPlannerService(
        entity_service=entity_service,
        capability_service=capability_service,
    )


@pytest.mark.parametrize(
    ("message", "domain", "intent", "capability"),
    [
        ("What is Python used for?", "skill", "general_explanation", None),
        ("Show the canonical definition and category for Python.", "skill", "lookup_skill_reference", "skill_technology_reference"),
        ("What demand trend is observed for Python?", "skill", "analyze_trend", "trend_velocity_analysis"),
        ("Which companies are hiring Python developers?", "job", "search_jobs", "job_posting_search"),
        ("What skills should I learn for a backend developer role?", "skill", "synthesize_actions", "action_recommendations"),
        ("What is the difference between Python and Java?", "skill", "general_explanation", None),
        ("Show historical observations for Python.", "skill", "retrieve_history", "historical_signal_retrieval"),
        ("What is the future demand for Python?", "skill", "forecast_future_demand", "skill_forecasting_half_life"),
    ],
)
def test_r3_fresh_question_routes_to_its_explicit_intent(
    offline_planner, message, domain, intent, capability
):
    plan = offline_planner.create_plan(IntelligencePlanRequest(message=message, domain=domain))

    assert plan.intent == intent
    assert plan.primary_capability == capability
    assert plan.selected_capabilities == ([capability] if capability else [])

    if intent == "lookup_skill_reference":
        assert plan.entities[0].canonical_entity.canonical_name == "Python"
        assert plan.selected_capabilities == ["skill_technology_reference"]
        assert "trend_velocity_analysis" not in plan.selected_capabilities
        assert "market_snapshot" not in plan.selected_capabilities
    elif intent == "analyze_trend":
        readiness = next(item for item in plan.readiness_results if item.capability_id == capability)
        assert readiness.can_execute is False
        assert "Zero observations found" in readiness.explanation
    elif intent == "forecast_future_demand":
        readiness = next(item for item in plan.readiness_results if item.capability_id == capability)
        assert readiness.can_execute is False
        assert readiness.runtime_status == "insufficient_data"


def test_r3_general_answers_are_explicitly_separate_from_platform_findings():
    answer = _offline_general_explanation("What is Python used for?")

    assert answer is not None
    assert "web services" in answer
    assert "not a TalentScope market finding" in answer


def test_r3_stale_python_trend_context_does_not_contaminate_role_learning(
    offline_planner, monkeypatch
):
    user_id = "r3-offline-user"
    conversation_id = "r3-offline-python-trend"
    store = ConversationStore()
    store._conversations[conversation_id] = ConversationState(
        conversation_id=conversation_id,
        user_id=user_id,
        portal_type="individual",
        domain="skill",
        active_entity="Python",
    )
    monkeypatch.setattr(
        ConversationStore,
        "get_instance",
        classmethod(lambda cls: store),
    )

    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="What skills should I learn for a backend developer role?",
        domain="skill",
        conversation_id=conversation_id,
    ))

    assert plan.intent == "synthesize_actions"
    assert plan.primary_capability == "action_recommendations"
    assert plan.context_summary["primary_entity"] != "Python"
    assert all(entity.raw_token.casefold() != "c" for entity in plan.entities)


def test_r3_selected_trend_feature_does_not_execute_an_unselected_learning_capability(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="What skills should I learn for a backend developer role?",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ))

    assert plan.intent == "unsupported_or_unclear"
    assert plan.primary_capability is None
    assert plan.selected_capabilities == []
    assert plan.plan_status == "requires_clarification"


def test_r3_skill_domain_does_not_add_domain_switch_instruction(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="Which companies are hiring Python developers?",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ))

    assert plan.intent == "unsupported_or_unclear"
    assert plan.plan_status == "requires_clarification"
    assert plan.selected_capabilities == []
    assert not any("Switch to the Job domain" in question for question in plan.clarification_questions)


def test_r3_genuine_ambiguous_entity_still_requests_disambiguation(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="What is the trend for C?",
        domain="skill",
    ))

    ambiguous = next(entity for entity in plan.entities if entity.raw_token.casefold() == "c")
    assert ambiguous.resolution_status == "ambiguous"
    assert ambiguous.candidates
    assert plan.clarification_required is True
    assert any("can refer to multiple entities" in q for q in plan.clarification_questions)


def test_r3_incidental_single_letter_is_not_extracted_as_an_entity(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="I heard C mentioned; what demand trend is observed for Python?",
        domain="skill",
    ))
    assert plan.entities
    assert plan.entities[0].raw_token.casefold() == "python"
    assert all(entity.raw_token.casefold() != "c" for entity in plan.entities)


def test_r3_explicit_comparison_keeps_ambiguous_c_for_clarification(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="Compare C and Python using available market evidence.",
        domain="skill",
    ))
    c_entity = next(entity for entity in plan.entities if entity.raw_token.casefold() == "c")
    assert c_entity.resolution_status == "ambiguous"
    assert c_entity.candidates
    assert plan.clarification_required


@pytest.mark.parametrize(
    ("domain", "message", "capability"),
    [
        ("skill", "What demand trend is observed for Python?", "trend_velocity_analysis"),
        ("skill", "What historical skill signals are available for Python?", "historical_signal_retrieval"),
        ("skill", "How do my selected skills align with Data Analyst?", "skill_gap_role_fit"),
        ("skill", "Show the evidence and sources for Python.", "evidence_provenance_retrieval"),
        ("skill", "Show the canonical definition and category for Python.", "skill_technology_reference"),
        ("skill", "What should I learn next based on evidence for Python?", "action_recommendations"),
        ("market", "What current market signals are available for Python?", "market_snapshot"),
        ("market", "What historical market signals are available for Python?", "historical_signal_retrieval"),
        ("market", "What trend is observed for Python?", "trend_velocity_analysis"),
        ("market", "Show the evidence and sources for Python.", "evidence_provenance_retrieval"),
        ("job", "Show stored job postings for Data Analyst.", "job_posting_search"),
        ("job", "What software skills are used in Data Analyst?", "occupation_software_skills"),
        ("job", "What occupations are related to Data Analyst?", "related_occupations"),
        ("job", "How do my selected skills align with Data Analyst?", "skill_gap_role_fit"),
        ("job", "What should I do next to prepare for Data Analyst?", "action_recommendations"),
    ],
)
def test_r3_all_current_feature_prompts_keep_the_selected_capability(
    offline_planner, domain, message, capability
):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message=message,
        domain=domain,
        capability_id=capability,
    ))
    assert plan.primary_capability == capability
    assert plan.selected_capabilities == [capability]


@pytest.mark.parametrize(
    ("message", "domain", "intent", "capability"),
    [
        ("What is the Python skill in ESCO?", "skill", "lookup_skill_reference", "skill_technology_reference"),
        ("What skills are associated with a Data Analyst?", "job", "crosswalk_occupation_software", "occupation_software_skills"),
        ("Which skills are growing in demand?", "market", "rank_skill_trends", "trend_velocity_analysis"),
        ("Is Python demand increasing or decreasing?", "market", "analyze_trend", "trend_velocity_analysis"),
        ("Find jobs requiring Python.", "job", "search_jobs", "job_posting_search"),
        ("Which skills appear in these job postings?", "job", "search_jobs", "job_posting_search"),
        ("What skills should I improve for a Data Analyst role?", "skill", "synthesize_actions", "action_recommendations"),
    ],
)
def test_phase10_unified_question_routing_matrix(offline_planner, message, domain, intent, capability):
    plan = offline_planner.create_plan(IntelligencePlanRequest(message=message, domain=domain))

    assert plan.intent == intent
    assert plan.selected_capabilities == [capability]
    assert plan.primary_capability == capability
    if capability == "occupation_software_skills":
        # This isolated planner intentionally has no O*NET reference database.
        assert plan.clarification_required is True
        assert plan.readiness_results[0].runtime_status == "insufficient_data"
    elif message == "What is the Python skill in ESCO?":
        # This fixture intentionally has no ESCO reference database, so it asks
        # for the missing taxonomy entity instead of implying lookup succeeded.
        assert plan.clarification_required is True
    elif message == "Which skills appear in these job postings?" or capability == "action_recommendations":
        # These handlers need a concrete search entity or target role.
        assert plan.clarification_required is True
    else:
        assert plan.clarification_required is False
    assert len(plan.readiness_results) == 1
    assert plan.readiness_results[0].capability_id == capability
    if intent in {"analyze_trend", "rank_skill_trends"}:
        assert plan.readiness_results[0].can_execute is False
        assert plan.readiness_results[0].runtime_status == "insufficient_data"
    if intent == "search_jobs":
        assert "stored" in " ".join(plan.limitations).lower() or plan.readiness_results[0].runtime_status in {"available", "insufficient_data"}


def test_phase10_onet_occupation_wording_routes_to_existing_reference_capability(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="Which skills are associated with a Data Analyst in O*NET?",
        domain="job",
    ))

    assert plan.intent == "crosswalk_occupation_software"
    assert plan.selected_capabilities == ["occupation_software_skills"]
    assert plan.entities and plan.entities[0].raw_token.casefold() == "data analyst"


def test_phase10_explicit_cross_domain_question_is_not_silently_partially_routed(offline_planner):
    plan = offline_planner.create_plan(IntelligencePlanRequest(
        message="What is the Python skill in ESCO and is its market demand increasing?",
        domain="skill",
    ))

    assert plan.intent == "unsupported_or_unclear"
    assert plan.selected_capabilities == []
    assert plan.plan_status == "requires_clarification"
    assert plan.clarification_required is True
    assert "split it into separate questions" in " ".join(plan.clarification_questions)

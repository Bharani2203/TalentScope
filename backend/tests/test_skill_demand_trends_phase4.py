"""Phase 4: End-to-End Skill Demand Trend Intelligence Feature Tests.

Covers:
1. Explicit capability selection (capability_id="trend_velocity_analysis").
2. Natural-language query routing:
   - "Why is Python demand changing?" -> analyze_trend / trend_velocity_analysis
   - "Is Python increasing or decreasing?" -> analyze_trend / trend_velocity_analysis
   - "What evidence supports this trend?" -> retrieve_evidence / evidence_provenance_retrieval (conversation context)
   - "Compare Python and Java using the available evidence." -> compare_entities
3. Capability-aware history window:
   - Default request without time_range automatically uses capability-specific history window (6m)
   - Explicit time_range="30d" is strictly respected and returns insufficient_data / INSUFFICIENT_TREND_HISTORY
4. Unverified/demo data rejection:
   - Demo data never produces a valid trend and emits OBSERVATION_PROVENANCE_UNAVAILABLE
5. Source comparability:
   - Job demand vs developer adoption signals are clearly distinguished and never conflated
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest

pytestmark = pytest.mark.usefixtures("local_conversation_firestore")

from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest
from app.models.skill_intelligence import MarketObservation
from app.services.capability_registry_service import CAPABILITY_CATALOG
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore

USER_PHASE4 = AuthenticatedUser(
    uid="user-phase4-tester",
    email="phase4@talentscope.ai",
    user_type="individual",
)


def make_python_demand_observations(
    *,
    count: int = 5,
    start_month: int = 5,
    data_origin: str = "real",
    source: str = "jsearch",
    signal_type: str = "demand",
) -> list[MarketObservation]:
    """Generate strictly consecutive monthly observations for Python."""
    observations: list[MarketObservation] = []
    for i in range(count):
        month = start_month + i
        period = f"2026-0{month}" if month < 10 else f"2026-{month}"
        observations.append(
            MarketObservation(
                id=f"obs-python-{source}-{period}",
                source=source,
                signal_type=signal_type,
                observed_at=datetime(2026, month, 15, 12, 0, 0, tzinfo=timezone.utc),
                period=period,
                skill="Python",
                skill_id="python",
                value=100.0 + (i * 20.0),
                unit="job_postings" if signal_type == "demand" else "repositories",
                data_origin=data_origin,
                history_type="platform_collected",
                series_id=f"{source}:{signal_type}:python:v1",
                query_id="python-series",
                panel_version="v1",
                fetch_run_id=f"fetch-run-{source}-{period}",
                location="Global",
                scope="global",
                observation_count=1,
            )
        )
    return observations


def test_explicit_selection_skill_demand_trends():
    """Explicitly selecting Skill Demand Trends runs trend_velocity_analysis."""
    obs = make_python_demand_observations(count=5)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What demand trend is observed for Python?",
        domain="skill",
        capability_id="trend_velocity_analysis",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE4)

    assert resp.intent == "analyze_trend"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
    assert "trend_velocity_analysis" in resp.capabilities_used
    assert any(f.fact_type == "trend_analysis" for f in resp.facts)

    trend_fact = next(f for f in resp.facts if f.fact_type == "trend_analysis")
    assert trend_fact.entity_name == "Python"
    assert trend_fact.metric_value == "Increasing"
    assert "Skill Demand Trends" in resp.answer
    assert "INCREASING" in resp.answer


def test_four_completed_comparable_periods_produce_a_trend():
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=make_python_demand_observations(count=4, start_month=5),
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "completed"
    assert "trend_velocity_analysis" in response.capabilities_used
    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    assert trend_fact.metric_value in {"Increasing", "Declining", "Stable"}
    assert trend_fact.details["periods_used"] == [
        "2026-05", "2026-06", "2026-07", "2026-08"
    ]


def test_six_retrieved_periods_across_short_source_series_report_validated_counts():
    observations = [
        *make_python_demand_observations(count=3, start_month=5, source="adzuna"),
        *make_python_demand_observations(count=3, start_month=8, source="jsearch"),
    ]
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=observations,
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "insufficient_data"
    assert response.capabilities_used == []
    assert "only 3 eligible completed monthly periods" in response.answer
    assert "6 distinct matched periods (" in response.answer
    assert "were retrieved across 2 source-specific series" in response.answer
    assert "those series are not pooled" in response.answer
    assert "Increasing" not in response.answer
    assert "Declining" not in response.answer
    assert "October" in response.answer or "2026-10" in response.answer


def test_incomplete_current_month_is_not_counted_as_a_completed_trend_period():
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=make_python_demand_observations(count=4, start_month=7),
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "insufficient_data"
    assert "only 3 eligible completed monthly periods" in response.answer
    assert "2026-10" in response.answer
    assert "incomplete current or future" in response.answer.lower()


def test_missing_month_does_not_produce_a_trend():
    observations = make_python_demand_observations(count=5, start_month=5)
    observations.pop(2)
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=observations,
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "insufficient_data"
    assert "required completed month is missing" in response.answer.lower()
    assert "at least 4 consecutive comparable completed monthly periods" in response.answer.lower()
    assert not any(fact.fact_type == "trend_analysis" for fact in response.facts)


def test_duplicate_observation_id_fails_quality_gate_without_a_trend():
    observations = make_python_demand_observations(count=4, start_month=5)
    observations.append(observations[0].model_copy(deep=True))
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=observations,
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "insufficient_data"
    assert "duplicate observations were found" in response.answer.lower()
    assert not any(fact.fact_type == "trend_analysis" for fact in response.facts)


def test_missing_demand_denominator_is_reported_as_raw_count_not_normalized_share():
    observations = make_python_demand_observations(count=4, start_month=5)
    observations = [
        observation.model_copy(update={"denominator": None})
        for observation in observations
    ]
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=observations,
        ),
        authenticated_user=USER_PHASE4,
    )

    assert response.execution_status == "completed"
    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    assert trend_fact.details["metric"] == "raw_count"
    assert trend_fact.unit != "share"
    assert any("raw count; platform volume changes may affect it" in item for item in response.limitations)


def test_selected_skill_gap_feature_routes_skill_gap_question_to_role_fit():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="Which skills match a backend developer role?",
            domain="skill",
            capability_id="skill_gap_role_fit",
            target_role="Backend Developer",
        ),
        authenticated_user=USER_PHASE4,
    )

    assert plan.intent == "analyze_skill_gap"
    assert plan.selected_capabilities == ["skill_gap_role_fit"]
    assert plan.clarification_required is True
    assert "specify which skills" in plan.clarification_questions[0].lower()


def test_selected_evidence_feature_routes_follow_up_evidence_question():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="What evidence supports this result?",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
            conversation_id="phase4-evidence-follow-up",
        ),
        authenticated_user=USER_PHASE4,
    )

    assert plan.intent == "retrieve_evidence"
    assert plan.selected_capabilities == ["evidence_provenance_retrieval"]


def test_stale_cross_domain_feature_does_not_route_to_a_different_capability():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
            capability_id="job_posting_search",
        ),
        authenticated_user=USER_PHASE4,
    )

    assert plan.intent == "unsupported_or_unclear"
    assert plan.selected_capabilities == []
    assert plan.clarification_required is True


def test_ambiguous_question_without_detectable_intent_requests_clarification():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="Can you help me with this?",
            domain="skill",
            capability_id="trend_velocity_analysis",
        ),
        authenticated_user=USER_PHASE4,
    )

    assert plan.clarification_required is True
    assert plan.plan_status == "requires_clarification"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]


def test_routing_why_is_python_demand_changing():
    """'Why is Python demand changing?' routes deterministically to analyze_trend."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(
        message="Why is Python demand changing?",
        domain="skill",
    )
    plan = planner.create_plan(req, authenticated_user=USER_PHASE4)

    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert any(e.raw_token.casefold() == "python" for e in plan.entities)


def test_routing_observed_python_demand_trend_variation():
    planner = IntentPlannerService()
    plan = planner.create_plan(
        IntelligencePlanRequest(
            message="What demand trend is observed for Python?",
            domain="skill",
        ),
        authenticated_user=USER_PHASE4,
    )

    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert any(
        entity.canonical_entity
        and entity.canonical_entity.canonical_name == "Python"
        for entity in plan.entities
    )


def test_capability_readiness_contracts_match_analytics():
    assert CAPABILITY_CATALOG["trend_velocity_analysis"].min_readiness_periods == 4
    assert CAPABILITY_CATALOG["skill_health_analysis"].min_readiness_periods == 4
    assert CAPABILITY_CATALOG["skill_half_life_analysis"].min_readiness_periods == 36
    assert CAPABILITY_CATALOG["skill_forecasting_half_life"].min_readiness_periods == 24


def test_routing_is_python_increasing_or_decreasing():
    """'Is Python increasing or decreasing?' routes to analyze_trend."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message="Is Python increasing or decreasing?")
    plan = planner.create_plan(req, authenticated_user=USER_PHASE4)

    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert any(e.raw_token.casefold() == "python" for e in plan.entities)


def test_routing_compare_python_and_java():
    """'Compare Python and Java using the available evidence.' routes to compare_entities."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(
        message="Compare Python and Java using the available evidence."
    )
    plan = planner.create_plan(req, authenticated_user=USER_PHASE4)

    assert plan.intent == "compare_entities"
    assert "trend_velocity_analysis" in plan.selected_capabilities
    entity_names = {
        e.canonical_entity.canonical_name for e in plan.entities if e.canonical_entity
    }
    assert "Python" in entity_names
    assert "Java" in entity_names


def test_multi_turn_what_evidence_supports_this_trend():
    """Turn 1 establishes Python trend; Turn 2 'What evidence supports this trend?' resolves evidence context."""
    obs = make_python_demand_observations(count=5)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_phase4_{uuid.uuid4().hex[:8]}"

    # Turn 1: Ask about trend
    turn1_req = CoreIntelligenceAnswerRequest(
        message="Why is Python demand changing?",
        conversation_id=conv_id,
        observations=obs,
    )
    turn1_resp = orchestrator.answer(turn1_req, authenticated_user=USER_PHASE4)
    assert turn1_resp.intent == "analyze_trend"
    assert turn1_resp.status == "ready"

    # Turn 2: Follow up on evidence
    turn2_req = CoreIntelligenceAnswerRequest(
        message="What evidence supports this trend?",
        conversation_id=conv_id,
        observations=obs,
    )
    turn2_resp = orchestrator.answer(turn2_req, authenticated_user=USER_PHASE4)
    assert turn2_resp.intent == "retrieve_evidence"
    assert turn2_resp.status == "ready"
    assert "evidence_provenance_retrieval" in turn2_resp.capabilities_used
    assert any(f.fact_type == "evidence_summary" for f in turn2_resp.facts)
    assert len(turn2_resp.evidence) >= 5
    assert "Python" in turn2_resp.answer


def test_capability_aware_history_window_default():
    """Default request without time_range automatically uses capability window (6m) and satisfies 4 periods."""
    obs = make_python_demand_observations(count=5)
    orchestrator = ExecutionOrchestratorService()

    # No time_range provided in request
    req = CoreIntelligenceAnswerRequest(
        message="Why is Python demand changing?",
        domain="skill",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE4)

    assert resp.intent == "analyze_trend"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
    assert resp.capabilities_used == ["trend_velocity_analysis"]
    assert any(f.fact_type == "trend_analysis" for f in resp.facts)


def test_explicit_narrow_time_range_returns_insufficient_data():
    """Explicitly passing time_range='30d' is not expanded; returns insufficient_data / honest limitation."""
    obs = make_python_demand_observations(count=5)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Is Python increasing or decreasing?",
        time_range="30d",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE4)

    assert resp.intent == "analyze_trend"
    assert resp.status == "insufficient_data"
    assert any(
        code in resp.reason_codes
        for code in ("INSUFFICIENT_TREND_HISTORY", "NO_OBSERVATIONS_FOR_SERIES")
    )
    assert any("consecutive" in lim.lower() for lim in resp.limitations)
    assert not any(fact.fact_type == "trend_analysis" for fact in resp.facts)
    assert resp.capabilities_used == []


def test_demo_observations_rejected_for_trend():
    """Observations with data_origin='demo' never produce a valid trend."""
    obs = make_python_demand_observations(count=5, data_origin="demo")
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Why is Python demand changing?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE4)

    assert resp.intent == "analyze_trend"
    assert resp.status == "insufficient_data"
    assert "OBSERVATION_PROVENANCE_UNAVAILABLE" in resp.reason_codes
    assert not any(f.fact_type == "trend_analysis" for f in resp.facts)
    assert "verified real-data provenance" in resp.answer


def test_source_comparability_distinct_signal_labeling():
    """Job demand (jsearch) and developer adoption (github) use distinct signal labels and are not conflated."""
    demand_obs = make_python_demand_observations(count=5, source="jsearch", signal_type="demand")
    adoption_obs = make_python_demand_observations(count=5, source="github", signal_type="adoption")

    orchestrator = ExecutionOrchestratorService()

    resp_demand = orchestrator.answer(
        CoreIntelligenceAnswerRequest(message="What is the Python trend?", observations=demand_obs),
        authenticated_user=USER_PHASE4,
    )
    resp_adoption = orchestrator.answer(
        CoreIntelligenceAnswerRequest(message="What is the Python trend?", observations=adoption_obs),
        authenticated_user=USER_PHASE4,
    )

    assert "job-posting demand" in resp_demand.answer
    assert "developer adoption/activity" in resp_adoption.answer

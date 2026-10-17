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
    data_origin: str = "real",
    source: str = "jsearch",
    signal_type: str = "demand",
) -> list[MarketObservation]:
    """Generate strictly consecutive monthly observations for Python."""
    observations: list[MarketObservation] = []
    for i in range(count):
        month = 5 + i
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
        message="Analyze Python",
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


def test_routing_why_is_python_demand_changing():
    """'Why is Python demand changing?' routes deterministically to analyze_trend."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message="Why is Python demand changing?")
    plan = planner.create_plan(req, authenticated_user=USER_PHASE4)

    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert any(e.raw_token.casefold() == "python" for e in plan.entities)


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
        message="Is Python increasing or decreasing?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE4)

    assert resp.intent == "analyze_trend"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
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
    assert "Observation provenance is missing or non-production" in resp.answer


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

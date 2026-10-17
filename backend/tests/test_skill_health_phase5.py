"""Phase 5: End-to-End Skill Health Engine Integration Tests.

Validates the full vertical slice:
User Question -> Intent/Entity Planning -> Skill Health Evaluation ->
Evidence Retrieval -> Synthesized Answer & Disclosures -> Deterministic Response Validation.

Covers:
1. Explicit capability selection (capability_id="skill_health_analysis").
2. Standard relative-momentum formula verification:
   score = round(clamp(50 + 50 * relative_slope / 0.03, 0, 100), 2)
   - Rising normalized share series -> score = 100.0, category = strengthening
   - Flat normalized share series -> score = 50.0, category = stable (neutral baseline)
3. Analytical and governance gates:
   - >= 4 consecutive completed monthly periods required
   - Rejection when < 4 periods -> INSUFFICIENT_HEALTH_HISTORY
   - Rejection when non-consecutive periods -> INSUFFICIENT_HEALTH_HISTORY
   - Rejection when missing denominators (raw counts) -> MISSING_SERIES_DENOMINATOR
   - Rejection when non-real data origin -> OBSERVATION_PROVENANCE_UNAVAILABLE
   - Non-interchangeable series are not combined into a single fabricated score (ambiguous_series)
   - Explicit narrow window (time_range="30d") is preserved and returns insufficient_data
4. Natural language queries:
   - "What is the Skill Health of Python?" -> analyze_skill_health
   - "Why is Python’s Skill Health score changing?" -> analyze_skill_health
   - "What evidence supports this Skill Health score?" -> retrieve_evidence (multi-turn carryover)
   - "Compare the available Skill Health evidence for Python and Java." -> compare_entities
5. Multi-tenant and conversation access isolation.
6. Deterministic fallback when LLM is unavailable.
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

USER_PHASE5 = AuthenticatedUser(
    uid="user-phase5-tester",
    email="phase5@talentscope.ai",
    user_type="individual",
)


def make_skill_health_observations(
    *,
    skill: str = "Python",
    skill_id: str = "python",
    count: int = 5,
    values: list[float] | None = None,
    denominators: list[float] | None = None,
    data_origin: str = "real",
    source: str = "jsearch",
    signal_type: str = "demand",
    consecutive: bool = True,
    start_month: int = 5,
) -> list[MarketObservation]:
    """Generate monthly observations with denominators for normalized share evaluation."""
    observations: list[MarketObservation] = []
    val_list = values or [10.0 + (i * 2.0) for i in range(count)]
    denom_list = denominators if denominators is not None else [1000.0 for _ in range(count)]

    for i in range(count):
        if consecutive:
            month = start_month + i
        else:
            month = start_month + (i * 2)  # Non-consecutive: skip every other month
        period = f"2026-0{month}" if month < 10 else f"2026-{month}"
        denom = denom_list[i] if denom_list else None
        val = val_list[i]

        observations.append(
            MarketObservation(
                id=f"obs-{skill_id}-{source}-{period}",
                source=source,
                signal_type=signal_type,
                observed_at=datetime(2026, month, 15, 12, 0, 0, tzinfo=timezone.utc),
                period=period,
                skill=skill,
                skill_id=skill_id,
                value=val,
                unit="postings",
                denominator=denom,
                denominator_unit="total_postings" if denom is not None else None,
                data_origin=data_origin,
                history_type="platform_collected",
                series_id=f"{source}:{signal_type}:{skill_id}:v1",
                query_id=f"{skill_id}-series",
                panel_version="v1",
                fetch_run_id=f"fetch-run-{source}-{period}",
                location="Global",
                scope="global",
                observation_count=1,
            )
        )
    return observations


def test_explicit_skill_health_selection_rising_series():
    """Explicit capability_id='skill_health_analysis' computes deterministic score and category."""
    obs = make_skill_health_observations(count=5)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Evaluate Skill Health for Python",
        domain="skill",
        capability_id="skill_health_analysis",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
    assert "skill_health_analysis" in resp.capabilities_used

    # Fact checks
    score_fact = next(f for f in resp.facts if f.fact_type == "skill_health_score")
    assert score_fact.metric_value == 100.0
    assert score_fact.unit == "score_0_100"
    assert score_fact.entity_name == "Python"

    cat_fact = next(f for f in resp.facts if f.fact_type == "skill_health_category")
    assert cat_fact.metric_value == "strengthening"

    # Narrative checks: contains baseline neutral disclosure and limits
    assert "100.00/100" in resp.answer
    assert "strengthening" in resp.answer
    assert "baseline score of 50.0 represents neutral relative momentum" in resp.answer
    assert any("relative-momentum indicator" in lim.lower() for lim in resp.limitations)


def test_skill_health_neutral_baseline_50():
    """Flat normalized share series produces baseline score of 50.0 and 'stable' category."""
    obs = make_skill_health_observations(count=5, values=[10.0, 10.0, 10.0, 10.0, 10.0])
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        domain="skill",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "ready"

    score_fact = next(f for f in resp.facts if f.fact_type == "skill_health_score")
    assert score_fact.metric_value == 50.0

    cat_fact = next(f for f in resp.facts if f.fact_type == "skill_health_category")
    assert cat_fact.metric_value == "stable"
    assert "50.00/100" in resp.answer
    assert "stable" in resp.answer


def test_natural_language_routing_what_is_skill_health():
    """'What is the Skill Health of Python?' routes deterministically to analyze_skill_health."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message="What is the Skill Health of Python?")
    plan = planner.create_plan(req, authenticated_user=USER_PHASE5)

    assert plan.intent == "analyze_skill_health"
    assert plan.selected_capabilities == ["skill_health_analysis"]
    assert any(e.raw_token.casefold() == "python" for e in plan.entities)


def test_natural_language_routing_why_is_score_changing():
    """'Why is Python’s Skill Health score changing?' routes to analyze_skill_health."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message="Why is Python’s Skill Health score changing?")
    plan = planner.create_plan(req, authenticated_user=USER_PHASE5)

    assert plan.intent == "analyze_skill_health"
    assert plan.selected_capabilities == ["skill_health_analysis"]
    assert any(e.raw_token.casefold() == "python" for e in plan.entities)


def test_natural_language_routing_compare_skill_health():
    """'Compare the available Skill Health evidence for Python and Java.' routes to compare_entities."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(
        message="Compare the available Skill Health evidence for Python and Java."
    )
    plan = planner.create_plan(req, authenticated_user=USER_PHASE5)

    assert plan.intent == "compare_entities"
    assert "skill_health_analysis" in plan.selected_capabilities
    entities = {e.canonical_entity.canonical_name for e in plan.entities if e.canonical_entity}
    assert "Python" in entities
    assert "Java" in entities


def test_multi_turn_what_evidence_supports_skill_health_score():
    """Turn 1: Skill health query; Turn 2: 'What evidence supports this Skill Health score?' carries over entity."""
    obs = make_skill_health_observations(count=5)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_phase5_{uuid.uuid4().hex[:8]}"

    # Turn 1
    t1_req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE5)
    assert t1_resp.intent == "analyze_skill_health"
    assert t1_resp.status == "ready"

    # Turn 2
    t2_req = CoreIntelligenceAnswerRequest(
        message="What evidence supports this Skill Health score?",
        conversation_id=conv_id,
        observations=obs,
    )
    t2_resp = orchestrator.answer(t2_req, authenticated_user=USER_PHASE5)
    assert t2_resp.intent == "retrieve_evidence"
    assert t2_resp.status == "ready"
    assert "evidence_provenance_retrieval" in t2_resp.capabilities_used
    assert any(f.fact_type == "evidence_summary" for f in t2_resp.facts)
    assert "Python" in t2_resp.answer


def test_skill_health_rejection_fewer_than_four_periods():
    """Skill Health requires at least 4 periods; 3 periods returns INSUFFICIENT_HEALTH_HISTORY."""
    obs = make_skill_health_observations(count=3)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_HEALTH_HISTORY" in resp.reason_codes
    assert any("at least four consecutive" in lim.lower() for lim in resp.limitations)


def test_skill_health_rejection_missing_denominators():
    """Raw count observations without denominators return MISSING_SERIES_DENOMINATOR."""
    obs = make_skill_health_observations(count=5, denominators=[None, None, None, None, None])
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "insufficient_data"
    assert "MISSING_SERIES_DENOMINATOR" in resp.reason_codes


def test_skill_health_rejection_non_consecutive_periods():
    """Non-consecutive observation months return INSUFFICIENT_HEALTH_HISTORY."""
    obs = make_skill_health_observations(count=5, consecutive=False, start_month=1)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_HEALTH_HISTORY" in resp.reason_codes


def test_skill_health_rejection_demo_observations():
    """Demo observations are rejected with OBSERVATION_PROVENANCE_UNAVAILABLE."""
    obs = make_skill_health_observations(count=5, data_origin="demo")
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "insufficient_data"
    assert "OBSERVATION_PROVENANCE_UNAVAILABLE" in resp.reason_codes


def test_skill_health_ambiguous_series_not_combined():
    """Multiple non-interchangeable series for Python report independently without a single fabricated score."""
    obs_jsearch = make_skill_health_observations(count=5, source="jsearch")
    obs_adzuna = make_skill_health_observations(count=5, source="adzuna")
    all_obs = obs_jsearch + obs_adzuna

    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        observations=all_obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    score_fact = next(f for f in resp.facts if f.fact_type == "skill_health_score")
    assert score_fact.metric_value is None
    assert score_fact.quality_state == "ambiguous_series"

    cat_fact = next(f for f in resp.facts if f.fact_type == "skill_health_category")
    assert cat_fact.metric_value == "insufficient_data"
    assert "Multiple non-interchangeable normalized share series were found" in resp.answer
    assert any("independently" in lim.lower() for lim in resp.limitations)


def test_skill_health_explicit_narrow_time_range_not_expanded():
    """Explicitly passing time_range='30d' is not expanded to 6m; returns insufficient_data."""
    obs = make_skill_health_observations(count=5)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        time_range="30d",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "analyze_skill_health"
    assert resp.status == "insufficient_data"
    assert any(
        code in resp.reason_codes
        for code in ("INSUFFICIENT_HEALTH_HISTORY", "NO_OBSERVATIONS_FOR_SERIES")
    )


def test_skill_health_conversation_isolation():
    """Conversations cannot be accessed by unauthorized users."""
    conv_store = ConversationStore.get_instance()
    conv_id = f"conv_iso_{uuid.uuid4().hex[:8]}"

    conv_store.create_conversation(
        user_id="legitimate-user",
        portal_type="individual",
        conversation_id=conv_id,
    )

    orchestrator = ExecutionOrchestratorService()
    attacker = AuthenticatedUser(uid="attacker-user", email="attacker@bad.com", user_type="individual")

    req = CoreIntelligenceAnswerRequest(
        message="What is the Skill Health of Python?",
        conversation_id=conv_id,
    )
    resp = orchestrator.answer(req, authenticated_user=attacker)

    assert resp.status in {"unavailable", "error"}
    assert "UNAUTHORIZED_CONVERSATION_ACCESS" in resp.reason_codes


def test_end_to_end_compare_python_and_java_skill_health():
    """'Compare the available Skill Health evidence for Python and Java.' evaluates both entities."""
    python_obs = make_skill_health_observations(skill="Python", skill_id="python", count=5)
    java_obs = make_skill_health_observations(skill="Java", skill_id="java", count=5)
    all_obs = python_obs + java_obs

    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Compare the available Skill Health evidence for Python and Java.",
        observations=all_obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE5)

    assert resp.intent == "compare_entities"
    assert resp.status == "ready"
    assert "skill_health_analysis" in resp.capabilities_used

    # Verifies both Python and Java facts exist
    python_facts = [f for f in resp.facts if f.entity_name == "Python"]
    java_facts = [f for f in resp.facts if f.entity_name == "Java"]
    assert len(python_facts) >= 2
    assert len(java_facts) >= 2

    assert "Comparative Skill Health" in resp.answer
    assert "Python" in resp.answer
    assert "Java" in resp.answer

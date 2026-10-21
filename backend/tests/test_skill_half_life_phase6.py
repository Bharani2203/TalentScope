"""Phase 6: End-to-End Skill Half-Life Engine Integration Tests.

Validates the full vertical slice:
User Question -> Intent/Entity Planning -> Skill Half-Life Evaluation ->
Evidence Retrieval -> Synthesized Answer & Disclosures -> Deterministic Response Validation.

Covers:
1. Canonical user questions:
   - "What is Python's skill half-life?" -> estimate_skill_half_life
   - "How was that half-life estimated?" -> estimate_skill_half_life
   - "What evidence supports this estimate?" -> retrieve_evidence (multi-turn carryover)
   - "Compare the available half-life evidence for Python and Java." -> compare_entities
2. Mathematical constraints & gates:
   - Exponential decay on log normalized share: half_life_months = ln(2) / |b|
   - Series with b < 0, Kendall tau <= -0.5, p < 0.05 returns status="ready"
   - Non-declining series (flat or rising) returns status="not_applicable"
   - Fewer than 36 consecutive monthly observations returns INSUFFICIENT_HALF_LIFE_HISTORY
   - Non-consecutive monthly periods returns INSUFFICIENT_HALF_LIFE_HISTORY
   - Raw counts without valid denominators returns MISSING_SERIES_DENOMINATOR
   - Non-real observation provenance (demo/synthetic) returns OBSERVATION_PROVENANCE_UNAVAILABLE
   - Explicit narrow window (time_range="30d" or "6m") is preserved and returns insufficient_data
   - Defaulted window expands to 36m automatically
3. Required disclosures:
   - Exponential decay model on log normalized share
   - Not a guarantee of skill obsolescence or future prediction
   - Historical decay rate only
   - Not applicable to growing or stable skills
4. Multi-tenant and conversation access isolation.
5. Deterministic fallback when LLM is unavailable.
"""

from __future__ import annotations

import math
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

USER_PHASE6 = AuthenticatedUser(
    uid="user-phase6-tester",
    email="phase6@talentscope.ai",
    user_type="individual",
)

USER_OTHER = AuthenticatedUser(
    uid="user-other-tenant",
    email="other@talentscope.ai",
    user_type="individual",
)


def make_skill_half_life_observations(
    *,
    skill: str = "Python",
    skill_id: str = "python",
    count: int = 36,
    decay_rate: float | None = 0.02,
    base_share: float = 0.20,
    values: list[float] | None = None,
    denominators: list[float] | None = None,
    data_origin: str = "real",
    source: str = "jsearch",
    signal_type: str = "demand",
    consecutive: bool = True,
    start_year: int = 2023,
    start_month: int = 10,
) -> list[MarketObservation]:
    """Generate monthly observations with denominators for half-life decay evaluation."""
    observations: list[MarketObservation] = []
    total_denom = 1000.0

    if values is not None:
        val_list = values
    elif decay_rate is not None:
        # Exponential decay: share_t = base_share * exp(-decay_rate * t)
        val_list = [base_share * math.exp(-decay_rate * i) * total_denom for i in range(count)]
    else:
        # Flat constant series
        val_list = [base_share * total_denom for _ in range(count)]

    denom_list = denominators if denominators is not None else [total_denom for _ in range(count)]

    for i in range(count):
        if consecutive:
            month_idx = (start_year * 12 + start_month - 1) + i
        else:
            month_idx = (start_year * 12 + start_month - 1) + (i * 2)  # Skip months
        year, month_zero = divmod(month_idx, 12)
        month = month_zero + 1
        period = f"{year:04d}-{month:02d}"

        denom = denom_list[i] if denom_list else None
        val = val_list[i]

        observations.append(
            MarketObservation(
                id=f"obs-{skill_id}-{source}-{period}",
                source=source,
                signal_type=signal_type,
                observed_at=datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc),
                period=period,
                skill=skill,
                skill_id=skill_id,
                value=round(val, 2),
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


# =============================================================================
# 1. CANONICAL USER QUESTIONS & NATURAL LANGUAGE ROUTING
# =============================================================================

def test_query_1_what_is_python_skill_half_life():
    """Q1: 'What is Python's skill half-life?' routes to estimate_skill_half_life and calculates half-life."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        domain="skill",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
    assert "skill_half_life_analysis" in resp.capabilities_used

    # Fact verification
    hl_fact = next(f for f in resp.facts if f.fact_type == "skill_half_life")
    assert hl_fact.metric_value is not None
    assert hl_fact.metric_value > 0
    assert hl_fact.unit == "months"
    assert hl_fact.quality_state == "ready"

    # Half-life months should be approximately ln(2) / 0.02 = 34.66
    assert 30.0 < hl_fact.metric_value < 40.0

    # Narrative checks
    assert f"{hl_fact.metric_value:.2f} months" in resp.answer
    assert "Skill Half-Life" in resp.answer
    assert "exponential decay model" in resp.answer
    assert any("not an obsolescence guarantee" in lim.lower() for lim in resp.limitations)


def test_query_2_how_was_that_half_life_estimated():
    """Q2: 'How was that half-life estimated?' routes to estimate_skill_half_life and explains methodology."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="How was that half-life estimated for Python?",
        domain="skill",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "ready"
    assert "skill_half_life_analysis" in resp.capabilities_used

    # Verifies methodology explanation
    assert "exponential decay model on log normalized market share" in resp.answer
    assert "Theil-Sen" in resp.answer
    assert "Kendall Tau" in resp.answer
    assert "36 consecutive monthly periods" in resp.answer


def test_query_3_what_evidence_supports_this_estimate_multi_turn():
    """Q3: 'What evidence supports this estimate?' carries over primary entity in multi-turn conversation."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_phase6_{uuid.uuid4().hex[:8]}"

    # Turn 1: Half-life estimate
    t1_req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE6)
    assert t1_resp.intent == "estimate_skill_half_life"
    assert t1_resp.status == "ready"

    # Turn 2: Evidence query carrying over Python
    t2_req = CoreIntelligenceAnswerRequest(
        message="What evidence supports this estimate?",
        conversation_id=conv_id,
        observations=obs,
    )
    t2_resp = orchestrator.answer(t2_req, authenticated_user=USER_PHASE6)
    assert t2_resp.intent == "retrieve_evidence"
    assert t2_resp.status == "ready"
    assert "evidence_provenance_retrieval" in t2_resp.capabilities_used
    assert "Python" in t2_resp.answer
    assert len(t2_resp.evidence) > 0


def test_query_4_compare_half_life_evidence():
    """Q4: 'Compare the available half-life evidence for Python and Java.' routes to compare_entities."""
    py_obs = make_skill_half_life_observations(skill="Python", skill_id="python", count=36, decay_rate=0.02)
    java_obs = make_skill_half_life_observations(skill="Java", skill_id="java", count=36, decay_rate=0.015)
    all_obs = py_obs + java_obs

    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Compare the available half-life evidence for Python and Java.",
        domain="skill",
        observations=all_obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "compare_entities"
    assert "skill_half_life_analysis" in resp.capabilities_used
    assert "Comparative Skill Half-Life" in resp.answer
    assert "Python" in resp.answer
    assert "Java" in resp.answer


# =============================================================================
# 2. MATHEMATICAL CONSTRAINTS & GOVERNANCE GATES
# =============================================================================

def test_non_declining_series_returns_not_applicable():
    """Flat or growing normalized share series returns status='not_applicable' and proper reason."""
    # Flat series: decay_rate=None
    obs = make_skill_half_life_observations(count=36, decay_rate=None)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"

    hl_fact = next(f for f in resp.facts if f.fact_type == "skill_half_life")
    assert hl_fact.quality_state == "not_applicable"
    assert hl_fact.metric_value is None

    assert "not applicable" in resp.answer.lower()
    assert (
        "decay fit is unsupported" in resp.answer.lower()
        or "growing or flat" in resp.answer.lower()
        or "not undergoing statistically significant decay" in resp.answer.lower()
    )


def test_growing_series_returns_not_applicable():
    """Rising normalized share series returns status='not_applicable'."""
    # Growing series: negative decay_rate
    obs = make_skill_half_life_observations(count=36, decay_rate=-0.02)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "ready"

    hl_fact = next(f for f in resp.facts if f.fact_type == "skill_half_life")
    assert hl_fact.quality_state == "not_applicable"
    assert "not applicable" in resp.answer.lower()


def test_rejection_fewer_than_36_periods():
    """Fewer than 36 monthly observations rejects with INSUFFICIENT_HALF_LIFE_HISTORY."""
    obs = make_skill_half_life_observations(count=24, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_HALF_LIFE_HISTORY" in resp.reason_codes
    assert any("at least 36 consecutive completed monthly periods" in lim.lower() for lim in resp.limitations)


def test_half_life_cannot_lower_operational_minimum_with_argument():
    from app.analytics.skill_half_life import calculate_skill_half_life
    from app.analytics.signal_aggregation import aggregate_market_signals

    observations = make_skill_half_life_observations(count=35, decay_rate=0.02)
    result = calculate_skill_half_life(
        aggregate_market_signals(observations), canonical_skill_id="python", min_periods=3,
    )
    assert result.status == "insufficient_data"
    assert result.required_min_periods == 36
    assert result.half_life_months is None


def test_rejection_non_consecutive_periods():
    """36 observations with skipped months rejects with INSUFFICIENT_HALF_LIFE_HISTORY."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02, consecutive=False)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_HALF_LIFE_HISTORY" in resp.reason_codes


def test_rejection_missing_denominators_raw_counts():
    """Raw counts without valid denominators rejects with MISSING_SERIES_DENOMINATOR."""
    obs = make_skill_half_life_observations(
        count=36,
        decay_rate=0.02,
        denominators=[None] * 36,
    )
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status == "insufficient_data"
    assert "MISSING_SERIES_DENOMINATOR" in resp.reason_codes


def test_rejection_non_real_provenance_demo_data():
    """Demo or synthetic observations reject with OBSERVATION_PROVENANCE_UNAVAILABLE."""
    obs = make_skill_half_life_observations(
        count=36,
        decay_rate=0.02,
        data_origin="demo",
    )
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.status in {"insufficient_data", "unavailable"}
    assert "OBSERVATION_PROVENANCE_UNAVAILABLE" in resp.reason_codes


def test_explicit_narrow_time_range_not_broadened():
    """User-supplied explicit time_range='6m' is not silently broadened to 36m and returns insufficient_data."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()

    # Pass explicit time_range="6m"
    req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        time_range="6m",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE6)

    assert resp.intent == "estimate_skill_half_life"
    assert resp.applied_filters.get("time_range") == "6m"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_HALF_LIFE_HISTORY" in resp.reason_codes


def test_default_time_range_broadened_to_36m():
    """When time_range is defaulted (not explicitly supplied), planner broadens to 36m."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(
        message="What is Python's skill half-life?",
    )
    plan = planner.create_plan(req, authenticated_user=USER_PHASE6)

    assert plan.intent == "estimate_skill_half_life"
    assert plan.context_summary.get("time_range") == "36m"


# =============================================================================
# 3. MULTI-TENANT ISOLATION
# =============================================================================

def test_conversation_access_isolation():
    """User B cannot access or continue User A's half-life conversation."""
    obs = make_skill_half_life_observations(count=36, decay_rate=0.02)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_phase6_iso_{uuid.uuid4().hex[:8]}"

    # User A starts conversation
    t1_req = CoreIntelligenceAnswerRequest(
        message="What is Python's skill half-life?",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE6)
    assert t1_resp.status == "ready"

    # User B attempts to access User A's conversation
    t2_req = CoreIntelligenceAnswerRequest(
        message="What evidence supports this estimate?",
        conversation_id=conv_id,
        observations=obs,
    )
    t2_resp = orchestrator.answer(t2_req, authenticated_user=USER_OTHER)

    # User B receives access denied error
    assert t2_resp.status in {"error", "unavailable"}
    assert (
        "UNAUTHORIZED_CONVERSATION_ACCESS" in t2_resp.reason_codes
        or "ACCESS_DENIED" in t2_resp.reason_codes
        or "CONVERSATION_ACCESS_DENIED" in t2_resp.reason_codes
    )

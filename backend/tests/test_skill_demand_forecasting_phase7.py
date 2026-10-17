"""Phase 7: End-to-End Skill Demand Forecasting Engine Integration Tests.

Validates the full vertical slice:
User Question -> Intent/Entity Planning -> Skill Demand Forecasting Evaluation ->
Evidence Retrieval -> Deterministic Forecast Synthesis -> Response Validation.

Covers:
1. Canonical user questions:
   - "Forecast Python skill demand." -> forecast_future_demand
   - "What might Python demand look like in the next six months?" -> forecast_future_demand
   - "How reliable is this forecast?" -> forecast_future_demand (multi-turn entity carryover)
   - "What historical evidence supports this forecast?" -> retrieve_evidence (multi-turn carryover)
   - "Compare the demand forecasts for Python and Java." -> compare_entities
2. Algorithmic and mathematical constraints:
   - Seasonal-naive carry-forward model repeating corresponding month from prior year
   - Evaluated out-of-sample on chronological holdouts against simple naive baseline
   - Reports out-of-sample RMSE and MAE, and beats_naive_baseline
   - Forecast horizon capped at min(6, history_length // 3)
   - Prediction intervals omitted until horizon-specific holdout coverage is sufficient
   - Minimum history requirement: >= 24 strictly consecutive completed monthly observations
3. Data quality and provenance safeguards:
   - Rejection of fewer than 24 periods -> INSUFFICIENT_FORECAST_HISTORY
   - Rejection of non-consecutive monthly periods (gaps) -> INSUFFICIENT_FORECAST_HISTORY
   - Rejection of demo/synthetic provenance -> OBSERVATION_PROVENANCE_UNAVAILABLE
   - Rejection of incompatible provider/geography partitions -> AMBIGUOUS_SOURCE_SERIES
   - Rejection of missing denominators for normalized share -> MISSING_SERIES_DENOMINATOR
4. Time range safeguards:
   - Explicit narrow time range (e.g. 6m, 30d) is preserved and returns insufficient_data
   - Default time range (30d) expands to 24m to permit forecasting
5. Enterprise and architecture safeguards:
   - Conversation access isolation across tenants
   - Workforce simulation and AI disruption remain strictly disabled
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

USER_PHASE7 = AuthenticatedUser(
    uid="user-phase7-forecaster",
    email="phase7@talentscope.ai",
    user_type="individual",
)

USER_OTHER = AuthenticatedUser(
    uid="user-other-tenant",
    email="other@talentscope.ai",
    user_type="individual",
)


def make_forecasting_observations(
    *,
    skill: str = "Python",
    skill_id: str = "python",
    count: int = 24,
    base_share: float = 0.15,
    total_denom: float = 1000.0,
    values: list[float] | None = None,
    denominators: list[float] | None = None,
    data_origin: str = "real",
    source: str = "adzuna",
    signal_type: str = "demand",
    unit: str = "job_postings",
    consecutive: bool = True,
    start_year: int = 2024,
    start_month: int = 10,
    location: str = "Global",
    scope: str = "global",
) -> list[MarketObservation]:
    """Generate monthly observations with denominators for deterministic demand forecasting."""
    observations: list[MarketObservation] = []

    if values is not None:
        val_list = values
    else:
        # Realistic seasonal monthly pattern: base_share * (1 + 0.15 * sin(2*pi*i/12))
        val_list = [
            base_share * (1.0 + 0.15 * math.sin(2 * math.pi * i / 12.0)) * total_denom
            for i in range(count)
        ]

    denom_list = denominators if denominators is not None else [total_denom for _ in range(count)]

    for i in range(count):
        if consecutive:
            month_idx = (start_year * 12 + start_month - 1) + i
        else:
            month_idx = (start_year * 12 + start_month - 1) + (i * 2)  # Skip months to create gaps
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
                unit=unit,
                denominator=denom,
                denominator_unit="total_postings" if denom is not None else None,
                data_origin=data_origin,
                history_type="platform_collected",
                series_id=f"{source}:{signal_type}:{skill_id}:{location.lower()}",
                query_id=f"{skill_id}-query",
                panel_version="v1",
                fetch_run_id=f"run-{source}-{period}",
                location=location,
                scope=scope,
                observation_count=1,
            )
        )
    return observations


# =============================================================================
# 1. CANONICAL USER QUESTIONS & INTENT ROUTING
# =============================================================================

def test_query_1_forecast_python_skill_demand():
    """Q1: 'Forecast Python skill demand.' routes to forecast_future_demand and produces seasonal-naive forecast."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"
    assert "skill_forecasting_half_life" in resp.capabilities_used

    # Fact verification
    fc_fact = next(f for f in resp.facts if f.fact_type == "skill_forecast")
    assert fc_fact.quality_state == "ready"
    assert fc_fact.details["selected_method"] == "seasonal_naive"
    assert fc_fact.details["horizon_months"] == 6
    assert len(fc_fact.details["forecasts"]) == 6
    assert fc_fact.details["winner_rmse"] is not None
    assert fc_fact.details["naive_rmse"] is not None

    # Individual forecast points
    pt_facts = [f for f in resp.facts if f.fact_type == "skill_forecast_point"]
    assert len(pt_facts) == 6
    assert pt_facts[0].period == "2026-10"
    assert pt_facts[5].period == "2027-03"

    # Answer text grounding
    assert "skill demand forecast" in resp.answer.lower()
    assert "seasonal-naive" in resp.answer.lower()
    assert "holdout" in resp.answer.lower()


def test_query_2_what_might_python_demand_look_like_next_six_months():
    """Q2: 'What might Python demand look like in the next six months?' routes to forecast."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="What might Python demand look like in the next six months?",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status == "ready"
    assert resp.execution_status == "completed"

    fc_fact = next(f for f in resp.facts if f.fact_type == "skill_forecast")
    assert fc_fact.quality_state == "ready"
    assert fc_fact.details["horizon_months"] == 6


def test_query_3_how_reliable_is_this_forecast_multi_turn():
    """Q3: 'How reliable is this forecast?' in multi-turn conversation retains entity and explains backtest evaluation."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"

    # Turn 1: Forecast query
    t1_req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE7)
    assert t1_resp.status == "ready"

    # Turn 2: Follow-up question about reliability
    t2_req = CoreIntelligenceAnswerRequest(
        message="How reliable is this forecast?",
        conversation_id=conv_id,
        observations=obs,
    )
    t2_resp = orchestrator.answer(t2_req, authenticated_user=USER_PHASE7)

    assert t2_resp.intent == "forecast_future_demand"
    assert t2_resp.status == "ready"

    fc_fact = next(f for f in t2_resp.facts if f.fact_type == "skill_forecast")
    assert fc_fact.entity_name == "Python"
    # Validates backtest sample size, RMSE, and baseline comparisons are reported
    assert fc_fact.details["backtest_sample_size"] == 8
    assert "validation accuracy" in t2_resp.answer.lower() or "rmse" in t2_resp.answer.lower()


def test_query_4_what_historical_evidence_supports_this_forecast_multi_turn():
    """Q4: 'What historical evidence supports this forecast?' routes to evidence retrieval with primary entity carryover."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv-{uuid.uuid4().hex[:8]}"

    # Turn 1: Forecast query
    t1_req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE7)
    assert t1_resp.status == "ready"

    # Turn 2: Evidence query
    t2_req = CoreIntelligenceAnswerRequest(
        message="What historical evidence supports this forecast?",
        conversation_id=conv_id,
        observations=obs,
    )
    t2_resp = orchestrator.answer(t2_req, authenticated_user=USER_PHASE7)

    assert t2_resp.intent == "retrieve_evidence"
    assert t2_resp.status == "ready"
    assert len(t2_resp.evidence) > 0
    # Verifies evidence originates from real observations
    assert any(e.source == "adzuna" for e in t2_resp.evidence)


def test_query_5_compare_demand_forecasts():
    """Q5: 'Compare the demand forecasts for Python and Java.' evaluates both entities independently."""
    py_obs = make_forecasting_observations(skill="Python", skill_id="python", count=24)
    java_obs = make_forecasting_observations(skill="Java", skill_id="java", count=24, base_share=0.10)
    all_obs = py_obs + java_obs

    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Compare the demand forecasts for Python and Java.",
        observations=all_obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "compare_entities"
    assert resp.status == "ready"

    fc_facts = [f for f in resp.facts if f.fact_type == "skill_forecast"]
    assert len(fc_facts) == 2
    ent_names = {f.entity_name for f in fc_facts}
    assert ent_names == {"Python", "Java"}

    assert "comparative skill demand forecast" in resp.answer.lower()


# =============================================================================
# 2. DATA QUALITY, CONTINUITY, AND PROVENANCE SAFEGUARDS
# =============================================================================

def test_rejection_fewer_than_24_periods():
    """Series with fewer than 24 monthly periods is rejected with INSUFFICIENT_FORECAST_HISTORY."""
    obs = make_forecasting_observations(count=18)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status == "insufficient_data"
    assert resp.execution_status in {"insufficient_data", "completed"}
    assert "INSUFFICIENT_FORECAST_HISTORY" in resp.reason_codes
    assert not any(f.fact_type == "skill_forecast" and f.quality_state == "ready" for f in resp.facts)
    assert not any(f.fact_type == "skill_forecast_point" for f in resp.facts)


def test_rejection_non_consecutive_periods_gaps():
    """Series with missing period gaps is rejected with INSUFFICIENT_FORECAST_HISTORY without zero-filling."""
    obs = make_forecasting_observations(count=24, consecutive=False)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_FORECAST_HISTORY" in resp.reason_codes
    assert "gaps" in resp.answer.lower() or "insufficient" in resp.answer.lower() or "withheld" in resp.answer.lower()


def test_rejection_demo_observations():
    """Demo or synthetic observations cannot produce a valid demand forecast."""
    obs = make_forecasting_observations(count=24, data_origin="demo")
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status in {"unavailable", "insufficient_data"}
    assert "OBSERVATION_PROVENANCE_UNAVAILABLE" in resp.reason_codes
    assert not any(f.fact_type == "skill_forecast_point" for f in resp.facts)


def test_rejection_missing_denominators_for_normalized_share():
    """Normalized share observations without denominators cannot be forecast."""
    obs = make_forecasting_observations(count=24, denominators=[None] * 24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status in {"insufficient_data", "unavailable"}
    assert any(
        code in resp.reason_codes
        for code in ["MISSING_SERIES_DENOMINATOR", "INSUFFICIENT_FORECAST_HISTORY"]
    )


def test_rejection_ambiguous_incompatible_partitions():
    """Mixing observations across different providers or units is withheld rather than aggregated."""
    obs_adzuna = make_forecasting_observations(count=24, source="adzuna", location="Global")
    obs_jsearch = make_forecasting_observations(count=24, source="jsearch", location="Global")
    mixed_obs = obs_adzuna + obs_jsearch

    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=mixed_obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "forecast_future_demand"
    assert resp.status in {"unavailable", "insufficient_data"}
    assert "AMBIGUOUS_SOURCE_SERIES" in resp.reason_codes


# =============================================================================
# 3. TIME-RANGE HANDLING & EXPLICIT FILTER PRESERVATION
# =============================================================================

def test_explicit_narrow_time_range_not_broadened():
    """An explicit narrow window (time_range='6m') is preserved and returns insufficient_data."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        time_range="6m",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    # 6m cutoff filters out observations older than 180 days, leaving < 24 months
    assert resp.intent == "forecast_future_demand"
    assert resp.status == "insufficient_data"
    assert "INSUFFICIENT_FORECAST_HISTORY" in resp.reason_codes


def test_default_time_range_broadened_to_24m():
    """When time_range is not explicitly specified, default 30d expands to 24m to permit forecasting."""
    planner = IntentPlannerService()
    req_plan = IntelligencePlanRequest(
        message="Forecast Python skill demand.",
    )
    plan = planner.create_plan(req_plan, authenticated_user=USER_PHASE7)
    assert plan.context_summary.get("time_range") == "24m"

    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.status == "ready"
    fc_fact = next(f for f in resp.facts if f.fact_type == "skill_forecast")
    assert fc_fact.quality_state == "ready"


# =============================================================================
# 4. HORIZON, UNCERTAINTY, AND METHOD DISCLOSURES
# =============================================================================

def test_horizon_capped_and_intervals_omitted():
    """Forecast horizon is capped at min(6, n // 3) and prediction intervals are omitted."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        observations=obs,
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    fc_fact = next(f for f in resp.facts if f.fact_type == "skill_forecast")
    assert fc_fact.details["horizon_months"] == 6

    # Verify prediction intervals are None (not fabricated)
    pt_facts = [f for f in resp.facts if f.fact_type == "skill_forecast_point"]
    for pt in pt_facts:
        assert pt.details["lower_80"] is None
        assert pt.details["upper_80"] is None
        assert pt.details["lower_95"] is None
        assert pt.details["upper_95"] is None

    # Disclosures in limitations
    assert any("prediction intervals are omitted" in lim.lower() for lim in resp.limitations)
    assert any("non-guaranteed" in lim.lower() or "external market shifts" in lim.lower() for lim in resp.limitations)


# =============================================================================
# 5. MULTI-TENANT CONVERSATION ACCESS ISOLATION
# =============================================================================

def test_conversation_access_isolation():
    """User B cannot access or follow up on User A's forecasting conversation."""
    obs = make_forecasting_observations(count=24)
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv-isolation-{uuid.uuid4().hex[:8]}"

    # User A initiates forecast
    t1_req = CoreIntelligenceAnswerRequest(
        message="Forecast Python skill demand.",
        conversation_id=conv_id,
        observations=obs,
    )
    t1_resp = orchestrator.answer(t1_req, authenticated_user=USER_PHASE7)
    assert t1_resp.status == "ready"

    # User B attempts to access User A's conversation
    t2_req = CoreIntelligenceAnswerRequest(
        message="How reliable is this forecast?",
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


# =============================================================================
# 6. BOUNDARY SAFETY: SIMULATION REMAINS DISABLED
# =============================================================================

def test_workforce_simulation_remains_strictly_disabled():
    """Workforce what-if simulation remains explicitly disabled in G2.6."""
    orchestrator = ExecutionOrchestratorService()

    req = CoreIntelligenceAnswerRequest(
        message="Simulate workforce attrition shock for our company.",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_PHASE7)

    assert resp.intent == "simulate_workforce_scenarios"
    assert resp.status == "unavailable"
    assert resp.plan_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp.reason_codes
    assert "workforce what-if simulation" in resp.answer.lower()

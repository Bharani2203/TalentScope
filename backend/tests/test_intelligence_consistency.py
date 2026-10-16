"""Deterministic test suite for G2.6: Intelligence Quality, Consistency & Explainability Hardening.

Verifies Criteria A through U:
A. Readiness consistency across layers
B. Trend consistency (direction, slope, velocity invariant)
C. Answer consistency (no trend claims when unready)
D. Action consistency (roadmap_eligible=False when unready, low priority)
E. Evidence consistency (traceability to observations/signals)
F. Roadmap eligibility consistency
G. Blocked quality
H. Blocked coverage
I. Blocked configuration
J. Missing period
K. Insufficient history
L. Insufficient data
M. Forecast lock (is_forecast_ready=False, ready_for_forecast_count=0)
N. Production/test data separation
O. Fallback fabrication audit (no fake zeros, no synthetic data)
P. Individual context
Q. Employee context
R. Company context
S. Deterministic output
T. Authentication required
U. Firestore read safety
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.core_intelligence import (
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
    HistoricalTrendItem,
    ReadinessSummary,
    CoreIntelligenceAnswer,
    IntelligenceSignal,
    IndividualContext,
    EmployeeContext,
    CompanyContext,
)
from app.models.action_recommendation import (
    ActionRecommendation,
    ActionRecommendationResponse,
)
from app.models.intelligence_consistency import (
    ConsistencyCheckItem,
    ConsistencyStatus,
    IntelligenceConsistencyResult,
)
from app.models.skill_intelligence import MarketObservation
from app.services.intelligence_consistency_service import IntelligenceConsistencyService
from app.services.core_intelligence_service import CoreIntelligenceService


# -------------------------------------------------------------------------
# Test Fixtures & Mock Store
# -------------------------------------------------------------------------

class MockObservationStore:
    """In-memory observation store ensuring zero live Firestore reads."""

    def __init__(self, observations: list[MarketObservation] | None = None):
        self.observations = list(observations or [])
        self.read_count = 0

    def get_observations(
        self,
        *,
        cutoff: datetime,
        location: str | None = None,
        signal_type: str | None = None,
    ) -> list[MarketObservation]:
        self.read_count += 1
        res = []
        for o in self.observations:
            obs_dt = o.observed_at
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            if obs_dt < cutoff:
                continue
            if location and o.location and location.casefold() not in o.location.casefold():
                continue
            if signal_type and o.signal_type != signal_type:
                continue
            res.append(o)
        return res


def _make_obs(
    *,
    source: str = "stackexchange",
    signal_type: str = "interest",
    skill: str = "Python",
    skill_id: str = "python",
    period: str = "2026-05",
    value: float = 100.0,
    unit: str | None = None,
    denominator: float | None = 1000.0,
    location: str = "Global",
    fetch_run_id: str = "run-1",
    raw_archive_id: str = "raw-1",
    quality: str = "valid",
) -> MarketObservation:
    year, month = (int(p) for p in period.split("-"))
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
    return MarketObservation(
        id=f"obs-{source}-{skill_id}-{period}",
        source=source,
        signal_type=signal_type,
        observed_at=dt,
        period=period,
        location=location,
        scope="global",
        skill=skill,
        skill_id=skill_id,
        value=value,
        unit=unit,
        denominator=denominator,
        data_origin="real",
        history_type="backfill" if source == "stackexchange" else "platform_collected",
        series_id=f"{source}:{signal_type}:{skill_id}:v1",
        quality=quality,
        confidence=0.92,
        fetch_run_id=fetch_run_id,
        metadata={"raw_archive_id": raw_archive_id},
    )


def _make_trend_ready_observations(skill: str = "Python", skill_id: str = "python") -> list[MarketObservation]:
    """5 consecutive monthly observations (>= 4 required for trend readiness)."""
    vals = [100.0, 115.0, 130.0, 145.0, 160.0]
    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    return [
        _make_obs(
            skill=skill,
            skill_id=skill_id,
            period=periods[i],
            value=vals[i],
            unit="activity_count",
            raw_archive_id=f"archive-{skill_id}-{periods[i]}",
        )
        for i in range(5)
    ]


def _make_trend_item(
    *,
    entity_name: str = "Python",
    canonical_skill_id: str = "python",
    trend_direction: str = "Increasing",
    trend_slope: float | None = 0.05,
    growth_pct: float | None = 15.0,
    velocity: float | None = 0.015,
    is_trend_ready: bool = True,
    is_forecast_ready: bool = False,
    periods_count: int = 5,
) -> HistoricalTrendItem:
    return HistoricalTrendItem(
        entity_id=f"trend-{canonical_skill_id}",
        entity_name=entity_name,
        canonical_skill_id=canonical_skill_id,
        display_name=entity_name,
        entity_type="skill",
        signal_type="interest",
        source="stackexchange",
        period_start="2026-05",
        period_end="2026-09",
        periods_count=periods_count,
        periods=["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"][:periods_count],
        trend_direction=trend_direction,
        trend_slope=trend_slope,
        velocity=velocity,
        growth_pct=growth_pct,
        is_trend_ready=is_trend_ready,
        is_forecast_ready=is_forecast_ready,
    )


def _make_action_item(
    *,
    action_id: str = "act-test-01",
    action_type: str = "review_skill",
    title: str = "Review Skill",
    summary: str = "Review skill demand",
    why_it_matters: str = "FACT: Test fact. INTERPRETATION: Test interp. ACTION: Test action.",
    recommended_action: str = "Evaluate skill trajectory",
    priority: str = "low",
    roadmap_eligible: bool = False,
    readiness_status: str = "ready_for_trend",
    portal: str = "individual",
    target_type: str = "skill",
    target_id: str = "python",
) -> ActionRecommendation:
    return ActionRecommendation(
        action_id=action_id,
        action_type=action_type,
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        priority=priority,
        target_type=target_type,
        target_id=target_id,
        portal=portal,
        readiness_status=readiness_status,
        roadmap_eligible=roadmap_eligible,
    )


def _make_mock_response(
    *,
    portal_type: str = "individual",
    intelligence_type: str = "skill",
    readiness_state: str = "ready_for_trend",
    headline: str = "Analytical Assessment",
    summary: str = "Summary of observations",
    contextual_focus: str = "Individual career focus",
    trends: list[HistoricalTrendItem] | None = None,
    actions: list[ActionRecommendation] | None = None,
    limitations: list[str] | None = None,
) -> CoreIntelligenceResponse:
    ready_for_trend_cnt = 1 if readiness_state == "ready_for_trend" else 0
    return CoreIntelligenceResponse(
        intelligence_type=intelligence_type,
        portal_type=portal_type,
        data_status="available" if readiness_state == "ready_for_trend" else "insufficient_data",
        data_state="ready" if readiness_state == "ready_for_trend" else "insufficient_data",
        data_origin="real",
        history_type="platform_collected",
        time_window="6m",
        readiness=ReadinessSummary(
            overall_readiness_state=readiness_state,
            total_series_assessed=1,
            ready_for_trend_count=ready_for_trend_cnt,
            ready_for_forecast_count=0,
            blocked_count=1 if "blocked" in readiness_state else 0,
            blocking_reasons=[] if readiness_state == "ready_for_trend" else ["Readiness criteria not met"],
        ),
        answer=CoreIntelligenceAnswer(
            headline=headline,
            summary=summary,
            domain=intelligence_type,
            portal=portal_type,
            readiness_status=readiness_state,
            contextual_focus=contextual_focus,
            limitations=limitations or [],
        ),
        historical_trends=trends or [],
        action_recommendations=actions or [],
    )


# -------------------------------------------------------------------------
# A. READINESS CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_a_readiness_consistency_ready_for_trend():
    """When trend is ready, consistency validator passes and flags valid status."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency is not None
    assert resp.consistency.valid is True
    assert resp.consistency.source_readiness == "ready_for_trend"
    assert resp.consistency.forecast_locked is True


def test_criterion_a_readiness_consistency_insufficient_history():
    """When history < 4 periods, trend readiness is blocked and actions reflect insufficient history."""
    obs = [
        _make_obs(skill="Python", skill_id="python", period="2026-08", value=100.0),
        _make_obs(skill="Python", skill_id="python", period="2026-09", value=110.0),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency is not None
    assert resp.consistency.valid is True
    assert resp.consistency.source_readiness == "insufficient_history"
    for act in resp.action_recommendations:
        assert act.roadmap_eligible is False
        assert act.priority == "low"


# -------------------------------------------------------------------------
# B. TREND CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_b_trend_consistency_invariant_values():
    """Theil-Sen slope and direction are mathematically aligned."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    trend = resp.historical_trends[0]
    assert trend.is_trend_ready is True
    assert trend.trend_direction in ("Increasing", "Growing", "Up")
    assert trend.velocity is not None and trend.velocity > 0
    assert resp.consistency.trend_consistent is True


def test_criterion_b_trend_consistency_detects_contradiction():
    """Validator detects when direction contradicts velocity sign."""
    trend = _make_trend_item(
        trend_direction="Declining",  # Contradiction: Declining with positive velocity & growth
        trend_slope=0.05,
        growth_pct=15.0,
        velocity=0.015,
        is_trend_ready=True,
    )
    resp = _make_mock_response(
        readiness_state="ready_for_trend",
        trends=[trend],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is False
    assert result.trend_consistent is False
    assert any("Trend math contradiction" in v for v in result.violations)


# -------------------------------------------------------------------------
# C. ANSWER CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_c_answer_consistency_detects_unready_momentum_claim():
    """Validator detects when headline claims verified positive momentum while readiness is insufficient."""
    resp = _make_mock_response(
        readiness_state="insufficient_history",
        headline="Python demonstrates verified increasing demand",  # Contradiction
        summary="Strong growth observed",
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is False
    assert any("claims positive momentum" in v for v in result.violations)


# -------------------------------------------------------------------------
# D. ACTION CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_d_action_consistency_unready_blocks_roadmap():
    """Validator detects if an action marks roadmap_eligible=True when upstream readiness is unready."""
    action = _make_action_item(
        action_id="act-test-01",
        action_type="review_skill",
        title="Adopt Immediately",
        summary="Adopt immediately without data",
        why_it_matters="FACT: None. INTERPRETATION: Test. ACTION: Adopt.",
        recommended_action="Invest heavily",
        priority="high",  # Contradiction
        roadmap_eligible=True,  # Contradiction
        readiness_status="insufficient_data",
    )
    resp = _make_mock_response(
        readiness_state="insufficient_data",
        actions=[action],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is False
    assert any("roadmap_eligible=True" in v for v in result.violations)
    assert any("priority='high'" in v for v in result.violations)


# -------------------------------------------------------------------------
# E. EVIDENCE CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_e_evidence_consistency():
    """Evidence sources and observations are traceable."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency.evidence_consistent is True
    assert "sources_used" in resp.evidence


# -------------------------------------------------------------------------
# F. ROADMAP ELIGIBILITY CONSISTENCY
# -------------------------------------------------------------------------

def test_criterion_f_roadmap_eligibility():
    """roadmap_eligible is True only when trend is ready."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert any(a.roadmap_eligible for a in resp.action_recommendations)


# -------------------------------------------------------------------------
# G. BLOCKED QUALITY
# -------------------------------------------------------------------------

def test_criterion_g_blocked_quality():
    """Readiness state blocked_quality prevents trend and roadmap recommendations."""
    action = _make_action_item(
        action_id="act-quality-01",
        action_type="monitor_market_signal",
        title="Resolve Data Quality Anomaly",
        summary="Quality checks flagged anomalies",
        why_it_matters="FACT: Data quality checks flagged anomalies. INTERPRETATION: Blocked. ACTION: Resolve.",
        recommended_action="Audit raw observation data",
        priority="low",
        roadmap_eligible=False,
        readiness_status="blocked_quality",
    )
    resp = _make_mock_response(
        readiness_state="blocked_quality",
        headline="Analytical Readiness Gate: Data Blocked (blocked_quality)",
        summary="Quality checks failed",
        actions=[action],
        limitations=["Quality check failed"],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is True
    assert result.source_readiness == "blocked_quality"


# -------------------------------------------------------------------------
# H. BLOCKED COVERAGE
# -------------------------------------------------------------------------

def test_criterion_h_blocked_coverage():
    """Readiness state blocked_coverage correctly propagates."""
    action = _make_action_item(
        action_id="act-cov-01",
        action_type="monitor_skill_relevance",
        title="Widen Market Data Ingestion",
        summary="Coverage is restricted",
        why_it_matters="FACT: Coverage is restricted. INTERPRETATION: Blocked. ACTION: Ingest.",
        recommended_action="Expand providers",
        priority="low",
        roadmap_eligible=False,
        readiness_status="blocked_coverage",
        portal="employee",
    )
    resp = _make_mock_response(
        portal_type="employee",
        readiness_state="blocked_coverage",
        headline="Analytical Readiness Gate: Data Blocked (blocked_coverage)",
        summary="Insufficient market coverage",
        contextual_focus="Internal team mobility and career progression",
        actions=[action],
        limitations=["Coverage below threshold"],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is True
    assert result.source_readiness == "blocked_coverage"


# -------------------------------------------------------------------------
# I. BLOCKED CONFIGURATION
# -------------------------------------------------------------------------

def test_criterion_i_blocked_configuration():
    """Readiness state blocked_configuration correctly handled."""
    action = _make_action_item(
        action_id="act-cfg-01",
        action_type="review_workforce_exposure",
        title="Correct Analytical Configuration",
        summary="Configuration mismatch",
        why_it_matters="FACT: Configuration mismatch. INTERPRETATION: Blocked. ACTION: Review.",
        recommended_action="Validate taxonomy",
        priority="low",
        roadmap_eligible=False,
        readiness_status="blocked_configuration",
        portal="company",
    )
    resp = _make_mock_response(
        portal_type="company",
        readiness_state="blocked_configuration",
        headline="Analytical Readiness Gate: Data Blocked (blocked_configuration)",
        summary="Skill definition or baseline window invalid",
        contextual_focus="Enterprise workforce planning and talent allocation",
        actions=[action],
        limitations=["Configuration invalid"],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is True
    assert result.source_readiness == "blocked_configuration"


# -------------------------------------------------------------------------
# J. MISSING PERIOD
# -------------------------------------------------------------------------

def test_criterion_j_missing_period():
    """Gapped periods trigger blocked_missing_period or gap warnings."""
    action = _make_action_item(
        action_id="act-gap-01",
        action_type="monitor_market_signal",
        title="Heal Time-Series Observations",
        summary="Sequence gap detected",
        why_it_matters="FACT: Time-series gaps exist. INTERPRETATION: Incomplete. ACTION: Collect.",
        recommended_action="Execute backfill",
        priority="low",
        roadmap_eligible=False,
        readiness_status="blocked_missing_period",
    )
    resp = _make_mock_response(
        readiness_state="blocked_missing_period",
        headline="Analytical Readiness Gate: Data Blocked (blocked_missing_period)",
        summary="Sequence gap detected",
        actions=[action],
        limitations=["Missing observation period"],
    )
    result = IntelligenceConsistencyService.validate(resp)
    assert result.valid is True
    assert result.source_readiness == "blocked_missing_period"


# -------------------------------------------------------------------------
# K. INSUFFICIENT HISTORY
# -------------------------------------------------------------------------

def test_criterion_k_insufficient_history():
    """Series with fewer than 4 periods reports insufficient_history correctly."""
    obs = [
        _make_obs(skill="Python", skill_id="python", period="2026-08", value=100.0),
        _make_obs(skill="Python", skill_id="python", period="2026-09", value=110.0),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency.valid is True
    assert resp.consistency.source_readiness == "insufficient_history"


# -------------------------------------------------------------------------
# L. INSUFFICIENT DATA
# -------------------------------------------------------------------------

def test_criterion_l_insufficient_data():
    """0 observations reports insufficient_data correctly."""
    store = MockObservationStore([])
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.data_status == "insufficient_data"
    assert resp.consistency.valid is True
    assert resp.consistency.source_readiness == "insufficient_data"
    for act in resp.action_recommendations:
        assert act.roadmap_eligible is False
        assert act.priority == "low"


# -------------------------------------------------------------------------
# M. FORECAST LOCK
# -------------------------------------------------------------------------

def test_criterion_m_forecast_lock():
    """ready_for_forecast_count is 0 and is_forecast_ready is False across all responses."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.readiness.ready_for_forecast_count == 0
    assert resp.consistency.forecast_locked is True
    for tr in resp.historical_trends:
        assert tr.is_forecast_ready is False


# -------------------------------------------------------------------------
# N. PRODUCTION / TEST DATA SEPARATION
# -------------------------------------------------------------------------

def test_criterion_n_production_test_data_separation():
    """Test fixtures run strictly against MockObservationStore without leaking to production."""
    store = MockObservationStore([])
    svc = CoreIntelligenceService(observation_store=store)
    assert svc._get_store() is store
    assert store.read_count == 0


# -------------------------------------------------------------------------
# O. FALLBACK FABRICATION AUDIT
# -------------------------------------------------------------------------

def test_criterion_o_fallback_fabrication_audit():
    """No synthetic zeros or fabricated values exist in unready states."""
    # 1. With few observations (<4 periods), trend item exists but direction is 'Insufficient Data' with None velocity
    obs = [_make_obs(skill="Python", skill_id="python", period="2026-09", value=100.0)]
    store1 = MockObservationStore(obs)
    svc1 = CoreIntelligenceService(observation_store=store1)
    req1 = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp1 = svc1.get_intelligence(req1)
    assert len(resp1.historical_trends) > 0
    trend = resp1.historical_trends[0]
    assert trend.growth_pct is None
    assert trend.velocity is None
    assert trend.trend_direction == "Insufficient Data"

    # 2. With 0 observations, no fake trends are created
    store2 = MockObservationStore([])
    svc2 = CoreIntelligenceService(observation_store=store2)
    resp2 = svc2.get_intelligence(req1)
    assert resp2.data_status == "insufficient_data"
    assert len(resp2.historical_trends) == 0


# -------------------------------------------------------------------------
# P. INDIVIDUAL CONTEXT
# -------------------------------------------------------------------------

def test_criterion_p_individual_context():
    """Individual portal contextual focus aligns with career development."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency.valid is True
    assert resp.consistency.context_aligned is True
    assert "individual" in resp.answer.contextual_focus.lower() or "career" in resp.answer.contextual_focus.lower()


# -------------------------------------------------------------------------
# Q. EMPLOYEE CONTEXT
# -------------------------------------------------------------------------

def test_criterion_q_employee_context():
    """Employee portal contextual focus aligns with internal mobility."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="employee",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
        employee_context=EmployeeContext(department="Engineering", current_role="Software Engineer"),
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency.valid is True
    assert resp.consistency.context_aligned is True
    assert "internal" in resp.answer.contextual_focus.lower() or "team" in resp.answer.contextual_focus.lower()


# -------------------------------------------------------------------------
# R. COMPANY CONTEXT
# -------------------------------------------------------------------------

def test_criterion_r_company_context():
    """Company portal contextual focus aligns with workforce strategy."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="company",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
        company_context=CompanyContext(industry="Technology", organization_size="500-1000"),
    )
    resp = svc.get_intelligence(req)
    assert resp.consistency.valid is True
    assert resp.consistency.context_aligned is True
    assert "workforce" in resp.answer.contextual_focus.lower() or "enterprise" in resp.answer.contextual_focus.lower()


# -------------------------------------------------------------------------
# S. DETERMINISTIC OUTPUT
# -------------------------------------------------------------------------

def test_criterion_s_deterministic_output():
    """Identical requests yield identical consistency reports."""
    obs = _make_trend_ready_observations("Python", "python")
    store1 = MockObservationStore(obs)
    store2 = MockObservationStore(obs)
    svc1 = CoreIntelligenceService(observation_store=store1)
    svc2 = CoreIntelligenceService(observation_store=store2)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp1 = svc1.get_intelligence(req)
    resp2 = svc2.get_intelligence(req)

    assert resp1.consistency.valid == resp2.consistency.valid
    assert resp1.consistency.status == resp2.consistency.status
    assert resp1.consistency.violations == resp2.consistency.violations
    assert resp1.consistency.source_readiness == resp2.consistency.source_readiness
    assert len(resp1.consistency.checks) == len(resp2.consistency.checks)


# -------------------------------------------------------------------------
# T. AUTHENTICATION REQUIRED
# -------------------------------------------------------------------------

def test_criterion_t_authentication_required():
    """Intelligence and Actions APIs reject unauthenticated requests with HTTP 401."""
    client = TestClient(app)

    # Core intelligence endpoint unauthenticated
    resp_core = client.post(
        "/api/v1/intelligence/core",
        json={"portal_type": "individual", "intelligence_type": "skill"},
    )
    assert resp_core.status_code == 401

    # Actions endpoint unauthenticated
    resp_action = client.post(
        "/api/v1/intelligence/actions",
        json={"portal_type": "individual", "intelligence_type": "skill"},
    )
    assert resp_action.status_code == 401


# -------------------------------------------------------------------------
# U. FIRESTORE READ SAFETY
# -------------------------------------------------------------------------

def test_criterion_u_firestore_read_safety():
    """Mock store receives exactly bounded reads and zero live Firestore access occurs."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert store.read_count == 1
    assert resp.consistency is not None

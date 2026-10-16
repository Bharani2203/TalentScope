"""Comprehensive test suite for G2.5: Action & Recommendation Intelligence.

Verifies Criteria A through N:
A. trend-ready skill
B. insufficient history
C. insufficient data
D. unavailable market dimension
E. Individual context
F. Employee context
G. Company context
H. evidence preservation
I. roadmap eligibility
J. no forecast generation
K. no fake zeros
L. deterministic output
M. authentication
N. Firestore read safety
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.core_intelligence import (
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
)
from app.models.action_recommendation import (
    ActionRecommendation,
    ActionRecommendationResponse,
)
from app.models.skill_intelligence import MarketObservation
from app.services.action_recommendation_service import (
    CALCULATION_VERSION,
    build_action_recommendations,
)
from app.services.core_intelligence_service import CoreIntelligenceService


# -------------------------------------------------------------------------
# Test Fixtures & Mock Store (Criterion N: Firestore Read Safety)
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
    denominator: float | None = 1000.0,
    location: str = "Global",
    fetch_run_id: str = "run-1",
    raw_archive_id: str = "raw-archive-123",
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
        unit={
            "interest": "tagged_questions",
            "adoption": "developers",
            "demand": "job_postings",
            "pageviews": "pageviews",
        }.get(signal_type, "observations"),
        denominator=denominator,
        data_origin="real",
        history_type="backfill" if source == "stackexchange" else "platform_collected",
        series_id=f"{source}:{signal_type}:{skill_id}:v1",
        quality="valid",
        confidence=0.92,
        fetch_run_id=fetch_run_id,
        metadata={"raw_archive_id": raw_archive_id},
    )


def _make_trend_ready_observations(skill: str = "Python", skill_id: str = "python", direction: str = "increasing") -> list[MarketObservation]:
    """Create 5 consecutive monthly observations (>= 4 required for trend readiness)."""
    if direction == "increasing":
        vals = [100.0, 115.0, 130.0, 145.0, 160.0]
    elif direction == "declining":
        vals = [160.0, 145.0, 130.0, 115.0, 100.0]
    else:  # stable
        vals = [120.0, 121.0, 120.0, 119.0, 120.0]

    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    return [
        _make_obs(
            skill=skill,
            skill_id=skill_id,
            period=periods[i],
            value=vals[i],
            denominator=1000.0,
            raw_archive_id=f"archive-{skill_id}-{periods[i]}",
        )
        for i in range(5)
    ]


# -------------------------------------------------------------------------
# A. TREND-READY SKILL
# -------------------------------------------------------------------------

def test_criterion_a_trend_ready_skill():
    """Trend-ready skill generates deterministic action based on verified mathematical facts."""
    obs = _make_trend_ready_observations("Python", "python", direction="declining")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert resp.data_status == "available"
    assert len(resp.action_recommendations) > 0

    rec = resp.action_recommendations[0]
    assert rec.readiness_status == "ready_for_trend"
    assert rec.action_type == "review_skill"
    assert rec.priority == "high"
    assert "declining" in rec.why_it_matters.lower()
    assert "consecutive observations" in rec.why_it_matters.lower()
    assert "Review Python skill relevance" in rec.title or "Review Python" in rec.title
    assert rec.roadmap_eligible is True
    assert len(rec.evidence_references) > 0


# -------------------------------------------------------------------------
# B. INSUFFICIENT HISTORY (< 4 periods)
# -------------------------------------------------------------------------

def test_criterion_b_insufficient_history():
    """Skill with < 4 periods yields observation/monitoring action and LOW priority."""
    obs = [
        _make_obs(period="2026-09", value=50.0, skill="Rust", skill_id="rust"),
        _make_obs(period="2026-10", value=55.0, skill="Rust", skill_id="rust"),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Rust"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)
    assert len(resp.action_recommendations) > 0

    rec = resp.action_recommendations[0]
    assert rec.readiness_status == "insufficient_history"
    assert rec.action_type == "monitor_market_signal"
    assert rec.priority == "low"
    assert rec.roadmap_eligible is False
    assert "Monitor this skill until additional validated historical observations are available." in rec.recommended_action
    assert any("insufficient" in lim.lower() for lim in rec.limitations)


# -------------------------------------------------------------------------
# C. INSUFFICIENT DATA
# -------------------------------------------------------------------------

def test_criterion_c_insufficient_data():
    """When zero observations exist, return honest insufficient data state and explicit limitation."""
    store = MockObservationStore([])
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["UnknownSkillXYZ"],
        time_range="30d",
    )
    resp = svc.get_intelligence(req)
    assert resp.data_status == "insufficient_data"
    assert len(resp.action_recommendations) > 0

    rec = resp.action_recommendations[0]
    assert rec.readiness_status == "insufficient_data"
    assert rec.priority == "low"
    assert rec.roadmap_eligible is False
    assert "Action cannot be reliably recommended because verified market history is insufficient." in rec.recommended_action
    assert any("insufficient" in lim.lower() for lim in rec.limitations)


# -------------------------------------------------------------------------
# D. UNAVAILABLE MARKET DIMENSION
# -------------------------------------------------------------------------

def test_criterion_d_unavailable_market_dimension():
    """Unavailable dimensions (e.g. investment/funding) are explicitly stated in limitations and not inferred."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="individual", intelligence_type="market")
    actions_res = svc.get_action_recommendations(req)

    assert any("investment" in lim.lower() and "unavailable" in lim.lower() for lim in actions_res.limitations)
    for rec in actions_res.recommendations:
        assert "investment" not in rec.action_type.lower()
        assert "funding" not in rec.action_type.lower()


# -------------------------------------------------------------------------
# E. INDIVIDUAL CONTEXT
# -------------------------------------------------------------------------

def test_criterion_e_individual_context():
    """Individual portal focuses on Personal Skill Relevance & Learning Roadmap."""
    obs = _make_trend_ready_observations("Python", "python", direction="increasing")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    actions_res = svc.get_action_recommendations(req)

    assert actions_res.contextual_focus == "Personal Skill Relevance & Learning Roadmap"
    assert len(actions_res.recommendations) > 0
    rec = actions_res.recommendations[0]
    assert rec.portal == "individual"
    assert rec.action_type in (
        "review_skill", "strengthen_skill", "learn_related_skill",
        "compare_career_direction", "review_job_readiness", "update_roadmap", "monitor_market_signal"
    )
    assert rec.action_type == "strengthen_skill"
    assert rec.roadmap_eligible is True


# -------------------------------------------------------------------------
# F. EMPLOYEE CONTEXT
# -------------------------------------------------------------------------

def test_criterion_f_employee_context():
    """Employee portal focuses on Internal Mobility & Role Alignment."""
    obs = _make_trend_ready_observations("Python", "python", direction="increasing")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="employee",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    actions_res = svc.get_action_recommendations(req)

    assert actions_res.contextual_focus == "Internal Mobility & Role Alignment"
    assert len(actions_res.recommendations) > 0
    rec = actions_res.recommendations[0]
    assert rec.portal == "employee"
    assert rec.action_type in (
        "strengthen_capability", "explore_internal_mobility", "review_role_alignment",
        "join_relevant_learning", "seek_project_exposure", "monitor_skill_relevance"
    )
    assert rec.action_type == "strengthen_capability"
    assert "mobility" in rec.recommended_action.lower() or "internal" in rec.recommended_action.lower()


# -------------------------------------------------------------------------
# G. COMPANY CONTEXT
# -------------------------------------------------------------------------

def test_criterion_g_company_context():
    """Company portal focuses on Enterprise Workforce Planning & Reskilling."""
    obs = _make_trend_ready_observations("Python", "python", direction="declining")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="company",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    actions_res = svc.get_action_recommendations(req)

    assert actions_res.contextual_focus == "Enterprise Workforce Planning & Reskilling"
    assert len(actions_res.recommendations) > 0
    rec = actions_res.recommendations[0]
    assert rec.portal == "company"
    assert rec.target_type == "workforce"
    assert rec.action_type in (
        "review_workforce_exposure", "identify_skill_gap", "prioritize_upskilling",
        "review_reskilling_need", "review_internal_mobility", "monitor_role_capability", "review_hiring_requirement"
    )
    assert rec.action_type == "review_reskilling_need"
    assert "workforce" in rec.recommended_action.lower() or "reskilling" in rec.recommended_action.lower()


# -------------------------------------------------------------------------
# H. EVIDENCE PRESERVATION
# -------------------------------------------------------------------------

def test_criterion_h_evidence_preservation():
    """Evidence references and provenance are retained end-to-end in action recommendations."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="individual", selected_skills=["Python"], time_range="6m")
    actions_res = svc.get_action_recommendations(req)

    assert "observations_count" in actions_res.evidence_summary
    assert actions_res.evidence_summary["observations_count"] == 5
    assert len(actions_res.evidence_summary["raw_archive_references"]) > 0

    rec = actions_res.recommendations[0]
    assert len(rec.evidence_references) > 0
    assert any("archive" in ref for ref in rec.evidence_references)


# -------------------------------------------------------------------------
# I. ROADMAP ELIGIBILITY
# -------------------------------------------------------------------------

def test_criterion_i_roadmap_eligibility():
    """Roadmap eligibility is True for trend-ready actions, False for monitoring/insufficient data."""
    # 1. Trend ready -> True
    ready_obs = _make_trend_ready_observations("Python", "python")
    svc_ready = CoreIntelligenceService(MockObservationStore(ready_obs))
    res_ready = svc_ready.get_action_recommendations(CoreIntelligenceRequest(selected_skills=["Python"], time_range="6m"))
    assert res_ready.recommendations[0].roadmap_eligible is True

    # 2. Insufficient history -> False
    short_obs = [_make_obs(period="2026-10", skill="Go", skill_id="go")]
    svc_short = CoreIntelligenceService(MockObservationStore(short_obs))
    res_short = svc_short.get_action_recommendations(CoreIntelligenceRequest(selected_skills=["Go"]))
    assert res_short.recommendations[0].roadmap_eligible is False

    # 3. Insufficient data -> False
    svc_empty = CoreIntelligenceService(MockObservationStore([]))
    res_empty = svc_empty.get_action_recommendations(CoreIntelligenceRequest(selected_skills=["Missing"]))
    assert res_empty.recommendations[0].roadmap_eligible is False


# -------------------------------------------------------------------------
# J. NO FORECAST GENERATION
# -------------------------------------------------------------------------

def test_criterion_j_no_forecast_generation():
    """Strictly verify is_forecast_ready is false, no predictions or simulated counts."""
    obs = _make_trend_ready_observations("Python", "python")
    svc = CoreIntelligenceService(MockObservationStore(obs))

    req = CoreIntelligenceRequest(portal_type="individual", selected_skills=["Python"], time_range="6m")
    resp = svc.get_intelligence(req)

    assert resp.readiness.ready_for_forecast_count == 0
    for trend in resp.historical_trends:
        assert trend.is_forecast_ready is False

    actions_res = svc.get_action_recommendations(req)
    for rec in actions_res.recommendations:
        # Check that limitations declare forecasting is inactive
        assert any("is_forecast_ready = false" in lim for lim in rec.limitations)
        # Ensure title/action does not promise guaranteed future metrics
        assert "guaranteed" not in rec.recommended_action.lower()
        assert "predicted salary" not in rec.why_it_matters.lower()


# -------------------------------------------------------------------------
# K. NO FAKE ZEROS
# -------------------------------------------------------------------------

def test_criterion_k_no_fake_zeros():
    """Missing or insufficient values remain null/None, never fabricated as zero."""
    store = MockObservationStore([])
    svc = CoreIntelligenceService(store)
    req = CoreIntelligenceRequest(selected_skills=["C++"])
    resp = svc.get_intelligence(req)

    assert resp.data_status == "insufficient_data"
    for trend in resp.historical_trends:
        assert trend.growth_pct is None
        assert trend.velocity is None
        assert trend.trend_slope is None


# -------------------------------------------------------------------------
# L. DETERMINISTIC OUTPUT
# -------------------------------------------------------------------------

def test_criterion_l_deterministic_output():
    """Identical requests over identical observations produce strictly identical outputs."""
    obs = _make_trend_ready_observations("Python", "python")
    store1 = MockObservationStore(obs)
    store2 = MockObservationStore(obs)

    svc1 = CoreIntelligenceService(store1)
    svc2 = CoreIntelligenceService(store2)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )

    res1 = svc1.get_action_recommendations(req)
    res2 = svc2.get_action_recommendations(req)

    assert res1.data_status == res2.data_status
    assert res1.contextual_focus == res2.contextual_focus
    assert len(res1.recommendations) == len(res2.recommendations)

    rec1 = res1.recommendations[0]
    rec2 = res2.recommendations[0]

    assert rec1.action_id == rec2.action_id
    assert rec1.action_type == rec2.action_type
    assert rec1.title == rec2.title
    assert rec1.why_it_matters == rec2.why_it_matters
    assert rec1.recommended_action == rec2.recommended_action
    assert rec1.priority == rec2.priority


# -------------------------------------------------------------------------
# M. AUTHENTICATION REQUIREMENT
# -------------------------------------------------------------------------

def test_criterion_m_authentication(monkeypatch):
    """POST /api/v1/intelligence/actions requires Bearer token authentication."""
    from firebase_admin import auth
    from app.api import dependencies

    client = TestClient(app)

    # 1. Without token -> 401 Unauthorized
    resp_unauth = client.post(
        "/api/v1/intelligence/actions",
        json={"portal_type": "individual", "intelligence_type": "skill"},
    )
    assert resp_unauth.status_code == 401

    # 2. With invalid token -> 401 Unauthorized
    def reject_token(token, **kwargs):
        raise auth.InvalidIdTokenError("invalid token")

    monkeypatch.setattr(dependencies.auth, "verify_id_token", reject_token)
    resp_invalid = client.post(
        "/api/v1/intelligence/actions",
        headers={"Authorization": "Bearer invalid_token_123"},
        json={"portal_type": "individual", "intelligence_type": "skill"},
    )
    assert resp_invalid.status_code == 401


# -------------------------------------------------------------------------
# N. FIRESTORE READ SAFETY
# -------------------------------------------------------------------------

def test_criterion_n_firestore_read_safety():
    """Verify that CoreIntelligenceService and ActionRecommendation execute bounded observation reads."""
    obs = _make_trend_ready_observations("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )

    # Calling get_action_recommendations should execute exactly 1 bounded store read
    res = svc.get_action_recommendations(req)
    assert store.read_count == 1
    assert len(res.recommendations) > 0

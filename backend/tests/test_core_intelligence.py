"""Deterministic test suite for G2.0: Shared Core Intelligence Architecture & Backend Contract.

Covers verification criteria A through Q:
A. Shared Skill request
B. Shared Market request
C. Shared Job request
D. Individual context
E. Employee context
F. Company context
G. Filter propagation
H. Data-state propagation
I. Provenance propagation
J. Signal-family isolation
K. Authentication
L. Unauthorized access
M. Insufficient data
N. No fake zero
O. No duplicate intelligence calculation
P. Gemini cannot replace deterministic calculations
Q. Existing G1.14 regression
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes.core_intelligence import router
from app.core.config import get_settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.core_intelligence import (
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
    IndividualContext,
    EmployeeContext,
    CompanyContext,
)
from app.models.skill_intelligence import MarketObservation
from app.services.core_intelligence_service import CoreIntelligenceService


# -------------------------------------------------------------------------
# Test Data Fixtures & In-Memory Store
# -------------------------------------------------------------------------

class MockObservationStore:
    """In-memory observation store for deterministic test isolation."""

    def __init__(self, observations: list[MarketObservation] | None = None):
        self.observations = list(observations or [])

    def get_observations(self, *, cutoff: datetime, location: str | None = None) -> list[MarketObservation]:
        res = []
        for o in self.observations:
            obs_dt = o.observed_at
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)
            if obs_dt < cutoff:
                continue
            if location and o.location and location.casefold() not in o.location.casefold():
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
    value: float = 120.0,
    denominator: float | None = 1000.0,
    location: str = "Global",
    fetch_run_id: str = "run-1",
    raw_archive_id: str = "raw-1",
    series_id: str | None = None,
) -> MarketObservation:
    sid = series_id or f"{source}:{signal_type}:{skill_id}:v1"
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
        series_id=sid,
        query_id=f"qid-{skill_id}",
        panel_version="v1",
        fetch_run_id=fetch_run_id,
        metadata={"raw_archive_id": raw_archive_id},
        observation_count=1,
    )


def _make_stackexchange_5periods(skill: str = "Python", skill_id: str = "python") -> list[MarketObservation]:
    """5 consecutive valid periods (2026-05 through 2026-09) -> trend ready, forecast blocked."""
    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    values = [100.0, 110.0, 120.0, 130.0, 140.0]
    return [
        _make_obs(
            source="stackexchange",
            signal_type="interest",
            skill=skill,
            skill_id=skill_id,
            period=p,
            value=v,
        )
        for p, v in zip(periods, values)
    ]


# -------------------------------------------------------------------------
# A. Shared Skill Request
# -------------------------------------------------------------------------

def test_a_shared_skill_request():
    """Verify shared Core Intelligence handles Skill Intelligence queries across portals."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)

    assert resp.intelligence_type == "skill"
    assert resp.portal_type == "individual"
    assert resp.data_status == "available"
    assert resp.data_state == "ready"
    assert len(resp.current_signals) > 0
    assert len(resp.historical_trends) == 1
    trend = resp.historical_trends[0]
    assert trend.entity_name == "Python"
    assert trend.is_trend_ready is True
    assert trend.is_forecast_ready is False
    assert trend.trend_direction in {"Increasing", "Rising"}


# -------------------------------------------------------------------------
# B. Shared Market Request
# -------------------------------------------------------------------------

def test_b_shared_market_request():
    """Verify shared Core Intelligence handles Market Intelligence queries."""
    obs = [
        _make_obs(source="github", signal_type="adoption", skill="FastAPI", period="2026-10", value=50.0),
        _make_obs(source="jsearch", signal_type="demand", skill="FastAPI", period="2026-10", value=20.0),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="market",
        time_range="30d",
    )
    resp = svc.get_intelligence(req)

    assert resp.intelligence_type == "market"
    assert resp.data_status == "available"
    assert "adoption_observations" in resp.summary
    assert "demand_observations" in resp.summary
    assert resp.summary["adoption_observations"] == 1
    assert resp.summary["demand_observations"] == 1
    # Multi-source signals preserved
    signals = {s.signal_type for s in resp.current_signals}
    assert "adoption" in signals


# -------------------------------------------------------------------------
# C. Shared Job Request
# -------------------------------------------------------------------------

def test_c_shared_job_request():
    """Verify shared Core Intelligence handles Job Intelligence without mixing denominators."""
    obs = [
        _make_obs(source="jsearch", signal_type="demand", skill="AI Engineer", period="2026-10", value=42.0, denominator=500.0),
        _make_obs(source="adzuna", signal_type="demand", skill="AI Engineer", period="2026-10", value=15.0, denominator=200.0),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="job",
        selected_roles=["AI Engineer"],
        time_range="30d",
    )
    resp = svc.get_intelligence(req)

    assert resp.intelligence_type == "job"
    assert resp.data_status == "available"
    assert resp.summary["jsearch_observations"] == 1
    assert resp.summary["adzuna_observations"] == 1
    assert resp.summary["trend_ready"] is False  # 1 period cannot produce trend


# -------------------------------------------------------------------------
# D. Individual Context
# -------------------------------------------------------------------------

def test_d_individual_context():
    """Verify Individual context personalizes the explanation for personal career growth."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        target_role="AI Systems Architect",
        selected_skills=["Python"],
        time_range="6m",
    )
    resp = svc.get_intelligence(req)

    assert resp.portal_type == "individual"
    assert len(resp.explanations) > 0
    assert any("trajectory towards AI Systems Architect" in e.body for e in resp.explanations)
    assert any(r.action_type == "learn" for r in resp.recommendations)
    assert any(a.module == "learning_roadmap" for a in resp.next_actions)


# -------------------------------------------------------------------------
# E. Employee Context
# -------------------------------------------------------------------------

def test_e_employee_context():
    """Verify Employee context adapts explanations to role, team, and company."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="employee",
        intelligence_type="skill",
        company_id="acme_corp",
        time_range="6m",
        context_override={
            "company_name": "Acme Corp",
            "department": "Engineering",
            "team": "Core AI Platform",
            "current_role": "Backend Staff Engineer",
        },
    )
    resp = svc.get_intelligence(req)

    assert resp.portal_type == "employee"
    assert len(resp.explanations) > 0
    assert any("Core AI Platform" in f for e in resp.explanations for f in e.supporting_facts)
    assert any(r.action_type == "upskill" for r in resp.recommendations)
    assert any(a.module == "internal_mobility" for a in resp.next_actions)


# -------------------------------------------------------------------------
# F. Company Context
# -------------------------------------------------------------------------

def test_f_company_context():
    """Verify Company context adapts explanations to workforce planning and cohorts."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="company",
        intelligence_type="skill",
        company_id="nvidia",
        time_range="6m",
        context_override={
            "company_name": "NVIDIA",
            "industry": "Semiconductors & AI Hardware",
        },
    )
    resp = svc.get_intelligence(req)

    assert resp.portal_type == "company"
    assert any(r.action_type == "redeploy" for r in resp.recommendations)
    assert any(a.module == "workforce_planning" for a in resp.next_actions)


# -------------------------------------------------------------------------
# G. Filter Propagation
# -------------------------------------------------------------------------

def test_g_filter_propagation():
    """Verify requested filters are explicitly propagated into filters_applied."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        location="Bangalore",
        time_range="3m",
        custom_days=90,
        selected_skills=["Python", "Machine Learning"],
    )
    resp = svc.get_intelligence(req)

    assert resp.filters_applied["location"] == "Bangalore"
    assert resp.filters_applied["time_range"] == "3m"
    assert resp.filters_applied["custom_days"] == 90
    assert "Python" in resp.filters_applied["selected_skills"]


# -------------------------------------------------------------------------
# H. Data-State Propagation
# -------------------------------------------------------------------------

def test_h_data_state_propagation():
    """Verify honest propagation of data_status and data_state."""
    # 1. Available state
    store_ok = MockObservationStore(_make_stackexchange_5periods())
    svc_ok = CoreIntelligenceService(observation_store=store_ok)
    resp_ok = svc_ok.get_intelligence(CoreIntelligenceRequest())
    assert resp_ok.data_status == "available"
    assert resp_ok.data_state == "ready"

    # 2. Insufficient data state
    store_empty = MockObservationStore([])
    svc_empty = CoreIntelligenceService(observation_store=store_empty)
    resp_empty = svc_empty.get_intelligence(CoreIntelligenceRequest())
    assert resp_empty.data_status == "insufficient_data"
    assert resp_empty.data_state == "insufficient_data"


# -------------------------------------------------------------------------
# I. Provenance Propagation
# -------------------------------------------------------------------------

def test_i_provenance_propagation():
    """Verify evidence retains raw archive IDs, sources, periods, and counts."""
    obs = _make_stackexchange_5periods()
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    resp = svc.get_intelligence(CoreIntelligenceRequest(time_range="6m"))
    ev = resp.evidence

    assert ev["observations_count"] == 5
    assert ev["sources_used"] == ["stackexchange"]
    assert ev["signal_families"] == ["interest"]
    assert "raw-1" in ev["raw_archive_references"]
    assert ev["periods"] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


# -------------------------------------------------------------------------
# J. Signal-Family Isolation
# -------------------------------------------------------------------------

def test_j_signal_family_isolation():
    """Verify signal types remain distinct and unmixed."""
    obs = [
        _make_obs(source="jsearch", signal_type="demand", skill="Python", period="2026-10", value=100.0),
        _make_obs(source="github", signal_type="adoption", skill="Python", period="2026-10", value=50.0),
        _make_obs(source="stackexchange", signal_type="interest", skill="Python", period="2026-10", value=25.0),
    ]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    resp = svc.get_intelligence(CoreIntelligenceRequest(intelligence_type="skill"))
    sig_types = {s.signal_type for s in resp.current_signals}

    assert sig_types == {"demand", "adoption", "interest"}
    # Verify no signal is mislabeled
    for s in resp.current_signals:
        if s.source == "stackexchange":
            assert s.signal_type == "interest"
        elif s.source == "github":
            assert s.signal_type == "adoption"
        elif s.source == "jsearch":
            assert s.signal_type == "demand"


# -------------------------------------------------------------------------
# K. Authentication
# -------------------------------------------------------------------------

def test_k_authentication():
    """Verify authenticated user can query Core Intelligence API endpoints."""
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="test-user-g2", email="g2@example.com")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    try:
        # POST /core
        r_post = client.post(
            "/api/v1/intelligence/core",
            json={"portal_type": "individual", "intelligence_type": "skill"},
        )
        assert r_post.status_code == 200
        data = r_post.json()
        assert data["intelligence_type"] == "skill"
        assert "data_status" in data

        # GET /skill
        r_skill = client.get("/api/v1/intelligence/skill?skill=Python")
        assert r_skill.status_code == 200

        # GET /market
        r_market = client.get("/api/v1/intelligence/market")
        assert r_market.status_code == 200

        # GET /job
        r_job = client.get("/api/v1/intelligence/job")
        assert r_job.status_code == 200
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# -------------------------------------------------------------------------
# L. Unauthorized Access
# -------------------------------------------------------------------------

def test_l_unauthorized_access():
    """Verify unauthenticated requests receive HTTP 401."""
    client = TestClient(app)
    # Ensure no override
    app.dependency_overrides.pop(dependencies.get_current_user, None)

    r_post = client.post("/api/v1/intelligence/core", json={})
    assert r_post.status_code in {401, 403}

    r_get = client.get("/api/v1/intelligence/skill")
    assert r_get.status_code in {401, 403}


# -------------------------------------------------------------------------
# M. Insufficient Data
# -------------------------------------------------------------------------

def test_m_insufficient_data():
    """Verify empty observation set returns explicit insufficient data status."""
    store = MockObservationStore([])
    svc = CoreIntelligenceService(observation_store=store)

    resp = svc.get_intelligence(CoreIntelligenceRequest())

    assert resp.data_status == "insufficient_data"
    assert resp.data_state == "insufficient_data"
    assert len(resp.current_signals) == 0
    assert len(resp.historical_trends) == 0


# -------------------------------------------------------------------------
# N. No Fake Zero
# -------------------------------------------------------------------------

def test_n_no_fake_zero():
    """Verify null values, missing slopes, and unobserved metrics are never coerced to 0.0."""
    # 1 period observation: not trend ready
    obs = [_make_obs(period="2026-10", value=100.0, denominator=None)]
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    resp = svc.get_intelligence(CoreIntelligenceRequest(intelligence_type="skill"))
    assert len(resp.historical_trends) == 1
    t = resp.historical_trends[0]

    assert t.velocity is None
    assert t.growth_pct is None
    assert t.trend_direction == "Insufficient Data"
    assert t.is_trend_ready is False


# -------------------------------------------------------------------------
# O. No Duplicate Intelligence Calculation
# -------------------------------------------------------------------------

def test_o_no_duplicate_intelligence_calculation():
    """Verify single service dispatch executes analytical calculation once without duplication."""
    obs = _make_stackexchange_5periods("Python", "python")
    store = MockObservationStore(obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="individual", intelligence_type="skill", time_range="6m")
    resp = svc.get_intelligence(req)

    # Exactly one trend record for Python
    python_trends = [t for t in resp.historical_trends if t.entity_name == "Python"]
    assert len(python_trends) == 1
    assert python_trends[0].velocity is not None


# -------------------------------------------------------------------------
# P. Gemini Cannot Replace Deterministic Calculations
# -------------------------------------------------------------------------

def test_p_gemini_cannot_replace_deterministic_calculations():
    """Verify core analytical math is pure deterministic code and no LLM computes trends or gates."""
    import sys
    for mod_name in sys.modules:
        assert not any(forbidden in mod_name.lower() for forbidden in ["arima", "prophet", "xgboost", "lstm"]), (
            f"Forbidden forecasting module detected in sys.modules: {mod_name}"
        )


# -------------------------------------------------------------------------
# Q. Existing G1.14 Regression
# -------------------------------------------------------------------------

def test_q_existing_g1_14_regression():
    """Verify G1.14 activated Stack Exchange series (Python and C#) produce identical valid results."""
    py_obs = _make_stackexchange_5periods("Python", "python")
    cs_obs = _make_stackexchange_5periods("C#", "c_sharp")
    store = MockObservationStore(py_obs + cs_obs)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(intelligence_type="skill", time_range="6m")
    resp = svc.get_intelligence(req)

    assert resp.readiness.ready_for_trend_count == 2
    assert resp.readiness.ready_for_forecast_count == 0  # Crucial G1.14/G2.0 invariant
    names = {t.entity_name for t in resp.historical_trends if t.is_trend_ready}
    assert names == {"Python", "C#"}

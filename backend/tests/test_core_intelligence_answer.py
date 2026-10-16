"""Deterministic test suite for G2.3: Core Intelligence Answer & Contextual Enrichment.

Verifies:
- Skill Intelligence: trend-ready (>=4 periods) vs insufficient history (<4 periods)
- Explicit mathematical slopes and velocities (no fake zeros, no synthetic extrapolation)
- HistoricalTrendItem enrichment (canonical_skill_id, display_name, trend_slope, limitations, explanation)
- Market Intelligence: multi-source synthesis, honest unavailable financial/investment metrics
- Job Intelligence: single-period 2026-10 baseline, no fake job counts, insufficient_data momentum
- Portal contextualization across Individual, Employee, and Company views
- Strict forecasting freeze (is_forecast_ready = false across all surfaces)
- Strict determinism and in-memory mock isolation (0 live Firestore reads)
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

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
# Test Fixtures & In-Memory Store
# -------------------------------------------------------------------------

class MockObservationStore:
    """In-memory observation store ensuring zero live Firestore reads."""

    def __init__(self, observations: list[MarketObservation] | None = None):
        self.observations = list(observations or [])

    def get_observations(self, *, cutoff: datetime, location: str | None = None, signal_type: str | None = None) -> list[MarketObservation]:
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
    raw_archive_id: str = "raw-1",
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


# -------------------------------------------------------------------------
# G2.3 TEST CASES
# -------------------------------------------------------------------------

def test_skill_intelligence_trend_ready_answer():
    """Skill with >= 4 periods yields trend-ready output, slope, and tailored answer."""
    # 4 consecutive periods with positive growth
    obs = [
        _make_obs(period="2026-06", value=100.0),
        _make_obs(period="2026-07", value=120.0),
        _make_obs(period="2026-08", value=140.0),
        _make_obs(period="2026-09", value=165.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["python"],
        time_range="6m",
    )
    res = service.get_intelligence(req)

    assert res.data_status == "available"
    assert res.data_state == "ready"
    assert len(res.historical_trends) >= 1

    trend = res.historical_trends[0]
    assert trend.is_trend_ready is True
    assert trend.is_forecast_ready is False  # Strictly false
    assert trend.canonical_skill_id == "python"
    assert trend.display_name == "Python"
    assert trend.trend_direction == "Increasing"
    assert trend.trend_slope is not None and trend.trend_slope > 0
    assert trend.growth_pct is not None and trend.growth_pct > 0
    assert trend.velocity is not None and trend.velocity > 0
    assert trend.confidence is not None
    assert trend.explanation is not None
    assert "Forecasting model inactive (is_forecast_ready = false)" in trend.limitations

    # Core Intelligence Answer verification
    answer = res.answer
    assert answer is not None
    assert answer.domain == "skill"
    assert answer.portal == "individual"
    assert answer.readiness_status == "ready_for_trend"
    assert answer.confidence is not None
    assert "Python" in answer.headline
    assert "Momentum" in answer.headline or "Rising" in answer.headline
    assert len(answer.key_insights) >= 2
    assert len(answer.evidence_citations) >= 2
    assert "Forecasting model inactive (is_forecast_ready = false)." in answer.limitations
    assert "Personal Skill Relevance" in answer.contextual_focus


def test_skill_intelligence_insufficient_history_honest_answer():
    """Skill with 1 period reports baseline without fake slope or zeros."""
    obs = [
        _make_obs(source="jsearch", signal_type="demand", period="2026-10", value=45.0, denominator=500.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["python"],
        time_range="30d",
    )
    res = service.get_intelligence(req)

    assert len(res.historical_trends) >= 1
    trend = res.historical_trends[0]
    assert trend.is_trend_ready is False
    assert trend.is_forecast_ready is False
    assert trend.trend_direction == "Insufficient Data"
    assert trend.trend_slope is None  # NO FAKE ZERO!
    assert trend.velocity is None  # NO FAKE ZERO!
    assert trend.growth_pct is None  # NO FAKE ZERO!
    assert trend.current_signal_value == 45.0
    assert trend.current_signal_period == "2026-10"
    assert any("Requires >= 4 periods" in lim for lim in trend.limitations)

    answer = res.answer
    assert answer is not None
    assert answer.readiness_status == "insufficient_history"
    assert "Baseline" in answer.headline
    assert any("withheld" in ki.lower() or "locked" in ki.lower() for ki in answer.key_insights)


def test_market_intelligence_honest_dimensions_and_answer():
    """Market domain reports multi-source ecosystem and declares unavailable dimensions."""
    obs = [
        _make_obs(source="github", signal_type="adoption", skill="FastAPI", skill_id="fastapi", period="2026-10", value=850.0),
        _make_obs(source="stackexchange", signal_type="interest", skill="FastAPI", skill_id="fastapi", period="2026-10", value=320.0),
        _make_obs(source="jsearch", signal_type="demand", skill="FastAPI", skill_id="fastapi", period="2026-10", value=110.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="market",
        time_range="30d",
    )
    res = service.get_intelligence(req)

    assert res.intelligence_type == "market"
    assert res.summary.get("investment_signals") == "unavailable"
    assert res.summary.get("financial_metrics") == "unavailable"
    assert res.summary.get("venture_funding") == "unavailable"

    answer = res.answer
    assert answer is not None
    assert answer.domain == "market"
    assert "Developer Interest & Technology Adoption" in answer.headline
    assert any("Financial, venture funding, and investment metrics are not supported" in lim for lim in answer.limitations)
    assert any("open-source" in ki.lower() for ki in answer.key_insights)


def test_job_intelligence_baseline_snapshot_and_answer():
    """Job domain strictly uses requisition demand, no fake momentum, no synthetic jobs."""
    obs = [
        _make_obs(source="jsearch", signal_type="demand", skill="Backend Engineer", skill_id="backend_engineer", period="2026-10", value=78.0),
        _make_obs(source="adzuna", signal_type="demand", skill="Backend Engineer", skill_id="backend_engineer", period="2026-10", value=64.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="job",
        time_range="30d",
    )
    res = service.get_intelligence(req)

    assert res.intelligence_type == "job"
    assert res.summary.get("trend_ready") is False
    assert res.summary.get("forecast_ready") is False
    assert res.summary.get("role_demand_momentum") == "insufficient_data"
    assert res.summary.get("reduction_signal") is None
    assert res.summary.get("hiring_company_activity") == "insufficient_data"

    answer = res.answer
    assert answer is not None
    assert answer.domain == "job"
    assert "Job Market Requisition Snapshot" in answer.headline
    assert any("insufficient_data" in ki for ki in answer.key_insights)
    assert any("baseline" in lim.lower() for lim in answer.limitations)


def test_portal_contextualization_three_perspectives():
    """Verify distinct headline, summary, and contextual focus across all 3 portals."""
    obs = [
        _make_obs(period="2026-06", value=100.0),
        _make_obs(period="2026-07", value=120.0),
        _make_obs(period="2026-08", value=140.0),
        _make_obs(period="2026-09", value=165.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    # Individual Portal
    req_ind = CoreIntelligenceRequest(portal_type="individual", intelligence_type="skill", selected_skills=["python"], time_range="6m")
    res_ind = service.get_intelligence(req_ind)
    assert res_ind.answer.portal == "individual"
    assert "Career Growth" in res_ind.answer.headline
    assert "Personal Skill Relevance" in res_ind.answer.contextual_focus

    # Employee Portal
    req_emp = CoreIntelligenceRequest(portal_type="employee", intelligence_type="skill", selected_skills=["python"], time_range="6m")
    res_emp = service.get_intelligence(req_emp)
    assert res_emp.answer.portal == "employee"
    assert "Internal Mobility" in res_emp.answer.headline
    assert "Internal Mobility, Team Capability" in res_emp.answer.contextual_focus

    # Company Portal
    req_comp = CoreIntelligenceRequest(portal_type="company", intelligence_type="skill", selected_skills=["python"], time_range="6m")
    res_comp = service.get_intelligence(req_comp)
    assert res_comp.answer.portal == "company"
    assert "Workforce Capability Alert" in res_comp.answer.headline
    assert "Enterprise Workforce Planning" in res_comp.answer.contextual_focus


def test_answer_empty_observations():
    """When no observations match, answer provides honest insufficient_data feedback."""
    store = MockObservationStore([])
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="individual", intelligence_type="skill")
    res = service.get_intelligence(req)

    assert res.data_status == "insufficient_data"
    assert res.data_state == "insufficient_data"
    assert res.answer is not None
    assert res.answer.readiness_status == "insufficient_data"
    assert res.answer.confidence is None
    assert "No Verified Skill Intelligence Observations" in res.answer.headline
    assert any("No data available" in lim for lim in res.answer.limitations)


def test_answer_determinism():
    """Identical inputs produce identical answers without stochastic variation."""
    obs = [
        _make_obs(period="2026-06", value=100.0),
        _make_obs(period="2026-07", value=120.0),
        _make_obs(period="2026-08", value=140.0),
        _make_obs(period="2026-09", value=165.0),
    ]
    store = MockObservationStore(obs)
    service = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="individual", intelligence_type="skill", selected_skills=["python"])
    res1 = service.get_intelligence(req)
    res2 = service.get_intelligence(req)

    assert res1.answer.headline == res2.answer.headline
    assert res1.answer.summary == res2.answer.summary
    assert res1.answer.key_insights == res2.answer.key_insights
    assert res1.answer.evidence_citations == res2.answer.evidence_citations
    assert res1.historical_trends[0].trend_slope == res2.historical_trends[0].trend_slope
    assert res1.historical_trends[0].velocity == res2.historical_trends[0].velocity

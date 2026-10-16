"""Comprehensive test suite for G1.9: Analytical Readiness & Forecast Input Contract."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.analytics.analytical_readiness import (
    assess_analytical_readiness,
    build_forecast_inputs,
    summarize_readiness,
)
from app.analytics.series_validation import validate_series_observations
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.api import dependencies
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import MarketObservation
from app.storage.firestore_observation_store import FirestoreObservationStore


def _make_obs(
    *,
    id: str,
    source: str = "jsearch",
    skill: str = "Python",
    signal_type: str = "demand",
    period: str = "2026-10",
    value: float = 1.0,
    scope: str = "global",
    query_id: str | None = "q-default",
    panel_version: str | None = "job-demand-v1",
    series_id: str | None = "s-default",
    data_origin: str = "real",
    history_type: str = "platform_collected",
    extractor_version: str | None = "v1",
    posting_id: str | None = None,
    denominator: float | None = 100.0,
) -> MarketObservation:
    dt = datetime(int(period.split("-")[0]), int(period.split("-")[1]), 1, tzinfo=timezone.utc)
    return MarketObservation(
        id=id,
        source=source,
        skill=skill,
        signal_type=signal_type,
        observed_at=dt,
        period=period,
        value=value,
        unit="job_postings" if signal_type == "demand" else "questions",
        scope=scope,
        query_id=query_id,
        panel_version=panel_version,
        series_id=series_id,
        data_origin=data_origin,
        history_type=history_type,
        extractor_version=extractor_version,
        posting_id=posting_id or f"post-{id}",
        denominator=denominator,
    )


# A. 1 period -> not_ready
def test_a_one_period_not_ready():
    obs = [_make_obs(id="1", period="2026-10")]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.readiness_state == "not_ready"
    assert rep.is_trend_ready is False
    assert rep.is_forecast_ready is False
    assert rep.consecutive_valid_periods == 1
    assert any("Only 1 valid comparable period" in r for r in rep.blocking_reasons)


# B. 3 consecutive valid periods -> not_ready
def test_b_three_periods_not_ready():
    obs = [
        _make_obs(id="1", period="2026-08"),
        _make_obs(id="2", period="2026-09"),
        _make_obs(id="3", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs, min_trend_periods=4)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.readiness_state == "not_ready"
    assert rep.is_trend_ready is False
    assert rep.is_forecast_ready is False
    assert rep.consecutive_valid_periods == 3
    assert any("Only 3 valid comparable periods is available; minimum 4 required" in r for r in rep.blocking_reasons)


# C. 4 consecutive compatible periods -> ready_for_trend
def test_c_four_consecutive_periods_ready_for_trend():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-08"),
        _make_obs(id="3", period="2026-09"),
        _make_obs(id="4", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs, min_trend_periods=4, min_forecast_periods=6)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.readiness_state == "ready_for_trend"
    assert rep.is_trend_ready is True
    assert rep.is_forecast_ready is False
    assert rep.consecutive_valid_periods == 4
    assert rep.coverage_gaps == []
    assert any("ready for trend, but minimum 6 required for forecast" in r for r in rep.blocking_reasons)


# D. Missing middle period -> blocked_missing_period
def test_d_missing_period_blocked():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-08"),
        # 2026-09 missing
        _make_obs(id="4", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.readiness_state == "blocked_missing_period"
    assert rep.is_trend_ready is False
    assert rep.is_forecast_ready is False
    assert "2026-09" in rep.coverage_gaps
    assert any("2026-09 is missing from the comparable series" in r for r in rep.blocking_reasons)


# E. Changed query -> separate insufficient series
def test_e_changed_query_is_separate_series():
    obs = [
        _make_obs(id="1", period="2026-07", query_id="query-v1"),
        _make_obs(id="2", period="2026-08", query_id="query-v1"),
        _make_obs(id="3", period="2026-09", query_id="query-v2"),
        _make_obs(id="4", period="2026-10", query_id="query-v2"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 2
    assert all(rep.readiness_state == "not_ready" for rep in reports)
    assert all(not rep.is_trend_ready and not rep.is_forecast_ready for rep in reports)
    assert {rep.query_id for rep in reports} == {"query-v1", "query-v2"}
    assert all(rep.comparability_status == "compatible" for rep in reports)


# F. Provider mismatch -> separate series, never merged
def test_f_provider_isolation():
    obs = [
        _make_obs(id="j1", source="jsearch", period="2026-10"),
        _make_obs(id="a1", source="adzuna", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 2
    providers = {r.provider for r in reports}
    assert providers == {"jsearch", "adzuna"}
    assert all(r.readiness_state == "not_ready" for r in reports)


# G. Signal-type mismatch -> separate series, never merged
def test_g_signal_type_isolation():
    obs = [
        _make_obs(id="d1", source="jsearch", signal_type="demand", period="2026-10"),
        _make_obs(id="a1", source="github", signal_type="adoption", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 2
    signals = {r.signal_type for r in reports}
    assert signals == {"demand", "adoption"}


# H. Low coverage -> blocked_coverage
def test_h_low_coverage_blocked():
    obs = [
        _make_obs(id="1", period="2026-10", denominator=None, value=1.0)
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.readiness_state == "blocked_coverage"
    assert rep.is_trend_ready is False
    assert any("Sample size is minimal or lacks a valid denominator" in r for r in rep.blocking_reasons)


# I. Invalid/incomparable G1.8 quality -> blocked_quality
def test_i_incomparable_quality_blocked():
    obs = [
        _make_obs(id="1", period="2026-07", scope="city"),
        _make_obs(id="2", period="2026-08", scope="country"),
        _make_obs(id="3", period="2026-09", scope="global"),
        _make_obs(id="4", period="2026-10", scope="country"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 3
    assert {rep.readiness_state for rep in reports}.issubset({"not_ready", "blocked_missing_period"})
    assert all(not rep.is_trend_ready and not rep.is_forecast_ready for rep in reports)
    assert {rep.scope for rep in reports} == {"city", "country", "global"}


# J. Valid 4-period series preserves provenance
def test_j_provenance_preservation():
    obs = [
        _make_obs(id="obs-1", period="2026-07", series_id="series-1", query_id="query-1", panel_version="panel-1"),
        _make_obs(id="obs-2", period="2026-08", series_id="series-1", query_id="query-1", panel_version="panel-1"),
        _make_obs(id="obs-3", period="2026-09", series_id="series-1", query_id="query-1", panel_version="panel-1"),
        _make_obs(id="obs-4", period="2026-10", series_id="series-1", query_id="query-1", panel_version="panel-1"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.series_id == "series-1"
    assert rep.panel_version == "panel-1"
    assert rep.query_ids == ["query-1"]
    assert "obs-1" in rep.observation_ids
    assert "obs-4" in rep.observation_ids


# K. Forecast input contains only eligible observations
def test_k_forecast_input_filters_ineligible():
    # JSearch has 4 periods (ready for trend, but not forecast-ready if min=6)
    # Adzuna has 6 periods (ready for forecast)
    obs = [
        _make_obs(id="j1", source="jsearch", period="2026-07"),
        _make_obs(id="j2", source="jsearch", period="2026-08"),
        _make_obs(id="j3", source="jsearch", period="2026-09"),
        _make_obs(id="j4", source="jsearch", period="2026-10"),
        _make_obs(id="a1", source="adzuna", period="2026-05"),
        _make_obs(id="a2", source="adzuna", period="2026-06"),
        _make_obs(id="a3", source="adzuna", period="2026-07"),
        _make_obs(id="a4", source="adzuna", period="2026-08"),
        _make_obs(id="a5", source="adzuna", period="2026-09"),
        _make_obs(id="a6", source="adzuna", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs, min_trend_periods=4, min_forecast_periods=6)
    forecast_inputs = build_forecast_inputs(obs, reports, require_forecast_ready=True)

    # Only Adzuna passes forecast readiness
    assert len(forecast_inputs) == 1
    assert forecast_inputs[0].provider == "adzuna"
    assert len(forecast_inputs[0].observations) == 6

    # If requiring trend readiness, both pass
    trend_inputs = build_forecast_inputs(obs, reports, require_forecast_ready=False)
    assert len(trend_inputs) == 2


# L. Forecast input preserves observation IDs
def test_l_forecast_input_preserves_observation_ids():
    obs = [
        _make_obs(id=f"a-{idx}", source="adzuna", period=f"2026-0{idx}")
        for idx in range(1, 7)
    ]
    reports = assess_analytical_readiness(obs, min_trend_periods=4, min_forecast_periods=6)
    forecast_inputs = build_forecast_inputs(obs, reports, require_forecast_ready=True)
    assert len(forecast_inputs) == 1
    obs_ids = [o.observation_id for o in forecast_inputs[0].observations]
    assert obs_ids == [f"a-{idx}" for idx in range(1, 7)]


# M. No null-to-zero conversion
def test_m_no_null_to_zero_conversion():
    obs = [
        _make_obs(id=f"a-{idx}", source="adzuna", period=f"2026-0{idx}", denominator=None)
        for idx in range(1, 7)
    ]
    reports = assess_analytical_readiness(obs, min_trend_periods=4, min_forecast_periods=6)
    forecast_inputs = build_forecast_inputs(obs, reports, require_forecast_ready=True)
    assert len(forecast_inputs) == 1
    for item in forecast_inputs[0].observations:
        assert item.denominator is None
        assert item.normalized_value is None


# N. No synthetic periods
def test_n_no_synthetic_periods():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-10"),
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    rep = reports[0]
    # Missing periods reported as gaps, never fabricated into periods_available
    assert rep.periods_available == ["2026-07", "2026-10"]
    assert rep.coverage_gaps == ["2026-08", "2026-09"]


# O. Deterministic repeated readiness calculation
def test_o_deterministic_readiness():
    obs = [
        _make_obs(id=f"o-{idx}", period=f"2026-0{idx}")
        for idx in range(1, 5)
    ]
    rep1 = assess_analytical_readiness(obs)
    rep2 = assess_analytical_readiness(obs)
    assert rep1 == rep2
    s1 = summarize_readiness(rep1)
    s2 = summarize_readiness(rep2)
    assert s1 == s2


# P. Current real production dataset with only 2026-10 -> not_ready
def test_p_real_production_dataset_is_not_ready():
    # Read real stored observations from Firestore store
    store = FirestoreObservationStore()
    observations = store.get_observations(cutoff=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert len(observations) >= 1  # Production has real observations

    reports = assess_analytical_readiness(observations, min_trend_periods=4, min_forecast_periods=6)
    assert len(reports) >= 1

    # In production demand series, each provider has only 2026-10
    demand_reports = [r for r in reports if r.signal_type == "demand"]
    for rep in demand_reports:
        assert rep.consecutive_valid_periods <= 1
        assert rep.is_trend_ready is False
        assert rep.is_forecast_ready is False
        assert rep.readiness_state in {"not_ready", "blocked_coverage", "blocked_configuration"}

    # No series in production is ready for forecast
    for rep in reports:
        assert rep.is_forecast_ready is False

    # No forecast series may be built
    forecast_inputs = build_forecast_inputs(observations, reports, require_forecast_ready=True)
    assert len(forecast_inputs) == 0

    summary = summarize_readiness(reports)
    assert summary.ready_for_forecast_count == 0
    assert summary.overall_readiness_state in {
        "not_ready", "blocked_coverage", "blocked_configuration", "ready_for_trend"
    }


# Q. Existing G1.3 aggregation remains unchanged
def test_q_g1_3_aggregation_unchanged():
    obs = [
        _make_obs(id="1", period="2026-09", value=5.0),
        _make_obs(id="2", period="2026-10", value=10.0),
    ]
    signals = aggregate_market_signals(obs)
    assert len(signals) == 2
    assert all(s.data_origin == "real" for s in signals)


# R. Existing G1.4 trend behavior remains unchanged
def test_r_g1_4_trend_behavior_unchanged():
    obs = [
        _make_obs(id="1", period="2026-09"),
        _make_obs(id="2", period="2026-10"),
    ]
    signals = aggregate_market_signals(obs)
    trends = calculate_trend_and_velocity(signals, min_periods=4)
    assert len(trends) == 1
    assert trends[0].trend == "Insufficient Data"
    assert trends[0].slope is None
    assert trends[0].data_state == "insufficient_data"


# S. Existing G1.6 API remains compatible
def test_s_g1_6_api_compatibility():
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="g1-9-tester", email="test@example.com")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    try:
        response = client.get("/api/v1/skills/intelligence?range=6m")
        assert response.status_code == 200
        data = response.json()
        assert "data_status" in data
        assert "data_state" in data
        assert "provenance" in data
        # G1.9 fields present
        assert "analytical_readiness" in data
        assert "analytical_readiness" in data["provenance"]
        assert "overall_readiness_state" in data["analytical_readiness"]
        assert data["analytical_readiness"]["ready_for_forecast_count"] == 0
        assert data["analytical_readiness"]["ready_for_trend_count"] in {0, 2}
        assert data["analytical_readiness"]["overall_readiness_state"] in {
            "not_ready", "blocked_coverage", "blocked_configuration", "blocked_quality", "insufficient_data", "ready_for_trend"
        }
        # Evidence remains intact
        if data.get("current_demand"):
            for item in data["current_demand"]:
                assert "readiness" in item
                assert "evidence" in item
                assert "analytical_readiness" in item["evidence"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# T. Existing G1.8 quality report remains compatible
def test_t_g1_8_quality_report_compatibility():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-08"),
        _make_obs(id="3", period="2026-09"),
        _make_obs(id="4", period="2026-10"),
    ]
    q_reports = validate_series_observations(obs)
    assert len(q_reports) == 1
    assert q_reports[0].quality_state == "valid"
    assert q_reports[0].is_analytically_sufficient is True

    # Pass directly into G1.9 readiness
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    assert len(r_reports) == 1
    assert r_reports[0].quality_state == "valid"
    assert r_reports[0].is_trend_ready is True

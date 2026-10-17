"""Comprehensive test suite for G1.8: Historical Data Validation & Signal Quality."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.analytics.series_validation import (
    filter_compatible_observations,
    summarize_quality,
    validate_series_observations,
)
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.api import dependencies
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import MarketObservation

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


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
    denominator: float | None = None,
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
        unit="job_postings" if signal_type == "demand" else "repositories" if signal_type == "adoption" else "questions",
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


# A. comparable observations
def test_a_comparable_observations():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-08"),
        _make_obs(id="3", period="2026-09"),
        _make_obs(id="4", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.comparability_status == "compatible"
    assert rep.periods_found == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert rep.coverage_gaps == []
    assert rep.is_analytically_sufficient is True


# B. incompatible providers
def test_b_incompatible_providers():
    obs = [
        _make_obs(id="js", source="jsearch", period="2026-10"),
        _make_obs(id="adz", source="adzuna", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    sources = {r.provider for r in reports}
    assert sources == {"jsearch", "adzuna"}
    # Never combined into a single report
    assert all(r.canonical_name == "Python" for r in reports)


# C. incompatible signal types
def test_c_incompatible_signal_types():
    obs = [
        _make_obs(id="d", source="jsearch", signal_type="demand", period="2026-10"),
        _make_obs(id="a", source="github", signal_type="adoption", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    signals = {r.signal_type for r in reports}
    assert signals == {"demand", "adoption"}


# D. changed query creates separate comparable series
def test_d_changed_query():
    obs = [
        _make_obs(id="1", period="2026-09", query_id="query-developer"),
        _make_obs(id="2", period="2026-10", query_id="query-engineer"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    assert {report.query_id for report in reports} == {"query-developer", "query-engineer"}
    assert all(report.comparability_status == "compatible" for report in reports)


# E. changed panel
def test_e_changed_panel():
    obs = [
        _make_obs(id="1", period="2026-09", panel_version="panel-v1"),
        _make_obs(id="2", period="2026-10", panel_version="panel-v2"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    assert {report.panel_version for report in reports} == {"panel-v1", "panel-v2"}
    assert all(report.comparability_status == "compatible" for report in reports)


# F. changed scope
def test_f_changed_scope():
    obs = [
        _make_obs(id="1", period="2026-09", scope="city"),
        _make_obs(id="2", period="2026-10", scope="country"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    assert {report.scope for report in reports} == {"city", "country"}
    assert all(report.comparability_status == "compatible" for report in reports)


# G. changed extractor version
def test_g_changed_extractor_version():
    obs = [
        _make_obs(id="1", period="2026-09", extractor_version="extractor-v1"),
        _make_obs(id="2", period="2026-10", extractor_version="extractor-v2"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    assert all(report.comparability_status == "compatible" for report in reports)


# H. missing period
def test_h_missing_period():
    obs = [
        _make_obs(id="1", period="2026-06"),
        _make_obs(id="2", period="2026-07"),
        _make_obs(id="3", period="2026-09"),
        _make_obs(id="4", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.coverage_gaps == ["2026-08"]
    assert rep.quality_state == "incomplete"
    assert rep.is_analytically_sufficient is False
    assert any("Missing period gap(s)" in issue for issue in rep.issues)


# I. provider failure
def test_i_provider_failure_isolation():
    # JSearch has 2 periods, Adzuna has 4 periods
    obs = [
        _make_obs(id="j1", source="jsearch", period="2026-09"),
        _make_obs(id="j2", source="jsearch", period="2026-10"),
        _make_obs(id="a1", source="adzuna", period="2026-07"),
        _make_obs(id="a2", source="adzuna", period="2026-08"),
        _make_obs(id="a3", source="adzuna", period="2026-09"),
        _make_obs(id="a4", source="adzuna", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    j_rep = next(r for r in reports if r.provider == "jsearch")
    a_rep = next(r for r in reports if r.provider == "adzuna")
    assert j_rep.quality_state == "insufficient_data"
    assert a_rep.is_analytically_sufficient is True


# J. low coverage
def test_j_low_coverage():
    obs = [_make_obs(id="1", period="2026-10", denominator=None)]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.coverage_metadata.sample_size_classification == "minimal"
    assert rep.quality_state == "low_coverage"
    assert any("Low sample size" in issue for issue in rep.issues)


# K. duplicate observation
def test_k_duplicate_observation():
    o = _make_obs(id="same-id", period="2026-10")
    reports = validate_series_observations([o, o])
    assert len(reports) == 1
    rep = reports[0]
    assert any("Duplicate observation IDs detected" in issue for issue in rep.issues)


# L. duplicate period with legitimate postings
def test_l_duplicate_period_legitimate_postings():
    obs = [
        _make_obs(id="post-1", posting_id="p-100", period="2026-10"),
        _make_obs(id="post-2", posting_id="p-200", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.coverage_metadata.unique_postings == 2
    assert rep.coverage_metadata.total_observations == 2


# M. valid four-period series
def test_m_valid_four_period_series():
    obs = [
        _make_obs(id="1", period="2026-07"),
        _make_obs(id="2", period="2026-08"),
        _make_obs(id="3", period="2026-09"),
        _make_obs(id="4", period="2026-10"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert rep.quality_state == "valid"
    assert rep.is_analytically_sufficient is True
    assert rep.coverage_gaps == []


# N. four periods with configuration drift
def test_n_four_periods_with_configuration_drift():
    # 4 periods, but series_id drifted at period 3
    obs = [
        _make_obs(id="1", period="2026-07", series_id="series-v1"),
        _make_obs(id="2", period="2026-08", series_id="series-v1"),
        _make_obs(id="3", period="2026-09", series_id="series-v2"),
        _make_obs(id="4", period="2026-10", series_id="series-v2"),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    assert reports[0].comparability_status == "drift_detected"
    assert reports[0].quality_state == "configuration_changed"

    # G1.4 trend integration: trend must NOT be calculated
    aggregated = aggregate_market_signals(obs)
    quality_reports = validate_series_observations(obs, min_periods=4)
    trends = calculate_trend_and_velocity(
        aggregated,
        min_periods=4,
        quality_reports=quality_reports,
    )
    assert len(trends) == 2
    assert all(trend.data_state == "configuration_changed" for trend in trends)
    assert trends[0].trend == "Insufficient Data"
    assert trends[0].slope is None
    assert trends[0].velocity is None


# O. provenance preservation
def test_o_provenance_preservation():
    obs = [_make_obs(id="prov-1", query_id="q-42", panel_version="p-42", series_id="s-42")]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    rep = reports[0]
    assert "prov-1" in rep.observation_ids
    assert "q-42" in rep.query_ids
    assert "p-42" in rep.panel_versions
    assert rep.series_id == "s-42"


# P. no synthetic values
def test_p_no_synthetic_values():
    obs = [_make_obs(id="1", value=7.5)]
    reports = validate_series_observations(obs)
    assert reports[0].coverage_metadata.total_observations == 1


# Q. no null-to-zero conversion
def test_q_no_null_to_zero_conversion():
    obs = [_make_obs(id="1", denominator=None)]
    reports = validate_series_observations(obs)
    assert reports[0].coverage_metadata.has_valid_denominator is False


# R. G1.3 compatibility
def test_r_g1_3_compatibility():
    obs = [
        _make_obs(id="1", period="2026-09"),
        _make_obs(id="2", period="2026-10"),
    ]
    compatible, reports = filter_compatible_observations(obs)
    assert len(compatible) == 2
    signals = aggregate_market_signals(compatible)
    assert len(signals) == 2


# S. G1.4 insufficient-data behavior
def test_s_g1_4_insufficient_data_behavior():
    obs = [
        _make_obs(id="1", period="2026-09"),
        _make_obs(id="2", period="2026-10"),
    ]
    aggregated = aggregate_market_signals(obs)
    trends = calculate_trend_and_velocity(aggregated, min_periods=4)
    assert len(trends) == 1
    assert trends[0].data_state == "insufficient_data"
    assert trends[0].slope is None


# T. G1.6 API compatibility
def test_t_g1_6_api_compatibility():
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="g1-8-tester", email="test@example.com")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    try:
        response = client.get("/api/v1/skills/intelligence?range=6m")
        assert response.status_code == 200
        data = response.json()
        assert "data_status" in data
        assert "provenance" in data
        assert "quality_summary" in data["provenance"]
        assert "total_series_assessed" in data["provenance"]["quality_summary"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# U. deterministic quality result
def test_u_deterministic_quality_result():
    obs = [
        _make_obs(id="1", period="2026-08"),
        _make_obs(id="2", period="2026-09"),
        _make_obs(id="3", period="2026-10"),
    ]
    rep1 = validate_series_observations(obs)
    rep2 = validate_series_observations(obs)
    assert rep1 == rep2

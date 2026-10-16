"""Deterministic test suite for G1.14: Production Trend & Velocity Activation + Explainable Signal Output.

Covers verification criteria A through S:
A. C# production series is trend-ready
B. Python production series is trend-ready
C. JSearch remains trend-blocked
D. Adzuna remains trend-blocked
E. GitHub remains trend-blocked
F. Missing period prevents trend
G. Configuration drift prevents trend
H. Invalid quality prevents trend
I. Theil-Sen calculation version is preserved
J. Observation IDs are preserved
K. Series ID is preserved
L. Signal type remains interest
M. No demand/adoption/interest mixing
N. Zero is never substituted for missing data
O. Growth handles zero denominator correctly
P. Velocity requires consecutive periods
Q. Calculation provenance remains traceable
R. Repeated calculation is deterministic
S. No forecasting model is invoked
"""

from datetime import datetime, timezone
import pytest

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.series_validation import validate_series_observations
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import (
    G14_CALCULATION_VERSION,
    calculate_trend_and_velocity,
    theil_sen_slope,
)
from app.models.market_signal import AggregatedMarketSignal, SkillTrendVelocityResult
from app.models.skill_intelligence import MarketObservation


def make_obs(
    *,
    source: str = "stackexchange",
    signal_type: str = "interest",
    skill: str = "C#",
    skill_id: str = "c_sharp",
    period: str,
    value: float,
    scope: str = "global",
    location: str = "Global",
    panel_version: str = "question-tag-v1",
    query_id: str = "se-tag-csharp",
    series_id: str = "stackexchange:stackoverflow:question-tag:c#:v1",
    data_origin: str = "real",
    history_type: str = "backfill",
    fetch_run_id: str = "run-se-1",
    obs_id: str | None = None,
) -> MarketObservation:
    obs_id = obs_id or f"obs-{source}-{skill_id}-{period}"
    year, month = (int(p) for p in period.split("-"))
    observed_at = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
    return MarketObservation(
        id=obs_id,
        source=source,
        signal_type=signal_type,
        observed_at=observed_at,
        period=period,
        location=location,
        scope=scope,
        skill=skill,
        skill_id=skill_id,
        value=value,
        unit="job_postings" if signal_type == "demand" else "repositories" if signal_type == "adoption" else "questions",
        data_origin=data_origin,
        history_type=history_type,
        series_id=series_id,
        query_id=query_id,
        panel_version=panel_version,
        fetch_run_id=fetch_run_id,
        observation_count=1,
    )


def make_csharp_series() -> list[MarketObservation]:
    # Real production values from Stack Exchange backfill: 99, 99, 67, 51, 54
    periods_values = [
        ("2026-05", 99.0),
        ("2026-06", 99.0),
        ("2026-07", 67.0),
        ("2026-08", 51.0),
        ("2026-09", 54.0),
    ]
    return [
        make_obs(
            source="stackexchange",
            signal_type="interest",
            skill="C#",
            skill_id="c_sharp",
            period=p,
            value=v,
            series_id="stackexchange:stackoverflow:question-tag:c#:v1",
            fetch_run_id="2756d38a0cef4b339f4712d3e08025e7",
        )
        for p, v in periods_values
    ]


def make_python_series() -> list[MarketObservation]:
    # Real production values from Stack Exchange backfill: 221, 213, 132, 138, 124
    periods_values = [
        ("2026-05", 221.0),
        ("2026-06", 213.0),
        ("2026-07", 132.0),
        ("2026-08", 138.0),
        ("2026-09", 124.0),
    ]
    return [
        make_obs(
            source="stackexchange",
            signal_type="interest",
            skill="Python",
            skill_id="python",
            period=p,
            value=v,
            series_id="stackexchange:stackoverflow:question-tag:python:v1",
            fetch_run_id="f7498934421e4818ab07ae003494eec3",
        )
        for p, v in periods_values
    ]


# ==================================================
# TEST A: C# production series is trend-ready
# ==================================================
def test_a_csharp_production_series_trend_ready():
    csharp_obs = make_csharp_series()
    q_reports = validate_series_observations(csharp_obs)
    r_reports = assess_analytical_readiness(csharp_obs, quality_reports=q_reports)

    assert len(q_reports) == 1
    assert q_reports[0].quality_state == "valid"

    assert len(r_reports) == 1
    csharp_r = r_reports[0]
    assert csharp_r.is_trend_ready is True
    assert csharp_r.consecutive_valid_periods == 5
    assert csharp_r.readiness_state == "ready_for_trend"

    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state == "ready"
    assert res.trend == "Declining"
    assert res.slope == -15.5
    assert res.velocity == 3.0  # 54 - 51 = 3.0
    assert res.growth_pct == 5.88  # (54 - 51)/51 * 100 = +5.88%
    assert res.latest_period == "2026-09"
    assert res.periods_used == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert res.provider == "stackexchange"
    assert res.signal_type == "interest"
    assert res.readiness_state == "ready_for_trend"


# ==================================================
# TEST B: Python production series is trend-ready
# ==================================================
def test_b_python_production_series_trend_ready():
    py_obs = make_python_series()
    q_reports = validate_series_observations(py_obs)
    r_reports = assess_analytical_readiness(py_obs, quality_reports=q_reports)

    assert len(q_reports) == 1
    assert q_reports[0].quality_state == "valid"

    assert len(r_reports) == 1
    py_r = r_reports[0]
    assert py_r.is_trend_ready is True
    assert py_r.consecutive_valid_periods == 5
    assert py_r.readiness_state == "ready_for_trend"

    agg_signals = aggregate_market_signals(py_obs)
    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state == "ready"
    assert res.trend == "Declining"
    assert res.slope == -25.958333
    assert res.velocity == -14.0  # 124 - 138 = -14.0
    assert res.growth_pct == -10.14  # (124 - 138)/138 * 100 = -10.14%
    assert res.latest_period == "2026-09"
    assert res.periods_used == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert res.provider == "stackexchange"
    assert res.signal_type == "interest"
    assert res.readiness_state == "ready_for_trend"


# ==================================================
# TEST C: JSearch remains trend-blocked
# ==================================================
def test_c_jsearch_remains_trend_blocked():
    obs = [
        make_obs(
            source="jsearch",
            signal_type="demand",
            skill="Python",
            skill_id="python",
            period="2026-10",
            value=86.0,
            series_id="jsearch:job-demand-v1:job-demand:python:v1",
            fetch_run_id="run-jsearch-1",
        )
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state in {"insufficient_data", "low_coverage"}
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.velocity is None
    assert res.growth_pct is None
    assert res.readiness_state in {"not_ready", "blocked_coverage"}


# ==================================================
# TEST D: Adzuna remains trend-blocked
# ==================================================
def test_d_adzuna_remains_trend_blocked():
    obs = [
        make_obs(
            source="adzuna",
            signal_type="demand",
            skill="Java",
            skill_id="java",
            period="2026-10",
            value=1.0,
            series_id="adzuna:job-demand-v1:job-demand:java:v1",
            fetch_run_id="run-adzuna-1",
        )
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state in {"insufficient_data", "low_coverage"}
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.velocity is None
    assert res.growth_pct is None


# ==================================================
# TEST E: GitHub remains trend-blocked
# ==================================================
def test_e_github_remains_trend_blocked():
    obs = [
        make_obs(
            source="github",
            signal_type="adoption",
            skill="Python",
            skill_id="python",
            period="2026-10",
            value=150000.0,
            series_id="github:adoption-v1:repo-count:python:v1",
            fetch_run_id="run-gh-1",
        )
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state == "insufficient_data"
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.velocity is None
    assert res.growth_pct is None


# ==================================================
# TEST F: Missing period prevents trend
# ==================================================
def test_f_missing_period_prevents_trend():
    # 4 periods with 2026-07 missing
    obs = [
        make_obs(period="2026-05", value=100.0),
        make_obs(period="2026-06", value=90.0),
        # 2026-07 missing!
        make_obs(period="2026-08", value=80.0),
        make_obs(period="2026-09", value=70.0),
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state in {"insufficient_data", "incomplete"}
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert any("gap" in r.lower() or "consecutive" in r.lower() or "missing" in r.lower() for r in res.blocking_reasons)


# ==================================================
# TEST G: Configuration drift prevents trend
# ==================================================
def test_g_configuration_drift_prevents_trend():
    # 5 periods where series_id changed in month 4
    obs = [
        make_obs(period="2026-05", value=100.0, series_id="se:v1"),
        make_obs(period="2026-06", value=90.0, series_id="se:v1"),
        make_obs(period="2026-07", value=80.0, series_id="se:v1"),
        make_obs(period="2026-08", value=70.0, series_id="se:v2"),  # DRIFT!
        make_obs(period="2026-09", value=60.0, series_id="se:v2"),
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert all(r.data_state in {"incomparable", "configuration_changed", "insufficient_data"} for r in results)
    assert all(r.slope is None for r in results)


def test_distinct_queries_and_geographies_keep_quality_gates_isolated():
    observations = [
        make_obs(
            period=period,
            value=value,
            query_id=query_id,
            series_id=series_id,
            scope=scope,
            location=location,
        )
        for query_id, series_id, scope, location, values in (
            ("query-global", "series-global", "global", "Global", [5, 6, 7, 8]),
            ("query-india", "series-india", "country", "India", [9, 8, 7, 6]),
        )
        for period, value in zip(
            ("2026-05", "2026-06", "2026-07", "2026-08"),
            values,
        )
    ]
    quality = validate_series_observations(observations)
    readiness = assess_analytical_readiness(observations, quality_reports=quality)
    results = calculate_trend_and_velocity(
        aggregate_market_signals(observations),
        quality_reports=quality,
        readiness_reports=readiness,
    )

    assert len(quality) == len(readiness) == len(results) == 2
    assert {result.data_state for result in results} == {"ready"}
    assert {(result.query_id, result.location) for result in results} == {
        ("query-global", "Global"),
        ("query-india", "India"),
    }


# ==================================================
# TEST H: Invalid quality prevents trend
# ==================================================
def test_h_invalid_quality_prevents_trend():
    obs = make_csharp_series()
    q_reports = validate_series_observations(obs)
    # Mark quality as incomplete/incomparable to test hard gate
    q_reports[0].quality_state = "incomplete"

    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    agg_signals = aggregate_market_signals(obs)

    results = calculate_trend_and_velocity(
        agg_signals,
        quality_reports=q_reports,
        readiness_reports=r_reports,
    )

    assert len(results) == 1
    res = results[0]
    assert res.data_state == "incomplete"
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.velocity is None


# ==================================================
# TEST I: Theil-Sen calculation version preserved
# ==================================================
def test_i_theil_sen_calculation_version_preserved():
    csharp_obs = make_csharp_series()
    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    assert results[0].calculation_version == G14_CALCULATION_VERSION
    raw_vals = [99.0, 99.0, 67.0, 51.0, 54.0]
    expected_slope = round(theil_sen_slope(raw_vals), 6)
    assert results[0].slope == expected_slope


# ==================================================
# TEST J: Observation IDs preserved
# ==================================================
def test_j_observation_ids_preserved():
    csharp_obs = make_csharp_series()
    expected_ids = {o.id for o in csharp_obs}
    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    assert set(results[0].observation_ids) == expected_ids


# ==================================================
# TEST K: Series ID preserved
# ==================================================
def test_k_series_id_preserved():
    csharp_obs = make_csharp_series()
    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    assert results[0].series_id == "stackexchange:stackoverflow:question-tag:c#:v1"


# ==================================================
# TEST L: Signal type remains interest
# ==================================================
def test_l_signal_type_remains_interest():
    csharp_obs = make_csharp_series()
    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    res = results[0]
    assert res.signal_type == "interest"
    explanation = res.explanation
    assert explanation is not None
    assert "developer interest" in explanation["why_it_matters"]
    assert "job demand" not in explanation["why_it_matters"]
    assert "market share" not in explanation["why_it_matters"]


# ==================================================
# TEST M: No demand/adoption/interest mixing
# ==================================================
def test_m_no_demand_adoption_interest_mixing():
    obs = [
        make_obs(source="jsearch", signal_type="demand", period="2026-10", value=10.0),
        make_obs(source="github", signal_type="adoption", period="2026-10", value=500.0),
        make_obs(source="stackexchange", signal_type="interest", period="2026-10", value=50.0),
    ]
    agg_signals = aggregate_market_signals(obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 3
    signal_types = {r.signal_type for r in results}
    assert signal_types == {"demand", "adoption", "interest"}


# ==================================================
# TEST N: Zero is never substituted for missing data
# ==================================================
def test_n_zero_never_substituted_for_missing_data():
    obs = [
        make_obs(period="2026-05", value=100.0),
        make_obs(period="2026-06", value=90.0),
        # 2026-07 missing
        make_obs(period="2026-08", value=80.0),
    ]
    agg_signals = aggregate_market_signals(obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    res = results[0]
    assert res.periods_used == ["2026-05", "2026-06", "2026-08"]
    assert "2026-07" not in res.periods_used


# ==================================================
# TEST O: Growth handles zero denominator correctly
# ==================================================
def test_o_growth_handles_zero_denominator_correctly():
    obs = [
        make_obs(period="2026-08", value=0.0),
        make_obs(period="2026-09", value=10.0),
    ]
    agg_signals = aggregate_market_signals(obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    res = results[0]
    assert res.velocity == 10.0  # 10 - 0 = 10
    assert res.growth_pct is None  # Undefined division by zero -> None


# ==================================================
# TEST P: Velocity requires consecutive periods
# ==================================================
def test_p_velocity_requires_consecutive_periods():
    # 2 non-consecutive periods
    obs = [
        make_obs(period="2026-05", value=10.0),
        make_obs(period="2026-07", value=20.0),
    ]
    agg_signals = aggregate_market_signals(obs)
    results = calculate_trend_and_velocity(agg_signals)

    assert len(results) == 1
    res = results[0]
    assert res.velocity is None  # Gap between May and July


# ==================================================
# TEST Q: Calculation provenance remains traceable
# ==================================================
def test_q_calculation_provenance_remains_traceable():
    csharp_obs = make_csharp_series()
    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    res = results[0]
    assert res.evidence_url == "/api/v1/skills/intelligence/c_sharp/evidence"
    assert res.explanation is not None
    evidence = res.explanation["evidence"]
    assert evidence["provider"] == "stackexchange"
    assert evidence["calculation_version"] == G14_CALCULATION_VERSION
    assert len(evidence["observation_ids"]) == 5
    assert len(evidence["fetch_run_ids"]) == 1


# ==================================================
# TEST R: Repeated calculation is deterministic
# ==================================================
def test_r_repeated_calculation_is_deterministic():
    csharp_obs = make_csharp_series()
    agg_signals = aggregate_market_signals(csharp_obs)

    runs = [calculate_trend_and_velocity(agg_signals) for _ in range(5)]
    first = runs[0][0]
    for run in runs[1:]:
        assert run[0].model_dump() == first.model_dump()


# ==================================================
# TEST S: No forecasting model is invoked
# ==================================================
def test_s_no_forecasting_model_is_invoked():
    csharp_obs = make_csharp_series()
    r_reports = assess_analytical_readiness(csharp_obs)

    assert r_reports[0].is_trend_ready is True
    assert r_reports[0].is_forecast_ready is False

    agg_signals = aggregate_market_signals(csharp_obs)
    results = calculate_trend_and_velocity(agg_signals)

    res = results[0]
    assert all(p <= "2026-09" for p in res.periods_used)
    assert res.latest_period == "2026-09"

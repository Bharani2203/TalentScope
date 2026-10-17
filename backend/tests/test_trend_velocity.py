from datetime import date, datetime, timezone
import pytest

from app.analytics.trend import (
    G14_CALCULATION_VERSION,
    calculate_trend_and_velocity as _calculate_trend_and_velocity,
    theil_sen_slope,
)
from app.models.market_signal import AggregatedMarketSignal, SkillTrendVelocityResult
from app.storage.calculation_record_store import FirestoreCalculationRecordStore


def calculate_trend_and_velocity(signals, **kwargs):
    # These fixtures model October 2026 as a completed historical month.
    kwargs.setdefault("as_of", date(2026, 11, 1))
    return _calculate_trend_and_velocity(signals, **kwargs)


def make_signal(
    *,
    source: str = "jsearch",
    signal_type: str = "demand",
    canonical_skill_id: str = "python",
    canonical_name: str = "Python",
    period: str,
    raw_value: float,
    normalized_value: float | None = None,
    denominator: float | None = None,
    metric: str = "normalized_share",
    unit: str | None = None,
    data_state: str = "ready",
    data_origin: str = "real",
    history_type: str = "platform_collected",
    panel_version: str | None = "job-demand-v1",
    series_id: str | None = "jsearch:job-demand-v1:job-demand:python:v1",
    scope: str = "global",
    location: str | None = None,
    query_id: str | None = "jsearch:query-v1",
    obs_id: str | None = None,
    run_id: str | None = None,
) -> AggregatedMarketSignal:
    return AggregatedMarketSignal(
        canonical_skill_id=canonical_skill_id,
        canonical_name=canonical_name,
        source=source,
        signal_type=signal_type,
        period=period,
        metric=metric,
        unit=unit or ("repositories" if signal_type == "adoption" else "job_postings"),
        raw_value=raw_value,
        normalized_value=normalized_value,
        denominator=denominator,
        observation_count=1,
        data_origin=data_origin,
        history_type=history_type,
        data_state=data_state,
        confidence=None,
        series_id=series_id,
        panel_version=panel_version,
        scope=scope,
        location=location,
        query_id=query_id,
        observation_ids=[obs_id or f"obs-{source}-{period}"],
        fetch_run_ids=[run_id or f"run-{source}-{period}"],
    )


# 1. 1 period -> insufficient_data
def test_one_period_returns_insufficient_data():
    sig = make_signal(period="2026-10", raw_value=10.0, normalized_value=0.1, denominator=100.0)
    results = calculate_trend_and_velocity([sig])
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.velocity is None
    assert res.growth_pct is None
    assert res.confidence is None
    assert res.data_state == "insufficient_data"
    assert res.periods_used == ["2026-10"]


# 2. 2 periods -> insufficient_data, but velocity is computed for consecutive months
def test_two_periods_returns_insufficient_data_with_velocity():
    sigs = [
        make_signal(period="2026-09", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-10", raw_value=15.0, normalized_value=0.15, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.data_state == "insufficient_data"
    assert res.latest_value == 0.15
    assert res.previous_value == 0.10
    assert res.velocity == 0.05
    assert res.growth_pct == 50.0  # (0.15 - 0.10)/0.10 * 100 = 50.0%


# 3. 3 periods -> insufficient_data
def test_three_periods_returns_insufficient_data():
    sigs = [
        make_signal(period="2026-07", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-08", raw_value=12.0, normalized_value=0.12, denominator=100.0),
        make_signal(period="2026-09", raw_value=15.0, normalized_value=0.15, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.data_state == "insufficient_data"


# 4. 4 valid periods increasing -> Increasing
def test_four_periods_increasing_returns_increasing():
    sigs = [
        make_signal(period="2026-07", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-08", raw_value=15.0, normalized_value=0.15, denominator=100.0),
        make_signal(period="2026-09", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-10", raw_value=25.0, normalized_value=0.25, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Increasing"
    assert res.slope > 0
    assert res.data_state == "ready"
    assert res.velocity == 0.05
    assert res.periods_used == ["2026-07", "2026-08", "2026-09", "2026-10"]


# 5. 4 valid periods decreasing -> Declining
def test_four_periods_decreasing_returns_declining():
    sigs = [
        make_signal(period="2026-07", raw_value=30.0, normalized_value=0.30, denominator=100.0),
        make_signal(period="2026-08", raw_value=25.0, normalized_value=0.25, denominator=100.0),
        make_signal(period="2026-09", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-10", raw_value=15.0, normalized_value=0.15, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Declining"
    assert res.slope < 0
    assert res.data_state == "ready"
    assert res.velocity == -0.05


# 6. 4 valid periods unchanged -> Stable
def test_four_periods_unchanged_returns_stable():
    sigs = [
        make_signal(period="2026-07", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-08", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-09", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-10", raw_value=20.0, normalized_value=0.20, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    assert len(results) == 1
    res = results[0]
    assert res.trend == "Stable"
    assert res.slope == 0.0
    assert res.data_state == "ready"
    assert res.velocity == 0.0


@pytest.mark.parametrize(
    ("values", "expected_trend", "expected_velocity"),
    [
        ([0.40, 0.30, 0.20, 0.25], "Declining", 0.05),
        ([0.10, 0.20, 0.30, 0.25], "Increasing", -0.05),
    ],
)
def test_long_term_trend_is_separate_from_latest_period_velocity(values, expected_trend, expected_velocity):
    signals = [
        make_signal(
            period=period,
            raw_value=value * 100,
            normalized_value=value,
            denominator=100,
        )
        for period, value in zip(
            ("2026-07", "2026-08", "2026-09", "2026-10"),
            values,
        )
    ]
    result = calculate_trend_and_velocity(signals)[0]
    assert result.trend == expected_trend
    assert result.velocity == expected_velocity
    assert result.latest_mom_change == expected_velocity
    assert result.slope_unit == "share per month"
    assert result.velocity_unit == "share per month"


# 7. normalized-share velocity (percentage point change)
def test_normalized_share_velocity_represents_point_difference():
    sigs = [
        make_signal(period="2026-09", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-10", raw_value=25.0, normalized_value=0.25, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    assert res.velocity == 0.05  # +0.05 point movement
    assert res.metric == "normalized_share"
    assert res.unit == "share"
    assert res.period_grain == "month"


# 8. raw-count velocity (absolute difference)
def test_raw_count_velocity_represents_count_difference():
    sigs = [
        make_signal(period="2026-09", raw_value=200.0, normalized_value=None, denominator=None, metric="raw_count"),
        make_signal(period="2026-10", raw_value=250.0, normalized_value=None, denominator=None, metric="raw_count"),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    assert res.latest_value == 250.0
    assert res.previous_value == 200.0
    assert res.velocity == 50.0
    assert res.growth_pct == 25.0
    assert res.metric == "raw_count"


# 9. growth percentage
def test_growth_percentage_calculation():
    sigs = [
        make_signal(period="2026-09", raw_value=100.0, normalized_value=0.10, denominator=1000.0),
        make_signal(period="2026-10", raw_value=120.0, normalized_value=0.12, denominator=1000.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    # (0.12 - 0.10) / 0.10 * 100 = 20.0%
    assert res.growth_pct == 20.0


# 10. previous value = 0 -> growth_pct = null
def test_growth_percentage_null_when_previous_is_zero():
    sigs = [
        make_signal(period="2026-09", raw_value=0.0, normalized_value=0.0, denominator=100.0),
        make_signal(period="2026-10", raw_value=10.0, normalized_value=0.10, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    assert res.growth_pct is None


# 11. missing period -> no fabricated zero & non-consecutive results in insufficient_data
def test_missing_period_is_not_fabricated_and_causes_insufficient_data():
    sigs = [
        make_signal(period="2026-06", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-07", raw_value=15.0, normalized_value=0.15, denominator=100.0),
        # 2026-08 is missing!
        make_signal(period="2026-09", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-10", raw_value=25.0, normalized_value=0.25, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    # Despite 4 periods total, they are non-consecutive -> "Insufficient Data"
    assert res.trend == "Insufficient Data"
    assert res.slope is None
    assert res.data_state == "insufficient_data"
    assert res.periods_used == ["2026-06", "2026-07", "2026-09", "2026-10"]


# 12. source separation -> JSearch and Adzuna never combined
def test_source_separation_maintains_isolated_series():
    jsearch_sig = make_signal(source="jsearch", period="2026-10", raw_value=10.0, normalized_value=0.1, denominator=100.0)
    adzuna_sig = make_signal(source="adzuna", period="2026-10", raw_value=5.0, normalized_value=0.05, denominator=100.0)
    results = calculate_trend_and_velocity([jsearch_sig, adzuna_sig])
    assert len(results) == 2
    sources = {r.source for r in results}
    assert sources == {"jsearch", "adzuna"}


# 13. signal separation -> demand and adoption never combined
def test_signal_separation_maintains_isolated_series():
    demand_sig = make_signal(source="github", signal_type="demand", period="2026-10", raw_value=10.0)
    adoption_sig = make_signal(source="github", signal_type="adoption", period="2026-10", raw_value=50000.0, metric="adoption_snapshot")
    results = calculate_trend_and_velocity([demand_sig, adoption_sig])
    assert len(results) == 2
    types = {r.signal_type for r in results}
    assert types == {"demand", "adoption"}


# 14. deterministic chronological ordering
def test_deterministic_chronological_ordering():
    # Pass unordered periods
    sigs = [
        make_signal(period="2026-10", raw_value=40.0, normalized_value=0.40, denominator=100.0),
        make_signal(period="2026-07", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-09", raw_value=30.0, normalized_value=0.30, denominator=100.0),
        make_signal(period="2026-08", raw_value=20.0, normalized_value=0.20, denominator=100.0),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    assert res.periods_used == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert res.latest_period == "2026-10"
    assert res.latest_value == 0.40
    assert res.previous_period == "2026-09"
    assert res.previous_value == 0.30
    assert res.trend == "Increasing"


# 15. provenance preservation
def test_provenance_preservation():
    sigs = [
        make_signal(period="2026-09", raw_value=10.0, normalized_value=0.1, denominator=100.0, obs_id="obs-1", run_id="run-1"),
        make_signal(period="2026-10", raw_value=20.0, normalized_value=0.2, denominator=100.0, obs_id="obs-2", run_id="run-2"),
    ]
    results = calculate_trend_and_velocity(sigs)
    res = results[0]
    assert res.observation_ids == ["obs-1", "obs-2"]
    assert res.fetch_run_ids == ["run-1", "run-2"]
    assert res.calculation_version == G14_CALCULATION_VERSION


# 16. calculation idempotency
def test_calculation_idempotency():
    sigs = [
        make_signal(period="2026-07", raw_value=10.0, normalized_value=0.10, denominator=100.0),
        make_signal(period="2026-08", raw_value=20.0, normalized_value=0.20, denominator=100.0),
        make_signal(period="2026-09", raw_value=30.0, normalized_value=0.30, denominator=100.0),
        make_signal(period="2026-10", raw_value=40.0, normalized_value=0.40, denominator=100.0),
    ]
    res1 = calculate_trend_and_velocity(sigs)
    res2 = calculate_trend_and_velocity(sigs)
    assert res1 == res2
    assert [r.model_dump() for r in res1] == [r.model_dump() for r in res2]


# 17. A one-period demo fixture remains insufficient_data.
def test_single_period_demo_signals_return_insufficient_data():
    demo_adzuna = make_signal(
        source="adzuna",
        canonical_skill_id="c_sharp",
        canonical_name="C#",
        period="2026-10",
        raw_value=1.0,
        normalized_value=None,
        denominator=None,
        metric="raw_count",
        data_state="insufficient_data",
        data_origin="demo",
    )
    demo_jsearch = make_signal(
        source="jsearch",
        canonical_skill_id="cloud_computing",
        canonical_name="Cloud Computing",
        period="2026-10",
        raw_value=2.0,
        normalized_value=0.2,
        denominator=10.0,
        metric="normalized_share",
        data_state="ready",
        data_origin="demo",
    )
    demo_github = make_signal(
        source="github",
        signal_type="adoption",
        canonical_skill_id="python",
        canonical_name="Python",
        period="2026-10",
        raw_value=925221.0,
        normalized_value=None,
        denominator=None,
        metric="adoption_snapshot",
        data_state="ready",
        data_origin="demo",
    )
    results = calculate_trend_and_velocity([demo_adzuna, demo_jsearch, demo_github])
    assert len(results) == 3
    for r in results:
        assert r.trend == "Insufficient Data"
        assert r.slope is None
        assert r.velocity is None
        assert r.growth_pct is None
        assert r.confidence is None
        assert r.data_state == "insufficient_data"
        assert len(r.periods_used) == 1
        assert r.periods_used == ["2026-10"]


def test_missing_unit_or_series_identity_is_unavailable_not_zero():
    missing_unit = make_signal(
        period="2026-09", raw_value=10, normalized_value=0.1, denominator=100,
    ).model_copy(update={"unit": None})
    missing_series = make_signal(
        period="2026-09", raw_value=10, normalized_value=0.1, denominator=100,
        series_id=None,
    )
    results = calculate_trend_and_velocity([missing_unit, missing_series])

    assert len(results) == 2
    assert all(result.data_state == "unavailable" for result in results)
    assert all(result.trend == "Insufficient Data" for result in results)
    assert all(result.velocity is None and result.slope is None for result in results)
    assert all(result.blocking_reasons for result in results)


def test_source_unit_geography_query_and_series_are_distinct_partitions():
    baseline = make_signal(period="2026-10", raw_value=10, normalized_value=0.1, denominator=100)
    variants = [
        make_signal(period="2026-10", raw_value=10, metric="raw_count", unit="repositories"),
        make_signal(period="2026-10", raw_value=10, normalized_value=0.1, denominator=100, source="adzuna"),
        make_signal(period="2026-10", raw_value=10, normalized_value=0.1, denominator=100, scope="country", location="India"),
        make_signal(period="2026-10", raw_value=10, normalized_value=0.1, denominator=100, query_id="jsearch:query-v2"),
        make_signal(period="2026-10", raw_value=10, normalized_value=0.1, denominator=100, series_id="other-series"),
    ]
    results = calculate_trend_and_velocity([baseline, *variants])

    assert len(results) == 6
    assert len({
        (
            result.source, result.metric, result.source_unit, result.scope,
            result.location, result.query_id, result.series_id,
        )
        for result in results
    }) == 6


def test_open_current_month_is_not_mixed_with_completed_history():
    signals = [
        make_signal(
            period=period,
            raw_value=value * 100,
            normalized_value=value,
            denominator=100,
        )
        for period, value in (
            ("2026-07", 0.10),
            ("2026-08", 0.20),
            ("2026-09", 0.30),
            ("2026-10", 0.99),
        )
    ]

    result = calculate_trend_and_velocity(signals, as_of=date(2026, 10, 12))[0]

    assert result.latest_period == "2026-09"
    assert result.periods_used == ["2026-07", "2026-08", "2026-09"]
    assert result.velocity == pytest.approx(0.10)
    assert result.data_state == "insufficient_data"


# 18. existing Adzuna C# observation remains unchanged
def test_existing_adzuna_c_sharp_observation_unchanged():
    from app.storage.observation_identity import stable_observation_id
    from app.models.skill_intelligence import MarketObservation
    obs = MarketObservation(
        id="e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc",
        source="adzuna",
        skill="C#",
        location="India",
        observed_at=datetime(2026, 10, 6, 18, 20, 32, tzinfo=timezone.utc),
        period="2026-10",
        scope="country",
        posting_id="4686701684",
        signal_type="demand",
        history_type="platform_collected",
        data_origin="real",
        fetch_run_id="61aa8c5206224fa28410d25299767696",
        query_id="adzuna:47838af054a71a055855",
        panel_version="job-demand-v1",
        series_id="adzuna:adzuna:47838af054a71a055855:job-demand:c_sharp:v1",
        value=1.0,
    )
    assert obs.id == "e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc"
    assert obs.skill == "C#"
    assert obs.signal_type == "demand"
    assert obs.data_origin == "real"
    assert obs.value == 1.0


# 19. existing JSearch observations remain unchanged
def test_existing_jsearch_observations_unchanged():
    from app.models.skill_intelligence import MarketObservation
    obs = MarketObservation(
        id="04b4cfc1a519a7c16484d25017222f03b9de465dd44a641fe4acba0c930564d6",
        source="jsearch",
        skill="Cloud Computing",
        observed_at=datetime(2026, 10, 6, 5, 6, 13, tzinfo=timezone.utc),
        period="2026-10",
        signal_type="demand",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
    )
    assert obs.source == "jsearch"
    assert obs.signal_type == "demand"
    assert obs.value == 1.0


# 20. existing GitHub adoption observation remains unchanged
def test_existing_github_adoption_observation_unchanged():
    from app.models.skill_intelligence import MarketObservation
    obs = MarketObservation(
        id="e533038d7f3cc5afabd07332a88739e0d321f397bb69eb6507cd9c60a4b38d58",
        source="github",
        skill="Python",
        observed_at=datetime(2026, 10, 6, 18, 45, 23, tzinfo=timezone.utc),
        period="2026-10",
        signal_type="adoption",
        value=925221.0,
        history_type="snapshot",
        data_origin="real",
    )
    assert obs.source == "github"
    assert obs.signal_type == "adoption"
    assert obs.value == 925221.0

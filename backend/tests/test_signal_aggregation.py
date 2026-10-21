"""Comprehensive test suite for G1.3 Real Market-Signal Aggregation.

Validates:
1. Adzuna demand aggregation
2. GitHub adoption aggregation
3. Source separation (Adzuna vs GitHub)
4. Signal-type separation (demand vs adoption)
5. Source-specific denominator application
6. Same-period denominator handling
7. Different-period denominator rejection (never cross-period)
8. Missing denominator handling (metric=raw_count, normalized_value=None, data_state=insufficient_data)
9. Raw count preservation
10. No raw-count-to-100% conversion (value=1.0 is never 100%)
11. Missing periods are not fabricated (period count strictly matches real periods)
12. Insufficient-data behavior (confidence=None, no fake trend)
13. Canonical skill normalization (c# -> c_sharp, python 3 -> python)
14. Provenance preservation (traces observation_ids, fetch_run_ids, series_id)
15. data_origin preservation (real vs demo)
16. history_type preservation (platform_collected vs snapshot)
17. panel_version preservation
18. Deterministic repeated aggregation (idempotent output)
19. Calculation-record compatibility / non-collision
20. Existing Adzuna C# production observation compatibility
"""

from datetime import datetime, timezone
import pytest

from app.analytics.signal_aggregation import aggregate_market_signals, partition_key
from app.analytics.shared_intelligence import analyze_market_observations
from app.models.market_signal import AggregatedMarketSignal
from app.models.skill_intelligence import MarketObservation


def test_1_adzuna_demand_aggregation_with_denominator():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = [
        MarketObservation(
            id="adz-1", source="adzuna", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
            history_type="platform_collected", data_origin="real",
            fetch_run_id="run-1", series_id="adz:panel:demand:python:v1",
        ),
        MarketObservation(
            id="adz-2", source="adzuna", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="p-2", value=1.0,
            history_type="platform_collected", data_origin="real",
            fetch_run_id="run-1", series_id="adz:panel:demand:python:v1",
        ),
        MarketObservation(
            id="adz-3", source="adzuna", skill="SQL", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="p-3", value=1.0,
            history_type="platform_collected", data_origin="real",
            fetch_run_id="run-1", series_id="adz:panel:demand:sql:v1",
        ),
    ]
    # 3 distinct postings in same partition -> local denominator = 3.0
    signals = aggregate_market_signals(obs)
    assert len(signals) == 2
    py_signal = next(s for s in signals if s.canonical_name == "Python")
    assert py_signal.source == "adzuna"
    assert py_signal.signal_type == "demand"
    assert py_signal.raw_value == 2.0
    assert py_signal.observation_count == 2
    assert py_signal.denominator == 3.0
    assert py_signal.normalized_value == round(2.0 / 3.0, 6)
    assert py_signal.metric == "normalized_share"
    assert py_signal.data_state == "ready"


def test_2_github_adoption_aggregation():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    gh_obs = MarketObservation(
        id="gh-1", source="github", skill="Python", signal_type="adoption",
        observed_at=now, period="2026-10", posting_id="topic:python", value=45000.0,
        history_type="snapshot", data_origin="real",
        fetch_run_id="run-gh-1", series_id="gh:topic:python:v1",
    )
    signals = aggregate_market_signals([gh_obs])
    assert len(signals) == 1
    signal = signals[0]
    assert signal.source == "github"
    assert signal.signal_type == "adoption"
    assert signal.metric == "adoption_snapshot"
    assert signal.raw_value == 45000.0
    assert signal.normalized_value is None  # absolute snapshot, never demand share
    assert signal.data_state == "ready"


def test_3_and_4_source_and_signal_type_separation():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    adzuna_demand = MarketObservation(
        id="adz-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    github_adoption = MarketObservation(
        id="gh-1", source="github", skill="Python", signal_type="adoption",
        observed_at=now, period="2026-10", posting_id="topic:python", value=500.0,
        history_type="snapshot", data_origin="real",
    )
    signals = aggregate_market_signals([adzuna_demand, github_adoption])
    assert len(signals) == 2
    # Verify separate entries, never merged or averaged
    adz = next(s for s in signals if s.source == "adzuna")
    gh = next(s for s in signals if s.source == "github")
    assert adz.signal_type == "demand"
    assert gh.signal_type == "adoption"
    assert adz.raw_value == 1.0
    assert gh.raw_value == 500.0


def test_5_and_6_source_specific_and_same_period_denominator():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adz-1", source="adzuna", skill="Java", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=5.0,
        history_type="platform_collected", data_origin="real",
    )
    denominators = {("adzuna", "demand", "2026-10"): 100.0}
    signals = aggregate_market_signals([obs], source_denominators=denominators)
    assert len(signals) == 1
    assert signals[0].denominator == 100.0
    assert signals[0].normalized_value == 0.05
    assert signals[0].metric == "normalized_share"


def test_7_different_period_denominator_not_used():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adz-1", source="adzuna", skill="Java", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=5.0,
        history_type="platform_collected", data_origin="real",
    )
    # Denominator exists for 2026-09 but NOT 2026-10
    denominators = {("adzuna", "demand", "2026-09"): 100.0}
    signals = aggregate_market_signals([obs], source_denominators=denominators)
    assert len(signals) == 1
    # Different period denominator is NOT applied to 2026-10
    assert signals[0].denominator is None
    assert signals[0].normalized_value is None
    assert signals[0].data_state == "insufficient_data"


def test_geography_query_and_unit_isolate_aggregation_denominators():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    observations = [
        MarketObservation(
            id="global-python", source="jsearch", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="g-1", value=1,
            unit="job_postings", query_id="query-a", scope="global",
        ),
        MarketObservation(
            id="global-sql", source="jsearch", skill="SQL", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="g-2", value=1,
            unit="job_postings", query_id="query-a", scope="global",
        ),
        MarketObservation(
            id="global-requisition-python", source="jsearch", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="gq-1", value=1,
            unit="requisitions", query_id="query-a", scope="global",
        ),
        MarketObservation(
            id="india-python", source="jsearch", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="i-1", value=1,
            unit="job_postings", query_id="query-a", scope="country", location="India",
        ),
        MarketObservation(
            id="other-query-python", source="jsearch", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="q-1", value=1,
            unit="requisitions", query_id="query-b", scope="global",
        ),
    ]

    result = aggregate_market_signals(
        observations,
        source_denominators={
            ("jsearch", "demand", "2026-10", "query-a", "global", None): 99,
            ("jsearch", "demand", "2026-10", "query-b", "global", None, "requisitions", None): 3,
        },
    )
    python = [item for item in result if item.canonical_name == "Python"]

    assert len(python) == 4
    assert {(item.scope, item.location, item.query_id, item.unit) for item in python} == {
        ("global", None, "query-a", "job_postings"),
        ("global", None, "query-a", "requisitions"),
        ("country", "India", "query-a", "job_postings"),
        ("global", None, "query-b", "requisitions"),
    }
    denominator_by_query = {
        (item.query_id, item.scope, item.location, item.unit): item.denominator
        for item in python
    }
    assert denominator_by_query == {
        ("query-a", "global", None, "job_postings"): 2,
        ("query-a", "global", None, "requisitions"): None,
        ("query-a", "country", "India", "job_postings"): None,
        ("query-b", "global", None, "requisitions"): 3,
    }


def test_8_9_10_missing_denominator_raw_count_preservation_no_100_pct_conversion():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adz-single", source="adzuna", skill="C#", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-single", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    signals = aggregate_market_signals([obs])
    assert len(signals) == 1
    s = signals[0]
    assert s.raw_value == 1.0
    assert s.metric == "raw_count"
    assert s.denominator is None
    assert s.normalized_value is None  # MUST NOT BE 1.0 or 100%!
    assert s.data_state == "insufficient_data"


def test_11_missing_periods_are_not_fabricated():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = [
        MarketObservation(
            id="adz-1", source="adzuna", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
            history_type="platform_collected", data_origin="real",
        ),
    ]
    signals = aggregate_market_signals(obs)
    # Strictly one signal for 2026-10; no missing months generated
    periods = [s.period for s in signals]
    assert periods == ["2026-10"]


def test_12_insufficient_data_confidence_is_none():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adz-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    signals = aggregate_market_signals([obs])
    assert signals[0].confidence is None


def test_incomplete_collection_is_not_ready_aggregated_evidence():
    observation = MarketObservation(
        id="synthetic-incomplete-1", source="fixture", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        period="2026-09", posting_id="synthetic-posting-1", value=1.0,
        history_type="platform_collected", data_origin="real",
        quality={"collection_complete": False, "pagination_complete": False},
    )
    signal = aggregate_market_signals([observation])[0]
    assert signal.data_state == "incomplete"
    assert any("COLLECTION_INCOMPLETE" in warning for warning in signal.warnings)


def test_synthetic_observation_remains_non_operational_after_aggregation():
    observation = MarketObservation(
        id="synthetic-test-1", source="fixture", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        period="2026-09", posting_id="synthetic-test-posting", value=1.0,
        history_type="platform_collected", data_origin="synthetic",
    )
    signal = aggregate_market_signals([observation])[0]
    assert signal.data_origin == "synthetic"
    assert signal.data_state == "insufficient_data"


def test_13_canonical_skill_normalization():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs1 = MarketObservation(
        id="adz-1", source="adzuna", skill="c sharp", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    obs2 = MarketObservation(
        id="adz-2", source="adzuna", skill="C#", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-2", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    signals = aggregate_market_signals([obs1, obs2])
    # Both aliases map to canonical skill "C#" with ID "c_sharp"
    assert len(signals) == 1
    assert signals[0].canonical_name == "C#"
    assert signals[0].canonical_skill_id == "c_sharp"
    assert signals[0].observation_count == 2
    assert signals[0].raw_value == 2.0


def test_14_provenance_preservation():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="obs-prov-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="platform_collected", data_origin="real",
        fetch_run_id="run-uuid-1", series_id="series-uuid-1", panel_version="v1",
    )
    signals = aggregate_market_signals([obs])
    s = signals[0]
    assert s.observation_ids == ["obs-prov-1"]
    assert s.fetch_run_ids == ["run-uuid-1"]
    assert s.series_id == "series-uuid-1"
    assert s.panel_version == "v1"


def test_15_16_17_data_origin_history_type_panel_version():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="obs-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="backfill", data_origin="real", panel_version="v2",
    )
    signals = aggregate_market_signals([obs])
    assert signals[0].data_origin == "real"
    assert signals[0].history_type == "backfill"
    assert signals[0].panel_version == "v2"


def test_18_deterministic_repeated_aggregation():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = [
        MarketObservation(
            id=f"obs-{i}", source="adzuna", skill="Python", signal_type="demand",
            observed_at=now, period="2026-10", posting_id=f"p-{i}", value=1.0,
            history_type="platform_collected", data_origin="real",
        )
        for i in range(5)
    ]
    res1 = aggregate_market_signals(obs)
    res2 = aggregate_market_signals(obs)
    assert res1 == res2


def test_19_calculation_record_compatibility():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="obs-calc-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="p-1", value=1.0,
        history_type="platform_collected", data_origin="real",
        fetch_run_id="run-1", series_id="adz:series:py:v1",
    )
    signals = aggregate_market_signals([obs])
    # Output schema contains all identity fields expected by calculation record generator
    s = signals[0]
    assert s.source == "adzuna"
    assert s.series_id == "adz:series:py:v1"
    assert s.period == "2026-10"
    assert s.observation_ids == ["obs-calc-1"]
    assert s.fetch_run_ids == ["run-1"]


def test_20_adzuna_c_sharp_compatibility_fixture():
    # Production record:
    # id = e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc
    # fetch_run_id = 61aa8c5206224fa28410d25299767696
    # skill = C#
    # value = 1.0
    now = datetime(2026, 10, 6, 18, 33, 18, tzinfo=timezone.utc)
    prod_obs = MarketObservation(
        id="e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc",
        source="adzuna",
        skill="C#",
        signal_type="demand",
        observed_at=now,
        period="2026-10",
        scope="country",
        location="India",
        posting_id="4686701684",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
        fetch_run_id="61aa8c5206224fa28410d25299767696",
        series_id="adzuna:adzuna:47838af054a71a055855:job-demand:c_sharp:v1",
        panel_version="job-demand-v1",
    )
    signals = aggregate_market_signals([prod_obs])
    assert len(signals) == 1
    signal = signals[0]
    assert signal.canonical_name == "C#"
    assert signal.canonical_skill_id == "c_sharp"
    assert signal.raw_value == 1.0
    assert signal.metric == "raw_count"
    assert signal.normalized_value is None  # Preserved as raw count without false 100% conversion
    assert signal.data_state == "insufficient_data"
    assert signal.observation_ids == ["e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc"]
    assert signal.fetch_run_ids == ["61aa8c5206224fa28410d25299767696"]


def test_missing_provenance_is_not_promoted_to_real_production_history():
    observations = [
        MarketObservation(
            id=f"legacy-{period}",
            source="jsearch",
            skill="Python",
            signal_type="demand",
            observed_at=datetime.fromisoformat(f"{period}-15T00:00:00+00:00"),
            period=period,
            value=10,
            denominator=100,
        )
        for period in ("2025-01", "2025-02", "2025-03", "2025-04")
    ]

    analysis = analyze_market_observations(observations)

    assert analysis.aggregated_signals
    assert all(signal.data_origin == "unavailable" for signal in analysis.aggregated_signals)
    assert all(signal.history_type == "unavailable" for signal in analysis.aggregated_signals)
    assert all(signal.data_state == "insufficient_data" for signal in analysis.aggregated_signals)
    assert analysis.trend_results
    assert all(result.data_origin == "unavailable" for result in analysis.trend_results)
    assert all(result.trend == "Insufficient Data" for result in analysis.trend_results)

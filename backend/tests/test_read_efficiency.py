"""Tests for Milestone G2.0.1: Firestore Read-Efficiency, Caching & Production Read Safety.

Validates Criteria A through N:
A. Targeted series query
B. Targeted skill query
C. Bounded date-range query
D. No unnecessary full collection scan
E. Calculation record reuse
F. Calculation invalidation when input changes
G. Repeated Core Intelligence request does not repeat unnecessary reads
H. Unit tests do not require production Firebase
I. Existing G1.14 analytical results remain unchanged
J. Existing provenance remains unchanged
K. Insufficient data remains insufficient_data
L. No missing data becomes zero
M. No synthetic observations are created
N. No forecasting is introduced
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.trend import calculate_trend_and_velocity
from app.analytics.signal_aggregation import aggregate_market_signals
from app.core.firebase import get_firestore_client
from app.models.core_intelligence import CoreIntelligenceRequest
from app.models.market_signal import SkillTrendVelocityResult
from app.services.core_intelligence_service import CoreIntelligenceService
from app.storage.calculation_record_store import (
    FirestoreCalculationRecordStore,
    clear_calculation_cache,
)
from app.storage.firestore_observation_store import (
    FirestoreObservationStore,
    clear_observations_cache,
)
from app.storage.firestore_read_guard import (
    UnboundedFirestoreReadBlockedError,
    read_guard,
)
from app.storage.mock_firestore_hub import (
    create_verified_production_snapshot,
    get_mock_firestore_client,
)


@pytest.fixture(autouse=True)
def setup_read_test_environment():
    """Ensure caches and counters are reset before each test."""
    clear_observations_cache()
    clear_calculation_cache()
    read_guard.reset_metrics()
    yield
    clear_observations_cache()
    clear_calculation_cache()
    read_guard.reset_metrics()


# -------------------------------------------------------------------------
# Criterion A: Targeted series query
# -------------------------------------------------------------------------
def test_criterion_a_targeted_series_query():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    read_guard.reset_metrics()
    series_id = "stackexchange:stackoverflow:question-tag:python:v1"
    obs = store.get_observations_by_series(series_id)

    assert len(obs) == 5
    assert all(o.series_id == series_id for o in obs)
    assert all(o.source == "stackexchange" for o in obs)

    metrics = read_guard.get_metrics()
    assert metrics["targeted_queries"] >= 1
    assert metrics["broad_scans_attempted"] == 0


# -------------------------------------------------------------------------
# Criterion B: Targeted skill query
# -------------------------------------------------------------------------
def test_criterion_b_targeted_skill_query():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    read_guard.reset_metrics()
    obs_csharp = store.get_observations_by_skill("C#")

    assert len(obs_csharp) >= 5
    assert all(o.skill.casefold() in {"c#", "c_sharp"} for o in obs_csharp)
    # Does NOT pull unrelated skills like Python
    assert not any(o.skill.casefold() == "python" for o in obs_csharp)

    metrics = read_guard.get_metrics()
    assert metrics["targeted_queries"] >= 1
    assert metrics["broad_scans_attempted"] == 0


# -------------------------------------------------------------------------
# Criterion C: Bounded date-range query
# -------------------------------------------------------------------------
def test_criterion_c_bounded_date_range_query():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    cutoff = datetime(2026, 8, 1, tzinfo=timezone.utc)
    obs = store.get_observations(cutoff=cutoff, use_cache=False)

    assert len(obs) > 0
    # No observation from earlier than 2026-08
    for o in obs:
        assert o.observed_at >= cutoff
        assert o.period >= "2026-08"


# -------------------------------------------------------------------------
# Criterion D: No unnecessary full collection scan
# -------------------------------------------------------------------------
def test_criterion_d_no_unnecessary_full_collection_scan(monkeypatch):
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    # In strict mode, broad scans raise an error
    monkeypatch.setenv("STRICT_FIRESTORE_READ_GUARD", "1")

    # Targeted queries succeed without triggering strict guard
    obs = store.get_observations_by_series("stackexchange:stackoverflow:question-tag:c#:v1")
    assert len(obs) == 5

    # all_documents triggers the scan guard
    with pytest.raises(UnboundedFirestoreReadBlockedError):
        store.all_documents()


# -------------------------------------------------------------------------
# Criterion E: Calculation record reuse
# -------------------------------------------------------------------------
def test_criterion_e_calculation_record_reuse():
    client = get_mock_firestore_client()
    calc_store = FirestoreCalculationRecordStore(client)

    obs_store = FirestoreObservationStore(client)
    py_obs = obs_store.get_observations_by_series("stackexchange:stackoverflow:question-tag:python:v1")
    assert len(py_obs) == 5

    agg = aggregate_market_signals(py_obs)
    trends = calculate_trend_and_velocity(agg)
    assert len(trends) == 1
    trend_res = trends[0]

    # First persistence: writes to store
    read_guard.reset_metrics()
    first_records = calc_store.persist_trend_velocity_results(
        [trend_res],
        observations_by_id={o.id: o for o in py_obs if o.id},
    )
    assert len(first_records) == 1
    key = next(iter(first_records.keys()))
    calc_id = first_records[key]

    # Second persistence call with same input: REUSES without duplicate reads/writes
    second_records = calc_store.persist_trend_velocity_results(
        [trend_res],
        observations_by_id={o.id: o for o in py_obs if o.id},
    )
    assert second_records[key] == calc_id

    metrics = read_guard.get_metrics()
    assert metrics["calculation_records_reused"] >= 1

    # find_reusable_trend_calculation retrieves the exact cached record
    cached = calc_store.find_reusable_trend_calculation(
        source=trend_res.source,
        signal_type=trend_res.signal_type,
        canonical_name=trend_res.canonical_name,
        latest_period=trend_res.latest_period,
        observation_ids=trend_res.observation_ids,
        formula_id=trend_res.calculation_version,
    )
    assert cached is not None
    assert cached.calculation_id == calc_id
    assert cached.result["velocity"] == trend_res.velocity


# -------------------------------------------------------------------------
# Criterion F: Calculation invalidation when input changes
# -------------------------------------------------------------------------
def test_criterion_f_calculation_invalidation_when_input_changes():
    client = get_mock_firestore_client()
    calc_store = FirestoreCalculationRecordStore(client)

    # 4 periods observation list
    obs_ids_4 = ["obs-1", "obs-2", "obs-3", "obs-4"]
    # 5 periods observation list (new observation arrived)
    obs_ids_5 = ["obs-1", "obs-2", "obs-3", "obs-4", "obs-5"]

    cached_before = calc_store.find_reusable_trend_calculation(
        source="stackexchange",
        signal_type="interest",
        canonical_name="Python",
        latest_period="2026-08",
        observation_ids=obs_ids_4,
    )
    assert cached_before is None

    # Persist record for 4 periods
    mock_trend = SkillTrendVelocityResult(
        source="stackexchange",
        signal_type="interest",
        canonical_name="Python",
        canonical_skill_id="python",
        latest_period="2026-08",
        latest_value=65.0,
        previous_value=60.0,
        periods_used=["2026-05", "2026-06", "2026-07", "2026-08"],
        observation_ids=obs_ids_4,
        data_state="ready",
        velocity=0.08,
        growth_pct=8.0,
        slope=5.0,
        trend="Increasing",
        confidence=0.85,
        calculation_version="demand-theil-sen-v2-source-specific",
        observation_count=4,
        fetch_run_ids=["run_1"],
        metric="raw_count",
    )
    calc_store.persist_trend_velocity_results([mock_trend])

    # Now 4 periods is found
    cached_4 = calc_store.find_reusable_trend_calculation(
        source="stackexchange",
        signal_type="interest",
        canonical_name="Python",
        latest_period="2026-08",
        observation_ids=obs_ids_4,
    )
    assert cached_4 is not None

    # Changed input (5 periods) MUST NOT reuse the 4-period calculation
    cached_5 = calc_store.find_reusable_trend_calculation(
        source="stackexchange",
        signal_type="interest",
        canonical_name="Python",
        latest_period="2026-09",
        observation_ids=obs_ids_5,
    )
    assert cached_5 is None


# -------------------------------------------------------------------------
# Criterion G: Repeated Core Intelligence request does not repeat reads
# -------------------------------------------------------------------------
def test_criterion_g_repeated_core_intelligence_request_reuses_cache():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="6m",
    )

    # First request
    read_guard.reset_metrics()
    resp1 = svc.get_intelligence(req)
    assert resp1.data_status == "available"
    first_reads = read_guard.get_metrics()["total_document_reads"]

    # Second identical request
    read_guard.reset_metrics()
    resp2 = svc.get_intelligence(req)
    assert resp2.data_status == "available"

    # Second request hits cache; total document reads is 0!
    second_reads = read_guard.get_metrics()["total_document_reads"]
    cache_hits = read_guard.get_metrics()["cache_hits"]

    assert second_reads == 0
    assert cache_hits >= 1
    assert len(resp1.historical_trends) == len(resp2.historical_trends)


# -------------------------------------------------------------------------
# Criterion H: Unit tests do not require production Firebase
# -------------------------------------------------------------------------
def test_criterion_h_unit_tests_do_not_require_production_firebase():
    assert os.getenv("RUN_LIVE_FIRESTORE_TESTS") != "1"
    fs_client = get_firestore_client()
    assert fs_client is not None
    # Collection access works seamlessly in memory
    docs = fs_client.collection("skill_market_signals").stream()
    assert len(docs) == 100


# -------------------------------------------------------------------------
# Criterion I: Existing G1.14 analytical results remain unchanged
# -------------------------------------------------------------------------
def test_criterion_i_g1_14_analytical_results_remain_unchanged():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    # Stack Exchange Python
    py_obs = store.get_observations_by_series("stackexchange:stackoverflow:question-tag:python:v1")
    py_agg = aggregate_market_signals(py_obs)
    py_trends = calculate_trend_and_velocity(py_agg)
    assert len(py_trends) == 1
    py_trend = py_trends[0]

    assert py_trend.trend == "Increasing"
    assert py_trend.slope is not None and py_trend.slope > 0
    assert py_trend.velocity is not None and py_trend.velocity > 0
    assert py_trend.data_state == "ready"

    # Stack Exchange C#
    cs_obs = store.get_observations_by_series("stackexchange:stackoverflow:question-tag:c#:v1")
    cs_agg = aggregate_market_signals(cs_obs)
    cs_trends = calculate_trend_and_velocity(cs_agg)
    assert len(cs_trends) == 1
    cs_trend = cs_trends[0]

    assert cs_trend.trend == "Increasing"
    assert cs_trend.slope is not None and cs_trend.slope > 0
    assert cs_trend.velocity is not None and cs_trend.velocity > 0
    assert cs_trend.data_state == "ready"


# -------------------------------------------------------------------------
# Criterion J: Existing provenance remains unchanged
# -------------------------------------------------------------------------
def test_criterion_j_existing_provenance_remains_unchanged():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    obs = store.get_observations_by_series("stackexchange:stackoverflow:question-tag:python:v1")
    for o in obs:
        assert o.series_id == "stackexchange:stackoverflow:question-tag:python:v1"
        assert o.fetch_run_id is not None
        assert o.fetch_run_id.startswith("run_se_")
        assert o.metadata.get("raw_archive_id") is not None


# -------------------------------------------------------------------------
# Criterion K: Insufficient data remains insufficient_data
# -------------------------------------------------------------------------
def test_criterion_k_insufficient_data_remains_insufficient_data():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    # JSearch has only 1 period (2026-10) in production
    jsearch_obs = [o for o in store.get_observations(cutoff=datetime(2020, 1, 1, tzinfo=timezone.utc)) if o.source == "jsearch"]
    jsearch_agg = aggregate_market_signals(jsearch_obs)
    jsearch_trends = calculate_trend_and_velocity(jsearch_agg)

    for tr in jsearch_trends:
        assert tr.data_state == "insufficient_data"
        assert tr.trend == "Insufficient Data"
        assert tr.velocity is None


# -------------------------------------------------------------------------
# Criterion L: No missing data becomes zero
# -------------------------------------------------------------------------
def test_criterion_l_no_missing_data_becomes_zero():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    svc = CoreIntelligenceService(observation_store=store)
    req = CoreIntelligenceRequest(
        portal_type="individual",
        intelligence_type="skill",
        selected_skills=["Docker"],  # Only 1 period
        time_range="6m",
    )
    resp = svc.get_intelligence(req)

    for t in resp.historical_trends:
        if t.trend_direction == "Insufficient Data":
            assert t.velocity is None
            assert t.growth_pct is None
            # Explicitly must NOT be 0.0
            assert t.velocity != 0.0
            assert t.growth_pct != 0.0


# -------------------------------------------------------------------------
# Criterion M: No synthetic observations are created
# -------------------------------------------------------------------------
def test_criterion_m_no_synthetic_observations():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)

    obs = store.get_observations(cutoff=datetime(2020, 1, 1, tzinfo=timezone.utc), use_cache=False)
    assert len(obs) == 100
    for o in obs:
        assert o.data_origin != "synthetic"
        assert o.data_origin in {"real", None}
        assert o.history_type in {"platform_collected", "snapshot", "backfill", "backfilled"}


# -------------------------------------------------------------------------
# Criterion N: No forecasting is introduced
# -------------------------------------------------------------------------
def test_criterion_n_no_forecasting_introduced():
    client = get_mock_firestore_client()
    store = FirestoreObservationStore(client)
    svc = CoreIntelligenceService(observation_store=store)

    req = CoreIntelligenceRequest(portal_type="company", intelligence_type="market", time_range="6m")
    resp = svc.get_intelligence(req)

    assert resp.readiness.ready_for_forecast_count == 0
    assert all(t.is_forecast_ready is False for t in resp.historical_trends)

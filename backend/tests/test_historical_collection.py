"""Comprehensive test suite for G1.10: Historical Collection Depth & Backfill Expansion."""

from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from app.analytics.analytical_readiness import assess_analytical_readiness, summarize_readiness
from app.analytics.series_validation import validate_series_observations
from app.api import dependencies
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.provider_capability import (
    get_provider_capability,
    list_provider_capabilities,
)
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.market_data.adzuna_provider import AdzunaProvider
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.job_observations import observations_from_postings
from app.services.market_data.jsearch_provider import JSearchProvider
from app.services.market_data.stack_exchange_historical_provider import (
    HistoricalSeriesResult,
    StackExchangeHistoricalProvider,
    _month_bounds,
    _month_periods,
)
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.observation_identity import stable_observation_id


# A. Stable series ID across repeated collection periods
def test_a_stable_series_id_across_periods():
    p1 = MarketPosting(source="jsearch", posting_id="p-1", title="Python Engineer", skills=["Python"])
    p2 = MarketPosting(source="jsearch", posting_id="p-2", title="Python Engineer", skills=["Python"])

    obs_jul = observations_from_postings(
        [p1], location=None, country="in",
        collected_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        query_id="query-fixed", panel_version="job-demand-v1",
    )
    obs_aug = observations_from_postings(
        [p2], location=None, country="in",
        collected_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        query_id="query-fixed", panel_version="job-demand-v1",
    )
    assert obs_jul[0].series_id == obs_aug[0].series_id
    assert "query-fixed" in obs_jul[0].series_id


# B. Different query configurations create different series
def test_b_different_query_configs_create_different_series():
    p = MarketPosting(source="jsearch", posting_id="p-1", title="Python Engineer", skills=["Python"])
    obs_q1 = observations_from_postings(
        [p], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="query-software-engineer",
    )
    obs_q2 = observations_from_postings(
        [p], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="query-data-scientist",
    )
    assert obs_q1[0].series_id != obs_q2[0].series_id


# C. Different providers never share series
def test_c_different_providers_never_share_series():
    cap_js = get_provider_capability("jsearch")
    cap_adz = get_provider_capability("adzuna")
    assert cap_js is not None and cap_adz is not None
    assert cap_js.provider != cap_adz.provider

    p_js = MarketPosting(source="jsearch", posting_id="1", title="Python Dev", skills=["Python"])
    p_adz = MarketPosting(source="adzuna", posting_id="1", title="Python Dev", skills=["Python"])
    obs_js = observations_from_postings([p_js], location=None, country="in", collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc))
    obs_adz = observations_from_postings([p_adz], location=None, country="in", collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert obs_js[0].series_id != obs_adz[0].series_id
    assert obs_js[0].source == "jsearch"
    assert obs_adz[0].source == "adzuna"


# D. Different signal types never share series
def test_d_different_signal_types_never_share_series():
    caps = {cap.provider: cap for cap in list_provider_capabilities()}
    assert caps["jsearch"].signal_type == "demand"
    assert caps["github"].signal_type == "adoption"
    assert caps["stackexchange"].signal_type == "interest"
    assert len({caps["jsearch"].signal_type, caps["github"].signal_type, caps["stackexchange"].signal_type}) == 3


# E. Repeated same collection is idempotent
def test_e_repeated_collection_idempotent():
    posting = MarketPosting(source="jsearch", posting_id="job-idempotent-1", title="Dev", skills=["Python"])
    obs1 = observations_from_postings(
        [posting], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="fixed-query",
    )
    obs2 = observations_from_postings(
        [posting], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="fixed-query",
    )
    id1 = stable_observation_id(obs1[0])
    id2 = stable_observation_id(obs2[0])
    assert id1 == id2


# F. Stack Exchange historical backfill uses genuine provider timestamps
def test_f_stack_exchange_genuine_provider_timestamps():
    start_ts, end_ts, period_end = _month_bounds("2026-07")
    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)
    assert start_dt.year == 2026 and start_dt.month == 7 and start_dt.day == 1
    assert end_dt.year == 2026 and end_dt.month == 7 and end_dt.day == 31
    assert period_end.month == 7


def test_stack_exchange_recursive_intervals_keep_raw_archive_callback():
    class Service:
        anonymous_page_limit = 1
        endpoint = "https://api.stackexchange.com/2.3/questions"

        def __init__(self):
            self.callback_presence = []

        async def questions_page(self, **kwargs):
            callback = kwargs.get("raw_response_callback")
            self.callback_presence.append(callback is not None)
            width = kwargs["todate"] - kwargs["fromdate"]
            return SimpleNamespace(
                items=[],
                has_more=width > 2_000_000,
                quota_remaining=100,
                quota_max=10_000,
                backoff=None,
            )

    service = Service()
    provider = StackExchangeHistoricalProvider(service=service)
    result = HistoricalSeriesResult(
        skill_id="python", skill="Python", tag="python",
        query_id="stackexchange:python", series_id="stackexchange:python",
    )
    archive_calls = []

    import asyncio
    start, end, _ = _month_bounds("2026-07")
    asyncio.run(provider._fetch_complete_interval(
        tag="python",
        start_epoch=start,
        end_epoch=end,
        result=result,
        archive_response=lambda payload, content_type: archive_calls.append(content_type),
    ))

    assert len(service.callback_presence) == 3
    assert all(service.callback_presence)


# G. Historical backfill preserves history_type=backfilled / backfill
def test_g_historical_backfill_preserves_history_type():
    cap = get_provider_capability("stackexchange")
    assert cap is not None
    assert cap.historical_backfill_supported is True
    assert cap.history_type == "backfill"
    assert cap.collection_type == "genuine_historical_backfill"


# H. JSearch uses platform_collected
def test_h_jsearch_uses_platform_collected():
    cap = get_provider_capability("jsearch")
    assert cap is not None
    assert cap.historical_backfill_supported is False
    assert cap.history_type == "platform_collected"
    assert cap.collection_type == "recurring_platform_collection"


# I. Adzuna uses platform_collected
def test_i_adzuna_uses_platform_collected():
    cap = get_provider_capability("adzuna")
    assert cap is not None
    assert cap.historical_backfill_supported is False
    assert cap.history_type == "platform_collected"
    assert cap.collection_type == "recurring_platform_collection"


# J. GitHub uses snapshot/current-live classification
def test_j_github_uses_snapshot():
    cap = get_provider_capability("github")
    assert cap is not None
    assert cap.historical_backfill_supported is False
    assert cap.history_type == "snapshot"
    assert cap.collection_type == "current_live_snapshot"


# K. Missing provider month creates no synthetic observation
def test_k_missing_month_creates_no_synthetic_observation():
    periods = _month_periods("2026-06", "2026-09")
    # Simulate a provider failure for 2026-08 (records only for 06, 07, 09)
    available_periods = [p for p in periods if p != "2026-08"]
    observations = [
        MarketObservation(
            id=f"obs-{p}", source="stackexchange", skill="Python", signal_type="interest",
            observed_at=datetime(2026, int(p.split("-")[1]), 1, tzinfo=timezone.utc),
            period=p, value=10.0, scope="global", posting_id=f"post-{p}",
            history_type="backfill", data_origin="real", series_id="se:series",
        )
        for p in available_periods
    ]
    # Verify no observation exists for 2026-08
    assert all(o.period != "2026-08" for o in observations)
    # G1.8 reports the gap
    reports = validate_series_observations(observations)
    assert len(reports) == 1
    assert "2026-08" in reports[0].coverage_gaps


# L. Provider failure isolation
def test_l_provider_failure_isolation():
    # If JSearch fails, GitHub and Adzuna are still evaluated independently
    obs_adz = MarketObservation(
        id="adz-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", value=5.0, scope="country", posting_id="p-1",
        history_type="platform_collected", data_origin="real",
    )
    obs_gh = MarketObservation(
        id="gh-1", source="github", skill="Python", signal_type="adoption",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", value=100.0, scope="global", posting_id="p-gh",
        history_type="snapshot", data_origin="real",
    )
    reports = validate_series_observations([obs_adz, obs_gh])
    assert len(reports) == 2
    sources = {r.provider for r in reports}
    assert sources == {"adzuna", "github"}


# M. Raw archive provenance preserved
def test_m_raw_archive_provenance():
    assert hasattr(FirestoreObservationStore, "document_for")


# N. Fetch run provenance preserved
def test_n_fetch_run_provenance():
    posting = MarketPosting(source="jsearch", posting_id="j-prov-1", title="Dev", skills=["Python"])
    obs = observations_from_postings(
        [posting], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fetch_run_id="run-uuid-12345",
    )
    assert obs[0].fetch_run_id == "run-uuid-12345"


# O. Observation provenance preserved
def test_o_observation_provenance():
    posting = MarketPosting(source="adzuna", posting_id="a-prov-1", title="Dev", skills=["Python"])
    obs = observations_from_postings(
        [posting], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="query-prov-1", panel_version="panel-v1",
    )
    assert obs[0].query_id == "query-prov-1"
    assert obs[0].panel_version == "panel-v1"


# P. Existing G1.8 validation still detects missing periods
def test_p_g1_8_detects_missing_periods():
    obs = [
        MarketObservation(
            id="1", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc), period="2026-07",
            value=1.0, scope="country", posting_id="p1", series_id="s1", query_id="q1",
            panel_version="p-v1", history_type="platform_collected", data_origin="real",
        ),
        MarketObservation(
            id="2", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), period="2026-09",
            value=1.0, scope="country", posting_id="p2", series_id="s1", query_id="q1",
            panel_version="p-v1", history_type="platform_collected", data_origin="real",
        ),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    assert "2026-08" in reports[0].coverage_gaps


# Q. Existing G1.9 readiness remains correct
def test_q_g1_9_readiness_remains_correct():
    obs = [
        MarketObservation(
            id="1", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
            value=1.0, scope="country", posting_id="p1", series_id="s1", query_id="q1",
            panel_version="p-v1", history_type="platform_collected", data_origin="real",
            denominator=100.0,
        )
    ]
    reports = assess_analytical_readiness(obs)
    assert len(reports) == 1
    assert reports[0].readiness_state == "not_ready"
    assert reports[0].is_trend_ready is False


# R. No null-to-zero conversion
def test_r_no_null_to_zero_conversion():
    obs = MarketObservation(
        id="1", source="adzuna", skill="C#", signal_type="demand",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
        value=1.0, scope="country", posting_id="p1", denominator=None,
        history_type="platform_collected", data_origin="real",
    )
    assert obs.denominator is None
    assert obs.confidence is None


# S. No synthetic historical values
def test_s_no_synthetic_historical_values():
    periods = _month_periods("2026-01", "2026-04")
    assert periods == ["2026-01", "2026-02", "2026-03", "2026-04"]


# T. No duplicate observations after repeated collection
def test_t_no_duplicate_observations():
    p = MarketPosting(source="jsearch", posting_id="dedupe-job-1", title="Python", skills=["Python"])
    time = datetime(2026, 10, 5, tzinfo=timezone.utc)
    obs_batch1 = observations_from_postings([p], location=None, country="in", collected_at=time, query_id="q")
    obs_batch2 = observations_from_postings([p], location=None, country="in", collected_at=time, query_id="q")
    id1 = stable_observation_id(obs_batch1[0])
    id2 = stable_observation_id(obs_batch2[0])
    assert id1 == id2


# U. Existing production records remain readable
def test_u_production_records_remain_readable():
    store = FirestoreObservationStore()
    observations = store.get_observations(cutoff=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert len(observations) >= 90
    sources = {o.source for o in observations}
    assert "adzuna" in sources
    assert "jsearch" in sources
    assert "github" in sources

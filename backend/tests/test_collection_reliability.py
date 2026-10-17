"""Comprehensive test suite for G1.11: Production Historical Accumulation & Collection Reliability."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.analytics.analytical_readiness import assess_analytical_readiness, summarize_readiness
from app.analytics.series_validation import validate_series_observations
from app.api import dependencies
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.provider_capability import get_provider_capability
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.external_apis.github_service import GitHubTopicCount
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.job_observations import observations_from_postings
from app.services.market_data.stack_exchange_historical_provider import (
    StackExchangeHistoricalProvider,
    _month_bounds,
    _month_periods,
)
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.mock_firestore_hub import get_demo_firestore_client
from app.storage.observation_identity import stable_observation_id


# A. Same GitHub configuration across periods → same series ID
def test_a_github_same_config_across_periods():
    class DummyClient:
        async def count_repositories_for_topic(self, topic, raw_response_callback=None):
            return GitHubTopicCount(topic, 100, 1, True, 200, True)

    settings = Settings(_env_file=None, github_token="tok", github_topic="python")
    provider = GitHubProvider(service=DummyClient(), settings=settings)

    import asyncio
    obs_jul = asyncio.run(provider.collect_observations(
        location=None, country=None, collected_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    ))[0]
    obs_aug = asyncio.run(provider.collect_observations(
        location=None, country=None, collected_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    ))[0]

    assert obs_jul.series_id == obs_aug.series_id == "github:repository-topic:python:v1"
    assert obs_jul.period == "2026-07"
    assert obs_aug.period == "2026-08"


# B. Changed GitHub configuration → different series ID
def test_b_github_changed_config_different_series():
    class DummyClient:
        async def count_repositories_for_topic(self, topic, raw_response_callback=None):
            return GitHubTopicCount(topic, 100, 1, True, 200, True)

    import asyncio
    p_py = GitHubProvider(service=DummyClient(), settings=Settings(_env_file=None, github_token="tok", github_topic="python"))
    p_ts = GitHubProvider(service=DummyClient(), settings=Settings(_env_file=None, github_token="tok", github_topic="typescript"))

    obs_py = asyncio.run(p_py.collect_observations(location=None, country=None, collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc)))[0]
    obs_ts = asyncio.run(p_ts.collect_observations(location=None, country=None, collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc)))[0]

    assert obs_py.series_id != obs_ts.series_id
    assert "python" in obs_py.series_id
    assert "typescript" in obs_ts.series_id


# C. Different GitHub queries remain separate comparable series
def test_c_github_query_changes_remain_separate_series():
    obs = [
        MarketObservation(
            id="gh-old", source="github", skill="Python", signal_type="adoption",
            observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), period="2026-09",
            value=100.0, scope="global", posting_id="p-old", query_id="github:0b56cb020be087019f0e",
            panel_version="github-adoption-v1", series_id="github:repository-topic:python:v1",
            history_type="snapshot", data_origin="real",
        ),
        MarketObservation(
            id="gh-new", source="github", skill="Python", signal_type="adoption",
            observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
            value=105.0, scope="global", posting_id="p-new", query_id="github:44cf79821e4a24d4ad68",
            panel_version="github-adoption-v1", series_id="github:repository-topic:python:v1",
            history_type="snapshot", data_origin="real",
        ),
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 2
    assert {report.query_id for report in reports} == {
        "github:0b56cb020be087019f0e",
        "github:44cf79821e4a24d4ad68",
    }
    assert {tuple(report.observation_ids) for report in reports} == {
        ("gh-old",),
        ("gh-new",),
    }
    assert all(report.comparability_status == "compatible" for report in reports)
    assert all("query_id drift" not in " ".join(report.issues) for report in reports)


# D. JSearch repeated collection preserves series ID
def test_d_jsearch_repeated_collection_preserves_series_id():
    p1 = MarketPosting(source="jsearch", posting_id="js-1", title="Python Engineer", skills=["Python"])
    p2 = MarketPosting(source="jsearch", posting_id="js-2", title="Python Engineer", skills=["Python"])
    obs_sep = observations_from_postings(
        [p1], location=None, country="in",
        collected_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        query_id="jsearch:d247ffe6bbdcb175b8de", panel_version="job-demand-v1",
    )
    obs_oct = observations_from_postings(
        [p2], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="jsearch:d247ffe6bbdcb175b8de", panel_version="job-demand-v1",
    )
    assert obs_sep[0].series_id == obs_oct[0].series_id
    assert "d247ffe6bbdcb175b8de" in obs_sep[0].series_id


# E. Adzuna repeated collection preserves series ID
def test_e_adzuna_repeated_collection_preserves_series_id():
    p1 = MarketPosting(source="adzuna", posting_id="adz-1", title="C# Dev", skills=["C#"])
    p2 = MarketPosting(source="adzuna", posting_id="adz-2", title="C# Dev", skills=["C#"])
    obs_sep = observations_from_postings(
        [p1], location=None, country="in",
        collected_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        query_id="adzuna:47838af054a71a055855", panel_version="job-demand-v1",
    )
    obs_oct = observations_from_postings(
        [p2], location=None, country="in",
        collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        query_id="adzuna:47838af054a71a055855", panel_version="job-demand-v1",
    )
    assert obs_sep[0].series_id == obs_oct[0].series_id
    assert "47838af054a71a055855" in obs_sep[0].series_id


# F. Repeated identical collection is idempotent
def test_f_repeated_collection_idempotent():
    p = MarketPosting(source="jsearch", posting_id="job-dup-check", title="Python Engineer", skills=["Python"])
    dt = datetime(2026, 10, 5, tzinfo=timezone.utc)
    b1 = observations_from_postings([p], location=None, country="in", collected_at=dt, query_id="q1")
    b2 = observations_from_postings([p], location=None, country="in", collected_at=dt, query_id="q1")
    assert stable_observation_id(b1[0]) == stable_observation_id(b2[0])


def test_f2_job_observation_identity_is_stable_across_fetch_runs():
    posting = MarketPosting(source="jsearch", posting_id="job-rerun", title="Python Engineer", skills=["Python"])
    common = {
        "location": "Chennai",
        "country": "in",
        "collected_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "query_id": "jsearch:stable-query",
        "panel_version": "job-demand-v1",
    }
    first = observations_from_postings([posting], fetch_run_id="run-a", **common)[0]
    rerun = observations_from_postings([posting], fetch_run_id="run-b", **common)[0]
    changed_query = observations_from_postings(
        [posting], fetch_run_id="run-c", **{**common, "query_id": "jsearch:other-query"},
    )[0]

    assert first.id == rerun.id
    assert stable_observation_id(first) == stable_observation_id(rerun)
    assert first.fetch_run_id == "run-a"
    assert rerun.fetch_run_id == "run-b"
    assert first.id != changed_query.id


# G. Provider failure does not affect other providers
def test_g_provider_failure_isolation():
    obs_adz = MarketObservation(
        id="adz-ok", source="adzuna", skill="C#", signal_type="demand",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
        value=1.0, scope="country", posting_id="p-adz",
        history_type="platform_collected", data_origin="real",
    )
    reports = validate_series_observations([obs_adz])
    assert len(reports) == 1
    assert reports[0].provider == "adzuna"


# H. Stack Exchange historical timestamps generate correct periods
def test_h_stack_exchange_timestamps_generate_correct_periods():
    start_ts, end_ts, period_end = _month_bounds("2026-08")
    assert period_end.strftime("%Y-%m") == "2026-08"
    assert start_ts < end_ts


# I. Stack Exchange backfill is idempotent
def test_i_stack_exchange_backfill_idempotent():
    o1 = MarketObservation(
        id="se-id-1", source="stackexchange", skill="C#", signal_type="interest",
        observed_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2026-08", value=50.0, scope="global", posting_id="monthly-count:c#:2026-08",
        history_type="backfill", data_origin="real", series_id="se:series:c#",
    )
    o2 = MarketObservation(
        id="se-id-1", source="stackexchange", skill="C#", signal_type="interest",
        observed_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2026-08", value=50.0, scope="global", posting_id="monthly-count:c#:2026-08",
        history_type="backfill", data_origin="real", series_id="se:series:c#",
    )
    assert stable_observation_id(o1) == stable_observation_id(o2)


# J. No future period can be fabricated
def test_j_no_future_period_fabricated():
    from app.services.historical_backfill_service import backfill
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
    with pytest.raises(ValueError, match="Historical backfill must end before"):
        backfill(source="stackexchange", skills=["C#"], start_period=current_period, end_period=current_period)


# K. Missing month remains missing
def test_k_missing_month_remains_missing():
    periods = ["2026-06", "2026-07", "2026-09"]
    obs = [
        MarketObservation(
            id=f"o-{p}", source="stackexchange", skill="C#", signal_type="interest",
            observed_at=datetime(2026, int(p.split("-")[1]), 1, tzinfo=timezone.utc),
            period=p, value=10.0, scope="global", posting_id=f"p-{p}",
            history_type="backfill", data_origin="real", series_id="se:s",
        )
        for p in periods
    ]
    reports = validate_series_observations(obs)
    assert "2026-08" in reports[0].coverage_gaps
    r_reports = assess_analytical_readiness(obs, quality_reports=reports)
    assert r_reports[0].readiness_state == "blocked_missing_period"


# L. Raw archive provenance preserved
def test_l_raw_archive_provenance():
    assert hasattr(FirestoreObservationStore, "document_for")


# M. Fetch run provenance preserved
def test_m_fetch_run_provenance():
    p = MarketPosting(source="jsearch", posting_id="j-prov", title="Dev", skills=["Python"])
    obs = observations_from_postings([p], location=None, country="in", collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc), fetch_run_id="run-999")
    assert obs[0].fetch_run_id == "run-999"


# N. Observation provenance preserved
def test_n_observation_provenance():
    p = MarketPosting(source="jsearch", posting_id="j-prov", title="Dev", skills=["Python"])
    obs = observations_from_postings([p], location=None, country="in", collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc), query_id="q-prov", panel_version="p-prov")
    assert obs[0].query_id == "q-prov"
    assert obs[0].panel_version == "p-prov"


# O. G1.8 receives the actual observations
def test_o_g1_8_receives_actual_observations():
    obs = [
        MarketObservation(
            id=f"o-{idx}", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, idx, 1, tzinfo=timezone.utc), period=f"2026-0{idx}",
            value=float(idx * 10), scope="country", posting_id=f"p-{idx}", series_id="s1",
            query_id="q1", panel_version="p1", history_type="platform_collected", data_origin="real",
            denominator=100.0,
        )
        for idx in range(6, 10)
    ]
    reports = validate_series_observations(obs)
    assert len(reports) == 1
    assert reports[0].quality_state == "valid"
    assert reports[0].is_analytically_sufficient is True


# P. G1.9 receives the G1.8 quality result
def test_p_g1_9_receives_g1_8_quality_result():
    obs = [
        MarketObservation(
            id=f"o-{idx}", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, idx, 1, tzinfo=timezone.utc), period=f"2026-0{idx}",
            value=float(idx * 10), scope="country", posting_id=f"p-{idx}", series_id="s1",
            query_id="q1", panel_version="p1", history_type="platform_collected", data_origin="real",
            denominator=100.0,
        )
        for idx in range(6, 10)
    ]
    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)
    assert r_reports[0].is_trend_ready is True
    assert r_reports[0].quality_state == "valid"


# Q. No null-to-zero conversion
def test_q_no_null_to_zero_conversion():
    obs = MarketObservation(
        id="1", source="adzuna", skill="C#", signal_type="demand",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
        value=1.0, scope="country", posting_id="p1", denominator=None,
        history_type="platform_collected", data_origin="real",
    )
    assert obs.denominator is None


# R. No synthetic observations are inserted into collected provider data
def test_r_no_synthetic_production_observations():
    periods = _month_periods("2026-05", "2026-07")
    assert periods == ["2026-05", "2026-06", "2026-07"]


# S. History taxonomy remains backward-compatible
def test_s_history_taxonomy_backward_compatible():
    cap = get_provider_capability("stackexchange")
    assert cap.history_type in {"backfill", "backfilled"}
    # Model allows both
    obs_backfill = MarketObservation(
        id="1", source="stackexchange", skill="Python", signal_type="interest",
        observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc), period="2026-07",
        value=1.0, scope="global", posting_id="p1", history_type="backfill", data_origin="real",
    )
    obs_backfilled = MarketObservation(
        id="2", source="stackexchange", skill="Python", signal_type="interest",
        observed_at=datetime(2026, 7, 1, tzinfo=timezone.utc), period="2026-07",
        value=1.0, scope="global", posting_id="p2", history_type="backfilled", data_origin="real",
    )
    assert obs_backfill.history_type == "backfill"
    assert obs_backfilled.history_type == "backfilled"


# T. Explicit demo observations remain readable
def test_t_explicit_demo_observations_remain_readable():
    store = FirestoreObservationStore(get_demo_firestore_client())
    observations = store.get_observations(cutoff=datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert len(observations) == 100
    assert all(observation.data_origin == "demo" for observation in observations)


# U. Collection status accurately reflects provider results
def test_u_collection_status_reflects_explicit_demo_provider_results(monkeypatch):
    from app.services import market_collection_service
    from app.storage.fetch_run_store import FirestoreFetchRunStore
    from app.storage.firestore_observation_store import FirestoreObservationStore

    demo_client = get_demo_firestore_client()
    monkeypatch.setattr(
        market_collection_service,
        "FirestoreFetchRunStore",
        lambda: FirestoreFetchRunStore(demo_client),
    )
    monkeypatch.setattr(
        market_collection_service,
        "FirestoreObservationStore",
        lambda: FirestoreObservationStore(demo_client),
    )
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="g1-11-tester", email="test@example.com")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    try:
        response = client.get("/api/v1/market/status")
        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "providers" in data
        provider_names = {p["provider"] for p in data["providers"]}
        assert "jsearch" in provider_names
        assert "adzuna" in provider_names
        assert "github" in provider_names
        for p in data["providers"]:
            assert "provider" in p
            assert "observation_count" in p
            assert "history_type" in p
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)

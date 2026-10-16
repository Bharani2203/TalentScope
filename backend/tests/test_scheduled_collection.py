"""Comprehensive test suite for G1.7: Real Historical Data Depth & Scheduled Collection."""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_skill_trends, calculate_trend_and_velocity
from app.api import dependencies
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import (
    MarketCollectionRequest,
    MarketCollectionResponse,
    MarketCollectionStatusResponse,
    MarketObservation,
    MarketPosting,
    ProviderCollectionResult,
)
from app.services.market_collection_service import (
    collect_market_data,
    get_collection_status,
)
from app.services.market_data.adzuna_provider import AdzunaProvider
from app.services.market_data.base import PostingFetchResult
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.jsearch_provider import JSearchProvider
from app.services.market_data.stack_exchange_historical_provider import (
    StackExchangeHistoricalProvider,
)
from app.services.market_data_scheduler import MarketDataScheduler


class MemoryFetchRunStore:
    def __init__(self):
        self.records: dict[str, dict] = {}

    def start(self, run_id: str, record: dict):
        assert run_id not in self.records
        self.records[run_id] = dict(record)

    def finish(self, run_id: str, record: dict):
        self.records[run_id].update(record)

    def collection_summary(self):
        latest = {}
        for row in sorted(self.records.values(), key=lambda item: item["started_at"], reverse=True):
            latest.setdefault(row["source"].casefold(), row)
        return {"last_collection": {"providers": latest} if latest else None}


class MemoryObservationStore:
    def __init__(self):
        self.records: dict[str, MarketObservation] = {}

    def insert_observations(self, observations, **kwargs):
        added = 0
        for observation in observations:
            doc_id = observation.id or f"{observation.source}:{observation.skill}:{observation.period}"
            if doc_id not in self.records:
                self.records[doc_id] = observation
                added += 1
        return added

    def get_observations(self, **kwargs):
        return list(self.records.values())


class MemoryRawArchive:
    def __init__(self):
        self.archived = []

    def archive(self, *, provider, fetch_run_id, collected_at, payload, content_type=None, response_index=0):
        ref = {
            "provider": provider,
            "fetch_run_id": fetch_run_id,
            "archive_reference": f"raw_response_archives/{provider}__{fetch_run_id}__{response_index:06d}",
            "content_type": content_type or "application/json",
        }
        self.archived.append(ref)
        return ref


class MockPostingProvider:
    def __init__(self, name: str, postings: list[MarketPosting], error: Exception | None = None):
        self.name = name
        self.postings = postings
        self.error = error
        self.historical_backfill_supported = False

    async def fetch_market_postings_with_stats(self, *, location, country, collected_at, fetch_run_id=None, archive_response=None):
        if self.error:
            raise self.error
        if archive_response:
            archive_response({"sample": "payload"})
        return PostingFetchResult(
            postings=self.postings,
            records_fetched=len(self.postings),
            records_rejected=0,
            records_filtered=0,
        )


class MockObservationProvider:
    def __init__(self, name: str, observations: list[MarketObservation], error: Exception | None = None):
        self.name = name
        self.observations = observations
        self.error = error
        self.historical_backfill_supported = False

    async def collect_observations(self, **kwargs):
        if self.error:
            raise self.error
        return self.observations


# A. provider collection creates a new fetch run
def test_a_provider_collection_creates_new_fetch_run():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="job-1", title="Python Developer", skills=["Python"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.status == "success"
    assert len(fetch_runs.records) == 1
    run_record = next(iter(fetch_runs.records.values()))
    assert run_record["source"] == "jsearch"
    assert run_record["collection_run_id"] == result.run_id
    assert run_record["status"] == "success"
    assert run_record["records_fetched"] == 1
    observation = next(iter(obs_store.records.values()))
    assert observation.skill_id == "python"
    assert observation.source == "jsearch"
    assert observation.signal_type == "demand"
    assert observation.unit == "job_postings"
    assert observation.denominator is None
    assert observation.series_id
    assert observation.query_id == run_record["query_id"]
    assert observation.fetch_run_id == run_record["run_id"]
    assert observation.period


# B. raw archive linkage
def test_b_raw_archive_linkage():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("adzuna", [
        MarketPosting(source="adzuna", posting_id="adz-1", title="Go Engineer", skills=["Go"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert len(archive.archived) == 1
    assert archive.archived[0]["provider"] == "adzuna"
    run_record = next(iter(fetch_runs.records.values()))
    assert run_record["raw_response_archive"] is not None
    assert run_record["raw_response_archive"]["archive_reference"] == archive.archived[0]["archive_reference"]


# C. observation persistence
def test_c_observation_persistence():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="p-100", title="TypeScript Specialist", skills=["TypeScript"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.observations_inserted == 1
    assert len(obs_store.records) == 1
    saved = next(iter(obs_store.records.values()))
    assert saved.skill == "TypeScript"
    assert saved.source == "jsearch"


# D. period assignment
def test_d_period_assignment():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="p-200", title="Python Engineer", skills=["Python"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    now_period = datetime.now(timezone.utc).strftime("%Y-%m")
    assert result.period == now_period
    saved = next(iter(obs_store.records.values()))
    assert saved.period == now_period


# E. repeated collection idempotency
def test_e_repeated_collection_idempotency():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    obs = MarketObservation(
        id="stable-id-1", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", posting_id="job-dup", value=1.0,
        unit="job_postings", skill_id="python", history_type="platform_collected",
        data_origin="real", series_id="jsearch:test-query:job-demand:python:v1",
        query_id="jsearch:test-query", panel_version="job-demand-v1",
    )
    provider = MockObservationProvider("jsearch", [obs])
    settings = Settings(_env_file=None)

    res1 = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))
    res2 = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert res1.observations_inserted == 1
    assert res2.observations_inserted == 0
    assert len(obs_store.records) == 1


# F. different-period persistence
def test_f_different_period_persistence():
    obs_store = MemoryObservationStore()
    obs_oct = MarketObservation(
        id="obs-oct-2026", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", posting_id="j-1", value=1.0,
    )
    obs_nov = MarketObservation(
        id="obs-nov-2026", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        period="2026-11", scope="global", posting_id="j-1", value=1.0,
    )

    obs_store.insert_observations([obs_oct])
    obs_store.insert_observations([obs_nov])

    assert len(obs_store.records) == 2
    periods = {item.period for item in obs_store.records.values()}
    assert periods == {"2026-10", "2026-11"}


# G. provider isolation
def test_g_provider_isolation():
    obs_jsearch = MarketObservation(
        id="js-1", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=10.0,
    )
    obs_adzuna = MarketObservation(
        id="adz-1", source="adzuna", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=5.0,
    )

    aggregated = aggregate_market_signals([obs_jsearch, obs_adzuna])
    assert len(aggregated) == 2
    sources = {sig.source for sig in aggregated}
    assert sources == {"jsearch", "adzuna"}


# H. signal-type isolation
def test_h_signal_type_isolation():
    obs_demand = MarketObservation(
        id="dem-1", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=1.0,
    )
    obs_adoption = MarketObservation(
        id="adp-1", source="github", skill="Python",
        signal_type="adoption", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=1000.0,
    )

    aggregated = aggregate_market_signals([obs_demand, obs_adoption])
    signals = {sig.signal_type for sig in aggregated}
    assert signals == {"demand", "adoption"}
    demand_sig = next(s for s in aggregated if s.signal_type == "demand")
    adoption_sig = next(s for s in aggregated if s.signal_type == "adoption")
    assert demand_sig.source == "jsearch"
    assert adoption_sig.source == "github"


# I. source-specific denominator preservation
def test_i_source_specific_denominator_preservation():
    obs_jsearch = MarketObservation(
        id="js-d", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=2.0, denominator=10.0,
    )
    obs_adzuna = MarketObservation(
        id="adz-d", source="adzuna", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=3.0, denominator=50.0,
    )

    denominators = {
        ("jsearch", "demand", "2026-10"): 10.0,
        ("adzuna", "demand", "2026-10"): 50.0,
    }
    aggregated = aggregate_market_signals([obs_jsearch, obs_adzuna], source_denominators=denominators)
    denom_by_source = {s.source: s.denominator for s in aggregated}
    assert denom_by_source["jsearch"] == 10.0
    assert denom_by_source["adzuna"] == 50.0


# J. JSearch failure does not erase Adzuna/GitHub
def test_j_jsearch_failure_does_not_erase_adzuna_or_github():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    js_fail = MockPostingProvider("jsearch", [], error=Exception("JSearch network error"))
    adz_ok = MockPostingProvider("adzuna", [
        MarketPosting(source="adzuna", posting_id="adz-1", title="C# Dev", skills=["C#"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[js_fail, adz_ok],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.status == "partial_failure"
    assert "jsearch" in result.sources_failed
    assert "adzuna" in result.sources_succeeded
    assert result.observations_inserted == 1
    assert len(obs_store.records) == 1


# K. Adzuna failure does not erase JSearch/GitHub
def test_k_adzuna_failure_does_not_erase_jsearch():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    adz_fail = MockPostingProvider("adzuna", [], error=Exception("Adzuna rate limited"))
    js_ok = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="js-1", title="Java Dev", skills=["Java"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[adz_fail, js_ok],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.status == "partial_failure"
    assert "adzuna" in result.sources_failed
    assert "jsearch" in result.sources_succeeded
    assert result.observations_inserted == 1


# L. GitHub failure does not erase demand data
def test_l_github_failure_does_not_erase_demand_data():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    gh_fail = MockObservationProvider("github", [], error=Exception("GitHub auth expired"))
    js_ok = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="js-2", title="Python Engineer", skills=["Python"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[gh_fail, js_ok],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.status == "partial_failure"
    assert "github" in result.sources_failed
    assert "jsearch" in result.sources_succeeded
    assert result.observations_inserted == 1


# M. historical backfill labeling
def test_m_historical_backfill_labeling():
    obs = MarketObservation(
        source="stackexchange", skill="Python", signal_type="interest",
        observed_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2026-08", value=42.0, history_type="backfill", data_origin="real",
    )
    assert obs.history_type == "backfill"
    assert obs.data_origin == "real"


# N. platform-collected labeling
def test_n_platform_collected_labeling():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="js-p", title="SQL Dev", skills=["SQL"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    assert result.data_origin == "real"
    assert result.history_type == "platform_collected"
    saved = next(iter(obs_store.records.values()))
    assert saved.data_origin == "real"
    assert saved.history_type == "platform_collected"


# O. missing-period behavior
def test_o_missing_period_behavior():
    signals = [
        MarketObservation(
            id="p-1", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 6, 1, tzinfo=timezone.utc), period="2026-06", value=10.0,
        ),
        MarketObservation(
            id="p-2", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc), period="2026-08", value=12.0,
        ),
    ]
    aggregated = aggregate_market_signals(signals)
    periods = [sig.period for sig in aggregated]
    # Missing period 2026-07 is NEVER fabricated
    assert periods == ["2026-06", "2026-08"]
    assert "2026-07" not in periods


# P. existing G1.4 insufficient-data behavior
def test_p_existing_g1_4_insufficient_data_behavior():
    # Only 2 periods: below minimum 4 periods
    signals = [
        MarketObservation(
            id="p-1", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), period="2026-09", value=10.0,
            unit="job_postings", skill_id="python", history_type="platform_collected",
            data_origin="real", series_id="jsearch:test-query:job-demand:python:v1",
            query_id="jsearch:test-query", panel_version="job-demand-v1",
        ),
        MarketObservation(
            id="p-2", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10", value=12.0,
            unit="job_postings", skill_id="python", history_type="platform_collected",
            data_origin="real", series_id="jsearch:test-query:job-demand:python:v1",
            query_id="jsearch:test-query", panel_version="job-demand-v1",
        ),
    ]
    aggregated = aggregate_market_signals(signals)
    trends = calculate_trend_and_velocity(aggregated, min_periods=4)
    assert len(trends) == 1
    t = trends[0]
    assert t.data_state == "insufficient_data"
    assert t.trend == "Insufficient Data"
    assert t.slope is None
    assert t.confidence is None


# Q. existing G1.6 API compatibility
def test_q_existing_g1_6_api_compatibility():
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="g1-7-test-user", email="test@example.com")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    try:
        response = client.get("/api/v1/skills/intelligence?range=6m")
        assert response.status_code == 200
        data = response.json()
        assert "data_status" in data
        assert "data_origin" in data
        assert "history_type" in data
        assert "skill_trends" in data
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


# R. provenance chain preservation
def test_r_provenance_chain_preservation():
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()
    archive = MemoryRawArchive()
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="p-chain", title="C++ Programmer", skills=["C++"])
    ])
    settings = Settings(_env_file=None)

    result = asyncio.run(collect_market_data(
        settings=settings, providers=[provider],
        fetch_run_store=fetch_runs, observation_store=obs_store,
        raw_response_archive=archive,
    ))

    saved = next(iter(obs_store.records.values()))
    assert saved.fetch_run_id is not None
    assert saved.query_id is not None
    assert saved.panel_version is not None
    assert saved.series_id is not None


# S. no synthetic values
def test_s_no_synthetic_values():
    signals = [
        MarketObservation(
            id="s-1", source="jsearch", skill="Python", signal_type="demand",
            observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10", value=1.0,
        )
    ]
    aggregated = aggregate_market_signals(signals)
    assert aggregated[0].raw_value == 1.0
    # No random or synthesized values
    assert aggregated[0].data_origin == "real"


# T. no duplicate observations
def test_t_no_duplicate_observations():
    obs_store = MemoryObservationStore()
    obs = MarketObservation(
        id="unique-obs-key", source="adzuna", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10", scope="global", value=1.0,
    )
    ins1 = obs_store.insert_observations([obs])
    ins2 = obs_store.insert_observations([obs])
    assert ins1 == 1
    assert ins2 == 0
    assert len(obs_store.records) == 1


# Provider historical_backfill_supported flags
def test_provider_historical_backfill_flags():
    assert JSearchProvider.historical_backfill_supported is False
    assert AdzunaProvider.historical_backfill_supported is False
    assert GitHubProvider.historical_backfill_supported is False
    assert StackExchangeHistoricalProvider.historical_backfill_supported is True


# Scheduler unit tests
def test_scheduler_lifecycle():
    settings = Settings(_env_file=None)
    scheduler = MarketDataScheduler(settings=settings, interval_seconds=10.0)
    assert scheduler.is_running is False
    assert scheduler.interval_seconds == 10.0
    status = scheduler.status()
    assert status["is_running"] is False
    assert status["run_count"] == 0


def test_scheduler_run_once(monkeypatch):
    settings = Settings(_env_file=None)
    provider = MockPostingProvider("jsearch", [
        MarketPosting(source="jsearch", posting_id="sched-1", title="Ruby Dev", skills=["Ruby"])
    ])
    fetch_runs = MemoryFetchRunStore()
    obs_store = MemoryObservationStore()

    scheduler = MarketDataScheduler(settings=settings, interval_seconds=10.0)

    # Patch collect_market_data inside scheduler
    async def mock_collect(**kwargs):
        return MarketCollectionResponse(
            run_id="sched-run-1",
            status="success",
            observations_inserted=1,
            sources_succeeded=["jsearch"],
            providers=[
                ProviderCollectionResult(
                    fetch_run_id="f-1", provider="jsearch", status="success",
                    records_fetched=1, period="2026-10",
                )
            ],
            period="2026-10",
            data_origin="real",
            history_type="platform_collected",
        )

    monkeypatch.setattr("app.services.market_data_scheduler.collect_market_data", mock_collect)
    result = asyncio.run(scheduler.run_once())
    assert result.status == "success"
    assert scheduler.status()["run_count"] == 1
    assert scheduler.status()["last_status"] == "success"


# Authenticated API endpoints: POST /api/v1/market/admin/collect and GET /api/v1/market/status
def test_unauthenticated_market_admin_collect_requires_auth():
    client = TestClient(app)
    response = client.post("/api/v1/market/admin/collect", json={})
    assert response.status_code == 401


def test_standard_user_market_collect_route_remains_404():
    client = TestClient(app)
    # The non-admin /collect route remains explicitly unexposed
    response = client.post("/api/v1/market/collect", json={})
    assert response.status_code == 404


def test_market_status_requires_authentication():
    client = TestClient(app)
    response = client.get("/api/v1/market/status")
    assert response.status_code == 401


def test_authenticated_market_collect_endpoint(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, **kwargs: {
            "uid": "admin-collector",
            "email": "admin@example.com",
            "role": "admin",
        },
    )

    async def mock_collect_data(**kwargs):
        return MarketCollectionResponse(
            run_id="mock-run-id",
            status="success",
            observations_inserted=2,
            sources_succeeded=["jsearch"],
            providers=[
                ProviderCollectionResult(
                    fetch_run_id="p-run-1",
                    provider="jsearch",
                    status="success",
                    records_fetched=2,
                    observations_created=2,
                    period="2026-10",
                    data_origin="real",
                    history_type="platform_collected",
                )
            ],
            period="2026-10",
            data_origin="real",
            history_type="platform_collected",
        )

    monkeypatch.setattr("app.api.routes.market.collect_market_data", mock_collect_data)
    try:
        response = client.post(
            "/api/v1/market/admin/collect",
            headers={"Authorization": "Bearer verified-admin-token"},
            json={"country": "in"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "mock-run-id"
        assert data["status"] == "success"
        assert len(data["providers"]) == 1
        p = data["providers"][0]
        assert p["fetch_run_id"] == "p-run-1"
        assert p["provider"] == "jsearch"
        assert p["data_origin"] == "real"
        assert p["history_type"] == "platform_collected"
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_non_admin_market_collect_is_forbidden_and_does_not_run(monkeypatch):
    client = TestClient(app)
    collector_called = False

    async def mock_user():
        return AuthenticatedUser(uid="ordinary-user", email="user@example.com", role="user")

    async def mock_collect_data(**kwargs):
        nonlocal collector_called
        collector_called = True
        raise AssertionError("unauthorized collection must not execute")

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    monkeypatch.setattr("app.api.routes.market.collect_market_data", mock_collect_data)
    try:
        response = client.post("/api/v1/market/admin/collect", json={"country": "in"})
        assert response.status_code == 403
        assert collector_called is False
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


@pytest.mark.parametrize("role_claim", [None, "", "user", "admin ", ["admin"]])
def test_market_collect_requires_verified_admin_claim(monkeypatch, role_claim):
    client = TestClient(app)
    collector_called = False

    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, **kwargs: {"uid": "claim-test-user", **({"role": role_claim} if role_claim is not None else {})},
    )

    async def mock_collect_data(**kwargs):
        nonlocal collector_called
        collector_called = True
        raise AssertionError("non-admin claim must not execute collection")

    monkeypatch.setattr("app.api.routes.market.collect_market_data", mock_collect_data)
    response = client.post(
        "/api/v1/market/admin/collect",
        headers={"Authorization": "Bearer verified-token"},
        json={"country": "in"},
    )

    assert response.status_code == 403
    assert collector_called is False


def test_client_supplied_admin_role_does_not_authorize_collection(monkeypatch):
    client = TestClient(app)
    collector_called = False

    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, **kwargs: {"uid": "ordinary-user", "role": "user"},
    )

    async def mock_collect_data(**kwargs):
        nonlocal collector_called
        collector_called = True
        raise AssertionError("client-supplied role must not execute collection")

    monkeypatch.setattr("app.api.routes.market.collect_market_data", mock_collect_data)
    response = client.post(
        "/api/v1/market/admin/collect",
        headers={"Authorization": "Bearer verified-user-token"},
        json={"role": "admin", "country": "in"},
    )

    assert response.status_code == 403
    assert collector_called is False


def test_market_collect_rejects_invalid_firebase_token_before_collection(monkeypatch):
    client = TestClient(app)
    collector_called = False

    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())

    def reject_token(token, **kwargs):
        from firebase_admin import auth
        raise auth.InvalidIdTokenError("invalid token")

    monkeypatch.setattr(dependencies.auth, "verify_id_token", reject_token)

    async def mock_collect_data(**kwargs):
        nonlocal collector_called
        collector_called = True
        raise AssertionError("invalid token must not execute collection")

    monkeypatch.setattr("app.api.routes.market.collect_market_data", mock_collect_data)
    response = client.post(
        "/api/v1/market/admin/collect",
        headers={"Authorization": "Bearer invalid-token"},
        json={"role": "admin", "country": "in"},
    )

    assert response.status_code == 401
    assert collector_called is False


def test_authenticated_market_status_endpoint(monkeypatch):
    client = TestClient(app)

    async def mock_user():
        return AuthenticatedUser(uid="admin-collector", email="admin@example.com")

    def mock_get_status(**kwargs):
        return MarketCollectionStatusResponse(
            overall_status="partial_failure",
            latest_collection=datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc),
            providers=[],
        )

    app.dependency_overrides[dependencies.get_current_user] = mock_user
    monkeypatch.setattr("app.api.routes.market.get_collection_status", mock_get_status)
    try:
        response = client.get("/api/v1/market/status")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "partial_failure"
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)

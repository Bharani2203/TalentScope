import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes import market as market_routes
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import MarketObservation
from app.models.skill_intelligence import MarketPosting
from app.services.market_data.base import PostingFetchResult
from app.services.market_collection_service import (
    collect_market_data,
    configured_market_providers,
    pending_market_sources,
)
from app.storage.market_store import MarketDataStore


class StubCollector:
    def __init__(self, name, *, error=None, observations=None):
        self.name = name
        self.error = error
        self.observations = observations or []

    async def collect_observations(self, **kwargs):
        if self.error:
            raise self.error
        return self.observations


class MemoryFetchRunStore:
    def __init__(self):
        self.records = {}

    def start(self, run_id, record):
        assert run_id not in self.records
        self.records[run_id] = dict(record)

    def finish(self, run_id, record):
        self.records[run_id].update(record)

    def collection_summary(self):
        latest = {}
        for row in sorted(self.records.values(), key=lambda item: item["started_at"], reverse=True):
            latest.setdefault(row["source"].casefold(), row)
        return {"last_collection": {"providers": latest} if latest else None}


class MemoryObservationStore:
    def __init__(self):
        self.records = {}

    def insert_observations(self, observations, **kwargs):
        added = 0
        for observation in observations:
            if observation.id not in self.records:
                self.records[observation.id] = observation
                added += 1
        return added


def test_configured_market_providers_respect_enabled_allow_list(monkeypatch):
    created = []

    def provider_factory(name):
        def create(*, settings):
            created.append((name, settings))
            return type("StubProvider", (), {"name": name})()
        return create

    monkeypatch.setattr("app.services.market_collection_service.JSearchProvider", provider_factory("jsearch"))
    monkeypatch.setattr("app.services.market_collection_service.AdzunaProvider", provider_factory("adzuna"))
    monkeypatch.setattr("app.services.market_collection_service.GitHubProvider", provider_factory("github"))
    settings = Settings(
        _env_file=None,
        jsearch_api_key="configured",
        adzuna_app_id="configured",
        adzuna_app_key="configured",
        github_token="configured",
        market_collection_enabled_providers=[" JSEARCH ", "github"],
    )

    providers = configured_market_providers(settings)

    assert [provider.name for provider in providers] == ["jsearch", "github"]
    assert [name for name, _ in created] == ["jsearch", "github"]
    assert "Adzuna" in pending_market_sources(settings)


def test_disabled_and_unconfigured_market_providers_are_not_constructed(monkeypatch):
    created = []

    def provider_factory(name):
        def create(*, settings):
            created.append((name, settings))
            return type("StubProvider", (), {"name": name})()
        return create

    monkeypatch.setattr("app.services.market_collection_service.JSearchProvider", provider_factory("jsearch"))
    monkeypatch.setattr("app.services.market_collection_service.AdzunaProvider", provider_factory("adzuna"))
    monkeypatch.setattr("app.services.market_collection_service.GitHubProvider", provider_factory("github"))
    settings = Settings(
        _env_file=None,
        jsearch_api_key="configured-but-disabled",
        market_collection_enabled_providers=["adzuna"],
    )

    assert configured_market_providers(settings) == []
    assert created == []


def test_unknown_enabled_market_provider_fails_closed():
    settings = Settings(
        _env_file=None,
        market_collection_enabled_providers=["jsearch", "unknown-provider"],
    )

    with pytest.raises(ValueError, match="Unsupported market collection provider"):
        configured_market_providers(settings)


def test_collection_continues_when_one_provider_fails_and_persists_results(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        id="jsearch-o1",
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=captured,
        period="2026-10",
        location="Chennai",
        scope="city",
        posting_id="job-1",
        value=1,
        unit="job_postings",
        history_type="platform_collected",
        data_origin="real",
    )
    configured = Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "market.sqlite3"))
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()

    result = asyncio.run(collect_market_data(
        location="Chennai",
        country="in",
        settings=configured,
        store=store,
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
        providers=[
            StubCollector("jsearch", observations=[observation]),
            StubCollector("adzuna", error=RuntimeError("sensitive upstream response")),
        ],
    ))

    assert result.status == "partial_failure"
    assert result.observations_inserted == 1
    assert result.sources_succeeded == ["jsearch"]
    assert result.sources_failed == {"adzuna": "Adzuna collection failed."}
    assert "sensitive upstream response" not in str(result.model_dump())
    assert len(observation_store.records) == 1
    assert {run["source"]: run["status"] for run in fetch_runs.records.values()} == {
        "jsearch": "success", "adzuna": "failed",
    }


def test_collection_continues_when_jsearch_fails_and_adzuna_results_are_preserved(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    captured = datetime(2026, 10, 6, tzinfo=timezone.utc)
    observation = MarketObservation(
        id="adzuna-o1",
        source="adzuna",
        skill="Python",
        signal_type="demand",
        observed_at=captured,
        period="2026-10",
        location="India",
        scope="country",
        posting_id="adzuna-job-1",
        value=1,
        unit="job_postings",
        history_type="platform_collected",
        data_origin="real",
    )
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()

    result = asyncio.run(collect_market_data(
        location=None,
        country="in",
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "market.sqlite3")),
        store=store,
        providers=[
            StubCollector("jsearch", error=RuntimeError("private upstream error")),
            StubCollector("adzuna", observations=[observation]),
        ],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "partial_failure"
    assert result.sources_failed == {"jsearch": "JSearch collection failed."}
    assert result.sources_succeeded == ["adzuna"]
    assert result.observations_inserted == 1
    assert len(observation_store.records) == 1
    assert "private upstream error" not in str(result.model_dump())
    assert {run["source"]: run["status"] for run in fetch_runs.records.values()} == {
        "jsearch": "failed", "adzuna": "success",
    }


def test_collection_idempotently_ignores_duplicate_observations(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    observed_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        id="same-id",
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=observed_at,
        period="2026-10",
        location="Chennai",
        scope="city",
        posting_id="job-1",
        value=1,
        unit="job_postings",
        history_type="platform_collected",
        data_origin="real",
    )
    settings = Settings(_env_file=None)
    provider = [StubCollector("jsearch", observations=[observation])]
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()

    first = asyncio.run(collect_market_data(settings=settings, store=store, providers=provider, fetch_run_store=fetch_runs, observation_store=observation_store))
    second = asyncio.run(collect_market_data(settings=settings, store=store, providers=provider, fetch_run_store=fetch_runs, observation_store=observation_store))

    assert first.observations_inserted == 1
    assert second.observations_inserted == 0
    assert len(observation_store.records) == 1
    assert len(fetch_runs.records) == 2
    assert len({run["run_id"] for run in fetch_runs.records.values()}) == 2


def test_fetch_run_separates_malformed_unmatched_and_filtered_provider_records(tmp_path):
    class Provider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[
                    MarketPosting(source="adzuna", posting_id="job-1", title="Python engineer"),
                    MarketPosting(source="adzuna", posting_id="job-2", title="Office coordinator"),
                ],
                records_fetched=4,
                records_rejected=1,
                records_filtered=1,
            )

    fetch_runs = MemoryFetchRunStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[Provider()],
        fetch_run_store=fetch_runs,
        observation_store=MemoryObservationStore(),
    ))

    run = next(iter(fetch_runs.records.values()))
    assert result.status == "partial_failure"
    assert run["status"] == "partial"
    assert run["records_fetched"] == 4
    assert run["records_normalized"] == 2
    assert run["records_processed"] == 1
    assert run["records_rejected"] == 1
    assert run["records_filtered"] == 1
    assert run["records_unmatched"] == 1


def test_collection_links_job_documents_to_provider_fetch_run(monkeypatch, tmp_path):
    from app.services import market_collection_service

    captured = []
    monkeypatch.setattr(
        market_collection_service,
        "store_collected_market_jobs",
        lambda postings, *, fetched_at, fetch_run_id=None: captured.append(
            (postings, fetched_at, fetch_run_id)
        ) or len(postings),
    )

    class Provider:
        name = "jsearch"

        async def fetch_market_postings(self, **kwargs):
            return [
                MarketPosting(
                    source="jsearch",
                    posting_id="posting-1",
                    provider_job_id="job-1",
                    title="Python developer",
                    source_url="https://jobs.example.test/1",
                )
            ]

    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[Provider()],
        fetch_run_store=MemoryFetchRunStore(),
        observation_store=MemoryObservationStore(),
    ))

    assert result.status == "success"
    assert len(captured) == 1
    postings, _, fetch_run_id = captured[0]
    assert postings[0].source_url == "https://jobs.example.test/1"
    assert fetch_run_id == result.providers[0].fetch_run_id


def test_collection_rejects_future_dated_provider_observations(tmp_path):
    future_observation = MarketObservation(
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime.now(timezone.utc) + timedelta(days=1),
        period=(datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m"),
        posting_id="future-job",
        value=1,
        unit="job_postings",
        history_type="platform_collected",
        data_origin="real",
    )
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()

    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[StubCollector("jsearch", observations=[future_observation])],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "error"
    assert result.observations_inserted == 0
    assert observation_store.records == {}
    assert next(iter(fetch_runs.records.values()))["status"] == "failed"


def test_collected_job_conversion_preserves_source_url_and_fetch_run(monkeypatch):
    from app.services import job_storage_service

    captured = []
    monkeypatch.setattr(
        job_storage_service,
        "store_jsearch_jobs",
        lambda jobs: captured.extend(jobs) or len(jobs),
    )
    posting = MarketPosting(
        source="adzuna",
        posting_id="posting-2",
        provider_job_id="job-2",
        source_url="https://jobs.example.test/2",
    )

    assert job_storage_service.store_collected_market_jobs(
        [posting],
        fetched_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        fetch_run_id="adzuna-run-2",
    ) == 1
    assert captured[0].source_url == "https://jobs.example.test/2"
    assert captured[0].fetch_run_id == "adzuna-run-2"


def test_github_failure_does_not_block_jsearch_and_adzuna(tmp_path):
    observations = [
        MarketObservation(id=f"{source}-observation", source=source, skill="Python", signal_type="demand", posting_id=f"{source}-1",
                          observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10", value=1,
                          unit="job_postings", history_type="platform_collected", data_origin="real")
        for source in ("jsearch", "adzuna")
    ]
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[
            StubCollector("github", error=RuntimeError("private token detail")),
            StubCollector("jsearch", observations=[observations[0]]),
            StubCollector("adzuna", observations=[observations[1]]),
        ],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "partial_failure"
    assert result.sources_succeeded == ["jsearch", "adzuna"]
    assert len(observation_store.records) == 2
    assert [run["status"] for run in fetch_runs.records.values()].count("failed") == 1
    assert "private token detail" not in str(fetch_runs.records)


def test_github_success_is_preserved_when_jsearch_fails(tmp_path):
    adoption = MarketObservation(
        source="github", skill="Python", signal_type="adoption", posting_id="topic:python",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10", value=250,
        unit="repositories",
        history_type="snapshot", data_origin="real", series_id="github:repository-topic:python:v1",
    )
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[
            StubCollector("jsearch", error=RuntimeError("upstream failure")),
            StubCollector("github", observations=[adoption]),
        ],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "partial_failure"
    assert result.sources_succeeded == ["github"]
    assert len(observation_store.records) == 1
    assert next(iter(observation_store.records.values())).signal_type == "adoption"


def test_collection_rejects_missing_provider_unit(tmp_path):
    observation = MarketObservation(
        source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="job-without-unit", value=1,
    )
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()

    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[StubCollector("jsearch", observations=[observation])],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "error"
    assert result.sources_failed == {"jsearch": "JSearch collection failed."}
    assert observation_store.records == {}
    assert next(iter(fetch_runs.records.values()))["status"] == "failed"


def test_observation_storage_failure_downgrades_provider_fetch_run(tmp_path):
    class FailingObservationStore:
        def insert_observations(self, observations, **kwargs):
            raise RuntimeError("private storage detail")

    observation = MarketObservation(
        source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="job-storage-failure", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    fetch_runs = MemoryFetchRunStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[StubCollector("jsearch", observations=[observation])],
        fetch_run_store=fetch_runs,
        observation_store=FailingObservationStore(),
    ))

    assert result.status == "error"
    assert result.sources_succeeded == []
    assert result.providers[0].status == "failed"
    assert result.providers[0].error_category == "storage"
    assert result.sources_failed["firestore_storage"] == "Market observations could not be stored in Firestore."
    assert next(iter(fetch_runs.records.values()))["status"] == "failed"
    assert "private storage detail" not in str(result.model_dump())


def test_multiple_provider_failures_complete_all_fetch_runs(tmp_path):
    fetch_runs = MemoryFetchRunStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[
            StubCollector("jsearch", error=RuntimeError("failure-a")),
            StubCollector("adzuna", error=RuntimeError("failure-b")),
            StubCollector("github", error=RuntimeError("failure-c")),
        ],
        fetch_run_store=fetch_runs,
        observation_store=MemoryObservationStore(),
    ))

    assert result.status == "error"
    assert set(result.sources_failed) == {"jsearch", "adzuna", "github"}
    assert len(fetch_runs.records) == 3
    assert {row["status"] for row in fetch_runs.records.values()} == {"failed"}


def test_rate_limit_retry_after_prevents_immediate_provider_retry(tmp_path):
    class Provider:
        name = "github"
        calls = 0

        async def collect_observations(self, **kwargs):
            self.calls += 1
            raise AssertionError("provider request should be held during cooldown")

    now = datetime.now(timezone.utc)
    fetch_runs = MemoryFetchRunStore()
    fetch_runs.records["prior"] = {
        "run_id": "prior", "source": "github", "status": "failed",
        "error_category": "rate_limit", "retry_after_seconds": "60",
        "started_at": now, "completed_at": now,
    }
    provider = Provider()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        store=MarketDataStore(tmp_path / "market.sqlite3"),
        providers=[provider],
        fetch_run_store=fetch_runs,
        observation_store=MemoryObservationStore(),
    ))

    current = [row for key, row in fetch_runs.records.items() if key != "prior"][0]
    assert provider.calls == 0
    assert result.status == "error"
    assert current["status"] == "failed"
    assert current["error_category"] == "rate_limit"
    assert int(current["retry_after_seconds"]) <= 60


@pytest.fixture
def clear_route_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_market_collection_http_route_is_not_exposed(clear_route_overrides):
    with TestClient(app) as client:
        response = client.post("/api/v1/market/collect", json={})

    assert response.status_code == 404


def test_collection_is_not_triggered_by_a_user_http_request(clear_route_overrides):
    with TestClient(app) as client:
        response = client.post("/api/v1/market/collect", json={})

    assert response.status_code == 404


def test_collection_http_route_does_not_invoke_collector(clear_route_overrides):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/market/collect",
            json={"location": "Chennai", "country": "IN"},
        )

    assert response.status_code == 404

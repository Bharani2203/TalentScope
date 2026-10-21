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


@pytest.fixture(autouse=True)
def prevent_job_firestore_writes(monkeypatch):
    """Collection unit tests never write collected postings to Firestore."""
    from app.services import market_collection_service
    monkeypatch.setattr(market_collection_service, "store_collected_market_jobs", lambda *args, **kwargs: 0)


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

    def get_observations(self, **kwargs):
        return list(self.records.values())


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


def test_collection_dry_run_validates_without_writing_any_persistence_surface(monkeypatch):
    from app.services.market_data.base import PostingFetchResult

    posting = MarketPosting(
        source="jsearch",
        posting_id="fixture-job-1",
        provider_job_id="fixture-job-1",
        title="Python developer",
        skills=["Python"],
    )

    class FixtureProvider:
        name = "jsearch"

        async def fetch_market_postings_with_stats(self, **kwargs):
            kwargs["archive_response"]({"fixture": True}, "application/json")
            return PostingFetchResult(postings=[posting], records_fetched=1)

    class WriteTrap:
        def start(self, *_args, **_kwargs):
            pytest.fail("dry run wrote a fetch-run record")

        def finish(self, *_args, **_kwargs):
            pytest.fail("dry run wrote a fetch-run completion")

        def insert_observations(self, *_args, **_kwargs):
            pytest.fail("dry run wrote observations")

        def archive(self, *_args, **_kwargs):
            pytest.fail("dry run archived a provider response")

    from app.services import market_collection_service

    monkeypatch.setattr(
        market_collection_service,
        "store_collected_market_jobs",
        lambda *_args, **_kwargs: pytest.fail("dry run stored job postings"),
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[FixtureProvider()],
        fetch_run_store=WriteTrap(),
        observation_store=WriteTrap(),
        raw_response_archive=WriteTrap(),
        dry_run=True,
    ))

    assert result.status == "dry_run"
    assert result.dry_run is True
    assert result.data_origin == "test"
    assert result.postings_validated == 1
    assert result.observations_validated == 1
    assert result.observations_inserted == 0
    assert result.providers[0].data_origin == "test"
    assert result.providers[0].observations_created == 0


def test_bounded_dry_run_selects_one_provider_and_passes_scope_without_writes():
    from app.services.market_data.base import PostingFetchResult

    calls = []

    class FixtureProvider:
        def __init__(self, name):
            self.name = name

        async def fetch_market_postings_with_stats(self, **kwargs):
            calls.append((self.name, kwargs))
            return PostingFetchResult(postings=[], records_fetched=0, zero_results_verified=True)

    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[FixtureProvider("jsearch"), FixtureProvider("adzuna")],
        provider_name="adzuna", query="software developer", result_limit=10,
        location="Chennai", country="in", dry_run=True,
    ))

    assert result.status == "dry_run"
    assert result.data_origin == "test"
    assert [name for name, _ in calls] == ["adzuna"]
    assert calls[0][1]["query"] == "software developer"
    assert calls[0][1]["result_limit"] == 10
    assert calls[0][1]["location"] == "Chennai"
    assert calls[0][1]["country"] == "in"
    assert result.observations_inserted == 0


def test_collection_reports_confirmed_posting_and_observation_persistence(monkeypatch):
    from app.services import market_collection_service

    posting = MarketPosting(
        source="adzuna", posting_id="adzuna:job-1", provider_job_id="job-1",
        title="Python developer", skills=["Python"],
    )

    class Provider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[posting], records_fetched=1, page_size_limit=10,
                provider_total_count=1, pagination_complete=True,
                sampling_frame="fixture bounded page",
            )

    monkeypatch.setattr(
        market_collection_service,
        "store_collected_market_jobs",
        lambda records, **kwargs: len(records),
    )
    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None), providers=[Provider()],
        provider_name="adzuna", result_limit=10, query="software developer",
        fetch_run_store=fetch_runs, observation_store=observation_store,
    ))

    assert result.status == "success"
    assert result.observation_storage_backend == "injected"
    assert result.postings_validated == 1
    assert result.postings_persisted_count == 1
    assert result.postings_readback_verified_count == 1
    assert result.postings_persistence_status == "confirmed"
    assert result.observations_validated == 1
    assert result.observations_persisted_count == 1
    assert result.observations_readback_verified_count == 1
    assert result.observations_persistence_status == "confirmed"
    assert result.providers[0].records_fetched == 1
    assert result.providers[0].records_validated == 1
    assert result.providers[0].postings_persisted_count == 1
    run = next(iter(fetch_runs.records.values()))
    assert run["observation_storage_backend"] == "injected"
    assert run["records_validated"] == run["records_persisted"] == 1
    assert run["records_persistence_status"] == "confirmed"
    assert run["collection_observations_inserted_count"] == 1
    assert run["collection_observations_persistence_status"] == "confirmed"


def test_duplicate_postings_are_counted_once_for_verified_persistence(monkeypatch):
    from app.services import market_collection_service

    posting = MarketPosting(
        source="adzuna", posting_id="duplicate-posting", provider_job_id="same-id",
        title="Python developer", skills=["Python"],
    )

    class Provider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[posting, posting], records_fetched=2,
                page_size_limit=10, pagination_complete=True,
                sampling_frame="fixture duplicate page",
            )

    monkeypatch.setattr(
        market_collection_service, "store_collected_market_jobs",
        lambda records, **kwargs: len({(item.source, item.provider_job_id or item.posting_id) for item in records}),
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None), providers=[Provider()],
        fetch_run_store=MemoryFetchRunStore(), observation_store=MemoryObservationStore(),
    ))

    assert result.status == "success"
    assert result.postings_validated == 2
    assert result.postings_duplicate_count == 1
    assert result.postings_persisted_count == 1
    assert result.postings_readback_verified_count == 1
    assert result.providers[0].records_duplicate == 1


def test_observation_write_without_readback_is_not_reported_as_persisted():
    class WriteOnlyObservationStore(MemoryObservationStore):
        def get_observations(self, **kwargs):
            return []

    observation = MarketObservation(
        source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="readback-missing", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[StubCollector("jsearch", observations=[observation])],
        fetch_run_store=MemoryFetchRunStore(),
        observation_store=WriteOnlyObservationStore(),
    ))

    assert result.status == "error"
    assert result.observations_persistence_status == "unknown"
    assert result.observations_persisted_count is None
    assert result.observations_readback_verified_count is None
    assert result.observations_persistence_unconfirmed_count == 1


def test_local_sqlite_collection_is_confirmed_only_after_targeted_readback(tmp_path):
    observation = MarketObservation(
        source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="sqlite-readback", value=7, unit="job_postings",
        location="India", scope="country", history_type="platform_collected",
        data_origin="real", series_id="jsearch:python:india:test",
    )
    store = MarketDataStore(tmp_path / "market-readback.sqlite3")

    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[StubCollector("jsearch", observations=[observation])],
        fetch_run_store=MemoryFetchRunStore(), observation_store=store,
    ))

    assert result.observation_storage_backend == "sqlite"
    assert result.observations_persistence_status == "confirmed"
    assert result.observations_readback_verified_count == 1
    stored = store.get_observations(
        skill="Python", cutoff=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert len(stored) == 1
    assert stored[0].posting_id == "sqlite-readback"


@pytest.mark.parametrize(
    "stored_override",
    [
        {"id": "different-stable-id"},
        {"value": 99.0},
    ],
    ids=["mismatched-id", "mismatched-payload-with-same-id"],
)
def test_observation_readback_rejects_wrong_id_or_payload(stored_override):
    from app.services.market_intelligence.persistence_verification import (
        PersistenceVerificationError,
        verify_observation_readback,
    )

    observation = MarketObservation(
        id="stable-observation-id", source="jsearch", skill="Python",
        signal_type="demand", observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10", posting_id="readback-integrity", value=1,
        unit="job_postings", location="India", scope="country",
        history_type="platform_collected", data_origin="real",
        series_id="jsearch:python:india:v1", query_id="jsearch-q1",
        panel_version="panel-v1",
    )

    class MismatchedStore:
        def get_observations(self, **kwargs):
            return [observation.model_copy(update=stored_override)]

    with pytest.raises(PersistenceVerificationError, match="read-back did not match"):
        verify_observation_readback(MismatchedStore(), [observation])


def test_offline_collection_to_authenticated_market_snapshot_answer(monkeypatch, tmp_path):
    import socket
    import httpx
    import firebase_admin
    from app.models.auth import AuthenticatedUser
    from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
    from app.models.intent_planner import IntelligencePlanRequest
    from app.services import market_collection_service
    from app.services.execution_orchestrator_service import ExecutionOrchestratorService
    from app.storage.conversation_store import ConversationStore
    from app.storage.mock_firestore_hub import MockFirestoreClient
    from app.core import firebase as firebase_module

    local_firestore = MockFirestoreClient()
    firestore_client_calls = []

    def injected_firestore_client():
        firestore_client_calls.append("mock")
        return local_firestore

    def reject_real_firebase(*args, **kwargs):
        pytest.fail("Real Firebase initialization/client construction attempted by offline test")

    monkeypatch.setattr(firebase_module, "get_firestore_client", injected_firestore_client)
    monkeypatch.setattr(firebase_module, "get_firebase_app", reject_real_firebase)
    monkeypatch.setattr(firebase_admin, "initialize_app", reject_real_firebase)
    monkeypatch.setattr(firebase_module.firestore, "client", reject_real_firebase)

    def reject_network(*args, **kwargs):
        pytest.fail("Network access attempted by offline collection-to-answer integration test")

    original_socket_connect = socket.socket.connect

    def reject_external_socket(sock, address):
        host = address[0].casefold() if isinstance(address, tuple) and address else ""
        if host in {"127.0.0.1", "::1", "localhost"}:
            return original_socket_connect(sock, address)
        pytest.fail("External socket connection attempted by offline collection-to-answer integration test")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_external_socket)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject_network)
    monkeypatch.setattr(httpx.Client, "request", reject_network)

    posting = MarketPosting(
        source="adzuna", posting_id="pipeline-posting-1", provider_job_id="pipeline-job-1",
        title="Python developer", company_name="Fixture employer", location="India",
        country="India", country_code="in", skills=["Python"],
        posted_at="2026-10-12T00:00:00Z",
    )

    class FixtureProvider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[posting], records_fetched=1, requested_page_count=1,
                page_size_limit=10, pagination_complete=True,
                sampling_frame="isolated offline fixture",
            )

    stored_postings = {}

    def persist_fixture_postings(records, *, fetch_run_id, **kwargs):
        for record in records:
            stored_postings[record.provider_job_id or record.posting_id] = record
        return len(stored_postings)

    monkeypatch.setattr(
        market_collection_service, "store_collected_market_jobs", persist_fixture_postings,
    )
    isolated_db = tmp_path / "market-answer-pipeline.sqlite3"
    observation_store = MarketDataStore(isolated_db)
    collection = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_read_backend="sqlite"),
        providers=[FixtureProvider()], fetch_run_store=MemoryFetchRunStore(), country="in",
        observation_store=observation_store,
    ))
    assert collection.status == "success"
    assert collection.postings_persisted_count == 1
    assert collection.observations_readback_verified_count == 1

    answer_service = ExecutionOrchestratorService(
        settings=Settings(_env_file=None, skill_intelligence_read_backend="sqlite"),
        db_path=isolated_db, market_store=observation_store,
        conversation_store=ConversationStore(),
    )
    persisted_observations = observation_store.get_observations()
    assert len(persisted_observations) == 1, persisted_observations
    pipeline_request = CoreIntelligenceAnswerRequest(
        message="Show a market snapshot for Python in India",
        portal_type="individual", domain="market", capability_id="market_snapshot",
        location="India", time_range="max",
    )
    pipeline_plan = answer_service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message=pipeline_request.message, portal_type=pipeline_request.portal_type,
            domain=pipeline_request.domain, capability_id=pipeline_request.capability_id,
            location=pipeline_request.location, time_range=pipeline_request.time_range,
        ),
    )
    pipeline_analysis = answer_service._shared_market_analysis(pipeline_request, pipeline_plan)
    assert pipeline_analysis.observations
    response = answer_service.answer(
        pipeline_request,
        authenticated_user=AuthenticatedUser(uid="offline-market-user", email="offline@example.test"),
    )

    assert response.execution_status == "completed", (
        response.plan_status, response.reason_codes, response.facts, response.capabilities_used,
    )
    assert response.planned_primary_capability == "market_snapshot"
    assert response.executed_primary_capability == "market_snapshot"
    snapshot = next(fact for fact in response.facts if fact.fact_type == "market_snapshot")
    assert snapshot.source == "adzuna"
    assert snapshot.metric_value == 1
    assert response.evidence
    assert response.evidence[0].evidence_id == snapshot.evidence_reference
    assert response.evidence[0].supporting_observation_ids
    assert response.evidence[0].fetch_run_id is not None
    assert firestore_client_calls
    assert local_firestore.collection("intelligence_conversations").records


def test_collection_reports_unconfirmed_job_write_as_unknown(monkeypatch):
    from app.services import market_collection_service

    posting = MarketPosting(
        source="adzuna", posting_id="adzuna:job-fail", provider_job_id="job-fail",
        title="Python developer", skills=["Python"],
    )

    class Provider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(postings=[posting], records_fetched=1)

    monkeypatch.setattr(
        market_collection_service,
        "store_collected_market_jobs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private storage detail")),
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None), providers=[Provider()],
        observation_store=MemoryObservationStore(), fetch_run_store=MemoryFetchRunStore(),
    ))

    assert result.status == "partial_failure"
    assert result.postings_validated == 1
    assert result.postings_persisted_count is None
    assert result.postings_persistence_status == "unknown"
    assert result.postings_persistence_unconfirmed_count == 1
    assert result.providers[0].postings_persisted_count is None
    assert result.providers[0].postings_persistence_status == "unknown"
    assert "job_persistence_unconfirmed" in result.providers[0].status_reasons
    assert "private storage detail" not in str(result.model_dump())


def test_cli_treats_partial_collection_as_nonzero_exit():
    from app.scripts.collect_market_data import _successful_exit
    from app.models.skill_intelligence import MarketCollectionResponse

    partial = MarketCollectionResponse(run_id="fixture-run", status="partial_failure")
    success = MarketCollectionResponse(run_id="fixture-run", status="success")

    assert _successful_exit(partial) is False
    assert _successful_exit(success) is True


def test_empty_dry_run_reports_pending_providers_without_storage():
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[],
        dry_run=True,
    ))

    assert result.status == "dry_run"
    assert result.dry_run is True
    assert result.data_origin == "test"
    assert result.observations_inserted == 0
    assert result.sources_pending


def test_sqlite_read_backend_receives_real_collection_observations(tmp_path):
    captured = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    observation = MarketObservation(
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=captured,
        period=captured.strftime("%Y-%m"),
        posting_id="sqlite-job-1",
        value=1,
        unit="job_postings",
        history_type="platform_collected",
        data_origin="real",
    )
    database = tmp_path / "local-market.sqlite3"
    store = MarketDataStore(database)
    settings = Settings(
        _env_file=None,
        skill_intelligence_db_path=str(database),
        skill_intelligence_read_backend="sqlite",
    )

    result = asyncio.run(collect_market_data(
        settings=settings,
        store=store,
        providers=[StubCollector("jsearch", observations=[observation])],
        fetch_run_store=MemoryFetchRunStore(),
    ))

    assert result.status == "success"
    assert result.observations_inserted == 1
    assert result.observation_storage_backend == "sqlite"
    assert result.observations_persisted_count == 1
    assert result.observations_persistence_status == "confirmed"
    stored = MarketDataStore(database, read_only=True).get_observations()
    assert len(stored) == 1
    assert stored[0].data_origin == "real"
    assert stored[0].fetch_run_id == result.providers[0].fetch_run_id


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
    assert run["records_with_recognized_skills"] == 1
    assert run["skill_posting_counts"] == {"python": 1}
    assert run["extractor_version"] == "skill-extractor-v1"


def test_valid_posting_without_registry_skills_is_counted_without_partial_failure(monkeypatch):
    class Provider:
        name = "jsearch"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[MarketPosting(
                    source="jsearch", posting_id="office-1", title="Office coordinator",
                    description="Scheduling and office support.",
                )],
                records_fetched=1,
                sampling_frame="fixture query, one page",
                pagination_complete=True,
            )

    runs = MemoryFetchRunStore()
    monkeypatch.setattr(
        "app.services.market_collection_service.store_collected_market_jobs",
        lambda postings, **kwargs: len(postings),
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[Provider()],
        fetch_run_store=runs,
        observation_store=MemoryObservationStore(),
    ))

    run = next(iter(runs.records.values()))
    assert result.status == "success"
    assert result.postings_validated == 1
    assert run["records_validated"] == 1
    assert run["records_with_recognized_skills"] == 0
    assert run["records_unmatched"] == 1
    assert run["skill_posting_counts"] == {}
    assert run["status"] == "success"


def test_extractor_version_change_creates_distinct_observation_series():
    from app.services.market_data.job_observations import observations_from_postings

    posting = MarketPosting(source="jsearch", posting_id="versioned-1", title="Python engineer")
    collected_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    first = observations_from_postings(
        [posting], location="Chennai", country="in", collected_at=collected_at,
        query_id="jsearch:fixture", panel_version="job-demand-v1", extractor_version="skill-extractor-v1",
    )[0]
    second = observations_from_postings(
        [posting], location="Chennai", country="in", collected_at=collected_at,
        query_id="jsearch:fixture", panel_version="job-demand-v1", extractor_version="skill-extractor-v2",
    )[0]

    assert first.id != second.id
    assert first.series_id != second.series_id
    assert first.extractor_version == "skill-extractor-v1"
    assert second.extractor_version == "skill-extractor-v2"


def test_query_panel_identity_includes_pagination_strategy():
    from app.services.market_collection_service import _query_id

    provider = type("Provider", (), {"name": "adzuna"})()
    first = _query_id(provider, "Chennai", "in", "Python related skills", result_limit=10)
    same = _query_id(provider, "Chennai", "in", "Python related skills", result_limit=10)
    changed_page_size = _query_id(provider, "Chennai", "in", "Python related skills", result_limit=20)
    changed_panel = _query_id(
        provider, "Chennai", "in", "Python related skills", result_limit=10,
        panel_version="job-demand-v2",
    )

    assert first == same
    assert first != changed_page_size
    assert first != changed_panel


def test_query_identity_includes_skill_registry_version(monkeypatch):
    import app.services.market_collection_service as collection

    provider = type("Provider", (), {"name": "adzuna"})()
    first = collection._query_id(provider, "Chennai", "in", "Python related skills", result_limit=10)
    monkeypatch.setattr(collection, "SKILL_REGISTRY_VERSION", "skill-registry-test-v2")
    changed_registry = collection._query_id(
        provider, "Chennai", "in", "Python related skills", result_limit=10,
    )
    assert first != changed_registry


def test_offline_fixture_collection_persists_and_repeats_idempotently(monkeypatch, tmp_path):
    from app.services.market_collection_service import OfflineFixtureProvider

    posting_ids = set()

    def persist_fixture_postings(postings, **kwargs):
        posting_ids.update(posting.posting_id for posting in postings)
        return len(postings)

    class MemoryArchive:
        def archive(self, **kwargs):
            return {"archive_reference": "test-fixture-only"}

    monkeypatch.setattr(
        "app.services.market_collection_service.store_collected_market_jobs",
        persist_fixture_postings,
    )
    database = tmp_path / "offline-collection.sqlite3"
    store = MarketDataStore(database)
    runs = MemoryFetchRunStore()
    settings_value = Settings(
        _env_file=None,
        skill_intelligence_read_backend="sqlite",
        market_collection_panel_version="fixture-panel-v7",
    )

    first = asyncio.run(collect_market_data(
        settings=settings_value,
        providers=[OfflineFixtureProvider("adzuna")],
        store=store,
        observation_store=store,
        fetch_run_store=runs,
        raw_response_archive=MemoryArchive(),
        country="in",
        query="Python related skills",
        result_limit=10,
    ))
    second = asyncio.run(collect_market_data(
        settings=settings_value,
        providers=[OfflineFixtureProvider("adzuna")],
        store=store,
        observation_store=store,
        fetch_run_store=runs,
        raw_response_archive=MemoryArchive(),
        country="in",
        query="Python related skills",
        result_limit=10,
    ))

    stored = store.get_observations()
    assert first.status == second.status == "success"
    assert first.observation_storage_backend == second.observation_storage_backend == "sqlite"
    assert first.postings_validated == second.postings_validated == 2
    assert first.observations_inserted > 0
    assert second.observations_inserted == 0
    assert len(stored) == first.observations_inserted
    assert len(posting_ids) == 2
    assert {item.extractor_version for item in stored} == {"skill-extractor-v1"}
    assert all(item.panel_version == "fixture-panel-v7" for item in stored)
    assert all(run["collection_schedule"] == settings_value.market_collection_cron for run in runs.records.values())
    assert len({run["query_id"] for run in runs.records.values()}) == 1
    assert {item.query_id for item in stored} == {run["query_id"] for run in runs.records.values()}
    assert all(item.period and item.observed_at for item in stored)
    assert all(run["records_validated"] == 2 for run in runs.records.values())
    assert all(run["records_with_recognized_skills"] == 2 for run in runs.records.values())
    assert all(run["skill_posting_counts"] for run in runs.records.values())
    assert all(run["status"] == "success" for run in runs.records.values())


def test_verified_zero_result_is_completed_and_records_sampling_context():
    class EmptyProvider:
        name = "jsearch"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[], records_fetched=0, zero_results_verified=True,
                sampling_frame="mock query, one page", requested_page_count=1,
                pagination_complete=True,
            )

    runs = MemoryFetchRunStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None),
        providers=[EmptyProvider()], fetch_run_store=runs,
        observation_store=MemoryObservationStore(),
    ))

    run = next(iter(runs.records.values()))
    assert result.status == "success"
    assert run["status"] == "success"
    assert run["lifecycle_state"] == "completed"
    assert run["coverage_status"] == "verified_zero"
    assert run["zero_results_verified"] is True
    assert run["requested_page_count"] == 1
    assert run["sampling_frame"] == "mock query, one page"
    assert run["geography"]["scope"] == "global"
    assert run["collection_window_start"].day == 1
    assert result.providers[0].lifecycle_state == "completed"
    assert result.providers[0].coverage_status == "verified_zero"


def test_incomplete_pagination_is_partial_and_observations_are_marked_incomplete():
    class LimitedProvider:
        name = "adzuna"

        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[MarketPosting(source="adzuna", posting_id="p-1", title="Python Engineer")],
                records_fetched=50, provider_total_count=90, page_size_limit=50,
                requested_page_count=1, pagination_complete=False,
                sampling_frame="first page only",
            )

    runs = MemoryFetchRunStore()
    observations = MemoryObservationStore()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None), providers=[LimitedProvider()],
        fetch_run_store=runs, observation_store=observations,
    ))

    run = next(iter(runs.records.values()))
    observation = next(iter(observations.records.values()))
    assert result.status == "partial_failure"
    assert run["lifecycle_state"] == "partial"
    assert run["coverage_status"] == "partial"
    assert run["provider_total_count"] == 90
    assert run["page_size_limit"] == 50
    assert observation.quality["collection_complete"] is False
    assert result.providers[0].lifecycle_state == "partial"
    assert "pagination_incomplete" in result.providers[0].status_reasons
    assert result.status_reasons == [
        "adzuna:posting_persistence_count_mismatch",
        "adzuna:pagination_incomplete",
    ]


def test_collection_status_exposes_partial_coverage_and_sampling_details():
    from app.services.market_collection_service import get_collection_status

    completed = datetime(2026, 10, 18, tzinfo=timezone.utc)

    class RunStore:
        def collection_summary(self):
            return {"last_collection": {"providers": {"adzuna": {
                "run_id": "mock-run", "source": "adzuna", "status": "partial",
                "lifecycle_state": "partial", "coverage_status": "partial",
                "started_at": completed, "completed_at": completed,
                "collection_window_start": datetime(2026, 10, 1, tzinfo=timezone.utc),
                "collection_window_end": completed,
                "geography": {"country": "in", "scope": "country"},
                "requested_page_count": 1, "page_size_limit": 50,
                "sampling_frame": "first page only",
            }}}}

    status = get_collection_status(
        fetch_run_store=RunStore(), settings=Settings(_env_file=None),
        observation_store=MemoryObservationStore(),
    )

    provider = next(item for item in status.providers if item.provider == "adzuna")
    assert status.overall_status == "partial_failure"
    assert provider.lifecycle_state == "partial"
    assert provider.coverage_status == "partial"
    assert provider.page_size_limit == 50
    assert provider.sampling_frame == "first page only"


def test_collection_and_provider_posting_timestamps_are_separate():
    from app.services.market_data.job_observations import observations_from_postings

    collected_at = datetime(2026, 10, 18, tzinfo=timezone.utc)
    posting = MarketPosting(
        source="jsearch", posting_id="timestamped", title="Python Engineer",
        posted_at="2026-10-02T12:30:00Z",
    )
    observation = observations_from_postings(
        [posting], location=None, country="in", collected_at=collected_at,
    )[0]
    assert observation.observed_at == collected_at
    assert observation.provider_posted_at == datetime(2026, 10, 2, 12, 30, tzinfo=timezone.utc)


def test_invalid_or_missing_provider_posting_time_does_not_replace_collection_time():
    from app.services.market_data.job_observations import observations_from_postings

    collected_at = datetime(2026, 10, 18, tzinfo=timezone.utc)
    for posted_at in (None, "not-a-timestamp"):
        observation = observations_from_postings(
            [MarketPosting(source="jsearch", posting_id=f"time-{posted_at}", title="Python Engineer", posted_at=posted_at)],
            location=None, country="in", collected_at=collected_at,
        )[0]
        assert observation.observed_at == collected_at
        assert observation.provider_posted_at is None


def test_market_observation_rejects_invalid_values_and_denominators():
    from pydantic import ValidationError

    fields = {
        "source": "jsearch", "skill": "Python", "signal_type": "demand",
        "observed_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "period": "2026-10", "value": 1, "unit": "job_postings",
    }
    with pytest.raises(ValidationError):
        MarketObservation(**{**fields, "value": float("nan")})
    with pytest.raises(ValidationError):
        MarketObservation(**{**fields, "denominator": 0})


def test_local_market_store_round_trips_provider_posting_time(tmp_path):
    store = MarketDataStore(tmp_path / "observations.sqlite3")
    observation = MarketObservation(
        source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 18, tzinfo=timezone.utc), period="2026-10",
        provider_posted_at=datetime(2026, 10, 2, 12, tzinfo=timezone.utc),
        posting_id="round-trip", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    assert store.insert_observations([observation]) == 1
    stored = store.get_observations()
    assert stored[0].provider_posted_at == observation.provider_posted_at


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
    posting_without_native_id = MarketPosting(
        source="jsearch",
        posting_id="stable-content-hash-1",
        title="Python developer",
    )

    assert job_storage_service.store_collected_market_jobs(
        [posting, posting_without_native_id],
        fetched_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        fetch_run_id="adzuna-run-2",
    ) == 2
    assert captured[0].source_url == "https://jobs.example.test/2"
    assert captured[0].fetch_run_id == "adzuna-run-2"
    # The monkeypatched store captures both normalized records; the first is
    # already asserted for provenance above, and the second uses its stable ID.
    assert len(captured) == 2
    assert captured[1].job_id == "stable-content-hash-1"


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
    assert result.sources_failed["injected_storage"] == (
        "Market observations could not be stored in injected observation store."
    )
    assert result.observation_storage_backend == "injected"
    assert result.observations_persisted_count is None
    assert result.observations_persistence_status == "unknown"
    assert result.observations_persistence_unconfirmed_count == 1
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

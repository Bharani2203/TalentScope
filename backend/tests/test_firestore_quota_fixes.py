from __future__ import annotations

from types import SimpleNamespace

from app.intelligence_v2 import source_registry
from app.services import execution_orchestrator_service, job_storage_service
from app.storage.conversation_store import ConversationStore
from app.storage.firestore_read_guard import read_guard


class Snapshot:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class Query:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.where_calls = []
        self.order_calls = []
        self.limit_value = None
        self.stream_calls = 0

    def where(self, *args, **kwargs):
        self.where_calls.append((args, kwargs))
        return self

    def order_by(self, *args, **kwargs):
        self.order_calls.append((args, kwargs))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def stream(self):
        self.stream_calls += 1
        return iter(self.rows[:self.limit_value] if self.limit_value else self.rows)


class FakeFirestore:
    def __init__(self, records=None):
        self.records = records or {}
        self.queries = {}

    def collection(self, name):
        query = self.queries.setdefault(name, Query(self.records.get(name, ())))
        return query


def test_read_logger_prints_only_when_enabled(monkeypatch, capsys):
    monkeypatch.setenv("FIRESTORE_READ_LOG", "1")
    with read_guard.track_request("/api/v1/market/jobs"):
        read_guard.record_read("jobs", 3)
        read_guard.record_read("jobs", 2)
        read_guard.record_read("fetch_runs", 1)
    enabled_output = capsys.readouterr().out
    assert enabled_output == (
        "firestore_request_reads route=/api/v1/market/jobs "
        "collection=fetch_runs,jobs documents_read=6\n"
    )

    monkeypatch.setenv("FIRESTORE_READ_LOG", "0")
    with read_guard.track_request("/api/v1/market/jobs"):
        read_guard.record_read("jobs", 4)
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("FIRESTORE_READ_LOG", "1")
    with read_guard.track_request("/api/v1/market/empty"):
        pass
    assert "route=/api/v1/market/empty collection=none documents_read=0" in capsys.readouterr().out


def test_failed_source_registry_stream_is_counted_as_read_attempt(monkeypatch, capsys):
    class FailingQuery(Query):
        def stream(self):
            raise RuntimeError("mocked stream failure")

    class FailingFirestore(FakeFirestore):
        def collection(self, name):
            return FailingQuery()

    monkeypatch.setenv("FIRESTORE_READ_LOG", "1")
    with read_guard.track_request("/api/v1/intelligence/guest/sources"):
        source_registry.V2SourceRegistry(client=FailingFirestore())
    output = capsys.readouterr().out
    assert "route=/api/v1/intelligence/guest/sources collection=skill_market_signals documents_read=1" in output


def test_source_registry_uses_shared_ttl_cache_and_invalidation():
    source_registry.invalidate_platform_counts_cache()
    client = FakeFirestore({
        "skill_market_signals": [Snapshot("s1", {"source": "jsearch"})],
        "jobs": [Snapshot("j1", {"source": "jsearch"})],
        "fetch_runs": [Snapshot("r1", {"source": "jsearch", "status": "success"})],
    })
    first = source_registry.V2SourceRegistry(client=client)
    second = source_registry.V2SourceRegistry(client=client)
    assert first._sources["jsearch"].observation_count == 1
    assert second._sources["jsearch"].job_posting_count == 1
    assert client.queries["skill_market_signals"].stream_calls == 1
    assert client.queries["jobs"].stream_calls == 1
    assert client.queries["fetch_runs"].stream_calls == 1

    source_registry.invalidate_platform_counts_cache()
    source_registry.V2SourceRegistry(client=client)
    assert client.queries["skill_market_signals"].stream_calls == 2


def test_conversation_list_limits_firestore_query(monkeypatch):
    client = FakeFirestore()
    monkeypatch.setattr("app.core.firebase.get_firestore_client", lambda: client)
    assert ConversationStore().list_conversations(user_id="u1", limit=7) == []
    query = client.queries["intelligence_conversations"]
    assert query.limit_value == 7
    assert query.order_calls == [(("updated_at",), {"direction": "DESCENDING"})]
    assert len(query.where_calls) == 1


def test_stored_job_search_limits_query_and_filters_country():
    client = FakeFirestore()
    assert job_storage_service.search_stored_jsearch_jobs(
        query="Python Developer", country="IN", firestore_client=client,
    ) == []
    query = client.queries["jobs"]
    assert query.limit_value == job_storage_service.STORED_JOB_SCAN_LIMIT == 300
    assert len(query.where_calls) == 1
    assert query.order_calls == [(("fetched_at",), {"direction": "DESCENDING"})]


def test_denominator_stats_are_loaded_once_per_service_request(monkeypatch):
    service = object.__new__(execution_orchestrator_service.ExecutionOrchestratorService)
    service._posting_sample_stats_loaded = False
    service._posting_sample_stats = {}
    service.firestore_store = SimpleNamespace(client=object())
    calls = []
    stats = {("jsearch", "2026-10", "country", "india"): {"recent": 2}}

    def fake_stats(*, firestore_client):
        calls.append(firestore_client)
        return stats

    monkeypatch.setattr(job_storage_service, "get_recent_posting_sample_stats", fake_stats)
    assert service._get_posting_sample_stats() == stats
    assert service._get_posting_sample_stats() == stats
    assert calls == [service.firestore_store.client]

"""Offline-only tests for the reviewed SQLite-to-Firestore Wikipedia handoff."""

from datetime import datetime, timezone

import pytest

from app.intelligence_v2.market_intelligence import V2MarketIntelligenceEngine
from app.scripts.load_wikipedia_pageviews import transfer_reviewed_wikipedia_sqlite_observations
from app.services.market_data.wikipedia_provider import WikipediaPageviewsProvider
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


class Snapshot:
    def __init__(self, document_id, value):
        self.id, self.value, self.exists = document_id, value, value is not None

    def to_dict(self):
        return self.value


class Query:
    def __init__(self, collection, filters=(), max_rows=None):
        self.collection, self.filters, self.max_rows = collection, list(filters), max_rows

    def where(self, *, filter):
        return Query(self.collection, (*self.filters, filter), self.max_rows)

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, value):
        return Query(self.collection, self.filters, value)

    def stream(self):
        records = list(self.collection.records.items())
        for field, operator, value in self.filters:
            if operator == "==":
                records = [(key, row) for key, row in records if row.get(field) == value]
            elif operator == ">=":
                records = [(key, row) for key, row in records if row.get(field) >= value]
        return [Snapshot(key, row) for key, row in records[: self.max_rows]]


class Document:
    def __init__(self, collection, key):
        self.collection, self.key = collection, key

    def get(self):
        return Snapshot(self.key, self.collection.records.get(self.key))

    def update(self, values):
        self.collection.records[self.key].update(values)


class Collection(Query):
    def __init__(self):
        self.records = {}
        super().__init__(self)

    def document(self, key):
        return Document(self, key)


class Batch:
    def __init__(self):
        self.writes = []

    def set(self, reference, payload):
        self.writes.append((reference, payload))

    def commit(self):
        for reference, payload in self.writes:
            reference.collection.records[reference.key] = dict(payload)


class MockFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


class FakeWikimediaService:
    endpoint = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"

    async def fetch_monthly_pageviews(self, article, start, end):
        end_month = int(end.split("-")[1]) if "-" in end else 4
        return [{"timestamp": f"2026{month:02d}0100", "views": 100 + month,
                 "project": "en.wikipedia", "access": "all-access", "agent": "user"}
                for month in range(1, end_month + 1)]

    def build_url(self, article, start, end):
        return self.endpoint


def _sqlite_store(
    path,
    *,
    include_duplicate=False,
    invalid_origin=None,
    missing_query_id=False,
    num_months=4,
    invalid_url=None,
    invalid_unit=None,
    invalid_scope=None,
    future_collection=False,
):
    store = MarketDataStore(path)
    end_month = f"2026-{num_months:02d}"
    observations = __import__("asyncio").run(
        WikipediaPageviewsProvider(FakeWikimediaService()).fetch_observations_for_skill(
            "python", "2026-01", end_month,
            now=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    )
    observations = [item.model_copy(update={
        "fetch_run_id": "fixture-wikipedia-run-2026-01",
        "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "metadata": {**item.metadata, "collection_timestamp_utc": "2026-05-01T00:00:00+00:00"},
    }) for item in observations]
    if invalid_origin:
        observations[0] = observations[0].model_copy(update={"data_origin": invalid_origin})
    if missing_query_id:
        observations[0] = observations[0].model_copy(update={"query_id": None})
    if invalid_url:
        observations[0] = observations[0].model_copy(update={"source_url": invalid_url})
    if invalid_unit:
        observations[0] = observations[0].model_copy(update={"unit": invalid_unit})
    if invalid_scope:
        observations[0] = observations[0].model_copy(update={"scope": invalid_scope})
    if future_collection:
        observations[0] = observations[0].model_copy(update={
            "metadata": {**observations[0].metadata, "collection_timestamp_utc": "2027-01-01T00:00:00+00:00"},
        })
    if include_duplicate:
        duplicate = observations[0].model_copy(update={"id": "second-id-same-month"})
        observations.append(duplicate)
    store.insert_observations(observations)
    return store


def _firestore(monkeypatch):
    monkeypatch.setattr("app.storage.firestore_observation_store.FieldFilter", lambda field, op, value: (field, op, value))
    db = MockFirestore()
    return db, FirestoreObservationStore(client=db, cache_ttl_seconds=0)


def test_reviewed_sqlite_rows_are_idempotent_and_readable_by_v2(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "market.sqlite3"
    _sqlite_store(sqlite_path)
    db, repository = _firestore(monkeypatch)

    first = transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
        skill="Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    second = transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
        skill="Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )

    assert first["status"] == "ready" and first["accepted_count"] == 4
    assert first["inserted_count"] == 4 and first["readback_verified"] is True
    assert second["inserted_count"] == 0
    assert len(db.collection("skill_market_signals").records) == 4
    engine = V2MarketIntelligenceEngine(
        store=ReferenceDataStore(tmp_path / "reference.sqlite3"), observation_store=repository,
    )
    result = engine.run_trend_velocity("Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "ready"
    assert result.facts[0].details["signal_type"] == "interest"
    assert result.facts[0].details["hiring_demand_included"] is False
    assert result.evidence[0].source == "Wikimedia Pageviews"
    assert result.evidence[0].query_id == "wikipedia:pageviews:python:2026-01:2026-04:v1"


def test_transfer_requires_approval_and_explicit_injected_store(tmp_path):
    sqlite_path = tmp_path / "market.sqlite3"
    _sqlite_store(sqlite_path)
    with pytest.raises(ValueError, match="review approval"):
        transfer_reviewed_wikipedia_sqlite_observations(
            database_path=sqlite_path, observation_store=object(), review_approved=False,
        )
    with pytest.raises(ValueError, match="explicitly injected"):
        transfer_reviewed_wikipedia_sqlite_observations(
            database_path=sqlite_path, observation_store=None, review_approved=True,
        )
    with pytest.raises(ValueError, match="explicit client"):
        transfer_reviewed_wikipedia_sqlite_observations(
            database_path=sqlite_path, observation_store=FirestoreObservationStore(client=None),
            review_approved=True,
        )


@pytest.mark.parametrize("kwargs", [
    {"include_duplicate": True},
    {"invalid_origin": "test"},
    {"missing_query_id": True},
    {"invalid_url": "https://attacker.evil.com/fake"},
    {"invalid_unit": "views"},
    {"invalid_scope": "country"},
    {"future_collection": True},
])
def test_transfer_rejects_duplicate_or_test_rows_without_writes(tmp_path, monkeypatch, kwargs):
    sqlite_path = tmp_path / "market.sqlite3"
    _sqlite_store(sqlite_path, **kwargs)
    db, repository = _firestore(monkeypatch)
    result = transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
        as_of=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    assert result["status"] == "rejected"
    assert result["accepted_count"] == 0
    assert db.collection("skill_market_signals").records == {}


def test_missing_sqlite_file_fails_without_creating_replacement(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError, match="Market database not found"):
        transfer_reviewed_wikipedia_sqlite_observations(
            database_path=missing, observation_store=object(), review_approved=True,
        )
    assert not missing.exists()


def test_empty_sqlite_history_is_not_reported_as_zero_or_ready(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "empty.sqlite3"
    MarketDataStore(sqlite_path)
    _, repository = _firestore(monkeypatch)
    result = transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
    )
    assert result["status"] == "no_data"
    assert result["accepted_count"] == result["inserted_count"] == 0


def test_transfer_requires_four_consecutive_completed_periods_for_trend_readiness(tmp_path, monkeypatch):
    """Part A: Verify that fewer than 4 periods leaves V2 trend readiness at insufficient_data."""
    sqlite_path = tmp_path / "market_3months.sqlite3"
    _sqlite_store(sqlite_path, num_months=3)
    db, repository = _firestore(monkeypatch)
    transfer = transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
        skill="Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    assert transfer["status"] == "ready" and transfer["accepted_count"] == 3
    engine = V2MarketIntelligenceEngine(
        store=ReferenceDataStore(tmp_path / "reference.sqlite3"), observation_store=repository,
    )
    result = engine.run_trend_velocity("Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "insufficient_data"
    assert "consecutive completed periods" in result.headline.lower() or "insufficient" in result.headline.lower()


def test_public_signals_isolated_from_hiring_demand(tmp_path, monkeypatch):
    """Part A: Verify that Wikipedia pageviews is isolated from hiring demand."""
    sqlite_path = tmp_path / "market_wiki.sqlite3"
    _sqlite_store(sqlite_path, num_months=4)
    db, repository = _firestore(monkeypatch)
    transfer_reviewed_wikipedia_sqlite_observations(
        database_path=sqlite_path, observation_store=repository, review_approved=True,
        skill="Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    engine = V2MarketIntelligenceEngine(
        store=ReferenceDataStore(tmp_path / "reference.sqlite3"), observation_store=repository,
    )
    result = engine.run_trend_velocity("Python", as_of=datetime(2026, 5, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "ready"
    assert result.facts[0].details["hiring_demand_included"] is False
    assert result.facts[0].details["signal_type"] == "interest"
    assert result.facts[0].unit in {"pageviews", "pageviews per month"}


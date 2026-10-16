from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.analytics.freshness import assess_freshness
from app.models.skill_intelligence import MarketObservation
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore
from app.storage.observation_identity import stable_observation_id


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return self.value


class Document:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def get(self):
        return Snapshot(self.collection.records.get(self.document_id))

    def update(self, values):
        self.collection.records[self.document_id].update(values)


class Collection:
    def __init__(self):
        self.records = {}

    def document(self, document_id):
        return Document(self, document_id)

    def stream(self):
        return [Snapshot(value) for value in self.records.values()]


class Batch:
    def __init__(self):
        self.operations = []

    def set(self, reference, payload):
        self.operations.append((reference, payload))

    def commit(self):
        for reference, payload in self.operations:
            reference.collection.records[reference.document_id] = dict(payload)


class Database:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


def test_firestore_observation_document_preserves_contract_and_registry_id():
    observed_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        id="stable-observation-id",
        source="JSearch",
        skill="JS",
        signal_type="demand",
        observed_at=observed_at,
        period="2026-10",
        scope="city",
        location="Chennai",
        posting_id="job-1",
        value=1,
        metadata={"title": "Python and JS engineer"},
    )

    document_id, data = FirestoreObservationStore.document_for(observation)

    assert document_id == "stable-observation-id"
    assert data["observation_id"] == document_id
    assert data["source"] == "jsearch"
    assert data["signal_type"] == "demand"
    assert data["skill"] == "JavaScript"
    assert data["skill_id"] == "javascript"
    assert data["period"] == "2026-10"
    assert data["location"] == "Chennai"
    assert data["scope"] == "city"
    assert data["value"] == 1
    assert data["unit"] is None
    assert data["denominator_unit"] is None
    assert data["source_url"] is None
    assert data["posting_id"] == "job-1"
    assert data["metadata"] == {"title": "Python and JS engineer"}
    assert data["history_type"] == "platform_collected"
    assert data["panel_version"] is None
    assert data["query_id"] is None
    assert data["series_id"] is None
    assert data["denominator"] is None
    assert data["extractor_version"] is None
    assert data["annotations"] == []
    assert data["quality"] is None
    assert data["confidence"] is None
    assert data["observation_count"] == 1
    assert data["created_at"] is not None


def test_observation_identity_and_firestore_document_canonicalize_aliases():
    observed_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    alias = MarketObservation(
        source="jsearch",
        skill="JS",
        signal_type="demand",
        observed_at=observed_at,
        period="2026-10",
        posting_id="job-alias",
        value=1,
        unit="job_postings",
        denominator_unit="job_postings",
        source_url="https://jobs.example.test/1",
        skill_id="not-the-canonical-id",
    )
    canonical = alias.model_copy(update={"skill": "JavaScript"})

    assert alias.skill == "JavaScript"
    assert alias.skill_id == "javascript"
    assert stable_observation_id(alias) == stable_observation_id(canonical)
    _, document = FirestoreObservationStore.document_for(alias)
    assert document["skill"] == "JavaScript"
    assert document["skill_id"] == "javascript"
    assert document["unit"] == "job_postings"
    assert document["denominator_unit"] == "job_postings"
    assert document["source_url"] == "https://jobs.example.test/1"


def test_sqlite_observation_store_round_trips_unit_and_source_url(tmp_path):
    store = MarketDataStore(tmp_path / "observations.sqlite3")
    observation = MarketObservation(
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="job-with-evidence",
        value=1,
        unit="job_postings",
        denominator_unit="job_postings",
        source_url="https://jobs.example.test/python",
    )

    assert store.insert_observations([observation]) == 1
    [restored] = store.get_observations()

    assert restored.unit == "job_postings"
    assert restored.denominator_unit == "job_postings"
    assert restored.source_url == "https://jobs.example.test/python"


@pytest.mark.parametrize(
    "overrides",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": -1},
        {"denominator": 0},
        {"denominator": -1},
        {"observation_count": -1},
        {"period": "2026-09"},
    ],
)
def test_observation_rejects_invalid_numeric_or_period_contract(overrides):
    fields = {
        "source": "test-provider",
        "skill": "Python",
        "signal_type": "demand",
        "observed_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "period": "2026-10",
        "value": 1,
    }
    fields.update(overrides)

    with pytest.raises(ValidationError):
        MarketObservation(**fields)


def test_firestore_document_preserves_non_demand_series_and_quality_fields():
    observation = MarketObservation(
        source="github", skill="Python", signal_type="adoption",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="topic:python", value=924083, history_type="snapshot",
        series_id="github:repository-topic:python:v1", observation_count=924083,
        quality={"metric": "topic search count"}, denominator=None,
    )

    _, document = FirestoreObservationStore.document_for(
        observation, query_id="github:topic:python", panel_version="github-adoption-v1",
    )

    assert document["history_type"] == "snapshot"
    assert document["series_id"] == "github:repository-topic:python:v1"
    assert document["query_id"] == "github:topic:python"
    assert document["panel_version"] == "github-adoption-v1"
    assert document["observation_count"] == 924083
    assert document["quality"] == {"metric": "topic search count"}
    assert document["denominator"] is None


@pytest.mark.parametrize("origin", ["real", "demo"])
def test_firestore_observation_serializes_explicit_data_origin(origin):
    observation = MarketObservation(
        source="test-provider", skill="Python", signal_type="demand",
        history_type="static_dataset", data_origin=origin,
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10", posting_id="known-origin", value=1,
    )

    _, document = FirestoreObservationStore.document_for(observation)

    assert document["data_origin"] == origin
    assert document["history_type"] == "static_dataset"


def test_observation_rejects_unrecognized_origin_and_history_type():
    fields = {
        "source": "test-provider", "skill": "Python", "signal_type": "demand",
        "observed_at": datetime(2026, 10, 5, tzinfo=timezone.utc), "value": 1,
    }
    with pytest.raises(ValidationError):
        MarketObservation(**fields, data_origin="generated")
    with pytest.raises(ValidationError):
        MarketObservation(**fields, history_type="current")


def test_firestore_observation_write_is_idempotent():
    database = Database()
    store = FirestoreObservationStore(database)
    observation = MarketObservation(
        id="stable-observation-id",
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="job-1",
        value=1,
    )

    assert store.insert_observations([observation]) == 1
    stored = store.all_documents()
    assert store.insert_observations([observation]) == 0

    assert len(store.all_documents()) == 1
    assert store.all_documents()[0]["observation_id"] == stored[0]["observation_id"]
    assert store.all_documents()[0]["created_at"] == stored[0]["created_at"]


def test_firestore_store_deduplicates_repeated_ids_within_a_batch():
    database = Database()
    store = FirestoreObservationStore(database)
    observation = MarketObservation(
        id="same-id",
        source="adzuna",
        skill="Go",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="job-2",
        value=1,
    )

    assert store.insert_observations([observation, observation]) == 1
    assert len(store.all_documents()) == 1


def test_firestore_store_rejects_conflicting_duplicates_in_one_batch():
    store = FirestoreObservationStore(Database())
    observed_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    first = MarketObservation(
        source="jsearch",
        skill="JS",
        signal_type="demand",
        observed_at=observed_at,
        period="2026-10",
        posting_id="same-posting",
        value=1,
    )
    conflicting = first.model_copy(update={"skill": "JavaScript", "value": 2})

    with pytest.raises(ValueError, match="Conflicting observation data"):
        store.insert_observations([first, conflicting])


def test_firestore_store_preserves_known_collection_provenance():
    database = Database()
    store = FirestoreObservationStore(database)
    observation = MarketObservation(
        id="provenance-id",
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="job-3",
        value=1,
    )

    store.insert_observations(
        [observation],
        provenance_by_observation_id={
            "provenance-id": {
                "query_id": "jsearch:abc123", "panel_version": "job-demand-v1",
                "fetch_run_id": "run-123",
            }
        },
    )

    document = store.all_documents()[0]
    assert document["query_id"] == "jsearch:abc123"
    assert document["panel_version"] == "job-demand-v1"
    assert document["fetch_run_id"] == "run-123"


def test_existing_legacy_observation_does_not_receive_inferred_origin_or_run_id():
    database = Database()
    store = FirestoreObservationStore(database)
    observation = MarketObservation(
        id="legacy-no-provenance", source="jsearch", skill="Python", signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="legacy-job", value=1,
    )
    store.insert_observations([observation])
    document = store.all_documents()[0]
    document.pop("data_origin", None)
    document.pop("fetch_run_id", None)
    store._collection().records["legacy-no-provenance"] = document

    store.insert_observations(
        [observation.model_copy(update={"data_origin": "real"})],
        provenance_by_observation_id={
            "legacy-no-provenance": {"fetch_run_id": "new-run", "query_id": "jsearch:q"}
        },
    )

    persisted = store.all_documents()[0]
    assert "data_origin" not in persisted
    assert "fetch_run_id" not in persisted


def test_firestore_store_rejects_conflicting_data_for_a_stable_id():
    database = Database()
    store = FirestoreObservationStore(database)
    first = MarketObservation(
        id="collision-id",
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="job-4",
        value=1,
    )
    conflicting = first.model_copy(update={"skill": "Java"})
    store.insert_observations([first])

    with pytest.raises(ValueError, match="Conflicting observation data"):
        store.insert_observations([conflicting])


def test_legacy_skill_fallback_preserves_all_requested_filters(monkeypatch):
    import app.storage.firestore_observation_store as observation_store_module

    matching = {
        "observation_id": "matching-document",
        "source": "jsearch",
        "signal_type": "demand",
        "observed_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "period": "2026-10",
        "location": "Chennai",
        "scope": "city",
        "skill": "Python",
        "skill_id": "python",
        "value": 1,
        "series_id": "jsearch:python:v1",
    }
    legacy_alias = {**matching, "observation_id": "legacy-document", "skill": "PYTHON", "skill_id": None}
    other_location = {**matching, "location": "Mumbai"}
    other_source = {**matching, "source": "adzuna"}

    class Query:
        def __init__(self, rows):
            self.rows = rows
            self.filters = []

        def where(self, *, filter):
            assert filter[0] in {"skill_id", "skill"}
            self.filters.append(filter)
            return self

        def order_by(self, _field, *, direction):
            raise AssertionError("Targeted skill reads must not require a composite index.")

        def limit(self, limit):
            assert limit == 2001
            return self

        def stream(self):
            return [Snapshot(row) for row in self.rows]

    class FallbackCollection:
        def __init__(self):
            self.targeted_queries = []

        def where(self, *, filter):
            field_name = filter[0]
            assert field_name in {"skill_id", "skill"}
            if field_name == "skill_id":
                query = Query([matching])
            else:
                assert filter[1] == "in"
                assert "Python" in filter[2]
                query = Query([matching, legacy_alias, other_location, other_source])
            self.targeted_queries.append(query)
            return query.where(filter=filter)

    class FallbackFirestore:
        def __init__(self):
            self.collection_value = FallbackCollection()

        def collection(self, name):
            assert name == "skill_market_signals"
            return self.collection_value

    monkeypatch.setattr(
        observation_store_module,
        "FieldFilter",
        lambda field, operator, value: (field, operator, value),
    )
    client = FallbackFirestore()
    store = FirestoreObservationStore(client)

    rows = store.get_observations(
        cutoff=datetime(2026, 10, 1, tzinfo=timezone.utc),
        skill="Python",
        location="Chennai",
        scope="city",
        source="jsearch",
        signal_type="demand",
        period="2026-10",
    )

    assert {row.id for row in rows} == {"matching-document", "legacy-document"}
    assert all(row.location == "Chennai" for row in rows)
    assert all(query.filters for query in client.collection_value.targeted_queries)


def test_period_snapshot_retry_keeps_stable_id_when_measurement_is_refetched():
    store = FirestoreObservationStore(Database())
    first = MarketObservation(
        source="github", skill="Python", signal_type="adoption",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="topic:python", value=120, history_type="snapshot",
        series_id="github:repository-topic:python:v1",
    )
    retry = first.model_copy(update={
        "observed_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
        "value": 124,
    })

    assert store.insert_observations([first]) == 1
    assert store.insert_observations([retry]) == 0
    documents = store.all_documents()
    assert len(documents) == 1
    assert documents[0]["value"] == 120


def test_existing_legacy_signal_row_is_enriched_without_duplicate_or_value_change():
    database = Database()
    store = FirestoreObservationStore(database)
    first = MarketObservation(
        source="github", skill="Python", signal_type="adoption",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc), period="2026-10",
        posting_id="topic:python", value=924083,
    )
    store.insert_observations([first])
    doc_id = store.all_documents()[0]["observation_id"]
    database.collection("skill_market_signals").records[doc_id].update({
        "history_type": "observed_signal", "series_id": None, "observation_count": 1,
    })
    corrected = first.model_copy(update={
        "history_type": "snapshot",
        "series_id": "github:repository-topic:python:v1",
        "observation_count": 924083,
        "quality": {"metric": "topic search count"},
    })

    assert store.insert_observations([corrected]) == 0
    document = store.all_documents()[0]
    assert len(store.all_documents()) == 1
    assert document["value"] == 924083
    assert document["history_type"] == "snapshot"
    assert document["series_id"] == "github:repository-topic:python:v1"
    assert document["observation_count"] == 924083


def test_existing_observation_with_noncanonical_skill_id_is_repaired():
    database = Database()
    store = FirestoreObservationStore(database)
    observation = MarketObservation(
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        period="2026-10",
        posting_id="legacy-python",
        value=1,
    )
    store.insert_observations([observation])
    doc_id = store.all_documents()[0]["observation_id"]
    database.collection("skill_market_signals").records[doc_id]["skill_id"] = "skill:python"

    assert store.insert_observations([observation]) == 0
    assert store.all_documents()[0]["skill_id"] == "python"


def test_legacy_github_snapshot_keeps_unknown_collection_provenance():
    class LegacySnapshot:
        id = "legacy-github-python"

        def to_dict(self):
            return {
                "observation_id": self.id,
                "source": "github",
                "signal_type": "adoption",
                "history_type": "snapshot",
                "skill": "Python",
                "observed_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
                "period": "2026-10",
                "scope": "global",
                "value": 123,
                "posting_id": "topic:python",
            }

    class LegacyQuery:
        def where(self, **_kwargs):
            return self

        def order_by(self, _field, *, direction):
            assert direction == "DESCENDING"
            return self

        def limit(self, limit):
            assert limit == 2001
            return self

        def stream(self):
            return [LegacySnapshot()]

    class LegacyCollection:
        def where(self, **kwargs):
            return LegacyQuery()

    class LegacyFirestore:
        def collection(self, name):
            assert name == "skill_market_signals"
            return LegacyCollection()

    store = FirestoreObservationStore(LegacyFirestore())
    rows = store.get_observations(cutoff=datetime(2026, 10, 1, tzinfo=timezone.utc))

    assert len(rows) == 1
    assert rows[0].id == "legacy-github-python"
    assert rows[0].source == "github"
    assert rows[0].signal_type == "adoption"
    assert rows[0].history_type == "snapshot"
    assert rows[0].data_origin is None
    assert rows[0].created_at is None
    assert rows[0].fetch_run_id is None
    assert assess_freshness(rows, now=datetime(2026, 10, 6, tzinfo=timezone.utc)).state == "building"


def test_observation_query_marks_limit_truncation_and_preserves_it_in_cache(monkeypatch):
    import app.storage.firestore_observation_store as observation_store_module

    monkeypatch.setattr(
        observation_store_module,
        "FieldFilter",
        lambda field, operator, value: (field, operator, value),
    )

    class Query:
        def __init__(self):
            self.limit_value = None
            self.rows = [
                {
                    "observation_id": f"unlisted-{index}",
                    "source": "jsearch",
                    "signal_type": "demand",
                    "observed_at": datetime(2020 + index // 12, index % 12 + 1, 1, tzinfo=timezone.utc),
                    "period": f"{2020 + index // 12}-{index % 12 + 1:02d}",
                    "location": "Global",
                    "scope": "global",
                    "skill": "UnlistedFramework",
                    "value": index + 1,
                    "unit": "job_postings",
                    "data_origin": "real",
                    "history_type": "platform_collected",
                }
                for index in range(2001)
            ]

        def where(self, *, filter):
            assert filter == ("skill", "==", "UnlistedFramework")
            return self

        def order_by(self, field, *, direction):
            raise AssertionError("Targeted skill reads must not require a composite index.")

        def limit(self, limit):
            self.limit_value = limit
            return self

        def stream(self):
            assert self.limit_value == 2001
            return [Snapshot(row) for row in self.rows]

    class QueryCollection:
        def __init__(self):
            self.query = Query()

        def where(self, *, filter):
            return self.query.where(filter=filter)

    class QueryFirestore:
        def __init__(self):
            self.collection_instance = QueryCollection()

        def collection(self, name):
            assert name == "skill_market_signals"
            return self.collection_instance

    store = FirestoreObservationStore(QueryFirestore())
    cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)
    first = store.get_observations(cutoff=cutoff, skill="UnlistedFramework")
    cached = store.get_observations(cutoff=cutoff, skill="UnlistedFramework")

    assert len(first) == 2000
    assert first.truncated is True
    assert cached.truncated is True
    assert first[0].observed_at >= cutoff

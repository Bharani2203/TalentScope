import asyncio
from datetime import datetime, timezone

from app.analytics.skill_registry import canonical_skill_id, extract_skills, source_mapping
from app.analytics.skill_normalization import normalize_skill
from app.core.config import Settings
from app.models.skill_intelligence import MarketObservation
from app.services.market_collection_service import collect_market_data
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore


class MemoryDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def create(self, data):
        if self.document_id in self.collection.records:
            raise ValueError("already exists")
        self.collection.records[self.document_id] = dict(data)

    def update(self, data):
        self.collection.records[self.document_id].update(data)


class MemoryCollection:
    def __init__(self):
        self.records = {}

    def document(self, document_id):
        return MemoryDocument(self, document_id)

    def stream(self):
        return [MemorySnapshot(value) for value in self.records.values()]


class MemoryFirestore:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, MemoryCollection())

    def batch(self):
        return MemoryBatch()


class MemorySnapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return self.value


class MemoryBatch:
    def __init__(self):
        self.operations = []

    def set(self, reference, data):
        self.operations.append((reference, data))

    def commit(self):
        for reference, data in self.operations:
            reference.collection.records[reference.document_id] = dict(data)


def _add_memory_get(collection):
    original_document = collection.document

    def document(document_id):
        ref = original_document(document_id)
        ref.get = lambda: MemorySnapshot(collection.records.get(document_id))
        return ref

    collection.document = document


class StubCollector:
    def __init__(self, name, observations=None, error=None):
        self.name = name
        self.observations = observations or []
        self.error = error

    async def collect_observations(self, **kwargs):
        if self.error:
            raise self.error
        return self.observations


def test_skill_alias_normalization_uses_registry():
    assert normalize_skill(" JS ") == "JavaScript"
    assert normalize_skill("Golang") == "Go"
    assert normalize_skill("Spring Boot") == "Spring"


def test_extraction_observes_word_boundaries():
    assert extract_skills("JavaScript and NodeJS, not Javax or NoSQL") == ["JavaScript", "Node.js"]


def test_ambiguous_skill_terms_need_language_context():
    assert extract_skills("We can go to the office in spring; R and C are short tokens.") == []
    assert extract_skills("Go programming, RStudio, C language, Spring Boot") == ["C", "Go", "R", "Spring"]


def test_registry_exposes_canonical_ids():
    assert canonical_skill_id("JS") == "javascript"
    assert canonical_skill_id("Go") == "go"
    assert canonical_skill_id("Spring Boot") == "spring_framework"
    assert canonical_skill_id("unregistered term") is None


def test_provider_specific_topic_and_tag_mapping():
    assert source_mapping("github", "golang").skill_id == "go"
    assert source_mapping("stack_exchange", "spring-boot").skill_id == "spring_framework"
    assert source_mapping("github", "unknown-topic") is None


def test_firestore_fetch_run_success_has_required_fields_and_unique_id(tmp_path):
    database = MemoryFirestore()
    run_store = FirestoreFetchRunStore(database)
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="jsearch", posting_id="job-1", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3")),
        store=MarketDataStore(tmp_path / "m.sqlite3"),
        providers=[StubCollector("jsearch", [observation])],
        fetch_run_store=run_store,
        observation_store=FirestoreObservationStore(_observation_database(database)),
    ))

    assert result.status == "success"
    records = database.collection("fetch_runs").records
    assert len(records) == 1
    run_id, record = next(iter(records.items()))
    assert run_id == record["run_id"]
    assert record["source"] == "jsearch"
    assert record["query_id"].startswith("jsearch:")
    assert record["panel_version"] == "job-demand-v1"
    assert record["started_at"] and record["completed_at"]
    assert record["status"] == "success"
    assert record["records_fetched"] == record["records_processed"] == 1
    assert record["records_rejected"] == 0
    assert record["error"] is None
    assert record["coverage_status"] == "complete"


def test_fetch_run_start_failure_does_not_fetch_or_report_success(tmp_path):
    database = MemoryFirestore()
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="jsearch", posting_id="job-untracked", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )

    class FailingRunStore:
        def start(self, _run_id, _record):
            raise RuntimeError("run record is unavailable")

        def finish(self, *_args):
            raise AssertionError("cannot finish an unstarted run")

        def collection_summary(self):
            return {}

    class TrackingCollector(StubCollector):
        called = False

        async def collect_observations(self, **kwargs):
            self.called = True
            return await super().collect_observations(**kwargs)

    provider = TrackingCollector("jsearch", [observation])
    observation_store = FirestoreObservationStore(_observation_database(database))
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3")),
        store=MarketDataStore(tmp_path / "m.sqlite3"),
        providers=[provider],
        fetch_run_store=FailingRunStore(),
        observation_store=observation_store,
    ))

    assert result.status == "error"
    assert result.sources_succeeded == []
    assert result.providers[0].status == "failed"
    assert result.providers[0].error_category == "storage"
    assert not provider.called
    assert observation_store.all_documents() == []


def test_fetch_run_finish_failure_reports_partial_collection(tmp_path):
    database = MemoryFirestore()
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="jsearch", posting_id="job-unreported", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )

    class FailingFinishRunStore:
        def start(self, _run_id, _record):
            return None

        def finish(self, _run_id, _record):
            raise RuntimeError("run completion is unavailable")

        def collection_summary(self):
            return {}

    observation_store = FirestoreObservationStore(_observation_database(database))
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3")),
        store=MarketDataStore(tmp_path / "m.sqlite3"),
        providers=[StubCollector("jsearch", [observation])],
        fetch_run_store=FailingFinishRunStore(),
        observation_store=observation_store,
    ))

    assert result.status == "partial_failure"
    assert result.observations_inserted == 1
    assert result.providers[0].status == "partial"
    assert result.providers[0].error_category == "storage"
    assert result.sources_failed == {
        "jsearch_fetch_run": "Fetch-run completion could not be recorded."
    }


def test_failed_provider_logs_safe_error_and_does_not_block_next_provider(tmp_path):
    database = MemoryFirestore()
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="adzuna", posting_id="job-2", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3")),
        store=MarketDataStore(tmp_path / "m.sqlite3"),
        providers=[
            StubCollector("jsearch", error=RuntimeError("credential=very-secret-token")),
            StubCollector("adzuna", [observation]),
        ],
        fetch_run_store=FirestoreFetchRunStore(database),
        observation_store=FirestoreObservationStore(_observation_database(database)),
    ))

    records = list(database.collection("fetch_runs").records.values())
    failed = next(record for record in records if record["source"] == "jsearch")
    assert result.status == "partial_failure"
    assert failed["status"] == "failed"
    assert failed["coverage_status"] == "unavailable"
    assert failed["completed_at"] is not None
    assert "very-secret-token" not in str(records)
    assert len(result.sources_succeeded) == 1


def test_retry_creates_new_run_ids_without_duplicate_observations(tmp_path):
    database = MemoryFirestore()
    store = MarketDataStore(tmp_path / "m.sqlite3")
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="jsearch", posting_id="stable-job", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", location="Chennai", scope="city", value=1,
        unit="job_postings", history_type="platform_collected", data_origin="real",
    )
    provider = [StubCollector("jsearch", [observation])]
    run_store = FirestoreFetchRunStore(database)
    settings = Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3"))

    observation_database = _observation_database(database)
    observation_store = FirestoreObservationStore(observation_database)
    first = asyncio.run(collect_market_data(settings=settings, store=store, providers=provider, fetch_run_store=run_store, observation_store=observation_store))
    second = asyncio.run(collect_market_data(settings=settings, store=store, providers=provider, fetch_run_store=run_store, observation_store=observation_store))

    runs = database.collection("fetch_runs").records
    assert first.observations_inserted == 1
    assert second.observations_inserted == 0
    assert len(runs) == 2
    assert len({record["run_id"] for record in runs.values()}) == 2
    assert len(observation_store.all_documents()) == 1
    assert len(observation_store.all_documents()) == 1


def test_adzuna_credentials_never_enter_fetch_run_documents(tmp_path):
    database = MemoryFirestore()
    captured = datetime(2026, 10, 5, tzinfo=timezone.utc)
    observation = MarketObservation(
        source="adzuna", posting_id="ad-job", skill="Python", signal_type="demand",
        observed_at=captured, period="2026-10", value=1, unit="job_postings",
        history_type="platform_collected", data_origin="real",
    )
    asyncio.run(collect_market_data(
        settings=Settings(_env_file=None, skill_intelligence_db_path=str(tmp_path / "m.sqlite3")),
        store=MarketDataStore(tmp_path / "m.sqlite3"),
        providers=[StubCollector("adzuna", [observation])],
        fetch_run_store=FirestoreFetchRunStore(database),
        observation_store=FirestoreObservationStore(_observation_database(database)),
    ))
    assert "credential" not in str(database.collection("fetch_runs").records).casefold()
    assert "api_key" not in str(database.collection("fetch_runs").records).casefold()


def _observation_database(database):
    """Add the generic Firestore document/batch methods used by observation storage."""
    collection = database.collection("skill_market_signals")
    _add_memory_get(collection)
    return database

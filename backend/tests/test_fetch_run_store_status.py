from datetime import datetime, timezone

from app.storage.fetch_run_store import FirestoreFetchRunStore


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return self.value


class Query:
    def __init__(self, records):
        self.records = records
        self.maximum = None

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, amount):
        self.maximum = amount
        return self

    def stream(self):
        ordered = sorted(
            self.records.values(), key=lambda row: row["started_at"], reverse=True,
        )
        return [Snapshot(row) for row in ordered[:self.maximum]]


class Database:
    def __init__(self, records):
        self.records = records

    def collection(self, name):
        assert name == "fetch_runs"
        return Query(self.records)


class WritableDocument:
    def __init__(self, records, key):
        self.records = records
        self.key = key

    def create(self, value):
        if self.key in self.records:
            raise ValueError("already exists")
        self.records[self.key] = dict(value)

    def update(self, value):
        self.records[self.key].update(value)

    def get(self):
        return Snapshot(self.records.get(self.key))


class WritableCollection:
    def __init__(self, records):
        self.records = records

    def document(self, key):
        return WritableDocument(self.records, key)


class WritableDatabase(Database):
    def collection(self, name):
        assert name == "fetch_runs"
        return WritableCollection(self.records)


def test_fetch_run_start_and_completion_are_verified_by_readback():
    database = WritableDatabase({})
    store = FirestoreFetchRunStore(database)
    started = {"source": "jsearch", "status": "running"}
    completed = {"status": "success", "records_fetched": 3}

    store.start("run-1", started)
    store.finish("run-1", completed)

    assert database.records["run-1"] == {**started, **completed}
    assert store.get("run-1") == {**started, **completed}


def test_collection_summary_derives_latest_status_per_provider_without_parent_run():
    older = datetime(2026, 10, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 10, 2, tzinfo=timezone.utc)
    store = FirestoreFetchRunStore(Database({
        "j1": {"source": "jsearch", "status": "failed", "started_at": older},
        "j2": {"source": "jsearch", "status": "success", "started_at": newer, "completed_at": newer},
        "a1": {"source": "adzuna", "status": "partial", "started_at": older, "completed_at": older},
    }))

    summary = store.collection_summary()

    assert summary["last_collection"]["status"] == "partial"
    assert summary["last_collection"]["provider_statuses"] == {
        "jsearch": "success", "adzuna": "partial",
    }
    assert summary["last_collection"]["latest_activity"] == newer


def test_collection_summary_reports_failed_only_when_all_latest_provider_runs_failed():
    now = datetime.now(timezone.utc)
    store = FirestoreFetchRunStore(Database({
        "j1": {"source": "jsearch", "status": "failed", "started_at": now},
        "a1": {"source": "adzuna", "status": "failed", "started_at": now},
    }))

    assert store.collection_summary()["last_collection"]["status"] == "failed"

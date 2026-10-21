from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from time import sleep
from unittest.mock import Mock

import firebase_admin
import pytest

from app.core import firebase as firebase_module
from app.core.config import Settings
from app.models.job import Job
from app.services import job_storage_service


def test_firebase_app_rejects_missing_emulator_opt_in_before_admin_lookup(monkeypatch):
    monkeypatch.delenv("TALENTSCOPE_FIREBASE_MODE", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(firebase_admin, "get_app", Mock(side_effect=AssertionError("Firebase app lookup occurred")))
    monkeypatch.setattr(firebase_admin, "initialize_app", Mock(side_effect=AssertionError("Firebase initialized")))
    try:
        with pytest.raises(RuntimeError, match="explicitly set"):
            firebase_module.get_firebase_app()
    finally:
        get_settings.cache_clear()


def test_firebase_admin_initializes_once_for_concurrent_first_requests(monkeypatch):
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    local_settings = Settings(_env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local")
    monkeypatch.setattr(firebase_module, "get_settings", lambda: local_settings)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    app = Mock()
    app.project_id = "demo-talentscope-local"
    app.credential = firebase_module._EmulatorCredential()
    state = {"app": None, "initialize_calls": 0, "initialize_kwargs": None}
    state_lock = Lock()

    def get_app():
        with state_lock:
            existing_app = state["app"]
        if existing_app is not None:
            return existing_app
        sleep(0.05)
        raise ValueError("not initialized")

    def initialize_app(**kwargs):
        with state_lock:
            if state["app"] is not None:
                raise ValueError("The default Firebase app already exists")
            state["initialize_calls"] += 1
            state["initialize_kwargs"] = kwargs
            state["app"] = app
        return app

    monkeypatch.setattr(firebase_admin, "get_app", get_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: firebase_module.get_firebase_app(), range(2)))

    assert results == [app, app]
    assert state["initialize_calls"] == 1
    assert isinstance(state["initialize_kwargs"]["credential"], firebase_module._EmulatorCredential)


def test_firestore_client_is_created_once_and_reused(monkeypatch):
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    local_settings = Settings(_env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local")
    monkeypatch.setattr(firebase_module, "get_settings", lambda: local_settings)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    firebase_module.clear_firebase_client_caches()
    client = object()
    app = object()
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(firebase_module, "get_firebase_app", lambda: app)
    monkeypatch.setattr(firebase_module.firestore, "client", client_factory)

    first = firebase_module.get_firestore_client()
    second = firebase_module.get_firestore_client()
    firebase_module.clear_firebase_client_caches()

    assert first is second is client
    client_factory.assert_called_once_with(app=app)


class FakeSnapshot:
    def __init__(self, data):
        self.exists = data is not None
        self.data = data

    def to_dict(self):
        return deepcopy(self.data)


class FakeDocument:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def get(self):
        return FakeSnapshot(self.store.get(self.path))


class FakeBatch:
    def __init__(self, store):
        self.store = store
        self.pending = []

    def set(self, document, data, merge=False):
        self.pending.append((document.path, deepcopy(data), merge))

    def commit(self):
        for path, data, merge in self.pending:
            current = self.store.get(path, {}) if merge else {}
            self.store[path] = {**current, **data}


class FakeCollection:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def document(self, document_id):
        return FakeDocument(self.store, f"{self.name}/{document_id}")


class FakeFirestore:
    def __init__(self):
        self.documents = {}

    def collection(self, name):
        return FakeCollection(self.documents, name)

    def batch(self):
        return FakeBatch(self.documents)


def test_job_storage_upserts_by_job_id_and_reads_existing_job():
    fake_db = FakeFirestore()
    job = Job(
        job_id="jsearch-test-unique-123",
        title="Backend Developer",
        source="jsearch",
        fetched_at=datetime.now(timezone.utc),
    )

    assert job_storage_service.store_jsearch_jobs([job, job], firestore_client=fake_db) == 1
    assert job_storage_service.store_jsearch_jobs([job], firestore_client=fake_db) == 1
    stored = job_storage_service.get_jsearch_job(job.job_id, firestore_client=fake_db)

    assert list(fake_db.documents) == ["jobs/jsearch:jsearch-test-unique-123"]
    assert stored is not None
    assert stored.job_id == job.job_id
    assert stored.title == "Backend Developer"


def test_job_storage_requires_readback_after_batch_commit():
    import pytest

    class LostWriteBatch(FakeBatch):
        def commit(self):
            return None

    class LostWriteFirestore(FakeFirestore):
        def batch(self):
            return LostWriteBatch(self.documents)

    job = Job(
        job_id="write-not-visible", title="Backend Developer", source="jsearch",
        fetched_at=datetime.now(timezone.utc),
    )

    with pytest.raises(RuntimeError, match="read-back verification failed"):
        job_storage_service.store_jsearch_jobs([job], firestore_client=LostWriteFirestore())


def test_job_storage_rejects_same_id_with_mismatched_readback_payload():
    import pytest

    class CorruptingBatch(FakeBatch):
        def commit(self):
            for path, data, merge in self.pending:
                altered = dict(data)
                altered["title"] = "Stale title"
                self.store[path] = altered

    class CorruptingFirestore(FakeFirestore):
        def batch(self):
            return CorruptingBatch(self.documents)

    job = Job(
        job_id="same-id-wrong-fields", title="Backend Developer", source="jsearch",
        fetched_at=datetime.now(timezone.utc),
    )

    with pytest.raises(RuntimeError, match="read-back verification failed"):
        job_storage_service.store_jsearch_jobs([job], firestore_client=CorruptingFirestore())


def test_job_storage_rejects_conflicting_duplicate_provider_identity():
    import pytest

    fake_db = FakeFirestore()
    fetched_at = datetime.now(timezone.utc)
    first = Job(job_id="same-provider-id", title="Backend Developer", source="jsearch", fetched_at=fetched_at)
    conflict = Job(job_id="same-provider-id", title="Different title", source="jsearch", fetched_at=fetched_at)

    with pytest.raises(ValueError, match="Conflicting job records"):
        job_storage_service.store_jsearch_jobs([first, conflict], firestore_client=fake_db)

    assert fake_db.documents == {}

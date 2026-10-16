from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from time import sleep
from unittest.mock import Mock

import firebase_admin

from app.core import firebase as firebase_module
from app.core.config import Settings
from app.models.job import Job
from app.services import job_storage_service


def test_firebase_admin_uses_configured_certificate_and_initializes_once(monkeypatch, tmp_path):
    firebase_module.get_firebase_app.cache_clear()
    app = object()
    certificate = object()
    get_app = Mock(side_effect=ValueError("not initialized"))
    certificate_factory = Mock(return_value=certificate)
    initialize_app = Mock(return_value=app)
    certificate_path = tmp_path / "service-account.json"
    certificate_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(firebase_admin, "get_app", get_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)
    monkeypatch.setattr(firebase_module.credentials, "Certificate", certificate_factory)
    monkeypatch.setattr(
        firebase_module,
        "get_settings",
        lambda: Settings(google_application_credentials=str(certificate_path)),
    )

    try:
        first = firebase_module.get_firebase_app()
        second = firebase_module.get_firebase_app()
    finally:
        firebase_module.get_firebase_app.cache_clear()

    assert first is app
    assert second is app
    certificate_factory.assert_called_once_with(str(certificate_path))
    initialize_app.assert_called_once()
    assert initialize_app.call_args.kwargs["credential"] is certificate
    assert initialize_app.call_args.kwargs["options"] == {"projectId": "skill-demand-forecasting"}


def test_firebase_certificate_relative_path_resolves_from_backend_root(monkeypatch, tmp_path):
    backend_root = tmp_path / "backend"
    secrets = backend_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "service-account.json").write_text("{}", encoding="utf-8")
    fake_module = backend_root / "app" / "core" / "firebase.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.touch()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(firebase_module, "__file__", str(fake_module))

    assert firebase_module._resolve_certificate_path(
        "secrets/service-account.json"
    ) == (secrets / "service-account.json").resolve()


def test_firebase_admin_initializes_once_for_concurrent_first_requests(monkeypatch):
    firebase_module.get_firebase_app.cache_clear()
    app = object()
    state = {"app": None, "initialize_calls": 0}
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
            state["app"] = app
        return app

    monkeypatch.setattr(firebase_admin, "get_app", get_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)
    monkeypatch.setattr(firebase_module, "get_settings", lambda: Settings())

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: firebase_module.get_firebase_app(), range(2)))
    finally:
        firebase_module.get_firebase_app.cache_clear()

    assert results == [app, app]
    assert state["initialize_calls"] == 1


def test_firestore_client_is_created_once_and_reused(monkeypatch):
    firebase_module.get_firestore_client.cache_clear()
    client = object()
    app = object()
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(firebase_module, "get_firebase_app", lambda: app)
    monkeypatch.setattr(firebase_module.firestore, "client", client_factory)

    try:
        first = firebase_module.get_firestore_client()
        second = firebase_module.get_firestore_client()
    finally:
        firebase_module.get_firestore_client.cache_clear()

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


def test_job_storage_upserts_by_job_id_and_reads_existing_job(monkeypatch):
    fake_db = FakeFirestore()
    monkeypatch.setattr(job_storage_service, "get_firestore_client", lambda: fake_db)
    job = Job(
        job_id="jsearch-test-unique-123",
        title="Backend Developer",
        source="jsearch",
        fetched_at=datetime.now(timezone.utc),
    )

    assert job_storage_service.store_jsearch_jobs([job]) == 1
    assert job_storage_service.store_jsearch_jobs([job]) == 1
    stored = job_storage_service.get_jsearch_job(job.job_id)

    assert list(fake_db.documents) == ["jobs/jsearch:jsearch-test-unique-123"]
    assert stored is not None
    assert stored.job_id == job.job_id
    assert stored.title == "Backend Developer"

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser
from app.services import learning_progress_service as progress_service


class Snapshot:
    def __init__(self, key, value):
        self.id, self.value = key, value

    def to_dict(self):
        return self.value


class ActivityRef:
    def __init__(self, store, uid, name, key):
        self.store, self.uid, self.name, self.key = store, uid, name, key

    def set(self, value, merge=False):
        collection = self.store.setdefault(self.uid, {}).setdefault(self.name, {})
        collection[self.key] = {**collection.get(self.key, {}), **value} if merge else value


class ActivityCollection:
    def __init__(self, store, uid, name):
        self.store, self.uid, self.name = store, uid, name

    def document(self, key):
        return ActivityRef(self.store, self.uid, self.name, key)

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, count):
        self.count = count
        return self

    def stream(self):
        values = self.store.get(self.uid, {}).get(self.name, {})
        rows = sorted(values.items(), key=lambda item: item[1].get("updated_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        return [Snapshot(key, value) for key, value in rows[:getattr(self, "count", 200)]]


class UserDoc:
    def __init__(self, store, uid):
        self.store, self.uid = store, uid

    def collection(self, name):
        return ActivityCollection(self.store, self.uid, name)


class Users:
    def __init__(self, store):
        self.store = store

    def document(self, uid):
        return UserDoc(self.store, uid)


class FirestoreFake:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        assert name == "users"
        return Users(self.store)


@pytest.fixture
def client(monkeypatch):
    fake = FirestoreFake()
    monkeypatch.setattr(progress_service, "get_firestore_client", lambda: fake)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="activity-user-a")
    with TestClient(app) as test_client:
        yield test_client, fake
    app.dependency_overrides.pop(get_current_user, None)


def test_user_attested_resource_progress_round_trip_and_isolation(client):
    test_client, fake = client
    response = test_client.put("/api/v1/learning/progress/github-skills", json={"status": "completed"})
    assert response.status_code == 200
    item = response.json()["activities"][0]
    assert item["activity_id"] == "github-skills"
    assert item["activity_kind"] == "resource"
    assert item["status"] == "completed"
    assert item["completion_source"] == "user_attested"
    assert test_client.get("/api/v1/learning/progress").json()["count"] == 1

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="activity-user-b")
    try:
        assert test_client.get("/api/v1/learning/progress").json() == {"activities": [], "count": 0}
        assert "activity-user-b" not in fake.store
    finally:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="activity-user-a")


def test_only_catalog_activities_can_be_updated_and_status_is_validated(client):
    test_client, _ = client
    assert test_client.put("/api/v1/learning/progress/not-a-catalog-item", json={"status": "completed"}).status_code == 404
    assert test_client.put("/api/v1/learning/progress/github-skills", json={"status": "watched"}).status_code == 422


def test_firestore_write_failure_is_not_reported_as_success(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(progress_service, "get_firestore_client", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    response = test_client.put("/api/v1/learning/progress/github-skills", json={"status": "in_progress"})
    assert response.status_code == 503
    assert "could not be saved" in response.json()["detail"].lower()


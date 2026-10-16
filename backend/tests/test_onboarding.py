from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser
from app.services import onboarding_service


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def authenticated_individual():
    return AuthenticatedUser(
        uid="onboarding-user-1",
        email="individual@example.com",
        email_verified=True,
        display_name="Individual User",
        auth_provider="password",
    )


class Snapshot:
    def __init__(self, value):
        self.value = deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self.value)


class Document:
    def __init__(self, db, collection, document_id):
        self.db = db
        self.collection = collection
        self.document_id = document_id
        self.path = f"{collection}/{document_id}"

    def get(self):
        if self.db.fail_reads:
            raise RuntimeError("mock Firestore read failure")
        return Snapshot(self.db.documents.get(self.path))

    def set(self, value, merge=False):
        current = deepcopy(self.db.documents.get(self.path, {})) if merge else {}
        current.update(value)
        self.db.documents[self.path] = current

    def update(self, updates):
        if self.db.fail_writes:
            raise RuntimeError("mock Firestore write failure")
        current = self.db.documents.setdefault(self.path, {})
        for path, value in updates.items():
            parts = path.split(".")
            target = current
            for part in parts[:-1]:
                nested = target.get(part)
                if not isinstance(nested, dict):
                    nested = {}
                    target[part] = nested
                target = nested
            target[parts[-1]] = value


class Collection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def document(self, document_id):
        return Document(self.db, self.name, document_id)


class FakeFirestore:
    def __init__(self, documents=None, fail_reads=False, fail_writes=False):
        self.documents = deepcopy(documents or {})
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes

    def collection(self, name):
        return Collection(self, name)


def set_authenticated_user():
    app.dependency_overrides[get_current_user] = authenticated_individual


def use_database(monkeypatch, database):
    monkeypatch.setattr(onboarding_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(
        onboarding_service.firestore,
        "SERVER_TIMESTAMP",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_unauthenticated_step_save_returns_401():
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/1",
            json={"answer": {"name": "A", "ageGroup": "22–25", "city": "Chennai", "country": "India"}},
        )

    assert response.status_code == 401


def test_step_one_persists_basic_profile_and_progress(monkeypatch):
    database = FakeFirestore()
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/1",
            json={"answer": {"name": "Ada", "ageGroup": "22–25", "city": "Chennai", "country": "India"}},
        )

    assert response.status_code == 200
    stored = database.documents["users/onboarding-user-1"]
    assert stored["profile"]["basic_profile"] == {
        "name": "Ada", "ageGroup": "22–25", "city": "Chennai", "country": "India"
    }
    assert stored["onboarding"]["current_step"] == 2
    assert stored["onboarding"]["completed_steps"] == [1]
    assert stored["onboarding"]["completed"] is False


def test_step_one_allows_optional_age_group_to_be_omitted(monkeypatch):
    database = FakeFirestore()
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/1",
            json={"answer": {"name": "Ada", "city": "Chennai", "country": "India"}},
        )

    assert response.status_code == 200
    assert database.documents["users/onboarding-user-1"]["profile"]["basic_profile"] == {
        "name": "Ada", "city": "Chennai", "country": "India"
    }


def test_step_five_requires_selected_skills_and_valid_levels(monkeypatch):
    database = FakeFirestore()
    use_database(monkeypatch, database)
    set_authenticated_user()
    with TestClient(app) as client:
        client.put("/api/v1/onboarding/individual/step/1", json={"answer": {
            "name": "Ada", "ageGroup": "22–25", "city": "Chennai", "country": "India"
        }})
        for step, answer in [(2, "Student"), (3, "No experience yet"), (4, ["Python"])]:
            response = client.put(f"/api/v1/onboarding/individual/step/{step}", json={"answer": answer})
            assert response.status_code == 200
        invalid = client.put(
            "/api/v1/onboarding/individual/step/5",
            json={"answer": {"SQL": "Expert"}},
        )
        valid = client.put(
            "/api/v1/onboarding/individual/step/5",
            json={"answer": {"Python": "Advanced"}},
        )

    assert invalid.status_code == 422
    assert valid.status_code == 200
    assert database.documents["users/onboarding-user-1"]["profile"]["skills"]["skill_levels"] == {
        "Python": "Advanced"
    }


def test_future_step_is_rejected_and_resume_progress_is_returned(monkeypatch):
    database = FakeFirestore()
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        future = client.put(
            "/api/v1/onboarding/individual/step/2",
            json={"answer": "Student"},
        )
        step_one = client.put(
            "/api/v1/onboarding/individual/step/1",
            json={"answer": {"name": "Ada", "ageGroup": "22–25", "city": "Chennai", "country": "India"}},
        )
        profile = client.get("/api/v1/onboarding/individual/profile")
        progress = client.get("/api/v1/onboarding/individual/progress")

    assert future.status_code == 409
    assert step_one.status_code == 200
    assert profile.status_code == 200
    assert profile.json()["answers"]["name_and_location"]["city"] == "Chennai"
    assert profile.json()["onboarding"]["current_step"] == 2
    assert progress.json()["completed_steps"] == [1]


def test_step_twelve_marks_onboarding_complete(monkeypatch):
    user_doc = {
        "uid": "onboarding-user-1",
        "user_type": "individual",
        "onboarding": {"current_step": 12, "completed_steps": list(range(1, 12)), "completed": False},
        "profile": {"skills": {"selected_skills": [], "skill_levels": {}}},
    }
    database = FakeFirestore({"users/onboarding-user-1": user_doc})
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/12",
            json={"answer": ["Example Company"]},
        )

    assert response.status_code == 200
    stored = database.documents["users/onboarding-user-1"]
    assert stored["onboarding"]["completed"] is True
    assert stored["onboarding"]["completed_steps"] == list(range(1, 13))
    assert stored["onboarding_completed"] is True
    assert stored["profile"]["company_preferences"]["preferred_companies"] == ["Example Company"]


def test_partial_update_preserves_other_profile_fields(monkeypatch):
    database = FakeFirestore({"users/onboarding-user-1": {
        "uid": "onboarding-user-1",
        "user_type": "individual",
        "onboarding": {"current_step": 2, "completed_steps": [1], "completed": False},
        "profile": {
            "basic_profile": {"name": "Ada", "city": "Chennai", "country": "India", "ageGroup": "22–25"},
            "interests": ["Fintech"],
        },
    }})
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/2",
            json={"answer": "Student"},
        )

    stored = database.documents["users/onboarding-user-1"]
    assert response.status_code == 200
    assert stored["profile"]["basic_profile"]["city"] == "Chennai"
    assert stored["profile"]["interests"] == ["Fintech"]
    assert stored["profile"]["current_stage"] == "Student"


def test_profile_retrieval_uses_verified_uid_not_request_uid(monkeypatch):
    database = FakeFirestore()
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.get("/api/v1/onboarding/individual/profile?uid=someone-else")

    assert response.status_code == 200
    assert response.json()["uid"] == "onboarding-user-1"
    assert "someone-else" not in database.documents


def test_firestore_failure_returns_safe_retryable_error(monkeypatch):
    database = FakeFirestore(fail_writes=True)
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/onboarding/individual/step/1",
            json={"answer": {"name": "Ada", "ageGroup": "22–25", "city": "Chennai", "country": "India"}},
        )

    assert response.status_code == 503
    assert "mock Firestore" not in response.text


def test_invalid_step_number_is_rejected():
    set_authenticated_user()
    with TestClient(app) as client:
        response = client.put("/api/v1/onboarding/individual/step/13", json={"answer": "x"})

    assert response.status_code == 422


def test_employee_onboarding_answers_persist_in_firestore(monkeypatch):
    database = FakeFirestore({"users/onboarding-user-1": {"uid": "onboarding-user-1", "user_type": "employee"}})
    use_database(monkeypatch, database)
    set_authenticated_user()
    with TestClient(app) as client:
        saved = client.put("/api/v1/onboarding/employee/step/1", json={
            "question_id": "emp_name_and_location",
            "answer": {"name": "Ada", "city": "Chennai", "country": "India"},
        })
        loaded = client.get("/api/v1/onboarding/employee/profile")
    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["answers"]["emp_name_and_location"]["name"] == "Ada"
    assert database.documents["users/onboarding-user-1"]["onboarding"]["completed_steps"] == [1]


def test_company_onboarding_completion_creates_owner_bound_company(monkeypatch):
    existing = {
        "uid": "onboarding-user-1", "user_type": "company",
        "profile": {"company_onboarding_answers": {"cmp_organization": {"companyName": "Northwind"}}},
        "onboarding": {"current_step": 11, "completed_steps": list(range(1, 11)), "completed": False},
    }
    database = FakeFirestore({"users/onboarding-user-1": existing})
    use_database(monkeypatch, database)
    set_authenticated_user()
    with TestClient(app) as client:
        response = client.put("/api/v1/onboarding/company/step/11", json={
            "question_id": "cmp_platform_usage", "answer": "Understand market hiring signals",
        })
    assert response.status_code == 200
    user = database.documents["users/onboarding-user-1"]
    assert user["onboarding_completed"] is True
    assert user["company_id"]
    assert user["profile"]["company"]["company_id"] == user["company_id"]
    company = database.documents[f"companies/{user['company_id']}"]
    assert company["owner_uid"] == "onboarding-user-1"
    assert company["company_name"] == "Northwind"
    with TestClient(app) as client:
        retry = client.put("/api/v1/onboarding/company/step/11", json={
            "question_id": "cmp_platform_usage", "answer": "Understand market hiring signals",
        })
    assert retry.status_code == 200
    assert len([path for path in database.documents if path.startswith("companies/")]) == 1

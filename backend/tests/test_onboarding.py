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


def test_employee_onboarding_persists_and_updates_authenticated_profile(monkeypatch):
    employee = AuthenticatedUser(
        uid="employee-user-1",
        email="employee@example.com",
        email_verified=True,
        display_name="Employee",
        auth_provider="password",
    )
    database = FakeFirestore({"users/employee-user-1": {
        "uid": "employee-user-1",
        "user_type": "employee",
        "profile": {"unrelated": {"keep": True}},
    }})
    use_database(monkeypatch, database)
    app.dependency_overrides[get_current_user] = lambda: employee
    answers = [
        ("emp_name_and_location", {"name": "Arun", "city": "Chennai", "country": "India"}),
        ("emp_workplace", {"company": "Example Ltd", "department": "Engineering", "currentRole": "Engineer"}),
        ("emp_experience_field", "3–5 years"),
        ("emp_skills", ["Python", "React"]),
        ("emp_skill_confidence", {"Python": "Advanced", "React": "Comfortable"}),
        ("emp_improvements", ["My technical skills"]),
        ("emp_trajectory", "Move to a senior role"),
        ("emp_next_skills", ["SQL"]),
        ("emp_time", "2–5 hours"),
        ("emp_internal_goals", ["Prepare for promotion milestone"]),
    ]

    with TestClient(app) as client:
        for step, (question_id, answer) in enumerate(answers, start=1):
            response = client.put(
                f"/api/v1/onboarding/employee/step/{step}",
                json={"question_id": question_id, "answer": answer},
            )
            assert response.status_code == 200, response.text
        profile_response = client.get("/api/v1/onboarding/employee/profile")

        updated = client.put(
            "/api/v1/onboarding/employee/step/1",
            json={"question_id": "emp_name_and_location", "answer": {
                "name": "Arun Kumar", "city": "Chennai", "country": "India",
            }},
        )

    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["answers"]["emp_name_and_location"]["name"] == "Arun"
    assert profile["profile"]["display_name"] == "Arun"
    assert profile["profile"]["current_skill_domains"] == ["Python", "React"]
    assert profile["profile"]["self_reported_skill_confidence"] == {
        "Python": "Advanced", "React": "Comfortable",
    }
    assert profile["profile"]["weekly_learning_time"] == "2–5 hours"
    assert profile["onboarding"]["completed"] is True
    assert updated.status_code == 200
    assert database.documents["users/employee-user-1"]["profile"]["unrelated"] == {"keep": True}
    assert database.documents["users/employee-user-1"]["profile"]["employee_onboarding_answers"]["emp_name_and_location"]["name"] == "Arun Kumar"
    assert len(database.documents) == 1


def test_employee_profile_access_is_scoped_to_verified_uid(monkeypatch):
    database = FakeFirestore({"users/employee-user-1": {
        "uid": "employee-user-1",
        "user_type": "employee",
    }})
    use_database(monkeypatch, database)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="employee-user-2",
        email="other@example.com",
        email_verified=True,
        auth_provider="password",
    )

    with TestClient(app) as client:
        read_response = client.get("/api/v1/onboarding/employee/profile")
        update_response = client.put(
            "/api/v1/onboarding/employee/step/1",
            json={"question_id": "emp_name_and_location", "answer": {
                "name": "Other", "city": "Chennai", "country": "India",
            }},
        )

    assert read_response.status_code == 403
    assert update_response.status_code == 403
    assert "users/employee-user-2" not in database.documents
    assert database.documents["users/employee-user-1"]["uid"] == "employee-user-1"


def test_employee_onboarding_rejects_invalid_answers_and_unauthenticated_requests(monkeypatch):
    database = FakeFirestore({"users/onboarding-user-1": {
        "uid": "onboarding-user-1",
        "user_type": "employee",
    }})
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        client.put("/api/v1/onboarding/employee/step/1", json={
            "question_id": "emp_name_and_location",
            "answer": {"name": "Ada", "city": "Chennai", "country": "India"},
        })
        client.put("/api/v1/onboarding/employee/step/2", json={
            "question_id": "emp_workplace",
            "answer": {"company": "Example Ltd", "currentRole": "Engineer"},
        })
        client.put("/api/v1/onboarding/employee/step/3", json={
            "question_id": "emp_experience_field", "answer": "3–5 years",
        })
        invalid = client.put("/api/v1/onboarding/employee/step/4", json={
            "question_id": "emp_skills", "answer": ["Python", 42],
        })
        app.dependency_overrides.clear()
        unauthenticated = client.get("/api/v1/onboarding/employee/profile")

    assert invalid.status_code == 422
    assert unauthenticated.status_code == 401
    assert "emp_skills" not in database.documents["users/onboarding-user-1"].get("profile", {}).get("employee_onboarding_answers", {})


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

def test_new_company_admin_starts_at_step_one_with_no_completed_steps(monkeypatch):
    """Ensure brand new company admins start at Question 1, even if legacy individual onboarding progress is present."""
    existing = {
        "uid": "onboarding-user-1",
        "user_type": "company",
        "profile": {"company_onboarding_answers": {}},
        "onboarding": {"current_step": 12, "completed_steps": list(range(1, 13)), "completed": True},
    }
    database = FakeFirestore({"users/onboarding-user-1": existing})
    use_database(monkeypatch, database)
    set_authenticated_user()
    with TestClient(app) as client:
        response = client.get("/api/v1/onboarding/company/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["onboarding"]["current_step"] == 1
        assert data["onboarding"]["completed_steps"] == []
        assert data["onboarding"]["completed"] is False

        # Attempting to jump directly to Step 11 without prior answers should fail with 409
        jump_response = client.put("/api/v1/onboarding/company/step/11", json={
            "question_id": "cmp_platform_usage",
            "answer": "External talent intelligence focus",
        })
        assert jump_response.status_code == 409

        # Answering Step 1 works and moves to step 2
        step1_response = client.put("/api/v1/onboarding/company/step/1", json={
            "question_id": "cmp_organization",
            "answer": {
                "companyName": "Acme Innovations",
                "industry": "Software & Internet",
                "city": "Austin",
                "country": "United States",
            },
        })
        assert step1_response.status_code == 200
        step1_data = step1_response.json()
        assert step1_data["onboarding"]["current_step"] == 2
        assert step1_data["onboarding"]["completed_steps"] == [1]



def test_onboarding_route_aliases_and_methods(monkeypatch):
    """Verify OPTIONS, POST, PUT, and prefix aliases for onboarding endpoints."""
    existing = {
        "uid": "onboarding-user-1",
        "user_type": "individual",
        "profile": {},
        "onboarding": {"current_step": 1, "completed_steps": [], "completed": False},
    }
    database = FakeFirestore({"users/onboarding-user-1": existing})
    use_database(monkeypatch, database)
    set_authenticated_user()

    with TestClient(app) as client:
        # 1. Options preflight handlers return 200
        opt1 = client.options("/api/v1/onboarding/individual/step/1")
        assert opt1.status_code == 200

        opt2 = client.options("/api/v1/onboarding/profile")
        assert opt2.status_code == 200

        opt3 = client.options("/api/v1/onboarding/employee/step/1")
        assert opt3.status_code == 200

        # 2. Both PUT and POST work on individual step
        ans1 = {"name": "Test User", "ageGroup": "22–25", "city": "Chennai", "country": "India"}
        post_step = client.post("/api/v1/onboarding/individual/step/1", json={"answer": ans1})
        assert post_step.status_code == 200
        assert post_step.json()["saved"] is True

        put_step = client.put("/api/v1/onboarding/individual/step/1", json={"answer": ans1})
        assert put_step.status_code == 200
        assert put_step.json()["saved"] is True

        # 3. Both GET and POST work on generic /onboarding/profile
        get_prof = client.get("/api/v1/onboarding/profile")
        assert get_prof.status_code == 200

        post_prof = client.post("/api/v1/onboarding/profile")
        assert post_prof.status_code == 200

        # 4. Endpoints accessible under /api prefix alias
        alias_get = client.get("/api/onboarding/individual/profile")
        assert alias_get.status_code == 200

        alias_step = client.post("/api/onboarding/individual/step/1", json={"answer": ans1})
        assert alias_step.status_code == 200

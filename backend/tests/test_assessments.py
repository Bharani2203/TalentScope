import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.dependencies import get_current_user
from app.api.router import api_router
from app.main import app
from app.models.auth import AuthenticatedUser
from app.services import assessment_service as service


def _approved(record):
    record["verification_status"] = "approved"
    record["review"] = {"status": "approved", "reviewer_id": "reviewer-test", "approved_at": "2026-10-01T00:00:00Z"}
    return record


@pytest.fixture
def bank(monkeypatch):
    monkeypatch.setattr(service.firestore, "transactional", lambda function: function)
    monkeypatch.setattr(service, "_approved_scoring_policy", lambda: {"minimum_questions_per_skill_difficulty": 1})
    question = _approved({
        "question_id": "ts-python-test-001", "skill_ids": ["python"], "topic_ids": ["python-functions"],
        "question_type": "mcq", "difficulty": "beginner", "question_text": "Which option is correct?",
        "options": [{"option_id": "a", "text": "First"}, {"option_id": "b", "text": "Second"}],
        "provenance": "Original TalentScope assessment question", "license": "TalentScope.ai original content",
    })
    answer = _approved({
        "question_id": "ts-python-test-001", "correct_answer": "b", "explanation": "Private explanation",
        "scoring_rubric": [{"criterion": "Select b", "points": 2}],
    })
    version = service._content_version(question, answer)
    question["review"]["content_version"] = version
    answer["review"]["content_version"] = version
    monkeypatch.setattr(service, "_load_bank", lambda: ([question], {answer["question_id"]: answer}, "test-digest"))
    return question, answer


class Snapshot:
    def __init__(self, data=None, snapshot_id=None):
        self.data = data
        self.exists = data is not None
        self.id = snapshot_id or (data or {}).get("attempt_id", "")

    def to_dict(self):
        return dict(self.data or {})


class FakeReference:
    def __init__(self, store, key):
        self.store, self.key = store, key

    def create(self, data):
        if self.key in self.store:
            raise RuntimeError("already exists")
        self.store[self.key] = dict(data)

    def set(self, data, merge=False):
        if merge and self.key in self.store:
            self.store[self.key].update(dict(data))
        else:
            self.store[self.key] = dict(data)

    def get(self, transaction=None):
        return Snapshot(self.store.get(self.key))


class FakeCollection:
    def __init__(self, store):
        self.store = store

    def document(self, key):
        return FakeReference(self.store, key)

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        return [Snapshot(value, key) for key, value in self.store.items()]


class FakeUserDocument:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return FakeCollection(self.store.setdefault(name, {}))


class FakeUsers:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        assert name == "users"
        return self

    def document(self, uid):
        return FakeUserDocument(self.data.setdefault(uid, {}))


class FakeTransaction:
    def _begin(self, *args, **kwargs):
        return None

    def _commit(self):
        return None

    def _rollback(self):
        return None

    def _clean_up(self):
        return None

    def update(self, ref, data):
        ref.store[ref.key].update(data)


class FakeFirestore:
    def __init__(self):
        self.users = FakeUsers()

    def collection(self, name):
        return self.users.collection(name)

    def transaction(self):
        return FakeTransaction()


class ReviewDB:
    def __init__(self):
        self.rows = {}

    def collection(self, name):
        return ReviewCollection(self, (name,))

    def batch(self):
        return ReviewBatch()


class ReviewBatch:
    def __init__(self):
        self.writes = []

    def set(self, ref, data):
        self.writes.append((ref, dict(data)))

    def commit(self):
        for ref, data in self.writes:
            ref.set(data)


class ReviewCollection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, key):
        return ReviewDocument(self.db, self.path + (key,))


class ReviewDocument:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def get(self):
        data = self.db.rows.get(self.path)
        return Snapshot(data)

    def set(self, data):
        self.db.rows[self.path] = dict(data)


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-user-a")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def test_existing_bank_is_draft_only_and_has_consistent_keys():
    root = Path(__file__).parents[1] / "app" / "data" / "question_bank"
    questions = json.loads((root / "questions_public.json").read_text(encoding="utf-8"))
    keys = json.loads((root / "private" / "answer_keys.json").read_text(encoding="utf-8"))["answers"]
    question_ids = [item["question_id"] for item in questions]
    key_ids = [item["question_id"] for item in keys]
    assert len(questions) == 80
    assert len(question_ids) == len(set(question_ids)) == len(key_ids) == len(set(key_ids))
    assert set(question_ids) == set(key_ids)
    assert all(item.get("verification_status") == "draft_unreviewed" for item in questions + keys)


def test_admin_review_queue_is_claim_protected_private_and_versioned(client, monkeypatch):
    question = {
        "question_id": "ts-python-draft-001", "skill_ids": ["python"], "topic_ids": ["python-functions"],
        "question_type": "mcq", "difficulty": "beginner", "question_text": "Choose the answer.",
        "options": [{"option_id": "a", "text": "A"}, {"option_id": "b", "text": "B"}],
        "verification_status": "draft_unreviewed",
    }
    answer = {"question_id": question["question_id"], "correct_answer": "b", "scoring_rubric": [{"points": 1}]}
    monkeypatch.setattr(service, "_load_bank", lambda: ([question], {question["question_id"]: answer}, "digest"))
    db = ReviewDB()
    monkeypatch.setattr(service, "get_firestore_client", lambda: db)

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="learner")
    denied = client.get("/api/v1/learning/assessments/admin/review-queue")
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="trusted-reviewer", role="admin")
    queue = client.get("/api/v1/learning/assessments/admin/review-queue")
    assert queue.status_code == 200
    item = queue.json()["items"][0]
    assert item["private_answer_record"]["correct_answer"] == "b"
    assert item["status"] == "draft_unreviewed"

    result = client.post(f"/api/v1/learning/assessments/admin/questions/{question['question_id']}/review", json={
        "decision": "approved", "reason": "Wording and key checked against the scoring rubric."
    })
    assert result.status_code == 200
    assert result.json()["reviewer_uid"] == "trusted-reviewer"
    assert result.json()["live_eligible"] is False
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}
    assert len([path for path in db.rows if path[0] == "learning_assessment_review_audit"]) == 1

    changed = {**question, "question_text": "Changed after review."}
    monkeypatch.setattr(service, "_load_bank", lambda: ([changed], {question["question_id"]: answer}, "digest-2"))
    reloaded = client.get("/api/v1/learning/assessments/admin/review-queue").json()["items"][0]
    assert reloaded["status"] == "re-review required"
    app.dependency_overrides.pop(get_current_user, None)


def test_review_decision_write_failure_is_not_reported_as_saved(monkeypatch):
    question = {"question_id": "ts-python-draft-001", "question_text": "Draft"}
    answer = {"question_id": question["question_id"], "correct_answer": "a"}
    monkeypatch.setattr(service, "_load_bank", lambda: ([question], {question["question_id"]: answer}, "digest"))

    class FailingBatch(ReviewBatch):
        def commit(self):
            raise RuntimeError("firestore unavailable")

    class FailingDB(ReviewDB):
        def batch(self):
            return FailingBatch()

    monkeypatch.setattr(service, "get_firestore_client", lambda: FailingDB())
    with pytest.raises(HTTPException) as failed:
        service.review_assessment_question(question["question_id"], "approved", "Checked wording and key.", "reviewer")
    assert failed.value.status_code == 503


def test_unreviewed_questions_are_excluded_and_attempt_unavailable(client, monkeypatch):
    question, answer = _approved({
        "question_id": "ts-python-test-001", "skill_ids": ["python"], "topic_ids": [],
        "question_type": "mcq", "difficulty": "beginner", "question_text": "Choose.",
        "options": [{"option_id": "a", "text": "A"}],
    }), _approved({"question_id": "ts-python-test-001", "correct_answer": "a", "scoring_rubric": [{"points": 1}]})
    question["review"]["status"] = "draft_unreviewed"
    monkeypatch.setattr(service, "_load_bank", lambda: ([question], {answer["question_id"]: answer}, "digest"))
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}
    assert client.post("/api/v1/learning/assessments/python/attempts").status_code == 409


def test_approved_questions_remain_unavailable_without_scoring_policy(client, bank, monkeypatch):
    monkeypatch.setattr(service, "_approved_scoring_policy", lambda: None)
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}
    assert client.post("/api/v1/learning/assessments/python/attempts").status_code == 409


def test_approved_question_and_key_need_matching_reviewer_metadata(client, bank, monkeypatch):
    question, answer = bank
    answer["review"]["reviewer_id"] = "different-reviewer"
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}
    answer["review"]["reviewer_id"] = question["review"]["reviewer_id"]
    answer["review"]["approved_at"] = "2026-10-02T00:00:00Z"
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}
    answer["review"]["approved_at"] = question["review"]["approved_at"]
    question["question_text"] = "Edited wording after approval."
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}


def test_question_pool_uses_only_the_explicit_per_difficulty_policy(client, bank, monkeypatch):
    monkeypatch.setattr(service, "_approved_scoring_policy", lambda: {
        "minimum_questions_per_skill_difficulty": 2,
    })
    assert client.get("/api/v1/learning/assessments").json() == {"assessments": []}


def test_start_redacts_answers_and_submission_is_server_scored(client, bank, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    started = client.post("/api/v1/learning/assessments/python/attempts?question_count=1")
    assert started.status_code == 201
    question = started.json()["questions"][0]
    assert question["question_id"] == "ts-python-test-001"
    assert "correct_answer" not in started.text and "Private explanation" not in started.text
    result = client.post(f"/api/v1/learning/assessments/attempts/{started.json()['attempt_id']}/submit", json={"answers": {question["question_id"]: {"answer": "b"}}})
    assert result.status_code == 200
    assert result.json()["score"] == result.json()["max_score"] == 2
    assert result.json()["percentage"] == 100
    assert result.json()["evidence_type"] == "assessment_derived_provisional"
    assert result.json()["proficiency"] == "provisional"
    attempt = store.users.data["verified-user-a"]["learning_assessment_attempts"][started.json()["attempt_id"]]
    assert "correct_answer" not in attempt and "Private explanation" not in json.dumps(attempt, default=str)
    assert attempt["status"] == "completed"
    history = client.get("/api/v1/learning/assessments/attempts").json()
    assert history["count"] == 1
    assert history["attempts"][0]["percentage"] == 100
    assert "submitted_answers" not in json.dumps(history)
    assert "correct_answer" not in json.dumps(history)


def test_invalid_format_duplicate_submit_and_user_isolation(client, bank, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    started = client.post("/api/v1/learning/assessments/python/attempts?question_count=1").json()
    attempt_id = started["attempt_id"]
    qid = started["questions"][0]["question_id"]
    route = f"/api/v1/learning/assessments/attempts/{attempt_id}/submit"
    assert client.post(route, json={"answers": {qid: {"answer": "not-an-option"}}}).status_code == 422
    assert client.post(route, json={"answers": {qid: {"answer": "a"}}}).status_code == 200
    assert client.post(route, json={"answers": {qid: {"answer": "b"}}}).status_code == 409

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-user-b")
    try:
        assert client.post(route, json={"answers": {qid: {"answer": "b"}}}).status_code == 404
    finally:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-user-a")


def test_auth_is_required_for_assessment_endpoints():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/api/v1/learning/assessments").status_code == 401


def test_firestore_failure_does_not_claim_attempt_saved(client, bank, monkeypatch):
    def fail():
        raise RuntimeError("storage offline")
    monkeypatch.setattr(service, "get_firestore_client", fail)
    response = client.post("/api/v1/learning/assessments/python/attempts?question_count=1")
    assert response.status_code == 503
    assert "could not be saved" in response.json()["detail"]


def test_firestore_failure_during_submission_is_not_reported_as_success(client, bank, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    started = client.post("/api/v1/learning/assessments/python/attempts?question_count=1").json()
    monkeypatch.setattr(store, "transaction", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    question_id = started["questions"][0]["question_id"]
    response = client.post(
        f"/api/v1/learning/assessments/attempts/{started['attempt_id']}/submit",
        json={"answers": {question_id: {"answer": "b"}}},
    )
    assert response.status_code == 503
    assert "no result was recorded" in response.json()["detail"]


def test_suspicious_activity_strikes_and_24h_restriction(client, bank, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)

    # Initially not restricted
    status = client.get("/api/v1/learning/assessments/security/restriction-status").json()
    assert status["is_restricted"] is False
    assert status["strike_count"] == 0
    assert status["active_strikes_remaining"] == 3

    # Strike 1: tab blur
    res1 = client.post("/api/v1/learning/assessments/security/strikes", json={
        "event_type": "tab_blur", "attempt_id": "attempt-1"
    }).json()
    assert res1["strike_count"] == 1
    assert res1["is_restricted"] is False
    assert res1["active_strikes_remaining"] == 2

    # Strike 2: fullscreen exit
    res2 = client.post("/api/v1/learning/assessments/security/strikes", json={
        "event_type": "fullscreen_exit", "attempt_id": "attempt-1"
    }).json()
    assert res2["strike_count"] == 2
    assert res2["is_restricted"] is False
    assert res2["active_strikes_remaining"] == 1

    # Strike 3: threshold reached -> triggers 24h restriction
    res3 = client.post("/api/v1/learning/assessments/security/strikes", json={
        "event_type": "copy_paste_attempt", "attempt_id": "attempt-1"
    }).json()
    assert res3["strike_count"] == 3
    assert res3["is_restricted"] is True
    assert res3["restriction_until"] is not None
    assert "24 hours" in res3["reason"]

    # Starting a new attempt while restricted fails with 403
    attempt_res = client.post("/api/v1/learning/assessments/python/attempts?question_count=1")
    assert attempt_res.status_code == 403
    assert "temporarily restricted" in attempt_res.json()["detail"]


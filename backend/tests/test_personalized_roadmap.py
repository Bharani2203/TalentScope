from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from firebase_admin import auth
from fastapi.testclient import TestClient
from google.cloud.firestore_v1._helpers import encode_value

from app.api import dependencies as auth_dependencies
from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser
from app.analytics.skill_registry import canonical_skill_id
from app.services import roadmap_service as service
from app.services import learning_gemini_service as learning_gemini
from app.services import learning_curriculum_service as curriculum_service


def profile(*, skills=None, levels=None, target_role="Software Developer"):
    return SimpleNamespace(
        profile={
            "basic_profile": {"city": "Chennai", "country": "India"},
            "experience": {"experience": "1-2 years", "studyField": "Computer Science"},
            "skills": {"selected_skills": skills if skills is not None else ["Python", "My Side Project"], "skill_levels": levels or {"Python": "Beginner"}},
            "career": {"career_goals": ["Get my first job"], "target_roles": [target_role] if target_role else []},
            "interests": ["Software Development"],
            "learning_preferences": ["Reading", "Hands-on practice"],
            "work_preferences": {"learning_time": "2-5 hours"},
        },
        answers={},
        onboarding=SimpleNamespace(completed=False),
    )


class FakeReferenceStore:
    def get_onet_occupations(self, *, title, limit):
        return [SimpleNamespace(soc_code="15-1252.00", title="Software Developer", description="")]

    def get_onet_essential_skills_by_occupation(self, soc_code, *, limit):
        return [
            {"element_name": "Python", "element_id": "python-ref", "data_value": 4.0},
            {"element_name": "Communication", "element_id": "comm-ref", "data_value": 3.2},
        ]

    def get_esco_occupations(self, *, query, limit):
        return []


class FakeSnapshot:
    def __init__(self, key, data):
        self.id = key
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class FakeRef:
    def __init__(self, store, uid, collection, key):
        self.store, self.uid, self.collection_name, self.key = store, uid, collection, key

    def _data(self):
        return self.store.setdefault(self.uid, {}).setdefault(self.collection_name, {})

    def get(self, transaction=None):
        return FakeSnapshot(self.key, self._data().get(self.key))

    def create(self, data):
        encode_value(data)
        if self.key in self._data():
            raise RuntimeError("already exists")
        self._data()[self.key] = data

    def set(self, data):
        encode_value(data)
        self._data()[self.key] = data

    def delete(self):
        self._data().pop(self.key, None)

    def collection(self, name):
        return FakeCollection(self.store, f"{self.uid}/{self.collection_name}/{self.key}", name)


class FakeCollection:
    def __init__(self, store, uid, collection):
        self.store, self.uid, self.collection_name = store, uid, collection

    def document(self, key):
        return FakeRef(self.store, self.uid, self.collection_name, key)

    def stream(self, transaction=None):
        rows = self.store.get(self.uid, {}).get(self.collection_name, {})
        return [FakeSnapshot(key, value) for key, value in rows.items()]


class FakeUserDoc:
    def __init__(self, store, uid):
        self.store, self.uid = store, uid

    def collection(self, name):
        return FakeCollection(self.store, self.uid, name)


class FakeUsers:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        assert name == "users"
        return self

    def document(self, uid):
        return FakeUserDoc(self.store, uid)


class FakeTransaction:
    def get(self, ref):
        return ref.get(transaction=self)

    def set(self, ref, data):
        ref.set(data)

    def _begin(self, *args, **kwargs):
        pass

    def _commit(self):
        pass

    def _rollback(self):
        pass

    def _clean_up(self):
        pass


class FakeFirestore:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeUsers(self.store).collection(name)

    def transaction(self):
        return FakeTransaction()


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-a")
    monkeypatch.setattr(service, "get_individual_profile", lambda uid: profile())
    monkeypatch.setattr(service, "_taxonomy_context", lambda role: service._taxonomy_context_from_store(role, FakeReferenceStore()))
    monkeypatch.setattr(service, "_assessment_evidence", lambda uid: ({}, True))
    monkeypatch.setattr(service.firestore, "transactional", lambda callback: callback)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def test_roadmap_maps_manual_and_canonical_skills_and_keeps_self_reported_levels(monkeypatch):
    monkeypatch.setattr(service, "_resource_rows", lambda skill_id, preferences: ([], "no catalog resource"))
    roadmap = service.build_personalized_roadmap(profile(), reference_store=FakeReferenceStore())
    assert roadmap.profile_context.target_role == "Software Developer"
    assert roadmap.profile_context.career_goals == ["Get my first job"]
    assert roadmap.profile_context.interests == ["Software Development"]
    assert roadmap.profile_context.weekly_learning_time == "2-5 hours"
    python = next(item for item in roadmap.milestones if item.skill_id == "python")
    assert python.self_reported_level == "Beginner"
    assert python.assessment_evidence["status"] == "not_available"
    manual = next(item for item in roadmap.milestones if item.skill_name == "My Side Project")
    assert manual.skill_id is None
    assert manual.skill_source == "manual_profile_skill"
    assert roadmap.prerequisites_available is False
    assert all(item.status == "not_started" and item.effort["estimated_minutes"] is None for item in roadmap.milestones)
    related = next(item for item in roadmap.milestones if item.skill_name == "Communication")
    assert related.skill_source == "onet_role_association"
    assert "not a verified qualification gap" in related.relation_note


def test_resource_preferences_prioritize_documentation_without_changing_catalog_sources(monkeypatch):
    documentation = SimpleNamespace(
        resource_id="python-docs", title="Python documentation", url="https://docs.python.org/3/",
        provider="Python", resource_type="documentation", verification_status="verified_official",
        provenance="official docs", license_attribution="Python docs", skill_ids=["python"],
    )
    practice = SimpleNamespace(
        resource_id="python-practice", title="Python practice", url="https://docs.python.org/3/",
        provider="Python", resource_type="practice", verification_status="verified_official",
        provenance="official docs", license_attribution="Python docs", skill_ids=["python"],
    )
    monkeypatch.setattr(service, "get_learning_catalog", lambda: (practice, documentation))
    monkeypatch.setattr(service, "get_verified_learning_videos", lambda: ())
    monkeypatch.setattr(service, "list_learning_resources", lambda **kwargs: [])

    rows, _ = service._resource_rows("python", ["Documentation"])

    assert [row["resource_type"] for row in rows] == ["documentation", "practice"]


def test_no_profile_skills_or_exact_role_reference_returns_safe_validation_error(monkeypatch):
    empty = profile(skills=[], target_role=None)
    monkeypatch.setattr(service, "_taxonomy_context", lambda role: (None, None, None, None, "No exact role match."))
    with pytest.raises(Exception) as error:
        service.build_personalized_roadmap(empty)
    assert getattr(error.value, "status_code", None) == 422


def test_roadmap_routes_require_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    assert client.get("/api/v1/learning/roadmap").status_code == 401
    assert client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "C"}], "target_duration_days": 60,
    }).status_code == 401


def test_roadmap_preview_rejects_invalid_firebase_token(client, monkeypatch):
    app.dependency_overrides.pop(get_current_user, None)
    monkeypatch.setattr(auth_dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(auth_dependencies.auth, "verify_id_token", lambda *args, **kwargs: (_ for _ in ()).throw(auth.InvalidIdTokenError("invalid token")))
    response = TestClient(app).post(
        "/api/v1/learning/roadmap/preview",
        json={"plan_type": "skill", "skills": [{"name": "C"}], "target_duration_days": 60},
        headers={"Authorization": "Bearer invalid-test-token"},
    )
    assert response.status_code == 401
    assert "invalid-test-token" not in response.text
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-a")


def test_generation_is_idempotent_progress_is_user_owned_and_saved(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    preview = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "combined", "skills": [{"name": "Python", "starting_level": "beginner"}], "target_role": "Software Developer", "preferences": ["Reading"]})
    assert preview.status_code == 201 and preview.json()["status"] == "preview"
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None
    approved = client.post(f"/api/v1/learning/roadmap/drafts/{preview.json()['draft_id']}/approve")
    assert approved.status_code == 200 and approved.json()["created"] is True
    original_id = approved.json()["roadmap"]["roadmap_id"]
    milestones = approved.json()["roadmap"]["milestones"]
    milestone0 = milestones[0]["milestone_id"]
    second = client.get("/api/v1/learning/roadmap")
    assert second.status_code == 200 and second.json()["roadmap"]["roadmap_id"] == original_id

    # Prerequisite gating: attempting to complete milestone 1 before milestone 0 should fail with 409
    if len(milestones) > 1:
        milestone1 = milestones[1]["milestone_id"]
        premature = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone1}", json={"status": "completed"})
        assert premature.status_code == 409
        assert "previous milestones" in premature.json()["detail"].lower()

    # Completing milestone 0 succeeds
    updated = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone0}", json={"status": "completed"})
    assert updated.status_code == 200
    assert updated.json()["roadmap"]["completed_count"] == 1
    m0_data = next(m for m in updated.json()["roadmap"]["milestones"] if m["milestone_id"] == milestone0)
    assert m0_data["status"] == "completed"
    assert m0_data["completion_source"] == "user_attested"
    assert m0_data["completed_at"] is not None

    # Idempotency: completing milestone 0 again succeeds without double incrementing
    repeat = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone0}", json={"status": "completed"})
    assert repeat.status_code == 200
    assert repeat.json()["roadmap"]["completed_count"] == 1

    # Verify persisted state on subsequent get
    regenerated = client.get("/api/v1/learning/roadmap")
    assert regenerated.status_code == 200
    assert regenerated.json()["roadmap"]["roadmap_id"] == original_id
    assert regenerated.json()["roadmap"]["completed_count"] == 1

    # User isolation: User B cannot access or modify User A's roadmap
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-b")
    try:
        other_user = client.get("/api/v1/learning/roadmap").json()["roadmap"]
        assert other_user is None
        other_patch = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone0}", json={"status": "completed"})
        assert other_patch.status_code == 404
    finally:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-a")


def test_firestore_failure_never_claims_roadmap_saved(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    response = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "Python"}]})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_assessment_history_stream_failure_is_unknown_not_a_roadmap_failure(monkeypatch):
    class FailedHistoryQuery:
        def order_by(self, *args, **kwargs):
            return self

        def limit(self, count):
            return self

        def stream(self):
            raise RuntimeError("history unavailable")

    class FailedUser:
        def collection(self, name):
            return FailedHistoryQuery()

    class FailedUsers:
        def document(self, uid):
            return FailedUser()

    class FailedClient:
        def collection(self, name):
            assert name == "users"
            return FailedUsers()

    monkeypatch.setattr(service, "get_firestore_client", FailedClient)
    assert service._assessment_evidence("user-a") == ({}, False)


def test_initial_roadmap_does_not_depend_on_assessment_question_availability(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    monkeypatch.setattr(service, "_assessment_evidence", lambda uid: ({}, False))
    response = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "combined", "skills": [{"name": "Python"}], "target_role": "Software Developer"})
    assert response.status_code == 201
    roadmap = response.json()["roadmap"]
    assert roadmap["assessment_evidence_status"] == "unknown"
    assert "could not be checked" in roadmap["profile_context"]["evidence_note"].lower()
    assert roadmap["milestones"]
    assert all(item["status"] == "not_started" for item in roadmap["milestones"])
    assert all(item["assessment_evidence"]["status"] == "unknown" for item in roadmap["milestones"])


def test_plan_preview_requires_explicit_approval_and_legacy_generate_is_disabled(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    response = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "My Manual Skill", "starting_level": "basic knowledge"}], "weekly_learning_time": "2 hours", "schedule_preference": "weekday evenings", "preferences": ["reading"], "target_duration_weeks": 8})
    assert response.status_code == 201
    assert response.json()["roadmap"]["status"] == "preview"
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None
    active = client.post(f"/api/v1/learning/roadmap/drafts/{response.json()['draft_id']}/approve")
    assert active.status_code == 200 and active.json()["roadmap"]["status"] == "active"
    assert active.json()["roadmap"]["plan_type"] == "skill"
    assert active.json()["roadmap"]["milestones"][0]["skill_source"] == "user_selected"
    assert active.json()["roadmap"]["milestones"][0]["starting_level_source"] == "user_provided"
    assert active.json()["roadmap"]["schedule_preference"] == "weekday evenings"
    assert active.json()["roadmap"]["target_duration_weeks"] == 8
    assert client.post("/api/v1/learning/roadmap/generate").status_code == 409


def test_target_duration_days_are_validated_and_preserved_in_preview(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    preview = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "Python"}], "target_duration_days": 60,
    })
    assert preview.status_code == 201
    assert preview.json()["roadmap"]["status"] == "preview"
    assert preview.json()["roadmap"]["target_duration_days"] == 60
    invalid = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "Python"}], "target_duration_days": 0,
    })
    assert invalid.status_code == 422


def test_draft_stage_edits_are_saved_and_approved_exactly(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    monkeypatch.setattr(learning_gemini.learning_gemini_service, "enrich", lambda **kwargs: None)
    preview = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "C", "starting_level": "beginner"}], "target_duration_days": 30,
    })
    assert preview.status_code == 201
    original = preview.json()["roadmap"]["milestones"][0]
    edited = client.patch(f"/api/v1/learning/roadmap/drafts/{preview.json()['draft_id']}", json={
        "target_duration_days": 30, "weekly_learning_time": "2-4 hours", "starting_level": "advanced", "stages": [{
            "milestone_id": original["milestone_id"], "title": "C foundations",
            "learning_objectives": ["Use variables and types", "Write a small function"],
            "practice_activity": "Write and compile a short C program.",
        }],
    })
    assert edited.status_code == 200
    assert edited.json()["roadmap"]["milestones"][0]["title"] == "C foundations"
    assert edited.json()["roadmap"]["target_duration_days"] == 30
    assert edited.json()["roadmap"]["milestones"][0]["self_reported_level"] == "advanced"
    assert edited.json()["roadmap"]["milestones"][0]["starting_level_source"] == "user_provided"
    assert edited.json()["roadmap"]["milestones"][0]["assessment_evidence"]["proficiency_verified"] is False
    approved = client.post(f"/api/v1/learning/roadmap/drafts/{preview.json()['draft_id']}/approve")
    assert approved.status_code == 200
    active_stage = approved.json()["roadmap"]["milestones"][0]
    assert active_stage["title"] == "C foundations"
    assert active_stage["learning_objectives"] == ["Use variables and types", "Write a small function"]
    assert active_stage["practice_activity"] == "Write and compile a short C program."
    assert approved.json()["roadmap"]["target_duration_days"] == 30
    assert active_stage["self_reported_level"] == "advanced"


def test_c_skill_preview_is_canonical_and_stays_a_draft_until_approval(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    monkeypatch.setattr(learning_gemini.learning_gemini_service, "enrich", lambda **kwargs: None)

    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "C"}], "target_duration_days": 30,
    })

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "preview"
    assert draft["roadmap"]["target_duration_days"] == 30
    assert draft["roadmap"]["profile_context"]["target_role"] is None
    assert draft["roadmap"]["profile_context"]["career_goals"] == []
    c_skill = next(item for item in draft["roadmap"]["milestones"] if item["skill_name"] == "C")
    assert c_skill["skill_id"] == "c"
    assert c_skill["skill_source"] == "user_selected"
    assert c_skill["content_source"] == "deterministic"
    assert "practice guidance" in c_skill["explanation"].lower()
    skill_text = " ".join([
        draft["roadmap"]["title"], draft["roadmap"]["summary"],
        *(value for item in draft["roadmap"]["milestones"] for value in [
            item["title"], item["explanation"], item["completion_criterion"],
            *(item.get("learning_objectives") or []), item.get("practice_activity") or "",
        ]),
    ]).lower()
    assert "ui/ux designer" not in skill_text
    assert "get my first job" not in skill_text
    assert "python" not in c_skill["completion_criterion"].lower()
    draft_document = store.store["roadmap-user-a"]["learning_roadmap_drafts"]["pending"]["roadmap"]
    encode_value(draft_document)  # Exercise Firestore's actual value encoder, including HttpUrl fields.
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None

    approved = client.post(f"/api/v1/learning/roadmap/drafts/{draft['draft_id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["roadmap"]["status"] == "active"
    assert next(item for item in approved.json()["roadmap"]["milestones"] if item["skill_id"] == "c")
    encode_value(store.store["roadmap-user-a"]["learning_roadmaps"]["current"])


def test_exact_c_programming_goal_isolated_from_uiux_profile_without_verified_resources(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    monkeypatch.setattr(service, "get_individual_profile", lambda _uid: profile(target_role="UI/UX Designer"))
    monkeypatch.setattr(service, "_resource_rows", lambda _skill_id, _preferences: ([], "No verified resource available yet."))
    monkeypatch.setattr(learning_gemini.learning_gemini_service, "enrich", lambda **kwargs: None)
    monkeypatch.setattr(curriculum_service, "get_learning_catalog", lambda: [])
    monkeypatch.setattr(curriculum_service, "get_firestore_client", lambda: store)
    monkeypatch.setattr(curriculum_service, "get_verified_learning_videos", lambda: [])
    monkeypatch.setattr(curriculum_service, "list_learning_videos", lambda **_kwargs: SimpleNamespace(fallback=None))
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])

    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "C Programming", "starting_level": "beginner"}],
        "target_duration_days": 30,
    })
    assert response.status_code == 201
    draft = response.json()
    roadmap = draft["roadmap"]
    assert roadmap["target_duration_days"] == 30
    assert roadmap["profile_context"]["target_role"] is None
    assert roadmap["profile_context"]["career_goals"] == []
    assert len(roadmap["milestones"]) == 5
    milestone = roadmap["milestones"][0]
    canonical = canonical_skill_id("C Programming")
    assert milestone["skill_name"] == ("C" if canonical == "c" else "C Programming")
    assert milestone["skill_id"] == canonical
    assert milestone["self_reported_level"] == "beginner"
    assert milestone["starting_level_source"] == "user_provided"
    assert milestone["assessment_evidence"]["proficiency_verified"] is False
    assert milestone["resources"] == []
    skill_text = " ".join([
        roadmap["title"], roadmap["summary"], milestone["title"], milestone["explanation"],
        milestone["practice_activity"], milestone["completion_criterion"], *milestone["learning_objectives"],
    ]).casefold()
    assert "c programming" in skill_text or " c " in f" {skill_text} "
    assert "ui/ux designer" not in skill_text
    assert "first job" not in skill_text
    assert "apply c to a ui" not in skill_text

    approved = client.post(f"/api/v1/learning/roadmap/drafts/{draft['draft_id']}/approve")
    assert approved.status_code == 200
    active = client.get("/api/v1/learning/roadmap")
    assert active.status_code == 200
    assert active.json()["roadmap"]["status"] == "active"
    assert active.json()["roadmap"]["title"] == approved.json()["roadmap"]["title"]
    curriculum_response = client.get("/api/v1/learning/curriculum")
    assert curriculum_response.status_code == 200
    curriculum = curriculum_response.json()["curriculum"]
    assert curriculum["title"] == active.json()["roadmap"]["title"]
    chapter = curriculum["levels"][0]["chapters"][0]
    assert chapter["resource_required"] is False
    assert chapter["status"] == "available"
    assert all(resource["can_attest_completion"] is False for resource in chapter["resources"])
    assert "No verified resource" in chapter["completion_policy"]


def test_draft_firestore_serialization_failure_is_503_and_logs_no_exception_data(client, monkeypatch, caplog):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())

    class BrokenDraft:
        def document(self, _key):
            return self

        def set(self, _data):
            raise TypeError("private-url-or-payload-must-not-be-logged")

    monkeypatch.setattr(service, "_draft_collection", lambda _uid: BrokenDraft())
    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "C"}], "target_duration_days": 60,
    })

    assert response.status_code == 503
    assert response.json()["detail"] == "The plan preview could not be saved safely."
    assert "stage=draft_save" in caplog.text
    assert "error_class=TypeError" in caplog.text
    assert "unsupported field type" in caplog.text
    assert "private-url-or-payload" not in caplog.text
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None


def test_learning_gemini_enriches_only_learning_content_for_missing_resource_skill(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    monkeypatch.setattr(learning_gemini.learning_gemini_service, "enrich", lambda **kwargs: [{
        "skill_name": "Rust",
        "learning_objectives": ["Use variables", "Organize a small program"],
        "practice_activity": "Write a small command-line program and test its inputs.",
        "estimated_minutes": 45,
    }])

    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "Rust"}], "target_duration_days": 60,
    })

    assert response.status_code == 201
    payload = response.json()
    milestone = next(item for item in payload["roadmap"]["milestones"] if item["skill_id"] == "rust")
    assert milestone["content_source"] == "learning_gemini"
    assert milestone["learning_objectives"] == ["Use variables", "Organize a small program"]
    assert milestone["practice_activity"].startswith("Write a small command-line program")
    assert milestone["effort"]["estimated_minutes"] == 45
    assert not any(resource["verification_status"] in {"verified_official", "verified_youtube_listing"} for resource in milestone["resources"])
    assert "learning-test-secret" not in response.text
    assert payload["status"] == "preview"
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None


def test_local_skill_search_and_unmatched_manual_role_do_not_invent_requirements(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    suggestions = client.get("/api/v1/learning/roadmap/options?kind=skill&query=py")
    assert suggestions.status_code == 200
    assert "Python" in suggestions.json()["skills"]
    preview = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "role", "target_role": "Imaginary Orbital Skill Wrangler", "target_duration_days": 90,
    })
    assert preview.status_code == 201
    roadmap = preview.json()["roadmap"]
    assert roadmap["profile_context"]["target_role"] == "Imaginary Orbital Skill Wrangler"
    assert roadmap["milestones"] == []
    assert "no matching o*net or esco" in roadmap["summary"].lower()


def test_saved_profile_level_stays_self_reported_when_wizard_has_no_override(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())

    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "Python"}],
    })

    assert response.status_code == 201
    python = next(item for item in response.json()["roadmap"]["milestones"] if item["skill_id"] == "python")
    assert python["self_reported_level"] == "Beginner"
    assert python["starting_level_source"] == "self_reported_onboarding"


def test_explicit_not_sure_clears_onboarding_level(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    response = client.post("/api/v1/learning/roadmap/preview", json={
        "plan_type": "skill", "skills": [{"name": "Python", "starting_level": "not sure"}],
    })
    assert response.status_code == 201
    python = next(item for item in response.json()["roadmap"]["milestones"] if item["skill_id"] == "python")
    assert python["self_reported_level"] is None
    assert python["starting_level_source"] is None


def test_plan_request_rejects_incomplete_mode_and_does_not_use_client_uid(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    invalid = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "combined", "skills": [{"name": "Python"}]})
    assert invalid.status_code == 422
    invalid_level = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "Python", "starting_level": "expert"}]})
    assert invalid_level.status_code == 422
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-b")
    try:
        assert client.get("/api/v1/learning/roadmap?uid=roadmap-user-a").json()["roadmap"] is None
    finally:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="roadmap-user-a")


def test_role_only_plan_uses_exact_taxonomy_associations_without_fake_job_data(client, monkeypatch):
    monkeypatch.setattr(service, "get_firestore_client", lambda: FakeFirestore())
    response = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "role", "target_role": "Software Developer", "location": "Chennai", "work_preference": "hybrid"})
    assert response.status_code == 201
    roadmap = response.json()["roadmap"]
    assert roadmap["profile_context"]["target_role"] == "Software Developer"
    assert roadmap["profile_context"]["location"] == "Chennai"
    assert roadmap["profile_context"]["work_preference"] == "hybrid"
    assert all(item["skill_source"] == "onet_role_association" for item in roadmap["milestones"])


def test_plan_preview_can_be_cancelled_without_activating_a_roadmap(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    preview = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "Python"}]})
    draft_id = preview.json()["draft_id"]
    cancelled = client.delete(f"/api/v1/learning/roadmap/drafts/{draft_id}")
    assert cancelled.status_code == 204
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None
    assert client.post(f"/api/v1/learning/roadmap/drafts/{draft_id}/approve").status_code == 409


def test_delete_active_roadmap_clears_roadmap_and_enables_new_plan(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    preview = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "Python"}]})
    draft_id = preview.json()["draft_id"]
    approved = client.post(f"/api/v1/learning/roadmap/drafts/{draft_id}/approve")
    assert approved.status_code == 200
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is not None

    deleted = client.delete("/api/v1/learning/roadmap")
    assert deleted.status_code == 204
    assert client.get("/api/v1/learning/roadmap").json()["roadmap"] is None


def test_assessment_checkpoint_gating_on_milestone_completion(client, monkeypatch):
    store = FakeFirestore()
    monkeypatch.setattr(service, "get_firestore_client", lambda: store)
    preview = client.post("/api/v1/learning/roadmap/preview", json={"plan_type": "skill", "skills": [{"name": "Python"}]})
    draft_id = preview.json()["draft_id"]
    approved = client.post(f"/api/v1/learning/roadmap/drafts/{draft_id}/approve")
    milestone = approved.json()["roadmap"]["milestones"][0]["milestone_id"]

    # Mock assessment service to report approved questions available
    from app.models.assessment import AssessmentSummary
    import app.services.assessment_service as asm_service
    fake_summary = [AssessmentSummary(skill_id="python", skill_name="Python", question_count=10, supported_types=["mcq"])]
    monkeypatch.setattr(asm_service, "list_assessment_summaries", lambda _skill: fake_summary)

    # 1. Without attempt: completion fails with 409
    attempt_fail = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone}", json={"status": "completed"})
    assert attempt_fail.status_code == 409
    assert "at least 70%" in attempt_fail.json()["detail"].lower()

    # 2. With failing attempt (< 70%): completion fails with 409
    attempts_col = store.collection("users").document("roadmap-user-a").collection("learning_assessment_attempts")
    attempts_col.document("attempt-1").set({
        "attempt_id": "attempt-1",
        "skill_id": "python",
        "status": "completed",
        "percentage": 65,
    })
    failing_attempt = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone}", json={"status": "completed"})
    assert failing_attempt.status_code == 409
    assert "at least 70%" in failing_attempt.json()["detail"].lower()

    # 3. With passing attempt (>= 70%): completion succeeds with 200
    attempts_col.document("attempt-2").set({
        "attempt_id": "attempt-2",
        "skill_id": "python",
        "status": "completed",
        "percentage": 85,
    })
    passing_attempt = client.patch(f"/api/v1/learning/roadmap/milestones/{milestone}", json={"status": "completed"})
    assert passing_attempt.status_code == 200
    assert passing_attempt.json()["roadmap"]["completed_count"] == 1
    assert passing_attempt.json()["roadmap"]["milestones"][0]["status"] == "completed"


def test_milestone_cors_preflight_patch_options_returns_ok(client):
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    response = client.options("/api/v1/learning/roadmap/milestones/milestone-1", headers=headers)
    assert response.status_code == 200
    assert "PATCH" in response.headers.get("access-control-allow-methods", "")



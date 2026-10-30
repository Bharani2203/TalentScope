from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from firebase_admin import firestore
from app.analytics.skill_registry import canonical_skill_id
from app.models.curriculum import ChapterProgressEventRequest
from app.models.roadmap import PersonalizedRoadmap, RoadmapMilestone, RoadmapProfileContext
from app.services import learning_curriculum_service as curriculum_service


class Snapshot:
    def __init__(self, key, value):
        self.id, self.value, self.exists = key, value, value is not None

    def to_dict(self):
        return self.value


class Ref:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return Collection(self.db, self.path + (name,))

    def get(self, transaction=None):
        return Snapshot(self.path[-1], self.db.rows.get(self.path))

    def set(self, value):
        self.db.rows[self.path] = value


class Collection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, key):
        return Ref(self.db, self.path + (key,))

    def stream(self, transaction=None):
        depth = len(self.path) + 1
        return [Snapshot(path[-1], value) for path, value in self.db.rows.items()
                if len(path) == depth and path[:-1] == self.path]


class FakeDB:
    def __init__(self, roadmap):
        self.rows = {("users", "phase-d-user", "learning_roadmaps", "current"): roadmap.model_dump(mode="python")}

    def collection(self, name):
        return Collection(self, (name,))

    def transaction(self):
        return FakeTransaction()

    def ref(self, *path):
        return Ref(self, tuple(path))


class FakeTransaction:
    def set(self, ref, value):
        ref.set(value)


def roadmap_with_python():
    now = datetime.now(timezone.utc)
    return PersonalizedRoadmap(
        roadmap_id="roadmap-phase-d-test", status="active", title="Learn Python",
        summary="A source-based Python plan", generated_at=now, updated_at=now,
        profile_context=RoadmapProfileContext(evidence_note="Test data"),
        relationship_note="No prerequisites are inferred", assessment_evidence_status="not_available",
        completed_count=0,
        milestones=[RoadmapMilestone(
            milestone_id="milestone-python", sequence=1, title="Python foundations",
            explanation="Learn the documented foundations of Python.", skill_id=canonical_skill_id("Python"),
            skill_name="Python", skill_source="user_selected", assessment_evidence={}, effort={},
            completion_criterion="Complete a small Python practice exercise.",
        )],
    )


def test_approved_plan_builds_source_matched_chapter_and_pending_checkpoint(monkeypatch):
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])
    curriculum = curriculum_service._build_curriculum(roadmap_with_python(), {})
    chapter = curriculum.levels[0].chapters[0]
    assert chapter.status == "available"
    assert chapter.objective == "Learn the documented foundations of Python."
    assert chapter.resources
    assert all(resource.activity_id and resource.provenance for resource in chapter.resources)
    assert chapter.assessment_checkpoint.status == "unavailable"
    assert "human review" in chapter.assessment_checkpoint.policy.lower()
    assert chapter.assessment_checkpoint.required_when_available is True


def test_chapter_progress_is_empty_without_saved_events(monkeypatch):
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])
    curriculum = curriculum_service._build_curriculum(roadmap_with_python(), {})
    chapter = curriculum.levels[0].chapters[0]
    assert chapter.progress.status == "not_started"
    assert chapter.progress.events == []
    assert chapter.progress.completed_at is None


def test_draft_questions_are_not_exposed_as_live_checkpoints(monkeypatch):
    # The assessment service returns only human-approved summaries. The Phase D
    # chapter builder consumes that filtered contract, never the draft bank.
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])
    curriculum = curriculum_service._build_curriculum(roadmap_with_python(), {})
    checkpoint = curriculum.levels[0].chapters[0].assessment_checkpoint
    assert checkpoint.status == "unavailable"
    assert checkpoint.question_count == 0
    assert checkpoint.result is None


def test_valid_chapter_without_verified_resources_is_available_and_practice_completes(monkeypatch):
    roadmap = roadmap_with_python()
    db = FakeDB(roadmap)
    monkeypatch.setattr(curriculum_service, "get_firestore_client", lambda: db)
    monkeypatch.setattr(curriculum_service, "get_learning_catalog", lambda: [])
    monkeypatch.setattr(curriculum_service, "get_verified_learning_videos", lambda: [])
    monkeypatch.setattr(curriculum_service, "list_learning_videos", lambda **_kwargs: type("Videos", (), {"fallback": None})())
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])
    monkeypatch.setattr(firestore, "transactional", lambda fn: lambda tx: fn(tx))

    initial = curriculum_service.load_learning_curriculum("phase-d-user").curriculum
    chapter = initial.levels[0].chapters[0]
    assert chapter.status == "available"
    assert chapter.resources == []
    assert chapter.resource_required is False
    assert "No verified resource" in chapter.completion_policy

    def submit(event_type, **kwargs):
        return curriculum_service.record_chapter_event("phase-d-user", chapter.chapter_id,
            ChapterProgressEventRequest(event_id=uuid4(), event_type=event_type, **kwargs))

    opened = submit("chapter_started").curriculum.levels[0].chapters[0]
    assert opened.status == "in_progress"
    assert opened.progress.completed_at is None
    completed = submit("practice_submitted", practice_summary="I wrote and ran a small Python function.", learner_attested=True)
    saved = completed.curriculum.levels[0].chapters[0]
    assert saved.status == "completed"
    assert saved.progress.practice_summary == "I wrote and ran a small Python function."
    assert saved.progress.completed_at is not None


def test_persisted_chapter_gates_separate_open_from_attested_completion(monkeypatch):
    roadmap = roadmap_with_python()
    roadmap.milestones.append(roadmap.milestones[0].model_copy(update={
        "milestone_id": "milestone-python-next", "sequence": 2, "title": "Python practice"
    }))
    db = FakeDB(roadmap)
    monkeypatch.setattr(curriculum_service, "get_firestore_client", lambda: db)
    monkeypatch.setattr(curriculum_service, "list_assessment_summaries", lambda _skill_id: [])
    monkeypatch.setattr(firestore, "transactional", lambda fn: lambda tx: fn(tx))
    curriculum = curriculum_service.load_learning_curriculum("phase-d-user").curriculum
    first, second = curriculum.levels[0].chapters
    assert first.status == "available" and second.status == "locked"
    assert curriculum_service.load_learning_curriculum("different-user").curriculum is None
    assert ("users", "different-user", "learning_roadmaps", "current") not in db.rows
    resource = next(item for item in first.resources if item.can_attest_completion)

    def submit(event_type, **kwargs):
        return curriculum_service.record_chapter_event("phase-d-user", first.chapter_id,
            ChapterProgressEventRequest(event_id=uuid4(), event_type=event_type, **kwargs))

    with pytest.raises(HTTPException) as not_opened:
        submit("resource_completed", activity_id=resource.activity_id, learner_attested=True)
    assert not_opened.value.status_code == 409
    opened = submit("resource_opened", activity_id=resource.activity_id)
    assert opened.curriculum.levels[0].chapters[0].progress.status == "in_progress"
    assert opened.curriculum.levels[0].chapters[1].status == "locked"
    after_resource = submit("resource_completed", activity_id=resource.activity_id, learner_attested=True)
    assert after_resource.curriculum.levels[0].chapters[0].status == "in_progress"
    assert after_resource.curriculum.levels[0].chapters[1].status == "locked"
    completed = submit("practice_submitted", practice_summary="Built and ran a small example.", learner_attested=True)
    assert completed.curriculum.levels[0].chapters[0].status == "completed"
    assert completed.curriculum.levels[0].chapters[1].status == "available"
    saved_chapter = completed.curriculum.levels[0].chapters[0]
    saved_event_count = len(saved_chapter.progress.events)
    duplicate = submit("practice_submitted", practice_summary="A later duplicate should not replace saved work.", learner_attested=True)
    restored = curriculum_service.load_learning_curriculum("phase-d-user").curriculum.levels[0].chapters[0]
    assert duplicate.curriculum.levels[0].chapters[0].progress.practice_summary == "Built and ran a small example."
    assert restored.status == "completed"
    assert restored.progress.practice_summary == "Built and ran a small example."
    assert len(restored.progress.events) == saved_event_count


def test_firestore_read_failure_does_not_return_empty_curriculum(monkeypatch):
    monkeypatch.setattr(curriculum_service, "get_firestore_client", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    with pytest.raises(HTTPException) as unavailable:
        curriculum_service.load_learning_curriculum("phase-d-user")
    assert unavailable.value.status_code == 503

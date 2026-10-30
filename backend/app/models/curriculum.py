from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class CurriculumResource(BaseModel):
    activity_id: str
    title: str
    url: HttpUrl
    provider: str
    kind: Literal["documentation", "course", "practice", "video", "video_search"]
    verification_status: str
    provenance: str
    license_attribution: str
    can_attest_completion: bool


class ChapterAssessmentCheckpoint(BaseModel):
    status: Literal["available", "unavailable"]
    skill_id: str | None = None
    question_count: int = Field(default=0, ge=0)
    required_when_available: bool = True
    policy: str
    result: dict | None = None


class ChapterResourceProgress(BaseModel):
    activity_id: str
    opened_at: datetime | None = None
    completed_at: datetime | None = None
    completion_source: Literal["user_attested"] | None = None


class ChapterProgressEvent(BaseModel):
    event_id: str
    event_type: Literal[
        "chapter_started", "resource_opened", "resource_completed",
        "practice_submitted", "assessment_completed", "chapter_completed",
        "milestone_completed",
    ]
    occurred_at: datetime
    activity_id: str | None = None
    label: str
    details: str | None = None


class ChapterProgressSnapshot(BaseModel):
    chapter_id: str
    roadmap_id: str
    status: Literal["not_started", "in_progress", "completed"] = "not_started"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    resources: list[ChapterResourceProgress] = Field(default_factory=list)
    practice_submitted_at: datetime | None = None
    practice_summary: str | None = None
    assessment_result: dict | None = None
    events: list[ChapterProgressEvent] = Field(default_factory=list)
    updated_at: datetime | None = None


class LearningChapter(BaseModel):
    chapter_id: str
    milestone_id: str
    sequence: int = Field(ge=1, le=30)
    title: str
    objective: str
    learning_objectives: list[str] = Field(default_factory=list, max_length=5)
    required_concepts: list[str] = Field(default_factory=list)
    content_status: Literal["ready", "incomplete"]
    content_note: str | None = None
    resources: list[CurriculumResource] = Field(default_factory=list, max_length=24)
    practice_activity: str | None = None
    completion_policy: str
    resource_required: bool = True
    assessment_checkpoint: ChapterAssessmentCheckpoint
    unlocked: bool = False
    status: Literal["locked", "available", "in_progress", "completed", "content_unavailable"]
    progress: ChapterProgressSnapshot
    prior_milestone_completed: bool = False


class LearningLevel(BaseModel):
    level_id: str
    title: str
    sequence: int = Field(ge=1, le=30)
    note: str
    chapters: list[LearningChapter] = Field(default_factory=list, max_length=30)


class LearningCurriculum(BaseModel):
    roadmap_id: str
    version: str = "phase-d-v1"
    title: str
    goal: str | None = None
    target_role: str | None = None
    level_note: str
    levels: list[LearningLevel] = Field(default_factory=list, max_length=30)


class LearningCurriculumResponse(BaseModel):
    curriculum: LearningCurriculum | None
    message: str | None = None


class ChapterProgressEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: Literal[
        "chapter_started", "resource_opened", "resource_completed",
        "practice_submitted", "assessment_completed",
    ]
    activity_id: str | None = Field(default=None, min_length=1, max_length=120)
    attempt_id: str | None = Field(default=None, min_length=1, max_length=80)
    practice_summary: str | None = Field(default=None, min_length=1, max_length=500)
    learner_attested: bool = False

    @model_validator(mode="after")
    def validate_event_payload(self) -> "ChapterProgressEventRequest":
        if self.event_type in {"resource_opened", "resource_completed"} and not self.activity_id:
            raise ValueError("A resource activity ID is required for resource events.")
        if self.event_type == "practice_submitted" and not self.practice_summary:
            raise ValueError("A short practice summary is required.")
        if self.event_type == "assessment_completed" and not self.attempt_id:
            raise ValueError("A saved assessment attempt ID is required.")
        if self.event_type in {"resource_completed", "practice_submitted"} and not self.learner_attested:
            raise ValueError("Explicit learner confirmation is required.")
        return self

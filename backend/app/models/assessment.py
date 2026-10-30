from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssessmentSummary(BaseModel):
    skill_id: str
    skill_name: str
    question_count: int = Field(ge=0)
    supported_types: list[Literal["mcq", "scenario"]]


class AssessmentList(BaseModel):
    assessments: list[AssessmentSummary]


class PublicOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=2000)


class AssessmentQuestion(BaseModel):
    question_id: str
    skill_ids: list[str]
    topic_ids: list[str]
    question_type: Literal["mcq", "scenario"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    question_text: str
    options: list[PublicOption] | None = None
    max_points: int = Field(ge=1, le=100)


class AssessmentAttemptStarted(BaseModel):
    attempt_id: str
    skill_id: str
    status: Literal["in_progress"]
    question_count: int
    questions: list[AssessmentQuestion]


class AssessmentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=10000)


class AssessmentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, AssessmentAnswer] = Field(min_length=1, max_length=30)


class AssessmentResult(BaseModel):
    attempt_id: str
    status: Literal["completed"]
    skill_id: str
    score: int = Field(ge=0)
    max_score: int = Field(gt=0)
    percentage: int = Field(ge=0, le=100)
    correct_count: int = Field(ge=0)
    question_count: int = Field(gt=0)
    evidence_type: Literal["assessment_derived_provisional"] = "assessment_derived_provisional"
    proficiency: Literal["provisional"]
    completed_at: datetime


class AssessmentHistoryItem(BaseModel):
    attempt_id: str
    skill_id: str
    status: Literal["in_progress", "completed"]
    question_count: int
    score: int | None = None
    max_score: int | None = None
    percentage: int | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AssessmentHistory(BaseModel):
    attempts: list[AssessmentHistoryItem]
    count: int = Field(ge=0)


class AssessmentReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=10, max_length=2000)


class AssessmentReviewItem(BaseModel):
    question_id: str
    question: dict[str, Any]
    private_answer_record: dict[str, Any]
    status: str
    content_version: str
    previous_review: dict[str, Any] | None = None


class AssessmentReviewQueue(BaseModel):
    items: list[AssessmentReviewItem]
    count: int = Field(ge=0)


class AssessmentReviewResult(BaseModel):
    question_id: str
    decision: Literal["approved", "rejected"]
    reviewer_uid: str
    reviewed_at: datetime
    content_version: str
    live_eligible: bool = False
    message: str


class AssessmentSuspiciousEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["tab_blur", "fullscreen_exit", "copy_paste_attempt", "multiple_windows"]
    attempt_id: str = Field(min_length=1, max_length=100)


class AssessmentRestrictionStatus(BaseModel):
    is_restricted: bool
    strike_count: int = Field(ge=0)
    restriction_until: datetime | None = None
    reason: str | None = None
    active_strikes_remaining: int = Field(ge=0)

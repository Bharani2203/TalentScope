from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


RoadmapMilestoneStatus = Literal["not_started", "in_progress", "completed"]


class RoadmapResource(BaseModel):
    resource_id: str
    title: str
    url: HttpUrl
    provider: str
    resource_type: Literal["documentation", "course", "video_search", "practice", "video"]
    verification_status: str
    provenance: str
    license_attribution: str
    video_id: str | None = None
    thumbnail_url: HttpUrl | None = None


class RoadmapMilestone(BaseModel):
    milestone_id: str
    sequence: int = Field(ge=1, le=30)
    title: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1, max_length=1200)
    learning_objectives: list[str] = Field(default_factory=list, max_length=5)
    practice_activity: str | None = Field(default=None, max_length=1000)
    content_source: Literal["deterministic", "learning_gemini"] = "deterministic"
    skill_id: str | None = None
    skill_name: str = Field(min_length=1, max_length=160)
    skill_source: Literal["onboarding_self_report", "onet_role_association", "esco_role_association", "manual_profile_skill", "user_selected"]
    self_reported_level: str | None = None
    starting_level_source: Literal["self_reported_onboarding", "user_provided"] | None = None
    assessment_evidence: dict
    relation_note: str | None = None
    resources: list[RoadmapResource] = Field(default_factory=list, max_length=12)
    resource_note: str | None = None
    effort: dict
    completion_criterion: str = Field(min_length=1, max_length=1000)
    status: RoadmapMilestoneStatus = "not_started"
    completion_source: Literal["user_attested"] | None = None
    completed_at: datetime | None = None


class RoadmapProfileContext(BaseModel):
    target_role: str | None = None
    career_goals: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    learning_preferences: list[str] = Field(default_factory=list)
    weekly_learning_time: str | None = None
    experience: str | None = None
    study_field: str | None = None
    location: str | None = None
    work_preference: str | None = None
    skills: list[dict] = Field(default_factory=list)
    onboarding_complete: bool = False
    evidence_note: str


class PersonalizedRoadmap(BaseModel):
    roadmap_id: str
    status: Literal["preview", "active"] = "active"
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1200)
    generated_at: datetime
    updated_at: datetime
    profile_context: RoadmapProfileContext
    taxonomy_source: str | None = None
    taxonomy_reference_id: str | None = None
    taxonomy_version: str | None = None
    relationship_note: str
    prerequisites_available: bool = False
    assessment_evidence_status: Literal["available_provisional", "not_available", "unknown"]
    milestones: list[RoadmapMilestone] = Field(default_factory=list, max_length=30)
    completed_count: int = Field(ge=0)
    plan_type: Literal["skill", "role", "combined"] = "role"
    plan_goal: str | None = None
    plan_preferences: list[str] = Field(default_factory=list, max_length=12)
    target_duration_weeks: int | None = Field(default=None, ge=1, le=104)
    target_duration_days: int | None = Field(default=None, ge=1, le=3650)
    schedule_preference: str | None = Field(default=None, max_length=120)
    work_preference: str | None = Field(default=None, max_length=80)


class RoadmapStateResponse(BaseModel):
    roadmap: PersonalizedRoadmap | None
    created: bool = False


class RoadmapPlanSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    starting_level: Literal["beginner", "basic knowledge", "intermediate", "advanced", "not sure"] | None = None


class RoadmapPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_type: Literal["skill", "role", "combined"]
    skills: list[RoadmapPlanSkill] = Field(default_factory=list, max_length=20)
    target_role: str | None = Field(default=None, max_length=120)
    goal: str | None = Field(default=None, max_length=500)
    weekly_learning_time: str | None = Field(default=None, max_length=80)
    preferences: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=12)
    target_duration_weeks: int | None = Field(default=None, ge=1, le=104)
    target_duration_days: int | None = Field(default=None, ge=1, le=3650)
    schedule_preference: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    work_preference: str | None = Field(default=None, max_length=80)


class RoadmapDraftResponse(BaseModel):
    draft_id: str
    status: Literal["preview"] = "preview"
    roadmap: PersonalizedRoadmap


class RoadmapDraftStageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    milestone_id: str | None = Field(default=None, max_length=100)
    based_on_milestone_id: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    learning_objectives: list[Annotated[str, Field(min_length=1, max_length=180)]] = Field(min_length=1, max_length=3)
    practice_activity: str = Field(min_length=10, max_length=1000)


class RoadmapDraftEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_duration_days: int = Field(ge=1, le=3650)
    weekly_learning_time: str | None = Field(default=None, max_length=80)
    starting_level: Literal["beginner", "basic knowledge", "intermediate", "advanced", "not sure"] | None = None
    stages: list[RoadmapDraftStageEdit] = Field(min_length=1, max_length=30)


class MilestoneProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoadmapMilestoneStatus

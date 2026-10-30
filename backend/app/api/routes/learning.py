from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.curriculum import ChapterProgressEventRequest, LearningCurriculumResponse
from app.models.learning import (
    LearningActivityProgressList, LearningActivityProgressUpdate,
    LearningResourceList, LearningVideoList, ResourceType,
)
from app.services.learning_catalog_service import (
    list_learning_resources, list_learning_videos, resolve_learning_skill_id, resolve_topic_video_record,
)
from app.services.learning_progress_service import get_learning_progress, update_learning_progress
from app.services.learning_curriculum_service import load_learning_curriculum, record_chapter_event, get_topic_lesson_detail
from app.services.code_execution_service import (
    CodeRunRequest,
    CodeRunResponse,
    CodingEvaluationRequest,
    CodingEvaluationResponse,
    execute_code,
    evaluate_coding_assessment,
)

router = APIRouter(prefix="/learning", tags=["learning"], dependencies=[Depends(get_current_user)])
_TOPIC_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@router.get("/curriculum", response_model=LearningCurriculumResponse)
def read_learning_curriculum(current_user: AuthenticatedUser = Depends(get_current_user)) -> LearningCurriculumResponse:
    return load_learning_curriculum(current_user.uid)


@router.post("/chapters/{chapter_id}/events", response_model=LearningCurriculumResponse)
def write_chapter_event(
    chapter_id: str,
    request: ChapterProgressEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningCurriculumResponse:
    return record_chapter_event(current_user.uid, chapter_id, request)


@router.get("/resources", response_model=LearningResourceList)
def list_resources(
    skill_id: str | None = Query(default=None, min_length=1, max_length=80),
    topic_id: str | None = Query(default=None, min_length=1, max_length=100),
    resource_type: ResourceType | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningResourceList:
    canonical_id = None
    if skill_id:
        canonical_id = resolve_learning_skill_id(skill_id)
        if canonical_id is None:
            raise HTTPException(status_code=422, detail="Unknown skill ID.")
    if topic_id and not _TOPIC_ID.fullmatch(topic_id):
        raise HTTPException(status_code=422, detail="Invalid topic ID.")
    try:
        resources = list_learning_resources(
            skill_id=canonical_id, topic_id=topic_id, resource_type=resource_type, limit=limit
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="The learning resource catalog is temporarily unavailable.") from exc
    return LearningResourceList(resources=resources, count=len(resources))


@router.get("/resources/by-skill/{skill_id}", response_model=LearningResourceList)
def resources_by_skill(
    skill_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningResourceList:
    canonical_id = resolve_learning_skill_id(skill_id)
    if canonical_id is None:
        raise HTTPException(status_code=422, detail="Unknown skill ID.")
    try:
        resources = list_learning_resources(skill_id=canonical_id, limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="The learning resource catalog is temporarily unavailable.") from exc
    return LearningResourceList(resources=resources, count=len(resources))


@router.get("/videos", response_model=LearningVideoList)
def list_videos(
    skill_id: str | None = Query(default=None, min_length=1, max_length=80),
    topic_id: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=8, ge=1, le=30),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningVideoList:
    canonical_id = None
    if skill_id:
        canonical_id = resolve_learning_skill_id(skill_id)
        if canonical_id is None:
            raise HTTPException(status_code=422, detail="Unknown skill ID.")
    if topic_id and not _TOPIC_ID.fullmatch(topic_id):
        raise HTTPException(status_code=422, detail="Invalid topic ID.")
    try:
        return list_learning_videos(skill_id=canonical_id, topic_id=topic_id, limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="The learning video catalog is temporarily unavailable.") from exc


@router.get("/progress", response_model=LearningActivityProgressList)
def read_learning_progress(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningActivityProgressList:
    return get_learning_progress(current_user.uid)


@router.put("/progress/{activity_id}", response_model=LearningActivityProgressList)
def set_learning_progress(
    activity_id: str,
    update: LearningActivityProgressUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> LearningActivityProgressList:
    return update_learning_progress(current_user.uid, activity_id, update.status)


@router.post("/compiler/run", response_model=CodeRunResponse)
def run_sandbox_code(
    request: CodeRunRequest,
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> CodeRunResponse:
    """Executes sample code in an isolated remote container sandbox."""
    return execute_code(
        language=request.language,
        source_code=request.source_code,
        stdin=request.stdin,
    )


@router.post("/compiler/evaluate", response_model=CodingEvaluationResponse)
def evaluate_assessment_code(
    request: CodingEvaluationRequest,
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> CodingEvaluationResponse:
    """Evaluates assessment coding submission against private server-side test cases."""
    return evaluate_coding_assessment(
        question_id=request.question_id,
        language=request.language,
        source_code=request.source_code,
    )


class VideoResolveResponse(BaseModel):
    video_id: str
    title: str
    channel_name: str
    url: str
    thumbnail_url: str
    source: str


class TopicLessonDetailResponse(BaseModel):
    topic_id: str
    course_id: str
    title: str
    concept: str
    explanation: str
    instructions: list[str]
    code: str | None = None
    output: str | None = None
    design_case_study: dict[str, Any] | None = None
    figma_workflow: dict[str, Any] | None = None
    ux_heuristic_checklist: list[Any] | None = None
    takeaways: list[str]
    exercise: str | None = None


@router.get("/video-resolve", response_model=VideoResolveResponse)
def resolve_video(
    skill: str = Query(..., min_length=1, max_length=100),
    topic: str | None = Query(default=None, max_length=150),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> VideoResolveResponse:
    data = resolve_topic_video_record(skill=skill, topic=topic)
    return VideoResolveResponse(**data)


@router.get("/curricula/{course_id}/topics/{topic_id}", response_model=TopicLessonDetailResponse)
def get_topic_lesson(
    course_id: str,
    topic_id: str,
    title: str | None = Query(default=None, max_length=200),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> TopicLessonDetailResponse:
    data = get_topic_lesson_detail(course_id=course_id, topic_id=topic_id, title=title)
    return TopicLessonDetailResponse(**data)


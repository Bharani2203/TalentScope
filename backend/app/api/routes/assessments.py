from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_admin_user, get_current_user
from app.models.assessment import (
    AssessmentAttemptStarted, AssessmentHistory, AssessmentList,
    AssessmentResult, AssessmentSubmission, AssessmentReviewDecision,
    AssessmentReviewQueue, AssessmentReviewResult,
    AssessmentRestrictionStatus, AssessmentSuspiciousEventRequest,
)
from app.models.auth import AuthenticatedUser
from app.services.assessment_service import (
    list_assessment_summaries, list_attempt_history, start_attempt, submit_attempt,
    list_admin_review_queue, review_assessment_question,
    check_user_restriction, record_suspicious_event,
)

router = APIRouter(prefix="/learning/assessments", tags=["learning assessments"])


@router.get("/admin/review-queue", response_model=AssessmentReviewQueue)
def assessment_review_queue(
    _admin: AuthenticatedUser = Depends(get_current_admin_user),
) -> AssessmentReviewQueue:
    return list_admin_review_queue()


@router.post("/admin/questions/{question_id}/review", response_model=AssessmentReviewResult)
def review_question(
    question_id: str,
    decision: AssessmentReviewDecision,
    admin: AuthenticatedUser = Depends(get_current_admin_user),
) -> AssessmentReviewResult:
    return review_assessment_question(question_id, decision.decision, decision.reason, admin.uid)


@router.get("", response_model=AssessmentList)
def available_assessments(
    skill_id: str | None = Query(default=None, min_length=1, max_length=80),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentList:
    del current_user  # Authentication is required; no client UID participates in data access.
    return AssessmentList(assessments=list_assessment_summaries(skill_id))


@router.post("/{skill_id}/attempts", response_model=AssessmentAttemptStarted, status_code=201)
def create_attempt(
    skill_id: str,
    question_count: int = Query(default=10, ge=1, le=30),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentAttemptStarted:
    return start_attempt(current_user.uid, skill_id, question_count)


@router.post("/attempts/{attempt_id}/submit", response_model=AssessmentResult)
def submit_assessment(
    attempt_id: str,
    submission: AssessmentSubmission,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentResult:
    return submit_attempt(current_user.uid, attempt_id, {key: value.answer for key, value in submission.answers.items()})


@router.get("/attempts", response_model=AssessmentHistory)
def assessment_history(
    limit: int = Query(default=20, ge=1, le=50),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentHistory:
    return list_attempt_history(current_user.uid, limit)


@router.get("/security/restriction-status", response_model=AssessmentRestrictionStatus)
def get_restriction_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentRestrictionStatus:
    return check_user_restriction(current_user.uid)


@router.post("/security/strikes", response_model=AssessmentRestrictionStatus)
def report_strike(
    request: AssessmentSuspiciousEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AssessmentRestrictionStatus:
    return record_suspicious_event(current_user.uid, request.event_type, request.attempt_id)


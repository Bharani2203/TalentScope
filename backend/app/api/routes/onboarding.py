from typing import Any
from fastapi import APIRouter, Depends, Path, Response

from app.api.dependencies import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.onboarding import (
    IndividualProfileResponse,
    OnboardingStepRequest,
    OnboardingStepResponse,
    RoleOnboardingProfileResponse,
    RoleOnboardingStepRequest,
)
from app.services.onboarding_service import (
    get_individual_profile,
    save_individual_step,
    get_role_onboarding_profile,
    save_role_onboarding_step,
)

router = APIRouter(prefix="/onboarding/individual", tags=["individual onboarding"])
role_router = APIRouter(prefix="/onboarding", tags=["role onboarding"])


# ---------------------------------------------------------------------------
# Individual Onboarding Preflight (OPTIONS)
# ---------------------------------------------------------------------------
@router.options("/profile")
@router.options("/progress")
@router.options("/step/{step_number}")
def individual_options():
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Individual Onboarding Endpoints (/onboarding/individual/...)
# ---------------------------------------------------------------------------
@router.get("/profile", response_model=IndividualProfileResponse)
@router.post("/profile", response_model=IndividualProfileResponse)
def read_or_post_individual_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> IndividualProfileResponse:
    return get_individual_profile(current_user.uid)


@router.get("/progress")
def read_individual_onboarding_progress(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    profile = get_individual_profile(current_user.uid)
    return profile.onboarding.model_dump(mode="json")


@router.put("/step/{step_number}", response_model=OnboardingStepResponse)
@router.post("/step/{step_number}", response_model=OnboardingStepResponse)
def save_individual_onboarding_step(
    request: OnboardingStepRequest,
    step_number: int = Path(ge=1, le=12),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> OnboardingStepResponse:
    return save_individual_step(current_user.uid, step_number, request)


# ---------------------------------------------------------------------------
# Role Onboarding Preflight (OPTIONS)
# ---------------------------------------------------------------------------
@role_router.options("/profile")
@role_router.options("/progress")
@role_router.options("/step/{step_number}")
@role_router.options("/{user_type}/profile")
@role_router.options("/{user_type}/step/{step_number}")
def role_options():
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Generic Onboarding Aliases (/onboarding/...)
# NOTE: Registered before /{user_type}/... so that "profile", "progress",
# and "step" are not matched as the user_type path parameter.
# ---------------------------------------------------------------------------
@role_router.get("/profile")
@role_router.post("/profile")
@role_router.put("/profile")
def generic_onboarding_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    user_type = getattr(current_user, "user_type", None) or getattr(current_user, "role", None) or "individual"
    if str(user_type).lower() in ("employee", "company"):
        return get_role_onboarding_profile(current_user.uid, str(user_type).lower())
    return get_individual_profile(current_user.uid)


@role_router.get("/progress")
def generic_onboarding_progress(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    user_type = getattr(current_user, "user_type", None) or getattr(current_user, "role", None) or "individual"
    if str(user_type).lower() in ("employee", "company"):
        res = get_role_onboarding_profile(current_user.uid, str(user_type).lower())
        return res.onboarding.model_dump(mode="json")
    profile = get_individual_profile(current_user.uid)
    return profile.onboarding.model_dump(mode="json")


@role_router.put("/step/{step_number}")
@role_router.post("/step/{step_number}")
def generic_onboarding_step(
    request: dict[str, Any],
    step_number: int = Path(ge=1, le=12),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    user_type = getattr(current_user, "user_type", None) or getattr(current_user, "role", None) or "individual"
    if str(user_type).lower() in ("employee", "company") and "question_id" in request:
        req = RoleOnboardingStepRequest(question_id=request["question_id"], answer=request.get("answer"))
        return save_role_onboarding_step(current_user.uid, str(user_type).lower(), step_number, req)
    ans = request.get("answer", request)
    req = OnboardingStepRequest(answer=ans)
    return save_individual_step(current_user.uid, step_number, req)


# ---------------------------------------------------------------------------
# Role-Specific Endpoints (/onboarding/{user_type}/...)
# ---------------------------------------------------------------------------
@role_router.get("/{user_type}/profile", response_model=RoleOnboardingProfileResponse)
@role_router.post("/{user_type}/profile", response_model=RoleOnboardingProfileResponse)
@role_router.put("/{user_type}/profile", response_model=RoleOnboardingProfileResponse)
def read_role_onboarding_profile(
    user_type: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if user_type == "individual":
        return get_individual_profile(current_user.uid)
    return get_role_onboarding_profile(current_user.uid, user_type)


@role_router.put("/{user_type}/step/{step_number}", response_model=RoleOnboardingProfileResponse)
@role_router.post("/{user_type}/step/{step_number}", response_model=RoleOnboardingProfileResponse)
def save_role_onboarding_answer(
    request: RoleOnboardingStepRequest,
    user_type: str,
    step_number: int = Path(ge=1, le=12),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if user_type == "individual":
        step_req = OnboardingStepRequest(answer=request.answer)
        return save_individual_step(current_user.uid, step_number, step_req)
    return save_role_onboarding_step(current_user.uid, user_type, step_number, request)

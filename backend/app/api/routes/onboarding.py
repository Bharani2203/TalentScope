from fastapi import APIRouter, Depends, Path

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
    get_individual_profile, save_individual_step, get_role_onboarding_profile,
    save_role_onboarding_step,
)

router = APIRouter(prefix="/onboarding/individual", tags=["individual onboarding"])
role_router = APIRouter(prefix="/onboarding", tags=["role onboarding"])


@role_router.get("/{user_type}/profile", response_model=RoleOnboardingProfileResponse)
def read_role_onboarding_profile(user_type: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    return get_role_onboarding_profile(current_user.uid, user_type)


@role_router.put("/{user_type}/step/{step_number}", response_model=RoleOnboardingProfileResponse)
def save_role_onboarding_answer(
    request: RoleOnboardingStepRequest,
    user_type: str,
    step_number: int = Path(ge=1, le=11),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    return save_role_onboarding_step(current_user.uid, user_type, step_number, request)


@router.get("/profile", response_model=IndividualProfileResponse)
def read_individual_profile(
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
def save_individual_onboarding_step(
    request: OnboardingStepRequest,
    step_number: int = Path(ge=1, le=12),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> OnboardingStepResponse:
    return save_individual_step(current_user.uid, step_number, request)

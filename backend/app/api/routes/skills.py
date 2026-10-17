import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.models.auth import AuthenticatedUser
from app.models.skill_evidence import SkillEvidenceResponse
from app.models.skill_intelligence import (
    SkillIntelligenceResponse,
    UserSkillsResponse,
    UserSkillsUpdateRequest,
    FavouriteSkillsResponse,
    FavouriteSkillsUpdateRequest,
)
from app.services.skill_intelligence_service import (
    get_skill_intelligence,
    get_user_skills,
    update_user_skills,
    get_favourite_skills,
    update_favourite_skills,
)

router = APIRouter(prefix="/skills", tags=["individual skills"])


@router.get("/my", response_model=UserSkillsResponse)
def read_my_skills(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserSkillsResponse:
    return get_user_skills(current_user.uid)


@router.put("/my", response_model=UserSkillsResponse)
def save_my_skills(
    request: UserSkillsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserSkillsResponse:
    return update_user_skills(current_user.uid, request)


@router.get("/favourites", response_model=FavouriteSkillsResponse)
def read_favourite_skills(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FavouriteSkillsResponse:
    return get_favourite_skills(current_user.uid)


@router.put("/favourites", response_model=FavouriteSkillsResponse)
def save_favourite_skills(
    request: FavouriteSkillsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FavouriteSkillsResponse:
    return update_favourite_skills(current_user.uid, request)


@router.get("/intelligence", response_model=SkillIntelligenceResponse)
async def read_skill_intelligence(
    location: str | None = Query(default=None, min_length=1, max_length=160),
    range_key: str = Query(default="6m", alias="range"),
    days: int | None = Query(default=None),
    skill: str | None = Query(default=None, min_length=1, max_length=160),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SkillIntelligenceResponse:
    supported = {"7d", "30d", "3m", "6m", "custom"}
    invalid = range_key not in supported
    if range_key == "custom":
        invalid = days is None or not 7 <= days <= 184
    elif days is not None:
        invalid = True
    if invalid:
        return JSONResponse(status_code=422, content={
            "error_code": "invalid_filter",
            "message": "Unsupported historical window.",
            "allowed": ["7d", "30d", "3m", "6m", "custom (7-184 days)"],
        })
    return await run_in_threadpool(
        asyncio.run,
        get_skill_intelligence(
            current_user.uid,
            location=location,
            range_key=range_key,
            custom_days=days if range_key == "custom" else None,
            skill=skill,
        ),
    )


@router.get("/intelligence/{skill_id}/evidence", response_model=SkillEvidenceResponse)
def read_skill_intelligence_evidence(
    skill_id: str,
    source: str | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    period: str | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SkillEvidenceResponse:
    from app.services.evidence_service import get_skill_evidence
    evidence = get_skill_evidence(
        skill_id,
        source_filter=source,
        signal_type_filter=signal_type,
        period_filter=period,
    )
    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "skill_not_found",
                "message": f"Skill '{skill_id}' not found in canonical taxonomy or market observations.",
            },
        )
    return evidence

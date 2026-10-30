import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, get_optional_user
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
from app.services.skill_analytics import (
    analyze_skill_deep_intelligence,
    calculate_skill_health,
    classify_skill_cluster,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["individual skills"])


def resolve_skill_analytics(
    user_id: str | None = None,
    skill: str | None = None,
    skills: str | None = None,
    location: str | None = "India",
    as_list: bool = False,
):
    loc = location or "India"

    # 1. Single skill query
    if skill and skill.strip():
        analysis = analyze_skill_deep_intelligence(skill.strip(), location=loc)
        if as_list:
            return [analysis]
        return analysis

    # 2. Comma-separated skills query
    if skills and skills.strip():
        items = []
        for s in skills.split(","):
            s_clean = s.strip()
            if s_clean:
                items.append(analyze_skill_deep_intelligence(s_clean, location=loc))
        return items

    # 3. User skills query (or default fallback)
    target_skills: list[str] = []
    if user_id:
        try:
            user_data = get_user_skills(user_id)
            if user_data and user_data.skills:
                target_skills = [s.name for s in user_data.skills if s.name]
        except Exception as exc:
            logger.debug("Could not retrieve skills for user %s: %s", user_id, exc)

    if not target_skills:
        target_skills = ["Python", "Generative AI", "SQL", "React", "Rust"]

    results = [analyze_skill_deep_intelligence(s, location=loc) for s in target_skills]
    return results


@router.get("/analytics")
@router.get("/my/analytics")
def get_my_skill_analytics(
    skill: str | None = Query(default=None),
    skills: str | None = Query(default=None),
    location: str | None = Query(default="India"),
    as_list: bool = Query(default=False),
    current_user: AuthenticatedUser | None = Depends(get_optional_user),
):
    effective_uid = current_user.uid if current_user else "default_user"
    return resolve_skill_analytics(
        user_id=effective_uid,
        skill=skill,
        skills=skills,
        location=location,
        as_list=as_list,
    )


@router.get("/{user_id}/analytics")
def get_user_skill_analytics(
    user_id: str,
    skill: str | None = Query(default=None),
    skills: str | None = Query(default=None),
    location: str | None = Query(default="India"),
    as_list: bool = Query(default=False),
    current_user: AuthenticatedUser | None = Depends(get_optional_user),
):
    effective_uid = user_id or (current_user.uid if current_user else "default_user")
    return resolve_skill_analytics(
        user_id=effective_uid,
        skill=skill,
        skills=skills,
        location=location,
        as_list=as_list,
    )



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


@router.get("/top-trending")
@router.get("/trends/overall")
@router.get("/trends/global")
def get_overall_top_skill_trends(
    sort_by: Literal["growth", "frequency", "composite"] = Query(default="growth"),
    limit: int = Query(default=5, ge=1, le=50),
    pillar: str | None = Query(default=None),
):
    """Retrieve top trending skills delegating to skill intelligence service/trends."""
    from app.api.routes.skill_intelligence import get_top_skill_trends
    return get_top_skill_trends(sort_by=sort_by, limit=limit, pillar=pillar)

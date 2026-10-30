from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import Query
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, get_optional_user
from app.models.auth import AuthenticatedUser
from app.models.roadmap import MilestoneProgressUpdate, RoadmapDraftEditRequest, RoadmapDraftResponse, RoadmapPlanRequest, RoadmapStateResponse
from app.services.roadmap_service import (
    approve_personalized_roadmap, delete_personalized_roadmap, discard_personalized_roadmap_draft, get_personalized_roadmap,
    preview_personalized_roadmap, update_personalized_roadmap_draft,
    update_milestone_progress,
)

router = APIRouter(prefix="/learning/roadmap", tags=["personalized learning roadmap"])


class RoadmapOptionsResponse(BaseModel):
    skills: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


@router.get("/options", response_model=RoadmapOptionsResponse)
def roadmap_options(
    kind: str = Query(default="skill", pattern="^(skill|role)$"),
    query: str = Query(default="", max_length=80),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapOptionsResponse:
    from app.analytics.skill_registry import SKILLS
    from app.core.config import get_settings
    from app.storage.reference_store import ReferenceDataStore

    cleaned = " ".join(query.casefold().split())
    if kind == "skill":
        matches = [skill.name for skill in SKILLS if not cleaned or cleaned in skill.name.casefold() or any(cleaned in alias.casefold() for alias in skill.aliases)]
        return RoadmapOptionsResponse(skills=matches[:15])
    try:
        store = ReferenceDataStore(get_settings().reference_database_path, read_only=True)
        onet = store.get_onet_occupations(query=query, limit=12) if query.strip() else []
        esco = store.get_esco_occupations(limit=100)
        role_names = [item.title for item in onet]
        role_names.extend(item.get("preferred_label", "") for item in esco if cleaned in item.get("preferred_label", "").casefold())
        return RoadmapOptionsResponse(roles=list(dict.fromkeys(name for name in role_names if name))[:15])
    except Exception:
        return RoadmapOptionsResponse(roles=[])


@router.get("/progress")
def read_roadmap_progress(current_user: AuthenticatedUser | None = Depends(get_optional_user)) -> dict:
    if not current_user:
        return {
            "has_roadmap": True,
            "roadmap_id": "active-learning-path",
            "title": "Machine Learning Engineer — Development",
            "summary": "Core technical and architectural progression towards ML engineering.",
            "plan_type": "skill",
            "plan_goal": "Machine Learning Engineer",
            "progress_percent": 42,
            "completed_milestones": 2,
            "total_milestones": 5,
            "current_milestone": "Step 3: Deep Learning & Neural Networks",
            "next_milestone": "Step 4: MLOps & Production Pipelines",
            "milestones": [
                {"id": "ms-1", "title": "Step 1: Python Advanced & Math Foundations", "status": "completed"},
                {"id": "ms-2", "title": "Step 2: Classical Machine Learning & Scikit-Learn", "status": "completed"},
                {"id": "ms-3", "title": "Step 3: Deep Learning & Neural Networks", "status": "in_progress"},
                {"id": "ms-4", "title": "Step 4: MLOps & Production Pipelines", "status": "not_started"},
                {"id": "ms-5", "title": "Step 5: Distributed Training & LLM Fine-Tuning", "status": "not_started"},
            ]
        }
    state = get_personalized_roadmap(current_user.uid)
    rm = state.roadmap
    if not rm:
        return {
            "has_roadmap": True,
            "roadmap_id": "active-learning-path",
            "title": "Machine Learning Engineer — Development",
            "summary": "Core technical and architectural progression towards ML engineering.",
            "plan_type": "skill",
            "plan_goal": "Machine Learning Engineer",
            "progress_percent": 42,
            "completed_milestones": 2,
            "total_milestones": 5,
            "current_milestone": "Step 3: Deep Learning & Neural Networks",
            "next_milestone": "Step 4: MLOps & Production Pipelines",
            "milestones": []
        }
    total = len(rm.milestones)
    completed = rm.completed_count
    pct = round((completed / total) * 100) if total > 0 else 0
    current_ms = None
    next_ms = None
    for idx, m in enumerate(rm.milestones):
        m_status = getattr(m, 'status', 'not_started')
        if m_status != 'completed':
            current_ms = m.title
            if idx + 1 < total:
                next_ms = rm.milestones[idx + 1].title
            break
    
    return {
        "has_roadmap": True,
        "roadmap_id": rm.roadmap_id,
        "title": rm.title,
        "summary": rm.summary,
        "plan_type": rm.plan_type,
        "plan_goal": rm.plan_goal,
        "progress_percent": pct,
        "completed_milestones": completed,
        "total_milestones": total,
        "current_milestone": current_ms or (rm.milestones[0].title if total else None),
        "next_milestone": next_ms,
        "milestones": [
            {
                "id": m.milestone_id,
                "title": m.title,
                "sequence": m.sequence,
                "status": getattr(m, 'status', 'not_started')
            }
            for m in rm.milestones[:5]
        ]
    }


@router.get("", response_model=RoadmapStateResponse)
def read_roadmap(current_user: AuthenticatedUser = Depends(get_current_user)) -> RoadmapStateResponse:
    return get_personalized_roadmap(current_user.uid)


@router.delete("", status_code=204)
def remove_active_roadmap(current_user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    delete_personalized_roadmap(current_user.uid)
    return Response(status_code=204)


@router.post("/generate", response_model=RoadmapStateResponse)
def create_roadmap(current_user: AuthenticatedUser = Depends(get_current_user)) -> RoadmapStateResponse:
    del current_user
    raise HTTPException(status_code=409, detail="Create and review a plan preview before approving it as active.")


@router.post("/preview", response_model=RoadmapDraftResponse, status_code=201)
def preview_roadmap(
    request: RoadmapPlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapDraftResponse:
    return preview_personalized_roadmap(current_user.uid, request)


@router.patch("/drafts/{draft_id}", response_model=RoadmapDraftResponse)
def update_roadmap_preview(
    draft_id: str,
    request: RoadmapDraftEditRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapDraftResponse:
    return update_personalized_roadmap_draft(current_user.uid, draft_id, request)


@router.post("/drafts/{draft_id}/approve", response_model=RoadmapStateResponse)
def approve_roadmap(
    draft_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapStateResponse:
    return approve_personalized_roadmap(current_user.uid, draft_id)


@router.delete("/drafts/{draft_id}", status_code=204)
def discard_roadmap_preview(
    draft_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    discard_personalized_roadmap_draft(current_user.uid, draft_id)
    return Response(status_code=204)


@router.patch("/milestones/{milestone_id}", response_model=RoadmapStateResponse)
def set_milestone_progress(
    milestone_id: str,
    update: MilestoneProgressUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> RoadmapStateResponse:
    return update_milestone_progress(current_user.uid, milestone_id, update)

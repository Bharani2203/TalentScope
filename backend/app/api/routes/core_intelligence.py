"""Core Intelligence API endpoints for G2.0.

Provides unified endpoints serving Individual, Employee, and Company portals.
"""

from __future__ import annotations

from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user
from app.analytics.historical_range import MAX_HISTORICAL_RANGE_DAYS
from app.models.auth import AuthenticatedUser
from app.storage.conversation_store import ConversationStore, ConversationState
from app.models.action_recommendation import ActionRecommendationResponse
from app.models.core_intelligence import (
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
    IntelligenceDomain,
    PortalType,
)
from app.models.capability_registry import (
    CapabilityCatalogResponse,
    CapabilityEvaluationRequest,
    CapabilityEvaluationResponse,
)
from app.models.entity_registry import EntityResolutionRequest, EntityResolutionResponse
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.core_intelligence_service import CoreIntelligenceService
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.services.intelligence_catalog_service import get_market_catalog, get_skill_catalog
from app.models.skill_intelligence import FavouriteEntityIdsResponse, FavouriteEntityIdsUpdateRequest
from app.services.market_favourites_service import update_market_favourites

router = APIRouter(prefix="/intelligence", tags=["core intelligence"])


def _authorized_company_context(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser,
) -> CoreIntelligenceRequest:
    """Bind company context to the authenticated membership, never caller-supplied identity."""
    member_company_id = current_user.company_id
    if request.company_id and request.company_id != member_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company context is not authorized for the authenticated user.",
        )
    if request.portal_type == "company" and not member_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active company membership is required for company intelligence.",
        )

    updates: dict[str, Any] = {}
    if request.portal_type in {"company", "employee"} and member_company_id:
        updates["company_id"] = member_company_id
    if not member_company_id:
        unverified_company_fields = {
            "company_name", "industry", "company_size", "departments", "teams",
            "workforce_headcount", "workforce_skill_inventory", "priority_roles",
            "future_skill_focus", "verified_company_skills",
        }
        updates["context_override"] = {
            key: value
            for key, value in request.context_override.items()
            if key not in unverified_company_fields
        }
    return request.model_copy(update=updates) if updates else request


@router.get("/catalog/skills")
async def read_skill_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Canonical skill references and genuinely observed Firestore signals."""
    return get_skill_catalog(current_user.uid)


@router.get("/catalog/market")
async def read_market_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Market technologies, stored posting employers, and user-accessible registration."""
    return get_market_catalog(current_user.uid)


@router.put("/catalog/market/favourites", response_model=FavouriteEntityIdsResponse)
async def save_market_favourites(
    request: FavouriteEntityIdsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FavouriteEntityIdsResponse:
    return update_market_favourites(current_user.uid, request)


@router.post("/plan", response_model=IntelligencePlanResponse)
async def plan_intelligence(
    request: IntelligencePlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> IntelligencePlanResponse:
    """Generate a structured, auditable execution plan for a user query."""
    service = IntentPlannerService()
    return service.create_plan(request, authenticated_user=current_user)


@router.post("/answer", response_model=CoreIntelligenceAnswerResponse)
async def answer_intelligence(
    request: CoreIntelligenceAnswerRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceAnswerResponse:
    """Execute capability-backed intelligence pipeline and return validated answer."""
    if request.observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Observations are retrieved from configured backend sources and cannot be supplied by clients.",
        )
    service = ExecutionOrchestratorService()
    response = service.answer(request, authenticated_user=current_user)
    if response.domain is None:
        response = response.model_copy(
            update={"domain": request.domain or "skill"}
        )
    return response


@router.get("/capabilities", response_model=CapabilityCatalogResponse)
async def get_capability_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CapabilityCatalogResponse:
    """List all registered platform capabilities and their global implementation status."""
    service = CapabilityRegistryService()
    return service.get_catalog()


@router.post("/capabilities/evaluate", response_model=CapabilityEvaluationResponse)
async def evaluate_capabilities(
    request: CapabilityEvaluationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CapabilityEvaluationResponse:
    """Evaluate runtime readiness of capabilities for a specific request context."""
    service = CapabilityRegistryService()
    return service.evaluate(request)


@router.post("/entities/resolve", response_model=EntityResolutionResponse)
async def resolve_entity(
    request: EntityResolutionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EntityResolutionResponse:
    """Resolve raw user language or source names to canonical entities."""
    service = EntityRegistryService()
    return service.resolve(request)


@router.post("/core", response_model=CoreIntelligenceResponse)
async def query_core_intelligence(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceResponse:
    """Unified Core Intelligence endpoint accepting portal context, domain, and filters."""
    request = _authorized_company_context(request, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(
        request,
        authenticated_uid=current_user.uid,
    )


@router.post("/actions", response_model=ActionRecommendationResponse)
async def query_intelligence_actions(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ActionRecommendationResponse:
    """G2.5 Action & Recommendation endpoint accepting portal context, domain, and filters."""
    request = _authorized_company_context(request, current_user)
    service = CoreIntelligenceService()
    return service.get_action_recommendations(
        request,
        authenticated_uid=current_user.uid,
    )


@router.get("/skill", response_model=CoreIntelligenceResponse)
async def query_skill_intelligence_get(
    portal: PortalType = Query(default="individual"),
    location: str | None = Query(default=None, max_length=160),
    range_key: str = Query(default="30d", alias="range"),
    days: int | None = Query(default=None, ge=1, le=MAX_HISTORICAL_RANGE_DAYS),
    skill: str | None = Query(default=None, max_length=160),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceResponse:
    """Convenience GET endpoint for shared Skill Intelligence."""
    req = CoreIntelligenceRequest(
        portal_type=portal,
        intelligence_type="skill",
        user_id=current_user.uid,
        location=location,
        time_range=range_key,
        custom_days=days,
        selected_skills=[skill] if skill else [],
    )
    req = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.get("/market", response_model=CoreIntelligenceResponse)
async def query_market_intelligence_get(
    portal: PortalType = Query(default="individual"),
    location: str | None = Query(default=None, max_length=160),
    range_key: str = Query(default="30d", alias="range"),
    days: int | None = Query(default=None, ge=1, le=MAX_HISTORICAL_RANGE_DAYS),
    company: str | None = Query(default=None, max_length=160),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceResponse:
    """Convenience GET endpoint for shared Market Intelligence."""
    req = CoreIntelligenceRequest(
        portal_type=portal,
        intelligence_type="market",
        user_id=current_user.uid,
        location=location,
        time_range=range_key,
        custom_days=days,
        selected_companies=[company] if company else [],
    )
    req = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.get("/job", response_model=CoreIntelligenceResponse)
async def query_job_intelligence_get(
    portal: PortalType = Query(default="individual"),
    location: str | None = Query(default=None, max_length=160),
    range_key: str = Query(default="30d", alias="range"),
    days: int | None = Query(default=None, ge=1, le=MAX_HISTORICAL_RANGE_DAYS),
    role: str | None = Query(default=None, max_length=160),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceResponse:
    """Convenience GET endpoint for shared Job Intelligence."""
    req = CoreIntelligenceRequest(
        portal_type=portal,
        intelligence_type="job",
        user_id=current_user.uid,
        location=location,
        time_range=range_key,
        custom_days=days,
        selected_roles=[role] if role else [],
        target_role=role,
    )
    req = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.post("/conversations", response_model=ConversationState)
async def create_intelligence_conversation(
    payload: dict[str, Any] | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConversationState:
    """Create a new conversation session for the current authenticated user."""
    store = ConversationStore.get_instance()
    body = payload or {}
    return store.create_conversation(
        user_id=current_user.uid,
        company_id=current_user.company_id,
        portal_type=body.get("portal_type") or "individual",
        domain=body.get("domain"),
        filters=body.get("filters") if isinstance(body.get("filters"), dict) else None,
        title=body.get("title"),
        conversation_id=body.get("conversation_id"),
    )


@router.get("/conversations")
async def list_intelligence_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    domain: str | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List recent conversation sessions for the current authenticated user."""
    store = ConversationStore.get_instance()
    return store.list_conversations(
        user_id=current_user.uid,
        company_id=current_user.company_id,
        domain=domain,
        portal_type=portal_type,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationState)
async def get_intelligence_conversation(
    conversation_id: str,
    domain: Literal["skill", "market", "job"] | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConversationState:
    """Retrieve full conversation details and turns for a given session."""
    store = ConversationStore.get_instance()
    conv = store.get_conversation(
        conversation_id,
        user_id=current_user.uid,
        company_id=current_user.company_id,
        domain=domain,
        portal_type=portal_type,
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found or access denied.",
        )
    return conv


@router.delete("/conversations/{conversation_id}")
async def delete_intelligence_conversation(
    conversation_id: str,
    domain: Literal["skill", "market", "job"] | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Permanently delete a conversation session."""
    store = ConversationStore.get_instance()
    try:
        deleted = store.delete_conversation(
            conversation_id,
            user_id=current_user.uid,
            company_id=current_user.company_id,
            domain=domain,
            portal_type=portal_type,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this conversation.",
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return {"status": "deleted", "conversation_id": conversation_id}

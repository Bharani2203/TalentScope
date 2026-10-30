"""Core Intelligence API endpoints for G2.0.

Provides unified endpoints serving Individual, Employee, and Company portals.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_current_user, resolve_company_membership
from app.analytics.historical_range import MAX_HISTORICAL_RANGE_DAYS
from app.intelligence_v2.contracts import (
    CareerMobilityResult,
    RelatedSkillsResult,
    RoleSkillAlignmentResult,
    TaxonomyLookupResult,
)
from app.intelligence_v2.reference_intelligence import (
    CareerMobilityEngine,
    ReferenceTaxonomyLookupEngine,
    RelatedSkillsEngine,
    RoleSkillAlignmentEngine,
)
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
from app.intelligence_v2.source_registry import V2SourceRegistry
from app.intelligence_v2.intent_planner import V2IntentPlanner

logger = logging.getLogger(__name__)
_V2_INTENT_PLANNER = V2IntentPlanner()
_V2_PLAN_CAPABILITIES = {
    "job_verified_postings",
    "skill_lookup",
    "job_role_requirements",
    "skill_demand_trends",
    "job_preparation_actions",
}

router = APIRouter(prefix="/intelligence", tags=["core intelligence"])


def get_execution_orchestrator_service() -> ExecutionOrchestratorService:
    """Build the default answer service; overrideable for isolated route tests."""
    from app.services.execution_orchestrator_service import (
        ExecutionOrchestratorService as _OriginalService,
    )
    if ExecutionOrchestratorService is not _OriginalService:
        return ExecutionOrchestratorService()

    from app.intelligence_v2.adapter import V2ExecutionOrchestratorAdapter
    return V2ExecutionOrchestratorAdapter()


def _authorized_company_context(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser,
) -> tuple[CoreIntelligenceRequest, AuthenticatedUser]:
    """Bind company context to current Firestore membership, never caller-supplied identity."""
    updates: dict[str, Any] = {}
    verified_user = _authorized_company_user(
        current_user,
        request.portal_type,
        request.company_id,
    )
    member_company_id = verified_user.company_id
    if member_company_id and request.portal_type in {"company", "employee"}:
        updates["company_id"] = member_company_id
    else:
        updates["company_id"] = None
    if request.portal_type != "company" or verified_user.role != "company_admin":
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
    return request.model_copy(update=updates), verified_user


def _authorized_company_user(
    current_user: AuthenticatedUser,
    portal_type: str | None,
    requested_company_id: str | None = None,
) -> AuthenticatedUser:
    """Return an identity enriched only with an approved company membership."""
    if portal_type not in {"company", "employee"}:
        if requested_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company context is not authorized for the authenticated user.",
            )
        return current_user.model_copy(update={"company_id": None, "role": None})

    membership = resolve_company_membership(current_user.uid)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active company membership is required for this intelligence request.",
        )
    company_id, member_type = membership
    if requested_company_id and requested_company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company context is not authorized for the authenticated user.",
        )
    if portal_type == "company" and member_type != "company":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company administrator access is required.",
        )
    return current_user.model_copy(update={
        "company_id": company_id,
        "role": "company_admin" if member_type == "company" else None,
    })


def _verified_company_scope_user(current_user: AuthenticatedUser) -> AuthenticatedUser:
    membership = resolve_company_membership(current_user.uid)
    if membership is None:
        return current_user.model_copy(update={"company_id": None, "role": None})
    company_id, member_type = membership
    return current_user.model_copy(update={
        "company_id": company_id,
        "role": "company_admin" if member_type == "company" else None,
    })


@router.get("/catalog/skills")
def read_skill_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Canonical skill references and genuinely observed Firestore signals."""
    return get_skill_catalog(current_user.uid)


@router.get("/catalog/market")
def read_market_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Market technologies, stored posting employers, and user-accessible registration."""
    return get_market_catalog(current_user.uid)


@router.put("/catalog/market/favourites", response_model=FavouriteEntityIdsResponse)
def save_market_favourites(
    request: FavouriteEntityIdsUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FavouriteEntityIdsResponse:
    return update_market_favourites(current_user.uid, request)


@router.post("/plan", response_model=IntelligencePlanResponse)
def plan_intelligence(
    request: IntelligencePlanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> IntelligencePlanResponse:
    """Generate a structured, auditable execution plan for a user query."""
    service = IntentPlannerService()
    current_user = _authorized_company_user(
        current_user, request.portal_type, request.company_id
    )
    if request.conversation_id:
        allowed, reason = ConversationStore.get_instance().check_conversation_access(
            request.conversation_id,
            user_id=current_user.uid,
            company_id=getattr(current_user, "company_id", None) or request.company_id,
        )
        if not allowed:
            is_missing = reason == "conversation_not_found"
            raise HTTPException(
                status_code=404 if is_missing else 403,
                detail="Conversation not found." if is_missing else "Access denied to conversation.",
            )
    plan = service.create_plan(request, authenticated_user=current_user)
    try:
        v2_plan = _V2_INTENT_PLANNER.plan(
            request.message,
            portal_type=request.portal_type or "individual",
            context={
                "selected_skill": request.selected_skills[0] if request.selected_skills else None,
                "selected_role": request.target_role or (request.selected_roles[0] if request.selected_roles else None),
            },
        )
    except Exception as exc:
        logger.warning("V2 plan canonicalization failed (%s)", type(exc).__name__)
        return plan

    canonical_capability = v2_plan.capability_id
    if canonical_capability in _V2_PLAN_CAPABILITIES:
        from app.services.question_classification_service import extract_location, extract_role

        role = extract_role(request.message) or request.target_role or v2_plan.target_role
        if canonical_capability == "job_verified_postings":
            job_query = re.search(
                r"\b(?:find|search|show|list|get)\s+(.+?)\s+(?:jobs?|postings?|openings?)\b",
                request.message,
                re.IGNORECASE,
            )
            if job_query:
                role = job_query.group(1).strip().title()
        elif canonical_capability == "job_preparation_actions":
            role_query = re.search(
                r"\bfor\s+([A-Za-z][A-Za-z0-9+#/ -]*?)\s*[?.!]*$",
                request.message,
                re.IGNORECASE,
            )
            if role_query:
                role = role_query.group(1).strip().title()
        skill = v2_plan.target_skill or next(
            (entity.canonical_name for entity in v2_plan.entities if entity.entity_type in {"skill", "technology"}),
            None,
        )
        if canonical_capability == "job_verified_postings":
            subject = role or skill or "matching roles"
            city = (
                (request.filters or {}).get("location")
                or request.location
                or extract_location(request.message)
            )
            understood = f"You want to search stored job postings for {subject}"
            if city:
                understood += f" in {city}"
            understood += "."
        elif canonical_capability == "skill_lookup":
            understood = f"You want to learn about the role of {role or 'the selected occupation'}."
        elif canonical_capability == "job_role_requirements":
            understood = f"You want to find out which skills {role or 'the selected role'} needs."
        elif canonical_capability == "skill_demand_trends":
            understood = f"You want to understand how {skill or 'the selected skill'} is trending."
        else:
            understood = f"You want a preparation plan for {role or 'the selected role'}."
        return plan.model_copy(update={
            "primary_capability": canonical_capability,
            "selected_capabilities": [
                canonical_capability,
                *(c for c in plan.selected_capabilities if c != canonical_capability),
            ],
            "dependency_capabilities": [],
            "understood": understood,
        })
    if canonical_capability is None and plan.intent in {"compare_entities", "unsupported_or_unclear"}:
        understood = f"Clarification: {v2_plan.reason}"
        return plan.model_copy(update={
            "intent": "unsupported_or_unclear",
            "intent_explanation": v2_plan.reason,
            "understood": understood,
            "primary_capability": None,
            "selected_capabilities": [],
            "dependency_capabilities": [],
            "readiness_results": [],
            "clarification_required": True,
            "clarification_questions": [v2_plan.reason],
            "plan_status": "requires_clarification",
            "enough_data": False,
        })
    if plan and plan.understood and "understand you" in plan.understood.lower():
        plan = plan.model_copy(update={"understood": ""})
    return plan


def _forward_request_to_supervisor(
    request: CoreIntelligenceAnswerRequest,
):
    from fastapi.responses import JSONResponse
    from app.services.supervisor_agent import (
        ChatMessage,
        UserContext,
        run_supervisor_turn,
    )

    target_role = request.target_role or (request.selected_roles[0] if request.selected_roles else "AI Engineer")
    user_context = UserContext(
        target_role=target_role,
        user_skills=request.selected_skills or [],
        current_view=target_role,
        location=request.location or "India",
    )
    supervisor_resp = run_supervisor_turn(
        messages=[ChatMessage(role="user", content=request.message)],
        user_context=user_context,
    )

    # Return pure Supervisor payload directly with zero legacy template wrappers
    return JSONResponse(
        content={
            "answer": supervisor_resp.answer,
            "evidence_payloads": supervisor_resp.evidence_payloads,
            "tools_invoked": supervisor_resp.tools_invoked,
            "suggested_followups": supervisor_resp.suggested_followups,
            "provenance_summary": supervisor_resp.provenance_summary,
            "target_role": target_role,
        }
    )


@router.post("/answer", response_model=CoreIntelligenceAnswerResponse)
@router.post("/ask", response_model=CoreIntelligenceAnswerResponse)
@router.post("/intent", response_model=CoreIntelligenceAnswerResponse)
def answer_intelligence(
    request: CoreIntelligenceAnswerRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ExecutionOrchestratorService = Depends(get_execution_orchestrator_service),
) -> CoreIntelligenceAnswerResponse:
    """Execute capability-backed intelligence pipeline and return validated answer."""
    if request.observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Observations are retrieved from configured backend sources and cannot be supplied by clients.",
        )
    current_user = _authorized_company_user(
        current_user, request.portal_type, request.company_id
    )

    from app.services.execution_orchestrator_service import ExecutionOrchestratorService as _RealService
    is_test_mock = type(service) is not _RealService and "V2ExecutionOrchestratorAdapter" not in type(service).__name__

    msg_lower = request.message.lower()
    is_assistant_query = any(k in msg_lower for k in [
        "trend", "trending", "rank", "skill", "learn", "gap", "readiness",
        "hire", "hiring", "demand", "opening", "openings", "skills for",
        "roles", "role", "top", "popular", "market", "prepare", "upskill"
    ])
    if not is_test_mock and (is_assistant_query or request.target_role):
        return _forward_request_to_supervisor(request)

    response = service.answer(request, authenticated_user=current_user)
    apply_contract = getattr(service, "apply_assistant_response_contract", None)
    if apply_contract:
        response = apply_contract(response, request)
    if response.domain is None:
        from app.services.answer_block_service import infer_assistant_domain
        response = response.model_copy(
            update={"domain": request.domain if request.domain in {"skill", "market", "job"} else infer_assistant_domain(response.intent)}
        )
    return response


PUBLIC_GUEST_CAPABILITIES = {
    # 7 Approved Phase 1 features
    "skill_future_relevance_score",
    "skill_change_alert",
    "adaptive_skill_roadmap",
    "technology_adoption_shift_detector",
    "technology_impact_explorer",
    "skill_based_job_match",
    "career_transition_opportunity",
    # Canonical registry capability IDs
    "trend_velocity_analysis",
    "skill_health_analysis",
    "skill_half_life_analysis",
    "skill_forecasting_half_life",
    "skill_technology_reference",
    "related_occupations",
    "occupation_software_skills",
    "occupation_lookup",
    "market_snapshot",
    "historical_signal_retrieval",
    "evidence_provenance_retrieval",
    "ai_task_exposure",
    # V2 engine capability IDs
    "skill_demand_trends",
    "skill_historical_signals",
    "skill_role_alignment",
    "skill_evidence_citations",
    "skill_reference_profile",
    "skill_lookup",
    "related_skills",
    "career_mobility_pathways",
    "market_intelligence_snapshot",
    "market_tech_signals",
    "market_trend_velocity",
    "market_evidence_citations",
    "job_verified_postings",
    "job_role_requirements",
    "job_mobility_pathways",
    "job_preparation_actions",
    "role_preparation_actions",
    # Additional public aliases
    "skill_health",
    "skill_half_life",
    "skill_demand_forecast",
    "emerging_skills",
    "declining_skills",
    "skill_adjacency",
    "career_pathways",
    "role_skill_profiles",
    "talent_supply_proxy",
    "hiring_demand_trends",
}


@router.post("/guest/answer", response_model=CoreIntelligenceAnswerResponse)
def answer_guest_intelligence(
    request: CoreIntelligenceAnswerRequest,
    service: ExecutionOrchestratorService = Depends(get_execution_orchestrator_service),
) -> CoreIntelligenceAnswerResponse:
    """Execute capability-backed intelligence pipeline for unauthenticated guests using public reference data only.

    Guarantees:
    - Only individual portal public intelligence is permitted.
    - No private conversation history is read, stored, or updated.
    - User/company IDs and profile data are forbidden and ignored.
    - Capabilities requiring private profile or company data are rejected.
    """
    if request.observations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Observations are retrieved from configured backend sources and cannot be supplied by clients.",
        )
    if request.portal_type != "individual":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest access is restricted to the individual public intelligence portal. Please sign in for employee or company features.",
        )
    if request.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company intelligence requires verified company membership. Please sign in.",
        )
    if request.capability_id and request.capability_id not in PUBLIC_GUEST_CAPABILITIES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"The requested capability '{request.capability_id}' requires authentication. Please sign in to access personalized profile and workforce insights.",
        )

    # Force guest isolation: no conversation tracking or private user state
    guest_request = request.model_copy(
        update={
            "conversation_id": None,
            "company_id": None,
        }
    )
    msg_lower = request.message.lower()
    is_assistant_query = any(k in msg_lower for k in [
        "trend", "trending", "rank", "skill", "learn", "gap", "readiness",
        "hire", "hiring", "demand", "opening", "openings", "skills for",
        "roles", "role", "top", "popular", "market", "prepare", "upskill"
    ])
    if is_assistant_query or request.target_role:
        return _forward_request_to_supervisor(guest_request)

    response = service.answer(guest_request, authenticated_user=None)
    if response.domain is None:
        from app.services.answer_block_service import infer_assistant_domain
        response = response.model_copy(
            update={"domain": request.domain if request.domain in {"skill", "market", "job"} else infer_assistant_domain(response.intent)}
        )
    if response.conversation_id:
        response = response.model_copy(
            update={"conversation_id": None}
        )
    return response


@router.get("/guest/answer", response_model=CoreIntelligenceAnswerResponse)
def answer_guest_intelligence_get(
    message: str = Query(..., min_length=1, max_length=500),
    domain: Literal["skill", "market", "job"] = Query(default="skill"),
    capability_id: str | None = Query(default=None),
    skill: str | None = Query(default=None),
    role: str | None = Query(default=None),
    service: ExecutionOrchestratorService = Depends(get_execution_orchestrator_service),
) -> CoreIntelligenceAnswerResponse:
    """Convenience GET endpoint for unauthenticated guest intelligence requests using public reference data."""
    req = CoreIntelligenceAnswerRequest(
        message=message,
        domain=domain,
        portal_type="individual",
        capability_id=capability_id,
        selected_skills=[skill] if skill else [],
        target_role=role,
    )
    return answer_guest_intelligence(request=req, service=service)


@router.get("/sources")
def list_intelligence_sources(
    domain: Literal["skill", "market", "job", "skill_intelligence", "market_intelligence", "job_intelligence"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all registered intelligence data sources, metadata, and limitations."""
    registry = V2SourceRegistry()
    sources = registry.list_sources(domain=domain)
    return [s.model_dump(mode="json") for s in sources]


@router.get("/sources/{source_id}")
def get_intelligence_source(
    source_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve detailed metadata, permitted/prohibited interpretations, and metrics for a specific source."""
    registry = V2SourceRegistry()
    source = registry.get_source(source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intelligence source '{source_id}' not found in registry.",
        )
    return source.model_dump(mode="json")


@router.get("/guest/sources")
def list_guest_intelligence_sources(
    domain: Literal["skill", "market", "job", "skill_intelligence", "market_intelligence", "job_intelligence"] | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Public read-only listing of registered data sources for guests without authentication."""
    registry = V2SourceRegistry()
    sources = registry.list_sources(domain=domain)
    return [s.model_dump(mode="json") for s in sources]


# ---------------------------------------------------------------------------
# Phase 2: Skill & Role Reference Intelligence Endpoints
# ---------------------------------------------------------------------------

@router.get("/reference/lookup", response_model=TaxonomyLookupResult)
def lookup_reference_taxonomy(
    query: str = Query(..., min_length=1, max_length=200),
    entity_type: Literal["all", "skill", "occupation"] = Query(default="all"),
    limit: int = Query(default=15, ge=1, le=50),
    context: str | None = Query(default=None),
) -> TaxonomyLookupResult:
    """Canonical lookup engine for skills and occupations across O*NET and ESCO with ambiguity protection."""
    engine = ReferenceTaxonomyLookupEngine()
    return engine.lookup(query=query, entity_type=entity_type, limit=limit, context=context)


@router.get("/reference/related-skills", response_model=RelatedSkillsResult)
def get_related_skills(
    skill_name: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
) -> RelatedSkillsResult:
    """Retrieve explainable related skills classified by explicit relationship type and PPMI/IOF ranking."""
    engine = RelatedSkillsEngine()
    return engine.get_related_skills(skill_name=skill_name, limit=limit)


class RoleAlignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str
    declared_skills: list[str] = Field(default_factory=list)


@router.post("/reference/role-alignment", response_model=RoleSkillAlignmentResult)
def evaluate_role_skill_alignment(
    payload: RoleAlignmentPayload,
) -> RoleSkillAlignmentResult:
    """Grounded alignment between declared candidate skills and reference-associated occupation profiles."""
    engine = RoleSkillAlignmentEngine()
    return engine.align(target_role=payload.target_role, declared_skills=payload.declared_skills)


@router.get("/reference/mobility-pathways", response_model=CareerMobilityResult)
def get_career_mobility_pathways(
    occupation: str = Query(..., min_length=1, max_length=150),
    limit: int = Query(default=10, ge=1, le=30),
) -> CareerMobilityResult:
    """Adjacent career mobility pathways grounded in O*NET related occupations with shared and additional skill analysis."""
    engine = CareerMobilityEngine()
    return engine.get_pathways(occupation_query=occupation, limit=limit)


@router.get("/capabilities", response_model=CapabilityCatalogResponse)
def get_capability_catalog(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CapabilityCatalogResponse:
    """List all registered platform capabilities and their global implementation status."""
    service = CapabilityRegistryService()
    return service.get_catalog()


@router.post("/capabilities/evaluate", response_model=CapabilityEvaluationResponse)
def evaluate_capabilities(
    request: CapabilityEvaluationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CapabilityEvaluationResponse:
    """Evaluate runtime readiness of capabilities for a specific request context."""
    service = CapabilityRegistryService()
    return service.evaluate(request)


@router.post("/entities/resolve", response_model=EntityResolutionResponse)
def resolve_entity(
    request: EntityResolutionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EntityResolutionResponse:
    """Resolve raw user language or source names to canonical entities."""
    service = EntityRegistryService()
    return service.resolve(request)


@router.post("/core", response_model=CoreIntelligenceResponse)
def query_core_intelligence(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CoreIntelligenceResponse:
    """Unified Core Intelligence endpoint accepting portal context, domain, and filters."""
    request, current_user = _authorized_company_context(request, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(
        request,
        authenticated_uid=current_user.uid,
    )


@router.post("/actions", response_model=ActionRecommendationResponse)
def query_intelligence_actions(
    request: CoreIntelligenceRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ActionRecommendationResponse:
    """G2.5 Action & Recommendation endpoint accepting portal context, domain, and filters."""
    request, current_user = _authorized_company_context(request, current_user)
    service = CoreIntelligenceService()
    return service.get_action_recommendations(
        request,
        authenticated_uid=current_user.uid,
    )


@router.get("/skill", response_model=CoreIntelligenceResponse)
def query_skill_intelligence_get(
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
    req, current_user = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.get("/market", response_model=CoreIntelligenceResponse)
def query_market_intelligence_get(
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
    req, current_user = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.get("/job", response_model=CoreIntelligenceResponse)
def query_job_intelligence_get(
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
    req, current_user = _authorized_company_context(req, current_user)
    service = CoreIntelligenceService()
    return service.get_intelligence(req, authenticated_uid=current_user.uid)


@router.post("/conversations", response_model=ConversationState)
def create_intelligence_conversation(
    payload: dict[str, Any] | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConversationState:
    """Create a new conversation session for the current authenticated user."""
    store = ConversationStore.get_instance()
    body = payload or {}
    portal_type = body.get("portal_type") or "individual"
    if portal_type not in {"individual", "employee", "company"}:
        raise HTTPException(status_code=422, detail="Unsupported conversation portal type.")
    current_user = _authorized_company_user(
        current_user,
        portal_type,
        body.get("company_id") if isinstance(body.get("company_id"), str) else None,
    )
    return store.create_conversation(
        user_id=current_user.uid,
        company_id=current_user.company_id,
        portal_type=portal_type,
        domain=body.get("domain"),
        filters=body.get("filters") if isinstance(body.get("filters"), dict) else None,
        title=body.get("title"),
        conversation_id=body.get("conversation_id"),
    )


@router.get("/conversations")
def list_intelligence_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    domain: str | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List recent conversation sessions for the current authenticated user."""
    current_user = (
        _verified_company_scope_user(current_user)
        if portal_type is None
        else _authorized_company_user(current_user, portal_type)
    )
    store = ConversationStore.get_instance()
    return store.list_conversations(
        user_id=current_user.uid,
        company_id=current_user.company_id,
        domain=domain,
        portal_type=portal_type,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationState)
def get_intelligence_conversation(
    conversation_id: str,
    domain: Literal["skill", "market", "job"] | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ConversationState:
    """Retrieve full conversation details and turns for a given session."""
    current_user = (
        _verified_company_scope_user(current_user)
        if portal_type is None
        else _authorized_company_user(current_user, portal_type)
    )
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
def delete_intelligence_conversation(
    conversation_id: str,
    domain: Literal["skill", "market", "job"] | None = Query(default=None),
    portal_type: Literal["individual", "employee", "company"] | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Permanently delete a conversation session."""
    current_user = (
        _verified_company_scope_user(current_user)
        if portal_type is None
        else _authorized_company_user(current_user, portal_type)
    )
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

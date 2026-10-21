"""Typed data models for G2.6 Task 5: Intent Resolver + Context Planner.

Defines the structured plan contract that routes natural language user requests
into canonical entities, capability requirements, readiness evaluations, and
clarification questions without executing unverified operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.capability_registry import CapabilityEvaluationResult, CapabilityId
from app.models.entity_registry import CanonicalEntity, EntityCandidate
from app.models.skill_intelligence import MarketObservation
from app.analytics.ai_disruption import AIExposureDatasetProvenance, TaskExposureRecord

PlanStatus = Literal[
    "ready_to_execute",
    "requires_clarification",
    "insufficient_data",
    "blocked",
    "unsupported",
]

IntentCategory = Literal[
    "general_explanation",
    "explain_concept",
    "resolve_entity",
    "lookup_skill_reference",
    "lookup_occupation",
    "crosswalk_occupation_software",
    "crosswalk_related_occupations",
    "retrieve_snapshot",
    "retrieve_history",
    "analyze_trend",
    "analyze_skill_health",
    "estimate_skill_half_life",
    "rank_skill_trends",
    "compare_entities",
    "retrieve_evidence",
    "analyze_skill_gap",
    "synthesize_actions",
    "search_jobs",
    "analyze_company_workforce",
    "forecast_future_demand",
    "analyze_ai_task_exposure",
    "simulate_workforce_scenarios",
    "unsupported_or_unclear",
]

ContextSource = Literal[
    "supplied_by_user",
    "authenticated_state",
    "retrieved_by_service",
    "missing",
]


class ContextFieldItem(BaseModel):
    """Single context parameter tracked in the plan."""

    model_config = ConfigDict(extra="forbid")

    field_name: str
    value: Any = None
    source: ContextSource
    description: str


class ResolvedEntityItem(BaseModel):
    """Entity mention extracted from user query and resolved via EntityRegistryService."""

    model_config = ConfigDict(extra="forbid")

    raw_token: str
    resolution_status: Literal["resolved", "ambiguous", "not_found"]
    canonical_entity: CanonicalEntity | None = None
    candidates: list[EntityCandidate] = Field(default_factory=list)
    is_primary: bool = True
    match_reason: str | None = None


class IntelligencePlanRequest(BaseModel):
    """User prompt and ambient application context submitted for planning."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    portal_type: Literal["individual", "employee", "company"] | None = None
    domain: Literal["skill", "market", "job"] | None = None
    capability_id: CapabilityId | None = None
    location: str | None = None
    time_range: str = "30d"
    target_role: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    selected_roles: list[str] = Field(default_factory=list)
    selected_companies: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    company_id: str | None = None
    conversation_id: str | None = None
    clear_context: bool = False
    observations: list[MarketObservation] = Field(default_factory=list)
    task_exposure_records: list[TaskExposureRecord] = Field(default_factory=list)
    dataset_provenance: AIExposureDatasetProvenance | None = None
    context_override: dict[str, Any] = Field(default_factory=dict)


class IntelligencePlanResponse(BaseModel):
    """Auditable structured plan produced by Intent Resolver and Context Planner."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_message: str
    portal_type: str
    intent: str
    intent_confidence: float
    intent_explanation: str
    conversation_id: str | None = None
    entities: list[ResolvedEntityItem] = Field(default_factory=list)
    primary_capability: str | None = None
    dependency_capabilities: list[str] = Field(default_factory=list)
    selected_capabilities: list[str] = Field(default_factory=list)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    missing_context: list[str] = Field(default_factory=list)
    clarification_required: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    readiness_results: list[CapabilityEvaluationResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    plan_status: PlanStatus
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

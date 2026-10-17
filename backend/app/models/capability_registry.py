"""Typed data models for G2.6 Capability Registry.

Defines the platform's control layer for intelligence capabilities, specifying
supported operations, required inputs, data signals, readiness requirements,
and runtime execution status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.skill_intelligence import MarketObservation
from app.analytics.ai_disruption import AIExposureDatasetProvenance, TaskExposureRecord

CapabilityState = Literal[
    "available",
    "partial",
    "insufficient_data",
    "blocked",
    "building",
]

CapabilityId = Literal[
    "entity_resolution",
    "skill_technology_reference",
    "occupation_lookup",
    "occupation_software_skills",
    "related_occupations",
    "market_snapshot",
    "historical_signal_retrieval",
    "trend_velocity_analysis",
    "skill_health_analysis",
    "skill_half_life_analysis",
    "evidence_provenance_retrieval",
    "skill_gap_role_fit",
    "action_recommendations",
    "job_posting_search",
    "company_intelligence",
    "skill_forecasting_half_life",
    "ai_task_exposure",
    "workforce_what_if_simulation",
]


class CapabilityRecord(BaseModel):
    """Deterministic capability record describing a platform capability."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    description: str
    supported_domains: list[str] = Field(default_factory=list)
    supported_intent: str
    supported_entity_types: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    required_signals: list[str] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    min_readiness_periods: int | None = None
    global_status: CapabilityState
    reason_code: str
    handler: str | None = None
    limitations: list[str] = Field(default_factory=list)
    provenance_requirements: list[str] = Field(default_factory=list)


class CapabilityCatalogResponse(BaseModel):
    """Platform capability catalog response listing all registered capabilities."""

    model_config = ConfigDict(extra="forbid")

    total_capabilities: int
    available_count: int
    partial_count: int
    insufficient_data_count: int = 0
    blocked_count: int = 0
    building_count: int
    capabilities: list[CapabilityRecord]


class CapabilityEvaluationRequest(BaseModel):
    """Request to evaluate runtime readiness of one or more capabilities."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    portal_type: Literal["individual", "employee", "company"] = "individual"
    time_range: str = "30d"
    location: str | None = None
    target_role: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    observations: list[MarketObservation] = Field(default_factory=list)
    task_exposure_records: list[TaskExposureRecord] = Field(default_factory=list)
    dataset_provenance: AIExposureDatasetProvenance | None = None
    context_override: dict[str, Any] = Field(default_factory=dict)


class CapabilityEvaluationResult(BaseModel):
    """Runtime evaluation result of a single capability for a specific request context."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    global_status: CapabilityState
    runtime_status: CapabilityState
    can_execute: bool
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str
    missing_requirements: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance_references: list[str] = Field(default_factory=list)
    provenance_requirements: list[str] = Field(default_factory=list)
    readiness_state: str | None = None


class CapabilityEvaluationResponse(BaseModel):
    """Response containing runtime evaluation results across requested capabilities."""

    model_config = ConfigDict(extra="forbid")

    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_summary: dict[str, Any] = Field(default_factory=dict)
    results: list[CapabilityEvaluationResult] = Field(default_factory=list)

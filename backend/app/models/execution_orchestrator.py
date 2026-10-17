"""Typed data models for G2.6 Task 6: Core Intelligence Execution Orchestrator.

Defines the response contract, execution status, structured facts, and evidence items
returned by the orchestrator after evaluating plan readiness and executing verified
capability handlers.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.intent_planner import PlanStatus
from app.models.capability_registry import CapabilityId
from app.models.skill_intelligence import MarketObservation
from app.models.intelligence_contract import IntelligenceMetricResult
from app.analytics.ai_disruption import AIExposureDatasetProvenance, TaskExposureRecord


ExecutionStatus = Literal[
    "completed",
    "requires_clarification",
    "insufficient_data",
    "blocked",
    "unsupported",
    "failed",
]

_TIME_RANGE_ALIASES = {
    "7 days": "7d",
    "30 days": "30d",
    "90d": "3m",
    "90 days": "3m",
    "180d": "6m",
    "180 days": "6m",
    "365d": "1y",
    "365 days": "1y",
    "12 months": "1y",
    "1 year": "1y",
    "12m": "1y",
    "max available": "max",
    "max_available": "max",
    "all": "max",
}


def _normalize_time_range(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = _TIME_RANGE_ALIASES.get(normalized, normalized)
    if normalized not in {"7d", "30d", "3m", "6m", "1y", "max"}:
        raise ValueError("time_range must be 7d, 30d, 3m, 6m, 1y, or max.")
    return normalized


class StructuredFact(BaseModel):
    """Verifiable structured fact derived directly from capability handler execution."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str | None = None
    fact_type: str
    entity_name: str | None = None
    canonical_entity_id: str | None = None
    entity_type: str | None = None
    metric_name: str
    metric_value: Any
    unit: str | None = None
    denominator: float | None = None
    period: str | None = None
    timestamp: datetime | None = None
    source: str
    data_origin: str | None = None
    history_type: str | None = None
    series_id: str | None = None
    panel_version: str | None = None
    quality_state: str | None = None
    readiness_state: str | None = None
    calculation_version: str | None = None
    provenance_id: str | None = None
    evidence_reference: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    """Verifiable citation / provenance item grounded in retrieved reference or observation records."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: str
    signal_type: str
    measured_signal_type: str | None = None
    period: str | None = None
    unit: str | None = None
    data_origin: str = "real"
    history_type: str | None = None
    series_id: str | None = None
    location: str | None = None
    scope: str | None = None
    query_id: str | None = None
    panel_version: str | None = None
    fetch_run_id: str | None = None
    supporting_fetch_run_ids: list[str] = Field(default_factory=list)
    source_url: str | None = None
    provenance_id: str | None = None
    supporting_observation_ids: list[str] = Field(default_factory=list)
    supporting_source_urls: list[str] = Field(default_factory=list)
    freshness_state: str | None = None
    quality: str = "valid"
    confidence: float | None = None
    description: str


class SelectedEntityResolution(BaseModel):
    """Canonical entity selection resolved for the submitted analysis context."""

    entity_id: str | None = None
    entity_type: str | None = None
    canonical_name: str
    resolution_status: Literal["resolved", "ambiguous", "not_found", "unsupported"]


class CoreIntelligenceAnswerRequest(BaseModel):
    """User prompt and ambient application context submitted for intelligence answering."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    portal_type: Literal["individual", "employee", "company"] | None = None
    domain: Literal["skill", "market", "job"] | None = None
    capability_id: CapabilityId | None = None
    location: str | None = None
    time_range: str = Field(default="30d", max_length=32)
    target_role: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    selected_roles: list[str] = Field(default_factory=list)
    selected_companies: list[str] = Field(default_factory=list)
    company_id: str | None = None
    conversation_id: str | None = None
    client_message_id: str | None = None
    regenerate: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)
    clear_context: bool = False
    observations: list[MarketObservation] = Field(default_factory=list)
    task_exposure_records: list[TaskExposureRecord] = Field(default_factory=list)
    dataset_provenance: AIExposureDatasetProvenance | None = None
    context_override: dict[str, Any] = Field(default_factory=dict)

    @field_validator("selected_skills", "selected_roles", "selected_companies")
    @classmethod
    def bound_selected_entities(cls, values: list[str]) -> list[str]:
        if len(values) > 20:
            raise ValueError("At most 20 entities may be selected per request.")
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            token = value.strip()
            if not token or len(token) > 200:
                raise ValueError("Selected entity values must contain 1 to 200 characters.")
            key = token.casefold()
            if key not in seen:
                normalized.append(token)
                seen.add(key)
        return normalized

    @field_validator("filters", "context_override")
    @classmethod
    def bound_request_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 24 or len(json.dumps(value, ensure_ascii=True, default=str)) > 8192:
            raise ValueError("Request context exceeds the supported size.")
        if any(not isinstance(key, str) or len(key) > 64 for key in value):
            raise ValueError("Request context keys must be strings of at most 64 characters.")
        return value

    @field_validator("time_range")
    @classmethod
    def normalize_time_range(cls, value: str) -> str:
        return _normalize_time_range(value)

    @model_validator(mode="after")
    def validate_filter_domain(self) -> "CoreIntelligenceAnswerRequest":
        filter_domain = self.filters.get("domain")
        if filter_domain is not None:
            normalized = str(filter_domain).strip().casefold()
            normalized = {
                "skills": "skill", "companies": "market", "company": "market",
                "jobs": "job", "roles": "job", "role": "job",
            }.get(normalized, normalized)
            if normalized not in {"skill", "market", "job"}:
                raise ValueError("filters.domain must identify skill, market, or job intelligence.")
            if self.domain and self.domain != normalized:
                raise ValueError("domain conflicts with filters.domain.")
            if self.domain is None:
                self.domain = normalized  # type: ignore[assignment]
        filter_time_ranges = [
            value for value in (
                self.filters.get("time_range"),
                self.filters.get("requested_time_window"),
            )
            if value is not None and value != ""
        ]
        if filter_time_ranges:
            if any(not isinstance(value, str) for value in filter_time_ranges):
                raise ValueError("Committed time-range filters must be strings.")
            normalized_ranges = {_normalize_time_range(value) for value in filter_time_ranges}
            if len(normalized_ranges) != 1:
                raise ValueError("Committed time-range filters conflict.")
            committed_range = normalized_ranges.pop()
            if "time_range" in self.model_fields_set and self.time_range != committed_range:
                raise ValueError("time_range conflicts with the committed time-range filter.")
            self.time_range = committed_range
        filter_location = self.filters.get("location")
        if filter_location is not None and filter_location != "":
            if not isinstance(filter_location, str):
                raise ValueError("filters.location must be a string.")
            filter_location = filter_location.strip()
            if not filter_location or len(filter_location) > 160:
                raise ValueError("filters.location must contain 1 to 160 characters.")
            if self.location and self.location.casefold() != filter_location.casefold():
                raise ValueError("location conflicts with filters.location.")
            self.location = None if filter_location.casefold() == "global" else filter_location
        country = self.filters.get("country")
        if country is not None and country != "":
            if not isinstance(country, str) or not re.fullmatch(r"[A-Za-z]{2}", country.strip()):
                raise ValueError("filters.country must be a two-letter country code.")
            self.filters["country"] = country.strip().lower()
        if "scope_empty" in self.filters and not isinstance(self.filters["scope_empty"], bool):
            raise ValueError("filters.scope_empty must be a boolean.")
        if self.filters.get("scope") is not None:
            if not isinstance(self.filters["scope"], str) or len(self.filters["scope"].strip()) > 64:
                raise ValueError("filters.scope must be a string of at most 64 characters.")
            self.filters["scope"] = self.filters["scope"].strip()
        selection_filters = (
            ("selected_skill", "selected_skills"),
            ("selected_company", "selected_companies"),
            ("selected_role", "selected_roles"),
        )
        for filter_name, selection_name in selection_filters:
            selected_value = self.filters.get(filter_name)
            if selected_value is None or selected_value == "":
                continue
            if not isinstance(selected_value, str):
                raise ValueError(f"filters.{filter_name} must be a string.")
            selected_value = selected_value.strip()
            if not selected_value or len(selected_value) > 200:
                raise ValueError(f"filters.{filter_name} must contain 1 to 200 characters.")
            selections = getattr(self, selection_name)
            if selections and selected_value.casefold() not in {value.casefold() for value in selections}:
                raise ValueError(f"filters.{filter_name} conflicts with {selection_name}.")
            if not selections:
                setattr(self, selection_name, [selected_value])
            if filter_name == "selected_role" and self.target_role is None:
                self.target_role = selected_value
            elif filter_name == "selected_role" and self.target_role.casefold() != selected_value.casefold():
                raise ValueError("filters.selected_role conflicts with target_role.")
        if self.location is not None and len(self.location) > 160:
            raise ValueError("location must be at most 160 characters.")
        if self.target_role is not None and len(self.target_role) > 200:
            raise ValueError("target_role must be at most 200 characters.")
        return self


class CoreIntelligenceAnswerResponse(BaseModel):
    """Validated, traceable response produced by Core Intelligence Execution Orchestrator."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_message: str
    portal_type: str
    domain: Literal["skill", "market", "job"] | None = None
    intent: str
    plan_status: PlanStatus
    execution_status: ExecutionStatus
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] = "insufficient_data"
    answer: str
    answer_origin: Literal["deterministic", "gemini"] = "deterministic"
    conversation_id: str | None = None
    client_message_id: str | None = None
    resolved_entity: str | None = None
    selected_entities: list[SelectedEntityResolution] = Field(default_factory=list)
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    unapplied_filters: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, Any] | None = None
    freshness: dict[str, Any] = Field(default_factory=dict)
    history_type: str = "platform_collected"
    source_coverage: dict[str, Any] = Field(default_factory=dict)
    facts: list[StructuredFact] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    metric_results: list[IntelligenceMetricResult] = Field(default_factory=list)
    capabilities_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

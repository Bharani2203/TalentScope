"""Greenfield Intelligence Engine V2 — Shared Contracts & Evidence Standards.

Defines standardized evidence items, structured facts, execution statuses,
and domain models ensuring strict compliance with truth-in-data rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.execution_orchestrator import (
    EvidenceItem,
    ExecutionStatus,
    SelectedEntityResolution,
    StructuredFact,
)

V2ExecutionStatus = ExecutionStatus


SignalFamily = Literal[
    "hiring_demand",
    "developer_adoption",
    "community_interest",
    "public_attention",
    "reference_taxonomy",
    "benchmark",
    "evidence_readiness",
]

DataOrigin = Literal[
    "real",
    "test",
    "local_reference_dataset",
    "benchmark",
    "unavailable",
]

TimeGrain = Literal[
    "month",
    "quarter",
    "static",
    "point_in_time",
]


class V2EvidenceItem(BaseModel):
    """Standardized citation and provenance item for all intelligence outputs."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source: str
    signal_family: SignalFamily
    measured_signal_type: str
    period: str | None = None
    time_grain: TimeGrain = "month"
    unit: str | None = None
    geography: str | None = None
    scope: str | None = None
    data_origin: DataOrigin = "real"
    history_type: str | None = None
    series_id: str | None = None
    query_id: str | None = None
    panel_version: str | None = None
    fetch_run_id: str | None = None
    source_url: str | None = None
    provenance_id: str | None = None
    canonical_mapping: str | None = None
    taxonomy_version: str | None = None
    extractor_version: str | None = None
    sample_size: int | None = None
    denominator: float | None = None
    readiness_state: str = "observed"
    confidence_status: str | None = None
    quality: str = "valid"
    description: str

    def to_public_evidence(self) -> EvidenceItem:
        """Convert to the public EvidenceItem model for frontend compatibility."""
        return EvidenceItem(
            evidence_id=self.evidence_id,
            source=self.source,
            signal_type=self.signal_family,
            measured_signal_type=self.measured_signal_type,
            period=self.period,
            unit=self.unit,
            data_origin=self.data_origin,
            history_type=self.history_type,
            series_id=self.series_id,
            location=self.geography,
            scope=self.scope,
            query_id=self.query_id,
            panel_version=self.panel_version,
            fetch_run_id=self.fetch_run_id,
            source_url=self.source_url,
            provenance_id=self.provenance_id,
            supporting_observation_ids=[],
            supporting_source_urls=[self.source_url] if self.source_url else [],
            freshness_state="fresh" if self.data_origin != "unavailable" else "unavailable",
            readiness_state=self.readiness_state,
            quality=self.quality,
            confidence=1.0 if self.confidence_status == "high" else 0.8 if self.confidence_status == "medium" else None,
            description=self.description,
        )


class V2StructuredFact(BaseModel):
    """Verifiable structured fact derived directly from an intelligence capability."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
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
    data_origin: DataOrigin = "real"
    history_type: str | None = None
    series_id: str | None = None
    panel_version: str | None = None
    quality_state: str = "valid"
    readiness_state: str = "observed"
    calculation_version: str = "v2.0"
    provenance_id: str | None = None
    evidence_reference: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    def to_public_fact(self) -> StructuredFact:
        """Convert to the public StructuredFact model for frontend compatibility."""
        return StructuredFact(
            fact_id=self.fact_id,
            fact_type=self.fact_type,
            entity_name=self.entity_name,
            canonical_entity_id=self.canonical_entity_id,
            entity_type=self.entity_type,
            metric_name=self.metric_name,
            metric_value=self.metric_value,
            unit=self.unit,
            denominator=self.denominator,
            period=self.period,
            timestamp=self.timestamp,
            source=self.source,
            data_origin=self.data_origin,
            history_type=self.history_type,
            series_id=self.series_id,
            panel_version=self.panel_version,
            quality_state=self.quality_state,
            readiness_state=self.readiness_state,
            calculation_version=self.calculation_version,
            provenance_id=self.provenance_id,
            evidence_reference=self.evidence_reference,
            details=self.details,
        )


RelationshipType = Literal[
    "direct_technical_relation",
    "same_occupation_cooccurrence",
    "general_occupational_association",
]


class TaxonomyLookupItem(BaseModel):
    """Detailed record for a matched skill or occupation in local reference datasets."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["skill", "occupation"]
    canonical_id: str
    name: str
    taxonomy: str
    description: str | None = None
    source: str
    status: Literal["matched", "partial", "ambiguous", "unmapped"] = "matched"
    ambiguity_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaxonomyLookupResult(BaseModel):
    """Unified outcome for skill and occupation lookup queries."""

    model_config = ConfigDict(extra="forbid")

    query: str
    status: Literal["ready", "partial", "ambiguous", "insufficient_data"]
    total_matches: int
    results: list[TaxonomyLookupItem] = Field(default_factory=list)
    clarification_needed: bool = False
    explanation: str
    limitations: list[str] = Field(default_factory=list)


class RelatedSkillItem(BaseModel):
    """Explainable related skill with explicit relationship type and ranking."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str
    canonical_id: str
    relationship_type: RelationshipType
    source: str
    supporting_relationship: str
    ranking_method: str
    ranking_score: float
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelatedSkillsResult(BaseModel):
    """Outcome for related-skill intelligence with deterministic explainability."""

    model_config = ConfigDict(extra="forbid")

    target_skill: str
    canonical_id: str | None = None
    status: Literal["ready", "partial", "ambiguous", "insufficient_data"]
    related_skills: list[RelatedSkillItem] = Field(default_factory=list)
    explanation: str
    limitations: list[str] = Field(default_factory=list)


class RoleSkillAlignmentResult(BaseModel):
    """Truthful role-skill alignment distinguishing reference baselines from live job requirements."""

    model_config = ConfigDict(extra="forbid")

    role_name: str
    canonical_occupation_id: str | None = None
    canonical_occupation_title: str | None = None
    taxonomy_source: str
    reference_associated_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    unmatched_reference_skills: list[str] = Field(default_factory=list)
    unresolved_skills: list[str] = Field(default_factory=list)
    ambiguous_skills: list[dict[str, str]] = Field(default_factory=list)
    status: Literal["ready", "partial", "ambiguous", "insufficient_data"]
    disclaimer: str
    explanation: str
    limitations: list[str] = Field(default_factory=list)


class CareerMobilityPathwayItem(BaseModel):
    """Adjacent occupation grounded in O*NET related occupations and skill overlap."""

    model_config = ConfigDict(extra="forbid")

    destination_occupation_title: str
    destination_soc_code: str
    relatedness_tier: str
    shared_skills: list[str] = Field(default_factory=list)
    additional_destination_skills: list[str] = Field(default_factory=list)
    relationship_nature: str
    explanation: str


class CareerMobilityResult(BaseModel):
    """Outcome for career mobility pathways grounded in official reference datasets."""

    model_config = ConfigDict(extra="forbid")

    source_occupation_title: str
    source_soc_code: str | None = None
    status: Literal["ready", "partial", "ambiguous", "insufficient_data"]
    pathways: list[CareerMobilityPathwayItem] = Field(default_factory=list)
    explanation: str
    limitations: list[str] = Field(default_factory=list)

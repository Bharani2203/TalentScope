"""Typed response and evidence models for the G1.5 Evidence & Provenance API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FetchRunEvidence(EvidenceModel):
    fetch_run_id: str
    source: str
    status: str
    collected_at: str | None = None
    records_fetched: int | None = None
    records_processed: int | None = None
    records_rejected: int | None = None
    records_filtered: int | None = None
    location: str | None = None
    country: str | None = None
    query_id: str | None = None


class RawArchiveEvidence(EvidenceModel):
    raw_archive_id: str
    provider: str
    fetch_run_id: str
    archive_reference: str
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    collected_at: str | None = None
    archived_at: str | None = None


class ObservationEvidence(EvidenceModel):
    observation_id: str
    source: str
    skill: str
    canonical_skill_id: str | None = None
    signal_type: Literal["demand", "adoption", "interest", "context"]
    period: str
    location: str | None = None
    scope: str
    value: float
    unit: str | None = None
    data_origin: Literal["real", "demo", "synthetic", "test", "mixed", "unavailable"] = "real"
    history_type: Literal["platform_collected", "backfill", "snapshot", "mixed", "unavailable"] = "platform_collected"
    fetch_run_id: str | None = None
    series_id: str | None = None
    panel_version: str | None = None
    observed_at: str | None = None


class CalculationRecordEvidence(EvidenceModel):
    calculation_record_id: str
    calculation_version: str
    formula_id: str
    metric: str
    window: str
    periods_used: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    result_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class SkillEvidenceItem(EvidenceModel):
    source: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    canonical_skill_id: str | None
    canonical_name: str
    period: str
    metric: Literal["raw_count", "normalized_share", "adoption_snapshot", "composite_demand"]
    raw_value: float
    normalized_value: float | None = None
    denominator: float | None = None
    data_state: Literal["ready", "fresh", "stale", "insufficient_data", "building", "unavailable", "error"]
    trend: Literal["Increasing", "Declining", "Stable", "Insufficient Data"]
    velocity: float | None = None
    growth_pct: float | None = None
    slope: float | None = None
    unit: str | None = None
    velocity_unit: str | None = None
    slope_unit: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    periods_used: list[str] = Field(default_factory=list)
    readiness_state: str | None = None
    confidence: float | None = None
    calculation_version: str
    series_id: str | None = None
    panel_version: str | None = None
    data_origin: Literal["real", "demo", "synthetic", "test", "mixed", "unavailable"] = "real"
    history_type: Literal["platform_collected", "backfill", "snapshot", "mixed", "unavailable"] = "platform_collected"
    
    # Provenance links
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    raw_archive_ids: list[str] = Field(default_factory=list)
    calculation_record_ids: list[str] = Field(default_factory=list)

    # Detailed evidence traces
    fetch_runs: list[FetchRunEvidence] = Field(default_factory=list)
    raw_archives: list[RawArchiveEvidence] = Field(default_factory=list)
    observations: list[ObservationEvidence] = Field(default_factory=list)
    calculations: list[CalculationRecordEvidence] = Field(default_factory=list)


class SkillEvidenceResponse(EvidenceModel):
    skill: str
    canonical_skill_id: str | None
    canonical_name: str
    data_state: Literal["ready", "fresh", "stale", "insufficient_data", "building", "unavailable", "error"]
    evidence_count: int
    items: list[SkillEvidenceItem] = Field(default_factory=list)
    sources_represented: list[str] = Field(default_factory=list)
    signal_types_represented: list[str] = Field(default_factory=list)

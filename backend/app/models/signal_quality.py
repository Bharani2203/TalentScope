"""Typed data models for G1.8: Historical Data Validation & Signal Quality."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

SeriesQualityState = Literal[
    "valid",
    "insufficient_data",
    "incomplete",
    "incomparable",
    "stale",
    "provider_failure",
    "low_coverage",
    "configuration_changed",
]

SeriesComparabilityStatus = Literal[
    "compatible",
    "incomparable",
    "drift_detected",
    "unknown",
]


class CoverageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_observations: int = 0
    unique_postings: int = 0
    periods_count: int = 0
    has_valid_denominator: bool = False
    sample_size_classification: Literal["adequate", "low", "minimal", "empty"] = "adequate"
    records_fetched_sum: int | None = None
    records_rejected_sum: int | None = None
    anomaly_detected: bool = False
    anomaly_details: str | None = None


class SeriesQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    canonical_skill_id: str | None
    canonical_name: str
    series_id: str | None = None
    series_ids: list[str] = Field(default_factory=list)
    unit: str | None = None
    denominator_unit: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    panel_version: str | None = None
    data_origin: str | None = None
    history_type: str | None = None
    extractor_version: str | None = None
    quality_state: SeriesQualityState
    comparability_status: SeriesComparabilityStatus
    periods_found: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    is_analytically_sufficient: bool = False
    coverage_metadata: CoverageMetadata = Field(default_factory=CoverageMetadata)
    issues: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    query_ids: list[str] = Field(default_factory=list)
    panel_versions: list[str] = Field(default_factory=list)


class QualityAssessmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_quality_state: SeriesQualityState
    total_series_assessed: int = 0
    compatible_series_count: int = 0
    incomparable_series_count: int = 0
    drift_detected_count: int = 0
    low_coverage_count: int = 0
    reports: list[SeriesQualityReport] = Field(default_factory=list)

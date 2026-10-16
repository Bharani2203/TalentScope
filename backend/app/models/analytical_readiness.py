"""Typed data models for G1.9: Analytical Readiness & Forecast Input Contract."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.signal_quality import SeriesComparabilityStatus, SeriesQualityState

ReadinessState = Literal[
    "not_ready",
    "ready_for_trend",
    "ready_for_forecast",
    "blocked_quality",
    "blocked_coverage",
    "blocked_configuration",
    "blocked_missing_period",
]


class AnalyticalReadinessReport(BaseModel):
    """Deterministic readiness assessment for a single partitioned series."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    canonical_skill_id: str | None
    canonical_skill_name: str
    canonical_name: str | None = None
    series_id: str | None = None
    series_ids: list[str] = Field(default_factory=list)
    panel_version: str | None = None
    query_ids: list[str] = Field(default_factory=list)
    query_id: str | None = None
    scope: str | None = None
    location: str | None = None
    unit: str | None = None
    denominator_unit: str | None = None
    extractor_version: str | None = None
    data_origin: Literal["real", "demo"] | None = "real"
    history_type: Literal["platform_collected", "backfill", "snapshot"] | None = "platform_collected"
    periods_available: list[str] = Field(default_factory=list)
    consecutive_valid_periods: int = 0
    coverage_gaps: list[str] = Field(default_factory=list)
    quality_state: SeriesQualityState
    comparability_status: SeriesComparabilityStatus
    is_analytically_sufficient: bool = False
    is_trend_ready: bool = False
    is_forecast_ready: bool = False
    readiness_state: ReadinessState
    blocking_reasons: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)
    calculation_version: str = "analytical-readiness-v1"


class AnalyticalReadinessSummary(BaseModel):
    """Rollup summary of readiness across all evaluated series."""

    model_config = ConfigDict(extra="forbid")

    overall_readiness_state: ReadinessState
    total_series_evaluated: int = 0
    ready_for_trend_count: int = 0
    ready_for_forecast_count: int = 0
    blocked_count: int = 0
    not_ready_count: int = 0
    reports: list[AnalyticalReadinessReport] = Field(default_factory=list)


class ForecastObservationInput(BaseModel):
    """Single observation passing analytical gates, ready for future forecasting engine input."""

    model_config = ConfigDict(extra="forbid")

    canonical_skill_id: str | None
    canonical_skill_name: str
    canonical_name: str | None = None
    provider: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    period: str
    value: float
    normalized_value: float | None = None
    denominator: float | None = None
    series_id: str | None = None
    panel_version: str | None = None
    query_id: str | None = None
    scope: str | None = None
    extractor_version: str | None = None
    data_origin: Literal["real", "demo"] | None = "real"
    history_type: Literal["platform_collected", "backfill", "snapshot"] | None = "platform_collected"
    observation_id: str
    readiness_state: ReadinessState


class ForecastSeriesInput(BaseModel):
    """Future-facing forecast input series containing only verified, gate-passing observations."""

    model_config = ConfigDict(extra="forbid")

    series_id: str | None = None
    canonical_skill_id: str | None
    canonical_skill_name: str
    canonical_name: str | None = None
    provider: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    panel_version: str | None = None
    query_id: str | None = None
    scope: str | None = None
    observations: list[ForecastObservationInput] = Field(default_factory=list)
    readiness_report: AnalyticalReadinessReport

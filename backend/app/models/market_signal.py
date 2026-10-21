"""Typed data model for validated, aggregated market signals."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AggregatedMarketSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_skill_id: str | None
    canonical_name: str
    source: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    period: str
    metric: Literal["raw_count", "normalized_share", "adoption_snapshot", "composite_demand"]
    raw_value: float
    normalized_value: float | None = None
    denominator: float | None = None
    observation_count: int = 1
    data_origin: Literal["real", "demo", "synthetic", "test", "mixed", "unavailable"] = "real"
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot", "mixed", "unavailable"] = "platform_collected"
    data_state: Literal[
        "ready", "fresh", "stale", "insufficient_data", "building", "unavailable", "error",
        "incomparable", "configuration_changed", "incomplete", "low_coverage"
    ] = "insufficient_data"
    confidence: float | None = None
    series_id: str | None = None
    panel_version: str | None = None
    unit: str | None = None
    denominator_unit: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    extractor_version: str | None = None
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillTrendVelocityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    signal_type: Literal["demand", "adoption", "interest", "context"]
    canonical_skill_id: str | None
    canonical_name: str
    latest_period: str
    latest_value: float
    previous_period: str | None = None
    previous_value: float | None = None
    first_period: str | None = None
    first_value: float | None = None
    velocity: float | None = None
    growth_pct: float | None = None
    whole_window_change: float | None = None
    whole_window_pct_change: float | None = None
    latest_mom_change: float | None = None
    latest_mom_pct_change: float | None = None
    slope: float | None = None
    trend: Literal["Increasing", "Declining", "Stable", "Insufficient Data"]
    confidence: float | None = None
    data_state: Literal[
        "ready", "fresh", "stale", "insufficient_data", "building", "unavailable", "error",
        "incomparable", "configuration_changed", "incomplete", "low_coverage"
    ]
    periods_used: list[str]
    series: list[dict[str, Any]] = Field(default_factory=list)
    observation_count: int
    observation_ids: list[str]
    fetch_run_ids: list[str]
    series_id: str | None = None
    panel_version: str | None = None
    unit: str | None = None
    source_unit: str | None = None
    velocity_unit: str | None = None
    slope_unit: str | None = None
    period_grain: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    data_origin: Literal["real", "demo", "synthetic", "test", "mixed", "unavailable"] = "real"
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot", "mixed", "unavailable"] = "platform_collected"
    metric: Literal["raw_count", "normalized_share", "adoption_snapshot", "composite_demand"]
    calculation_version: str = "trend-velocity-theil-sen-v2-comparable-units"
    provider: str | None = None
    trend_direction: str | None = None
    trend_slope: float | None = None
    growth: float | None = None
    evidence_url: str | None = None
    readiness_state: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] | None = None

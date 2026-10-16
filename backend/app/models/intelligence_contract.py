"""Common evidence contract for measured and derived intelligence results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceMetricResult(BaseModel):
    """One observed or derived metric with an auditable evidence boundary."""

    model_config = ConfigDict(extra="forbid")

    capability: str
    status: Literal[
        "ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"
    ]
    metric_kind: Literal["observed", "predicted", "derived", "readiness"]
    canonical_entity_id: str | None = None
    entity_name: str | None = None
    series_id: str | None = None
    metric_name: str
    metric_value: Any = None
    unit: str | None = None
    denominator: float | None = None
    denominator_unit: str | None = None
    source: str | None = None
    signal_type: str | None = None
    location: str | None = None
    scope: str | None = None
    query_id: str | None = None
    period: str | None = None
    observation_periods: list[str] = Field(default_factory=list)
    latest_observed_at: datetime | None = None
    freshness_state: Literal["fresh", "stale", "unknown", "incomplete"] = "unknown"
    source_urls: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    readiness_state: str | None = None
    method_version: str | None = None
    limitations: list[str] = Field(default_factory=list)
    reason: str = ""

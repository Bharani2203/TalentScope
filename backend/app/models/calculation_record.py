"""Persisted provenance envelope for deterministic intelligence calculations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CalculationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculation_id: str
    metric: str
    window: str
    formula_id: str
    formula_parameters: dict[str, Any]
    rounding: str | None = None
    inputs: list[dict[str, Any]]
    result: dict[str, Any]
    source: str
    series_id: str
    period: str
    fetch_run_ids: list[str]
    observation_ids: list[str]
    panel_version: str | None = None
    extractor_version: str | None = None
    calculation_version: str
    data_state: str
    created_at: datetime
    evidence: dict[str, Any]

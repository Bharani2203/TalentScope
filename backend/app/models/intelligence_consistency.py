"""Typed data models for G2.6: Intelligence Quality, Consistency & Explainability Hardening."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


ConsistencyStatus = Literal["consistent", "warning", "violation"]


class ConsistencyCheckItem(BaseModel):
    """Individual rule verification check."""

    model_config = ConfigDict(extra="ignore")

    rule_name: str
    passed: bool
    description: str
    details: dict[str, Any] = Field(default_factory=dict)


class IntelligenceConsistencyResult(BaseModel):
    """Deterministic validation result verifying cross-layer consistency.

    Verifies that:
    RAW DATA -> QUALITY -> READINESS -> TREND -> CORE INTELLIGENCE -> ANSWER -> ACTION -> UI
    remain strictly aligned and logically consistent without contradictions.
    """

    model_config = ConfigDict(extra="ignore")

    valid: bool = True
    status: ConsistencyStatus = "consistent"
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_readiness: str = "insufficient_data"
    answer_readiness: str = "insufficient_data"
    action_readiness: str = "insufficient_data"
    evidence_consistent: bool = True
    forecast_locked: bool = True
    trend_consistent: bool = True
    context_aligned: bool = True
    checks: list[ConsistencyCheckItem] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)

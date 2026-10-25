"""Additive response fields shared by the existing assistant routes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistantSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["job_posting", "market_signal", "workforce", "taxonomy"]
    label: str
    detail: str


DegradedReason = Literal[
    "rate_limited",
    "provider_error",
    "unavailable",
    "usage_ledger_unavailable",
]


class AssistantResponseFields(BaseModel):
    """Stable, backward-compatible conversational metadata."""

    understood: str = ""
    secondary_intents: list[str] = Field(default_factory=list)
    enough_data: bool = False
    sources: list[AssistantSource] = Field(default_factory=list)
    features_used: list[str] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: DegradedReason | None = None

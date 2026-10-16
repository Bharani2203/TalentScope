"""Data contracts for the Core Intelligence Entity Registry."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

EntityType = Literal["skill", "technology", "occupation", "company"]
EntityResolutionStatus = Literal["resolved", "ambiguous", "not_found", "needs_review"]
EntityMatchMethod = Literal["exact", "alias", "normalized", "contextual", "candidate_ranked"]


class EntityBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CanonicalEntity(EntityBaseModel):
    """Stable canonical entity representation across all supported entity types."""
    entity_id: str = Field(min_length=1, max_length=120)
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    category: str | None = None
    source: str = Field(min_length=1, max_length=80)
    source_record_id: str | None = None
    status: Literal["active", "provisional", "deprecated"] = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityCandidate(EntityBaseModel):
    """Candidate match when an entity resolution is ambiguous or multi-option."""
    entity: CanonicalEntity
    score: float = Field(ge=0.0, le=1.0)
    match_reason: str


class EntityResolutionRequest(EntityBaseModel):
    """Input payload to resolve a raw text label to a canonical entity."""
    name: str = Field(default="", min_length=0, max_length=200)
    entity_type: EntityType | None = None
    context: dict[str, Any] | None = None


class EntityResolutionResponse(EntityBaseModel):
    """Output envelope detailing canonical match, candidates, or failure reasons."""
    name: str
    status: EntityResolutionStatus
    entity: CanonicalEntity | None = None
    candidates: list[EntityCandidate] = Field(default_factory=list)
    match_method: EntityMatchMethod | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_provenance: dict[str, Any] = Field(default_factory=dict)

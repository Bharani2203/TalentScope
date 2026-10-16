"""Action & Recommendation Intelligence data models for G2.5.

Transforms verified Core Intelligence into context-aware, evidence-backed
action recommendations across Individual, Employee, and Company portals.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

PortalType = Literal["individual", "employee", "company"]
DataStatus = Literal["available", "insufficient_data", "pending_source_data", "error"]

ActionType = Literal[
    # Individual actions
    "review_skill",
    "strengthen_skill",
    "learn_related_skill",
    "compare_career_direction",
    "review_job_readiness",
    "update_roadmap",
    "monitor_market_signal",
    # Employee actions
    "strengthen_capability",
    "explore_internal_mobility",
    "review_role_alignment",
    "join_relevant_learning",
    "seek_project_exposure",
    "monitor_skill_relevance",
    # Company actions
    "review_workforce_exposure",
    "identify_skill_gap",
    "prioritize_upskilling",
    "review_reskilling_need",
    "review_internal_mobility",
    "monitor_role_capability",
    "review_hiring_requirement",
]

PriorityLevel = Literal["high", "medium", "low"]
TargetType = Literal["skill", "role", "company", "workforce", "general"]


class ActionRecommendation(BaseModel):
    """Context-aware, evidence-backed operational recommendation."""
    action_id: str
    action_type: ActionType
    title: str
    summary: str
    why_it_matters: str
    recommended_action: str
    priority: PriorityLevel
    target_type: TargetType
    target_id: str
    portal: PortalType
    readiness_status: str
    evidence_references: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    roadmap_eligible: bool = False
    calculation_version: str | None = None


from app.models.intelligence_consistency import IntelligenceConsistencyResult


class ActionRecommendationResponse(BaseModel):
    """Unified response containing deterministic action recommendations."""
    data_status: DataStatus
    recommendations: list[ActionRecommendation] = Field(default_factory=list)
    contextual_focus: str
    limitations: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    consistency: IntelligenceConsistencyResult | None = None
    calculation_version: str = "g2.5-v1"

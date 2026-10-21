"""Shared Core Intelligence data models for G2.0.

Serves all three portals (Individual, Employee, Company) across all three domains
(Skill Intelligence, Market Intelligence, Job Intelligence).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
from app.analytics.historical_range import MAX_HISTORICAL_RANGE_DAYS

from app.models.action_recommendation import (
    ActionRecommendation,
    ActionRecommendationResponse,
    ActionType,
)
from app.models.intelligence_consistency import IntelligenceConsistencyResult
from app.models.intelligence_contract import IntelligenceMetricResult


PortalType = Literal["individual", "employee", "company"]
IntelligenceDomain = Literal["skill", "market", "job"]
DataStatus = Literal["available", "insufficient_data", "pending_source_data", "error"]
DataState = Literal[
    "ready",
    "fresh",
    "stale",
    "partial",
    "insufficient_data",
    "building",
    "unavailable",
    "error",
]
DataOrigin = Literal["real", "demo", "synthetic", "test", "mixed", "unavailable"]
HistoryType = Literal["platform_collected", "backfill", "snapshot", "mixed", "unavailable"]


# =========================================================================
# CONTEXT MODELS
# =========================================================================

class IndividualContext(BaseModel):
    """Context specific to an individual user (student, job seeker, professional)."""
    user_id: str | None = None
    target_role: str | None = None
    target_direction: str | None = None
    education_level: str | None = None
    stage: str | None = None
    location: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    skill_levels: dict[str, str] = Field(default_factory=dict)
    learning_preferences: list[str] = Field(default_factory=list)


class EmployeeContext(BaseModel):
    """Context specific to an employee connected to an employer."""
    user_id: str | None = None
    company_id: str | None = None
    company_name: str | None = None
    department: str | None = None
    team: str | None = None
    current_role: str | None = None
    time_in_role: str | None = None
    is_connected: bool = False
    internal_mobility_preference: str | None = None
    verified_company_skills: list[str] = Field(default_factory=list)


class CompanyContext(BaseModel):
    """Context specific to a company / enterprise workforce administrator."""
    company_id: str | None = None
    company_name: str | None = None
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    departments: list[str] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    workforce_headcount: int | None = None
    workforce_skill_inventory: list[str] = Field(default_factory=list)
    priority_roles: list[str] = Field(default_factory=list)
    future_skill_focus: list[str] = Field(default_factory=list)


# =========================================================================
# REQUEST MODEL
# =========================================================================

class CoreIntelligenceRequest(BaseModel):
    """Unified request model for Core Intelligence across all portals and domains."""
    portal_type: PortalType = "individual"
    intelligence_type: IntelligenceDomain = "skill"
    user_id: str | None = None
    company_id: str | None = None
    location: str | None = None
    time_range: str = "30d"  # "7d", "30d", "3m", "6m", "custom"
    custom_days: int | None = Field(default=None, ge=1, le=MAX_HISTORICAL_RANGE_DAYS)
    selected_skills: list[str] = Field(default_factory=list)
    selected_roles: list[str] = Field(default_factory=list)
    selected_companies: list[str] = Field(default_factory=list)
    target_role: str | None = None
    query: str | None = None
    requested_analysis: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    context_override: dict[str, Any] = Field(default_factory=dict)


# =========================================================================
# RESPONSE SUB-MODELS
# =========================================================================

class IntelligenceSignal(BaseModel):
    """Single discrete market, skill, or role signal with provenance."""
    signal_id: str
    signal_type: Literal["demand", "adoption", "interest", "market_momentum", "hiring", "investment"]
    source: str
    entity_name: str
    entity_type: Literal["skill", "role", "company", "market"]
    period: str
    value: float | None = None
    denominator: float | None = None
    share: float | None = None
    unit: str
    data_origin: DataOrigin = "real"
    history_type: HistoryType = "platform_collected"
    quality_state: str = "valid"
    confidence: float | None = None
    raw_archive_id: str | None = None
    fetch_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HistoricalTrendItem(BaseModel):
    """Time-series trend for a skill, role, or technology."""
    entity_id: str
    entity_name: str
    canonical_skill_id: str | None = None
    display_name: str | None = None
    entity_type: Literal["skill", "role", "company", "technology"]
    signal_type: Literal["demand", "adoption", "interest"]
    source: str
    series_id: str | None = None
    period_start: str
    period_end: str
    periods_count: int
    periods: list[str] = Field(default_factory=list)
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    trend_direction: str | None = None  # "Rising", "Stable", "Declining", "Insufficient Data"
    trend_slope: float | None = None
    velocity: float | None = None
    growth_pct: float | None = None
    whole_window_change: float | None = None
    whole_window_pct_change: float | None = None
    latest_mom_change: float | None = None
    latest_mom_pct_change: float | None = None
    value_unit: str | None = None
    velocity_unit: str | None = None
    slope_unit: str | None = None
    period_grain: str | None = None
    metric_mode: str = "raw_count"
    warnings: list[str] = Field(default_factory=list)
    calculation_version: str | None = None
    readiness_state: str = "insufficient_data"
    quality_state: str = "valid"
    data_origin: DataOrigin = "real"
    history_type: HistoryType = "platform_collected"
    is_trend_ready: bool = False
    is_forecast_ready: bool = False
    confidence: float | None = None
    current_signal_value: float | None = None
    current_signal_share: float | None = None
    current_signal_period: str | None = None
    limitations: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    explanation: str | None = None


class KeyChangeItem(BaseModel):
    """Explainable change detected between periods or within an entity."""
    change_type: str
    title: str
    description: str
    magnitude_pct: float | None = None
    direction: Literal["up", "down", "neutral"]
    affected_entity: str
    evidence_source: str
    period: str


class ExplanationItem(BaseModel):
    """Contextual natural-language explanation derived strictly from verified facts."""
    topic: str
    heading: str
    body: str
    impact_level: Literal["high", "medium", "low", "informational"]
    target_audience: PortalType
    supporting_facts: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    """Actionable recommendation tailored to individual, employee, or company."""
    action_type: Literal["learn", "verify", "upskill", "reskill", "redeploy", "hire", "monitor"]
    title: str
    description: str
    priority: Literal["critical", "high", "medium", "low"]
    target_entity: str  # skill, role, or cohort name
    rationale: str
    alignment_score: float | None = None
    estimated_timeframe: str | None = None


class NextActionItem(BaseModel):
    """Direct next operational step linking intelligence to downstream modules."""
    module: Literal["learning_roadmap", "internal_mobility", "workforce_planning", "job_search", "assessment"]
    action_title: str
    target_url_or_route: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ReadinessSummary(BaseModel):
    """Deterministic readiness evaluation across assessed series."""
    overall_readiness_state: str = "insufficient_data"
    total_series_assessed: int = 0
    ready_for_trend_count: int = 0
    ready_for_forecast_count: int = 0
    blocked_count: int = 0
    blocking_reasons: list[str] = Field(default_factory=list)


class CapabilityEnvelope(BaseModel):
    """Standard status, payload, and reason envelope for each core capability."""
    capability: str
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    reason: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class CoreIntelligenceAnswer(BaseModel):
    """Synthesized, evidence-backed contextual answer for the requested domain and portal."""
    headline: str
    summary: str
    domain: IntelligenceDomain
    portal: PortalType
    confidence: float | None = None
    confidence_band: str | None = None
    readiness_status: str  # e.g., "ready_for_trend", "insufficient_history", "blocked_coverage", etc.
    key_insights: list[str] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    contextual_focus: str  # e.g. "Personal Skill Relevance & Career Trajectory"


# =========================================================================
# RESPONSE MODEL
# =========================================================================

class CoreIntelligenceResponse(BaseModel):
    """Unified response model returned by the Core Intelligence engine."""
    intelligence_type: IntelligenceDomain
    portal_type: PortalType
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] = "insufficient_data"
    data_status: DataStatus
    data_state: DataState
    data_origin: DataOrigin
    history_type: HistoryType
    effective_location: str | None = None
    time_window: str
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    unapplied_filters: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: dict[str, CapabilityEnvelope] = Field(default_factory=dict)
    metric_results: list[IntelligenceMetricResult] = Field(default_factory=list)
    skill_health: dict[str, Any] | None = None
    skill_half_life: dict[str, Any] | None = None
    forecast: dict[str, Any] | None = None
    ai_disruption: dict[str, Any] | None = None
    market_rankings: dict[str, Any] | None = None
    workforce_impact: dict[str, Any] | None = None
    confidence_breakdown: dict[str, Any] | None = None
    freshness: dict[str, Any] = Field(default_factory=dict)
    source_coverage: dict[str, Any] = Field(default_factory=dict)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    answer: CoreIntelligenceAnswer | None = None
    current_signals: list[IntelligenceSignal] = Field(default_factory=list)
    historical_trends: list[HistoricalTrendItem] = Field(default_factory=list)
    key_changes: list[KeyChangeItem] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    explanations: list[ExplanationItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    readiness: ReadinessSummary = Field(default_factory=ReadinessSummary)
    blocking_reasons: list[str] = Field(default_factory=list)
    next_actions: list[NextActionItem] = Field(default_factory=list)
    action_recommendations: list[ActionRecommendation] = Field(default_factory=list)
    consistency: IntelligenceConsistencyResult | None = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())

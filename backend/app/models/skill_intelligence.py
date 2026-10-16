from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.analytics.observation_period import normalize_month_period
from app.analytics.skill_registry import canonical_skill_id, normalize_skill
from app.models.intelligence_contract import IntelligenceMetricResult

from app.models.onboarding import SkillLevel


class SkillModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserSkill(SkillModel):
    name: str = Field(min_length=1, max_length=160)
    level: SkillLevel | None = None
    category: str | None = None


class UserSkillsResponse(SkillModel):
    skills: list[UserSkill]
    profile_updated_at: datetime | None = None


class UserSkillsUpdateRequest(SkillModel):
    skills: list[UserSkill] = Field(max_length=100)


class FavouriteSkillsUpdateRequest(SkillModel):
    skill_ids: list[str] = Field(max_length=100)


class FavouriteSkillsResponse(SkillModel):
    skill_ids: list[str]


class FavouriteEntityIdsUpdateRequest(SkillModel):
    entity_ids: list[str] = Field(max_length=200)


class FavouriteEntityIdsResponse(SkillModel):
    entity_ids: list[str]


class SkillProfileContext(SkillModel):
    location: str | None = None
    selected_skills: list[str]


class SkillIntelligenceFilters(SkillModel):
    location: str | None = None
    range: str
    skill: str | None = None


class MarketObservation(SkillModel):
    id: str | None = None
    source: str = Field(min_length=1, max_length=80)
    skill: str = Field(min_length=1, max_length=160)
    location: str | None = None
    observed_at: datetime
    period: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    scope: Literal["city", "country", "global"] = "global"
    posting_id: str | None = None
    signal_type: Literal["demand", "adoption", "interest", "context"]
    value: float = Field(ge=0, allow_inf_nan=False)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    denominator_unit: str | None = Field(default=None, min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)
    skill_id: str | None = None
    history_type: Literal["backfill", "backfilled", "platform_collected", "snapshot", "static_dataset"] | None = None
    data_origin: Literal["real", "demo"] | None = None
    fetch_run_id: str | None = None
    series_id: str | None = None
    query_id: str | None = None
    panel_version: str | None = None
    denominator: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    quality: Any = None
    confidence: float | None = None
    observation_count: int | None = Field(default=None, ge=0)
    extractor_version: str | None = None
    annotations: list[Any] = Field(default_factory=list)
    created_at: datetime | None = None

    @field_validator("period", mode="before")
    @classmethod
    def canonicalize_period(cls, value: Any) -> Any:
        return normalize_month_period(value) if value is not None else None

    @model_validator(mode="after")
    def validate_period_matches_timestamp(self) -> "MarketObservation":
        self.skill = normalize_skill(self.skill)
        registered_skill_id = canonical_skill_id(self.skill)
        if registered_skill_id is not None:
            self.skill_id = registered_skill_id
        if self.period is None:
            return self
        observed_at = self.observed_at
        if observed_at.tzinfo is not None:
            observed_at = observed_at.astimezone(timezone.utc)
        if observed_at.strftime("%Y-%m") != self.period:
            raise ValueError("Observation period must match observed_at in UTC.")
        return self


class MarketPosting(SkillModel):
    source: str
    posting_id: str
    provider_job_id: str | None = None
    title: str | None = None
    description: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    company_name: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    category: str | None = None
    source_url: str | None = None
    posted_at: str | None = None


class SkillTrendPoint(SkillModel):
    period: str
    value: float


class TrendingSkill(SkillModel):
    skill: str
    category: str | None = None
    growth_pct: float | None = None
    trend: str | None = None
    confidence: float | None = None
    source: str | None = None


class SkillTrend(SkillModel):
    skill: str
    series: list[SkillTrendPoint]
    growth_pct: float | None = None
    trend: str | None = None
    confidence: float | None = None
    category: str | None = None
    demand_share: float | None = None
    ranking_score: float | None = None
    source: str | None = None
    unit: str | None = None
    velocity: float | None = None
    velocity_unit: str | None = None
    latest_period_change: float | None = None
    latest_period_change_pct: float | None = None
    slope: float | None = None
    slope_unit: str | None = None
    period_grain: str | None = None
    readiness_state: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    periods_used: list[str] = Field(default_factory=list)
    series_id: str | None = None
    data_origin: Literal["real", "demo"] | None = None
    series_provenance: dict[str, Any] | None = None


class SelectedSkillIntelligence(SkillModel):
    skill: str
    proficiency: str | None = None
    growth_pct: float | None = None
    trend: str = "Insufficient Data"
    confidence: float | None = None
    series: list[SkillTrendPoint] = Field(default_factory=list)
    category: str | None = None
    demand_share: float | None = None
    source: str | None = None
    unit: str | None = None
    velocity: float | None = None
    velocity_unit: str | None = None
    latest_period_change: float | None = None
    latest_period_change_pct: float | None = None
    slope: float | None = None
    slope_unit: str | None = None
    period_grain: str | None = None
    readiness_state: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    series_provenance: dict[str, Any] | None = None


class MarketCollectionRequest(SkillModel):
    location: str | None = Field(default=None, min_length=1, max_length=160)
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")


class ProviderCollectionResult(SkillModel):
    fetch_run_id: str
    provider: str
    status: str
    records_fetched: int = 0
    records_rejected: int = 0
    observations_created: int = 0
    period: str
    data_origin: Literal["real", "demo"] = "real"
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot"] = "platform_collected"
    error: str | None = None
    error_category: str | None = None


class MarketCollectionResponse(SkillModel):
    run_id: str
    status: Literal["success", "partial_failure", "error", "pending_source_data"]
    location: str | None = None
    country: str | None = None
    observations_inserted: int = 0
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: dict[str, str] = Field(default_factory=dict)
    sources_pending: list[str] = Field(default_factory=list)
    providers: list[ProviderCollectionResult] = Field(default_factory=list)
    period: str | None = None
    data_origin: Literal["real", "demo"] | None = "real"
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot"] | None = "platform_collected"


class ProviderCollectionStatus(SkillModel):
    provider: str
    latest_successful_collection: datetime | None = None
    last_failed_collection: datetime | None = None
    latest_period: str | None = None
    fetch_run_id: str | None = None
    observation_count: int = 0
    failure_status: str | None = None
    last_error_category: str | None = None
    query_id: str | None = None
    series_id: str | None = None
    provider_capability: str | None = None
    history_type: str | None = None
    data_origin: str | None = None
    quality_status: str | None = None
    readiness_status: str | None = None


class MarketCollectionStatusResponse(SkillModel):
    overall_status: Literal["success", "partial_failure", "failed", "pending", "idle"]
    latest_collection: datetime | None = None
    providers: list[ProviderCollectionStatus] = Field(default_factory=list)


class SkillIntelligenceResponse(SkillModel):
    profile_context: SkillProfileContext
    filters: SkillIntelligenceFilters
    data_status: Literal["available", "insufficient_data", "pending_source_data", "error"]
    # Standardized contract state vocabulary: fresh, stale, insufficient_data, building, unavailable, error
    data_state: Literal[
        "ready", "partial", "fresh", "stale", "insufficient_data", "building", "unavailable", "error",
        "incomparable", "configuration_changed", "incomplete", "low_coverage"
    ] | None = None
    data_origin: Literal["real", "demo", "mixed", "unavailable"] | None = None
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot", "mixed", "unavailable"] | None = None
    quality_summary: dict[str, Any] | None = None
    analytical_readiness: dict[str, Any] | None = None
    metric_results: list[IntelligenceMetricResult] = Field(default_factory=list)
    history_complete: bool = True
    history_completeness_reason: str | None = None
    top_skills: list[TrendingSkill]
    skill_trends: list[SkillTrend]
    current_demand: list[dict[str, Any]] = Field(default_factory=list)
    current_interest: list[dict[str, Any]] = Field(default_factory=list)
    current_adoption: list[dict[str, Any]] = Field(default_factory=list)
    production_trends: list[dict[str, Any]] = Field(default_factory=list)
    personal_top_skills: list[SkillTrend] = Field(default_factory=list)
    market_top_skills: list[SkillTrend] = Field(default_factory=list)
    selected_skill: SelectedSkillIntelligence | None = None
    sources_used: list[str] = Field(default_factory=list)
    sources_pending: list[str] = Field(default_factory=list)
    observations_count: int = 0
    historical_periods_count: int = 0
    calculation_version: str = "demand-theil-sen-v3-comparable-series"
    calculation: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    error_message: str | None = None

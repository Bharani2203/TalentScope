"""Shared typed aggregation and trend calculation for intelligence requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Sequence

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.series_validation import validate_series_observations
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.models.market_signal import AggregatedMarketSignal, SkillTrendVelocityResult
from app.models.signal_quality import SeriesQualityReport
from app.models.skill_intelligence import MarketObservation


@dataclass(frozen=True)
class SharedIntelligenceAnalysis:
    observations: list[MarketObservation]
    aggregated_signals: list[AggregatedMarketSignal]
    trend_results: list[SkillTrendVelocityResult]
    quality_reports: list[SeriesQualityReport] = field(default_factory=list)
    history_complete: bool = True
    completeness_reason: str | None = None


def analyze_market_observations(
    observations: Sequence[MarketObservation],
    *,
    quality_reports: list[Any] | None = None,
    readiness_reports: list[Any] | None = None,
    include_trends: bool = True,
    history_complete: bool | None = None,
    as_of: date | datetime | None = None,
) -> SharedIntelligenceAnalysis:
    """Calculate comparable series and trends once while preserving validated readiness."""
    if history_complete is None:
        history_complete = not bool(getattr(observations, "truncated", False))
    observation_list = list(observations)
    if quality_reports is None:
        quality_reports = validate_series_observations(observation_list)
    if readiness_reports is None:
        readiness_reports = assess_analytical_readiness(
            observation_list,
            quality_reports=quality_reports,
            as_of=as_of,
        )
    aggregated = aggregate_market_signals(observation_list)
    trends = (
        calculate_trend_and_velocity(
            aggregated,
            quality_reports=quality_reports,
            readiness_reports=readiness_reports,
            as_of=as_of,
        )
        if aggregated and include_trends and history_complete else []
    )
    return SharedIntelligenceAnalysis(
        observation_list,
        aggregated if history_complete else [],
        trends,
        quality_reports,
        history_complete,
        None if history_complete else "Observation retrieval reached its bounded row limit.",
    )

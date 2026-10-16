"""Shared typed aggregation and trend calculation for intelligence requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.models.market_signal import AggregatedMarketSignal, SkillTrendVelocityResult
from app.models.skill_intelligence import MarketObservation


@dataclass(frozen=True)
class SharedIntelligenceAnalysis:
    observations: list[MarketObservation]
    aggregated_signals: list[AggregatedMarketSignal]
    trend_results: list[SkillTrendVelocityResult]
    history_complete: bool = True
    completeness_reason: str | None = None


def analyze_market_observations(
    observations: Sequence[MarketObservation],
    *,
    quality_reports: list[Any] | None = None,
    readiness_reports: list[Any] | None = None,
    include_trends: bool = True,
    history_complete: bool | None = None,
) -> SharedIntelligenceAnalysis:
    """Calculate comparable series and trends once while preserving validated readiness."""
    if history_complete is None:
        history_complete = not bool(getattr(observations, "truncated", False))
    observation_list = list(observations)
    aggregated = aggregate_market_signals(observation_list)
    trends = (
        calculate_trend_and_velocity(
            aggregated,
            quality_reports=quality_reports,
            readiness_reports=readiness_reports,
        )
        if aggregated and include_trends and history_complete else []
    )
    return SharedIntelligenceAnalysis(
        observation_list,
        aggregated if history_complete else [],
        trends,
        history_complete,
        None if history_complete else "Observation retrieval reached its bounded row limit.",
    )

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.analytics.observation_period import (
    is_completed_month,
    normalize_month_period,
)
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.models.market_signal import AggregatedMarketSignal
from app.models.skill_intelligence import MarketObservation


def observation(period: str, value: float, denominator: float | None):
    year, month = map(int, normalize_month_period(period).split("-"))
    return MarketObservation(
        source="jsearch", skill="Python", skill_id="python", signal_type="demand",
        observed_at=datetime(year, month, 15, tzinfo=timezone.utc), period=period,
        scope="global", location="Global", value=value, posting_id=f"job:{period}:{value}",
        denominator=denominator, data_origin="real", history_type="platform_collected",
        series_id="jsearch:demand:python", panel_version="v1", unit="job_postings",
    )


def signal(period: str, value: float) -> AggregatedMarketSignal:
    return AggregatedMarketSignal(
        canonical_skill_id="python", canonical_name="Python", source="jsearch",
        signal_type="demand", period=period, metric="raw_count", raw_value=value,
        data_origin="real", history_type="platform_collected", data_state="ready",
        series_id="jsearch:demand:python", panel_version="v1", unit="job_postings",
    )


def test_legacy_month_year_period_normalizes_and_invalid_month_is_rejected():
    assert normalize_month_period("10-2026") == "2026-10"
    assert MarketObservation.model_validate({**observation("10-2026", 2, 10).model_dump(), "period": "10-2026"}).period == "2026-10"
    with pytest.raises((ValueError, ValidationError)):
        normalize_month_period("13-2026")


def test_current_month_is_not_a_completed_month():
    assert is_completed_month("2026-09", as_of=date(2026, 10, 11))
    assert not is_completed_month("10-2026", as_of=date(2026, 10, 11))


def test_zero_count_and_zero_share_are_valid_but_missing_denominator_is_not_share():
    no_denominator = aggregate_market_signals([observation("2026-08", 0, None)])[0]
    zero_share = aggregate_market_signals([observation("2026-08", 0, 20)])[0]
    assert no_denominator.metric == "raw_count"
    assert no_denominator.raw_value == 0
    assert no_denominator.normalized_value is None
    assert zero_share.metric == "normalized_share"
    assert zero_share.normalized_value == 0
    assert zero_share.denominator == 20


def test_trend_excludes_open_current_period_and_requires_four_completed_periods():
    rows = [signal(f"2026-{month:02d}", value) for month, value in ((6, 1), (7, 2), (8, 3), (9, 4), (10, 100))]
    result = calculate_trend_and_velocity(rows, as_of=date(2026, 10, 11))[0]
    assert result.trend == "Increasing"
    assert result.latest_period == "2026-09"
    assert result.latest_value == 4
    assert result.latest_mom_change == 1


def test_single_completed_period_reports_insufficient_trend():
    result = calculate_trend_and_velocity([signal("2026-09", 3)], as_of=date(2026, 10, 11))[0]
    assert result.trend == "Insufficient Data"
    assert result.latest_period == "2026-09"
    assert any("only 1 available" in reason for reason in result.blocking_reasons)


def test_percentage_change_is_omitted_when_previous_denominator_value_is_zero():
    rows = [
        AggregatedMarketSignal(
            canonical_skill_id="python", canonical_name="Python", source="jsearch",
            signal_type="demand", period=period, metric="normalized_share", raw_value=value,
            normalized_value=value, denominator=100, data_origin="real",
            history_type="platform_collected", data_state="ready", series_id="same", panel_version="v1",
            unit="job_postings",
        )
        for period, value in (("2026-07", 1), ("2026-08", 2), ("2026-09", 0), ("2026-10", 3))
    ]
    result = calculate_trend_and_velocity(rows, as_of=date(2026, 11, 1))[0]
    assert result.latest_mom_change == 3
    assert result.growth_pct is None

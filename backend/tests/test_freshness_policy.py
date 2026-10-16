from datetime import datetime, timedelta, timezone

from app.analytics.freshness import assess_freshness
from app.analytics.trend import compatible_demand_observations
from app.models.skill_intelligence import MarketObservation

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


def observation(*, history_type="platform_collected", signal_type="demand", created_at=NOW):
    return MarketObservation(
        source="jsearch", skill="Python", signal_type=signal_type,
        history_type=history_type, observed_at=NOW - timedelta(days=120),
        created_at=created_at, period="2026-10", value=0.4,
    )


def test_fresh_platform_observation_is_ready():
    result = assess_freshness([observation()], now=NOW)
    assert result.state == "ready"
    assert (result.fresh_count, result.stale_count) == (1, 0)


def test_observation_beyond_threshold_is_stale():
    result = assess_freshness([observation(created_at=NOW - timedelta(hours=49))], now=NOW)
    assert result.state == "stale"
    assert result.stale_count == 1


def test_historical_backfill_does_not_age_into_stale():
    result = assess_freshness([
        observation(history_type="backfill", created_at=NOW - timedelta(days=500))
    ], now=NOW)
    assert result.state == "insufficient_data"
    assert result.stale_count == 0
    assert result.excluded_count == 1


def test_missing_collection_timestamp_is_building_not_stale():
    result = assess_freshness([observation(created_at=None)], now=NOW)
    assert result.state == "building"
    assert result.unknown_count == 1


def test_missing_observations_are_insufficient_data():
    assert assess_freshness([], now=NOW).state == "insufficient_data"


def test_mixed_freshness_is_partial():
    result = assess_freshness([
        observation(),
        observation(created_at=NOW - timedelta(hours=72)),
    ], now=NOW)
    assert result.state == "partial"
    assert result.fresh_count == result.stale_count == 1


def test_fresh_and_unknown_timestamps_are_partial():
    result = assess_freshness([observation(), observation(created_at=None)], now=NOW)
    assert result.state == "partial"
    assert result.unknown_count == 1


def test_snapshot_freshness_uses_collection_time_not_published_observed_at():
    result = assess_freshness([
        observation(history_type="snapshot", signal_type="adoption")
    ], now=NOW)
    assert result.state == "ready"


def test_provenance_filter_keeps_signal_and_history_families_separate():
    demand = observation()
    adoption = observation(history_type="snapshot", signal_type="adoption")
    interest = observation(history_type="backfill", signal_type="interest")
    assert compatible_demand_observations([demand, adoption, interest]) == [demand]

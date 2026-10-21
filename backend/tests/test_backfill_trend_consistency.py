"""Regression tests for Task 1: Backfill consistency in compatible_demand_observations.

Verifies that the eligibility filter in trend.py aligns with the forecasting path in
forecasting.py: both accept history_type in {"platform_collected", "backfill", "backfilled"}.

Evidence for the fix:
- job_observations.py line 59 hard-codes history_type="platform_collected" for live collection.
- Stack Exchange backfill uses history_type="backfill" but signal_type="interest" (not "demand").
- forecasting.py L268 already accepted {"platform_collected", "backfill", "backfilled"}.
- The original trend filter only accepted "platform_collected", creating a latent inconsistency:
  any future demand backfill (e.g. historical job-board API) would silently pass forecasting
  but be dropped from trends. The fix aligns the two paths proactively.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.analytics.trend import _DEMAND_HISTORY_TYPES, compatible_demand_observations
from app.models.skill_intelligence import MarketObservation


def _make_obs(
    *,
    signal_type: str = "demand",
    history_type: str = "platform_collected",
    data_origin: str = "real",
    skill: str = "Python",
    period: str = "2026-01",
) -> MarketObservation:
    year, month = (int(p) for p in period.split("-"))
    return MarketObservation(
        id=f"test-{signal_type}-{history_type}-{data_origin}-{period}",
        source="jsearch",
        skill=skill,
        signal_type=signal_type,
        history_type=history_type,
        data_origin=data_origin,
        observed_at=datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc),
        period=period,
        value=1.0,
        unit="job_postings",
    )


# ============================================================================
# Accepted cases
# ============================================================================

class TestAcceptedCases:
    def test_platform_collected_demand_real_is_accepted(self):
        """Standard live-collection demand observation must always pass."""
        obs = _make_obs(signal_type="demand", history_type="platform_collected", data_origin="real")
        result = compatible_demand_observations([obs])
        assert len(result) == 1
        assert result[0] is obs

    def test_backfill_demand_real_is_accepted(self):
        """Demand observation with history_type='backfill' and data_origin='real' must pass.

        This matches the forecasting path gate in forecasting.py (line 268).
        Future providers (e.g. job-board historical APIs) may produce such observations.
        """
        obs = _make_obs(signal_type="demand", history_type="backfill", data_origin="real")
        result = compatible_demand_observations([obs])
        assert len(result) == 1
        assert result[0] is obs

    def test_backfilled_demand_real_is_accepted(self):
        """Demand observation with history_type='backfilled' (migration alias) must pass."""
        obs = _make_obs(signal_type="demand", history_type="backfilled", data_origin="real")
        result = compatible_demand_observations([obs])
        assert len(result) == 1
        assert result[0] is obs

    def test_demand_history_types_constant_matches_forecasting_path(self):
        """The _DEMAND_HISTORY_TYPES constant must match the set used in forecasting.py."""
        assert _DEMAND_HISTORY_TYPES == frozenset({"platform_collected", "backfill", "backfilled"})


# ============================================================================
# Rejected cases
# ============================================================================

class TestRejectedCases:
    def test_interest_backfill_is_rejected(self):
        """Stack Exchange backfill (signal_type='interest') must never pass.

        Even though history_type='backfill' is now accepted, signal_type must be 'demand'.
        """
        obs = _make_obs(signal_type="interest", history_type="backfill", data_origin="real")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_adoption_platform_collected_is_rejected(self):
        """GitHub adoption (signal_type='adoption') must never pass, regardless of history_type."""
        obs = _make_obs(signal_type="adoption", history_type="platform_collected", data_origin="real")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_synthetic_demand_is_rejected(self):
        """data_origin='synthetic' must be rejected regardless of signal_type or history_type."""
        obs = _make_obs(signal_type="demand", history_type="platform_collected", data_origin="synthetic")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_test_origin_demand_is_rejected(self):
        """data_origin='test' (demo fixture) must be rejected."""
        obs = _make_obs(signal_type="demand", history_type="platform_collected", data_origin="test")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_demo_origin_demand_is_rejected(self):
        """data_origin='demo' must be rejected — demo data must never appear as real trends."""
        obs = _make_obs(signal_type="demand", history_type="platform_collected", data_origin="demo")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_snapshot_history_type_is_rejected(self):
        """history_type='snapshot' (used for GitHub adoption) must be rejected for demand trends.

        'snapshot' is a valid history_type Literal in the model but is not in _DEMAND_HISTORY_TYPES.
        """
        obs = _make_obs(signal_type="demand", history_type="snapshot", data_origin="real")
        result = compatible_demand_observations([obs])
        assert result == []

    def test_static_dataset_history_type_is_rejected(self):
        """history_type='static_dataset' must be rejected — only the approved set is accepted."""
        obs = _make_obs(signal_type="demand", history_type="static_dataset", data_origin="real")
        result = compatible_demand_observations([obs])
        assert result == []


# ============================================================================
# Mixed batch behaviour
# ============================================================================

class TestMixedBatchBehaviour:
    def test_mixed_history_types_in_same_call_are_filtered_deterministically(self):
        """A batch with multiple history types: only eligible ones pass."""
        obs_platform = _make_obs(history_type="platform_collected", period="2026-01")
        obs_backfill = _make_obs(history_type="backfill", period="2026-02")
        obs_backfilled = _make_obs(history_type="backfilled", period="2026-03")
        obs_interest = _make_obs(signal_type="interest", history_type="backfill", period="2026-04")
        obs_synthetic = _make_obs(history_type="platform_collected", data_origin="synthetic", period="2026-05")
        obs_snapshot = _make_obs(history_type="snapshot", period="2026-06")

        all_obs = [obs_platform, obs_backfill, obs_backfilled, obs_interest, obs_synthetic, obs_snapshot]
        result = compatible_demand_observations(all_obs)

        assert len(result) == 3
        periods = {o.period for o in result}
        assert periods == {"2026-01", "2026-02", "2026-03"}

    def test_empty_input_returns_empty(self):
        assert compatible_demand_observations([]) == []

    def test_all_rejected_returns_empty(self):
        obs = [
            _make_obs(signal_type="interest"),
            _make_obs(data_origin="synthetic"),
            _make_obs(history_type="snapshot"),
        ]
        result = compatible_demand_observations(obs)
        assert result == []

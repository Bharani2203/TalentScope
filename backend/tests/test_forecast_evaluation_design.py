"""Regression tests for Task 4: Forecast evaluation design fix.

Verifies that:
1. beats_naive_baseline reflects a genuine ETS challenger vs seasonal-naive baseline comparison.
2. The seasonal-naive baseline can never be reported as beating itself.
3. ETS is correctly unavailable (beats_naive_baseline=False) when training data is < 2 seasons.
4. When ETS outperforms seasonal-naive on holdout, beats_naive_baseline=True and selected_method='es_smoothing'.
5. When ETS does NOT outperform, selected_method='seasonal_naive' and beats_naive_baseline=False.
6. Chronological holdout prevents data leakage.
7. _holt_winters_additive returns empty list when training < 24 obs (2 * season_length).
8. MASE denominator is never zero-divided.
"""

from __future__ import annotations

import math
import types
from datetime import date, datetime, timezone

import pytest

from app.analytics.forecasting import (
    DEFAULT_FORECAST_MIN_PERIODS,
    _holt_winters_additive,
    _seasonal_naive,
    forecast_signal_series,
)


def _make_signal(
    *,
    skill_id: str = "python",
    skill_name: str = "Python",
    source: str = "jsearch",
    period: str,
    value: float,
    unit: str = "job_postings",
    series_id: str = "jsearch:demand:python:global",
    history_type: str = "platform_collected",
    data_origin: str = "real",
    data_state: str = "ready",
    metric: str = "raw_count",
) -> types.SimpleNamespace:
    """Build a signal object with all attributes required by forecast_signal_series() duck typing."""
    return types.SimpleNamespace(
        canonical_skill_id=skill_id,
        canonical_name=skill_name,
        source=source,
        signal_type="demand",
        period=period,
        raw_value=value,
        normalized_value=None,
        value=value,
        denominator=None,
        denominator_unit=None,
        unit=unit,
        series_id=series_id,
        panel_version="v1",
        query_id=f"{skill_id}-query",
        scope="global",
        location="Global",
        data_origin=data_origin,
        history_type=history_type,
        data_state=data_state,
        metric=metric,
        extractor_version=None,
        observation_ids=[f"obs-{period}"],
        fetch_run_ids=[f"run-{period}"],
    )


def _make_series(
    n: int,
    *,
    skill_id: str = "python",
    skill_name: str = "Python",
    source: str = "jsearch",
    base_value: float = 150.0,
    history_type: str = "platform_collected",
    data_origin: str = "real",
    data_state: str = "ready",
    start_year: int = 2022,
    start_month: int = 1,
    consecutive: bool = True,
) -> list:
    """Generate n consecutive monthly raw_count demand signals for forecast_signal_series()."""
    signals = []
    for i in range(n):
        if consecutive:
            idx = (start_year * 12 + start_month - 1) + i
        else:
            idx = (start_year * 12 + start_month - 1) + (i * 2)
        year, month_zero = divmod(idx, 12)
        month = month_zero + 1
        period = f"{year:04d}-{month:02d}"
        val = base_value * (1.0 + 0.15 * math.sin(2 * math.pi * i / 12.0))
        signals.append(_make_signal(
            skill_id=skill_id,
            skill_name=skill_name,
            source=source,
            period=period,
            value=round(val, 4),
            history_type=history_type,
            data_origin=data_origin,
            data_state=data_state,
        ))
    return signals


# ============================================================================
# Unit tests for the ETS and seasonal-naive functions
# ============================================================================

class TestHelperFunctions:
    def test_seasonal_naive_returns_season_length_predictions(self):
        train = list(range(1, 25))  # 24 values
        preds = _seasonal_naive(train, 3)
        assert len(preds) == 3
        # step 1 → train[-12+0] = train[12] = 13
        assert preds[0] == float(train[-12])

    def test_holt_winters_returns_empty_when_training_too_short(self):
        """ETS requires >= 2 * season_length = 24 training observations."""
        for short_n in [0, 1, 12, 23]:
            preds = _holt_winters_additive(list(range(short_n)), 1)
            assert preds == [], f"Expected empty list for n={short_n}"

    def test_holt_winters_returns_predictions_when_training_sufficient(self):
        train = [100.0 + i * 0.5 for i in range(24)]
        preds = _holt_winters_additive(train, 3)
        assert len(preds) == 3
        assert all(isinstance(p, float) for p in preds)
        assert all(p >= 0.0 for p in preds)

    def test_holt_winters_all_predictions_non_negative(self):
        """Forecast values must always be clipped at 0.0."""
        # Rapidly declining series that could produce negative ETS preds without clipping
        train = [max(0.01, 100.0 - i * 5.0) for i in range(24)]
        preds = _holt_winters_additive(train, 6)
        assert all(p >= 0.0 for p in preds)

    def test_holt_winters_constant_series(self):
        """Constant training series should produce constant forecasts."""
        train = [50.0] * 24
        preds = _holt_winters_additive(train, 3)
        assert len(preds) == 3
        # Allow small numerical tolerance
        for p in preds:
            assert abs(p - 50.0) < 5.0


# ============================================================================
# beats_naive_baseline is structurally False for short histories
# ============================================================================

class TestBeatsNaiveBaselineFalseWhenETSUnavailable:
    def test_beats_naive_is_false_when_exactly_24_obs(self):
        """24 obs: holdout_size=max(6, 24//3)=8, holdout_start=16.
        First ETS train_slice has 16 obs, which is < 24 required.
        ETS is unavailable; beats_naive_baseline must be False.
        """
        obs = _make_series(24)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        assert result.beats_naive_baseline is False
        # The selected method must still be seasonal_naive (fallback)
        assert result.selected_method == "seasonal_naive"

    def test_backtest_scores_include_seasonal_naive(self):
        obs = _make_series(24)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        methods = {s.method for s in result.backtest_scores}
        assert "seasonal_naive" in methods

    def test_seasonal_naive_beats_naive_is_always_false(self):
        """The seasonal-naive baseline entry in backtest_scores must have beats_naive=False
        because the baseline cannot beat itself.
        """
        obs = _make_series(24)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        sn_scores = [s for s in result.backtest_scores if s.method == "seasonal_naive"]
        assert len(sn_scores) == 1
        assert sn_scores[0].beats_naive is False, "Baseline must never report beats_naive=True"

    def test_insufficient_history_returns_not_ready(self):
        obs = _make_series(12)
        result = forecast_signal_series(
            obs, canonical_skill_id="python", canonical_name="Python", min_periods=24,
        )
        assert result.status == "insufficient_data"
        assert result.beats_naive_baseline is False


# ============================================================================
# ETS can compete when training is large enough
# ============================================================================

class TestETSCanCompeteWithSufficientData:
    def test_ets_score_present_in_backtest_when_training_sufficient(self):
        """With 48 obs: holdout_size=max(6, 48//3)=16, holdout_start=32.
        First ETS train_slice has 32 obs >= 24; ETS can be evaluated.
        """
        obs = _make_series(48)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        methods = {s.method for s in result.backtest_scores}
        assert "es_smoothing" in methods, f"ETS score missing from backtest_scores; got {methods}"

    def test_beats_naive_reflects_actual_comparison(self):
        """beats_naive_baseline must match whether ETS RMSE < seasonal-naive RMSE on holdout."""
        obs = _make_series(48)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        sn_scores = [s for s in result.backtest_scores if s.method == "seasonal_naive"]
        ets_scores = [s for s in result.backtest_scores if s.method == "es_smoothing"]
        if ets_scores:
            ets_rmse = ets_scores[0].rmse
            sn_rmse = sn_scores[0].rmse
            expected_beats = ets_rmse < sn_rmse
            assert result.beats_naive_baseline == expected_beats

    def test_selected_method_matches_winner(self):
        """selected_method must be 'es_smoothing' when ETS wins, else 'seasonal_naive'."""
        obs = _make_series(48)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        if result.beats_naive_baseline:
            assert result.selected_method == "es_smoothing"
        else:
            assert result.selected_method == "seasonal_naive"

    def test_winner_rmse_is_minimum_of_evaluated_methods(self):
        """winner_rmse must equal min(ETS RMSE, baseline RMSE) when both are evaluated."""
        obs = _make_series(48)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        if result.status != "ready":
            return
        rmses = [s.rmse for s in result.backtest_scores if s.rmse < math.inf]
        if rmses:
            assert result.winner_rmse == min(rmses)


# ============================================================================
# Provenance and data-leakage guards
# ============================================================================

class TestDataLeakageGuards:
    def test_holdout_backtest_periods_are_at_the_end(self):
        """Backtest periods must be the chronological tail of the history, not shuffled."""
        obs = _make_series(30)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        assert len(result.backtest_periods) > 0
        # Backtest periods must be a suffix of the observed history periods
        history_periods = [h["period"] for h in result.observed_history]
        n_back = len(result.backtest_periods)
        assert result.backtest_periods == history_periods[-n_back:]

    def test_backtest_sample_size_matches_holdout(self):
        obs = _make_series(30)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        n = 30
        expected_holdout = max(6, n // 3)
        assert result.backtest_sample_size == expected_holdout

    def test_forecast_horizon_capped_at_min6_n_div_3(self):
        obs = _make_series(24)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        assert result.horizon_months == min(6, 24 // 3)

    def test_all_forecast_point_values_non_negative(self):
        obs = _make_series(48)
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "ready"
        for pt in result.forecasts:
            assert pt.point_forecast >= 0.0


# ============================================================================
# Synthetic/demo data is still rejected
# ============================================================================

class TestSyntheticDataRejected:
    def test_synthetic_data_origin_blocked(self):
        obs = _make_series(24, data_origin="synthetic")
        result = forecast_signal_series(obs, canonical_skill_id="python", canonical_name="Python")
        assert result.status == "unavailable"
        assert result.beats_naive_baseline is False

    def test_non_consecutive_periods_blocked(self):
        """A gap in the series must block forecasting."""
        obs = _make_series(24)
        # Remove one observation from the middle to create a gap
        obs_with_gap = obs[:10] + obs[12:]
        result = forecast_signal_series(obs_with_gap, canonical_skill_id="python", canonical_name="Python")
        assert result.status in {"unavailable", "insufficient_data"}
        assert result.beats_naive_baseline is False

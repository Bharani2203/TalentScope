"""Deterministic Forecasting and Market Rankings for TalentScope.ai.

Forecasting rules:
1. Requires at least 24 valid consecutive monthly observations.
2. Uses a seasonal-naive method as the baseline (repeats corresponding month from the prior year).
3. Evaluates a Holt-Winters additive exponential smoothing (ETS) challenger on the same holdout.
4. Reports out-of-sample RMSE and MAE from a chronological one-step holdout for both methods.
5. Selects the method with lower holdout RMSE; beats_naive_baseline=True only when the ETS
   challenger genuinely outperforms the seasonal-naive baseline on the holdout.
6. Emits empirical error bounds only with at least 20 holdout predictions.
7. Forecasts only validated, complete, source-specific job-demand observations.
8. Horizon is capped at `min(6, history_length // 3)` months.
9. Preserves exact series, unit, history, observation, and collection-run provenance.
10. No external ML libraries required; ETS is implemented in pure Python.
11. If insufficient history for ETS initialisation, seasonal-naive is used and
    beats_naive_baseline is always False (baseline cannot beat itself).

Market Ranking rules:
1. Ranks by one named metric, time window, period, provider, and tracked panel.
2. Includes eligible entity count, panel coverage, metric definition, and limitations.
3. Shows `< 5` rows honestly when coverage is insufficient without padding or merging providers.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.trend import _consecutive_periods, _month_index, theil_sen_slope
from app.analytics.skill_registry import BY_ID

DEFAULT_FORECAST_MIN_PERIODS = 24
ForecastMethodName = Literal["naive", "seasonal_naive", "es_smoothing"]


def _format_period_from_index(month_idx: int) -> str:
    year = (month_idx - 1) // 12
    month = (month_idx - 1) % 12 + 1
    return f"{year:04d}-{month:02d}"


class ForecastPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    horizon_step: int
    point_forecast: float
    lower_80: float | None = None
    upper_80: float | None = None
    lower_95: float | None = None
    upper_95: float | None = None


class BacktestMethodScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: ForecastMethodName
    rmse: float
    mae: float
    beats_naive: bool


class DeterministicForecastResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_series: str
    canonical_skill_id: str | None
    canonical_name: str
    provider: str
    signal_family: str
    metric: str
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    selected_method: ForecastMethodName | None = None
    baseline_name: str | None = None
    error_metric: str = "RMSE"
    winner_rmse: float | None = None
    naive_rmse: float | None = None
    beats_naive_baseline: bool = False
    horizon_months: int = 0
    history_length: int = 0
    required_min_periods: int = DEFAULT_FORECAST_MIN_PERIODS
    unit: str | None = None
    period_grain: str = "month"
    readiness: str = "insufficient_history"
    backtest_sample_size: int = 0
    backtest_periods: list[str] = Field(default_factory=list)
    observed_history: list[dict[str, Any]] = Field(default_factory=list)
    first_history_period: str | None = None
    latest_history_period: str | None = None
    backtest_scores: list[BacktestMethodScore] = Field(default_factory=list)
    forecasts: list[ForecastPoint] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    explanation: str = ""
    limitations: list[str] = Field(default_factory=list)
    calculation_version: str = "seasonal-naive-ets-chronological-holdout-v2"


def _seasonal_naive(train: Sequence[float], steps: int, season_length: int = 12) -> list[float]:
    return [float(train[-season_length + ((step - 1) % season_length)]) for step in range(1, steps + 1)]


def _holt_winters_additive(
    train: Sequence[float],
    steps: int,
    season_length: int = 12,
    alpha: float = 0.3,
    beta: float = 0.1,
    gamma: float = 0.2,
) -> list[float]:
    """Holt-Winters additive exponential smoothing (no external dependencies).

    Requires at least 2 full seasons (``2 * season_length``) in training data.
    Returns an empty list if training data is insufficient, so callers must
    handle that by falling back to the seasonal-naive baseline.

    Parameters
    ----------
    train:
        Ordered historical values (oldest first).
    steps:
        Number of forecast steps ahead.
    season_length:
        Seasonal period; 12 for monthly data.
    alpha:
        Level smoothing weight (0 < alpha < 1).
    beta:
        Trend smoothing weight (0 < beta < 1).
    gamma:
        Seasonal smoothing weight (0 < gamma < 1).
    """
    n = len(train)
    if n < 2 * season_length:
        return []

    # Initialise level, trend, and seasonal components from the first two seasons.
    season_means = [
        sum(train[s * season_length: (s + 1) * season_length]) / season_length
        for s in range(n // season_length)
    ]
    level = season_means[0]
    trend = (season_means[1] - season_means[0]) / season_length

    # Initial seasonal indices from the first complete season.
    first_mean = level if level != 0 else 1e-9
    seasonals: list[float] = [train[i] - level for i in range(season_length)]

    # Smooth over all historical observations.
    smoothed_level = level
    smoothed_trend = trend
    smoothed_seasonals = list(seasonals)
    for t in range(n):
        s_idx = t % season_length
        prev_level = smoothed_level
        prev_trend = smoothed_trend
        observation = train[t]
        seasonal = smoothed_seasonals[s_idx]
        new_level = alpha * (observation - seasonal) + (1 - alpha) * (prev_level + prev_trend)
        new_trend = beta * (new_level - prev_level) + (1 - beta) * prev_trend
        new_seasonal = gamma * (observation - new_level) + (1 - gamma) * seasonal
        smoothed_level = new_level
        smoothed_trend = new_trend
        smoothed_seasonals[s_idx] = new_seasonal

    # Produce forecasts.
    forecasts: list[float] = []
    for h in range(1, steps + 1):
        s_idx = (n + h - 1) % season_length
        forecast = smoothed_level + smoothed_trend * h + smoothed_seasonals[s_idx]
        forecasts.append(max(0.0, forecast))
    return forecasts


def _forecast_month_is_complete(period: str, as_of: date) -> bool:
    try:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
            return False
        year, month = (int(part) for part in period.split("-"))
        return (year, month) < (as_of.year, as_of.month)
    except (TypeError, ValueError):
        return False


def _forecast_month_position(period: str) -> tuple[int, int] | None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        return None
    year_text, month_text = period.split("-")
    return int(year_text), int(month_text)


def _forecast_value(signal: Any) -> float:
    metric = getattr(signal, "metric", None)
    if metric == "normalized_share":
        value = getattr(signal, "normalized_value", None)
        denominator = getattr(signal, "denominator", None)
        denominator_unit = getattr(signal, "denominator_unit", None)
        if value is None or denominator is None or float(denominator) <= 0 or not denominator_unit:
            raise ValueError("normalized_share requires a value, positive denominator, and denominator unit")
        return float(value)
    if metric != "raw_count":
        raise ValueError(f"Unsupported demand metric for forecasting: {metric}")
    return float(getattr(signal, "raw_value"))


def forecast_signal_series(
    signals: Sequence[Any],
    *,
    canonical_skill_id: str | None = None,
    canonical_name: str = "",
    signal_family: str = "demand",
    provider: str | None = None,
    min_periods: int = DEFAULT_FORECAST_MIN_PERIODS,
    quality_reports: Sequence[Any] | None = None,
    as_of: date | None = None,
    history_complete: bool = True,
) -> DeterministicForecastResult:
    """Forecast one complete monthly job-demand series using seasonal-naive carry-forward."""
    min_periods = max(min_periods, 24)
    as_of = as_of or datetime.now(timezone.utc).date()
    if not history_complete:
        return DeterministicForecastResult(
            target_series="incomplete_history",
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            provider=provider or "unavailable",
            signal_family=signal_family,
            metric="unavailable",
            status="unavailable",
            readiness="incomplete_history",
            required_min_periods=min_periods,
            reason="Observation retrieval reached its bounded row limit; a complete forecast history is unavailable.",
            explanation="Forecasting is withheld because the retrieved observation history may be truncated.",
            limitations=["Truncated history is never treated as a complete forecast series."],
        )
    matching = [
        s for s in signals
        if getattr(s, "signal_type", None) == signal_family
        and (not provider or getattr(s, "source", "").casefold().strip() == provider.casefold().strip())
        and (
            (not canonical_skill_id and not canonical_name)
            or (canonical_skill_id and getattr(s, "canonical_skill_id", None) == canonical_skill_id)
            or (
                not canonical_skill_id
                and canonical_name
                and getattr(s, "canonical_name", "").casefold() == canonical_name.casefold()
            )
        )
    ]

    if signal_family != "demand":
        matching = []
    if not matching:
        target_id = f"{provider or 'unknown'}:{signal_family}:{canonical_skill_id or canonical_name or 'unknown'}:unavailable"
        return DeterministicForecastResult(
            target_series=target_id,
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            provider=provider or "unavailable",
            signal_family=signal_family,
            metric="unavailable",
            status="unavailable",
            readiness="unavailable",
            required_min_periods=min_periods,
            reason=f"No '{signal_family}' series found for {canonical_name or canonical_skill_id or 'requested entity'}.",
            explanation="Forecasting is unavailable because no matching historical series exists.",
            limitations=["Forecasting is limited to source-specific job-demand series."],
        )

    dimensions = lambda s: (
        getattr(s, "source", "").casefold().strip(),
        getattr(s, "signal_type", None),
        getattr(s, "canonical_skill_id", None),
        getattr(s, "metric", None),
        getattr(s, "unit", None),
        getattr(s, "denominator_unit", None),
        getattr(s, "series_id", None),
        getattr(s, "panel_version", None),
        getattr(s, "scope", None),
        getattr(s, "location", None),
        getattr(s, "query_id", None),
        getattr(s, "data_origin", None),
        getattr(s, "history_type", None),
    )
    partitions: dict[tuple[Any, ...], list[Any]] = {}
    for signal in matching:
        partitions.setdefault(dimensions(signal), []).append(signal)
    if len(partitions) != 1:
        return DeterministicForecastResult(
            target_series="ambiguous_source_series",
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            provider=provider or "multiple",
            signal_family=signal_family,
            metric="unavailable",
            status="unavailable",
            readiness="unavailable",
            required_min_periods=min_periods,
            reason="Matching observations contain multiple incompatible source, unit, geography, or series partitions.",
            explanation="Forecasting is withheld rather than combining incompatible demand series.",
            limitations=["Select one comparable source-specific demand series before forecasting."],
        )

    (partition_key, partition_signals) = next(iter(partitions.items()))
    chosen_provider = partition_key[0] or "unknown"
    metric = partition_key[3]
    unit = "share" if metric == "normalized_share" else partition_key[4]
    invalid_periods = [
        signal for signal in partition_signals
        if _forecast_month_position(str(getattr(signal, "period", ""))) is None
    ]
    future_periods = [
        signal for signal in partition_signals
        if (position := _forecast_month_position(str(getattr(signal, "period", "")))) is not None
        and position > (as_of.year, as_of.month)
    ]
    eligible = [
        s for s in partition_signals
        if _forecast_month_is_complete(str(getattr(s, "period", "")), as_of)
    ]
    eligible.sort(key=lambda signal: _month_index(signal.period))
    periods = [str(signal.period) for signal in eligible]
    ordered = eligible
    first_sig = ordered[0] if ordered else None
    latest_sig = ordered[-1] if ordered else None
    resolved_name = canonical_name or getattr(latest_sig, "canonical_name", "Unknown")
    resolved_id = canonical_skill_id or getattr(latest_sig, "canonical_skill_id", None)
    target_series = getattr(latest_sig, "series_id", None) or f"{chosen_provider}:{signal_family}:{resolved_id or resolved_name}:{metric}" if latest_sig else f"{chosen_provider}:{signal_family}:{resolved_id or resolved_name}:unavailable"

    obs_ids: set[str] = set()
    run_ids: set[str] = set()
    for s in ordered:
        obs_ids.update(getattr(s, "observation_ids", []) or [])
        run_ids.update(getattr(s, "fetch_run_ids", []) or [])

    invalid_rows = [
        signal for signal in ordered
        if getattr(signal, "data_state", None) not in {"ready", "fresh"}
        or getattr(signal, "data_origin", None) != "real"
        or not str(getattr(signal, "unit", "") or "").strip()
        or getattr(signal, "history_type", None) not in {"platform_collected", "backfill", "backfilled"}
    ]
    invalid_rows.extend(invalid_periods)
    invalid_rows.extend(future_periods)
    if not resolved_id or resolved_id not in BY_ID:
        invalid_rows.extend(ordered or partition_signals)
    try:
        values = [_forecast_value(signal) for signal in ordered]
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Demand values must be finite and non-negative")
    except (TypeError, ValueError, OverflowError):
        values = []
        invalid_rows = invalid_rows or ordered

    # Quality reports are applicable only to the same source, signal family, skill, and series.
    if quality_reports and first_sig is not None and latest_sig is not None:
        for qr in quality_reports:
            if (
                getattr(qr, "provider", "").casefold().strip() == chosen_provider
                and getattr(qr, "signal_type", "") == signal_family
                and getattr(qr, "canonical_skill_id", None) == resolved_id
                and (not getattr(qr, "series_id", None) or getattr(qr, "series_id", None) == partition_key[6])
                and getattr(qr, "quality_state", "valid") != "valid"
            ):
                return DeterministicForecastResult(
                    target_series=target_series,
                    canonical_skill_id=resolved_id,
                    canonical_name=resolved_name,
                    provider=chosen_provider,
                    signal_family=signal_family,
                    metric=metric,
                    unit=unit,
                    status="unavailable",
                    readiness="unavailable",
                    history_length=len(periods),
                    required_min_periods=min_periods,
                    first_history_period=first_sig.period if first_sig else None,
                    latest_history_period=latest_sig.period if latest_sig else None,
                    observation_ids=sorted(obs_ids),
                    fetch_run_ids=sorted(run_ids),
                    reason=f"Quality gate blocked forecasting: quality_state='{qr.quality_state}'.",
                    explanation=f"Forecasting for {target_series} is blocked by series quality checks ({qr.quality_state}).",
                    limitations=["Series must pass quality and continuity gates before forecasting."],
                )

    if invalid_rows:
        return DeterministicForecastResult(
            target_series=target_series,
            canonical_skill_id=resolved_id,
            canonical_name=resolved_name,
            provider=chosen_provider,
            signal_family=signal_family,
            metric=str(metric or "unavailable"),
            unit=unit,
            status="unavailable",
            readiness="unavailable",
            history_length=len(periods),
            required_min_periods=min_periods,
            reason="One or more observations failed period, identity, state, origin, history-type, unit, or numeric-value validation.",
            explanation="Forecasting is withheld because the candidate series contains invalid demand observations.",
            limitations=["Only real, validated, canonical monthly observations with explicit units can be forecast."],
        )

    if len(periods) < min_periods or not _consecutive_periods(periods):
        reason = (
            f"Requires >= {min_periods} valid consecutive monthly observations; only {len(periods)} available."
            if len(periods) < min_periods
            else f"Series contains missing period gaps between {first_sig.period} and {latest_sig.period}."
        )
        return DeterministicForecastResult(
            target_series=target_series,
            canonical_skill_id=resolved_id,
            canonical_name=resolved_name,
            provider=chosen_provider,
            signal_family=signal_family,
            metric=metric,
            unit=unit,
            status="insufficient_data",
            readiness="insufficient_history",
            history_length=len(periods),
            required_min_periods=min_periods,
            first_history_period=first_sig.period if first_sig else None,
            latest_history_period=latest_sig.period if latest_sig else None,
            observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids),
            reason=reason,
            explanation=f"Deterministic forecast for {target_series} is withheld: {reason}",
            limitations=[
                f"Minimum history gate for forecasting is {min_periods} consecutive monthly periods.",
                "No forecast values are fabricated when historical depth is insufficient.",
            ],
        )

    n = len(values)
    horizon = min(6, n // 3)
    if horizon < 1:
        horizon = 1

    # Reserve a chronological tail for evaluation; never score on in-sample fitted values.
    holdout_size = max(6, n // 3)
    holdout_start = n - holdout_size

    # Baseline: seasonal-naive (12-month carry-forward).
    # Challenger: Holt-Winters additive ETS (pure Python, no external dependencies).
    # Each model is evaluated on chronological one-step-ahead holdout predictions.
    # Data leakage is prevented: each split uses only the training prefix values[:split_idx].
    baseline_errors: list[float] = []
    ets_errors: list[float] = []
    ets_available = True

    for split_idx in range(holdout_start, n):
        train_slice = values[:split_idx]
        actual = values[split_idx]

        # Seasonal-naive: repeat the value from 12 months prior.
        baseline_pred = _seasonal_naive(train_slice, 1)[0]
        baseline_errors.append(actual - baseline_pred)

        # ETS challenger: Holt-Winters additive with fixed smoothing weights.
        # Falls back gracefully if training length is insufficient (< 2 seasons = 24 obs).
        if ets_available:
            ets_preds = _holt_winters_additive(train_slice, 1)
            if ets_preds:
                ets_errors.append(actual - ets_preds[0])
            else:
                ets_available = False

    def _rmse(errors: list[float]) -> float:
        return math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else math.inf

    def _mae(errors: list[float]) -> float:
        return sum(abs(e) for e in errors) / len(errors) if errors else math.inf

    def _mase(errors: list[float], train: list[float]) -> float | None:
        """Mean Absolute Scaled Error using naive (lag-1) in-sample denominator."""
        if len(train) < 2 or not errors:
            return None
        naive_mae = sum(abs(train[i] - train[i - 1]) for i in range(1, len(train))) / (len(train) - 1)
        if naive_mae == 0.0:
            return None
        return sum(abs(e) for e in errors) / (len(errors) * naive_mae)

    baseline_rmse = _rmse(baseline_errors)
    baseline_mae = _mae(baseline_errors)
    baseline_mase = _mase(baseline_errors, values[:holdout_start])

    # Determine winner: ETS wins only if it produces lower RMSE on the holdout
    # and was successfully evaluated on the same holdout window.
    ets_rmse = _rmse(ets_errors) if (ets_available and len(ets_errors) == holdout_size) else math.inf
    ets_mae = _mae(ets_errors) if ets_errors else math.inf
    ets_mase = _mase(ets_errors, values[:holdout_start]) if ets_errors else None

    ets_beats_baseline = ets_available and len(ets_errors) == holdout_size and ets_rmse < baseline_rmse
    selected_method: ForecastMethodName = "es_smoothing" if ets_beats_baseline else "seasonal_naive"
    winner_rmse = ets_rmse if ets_beats_baseline else baseline_rmse

    scores: list[BacktestMethodScore] = [
        BacktestMethodScore(
            method="seasonal_naive",
            rmse=round(baseline_rmse, 6),
            mae=round(baseline_mae, 6),
            beats_naive=False,  # The baseline cannot beat itself
        ),
    ]
    if ets_available and len(ets_errors) == holdout_size:
        scores.append(BacktestMethodScore(
            method="es_smoothing",
            rmse=round(ets_rmse, 6),
            mae=round(ets_mae, 6),
            beats_naive=ets_beats_baseline,
        ))

    # Report whether the challenger beat the baseline; if ETS was unavailable (insufficient
    # training history for 2 seasons), beats_naive_baseline stays False — correct, not fabricated.
    beats_naive_baseline = ets_beats_baseline

    limitations: list[str] = [
        f"Forecast horizon is capped at {horizon} months (min(6, history_length // 3)).",
        "Baseline: seasonal-naive (12-month carry-forward). Challenger: Holt-Winters additive ETS.",
        f"RMSE and MAE evaluated on {holdout_size} chronological one-step holdout predictions.",
        "beats_naive_baseline=True only when the ETS challenger outperforms seasonal-naive on the holdout.",
    ]
    if not ets_available or len(ets_errors) < holdout_size:
        limitations.append(
            f"ETS challenger required >= 24 training observations per holdout split; "
            f"seasonal-naive was used exclusively. beats_naive_baseline is always False "
            f"when only the baseline is evaluated."
        )
    if metric != "normalized_share":
        limitations.append(f"Values are reported in source unit '{unit}'; platform volume changes may affect them.")

    # Generate final forecasts using the selected (winning) method.
    if selected_method == "es_smoothing":
        raw_preds = _holt_winters_additive(values, horizon) or _seasonal_naive(values, horizon)
    else:
        raw_preds = _seasonal_naive(values, horizon)

    last_month_idx = _month_index(latest_sig.period)
    forecast_points: list[ForecastPoint] = []
    limitations.append("Prediction intervals are omitted until horizon-specific holdout coverage is sufficient.")
    for step_idx, pt in enumerate(raw_preds, start=1):
        pf = max(0.0, pt)
        forecast_points.append(ForecastPoint(
            period=_format_period_from_index(last_month_idx + step_idx),
            horizon_step=step_idx,
            point_forecast=round(pf, 6),
        ))

    winner_mae = ets_mae if ets_beats_baseline else baseline_mae
    baseline_name = (
        "seasonal_naive (12-month seasonal carry-forward)"
    )
    selected_name = (
        "es_smoothing (Holt-Winters additive ETS)" if ets_beats_baseline
        else "seasonal_naive (12-month seasonal carry-forward, baseline only)"
    )

    return DeterministicForecastResult(
        target_series=target_series,
        canonical_skill_id=resolved_id,
        canonical_name=resolved_name,
        provider=chosen_provider,
        signal_family=signal_family,
        metric=metric,
        unit=unit,
        status="ready",
        readiness="ready",
        selected_method=selected_method,
        baseline_name=baseline_name,
        error_metric="RMSE",
        winner_rmse=round(winner_rmse, 6),
        naive_rmse=round(baseline_rmse, 6),
        beats_naive_baseline=beats_naive_baseline,
        horizon_months=horizon,
        history_length=n,
        required_min_periods=min_periods,
        backtest_sample_size=holdout_size,
        backtest_periods=periods[holdout_start:],
        observed_history=[
            {"period": signal.period, "value": round(value, 6), "unit": unit}
            for signal, value in zip(ordered, values)
        ],
        first_history_period=first_sig.period,
        latest_history_period=latest_sig.period,
        backtest_scores=scores,
        forecasts=forecast_points,
        observation_ids=sorted(obs_ids),
        fetch_run_ids=sorted(run_ids),
        reason=(
            f"Selected method: {selected_method}. "
            f"ETS {'beat' if ets_beats_baseline else 'did not beat'} seasonal-naive on "
            f"{holdout_size} chronological holdout predictions "
            f"(ETS RMSE={ets_rmse:.6f} vs baseline RMSE={baseline_rmse:.6f})."
            if (ets_available and len(ets_errors) == holdout_size) else
            f"Seasonal-naive baseline used exclusively (ETS requires >= 24 obs per holdout split; "
            f"holdout had {holdout_size} steps, minimum training per step was {holdout_start} obs)."
        ),
        explanation=(
            f"{horizon}-month forecast for {target_series} using {selected_name}. "
            f"Holdout RMSE={round(winner_rmse, 6)} {unit}; MAE={round(winner_mae, 6)} {unit}. "
            f"beats_naive_baseline={beats_naive_baseline}."
        ),
        limitations=limitations,
    )



def forecast_signal_series_by_source(
    signals: Sequence[Any],
    *,
    canonical_skill_id: str | None = None,
    canonical_name: str = "",
    min_periods: int = DEFAULT_FORECAST_MIN_PERIODS,
    quality_reports: Sequence[Any] | None = None,
    as_of: date | None = None,
    history_complete: bool = True,
) -> list[DeterministicForecastResult]:
    """Forecast each strictly comparable monthly demand partition independently."""
    if not history_complete:
        return [forecast_signal_series(
            [],
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name,
            min_periods=min_periods,
            quality_reports=quality_reports,
            as_of=as_of,
            history_complete=False,
        )]
    partitions: dict[tuple[Any, ...], list[Any]] = {}
    for signal in signals:
        if getattr(signal, "signal_type", None) != "demand":
            continue
        if canonical_skill_id and getattr(signal, "canonical_skill_id", None) != canonical_skill_id:
            continue
        if canonical_name and getattr(signal, "canonical_name", "").casefold() != canonical_name.casefold():
            continue
        key = (
            getattr(signal, "source", "").casefold().strip(),
            getattr(signal, "signal_type", None),
            getattr(signal, "canonical_skill_id", None),
            getattr(signal, "metric", None),
            getattr(signal, "unit", None),
            getattr(signal, "denominator_unit", None),
            getattr(signal, "series_id", None),
            getattr(signal, "panel_version", None),
            getattr(signal, "scope", None),
            getattr(signal, "location", None),
            getattr(signal, "query_id", None),
            getattr(signal, "data_origin", None),
            getattr(signal, "history_type", None),
        )
        partitions.setdefault(key, []).append(signal)

    results = [
        forecast_signal_series(
            group,
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name,
            signal_family="demand",
            provider=str(key[0]),
            min_periods=min_periods,
            quality_reports=quality_reports,
            as_of=as_of,
            history_complete=history_complete,
        )
        for key, group in partitions.items()
    ]
    return sorted(results, key=lambda result: (result.provider, result.target_series))


class MarketRankingRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    entity_id: str | None
    entity_name: str
    metric_value: float
    raw_value: float
    denominator: float | None = None
    period: str
    theil_sen_slope_per_month: float | None = None
    whole_window_change: float | None = None
    whole_window_pct_change: float | None = None
    latest_mom_change: float | None = None
    latest_mom_pct_change: float | None = None
    trend_direction: str = "Insufficient Data"
    observation_ids: list[str] = Field(default_factory=list)


class MarketRankingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error"]
    metric_name: str
    metric_definition: str
    time_window: str
    period: str | None
    provider: str
    signal_family: str
    tracked_panel: str
    tracked_panel_size: int
    eligible_entity_count: int
    panel_coverage_ratio: float
    rows: list[MarketRankingRow] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason: str = ""


def build_market_ranking(
    signals: Sequence[Any],
    *,
    provider: str,
    signal_family: str = "demand",
    metric_name: Literal["normalized_share", "theil_sen_slope", "raw_count"] = "normalized_share",
    period: str | None = None,
    tracked_panel: str = "canonical_registry_v1",
    tracked_panel_size: int = 25,
    top_k: int = 5,
    min_trend_periods: int = 4,
) -> MarketRankingResult:
    """Rank entities within a single provider, signal family, metric, and period/window without padding."""
    prov_norm = provider.casefold().strip()
    fam_norm = signal_family.strip()

    prov_signals = [
        s for s in signals
        if getattr(s, "source", "").casefold().strip() == prov_norm
        and getattr(s, "signal_type", "").strip() == fam_norm
    ]

    metric_defs = {
        "normalized_share": "Entity observation count divided by source-specific total observations in the same period.",
        "theil_sen_slope": "Theil-Sen median pairwise monthly slope across the eligible consecutive observation window.",
        "raw_count": "Raw provider observation count in the period (subject to platform volume changes).",
    }
    definition = metric_defs.get(metric_name, metric_name)

    if not prov_signals:
        return MarketRankingResult(
            status="unavailable",
            metric_name=metric_name,
            metric_definition=definition,
            time_window="unavailable",
            period=period,
            provider=prov_norm,
            signal_family=fam_norm,
            tracked_panel=tracked_panel,
            tracked_panel_size=tracked_panel_size,
            eligible_entity_count=0,
            panel_coverage_ratio=0.0,
            rows=[],
            limitations=["No observations available for this provider and signal family."],
            reason=f"No '{fam_norm}' signals found for provider '{prov_norm}'.",
        )

    all_periods = sorted({s.period for s in prov_signals}, key=_month_index)
    target_period = period or all_periods[-1]
    time_window = f"{all_periods[0]} to {target_period}" if len(all_periods) > 1 else target_period

    by_entity: dict[str, list[Any]] = {}
    for s in prov_signals:
        if _month_index(s.period) <= _month_index(target_period):
            by_entity.setdefault(s.canonical_name, []).append(s)

    candidates: list[MarketRankingRow] = []
    for entity_name, ent_sigs in by_entity.items():
        by_p = {s.period: s for s in sorted(ent_sigs, key=lambda x: _month_index(x.period))}
        if target_period not in by_p:
            continue
        latest = by_p[target_period]
        p_list = sorted(by_p.keys(), key=_month_index)
        ordered = [by_p[p] for p in p_list]

        if metric_name == "normalized_share":
            if getattr(latest, "metric", "") != "normalized_share" or getattr(latest, "normalized_value", None) is None:
                continue
            m_val = float(latest.normalized_value)
        elif metric_name == "raw_count":
            m_val = float(latest.raw_value)
        elif metric_name == "theil_sen_slope":
            if len(ordered) < min_trend_periods or not _consecutive_periods(p_list):
                continue
            vals = [
                float(s.normalized_value) if (s.metric == "normalized_share" and s.normalized_value is not None) else float(s.raw_value)
                for s in ordered
            ]
            m_val = round(theil_sen_slope(vals), 6)
        else:
            continue

        vals = [
            float(s.normalized_value) if (s.metric == "normalized_share" and s.normalized_value is not None) else float(s.raw_value)
            for s in ordered
        ]
        slope_val = None
        trend_dir = "Insufficient Data"
        if len(vals) >= min_trend_periods and _consecutive_periods(p_list):
            slope_val = round(theil_sen_slope(vals), 6)
            trend_dir = "Increasing" if slope_val > 1e-6 else "Declining" if slope_val < -1e-6 else "Stable"

        ww_change = round(vals[-1] - vals[0], 6) if len(vals) >= 2 else None
        ww_pct = round(((vals[-1] - vals[0]) / abs(vals[0])) * 100, 2) if (len(vals) >= 2 and vals[0] != 0) else None
        mom_change = None
        mom_pct = None
        if len(vals) >= 2 and _month_index(p_list[-1]) - _month_index(p_list[-2]) == 1:
            mom_change = round(vals[-1] - vals[-2], 6)
            if vals[-2] != 0:
                mom_pct = round(((vals[-1] - vals[-2]) / abs(vals[-2])) * 100, 2)

        candidates.append(MarketRankingRow(
            rank=0,
            entity_id=getattr(latest, "canonical_skill_id", None),
            entity_name=entity_name,
            metric_value=round(m_val, 6),
            raw_value=float(latest.raw_value),
            denominator=getattr(latest, "denominator", None),
            period=target_period,
            theil_sen_slope_per_month=slope_val,
            whole_window_change=ww_change,
            whole_window_pct_change=ww_pct,
            latest_mom_change=mom_change,
            latest_mom_pct_change=mom_pct,
            trend_direction=trend_dir,
            observation_ids=list(getattr(latest, "observation_ids", []) or []),
        ))

    candidates.sort(key=lambda r: (-r.metric_value, r.entity_name))
    eligible_count = len(candidates)
    panel_size = max(tracked_panel_size, eligible_count, 1)
    coverage = round(eligible_count / panel_size, 4)

    top_rows: list[MarketRankingRow] = []
    for idx, row in enumerate(candidates[:top_k], start=1):
        row.rank = idx
        top_rows.append(row)

    limitations: list[str] = [
        f"Ranked strictly within provider '{prov_norm}' ({fam_norm}) for period {target_period}; providers are never merged.",
    ]
    if metric_name == "raw_count":
        limitations.append("raw count; platform volume changes may affect it")
    if eligible_count < top_k:
        limitations.append(
            f"Only {eligible_count} eligible entities available in panel '{tracked_panel}' for {target_period} "
            f"(< {top_k} requested); rows are never padded with synthetic or cross-provider entries."
        )

    if eligible_count == 0:
        status: Literal["ready", "partial", "insufficient_data"] = "insufficient_data"
        reason = f"0 eligible entities met metric '{metric_name}' criteria in period {target_period}."
    elif eligible_count < top_k:
        status = "partial"
        reason = f"Partial panel coverage: {eligible_count}/{panel_size} eligible entities ({len(top_rows)} rows returned)."
    else:
        status = "ready"
        reason = f"Ranked {len(top_rows)} of {eligible_count} eligible entities in '{tracked_panel}'."

    return MarketRankingResult(
        status=status,
        metric_name=metric_name,
        metric_definition=definition,
        time_window=time_window,
        period=target_period,
        provider=prov_norm,
        signal_family=fam_norm,
        tracked_panel=tracked_panel,
        tracked_panel_size=panel_size,
        eligible_entity_count=eligible_count,
        panel_coverage_ratio=coverage,
        rows=top_rows,
        limitations=limitations,
        reason=reason,
    )

"""Skill Half-Life calculation for TalentScope.ai.

Definition:
- Estimated months for a skill's market share in a single named signal family
  (`demand`, `interest`, or `adoption`) to decay by 50% under an exponential decay model.
- The reference level is the first observed normalized share in the returned fitted period.
- Formula: `half_life_months = ln(2) / abs(b)`, where `b` is the Theil-Sen slope of `ln(share)`
  per month.
- Eligibility gates:
  1. Single named signal family (`demand`, `interest`, or `adoption`).
  2. Valid positive share series (`metric == "normalized_share"`, `share > 0`).
     Never calculate Half-Life from raw counts without a valid source-specific denominator.
  3. Default `>= 36` consecutive monthly observations (configurable via `min_periods`).
  4. Statistically supported monotone decline (`b < 0`, Kendall tau `<= -0.5`, and
     one-sided Mann-Kendall p-value `< alpha`, default `alpha = 0.05`).
- Returns:
  - `not_applicable` when the series is growing (`b >= 0`) or flat / not statistically
    significantly declining (`p_value >= alpha`).
  - `insufficient_data` or `unavailable` when history is shorter than `min_periods`,
    has gaps, or lacks a valid denominator (raw count).
  - `ready` with `half_life_months`, `half_life_years`, and Sen-slope confidence interval
    uncertainty range `[lower_months, upper_months]` when all gates pass.
"""

from __future__ import annotations

import math
import re
import statistics
from datetime import date
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.trend import _consecutive_periods, _month_index, _period_is_complete

LN2 = math.log(2.0)
DEFAULT_HALF_LIFE_MIN_PERIODS = 36
MIN_NEGATIVE_KENDALL_TAU = -0.5


class SkillHalfLifeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_skill_id: str | None
    canonical_name: str
    signal_family: Literal["demand", "interest", "adoption"]
    provider: str
    signal_type: Literal["demand", "interest", "adoption"] = "demand"
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    half_life_months: float | None = None
    half_life_years: float | None = None
    uncertainty_range_months: tuple[float, float | None] | None = None
    log_share_slope_per_month: float | None = None
    slope_ci_95: tuple[float, float] | None = None
    kendall_tau: float | None = None
    kendall_p_value: float | None = None
    periods_evaluated: int = 0
    required_min_periods: int = DEFAULT_HALF_LIFE_MIN_PERIODS
    first_period: str | None = None
    latest_period: str | None = None
    reference_period: str | None = None
    reference_normalized_share: float | None = None
    periods_used: list[str] = Field(default_factory=list)
    value_unit: str | None = None
    denominator_unit: str | None = None
    half_life_unit: str = "months"
    model_name: str = "exponential_decay_on_log_normalized_share"
    fit_residual_mad: float | None = None
    robust_fit_r_squared: float | None = None
    metric: str = "raw_count"
    series_id: str | None = None
    panel_version: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    data_origin: str | None = None
    history_type: str | None = None
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    limitations: list[str] = Field(default_factory=list)
    explanation: str = ""
    calculation_version: str = "skill-half-life-theil-sen-log-share-v1"


def _mann_kendall_and_sen_ci(
    values: Sequence[float],
    *,
    z_alpha: float = 1.959963984540054,
) -> tuple[float, float, float, float, float]:
    """Compute Theil-Sen slope, Kendall's tau, two-sided/one-sided p-value, and 95% slope CI."""
    n = len(values)
    if n < 2:
        raise ValueError("At least 2 values are required.")

    slopes: list[float] = []
    s_stat = 0
    tie_counts: dict[float, int] = {}

    for v in values:
        tie_counts[v] = tie_counts.get(v, 0) + 1

    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            slopes.append(diff / (j - i))
            if diff > 0:
                s_stat += 1
            elif diff < 0:
                s_stat -= 1

    slopes.sort()
    m = len(slopes)
    b = statistics.median(slopes)
    tau = s_stat / m if m > 0 else 0.0

    # Variance of S with tie correction
    tie_term = sum(t * (t - 1) * (2 * t + 5) for t in tie_counts.values() if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    if var_s <= 0:
        return b, tau, 1.0, b, b

    std_s = math.sqrt(var_s)
    if s_stat > 0:
        z_stat = (s_stat - 1.0) / std_s
    elif s_stat < 0:
        z_stat = (s_stat + 1.0) / std_s
    else:
        z_stat = 0.0

    # One-sided p-value for negative trend (H1: tau < 0)
    # Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
    p_value_negative = 0.5 * (1.0 + math.erf(z_stat / math.sqrt(2.0)))

    # Sen slope confidence interval via rank order statistics
    c_alpha = z_alpha * std_s
    r1 = max(0, int(math.floor((m - c_alpha) / 2.0)))
    r2 = min(m - 1, int(math.ceil((m + c_alpha) / 2.0)))
    slope_lower = slopes[r1]
    slope_upper = slopes[r2]

    return b, tau, p_value_negative, slope_lower, slope_upper


def calculate_skill_half_life(
    signals: Sequence[Any],
    *,
    canonical_skill_id: str | None = None,
    canonical_name: str = "",
    signal_family: Literal["demand", "interest", "adoption"] = "demand",
    provider: str | None = None,
    min_periods: int = DEFAULT_HALF_LIFE_MIN_PERIODS,
    alpha: float = 0.05,
    history_complete: bool = True,
    as_of: date | None = None,
) -> SkillHalfLifeResult:
    """Calculate Skill Half-Life for a single named signal family from normalized share observations."""
    # Keep the operational policy fixed even if an internal caller requests a lower floor.
    min_periods = max(DEFAULT_HALF_LIFE_MIN_PERIODS, min_periods)
    matching = [
        s for s in signals
        if getattr(s, "signal_type", None) == signal_family
        and (not provider or getattr(s, "source", "").casefold().strip() == provider.casefold().strip())
        and (
            getattr(s, "canonical_skill_id", None) == canonical_skill_id
            if canonical_skill_id else
            bool(canonical_name) and getattr(s, "canonical_name", "").casefold() == canonical_name.casefold()
        )
    ]

    if not history_complete:
        return SkillHalfLifeResult(
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            signal_family=signal_family,
            signal_type=signal_family,
            provider=provider or "unavailable",
            status="unavailable",
            required_min_periods=min_periods,
            reason="Observation history is incomplete because the bounded read reached its row limit.",
            limitations=["Truncated history cannot support a complete-period decay fit."],
            explanation="Skill Half-Life is unavailable because the retrieved observation history may be truncated.",
        )
    if not matching:
        return SkillHalfLifeResult(
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            signal_family=signal_family,
            signal_type=signal_family,
            provider=provider or "unavailable",
            status="unavailable",
            required_min_periods=min_periods,
            reason=f"No '{signal_family}' series found for {canonical_name or canonical_skill_id or 'requested skill'}.",
            limitations=["No verified source-specific skill observations were available for this measure."],
            explanation=(
                f"Skill Half-Life is unavailable because no '{signal_family}' series exists for "
                f"{canonical_name or canonical_skill_id or 'this skill'}."
            ),
        )

    # Never join different series identities or dimensions into one decay fit.
    by_series: dict[tuple[Any, ...], list[Any]] = {}
    for sig in matching:
        key = (
            getattr(sig, "source", "unknown").casefold().strip(),
            getattr(sig, "metric", None),
            getattr(sig, "series_id", None),
            getattr(sig, "unit", None),
            getattr(sig, "denominator_unit", None),
            getattr(sig, "scope", None),
            (getattr(sig, "location", None) or "").casefold(),
            getattr(sig, "query_id", None),
            getattr(sig, "panel_version", None),
            getattr(sig, "data_origin", None),
            getattr(sig, "history_type", None),
            getattr(sig, "extractor_version", None),
            getattr(sig, "canonical_skill_id", None),
        )
        by_series.setdefault(key, []).append(sig)

    if len(by_series) != 1:
        return SkillHalfLifeResult(
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or getattr(matching[0], "canonical_name", "Unknown"),
            signal_family=signal_family,
            signal_type=signal_family,
            provider=provider or "multiple",
            status="unavailable",
            required_min_periods=min_periods,
            reason="Multiple incompatible source-specific series matched; select one provider and compatible series.",
            limitations=["Source, unit, geography, query, and series dimensions are not interchangeable."],
            explanation="Skill Half-Life is unavailable because the matching observations do not identify one comparable series.",
        )
    (chosen_provider, metric, series_id, unit, denominator_unit, scope, _, query_id,
     panel_version, data_origin, history_type, _, series_skill_id), prov_signals = next(iter(by_series.items()))

    by_period: dict[str, Any] = {}
    for s in sorted(prov_signals, key=lambda x: _month_index(x.period)):
        by_period[s.period] = s
    periods = sorted(by_period.keys(), key=_month_index)
    ordered = [by_period[p] for p in periods]

    first_sig = ordered[0]
    latest_sig = ordered[-1]
    resolved_name = canonical_name or getattr(latest_sig, "canonical_name", "Unknown")
    resolved_id = canonical_skill_id or series_skill_id
    location_display = getattr(latest_sig, "location", None)

    obs_ids: set[str] = set()
    run_ids: set[str] = set()
    for s in ordered:
        obs_ids.update(getattr(s, "observation_ids", []) or [])
        run_ids.update(getattr(s, "fetch_run_ids", []) or [])

    identity_valid = bool(resolved_id and series_id and unit and denominator_unit)
    monthly_periods = all(re.fullmatch(r"\d{4}-\d{2}", period or "") for period in periods)
    latest_period_is_closed = bool(periods and _period_is_complete(periods[-1], as_of=as_of))

    # Gate 1: Must have valid source-specific denominator (normalized_share)
    is_valid_share = (
        metric == "normalized_share"
        and bool(unit)
        and bool(denominator_unit)
        and all(
            getattr(s, "normalized_value", None) is not None
            and float(getattr(s, "normalized_value", 0.0)) > 0
            and float(getattr(s, "normalized_value", 0.0)) <= 1
            and math.isfinite(float(getattr(s, "normalized_value", 0.0)))
            and getattr(s, "denominator", None) is not None
            and float(getattr(s, "denominator", 0.0)) > 0
            and math.isfinite(float(getattr(s, "denominator", 0.0)))
            and getattr(s, "data_state", None) in {"ready", "fresh"}
            and getattr(s, "data_origin", None) == "real"
            for s in ordered
        )
    )
    if not is_valid_share:
        reason = (
            "Raw count series without a source-specific denominator; Half-Life is never calculated from raw counts."
            if metric != "normalized_share"
            else "Normalized share or denominator failed validation; values must be finite, shares in (0, 1], and observations ready real data."
        )
        return SkillHalfLifeResult(
            canonical_skill_id=resolved_id,
            canonical_name=resolved_name,
            signal_family=signal_family,
            signal_type=signal_family,
            provider=chosen_provider,
            status="insufficient_data",
            periods_evaluated=len(periods),
            required_min_periods=min_periods,
            first_period=first_sig.period,
            latest_period=latest_sig.period,
            periods_used=periods,
            value_unit=unit,
            denominator_unit=denominator_unit,
            metric=metric,
            series_id=series_id,
            panel_version=panel_version,
            scope=scope,
            location=location_display,
            query_id=query_id,
            data_origin=data_origin,
            history_type=history_type,
            observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids),
            reason=reason,
            limitations=["A positive finite normalized share and denominator are required for a decay fit."],
            explanation=(
                f"Skill Half-Life for {resolved_name} ({signal_family} on {chosen_provider}) cannot be calculated "
                f"because {reason.casefold()}"
            ),
        )

    if not identity_valid or not monthly_periods or not latest_period_is_closed:
        reason = (
            "A canonical skill ID, stable series identity, value unit, and denominator unit are required."
            if not identity_valid else
            "Half-Life currently requires monthly periods."
            if not monthly_periods else
            "The latest observation period is not yet complete."
        )
        return SkillHalfLifeResult(
            canonical_skill_id=resolved_id, canonical_name=resolved_name,
            signal_family=signal_family, signal_type=signal_family, provider=chosen_provider,
            status="insufficient_data", periods_evaluated=len(periods),
            required_min_periods=min_periods, first_period=first_sig.period,
            latest_period=latest_sig.period, reference_period=first_sig.period,
            reference_normalized_share=float(first_sig.normalized_value),
            periods_used=periods,
            value_unit=unit, denominator_unit=denominator_unit, metric=metric,
            series_id=series_id, panel_version=panel_version, scope=scope,
            location=location_display, query_id=query_id, data_origin=data_origin,
            history_type=history_type, observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids), reason=reason,
            limitations=["A canonical, complete monthly series is required for a supported half-life estimate."],
            explanation=f"Skill Half-Life is unavailable for {resolved_name}: {reason}",
        )

    # Gate 2: Require complete monthly coverage.
    if len(periods) < min_periods or not _consecutive_periods(periods):
        reason = (
            f"Requires >= {min_periods} consecutive monthly share observations; only {len(periods)} available."
            if len(periods) < min_periods
            else f"Series has missing monthly periods across {first_sig.period} to {latest_sig.period}."
        )
        return SkillHalfLifeResult(
            canonical_skill_id=resolved_id,
            canonical_name=resolved_name,
            signal_family=signal_family,
            signal_type=signal_family,
            provider=chosen_provider,
            status="insufficient_data",
            periods_evaluated=len(periods),
            required_min_periods=min_periods,
            first_period=first_sig.period,
            latest_period=latest_sig.period,
            reference_period=first_sig.period,
            reference_normalized_share=float(first_sig.normalized_value),
            periods_used=periods,
            value_unit=unit,
            denominator_unit=denominator_unit,
            metric=metric,
            series_id=series_id,
            panel_version=panel_version,
            scope=scope,
            location=location_display,
            query_id=query_id,
            data_origin=data_origin,
            history_type=history_type,
            observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids),
            reason=reason,
            limitations=["Every month in the fitted interval must be present; missing months are not imputed."],
            explanation=(
                f"Skill Half-Life for {resolved_name} ({signal_family} on {chosen_provider}) is insufficient_data: {reason}"
            ),
        )

    log_shares = [math.log(float(s.normalized_value)) for s in ordered]
    b, tau, p_val_neg, slope_low, slope_high = _mann_kendall_and_sen_ci(log_shares)
    x_values = list(range(len(log_shares)))
    intercept = statistics.median(y - b * x for x, y in zip(x_values, log_shares))
    residuals = [y - (intercept + b * x) for x, y in zip(x_values, log_shares)]
    fit_residual_mad = statistics.median(abs(value - statistics.median(residuals)) for value in residuals)
    mean_log_share = statistics.mean(log_shares)
    total_squared_deviation = sum((value - mean_log_share) ** 2 for value in log_shares)
    robust_fit_r_squared = (
        1.0 - sum(value**2 for value in residuals) / total_squared_deviation
        if total_squared_deviation > 0 else 1.0
    )

    # Gate 3: reject growing, weakly monotone, or statistically unsupported decline.
    if b >= 0 or tau > MIN_NEGATIVE_KENDALL_TAU or p_val_neg >= alpha:
        reason = (
            f"Decay fit is unsupported (log-share Theil-Sen slope {b:+.6f}/mo, Kendall tau {tau:+.4f}, "
            f"one-sided decay p-value {p_val_neg:.4f}; require slope < 0, tau <= {MIN_NEGATIVE_KENDALL_TAU}, "
            f"and p < {alpha})."
        )
        return SkillHalfLifeResult(
            canonical_skill_id=resolved_id,
            canonical_name=resolved_name,
            signal_family=signal_family,
            signal_type=signal_family,
            provider=chosen_provider,
            status="not_applicable",
            half_life_months=None,
            half_life_years=None,
            uncertainty_range_months=None,
            log_share_slope_per_month=round(b, 6),
            slope_ci_95=(round(slope_low, 6), round(slope_high, 6)),
            kendall_tau=round(tau, 4),
            kendall_p_value=round(p_val_neg, 4),
            periods_evaluated=len(periods),
            required_min_periods=min_periods,
            first_period=first_sig.period,
            latest_period=latest_sig.period,
            reference_period=first_sig.period,
            reference_normalized_share=float(first_sig.normalized_value),
            periods_used=periods,
            value_unit=unit,
            denominator_unit=denominator_unit,
            fit_residual_mad=round(fit_residual_mad, 6),
            robust_fit_r_squared=round(robust_fit_r_squared, 4),
            metric=metric,
            series_id=series_id,
            panel_version=panel_version,
            scope=scope,
            location=location_display,
            query_id=query_id,
            data_origin=data_origin,
            history_type=history_type,
            observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids),
            reason=reason,
            limitations=[
                "Half-Life is an empirical source-specific decay estimate, not a forecast of skill obsolescence.",
                "A weak or irregular monotonic relationship does not support the exponential-decay interpretation.",
            ],
            explanation=(
                f"Skill Half-Life is not_applicable for {resolved_name} ({signal_family} on {chosen_provider}) "
                "because the normalized share series is not undergoing statistically significant decay."
            ),
        )

    # Statistically significant negative slope: b < 0 and p_val_neg < alpha
    half_life_months = round(LN2 / abs(b), 2)
    half_life_years = round(half_life_months / 12.0, 2)

    # Uncertainty range from slope confidence interval [slope_low, slope_high]
    # Faster decay corresponds to more negative slope (slope_low < b < 0) -> shorter half-life
    lower_hl = round(LN2 / abs(slope_low), 2) if slope_low < 0 else half_life_months
    upper_hl: float | None = round(LN2 / abs(slope_high), 2) if slope_high < -1e-9 else None

    uncertainty_text = (
        f"[{lower_hl}, {upper_hl}] months" if upper_hl is not None else f"[{lower_hl}, inf) months"
    )

    return SkillHalfLifeResult(
        canonical_skill_id=resolved_id,
        canonical_name=resolved_name,
        signal_family=signal_family,
        signal_type=signal_family,
        provider=chosen_provider,
        status="ready",
        half_life_months=half_life_months,
        half_life_years=half_life_years,
        uncertainty_range_months=(lower_hl, upper_hl),
        log_share_slope_per_month=round(b, 6),
        slope_ci_95=(round(slope_low, 6), round(slope_high, 6)),
        kendall_tau=round(tau, 4),
        kendall_p_value=round(p_val_neg, 4),
        periods_evaluated=len(periods),
        required_min_periods=min_periods,
        first_period=first_sig.period,
        latest_period=latest_sig.period,
        reference_period=first_sig.period,
        reference_normalized_share=float(first_sig.normalized_value),
        periods_used=periods,
        value_unit=unit,
        denominator_unit=denominator_unit,
        fit_residual_mad=round(fit_residual_mad, 6),
        robust_fit_r_squared=round(robust_fit_r_squared, 4),
        metric=metric,
        series_id=series_id,
        panel_version=panel_version,
        scope=scope,
        location=location_display,
        query_id=query_id,
        data_origin=data_origin,
        history_type=history_type,
        observation_ids=sorted(obs_ids),
        fetch_run_ids=sorted(run_ids),
        reason=f"Statistically significant decay detected across {len(periods)} monthly share observations.",
        limitations=[
            "Half-Life describes the fitted normalized share series only; it is not a job-loss or skill-obsolescence probability.",
            "The exponential-decay assumption is supported only for the selected source, signal, unit, geography, and period window.",
            "The Kendall significance test and Sen-slope interval do not adjust for serial autocorrelation or structural breaks.",
        ],
        explanation=(
            f"{resolved_name} {signal_family} share on {chosen_provider} has an estimated Skill Half-Life of "
            f"{half_life_months} months ({half_life_years} years), with 95% slope uncertainty range {uncertainty_text} "
            f"(log-share Theil-Sen slope {b:+.6f}/mo, Kendall tau {tau:+.4f}, p={p_val_neg:.4f})."
        ),
    )

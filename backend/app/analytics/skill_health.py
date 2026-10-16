"""Explainable source-specific Skill Health calculation for TalentScope.ai.

Guarantees:
1. Categorical status and a deterministic numeric score for a single eligible series.
2. Evaluates each signal family (`demand`, `interest`, `adoption`) separately using
   eligible share series (`metric == "normalized_share"`) across >= 4 consecutive,
   completed monthly periods.
3. Uses explicit relative Theil-Sen slope per month thresholds:
   - rising: relative slope > +0.015 per month (+1.5%/mo)
   - falling: relative slope < -0.015 per month (-1.5%/mo)
   - flat: abs(relative slope) <= 0.015 per month
4. Score v1 is `round(clamp(50 + 50 * relative_slope / 0.03, 0, 100), 2)`, with a
   single relative-momentum component at weight 1.0; separate series are never combined.
5. Raw counts without valid denominators are ineligible for Skill Health direction
   and reported transparently in the component table.
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.trend import _consecutive_periods, _month_index, _period_is_complete, theil_sen_slope

SkillHealthCategory = Literal[
    "strengthening", "weakening", "stable", "mixed", "insufficient_data"
]
ComponentDirection = Literal[
    "rising", "falling", "flat", "insufficient_data", "ineligible_raw_count"
]

# Explicit relative monthly slope threshold (1.5% of median series share per month)
RELATIVE_SLOPE_THRESHOLD_PER_MONTH = 0.015
ABSOLUTE_SLOPE_TOLERANCE = 1e-6
SKILL_HEALTH_SCORE_VERSION = "skill-health-relative-momentum-v1"
SKILL_HEALTH_SCORE_SATURATION_PER_MONTH = 0.03


class SkillHealthComponentRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_family: Literal["demand", "interest", "adoption"]
    provider: str
    metric: str
    direction: ComponentDirection
    is_eligible_share: bool
    periods_evaluated: int
    first_period: str | None = None
    latest_period: str | None = None
    first_value: float | None = None
    latest_value: float | None = None
    theil_sen_slope_per_month: float | None = None
    relative_slope_per_month: float | None = None
    whole_window_change: float | None = None
    whole_window_pct_change: float | None = None
    latest_mom_change: float | None = None
    latest_mom_pct_change: float | None = None
    health_score: float | None = None
    score_weight: float = 1.0
    periods_used: list[str] = Field(default_factory=list)
    unit: str | None = None
    denominator_unit: str | None = None
    series_id: str | None = None
    panel_version: str | None = None
    scope: str | None = None
    location: str | None = None
    query_id: str | None = None
    data_origin: str | None = None
    history_type: str | None = None
    reliability_assumptions: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    fetch_run_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reason: str = ""


class SkillHealthResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_skill_id: str | None
    canonical_name: str
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    health_category: SkillHealthCategory
    score: float | None = None
    score_status: Literal["ready", "ambiguous_series", "insufficient_data"] = "insufficient_data"
    score_unit: str = "score_0_100"
    score_method_version: str = SKILL_HEALTH_SCORE_VERSION
    score_formula: str = "round(clamp(50 + 50 * relative_slope_per_month / 0.03, 0, 100), 2)"
    score_weights: dict[str, float] = Field(default_factory=lambda: {"relative_momentum": 1.0})
    score_range: tuple[float, float] = (0.0, 100.0)
    component_table: list[SkillHealthComponentRow] = Field(default_factory=list)
    eligible_family_count: int = 0
    ready_families: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "relative_slope_per_month": RELATIVE_SLOPE_THRESHOLD_PER_MONTH,
            "min_consecutive_periods": 4.0,
        }
    )
    explanation: str = ""
    limitations: list[str] = Field(default_factory=list)
    calculation_version: str = SKILL_HEALTH_SCORE_VERSION


def evaluate_skill_health(
    signals: Sequence[Any],
    *,
    canonical_skill_id: str | None = None,
    canonical_name: str = "",
    min_periods: int = 4,
    relative_slope_threshold: float = RELATIVE_SLOPE_THRESHOLD_PER_MONTH,
    history_complete: bool = True,
) -> SkillHealthResult:
    """Compute categorical Skill Health from aggregated market signals for a single skill."""
    skill_signals = [
        s for s in signals
        if (
            getattr(s, "canonical_skill_id", None) == canonical_skill_id
            if canonical_skill_id else
            bool(canonical_name) and getattr(s, "canonical_name", "").casefold() == canonical_name.casefold()
        )
    ] if (canonical_skill_id or canonical_name) else list(signals)

    if not history_complete:
        return SkillHealthResult(
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            status="unavailable",
            health_category="insufficient_data",
            score_status="insufficient_data",
            explanation="Skill Health is unavailable because bounded observation retrieval may have truncated history.",
            limitations=["Incomplete observation history cannot support a Skill Health assessment."],
        )
    if not skill_signals:
        return SkillHealthResult(
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name or "Unknown",
            status="insufficient_data",
            health_category="insufficient_data",
            component_table=[],
            eligible_family_count=0,
            ready_families=[],
            explanation="No validated market signal series available to evaluate categorical Skill Health.",
            limitations=["Requires at least one eligible normalized share series with >= 4 consecutive monthly periods."],
        )

    resolved_name = canonical_name or getattr(skill_signals[0], "canonical_name", "Unknown")
    resolved_id = canonical_skill_id or getattr(skill_signals[0], "canonical_skill_id", None)

    # Preserve every source, unit, geography, query, and history series independently.
    by_family_source: dict[tuple[Any, ...], list[Any]] = {}
    for sig in skill_signals:
        st = getattr(sig, "signal_type", "")
        if st not in ("demand", "interest", "adoption"):
            continue
        key = (
            st,
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
        )
        by_family_source.setdefault(key, []).append(sig)

    component_rows: list[SkillHealthComponentRow] = []
    family_directions: dict[str, ComponentDirection] = {}
    eligible_series_scores: list[float] = []

    for key, fam_signals in sorted(by_family_source.items(), key=lambda item: tuple(str(value) for value in item[0])):
        family, provider = key[:2]
        by_period: dict[str, Any] = {}
        for s in sorted(fam_signals, key=lambda x: _month_index(x.period)):
            by_period[s.period] = s
        periods = sorted(by_period.keys(), key=_month_index)
        ordered = [by_period[p] for p in periods]
        latest_sig = ordered[-1]
        first_sig = ordered[0]
        metric = getattr(latest_sig, "metric", "raw_count")

        is_share = (
            metric == "normalized_share"
            and bool(getattr(latest_sig, "unit", None))
            and bool(getattr(latest_sig, "denominator_unit", None))
            and all(
                getattr(s, "normalized_value", None) is not None
                and getattr(s, "denominator", None) is not None
                and math.isfinite(float(s.normalized_value))
                and float(s.normalized_value) >= 0
                and float(s.normalized_value) <= 1
                and math.isfinite(float(s.denominator))
                and float(s.denominator) > 0
                and getattr(s, "data_state", None) in {"ready", "fresh"}
                and getattr(s, "data_origin", None) == "real"
                for s in ordered
            )
        )

        obs_ids: set[str] = set()
        run_ids: set[str] = set()
        warnings: list[str] = []
        for s in ordered:
            obs_ids.update(getattr(s, "observation_ids", []) or [])
            run_ids.update(getattr(s, "fetch_run_ids", []) or [])
            for w in getattr(s, "warnings", []) or []:
                if w not in warnings:
                    warnings.append(w)
        series_details = {
            "periods_used": periods,
            "unit": getattr(latest_sig, "unit", None),
            "denominator_unit": getattr(latest_sig, "denominator_unit", None),
            "panel_version": getattr(latest_sig, "panel_version", None),
            "scope": getattr(latest_sig, "scope", None),
            "location": getattr(latest_sig, "location", None),
            "query_id": getattr(latest_sig, "query_id", None),
            "data_origin": getattr(latest_sig, "data_origin", None),
            "history_type": getattr(latest_sig, "history_type", None),
        }
        reliability_assumptions = [
            "Provider denominators are assumed valid, positive, and specific to this series.",
            "Raw counts are not eligible for the numeric Skill Health score.",
            "The score is a deterministic measurement summary, not an outcome-calibrated probability.",
        ]

        def _val(s: Any) -> float:
            if is_share and getattr(s, "normalized_value", None) is not None:
                return float(s.normalized_value)
            return float(s.raw_value)

        if metric == "normalized_share" and not is_share:
            warnings.append("normalized share or denominator failed validation")
            component_rows.append(SkillHealthComponentRow(
                signal_family=family,  # type: ignore[arg-type]
                provider=provider,
                metric=metric,
                direction="insufficient_data",
                is_eligible_share=False,
                periods_evaluated=len(periods),
                first_period=first_sig.period,
                latest_period=latest_sig.period,
                **series_details,
                reliability_assumptions=reliability_assumptions,
                series_id=getattr(latest_sig, "series_id", None),
                observation_ids=sorted(obs_ids),
                fetch_run_ids=sorted(run_ids),
                warnings=warnings,
                reason=(
                    "Normalized share requires finite values in [0, 1], positive finite denominators, "
                    "ready real-data observations, and explicit units."
                ),
            ))
            continue

        values = [_val(s) for s in ordered]
        first_val = values[0]
        latest_val = values[-1]
        ww_change = round(latest_val - first_val, 6) if len(values) >= 2 else None
        ww_pct = round(((latest_val - first_val) / abs(first_val)) * 100, 2) if (len(values) >= 2 and first_val != 0) else None

        mom_change = None
        mom_pct = None
        if len(values) >= 2 and _month_index(periods[-1]) - _month_index(periods[-2]) == 1:
            prev_val = values[-2]
            mom_change = round(latest_val - prev_val, 6)
            if prev_val != 0:
                mom_pct = round(((latest_val - prev_val) / abs(prev_val)) * 100, 2)

        if metric != "normalized_share":
            if "raw count; platform volume changes may affect it" not in warnings:
                warnings.append("raw count; platform volume changes may affect it")
            slope_val = round(theil_sen_slope(values), 6) if len(values) >= min_periods and _consecutive_periods(periods) else None
            component_rows.append(SkillHealthComponentRow(
                signal_family=family,  # type: ignore[arg-type]
                provider=provider,
                metric=metric,
                direction="ineligible_raw_count",
                is_eligible_share=False,
                periods_evaluated=len(periods),
                first_period=first_sig.period,
                latest_period=latest_sig.period,
                first_value=first_val,
                latest_value=latest_val,
                theil_sen_slope_per_month=slope_val,
                relative_slope_per_month=None,
                whole_window_change=ww_change,
                whole_window_pct_change=ww_pct,
                latest_mom_change=mom_change,
                latest_mom_pct_change=mom_pct,
                **series_details,
                reliability_assumptions=reliability_assumptions,
                series_id=getattr(latest_sig, "series_id", None),
                observation_ids=sorted(obs_ids),
                fetch_run_ids=sorted(run_ids),
                warnings=warnings,
                reason="Raw count series without source-specific denominator cannot determine Skill Health category.",
            ))
            continue

        monthly_periods = all(re.fullmatch(r"\d{4}-\d{2}", period) for period in periods)
        latest_period_complete = bool(periods and _period_is_complete(periods[-1]))
        if (
            len(periods) < min_periods
            or not monthly_periods
            or not _consecutive_periods(periods)
            or not latest_period_complete
        ):
            reason = (
                f"Requires >= {min_periods} consecutive periods; found {len(periods)}."
                if len(periods) < min_periods
                else "Skill Health scoring requires monthly periods."
                if not monthly_periods
                else "Non-consecutive periods detected in share series."
                if not _consecutive_periods(periods)
                else "The latest observation month is not yet complete."
            )
            component_rows.append(SkillHealthComponentRow(
                signal_family=family,  # type: ignore[arg-type]
                provider=provider,
                metric=metric,
                direction="insufficient_data",
                is_eligible_share=True,
                periods_evaluated=len(periods),
                first_period=first_sig.period,
                latest_period=latest_sig.period,
                first_value=first_val,
                latest_value=latest_val,
                theil_sen_slope_per_month=None,
                relative_slope_per_month=None,
                whole_window_change=ww_change,
                whole_window_pct_change=ww_pct,
                latest_mom_change=mom_change,
                latest_mom_pct_change=mom_pct,
                **series_details,
                reliability_assumptions=reliability_assumptions,
                series_id=getattr(latest_sig, "series_id", None),
                observation_ids=sorted(obs_ids),
                fetch_run_ids=sorted(run_ids),
                warnings=warnings,
                reason=reason,
            ))
            continue

        slope_val = round(theil_sen_slope(values), 6)
        median_val = statistics.median(values)
        rel_slope = round(slope_val / abs(median_val), 6) if median_val != 0 else 0.0

        if rel_slope > relative_slope_threshold and slope_val > ABSOLUTE_SLOPE_TOLERANCE:
            direction: ComponentDirection = "rising"
        elif rel_slope < -relative_slope_threshold and slope_val < -ABSOLUTE_SLOPE_TOLERANCE:
            direction = "falling"
        else:
            direction = "flat"

        # Record family direction (prefer series with most periods if multiple providers exist in same family)
        if family not in family_directions:
            family_directions[family] = direction

        has_score_identity = bool(
            resolved_id
            and getattr(latest_sig, "series_id", None)
            and getattr(latest_sig, "unit", None)
            and getattr(latest_sig, "denominator_unit", None)
            and median_val > 0
        )
        health_score = (
            round(
                min(
                    100.0,
                    max(
                        0.0,
                        50.0 + 50.0 * rel_slope / SKILL_HEALTH_SCORE_SATURATION_PER_MONTH,
                    ),
                ),
                2,
            )
            if has_score_identity else None
        )
        if health_score is not None:
            eligible_series_scores.append(health_score)
        component_rows.append(SkillHealthComponentRow(
            signal_family=family,  # type: ignore[arg-type]
            provider=provider,
            metric=metric,
            direction=direction,
            is_eligible_share=True,
            periods_evaluated=len(periods),
            first_period=first_sig.period,
            latest_period=latest_sig.period,
            first_value=first_val,
            latest_value=latest_val,
            theil_sen_slope_per_month=slope_val,
            relative_slope_per_month=rel_slope,
            whole_window_change=ww_change,
            whole_window_pct_change=ww_pct,
            latest_mom_change=mom_change,
            latest_mom_pct_change=mom_pct,
            health_score=health_score,
            **series_details,
            reliability_assumptions=[
                *reliability_assumptions,
                "Theil-Sen relative monthly slope is the only scored input; score saturates at +/-3% monthly relative change.",
            ],
            series_id=getattr(latest_sig, "series_id", None),
            observation_ids=sorted(obs_ids),
            fetch_run_ids=sorted(run_ids),
            warnings=warnings,
            reason=f"Evaluated on {len(periods)} consecutive share observations (relative slope {rel_slope:+.4f}/mo).",
        ))

    ready_families = sorted(family_directions.keys())
    directions = [family_directions[f] for f in ready_families]
    limitations: list[str] = []

    if not directions:
        health_category: SkillHealthCategory = "insufficient_data"
        status: Literal["ready", "partial", "insufficient_data"] = "insufficient_data"
        explanation = (
            f"Skill Health for {resolved_name} is insufficient_data because no signal family has an eligible "
            f"normalized share series with at least {min_periods} consecutive monthly periods."
        )
        limitations.append("At least one normalized share series with >= 4 consecutive months is required.")
    else:
        has_rising = "rising" in directions
        has_falling = "falling" in directions
        if has_rising and has_falling:
            health_category = "mixed"
        elif has_rising and not has_falling:
            health_category = "strengthening"
        elif has_falling and not has_rising:
            health_category = "weakening"
        else:
            health_category = "stable"

        status = "ready" if len(ready_families) >= 2 else "partial"
        if len(ready_families) < 2:
            limitations.append(
                f"Only {len(ready_families)} signal family ({', '.join(ready_families)}) has eligible share history; "
                "cross-family agreement requires at least 2 signal families."
            )
        family_summary = ", ".join(f"{f}={family_directions[f]}" for f in ready_families)
        explanation = (
            f"Categorical Skill Health for {resolved_name} is '{health_category}' "
            f"based on {len(ready_families)} eligible signal family series ({family_summary})."
        )

    score = eligible_series_scores[0] if len(eligible_series_scores) == 1 else None
    if len(eligible_series_scores) == 1:
        score_status: Literal["ready", "ambiguous_series", "insufficient_data"] = "ready"
        scored_row = next(row for row in component_rows if row.health_score is not None)
        assert scored_row.relative_slope_per_month is not None
        explanation += (
            f" Score {score:.2f}/100 is reproducible from the reported relative monthly slope "
            f"{scored_row.relative_slope_per_month:+.6f}/mo using "
            "round(clamp(50 + 50 * relative_slope / 0.03, 0, 100), 2); relative momentum has weight 1.0."
        )
    elif len(eligible_series_scores) > 1:
        score_status = "ambiguous_series"
        health_category = "insufficient_data"
        status = "partial"
        explanation = (
            f"Source-specific Skill Health components for {resolved_name} are available, but a single overall "
            "category or score is withheld because multiple non-interchangeable series matched."
        )
        limitations.append(
            "Eligible series are returned independently; no overall category or score combines different sources, signals, or units."
        )
    else:
        score_status = "insufficient_data"
        limitations.append(
            "A numeric score requires a canonical skill ID, stable series identity, positive normalized share, and sufficient consecutive monthly coverage."
        )

    return SkillHealthResult(
        canonical_skill_id=resolved_id,
        canonical_name=resolved_name,
        status=status,
        health_category=health_category,
        score=score,
        score_status=score_status,
        component_table=component_rows,
        eligible_family_count=len(ready_families),
        ready_families=ready_families,
        thresholds={
            "relative_slope_per_month": relative_slope_threshold,
            "min_consecutive_periods": float(min_periods),
        },
        explanation=explanation,
        limitations=limitations,
    )

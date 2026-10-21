import calendar
import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from app.analytics.skill_normalization import normalize_skill, skill_category
from app.analytics.observation_period import is_completed_month, normalize_month_period
from app.analytics.series_validation import comparable_series_key
from app.models.skill_intelligence import MarketObservation, SkillTrendPoint

CALCULATION_VERSION = "demand-theil-sen-v4-backfill-consistent"
SMOOTHING_ALPHA = 0.5
STABLE_GROWTH_THRESHOLD_PCT_PER_MONTH = 2.0


def _period_index(period: str) -> int:
    quarter = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if quarter:
        return int(quarter.group(1)) * 4 + int(quarter.group(2)) - 1
    canonical = normalize_month_period(period)
    if canonical is None:
        raise ValueError("Observation period is required.")
    year, month = (int(part) for part in canonical.split("-", maxsplit=1))
    return year * 12 + month


def _month_index(period: str) -> int:
    return _period_index(period)


def _consecutive_periods(periods: list[str]) -> bool:
    if not periods:
        return False
    is_quarterly = all(re.fullmatch(r"\d{4}-Q[1-4]", period) for period in periods)
    if any(bool(re.fullmatch(r"\d{4}-Q[1-4]", period)) != is_quarterly for period in periods):
        return False
    indices = [_period_index(period) for period in periods]
    return all(right - left == 1 for left, right in zip(indices, indices[1:]))


def _period_is_complete(period: str, as_of: date | datetime | None = None) -> bool:
    if re.fullmatch(r"\d{4}-Q[1-4]", period):
        year, quarter = int(period[:4]), int(period[-1])
        end_month = quarter * 3
        period_end = date(year, end_month, calendar.monthrange(year, end_month)[1])
        reference = as_of.date() if isinstance(as_of, datetime) else as_of or datetime.now(timezone.utc).date()
        return period_end < reference
    return is_completed_month(period, as_of=as_of)


def _period_grain(period: str) -> str:
    return "quarter" if re.fullmatch(r"\d{4}-Q[1-4]", period) else "month"


def _value_unit(metric: str, source_unit: str | None, normalized_value: float | None) -> str | None:
    if metric == "normalized_share" and normalized_value is not None:
        return "share"
    if not source_unit:
        return None
    return re.sub(r"\s+per\s+(month|quarter|year)$", "", source_unit.strip(), flags=re.IGNORECASE)


def theil_sen_slope(values: list[float]) -> float:
    if len(values) < 2:
        raise ValueError("At least two points are required to calculate a slope.")
    slopes = [
        (values[right] - values[left]) / (right - left)
        for left in range(len(values) - 1)
        for right in range(left + 1, len(values))
    ]
    return statistics.median(slopes)


def _confidence(
    *,
    period_count: int,
    posting_count: int,
    observed_at: datetime,
    values: list[float],
    source_slopes: list[float],
    now: datetime,
) -> float:
    coverage = min(1.0, period_count / 6)
    sample = min(1.0, posting_count / 100)
    age_days = max(0.0, (now - observed_at).total_seconds() / 86400)
    freshness = max(0.0, 1.0 - age_days / 30)
    slope = theil_sen_slope(values)
    residuals = [abs(value - (values[0] + slope * index)) for index, value in enumerate(values)]
    mean_value = statistics.mean(values) or SMOOTHING_ALPHA
    fit = 1.0 / (1.0 + statistics.mean(residuals) / mean_value)
    if len(source_slopes) > 1:
        direction = 1 if slope > 0 else -1 if slope < 0 else 0
        agreement = sum(
            1 for source_slope in source_slopes
            if (1 if source_slope > 0 else -1 if source_slope < 0 else 0) == direction
        ) / len(source_slopes)
    else:
        agreement = 0.5
    score = (
        0.30 * coverage
        + 0.25 * sample
        + 0.20 * freshness
        + 0.15 * fit
        + 0.10 * agreement
    )
    return round(max(0.0, min(1.0, score)), 3)


def _source_demand_shares(
    observations: list[MarketObservation],
) -> tuple[
    dict[tuple[str, str, tuple[Any, ...], str | None], dict[str, float]],
    dict[tuple[tuple[Any, ...], str], int],
]:
    job_ids: dict[tuple[tuple[Any, ...], str], set[str]] = defaultdict(set)
    skill_jobs: dict[tuple[tuple[Any, ...], str, str, str | None], set[str]] = defaultdict(set)
    skill_series_by_period: dict[tuple[tuple[Any, ...], str], set[tuple[str, str | None]]] = defaultdict(set)
    for index, observation in enumerate(observations):
        period = observation.period or observation.observed_at.strftime("%Y-%m")
        posting_id = observation.posting_id or str(observation.metadata.get("posting_id") or observation.id or index)
        skill = normalize_skill(observation.skill)
        identity = (
            observation.source.casefold().strip(),
            observation.scope,
            observation.location.strip().casefold() if observation.location else None,
            observation.query_id.strip() if observation.query_id else None,
            observation.panel_version.strip() if observation.panel_version else None,
            observation.unit.strip().casefold() if observation.unit else None,
            observation.denominator_unit.strip().casefold() if observation.denominator_unit else None,
            observation.extractor_version.strip() if observation.extractor_version else None,
            observation.data_origin,
            observation.history_type,
        )
        series_id = observation.series_id.strip() if observation.series_id else None
        job_ids[(identity, period)].add(posting_id)
        skill_jobs[(identity, period, skill, series_id)].add(posting_id)
        skill_series_by_period[(identity, period)].add((skill, series_id))

    shares: dict[tuple[str, str, tuple[Any, ...], str | None], dict[str, float]] = defaultdict(dict)
    denominators: dict[tuple[tuple[Any, ...], str], int] = {}
    for (identity, period), postings in job_ids.items():
        skill_series = skill_series_by_period[(identity, period)]
        denominator = sum(
            len(skill_jobs[(identity, period, skill, series_id)])
            for skill, series_id in skill_series
        )
        denominators[(identity, period)] = len(postings)
        if denominator == 0:
            continue
        smoothed_total = denominator + SMOOTHING_ALPHA * max(1, len(skill_series))
        for skill, series_id in skill_series:
            count = len(skill_jobs[(identity, period, skill, series_id)])
            shares[(skill, identity[0], identity, series_id)][period] = (
                count + SMOOTHING_ALPHA
            ) / smoothed_total
    return shares, denominators


# History types accepted for demand trend calculation.
# Must match the eligibility gate in forecast_signal_series() in forecasting.py to prevent
# a situation where observations pass forecasting but are silently dropped from trends.
_DEMAND_HISTORY_TYPES = frozenset({"platform_collected", "backfill", "backfilled"})


def compatible_demand_observations(
    observations: list[MarketObservation],
) -> list[MarketObservation]:
    """Keep eligible demand records; downstream groups each compatible series independently.

    Accepted history types mirror the forecasting gate in ``forecasting.py``::

        history_type in {"platform_collected", "backfill", "backfilled"}

    ``"backfill"`` covers controlled historical ingestion (e.g. Stack Exchange monthly counts,
    or a future job-board historical API); ``"backfilled"`` is the post-migration alias.
    ``"platform_collected"`` covers live API collection runs from JSearch, Adzuna, and GitHub.

    All three filters — signal_type, history_type, and data_origin — must pass.
    Synthetic, test, and demo observations are always excluded (data_origin == "real" required).
    """
    return [
        item for item in observations
        if item.signal_type == "demand"
        and item.history_type in _DEMAND_HISTORY_TYPES
        and item.data_origin == "real"
    ]


def calculate_skill_trends(
    observations: list[MarketObservation],
    *,
    min_periods: int = 4,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Calculate comparable, source-specific demand trends without filling missing periods."""
    now = now or datetime.now(timezone.utc)
    observations = compatible_demand_observations(observations)
    source_shares, denominators = _source_demand_shares(observations)
    source_observations: dict[tuple[str, str, tuple[Any, ...], str | None], list[MarketObservation]] = defaultdict(list)
    for item in observations:
        identity = (
            item.source.casefold().strip(),
            item.scope,
            item.location.strip().casefold() if item.location else None,
            item.query_id.strip() if item.query_id else None,
            item.panel_version.strip() if item.panel_version else None,
            item.unit.strip().casefold() if item.unit else None,
            item.denominator_unit.strip().casefold() if item.denominator_unit else None,
            item.extractor_version.strip() if item.extractor_version else None,
            item.data_origin,
            item.history_type,
        )
        series_id = item.series_id.strip() if item.series_id else None
        source_observations[(normalize_skill(item.skill), item.source.casefold(), identity, series_id)].append(item)

    results: list[dict[str, Any]] = []
    for (skill, source, identity, series_id), by_period in source_shares.items():
        completed_periods = [
            period for period in by_period
            if _period_is_complete(period, as_of=now)
        ]
        incomplete_periods = [period for period in by_period if period not in completed_periods]
        periods = sorted(
            completed_periods or incomplete_periods[-1:],
            key=_period_index,
        )
        if not periods:
            continue
        values = [by_period[period] for period in periods]
        points = [
            SkillTrendPoint(period=period, value=round(value, 6)).model_dump()
            for period, value in zip(periods, values)
        ]
        observations_for_series = source_observations[(skill, source, identity, series_id)]
        used_observations = [
            item for item in observations_for_series
            if (item.period or item.observed_at.strftime("%Y-%m")) in periods
        ]
        last_observed_at = max((item.observed_at for item in used_observations), default=None)
        canonical_id = next((item.skill_id for item in used_observations if item.skill_id), None)
        period_job_counts = [
            denominators.get((identity, period), 0)
            for period in periods
        ]
        enough_history = (
            len(periods) >= min_periods
            and _consecutive_periods(periods)
            and bool(series_id)
            and bool(identity[5])
            and bool(canonical_id)
        )
        slope = theil_sen_slope(values) if enough_history else None
        trend_label = "Insufficient Data"
        growth_pct = None
        confidence = None
        ranking_score = None
        if enough_history and last_observed_at is not None and slope is not None:
            baseline = statistics.median(values[: max(1, len(values) // 2)])
            growth_pct = round(100 * slope * (len(values) - 1) / max(baseline, 0.005), 2)
            monthly_growth = growth_pct / max(1, len(values) - 1)
            if monthly_growth > STABLE_GROWTH_THRESHOLD_PCT_PER_MONTH:
                trend_label = "Growing"
            elif monthly_growth < -STABLE_GROWTH_THRESHOLD_PCT_PER_MONTH:
                trend_label = "Declining"
            else:
                trend_label = "Stable"
            confidence = _confidence(
                period_count=len(periods),
                posting_count=max(period_job_counts, default=0),
                observed_at=last_observed_at,
                values=values,
                source_slopes=[],
                now=now,
            )
            ranking_score = round(
                (growth_pct * 0.01) + (values[-1] * 10) + (confidence * 0.5),
                6,
            )

        comparable_inputs = bool(series_id and identity[5] and canonical_id)
        previous_value = (
            values[-2]
            if comparable_inputs and len(values) >= 2 and _consecutive_periods(periods[-2:])
            else None
        )
        velocity = round(values[-1] - previous_value, 6) if previous_value is not None else None
        growth_latest = (
            round((velocity / abs(previous_value)) * 100, 2)
            if velocity is not None and previous_value not in (None, 0)
            else None
        )
        reasons = []
        if len(periods) < min_periods:
            reasons.append(f"Requires >= {min_periods} completed periods; only {len(periods)} available")
        if len(periods) >= 2 and not _consecutive_periods(periods):
            reasons.append("Periods are not strictly consecutive; missing period gap detected")
        if not series_id:
            reasons.append("Stable series identity is unavailable")
        if not identity[5]:
            reasons.append("Explicit observation unit is unavailable")
        if not canonical_id:
            reasons.append("Canonical skill identity is unavailable")
        if incomplete_periods and not completed_periods:
            reasons.append("Only an incomplete current period is available")
        readiness_state = "ready_for_trend" if enough_history else (
            "unavailable" if not series_id or not identity[5] else "insufficient_history"
        )
        scope = identity[1]
        location = identity[2]
        query_id = identity[3]
        panel_version = identity[4]
        unit = identity[5]
        data_origin = identity[8]
        history_type = identity[9]
        result_unit = "share"
        grain = "month"
        results.append({
            "skill": skill,
            "canonical_skill_id": canonical_id,
            "category": skill_category(skill),
            "series": points,
            "growth_pct": growth_pct,
            "trend": trend_label,
            "confidence": confidence,
            "demand_share": values[-1],
            "raw_value": len({
                item.posting_id or item.id or f"record-{index}"
                for index, item in enumerate(used_observations)
                if (item.period or item.observed_at.strftime("%Y-%m")) == periods[-1]
            }),
            "denominator": denominators.get((identity, periods[-1]), 0),
            "ranking_score": ranking_score,
            "source": source,
            "series_id": series_id,
            "data_origin": data_origin,
            "unit": result_unit,
            "velocity": velocity,
            "velocity_unit": f"{result_unit} per {grain}",
            "latest_period_change": velocity,
            "latest_period_change_pct": growth_latest,
            "whole_window_change": round(values[-1] - values[0], 6) if comparable_inputs and len(values) >= 2 else None,
            "whole_window_pct_change": (
                round((values[-1] - values[0]) / abs(values[0]) * 100, 2)
                if comparable_inputs and len(values) >= 2 and values[0] != 0 else None
            ),
            "slope": round(slope, 6) if slope is not None else None,
            "slope_unit": f"{result_unit} per {grain}",
            "period_grain": grain,
            "readiness_state": readiness_state,
            "data_state": (
                "ready" if enough_history
                else "unavailable" if not comparable_inputs
                else "insufficient_data"
            ),
            "blocking_reasons": reasons,
            "periods_used": periods,
            "latest_period": periods[-1],
            "previous_period": periods[-2] if previous_value is not None else None,
            "series_provenance": {
                "source": source,
                "signal_type": "demand",
                "history_type": history_type,
                "series_id": series_id,
                "query_id": query_id,
                "panel_version": panel_version,
                "scope": scope,
                "location": location,
                "unit": unit,
                "denominator_unit": identity[6],
                "extractor_version": identity[7],
                "data_origin": data_origin,
                "observation_count": len(used_observations),
                "period_count": len(points),
                "posting_counts_by_period": dict(zip(periods, period_job_counts)),
                "observation_ids": sorted({item.id for item in used_observations if item.id}),
                "fetch_run_ids": sorted({item.fetch_run_id for item in used_observations if item.fetch_run_id}),
                "collected_at": last_observed_at.isoformat() if last_observed_at else None,
                "periods_used": periods,
            },
        })
    return sorted(
        results,
        key=lambda item: (
            item["source"], item["skill"], item.get("series_id") or "",
            item["series_provenance"].get("scope") or "",
            item["series_provenance"].get("location") or "",
        ),
    )


def _format_trend_explanation(
    *,
    source: str,
    signal_type: str,
    canonical_name: str,
    trend_dir: str,
    slope: float | None,
    velocity: float | None,
    growth_pct: float | None,
    whole_window_change: float | None = None,
    whole_window_pct_change: float | None = None,
    metric: str,
    data_state: str,
    ordered_periods: list[str],
    ordered_values: list[float],
    total_obs_count: int,
    all_obs_ids: list[str],
    all_run_ids: list[str],
    series_id: str | None,
    unit: str | None,
    velocity_unit: str | None,
    slope_unit: str | None,
    period_grain: str,
    scope: str | None,
    location: str | None,
    query_id: str | None,
    calculation_version: str,
    blocking_reasons: list[str],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    signal_label = (
        "developer interest" if signal_type == "interest"
        else "job demand" if signal_type == "demand"
        else "code adoption" if signal_type == "adoption"
        else f"{signal_type} signal"
    )

    if data_state == "ready" and slope is not None:
        first_p, last_p = ordered_periods[0], ordered_periods[-1]
        first_val, last_val = ordered_values[0], ordered_values[-1]
        change_dir = "increased" if last_val > first_val else "decreased" if last_val < first_val else "remained constant"
        vel_text = f"{velocity:+g} {velocity_unit}" if velocity is not None else "unavailable"
        slope_text = f"{slope:+.6f} {slope_unit}" if slope is not None else "unavailable"
        ww_text = f"{whole_window_change:+g}" if whole_window_change is not None else "unavailable"
        ww_pct_text = f" ({whole_window_pct_change:+.2f}%)" if whole_window_pct_change is not None else ""
        mom_pct_text = f" ({growth_pct:+.2f}%)" if growth_pct is not None else ""
        period_change_name = "month-over-month" if period_grain == "month" else "quarter-over-quarter"
        what_changed = (
            f"Overall trend is {trend_dir} (Theil-Sen slope {slope_text} across {len(ordered_periods)} periods from {first_p} to {last_p}). "
            f"Whole-window {metric.replace('_', ' ')} {change_dir} from {first_val} to {last_val} (change {ww_text}{ww_pct_text}). "
            f"Latest {period_change_name} change between {ordered_periods[-2]} and {last_p} is {vel_text}{mom_pct_text}."
        )
        if warnings:
            what_changed += f" Note: {'; '.join(warnings)}."
        why_it_matters = (
            f"A robust Theil-Sen slope of {slope_text} indicates an overall {trend_dir.lower()} direction "
            f"in {canonical_name} {signal_label} on {source} across the full window, distinct from latest-period movement."
        )
    else:
        what_changed = (
            f"Series has {len(ordered_periods)} period(s) ({', '.join(ordered_periods)}). "
            f"Historical trend calculation is unavailable because at least 4 consecutive valid periods are required."
        )
        reasons_text = "; ".join(blocking_reasons) if blocking_reasons else f"Insufficient historical depth ({len(ordered_periods)}/4 periods)."
        why_it_matters = (
            f"Trend and velocity calculation is gated to prevent false signals. Reason: {reasons_text}."
        )

    return {
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "overall_direction": trend_dir,
        "theil_sen_slope_per_month": slope,
        "whole_window_change": whole_window_change,
        "whole_window_pct_change": whole_window_pct_change,
        "latest_mom_change": velocity,
        "latest_mom_pct_change": growth_pct,
        "warnings": warnings or [],
        "evidence": {
            "provider": source,
            "signal_type": signal_type,
            "periods_used": ordered_periods,
            "observation_count": total_obs_count,
            "observation_ids": sorted(all_obs_ids),
            "fetch_run_ids": sorted(all_run_ids),
            "series_id": series_id,
            "unit": unit,
            "velocity_unit": velocity_unit,
            "slope_unit": slope_unit,
            "period_grain": period_grain,
            "scope": scope,
            "location": location,
            "query_id": query_id,
            "calculation_version": calculation_version,
            "blocking_reasons": blocking_reasons,
        },
    }


G14_CALCULATION_VERSION = "trend-velocity-theil-sen-v2-comparable-units"


def calculate_trend_and_velocity(
    signals: list[Any],
    *,
    min_periods: int = 4,
    slope_tolerance: float = 1e-6,
    quality_reports: list[Any] | None = None,
    readiness_reports: list[Any] | None = None,
    as_of: date | datetime | None = None,
) -> list[Any]:
    """Calculate deterministic trend, Theil-Sen slope, and velocity from G1.3 AggregatedMarketSignal records.

    Partitioning:
        Series are partitioned by source, signal family, canonical skill, metric,
        unit, panel/query/series identity, geography, and history/data origin.
        Different sources or signal families are NEVER merged into one trend series.

    Hard Gates:
        - G1.8 Quality Gate: quality_state must be 'valid'.
        - G1.9 Readiness Gate: is_trend_ready must be True with >= 4 consecutive periods.
        - Minimum History: requires >= min_periods (default 4) valid consecutive periods.
        - Configuration drift or missing periods block trend calculation.
    """
    from app.models.market_signal import SkillTrendVelocityResult

    if not signals:
        return []

    # Match gates to the same comparable dimensions as each trend partition.
    quality_map: dict[tuple[object, ...], Any] = {}
    quality_by_base: dict[tuple[str, str, str | None], list[Any]] = defaultdict(list)
    if quality_reports:
        for qr in quality_reports:
            base_key = (qr.provider.casefold().strip(), qr.signal_type.strip(), qr.canonical_skill_id)
            quality_by_base[base_key].append(qr)
            key = comparable_series_key(
                source=qr.provider,
                signal_type=qr.signal_type,
                canonical_skill_id=qr.canonical_skill_id,
                unit=qr.unit,
                denominator_unit=qr.denominator_unit,
                scope=qr.scope,
                location=qr.location,
                query_id=qr.query_id,
                panel_version=qr.panel_version,
                data_origin=qr.data_origin,
                history_type=qr.history_type,
                extractor_version=qr.extractor_version,
            )
            quality_map[key] = qr

    readiness_map: dict[tuple[object, ...], Any] = {}
    readiness_by_base: dict[tuple[str, str, str | None], list[Any]] = defaultdict(list)
    if readiness_reports:
        for rr in readiness_reports:
            base_key = (rr.provider.casefold().strip(), rr.signal_type.strip(), rr.canonical_skill_id)
            readiness_by_base[base_key].append(rr)
            key = comparable_series_key(
                source=rr.provider,
                signal_type=rr.signal_type,
                canonical_skill_id=rr.canonical_skill_id,
                unit=rr.unit,
                denominator_unit=rr.denominator_unit,
                scope=rr.scope,
                location=rr.location,
                query_id=rr.query_id,
                panel_version=rr.panel_version,
                data_origin=rr.data_origin,
                history_type=rr.history_type,
                extractor_version=rr.extractor_version,
            )
            readiness_map[key] = rr

    # 1. Group signals by strict series partition
    groups: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
    for signal in signals:
        key = (
            signal.source.casefold().strip(),
            signal.signal_type.strip(),
            signal.canonical_skill_id,
            signal.metric,
            signal.unit.strip().casefold() if signal.unit else None,
            signal.denominator_unit.strip().casefold() if signal.denominator_unit else None,
            signal.scope,
            signal.location.strip().casefold() if signal.location else None,
            signal.query_id.strip() if signal.query_id else None,
            signal.series_id.strip() if signal.series_id else None,
            signal.panel_version.strip() if signal.panel_version else None,
            signal.data_origin,
            signal.history_type,
            signal.extractor_version.strip() if signal.extractor_version else None,
            _period_grain(signal.period),
        )
        groups[key].append(signal)

    results: list[SkillTrendVelocityResult] = []

    for key, series_signals in groups.items():
        (
            source, signal_type, canonical_skill_id, metric, source_unit, denominator_unit,
            scope, location_key, query_id, series_id_key, panel_version,
            data_origin, history_type, extractor_version, period_grain,
        ) = key
        report_key = comparable_series_key(
            source=source,
            signal_type=signal_type,
            canonical_skill_id=canonical_skill_id,
            unit=source_unit,
            denominator_unit=denominator_unit,
            scope=scope,
            location=location_key,
            query_id=query_id,
            panel_version=panel_version,
            data_origin=data_origin,
            history_type=history_type,
            extractor_version=extractor_version,
        )

        # 2. Sort chronologically by period; deduplicate periods if needed
        by_period: dict[str, Any] = {}
        # The current calendar month is an incomplete observation window. Keep it
        # in the snapshot/catalog, but never let it qualify as a completed trend period.
        completed_signals = [sig for sig in series_signals if sig.period and _period_is_complete(sig.period, as_of=as_of)]
        # Keep a lone open-period snapshot visible as an insufficient-data result;
        # it must never participate in a calculated trend.
        trend_signals = completed_signals or series_signals

        def _get_val(sig: Any) -> float:
            if sig.metric == "normalized_share" and sig.normalized_value is not None:
                return float(sig.normalized_value)
            return float(sig.raw_value)

        for sig in sorted(
            trend_signals,
            key=lambda s: (_period_index(s.period), _get_val(s), tuple(s.observation_ids)),
        ):
            by_period[sig.period] = sig

        ordered_periods = sorted(by_period.keys(), key=_period_index)
        if not ordered_periods:
            continue

        ordered_signals = [by_period[p] for p in ordered_periods]
        first_sig = ordered_signals[0]
        latest_sig = ordered_signals[-1]
        canonical_name = latest_sig.canonical_name
        metric = latest_sig.metric
        result_unit = _value_unit(metric, latest_sig.unit, latest_sig.normalized_value)
        if any(
            not item.canonical_skill_id
            or not item.series_id
            or not item.unit
            or not math.isfinite(float(item.raw_value))
            or float(item.raw_value) < 0
            or (
                item.metric == "normalized_share"
                and (
                    item.normalized_value is None
                    or item.denominator is None
                    or item.denominator <= 0
                    or not math.isfinite(float(item.normalized_value))
                    or float(item.normalized_value) < 0
                )
            )
            for item in ordered_signals
        ):
            invalid_input = True
        else:
            invalid_input = False

        first_period = first_sig.period
        first_value = _get_val(first_sig)
        latest_period = latest_sig.period
        latest_value = _get_val(latest_sig)

        previous_period: str | None = None
        previous_value: float | None = None
        velocity: float | None = None
        growth_pct: float | None = None
        whole_window_change: float | None = None
        whole_window_pct_change: float | None = None

        if not invalid_input and len(ordered_signals) >= 2:
            whole_window_change = round(latest_value - first_value, 6)
            if first_value != 0:
                whole_window_pct_change = round(((latest_value - first_value) / abs(first_value)) * 100, 2)
            prev_sig = ordered_signals[-2]
            # Verify consecutive month for velocity
            if _period_index(latest_period) - _period_index(prev_sig.period) == 1:
                previous_period = prev_sig.period
                previous_value = _get_val(prev_sig)
                velocity = round(latest_value - previous_value, 6)
                if previous_value != 0:
                    growth_pct = round(((latest_value - previous_value) / abs(previous_value)) * 100, 2)
                else:
                    growth_pct = None

        # Collect provenance and warnings across all used signals
        all_obs_ids: set[str] = set()
        all_run_ids: set[str] = set()
        total_obs_count = 0
        series_ids: set[str] = set()
        series_warnings: list[str] = []
        for s in ordered_signals:
            all_obs_ids.update(s.observation_ids)
            all_run_ids.update(s.fetch_run_ids)
            total_obs_count += s.observation_count
            if s.series_id:
                series_ids.add(s.series_id)
            for w in getattr(s, "warnings", []) or []:
                if w not in series_warnings:
                    series_warnings.append(w)
        if metric != "normalized_share" and "raw count; platform volume changes may affect it" not in series_warnings:
            series_warnings.append("raw count; platform volume changes may affect it")

        chosen_series_id = next(iter(series_ids)) if len(series_ids) == 1 else latest_sig.series_id

        # Evaluate Hard Gates
        blocking_reasons: list[str] = []
        is_blocked = False

        if invalid_input:
            is_blocked = True
            blocking_reasons.append(
                "Canonical skill, stable series identity, explicit unit, or valid metric inputs are missing"
            )

        # Configuration drift validation: if series_id changed across periods, series is incomparable
        has_config_drift = len(series_ids) > 1 or any(
            s.data_state in {"incomparable", "configuration_changed"} for s in ordered_signals
        )
        if has_config_drift:
            is_blocked = True
            blocking_reasons.append("Configuration drift or incompatible series definition detected across periods")

        # G1.8 Quality Gate
        qr = quality_map.get(report_key)
        if qr is None:
            legacy_reports = quality_by_base[(source, signal_type, canonical_skill_id)]
            if len(legacy_reports) == 1:
                legacy_report = legacy_reports[0]
                if not any((
                    legacy_report.unit,
                    legacy_report.denominator_unit,
                    legacy_report.scope,
                    legacy_report.location,
                    legacy_report.query_id,
                    legacy_report.panel_version,
                    legacy_report.data_origin,
                    legacy_report.history_type,
                    legacy_report.extractor_version,
                )):
                    qr = legacy_report
        if qr is not None and qr.quality_state != "valid":
            is_blocked = True
            blocking_reasons.append(f"G1.8 quality state is '{qr.quality_state}'")
            blocking_reasons.extend(
                issue for issue in qr.issues if issue not in blocking_reasons
            )
        if any(s.data_state in {"error", "unavailable", "incomplete", "low_coverage"} for s in ordered_signals):
            is_blocked = True
            blocking_reasons.append("Series contains observations with invalid quality states")

        # G1.9 Readiness Gate
        rr = readiness_map.get(report_key)
        if rr is None:
            legacy_reports = readiness_by_base[(source, signal_type, canonical_skill_id)]
            if len(legacy_reports) == 1:
                legacy_report = legacy_reports[0]
                if not any((
                    legacy_report.unit,
                    legacy_report.denominator_unit,
                    legacy_report.scope,
                    legacy_report.location,
                    legacy_report.query_id,
                    legacy_report.panel_version,
                    legacy_report.data_origin,
                    legacy_report.history_type,
                    legacy_report.extractor_version,
                )):
                    rr = legacy_report
        if rr is not None and not rr.is_trend_ready:
            is_blocked = True
            blocking_reasons.extend(rr.blocking_reasons or ["G1.9 analytical readiness check failed"])

        # History and Consecutiveness Check
        enough_history = (
            len(ordered_periods) >= min_periods
            and _consecutive_periods(ordered_periods)
        )
        if not enough_history:
            is_blocked = True
            if len(ordered_periods) < min_periods:
                blocking_reasons.append(f"Requires >= {min_periods} periods; only {len(ordered_periods)} available")
            if not completed_signals and any(sig.period and not _period_is_complete(sig.period, as_of=as_of) for sig in series_signals):
                blocking_reasons.append("The only available observation is in an incomplete current period.")
            if not _consecutive_periods(ordered_periods):
                blocking_reasons.append("Periods are not strictly consecutive; missing period gap detected")

        if invalid_input:
            slope_val = None
            trend_dir = "Insufficient Data"
            confidence_val = None
            data_state_val = "unavailable"
            velocity = None
            growth_pct = None
            whole_window_change = None
            whole_window_pct_change = None
            readiness_state_val = "unavailable"
        elif has_config_drift:
            slope_val = None
            trend_dir = "Insufficient Data"
            confidence_val = None
            data_state_val = "incomparable"
            velocity = None
            growth_pct = None
            whole_window_change = None
            whole_window_pct_change = None
            readiness_state_val = "blocked_configuration"
        elif is_blocked:
            slope_val = None
            trend_dir = "Insufficient Data"
            confidence_val = None
            whole_window_change = None
            whole_window_pct_change = None
            if qr and qr.quality_state != "valid":
                data_state_val = qr.quality_state
                velocity = None
                growth_pct = None
            elif any(s.data_state in {"error", "unavailable", "incomplete", "low_coverage"} for s in ordered_signals):
                data_state_val = "insufficient_data"
                velocity = None
                growth_pct = None
            else:
                data_state_val = "insufficient_data"
            readiness_state_val = rr.readiness_state if rr else ("blocked_quality" if qr and qr.quality_state != "valid" else "not_ready")
        else:
            values = [_get_val(s) for s in ordered_signals]
            slope_val = round(theil_sen_slope(values), 6)
            if slope_val > slope_tolerance:
                trend_dir = "Increasing"
            elif slope_val < -slope_tolerance:
                trend_dir = "Declining"
            else:
                trend_dir = "Stable"
            confidence_val = None
            data_state_val = "ready"
            readiness_state_val = "ready_for_trend"

        evidence_url = f"/api/v1/skills/intelligence/{canonical_skill_id or canonical_name}/evidence"
        ordered_values = [_get_val(s) for s in ordered_signals]
        explanation = _format_trend_explanation(
            source=source,
            signal_type=signal_type,
            canonical_name=canonical_name,
            trend_dir=trend_dir,
            slope=slope_val,
            velocity=velocity,
            growth_pct=growth_pct,
            whole_window_change=whole_window_change,
            whole_window_pct_change=whole_window_pct_change,
            metric=metric,
            data_state=data_state_val,
            ordered_periods=ordered_periods,
            ordered_values=ordered_values,
            total_obs_count=total_obs_count,
            all_obs_ids=list(all_obs_ids),
            all_run_ids=list(all_run_ids),
            series_id=chosen_series_id,
            unit=result_unit,
            velocity_unit=f"{result_unit} per {period_grain}" if result_unit else None,
            slope_unit=f"{result_unit} per {period_grain}" if result_unit else None,
            period_grain=period_grain,
            scope=latest_sig.scope,
            location=latest_sig.location,
            query_id=latest_sig.query_id,
            calculation_version=G14_CALCULATION_VERSION,
            blocking_reasons=blocking_reasons,
            warnings=series_warnings,
        )

        results.append(SkillTrendVelocityResult(
            source=source,
            signal_type=signal_type,
            canonical_skill_id=canonical_skill_id,
            canonical_name=canonical_name,
            latest_period=latest_period,
            latest_value=latest_value,
            previous_period=previous_period,
            previous_value=previous_value,
            first_period=first_period,
            first_value=first_value,
            velocity=velocity,
            growth_pct=growth_pct,
            whole_window_change=whole_window_change,
            whole_window_pct_change=whole_window_pct_change,
            latest_mom_change=velocity,
            latest_mom_pct_change=growth_pct,
            slope=slope_val,
            trend=trend_dir,
            confidence=confidence_val,
            data_state=data_state_val,
            periods_used=ordered_periods,
            series=[
                {"period": period, "value": value}
                for period, value in zip(ordered_periods, ordered_values)
            ],
            observation_count=total_obs_count,
            observation_ids=sorted(all_obs_ids),
            fetch_run_ids=sorted(all_run_ids),
            series_id=chosen_series_id,
            panel_version=panel_version,
            unit=result_unit,
            source_unit=latest_sig.unit,
            velocity_unit=f"{result_unit} per {period_grain}" if result_unit else None,
            slope_unit=f"{result_unit} per {period_grain}" if result_unit else None,
            period_grain=period_grain,
            scope=latest_sig.scope,
            location=latest_sig.location,
            query_id=latest_sig.query_id,
            data_origin=data_origin,
            history_type=history_type,
            metric=metric,
            calculation_version=G14_CALCULATION_VERSION,
            provider=source,
            trend_direction=trend_dir,
            trend_slope=slope_val,
            growth=growth_pct,
            evidence_url=evidence_url,
            readiness_state=readiness_state_val,
            blocking_reasons=blocking_reasons,
            warnings=series_warnings,
            explanation=explanation,
        ))

    return sorted(
        results,
        key=lambda r: (
            r.source, r.signal_type, r.canonical_name, r.series_id or "",
            r.scope or "", r.location or "", r.metric, r.period_grain or "",
        ),
    )

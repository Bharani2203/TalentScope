"""Analytical readiness gate and forecast input contract logic for G1.9."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Sequence

from app.analytics.observation_period import is_completed_month
from app.analytics.series_validation import (
    _find_period_gaps,
    _month_index,
    comparable_series_key,
    validate_series_observations,
)
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.models.analytical_readiness import (
    AnalyticalReadinessReport,
    AnalyticalReadinessSummary,
    ForecastObservationInput,
    ForecastSeriesInput,
    ReadinessState,
)
from app.models.signal_quality import SeriesQualityReport
from app.models.skill_intelligence import MarketObservation


def _longest_consecutive_run(ordered_periods: list[str]) -> int:
    """Calculate the longest run of strictly consecutive monthly periods."""
    if not ordered_periods:
        return 0
    indices = sorted(set(_month_index(p) for p in ordered_periods if p))
    if not indices:
        return 0
    max_run = 1
    current_run = 1
    for i in range(1, len(indices)):
        if indices[i] == indices[i - 1] + 1:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    return max_run


def assess_analytical_readiness(
    observations: Sequence[MarketObservation],
    *,
    quality_reports: Sequence[SeriesQualityReport] | None = None,
    min_trend_periods: int = 4,
    min_forecast_periods: int = 24,
    as_of: date | datetime | None = None,
) -> list[AnalyticalReadinessReport]:
    """Assess whether validated market observation series are ready for trend or forecasting.

    Strict rules:
    - Never mix providers (e.g. JSearch vs Adzuna).
    - Never mix signal types (e.g. demand vs adoption).
    - Reuses G1.8 validation results as the quality authority.
    - Requires >=4 consecutive valid periods for trend readiness.
    - Requires at least 24 (or a larger configured minimum) consecutive periods for forecast readiness.
    - Zero synthetic periods, zero interpolation, zero null-to-zero conversion.
    """
    if not observations:
        return []

    min_forecast_periods = max(24, min_forecast_periods)

    # Ensure quality reports are available
    if quality_reports is None:
        quality_reports = validate_series_observations(
            observations,
            min_periods=min_trend_periods,
        )

    quality_map: dict[tuple[object, ...], SeriesQualityReport] = {}
    quality_by_base: dict[tuple[str, str, str | None], list[SeriesQualityReport]] = defaultdict(list)
    for report in quality_reports:
        base_key = (report.provider.casefold().strip(), report.signal_type.strip(), report.canonical_skill_id)
        quality_by_base[base_key].append(report)
        quality_map[comparable_series_key(
            source=report.provider,
            signal_type=report.signal_type,
            canonical_skill_id=report.canonical_skill_id,
            unit=report.unit,
            denominator_unit=report.denominator_unit,
            scope=report.scope,
            location=report.location,
            query_id=report.query_id,
            panel_version=report.panel_version,
            data_origin=report.data_origin,
            history_type=report.history_type,
            extractor_version=report.extractor_version,
        )] = report

    # Group observations by source, signal, skill, and all comparable dimensions.
    grouped: dict[tuple[object, ...], list[MarketObservation]] = defaultdict(list)
    for obs in observations:
        norm_name = normalize_skill(obs.skill)
        c_id = canonical_skill_id(norm_name)
        key = comparable_series_key(
            source=obs.source,
            signal_type=obs.signal_type,
            canonical_skill_id=c_id,
            unit=obs.unit,
            denominator_unit=obs.denominator_unit,
            scope=obs.scope,
            location=obs.location,
            query_id=obs.query_id,
            panel_version=obs.panel_version,
            data_origin=obs.data_origin,
            history_type=obs.history_type,
            extractor_version=obs.extractor_version,
        )
        grouped[key].append(obs)

    reports: list[AnalyticalReadinessReport] = []

    for key, items in grouped.items():
        source, signal_type, c_id = key[:3]
        canonical_name = normalize_skill(items[0].skill)
        q_report = quality_map.get(key)
        if q_report is None:
            legacy_reports = quality_by_base[(source, signal_type, c_id)]
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
                    q_report = legacy_report

        all_periods_set = {
            item.period or item.observed_at.strftime("%Y-%m")
            for item in items
            if item.period or item.observed_at
        }
        periods_set = set()
        invalid_periods = set()
        for period in all_periods_set:
            try:
                if is_completed_month(period, as_of=as_of):
                    periods_set.add(period)
            except ValueError:
                invalid_periods.add(period)
        ordered_periods = sorted(periods_set, key=_month_index)
        consecutive_periods = _longest_consecutive_run(ordered_periods)
        coverage_gaps = q_report.coverage_gaps if q_report else _find_period_gaps(ordered_periods)

        scopes = sorted({i.scope for i in items if i.scope})
        panels = sorted({i.panel_version for i in items if i.panel_version})
        queries = sorted({i.query_id for i in items if i.query_id})
        series_ids = sorted({i.series_id for i in items if i.series_id})
        origins = sorted({i.data_origin for i in items if i.data_origin})
        histories = sorted({i.history_type for i in items if i.history_type})
        extractors = sorted({i.extractor_version for i in items if i.extractor_version})

        quality_state = q_report.quality_state if q_report else "insufficient_data"
        comparability = q_report.comparability_status if q_report else "compatible"
        is_sufficient = q_report.is_analytically_sufficient if q_report else False
        if any(item.data_origin != "real" for item in items):
            is_sufficient = False

        blocking_reasons: list[str] = []
        is_trend_ready = False
        is_forecast_ready = False

        # Deterministic readiness gate evaluation
        if any(item.data_origin != "real" for item in items):
            readiness_state = "blocked_quality"
            blocking_reasons.append(
                "OBSERVATION_PROVENANCE_UNAVAILABLE: synthetic, test, demo, or unknown-origin observations are not operational evidence."
            )
        elif comparability == "drift_detected" or quality_state == "configuration_changed":
            readiness_state: ReadinessState = "blocked_configuration"
            if q_report and q_report.issues:
                for issue in q_report.issues:
                    if "drift" in issue.lower() or "configuration" in issue.lower():
                        blocking_reasons.append(issue)
            if not blocking_reasons:
                blocking_reasons.append("Configuration drift detected between historical observation periods.")
        elif coverage_gaps:
            readiness_state = "blocked_missing_period"
            for gap in coverage_gaps:
                blocking_reasons.append(f"{gap} is missing from the comparable series.")
        elif quality_state == "low_coverage":
            readiness_state = "blocked_coverage"
            blocking_reasons.append("Sample size is minimal or lacks a valid denominator for meaningful analytical modeling.")
        elif quality_state in {"incomparable", "provider_failure", "incomplete"} or comparability == "incomparable":
            readiness_state = "blocked_quality"
            blocking_reasons.append(f"Series quality validation failed with state '{quality_state}'.")
        elif len(ordered_periods) == 0:
            readiness_state = "not_ready"
            if invalid_periods:
                blocking_reasons.append(
                    f"Invalid monthly observation period(s) were excluded: {sorted(invalid_periods)}."
                )
            if all_periods_set - periods_set - invalid_periods:
                blocking_reasons.append(
                    "Only incomplete current or future monthly observations were retrieved; no completed periods qualify."
                )
            if not blocking_reasons:
                blocking_reasons.append("No valid completed monthly observations found for series.")
        elif consecutive_periods < min_trend_periods:
            readiness_state = "not_ready"
            period_word = "period" if consecutive_periods == 1 else "periods"
            blocking_reasons.append(
                f"Only {consecutive_periods} valid comparable {period_word} is available; minimum {min_trend_periods} required for trend readiness."
            )
        elif consecutive_periods < min_forecast_periods:
            readiness_state = "ready_for_trend"
            is_trend_ready = True
            is_forecast_ready = False
            blocking_reasons.append(
                f"Series has {consecutive_periods} valid periods; ready for trend, but minimum {min_forecast_periods} required for forecast readiness."
            )
        else:
            readiness_state = "ready_for_forecast"
            is_trend_ready = True
            is_forecast_ready = True

        obs_ids = sorted({i.id for i in items if i.id})[:50]
        fetch_runs = sorted({i.fetch_run_id for i in items if i.fetch_run_id})

        reports.append(AnalyticalReadinessReport(
            provider=source,
            signal_type=signal_type,
            canonical_skill_id=c_id,
            canonical_skill_name=canonical_name,
            canonical_name=canonical_name,
            series_id=series_ids[0] if len(series_ids) == 1 else None,
            series_ids=series_ids,
            panel_version=panels[0] if len(panels) == 1 else None,
            query_ids=queries,
            query_id=items[0].query_id,
            scope=scopes[0] if len(scopes) == 1 else None,
            location=items[0].location,
            unit=items[0].unit,
            denominator_unit=items[0].denominator_unit,
            extractor_version=extractors[0] if len(extractors) == 1 else None,
            data_origin=origins[0] if len(origins) == 1 else None,
            history_type=histories[0] if len(histories) == 1 else None,
            periods_available=ordered_periods,
            consecutive_valid_periods=consecutive_periods,
            coverage_gaps=coverage_gaps,
            quality_state=quality_state,
            comparability_status=comparability,
            is_analytically_sufficient=is_sufficient,
            is_trend_ready=is_trend_ready,
            is_forecast_ready=is_forecast_ready,
            readiness_state=readiness_state,
            blocking_reasons=blocking_reasons,
            observation_ids=obs_ids,
            fetch_run_ids=fetch_runs,
            provenance_summary={
                "provider": source,
                "signal_type": signal_type,
                "observation_count": len(items),
                "unique_postings": len({i.posting_id for i in items if i.posting_id}),
                "periods_count": len(ordered_periods),
                "quality_state": quality_state,
            },
            calculation_version="analytical-readiness-v1",
        ))

    return sorted(reports, key=lambda r: (r.provider, r.signal_type, r.canonical_name))


def summarize_readiness(
    reports: Sequence[AnalyticalReadinessReport],
) -> AnalyticalReadinessSummary:
    """Summarize analytical readiness across all evaluated series."""
    if not reports:
        return AnalyticalReadinessSummary(
            overall_readiness_state="not_ready",
            total_series_evaluated=0,
        )

    trend_count = sum(1 for r in reports if r.is_trend_ready)
    forecast_count = sum(1 for r in reports if r.is_forecast_ready)
    blocked_count = sum(1 for r in reports if r.readiness_state.startswith("blocked_"))
    not_ready_count = sum(1 for r in reports if r.readiness_state == "not_ready")

    # Priority for overall readiness state
    if forecast_count > 0 and forecast_count == len(reports):
        overall: ReadinessState = "ready_for_forecast"
    elif trend_count > 0:
        overall = "ready_for_trend"
    elif any(r.readiness_state == "blocked_configuration" for r in reports):
        overall = "blocked_configuration"
    elif any(r.readiness_state == "blocked_missing_period" for r in reports):
        overall = "blocked_missing_period"
    elif any(r.readiness_state == "blocked_quality" for r in reports):
        overall = "blocked_quality"
    elif any(r.readiness_state == "blocked_coverage" for r in reports):
        overall = "blocked_coverage"
    else:
        overall = "not_ready"

    return AnalyticalReadinessSummary(
        overall_readiness_state=overall,
        total_series_evaluated=len(reports),
        ready_for_trend_count=trend_count,
        ready_for_forecast_count=forecast_count,
        blocked_count=blocked_count,
        not_ready_count=not_ready_count,
        reports=list(reports),
    )


def build_forecast_inputs(
    observations: Sequence[MarketObservation],
    readiness_reports: Sequence[AnalyticalReadinessReport],
    *,
    require_forecast_ready: bool = True,
) -> list[ForecastSeriesInput]:
    """Construct forecast input series containing ONLY eligible observations passing the gates.

    Preserves full provenance, source isolation, and original numeric values without mutation.
    """
    eligible_reports = [
        r for r in readiness_reports
        if (r.is_forecast_ready if require_forecast_ready else r.is_trend_ready)
    ]
    if not eligible_reports:
        return []

    def report_series_key(report: AnalyticalReadinessReport) -> tuple[object, ...]:
        return comparable_series_key(
            source=report.provider,
            signal_type=report.signal_type,
            canonical_skill_id=report.canonical_skill_id,
            unit=report.unit,
            denominator_unit=report.denominator_unit,
            scope=report.scope,
            location=report.location,
            query_id=report.query_id,
            panel_version=report.panel_version,
            data_origin=report.data_origin,
            history_type=report.history_type,
            extractor_version=report.extractor_version,
        )

    eligible_map = {report_series_key(report): report for report in eligible_reports}

    # Group observations matching eligible reports
    series_obs_map: dict[tuple[object, ...], list[MarketObservation]] = defaultdict(list)
    for obs in observations:
        norm_name = normalize_skill(obs.skill)
        c_id = canonical_skill_id(norm_name)
        key = comparable_series_key(
            source=obs.source,
            signal_type=obs.signal_type,
            canonical_skill_id=c_id,
            unit=obs.unit,
            denominator_unit=obs.denominator_unit,
            scope=obs.scope,
            location=obs.location,
            query_id=obs.query_id,
            panel_version=obs.panel_version,
            data_origin=obs.data_origin,
            history_type=obs.history_type,
            extractor_version=obs.extractor_version,
        )
        if key in eligible_map:
            series_obs_map[key].append(obs)

    results: list[ForecastSeriesInput] = []
    for key, items in series_obs_map.items():
        rep = eligible_map[key]
        eligible_periods = set(rep.periods_available)
        sorted_items = sorted(
            [
                item for item in items
                if (item.period or item.observed_at.strftime("%Y-%m")) in eligible_periods
            ],
            key=lambda item: _month_index(item.period or item.observed_at.strftime("%Y-%m")),
        )
        if not sorted_items:
            continue
        obs_inputs = [
            ForecastObservationInput(
                canonical_skill_id=rep.canonical_skill_id,
                canonical_skill_name=rep.canonical_name,
                canonical_name=rep.canonical_name,
                provider=item.source,
                signal_type=item.signal_type,
                period=item.period or item.observed_at.strftime("%Y-%m"),
                value=item.value,
                normalized_value=(item.value / item.denominator) if (item.denominator is not None and item.denominator > 0) else None,
                denominator=item.denominator,
                unit=item.unit,
                denominator_unit=item.denominator_unit,
                series_id=item.series_id,
                panel_version=item.panel_version,
                query_id=item.query_id,
                scope=item.scope,
                location=item.location,
                extractor_version=item.extractor_version,
                data_origin=item.data_origin,
                history_type=item.history_type,
                observation_id=item.id,
                readiness_state=rep.readiness_state,
            )
            for item in sorted_items
        ]
        results.append(ForecastSeriesInput(
            series_id=rep.series_id,
            canonical_skill_id=rep.canonical_skill_id,
            canonical_skill_name=rep.canonical_name,
            canonical_name=rep.canonical_name,
            provider=rep.provider,
            signal_type=rep.signal_type,
            unit=rep.unit,
            denominator_unit=rep.denominator_unit,
            location=rep.location,
            panel_version=rep.panel_version,
            query_id=rep.query_ids[0] if len(rep.query_ids) == 1 else None,
            scope=rep.scope,
            observations=obs_inputs,
            readiness_report=rep,
        ))

    return results

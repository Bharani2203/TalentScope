"""Series comparability, configuration drift, and signal quality validation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Sequence

from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.models.signal_quality import (
    CoverageMetadata,
    QualityAssessmentSummary,
    SeriesComparabilityStatus,
    SeriesQualityReport,
    SeriesQualityState,
)
from app.models.skill_intelligence import MarketObservation


def comparable_series_key(
    *,
    source: str,
    signal_type: str,
    canonical_skill_id: str | None,
    unit: str | None,
    denominator_unit: str | None,
    scope: str | None,
    location: str | None,
    query_id: str | None,
    panel_version: str | None,
    data_origin: str | None,
    history_type: str | None,
    extractor_version: str | None,
) -> tuple[object, ...]:
    """Identity shared by quality, readiness, and trend checks; series ID drift stays detectable."""
    return (
        source.casefold().strip(),
        signal_type.strip(),
        canonical_skill_id,
        unit.casefold().strip() if unit else None,
        denominator_unit.casefold().strip() if denominator_unit else None,
        scope.strip().casefold() if scope else None,
        location.strip().casefold() if location else None,
        query_id.strip() if query_id else None,
        panel_version.strip() if panel_version else None,
        data_origin,
        history_type,
        extractor_version.strip() if extractor_version else None,
    )


def _month_index(period: str) -> int:
    try:
        parts = period.split("-")
        return int(parts[0]) * 12 + int(parts[1])
    except (ValueError, IndexError):
        return 0


def _find_period_gaps(ordered_periods: list[str]) -> list[str]:
    """Find any missing monthly periods between the earliest and latest period."""
    if len(ordered_periods) < 2:
        return []
    indices = [_month_index(p) for p in ordered_periods]
    gaps: list[str] = []
    min_idx, max_idx = min(indices), max(indices)
    present = set(indices)
    for idx in range(min_idx, max_idx + 1):
        if idx not in present:
            year = idx // 12
            month = idx % 12
            if month == 0:
                year -= 1
                month = 12
            gaps.append(f"{year:04d}-{month:02d}")
    return gaps


def validate_series_observations(
    observations: Sequence[MarketObservation],
    *,
    min_periods: int = 4,
) -> list[SeriesQualityReport]:
    """Validate series comparability, detect configuration drift, and report signal quality.

    Rules:
        - Provider, signal family, canonical skill, unit, denominator unit, scope, geography,
          query, panel, provenance, and extractor identity define separate comparable series.
        - A series_id change within those dimensions is flagged as configuration drift.
        - Missing periods are detected and reported as coverage gaps; NEVER coerced or fabricated.
        - Low coverage (e.g. single posting or missing denominator) is explicitly reported.
        - Anomalous multi-magnitude jumps are flagged as potential coverage anomalies without
          altering the underlying numbers.
    """
    if not observations:
        return []

    # Keep comparable dimensions separate while allowing series-ID drift to be detected.
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

    reports: list[SeriesQualityReport] = []

    for key, items in grouped.items():
        source, signal_type, c_id = key[:3]
        canonical_name = normalize_skill(items[0].skill)
        issues: list[str] = []

        # 1. Inspect analytical dimension consistency across periods
        scopes = {i.scope for i in items if i.scope}
        panels = {i.panel_version for i in items if i.panel_version}
        queries = {i.query_id for i in items if i.query_id}
        series_ids = {i.series_id for i in items if i.series_id}
        origins = {i.data_origin for i in items if i.data_origin}
        histories = {i.history_type for i in items if i.history_type}
        extractors = {i.extractor_version for i in items if i.extractor_version}

        drift_detected = False
        drift_reasons: list[str] = []

        if len(scopes) > 1:
            drift_detected = True
            drift_reasons.append(f"scope drift: {sorted(scopes)}")
        if len(panels) > 1:
            drift_detected = True
            drift_reasons.append(f"panel_version drift: {sorted(panels)}")
        if len(queries) > 1:
            drift_detected = True
            drift_reasons.append(f"query_id drift: {sorted(queries)}")
        if len(series_ids) > 1:
            drift_detected = True
            drift_reasons.append(f"series_id drift: {sorted(series_ids)}")
        if len(series_ids) == 1 and any(not item.series_id for item in items):
            drift_detected = True
            drift_reasons.append("series_id is missing from some observations")
        if len(origins) > 1:
            drift_detected = True
            drift_reasons.append(f"data_origin drift: {sorted(origins)}")
        if len(histories) > 1:
            drift_detected = True
            drift_reasons.append(f"history_type drift: {sorted(histories)}")
        if len(extractors) > 1:
            drift_detected = True
            drift_reasons.append(f"extractor_version drift: {sorted(extractors)}")

        if drift_detected:
            issues.append(f"Configuration drift detected: {'; '.join(drift_reasons)}")
            comparability = "drift_detected"
        else:
            comparability = "compatible"

        # 2. Period and gap analysis
        periods_set = {
            item.period or item.observed_at.strftime("%Y-%m")
            for item in items
            if item.period or item.observed_at
        }
        ordered_periods = sorted(periods_set, key=_month_index)
        coverage_gaps = _find_period_gaps(ordered_periods)
        if coverage_gaps:
            issues.append(f"Missing period gap(s): {coverage_gaps}")

        # 3. Duplicate detection
        posting_ids = [item.posting_id for item in items if item.posting_id]
        obs_ids = [item.id for item in items if item.id]
        duplicate_observation_ids = len(obs_ids) != len(set(obs_ids))
        if duplicate_observation_ids:
            issues.append("Duplicate observation IDs detected in series batch.")

        # 4. Coverage analysis
        total_obs = len(items)
        unique_postings = len(set(posting_ids))
        has_denom = any(item.denominator is not None and item.denominator > 0 for item in items)
        
        sample_classification = (
            "empty" if total_obs == 0
            else "minimal" if total_obs == 1
            else "low" if total_obs < 5
            else "adequate"
        )
        if sample_classification in {"minimal", "low"} and signal_type == "demand" and not has_denom:
            issues.append(f"Low sample size ({total_obs} observation(s)) without valid denominator.")

        # 5. Outlier / Anomaly detection (without mutating values)
        anomaly_detected = False
        anomaly_details = None
        period_values: dict[str, float] = defaultdict(float)
        for item in items:
            p = item.period or item.observed_at.strftime("%Y-%m")
            period_values[p] += item.value

        sorted_period_vals = [period_values[p] for p in ordered_periods]
        for idx in range(1, len(sorted_period_vals)):
            prev_v = sorted_period_vals[idx - 1]
            curr_v = sorted_period_vals[idx]
            if prev_v > 0 and curr_v >= prev_v * 100:
                anomaly_detected = True
                anomaly_details = f"Value jumped from {prev_v} in {ordered_periods[idx-1]} to {curr_v} in {ordered_periods[idx]}"
                issues.append(f"Potential coverage anomaly: {anomaly_details}")
                break

        coverage = CoverageMetadata(
            total_observations=total_obs,
            unique_postings=unique_postings,
            periods_count=len(ordered_periods),
            has_valid_denominator=has_denom,
            sample_size_classification=sample_classification,
            anomaly_detected=anomaly_detected,
            anomaly_details=anomaly_details,
        )

        # 6. Quality state determination
        if drift_detected:
            quality_state: SeriesQualityState = "configuration_changed"
        elif duplicate_observation_ids:
            quality_state = "incomplete"
        elif coverage_gaps and len(ordered_periods) >= min_periods:
            quality_state = "incomplete"
        elif sample_classification == "minimal" and not has_denom and signal_type == "demand":
            quality_state = "low_coverage"
        elif len(ordered_periods) < min_periods:
            quality_state = "insufficient_data"
        else:
            quality_state = "valid"

        is_sufficient = (
            quality_state == "valid"
            and len(ordered_periods) >= min_periods
            and not coverage_gaps
            and comparability == "compatible"
        )

        reports.append(SeriesQualityReport(
            provider=source,
            signal_type=signal_type,
            canonical_skill_id=c_id,
            canonical_name=canonical_name,
            series_id=next(iter(series_ids)) if len(series_ids) == 1 else None,
            series_ids=sorted(series_ids),
            unit=items[0].unit,
            denominator_unit=items[0].denominator_unit,
            scope=items[0].scope,
            location=items[0].location,
            query_id=items[0].query_id,
            panel_version=items[0].panel_version,
            data_origin=items[0].data_origin,
            history_type=items[0].history_type,
            extractor_version=items[0].extractor_version,
            quality_state=quality_state,
            comparability_status=comparability,
            periods_found=ordered_periods,
            coverage_gaps=coverage_gaps,
            is_analytically_sufficient=is_sufficient,
            coverage_metadata=coverage,
            issues=issues,
            observation_ids=sorted({i.id for i in items if i.id})[:50],
            fetch_run_ids=sorted({i.fetch_run_id for i in items if i.fetch_run_id}),
            query_ids=sorted(queries),
            panel_versions=sorted(panels),
        ))

    return sorted(reports, key=lambda r: (r.provider, r.signal_type, r.canonical_name))


def filter_compatible_observations(
    observations: Sequence[MarketObservation],
    *,
    min_periods: int = 4,
) -> tuple[list[MarketObservation], list[SeriesQualityReport]]:
    """Filter observations, returning only those belonging to compatible non-drifted series."""
    reports = validate_series_observations(observations, min_periods=min_periods)
    incompatible_keys = {
        comparable_series_key(
            source=r.provider,
            signal_type=r.signal_type,
            canonical_skill_id=r.canonical_skill_id,
            unit=r.unit,
            denominator_unit=r.denominator_unit,
            scope=r.scope,
            location=r.location,
            query_id=r.query_id,
            panel_version=r.panel_version,
            data_origin=r.data_origin,
            history_type=r.history_type,
            extractor_version=r.extractor_version,
        )
        for r in reports
        if r.comparability_status != "compatible"
    }

    compatible_obs = [
        item for item in observations
        if (
            comparable_series_key(
                source=item.source,
                signal_type=item.signal_type,
                canonical_skill_id=canonical_skill_id(normalize_skill(item.skill)),
                unit=item.unit,
                denominator_unit=item.denominator_unit,
                scope=item.scope,
                location=item.location,
                query_id=item.query_id,
                panel_version=item.panel_version,
                data_origin=item.data_origin,
                history_type=item.history_type,
                extractor_version=item.extractor_version,
            ),
        ) not in incompatible_keys
    ]

    return compatible_obs, reports


def summarize_quality(reports: list[SeriesQualityReport]) -> QualityAssessmentSummary:
    """Provide an aggregate quality assessment summary across all series."""
    if not reports:
        return QualityAssessmentSummary(
            overall_quality_state="insufficient_data",
            total_series_assessed=0,
        )

    states = {r.quality_state for r in reports}
    if "configuration_changed" in states:
        overall = "configuration_changed"
    elif "incomplete" in states:
        overall = "incomplete"
    elif "incomparable" in states:
        overall = "incomparable"
    elif "low_coverage" in states:
        overall = "low_coverage"
    elif "valid" in states:
        overall = "valid"
    else:
        overall = "insufficient_data"

    compatible_count = sum(1 for r in reports if r.comparability_status == "compatible")
    incomp_count = sum(1 for r in reports if r.comparability_status in {"incomparable", "drift_detected"})
    drift_count = sum(1 for r in reports if r.comparability_status == "drift_detected")
    low_cov_count = sum(1 for r in reports if r.quality_state == "low_coverage")

    return QualityAssessmentSummary(
        overall_quality_state=overall,
        total_series_assessed=len(reports),
        compatible_series_count=compatible_count,
        incomparable_series_count=incomp_count,
        drift_detected_count=drift_count,
        low_coverage_count=low_cov_count,
        reports=reports,
    )

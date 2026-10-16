"""Authenticated, real-source catalogs for the shared intelligence interfaces.

Reference registry rows are deliberately kept separate from Firestore observations.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
import hashlib
import json
import re
from threading import RLock
from typing import Any

from app.analytics.skill_registry import BY_ID, SKILLS, canonical_skill_id, reference_skill_id
from app.analytics.forecasting import forecast_signal_series
from app.analytics.skill_half_life import calculate_skill_half_life
from app.analytics.skill_health import evaluate_skill_health
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import calculate_trend_and_velocity
from app.analytics.observation_period import is_completed_month
from app.core.firebase import get_firestore_client
from app.models.market_signal import AggregatedMarketSignal
from app.services.skill_intelligence_service import get_favourite_skills, get_user_skills
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.firestore_read_guard import read_guard
from app.storage.reference_store import ReferenceDataStore

_cache_lock = RLock()
_catalog_cache: tuple[float, dict[str, Any]] | None = None
_TTL_SECONDS = 900
_OBSERVATION_LIMIT_PER_BATCH = 500
_job_catalog_cache: tuple[float, list[dict[str, Any]]] | None = None
_JOB_CATALOG_PAGE_SIZE = 500
_JOB_CATALOG_MAX_PAGES = 10
_job_catalog_may_be_incomplete = False
_observation_catalog_truncated = False
_REFERENCE_SOURCE_FILES = {
    "onet_software": "software_skills.csv",
    "onet_essential": "essential_skills.csv",
    "esco": "ESCO dataset - v1.2.1 - classification - en - csv.zip",
}
_GITHUB_STALE_AFTER_DAYS = 180


def _employer_entity_id(name: str) -> str:
    return "company:" + hashlib.sha256(name.casefold().strip().encode("utf-8")).hexdigest()[:20]


def clear_catalog_cache() -> None:
    global _catalog_cache, _job_catalog_cache, _job_catalog_may_be_incomplete, _observation_catalog_truncated
    with _cache_lock:
        _catalog_cache = None
        _job_catalog_cache = None
        _job_catalog_may_be_incomplete = False
        _observation_catalog_truncated = False


def _max_compatible_period_run(observations: list[Any]) -> int:
    """Longest monthly run within one source/signal/entity/configuration series."""
    groups: dict[tuple[Any, ...], set[str]] = {}
    for item in observations:
        key = (item.skill_id, item.source, item.signal_type, item.series_id, item.panel_version, item.data_origin, item.history_type)
        if item.period and is_completed_month(item.period):
            groups.setdefault(key, set()).add(item.period)
    longest = 0
    for periods in groups.values():
        indexes = sorted(int(period[:4]) * 12 + int(period[5:7]) for period in periods if len(period) == 7 and period[4] == "-")
        run = prior = 0
        for index in indexes:
            run = run + 1 if prior and index == prior + 1 else 1
            longest = max(longest, run)
            prior = index
    return longest


def _signal_coverage(observations: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Any]] = {}
    for item in observations:
        grouped.setdefault((item.source, item.signal_type), []).append(item)
    coverage = []
    for (source, signal_type), rows in sorted(grouped.items()):
        periods = sorted({item.period for item in rows if item.period})
        locations: dict[str, set[str]] = {}
        for item in rows:
            if item.location:
                locations.setdefault(item.scope or "global", set()).add(item.location)
        coverage.append({
            "source": source,
            "signal_type": signal_type,
            "first_period": periods[0] if periods else None,
            "latest_period": periods[-1] if periods else None,
            "latest_completed_period": next((period for period in reversed(periods) if is_completed_month(period)), None),
            "period_count": len(periods),
            "locations_by_scope": {scope: sorted(values, key=str.casefold) for scope, values in sorted(locations.items())},
            "consecutive_completed_months": _max_compatible_period_run(rows),
        })
    return coverage


def _observations() -> list[Any]:
    """Query known canonical IDs in bounded batches; never scan the collection."""
    global _observation_catalog_truncated
    from google.cloud.firestore_v1 import FieldFilter

    registry = FirestoreObservationStore()
    collection = registry._collection()
    cutoff = datetime(2000, 1, 1, tzinfo=timezone.utc)
    result: list[Any] = []
    _observation_catalog_truncated = False
    ids = [item.skill_id for item in SKILLS]
    names_and_aliases = sorted({value for item in SKILLS for value in (item.name, *item.aliases)}, key=str.casefold)
    seen_ids: set[str] = set()
    # Query by canonical ID first, then by the exact registry names/aliases for
    # older records written before skill_id was consistently stored.
    for field, values, query_type in (("skill_id", ids, "catalog_canonical_ids"), ("skill", names_and_aliases, "catalog_registry_names")):
        for offset in range(0, len(values), 30):
            query = collection.where(filter=FieldFilter(field, "in", values[offset:offset + 30])).limit(_OBSERVATION_LIMIT_PER_BATCH)
            snapshots = list(query.stream())
            if len(snapshots) >= _OBSERVATION_LIMIT_PER_BATCH:
                _observation_catalog_truncated = True
            read_guard.record_read(registry.collection_name, len(snapshots), query_type=query_type)
            for snapshot in snapshots:
                if snapshot.id in seen_ids:
                    continue
                seen_ids.add(snapshot.id)
                observation = registry._deserialize_observation(snapshot.id, snapshot.to_dict() or {}, cutoff)
                if observation and observation.data_origin != "demo":
                    result.append(observation)
    return result


def _global_catalog() -> dict[str, Any]:
    global _catalog_cache
    now = datetime.now(timezone.utc).timestamp()
    with _cache_lock:
        if _catalog_cache and now - _catalog_cache[0] < _TTL_SECONDS:
            return _catalog_cache[1]

    observations = _observations()
    aggregates = aggregate_market_signals(observations)
    trends = calculate_trend_and_velocity(aggregates)
    by_id: dict[str, list[Any]] = {}
    for item in aggregates:
        if item.canonical_skill_id:
            by_id.setdefault(item.canonical_skill_id, []).append(item)
    trend_by_skill: dict[str, list[Any]] = {}
    for item in trends:
        if item.canonical_skill_id:
            trend_by_skill.setdefault(item.canonical_skill_id, []).append(item)
    entries = []
    for definition in SKILLS:
        series = sorted(by_id.get(definition.skill_id, []), key=lambda item: (item.period, item.source, item.signal_type))
        skill_signals = by_id.get(definition.skill_id, [])
        comparable_candidates = trend_by_skill.get(definition.skill_id, [])
        comparable = max(comparable_candidates, key=lambda item: item.latest_period) if comparable_candidates else None
        # The latest snapshot remains independent from the last completed point
        # used by the trend engine (the current month can be incomplete).
        latest = series[-1] if series else None
        trend_ready = bool(comparable and comparable.data_state in {"ready", "fresh"} and comparable.previous_period)
        signal_labels = {"demand": "Job-posting demand", "adoption": "Developer activity/adoption", "interest": "Community interest", "context": "Reference context"}
        if comparable and not trend_ready:
            trend_unavailable_reason = "; ".join(comparable.blocking_reasons) or "Comparable completed history is insufficient."
        elif latest and not comparable:
            trend_unavailable_reason = "No completed monthly history is available for comparison."
        else:
            trend_unavailable_reason = None
        monthly_series = _group_monthly_signals(skill_signals)
        health_by_family_provider: dict[tuple[str, str], list[Any]] = {}
        half_life_results = []
        forecast_results = []
        for source_series in monthly_series:
            signal_family = source_series[0].signal_type
            provider = source_series[0].source
            health_key = (signal_family, provider.casefold())
            prior_health_series = health_by_family_provider.get(health_key)
            if prior_health_series is None or len(source_series) > len(prior_health_series):
                health_by_family_provider[health_key] = source_series
            half_life_results.append(calculate_skill_half_life(
                source_series,
                canonical_skill_id=definition.skill_id,
                canonical_name=definition.name,
                signal_family=signal_family,
                provider=provider,
            ))
            if signal_family == "demand":
                forecast_results.append(forecast_signal_series(
                    source_series,
                    canonical_skill_id=definition.skill_id,
                    canonical_name=definition.name,
                    signal_family="demand",
                    provider=provider,
                ))
        health_candidates = [
            item
            for source_series in health_by_family_provider.values()
            for item in source_series
        ]
        health_result = evaluate_skill_health(
            health_candidates,
            canonical_skill_id=definition.skill_id,
            canonical_name=definition.name,
        )
        latest_observed_at = max((item.observed_at for item in observations
            if item.source.casefold() == latest.source.casefold()
            and item.signal_type == latest.signal_type
            and item.period == latest.period
            and canonical_skill_id(item.skill) == definition.skill_id
        ), default=None) if latest else None
        entries.append({
            "skill_id": definition.skill_id,
            "name": definition.name,
            "aliases": list(definition.aliases),
            "category": definition.category,
            "reference_source": "TalentScope canonical skill registry",
            "status": "observed" if latest else "reference_only",
            "observation_sources": sorted({item.source for item in series}),
            "signals": [{"source": item.source, "signal_type": item.signal_type, "signal_label": signal_labels.get(item.signal_type, item.signal_type), "metric": item.metric, "value": item.normalized_value if item.normalized_value is not None else item.raw_value, "raw_value": item.raw_value, "unit": "share" if item.metric == "normalized_share" else item.unit, "denominator": item.denominator, "period": item.period, "series_id": item.series_id, "panel_version": item.panel_version, "scope": item.scope, "location": item.location, "data_origin": item.data_origin, "history_type": item.history_type} for item in series],
            "latest": ({"source": latest.source, "signal_type": latest.signal_type, "signal_label": signal_labels.get(latest.signal_type, latest.signal_type), "metric": latest.metric, "value": latest.normalized_value if latest.normalized_value is not None else latest.raw_value, "raw_value": latest.raw_value, "unit": "share" if latest.metric == "normalized_share" else latest.unit, "denominator": latest.denominator, "period": latest.period, "observed_at": latest_observed_at.isoformat() if latest_observed_at else None, "observation_count": latest.observation_count} if latest else None),
            "trend": ({
                "direction": comparable.trend,
                "latest_value": comparable.latest_value,
                "previous_value": comparable.previous_value,
                "change": comparable.velocity,
                "change_pct": comparable.growth_pct,
                "velocity": comparable.velocity,
                "velocity_metric": comparable.velocity_unit,
                "trend_slope": comparable.slope,
                "trend_slope_unit": comparable.slope_unit,
                "period_grain": comparable.period_grain,
                "unit": comparable.unit,
                "previous_period": comparable.previous_period,
                "period": comparable.latest_period,
                "periods_used": comparable.periods_used,
                "source": comparable.source,
                "signal_type": comparable.signal_type,
                "metric": comparable.metric,
                "scope": comparable.scope,
                "location": comparable.location,
                "query_id": comparable.query_id,
                "readiness_state": comparable.readiness_state,
                "blocking_reasons": comparable.blocking_reasons,
            } if comparable and (trend_ready or comparable.previous_period) else None),
            "trend_available": trend_ready,
            "trend_unavailable_reason": trend_unavailable_reason,
            "trend_readiness": {"ready": trend_ready, "reason": trend_unavailable_reason},
            "skill_health": health_result.model_dump(),
            "half_life": [item.model_dump() for item in half_life_results],
            "forecast": [item.model_dump() for item in forecast_results],
            "forecast_available": any(item.status == "ready" for item in forecast_results),
            "half_life_available": any(item.status == "ready" for item in half_life_results),
        })
    max_compatible_periods = _max_compatible_period_run(observations)
    completed_observations = [item for item in observations if item.period and is_completed_month(item.period)]
    entries.sort(key=lambda row: (0 if row["trend_available"] else 1 if row["status"] == "observed" else 2, row["name"].casefold()))
    data = {
        "skills": entries,
        "groups": {"with_observations": [row["skill_id"] for row in entries if row["status"] == "observed"], "with_historical_trends": [row["skill_id"] for row in entries if row["trend_available"]], "reference_only": [row["skill_id"] for row in entries if row["status"] == "reference_only"]},
        "counts": {"observed": sum(row["status"] == "observed" for row in entries), "historical_trends": sum(row["trend_available"] for row in entries), "reference_only": sum(row["status"] == "reference_only" for row in entries)},
        "locations": sorted({item.location for item in observations if item.location}),
        "coverage_by_signal": _signal_coverage(observations),
        "coverage": {"first_period": min((item.period for item in observations if item.period), default=None), "latest_period": max((item.period for item in observations if item.period), default=None), "period_count": len({item.period for item in observations if item.period}), "source": "Firestore skill_market_signals", "catalog_query_limit_per_batch": _OBSERVATION_LIMIT_PER_BATCH, "possibly_truncated": _observation_catalog_truncated, "cached_seconds": _TTL_SECONDS},
        "available_ranges": (["30d"] + (["3m"] if max_compatible_periods >= 3 else []) + (["6m"] if max_compatible_periods >= 6 else [])) if completed_observations else [],
        "market": {"technologies": [row for row in entries if row["status"] == "observed" and any(s["signal_type"] in {"adoption", "interest"} for s in row["signals"])], "companies_with_market_observations": [], "company_market_telemetry_available": False, "employers_from_job_records": [], "job_records_source": "Firestore jobs; catalog listing is not company market telemetry"},
    }
    with _cache_lock:
        _catalog_cache = (now, data)
    return data


def _reference_skill_catalog() -> list[dict[str, Any]]:
    """Merge local O*NET/ESCO reference labels by canonical identity or label."""
    store = ReferenceDataStore()
    manifest_path = store.database_path.resolve().parent / "reference" / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = {
        str(item.get("local_filename")): item
        for item in manifest.get("datasets", [])
        if isinstance(item, dict) and item.get("local_filename")
    }
    merged: dict[str, dict[str, Any]] = {}
    for row in store.get_reference_skill_rows():
        name = " ".join(str(row.get("name") or "").split())
        if not name:
            continue
        aliases = row.get("aliases") or "[]"
        try:
            aliases = json.loads(aliases) if isinstance(aliases, str) else aliases
        except (TypeError, ValueError):
            aliases = []
        identities = [canonical_skill_id(value) for value in [name, *(aliases if isinstance(aliases, list) else [])]]
        canon_id = next((value for value in identities if value), None)
        key = f"canonical:{canon_id}" if canon_id else f"label:{name.casefold()}"
        item = merged.setdefault(key, {
            "skill_id": canon_id or reference_skill_id(name),
            "name": BY_ID[canon_id].name if canon_id in BY_ID else name,
            "aliases": set(), "reference_sources": set(), "reference_details": [],
            "status": "reference_only", "reference_only": True,
        })
        if name.casefold() != item["name"].casefold():
            item["aliases"].add(name)
        item["aliases"].update(str(value).strip() for value in aliases if str(value).strip())
        item["reference_sources"].add(row.get("source"))
        source_file = _REFERENCE_SOURCE_FILES.get(str(row.get("source") or ""))
        source_metadata = datasets.get(source_file or "", {})
        detail = {
            "source": row.get("source"),
            "taxonomy_id": row.get("taxonomy_id"),
            "source_version": row.get("source_version") or source_metadata.get("version"),
            "source_file": source_file,
            "source_sha256": source_metadata.get("sha256"),
            "manifest_generated_at": manifest.get("generated_at"),
            "occupation_ids": (row.get("occupation_ids") or "").split(",")[:100],
            "category": row.get("categories"),
            "hot_technology": bool(row.get("hot_technology")) if row.get("hot_technology") is not None else None,
            "in_demand_flag": bool(row.get("in_demand")) if row.get("in_demand") is not None else None,
        }
        if detail not in item["reference_details"]:
            item["reference_details"].append(detail)
    return [{**item, "aliases": sorted(item["aliases"], key=str.casefold),
             "reference_sources": sorted(item["reference_sources"]),
             "reference_details": item["reference_details"]}
            for item in merged.values()]


def _quarter_index(period: str) -> int:
    match = re.fullmatch(r"(\d{4})-Q([1-4])", period or "")
    if not match:
        raise ValueError(f"Invalid quarterly period: {period}")
    return int(match.group(1)) * 4 + int(match.group(2)) - 1


def _local_github_series() -> dict[str, list[dict[str, Any]]]:
    """Compact mapped India series, retaining original quarterly periods."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in ReferenceDataStore().get_github_adoption_series_for_country("IN"):
        skill_id = row.get("canonical_skill_id")
        if skill_id not in BY_ID or not row.get("period"):
            continue
        groups.setdefault((skill_id, row["metric"], row["label"]), []).append(row)
    output: dict[str, list[dict[str, Any]]] = {}
    for (skill_id, metric, label), rows in groups.items():
        ordered = sorted(rows, key=lambda row: _quarter_index(row["period"]))
        points = [{"period": row["period"], "value": row["value"], "unit": row["unit"], "label": row["label"]} for row in ordered]
        indexes = [_quarter_index(point["period"]) for point in points]
        last_run_start = 0
        for index in range(1, len(indexes)):
            if indexes[index] - indexes[index - 1] != 1:
                last_run_start = index
        trend_points = points[last_run_start:]
        engine_signals = [
            AggregatedMarketSignal(
                canonical_skill_id=skill_id,
                canonical_name=BY_ID[skill_id].name,
                source="github_innovation_graph",
                signal_type="adoption",
                period=point["period"],
                metric="adoption_snapshot",
                raw_value=point["value"],
                data_origin="real",
                history_type="backfill",
                data_state="ready",
                series_id=f"github_innovation_graph:{metric}:{skill_id}",
                panel_version=f"github-innovation-graph-quarterly-v1:{metric}",
                unit=point["unit"],
                scope="country",
                location="India",
                query_id=f"github-innovation-graph:{metric}:in",
                warnings=["Raw unique-developer count; this is developer activity, not job demand."],
                metadata={"source_metric": metric, "unit": point["unit"], "time_grain": "quarter"},
            )
            for point in trend_points
        ]
        engine_result = next(iter(calculate_trend_and_velocity(engine_signals)), None)
        trend_ready = bool(engine_result and engine_result.data_state in {"ready", "fresh"})
        completed_periods = set(engine_result.periods_used) if engine_result else set()
        completed_points = [point for point in trend_points if point["period"] in completed_periods]
        if not trend_ready:
            direction = "Insufficient Data"
        else:
            direction = {
                "Increasing": "Rising",
                "Declining": "Falling",
                "Stable": "Stable",
            }.get(engine_result.trend, "Insufficient Data")
        velocity = engine_result.velocity if trend_ready else None
        relative_velocity_pct = engine_result.growth_pct if trend_ready else None
        latest_change = (
            round(engine_result.latest_value - engine_result.previous_value, 6)
            if engine_result and engine_result.previous_period is not None and engine_result.previous_value is not None
            else None
        )
        latest_index = indexes[-1] if indexes else None
        latest_year = latest_index // 4 if latest_index is not None else 0
        latest_quarter = latest_index % 4 + 1 if latest_index is not None else 0
        quarter_end_month = latest_quarter * 3
        quarter_end_day = calendar.monthrange(latest_year, quarter_end_month)[1] if latest_index is not None else 1
        latest_period_end = datetime(latest_year, quarter_end_month, quarter_end_day, tzinfo=timezone.utc) if latest_index is not None else None
        is_stale = bool(latest_period_end and (datetime.now(timezone.utc) - latest_period_end).days > _GITHUB_STALE_AFTER_DAYS)
        output.setdefault(skill_id, []).append({
            "source": "github_innovation_graph", "signal_type": "adoption", "metric": metric,
            "label": label,
            "unit": "unique developers per quarter", "location": "India", "scope": "country",
            "period_grain": "quarter", "points": points,
            "latest": points[-1] if points else None,
            "latest_trend_period": engine_result.latest_period if trend_ready else None,
            "period_over_period_change": latest_change,
            "velocity_per_quarter": round(velocity, 4) if velocity is not None else None,
            "velocity_metric": engine_result.velocity_unit if engine_result else "unique developers per quarter",
            "trend_slope_unit": engine_result.slope_unit if engine_result else "unique developers per quarter",
            "relative_velocity_pct_per_quarter": round(relative_velocity_pct, 4) if relative_velocity_pct is not None else None,
            "trend_direction": direction, "trend_ready": trend_ready,
            "trend_slope": engine_result.slope if trend_ready else None,
            "trend_calculation": engine_result.calculation_version if engine_result else None,
            "trend_periods_used": engine_result.periods_used if engine_result else [],
            "trend_unavailable_reason": None if trend_ready else (
                "; ".join(engine_result.blocking_reasons) if engine_result and engine_result.blocking_reasons
                else f"Requires 4 contiguous completed quarterly observations; found {len(trend_points)} in the latest contiguous run."
            ),
            "period_over_period_reason": None if latest_change is not None else "The latest complete observation has no immediately preceding complete quarter in this series.",
            "data_origin": "local_reference_dataset", "history_type": "backfill",
            "dataset_period_range": f"{points[0]['period']} through {points[-1]['period']}" if points else None,
            "latest_period_end": latest_period_end.date().isoformat() if latest_period_end else None,
            "stale": is_stale,
            "stale_reason": f"Latest source period ended {latest_period_end.date().isoformat()}." if is_stale and latest_period_end else None,
        })
    return output


def get_local_github_skill_series(skill_id: str) -> list[dict[str, Any]]:
    """Return source-separated quarterly developer-activity series for one skill."""
    if skill_id not in BY_ID:
        return []
    return _local_github_series().get(skill_id, [])


def _group_monthly_signals(signals: list[Any]) -> list[list[Any]]:
    """Keep analytical inputs isolated to one fully comparable source series."""
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for signal in signals:
        if not re.fullmatch(r"\d{4}-\d{2}", str(signal.period or "")):
            continue
        key = (
            signal.source,
            signal.signal_type,
            signal.canonical_skill_id,
            signal.series_id,
            signal.metric,
            signal.panel_version,
            signal.unit,
            signal.denominator_unit,
            signal.scope,
            signal.location,
            signal.query_id,
            signal.data_origin,
            signal.history_type,
        )
        groups.setdefault(key, []).append(signal)
    return [
        sorted(rows, key=lambda item: item.period)
        for rows in groups.values()
    ]


def _skill_analysis_readiness(row: dict[str, Any]) -> dict[str, Any]:
    """Describe readiness without treating static references or quarterly snapshots as monthly data."""
    activity = row.get("developer_activity") or []
    ready_activity = [series for series in activity if series.get("trend_ready")]
    github_history_counts = [len(series.get("points") or []) for series in activity]
    market_periods: dict[tuple[Any, ...], set[str]] = {}
    for signal in row.get("signals") or []:
        period = str(signal.get("period") or "")
        if not period:
            continue
        key = (
            str(signal.get("source") or "").casefold(),
            signal.get("signal_type"),
            signal.get("series_id"),
            signal.get("metric"),
            signal.get("panel_version"),
        )
        market_periods.setdefault(key, set()).add(period)
    market_history_counts = [len(periods) for periods in market_periods.values()]
    history_count = max((*github_history_counts, *market_history_counts), default=0)
    observation_count = sum(github_history_counts) + sum(market_history_counts)
    latest_period = max(
        (str(series.get("latest", {}).get("period") or "") for series in activity),
        default="",
    )
    health = row.get("skill_health") or {}
    half_life = row.get("half_life") or []
    forecasts = row.get("forecast") or []
    trend_ready = bool(row.get("trend_available") or ready_activity)
    if row.get("trend_available"):
        trend = {"status": "ready", "reason": None, "source": (row.get("trend") or {}).get("source")}
    elif ready_activity:
        trend = {"status": "ready", "reason": None, "source": "github_innovation_graph"}
    elif history_count:
        if activity:
            reason = next(
                (series.get("trend_unavailable_reason") for series in activity if series.get("trend_unavailable_reason")),
                "Not enough ordered quarterly observations.",
            )
            source = "github_innovation_graph"
        else:
            maximum_periods = max(market_history_counts, default=0)
            reason = (
                f"Requires at least 4 consecutive completed monthly observations in one source/metric series; found {maximum_periods}."
                if maximum_periods < 4
                else "Monthly observations are not a valid, strictly consecutive series from one source and metric."
            )
            source = next((str(signal.get("source")) for signal in row.get("signals") or [] if signal.get("source")), None)
        trend = {"status": "insufficient_history", "reason": reason, "source": source}
    elif row.get("status") == "reference_only":
        trend = {"status": "unavailable", "reason": "Reference taxonomy is static and is not a dated market observation.", "source": None}
    else:
        trend = {"status": "insufficient_history", "reason": row.get("trend_unavailable_reason") or "No valid dated observations are available.", "source": None}
    market_trend = row.get("trend") or {}
    velocity_ready = bool(
        row.get("trend_available") and market_trend.get("velocity") is not None
    ) or any(
        series.get("trend_ready") and series.get("velocity_per_quarter") is not None
        for series in activity
    )
    period_change_ready = (
        market_trend.get("change") is not None
        or any(series.get("period_over_period_change") is not None for series in activity)
    )
    health_ready = health.get("status") in {"ready", "partial"}
    if health_ready:
        health_reason = health.get("explanation")
    elif activity:
        health_reason = "GitHub Innovation Graph reports raw quarterly developer counts without a denominator; Skill Health requires a valid normalized-share series."
    else:
        health_reason = health.get("explanation") or "No validated market signal series is available."
    return {
        "history": {
            "status": "historical" if history_count > 1 else "single_snapshot" if row.get("status") == "observed" else "reference_only" if row.get("status") == "reference_only" else "unavailable",
            "latest_period": latest_period or (row.get("latest") or {}).get("period"),
            "observation_count": observation_count,
            "stale": any(series.get("stale") for series in activity),
        },
        "trend": trend,
        "velocity": {
            "status": "ready" if velocity_ready else "insufficient_history",
            "reason": None if velocity_ready else "A valid four-period trend is required to calculate the Theil-Sen rate of change.",
            "source": "github_innovation_graph" if velocity_ready else None,
            "unit": "Theil-Sen slope in unique developers per quarter" if velocity_ready else None,
        },
        "period_over_period_change": {
            "status": "ready" if period_change_ready else "insufficient_history",
            "reason": None if period_change_ready else next((series.get("period_over_period_reason") for series in activity if series.get("period_over_period_reason")), "A complete latest period and its immediately preceding comparable period are required."),
            "source": "github_innovation_graph" if period_change_ready else None,
        },
        "skill_health": {
            "status": health.get("status", "insufficient_data"),
            "category": health.get("health_category", "insufficient_data"),
            "reason": health_reason,
        },
        "half_life": {
            "status": "ready" if any(item.get("status") == "ready" for item in half_life) else "insufficient_history",
            "reason": next((item.get("reason") for item in half_life if item.get("status") == "ready"), None)
                or next((item.get("reason") for item in half_life if item.get("reason")), None)
                or ("Quarterly raw developer counts cannot support Half-Life; it requires 36 consecutive monthly normalized-share observations." if activity else "No dated source-specific monthly share series is available; static taxonomy data cannot support Half-Life."),
            "eligible": any(item.get("status") == "ready" for item in half_life),
        },
        "forecast": {
            "status": "ready" if any(item.get("status") == "ready" for item in forecasts) else "insufficient_history",
            "reason": next((item.get("reason") for item in forecasts if item.get("status") == "ready"), None)
                or next((item.get("reason") for item in forecasts if item.get("reason")), None)
                or ("Quarterly GitHub activity is not monthly demand history; forecasting requires 24 consecutive monthly observations and a model that beats the naive baseline." if activity else "No dated source-specific monthly series is available for forecasting."),
            "eligible": any(item.get("status") == "ready" for item in forecasts),
            "target": next((item.get("target_series") for item in forecasts if item.get("status") == "ready"), None),
            "period": next((item.get("forecasts", [{}])[0].get("period") for item in forecasts if item.get("status") == "ready" and item.get("forecasts")), None),
        },
        "trend_ready": trend_ready,
        "velocity_ready": velocity_ready,
        "period_over_period_change_ready": period_change_ready,
        "skill_health_ready": health_ready,
        "half_life_ready": any(item.get("status") == "ready" for item in half_life),
        "forecast_ready": any(item.get("status") == "ready" for item in forecasts),
    }


def _job_catalog_rows() -> tuple[list[dict[str, Any]], float]:
    """Return a bounded, source-targeted catalog of stored JSearch and Adzuna jobs.

    Query providers separately so unrelated/legacy documents in ``jobs`` cannot
    consume the shared read cap before current provider records are reached.
    """
    global _job_catalog_cache, _job_catalog_may_be_incomplete
    now = datetime.now(timezone.utc).timestamp()
    with _cache_lock:
        if _job_catalog_cache and now - _job_catalog_cache[0] < _TTL_SECONDS:
            read_guard.record_cache_hit()
            return _job_catalog_cache[1], now - _job_catalog_cache[0]
    from google.cloud.firestore_v1 import FieldFilter

    collection = get_firestore_client().collection("jobs")
    rows: list[dict[str, Any]] = []
    snapshots_read = 0
    _job_catalog_may_be_incomplete = False
    seen_document_ids: set[str] = set()
    for source in ("jsearch", "adzuna"):
        query = collection.where(filter=FieldFilter("source", "==", source)).limit(_JOB_CATALOG_PAGE_SIZE)
        for page_number in range(_JOB_CATALOG_MAX_PAGES):
            snapshots = list(query.stream())
            snapshots_read += len(snapshots)
            for snapshot in snapshots:
                if snapshot.id in seen_document_ids:
                    continue
                seen_document_ids.add(snapshot.id)
                row = snapshot.to_dict() or {}
                # Only these supported persisted provider records belong in the
                # employer evidence catalog; never infer providers from titles.
                if str(row.get("source") or "").casefold() == source:
                    rows.append(row)
            if len(snapshots) < _JOB_CATALOG_PAGE_SIZE:
                break
            if page_number == _JOB_CATALOG_MAX_PAGES - 1:
                _job_catalog_may_be_incomplete = True
                break
            query = query.start_after(snapshots[-1])
    read_guard.record_read("jobs", snapshots_read, query_type="bounded_cursor_catalog")
    with _cache_lock:
        _job_catalog_cache = (now, rows)
    return rows, 0.0


def get_skill_catalog(uid: str) -> dict[str, Any]:
    catalog = _global_catalog()
    profile = get_user_skills(uid)
    data = dict(catalog)
    skill_rows = {row["skill_id"]: dict(row) for row in catalog["skills"]}
    references = _reference_skill_catalog()
    for reference in references:
        prior = skill_rows.get(reference["skill_id"])
        if prior:
            prior["reference_only"] = prior["status"] != "observed"
            prior["reference_sources"] = reference["reference_sources"]
            prior["reference_details"] = reference["reference_details"]
            prior["aliases"] = sorted(set(prior.get("aliases", [])) | set(reference["aliases"]), key=str.casefold)
        else:
            skill_rows[reference["skill_id"]] = reference
    github_series = _local_github_series()
    for skill_id, series in github_series.items():
        if skill_id in skill_rows:
            row = skill_rows[skill_id]
            row["developer_activity"] = series
            row["status"] = "observed"
            row["reference_only"] = False
            row["observation_sources"] = sorted(set(row.get("observation_sources", [])) | {"github_innovation_graph"})
    for row in skill_rows.values():
        activity = row.get("developer_activity") or []
        activity_ready = any(item.get("trend_ready") for item in activity)
        if activity:
            row["trend_available"] = bool(row.get("trend_available") or activity_ready)
            if row["trend_available"]:
                row["trend_unavailable_reason"] = None
            elif not row.get("trend_unavailable_reason"):
                row["trend_unavailable_reason"] = next(
                    (item.get("trend_unavailable_reason") for item in activity if item.get("trend_unavailable_reason")),
                    "Comparable quarterly history is insufficient.",
                )
        row["analysis_readiness"] = _skill_analysis_readiness(row)
        latest_observed_at = (row.get("latest") or {}).get("observed_at")
        market_stale = False
        if latest_observed_at:
            try:
                observed_at = datetime.fromisoformat(str(latest_observed_at).replace("Z", "+00:00"))
                if observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=timezone.utc)
                market_stale = (datetime.now(timezone.utc) - observed_at).days > 90
            except ValueError:
                market_stale = False
        row["provider_data_state"] = (
            "reference_only" if row.get("status") == "reference_only"
            else "stale" if market_stale or any(item.get("stale") for item in activity)
            else "available"
        )
        row["forecast_available"] = row["analysis_readiness"]["forecast_ready"]
        row["half_life_available"] = row["analysis_readiness"]["half_life_ready"]

    data["skills"] = sorted(skill_rows.values(), key=lambda row: (row["status"] != "observed", row["name"].casefold()))
    data["my_skills"] = [skill.model_dump() for skill in profile.skills]
    data["favorite_skill_ids"] = get_favourite_skills(uid).skill_ids
    skill_rows_list = data["skills"]
    unique_ids = {row["skill_id"] for row in skill_rows_list}
    observed_rows = [row for row in skill_rows_list if row.get("status") == "observed"]
    historical_rows = [
        row for row in skill_rows_list
        if row.get("analysis_readiness", {}).get("history", {}).get("status") == "historical"
    ]
    readiness_counts = {
        name: sum(bool(row.get("analysis_readiness", {}).get(flag)) for row in skill_rows_list)
        for name, flag in (
            ("trend", "trend_ready"),
            ("velocity", "velocity_ready"),
            ("period_over_period_change", "period_over_period_change_ready"),
            ("skill_health", "skill_health_ready"),
            ("half_life", "half_life_ready"),
            ("forecast", "forecast_ready"),
        )
    }
    data["counts"] = {
        "total_unique": len(unique_ids),
        "observed": len(observed_rows),
        "reference_only": sum(row.get("status") == "reference_only" for row in skill_rows_list),
        "historically_supported": len(historical_rows),
        "with_historical_market_trend": readiness_counts["trend"],
        "trend_ready": readiness_counts["trend"],
        "with_local_quarterly_developer_history": sum(bool(row.get("developer_activity")) for row in skill_rows_list),
        "unique_canonical_ids": len(unique_ids),
        "alias_entries": sum(len({str(alias).casefold() for alias in row.get("aliases", [])}) for row in skill_rows_list),
        "analytical_eligibility": readiness_counts,
    }
    data["groups"] = {
        "with_observations": [row["skill_id"] for row in observed_rows],
        "with_historical_trends": [row["skill_id"] for row in skill_rows_list if row.get("analysis_readiness", {}).get("trend_ready")],
        "trend_ready_skill_ids": [row["skill_id"] for row in skill_rows_list if row.get("analysis_readiness", {}).get("trend_ready")],
        "reference_only": [row["skill_id"] for row in skill_rows_list if row.get("status") == "reference_only"],
    }
    reference_store = ReferenceDataStore()
    reference_counts = reference_store.get_table_counts()
    esco_archive = reference_store.database_path.resolve().parent / "reference" / _REFERENCE_SOURCE_FILES["esco"]
    data["reference_data"] = {
        "storage": "local SQLite reference data; not Firestore market observations",
        "onet_software_rows": reference_counts["ref_onet_software_skills"],
        "onet_essential_rows": reference_counts["ref_onet_essential_skills"],
        "esco_archive_available_locally": esco_archive.is_file(),
        "esco_skills_ingested_locally": reference_counts["ref_esco_skills"],
    }
    return data


def get_market_catalog(uid: str) -> dict[str, Any]:
    catalog = _global_catalog()
    # Job-employer names are obtained from a bounded recent snapshot. They are explicitly
    # labeled as posting evidence and never promoted to market telemetry.
    job_rows, job_cache_age = _job_catalog_rows()
    companies: dict[str, dict[str, Any]] = {}
    job_locations: set[str] = set()
    first_dates: list[str] = []
    latest_dates: list[str] = []
    roles: set[str] = set()
    for row in job_rows:
        date = str(row.get("posted_at") or "")[:10]
        name = str(row.get("company_name") or "").strip()
        if name:
            item = companies.setdefault(name.casefold(), {"entity_id": _employer_entity_id(name), "name": name, "entity_type": "employer", "evidence_type": "stored_job_postings", "posting_count_in_sample": 0, "company_market_telemetry": False, "sources": set(), "locations": set(), "latest_posted_at": None, "evidence_links": []})
            item["posting_count_in_sample"] += 1
            source = str(row.get("source") or "stored job posting").strip()
            item["sources"].add(source)
            for location_key in ("location", "city", "country"):
                if row.get(location_key):
                    item["locations"].add(str(row[location_key]).strip())
            if date and (not item["latest_posted_at"] or date > item["latest_posted_at"]):
                item["latest_posted_at"] = date
            link = str(row.get("source_url") or "").strip()
            if link.startswith(("https://", "http://")) and link not in item["evidence_links"] and len(item["evidence_links"]) < 3:
                item["evidence_links"].append(link)
        title = str(row.get("title") or "").strip()
        if title:
            roles.add(title)
        for key in ("location", "city", "country"):
            if row.get(key): job_locations.add(str(row[key]).strip())
        # Posting coverage uses the original posted date only; fetch time is not
        # presented as historical job-market coverage.
        date = str(row.get("posted_at") or "")[:10]
        if date: first_dates.append(date); latest_dates.append(date)
    profile_company = None
    try:
        user_doc = get_firestore_client().collection("users").document(uid).get()
        profile = user_doc.to_dict() if user_doc.exists else {}
        company_id = (profile or {}).get("company_id")
        if company_id:
            company_doc = get_firestore_client().collection("companies").document(str(company_id)).get()
            record = company_doc.to_dict() if company_doc.exists else {}
            if record and record.get("owner_uid") == uid and record.get("status") == "active":
                profile_company = {"id": str(company_id), "entity_id": f"registered_company:{company_id}", "name": record.get("company_name"), "entity_type": "registered_company", "evidence_type": "company_registration", "company_market_telemetry": False}
    except Exception:
        # Catalog remains usable when the user's optional company context is unavailable.
        profile_company = None
    result = dict(catalog["market"])
    max_job_days = 0
    if first_dates and latest_dates:
        try:
            max_job_days = (datetime.strptime(max(latest_dates), "%Y-%m-%d") - datetime.strptime(min(first_dates), "%Y-%m-%d")).days
        except ValueError:
            max_job_days = 0
    job_ranges = (["30d"] if latest_dates else []) + (["3m"] if max_job_days >= 90 else []) + (["6m"] if max_job_days >= 180 else [])
    favorite_ids: list[str] = []
    try:
        user_snapshot = get_firestore_client().collection("users").document(uid).get()
        user_record = user_snapshot.to_dict() if user_snapshot.exists else {}
        preferences = (user_record or {}).get("preferences", {})
        stored_ids = preferences.get("favorite_market_entity_ids", []) if isinstance(preferences, dict) else []
        supported_ids = {item["entity_id"] for item in companies.values()}
        supported_ids.update(item["skill_id"] for item in result["technologies"] if item.get("skill_id"))
        if profile_company:
            supported_ids.add(profile_company["entity_id"])
        favorite_ids = [value for value in stored_ids if isinstance(value, str) and value in supported_ids] if isinstance(stored_ids, list) else []
    except Exception:
        favorite_ids = []
    company_rows = []
    for company in companies.values():
        company_rows.append({**company, "sources": sorted(company["sources"]), "locations": sorted(company["locations"]), "evidence_links": list(company["evidence_links"])})
    result.update({"companies_with_job_evidence": sorted(company_rows, key=lambda item: item["name"].casefold()), "roles_in_sample": sorted(roles, key=str.casefold), "registered_company": profile_company, "favorite_entity_ids": sorted(set(favorite_ids)), "locations": catalog["locations"], "job_locations_in_sample": sorted(job_locations), "available_ranges": catalog["available_ranges"], "job_available_ranges": job_ranges, "job_coverage": {"sample_limit": _JOB_CATALOG_PAGE_SIZE * _JOB_CATALOG_MAX_PAGES, "records_read": len(job_rows), "sample_may_be_incomplete": _job_catalog_may_be_incomplete, "cache_ttl_seconds": _TTL_SECONDS, "cache_age_seconds": round(job_cache_age), "first_posted_date_in_sample": min(first_dates, default=None), "latest_posted_date_in_sample": max(latest_dates, default=None), "trends_available": False}})
    return result

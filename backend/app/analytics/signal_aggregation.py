"""Deterministic aggregation layer for multi-source market signals.

Guarantees:
1. Signal family separation: demand vs adoption vs interest vs context are never combined.
2. Source separation: different providers form separate partitions and series.
3. Source-specific denominators: denominators are derived strictly from the same (source, signal_type, period, panel) partition.
4. Raw count vs share preservation: raw counts are never coerced to 100% or artificial shares without valid denominators.
5. Canonical skill identity: all skills normalized via G1.2 canonical registry.
6. Provenance preservation: traces observation_ids, fetch_run_ids, series_id, and panel_version.
7. Zero data fabrication: missing periods, missing denominators, or missing observations are never invented.
8. Missing origin or history provenance remains unavailable; it is never inferred as real.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from app.analytics.skill_normalization import canonical_skill_id, normalize_skill
from app.models.market_signal import AggregatedMarketSignal
from app.models.skill_intelligence import MarketObservation


def partition_key(obs: MarketObservation) -> tuple[object, ...]:
    """Partition observations without crossing source, unit, query, or geography boundaries."""
    period = obs.period or obs.observed_at.strftime("%Y-%m")
    source = obs.source.casefold().strip()
    signal_type = obs.signal_type.strip()
    panel = obs.panel_version.strip() if obs.panel_version else None
    data_origin = obs.data_origin or "unavailable"
    history_type = obs.history_type or "unavailable"
    return (
        source,
        signal_type,
        period,
        panel,
        data_origin,
        history_type,
        obs.unit.strip().casefold() if obs.unit else None,
        obs.denominator_unit.strip().casefold() if obs.denominator_unit else None,
        obs.scope,
        obs.location.strip().casefold() if obs.location else None,
        obs.query_id.strip() if obs.query_id else None,
        obs.extractor_version.strip() if obs.extractor_version else None,
    )


def aggregate_market_signals(
    observations: Sequence[MarketObservation],
    *,
    source_denominators: dict[tuple[object, ...], float] | None = None,
) -> list[AggregatedMarketSignal]:
    """Aggregate observations into deterministic, partition-isolated market signals.
    
    Args:
        observations: Sequence of validated MarketObservation objects.
        source_denominators: Optional mapping of (source, signal_type, period) -> total_items,
                                 (source, signal_type, period, query_id, scope, location), or
                                 the same six dimensions followed by unit and denominator unit.
                                 Less-specific keys apply only when they match a single compatible
                                 partition, preventing denominators from crossing units or panels.
    """
    if not observations:
        return []

    # 1. Partition observations by exact source, signal_type, period, panel, origin, history
    partitions: dict[tuple[object, ...], list[MarketObservation]] = defaultdict(list)

    for obs in observations:
        partitions[partition_key(obs)].append(obs)

    legacy_denom_partitions: dict[tuple[str, str, str], set[tuple[object, ...]]] = defaultdict(set)
    explicit_denom_partitions: dict[tuple[object, ...], set[tuple[object, ...]]] = defaultdict(set)
    for partition in partitions:
        legacy_denom_partitions[(partition[0], partition[1], partition[2])].add(partition)
        explicit_denom_partitions[
            (partition[0], partition[1], partition[2], partition[10], partition[8], partition[9])
        ].add(partition)

    results: list[AggregatedMarketSignal] = []

    for partition, partition_obs in partitions.items():
        (
            source, signal_type, period, panel, origin, history,
            unit_key, denominator_unit_key, scope, location_key, query_id, extractor_version,
        ) = partition
        unit = partition_obs[0].unit
        denominator_unit = partition_obs[0].denominator_unit
        location = partition_obs[0].location
        # 2. Group within partition by canonical skill
        by_skill: dict[tuple[str, str | None], list[MarketObservation]] = defaultdict(list)
        all_posting_ids: set[str] = set()

        for obs in partition_obs:
            canon_name = normalize_skill(obs.skill)
            canon_id = canonical_skill_id(canon_name)
            by_skill[(canon_name, canon_id)].append(obs)
            if obs.posting_id:
                all_posting_ids.add(obs.posting_id)

        # 3. Determine partition denominator
        explicit_denom_key = (source, signal_type, period, query_id, scope, location_key)
        fully_qualified_denom_key = (
            source, signal_type, period, query_id, scope, location_key,
            unit_key, denominator_unit_key,
        )
        denom: float | None = None
        if source_denominators and fully_qualified_denom_key in source_denominators:
            denom = float(source_denominators[fully_qualified_denom_key])
        elif (
            source_denominators
            and explicit_denom_key in source_denominators
            and len(explicit_denom_partitions[explicit_denom_key]) == 1
        ):
            denom = float(source_denominators[explicit_denom_key])
        elif (
            source_denominators
            and (source, signal_type, period) in source_denominators
            and len(legacy_denom_partitions[(source, signal_type, period)]) == 1
        ):
            denom = float(source_denominators[(source, signal_type, period)])
        elif len(all_posting_ids) > 1 and signal_type == "demand":
            # If multiple postings exist in this single partition, posting count is the local denominator
            denom = float(len(all_posting_ids))
        else:
            # Check if observations carry an explicit denominator from the provider
            obs_denoms = {float(item.denominator) for item in partition_obs if getattr(item, "denominator", None) is not None and float(item.denominator) > 0}
            if len(obs_denoms) == 1:
                denom = next(iter(obs_denoms))
            else:
                denom = None

        # 4. Generate AggregatedMarketSignal for each skill
        for (canon_name, canon_id), skill_obs in by_skill.items():
            obs_ids = sorted({item.id for item in skill_obs if item.id})
            run_ids = sorted({item.fetch_run_id for item in skill_obs if item.fetch_run_id})
            series_ids = {item.series_id for item in skill_obs if item.series_id}
            series_id = next(iter(series_ids)) if len(series_ids) == 1 else None

            # Raw count or accumulated value
            raw_value = sum(item.value for item in skill_obs)
            obs_count = len(skill_obs)
            warnings: list[str] = []
            incomplete_collection = any(
                isinstance(getattr(item, "quality", None), dict)
                and (
                    item.quality.get("collection_complete") is False
                    or item.quality.get("pagination_complete") is False
                )
                for item in skill_obs
            )

            # Metric determination
            if signal_type == "adoption":
                if denom is not None and denom > 0:
                    metric = "normalized_share"
                    normalized_value = round(raw_value / denom, 6)
                    data_state = "ready" if origin == "real" else "insufficient_data"
                else:
                    metric = "adoption_snapshot"
                    normalized_value = None  # Adoption metrics without denominator are absolute counts
                    data_state = "ready" if origin == "real" else "insufficient_data"
                    warnings.append("raw count; platform volume changes may affect it")
            elif signal_type in ("demand", "interest"):
                if denom is not None and denom > 0:
                    metric = "normalized_share"
                    normalized_value = round(raw_value / denom, 6)
                    data_state = "ready" if origin == "real" else "insufficient_data"
                else:
                    metric = "raw_count"
                    normalized_value = None  # Insufficient denominator: do NOT return 1.0 as 100%
                    data_state = "insufficient_data"
                    warnings.append("raw count; platform volume changes may affect it")
            else:
                metric = "raw_count"
                normalized_value = None
                data_state = "insufficient_data"
                warnings.append("raw count; platform volume changes may affect it")

            if incomplete_collection:
                data_state = "incomplete"
                warnings.append(
                    "COLLECTION_INCOMPLETE: coverage is incomplete; this period is not completed evidence"
                )

            results.append(AggregatedMarketSignal(
                canonical_skill_id=canon_id,
                canonical_name=canon_name,
                source=source,
                signal_type=signal_type,
                period=period,
                metric=metric,
                raw_value=raw_value,
                normalized_value=normalized_value,
                denominator=denom,
                observation_count=obs_count,
                data_origin=origin,
                history_type=history,
                data_state=data_state,
                confidence=None,  # Never fabricated for single periods
                series_id=series_id,
                panel_version=panel,
                unit=unit,
                denominator_unit=denominator_unit,
                scope=scope,
                location=location,
                query_id=query_id,
                extractor_version=extractor_version,
                observation_ids=obs_ids,
                fetch_run_ids=run_ids,
                warnings=warnings,
            ))

    return sorted(
        results,
        key=lambda s: (
            s.source, s.signal_type, s.period, s.canonical_name,
            s.series_id or "", s.scope or "", s.location or "",
        ),
    )

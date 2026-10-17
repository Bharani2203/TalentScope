"""Service layer for retrieving real, traceable evidence and provenance."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.analytics.trend import G14_CALCULATION_VERSION, calculate_trend_and_velocity
from app.core.firebase import get_firestore_client
from app.models.skill_evidence import (
    CalculationRecordEvidence,
    FetchRunEvidence,
    ObservationEvidence,
    RawArchiveEvidence,
    SkillEvidenceItem,
    SkillEvidenceResponse,
)
from app.storage.calculation_record_store import FirestoreCalculationRecordStore
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore


def get_skill_evidence(
    skill_query: str,
    *,
    source_filter: str | None = None,
    signal_type_filter: str | None = None,
    period_filter: str | None = None,
    range_days: int = 365,
    client: Any | None = None,
) -> SkillEvidenceResponse | None:
    """Retrieve end-to-end evidence chain for a skill across real Firestore collections."""
    from app.analytics.skill_registry import BY_ID, canonical_skill_id
    
    definition_by_id = BY_ID.get(skill_query.strip().casefold())
    if definition_by_id:
        normalized_name = definition_by_id.name
        canon_id = definition_by_id.skill_id
    else:
        normalized_name = normalize_skill(skill_query)
        canon_id = canonical_skill_id(normalized_name)
    
    fs_client = client or get_firestore_client()
    obs_store = FirestoreObservationStore(fs_client)
    fetch_store = FirestoreFetchRunStore(fs_client)
    calc_store = FirestoreCalculationRecordStore(fs_client)
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=range_days)
    
    # 1. Fetch matching observations from Firestore
    raw_obs = obs_store.get_observations(
        cutoff=cutoff,
        skill=normalized_name,
        source=source_filter,
        signal_type=signal_type_filter,
        period=period_filter,
    )
    
    if not raw_obs:
        # Check if skill exists anywhere in canonical registry or aliases
        if canon_id is None:
            # Unknown skill
            return None
        # Known skill, but no observations in window
        return SkillEvidenceResponse(
            skill=skill_query,
            canonical_skill_id=canon_id,
            canonical_name=normalized_name,
            data_state="insufficient_data",
            evidence_count=0,
            items=[],
            sources_represented=[],
            signal_types_represented=[],
        )

    # 2. Feed into G1.3 Aggregation
    agg_signals = aggregate_market_signals(raw_obs)
    
    # 3. Feed into G1.4 Trend & Velocity
    trend_results = calculate_trend_and_velocity(agg_signals)
    trend_map = {
        (
            t.source.casefold(), t.signal_type, t.canonical_skill_id, t.latest_period,
            t.series_id, t.query_id, t.panel_version, t.scope,
            (t.location or "").casefold(), t.source_unit, t.metric,
        ): t
        for t in trend_results
    }

    # 4. Gather provenance collections
    evidence_items: list[SkillEvidenceItem] = []
    sources_seen: set[str] = set()
    signal_types_seen: set[str] = set()
    overall_states: set[str] = set()

    for sig in agg_signals:
        sources_seen.add(sig.source)
        signal_types_seen.add(sig.signal_type)
        overall_states.add(sig.data_state)

        # Match corresponding G1.4 trend result
        trend_key = (
            sig.source.casefold(), sig.signal_type, sig.canonical_skill_id, sig.period,
            sig.series_id, sig.query_id, sig.panel_version, sig.scope,
            (sig.location or "").casefold(), sig.unit, sig.metric,
        )
        trend_res = trend_map.get(trend_key)

        trend_val = trend_res.trend if trend_res else "Insufficient Data"
        velocity_val = trend_res.velocity if trend_res else None
        growth_val = trend_res.growth_pct if trend_res else None
        slope_val = trend_res.slope if trend_res else None
        confidence_val = trend_res.confidence if trend_res else None
        calc_version = trend_res.calculation_version if trend_res else G14_CALCULATION_VERSION
        item_data_state = trend_res.data_state if trend_res else sig.data_state

        # Resolve detailed Observation Evidence
        matching_obs = [
            o for o in raw_obs
            if o.source.casefold() == sig.source.casefold()
            and o.signal_type == sig.signal_type
            and (o.period or o.observed_at.strftime("%Y-%m")) == sig.period
            and normalize_skill(o.skill).casefold() == sig.canonical_name.casefold()
            and o.series_id == sig.series_id
            and o.query_id == sig.query_id
            and o.panel_version == sig.panel_version
            and o.scope == sig.scope
            and (o.location or "").casefold() == (sig.location or "").casefold()
            and o.unit == sig.unit
        ]

        obs_evidence_list: list[ObservationEvidence] = []
        for o in matching_obs:
            obs_evidence_list.append(ObservationEvidence(
                observation_id=o.id or "",
                source=o.source,
                skill=o.skill,
                canonical_skill_id=sig.canonical_skill_id,
                signal_type=o.signal_type,
                period=o.period or o.observed_at.strftime("%Y-%m"),
                location=o.location,
                scope=o.scope,
                value=o.value,
                unit=o.unit,
                data_origin=o.data_origin or "unavailable",
                history_type=o.history_type or "unavailable",
                fetch_run_id=o.fetch_run_id,
                series_id=o.series_id,
                panel_version=o.panel_version,
                observed_at=o.observed_at.isoformat() if o.observed_at else None,
            ))

        # Resolve Fetch Run and Raw Archive Evidence
        fetch_runs_list: list[FetchRunEvidence] = []
        raw_archives_list: list[RawArchiveEvidence] = []
        raw_archive_ids: set[str] = set()

        for run_id in sig.fetch_run_ids:
            run_data = fetch_store.get(run_id)
            if isinstance(run_data, dict):
                fetch_runs_list.append(FetchRunEvidence(
                    fetch_run_id=run_id,
                    source=str(run_data.get("source") or sig.source),
                    status=str(run_data.get("status") or "unknown"),
                    collected_at=str(run_data.get("started_at") or run_data.get("completed_at") or ""),
                    records_fetched=run_data.get("records_fetched"),
                    records_processed=run_data.get("records_processed"),
                    records_rejected=run_data.get("records_rejected"),
                    records_filtered=run_data.get("records_filtered"),
                    location=run_data.get("location"),
                    country=run_data.get("country"),
                    query_id=run_data.get("query_id"),
                ))
                archive_dict = run_data.get("raw_response_archive")
                if isinstance(archive_dict, dict):
                    ref = archive_dict.get("archive_reference") or ""
                    archive_id = ref.replace("raw_response_archives/", "") if ref else f"{sig.source}__{run_id}__000000"
                    raw_archive_ids.add(archive_id)
                    raw_archives_list.append(RawArchiveEvidence(
                        raw_archive_id=archive_id,
                        provider=str(archive_dict.get("provider") or sig.source),
                        fetch_run_id=run_id,
                        archive_reference=ref,
                        content_type=archive_dict.get("content_type"),
                        size_bytes=archive_dict.get("size_bytes"),
                        sha256=archive_dict.get("sha256"),
                        collected_at=str(archive_dict.get("collected_at") or ""),
                        archived_at=str(archive_dict.get("archived_at") or ""),
                    ))

        # Resolve Calculation Record Evidence
        from google.cloud.firestore_v1 import FieldFilter
        calculations_list: list[CalculationRecordEvidence] = []
        calc_record_ids: list[str] = []
        calc_query = (
            fs_client.collection("calculation_records")
            .where(filter=FieldFilter("source", "==", sig.source))
            .where(filter=FieldFilter("period", "==", sig.period))
            .stream()
        )
        for c_doc in calc_query:
            c_data = c_doc.to_dict() or {}
            params = c_data.get("formula_parameters") or {}
            if params.get("canonical_name", "").casefold() == sig.canonical_name.casefold():
                calc_record_ids.append(c_doc.id)
                calculations_list.append(CalculationRecordEvidence(
                    calculation_record_id=c_doc.id,
                    calculation_version=str(c_data.get("calculation_version") or calc_version),
                    formula_id=str(c_data.get("formula_id") or calc_version),
                    metric=str(c_data.get("metric") or sig.metric),
                    window=str(c_data.get("window") or "trend"),
                    periods_used=params.get("periods_used", [sig.period]),
                    observation_ids=c_data.get("observation_ids", sig.observation_ids),
                    result_snapshot=c_data.get("result", {}),
                    created_at=str(c_data.get("created_at") or ""),
                ))

        evidence_items.append(SkillEvidenceItem(
            source=sig.source,
            signal_type=sig.signal_type,
            canonical_skill_id=sig.canonical_skill_id,
            canonical_name=sig.canonical_name,
            period=sig.period,
            metric=sig.metric,
            raw_value=sig.raw_value,
            normalized_value=sig.normalized_value,
            denominator=sig.denominator,
            data_state=item_data_state,
            trend=trend_val,
            velocity=velocity_val,
            growth_pct=growth_val,
            slope=slope_val,
            unit=trend_res.unit if trend_res else None,
            velocity_unit=trend_res.velocity_unit if trend_res else None,
            slope_unit=trend_res.slope_unit if trend_res else None,
            scope=trend_res.scope if trend_res else sig.scope,
            location=trend_res.location if trend_res else sig.location,
            query_id=trend_res.query_id if trend_res else sig.query_id,
            periods_used=trend_res.periods_used if trend_res else [sig.period],
            readiness_state=trend_res.readiness_state if trend_res else "not_ready",
            confidence=confidence_val,
            calculation_version=calc_version,
            series_id=sig.series_id,
            panel_version=sig.panel_version,
            data_origin=sig.data_origin,
            history_type=sig.history_type,
            observation_ids=sig.observation_ids,
            fetch_run_ids=sig.fetch_run_ids,
            raw_archive_ids=sorted(raw_archive_ids),
            calculation_record_ids=sorted(calc_record_ids),
            fetch_runs=fetch_runs_list,
            raw_archives=raw_archives_list,
            observations=obs_evidence_list,
            calculations=calculations_list,
        ))

    root_state = (
        "ready" if overall_states == {"ready"}
        else "insufficient_data" if "insufficient_data" in overall_states or not overall_states
        else next(iter(overall_states))
    )

    return SkillEvidenceResponse(
        skill=skill_query,
        canonical_skill_id=canon_id,
        canonical_name=normalized_name,
        data_state=root_state,
        evidence_count=len(evidence_items),
        items=evidence_items,
        sources_represented=sorted(sources_seen),
        signal_types_represented=sorted(signal_types_seen),
    )

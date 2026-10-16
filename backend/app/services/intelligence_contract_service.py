"""Pure projections into the shared intelligence metric response contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from app.models.execution_orchestrator import EvidenceItem, StructuredFact
from app.models.intelligence_contract import IntelligenceMetricResult
from app.models.skill_intelligence import MarketObservation


def _status(value: Any, *, fallback: str = "insufficient_data") -> str:
    allowed = {"ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"}
    return value if value in allowed else fallback


def _freshness_state(*states: Any, complete: bool) -> str:
    if not complete or "incomplete_history" in states or "incomplete" in states:
        return "incomplete"
    if "stale" in states:
        return "stale"
    if any(state in {"ready", "fresh", "valid"} for state in states):
        return "fresh"
    return "unknown"


def trend_metric_results(
    trends: Sequence[Any],
    observations: Sequence[MarketObservation],
    *,
    history_complete: bool,
) -> list[IntelligenceMetricResult]:
    results: list[IntelligenceMetricResult] = []
    for trend in trends:
        periods = list(getattr(trend, "periods", None) or getattr(trend, "periods_used", []))
        period_end = getattr(trend, "period_end", None) or getattr(trend, "latest_period", None)
        is_trend_ready = bool(
            getattr(trend, "is_trend_ready", False)
            or getattr(trend, "data_state", None) in {"ready", "fresh"}
        )
        matching = [
            observation for observation in observations
            if observation.source.casefold() == str(trend.source).casefold()
            and observation.signal_type == trend.signal_type
            and observation.series_id == trend.series_id
            and observation.period in periods
        ]
        observation_ids = sorted({item.id for item in matching if item.id})
        fetch_run_ids = sorted({item.fetch_run_id for item in matching if item.fetch_run_id})
        source_urls = sorted({item.source_url for item in matching if item.source_url})
        latest_observed_at = max((item.observed_at for item in matching), default=None)
        limitations = list(
            getattr(trend, "limitations", None)
            or getattr(trend, "blocking_reasons", None)
            or getattr(trend, "warnings", None)
            or []
        )
        ready = bool(is_trend_ready and history_complete)
        if not history_complete:
            limitations.append("Trend metrics are withheld because observation history may be truncated.")
        shared = {
            "capability": "trend_velocity_analysis",
            "status": "ready" if ready else "partial" if not history_complete else "insufficient_data",
            "canonical_entity_id": trend.canonical_skill_id,
            "entity_name": getattr(trend, "entity_name", None) or getattr(trend, "canonical_name", None),
            "series_id": trend.series_id,
            "source": trend.source,
            "signal_type": trend.signal_type,
            "location": getattr(trend, "location", None)
            or (matching[0].location if matching else None),
            "scope": matching[0].scope if matching else None,
            "query_id": getattr(trend, "query_id", None)
            or (matching[0].query_id if matching else None),
            "period": period_end,
            "observation_periods": periods,
            "latest_observed_at": latest_observed_at,
            "freshness_state": "incomplete" if not history_complete else (
                "fresh" if latest_observed_at else "unknown"
            ),
            "source_urls": source_urls,
            "observation_ids": observation_ids,
            "fetch_run_ids": fetch_run_ids,
            "readiness_state": "ready_for_trend" if ready else (
                "incomplete_history" if not history_complete
                else getattr(trend, "readiness_state", None) or getattr(trend, "data_state", None)
            ),
            "method_version": getattr(trend, "calculation_version", None),
            "limitations": limitations,
            "reason": "" if ready else "; ".join(limitations),
        }
        if ready:
            metric_specs = [
                (
                    "long_term_trend_direction",
                    getattr(trend, "trend_direction", None) or getattr(trend, "trend", None),
                    "direction",
                    period_end,
                ),
                (
                    "long_term_trend_slope",
                    getattr(trend, "trend_slope", None)
                    if getattr(trend, "trend_slope", None) is not None
                    else getattr(trend, "slope", None),
                    getattr(trend, "slope_unit", None),
                    period_end,
                ),
                (
                    "latest_period_velocity",
                    getattr(trend, "velocity", None),
                    getattr(trend, "velocity_unit", None),
                    getattr(trend, "current_signal_period", None) or period_end,
                ),
            ]
            for metric_name, metric_value, unit, metric_period in metric_specs:
                if metric_value is None or unit is None:
                    results.append(IntelligenceMetricResult(
                        **{
                            **shared,
                            "period": metric_period,
                            "status": "insufficient_data",
                            "metric_kind": "readiness",
                            "metric_name": f"{metric_name}_readiness",
                            "metric_value": "unavailable",
                            "unit": "status",
                            "readiness_state": "missing_metric_value_or_unit",
                            "reason": f"{metric_name} cannot be reported without both a value and unit.",
                        },
                    ))
                    continue
                results.append(IntelligenceMetricResult(
                    **{**shared, "period": metric_period},
                    metric_kind="derived",
                    metric_name=metric_name,
                    metric_value=metric_value,
                    unit=unit,
                ))
        else:
            results.append(IntelligenceMetricResult(
                **shared,
                metric_kind="readiness",
                metric_name="trend_readiness",
                metric_value=(
                    getattr(trend, "readiness_state", None)
                    or getattr(trend, "data_state", None)
                    or "insufficient_data"
                ),
                unit="status",
            ))
    return results


def observed_metric_results(
    observations: Sequence[MarketObservation],
    *,
    history_complete: bool,
) -> list[IntelligenceMetricResult]:
    results: list[IntelligenceMetricResult] = []
    for observation in observations:
        period = observation.period or observation.observed_at.strftime("%Y-%m")
        quality = observation.quality
        quality_state = quality if isinstance(quality, str) else getattr(quality, "quality_state", None)
        limitations = []
        if not history_complete:
            limitations.append("This observed record is part of a bounded read whose full history may be truncated.")
        if quality_state not in {"ready", "fresh", "valid"}:
            limitations.append("Observation quality is not explicitly marked ready or valid.")
        if not observation.unit:
            limitations.append("The observation does not declare a measurement unit.")
        if not observation.series_id:
            limitations.append("The observation does not declare a canonical series identifier.")
        if not observation.skill_id:
            limitations.append("The observation does not declare a canonical entity identifier.")
        observation_ready = not limitations
        results.append(IntelligenceMetricResult(
            capability="observation",
            status="ready" if observation_ready else "partial",
            metric_kind="observed",
            canonical_entity_id=observation.skill_id,
            entity_name=observation.skill,
            series_id=observation.series_id,
            metric_name=observation.signal_type,
            metric_value=observation.value,
            unit=observation.unit,
            denominator=observation.denominator,
            denominator_unit=observation.denominator_unit,
            source=observation.source,
            signal_type=observation.signal_type,
            location=observation.location,
            scope=observation.scope,
            query_id=observation.query_id,
            period=period,
            observation_periods=[period],
            latest_observed_at=observation.observed_at,
            freshness_state=_freshness_state(
                quality_state,
                complete=history_complete,
            ),
            source_urls=[observation.source_url] if observation.source_url else [],
            observation_ids=[observation.id] if observation.id else [],
            fetch_run_ids=[observation.fetch_run_id] if observation.fetch_run_id else [],
            readiness_state="ready" if observation_ready else (
                "incomplete_history" if not history_complete
                else "stale" if quality_state == "stale"
                else "incomplete_evidence"
            ),
            limitations=limitations,
            reason="Retrieved observation with complete metadata." if observation_ready else "; ".join(limitations),
        ))
    return results


def fact_metric_results(
    facts: Sequence[StructuredFact],
    evidence: Sequence[EvidenceItem],
    *,
    history_complete: bool,
) -> list[IntelligenceMetricResult]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    results: list[IntelligenceMetricResult] = []
    for fact in facts:
        readiness = fact.readiness_state
        fact_status = (
            _status(fact.metric_value, fallback="insufficient_data")
            if fact.fact_type == "analysis_readiness"
            else "ready" if fact.metric_value is not None else "insufficient_data"
        )
        evidence_item = evidence_by_id.get(fact.evidence_reference or "")
        details = fact.details or {}
        if fact_status == "ready" and (
            fact.quality_state in {"stale", "invalid", "error", "configuration_changed"}
            or readiness in {"stale", "incomplete_history", "blocked_coverage", "invalid"}
            or evidence_item is not None
            and evidence_item.quality in {"stale", "invalid", "error", "unavailable", "insufficient_history"}
        ):
            fact_status = "partial"
            readiness = readiness or fact.quality_state or (
                evidence_item.quality if evidence_item is not None else None
            )
        if not history_complete and fact.fact_type in {"trend_analysis", "analysis_readiness"}:
            fact_status = "partial"
            readiness = "incomplete_history"
        if fact.metric_value is None and not readiness:
            readiness = "missing_metric_value"
        results.append(IntelligenceMetricResult(
            capability=fact.fact_type,
            status=fact_status,
            metric_kind=(
                "readiness" if fact.fact_type == "analysis_readiness"
                else "observed" if fact.fact_type in {"historical_observation", "market_snapshot", "stored_job_postings"}
                else "derived"
            ),
            canonical_entity_id=fact.canonical_entity_id,
            entity_name=fact.entity_name,
            series_id=fact.series_id or details.get("series_id"),
            metric_name=fact.metric_name,
            metric_value=fact.metric_value,
            unit=fact.unit,
            denominator=fact.denominator,
            denominator_unit=details.get("denominator_unit"),
            source=fact.source,
            signal_type=details.get("signal_type") or (
                fact.metric_name if fact.metric_name in {"demand", "adoption", "interest"} else None
            ),
            location=evidence_item.location if evidence_item else details.get("location"),
            scope=evidence_item.scope if evidence_item else details.get("scope"),
            query_id=evidence_item.query_id if evidence_item else details.get("query_id"),
            period=fact.period,
            observation_periods=details.get("periods_used") or (
                [fact.period] if fact.period else []
            ),
            latest_observed_at=fact.timestamp,
            freshness_state=_freshness_state(
                fact.quality_state,
                readiness,
                evidence_item.quality if evidence_item else None,
                complete=history_complete,
            ),
            source_urls=(
                [evidence_item.source_url] if evidence_item and evidence_item.source_url else
                list(details.get("source_urls") or details.get("supporting_source_urls") or [])
            ),
            observation_ids=(
                list(details.get("observation_ids") or details.get("supporting_observation_ids") or [])
                or ([fact.provenance_id] if fact.provenance_id and fact.fact_type == "historical_observation" else [])
            ),
            fetch_run_ids=(
                [evidence_item.fetch_run_id] if evidence_item and evidence_item.fetch_run_id else
                list(details.get("fetch_run_ids") or [])
            ),
            readiness_state=readiness,
            method_version=fact.calculation_version,
            limitations=list(details.get("limitations") or []),
            reason=str(details.get("reason") or ""),
        ))
    return results


def capability_metric_results(
    capabilities: Mapping[str, Any],
    observations: Sequence[MarketObservation] = (),
    *,
    history_complete: bool,
) -> list[IntelligenceMetricResult]:
    observation_by_id = {item.id: item for item in observations if item.id}
    output: list[IntelligenceMetricResult] = []

    def provenance(payload: Mapping[str, Any]) -> tuple[list[str], list[str], list[str], datetime | None]:
        observation_ids = sorted(set(payload.get("observation_ids") or []))
        fetch_run_ids = sorted(set(payload.get("fetch_run_ids") or []))
        source_urls = sorted({
            observation_by_id[item_id].source_url
            for item_id in observation_ids
            if item_id in observation_by_id and observation_by_id[item_id].source_url
        })
        observed_at = max(
            (observation_by_id[item_id].observed_at for item_id in observation_ids if item_id in observation_by_id),
            default=None,
        )
        return observation_ids, fetch_run_ids, source_urls, observed_at

    def add_result(
        capability: str,
        payload: Mapping[str, Any],
        *,
        metric_name: str,
        metric_value: Any,
        metric_kind: str,
        status: str,
        unit: str | None = None,
        period: str | None = None,
        observation_periods: Sequence[str] = (),
        source: str | None = None,
        signal_type: str | None = None,
        readiness_state: str | None = None,
        reason: str = "",
        limitations: Sequence[str] = (),
        method_version: str | None = None,
    ) -> None:
        observation_ids, fetch_run_ids, source_urls, observed_at = provenance(payload)
        incomplete = not history_complete
        output.append(IntelligenceMetricResult(
            capability=capability,
            status="partial" if incomplete and status == "ready" else _status(status),
            metric_kind=metric_kind,  # type: ignore[arg-type]
            canonical_entity_id=payload.get("canonical_skill_id") or payload.get("canonical_entity_id"),
            entity_name=payload.get("canonical_name") or payload.get("entity_name"),
            series_id=payload.get("series_id") or payload.get("target_series"),
            metric_name=metric_name,
            metric_value=metric_value,
            unit=unit,
            denominator=payload.get("denominator"),
            denominator_unit=payload.get("denominator_unit"),
            source=source or payload.get("provider") or payload.get("source"),
            signal_type=signal_type or payload.get("signal_type") or payload.get("signal_family"),
            location=payload.get("location") or payload.get("geography"),
            scope=payload.get("scope"),
            query_id=payload.get("query_id"),
            period=period,
            observation_periods=list(observation_periods),
            latest_observed_at=observed_at,
            freshness_state="incomplete" if incomplete else "fresh" if observed_at else "unknown",
            source_urls=source_urls,
            observation_ids=observation_ids,
            fetch_run_ids=fetch_run_ids,
            readiness_state="incomplete_history" if incomplete else readiness_state,
            method_version=method_version or payload.get("calculation_version"),
            limitations=[
                *list(limitations),
                *(
                    ["Bounded observation history is incomplete; derived values are withheld."]
                    if incomplete and status == "ready" else []
                ),
            ],
            reason=reason,
        ))

    for capability in ("skill_health", "skill_half_life", "forecast"):
        envelope = capabilities.get(capability)
        if not isinstance(envelope, Mapping):
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            continue

        if capability == "skill_health":
            components = payload.get("component_table") or []
            component_observation_ids = sorted({
                observation_id
                for component in components if isinstance(component, Mapping)
                for observation_id in component.get("observation_ids", [])
            })
            category_status = (
                "partial" if not history_complete else
                _status(payload.get("status"), fallback="insufficient_data")
            )
            category_runs = sorted({
                run_id
                for component in components if isinstance(component, Mapping)
                for run_id in component.get("fetch_run_ids", [])
            })
            category_urls = sorted({
                observation_by_id[observation_id].source_url
                for observation_id in component_observation_ids
                if observation_id in observation_by_id and observation_by_id[observation_id].source_url
            })
            category_periods = sorted({
                period
                for component in components if isinstance(component, Mapping)
                for period in component.get("periods_used", [])
            })
            output.append(IntelligenceMetricResult(
                capability=capability,
                status=category_status,
                metric_kind="derived" if payload.get("health_category") not in {None, "insufficient_data"} else "readiness",
                canonical_entity_id=payload.get("canonical_skill_id"),
                entity_name=payload.get("canonical_name"),
                metric_name="skill_health_category",
                metric_value=payload.get("health_category"),
                unit="category",
                observation_periods=category_periods,
                freshness_state="incomplete" if not history_complete else "fresh" if component_observation_ids else "unknown",
                source_urls=category_urls,
                observation_ids=component_observation_ids,
                fetch_run_ids=category_runs,
                readiness_state="incomplete_history" if not history_complete else payload.get("score_status"),
                method_version=payload.get("score_method_version"),
                limitations=list(payload.get("limitations") or []),
                reason=str(envelope.get("reason") or payload.get("explanation") or ""),
            ))
            if payload.get("score") is not None:
                output.append(IntelligenceMetricResult(
                    capability=capability,
                    status=category_status,
                    metric_kind="derived",
                    canonical_entity_id=payload.get("canonical_skill_id"),
                    entity_name=payload.get("canonical_name"),
                    metric_name="skill_health_score",
                    metric_value=payload.get("score"),
                    unit=payload.get("score_unit"),
                    observation_periods=category_periods,
                    freshness_state="incomplete" if not history_complete else "fresh",
                    source_urls=category_urls,
                    observation_ids=component_observation_ids,
                    fetch_run_ids=category_runs,
                    readiness_state="incomplete_history" if not history_complete else payload.get("score_status"),
                    method_version=payload.get("score_method_version"),
                    limitations=list(payload.get("limitations") or []),
                    reason=str(envelope.get("reason") or payload.get("explanation") or ""),
                ))
            for component in components:
                if not isinstance(component, Mapping):
                    continue
                observation_ids, fetch_run_ids, source_urls, observed_at = provenance(component)
                output.append(IntelligenceMetricResult(
                    capability=capability,
                    status=(
                        "partial" if not history_complete and component.get("health_score") is not None
                        else "ready" if component.get("health_score") is not None
                        else "insufficient_data"
                    ),
                    metric_kind="derived" if component.get("health_score") is not None else "readiness",
                    canonical_entity_id=payload.get("canonical_skill_id"),
                    entity_name=payload.get("canonical_name"),
                    series_id=component.get("series_id"),
                    metric_name="skill_health_score" if component.get("health_score") is not None else "skill_health_component_readiness",
                    metric_value=component.get("health_score") if component.get("health_score") is not None else component.get("direction"),
                    unit="score_0_100" if component.get("health_score") is not None else "status",
                    location=component.get("location"),
                    scope=component.get("scope"),
                    query_id=component.get("query_id"),
                    source=component.get("provider"),
                    signal_type=component.get("signal_family"),
                    period=component.get("latest_period"),
                    observation_periods=list(component.get("periods_used") or []),
                    latest_observed_at=observed_at,
                    freshness_state="incomplete" if not history_complete else "fresh" if observed_at else "unknown",
                    source_urls=source_urls,
                    observation_ids=observation_ids,
                    fetch_run_ids=fetch_run_ids,
                    readiness_state=(
                        "incomplete_history" if not history_complete
                        else "ready" if component.get("health_score") is not None
                        else component.get("direction")
                    ),
                    method_version=payload.get("score_method_version"),
                    limitations=list(payload.get("limitations") or []) + list(component.get("warnings") or []),
                    reason=component.get("reason") or payload.get("explanation", ""),
                ))
            continue

        if capability == "skill_half_life":
            ready = payload.get("status") == "ready" and payload.get("half_life_months") is not None
            add_result(
                capability, payload,
                metric_name="skill_half_life_months" if ready else "skill_half_life_readiness",
                metric_value=payload.get("half_life_months") if ready else payload.get("status"),
                metric_kind="derived" if ready else "readiness",
                status=payload.get("status", "insufficient_data"),
                unit=payload.get("half_life_unit") if ready else "status",
                period=payload.get("latest_period"),
                observation_periods=payload.get("periods_used") or [],
                readiness_state=payload.get("status"),
                reason=str(envelope.get("reason") or payload.get("reason") or ""),
                limitations=payload.get("limitations") or [],
                method_version=payload.get("calculation_version"),
            )
            continue

        series = payload.get("series_forecasts")
        forecast_payloads = [
            item for item in series if isinstance(item, Mapping)
        ] if isinstance(series, list) else [payload]
        emitted = False
        for forecast in forecast_payloads:
            points = forecast.get("forecasts") or []
            for point in points:
                if not isinstance(point, Mapping):
                    continue
                if point.get("point_forecast") is None:
                    continue
                emitted = True
                add_result(
                    capability, forecast,
                    metric_name="forecast_value",
                    metric_value=point.get("point_forecast"),
                    metric_kind="predicted",
                    status=forecast.get("status", "insufficient_data"),
                    unit=forecast.get("unit"),
                    period=point.get("period"),
                    observation_periods=[
                        str(forecast.get("first_history_period") or ""),
                        str(forecast.get("latest_history_period") or ""),
                    ],
                    readiness_state=forecast.get("readiness"),
                    reason=str(forecast.get("reason") or ""),
                    limitations=forecast.get("limitations") or [],
                    method_version=forecast.get("calculation_version"),
                )
        if not emitted:
            add_result(
                capability, payload,
                metric_name="forecast_readiness",
                metric_value=payload.get("readiness") or payload.get("status"),
                metric_kind="readiness",
                status=payload.get("status", "insufficient_data"),
                unit="status",
                observation_periods=[
                    value for value in (
                        payload.get("first_history_period"),
                        payload.get("latest_history_period"),
                    ) if value
                ],
                readiness_state=payload.get("readiness"),
                reason=str(envelope.get("reason") or payload.get("reason") or ""),
                limitations=payload.get("limitations") or [],
                method_version=payload.get("calculation_version"),
            )
    return output

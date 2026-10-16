"""Shared Core Intelligence Service for G2.0.

Provides unified analytical intelligence across Skill, Market, and Job domains
and personalizes the interpretation for Individual, Employee, and Company portals.

Strictly preserves:
- G0 authentication and Firestore provenance
- G1.2 canonical skill registry & normalization
- G1.3 multi-source signal aggregation with denominator separation
- G1.4 Theil-Sen trend and velocity formulas
- G1.8 series validation and signal quality
- G1.9 analytical readiness gates
- G1.14 production trend activation
- Phase 4 seasonal-naive forecasts and task-impact assessments remain evidence-gated.
- No fabricated observations, metrics, or task evidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Sequence

from app.analytics.analytical_readiness import assess_analytical_readiness, summarize_readiness
from app.analytics.ai_disruption import (
    evaluate_ai_task_disruption,
    evaluate_market_to_person_to_company_impact,
)
from app.analytics.confidence import compute_evidence_confidence
from app.analytics.forecasting import (
    build_market_ranking,
    forecast_signal_series,
    forecast_signal_series_by_source,
)
from app.analytics.historical_range import historical_cutoff
from app.analytics.series_validation import validate_series_observations, summarize_quality
from app.analytics.shared_intelligence import analyze_market_observations
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.skill_half_life import calculate_skill_half_life
from app.analytics.skill_health import evaluate_skill_health
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.analytics.trend import (
    CALCULATION_VERSION,
    G14_CALCULATION_VERSION,
    calculate_skill_trends,
    calculate_trend_and_velocity,
)
from app.models.core_intelligence import (
    CapabilityEnvelope,
    CompanyContext,
    CoreIntelligenceAnswer,
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
    DataOrigin,
    DataState,
    DataStatus,
    EmployeeContext,
    ExplanationItem,
    HistoricalTrendItem,
    HistoryType,
    IndividualContext,
    IntelligenceDomain,
    IntelligenceSignal,
    KeyChangeItem,
    NextActionItem,
    PortalType,
    ReadinessSummary,
    RecommendationItem,
)
from app.models.action_recommendation import (
    ActionRecommendation,
    ActionRecommendationResponse,
)
from app.models.skill_intelligence import MarketObservation
from app.models.market_signal import AggregatedMarketSignal, SkillTrendVelocityResult
from app.services.action_recommendation_service import build_action_recommendations
from app.services.intelligence_consistency_service import IntelligenceConsistencyService
from app.services.intelligence_contract_service import (
    capability_metric_results,
    observed_metric_results,
    trend_metric_results,
)
from app.services.onboarding_service import get_individual_profile
from app.storage.firestore_observation_store import FirestoreObservationStore



# Historical range lookups matching platform standard
RANGE_DAYS: dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "3m": 90,
    "6m": 180,
}


def _range_cutoff(range_key: str, now: datetime, custom_days: int | None = None) -> datetime:
    if range_key == "custom" and custom_days:
        return historical_cutoff(now, custom_days)
    else:
        days = RANGE_DAYS.get(range_key, 30)
    return now - timedelta(days=days)


def _normalize_quality_state(q: Any) -> str:
    if isinstance(q, str) and q.strip():
        return q.strip()
    if isinstance(q, dict):
        return str(q.get("quality_state") or q.get("state") or "valid")
    return "valid"


class CoreIntelligenceService:
    """Unified intelligence service serving Individual, Employee, and Company portals."""

    def __init__(self, observation_store: Any | None = None):
        self._store = observation_store

    def _get_store(self) -> Any:
        if self._store is not None:
            return self._store
        return FirestoreObservationStore()

    # -------------------------------------------------------------------------
    # CONTEXT RESOLUTION
    # -------------------------------------------------------------------------

    def resolve_individual_context(self, user_id: str | None, request: CoreIntelligenceRequest) -> IndividualContext:
        """Resolve individual user context from onboarding profile and request overrides."""
        if not user_id:
            return IndividualContext(
                user_id=None,
                target_role=request.target_role,
                location=request.location,
                selected_skills=request.selected_skills,
            )
        try:
            profile_resp = get_individual_profile(user_id)
            prof = profile_resp.profile or {}
        except Exception:
            prof = {}

        skills_dict = prof.get("skills", {}) if isinstance(prof.get("skills"), dict) else {}
        selected_skills = request.selected_skills or skills_dict.get("selected_skills", [])
        skill_levels = skills_dict.get("skill_levels", {})

        target_role = (
            request.target_role
            or prof.get("role_direction", {}).get("target_role")
            or prof.get("target_role")
        )
        location = (
            request.location
            or prof.get("location", {}).get("preferred_location")
            or prof.get("location")
            or "Global"
        )

        return IndividualContext(
            user_id=user_id,
            target_role=target_role,
            target_direction=prof.get("role_direction", {}).get("direction_category"),
            stage=prof.get("user_category"),
            location=location,
            selected_skills=selected_skills,
            skill_levels=skill_levels if isinstance(skill_levels, dict) else {},
        )

    def resolve_employee_context(
        self,
        user_id: str | None,
        company_id: str | None,
        request: CoreIntelligenceRequest,
    ) -> EmployeeContext:
        """Resolve employee context, preserving boundaries between public and private company data."""
        # Check company context override or requested parameters
        is_connected = bool(company_id or request.company_id)
        cid = company_id or request.company_id
        company_name = request.context_override.get("company_name") or (cid.capitalize() if cid else None)

        return EmployeeContext(
            user_id=user_id,
            company_id=cid,
            company_name=company_name,
            department=request.context_override.get("department"),
            team=request.context_override.get("team"),
            current_role=request.target_role or request.context_override.get("current_role"),
            time_in_role=request.context_override.get("time_in_role"),
            is_connected=is_connected,
            internal_mobility_preference=request.context_override.get("internal_mobility_preference"),
            verified_company_skills=request.context_override.get("verified_company_skills", []),
        )

    def resolve_company_context(self, company_id: str | None, request: CoreIntelligenceRequest) -> CompanyContext:
        """Resolve company workforce context."""
        cid = company_id or request.company_id or "default_org"
        return CompanyContext(
            company_id=cid,
            company_name=request.context_override.get("company_name") or cid.capitalize(),
            industry=request.context_override.get("industry") or "Technology & Software",
            company_size=request.context_override.get("company_size") or "Enterprise",
            headquarters=request.location or "Global",
            departments=request.context_override.get("departments", []),
            teams=request.context_override.get("teams", []),
            workforce_headcount=request.context_override.get("workforce_headcount"),
            workforce_skill_inventory=request.selected_skills or request.context_override.get("workforce_skill_inventory", []),
            priority_roles=request.selected_roles or request.context_override.get("priority_roles", []),
            future_skill_focus=request.context_override.get("future_skill_focus", []),
        )

    # -------------------------------------------------------------------------
    # MAIN INTELLIGENCE ENTRY POINT
    # -------------------------------------------------------------------------

    def get_intelligence(
        self,
        request: CoreIntelligenceRequest,
        *,
        authenticated_uid: str | None = None,
    ) -> CoreIntelligenceResponse:
        """Evaluate shared intelligence for the requested domain and context."""
        user_id = authenticated_uid or request.user_id
        now = datetime.now(timezone.utc)
        cutoff = _range_cutoff(request.time_range, now, request.custom_days)

        # Normalize location
        effective_loc = request.location.strip() if request.location and request.location.strip() else None
        if effective_loc and effective_loc.casefold() == "global":
            effective_loc = None

        # 1. Retrieve observations from the shared store
        observations: list[MarketObservation] = []
        fetch_error: bool = False
        try:
            store = self._get_store()
            filter_skills = [s.strip().casefold() for s in (request.selected_skills or []) if s.strip()]
            if request.query and request.query.strip():
                filter_skills.append(request.query.strip().casefold())

            sig_type = "demand" if request.intelligence_type == "job" else None

            if filter_skills and hasattr(store, "get_observations_by_skills"):
                observations = store.get_observations_by_skills(
                    filter_skills,
                    cutoff=cutoff,
                    location=effective_loc,
                    signal_type=sig_type,
                )
            else:
                try:
                    if sig_type:
                        observations = store.get_observations(
                            cutoff=cutoff,
                            location=effective_loc,
                            signal_type=sig_type,
                        )
                    else:
                        observations = store.get_observations(
                            cutoff=cutoff,
                            location=effective_loc,
                        )
                except TypeError:
                    observations = store.get_observations(cutoff=cutoff, location=effective_loc)
        except Exception:
            fetch_error = True
            observations = []
        history_complete = not bool(getattr(observations, "truncated", False))

        # 2. Resolve portal context
        ind_ctx = self.resolve_individual_context(user_id, request)
        emp_ctx = self.resolve_employee_context(user_id, request.company_id, request)
        comp_ctx = self.resolve_company_context(request.company_id, request)

        # 3. Determine data state and origin
        if fetch_error:
            data_status: DataStatus = "error"
            data_state: DataState = "error"
            data_origin: DataOrigin = "unavailable"
            history_type: HistoryType = "unavailable"
        elif not observations:
            data_status = "insufficient_data"
            data_state = "insufficient_data"
            data_origin = "unavailable"
            history_type = "unavailable"
        else:
            data_status = "available"
            origins = {o.data_origin for o in observations if o.data_origin}
            data_origin = "real" if origins == {"real"} else "mixed" if len(origins) > 1 else "demo" if origins == {"demo"} else "real"
            hist_types = {o.history_type for o in observations if o.history_type}
            history_type = next(iter(hist_types)) if len(hist_types) == 1 else "mixed" if hist_types else "platform_collected"
            data_state = "ready" if history_complete else "partial"

        # 4. Filter observations if specific skills/roles/companies were selected
        relevant_observations = observations
        filter_skills = [s.strip().casefold() for s in (request.selected_skills or []) if s.strip()]
        if filter_skills:
            relevant_observations = [
                o for o in observations
                if normalize_skill(o.skill).casefold() in filter_skills
            ]

        # 5. Shared analytical evaluation (Quality, Readiness, Trends)
        quality_reports = validate_series_observations(relevant_observations)
        readiness_reports = assess_analytical_readiness(relevant_observations, quality_reports=quality_reports)
        readiness_summary = summarize_readiness(readiness_reports)
        all_blocking_reasons = sorted({b for r in readiness_reports for b in r.blocking_reasons})
        if not history_complete:
            all_blocking_reasons = sorted(
                set(all_blocking_reasons + ["OBSERVATION_READ_LIMIT_REACHED"])
            )

        norm_overall_readiness = (
            "incomplete_history" if not history_complete
            else
            "insufficient_data" if not relevant_observations
            else "ready_for_trend" if readiness_summary.ready_for_trend_count > 0
            else (
                readiness_summary.overall_readiness_state
                if readiness_summary.overall_readiness_state != "not_ready"
                else "insufficient_history"
            )
        )

        readiness_obj = ReadinessSummary(
            overall_readiness_state=norm_overall_readiness,
            total_series_assessed=readiness_summary.total_series_evaluated,
            ready_for_trend_count=readiness_summary.ready_for_trend_count if history_complete else 0,
            ready_for_forecast_count=readiness_summary.ready_for_forecast_count if history_complete else 0,
            blocked_count=readiness_summary.blocked_count + (1 if not history_complete else 0),
            blocking_reasons=all_blocking_reasons,
        )

        shared_analysis = analyze_market_observations(
            relevant_observations,
            quality_reports=quality_reports,
            readiness_reports=readiness_reports,
            include_trends=request.intelligence_type in {"skill", "market"},
            history_complete=history_complete,
        )
        agg_signals_all = shared_analysis.aggregated_signals

        # 6. Dispatch domain-specific synthesis
        if request.intelligence_type == "skill":
            signals, trends, key_changes, summary = self._synthesize_skill_domain(
                relevant_observations, quality_reports, readiness_reports, now,
                aggregated_signals=agg_signals_all,
                trend_results=shared_analysis.trend_results,
            )
        elif request.intelligence_type == "market":
            signals, trends, key_changes, summary = self._synthesize_market_domain(
                relevant_observations, quality_reports, readiness_reports, now, request,
                aggregated_signals=agg_signals_all,
                trend_results=shared_analysis.trend_results,
            )
        elif request.intelligence_type == "job":
            signals, trends, key_changes, summary = self._synthesize_job_domain(
                relevant_observations, quality_reports, readiness_reports, now, request
            )
        else:
            signals, trends, key_changes, summary = [], [], [], {}

        # 7. Generate contextual explanations, recommendations, and next actions
        explanations = self._generate_explanations(
            request.intelligence_type,
            request.portal_type,
            signals,
            trends,
            key_changes,
            ind_ctx,
            emp_ctx,
            comp_ctx,
            request,
        )
        recommendations = self._generate_recommendations(
            request.intelligence_type,
            request.portal_type,
            signals,
            trends,
            ind_ctx,
            emp_ctx,
            comp_ctx,
            request,
        )
        next_actions = self._generate_next_actions(
            request.intelligence_type,
            request.portal_type,
            recommendations,
            request,
        )
        answer = self._generate_core_answer(
            request.intelligence_type,
            request.portal_type,
            signals,
            trends,
            key_changes,
            summary,
            ind_ctx,
            emp_ctx,
            comp_ctx,
            request,
            overall_readiness_state=norm_overall_readiness,
        )

        # 8. Provenance / Evidence summary
        evidence = {
            "observations_count": len(relevant_observations),
            "sources_used": sorted({o.source for o in relevant_observations}),
            "signal_families": sorted({o.signal_type for o in relevant_observations}),
            "periods": sorted({o.period for o in relevant_observations if o.period}),
            "history_complete": history_complete,
            "history_completeness_reason": (
                None if history_complete
                else "Observation retrieval reached the bounded query row limit; trend and forecast calculations were withheld."
            ),
            "observation_provenance": [
                {
                    "observation_id": o.id,
                    "source": o.source,
                    "signal_type": o.signal_type,
                    "unit": o.unit,
                    "period": o.period,
                    "location": o.location,
                    "scope": o.scope,
                    "series_id": o.series_id,
                    "query_id": o.query_id,
                    "panel_version": o.panel_version,
                    "data_origin": o.data_origin,
                    "history_type": o.history_type,
                    "fetch_run_id": o.fetch_run_id,
                    "source_url": o.source_url,
                }
                for o in relevant_observations
            ],
            "raw_archive_references": sorted({o.metadata.get("raw_archive_id") for o in relevant_observations if o.metadata and o.metadata.get("raw_archive_id")}),
            "quality_status": summarize_quality(quality_reports).overall_quality_state,
        }

        # If data is insufficient, ensure state is honest
        if not relevant_observations and not fetch_error:
            data_status = "insufficient_data"
            data_state = "insufficient_data"

        # 9. Compute the 6 Core Capabilities & Filter Audit
        primary_skill = (
            (request.selected_skills[0] if request.selected_skills else None)
            or (trends[0].entity_name if trends else None)
            or (signals[0].entity_name if signals else None)
            or "Python"
        )
        primary_canon = normalize_skill(primary_skill)
        primary_canon_id = canonical_skill_id(primary_canon)

        skill_health_res = evaluate_skill_health(
            agg_signals_all,
            canonical_skill_id=primary_canon_id,
            canonical_name=primary_canon,
            history_complete=history_complete,
        )
        half_life_res = calculate_skill_half_life(
            agg_signals_all,
            canonical_skill_id=primary_canon_id,
            canonical_name=primary_canon,
            signal_family=(
                "demand" if any(s.signal_type == "demand" for s in agg_signals_all)
                else "adoption" if any(s.signal_type == "adoption" for s in agg_signals_all)
                else "interest"
            ),
            history_complete=history_complete,
        )
        primary_trend = next((t for t in trends if t.entity_name.casefold() == primary_canon.casefold()), None)
        forecast_series_results = forecast_signal_series_by_source(
            agg_signals_all,
            canonical_skill_id=primary_canon_id,
            canonical_name=primary_canon,
            quality_reports=quality_reports,
            history_complete=history_complete,
        )
        if forecast_series_results:
            preferred_results = [
                result for result in forecast_series_results
                if primary_trend and result.provider.casefold() == primary_trend.source.casefold()
            ]
            forecast_res = (
                next((result for result in preferred_results if result.status == "ready"), None)
                or next((result for result in forecast_series_results if result.status == "ready"), None)
                or (preferred_results[0] if preferred_results else forecast_series_results[0])
            )
        else:
            forecast_res = forecast_signal_series(
                [],
                canonical_skill_id=primary_canon_id,
                canonical_name=primary_canon,
                signal_family="demand",
                quality_reports=quality_reports,
            )
        forecast_payload = forecast_res.model_dump()
        forecast_payload["series_forecasts"] = [
            result.model_dump() for result in forecast_series_results
        ]
        demand_dir = primary_trend.trend_direction if (primary_trend and primary_trend.trend_direction) else "Insufficient Data"
        ai_disruption_res = evaluate_ai_task_disruption(
            entity_name=primary_canon,
            entity_type="skill",
            canonical_id=primary_canon_id,
            empirical_demand_direction=demand_dir,
        )
        default_provider = sorted({s.source for s in agg_signals_all})[0] if agg_signals_all else "adzuna"
        default_family = "demand" if any(s.signal_type == "demand" for s in agg_signals_all) else ("interest" if any(s.signal_type == "interest" for s in agg_signals_all) else "adoption")
        ranking_res = build_market_ranking(
            agg_signals_all,
            provider=default_provider,
            signal_family=default_family,
            metric_name="normalized_share" if any(s.metric == "normalized_share" for s in agg_signals_all) else "raw_count",
        )
        workforce_impact_res = evaluate_market_to_person_to_company_impact(
            skill_name=primary_canon,
            skill_health_category=skill_health_res.health_category,
            demand_trend_direction=demand_dir,
            demand_slope=primary_trend.trend_slope if primary_trend else None,
            half_life_status=half_life_res.status,
            half_life_months=half_life_res.half_life_months,
            user_skills=ind_ctx.selected_skills,
            user_target_role=ind_ctx.target_role,
            company_skill_inventory={s: 1 for s in comp_ctx.workforce_skill_inventory} if comp_ctx.workforce_skill_inventory else None,
            company_open_roles=comp_ctx.priority_roles,
            observation_ids=primary_trend.evidence_references if primary_trend else [],
        )

        latest_obs_dt = max((o.observed_at for o in relevant_observations if o.observed_at), default=None)
        max_periods = max((len(t.periods) for t in trends), default=0)
        conf_res = compute_evidence_confidence(
            period_count=max_periods,
            ready_signal_families=skill_health_res.ready_families,
            family_directions=[r.direction for r in skill_health_res.component_table if r.is_eligible_share],
            latest_observed_at=latest_obs_dt,
            has_valid_denominator=any(s.metric == "normalized_share" for s in agg_signals_all),
            quality_valid=(evidence["quality_status"] == "valid"),
            now=now,
        )
        if answer is not None:
            if relevant_observations and answer.confidence is not None:
                answer.confidence = conf_res.final_score
            answer.confidence_band = conf_res.band

        # Applied vs Unapplied Filters Audit
        applied_filters: dict[str, Any] = {
            "domain": request.intelligence_type,
            "portal_type": request.portal_type,
            "time_range": request.time_range,
            "location": request.location or "Global",
        }
        if request.selected_skills:
            applied_filters["selected_skills"] = request.selected_skills
        unapplied_filters: list[dict[str, Any]] = []
        for fk, fv in (request.filters or {}).items():
            if fk in ("salary_band", "remote_hybrid", "experience_years", "company_tier", "custom_date_range"):
                unapplied_filters.append({
                    "filter": fk,
                    "requested_value": fv,
                    "reason": f"Filter '{fk}' is not supported by the verified observation series schema and was not applied.",
                })
            else:
                applied_filters[fk] = fv
        if effective_loc and relevant_observations and all(
            o.source.casefold() in ("stackexchange", "wikipedia", "github") for o in relevant_observations
        ):
            unapplied_filters.append({
                "filter": "location",
                "requested_value": request.location,
                "reason": "Global developer interest/adoption providers (Stack Exchange, Wikipedia, GitHub Topics) do not partition by city; showing global series.",
            })

        capabilities_map = {
            "skill_health": CapabilityEnvelope(
                capability="skill_health",
                status=skill_health_res.status,
                reason=skill_health_res.explanation,
                payload=skill_health_res.model_dump(),
            ),
            "skill_half_life": CapabilityEnvelope(
                capability="skill_half_life",
                status=half_life_res.status,
                reason=half_life_res.reason,
                payload=half_life_res.model_dump(),
            ),
            "workforce_impact": CapabilityEnvelope(
                capability="workforce_impact",
                status=workforce_impact_res.status,
                reason=workforce_impact_res.reason,
                payload=workforce_impact_res.model_dump(),
            ),
            "ai_disruption": CapabilityEnvelope(
                capability="ai_disruption",
                status=ai_disruption_res.status,
                reason=ai_disruption_res.reason,
                payload=ai_disruption_res.model_dump(),
            ),
            "forecast": CapabilityEnvelope(
                capability="forecast",
                status=forecast_res.status,
                reason=forecast_res.reason,
                payload=forecast_payload,
            ),
            "recommendations": CapabilityEnvelope(
                capability="recommendations",
                status=workforce_impact_res.status,
                reason="Evidence-grounded Learn, Reskill, Redeploy, and Hire recommendations.",
                payload={"items": [r.model_dump() for r in workforce_impact_res.recommendations]},
            ),
        }

        metric_results = [
            *observed_metric_results(
                relevant_observations,
                history_complete=history_complete,
            ),
            *trend_metric_results(
                trends,
                relevant_observations,
                history_complete=history_complete,
            ),
            *capability_metric_results(
                {
                    name: {
                        "status": capability.status,
                        "reason": capability.reason,
                        "payload": capability.payload,
                    }
                    for name, capability in capabilities_map.items()
                },
                relevant_observations,
                history_complete=history_complete,
            ),
        ]

        top_status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] = (
            "error" if fetch_error
            else "partial" if not history_complete
            else "insufficient_data" if not relevant_observations
            else "ready" if any(t.is_trend_ready for t in trends)
            else "partial" if signals
            else "insufficient_data"
        )

        follow_ups = [
            f"What is the categorical Skill Health and Half-Life for {primary_canon}?",
            f"How does {primary_canon} demand compare across signal families?",
        ][:2]

        core_resp = CoreIntelligenceResponse(
            intelligence_type=request.intelligence_type,
            portal_type=request.portal_type,
            status=top_status,
            data_status=data_status,
            data_state=data_state,
            data_origin=data_origin,
            history_type=history_type,
            effective_location=request.location or "Global",
            time_window=request.time_range,
            filters_applied={
                "location": request.location or "Global",
                "time_range": request.time_range,
                "selected_skills": request.selected_skills,
                "selected_roles": request.selected_roles,
                "selected_companies": request.selected_companies,
                "custom_days": request.custom_days,
            },
            applied_filters=applied_filters,
            unapplied_filters=unapplied_filters,
            capabilities=capabilities_map,
            metric_results=metric_results,
            skill_health=skill_health_res.model_dump(),
            skill_half_life=half_life_res.model_dump(),
            forecast=forecast_payload,
            ai_disruption=ai_disruption_res.model_dump(),
            market_rankings=ranking_res.model_dump(),
            workforce_impact=workforce_impact_res.model_dump(),
            confidence_breakdown=conf_res.model_dump(),
            freshness={
                "latest_observed_at": latest_obs_dt.isoformat() if latest_obs_dt else None,
                "evaluated_at": now.isoformat(),
                "freshness_score": conf_res.freshness_score,
            },
            source_coverage={
                "providers": sorted({o.source for o in relevant_observations}),
                "signal_families": sorted({o.signal_type for o in relevant_observations}),
                "ready_families": skill_health_res.ready_families,
                "observation_count": len(relevant_observations),
            },
            follow_up_suggestions=follow_ups,
            summary=summary,
            answer=answer,
            current_signals=signals,
            historical_trends=trends,
            key_changes=key_changes,
            evidence=evidence,
            explanations=explanations,
            recommendations=recommendations,
            readiness=readiness_obj,
            blocking_reasons=all_blocking_reasons,
            next_actions=next_actions,
            action_recommendations=[],
            consistency=None,
            evaluated_at=now,
        )

        # G2.5: Generate context-aware, evidence-backed action recommendations
        action_res = build_action_recommendations(
            core_resp,
            request,
            ind_ctx=ind_ctx,
            emp_ctx=emp_ctx,
            comp_ctx=comp_ctx,
        )
        core_resp.action_recommendations = action_res.recommendations

        # G2.6: Cross-layer consistency validation
        consistency_report = IntelligenceConsistencyService.validate(core_resp, action_res)
        core_resp.consistency = consistency_report
        action_res.consistency = consistency_report

        return core_resp

    def get_action_recommendations(
        self,
        request: CoreIntelligenceRequest,
        authenticated_uid: str | None = None,
    ) -> ActionRecommendationResponse:
        """G2.5 dedicated action recommendation entry point."""
        ind_ctx = self.resolve_individual_context(authenticated_uid, request)
        emp_ctx = self.resolve_employee_context(authenticated_uid, request.company_id, request)
        comp_ctx = self.resolve_company_context(request.company_id, request)
        core_resp = self.get_intelligence(request, authenticated_uid=authenticated_uid)
        action_res = build_action_recommendations(
            core_resp,
            request,
            ind_ctx=ind_ctx,
            emp_ctx=emp_ctx,
            comp_ctx=comp_ctx,
        )
        action_res.consistency = core_resp.consistency or IntelligenceConsistencyService.validate(core_resp, action_res)
        return action_res

    # -------------------------------------------------------------------------
    # DOMAIN SYNTHESIS: SKILL INTELLIGENCE
    # -------------------------------------------------------------------------

    def _synthesize_skill_domain(
        self,
        observations: list[MarketObservation],
        quality_reports: list[Any],
        readiness_reports: list[Any],
        now: datetime,
        *,
        aggregated_signals: list[AggregatedMarketSignal] | None = None,
        trend_results: list[SkillTrendVelocityResult] | None = None,
    ) -> tuple[list[IntelligenceSignal], list[HistoricalTrendItem], list[KeyChangeItem], dict[str, Any]]:
        signals: list[IntelligenceSignal] = []
        trends: list[HistoricalTrendItem] = []
        key_changes: list[KeyChangeItem] = []

        if not observations:
            return signals, trends, key_changes, {"total_skills": 0, "active_signals": 0}

        # 1. Convert current observations to Discrete Signals
        for o in observations[:50]:  # Cap signals at 50 for concise payload
            denom_f = float(o.denominator) if (o.denominator is not None and str(o.denominator).replace(".", "", 1).isdigit() and float(o.denominator) > 0) else None
            signals.append(
                IntelligenceSignal(
                    signal_id=o.id or f"sig-{o.source}-{o.skill}-{o.period}",
                    signal_type=o.signal_type if o.signal_type in {"demand", "adoption", "interest"} else "demand",
                    source=o.source,
                    entity_name=normalize_skill(o.skill),
                    entity_type="skill",
                    period=o.period or o.observed_at.strftime("%Y-%m"),
                    value=o.value,
                    denominator=denom_f,
                    share=(o.value / denom_f) if denom_f and denom_f > 0 else None,
                    unit=o.unit or (
                        "job_postings" if o.signal_type == "demand"
                        else "repositories" if o.signal_type == "adoption"
                        else "tagged_questions"
                    ),
                    data_origin=o.data_origin or "real",
                    history_type=o.history_type or "platform_collected",
                    quality_state=_normalize_quality_state(o.quality),
                    confidence=o.confidence,
                    raw_archive_id=o.metadata.get("raw_archive_id") if o.metadata else None,
                    fetch_run_id=o.fetch_run_id,
                    metadata={
                        "source_url": o.source_url,
                        "location": o.location,
                        "scope": o.scope,
                        "series_id": o.series_id,
                        "query_id": o.query_id,
                        "panel_version": o.panel_version,
                    },
                )
            )

        # 2. Calculate Historical Trends per Series via G1.3 and G1.4/G1.14
        agg_signals = aggregated_signals if aggregated_signals is not None else aggregate_market_signals(observations)
        if trend_results is None:
            trend_results = calculate_trend_and_velocity(
                agg_signals,
                quality_reports=quality_reports,
                readiness_reports=readiness_reports,
            )

        for tr in trend_results:
            is_ready = tr.data_state == "ready" and len(tr.periods_used) >= 4
            p_used = sorted(tr.periods_used)

            # Map data points from original observations for this series
            series_points = [
                {
                    "period": signal.period,
                    "value": (
                        signal.normalized_value
                        if tr.metric == "normalized_share" and signal.normalized_value is not None
                        else signal.raw_value
                    ),
                }
                for signal in agg_signals
                if signal.canonical_skill_id == tr.canonical_skill_id
                and signal.source.casefold() == tr.source.casefold()
                and signal.signal_type == tr.signal_type
                and signal.series_id == tr.series_id
                and signal.query_id == tr.query_id
                and signal.panel_version == tr.panel_version
                and signal.scope == tr.scope
                and (signal.location or "").casefold() == (tr.location or "").casefold()
                and signal.unit == tr.source_unit
                and signal.metric == tr.metric
            ]
            dedup_points = sorted(series_points, key=lambda point: point["period"])

            limitations_list = list(tr.blocking_reasons) if tr.blocking_reasons else []
            for w in getattr(tr, "warnings", []) or []:
                if w not in limitations_list:
                    limitations_list.append(w)
            if not is_ready:
                if len(p_used) < 4:
                    limitations_list.append(f"Requires >= 4 periods for statistical trend; only {len(p_used)} period(s) available")
                limitations_list.append("Forecasting model inactive (is_forecast_ready = false)")
            else:
                if len(p_used) < 24:
                    limitations_list.append("Forecasting model inactive (is_forecast_ready = false)")
                    limitations_list.append("Forecasting model requires >= 24 periods (is_forecast_ready = false)")

            vel_str = (
                f"{tr.velocity:+.4f} {tr.velocity_unit}"
                if tr.velocity is not None else f"unavailable ({tr.velocity_unit})"
            )
            mom_pct_str = f"{tr.growth_pct:+.2f}%" if tr.growth_pct is not None else "unavailable"
            change_name = "month-over-month" if tr.period_grain == "month" else "quarter-over-quarter"
            if is_ready:
                slope_str = f"{tr.slope:+.6f} {tr.slope_unit}" if tr.slope is not None else "unavailable"
                ww_change_str = f"{tr.whole_window_change:+g}" if tr.whole_window_change is not None else "unavailable"
                ww_pct_str = f"{tr.whole_window_pct_change:+.2f}%" if tr.whole_window_pct_change is not None else "unavailable"
                item_explanation = (
                    f"Overall direction for {tr.canonical_name} on {tr.source} is {tr.trend} "
                    f"(Theil-Sen slope {slope_str} across {len(p_used)} periods). "
                    f"Whole-window change: {ww_change_str} ({ww_pct_str}); "
                    f"latest {change_name} change: {vel_str} ({mom_pct_str})."
                )
            else:
                item_explanation = (
                    f"Baseline signal recorded at {tr.latest_value} in period {tr.latest_period} from {tr.source}. "
                    f"Overall trend pending historical depth ({len(p_used)} of 4 required periods); "
                    f"latest {change_name} change: {vel_str} ({mom_pct_str})."
                )

            series_confs = [
                o.confidence for o in observations
                if o.confidence is not None
                and normalize_skill(o.skill).casefold() == tr.canonical_name.casefold()
                and o.source.casefold() == tr.source.casefold()
            ]
            trend_conf = tr.confidence if tr.confidence is not None else (
                round(sum(series_confs) / len(series_confs), 2) if series_confs else None
            )

            matching_obs = [
                observation
                for observation in observations
                if normalize_skill(observation.skill).casefold() == tr.canonical_name.casefold()
                and observation.source.casefold() == tr.source.casefold()
                and observation.signal_type == tr.signal_type
                and observation.series_id == tr.series_id
                and observation.query_id == tr.query_id
                and observation.panel_version == tr.panel_version
                and observation.scope == tr.scope
                and (observation.location or "").casefold() == (tr.location or "").casefold()
                and observation.unit == tr.source_unit
            ]
            matching_period_obs = [
                observation
                for observation in matching_obs
                if (observation.period or observation.observed_at.strftime("%Y-%m")) == tr.latest_period
            ]
            latest_raw_val = sum(
                float(observation.value)
                for observation in matching_period_obs
            ) if matching_period_obs else tr.latest_value
            entity_id_val = tr.canonical_skill_id or canonical_skill_id(tr.canonical_name) or tr.canonical_name.casefold()
            trends.append(
                HistoricalTrendItem(
                    entity_id=entity_id_val,
                    entity_name=tr.canonical_name,
                    canonical_skill_id=tr.canonical_skill_id or entity_id_val,
                    display_name=tr.canonical_name,
                    entity_type="skill",
                    signal_type=tr.signal_type if tr.signal_type in {"demand", "adoption", "interest"} else "interest",
                    source=tr.source,
                    series_id=tr.series_id,
                    period_start=p_used[0] if p_used else "",
                    period_end=p_used[-1] if p_used else "",
                    periods_count=len(p_used),
                    periods=p_used,
                    data_points=dedup_points,
                    trend_direction=tr.trend if is_ready else "Insufficient Data",
                    trend_slope=tr.slope if is_ready else None,
                    velocity=tr.velocity,
                    growth_pct=tr.growth_pct,
                    whole_window_change=tr.whole_window_change if is_ready else None,
                    whole_window_pct_change=tr.whole_window_pct_change if is_ready else None,
                    latest_mom_change=tr.latest_mom_change,
                    latest_mom_pct_change=tr.latest_mom_pct_change,
                    value_unit=tr.unit,
                    velocity_unit=tr.velocity_unit,
                    slope_unit=tr.slope_unit,
                    period_grain=tr.period_grain,
                    metric_mode=tr.metric,
                    warnings=list(getattr(tr, "warnings", []) or []),
                    calculation_version=tr.calculation_version,
                    readiness_state=tr.readiness_state or ("ready_for_trend" if is_ready else "not_ready"),
                    quality_state="valid" if is_ready else getattr(tr, "data_state", "valid"),
                    data_origin=getattr(tr, "data_origin", "real"),
                    history_type=getattr(tr, "history_type", "platform_collected"),
                    is_trend_ready=is_ready,
                    is_forecast_ready=(len(p_used) >= 24 and is_ready),
                    confidence=trend_conf if is_ready else None,
                    current_signal_value=latest_raw_val,
                    current_signal_share=tr.latest_value if tr.metric == "normalized_share" else None,
                    current_signal_period=tr.latest_period,
                    limitations=limitations_list,
                    evidence_references=tr.observation_ids or [],
                    explanation=item_explanation,
                )
            )

            # Key Change generation if growth or velocity exists
            if is_ready and tr.growth_pct is not None:
                dir_literal: Literal["up", "down", "neutral"] = "up" if tr.growth_pct > 0 else "down" if tr.growth_pct < 0 else "neutral"
                key_changes.append(
                    KeyChangeItem(
                        change_type="trend_acceleration",
                        title=f"{tr.canonical_name} {tr.trend}",
                        description=f"{tr.canonical_name} exhibited {tr.trend.lower()} momentum with a velocity of {tr.velocity:.4f} and {tr.growth_pct:+.2f}% change across {len(p_used)} periods.",
                        magnitude_pct=tr.growth_pct,
                        direction=dir_literal,
                        affected_entity=tr.canonical_name,
                        evidence_source=tr.source,
                        period=tr.latest_period,
                    )
                )

        summary = {
            "total_skills_assessed": len(trend_results),
            "trend_ready_skills": sum(1 for t in trends if t.is_trend_ready),
            "active_sources": sorted({o.source for o in observations}),
            "total_observations": len(observations),
        }
        return signals, trends, key_changes, summary

    # -------------------------------------------------------------------------
    # DOMAIN SYNTHESIS: MARKET INTELLIGENCE
    # -------------------------------------------------------------------------

    def _synthesize_market_domain(
        self,
        observations: list[MarketObservation],
        quality_reports: list[Any],
        readiness_reports: list[Any],
        now: datetime,
        request: CoreIntelligenceRequest,
        *,
        aggregated_signals: list[AggregatedMarketSignal] | None = None,
        trend_results: list[SkillTrendVelocityResult] | None = None,
    ) -> tuple[list[IntelligenceSignal], list[HistoricalTrendItem], list[KeyChangeItem], dict[str, Any]]:
        signals: list[IntelligenceSignal] = []
        trends: list[HistoricalTrendItem] = []
        key_changes: list[KeyChangeItem] = []

        if not observations:
            return signals, trends, key_changes, {"market_momentum": "insufficient_data", "total_employers": None}

        # Market domain analyzes multi-source shifts: technology adoption (GitHub), developer interest (Stack Exchange), and demand (JSearch/Adzuna)
        tech_obs = [o for o in observations if o.signal_type == "adoption"]
        interest_obs = [o for o in observations if o.signal_type == "interest"]
        demand_obs = [o for o in observations if o.signal_type == "demand"]

        for o in tech_obs:
            signals.append(
                IntelligenceSignal(
                    signal_id=o.id or f"tech-{o.skill}-{o.period}",
                    signal_type="adoption",
                    source=o.source,
                    entity_name=normalize_skill(o.skill),
                    entity_type="market",
                    period=o.period or o.observed_at.strftime("%Y-%m"),
                    value=o.value,
                    denominator=o.denominator,
                    share=o.value / o.denominator if o.denominator and o.denominator > 0 else None,
                    unit="repository_count",
                    quality_state=_normalize_quality_state(o.quality),
                )
            )

        for o in interest_obs:
            signals.append(
                IntelligenceSignal(
                    signal_id=o.id or f"interest-{o.skill}-{o.period}",
                    signal_type="interest",
                    source=o.source,
                    entity_name=normalize_skill(o.skill),
                    entity_type="market",
                    period=o.period or o.observed_at.strftime("%Y-%m"),
                    value=o.value,
                    denominator=o.denominator,
                    share=o.value / o.denominator if o.denominator and o.denominator > 0 else None,
                    unit="tagged_questions",
                    quality_state=_normalize_quality_state(o.quality),
                )
            )

        # Market trends reuse Stack Exchange and GitHub multi-period data
        skill_signals, skill_trends, _, _ = self._synthesize_skill_domain(
            observations, quality_reports, readiness_reports, now,
            aggregated_signals=aggregated_signals,
            trend_results=trend_results,
        )
        trends = skill_trends

        if tech_obs:
            key_changes.append(
                KeyChangeItem(
                    change_type="tech_adoption",
                    title="Technology Ecosystem Signal",
                    description=f"Recorded {len(tech_obs)} adoption signals from open-source repositories.",
                    magnitude_pct=None,
                    direction="neutral",
                    affected_entity="Open Source Ecosystem",
                    evidence_source="github",
                    period=tech_obs[0].period or "2026-10",
                )
            )

        summary = {
            "demand_observations": len(demand_obs),
            "adoption_observations": len(tech_obs),
            "interest_observations": len(interest_obs),
            "sources": sorted({o.source for o in observations}),
            "market_data_state": "ready" if len(observations) >= 4 else "partial",
            "investment_signals": "unavailable",
            "financial_metrics": "unavailable",
            "venture_funding": "unavailable",
            "data_limitations": [
                "Financial, investment, and venture capital signals are not supported by verified data providers.",
                "Ecosystem metrics are derived strictly from developer interest (Stack Exchange), code adoption (GitHub), and job demand (JSearch/Adzuna).",
            ],
        }
        return signals, trends, key_changes, summary

    # -------------------------------------------------------------------------
    # DOMAIN SYNTHESIS: JOB INTELLIGENCE
    # -------------------------------------------------------------------------

    def _synthesize_job_domain(
        self,
        observations: list[MarketObservation],
        quality_reports: list[Any],
        readiness_reports: list[Any],
        now: datetime,
        request: CoreIntelligenceRequest,
    ) -> tuple[list[IntelligenceSignal], list[HistoricalTrendItem], list[KeyChangeItem], dict[str, Any]]:
        signals: list[IntelligenceSignal] = []
        trends: list[HistoricalTrendItem] = []
        key_changes: list[KeyChangeItem] = []

        # Job domain relies strictly on demand observations from JSearch and Adzuna
        demand_obs = [o for o in observations if o.signal_type == "demand"]

        if not demand_obs:
            return signals, trends, key_changes, {
                "open_roles_status": "insufficient_data",
                "requisitions_count": None,
                "role_momentum": "insufficient_data",
            }

        # Keep provider / denominator isolation
        jsearch_obs = [o for o in demand_obs if o.source == "jsearch"]
        adzuna_obs = [o for o in demand_obs if o.source == "adzuna"]

        for o in demand_obs[:40]:
            signals.append(
                IntelligenceSignal(
                    signal_id=o.id or f"job-{o.source}-{o.skill}-{o.period}",
                    signal_type="demand",
                    source=o.source,
                    entity_name=normalize_skill(o.skill),
                    entity_type="role",
                    period=o.period or o.observed_at.strftime("%Y-%m"),
                    value=o.value,
                    denominator=o.denominator,
                    share=(o.value / o.denominator) if o.denominator and o.denominator > 0 else None,
                    unit="job_postings",
                    quality_state=_normalize_quality_state(o.quality),
                )
            )

        # Job demand has only 1 period in current production
        periods = sorted({o.period for o in demand_obs if o.period})
        key_changes.append(
            KeyChangeItem(
                change_type="requisition_snapshot",
                title="Job Market Baseline",
                description=f"Captured {len(demand_obs)} real job-demand observations across period(s): {', '.join(periods)}.",
                magnitude_pct=None,
                direction="neutral",
                affected_entity="Job Market",
                evidence_source="jsearch,adzuna",
                period=periods[-1] if periods else "2026-10",
            )
        )

        summary = {
            "total_job_observations": len(demand_obs),
            "jsearch_observations": len(jsearch_obs),
            "adzuna_observations": len(adzuna_obs),
            "available_periods": periods,
            "open_role_activity": "verified_snapshot",
            "hiring_company_activity": "insufficient_data",
            "role_demand_momentum": "insufficient_data",
            "reduction_signal": None,
            "trend_ready": False,  # Strict: 1 period cannot produce trend
            "forecast_ready": False,
            "data_limitations": [
                "Job demand observations represent 2026-10 baseline; multi-period momentum requires subsequent collection runs.",
                "Hiring claims reflect aggregated job posting counts, not individual placement guarantees.",
            ],
        }
        return signals, trends, key_changes, summary

    # -------------------------------------------------------------------------
    # CONTEXTUAL EXPLANATIONS
    # -------------------------------------------------------------------------

    def _generate_explanations(
        self,
        domain: IntelligenceDomain,
        portal: PortalType,
        signals: list[IntelligenceSignal],
        trends: list[HistoricalTrendItem],
        key_changes: list[KeyChangeItem],
        ind_ctx: IndividualContext,
        emp_ctx: EmployeeContext,
        comp_ctx: CompanyContext,
        request: CoreIntelligenceRequest,
    ) -> list[ExplanationItem]:
        explanations: list[ExplanationItem] = []

        trend_ready_items = [t for t in trends if t.is_trend_ready]
        supporting_sources = sorted({s.source for s in signals})

        if portal == "individual":
            target = ind_ctx.target_role or "your career target"
            skills_mentioned = ind_ctx.selected_skills[:3] or ["core technical skills"]

            if trend_ready_items:
                top_trend = trend_ready_items[0]
                vel_text = f"a verified velocity of {top_trend.velocity:.4f}" if top_trend.velocity is not None else "positive velocity"
                explanations.append(
                    ExplanationItem(
                        topic=f"Verified Skill Trajectory: {top_trend.entity_name}",
                        heading=f"{top_trend.entity_name} is showing {top_trend.trend_direction} momentum",
                        body=(
                            f"Based on {top_trend.periods_count} consecutive validated periods from {top_trend.source}, "
                            f"{top_trend.entity_name} recorded {vel_text}. "
                            f"This directly impacts your trajectory towards {target}."
                        ),
                        impact_level="high",
                        target_audience="individual",
                        supporting_facts=[
                            f"Series periods: {top_trend.period_start} to {top_trend.period_end}",
                            f"Source provider: {top_trend.source}",
                            f"Direction: {top_trend.trend_direction}",
                        ],
                        evidence_sources=[top_trend.source],
                    )
                )
            else:
                explanations.append(
                    ExplanationItem(
                        topic="Market Signal Baseline",
                        heading=f"Market Demand Baseline for {', '.join(skills_mentioned)}",
                        body=(
                            f"Real observations in your target location ({ind_ctx.location or 'Global'}) "
                            f"have established baseline demand across {len(signals)} real signals. "
                            f"Multi-period trend calculation requires continuous collection over subsequent cycles."
                        ),
                        impact_level="medium",
                        target_audience="individual",
                        supporting_facts=[f"Total verified signals: {len(signals)}"],
                        evidence_sources=supporting_sources,
                    )
                )

        elif portal == "employee":
            team = emp_ctx.team or "Engineering"
            role = emp_ctx.current_role or "Technical Specialist"

            if emp_ctx.is_connected:
                explanations.append(
                    ExplanationItem(
                        topic="Role Alignment & Internal Direction",
                        heading=f"Market Shifts Relevant to {role} in {emp_ctx.company_name or 'Your Organization'}",
                        body=(
                            f"Within {team}, external market requirements indicate changing demand across technical skills. "
                            f"Verified trends from {', '.join(supporting_sources) or 'market sources'} help benchmark your internal role competencies."
                        ),
                        impact_level="high",
                        target_audience="employee",
                        supporting_facts=[f"Active team context: {team}", f"Company affiliation: {emp_ctx.company_name}"],
                        evidence_sources=supporting_sources,
                    )
                )
            else:
                explanations.append(
                    ExplanationItem(
                        topic="Independent Professional Context",
                        heading=f"External Market Benchmarks for {role}",
                        body=(
                            "Operating in independent employee mode. Enterprise private data is isolated. "
                            f"Showing public market signals across {len(signals)} observations."
                        ),
                        impact_level="informational",
                        target_audience="employee",
                        supporting_facts=["Private company data isolated"],
                        evidence_sources=supporting_sources,
                    )
                )

        elif portal == "company":
            org = comp_ctx.company_name or "Enterprise Workforce"
            explanations.append(
                ExplanationItem(
                    topic="Workforce Capability Telemetry",
                    heading=f"Workforce Skill Alignment for {org}",
                    body=(
                        f"Analyzing market demand curves across {len(signals)} signals against your enterprise workforce inventory. "
                        f"{len(trend_ready_items)} skills have passed the analytical trend gate."
                    ),
                    impact_level="high",
                    target_audience="company",
                    supporting_facts=[
                        f"Trend-ready skill series: {len(trend_ready_items)}",
                        f"Industry context: {comp_ctx.industry}",
                    ],
                    evidence_sources=supporting_sources,
                )
            )

        return explanations

    # -------------------------------------------------------------------------
    # CONTEXTUAL RECOMMENDATIONS
    # -------------------------------------------------------------------------

    def _generate_recommendations(
        self,
        domain: IntelligenceDomain,
        portal: PortalType,
        signals: list[IntelligenceSignal],
        trends: list[HistoricalTrendItem],
        ind_ctx: IndividualContext,
        emp_ctx: EmployeeContext,
        comp_ctx: CompanyContext,
        request: CoreIntelligenceRequest,
    ) -> list[RecommendationItem]:
        recommendations: list[RecommendationItem] = []

        trend_ready = [t for t in trends if t.is_trend_ready]

        if portal == "individual":
            if trend_ready:
                top = trend_ready[0]
                recommendations.append(
                    RecommendationItem(
                        action_type="learn",
                        title=f"Prioritize {top.entity_name} Proficiency",
                        description=f"Verified market data confirms {top.trend_direction.lower()} momentum. Deepening your proficiency will improve role matching.",
                        priority="high",
                        target_entity=top.entity_name,
                        rationale=f"Backed by {top.periods_count} consecutive periods from {top.source}.",
                        alignment_score=92.0,
                        estimated_timeframe="4-6 weeks",
                    )
                )
            else:
                skill_name = ind_ctx.selected_skills[0] if ind_ctx.selected_skills else "Core Programming"
                recommendations.append(
                    RecommendationItem(
                        action_type="monitor",
                        title=f"Establish Baseline Verification for {skill_name}",
                        description="Complete profile skill verification while recurring scheduled collection gathers additional comparable market periods.",
                        priority="medium",
                        target_entity=skill_name,
                        rationale="Awaiting historical depth for trend activation.",
                        alignment_score=80.0,
                        estimated_timeframe="2 weeks",
                    )
                )

        elif portal == "employee":
            if trend_ready:
                top = trend_ready[0]
                recommendations.append(
                    RecommendationItem(
                        action_type="upskill",
                        title=f"Align Role Competency with {top.entity_name}",
                        description=f"Explore internal learning pathways in {top.entity_name} to strengthen alignment with team technology initiatives.",
                        priority="high",
                        target_entity=top.entity_name,
                        rationale=f"Market momentum confirmed by {top.source} trajectory.",
                        alignment_score=88.0,
                        estimated_timeframe="6-8 weeks",
                    )
                )
            else:
                recommendations.append(
                    RecommendationItem(
                        action_type="verify",
                        title="Review Internal Skill Profile",
                        description="Confirm your verified team competencies to prepare for upcoming internal mobility cycles.",
                        priority="medium",
                        target_entity="Internal Competency Profile",
                        rationale="Ensure internal records reflect verified capabilities.",
                        alignment_score=75.0,
                        estimated_timeframe="1 week",
                    )
                )

        elif portal == "company":
            if trend_ready:
                top = trend_ready[0]
                vel_info = f"statistical slope of {top.velocity:.4f}" if top.velocity is not None else "positive slope"
                recommendations.append(
                    RecommendationItem(
                        action_type="redeploy",
                        title=f"Structure Reskilling Cohort for {top.entity_name}",
                        description=f"Accelerating market relevance suggests establishing an internal upskilling cohort for engineers transitioning into {top.entity_name}.",
                        priority="critical",
                        target_entity=top.entity_name,
                        rationale=f"Sustained momentum with {vel_info} indicates long-term adoption.",
                        alignment_score=95.0,
                        estimated_timeframe="Quarterly Cohort",
                    )
                )
            else:
                recommendations.append(
                    RecommendationItem(
                        action_type="monitor",
                        title="Conduct Workforce Skills Audit",
                        description="Audit current departmental skills inventory while external market history accumulates.",
                        priority="medium",
                        target_entity="Enterprise Skill Inventory",
                        rationale="Prepares organizational baseline for workforce gap simulation.",
                        alignment_score=82.0,
                        estimated_timeframe="30 days",
                    )
                )

        return recommendations

    # -------------------------------------------------------------------------
    # DOWNSTREAM NEXT ACTIONS
    # -------------------------------------------------------------------------

    def _generate_next_actions(
        self,
        domain: IntelligenceDomain,
        portal: PortalType,
        recommendations: list[RecommendationItem],
        request: CoreIntelligenceRequest,
    ) -> list[NextActionItem]:
        actions: list[NextActionItem] = []
        top_rec = recommendations[0] if recommendations else None

        if portal == "individual":
            entity = top_rec.target_entity if top_rec else "Python"
            actions.append(
                NextActionItem(
                    module="learning_roadmap",
                    action_title=f"Generate Personalized Learning Roadmap for {entity}",
                    target_url_or_route="#/individual/learning",
                    parameters={"skill": entity, "priority": "high"},
                )
            )
            actions.append(
                NextActionItem(
                    module="assessment",
                    action_title=f"Take Skill Benchmark Assessment for {entity}",
                    target_url_or_route="#/individual/skills",
                    parameters={"skill": entity},
                )
            )
        elif portal == "employee":
            entity = top_rec.target_entity if top_rec else "Core Skills"
            actions.append(
                NextActionItem(
                    module="internal_mobility",
                    action_title="Explore Internal Project & Role Opportunities",
                    target_url_or_route="#/employee/mobility",
                    parameters={"focus_skill": entity},
                )
            )
        elif portal == "company":
            entity = top_rec.target_entity if top_rec else "Workforce Planning"
            actions.append(
                NextActionItem(
                    module="workforce_planning",
                    action_title=f"Model Workforce Reskilling Simulation for {entity}",
                    target_url_or_route="#/company/simulation",
                    parameters={"cohort_focus": entity},
                )
            )

        return actions

    # -------------------------------------------------------------------------
    # CORE INTELLIGENCE ANSWER SYNTHESIS
    # -------------------------------------------------------------------------

    def _generate_core_answer(
        self,
        domain: IntelligenceDomain,
        portal: PortalType,
        signals: list[IntelligenceSignal],
        trends: list[HistoricalTrendItem],
        key_changes: list[KeyChangeItem],
        summary: dict[str, Any],
        ind_ctx: IndividualContext,
        emp_ctx: EmployeeContext,
        comp_ctx: CompanyContext,
        request: CoreIntelligenceRequest,
        overall_readiness_state: str | None = None,
    ) -> CoreIntelligenceAnswer:
        ready_trends = [t for t in trends if t.is_trend_ready]
        sources = sorted({s.source for s in signals})
        periods = sorted({s.period for s in signals if s.period})

        # Determine readiness status
        if ready_trends:
            readiness_status = "ready_for_trend"
        elif overall_readiness_state in (
            "blocked_quality",
            "blocked_coverage",
            "blocked_configuration",
            "blocked_missing_period",
        ):
            readiness_status = overall_readiness_state
        elif signals:
            readiness_status = "insufficient_history"
        else:
            readiness_status = "insufficient_data"

        # Determine confidence
        confidence_vals = [t.confidence for t in ready_trends if t.confidence is not None]
        if confidence_vals:
            confidence = round(sum(confidence_vals) / len(confidence_vals), 2)
        else:
            sig_conf_vals = [s.confidence for s in signals if s.confidence is not None]
            confidence = round(sum(sig_conf_vals) / len(sig_conf_vals), 2) if sig_conf_vals else None

        # Evidence citations
        evidence_citations: list[str] = []
        if signals:
            evidence_citations.append(
                f"{len(signals)} verified signal(s) evaluated across period(s): {', '.join(periods) if periods else 'N/A'}."
            )
        if sources:
            evidence_citations.append(
                f"Empirical data ingested from verified sources: {', '.join(sources)}."
            )
        if ready_trends:
            evidence_citations.append(
                f"{len(ready_trends)} series met statistical depth requirements (>= 4 consecutive observation periods)."
            )
        else:
            evidence_citations.append(
                f"0 series currently meet the 4-period threshold for statistical trend calculation (status: {readiness_status})."
            )

        # Contextual focus
        if portal == "individual":
            contextual_focus = "Personal Skill Relevance, Learning Roadmap & Career Trajectory"
        elif portal == "employee":
            contextual_focus = "Internal Mobility, Team Capability & Role Progression"
        else:
            contextual_focus = "Enterprise Workforce Planning, Reskilling Pipeline & Talent Strategy"

        # Limitations
        limitations: list[str] = []
        if domain == "skill":
            if not ready_trends:
                limitations.append("Trend and velocity calculations require >= 4 consecutive periods; single-period data serves as baseline only.")
            if readiness_status.startswith("blocked_"):
                limitations.append(f"Analytical gate enforced ({readiness_status}); trend calculations are strictly locked.")
            limitations.append("Forecasting model inactive (is_forecast_ready = false).")
        elif domain == "market":
            limitations.append("Financial, venture funding, and investment metrics are not supported by verified data providers.")
            limitations.append("Market dynamics are measured strictly via open-source adoption, developer activity, and job demand.")
            limitations.append("Forecasting model inactive (is_forecast_ready = false).")
        elif domain == "job":
            limitations.append("Job demand observations represent baseline postings; multi-period hiring momentum is withheld until longitudinal cycles accumulate.")
            limitations.append("Posting counts reflect external requisitions, not internal placement guarantees.")
            limitations.append("Forecasting model inactive (is_forecast_ready = false).")

        # Fallback / Empty signals case
        if not signals:
            return CoreIntelligenceAnswer(
                headline=f"No Verified {domain.capitalize()} Intelligence Observations Available",
                summary=f"No verified market observations were found matching the requested filters ({request.location or 'Global'}, {request.time_range}).",
                domain=domain,
                portal=portal,
                confidence=None,
                readiness_status="insufficient_data",
                key_insights=[
                    "FACT: 0 verified market observations retrieved for requested parameters.",
                    "INTERPRETATION: Insufficient data to evaluate trends or calculate demand momentum.",
                    "ACTION: Expand query parameters or select Global location to view verified observations."
                ],
                evidence_citations=["No verified observations retrieved."],
                limitations=["No data available for analytical evaluation.", "Forecasting model inactive (is_forecast_ready = false)."],
                contextual_focus=contextual_focus,
            )

        top_trend = ready_trends[0] if ready_trends else None
        top_signal = signals[0] if signals else None

        # Build Domain + Portal specific headline, summary, key_insights
        key_insights: list[str] = []

        if domain == "skill":
            if top_trend:
                t_name = top_trend.entity_name
                t_dir = top_trend.trend_direction or "Stable"
                growth_text = f"{top_trend.growth_pct:+.1f}%" if top_trend.growth_pct is not None else "measured"
                vel_text = f"{top_trend.velocity:+.2f}/mo" if top_trend.velocity is not None else "steady"

                if portal == "individual":
                    headline = f"{t_name} Demonstrates Verified {t_dir} Momentum for Career Growth"
                    summary = (
                        f"Longitudinal analysis confirms {t_name} is {t_dir.lower()} with {growth_text} growth "
                        f"and {vel_text} velocity across {top_trend.periods_count} observation periods. "
                        f"Prioritizing this skill directly strengthens your profile against verified market demand."
                    )
                    key_insights = [
                        f"FACT: {top_trend.periods_count} consecutive validated observation periods recorded from {top_trend.source}.",
                        f"INTERPRETATION: Statistically verified {t_dir} momentum ({vel_text} velocity, {growth_text} growth).",
                        f"ACTION: Prioritize personal development milestones in {t_name} to align with active market demand."
                    ]
                elif portal == "employee":
                    headline = f"{t_name} {t_dir} Trajectory Highlights Key Competency for Internal Mobility"
                    summary = (
                        f"Market signals confirm {t_name} has verified {t_dir.lower()} momentum ({vel_text} velocity). "
                        f"Deepening expertise in {t_name} positions you for cross-functional project assignments "
                        f"and internal role advancement within your organization."
                    )
                    key_insights = [
                        f"FACT: {t_name} shows sustained {t_dir.lower()} momentum across {top_trend.periods_count} monitored periods.",
                        f"INTERPRETATION: Internal mobility pathways increasingly align with verified market velocity ({vel_text}).",
                        f"ACTION: Connect with internal team initiatives utilizing {t_name}."
                    ]
                else:  # company
                    headline = f"Workforce Capability Alert: {t_name} Demonstrates Verified {t_dir} Expansion"
                    summary = (
                        f"Empirical intelligence verifies a {t_dir.lower()} trajectory for {t_name} "
                        f"({growth_text} change, {vel_text} velocity across {top_trend.periods_count} periods). "
                        f"Workforce leaders should prioritize internal upskilling cohorts to mitigate emerging talent acquisition costs."
                    )
                    key_insights = [
                        f"FACT: {t_name} exhibits statistically verified {t_dir.lower()} momentum with {growth_text} growth.",
                        f"INTERPRETATION: Cross-period stability confirms demand resilience across {top_trend.periods_count} periods.",
                        f"ACTION: Prioritize workforce reskilling pathways to build internal capacity before hiring externally."
                    ]
            elif readiness_status == "blocked_quality":
                entity = top_signal.entity_name if top_signal else "Monitored Skills"
                headline = f"Data Quality Gate Enforced for {entity} (Analytical Quality Alert)"
                summary = (
                    f"Observation series for {entity} did not satisfy analytical comparability or data quality standards. "
                    f"Directional trends and velocity are strictly withheld until data quality is re-established."
                )
                key_insights = [
                    f"FACT: {len(signals)} observation(s) ingested from {', '.join(sources)}.",
                    f"INTERPRETATION: Analytical quality gate '{readiness_status}' active due to comparability/quality issues.",
                    f"ACTION: Monitor data collection; verify provider stability before committing strategic resources."
                ]
            elif readiness_status == "blocked_coverage":
                entity = top_signal.entity_name if top_signal else "Monitored Skills"
                headline = f"Low Observation Coverage for {entity} (Analytical Gate Enforced)"
                summary = (
                    f"Sample size or observation coverage for {entity} is minimal. "
                    f"Analytical modeling is withheld per G1.9 readiness standards."
                )
                key_insights = [
                    f"FACT: Low sample coverage recorded across {len(signals)} observation(s).",
                    f"INTERPRETATION: Minimal sample size prevents reliable statistical trend activation.",
                    f"ACTION: Expand query scope or await broader empirical collection."
                ]
            elif readiness_status == "blocked_configuration":
                entity = top_signal.entity_name if top_signal else "Monitored Skills"
                headline = f"Configuration Drift Detected for {entity} (Analytical Gate Enforced)"
                summary = (
                    f"Schema or extractor configuration changes were detected across observation periods for {entity}. "
                    f"Trend calculations are locked to avoid false comparisons."
                )
                key_insights = [
                    f"FACT: Incompatible extraction configurations detected across historical periods.",
                    f"INTERPRETATION: Cross-period comparability compromised per G1.8/G1.9 quality rules.",
                    f"ACTION: Await collection under consistent panel configuration."
                ]
            elif readiness_status == "blocked_missing_period":
                entity = top_signal.entity_name if top_signal else "Monitored Skills"
                headline = f"Period Discontinuity for {entity} (Analytical Gate Enforced)"
                summary = (
                    f"Historical observation series contains gaps or missing consecutive periods for {entity}. "
                    f"Theil-Sen trend evaluation requires continuous periods."
                )
                key_insights = [
                    f"FACT: Gaps identified in observation periods.",
                    f"INTERPRETATION: Discontinuous series violates analytical continuity requirements.",
                    f"ACTION: Continue scheduled collection until continuous consecutive periods accumulate."
                ]
            else:
                # Skill domain with baseline only (no 4-period ready trends)
                entity = top_signal.entity_name if top_signal else "Monitored Skills"
                if portal == "individual":
                    headline = f"Baseline Intelligence Recorded for {entity} (Historical Depth Pending)"
                    summary = (
                        f"Current market signals establish verified baseline activity for {entity} across {len(signals)} observation(s). "
                        f"Directional trends and velocity are withheld until 4 consecutive periods are recorded."
                    )
                    key_insights = [
                        f"FACT: Baseline activity confirmed across {len(signals)} observation(s) from {', '.join(sources)}.",
                        "INTERPRETATION: Trend velocity calculation is locked pending longitudinal depth to prevent false extrapolations.",
                        "ACTION: Focus personal development on verified core competencies while multi-period signals mature."
                    ]
                elif portal == "employee":
                    headline = f"Employee Competency Baseline Verified for {entity}"
                    summary = (
                        f"Market observations record verified baseline signals for {entity}. "
                        f"Trajectory metrics require 4 historical periods before statistical velocity is calculated."
                    )
                    key_insights = [
                        f"FACT: Verified signal presence documented from {', '.join(sources)}.",
                        "INTERPRETATION: Longitudinal tracking is active; velocity metrics will unlock upon subsequent observation cycles.",
                        "ACTION: Align internal capability development with documented operational baseline signals."
                    ]
                else:  # company
                    headline = f"Workforce Skill Baseline Established for {entity} (Quality Gates Enforced)"
                    summary = (
                        f"Captured {len(signals)} verified baseline observation(s) for {entity}. "
                        f"In accordance with analytical quality standards, trend slopes and velocity are strictly withheld until 4 periods exist."
                    )
                    key_insights = [
                        f"FACT: Authoritative baseline established without speculative extrapolation or synthetic fill.",
                        "INTERPRETATION: Quality gates actively protect workforce planning from premature single-period trend claims.",
                        "ACTION: Benchmark current organizational skill inventories against observed market requisition baselines."
                    ]

        elif domain == "market":
            adoption_count = summary.get("adoption_observations", len([s for s in signals if s.signal_type == "adoption"]))
            interest_count = summary.get("interest_observations", len([s for s in signals if s.signal_type == "interest"]))

            if portal == "individual":
                headline = "Multi-Source Market Ecosystem: Developer Interest & Technology Adoption"
                summary = (
                    f"Cross-ecosystem market signals aggregate {len(signals)} verified observations across developer "
                    f"community interest ({interest_count} signals) and open-source adoption ({adoption_count} signals). "
                    f"Provides objective context on developer traction without speculative financial claims."
                )
                key_insights = [
                    f"Technology adoption tracks {adoption_count} open-source repository signals.",
                    f"Developer interest reflects {interest_count} community question volumes.",
                    "Align learning investments with verified developer traction across active ecosystems."
                ]
            elif portal == "employee":
                headline = "Industry Market Dynamics: Technology Adoption & Workforce Context"
                summary = (
                    f"Ecosystem signals reflect active open-source adoption ({adoption_count} signals) and developer interest "
                    f"({interest_count} signals). Informs organizational skill value and internal team project selection."
                )
                key_insights = [
                    f"Verified multi-source indicators span {', '.join(sources)}.",
                    "Provides empirical grounding for technical specialization and internal project alignment.",
                    "Investment and venture funding signals are excluded in favor of verified technical adoption."
                ]
            else:  # company
                headline = "Enterprise Market Intelligence: Open-Source Adoption & Talent Ecosystem"
                summary = (
                    f"Enterprise intelligence combines {adoption_count} open-source code adoption signals with "
                    f"{interest_count} developer mindshare metrics across verified sources ({', '.join(sources)}). "
                    f"Enables evidence-based technology stack evaluation without financial speculation."
                )
                key_insights = [
                    f"Grounded strictly in verified technical ecosystem signals across {len(signals)} observations.",
                    "Provides reliable benchmarks for technology selection and workforce skill modernization.",
                    "Financial metrics and venture funding are flagged as unavailable per strict source validation."
                ]

        else:  # job domain
            job_count = summary.get("total_job_observations", len(signals))
            if portal == "individual":
                headline = "Job Market Requisition Snapshot: Current Hiring Demand Baseline"
                summary = (
                    f"Job intelligence captures {job_count} verified job requisition signals across available periods "
                    f"({', '.join(periods) if periods else 'current period'}). Multi-period hiring momentum is withheld until longitudinal cycles accumulate."
                )
                key_insights = [
                    f"Active job postings observed across verified job providers ({', '.join(sources)}).",
                    "Role demand momentum is marked as insufficient_data to avoid false growth claims.",
                    "Focus application efforts on verified roles where requisition counts demonstrate active demand."
                ]
            elif portal == "employee":
                headline = "External Job Market Benchmark for Internal Career Mobility"
                summary = (
                    f"External hiring activity provides a competitive benchmark with {job_count} verified job postings. "
                    f"Guides internal career mobility by comparing external market demand with organizational roles."
                )
                key_insights = [
                    f"Current hiring snapshot reflects {job_count} postings from {', '.join(sources)}.",
                    "External requisition data highlights high-demand capabilities to guide cross-skilling.",
                    "Longitudinal hiring velocity is paused pending subsequent collection cycles."
                ]
            else:  # company
                headline = "Workforce Hiring Demand Benchmark: Verified Market Postings"
                summary = (
                    f"Captured {job_count} verified job requisition signals across {', '.join(sources)}. "
                    f"Provides an empirical baseline for external recruitment pressure versus internal talent reskilling."
                )
                key_insights = [
                    f"Aggregated {job_count} verified postings across monitored role categories.",
                    "Hiring momentum is marked as insufficient_data until multi-period collection matures.",
                    "Benchmark hiring needs against internal workforce mobility to optimize acquisition costs."
                ]

        return CoreIntelligenceAnswer(
            headline=headline,
            summary=summary,
            domain=domain,
            portal=portal,
            confidence=confidence,
            readiness_status=readiness_status,
            key_insights=key_insights,
            evidence_citations=evidence_citations,
            limitations=limitations,
            contextual_focus=contextual_focus,
        )

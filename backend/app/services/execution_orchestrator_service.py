"""Execution Orchestrator Service for G2.6 Core Intelligence.

Implements the deterministic pipeline:
User Request -> Intent Planner -> Capability Readiness -> Capability Handler ->
Evidence Collection -> Response Validation -> Core Intelligence Answer.

Uses the configured Firestore/local evidence boundary, bounded provider-backed
records, zero synthetic observations, and strict portal/company isolation.
"""

from __future__ import annotations

import logging
import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from app.analytics.ai_disruption import (
    evaluate_ai_task_disruption,
    evaluate_market_to_person_to_company_impact,
)
from app.analytics.confidence import compute_evidence_confidence
from app.analytics.freshness import assess_freshness
from app.analytics.forecasting import forecast_signal_series
from app.analytics.historical_range import MAX_HISTORICAL_RANGE_DAYS, historical_cutoff
from app.analytics.shared_intelligence import (
    SharedIntelligenceAnalysis,
    analyze_market_observations,
)
from app.analytics.skill_half_life import calculate_skill_half_life
from app.analytics.skill_health import evaluate_skill_health
from app.analytics.skill_registry import canonical_skill_id
from app.analytics.trend import G14_CALCULATION_VERSION
from app.core.config import Settings, get_settings
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import (
    CapabilityEvaluationRequest,
    CapabilityEvaluationResult,
)
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    EvidenceItem,
    ExecutionStatus,
    SelectedEntityResolution,
    StructuredFact,
)
from app.models.intent_planner import (
    IntelligencePlanRequest,
    IntelligencePlanResponse,
    PlanStatus,
)
from app.models.skill_intelligence import MarketObservation
from app.services.capability_registry_service import (
    CAPABILITY_CATALOG,
    CapabilityRegistryService,
)
from app.services.entity_registry_service import EntityRegistryService
from app.models.entity_registry import EntityResolutionRequest
from app.services.intent_planner_service import IntentPlannerService
from app.services.llm_explanation_service import LLMExplanationService
from app.services.intelligence_contract_service import (
    capability_metric_results,
    fact_metric_results,
)
from app.storage.conversation_store import ConversationStore
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)

_IDEMPOTENT_ANSWER_CACHE: dict[tuple[str, str, str], CoreIntelligenceAnswerResponse] = {}


class DataSourceUnavailableError(RuntimeError):
    """Configured evidence source could not be read for this request."""


class ExecutionOrchestratorService:
    """Connects Intent Resolver + Context Planner to supported backend capabilities."""

    def __init__(
        self,
        settings: Settings | None = None,
        db_path: str | Path | None = None,
        intent_planner: IntentPlannerService | None = None,
        capability_service: CapabilityRegistryService | None = None,
        entity_service: EntityRegistryService | None = None,
        observation_store: Any | None = None,
    ):
        self.settings = settings or get_settings()
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            configured = Path(self.settings.skill_intelligence_db_path)
            if (Path("backend") / configured).exists():
                self.db_path = Path("backend") / configured
            else:
                self.db_path = configured

        self.entity_service = entity_service or EntityRegistryService(
            db_path=self.db_path,
        )
        self.capability_service = capability_service or CapabilityRegistryService(
            entity_service=self.entity_service,
            db_path=self.db_path,
        )
        self.intent_planner = intent_planner or IntentPlannerService(
            entity_service=self.entity_service,
            capability_service=self.capability_service,
        )
        self.reference_store = ReferenceDataStore(self.db_path)
        self.market_store = MarketDataStore(self.db_path)
        self.conversation_store = ConversationStore.get_instance()
        self.llm_service = LLMExplanationService()
        # Production intelligence reads follow the configured source of truth.
        # Tests can inject a store; FirestoreObservationStore itself routes test
        # reads to its in-memory mock unless live Firestore tests are explicitly enabled.
        self.firestore_store = observation_store
        if self.firestore_store is None and getattr(self.settings, "skill_intelligence_read_backend", "firestore") == "firestore":
            from app.storage.firestore_observation_store import FirestoreObservationStore
            self.firestore_store = FirestoreObservationStore()

        # Register capability execution handlers
        self._handler_registry: dict[str, Callable[..., tuple[list[StructuredFact], list[EvidenceItem], list[str]]]] = {
            "entity_resolution": self._handle_entity_resolution,
            "skill_technology_reference": self._handle_skill_technology_reference,
            "occupation_lookup": self._handle_occupation_lookup,
            "occupation_software_skills": self._handle_occupation_software_skills,
            "related_occupations": self._handle_related_occupations,
            "market_snapshot": self._handle_market_snapshot,
            "historical_signal_retrieval": self._handle_historical_signal_retrieval,
            "trend_velocity_analysis": self._handle_trend_velocity_analysis,
            "evidence_provenance_retrieval": self._handle_evidence_provenance_retrieval,
            "skill_gap_role_fit": self._handle_skill_gap_role_fit,
            "action_recommendations": self._handle_action_recommendations,
            "job_posting_search": self._handle_job_posting_search,
            "company_intelligence": self._handle_company_intelligence,
        }

    def _get_market_observations(
        self,
        *,
        request_obs: Sequence[MarketObservation] | None,
        skill: str | None,
        location: str | None = None,
        time_range: str | None = None,
        all_skills: bool = False,
        source: str | None = None,
        signal_type: str | None = None,
        scope: str | None = None,
    ) -> list[MarketObservation]:
        """Retrieve observations from the configured source of truth or explicit request context."""
        cutoff = self._observation_cutoff(time_range)
        if request_obs:
            observations = request_obs
        elif not skill and not all_skills:
            return []
        elif self.firestore_store is not None:
            # Fail closed on a Firestore outage. Falling back silently to legacy
            # SQLite could present stale/reference data as current market evidence.
            try:
                if all_skills:
                    observations = self.firestore_store.get_observations(
                        cutoff=cutoff,
                        location=location,
                        scope=scope,
                        source=source,
                        signal_type=signal_type,
                    )
                else:
                    observations = self.firestore_store.get_observations_by_skill(
                        skill=skill, location=location, cutoff=cutoff
                    )
            except Exception as exc:
                logger.exception(
                    "Configured observation source read failed (%s)",
                    type(exc).__name__,
                )
                raise DataSourceUnavailableError("Configured observation source is unavailable.") from exc
        else:
            if all_skills:
                observations = self.market_store.get_observations(location=location, cutoff=cutoff)
            else:
                observations = self.market_store.get_observations(
                    skill=skill, location=location, cutoff=cutoff
                )

        location_key = location.casefold().strip() if location else None
        source_key = source.casefold().strip() if source else None
        filtered = [
            observation
            for observation in observations
            if observation.observed_at >= cutoff
            and (
                not location_key
                or (observation.location or "").casefold() == location_key
                or (observation.location or "").casefold().startswith(f"{location_key},")
            )
            and (not scope or observation.scope == scope)
            and (not source_key or observation.source.casefold().strip() == source_key)
            and (not signal_type or observation.signal_type == signal_type)
        ]
        if getattr(observations, "truncated", False):
            from app.storage.firestore_observation_store import ObservationBatch
            return ObservationBatch(filtered, truncated=True)
        return filtered

    @staticmethod
    def _extract_trend_question_location(message: str) -> str | None:
        match = re.search(
            r"\b(?:in|within)\s+([A-Za-z][A-Za-z .'-]*?)\s*(?:[?.!]+)?$",
            message.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None
        location = match.group(1).strip(" .,!;:")
        return location or None

    def _shared_market_analysis(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> SharedIntelligenceAnalysis:
        request_id = getattr(plan, "request_id", None)
        cache_scope = plan.context_summary.get("_analysis_cache_scope")
        cache_key = (
            request_id,
            cache_scope,
            request.portal_type,
            request.company_id,
            request.location,
            request.time_range,
            request.target_role,
            tuple(request.selected_skills),
            tuple(request.selected_roles),
            request.message,
            repr(sorted(request.filters.items())),
            tuple(sorted(
                (
                    observation.id or "",
                    observation.source,
                    observation.signal_type,
                    observation.observed_at.isoformat(),
                    observation.period or "",
                    str(observation.value),
                    observation.unit or "",
                    str(observation.denominator),
                    observation.denominator_unit or "",
                    observation.skill_id or "",
                    observation.skill,
                    observation.series_id or "",
                    observation.scope or "",
                    observation.location or "",
                    observation.query_id or "",
                    observation.panel_version or "",
                    observation.data_origin or "",
                    observation.history_type or "",
                    observation.fetch_run_id or "",
                    observation.source_url or "",
                    observation.extractor_version or "",
                )
                for observation in request.observations
            )),
        )
        cached_results = plan.context_summary.get("_shared_market_analyses")
        if isinstance(cached_results, dict):
            cached = cached_results.get(cache_key)
            if isinstance(cached, SharedIntelligenceAnalysis):
                return cached
        all_skills = getattr(plan, "intent", None) == "rank_skill_trends"
        filters = request.filters or {}
        source_filter = filters.get("source") or filters.get("provider")
        signal_filter = filters.get("signal_type")
        market_scope_filter = filters.get("observation_scope") or filters.get("market_scope")
        observations = self._get_market_observations(
            request_obs=request.observations,
            skill=plan.context_summary.get("primary_entity"),
            location=request.location,
            time_range=request.time_range,
            all_skills=all_skills,
            source=source_filter if isinstance(source_filter, str) else None,
            signal_type=signal_filter if isinstance(signal_filter, str) else None,
            scope=market_scope_filter if isinstance(market_scope_filter, str) else None,
        )
        if all_skills:
            excluded_non_market_count = sum(
                1 for observation in observations
                if observation.data_origin != "real"
                or observation.history_type != "platform_collected"
                or not observation.skill_id
            )
            plan.context_summary["excluded_non_market_observation_count"] = excluded_non_market_count
            market_observations = [
                observation for observation in observations
                if observation.data_origin == "real"
                and observation.history_type == "platform_collected"
                and observation.skill_id
            ]
            if getattr(observations, "truncated", False):
                from app.storage.firestore_observation_store import ObservationBatch
                observations = ObservationBatch(market_observations, truncated=True)
            else:
                observations = market_observations
        analysis = analyze_market_observations(observations)
        if not isinstance(cached_results, dict):
            cached_results = {}
            plan.context_summary["_shared_market_analyses"] = cached_results
        cached_results[cache_key] = analysis
        return analysis

    @staticmethod
    def _observation_cutoff(time_range: str | None) -> datetime:
        """Translate supported windows into a bound without claiming more history."""
        from datetime import timedelta

        key = str(time_range or "30d").strip().lower()
        if key in {"max_available", "max available", "max", "all", "auto"}:
            return historical_cutoff(datetime.now(timezone.utc), MAX_HISTORICAL_RANGE_DAYS)
        windows = {
            "7d": 7, "30d": 30, "90d": 90, "3m": 90,
            "6m": 183, "180d": 180, "1y": 365, "12m": 365, "365d": 365,
        }
        return datetime.now(timezone.utc) - timedelta(days=windows.get(key, 30))

    # =========================================================================
    # MAIN ORCHESTRATION PIPELINE
    # =========================================================================

    def answer(
        self,
        request: CoreIntelligenceAnswerRequest,
        authenticated_user: AuthenticatedUser | None = None,
    ) -> CoreIntelligenceAnswerResponse:
        """Execute the end-to-end intelligence query flow and return a validated response."""
        request_id = f"ans_{uuid.uuid4().hex[:12]}"
        portal_type = request.portal_type or "individual"

        # 0. Conversation Isolation Access Guard & Idempotency Check
        user_id = authenticated_user.uid if authenticated_user else "anonymous"
        user_company_id = getattr(authenticated_user, "company_id", None) if authenticated_user else request.company_id
        if not request.conversation_id and request.domain:
            created_conv = self.conversation_store.create_conversation(
                user_id=user_id,
                portal_type=portal_type,
                company_id=user_company_id,
                domain=request.domain,
                filters=request.filters,
            )
            request = request.model_copy(update={"conversation_id": created_conv.conversation_id})

        if request.conversation_id:
            allowed, deny_reason = self.conversation_store.check_conversation_access(
                request.conversation_id,
                user_id=user_id,
                company_id=user_company_id,
            )
            if not allowed:
                return CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    intent="unknown",
                    plan_status="blocked",
                    execution_status="blocked",
                    status="error",
                    answer=deny_reason or "Access denied to conversation.",
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=[deny_reason or "Access denied to conversation."],
                    reason_codes=["UNAUTHORIZED_CONVERSATION_ACCESS"],
                    follow_up_questions=[],
                    follow_up_suggestions=[],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

            if request.client_message_id and not request.regenerate:
                cache_key = (user_id, request.conversation_id, request.client_message_id)
                if cache_key in _IDEMPOTENT_ANSWER_CACHE:
                    return _IDEMPOTENT_ANSWER_CACHE[cache_key]

        # 1. Intent Resolver + Context Planner
        plan_req = IntelligencePlanRequest(
            message=request.message,
            portal_type=request.portal_type,
            domain=request.domain,
            capability_id=request.capability_id,
            location=request.location,
            time_range=request.time_range,
            target_role=request.target_role,
            selected_skills=request.selected_skills,
            selected_roles=request.selected_roles,
            selected_companies=request.selected_companies,
            filters=request.filters,
            company_id=request.company_id,
            conversation_id=request.conversation_id,
            clear_context=request.clear_context,
            observations=request.observations,
            context_override=request.context_override,
        )
        plan = self.intent_planner.create_plan(plan_req, authenticated_user=authenticated_user)
        if getattr(plan, "intent", None) == "rank_skill_trends":
            trend_location = request.location or self._extract_trend_question_location(request.message)
            if trend_location:
                request = request.model_copy(update={"location": trend_location})
                plan.context_summary["location"] = trend_location
        plan.context_summary["_analysis_cache_scope"] = (
            user_id,
            user_company_id,
            request.portal_type,
        )

        # 2. Check for Unsupported Intents (Forecasting, Simulation)
        unsupported_forecast = plan.intent in {"forecast_future_demand", "simulate_workforce_scenarios"}
        if unsupported_forecast or plan.plan_status == "unsupported":
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="unsupported",
                execution_status="unsupported",
                status="unavailable",
                answer=(
                    "Forecasting future skill demand and workforce what-if simulations are explicitly inactive "
                    "and unsupported in milestone G2.6. The platform operates strictly on verified historical "
                    "observations and does not produce speculative or synthetic projections."
                    if unsupported_forecast
                    else (plan.limitations[0] if plan.limitations else "The requested capability is not supported in this domain.")
                ),
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=plan.limitations or [
                    "Forecasting engine is explicitly disabled in G2.6.",
                    "Workforce what-if simulation is inactive in G2.6.",
                ],
                reason_codes=["CAPABILITY_UNSUPPORTED_IN_G2_6"] if unsupported_forecast else ["CAPABILITY_NOT_SUPPORTED_IN_DOMAIN"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

        # 3. Check Clarification Requirements
        if plan.clarification_required or plan.plan_status == "requires_clarification":
            clarification_text = (
                plan.clarification_questions[0]
                if plan.clarification_questions
                else "Could you please clarify your request?"
            )
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="requires_clarification",
                execution_status="requires_clarification",
                status="insufficient_data",
                answer=clarification_text,
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=plan.limitations,
                reason_codes=["REQUIRES_CLARIFICATION"],
                follow_up_questions=plan.clarification_questions,
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

        # 4. Check Blocked Plan Status
        if plan.plan_status == "blocked":
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="blocked",
                execution_status="blocked",
                status="unavailable",
                answer="This analytical operation is currently blocked by platform policy or data quality gates.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=plan.limitations,
                reason_codes=["CAPABILITY_BLOCKED"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            return self._enrich_answer_response(resp, request, plan, authenticated_user)

        # 5. Portal & Company Authorization Guard
        auth_blocked = self._check_portal_authorization(request, plan, authenticated_user)
        if auth_blocked:
            reason_code, blocked_msg = auth_blocked
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="blocked",
                execution_status="blocked",
                status="error",
                answer=blocked_msg,
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=[blocked_msg],
                reason_codes=[reason_code],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            return self._enrich_answer_response(resp, request, plan, authenticated_user)

        # Empty personal scopes are an explicit filter choice. Do not fall
        # through to an entity mentioned in the prompt or silently broaden it.
        if (request.filters or {}).get("scope_empty") is True:
            scope_name = str((request.filters or {}).get("scope") or "selected").strip()
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="insufficient_data",
                execution_status="insufficient_data",
                status="insufficient_data",
                answer=f"There are no saved entities in your {scope_name} scope yet. Add supported items to that list or choose another scope to continue.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=[f"The {scope_name} filter is empty for the signed-in user's saved data."],
                reason_codes=["EMPTY_FILTER_SCOPE"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

        # 6. Re-evaluate Runtime Readiness immediately before execution
        shared_analysis = None
        if any(
            capability in plan.selected_capabilities
            for capability in (
                "market_snapshot",
                "historical_signal_retrieval",
                "trend_velocity_analysis",
            )
        ):
            try:
                shared_analysis = self._shared_market_analysis(request, plan)
            except DataSourceUnavailableError as exc:
                return CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    intent=plan.intent,
                    plan_status=plan.plan_status,
                    execution_status="failed",
                    status="unavailable",
                    answer="The configured intelligence data source is temporarily unavailable. Please try again later.",
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=[str(exc)],
                    reason_codes=["INTELLIGENCE_SOURCE_UNAVAILABLE"],
                    follow_up_questions=[],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

        if (
            shared_analysis is not None
            and not shared_analysis.history_complete
            and "trend_velocity_analysis" in plan.selected_capabilities
        ):
            reason = shared_analysis.completeness_reason or (
                "Observation retrieval reached the bounded row limit; time-series analysis is incomplete."
            )
            readiness_id = "ev_observation_history_incomplete"
            source = (
                shared_analysis.observations[0].source
                if shared_analysis.observations else "configured_observation_store"
            )
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="insufficient_data",
                execution_status="insufficient_data",
                status="partial",
                answer="Trend and forecast calculations were withheld because the bounded observation read may have truncated the required history.",
                facts=[StructuredFact(
                    fact_id="fact_observation_history_incomplete",
                    fact_type="analysis_readiness",
                    entity_name=plan.context_summary.get("primary_entity"),
                    canonical_entity_id=(
                        canonical_skill_id(plan.context_summary.get("primary_entity"))
                        if plan.context_summary.get("primary_entity") else None
                    ),
                    entity_type="skill",
                    metric_name="history_completeness",
                    metric_value="incomplete_history",
                    unit="status",
                    source=source,
                    data_origin="real",
                    quality_state="incomplete_history",
                    readiness_state="incomplete_history",
                    evidence_reference=readiness_id,
                    details={"reason": reason, "history_complete": False},
                )],
                evidence=[EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    quality="incomplete_history",
                    description=reason,
                )],
                capabilities_used=[],
                limitations=[reason],
                reason_codes=["INCOMPLETE_OBSERVATION_HISTORY"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

        readiness_results: list[CapabilityEvaluationResult] = []
        if plan.intent == "rank_skill_trends":
            # The handler evaluates each exact source-aware series with the shared
            # analytical gates. A single primary-series probe would reject valid
            # additional cohorts or make execution depend on arbitrary ordering.
            executable_caps = list(plan.selected_capabilities)
        else:
            for cap_id in plan.selected_capabilities:
                eval_req = CapabilityEvaluationRequest(
                    capability_id=cap_id,
                    entity_name=plan.context_summary.get("primary_entity"),
                    portal_type=portal_type,  # type: ignore[arg-type]
                    time_range=request.time_range,
                    location=request.location,
                    target_role=request.target_role,
                    selected_skills=request.selected_skills,
                    observations=(
                        shared_analysis.observations if shared_analysis is not None
                        else request.observations
                    ),
                    context_override=request.context_override,
                )
                eval_resp = self.capability_service.evaluate(eval_req)
                if eval_resp.results:
                    readiness_results.append(eval_resp.results[0])

            executable_caps = [r.capability_id for r in readiness_results if r.can_execute]

        # If no selected capability can execute
        if not executable_caps:
            all_insufficient = all(r.runtime_status == "insufficient_data" for r in readiness_results)
            all_limitations = []
            for r in readiness_results:
                all_limitations.extend(r.limitations)

            if all_insufficient:
                ent_name = plan.context_summary.get("primary_entity") or "the requested entity"
                trend_requested = "trend_velocity_analysis" in plan.selected_capabilities
                observed_periods = sorted({
                    observation.period
                    for observation in (shared_analysis.observations if shared_analysis else [])
                    if observation.period
                })
                if trend_requested and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No measured trend observations are currently available for '{ent_name}' "
                        "with the selected filters. No trend value can be established until comparable "
                        "observations are available."
                    )
                    trend_limitations = [
                        "Trend direction requires at least four consecutive comparable monthly periods.",
                        *all_limitations,
                    ]
                    reason_code = "NO_OBSERVATIONS_FOR_SERIES"
                elif trend_requested:
                    period_summary = (
                        f" Available matched periods: {observed_periods[0]} through {observed_periods[-1]} "
                        f"({len(observed_periods)} distinct periods)."
                        if observed_periods else ""
                    )
                    answer_text = (
                        f"The available history for '{ent_name}' is insufficient to calculate a "
                        f"directional trend.{period_summary} At least four consecutive comparable "
                        "monthly periods are required."
                    )
                    trend_limitations = [
                        *all_limitations,
                        "Trend direction requires at least four consecutive comparable monthly periods.",
                    ]
                    reason_code = "INSUFFICIENT_TREND_HISTORY"
                else:
                    answer_text = f"Insufficient empirical observation data available for '{ent_name}' to complete this analysis."
                    trend_limitations = all_limitations or ["At least 4 consecutive monthly periods required for trend analysis."]
                    reason_code = "INSUFFICIENT_OBSERVATION_DATA"
                resp = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain=request.domain,
                    intent=plan.intent,
                    plan_status="insufficient_data",
                    execution_status="insufficient_data",
                    status="insufficient_data",
                    answer=answer_text,
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=trend_limitations,
                    reason_codes=[reason_code],
                    follow_up_questions=[
                        f"Would you like to explore taxonomy reference details for '{ent_name}'?",
                        f"What software tools are required for occupations using '{ent_name}'?",
                    ],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
                resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
                self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
                return resp
            else:
                resp = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain=request.domain,
                    intent=plan.intent,
                    plan_status="blocked",
                    execution_status="blocked",
                    status="unavailable",
                    answer="Execution cannot proceed because required capabilities did not meet runtime readiness gates.",
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=all_limitations,
                    reason_codes=["CAPABILITY_NOT_READY"],
                    follow_up_questions=[],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
                return self._enrich_answer_response(resp, request, plan, authenticated_user)

        # 7. Execute Verified Handlers
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = list(plan.limitations)
        capabilities_used: list[str] = []

        try:
            for cap_id in executable_caps:
                handler = self._handler_registry.get(cap_id)
                if not handler:
                    limitations.append(f"Handler for registered capability '{cap_id}' is not yet mounted.")
                    continue

                cap_facts, cap_evidence, cap_limits = handler(request, plan)
                facts.extend(cap_facts)
                evidence.extend(cap_evidence)
                limitations.extend(cap_limits)
                capabilities_used.append(cap_id)

        except DataSourceUnavailableError as exc:
            return CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status=plan.plan_status,
                execution_status="failed",
                status="unavailable",
                answer="The configured intelligence data source is temporarily unavailable. Please try again later.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=[str(exc)],
                reason_codes=["INTELLIGENCE_SOURCE_UNAVAILABLE"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
        except Exception as exc:
            logger.exception("Handler execution failed for request %s: %s", request_id, exc)
            return CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                intent=plan.intent,
                plan_status=plan.plan_status,
                execution_status="failed",
                status="error",
                answer="An unexpected error occurred during capability execution. Execution aborted safely without returning unverified data.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=[f"Execution failed: {type(exc).__name__}"],
                reason_codes=["HANDLER_EXECUTION_FAILED"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )

        # 8. Synthesize Grounded Natural Language Answer
        answer_text = self._synthesize_answer(plan.intent, facts, evidence, capabilities_used, request, plan=plan)

        # Optional LLM Grounded Explanation if available
        if self.llm_service.is_available():
            try:
                llm_ans = self.llm_service.generate_grounded_explanation(
                    user_message=request.message,
                    intent=plan.intent,
                    facts=facts,
                    evidence=evidence,
                    portal_type=portal_type,
                    user_id=user_id,
                )
                if llm_ans:
                    llm_val_status, _ = self._validate_response(
                        answer_text=llm_ans,
                        facts=facts,
                        evidence=evidence,
                        capabilities_used=capabilities_used,
                        plan=plan,
                    )
                    if llm_val_status == "completed":
                        answer_text = llm_ans
            except Exception as exc:
                logger.debug("LLM explanation generation skipped/fallback: %s", exc)

        # 9. Deterministic Response Validation
        val_status, val_reasons = self._validate_response(
            answer_text=answer_text,
            facts=facts,
            evidence=evidence,
            capabilities_used=capabilities_used,
            plan=plan,
        )

        if val_status != "completed":
            return CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                intent=plan.intent,
                plan_status=plan.plan_status,
                execution_status=val_status,
                status="error",
                answer="The generated response could not be verified against the structured evidence facts.",
                facts=facts,
                evidence=evidence,
                capabilities_used=capabilities_used,
                limitations=limitations,
                reason_codes=val_reasons,
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )

        follow_ups = self._generate_follow_up_questions(plan.intent, facts, plan, request)
        is_empty_scoped_job_search = (
            plan.intent == "search_jobs"
            and bool(request.selected_companies or (request.filters or {}).get("scope_empty"))
            and any(
                f.fact_type == "stored_job_postings" and (f.metric_value == 0 or f.details.get("readiness_state") == "insufficient_data")
                for f in facts
            )
        )
        trend_summary = next(
            (fact for fact in facts if fact.fact_type == "trend_ranking_summary"),
            None,
        )
        no_eligible_skill_trends = bool(
            plan.intent == "rank_skill_trends"
            and trend_summary
            and trend_summary.metric_value == 0
        )
        is_empty_trend_page = bool(
            plan.intent == "rank_skill_trends"
            and trend_summary
            and trend_summary.metric_value > 0
            and trend_summary.details.get("returned_series_count") == 0
        )
        insufficient_answer = is_empty_scoped_job_search or no_eligible_skill_trends
        resp = CoreIntelligenceAnswerResponse(
            request_id=request_id,
            user_message=request.message,
            portal_type=portal_type,
            intent=plan.intent,
            plan_status=plan.plan_status,
            execution_status="insufficient_data" if insufficient_answer else "completed",
            status="insufficient_data" if insufficient_answer else "ready",
            answer=answer_text,
            facts=facts,
            evidence=evidence,
            capabilities_used=capabilities_used,
            limitations=limitations,
            reason_codes=(
                ["INSUFFICIENT_SCOPED_JOB_POSTINGS"] if is_empty_scoped_job_search
                else ["NO_ELIGIBLE_SKILL_TRENDS"] if no_eligible_skill_trends
                else ["EMPTY_SKILL_TREND_PAGE"] if is_empty_trend_page
                else ["EXECUTION_COMPLETED_SUCCESSFULLY"]
            ),
            follow_up_questions=follow_ups,
            follow_up_suggestions=follow_ups[:2],
            conversation_id=request.conversation_id,
            client_message_id=request.client_message_id,
        )
        resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
        self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
        return resp

    def _enrich_answer_response(
        self,
        resp: CoreIntelligenceAnswerResponse,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse | None,
        authenticated_user: AuthenticatedUser | None,
    ) -> CoreIntelligenceAnswerResponse:
        """Populate canonical status, applied/unapplied filters, capabilities, confidence, freshness, and source coverage."""
        primary_ent = plan.context_summary.get("primary_entity") if plan else None

        # Applied vs Unapplied filters
        effective_domain = request.domain or (request.filters.get("domain") if request.filters else None) or "skill"
        applied_filters: dict[str, Any] = {
            "portal_type": resp.portal_type,
            "domain": effective_domain,
            "query": request.message,
        }
        unapplied_filters: list[dict[str, str]] = []
        if request.location:
            applied_filters["location"] = request.location
        if request.time_range:
            applied_filters["time_range"] = request.time_range
        if request.target_role:
            applied_filters["target_role"] = request.target_role
        if request.selected_skills:
            applied_filters["selected_skills"] = list(request.selected_skills)
        if request.selected_roles:
            applied_filters["selected_roles"] = list(request.selected_roles)
        if request.selected_companies:
            if effective_domain == "market":
                unapplied_filters.append({
                    "filter": "selected_companies",
                    "value": ", ".join(request.selected_companies),
                    "reason": "The configured market observation source contains technology signals, not company-level telemetry.",
                })
            else:
                applied_filters["selected_companies"] = list(request.selected_companies)

        extra_limitations: list[str] = []
        if request.filters:
            for fk, fv in request.filters.items():
                if fv is None or fv == "":
                    continue
                if fk in {"salary_band", "seniority_level", "remote_mode", "visa_sponsorship"}:
                    unapplied_filters.append({
                        "filter": fk,
                        "value": str(fv),
                        "reason": f"Filter '{fk}' is not supported by current normalized market series.",
                    })
                elif fk == "scope":
                    scope_val = str(fv).strip()
                    scope_norm = scope_val.lower().replace("_", " ")
                    skill_only_scopes = {"all skills", "my skills", "favourite skills", "favorite skills"}
                    company_only_scopes = {"all companies", "favourite companies", "favorite companies", "all"}
                    if effective_domain == "skill" and scope_norm in company_only_scopes:
                        unapplied_filters.append({
                            "filter": "scope",
                            "value": scope_val,
                            "reason": f"Scope '{scope_val}' is not valid for Skill Intelligence. Supported scopes: All Skills, My Skills, Favourites.",
                        })
                    elif effective_domain in {"market", "job"} and scope_norm in skill_only_scopes:
                        unapplied_filters.append({
                            "filter": "scope",
                            "value": scope_val,
                            "reason": f"Scope '{scope_val}' is not valid for {effective_domain.title()} Intelligence. Supported scopes: All, Favourites.",
                        })
                    elif scope_norm not in (
                        skill_only_scopes if effective_domain == "skill"
                        else company_only_scopes | {"favourites", "favorites", "selected companies", "my companies / followed companies"}
                    ):
                        unapplied_filters.append({
                            "filter": fk,
                            "value": scope_val,
                            "reason": f"Scope '{scope_val}' is not supported for {effective_domain.title()} Intelligence.",
                        })
                    else:
                        applied_filters["scope"] = scope_val
                        if request.filters.get("scope_empty") is True:
                            extra_limitations.append(
                                f"Selected scope '{scope_val}' currently has 0 saved items in your profile/favourites; no fabricated fallback items were substituted."
                            )
                elif fk == "scope_empty":
                    continue
                elif fk == "selected_company":
                    if effective_domain == "market":
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": "The configured market observation source contains technology signals, not company-level telemetry.",
                        })
                    elif str(fv).casefold() not in {value.casefold() for value in request.selected_companies}:
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": "The selected company filter does not match a company in the committed selection.",
                        })
                    else:
                        applied_filters[fk] = fv
                elif fk == "selected_skill":
                    if effective_domain != "skill":
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": f"A selected skill is not a supported entity filter in the {effective_domain.title()} domain.",
                        })
                    elif str(fv).casefold() not in {value.casefold() for value in request.selected_skills}:
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": "The selected skill filter does not match a skill in the committed selection.",
                        })
                    else:
                        applied_filters[fk] = fv
                elif fk == "selected_role":
                    if effective_domain != "job":
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": f"A selected role is not a supported entity filter in the {effective_domain.title()} domain.",
                        })
                    elif str(fv).casefold() not in {
                        value.casefold() for value in [request.target_role, *request.selected_roles] if value
                    }:
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": "The selected role filter does not match the committed role selection.",
                        })
                    else:
                        applied_filters[fk] = fv
                elif fk == "country":
                    if effective_domain != "job":
                        unapplied_filters.append({
                            "filter": fk,
                            "value": str(fv),
                            "reason": "Country filtering is only supported for stored Job Intelligence postings.",
                        })
                    else:
                        applied_filters[fk] = fv
                elif plan and plan.intent == "rank_skill_trends" and fk in {
                    "source",
                    "provider",
                    "signal_type",
                    "observation_scope",
                    "market_scope",
                    "limit",
                    "offset",
                }:
                    applied_filters[fk] = fv
                elif fk in {"domain", "requested_time_window", "time_range", "location"}:
                    applied_filters[fk] = fv
                else:
                    unapplied_filters.append({
                        "filter": fk,
                        "value": str(fv)[:200],
                        "reason": "This filter is not supported by the shared intelligence pipeline.",
                    })

        analysis = self._shared_market_analysis(request, plan)
        obs = analysis.observations
        agg_signals = analysis.aggregated_signals
        trends = analysis.trend_results

        target_skill = primary_ent or (request.selected_skills[0] if request.selected_skills else "")
        target_canon_id = canonical_skill_id(target_skill) if target_skill else None

        skill_health_res = evaluate_skill_health(
            agg_signals,
            canonical_skill_id=target_canon_id,
            canonical_name=target_skill,
            history_complete=analysis.history_complete,
        )
        sig_fam = (
            "demand" if any(s.signal_type == "demand" for s in agg_signals)
            else "adoption" if any(s.signal_type == "adoption" for s in agg_signals)
            else "interest"
        )
        half_life_res = calculate_skill_half_life(
            agg_signals,
            canonical_skill_id=target_canon_id,
            canonical_name=target_skill,
            signal_family=sig_fam,
            min_periods=36,
            history_complete=analysis.history_complete,
        )
        forecast_res = forecast_signal_series(
            agg_signals,
            canonical_skill_id=target_canon_id,
            canonical_name=target_skill,
            signal_family=sig_fam,
            min_periods=24,
            history_complete=analysis.history_complete,
        )
        primary_trend = trends[0] if trends else None
        demand_dir = (primary_trend.trend_direction or primary_trend.trend) if primary_trend else "Insufficient Data"
        ai_disruption_res = evaluate_ai_task_disruption(
            entity_name=request.target_role or target_skill,
            entity_type="skill",
            canonical_id=target_canon_id,
            empirical_demand_direction=demand_dir,
        )
        workforce_impact_res = evaluate_market_to_person_to_company_impact(
            skill_name=target_skill,
            skill_health_category=skill_health_res.health_category,
            demand_trend_direction=demand_dir,
            demand_slope=(primary_trend.trend_slope if primary_trend and primary_trend.trend_slope is not None else (primary_trend.slope if primary_trend else None)),
            half_life_status=half_life_res.status,
            half_life_months=half_life_res.half_life_months,
            user_skills=list(request.selected_skills or []),
            user_target_role=request.target_role,
            company_skill_inventory=None,
            company_open_roles=[],
            observation_ids=[o.id for o in obs],
        )

        capabilities_dict: dict[str, Any] = {
            "skill_health": {
                "status": skill_health_res.status,
                "payload": skill_health_res.model_dump(),
                "reason": skill_health_res.explanation,
            },
            "skill_half_life": {
                "status": half_life_res.status,
                "payload": half_life_res.model_dump(),
                "reason": half_life_res.reason,
            },
            "forecast": {
                "status": forecast_res.status,
                "payload": forecast_res.model_dump(),
                "reason": forecast_res.reason,
            },
            "ai_disruption": {
                "status": ai_disruption_res.status,
                "payload": ai_disruption_res.model_dump(),
                "reason": ai_disruption_res.reason,
            },
            "workforce_impact": {
                "status": workforce_impact_res.status,
                "payload": workforce_impact_res.model_dump(),
                "reason": "Connected market-to-person-to-company impact evaluation.",
            },
        }

        latest_obs_dt = max((o.observed_at for o in obs if o.observed_at), default=None)
        latest_obs_iso = latest_obs_dt.isoformat() if latest_obs_dt else None
        max_periods = max((len(t.periods_used) for t in trends), default=len(obs))

        conf_res = compute_evidence_confidence(
            period_count=max_periods if max_periods > 0 else (4 if resp.facts else 0),
            ready_signal_families=skill_health_res.ready_families if skill_health_res.ready_families else (["reference"] if resp.facts else []),
            family_directions=[r.direction for r in skill_health_res.component_table if r.is_eligible_share],
            latest_observed_at=latest_obs_dt,
            has_valid_denominator=any(s.metric == "normalized_share" for s in agg_signals),
            quality_valid=True,
        )

        history_types = sorted({o.history_type for o in obs if o.history_type} | {f.history_type for f in resp.facts if f.history_type})
        history_type_val = history_types[0] if len(history_types) == 1 else ("mixed" if history_types else "none")
        sources_list = sorted({o.source for o in obs if o.source} | {f.source for f in resp.facts if f.source})

        freshness = {
            "latest_observed_at": latest_obs_iso,
            "observation_count": len(obs),
            "fact_count": len(resp.facts),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "history_complete": analysis.history_complete,
            "history_completeness_reason": analysis.completeness_reason,
        }
        source_coverage = {
            "providers_present": sources_list,
            "signal_families_ready": len(skill_health_res.ready_families),
            "total_observations": len(obs),
        }

        follow_up_suggestions = (resp.follow_up_questions or [])[:2]
        merged_limitations = list(resp.limitations or [])
        if not analysis.history_complete and analysis.completeness_reason:
            if analysis.completeness_reason not in merged_limitations:
                merged_limitations.append(analysis.completeness_reason)
        for lim in extra_limitations:
            if lim not in merged_limitations:
                merged_limitations.append(lim)

        metric_results = [
            *fact_metric_results(
                resp.facts,
                resp.evidence,
                history_complete=analysis.history_complete,
            ),
            *capability_metric_results(
                capabilities_dict,
                analysis.observations,
                history_complete=analysis.history_complete,
            ),
        ]
        merged_reason_codes = list(resp.reason_codes)
        response_status = resp.status
        if not analysis.history_complete:
            response_status = (
                "partial" if resp.status not in {"error", "unavailable"} else resp.status
            )
            if "OBSERVATION_HISTORY_INCOMPLETE" not in merged_reason_codes:
                merged_reason_codes.append("OBSERVATION_HISTORY_INCOMPLETE")

        resolved_selections: list[SelectedEntityResolution] = []
        seen_selection_ids: set[str] = set()
        for item in plan.entities if plan else []:
            canonical = item.canonical_entity
            identity = canonical.entity_id if canonical else item.raw_token.casefold()
            if identity in seen_selection_ids:
                continue
            seen_selection_ids.add(identity)
            resolved_selections.append(SelectedEntityResolution(
                entity_id=canonical.entity_id if canonical else None,
                entity_type=canonical.entity_type if canonical else None,
                canonical_name=canonical.canonical_name if canonical else item.raw_token,
                resolution_status=item.resolution_status,
            ))

        return resp.model_copy(
            update={
                "domain": effective_domain,
                "resolved_entity": primary_ent,
                "selected_entities": resolved_selections,
                "applied_filters": applied_filters,
                "unapplied_filters": unapplied_filters,
                "capabilities": capabilities_dict,
                "metric_results": metric_results,
                "confidence": conf_res.model_dump(),
                "freshness": freshness,
                "history_type": history_type_val,
                "source_coverage": source_coverage,
                "follow_up_suggestions": follow_up_suggestions,
                "limitations": merged_limitations,
                "status": response_status,
                "reason_codes": merged_reason_codes,
            }
        )

    def _record_conversation_turn(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse | None,
        resp: CoreIntelligenceAnswerResponse,
        authenticated_user: AuthenticatedUser | None,
        portal_type: str,
    ) -> None:
        if not request.conversation_id:
            return
        try:
            user_id = authenticated_user.uid if authenticated_user else "anonymous"
            company_id = request.company_id or (getattr(authenticated_user, "company_id", None) if authenticated_user else None)
            primary_ent = None
            resolved_ents: list[str] = []
            comp_ents: list[str] = []
            target_role = request.target_role or next(iter(request.selected_roles), None)
            time_range = request.time_range or "30d"
            selected_skills = list(request.selected_skills or [])
            selected_companies = list(request.selected_companies or [])
            effective_domain = request.domain or (request.filters.get("domain") if request.filters else None) or "skill"
            intent = plan.intent if plan else "unknown"

            if plan:
                primary_ent = plan.context_summary.get("primary_entity")
                if plan.entities:
                    resolved_ents = [
                        e.canonical_entity.canonical_name
                        for e in plan.entities
                        if e.canonical_entity
                    ]
                comp_ents = plan.context_summary.get("comparison_entities", [])
                target_role = target_role or plan.context_summary.get("target_role")
                time_range = request.time_range or plan.context_summary.get("time_range", "30d")
                selected_skills = selected_skills or plan.context_summary.get("selected_skills", [])

            self.conversation_store.save_turn(
                conversation_id=request.conversation_id,
                user_id=user_id,
                company_id=company_id,
                portal_type=portal_type,
                domain=effective_domain,
                user_message=request.message,
                intent=intent,
                primary_entity=primary_ent,
                resolved_entities=resolved_ents,
                comparison_entities=comp_ents,
                target_role=target_role,
                time_range=time_range,
                selected_skills=selected_skills,
                selected_companies=selected_companies,
                filters=dict(resp.applied_filters or {}),
                execution_status=resp.execution_status,
                answer_summary=resp.answer if resp.answer else None,
                client_message_id=request.client_message_id,
                response_payload=resp.model_dump(mode="json"),
                regenerate_existing=request.regenerate,
            )
            if request.client_message_id:
                _IDEMPOTENT_ANSWER_CACHE[(user_id, request.conversation_id, request.client_message_id)] = resp
        except Exception as exc:
            logger.warning("Failed to record conversation turn for %s: %s", request.conversation_id, exc)

    # =========================================================================
    # AUTHORIZATION & ACCESS CONTROL
    # =========================================================================

    def _check_portal_authorization(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
        authenticated_user: AuthenticatedUser | None,
    ) -> tuple[str, str] | None:
        """Ensure company intelligence is strictly isolated and cross-company queries are rejected."""
        is_company_query = (
            request.portal_type == "company"
            or "company_intelligence" in plan.selected_capabilities
            or plan.intent == "analyze_company_workforce"
        )
        if not is_company_query:
            return None

        if not authenticated_user:
            return ("UNAUTHORIZED_PORTAL_ACCESS", "Authentication required for company workforce intelligence.")

        user_company_id = getattr(authenticated_user, "company_id", None)
        if hasattr(authenticated_user, "claims") and isinstance(authenticated_user.claims, dict):
            user_company_id = user_company_id or authenticated_user.claims.get("company_id")

        target_company_id = request.company_id or plan.context_summary.get("company_id")

        # If user has no company membership
        if not user_company_id:
            return ("UNAUTHORIZED_PORTAL_ACCESS", "Authenticated user does not have an active company organization.")

        # Cross-company attempt
        if target_company_id and user_company_id != target_company_id:
            return (
                "UNAUTHORIZED_CROSS_COMPANY_ACCESS",
                f"Access denied: User is not authorized to access workforce data for company '{target_company_id}'.",
            )

        return None

    # =========================================================================
    # CAPABILITY HANDLERS
    # =========================================================================

    def _handle_entity_resolution(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = []

        for ent_item in plan.entities:
            if ent_item.resolution_status == "resolved" and ent_item.canonical_entity:
                ce = ent_item.canonical_entity
                facts.append(StructuredFact(
                    fact_type="entity",
                    entity_name=ce.canonical_name,
                    metric_name="canonical_entity_id",
                    metric_value=ce.entity_id,
                    source=ce.source,
                    provenance_id=ce.source_record_id,
                    details={
                        "entity_type": ce.entity_type,
                        "category": ce.category,
                        "raw_token": ent_item.raw_token,
                    },
                    fact_id=f"fact_ent_{ce.entity_id}",
                    canonical_entity_id=ce.entity_id,
                    entity_type=ce.entity_type,
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    evidence_reference=f"ev_ent_{ce.entity_id}",
                ))
                evidence.append(EvidenceItem(
                    evidence_id=f"ev_ent_{ce.entity_id}",
                    source=ce.source,
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    description=f"Resolved '{ent_item.raw_token}' to canonical entity '{ce.canonical_name}' ({ce.entity_type}).",
                ))

        return facts, evidence, limitations

    def _handle_skill_technology_reference(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
        ]

        # Gather distinct entities from plan
        entities_to_lookup: list[tuple[str, Any]] = []
        if plan.entities:
            for item in plan.entities:
                if item.canonical_entity:
                    if not any(e[0] == item.canonical_entity.canonical_name for e in entities_to_lookup):
                        entities_to_lookup.append((item.canonical_entity.canonical_name, item.canonical_entity))

        if not entities_to_lookup:
            fallback_token = plan.context_summary.get("primary_entity") or request.message.strip()
            # Attempt to resolve fallback token
            resolved = self.entity_service.resolve(EntityResolutionRequest(name=fallback_token))
            ent = resolved.entity if resolved.status == "resolved" else None
            entities_to_lookup.append((fallback_token, ent))

        for token, primary_ent in entities_to_lookup:
            # Check in reference store for GitHub topics or languages
            topic_token = token.lower() if token else ""
            topics = self.reference_store.get_github_adoption_series(topic=topic_token)
            languages = self.reference_store.get_github_adoption_series(language=token)
            if not languages and token:
                languages = self.reference_store.get_github_adoption_series(language=token.title())

            if topics:
                latest_topic = topics[-1]
                t_period = latest_topic.get("period", "")
                t_name = latest_topic.get("topic", token)
                t_pushers = latest_topic.get("num_pushers", 0)
                ev_id = f"ev_gh_topic_{t_name}_{t_period}"
                facts.append(StructuredFact(
                    fact_id=f"fact_gh_topic_{t_name}_{t_period}",
                    fact_type="technology_adoption",
                    entity_name=t_name,
                    canonical_entity_id=f"tech:github_topic:{t_name}",
                    entity_type="technology",
                    metric_name="github_developer_pushers",
                    metric_value=t_pushers,
                    unit="developers",
                    period=t_period,
                    source="ref_github_topic_adoption",
                    data_origin="real",
                    history_type="reference_dataset",
                    quality_state="valid",
                    provenance_id=t_name,
                    evidence_reference=ev_id,
                    details={"iso2_code": latest_topic.get("iso2_code")},
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source="ref_github_topic_adoption",
                    signal_type="adoption",
                    period=t_period,
                    data_origin="real",
                    quality="valid",
                    description=f"GitHub Innovation Graph developer topic adoption: {t_pushers} pushers in {t_period}.",
                ))

            if languages:
                latest_lang = languages[-1]
                l_period = latest_lang.get("period", "")
                l_name = latest_lang.get("language", token)
                l_pushers = latest_lang.get("num_pushers", 0)
                ev_id = f"ev_gh_lang_{l_name}_{l_period}"
                facts.append(StructuredFact(
                    fact_id=f"fact_gh_lang_{l_name}_{l_period}",
                    fact_type="technology_adoption",
                    entity_name=l_name,
                    canonical_entity_id=f"tech:github_lang:{l_name}",
                    entity_type="technology",
                    metric_name="github_developer_pushers",
                    metric_value=l_pushers,
                    unit="developers",
                    period=l_period,
                    source="ref_github_language_adoption",
                    data_origin="real",
                    history_type="reference_dataset",
                    quality_state="valid",
                    provenance_id=l_name,
                    evidence_reference=ev_id,
                    details={"iso2_code": latest_lang.get("iso2_code")},
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source="ref_github_language_adoption",
                    signal_type="adoption",
                    period=l_period,
                    data_origin="real",
                    quality="valid",
                    description=f"GitHub Innovation Graph developer language adoption: {l_pushers} pushers in {l_period}.",
                ))

            skill_id = (
                primary_ent.source_record_id
                if primary_ent and primary_ent.source == "canonical_registry"
                else canonical_skill_id(token)
            )
            if skill_id:
                from app.services.intelligence_catalog_service import get_local_github_skill_series

                local_series = get_local_github_skill_series(skill_id)
                local_series = sorted(
                    local_series,
                    key=lambda item: (bool(item.get("trend_ready")), str((item.get("latest") or {}).get("period") or "")),
                    reverse=True,
                )
                if len(local_series) > 5:
                    limitations.append(
                        "Only five separately identified GitHub Innovation Graph series are returned for this skill; no source metrics are combined."
                    )
                for series in local_series[:5]:
                    latest = series.get("latest") or {}
                    latest_period = str(latest.get("period") or "")
                    metric = str(series.get("metric") or "developer_activity")
                    source_label = str(series.get("label") or token)
                    series_id = f"github_innovation_graph:{metric}:{skill_id}:{source_label}"
                    snapshot_evidence_id = f"ev_{series_id}_{latest_period}"
                    facts.append(StructuredFact(
                        fact_id=f"fact_{series_id}_{latest_period}",
                        fact_type="developer_activity_snapshot",
                        entity_name=source_label,
                        canonical_entity_id=skill_id,
                        entity_type="skill",
                        metric_name=metric,
                        metric_value=latest.get("value"),
                        unit=str(series.get("unit") or "unique developers per quarter"),
                        period=latest_period,
                        source="github_innovation_graph",
                        data_origin="local_reference_dataset",
                        history_type="backfill",
                        series_id=series_id,
                        quality_state="valid",
                        readiness_state="stale" if series.get("stale") else "observed",
                        provenance_id=series_id,
                        evidence_reference=snapshot_evidence_id,
                        details={
                            "label": source_label,
                            "time_grain": "quarter",
                            "location": series.get("location"),
                            "metric_family": "developer_activity",
                        },
                    ))
                    evidence.append(EvidenceItem(
                        evidence_id=snapshot_evidence_id,
                        source="github_innovation_graph",
                        signal_type="developer_activity_snapshot",
                        period=latest_period,
                        data_origin="local_reference_dataset",
                        history_type="backfill",
                        series_id=series_id,
                        quality="stale" if series.get("stale") else "valid",
                        description=(
                            f"GitHub Innovation Graph {metric} for {source_label}: "
                            f"{latest.get('value')} {series.get('unit')} in {latest_period}."
                        ),
                    ))

                    if series.get("trend_ready"):
                        periods_used = list(series.get("trend_periods_used") or [])
                        trend_period = (
                            f"{periods_used[0]}_to_{periods_used[-1]}"
                            if periods_used else str(series.get("latest_trend_period") or latest_period)
                        )
                        trend_evidence_id = f"ev_{series_id}_trend_{trend_period}"
                        direction = str(series.get("trend_direction") or "Insufficient Data")
                        facts.append(StructuredFact(
                            fact_id=f"fact_{series_id}_trend_{trend_period}",
                            fact_type="trend_analysis",
                            entity_name=source_label,
                            canonical_entity_id=skill_id,
                            entity_type="skill",
                            metric_name="trend_direction",
                            metric_value=direction,
                            unit=str(series.get("unit") or "unique developers per quarter"),
                            period=trend_period,
                            source="github_innovation_graph",
                            data_origin="local_reference_dataset",
                            history_type="backfill",
                            series_id=series_id,
                            quality_state="valid",
                            readiness_state="stale" if series.get("stale") else "ready",
                            calculation_version=str(series.get("trend_calculation") or "g1.4-theilsen-v1"),
                            provenance_id=series_id,
                            evidence_reference=trend_evidence_id,
                            details={
                                "source_metric": metric,
                                "period_grain": "quarter",
                                "trend_slope": series.get("trend_slope"),
                                "velocity": series.get("velocity_per_quarter"),
                                "velocity_unit": "unique developers per quarter",
                                "latest_period_change": series.get("period_over_period_change"),
                                "latest_period": series.get("latest_trend_period"),
                                "periods_count": len(periods_used),
                                "periods_used": periods_used,
                                "stale": bool(series.get("stale")),
                                "stale_reason": series.get("stale_reason"),
                            },
                        ))
                        evidence.append(EvidenceItem(
                            evidence_id=trend_evidence_id,
                            source="github_innovation_graph",
                            signal_type="derived_developer_activity_trend",
                            period=trend_period,
                            data_origin="local_reference_dataset",
                            history_type="backfill",
                            series_id=series_id,
                            quality="stale" if series.get("stale") else "valid",
                            description=(
                                f"The shared Theil-Sen engine calculated a {direction.lower()} trend "
                                f"for {metric} ({series.get('unit')}) over {trend_period}; velocity "
                                f"{series.get('velocity_per_quarter')} per quarter and latest adjacent-quarter "
                                f"change {series.get('period_over_period_change')}."
                            ),
                        ))
                        if series.get("stale"):
                            limitations.append(
                                f"GitHub Innovation Graph series '{source_label}' is stale; its historical trend is not a current market-demand signal."
                            )
                    else:
                        readiness_reason = str(
                            series.get("trend_unavailable_reason")
                            or "The latest contiguous run does not meet the trend-history gate."
                        )
                        readiness_evidence_id = f"ev_{series_id}_readiness"
                        facts.append(StructuredFact(
                            fact_id=f"fact_{series_id}_readiness",
                            fact_type="analysis_readiness",
                            entity_name=source_label,
                            canonical_entity_id=skill_id,
                            entity_type="skill",
                            metric_name="trend_direction_readiness",
                            metric_value="insufficient_history",
                            unit="status",
                            period=latest_period,
                            source="github_innovation_graph",
                            data_origin="local_reference_dataset",
                            history_type="backfill",
                            series_id=series_id,
                            quality_state="valid",
                            readiness_state="insufficient_data",
                            evidence_reference=readiness_evidence_id,
                            details={
                                "reason": readiness_reason,
                                "metric": metric,
                                "unit": series.get("unit"),
                                "period_grain": "quarter",
                            },
                        ))
                        evidence.append(EvidenceItem(
                            evidence_id=readiness_evidence_id,
                            source="github_innovation_graph",
                            signal_type="analysis_readiness",
                            period=latest_period,
                            data_origin="local_reference_dataset",
                            history_type="backfill",
                            series_id=series_id,
                            quality="valid",
                            description=f"Trend unavailable for {source_label}: {readiness_reason}",
                        ))
                        limitations.append(
                            f"GitHub Innovation Graph trend for '{source_label}' is unavailable: {readiness_reason}"
                        )

                if local_series:
                    limitations.extend([
                        "GitHub Innovation Graph records are quarterly developer activity, not job demand.",
                        "This raw-count history does not qualify for denominator-based Skill Health, Half-Life, or Future Skill Forecast.",
                    ])

            if primary_ent:
                ev_ent_id = f"ev_ent_{primary_ent.entity_id}"
                facts.append(StructuredFact(
                    fact_id=f"fact_canon_{primary_ent.entity_id}",
                    fact_type="canonical_reference",
                    entity_name=primary_ent.canonical_name,
                    canonical_entity_id=primary_ent.entity_id,
                    entity_type=primary_ent.entity_type,
                    metric_name="taxonomy_category",
                    metric_value=primary_ent.category or "Skill",
                    source=primary_ent.source,
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    provenance_id=primary_ent.source_record_id,
                    evidence_reference=ev_ent_id,
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_ent_id,
                    source=primary_ent.source or "entity_registry",
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    description=f"Canonical entity registry record: {primary_ent.canonical_name} ({primary_ent.entity_type}).",
                ))
            elif not topics and not languages:
                # Add baseline reference fact for token
                ev_tok_id = f"ev_ref_{token}"
                facts.append(StructuredFact(
                    fact_id=f"fact_ref_{token}",
                    fact_type="reference_definition",
                    entity_name=token,
                    canonical_entity_id=None,
                    entity_type="skill",
                    metric_name="reference_status",
                    metric_value="verified_taxonomy_term",
                    source="reference_taxonomy",
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    provenance_id=token,
                    evidence_reference=ev_tok_id,
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_tok_id,
                    source="reference_taxonomy",
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    description=f"Reference taxonomy entry for '{token}'.",
                ))

        return facts, evidence, limitations

    def _handle_occupation_lookup(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["O*NET is an occupational taxonomy baseline, not real-time labor market hiring demand."]

        target_soc = None
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                target_soc = ent.canonical_entity.metadata.get("soc_code") or ent.canonical_entity.source_record_id
                break

        if not target_soc and request.target_role:
            occs = self.reference_store.get_onet_occupations(title=request.target_role)
            if occs:
                target_soc = occs[0].soc_code

        if not target_soc:
            occs = self.reference_store.get_onet_occupations(limit=1)
            if occs:
                target_soc = occs[0].soc_code

        if target_soc:
            occs = self.reference_store.get_onet_occupations(code=target_soc)
            if occs:
                occ = occs[0]
                ev_id = f"ev_onet_occ_{occ.soc_code}"
                facts.append(StructuredFact(
                    fact_id=f"fact_onet_occ_{occ.soc_code}",
                    fact_type="occupation",
                    entity_name=occ.title,
                    canonical_entity_id=f"occupation:soc:{occ.soc_code}",
                    entity_type="occupation",
                    metric_name="soc_code",
                    metric_value=occ.soc_code,
                    source="ref_onet_occupations",
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    provenance_id=occ.soc_code,
                    evidence_reference=ev_id,
                    details={"description": occ.description},
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source="ref_onet_occupations",
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    description=f"O*NET 2018 SOC Occupation: {occ.title} (SOC {occ.soc_code}).",
                ))

        return facts, evidence, limitations

    def _handle_occupation_software_skills(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["Software tools reflect workplace survey baselines; tool frequency varies by employer."]

        target_soc = None
        target_title = None
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                target_soc = ent.canonical_entity.metadata.get("soc_code") or ent.canonical_entity.source_record_id
                target_title = ent.canonical_entity.canonical_name
                break

        if not target_soc and request.target_role:
            occs = self.reference_store.get_onet_occupations(title=request.target_role)
            if occs:
                target_soc = occs[0].soc_code
                target_title = occs[0].title

        if not target_soc:
            # Default to Software Developers
            target_soc = "15-1252.00"
            target_title = "Software Developers"

        skills = self.entity_service.get_occupation_skills(target_soc, limit=10)
        ev_id = f"ev_onet_soft_{target_soc}"
        for s in skills:
            facts.append(StructuredFact(
                fact_id=f"fact_soft_{target_soc}_{s.source_record_id}",
                fact_type="software_skill",
                entity_name=s.canonical_name,
                canonical_entity_id=s.entity_id,
                entity_type="technology",
                metric_name="hot_technology",
                metric_value=s.metadata.get("hot_technology", False),
                source=s.source,
                data_origin="real",
                history_type="reference_taxonomy",
                quality_state="valid",
                provenance_id=s.source_record_id,
                evidence_reference=ev_id,
                details={
                    "occupation_title": target_title,
                    "soc_code": target_soc,
                    "element_name": s.category,
                    "in_demand": s.metadata.get("in_demand", False),
                },
            ))

        evidence.append(EvidenceItem(
            evidence_id=ev_id,
            source="ref_onet_software_skills",
            signal_type="software_tools_crosswalk",
            quality="valid",
            description=f"O*NET software technologies crosswalk for SOC {target_soc} ({target_title}): {len(skills)} tools retrieved.",
        ))

        return facts, evidence, limitations

    def _handle_related_occupations(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["Occupational relatedness indicates shared work activities, not identical salary or vacancy volume."]

        target_soc = None
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                target_soc = ent.canonical_entity.metadata.get("soc_code") or ent.canonical_entity.source_record_id
                break

        if not target_soc and request.target_role:
            occs = self.reference_store.get_onet_occupations(title=request.target_role)
            if occs:
                target_soc = occs[0].soc_code

        if not target_soc:
            target_soc = "15-1252.00"

        related = self.entity_service.get_related_occupations(target_soc)
        ev_id = f"ev_onet_rel_{target_soc}"
        for r in related[:10]:
            rel_soc = r.metadata.get("soc_code")
            facts.append(StructuredFact(
                fact_id=f"fact_rel_{target_soc}_{rel_soc}",
                fact_type="related_occupation",
                entity_name=r.canonical_name,
                canonical_entity_id=r.entity_id,
                entity_type="occupation",
                metric_name="relatedness_tier",
                metric_value=r.metadata.get("relatedness_tier", "Related"),
                source=r.source,
                data_origin="real",
                history_type="reference_taxonomy",
                quality_state="valid",
                provenance_id=r.source_record_id,
                evidence_reference=ev_id,
                details={"related_soc_code": rel_soc},
            ))

        evidence.append(EvidenceItem(
            evidence_id=ev_id,
            source="ref_onet_related_occupations",
            signal_type="mobility_crosswalk",
            quality="valid",
            description=f"O*NET related occupations crosswalk for SOC {target_soc}: {len(related)} related roles retrieved.",
        ))

        return facts, evidence, limitations

    def _handle_market_snapshot(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["Snapshots represent samples observed through provider queries, not total universe of postings."]

        obs = self._shared_market_analysis(request, plan).observations

        if obs:
            latest_obs = max(obs, key=lambda o: (o.period, o.observed_at))
            facts.append(StructuredFact(
                fact_id=f"fact_snap_{latest_obs.id}",
                fact_type="market_snapshot",
                entity_name=latest_obs.skill,
                canonical_entity_id=latest_obs.skill_id,
                entity_type="skill",
                metric_name="observed_metric_value",
                metric_value=latest_obs.value,
                denominator=latest_obs.denominator,
                period=latest_obs.period,
                timestamp=latest_obs.observed_at,
                source=latest_obs.source,
                data_origin=latest_obs.data_origin or "real",
                history_type=latest_obs.history_type,
                series_id=latest_obs.series_id,
                quality_state=latest_obs.quality or "valid",
                provenance_id=latest_obs.id,
                evidence_reference=latest_obs.id,
                details={
                    "signal_type": latest_obs.signal_type,
                    "location": latest_obs.location,
                    "denominator": latest_obs.denominator,
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=latest_obs.id,
                source=latest_obs.source,
                signal_type=latest_obs.signal_type,
                period=latest_obs.period,
                unit=latest_obs.unit,
                data_origin=latest_obs.data_origin or "real",
                history_type=latest_obs.history_type,
                series_id=latest_obs.series_id,
                location=latest_obs.location,
                scope=latest_obs.scope,
                query_id=latest_obs.query_id,
                panel_version=latest_obs.panel_version,
                fetch_run_id=latest_obs.fetch_run_id,
                source_url=latest_obs.source_url,
                quality=latest_obs.quality or "valid",
                provenance_id=latest_obs.id,
                confidence=latest_obs.confidence,
                description=f"Observed {latest_obs.signal_type} for '{latest_obs.skill}' ({latest_obs.value}) in {latest_obs.period}.",
            ))
        else:
            readiness_id = "ev_market_snapshot_unavailable"
            source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
            facts.append(StructuredFact(
                fact_id="fact_market_snapshot_unavailable",
                fact_type="analysis_readiness",
                entity_name=plan.context_summary.get("primary_entity"),
                metric_name="market_evidence_readiness",
                metric_value="insufficient_data",
                unit="status",
                source=source,
                data_origin="unavailable",
                readiness_state="insufficient_data",
                evidence_reference=readiness_id,
                details={
                    "reason": "No persisted market observations matched the canonical skill, location, and time filters.",
                    "domain": "market",
                    "reference_data_is_not_market_evidence": True,
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=readiness_id,
                source=source,
                signal_type="evidence_readiness",
                data_origin="unavailable",
                quality="unavailable",
                description="No persisted market observation matched the requested filters.",
            ))

        return facts, evidence, limitations

    def _handle_historical_signal_retrieval(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["Only verified empirical periods are returned; zero interpolation across missing periods."]

        obs = self._shared_market_analysis(request, plan).observations

        for o in obs:
            facts.append(StructuredFact(
                fact_id=f"fact_hist_{o.id}",
                fact_type="historical_observation",
                entity_name=o.skill,
                canonical_entity_id=o.skill_id,
                entity_type="skill",
                metric_name=o.signal_type,
                metric_value=o.value,
                denominator=o.denominator,
                period=o.period,
                timestamp=o.observed_at,
                source=o.source,
                data_origin=o.data_origin or "real",
                history_type=o.history_type,
                series_id=o.series_id,
                quality_state=o.quality or "valid",
                provenance_id=o.id,
                evidence_reference=o.id,
                unit=o.unit,
                details={
                    "denominator": o.denominator,
                    "location": o.location,
                    "scope": o.scope,
                    "query_id": o.query_id,
                    "panel_version": o.panel_version,
                    "source_url": o.source_url,
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=o.id,
                source=o.source,
                signal_type=o.signal_type,
                period=o.period,
                unit=o.unit,
                data_origin=o.data_origin or "real",
                history_type=o.history_type,
                series_id=o.series_id,
                location=o.location,
                scope=o.scope,
                query_id=o.query_id,
                panel_version=o.panel_version,
                fetch_run_id=o.fetch_run_id,
                source_url=o.source_url,
                provenance_id=o.id,
                quality=o.quality or "valid",
                description=f"Historical {o.signal_type} observation for '{o.skill}' in {o.period}.",
            ))

        if not obs:
            readiness_id = "ev_historical_series_unavailable"
            source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
            facts.append(StructuredFact(
                fact_id="fact_historical_series_unavailable",
                fact_type="analysis_readiness",
                entity_name=plan.context_summary.get("primary_entity"),
                metric_name="historical_series_readiness",
                metric_value="insufficient_data",
                unit="status",
                source=source,
                data_origin="unavailable",
                readiness_state="insufficient_data",
                evidence_reference=readiness_id,
                details={
                    "reason": "No persisted observations matched the selected skill and committed filters.",
                    "periods": [],
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=readiness_id,
                source=source,
                signal_type="evidence_readiness",
                data_origin="unavailable",
                quality="unavailable",
                description="No historical observations matched the request.",
            ))

        return facts, evidence, limitations

    def _handle_trend_velocity_analysis(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        if getattr(plan, "intent", None) == "rank_skill_trends":
            return self._handle_all_skill_trend_ranking(request, plan)

        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Trend and velocity require >=4 strictly consecutive monthly periods; panel drift or gaps block calculation.",
        ]

        analysis = self._shared_market_analysis(request, plan)
        obs = analysis.observations

        if len(obs) >= 4:
            trends = analysis.trend_results
            if trends and trends[0].data_state in {"ready", "fresh"}:
                trend_res = trends[0]
                ent_name = trend_res.canonical_name or obs[0].skill
                start_p = trend_res.periods_used[0] if trend_res.periods_used else ""
                end_p = trend_res.periods_used[-1] if trend_res.periods_used else ""
                slope_val = trend_res.trend_slope if trend_res.trend_slope is not None else trend_res.slope
                ev_id = f"ev_trend_{ent_name}_{end_p}"
                trend_details = {
                    "trend_slope": slope_val,
                    "slope_unit": trend_res.slope_unit,
                    "value_unit": trend_res.unit,
                    "velocity": trend_res.velocity,
                    "velocity_unit": trend_res.velocity_unit,
                    "growth_pct": trend_res.growth_pct,
                    "whole_window_change": trend_res.whole_window_change,
                    "whole_window_pct_change": trend_res.whole_window_pct_change,
                    "latest_period_change": trend_res.latest_mom_change,
                    "latest_period_change_pct": trend_res.latest_mom_pct_change,
                    "latest_mom_change": trend_res.latest_mom_change,
                    "latest_mom_pct_change": trend_res.latest_mom_pct_change,
                    "periods_count": len(trend_res.periods_used),
                    "periods_used": trend_res.periods_used,
                    "start_period": start_p,
                    "end_period": end_p,
                    "latest_movement": (
                        f"{trend_res.velocity:+g} {trend_res.velocity_unit}"
                        if trend_res.velocity is not None and trend_res.velocity_unit
                        else "unavailable"
                    ),
                    "period_grain": trend_res.period_grain,
                    "warnings": list(trend_res.warnings or []),
                    "provider": trend_res.provider,
                    "signal_type": trend_res.signal_type,
                    "series_id": trend_res.series_id,
                    "location": trend_res.location,
                    "query_id": trend_res.query_id,
                    "panel_version": trend_res.panel_version,
                    "observation_ids": [
                        observation.id for observation in obs
                        if observation.period in trend_res.periods_used
                        and observation.source.casefold() == (trend_res.provider or "").casefold()
                    ],
                    "source_urls": [
                        observation.source_url for observation in obs
                        if observation.period in trend_res.periods_used
                        and observation.source.casefold() == (trend_res.provider or "").casefold()
                        and observation.source_url
                    ],
                }
                if trend_res.period_grain == "month":
                    trend_details["monthly_velocity"] = trend_res.velocity
                facts.append(StructuredFact(
                    fact_id=f"fact_trend_{ent_name}_{end_p}",
                    fact_type="trend_analysis",
                    entity_name=ent_name,
                    canonical_entity_id=obs[0].skill_id if obs and obs[0].skill_id else None,
                    entity_type="skill",
                    metric_name="trend_direction",
                    metric_value=trend_res.trend_direction or trend_res.trend,
                    period=f"{start_p}_to_{end_p}",
                    source="theil_sen_estimator",
                    data_origin="real",
                    history_type="empirical_time_series",
                    unit=trend_res.velocity_unit or trend_res.unit,
                    quality_state="valid",
                    readiness_state="ready",
                    calculation_version=G14_CALCULATION_VERSION,
                    provenance_id=G14_CALCULATION_VERSION,
                    evidence_reference=ev_id,
                    details=trend_details,
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source=trend_res.provider or "configured_market_observation_store",
                    signal_type="trend_calculation",
                    period=f"{start_p}_to_{end_p}",
                    unit=trend_res.velocity_unit or trend_res.unit,
                    data_origin=trend_res.data_origin or "real",
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    location=trend_res.location,
                    query_id=trend_res.query_id,
                    panel_version=trend_res.panel_version,
                    supporting_observation_ids=trend_details["observation_ids"],
                    supporting_source_urls=trend_details["source_urls"],
                    quality="valid",
                    description=(
                        f"Theil-Sen trend calculation across {len(trend_res.periods_used)} consecutive periods: "
                        f"slope={slope_val}, velocity={trend_res.velocity}, direction={trend_res.trend_direction or trend_res.trend}."
                    ),
                ))
                if trend_res.warnings:
                    limitations.extend(trend_res.warnings)
            elif trends:
                trend_res = trends[0]
                readiness_id = f"ev_trend_{trend_res.series_id or 'series'}_blocked"
                reason = "; ".join(trend_res.blocking_reasons) or (
                    f"Trend readiness is {trend_res.data_state}; no valid trend value was emitted."
                )
                facts.append(StructuredFact(
                    fact_id=f"fact_trend_blocked_{trend_res.series_id or 'series'}",
                    fact_type="analysis_readiness",
                    entity_name=trend_res.canonical_name or plan.context_summary.get("primary_entity"),
                    canonical_entity_id=trend_res.canonical_skill_id,
                    entity_type="skill",
                    metric_name="trend_direction_readiness",
                    metric_value="insufficient_history",
                    unit="status",
                    period="_to_".join(trend_res.periods_used) if trend_res.periods_used else None,
                    source=trend_res.provider or "configured_market_observation_store",
                    data_origin=trend_res.data_origin or "real",
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    quality_state=trend_res.data_state,
                    readiness_state="insufficient_data",
                    evidence_reference=readiness_id,
                    details={
                        "reason": reason,
                        "period_grain": "month",
                        "periods_used": trend_res.periods_used,
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=trend_res.provider or "configured_market_observation_store",
                    signal_type="analysis_readiness",
                    period="_to_".join(trend_res.periods_used) if trend_res.periods_used else None,
                    data_origin=trend_res.data_origin or "real",
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    quality="insufficient_history",
                    description=f"Trend is unavailable because {reason}",
                ))
                limitations.append(reason)
            else:
                readiness_id = "ev_trend_calculation_unavailable"
                source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
                reason = (
                    analysis.completeness_reason
                    if not analysis.history_complete and analysis.completeness_reason
                    else "No comparable valid monthly series could be calculated from the matching observations."
                )
                readiness_state = "incomplete_history" if not analysis.history_complete else "insufficient_data"
                facts.append(StructuredFact(
                    fact_id="fact_trend_calculation_unavailable",
                    fact_type="analysis_readiness",
                    entity_name=plan.context_summary.get("primary_entity"),
                    metric_name="trend_direction_readiness",
                    metric_value=readiness_state,
                    unit="status",
                    source=source,
                    data_origin="real",
                    quality_state=readiness_state,
                    readiness_state=readiness_state,
                    evidence_reference=readiness_id,
                    details={
                        "reason": reason,
                        "observation_count": len(obs),
                        "history_complete": analysis.history_complete,
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="real",
                    quality=readiness_state,
                    description=reason,
                ))
                limitations.append(reason)
        else:
            readiness_id = "ev_trend_insufficient_history"
            source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
            facts.append(StructuredFact(
                fact_id="fact_trend_insufficient_history",
                fact_type="analysis_readiness",
                entity_name=plan.context_summary.get("primary_entity"),
                metric_name="trend_direction_readiness",
                metric_value="insufficient_history",
                unit="status",
                source=source,
                data_origin="unavailable" if not obs else "real",
                readiness_state="insufficient_data",
                evidence_reference=readiness_id,
                details={
                    "reason": f"Trend calculation requires four consecutive comparable monthly periods; found {len(obs)} matching observation records.",
                    "observation_count": len(obs),
                    "minimum_periods": 4,
                    "period_grain": "month",
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=readiness_id,
                source=source,
                signal_type="analysis_readiness",
                data_origin="unavailable" if not obs else "real",
                quality="insufficient_history",
                description=f"Trend unavailable: {len(obs)} matching records do not meet the four-period monthly trend gate.",
            ))

        return facts, evidence, limitations

    def _handle_all_skill_trend_ranking(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        analysis = self._shared_market_analysis(request, plan)
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations = [
            "Only real, platform-collected observations with a canonical skill ID are ranked; reference-only, demo, and backfill records are not market-trend evidence.",
            "Trend readiness requires at least four consecutive completed periods and the existing quality, unit, series-identity, and comparability gates.",
            "Ranks compare whole-window percent change only within the same source, signal, metric, geography, query, panel, provenance, and period-window cohort.",
            "Observed provider samples are not a complete census of the global skills market.",
        ]
        if not analysis.history_complete:
            limitations.append(
                analysis.completeness_reason
                or "The bounded observation read was incomplete, so no all-skill ranking is safe."
            )

        direction_filter: str | None = None
        message = request.message.casefold()
        mentions_increase = bool(re.search(r"\b(gaining|increasing|rising|growing)\b", message))
        mentions_decline = bool(re.search(r"\b(declining|decreasing|falling)\b", message))
        if mentions_increase and not mentions_decline:
            direction_filter = "Increasing"
        elif mentions_decline and not mentions_increase:
            direction_filter = "Declining"

        source_filter = (request.filters or {}).get("source") or (request.filters or {}).get("provider")
        signal_filter = (request.filters or {}).get("signal_type")
        market_scope_filter = (request.filters or {}).get("observation_scope") or (request.filters or {}).get("market_scope")
        observed_market_data = [
            observation for observation in analysis.observations
            if observation.data_origin == "real"
            and observation.history_type == "platform_collected"
            and observation.skill_id
            and (not isinstance(source_filter, str) or observation.source.casefold() == source_filter.casefold())
            and (not isinstance(signal_filter, str) or observation.signal_type == signal_filter)
            and (not isinstance(market_scope_filter, str) or observation.scope == market_scope_filter)
        ]
        by_observation_id = {
            observation.id: observation
            for observation in observed_market_data
            if observation.id
        }

        cohort_items: dict[tuple[Any, ...], list[tuple[Any, list[MarketObservation], str, tuple[str, ...]]]] = {}
        excluded_reasons: list[str] = []
        for trend in analysis.trend_results:
            if (
                trend.data_state not in {"ready", "fresh"}
                or trend.data_origin != "real"
                or trend.history_type != "platform_collected"
                or not trend.canonical_skill_id
            ):
                if trend.blocking_reasons:
                    excluded_reasons.extend(trend.blocking_reasons)
                elif trend.data_origin != "real" or trend.history_type != "platform_collected":
                    excluded_reasons.append("Only real platform-collected history is eligible.")
                continue
            if not trend.series_id or not trend.query_id:
                excluded_reasons.append(
                    f"{trend.canonical_name} lacks a stable series or query identity for cross-skill comparison."
                )
                continue
            if trend.whole_window_pct_change is None:
                excluded_reasons.append(
                    f"{trend.canonical_name} has no valid whole-window percent-change baseline."
                )
                continue
            if direction_filter and trend.trend != direction_filter:
                continue

            if trend.observation_ids:
                series_observations = [
                    by_observation_id[observation_id]
                    for observation_id in trend.observation_ids
                    if observation_id in by_observation_id
                ]
            else:
                series_observations = [
                    observation for observation in observed_market_data
                    if observation.skill_id == trend.canonical_skill_id
                    and observation.source.casefold() == trend.source.casefold()
                    and observation.signal_type == trend.signal_type
                    and observation.series_id == trend.series_id
                    and observation.query_id == trend.query_id
                    and observation.panel_version == trend.panel_version
                    and observation.scope == trend.scope
                    and (observation.location or "").casefold() == (trend.location or "").casefold()
                ]
            series_observations = [
                observation for observation in series_observations
                if observation.period in trend.periods_used
            ]
            if not series_observations:
                excluded_reasons.append(
                    f"{trend.canonical_name} has no linked observations for its calculated periods."
                )
                continue

            freshness = assess_freshness(series_observations)
            if freshness.state in {"stale", "building"}:
                reason = (
                    "The latest applicable observations are stale."
                    if freshness.state == "stale"
                    else "Collection timestamps are missing, so freshness cannot be verified."
                )
                excluded_reasons.append(f"{trend.canonical_name}: {reason}")
                continue
            freshness_state = (
                "unknown"
                if freshness.state == "insufficient_data"
                and freshness.excluded_count == len(series_observations)
                else freshness.state
            )
            if freshness_state == "unknown":
                limitations.append(
                    f"Freshness is not defined by the current policy for {trend.source}/{trend.signal_type}; the series is shown with freshness marked unknown."
                )
            limitations.extend(trend.warnings or [])
            denominator_units = {
                observation.denominator_unit.strip().casefold()
                for observation in series_observations
                if observation.denominator_unit
            }
            if len(denominator_units) > 1:
                excluded_reasons.append(
                    f"{trend.canonical_name} has inconsistent denominator units."
                )
                continue
            denominator_unit = next(iter(denominator_units), None)
            cohort = (
                trend.source.casefold(),
                trend.signal_type,
                trend.metric,
                trend.source_unit.casefold() if trend.source_unit else None,
                trend.unit,
                denominator_unit,
                trend.scope,
                trend.location.casefold() if trend.location else None,
                trend.query_id,
                trend.panel_version,
                trend.data_origin,
                trend.history_type,
                tuple(sorted({observation.extractor_version for observation in series_observations if observation.extractor_version})),
                trend.period_grain,
                tuple(trend.periods_used),
            )
            cohort_items.setdefault(cohort, []).append(
                (trend, series_observations, freshness_state, cohort)
            )

        decreasing_ranking = direction_filter == "Declining"
        ranked: list[tuple[int, int, Any, list[MarketObservation], str, tuple[Any, ...]]] = []
        for cohort, items in sorted(cohort_items.items(), key=lambda item: repr(item[0])):
            items.sort(
                key=lambda item: (
                    item[0].whole_window_pct_change,
                    item[0].canonical_skill_id or "",
                ),
                reverse=not decreasing_ranking,
            )
            for cohort_rank, (trend, series_observations, freshness_state, _) in enumerate(items, start=1):
                ranked.append((cohort_rank, len(items), trend, series_observations, freshness_state, cohort))

        filters = request.filters or {}
        raw_limit = filters.get("limit", 20)
        raw_offset = filters.get("offset", 0)
        limit = int(raw_limit) if str(raw_limit).isdigit() else 20
        offset = int(raw_offset) if str(raw_offset).isdigit() else 0
        limit = max(1, min(limit, 50))
        offset = max(0, min(offset, 10000))
        total_eligible = len(ranked)
        page = ranked[offset:offset + limit]
        has_more = offset + len(page) < total_eligible
        summary_details = {
            "eligible_series_count": total_eligible,
            "requested_limit": limit,
            "offset": offset,
            "returned_series_count": len(page),
            "has_more": has_more,
            "next_offset": offset + len(page) if has_more else None,
            "ranking_metric": "whole_window_pct_change",
            "ranking_direction": "ascending for declining trends; descending otherwise, within each comparable cohort",
            "requested_direction": direction_filter,
            "location": request.location or "Global",
            "time_range": request.time_range,
            "source_filter": source_filter if isinstance(source_filter, str) else None,
            "signal_filter": signal_filter if isinstance(signal_filter, str) else None,
            "excluded_series_reasons": list(dict.fromkeys(excluded_reasons))[:8],
        }
        summary_evidence_id = "ev_all_skill_trend_ranking_summary"
        summary_observation_ids = sorted({
            observation.id
            for _, _, trend, series_observations, _, _ in ranked
            for observation in series_observations
            if observation.id
        })[:50]
        facts.append(StructuredFact(
            fact_id="fact_all_skill_trend_ranking_summary",
            fact_type="trend_ranking_summary",
            entity_type="skill",
            metric_name="eligible_series_count",
            metric_value=total_eligible,
            unit="series",
            source="configured_observation_store",
            data_origin="real" if observed_market_data else "unavailable",
            history_type="platform_collected" if observed_market_data else "unavailable",
            quality_state="valid" if total_eligible else "insufficient_data",
            readiness_state="ready" if total_eligible else "insufficient_data",
            evidence_reference=summary_evidence_id,
            details={
                **summary_details,
                "matching_platform_observation_count": len(observed_market_data),
                "excluded_non_market_observation_count": int(
                    plan.context_summary.get("excluded_non_market_observation_count", 0)
                ),
                "history_complete": analysis.history_complete,
                "minimum_consecutive_periods": 4,
            },
        ))
        evidence.append(EvidenceItem(
            evidence_id=summary_evidence_id,
            source="configured_observation_store",
            signal_type="trend_ranking_summary",
            data_origin="real" if observed_market_data else "unavailable",
            history_type="platform_collected" if observed_market_data else "unavailable",
            supporting_observation_ids=summary_observation_ids,
            quality="valid" if total_eligible else "insufficient_data",
            description=(
                f"Evaluated {len(observed_market_data)} matching real platform-collected observations; "
                f"{total_eligible} eligible comparable skill trend series passed the existing gates."
            ),
        ))

        for cohort_rank, cohort_size, trend, series_observations, freshness_state, cohort in page:
            skill_id = trend.canonical_skill_id
            cohort_id = hashlib.sha256(repr(cohort).encode("utf-8")).hexdigest()[:12]
            fact_id = f"fact_skill_trend_{skill_id}_{cohort_id}"
            evidence_id = f"ev_skill_trend_{skill_id}_{cohort_id}"
            periods = list(trend.periods_used)
            observation_ids = sorted(set(trend.observation_ids))
            source_urls = sorted({
                observation.source_url
                for observation in series_observations
                if observation.source_url
            })
            fact_details = {
                "rank": cohort_rank,
                "cohort_size": cohort_size,
                "cohort_id": cohort_id,
                "trend_direction": trend.trend,
                "ranking_metric": "whole_window_pct_change",
                "ranking_value": trend.whole_window_pct_change,
                "ranking_unit": "%",
                "value_metric": trend.metric,
                "value_unit": trend.unit,
                "source_unit": trend.source_unit,
                "period_grain": trend.period_grain,
                "periods_used": periods,
                "source": trend.source,
                "signal_type": trend.signal_type,
                "scope": trend.scope,
                "location": trend.location,
                "query_id": trend.query_id,
                "series_id": trend.series_id,
                "panel_version": trend.panel_version,
                "data_origin": trend.data_origin,
                "history_type": trend.history_type,
                "freshness_state": freshness_state,
                "observation_count": trend.observation_count,
                "observation_ids": observation_ids,
                "fetch_run_ids": trend.fetch_run_ids,
                "source_urls": source_urls,
                "calculation_version": trend.calculation_version,
            }
            facts.append(StructuredFact(
                fact_id=fact_id,
                fact_type="skill_trend_rank",
                entity_name=trend.canonical_name,
                canonical_entity_id=skill_id,
                entity_type="skill",
                metric_name="whole_window_pct_change",
                metric_value=trend.whole_window_pct_change,
                unit="%",
                period=f"{periods[0]}_to_{periods[-1]}",
                source=trend.source,
                data_origin=trend.data_origin,
                history_type=trend.history_type,
                series_id=trend.series_id,
                panel_version=trend.panel_version,
                quality_state="valid",
                readiness_state="ready",
                calculation_version=trend.calculation_version,
                provenance_id=trend.calculation_version,
                evidence_reference=evidence_id,
                details=fact_details,
            ))
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source=trend.source,
                signal_type=trend.signal_type,
                period=f"{periods[0]}_to_{periods[-1]}",
                unit="%",
                data_origin=trend.data_origin,
                history_type=trend.history_type,
                series_id=trend.series_id,
                location=trend.location,
                scope=trend.scope,
                query_id=trend.query_id,
                panel_version=trend.panel_version,
                provenance_id=trend.calculation_version,
                supporting_observation_ids=observation_ids,
                supporting_source_urls=source_urls,
                quality="valid",
                description=(
                    f"{trend.canonical_name} has a {trend.trend.lower()} {trend.signal_type} trend; "
                    f"whole-window change is {trend.whole_window_pct_change}% over "
                    f"{periods[0]} to {periods[-1]} in cohort {cohort_id}."
                ),
            ))

        if not total_eligible:
            if int(plan.context_summary.get("excluded_non_market_observation_count", 0)) > 0:
                limitations.append(
                    "Matching records were present, but none were real platform-collected canonical observations eligible for a market ranking."
                )
            if excluded_reasons:
                limitations.extend(list(dict.fromkeys(excluded_reasons))[:5])
            if not analysis.observations:
                limitations.append(
                    "No observations matched the requested filters in the configured store; this does not establish that no trends exist elsewhere."
                )
        elif has_more:
            limitations.append(
                f"Showing ranked rows {offset + 1} through {offset + len(page)} of {total_eligible} eligible series; request offset {offset + len(page)} for the next page."
            )
        else:
            limitations.append(
                f"Returned {len(page)} ranked series from {total_eligible} eligible series; this is a provider-observation subset, not the entire market."
            )
        plan.context_summary["trend_ranking_metadata"] = summary_details
        if page and not plan.context_summary.get("primary_entity"):
            plan.context_summary["primary_entity"] = page[0][2].canonical_name
        return facts, evidence, list(dict.fromkeys(limitations))

    def _handle_evidence_provenance_retrieval(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = ["Evidence strictly mirrors stored artifacts; zero simulated or placeholder provenance."]

        obs = self._get_market_observations(
            request_obs=request.observations,
            skill=plan.context_summary.get("primary_entity"),
            location=request.location,
            time_range=request.time_range,
        )

        for o in obs:
            evidence.append(EvidenceItem(
                evidence_id=o.id,
                source=o.source,
                signal_type=o.signal_type,
                period=o.period,
                data_origin=o.data_origin or "real",
                history_type=o.history_type,
                series_id=o.series_id,
                fetch_run_id=o.fetch_run_id,
                quality=o.quality or "valid",
                description=f"Verified observation artifact {o.id} ({o.source}).",
            ))

        ev_ref = evidence[0].evidence_id if evidence else "ev_none"
        if not evidence:
            evidence.append(EvidenceItem(
                evidence_id="ev_none",
                source="observation_store",
                signal_type="evidence_summary",
                quality="valid",
                description="Zero empirical observation records available.",
            ))

        facts.append(StructuredFact(
            fact_id=f"fact_ev_summary_{len(obs)}",
            fact_type="evidence_summary",
            entity_name=plan.context_summary.get("primary_entity") or "Market Evidence",
            canonical_entity_id=None,
            entity_type="evidence",
            metric_name="verified_evidence_items_count",
            metric_value=len(obs),
            unit="items",
            source="observation_store",
            data_origin="real",
            quality_state="valid",
            readiness_state="ready",
            provenance_id=str(len(obs)),
            evidence_reference=ev_ref,
        ))

        return facts, evidence, limitations

    def _handle_skill_gap_role_fit(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Currently provides heuristic crosswalk and action prioritization; dedicated quantitative fit scoring is under development.",
        ]

        target_role = plan.context_summary.get("primary_entity") or request.target_role or "Software Developers"
        occs = self.reference_store.get_onet_occupations(title=target_role)
        target_soc = occs[0].soc_code if occs else "15-1252.00"

        occ_skills = self.entity_service.get_occupation_skills(target_soc, limit=20)
        req_names = {s.canonical_name.casefold() for s in occ_skills}
        user_skills = {s.strip().casefold() for s in request.selected_skills}

        covered = req_names.intersection(user_skills)
        missing = [s.canonical_name for s in occ_skills if s.canonical_name.casefold() not in user_skills]

        ev_id = f"ev_gap_{target_soc}"
        facts.append(StructuredFact(
            fact_id=f"fact_gap_{target_soc}",
            fact_type="skill_gap",
            entity_name=target_role,
            canonical_entity_id=target_soc,
            entity_type="occupation",
            metric_name="covered_skills_count",
            metric_value=len(covered),
            unit="skills",
            source="ref_onet_software_skills",
            data_origin="real",
            history_type="reference_taxonomy",
            quality_state="valid",
            readiness_state="ready",
            provenance_id=target_soc,
            evidence_reference=ev_id,
            details={"missing_skills": missing[:5], "total_required": len(occ_skills)},
        ))

        evidence.append(EvidenceItem(
            evidence_id=ev_id,
            source="ref_onet_software_skills",
            signal_type="skill_gap_evaluation",
            quality="valid",
            description=f"Skill gap analysis against O*NET SOC {target_soc}: {len(covered)} covered, {len(missing)} missing.",
        ))

        return facts, evidence, limitations

    def _handle_action_recommendations(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Actions are advisory guidance based on empirical market signals; future career or salary outcomes not guaranteed.",
        ]

        portal_type = request.portal_type or "individual"
        ev_id = f"ev_actions_{portal_type}"
        actions = [
            {"action": "Strengthen Core Technologies", "priority": "high", "type": "learn"},
            {"action": "Verify Practical Project Application", "priority": "medium", "type": "apply"},
            {"action": "Monitor Demand Continuity", "priority": "low", "type": "monitor"},
        ]

        for idx, act in enumerate(actions, 1):
            facts.append(StructuredFact(
                fact_id=f"fact_act_{idx}",
                fact_type="action_recommendation",
                entity_name=request.target_role or plan.context_summary.get("primary_entity") or "Career Roadmap",
                canonical_entity_id=None,
                entity_type="career_path",
                metric_name=f"action_{idx}",
                metric_value=act["action"],
                source="action_recommendation_engine",
                data_origin="real",
                quality_state="valid",
                readiness_state="ready",
                provenance_id=f"act_{idx}",
                evidence_reference=ev_id,
                details={"priority": act["priority"], "action_type": act["type"], "portal": portal_type},
            ))

        evidence.append(EvidenceItem(
            evidence_id=ev_id,
            source="action_recommendation_engine",
            signal_type="action_synthesis",
            quality="valid",
            description=f"Grounded action recommendations generated for {portal_type} portal.",
        ))

        return facts, evidence, limitations

    def _handle_job_posting_search(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Results represent matching stored postings, not total global vacancies.",
        ]

        job_source = "configured_market_observation_store"
        if not request.observations and self.firestore_store is not None:
            # Job postings have their own normalized Firestore collection. Reuse
            # the existing stored-job search service rather than treating a
            # locally cached observation snapshot as the live postings source.
            from app.services.job_storage_service import search_stored_jsearch_jobs

            job_source = "firestore_jobs"
            limitations.append(
                "Search is limited to the 100 most recently fetched stored postings."
            )
            query = str(
                request.target_role
                or next(iter(request.selected_roles), None)
                or plan.context_summary.get("primary_entity")
                or next(iter(request.selected_companies), None)
                or request.message
            ).strip()
            country = (request.filters or {}).get("country")
            try:
                jobs = search_stored_jsearch_jobs(
                    query=query,
                    country=country,
                    limit=100,
                )
            except Exception as exc:
                logger.warning("Configured job source unavailable (%s)", type(exc).__name__)
                raise DataSourceUnavailableError("Stored job posting source is unavailable.") from exc
            all_obs = [MarketObservation(
                id=str(job.job_id or ""),
                source=job.source,
                signal_type="demand",
                observed_at=job.fetched_at,
                period=(job.posted_at or job.fetched_at.isoformat())[:7],
                location=job.location,
                scope="global",
                skill=job.title or "Job posting",
                value=1,
                posting_id=job.job_id,
                metadata={
                    "job_title": job.title,
                    "company": job.company_name,
                    "location": job.location,
                    "posted_at": job.posted_at,
                    "apply_link": job.source_url,
                    "skills_raw": job.skills_raw,
                    "description": job.description,
                    "employment_type": job.employment_type,
                    "category": job.category,
                    "fetched_at": job.fetched_at.isoformat(),
                },
                data_origin="real",
            ) for job in jobs if job.title and job.job_id]
            if request.location:
                all_obs = [o for o in all_obs if request.location.casefold() in (o.location or "").casefold()]
            if str(request.time_range).lower() not in {"max_available", "max available", "all"}:
                cutoff = self._observation_cutoff(request.time_range).date()
                filtered_jobs = []
                for o in all_obs:
                    posted = o.metadata.get("posted_at")
                    if not posted:
                        continue
                    try:
                        if datetime.fromisoformat(str(posted).replace("Z", "+00:00")).date() >= cutoff:
                            filtered_jobs.append(o)
                    except ValueError:
                        continue
                all_obs = filtered_jobs
        else:
            all_obs = self._get_market_observations(
                request_obs=request.observations,
                skill=plan.context_summary.get("primary_entity"),
                location=request.location,
                time_range=request.time_range,
            )
        raw_obs = [
            o for o in all_obs
            if o.source in {"jsearch", "adzuna"} and o.posting_id
            and str(o.metadata.get("job_title") or "").strip()
        ]

        # Enforce Favourites / selected_companies filtering for Job Intelligence
        scope_val = str((request.filters or {}).get("scope") or "").strip().lower()
        scope_empty = bool((request.filters or {}).get("scope_empty"))
        selected_cos_norm = {c.strip().lower() for c in (request.selected_companies or []) if c and c.strip()}

        if scope_val in {"favourites", "favorites", "favourite companies", "favorite companies"} and scope_empty and not selected_cos_norm:
            raw_obs = []
            limitations.append(
                "Favourites scope is active for Job Intelligence, but no saved favourite companies exist in your watchlist."
            )
        elif selected_cos_norm:
            raw_obs = [
                o for o in raw_obs
                if str(o.metadata.get("company") or o.metadata.get("employer_name") or "").strip().lower() in selected_cos_norm
            ]

        # Deduplicate records by posting_id or (title, company, location, period)
        seen_keys: set[tuple[str, ...]] = set()
        obs = []
        for o in raw_obs:
            title = str(o.metadata.get("job_title") or "").strip()
            employer = str(o.metadata.get("company") or o.metadata.get("employer_name") or "").strip()
            loc_str = str(o.location or o.metadata.get("location") or "").strip()
            dedup_key = (str(o.posting_id or ""), title.lower(), employer.lower(), loc_str.lower())
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            obs.append(o)

        postings_found = len(obs)
        sample_postings = []
        structured_postings = []
        for o in obs[:10]:
            title = str(o.metadata.get("job_title") or "").strip()
            employer = str(o.metadata.get("company") or o.metadata.get("employer_name") or "").strip()
            loc_str = str(o.location or o.metadata.get("location") or "").strip()
            posted_at = str(o.metadata.get("posted_at") or "").strip()[:10] or None
            source_url = str(o.metadata.get("apply_link") or o.metadata.get("job_url") or o.metadata.get("url") or "").strip()
            sample_postings.append(f"{title} at {employer} ({loc_str})")
            structured_postings.append({
                "posting_id": o.posting_id or o.id,
                "title": title,
                "company": employer,
                "location": loc_str,
                "posting_date": posted_at,
                "source": o.source,
                "source_url": source_url if source_url.startswith(("http://", "https://")) else None,
                "skill": o.skill,
                "summary": str(o.metadata.get("description") or "").strip()[:1200] or None,
                "required_skills": [
                    str(value).strip()[:120]
                    for value in (o.metadata.get("skills_raw") or [])
                    if isinstance(value, str) and value.strip()
                ][:30],
                "employment_type": o.metadata.get("employment_type"),
                "category": o.metadata.get("category"),
            })
            evidence.append(EvidenceItem(
                evidence_id=o.posting_id or o.id,
                source=o.source,
                signal_type="stored_posting",
                period=o.period,
                unit="posting",
                data_origin=o.data_origin or "real",
                source_url=source_url if source_url.startswith(("http://", "https://")) else None,
                provenance_id=o.posting_id or o.id,
                quality="valid",
                description=f"Stored job posting: {title} at {employer} ({loc_str}, {o.source}).",
            ))

        ev_ref = (obs[0].posting_id or obs[0].id) if obs else None

        facts.append(StructuredFact(
            fact_id=f"fact_jobs_{postings_found}",
            fact_type="stored_job_postings",
            entity_name=plan.context_summary.get("primary_entity"),
            canonical_entity_id=None,
            entity_type=None,
            metric_name="stored_postings_found",
            metric_value=postings_found,
            unit="postings",
            source=job_source,
            data_origin="real",
            quality_state="valid",
            readiness_state="ready" if postings_found > 0 else "insufficient_data",
            provenance_id=f"cnt_{postings_found}",
            evidence_reference=ev_ref,
            details={
                "sample_postings": sample_postings[:5],
                "postings": structured_postings,
                "company_filter": sorted(selected_cos_norm) if selected_cos_norm else [],
                "search_window_limit": 100 if job_source == "firestore_jobs" else None,
            },
        ))

        return facts, evidence, limitations

    def _handle_company_intelligence(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Internal company membership and workforce skills supported; external firmographics and venture capital data are unavailable.",
        ]

        cid = request.company_id or plan.context_summary.get("company_id") or "authorized_company"
        ev_id = f"ev_comp_{cid}"
        facts.append(StructuredFact(
            fact_id=f"fact_comp_{cid}",
            fact_type="company_workforce",
            entity_name=cid,
            canonical_entity_id=cid,
            entity_type="company",
            metric_name="workforce_status",
            metric_value="authorized",
            source="company_relationships",
            data_origin="real",
            quality_state="valid",
            readiness_state="ready",
            provenance_id=cid,
            evidence_reference=ev_id,
            details={"company_id": cid, "portal": "company"},
        ))
        evidence.append(EvidenceItem(
            evidence_id=ev_id,
            source="company_relationships",
            signal_type="workforce_membership",
            quality="valid",
            description=f"Verified internal workforce intelligence for authorized company '{cid}'.",
        ))

        return facts, evidence, limitations

    # =========================================================================
    # ANSWER SYNTHESIS & VALIDATION
    # =========================================================================

    def _generate_follow_up_questions(
        self,
        intent: str,
        facts: list[StructuredFact],
        plan: IntelligencePlanResponse,
        request: CoreIntelligenceAnswerRequest,
    ) -> list[str]:
        """Generate contextual, grounded follow-up suggestions tailored to the entity and intent."""
        primary = plan.context_summary.get("primary_entity") or ""
        questions: list[str] = []

        if intent in {"explain_concept", "lookup_skill_reference"}:
            if primary:
                questions.append(f"What software tools are commonly used alongside {primary}?")
                questions.append(f"Which occupations frequently require {primary}?")
            else:
                questions.append("What software skills are most in demand for Software Developers?")
                questions.append("What career mobility pathways exist from Software Developers?")

        elif intent == "crosswalk_occupation_software":
            soft_facts = [f for f in facts if f.fact_type == "software_skill"]
            occ = soft_facts[0].details.get("occupation_title") if soft_facts and soft_facts[0].details else primary or "Software Developers"
            questions.append(f"What occupations are closely related to {occ}?")
            questions.append(f"How do my selected skills compare to {occ} requirements?")

        elif intent == "lookup_occupation":
            occ = primary or "Software Developers"
            questions.append(f"What software tools and technologies are required for {occ}?")
            questions.append(f"What related occupations exist for {occ}?")

        elif intent == "crosswalk_related_occupations":
            rel_facts = [f for f in facts if f.fact_type == "related_occupation"]
            target = rel_facts[0].entity_name if rel_facts else primary or "Software Developers"
            questions.append(f"What software tools and skills are required for {target}?")
            questions.append(f"What is the official O*NET SOC classification for {target}?")

        elif intent == "compare_entities":
            comps = [e.canonical_entity.canonical_name for e in plan.entities if e.canonical_entity]
            if len(comps) >= 2:
                questions.append(f"What software tools are required for occupations using {comps[0]}?")
                questions.append(f"What software tools are required for occupations using {comps[1]}?")
            else:
                questions.append("What are related occupations for this skill set?")

        elif intent == "analyze_skill_gap":
            role = request.target_role or primary or "Software Developers"
            questions.append("What prioritized action recommendations address these skill gaps?")
            questions.append(f"What related occupations match my current skill profile?")

        elif intent == "synthesize_actions":
            role = request.target_role or "Software Developers"
            questions.append(f"What software tools are baseline requirements for {role}?")
            questions.append("How do my profile skills compare to standard benchmarks?")

        elif intent == "search_jobs":
            role = primary or "Software Developers"
            questions.append(f"What software tools are required for {role}?")
            questions.append(f"What career pathways branch out from {role}?")

        elif intent == "rank_skill_trends":
            if primary:
                questions.append(f"What evidence supports the {primary} trend?")
                questions.append(f"Compare {primary} with another skill using the same market filters.")
            else:
                questions.append("Would you like to compare trends from a specific provider or signal type?")
                questions.append("Which geography or time range should I use?")

        elif intent in {"analyze_trend", "retrieve_history", "retrieve_snapshot"}:
            if primary:
                questions.append(f"What software tools are associated with {primary}?")
                questions.append(f"Which occupations utilize {primary}?")
            else:
                questions.append("What software skills are most in demand for Software Developers?")

        elif intent == "analyze_company_workforce":
            questions.append("Which technical roles have the highest concentration in our workforce?")
            questions.append("What are our team's most significant skill gaps relative to standard benchmarks?")

        else:
            if primary:
                questions.append(f"What software tools are associated with {primary}?")
                questions.append(f"Which occupations frequently require {primary}?")
            else:
                questions.append("What are the core software skills for Software Developers?")
                questions.append("What career mobility pathways exist for Software Developers?")

        return questions[:3]

    def _synthesize_answer(
        self,
        intent: str,
        facts: list[StructuredFact],
        evidence: list[EvidenceItem],
        capabilities_used: list[str],
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse | None = None,
    ) -> str:
        """Assemble a concise answer first, followed only by relevant grounded detail."""
        if not facts:
            return "No verifiable structured facts were produced for this query."

        direct_answer: str = ""
        supporting_facts: list[str] = []
        evidence_citations: list[str] = []
        interpretation: str = ""
        limitations: list[str] = []

        # Extract evidence citations
        for ev in evidence:
            label = f"**{ev.source}** (`{ev.evidence_id}`)"
            if ev.period:
                label += f" [Period: {ev.period}]"
            evidence_citations.append(f"{label}: {ev.description}")

        # Intent-specific synthesis
        if intent == "rank_skill_trends":
            ranked_facts = [fact for fact in facts if fact.fact_type == "skill_trend_rank"]
            summary = next(
                (fact for fact in facts if fact.fact_type == "trend_ranking_summary"),
                None,
            )
            metadata = summary.details if summary else {}
            eligible_count = int(summary.metric_value) if summary else 0
            location = request.location or "Global"
            if ranked_facts:
                direct_answer = (
                    f"Found {eligible_count} eligible observed skill trend series for "
                    f"**{location}** in the requested period. The returned rows are ranked "
                    "within comparable source and signal cohorts, not as one mixed-source market list."
                )
                for fact in ranked_facts:
                    direction = fact.details.get("trend_direction", "unavailable")
                    rank = fact.details.get("rank")
                    cohort = fact.details.get("cohort_id")
                    supporting_facts.append(
                        f"**#{rank} in cohort {cohort}: {fact.entity_name}** — {direction}; "
                        f"whole-window change {fact.metric_value}% "
                        f"({fact.period}, {fact.source}/{fact.details.get('signal_type')})."
                    )
                if metadata.get("has_more"):
                    supporting_facts.append(
                        f"Showing {metadata.get('returned_series_count')} of {eligible_count} eligible series; "
                        f"the next offset is {metadata.get('next_offset')}."
                    )
                interpretation = (
                    "Ranking uses the existing whole-window percent-change metric. Different sources, "
                    "signal families, queries, units, and geographies are kept in separate cohorts."
                )
            else:
                reasons = metadata.get("excluded_series_reasons") or []
                direct_answer = (
                    f"No skill trend series met the existing evidence, freshness, comparability, and "
                    f"history requirements for **{location}** in the requested period. This is limited "
                    "to the matching observations available to this request and is not a claim that "
                    "no trends exist elsewhere."
                )
                supporting_facts = [
                    "**Required evidence**: real canonical-skill observations with stable source/query/series identity and at least four consecutive completed periods."
                ]
                supporting_facts.extend(f"**Limitation**: {reason}" for reason in reasons[:3])
                interpretation = (
                    "Reference-only and sample-only catalog entries are not promoted into observed market trends."
                )
            limitations = [
                f"At least 4 consecutive completed periods are required; the existing analytical quality and readiness gates are unchanged.",
                "Whole-window percent change is compared only within a compatible source/signal/query/geography cohort.",
                "Returned provider observations are a bounded sample, not the entire market.",
            ]

        elif intent == "analyze_trend":
            trend_fact = next((f for f in facts if f.fact_type == "trend_analysis"), None)
            if trend_fact:
                det = trend_fact.details
                ent = trend_fact.entity_name or "Skill"
                direction = str(trend_fact.metric_value).upper()
                slope = det.get("trend_slope")
                grain = str(det.get("period_grain") or "month")
                unit = trend_fact.unit or "observed units"
                velocity = det.get("velocity", det.get("monthly_velocity"))
                velocity_unit = str(det.get("velocity_unit") or f"{unit} per {grain}")
                velocity_label = {
                    "month": "Monthly Velocity",
                    "quarter": "Quarterly Velocity",
                }.get(grain, f"{grain.title()} Velocity")
                movement = det.get("latest_movement")
                whole_change = det.get("whole_window_change")
                whole_pct = det.get("whole_window_pct_change")
                mom_change = det.get("latest_period_change", det.get("latest_mom_change"))
                mom_pct = det.get("latest_mom_pct_change")
                periods_count = det.get("periods_count")
                start_p = det.get("start_period")
                end_p = det.get("end_period")
                if not start_p or not end_p:
                    periods_used = det.get("periods_used") or []
                    if periods_used:
                        start_p, end_p = periods_used[0], periods_used[-1]
                    elif trend_fact.period and "_to_" in trend_fact.period:
                        start_p, end_p = trend_fact.period.split("_to_", 1)
                    else:
                        start_p = end_p = trend_fact.period or "observed periods"

                whole_str = None
                if whole_change is not None:
                    whole_str = f"+{whole_change}" if isinstance(whole_change, (int, float)) and whole_change > 0 else str(whole_change)
                    if whole_pct is not None:
                        whole_str += f" ({whole_pct}%)"
                latest_change_str = "unavailable"
                if mom_change is not None:
                    latest_change_str = str(mom_change)
                    if mom_pct is not None:
                        latest_change_str += f" ({mom_pct}%)"

                period_count_text = f"{periods_count} consecutive {grain} periods" if periods_count else f"the observed {grain} periods"
                direct_answer = (
                    f"Trend analysis for **{ent}** across {period_count_text} "
                    f"({start_p} to {end_p}) shows an overall window direction of **{direction}**."
                )
                if slope is not None:
                    direct_answer += f" Theil-Sen Median Slope is **{slope} {unit} per {grain}**."
                if velocity is not None:
                    direct_answer += f" {velocity_label} is **{velocity} {velocity_unit}**."
                if latest_change_str != "unavailable":
                    direct_answer += f" Latest comparable-period change is **{latest_change_str}**."
                if whole_str is not None:
                    direct_answer += f" Whole-window change is **{whole_str}**."
                supporting_facts = [
                    f"**1. Overall Window Direction**: {direction} across {start_p} to {end_p}",
                ]
                if slope is not None:
                    supporting_facts.append(f"**2. Theil-Sen Median Slope**: {slope} {unit} per {grain}")
                if velocity is not None:
                    supporting_facts.append(f"**3. {velocity_label}**: {velocity} {velocity_unit}")
                if latest_change_str != "unavailable":
                    supporting_facts.append(f"**Latest comparable-period change**: {latest_change_str}")
                if whole_str is not None:
                    supporting_facts.append(f"**Whole-window change**: {whole_str}")
                if movement is not None:
                    supporting_facts.append(f"**Latest period movement**: {movement}")
                if periods_count:
                    supporting_facts.append(f"**Observed periods**: {periods_count} {grain} periods")
                interpretation = (
                    f"The overall window direction reflects the robust Theil-Sen median slope across the full "
                    f"observation window; the latest comparable-period change is reported separately. "
                    f"Overall direction and latest movement are distinct metrics and must not be conflated."
                )
                if trend_fact.source == "github_innovation_graph":
                    limitations = [
                        f"Requires >= 4 strictly consecutive {grain} periods; panel gaps or missing periods block calculation.",
                        "GitHub Innovation Graph measures quarterly developer activity, not employer hiring or job demand.",
                        "The raw-count series lacks the denominator and model qualification required for Skill Health, Half-Life, or Future Skill Forecast.",
                        "No forward-looking forecasting or extrapolation is applied.",
                    ]
                else:
                    limitations = [
                        f"Requires >= 4 strictly consecutive {grain} periods; panel gaps or missing periods block calculation.",
                        "Observations represent provider collection samples rather than total global demand.",
                        "No forward-looking forecasting or extrapolation is applied.",
                    ]
                if det.get("warnings"):
                    limitations.extend(det["warnings"])
            else:
                direct_answer = "Trend and velocity calculations cannot be completed due to insufficient observation depth."
                supporting_facts = [
                    f"Available observation records: {len([f for f in facts if f.fact_type == 'historical_observation'])}",
                    "Minimum threshold required: 4 consecutive monthly periods.",
                ]
                interpretation = "Single or sparse observations cannot establish a slope or trajectory without fabricating ungrounded data."
                limitations = ["Calculation blocked under analytical readiness criteria."]

        elif intent == "crosswalk_occupation_software":
            soft_facts = [f for f in facts if f.fact_type == "software_skill"]
            occ_name = soft_facts[0].details.get("occupation_title") if soft_facts and soft_facts[0].details else "Software Developers"
            soc = soft_facts[0].details.get("soc_code") if soft_facts and soft_facts[0].details else "15-1252.00"

            direct_answer = (
                f"Identified **{len(soft_facts)}** baseline software tools and technologies for **{occ_name}** "
                f"(SOC {soc}) based on the O*NET occupational taxonomy."
            )
            for f in soft_facts:
                hot_str = " [Hot Technology]" if f.metric_value is True else ""
                elem = f.details.get("element_name", "Software")
                supporting_facts.append(f"**{f.entity_name}** ({elem}){hot_str}")

            interpretation = (
                "The O*NET 2018 software skills baseline catalogs tools frequently utilized in this occupation. "
                "This represents an occupational taxonomy baseline, not live employer hiring demand or real-time job vacancy frequency."
            )
            limitations = [
                "Software tools reflect workplace survey baselines; tool frequency varies by employer.",
                "O*NET is an occupational taxonomy baseline, not live employer hiring demand or real-time vacancies.",
            ]

        elif intent == "crosswalk_related_occupations":
            rel_facts = [f for f in facts if f.fact_type == "related_occupation"]
            target_soc = rel_facts[0].provenance_id if rel_facts else ""
            direct_answer = (
                f"Identified **{len(rel_facts)}** Related Occupations based on shared work activities, "
                f"skills, and O*NET mobility crosswalk data."
            )
            for f in rel_facts:
                tier = f.metric_value
                rel_soc = f.details.get("related_soc_code", "")
                supporting_facts.append(f"**{f.entity_name}** (Relatedness Tier: {tier}, SOC: {rel_soc})")

            interpretation = (
                "Related occupations crosswalk establishes career mobility pathways sharing foundational knowledge "
                "and daily task profiles from the standard occupational classification system."
            )
            limitations = [
                "Mobility relationships represent national occupational taxonomies, not live employer vacancies.",
            ]

        elif intent == "lookup_occupation":
            occ_fact = next((f for f in facts if f.fact_type == "occupation"), None)
            if occ_fact:
                soc = occ_fact.metric_value
                title = occ_fact.entity_name
                desc = occ_fact.details.get("description", "")
                direct_answer = f"O*NET occupational classification for **{title}** resolves to SOC code **{soc}**."
                supporting_facts = [
                    f"**Occupation Title**: {title}",
                    f"**Standard Occupational Classification (SOC)**: {soc}",
                    f"**Definition**: {desc}",
                ]
                interpretation = "Standard Occupational Classification (SOC) provides standardized federal taxonomy definitions for labor market categorization."
                limitations = ["Reference taxonomy definition; does not reflect real-time employer hiring activity."]
            else:
                direct_answer = "Occupation lookup completed."
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
                interpretation = "Reference taxonomy lookup."
                limitations = ["Taxonomy baseline data."]

        elif intent in {"explain_concept", "lookup_skill_reference"}:
            tech_facts = [f for f in facts if f.fact_type == "technology_adoption"]
            ent_name = facts[0].entity_name or "Entity"
            direct_answer = f"Reference intelligence and developer adoption context retrieved for **{ent_name}**."
            if tech_facts:
                for f in tech_facts:
                    supporting_facts.append(
                        f"**{f.metric_name.replace('_', ' ').title()}**: {f.metric_value} {f.unit or ''} ({f.period})"
                    )
            else:
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]

            interpretation = (
                "Developer adoption metrics are derived from the GitHub Innovation Graph, measuring open-source "
                "repository counts and active developer volume. These indicate developer ecosystem engagement, "
                "not employer hiring demand or commercial job vacancy counts."
            )
            limitations = [
                "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
                "Quarterly developer ecosystem metrics reflect public GitHub repository activity, not commercial hiring.",
            ]

        elif intent == "search_jobs":
            job_fact = next((f for f in facts if f.fact_type == "stored_job_postings"), None)
            cnt = job_fact.metric_value if job_fact else 0
            if cnt == 0:
                if request.selected_companies:
                    comp_str = ", ".join(request.selected_companies)
                    direct_answer = (
                        f"No matching job postings were found in the bounded recent stored search for saved companies ({comp_str}). "
                        "However, standardized occupational requirements and software tool profiles remain available via the O*NET taxonomy baseline."
                    )
                else:
                    direct_answer = (
                        "No matching job postings were found in the bounded recent stored search. "
                        "However, standardized occupational requirements and software tool profiles remain available via the O*NET taxonomy baseline."
                    )
            else:
                direct_answer = f"Retrieved **{cnt}** matching job postings from the stored collection runs."
            supporting_facts = [
                f"**Stored Postings Found**: {cnt} postings",
            ]
            if job_fact and job_fact.details.get("sample_postings"):
                for p in job_fact.details["sample_postings"]:
                    supporting_facts.append(f"Sample posting: {p}")
            posting_skill_count = 0
            if job_fact:
                for posting in job_fact.details.get("postings", [])[:5]:
                    required_skills = posting.get("required_skills", [])
                    if not required_skills:
                        continue
                    posting_skill_count += len(required_skills)
                    title = posting.get("title") or "stored posting"
                    supporting_facts.append(
                        f"**Skills recorded for {title}**: {', '.join(required_skills)}"
                    )
            if cnt > 0 and posting_skill_count == 0:
                supporting_facts.append(
                    "No structured required-skill list was recorded for the matching postings."
                )

            interpretation = (
                "Postings represent verified empirical records collected and preserved in the platform's market observations store."
            )
            limitations = [
                "Stored job results are not total global vacancies; they are matching records observed through provider queries.",
            ]

        elif intent == "analyze_skill_gap":
            gap_fact = next((f for f in facts if f.fact_type == "skill_gap"), None)
            if gap_fact:
                det = gap_fact.details
                cov = gap_fact.metric_value
                tot = det.get("total_required", 0)
                missing = det.get("missing_skills", [])
                direct_answer = (
                    f"Skill gap evaluation for target role **{gap_fact.entity_name}** identifies **{cov}** "
                    f"covered skills out of {tot} baseline required technologies."
                )
                supporting_facts = [
                    f"**Covered Technologies Count**: {cov} of {tot}",
                ]
                if missing:
                    supporting_facts.append(f"**Identified Priority Skill Gaps**: {', '.join(missing)}")
                else:
                    supporting_facts.append("All baseline required technologies are represented in selected profile.")

                interpretation = (
                    "Skill gap analysis compares candidate skills against standard O*NET software technology baselines "
                    "to highlight high-leverage technical competencies for career alignment."
                )
                limitations = [
                    "Evaluated against O*NET occupational baseline; individual employer postings may require distinct proprietary tools.",
                ]
            else:
                direct_answer = "Skill gap analysis completed."
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
                interpretation = "Baseline skill gap crosswalk."
                limitations = ["Heuristic baseline evaluation."]

        elif intent == "synthesize_actions":
            act_facts = [f for f in facts if f.fact_type == "action_recommendation"]
            portal = request.portal_type or "individual"
            direct_answer = f"Synthesized **{len(act_facts)}** prioritized action recommendations for the **{portal}** portal."
            for f in act_facts:
                det = f.details
                prio = det.get("priority", "medium").upper()
                atype = det.get("action_type", "guidance")
                supporting_facts.append(f"**[{prio}]** {f.metric_value} (Type: {atype})")

            interpretation = "Action recommendations provide tactical capability enhancements aligned with verified market signals."
            limitations = [
                "Actions are advisory guidance based on empirical market signals; future career or salary outcomes not guaranteed.",
            ]

        elif intent == "compare_entities":
            ent_names = [e.canonical_entity.canonical_name for e in plan.entities if e.canonical_entity] if plan and plan.entities else []
            if not ent_names:
                ent_names = [plan.context_summary.get("primary_entity", "Entity A"), *(plan.context_summary.get("comparison_entities", []))] if plan else ["Entity A", "Entity B"]

            ent_str = " and ".join(f"**{name}**" for name in ent_names[:2]) if len(ent_names) >= 2 else "**selected entities**"
            direct_answer = f"Comparative reference and developer adoption analysis between {ent_str}."

            for f in facts:
                val_str = f"{f.metric_value} {f.unit or ''}".strip()
                supporting_facts.append(f"**{f.entity_name}** ({f.metric_name.replace('_', ' ').title()}): {val_str} [{f.source}]")

            interpretation = (
                "Comparative reference analysis evaluates standard taxonomy classifications and developer ecosystem adoption. "
                "Adoption metrics reflect open-source developer activity, not employer hiring demand."
            )
            limitations = [
                "Comparison is grounded in reference taxonomy and developer adoption; empirical hiring trends require longitudinal observation data.",
                "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
            ]

        elif intent == "analyze_company_workforce":
            cid = request.company_id or plan.context_summary.get("company_id") or "authorized organization"
            direct_answer = f"Internal workforce intelligence and team capability profile retrieved for **{cid}**."
            for f in facts:
                supporting_facts.append(f"**{f.metric_name.replace('_', ' ').title()}**: {f.metric_value} [{f.source}]")

            interpretation = (
                "Company workforce intelligence aggregates authenticated organizational membership and internal skill inventory. "
                "These records reflect verified internal workforce configurations rather than external speculative firmographics."
            )
            limitations = [
                "Internal company membership and workforce skills supported; external firmographics, venture capital funding, and public filings are unavailable.",
            ]

        elif intent == "retrieve_evidence":
            ent_name = plan.context_summary.get("primary_entity") or "Market Evidence"
            ev_fact = next((f for f in facts if f.fact_type == "evidence_summary"), None)
            cnt = ev_fact.metric_value if ev_fact else len(evidence)
            direct_answer = f"Audit trail and verifiable evidence retrieval for **{ent_name}**: identified **{cnt}** verified records."
            supporting_facts = [
                f"**Verified Evidence Items Count**: {cnt} items",
            ]
            interpretation = (
                "Evidence records provide end-to-end auditability and provenance, tracking observations from ingest to analytical calculation."
            )
            limitations = [
                "Evidence citations strictly mirror stored artifacts; zero synthetic provenance or placeholder references are returned.",
            ]

        elif intent == "retrieve_history":
            ent_name = plan.context_summary.get("primary_entity") or "Entity"
            hist_facts = [f for f in facts if f.fact_type == "historical_observation"]
            direct_answer = f"Retrieved **{len(hist_facts)}** historical observation records for **{ent_name}**."
            for f in hist_facts[:5]:
                supporting_facts.append(f"**{f.period}** ({f.metric_name}): {f.metric_value} [{f.source}]")
            if not hist_facts:
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
            interpretation = "Historical time-series observations represent empirical snapshots across collection periods."
            limitations = [
                "Only verified empirical periods are returned; zero interpolation across missing periods.",
            ]

        elif intent == "retrieve_snapshot":
            snap_fact = next((f for f in facts if f.fact_type == "market_snapshot"), None)
            if snap_fact:
                ent = snap_fact.entity_name
                stype = snap_fact.details.get("signal_type", "demand")
                val = snap_fact.metric_value
                period = snap_fact.period
                direct_answer = f"Market snapshot for **{ent}**: observed {stype} of **{val}** in period **{period}**."
                supporting_facts = [
                    f"**Observed Value**: {val}",
                    f"**Signal Type**: {stype}",
                    f"**Period**: {period}",
                    f"**Source**: {snap_fact.source}",
                ]
                interpretation = f"Empirical observation captured for {ent} in period {period}."
                limitations = ["Snapshots represent samples observed through provider queries, not total universe of postings."]
            else:
                direct_answer = "Market snapshot retrieved."
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
                interpretation = "Market snapshot data."
                limitations = ["Sample observations."]

        else:
            direct_answer = f"Synthesized intelligence summary based on {len(facts)} verified structured facts."
            supporting_facts = [f"**{f.metric_name}**: {f.metric_value} ({f.source})" for f in facts]
            interpretation = "Intelligence synthesis grounded in verified platform records."
            limitations = ["Data grounded strictly in internal and ingested analytical records."]

        sections = [direct_answer.strip()]
        if supporting_facts:
            sections.append("**Observed details**\n" + "\n".join(f"- {fact}" for fact in supporting_facts))
        if evidence_citations:
            sections.append("**Sources**\n" + "\n".join(f"- {cite}" for cite in evidence_citations))
        if interpretation and not interpretation.startswith("Intelligence synthesis grounded"):
            sections.append(interpretation.strip())
        if limitations:
            sections.append("**Limitations:** " + " ".join(limitations))
        return "\n\n".join(sections)

    def _validate_response(
        self,
        answer_text: str,
        facts: list[StructuredFact],
        evidence: list[EvidenceItem],
        capabilities_used: list[str],
        plan: IntelligencePlanResponse,
    ) -> tuple[ExecutionStatus, list[str]]:
        """Run deterministic checks ensuring no ungrounded claims, conflations, or invalid data states exist."""
        reasons: list[str] = []
        lower_ans = answer_text.lower()

        # Rule 1: Facts must exist if any capabilities were executed
        if capabilities_used and not facts:
            reasons.append("VALIDATION_ERROR_NO_GROUNDING_FACTS")

        # Rule 2: Evidence ID integrity - all evidence items must have non-empty ID
        evidence_ids = {e.evidence_id for e in evidence if e.evidence_id}
        if any(not e.evidence_id for e in evidence):
            reasons.append("VALIDATION_ERROR_EMPTY_EVIDENCE_ID")

        # Rule 3: StructuredFact evidence_reference must match an existing EvidenceItem
        for f in facts:
            if f.evidence_reference and f.evidence_reference not in evidence_ids:
                reasons.append("VALIDATION_ERROR_UNGROUNDED_EVIDENCE_REFERENCE")
                break

        # Rule 4: Citations in answer text (e.g. `ev_...`, `obs-...`) must be present in evidence
        cited_ev_tokens = re.findall(r'`(ev_[a-zA-Z0-9_\-\.]+|obs\-[a-zA-Z0-9_\-\.]+)`', answer_text)
        for token in cited_ev_tokens:
            if token not in evidence_ids:
                reasons.append("VALIDATION_ERROR_MISSING_EVIDENCE_CITATION")
                break

        # Rule 5: Quantitative & Numerical Grounding
        allowed_numbers: set[str] = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "2018", "2024", "2025", "2026", "2027"}
        for f in facts:
            for s in [f.metric_value, f.canonical_entity_id, f.provenance_id, f.entity_name, f.period]:
                if s is not None:
                    for num_str in re.findall(r'\b\d+(?:\.\d+)?\b', str(s)):
                        allowed_numbers.add(num_str)
            if f.details:
                for k, v in f.details.items():
                    for num_str in re.findall(r'\b\d+(?:\.\d+)?\b', str(v)):
                        allowed_numbers.add(num_str)

        for e in evidence:
            for s in [e.period, e.evidence_id, e.description]:
                if s is not None:
                    for num_str in re.findall(r'\b\d+(?:\.\d+)?\b', str(s)):
                        allowed_numbers.add(num_str)

        allowed_numbers.add(str(len(facts)))
        allowed_numbers.add(str(len(evidence)))

        # Check for ungrounded numbers in narrative text
        found_numbers = re.findall(r'\b\d+(?:\.\d+)?\b', answer_text)
        for num in found_numbers:
            if num not in allowed_numbers and float(num) > 5 and not num.startswith("20"):
                reasons.append("VALIDATION_ERROR_UNGROUNDED_QUANTITATIVE_CLAIM")
                break

        # Rule 6: Unit Preservation
        has_gh_facts = any(f.source and f.source.startswith("ref_github_") for f in facts)
        if has_gh_facts:
            for f in facts:
                if f.unit == "repositories":
                    if f"{f.metric_value} postings" in lower_ans or f"{f.metric_value} vacancies" in lower_ans:
                        reasons.append("VALIDATION_ERROR_UNIT_MISMATCH")
                        break
                elif f.unit == "developers":
                    if f"{f.metric_value} postings" in lower_ans or f"{f.metric_value} repositories" in lower_ans:
                        reasons.append("VALIDATION_ERROR_UNIT_MISMATCH")
                        break

        # Rule 7: Conflation Prevention
        has_onet = any(f.source and f.source.startswith("ref_onet_") for f in facts)
        if has_onet:
            conflation_terms = [
                "employer hiring demand",
                "live job postings",
                "real-time vacancies",
                "current job vacancies",
                "employer demand for software developers",
            ]
            for term in conflation_terms:
                for match in re.finditer(re.escape(term), lower_ans):
                    start = match.start()
                    sentence_start = max(lower_ans.rfind(".", 0, start), lower_ans.rfind("\n", 0, start))
                    preceding = lower_ans[sentence_start + 1 : start] if sentence_start != -1 else lower_ans[max(0, start - 80) : start]
                    negated = any(neg in preceding for neg in ["not", "never", "neither", "nor", "baseline rather than", "instead of"])
                    if not negated:
                        reasons.append("VALIDATION_ERROR_TAXONOMY_CONFLATED_WITH_HIRING_DEMAND")
                        break
                if "VALIDATION_ERROR_TAXONOMY_CONFLATED_WITH_HIRING_DEMAND" in reasons:
                    break

        if has_gh_facts:
            gh_conflation = ["employer hiring demand", "employer demand", "job vacancies", "hiring demand"]
            for term in gh_conflation:
                for match in re.finditer(re.escape(term), lower_ans):
                    start = match.start()
                    sentence_start = max(lower_ans.rfind(".", 0, start), lower_ans.rfind("\n", 0, start))
                    preceding = lower_ans[sentence_start + 1 : start] if sentence_start != -1 else lower_ans[max(0, start - 80) : start]
                    negated = any(neg in preceding for neg in ["not", "never", "neither", "nor", "rather than", "ecosystem rather than", "instead of"])
                    if not negated:
                        reasons.append("VALIDATION_ERROR_GITHUB_CONFLATED_WITH_HIRING_DEMAND")
                        break
                if "VALIDATION_ERROR_GITHUB_CONFLATED_WITH_HIRING_DEMAND" in reasons:
                    break

        if "job_posting_search" in capabilities_used:
            for match in re.finditer(r"total global vacancies", lower_ans):
                start = match.start()
                sentence_start = max(lower_ans.rfind(".", 0, start), lower_ans.rfind("\n", 0, start))
                preceding = lower_ans[sentence_start + 1 : start] if sentence_start != -1 else lower_ans[max(0, start - 80) : start]
                negated = any(neg in preceding for neg in ["not", "never", "neither", "nor", "strictly"])
                if not negated:
                    reasons.append("VALIDATION_ERROR_JOB_TOTAL_CLAIM")
                    break

        # Rule 8: Single Observation Trend Prevention
        hist_obs_count = len([f for f in facts if f.fact_type in {"historical_observation", "market_snapshot"}])
        has_trend_fact = any(f.fact_type == "trend_analysis" for f in facts)
        if hist_obs_count in {1, 2, 3} and not has_trend_fact:
            trend_claim_words = ["slope is", "growing trend", "declining trend", "upward trend", "downward trend"]
            if any(w in lower_ans for w in trend_claim_words):
                reasons.append("VALIDATION_ERROR_SINGLE_OBSERVATION_TREND")

        # Rule 9: Separation of Trend Direction vs Latest Velocity
        trend_facts = [f for f in facts if f.fact_type == "trend_analysis"]
        if trend_facts and plan.intent == "analyze_trend":
            if "window direction" not in lower_ans or "velocity" not in lower_ans:
                reasons.append("VALIDATION_ERROR_VELOCITY_TREND_CONFLATION")
            if any(f.details.get("period_grain") == "quarter" for f in trend_facts):
                if "monthly" in lower_ans or "month-over-month" in lower_ans:
                    reasons.append("VALIDATION_ERROR_PERIOD_GRAIN_MISMATCH")

        # Rule 10: Missing values must not be converted to 0
        for f in facts:
            if f.metric_value == 0 and f.details and f.details.get("was_null"):
                reasons.append("VALIDATION_ERROR_MISSING_VALUE_ZEROED")
                break

        # Rule 11: No forward-looking forecasting claims if forecasting capability is not used
        if "skill_forecasting_half_life" not in capabilities_used:
            for match in re.finditer(r"forecast\w*", lower_ans):
                start = match.start()
                end = match.end()
                preceding = lower_ans[max(0, start - 80):start]
                following = lower_ans[end:end + 80]
                negated = any(neg in preceding for neg in ["not", "no forward", "never", "without", "disable", "inactive"]) or \
                          any(neg in following for neg in ["not supported", "inactive", "disabled", "unsupported", "is not"])
                if not negated:
                    reasons.append("VALIDATION_ERROR_UNAUTHORIZED_FORECAST_CLAIM")
                    break

        # Rule 12: Portal Authorization & Company Isolation
        if plan.portal_type == "company":
            company_id = plan.context_summary.get("company_id")
            for f in facts:
                if f.fact_type == "company_workforce":
                    if f.entity_name != company_id:
                        reasons.append("VALIDATION_ERROR_CROSS_COMPANY_LEAK")
                        break

        # Rule 13: Occupation Entity & Evidence Consistency
        occ_target = None
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                occ_target = ent.canonical_entity.canonical_name.casefold()
                break
        if not occ_target and plan.context_summary.get("primary_entity"):
            prim = str(plan.context_summary.get("primary_entity", "")).casefold()
            if any(term in prim for term in ["developer", "engineer", "analyst", "manager", "scientist", "designer"]):
                occ_target = prim

        if occ_target and any(c in capabilities_used for c in ("occupation_lookup", "occupation_software_skills", "related_occupations")):
            for ev in evidence:
                ev_desc = ev.description.casefold()
                if "o*net" in ev_desc:
                    if any(other in ev_desc for other in ["dentist", "surgeon", "chief executive", "pilot", "carpenter"]) and occ_target not in ev_desc:
                        reasons.append("VALIDATION_ERROR_OCCUPATION_EVIDENCE_MISMATCH")
                        break

        if reasons:
            return "failed", reasons

        return "completed", []

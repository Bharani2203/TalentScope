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
import ipaddress
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlsplit

from fastapi import HTTPException

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
from app.analytics.job_skill_extraction import extract_posting_skills
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
from app.models.assistant import AssistantSource
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
from app.services.assistant_feature_registry import HANDLER_METHODS, INTENT_FEATURES
from app.services.llm_explanation_service import GEMINI_DEGRADED_MESSAGE, LLMExplanationService
from app.services.intelligence_contract_service import (
    capability_metric_results,
    fact_metric_results,
)
from app.storage.conversation_store import ConversationStore
from app.storage.company_workforce_store import (
    CompanyWorkforceStoreUnavailable,
    FirestoreCompanyWorkforceStore,
)
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


def _valid_application_url(value: str | None) -> bool:
    """Accept only absolute HTTP(S) URLs with a syntactically valid host."""
    if not value or any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme.casefold() not in {"http", "https"} or not host:
            return False
        if parsed.username or parsed.password:
            return False
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return False
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            if host.casefold() == "localhost":
                return True
            host = host.rstrip(".")
            if len(host) > 253 or "." not in host:
                return False
            return all(
                label and len(label) <= 63
                and re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", label)
                for label in host.rstrip(".").split(".")
            )
    except ValueError:
        return False


def _feature_intent(feature_id: str, preferred_intent: str) -> str:
    if feature_id in INTENT_FEATURES.get(preferred_intent, frozenset()):
        return preferred_intent
    return next(
        (intent for intent, features in INTENT_FEATURES.items() if feature_id in features),
        preferred_intent,
    )


def _offline_general_explanation(message: str) -> str | None:
    """Small, explicitly non-market fallback for common technology concepts."""
    normalized = message.casefold()
    if re.search(r"\bjava\b", normalized) and re.search(r"\bpython\b", normalized) and re.search(r"\bdifference between\b", normalized):
        return (
            "Java and Python are both general-purpose programming languages. Java is commonly "
            "used for large applications and Android development; Python is often chosen for "
            "automation, data work, and concise scripting. The best fit depends on the project. "
            "This is general guidance, not a TalentScope market finding."
        )
    if re.search(r"\bpython\b", normalized):
        return (
            "Python is a general-purpose programming language used to build web services, "
            "automate tasks, analyze data, and develop machine-learning applications. "
            "This is a general explanation, not a TalentScope market finding."
        )
    if re.search(r"\bjava\b", normalized):
        return (
            "Java is a general-purpose programming language commonly used for backend services, "
            "enterprise applications, and Android development. This is a general explanation, "
            "not a TalentScope market finding."
        )
    if re.search(r"\bui\s*/\s*ux\b|\buser (?:interface|experience)\b", normalized):
        return (
            "UI/UX design is the work of shaping how a digital product looks and how people use it. "
            "A trend means a pattern designers are adopting; this explanation does not verify which "
            "approaches are currently most common."
        )
    return None

_IDEMPOTENT_ANSWER_CACHE: dict[tuple[str, str, str, str], CoreIntelligenceAnswerResponse] = {}


def _answer_idempotency_key(
    user_id: str, conversation_id: str, client_message_id: str, message: str
) -> tuple[str, str, str, str]:
    normalized_question = " ".join(message.casefold().split())
    return user_id, conversation_id, client_message_id, normalized_question


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
        workforce_store: Any | None = None,
        reference_store: Any | None = None,
        market_store: Any | None = None,
        conversation_store: Any | None = None,
        llm_service: Any | None = None,
        job_searcher: Callable[..., Sequence[Any]] | None = None,
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
        self.reference_store = reference_store or ReferenceDataStore(self.db_path)
        self.capability_service = capability_service or CapabilityRegistryService(
            entity_service=self.entity_service,
            reference_store=self.reference_store,
            db_path=self.db_path,
        )
        self.market_store = market_store or MarketDataStore(self.db_path)
        self.workforce_store = workforce_store or FirestoreCompanyWorkforceStore()
        self.conversation_store = conversation_store or ConversationStore.get_instance()
        self.llm_service = llm_service or LLMExplanationService()
        self.intent_planner = intent_planner or IntentPlannerService(
            entity_service=self.entity_service,
            capability_service=self.capability_service,
            llm_service=self.llm_service,
        )
        self.job_searcher = job_searcher
        # Production intelligence reads follow the configured source of truth.
        # Unit tests must inject an explicit observation store.
        self.firestore_store = observation_store
        if self.firestore_store is None and getattr(self.settings, "skill_intelligence_read_backend", "firestore") == "firestore":
            from app.storage.firestore_observation_store import FirestoreObservationStore
            self.firestore_store = FirestoreObservationStore()
        # Denominator scans are shared across every skill query in this answer
        # service instance (FastAPI creates the dependency per request).
        self._posting_sample_stats_loaded = False
        self._posting_sample_stats: dict[tuple[str, str, str, str], dict[str, int]] = {}

        # The registry is shared with planning and the public capability catalog.
        self._handler_registry: dict[str, Callable[..., tuple[list[StructuredFact], list[EvidenceItem], list[str]]]] = {
            capability_id: getattr(self, method_name)
            for capability_id, method_name in HANDLER_METHODS.items()
        }

    def _get_posting_sample_stats(self) -> dict[tuple[str, str, str, str], dict[str, int]]:
        """Read job denominators at most once for this request-scoped service."""
        if self._posting_sample_stats_loaded:
            return self._posting_sample_stats
        self._posting_sample_stats_loaded = True
        try:
            from app.services.job_storage_service import get_recent_posting_sample_stats
            self._posting_sample_stats = get_recent_posting_sample_stats(
                firestore_client=self.firestore_store.client,
            )
        except Exception as exc:
            logger.warning("Job posting denominator lookup unavailable error_class=%s", type(exc).__name__)
            self._posting_sample_stats = {}
        return self._posting_sample_stats

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
        cutoff_90d = datetime.now(timezone.utc) - timedelta(days=90)
        excluded_old_ids: set[str] = set()
        unknown_posting_ids: set[str] = set()
        duplicate_count = 0
        deduplicated: list[MarketObservation] = []
        seen_posting_skills: set[tuple[str, str, str]] = set()
        denominator_keys: set[tuple[str, str, str, str]] = set()
        for observation in filtered:
            is_job_demand = observation.signal_type == "demand" and observation.source.casefold() in {
                "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
            }
            if is_job_demand and observation.posting_id and observation.period:
                denominator_keys.add((
                    observation.source.casefold(), observation.period,
                    observation.scope, (observation.location or "").casefold().strip(),
                ))
            if is_job_demand:
                posted_at = observation.provider_posted_at
                if posted_at is None:
                    unknown_posting_ids.add(str(observation.posting_id or observation.id or "unknown"))
                    continue
                if (posted_at.replace(tzinfo=timezone.utc) if posted_at.tzinfo is None else posted_at.astimezone(timezone.utc)) < cutoff_90d:
                    excluded_old_ids.add(str(observation.posting_id or observation.id or "unknown"))
                    continue
            if observation.posting_id and observation.period:
                identity = (
                    str(observation.posting_id).casefold(),
                    observation.skill.casefold().strip(),
                    observation.period,
                )
                if identity in seen_posting_skills:
                    duplicate_count += 1
                    continue
                seen_posting_skills.add(identity)
            deduplicated.append(observation)

        excluded_old = len(excluded_old_ids)
        unknown_date = len(unknown_posting_ids)
        if deduplicated and self.firestore_store is not None and request_obs is None:
            from app.storage.firestore_observation_store import FirestoreObservationStore
            if isinstance(self.firestore_store, FirestoreObservationStore):
                stats = self._get_posting_sample_stats()
                if stats:
                    for index, observation in enumerate(deduplicated):
                        if observation.signal_type != "demand" or observation.source.casefold() not in {
                            "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
                        }:
                            continue
                        key = (
                            observation.source.casefold(),
                            observation.period or "",
                            observation.scope,
                            (observation.location or "").casefold().strip(),
                        )
                        sample = stats.get(key)
                        if sample and sample["recent"] > 0:
                            deduplicated[index] = observation.model_copy(update={
                                "denominator": float(sample["recent"]),
                                "denominator_unit": "job_postings",
                            })
                    if denominator_keys:
                        excluded_old = sum(stats.get(key, {}).get("older_than_90_days", 0) for key in denominator_keys)
                        unknown_date = sum(stats.get(key, {}).get("date_unknown", 0) for key in denominator_keys)

        from app.storage.firestore_observation_store import ObservationBatch
        return ObservationBatch(
            deduplicated,
            truncated=bool(getattr(observations, "truncated", False)),
            duplicate_count=duplicate_count,
            excluded_old_postings=excluded_old,
            unknown_posted_at=unknown_date,
        )

    @staticmethod
    def _extract_question_country(message: str) -> str | None:
        known_countries = (
            "United States|United Kingdom|South Korea|North Korea|South Africa|New Zealand|Saudi Arabia|"
            "United Arab Emirates|India|Canada|Australia|Germany|France|Brazil|Japan|China|Singapore|"
            "Ireland|Netherlands|Sweden|Norway|Denmark|Finland|Spain|Italy|Mexico|Argentina|Nigeria|Kenya|"
            "Indonesia|Pakistan|Bangladesh|Philippines|Vietnam|Thailand|Malaysia|Israel|Switzerland|Poland"
        )
        country_match = re.search(
            rf"\b(?:in|within)\s+({known_countries})\b",
            message,
            re.IGNORECASE,
        )
        if country_match:
            return country_match.group(1)

    @staticmethod
    def _company_query_from_message(message: str) -> str | None:
        match = re.search(
            r"\b(?:tell me about|information about|details for|profile for|address for)\s+(?:the\s+)?(.+?)\s*(?:company|employer)?[?.!]*$",
            message,
            re.IGNORECASE,
        )
        if not match:
            return None
        value = re.sub(r"\s+(?:company|employer)$", "", match.group(1), flags=re.IGNORECASE).strip(" .?!")
        return value[:160] or None

    @staticmethod
    def _extract_trend_question_location(message: str) -> str | None:
        country = ExecutionOrchestratorService._extract_question_country(message)
        if country:
            return country
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
            from app.storage.firestore_observation_store import ObservationBatch
            observations = ObservationBatch(
                market_observations,
                truncated=bool(getattr(observations, "truncated", False)),
                duplicate_count=int(getattr(observations, "duplicate_count", 0)),
                excluded_old_postings=int(getattr(observations, "excluded_old_postings", 0)),
                unknown_posted_at=int(getattr(observations, "unknown_posted_at", 0)),
            )
        demand_sample_sizes: dict[tuple[str, str], int] = {}
        for observation in observations:
            if observation.signal_type == "demand" and observation.denominator:
                key = (observation.period or "unknown", observation.source.casefold())
                demand_sample_sizes[key] = max(demand_sample_sizes.get(key, 0), int(observation.denominator))
        plan.context_summary["_demand_sample_sizes"] = [
            {"period": period, "source": source_name, "n": sample_size}
            for (period, source_name), sample_size in sorted(demand_sample_sizes.items())
        ]
        plan.context_summary["_demand_exclusions"] = {
            "older_than_90_days": int(getattr(observations, "excluded_old_postings", 0)),
            "date_unknown": int(getattr(observations, "unknown_posted_at", 0)),
            "duplicate_observations": int(getattr(observations, "duplicate_count", 0)),
        }
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
            "2y": 800, "24m": 800,
            "3y": 1200, "36m": 1200,
        }
        return datetime.now(timezone.utc) - timedelta(days=windows.get(key, 30))

    def _apply_authenticated_learning_profile(
        self,
        request: CoreIntelligenceAnswerRequest,
        authenticated_user: AuthenticatedUser | None,
        *,
        portal_type: str,
    ) -> CoreIntelligenceAnswerRequest:
        """Bind recommendation context only to the authenticated individual's own profile."""
        context = dict(request.context_override)
        context.pop("_authenticated_learning_profile", None)
        context.pop("_learning_profile_state", None)
        context.pop("_learning_skill_source", None)
        if (
            portal_type != "individual"
            or authenticated_user is None
            or not authenticated_user.uid
        ):
            return request.model_copy(update={"context_override": context})

        from app.services.onboarding_service import get_individual_profile

        try:
            profile_response = get_individual_profile(authenticated_user.uid)
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            context["_learning_profile_state"] = "unavailable"
            return request.model_copy(update={"context_override": context})

        profile = profile_response.profile if isinstance(profile_response.profile, dict) else {}
        skills = profile.get("skills") if isinstance(profile.get("skills"), dict) else {}
        career = profile.get("career") if isinstance(profile.get("career"), dict) else {}
        preferences = profile.get("work_preferences") if isinstance(profile.get("work_preferences"), dict) else {}
        saved_skills = [
            str(skill).strip()
            for skill in skills.get("selected_skills", [])
            if isinstance(skill, str) and skill.strip()
        ]
        target_roles = [
            str(role).strip()
            for role in career.get("target_roles", [])
            if isinstance(role, str) and role.strip()
        ]

        target_role = request.target_role
        selected_roles = list(request.selected_roles)
        if not target_role and len(selected_roles) == 1:
            target_role = selected_roles[0]
        if not target_role and len(target_roles) == 1:
            target_role = target_roles[0]
        if not selected_roles and target_roles:
            selected_roles = target_roles[:20]

        context["_learning_profile_state"] = "available"
        context["_learning_skill_source"] = (
            "request_supplied_skills" if request.selected_skills else "authenticated_individual_profile"
        )
        context["_authenticated_learning_profile"] = {
            "uid": authenticated_user.uid,
            "target_roles": target_roles,
            "skill_levels": (
                skills.get("skill_levels", {})
                if isinstance(skills.get("skill_levels"), dict)
                else {}
            ),
            "weekly_learning_time": preferences.get("learning_time"),
            "learning_preferences": [
                str(value).strip()
                for value in profile.get("learning_preferences", [])
                if isinstance(value, str) and value.strip()
            ],
        }
        return request.model_copy(update={
            "target_role": target_role,
            "selected_roles": selected_roles,
            "selected_skills": request.selected_skills or saved_skills,
            "context_override": context,
        })

    # =========================================================================
    # MAIN ORCHESTRATION PIPELINE
    # =========================================================================

    def answer(
        self,
        request: CoreIntelligenceAnswerRequest,
        authenticated_user: AuthenticatedUser | None = None,
    ) -> CoreIntelligenceAnswerResponse:
        """Execute the end-to-end intelligence query flow and return a validated response."""
        if request.domain == "auto":
            request = request.model_copy(update={"domain": None})
        request_id = f"ans_{uuid.uuid4().hex[:12]}"
        portal_type = request.portal_type or "individual"

        # 0. Conversation Isolation Access Guard & Idempotency Check
        user_id = authenticated_user.uid if authenticated_user else "anonymous"
        user_company_id = getattr(authenticated_user, "company_id", None) if authenticated_user else request.company_id
        if not request.conversation_id:
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
                is_missing = deny_reason == "conversation_not_found"
                if is_missing:
                    reason_code = "missing_document"
                elif deny_reason == "conversation_lookup_error" or "could not be verified" in str(deny_reason).lower():
                    reason_code = "lookup_error"
                elif deny_reason == "conversation_company_mismatch" or "different company" in str(deny_reason).lower():
                    reason_code = "company_mismatch"
                else:
                    reason_code = "owner_mismatch"
                logger.warning("conversation_access_denied reason_code=%s", reason_code)
                raise HTTPException(
                    status_code=404 if is_missing else 403,
                    detail="Conversation not found." if is_missing else "Access denied to conversation.",
                )

        # Read clarification state from the already loaded conversation object.
        # It is persisted with the ordinary save_turn write below.
        conversation_state = None
        if request.conversation_id:
            conversation_state = self.conversation_store.get_conversation(
                request.conversation_id,
                user_id=user_id,
                company_id=user_company_id,
            )
        stored_session_state = dict(conversation_state.session_state or {}) if conversation_state else {}
        active_clarification = stored_session_state.get("job_clarification")
        from app.services.question_classification_service import (
            classify_question, clarification_question, extract_location, extract_role,
            extract_technology, extract_experience_level, merge_follow_up, missing_job_slot, quick_reply_options,
            merged_search_query, next_clarification_round,
        )
        question_class = classify_question(request.message, active_clarification)
        aggregate_for_slots: dict[str, Any] | None = None

        def get_slot_aggregate() -> dict[str, Any]:
            nonlocal aggregate_for_slots
            if aggregate_for_slots is None:
                from app.services.collected_posting_skills_service import get_collected_posting_skills
                aggregate_for_slots = get_collected_posting_skills(
                    firestore_client=self.firestore_store.client if self.firestore_store is not None else None,
                )
            return aggregate_for_slots

        def persist_session_state(value: dict[str, Any]) -> None:
            request._session_state_update = value

        if question_class == "OFF-TOPIC":
            persist_session_state({})
            response = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain="skill",
                intent="off_topic",
                plan_status="ready_to_execute",
                execution_status="completed",
                status="ready",
                answer="I can help with skills, job postings, and market signals. What would you like to explore?",
                answer_block={
                    "verdict": "I can help with skills, job postings, and market signals.",
                    "summary": "What would you like to explore?",
                },
                limitations=[],
                reason_codes=["OFF_TOPIC_SCOPE_BOUNDARY"],
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            self._record_conversation_turn(request, None, response, authenticated_user, portal_type)
            return response

        if question_class == "TOO BROAD":
            base_slots = {
                "role": extract_role(request.message),
                "location": extract_location(request.message),
                "technology": extract_technology(request.message, []),
                "experience_level": extract_experience_level(request.message),
            }
            missing = missing_job_slot(base_slots) or "location"
            next_state = {
                "active": True,
                "original_query": request.message,
                "slots": base_slots,
                "pending_slot": missing,
                "round_count": 1,
            }
            aggregate = get_slot_aggregate()
            question = clarification_question(missing, base_slots.get("role"))
            options = quick_reply_options(missing, aggregate)
            persist_session_state({**stored_session_state, "job_clarification": next_state})
            response = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain="job",
                intent="search_jobs",
                plan_status="requires_clarification",
                execution_status="requires_clarification",
                status="insufficient_data",
                answer=question,
                answer_block={
                    "verdict": question,
                    "summary": "Choose a stored option or use an escape option.",
                    "clarification": {
                        "classification": "TOO BROAD",
                        "slot": missing,
                        "round_count": 1,
                        "options": options,
                    },
                },
                limitations=["Quick-reply values are drawn from collected stored postings."],
                reason_codes=["JOB_SEARCH_NEEDS_ONE_CONSTRAINT"],
                follow_up_questions=[question],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            self._record_conversation_turn(request, None, response, authenticated_user, portal_type)
            return response

        if question_class == "FOLLOW-UP" and active_clarification:
            aggregate = get_slot_aggregate()
            slots, escape_requested = merge_follow_up(
                active_clarification,
                request.message,
                known_skills=[str(row.get("skill")) for row in aggregate.get("skill_counts", [])],
            )
            answer_all = request.message.strip().casefold() in {"show everything", "show all", "everything", "all"}
            if answer_all:
                slots["location"] = None
                slots["technology"] = None
            missing = missing_job_slot(slots)
            round_count = int(active_clarification.get("round_count") or 1)
            next_round = next_clarification_round(round_count, missing, escape_requested)
            if next_round is not None:
                next_state = {
                    **active_clarification,
                    "active": True,
                    "slots": slots,
                    "pending_slot": missing,
                    "round_count": next_round,
                }
                question = clarification_question(missing, slots.get("role"))
                persist_session_state({**stored_session_state, "job_clarification": next_state})
                response = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain="job",
                    intent="search_jobs",
                    plan_status="requires_clarification",
                    execution_status="requires_clarification",
                    status="insufficient_data",
                    answer=question,
                    answer_block={
                        "verdict": question,
                        "summary": "One more detail will help narrow the stored postings.",
                        "clarification": {
                            "classification": "TOO BROAD",
                            "slot": missing,
                            "round_count": next_round,
                            "options": quick_reply_options(missing, aggregate),
                        },
                    },
                    limitations=["Quick-reply values are drawn from collected stored postings."],
                    reason_codes=["JOB_SEARCH_NEEDS_ONE_CONSTRAINT"],
                    follow_up_questions=[question],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
                self._record_conversation_turn(request, None, response, authenticated_user, portal_type)
                return response

            # Slot answer, Skip, Show everything, or turn three: execute a best-effort search.
            request = request.model_copy(update={
                "target_role": slots.get("role"),
                "selected_roles": [slots["role"]] if slots.get("role") else [],
                "location": slots.get("location"),
                "technology": slots.get("technology"),
                "selected_skills": [slots["technology"]] if slots.get("technology") else [],
            })
            request._session_state_update = {
                **stored_session_state,
                "job_clarification": {"active": False, "slots": slots, "round_count": round_count},
            }
            request._merged_job_search_query = merged_search_query(slots)
        elif active_clarification:
            persist_session_state({**stored_session_state, "job_clarification": {"active": False}})

            if request.client_message_id and not request.regenerate:
                cache_key = _answer_idempotency_key(
                    user_id, request.conversation_id, request.client_message_id, request.message
                )
                if cache_key in _IDEMPOTENT_ANSWER_CACHE:
                    return _IDEMPOTENT_ANSWER_CACHE[cache_key]

        # 1. Intent Resolver + Context Planner
        plan_req = IntelligencePlanRequest(
            message=request._merged_job_search_query or request.message,
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
        if plan.intent in {"synthesize_actions", "analyze_skill_gap"}:
            request = self._apply_authenticated_learning_profile(
                request,
                authenticated_user,
                portal_type=plan.portal_type,
            )
            plan_req = plan_req.model_copy(update={
                "target_role": request.target_role,
                "selected_skills": request.selected_skills,
                "selected_roles": request.selected_roles,
                "context_override": request.context_override,
            })
            plan = self.intent_planner.create_plan(
                plan_req, authenticated_user=authenticated_user
            )

        if plan.intent == "platform_help":
            response = self._platform_help_response(request, plan, portal_type)
            self._record_conversation_turn(request, plan, response, authenticated_user, portal_type)
            return response

        job_follow_up_kind = self._job_follow_up_kind(request.message)
        job_follow_up_intents = {
            "search_jobs",
            "aggregate_posting_skills",
            "company_postings_summary",
        }
        has_prior_turns = bool(conversation_state and conversation_state.turns)
        should_handle_saved_job_follow_up = bool(
            job_follow_up_kind
            and request.conversation_id
            and (
                plan.intent in job_follow_up_intents
                or (plan.intent == "unsupported_or_unclear" and has_prior_turns)
            )
        )
        if should_handle_saved_job_follow_up:
            follow_up_response = self._answer_saved_job_follow_up(
                request, plan, authenticated_user, portal_type, job_follow_up_kind,
            )
            self._record_conversation_turn(request, plan, follow_up_response, authenticated_user, portal_type)
            return follow_up_response

        if plan.intent == "retrieve_evidence" and request.conversation_id:
            conv_state = self.conversation_store.get_conversation(
                request.conversation_id,
                user_id=user_id,
                company_id=user_company_id,
            )
            last_turn = conv_state.turns[-1] if conv_state and conv_state.turns else None
            prior_payload = last_turn.response_payload if last_turn else None
            if (
                last_turn
                and last_turn.intent == "analyze_ai_task_exposure"
                and last_turn.execution_status == "blocked"
                and prior_payload
                and prior_payload.get("status") == "unavailable"
            ):
                response = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    intent=plan.intent,
                    plan_status="blocked",
                    execution_status="blocked",
                    status="unavailable",
                    answer=(
                        "There is no validated task-exposure assessment to cite. "
                        "The previous request was blocked because no approved dataset, methodology, "
                        "and task mappings are configured."
                    ),
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=[
                        "No task-exposure evidence was retrieved or retained for the previous request.",
                        "Task exposure must not be interpreted as automation potential, job displacement, or workforce impact.",
                    ],
                    reason_codes=["NO_LICENSED_EXPOSURE_DATASET"],
                    follow_up_questions=[],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
                self._record_conversation_turn(
                    request, plan, response, authenticated_user, portal_type
                )
                return response

        if self._looks_like_combined_question(request.message) and len(plan.selected_capabilities) != 2:
            clarification = CoreIntelligenceAnswerResponse(
                request_id=request_id, user_message=request.message, portal_type=portal_type,
                intent="unsupported_or_unclear", plan_status="requires_clarification",
                execution_status="clarification_required", status="insufficient_data",
                answer="I can answer this in two evidence-backed parts, but I could not safely identify both requests. Which two should I handle?",
                limitations=["No handler was run because the combined request could not be split safely."],
                reason_codes=["COMBINED_QUESTION_NEEDS_CLARIFICATION"],
                follow_up_questions=["Please name the two parts you want answered."],
                conversation_id=request.conversation_id, client_message_id=request.client_message_id,
            )
            self._record_conversation_turn(request, plan, clarification, authenticated_user, portal_type)
            return clarification
            if (
                last_turn
                and last_turn.intent == "analyze_company_workforce"
                and last_turn.execution_status in {"completed", "insufficient_data"}
                and prior_payload
                and request.portal_type == "company"
                and authenticated_user is not None
                and getattr(authenticated_user, "role", None) == "company_admin"
                and conv_state is not None
                and conv_state.portal_type == "company"
                and user_company_id == conv_state.company_id
                and re.search(
                    r"\b(?:what\s+evidence|what\s+records?|which\s+sources?|how\s+was\s+this\s+calculated|why\s+this\s+coverage)\b",
                    request.message,
                    re.IGNORECASE,
                )
            ):
                try:
                    prior_response = CoreIntelligenceAnswerResponse.model_validate(
                        prior_payload
                    )
                except Exception as exc:
                    logger.warning(
                        "Stored company workforce response could not be validated (%s)",
                        type(exc).__name__,
                    )
                else:
                    evidence_lookup = {
                        item.evidence_id: item for item in prior_response.evidence
                    }
                    cited_facts = [
                        fact for fact in prior_response.facts
                        if fact.fact_type in {
                            "company_workforce_summary",
                            "company_skill_coverage",
                            "company_declared_priority_skill",
                        }
                        and fact.evidence_reference in evidence_lookup
                        and all(
                            reference in evidence_lookup
                            for reference in fact.details.get(
                                "supporting_evidence_references", []
                            )
                        )
                    ]
                    cited_ids = {
                        reference
                        for fact in cited_facts
                        for reference in [
                            fact.evidence_reference,
                            *fact.details.get("supporting_evidence_references", []),
                        ]
                    }
                    prior_evidence = [
                        item for item in prior_response.evidence
                        if item.evidence_id in cited_ids
                    ]
                    if cited_facts and prior_evidence:
                        evidence_sources = "; ".join(
                            item.description for item in prior_evidence
                        )
                        response = CoreIntelligenceAnswerResponse(
                            request_id=request_id,
                            user_message=request.message,
                            portal_type=portal_type,
                            intent=plan.intent,
                            plan_status="ready_to_execute",
                            execution_status="completed",
                            status=prior_response.status,
                            answer=(
                                "The previous workforce summary used these stored records: "
                                f"{evidence_sources} These records establish membership and "
                                "self-reported skill coverage only; they do not validate proficiency "
                                "or organizational competence."
                            ),
                            facts=cited_facts,
                            evidence=prior_evidence,
                            capabilities_used=["company_intelligence"],
                            limitations=list(dict.fromkeys([
                                *prior_response.limitations,
                                "This follow-up reuses evidence from the prior authorized company turn; it does not fetch new workforce records.",
                            ])),
                            reason_codes=["PRIOR_WORKFORCE_EVIDENCE_RETRIEVED"],
                            follow_up_questions=[],
                            conversation_id=request.conversation_id,
                            client_message_id=request.client_message_id,
                        )
                        validation_status, validation_reasons = self._validate_response(
                            answer_text=response.answer,
                            facts=response.facts,
                            evidence=response.evidence,
                            capabilities_used=response.capabilities_used,
                            plan=plan,
                        )
                        if validation_status == "completed":
                            self._record_conversation_turn(
                                request, plan, response, authenticated_user, portal_type
                            )
                            return response
                        logger.warning(
                            "Prior company workforce evidence failed response validation: %s",
                            validation_reasons,
                        )
            if (
                last_turn
                and last_turn.intent in {"synthesize_actions", "analyze_skill_gap"}
                and last_turn.execution_status == "completed"
                and prior_payload
                and re.search(
                    r"\b(?:why\s+(?:are|did)\s+you\s+recommend(?:ing)?|what\s+evidence|what\s+sources?|methodology|why\s+this\s+skill)\b",
                    request.message,
                    re.IGNORECASE,
                )
            ):
                try:
                    prior_response = CoreIntelligenceAnswerResponse.model_validate(
                        prior_payload
                    )
                except Exception as exc:
                    logger.warning(
                        "Stored recommendation response could not be validated (%s)",
                        type(exc).__name__,
                    )
                else:
                    cited_ids = {
                        fact.evidence_reference
                        for fact in prior_response.facts
                        if fact.evidence_reference
                    }
                    prior_evidence = [
                        item for item in prior_response.evidence
                        if item.evidence_id in cited_ids
                    ]
                    evidence_lookup = {
                        item.evidence_id: item for item in prior_evidence
                    }
                    cited_facts = [
                        fact for fact in prior_response.facts
                        if fact.evidence_reference in evidence_lookup
                        and fact.fact_type in {
                            "action_recommendation",
                            "learning_market_evidence",
                            "learning_recommendation_summary",
                            "learning_recommendation_readiness",
                            "skill_gap",
                        }
                    ]
                    candidate_facts = [
                        fact for fact in cited_facts
                        if fact.fact_type == "action_recommendation"
                    ]
                    if candidate_facts and prior_evidence:
                        details = candidate_facts[0].details
                        explanation = str(details.get("reason") or "")
                        source = evidence_lookup[
                            candidate_facts[0].evidence_reference
                        ].source
                        response = CoreIntelligenceAnswerResponse(
                            request_id=request_id,
                            user_message=request.message,
                            portal_type=portal_type,
                            intent=plan.intent,
                            plan_status="ready_to_execute",
                            execution_status="completed",
                            status="ready",
                            answer=(
                                f"**{candidate_facts[0].entity_name}** was listed as a learning candidate "
                                f"because {explanation} The role association is from {source}. "
                                "O*NET's static technology mapping is role context, not proof of a required qualification "
                                "or current employer demand."
                            ),
                            facts=cited_facts,
                            evidence=prior_evidence,
                            capabilities_used=["action_recommendations"],
                            limitations=list(dict.fromkeys([
                                *prior_response.limitations,
                                "This follow-up reuses validated evidence from the prior recommendation turn; no new market data was retrieved.",
                            ])),
                            reason_codes=["PRIOR_RECOMMENDATION_EVIDENCE_RETRIEVED"],
                            follow_up_questions=[],
                            conversation_id=request.conversation_id,
                            client_message_id=request.client_message_id,
                        )
                        validation_status, validation_reasons = self._validate_response(
                            answer_text=response.answer,
                            facts=response.facts,
                            evidence=response.evidence,
                            capabilities_used=response.capabilities_used,
                            plan=plan,
                        )
                        if validation_status == "completed":
                            self._record_conversation_turn(
                                request, plan, response, authenticated_user, portal_type
                            )
                            return response
                        logger.warning(
                            "Prior recommendation evidence failed response validation: %s",
                            validation_reasons,
                        )

        explicit_time_range = (
            "time_range" in request.model_fields_set
            or any(
                request.filters.get(key) not in (None, "")
                for key in ("time_range", "requested_time_window")
            )
        )
        if request.conversation_id and not explicit_time_range:
            conv_state = self.conversation_store.get_conversation(
                request.conversation_id,
                user_id=user_id,
                company_id=user_company_id,
            )
            if conv_state and conv_state.time_range and conv_state.time_range != "30d":
                request = request.model_copy(update={"time_range": conv_state.time_range})
                plan.context_summary["time_range"] = conv_state.time_range
        if (
            plan.intent in {"synthesize_actions", "analyze_skill_gap"}
            and not explicit_time_range
            and request.time_range == "30d"
        ):
            request = request.model_copy(update={"time_range": "6m"})
            plan.context_summary["time_range"] = "6m"

        if (
            (
                "skill_half_life_analysis" in plan.selected_capabilities
                or plan.intent == "estimate_skill_half_life"
                or (
                    "evidence_provenance_retrieval" in plan.selected_capabilities
                    and re.search(r"\b(?:half[- ]life)\b", request.message, re.IGNORECASE)
                )
            )
            and not explicit_time_range
        ):
            request = request.model_copy(update={"time_range": "36m"})
            plan.context_summary["time_range"] = "36m"
        elif (
            (
                "skill_forecasting_half_life" in plan.selected_capabilities
                or plan.intent == "forecast_future_demand"
                or (
                    "evidence_provenance_retrieval" in plan.selected_capabilities
                    and re.search(r"\b(?:forecast|future)\b", request.message, re.IGNORECASE)
                )
            )
            and not explicit_time_range
        ):
            request = request.model_copy(update={"time_range": "24m"})
            plan.context_summary["time_range"] = "24m"
        elif (
            (
                "trend_velocity_analysis" in plan.selected_capabilities
                or plan.intent == "analyze_trend"
                or "skill_health_analysis" in plan.selected_capabilities
                or plan.intent == "analyze_skill_health"
                or (
                    "evidence_provenance_retrieval" in plan.selected_capabilities
                    and re.search(r"\b(?:trend|health)\b", request.message, re.IGNORECASE)
                )
            )
            and not explicit_time_range
        ):
            request = request.model_copy(update={"time_range": "6m"})
            plan.context_summary["time_range"] = "6m"
        market_capabilities = {
            "market_snapshot", "historical_signal_retrieval", "trend_velocity_analysis",
            "evidence_provenance_retrieval",
        }
        if request.domain == "market" or market_capabilities.intersection(plan.selected_capabilities):
            trend_location = request.location or self._extract_trend_question_location(request.message)
            if trend_location:
                request = request.model_copy(update={"location": trend_location})
                plan.context_summary["location"] = trend_location
        elif "job_posting_search" in plan.selected_capabilities:
            job_location = request.location or self._extract_question_country(request.message)
            if job_location:
                filters = dict(request.filters or {})
                country_codes = {
                    "india": "IN", "united states": "US", "usa": "US", "united kingdom": "GB",
                    "uk": "GB", "canada": "CA", "australia": "AU", "germany": "DE",
                    "france": "FR", "brazil": "BR", "japan": "JP", "china": "CN",
                    "singapore": "SG", "ireland": "IE", "netherlands": "NL", "sweden": "SE",
                    "norway": "NO", "denmark": "DK", "finland": "FI", "spain": "ES",
                    "italy": "IT", "mexico": "MX", "argentina": "AR", "south korea": "KR",
                    "new zealand": "NZ", "south africa": "ZA", "united arab emirates": "AE",
                    "switzerland": "CH", "poland": "PL",
                }
                normalized_country = job_location.casefold().strip()
                if not filters.get("country") and normalized_country in country_codes:
                    filters["country"] = country_codes[normalized_country]
                request = request.model_copy(update={"location": job_location, "filters": filters})
                plan.context_summary["location"] = job_location
        elif getattr(plan, "intent", None) == "rank_skill_trends":
            trend_location = request.location or self._extract_trend_question_location(request.message)
            if trend_location:
                request = request.model_copy(update={"location": trend_location})
                plan.context_summary["location"] = trend_location
        plan.context_summary["_analysis_cache_scope"] = (
            user_id,
            user_company_id,
            request.portal_type,
        )

        # 2. Check for Unsupported Intents (Simulation)
        unsupported_simulation = plan.intent in {"simulate_workforce_scenarios"}
        if unsupported_simulation or plan.plan_status == "unsupported":
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
                    "Workforce what-if simulation is explicitly inactive and unsupported in milestone G2.6. "
                    "It is unavailable because the repository has no approved "
                    "simulation engine or reproducible calculation method, verified workforce baseline, "
                    "validated employee-to-role assignments, trustworthy proficiency records, approved "
                    "future skill requirements, or documented action assumptions. No projections, costs, "
                    "savings, staffing recommendations, or hiring outcomes were generated."
                    if unsupported_simulation
                    else (plan.limitations[0] if plan.limitations else "The requested capability is not supported in this domain.")
                ),
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=(
                    list(dict.fromkeys([
                        *plan.limitations,
                        "No verified workforce baseline is available as a simulation input.",
                        "Validated employee-to-role assignments and trustworthy skill proficiency records are unavailable.",
                        "Approved future role-skill requirements and documented upskilling, reskilling, redeployment, or hiring assumptions are unavailable.",
                        "No approved simulation engine or reproducible calculation method is implemented.",
                    ]))
                    if unsupported_simulation
                    else plan.limitations or ["The requested capability is not supported in this domain."]
                ),
                reason_codes=(
                    ["CAPABILITY_UNSUPPORTED_IN_G2_6", "SIMULATION_PREREQUISITES_NOT_MET"]
                    if unsupported_simulation
                    else ["CAPABILITY_NOT_SUPPORTED_IN_DOMAIN"]
                ),
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
            blocked_readiness = next(
                (
                    result for result in plan.readiness_results
                    if result.capability_id == "ai_task_exposure"
                ),
                None,
            )
            resp = CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                domain=request.domain,
                intent=plan.intent,
                plan_status="blocked",
                execution_status="blocked",
                status="unavailable",
                answer=(
                    blocked_readiness.explanation
                    if blocked_readiness
                    else "This analytical operation is currently blocked by platform policy or data quality gates."
                ),
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=plan.limitations,
                reason_codes=(
                    blocked_readiness.reason_codes
                    if blocked_readiness and blocked_readiness.reason_codes
                    else ["CAPABILITY_BLOCKED"]
                ),
                follow_up_questions=[],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
            resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

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

        # General knowledge answers have no platform evidence. Keep this path
        # separate from capability execution so empty evidence cannot be mistaken
        # for an insufficient or measured TalentScope result.
        if plan.intent == "general_explanation":
            general_text = None
            try:
                if self.llm_service.is_available():
                    general_text = self.llm_service.generate_grounded_explanation(
                        user_message=request.message,
                        intent=plan.intent,
                        facts=[],
                        evidence=[],
                        portal_type="general",
                        user_id=user_id,
                        general_knowledge=True,
                    )
            except Exception as exc:
                logger.warning("Gemini general explanation failed error_class=%s", type(exc).__name__)
                try:
                    self.llm_service.last_error_class = "provider_error"
                    self.llm_service.last_provider_error_class = "provider_error"
                except Exception:
                    pass
            used_provider = bool(general_text)
            provider_failure = getattr(self.llm_service, "last_provider_error_class", None)
            exhausted_provider = bool(
                provider_failure
                and provider_failure not in {"offline", "missing_api_key", "no_grounding_facts"}
            )
            if not general_text:
                general_text = (
                    GEMINI_DEGRADED_MESSAGE
                    if exhausted_provider
                    else _offline_general_explanation(request.message)
                )
            if general_text:
                resp = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain=request.domain,
                    intent=plan.intent,
                    plan_status="ready_to_execute",
                    execution_status="failed" if exhausted_provider else "completed",
                    status="unavailable" if exhausted_provider else "ready",
                    answer=(
                        ("General AI explanation (not a TalentScope data finding): " + general_text)
                        if used_provider
                        else general_text if exhausted_provider
                        else "General explanation (offline fallback; not a TalentScope data finding): " + general_text
                    ),
                    answer_origin=("gemini" if used_provider else "deterministic"),
                    degraded=(not used_provider or exhausted_provider),
                    degraded_reason=(None if used_provider else (getattr(self.llm_service, "last_error_class", None) or "unavailable")),
                    facts=[],
                    evidence=[],
                    planned_capabilities=[],
                    capabilities_used=[],
                    limitations=(
                        ["Gemini providers failed after bounded retries; no analysis was generated."]
                        if exhausted_provider
                        else ["This is general knowledge, not a measured TalentScope market or hiring result."]
                    ),
                    reason_codes=["GEMINI_PROVIDERS_UNAVAILABLE" if exhausted_provider else "GENERAL_KNOWLEDGE_EXPLANATION"],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
            else:
                resp = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain=request.domain,
                    intent=plan.intent,
                    plan_status="ready_to_execute",
                    execution_status="unsupported",
                    status="unavailable",
                    answer="General AI explanation is unavailable right now. No TalentScope market or hiring result was produced.",
                    answer_origin="deterministic",
                    facts=[],
                    evidence=[],
                    planned_capabilities=[],
                    capabilities_used=[],
                    limitations=["Gemini is unavailable, over budget, or returned an answer that failed validation."],
                    reason_codes=["GENERAL_EXPLANATION_UNAVAILABLE"],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
            self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
            return resp

        if (
            plan.intent == "analyze_company_workforce"
            and authenticated_user is not None
            and user_company_id
        ):
            trusted_context = dict(request.context_override)
            trusted_context["_authorized_company_owner_uid"] = authenticated_user.uid
            trusted_context["_authorized_company_id"] = user_company_id
            request = request.model_copy(update={"context_override": trusted_context})
            plan.context_summary["company_id"] = user_company_id

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
                "skill_health_analysis",
                "skill_half_life_analysis",
                "skill_forecasting_half_life",
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
            and any(c in plan.selected_capabilities for c in ("trend_velocity_analysis", "skill_health_analysis", "skill_half_life_analysis", "skill_forecasting_half_life"))
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
            capability_context = dict(request.context_override)
            if plan.context_summary.get("_historical_signal_context"):
                capability_context["_historical_signal_context"] = plan.context_summary["_historical_signal_context"]
            primary_entity = next((item.canonical_entity for item in plan.entities if item.canonical_entity), None)
            if primary_entity and primary_entity.source == "ref_esco_occupations":
                capability_context.update({"taxonomy": "esco", "occupation_uri": primary_entity.source_record_id})
            elif primary_entity and primary_entity.source == "ref_esco_skills":
                capability_context.update({"taxonomy": "esco", "skill_uri": primary_entity.source_record_id})
            for cap_id in plan.selected_capabilities:
                eval_req = CapabilityEvaluationRequest(
                    capability_id=cap_id,
                    entity_name=(
                        request.target_role
                        or (request.selected_roles[0] if request.selected_roles else None)
                        or plan.context_summary.get("primary_entity")
                        or (request.message if cap_id == "job_posting_search" else None)
                    ),
                    portal_type=portal_type,  # type: ignore[arg-type]
                    time_range=request.time_range,
                    location=request.location,
                    target_role=request.target_role,
                    selected_skills=request.selected_skills or [
                        item.canonical_entity.canonical_name
                        for item in plan.entities
                        if item.canonical_entity
                        and item.canonical_entity.entity_type in {"skill", "technology"}
                    ],
                    observations=(
                        shared_analysis.observations if shared_analysis is not None
                        else request.observations
                    ),
                    task_exposure_records=request.task_exposure_records,
                    dataset_provenance=request.dataset_provenance,
                    context_override=capability_context,
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
                half_life_requested = "skill_half_life_analysis" in plan.selected_capabilities
                forecast_requested = "skill_forecasting_half_life" in plan.selected_capabilities or plan.intent == "forecast_future_demand"
                health_requested = "skill_health_analysis" in plan.selected_capabilities
                trend_requested = "trend_velocity_analysis" in plan.selected_capabilities
                task_exposure_requested = "ai_task_exposure" in plan.selected_capabilities or plan.intent == "analyze_ai_task_exposure"
                learning_requested = (
                    "action_recommendations" in plan.selected_capabilities
                    or "skill_gap_role_fit" in plan.selected_capabilities
                    or plan.intent in {"synthesize_actions", "analyze_skill_gap"}
                )
                if forecast_requested and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No measured demand observations are currently available for '{ent_name}' "
                        "with the selected filters. A skill demand forecast cannot be established until comparable "
                        "observations are available."
                    )
                    insufficient_limitations = [
                        "Skill Demand Forecasting requires at least 24 consecutive completed monthly periods.",
                        *all_limitations,
                    ]
                    reason_code = "NO_OBSERVATIONS_FOR_SERIES"
                elif forecast_requested:
                    first_res = next((r for r in readiness_results if r.capability_id == "skill_forecasting_half_life"), None)
                    reason_code = first_res.reason_codes[0] if first_res and first_res.reason_codes else "INSUFFICIENT_FORECAST_HISTORY"
                    answer_text = (
                        first_res.explanation
                        if first_res and first_res.explanation
                        else f"The available history for '{ent_name}' is insufficient to calculate a skill demand forecast. At least 24 consecutive completed monthly periods are required."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        "Skill Demand Forecasting requires at least 24 consecutive completed monthly periods.",
                    ]
                elif half_life_requested and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No measured Skill Half-Life observations are currently available for '{ent_name}' "
                        "with the selected filters. A Skill Half-Life estimate cannot be established until comparable "
                        "observations with denominators are available."
                    )
                    insufficient_limitations = [
                        "Skill Half-Life requires at least 36 consecutive completed monthly periods with valid denominators.",
                        *all_limitations,
                    ]
                    reason_code = "NO_OBSERVATIONS_FOR_SERIES"
                elif half_life_requested:
                    first_res = next((r for r in readiness_results if r.capability_id == "skill_half_life_analysis"), None)
                    reason_code = first_res.reason_codes[0] if first_res and first_res.reason_codes else "INSUFFICIENT_HALF_LIFE_HISTORY"
                    answer_text = (
                        first_res.explanation
                        if first_res and first_res.explanation
                        else f"The available history for '{ent_name}' is insufficient to calculate Skill Half-Life. At least 36 consecutive completed monthly periods with denominators are required."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        "Skill Half-Life requires at least 36 consecutive completed monthly periods with valid denominators.",
                    ]
                elif health_requested and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No measured Skill Health observations are currently available for '{ent_name}' "
                        "with the selected filters. A Skill Health score cannot be established until comparable "
                        "observations with denominators are available."
                    )
                    insufficient_limitations = [
                        "Skill Health requires at least four consecutive completed monthly periods with valid denominators.",
                        *all_limitations,
                    ]
                    reason_code = "NO_OBSERVATIONS_FOR_SERIES"
                elif health_requested:
                    first_res = next((r for r in readiness_results if r.capability_id == "skill_health_analysis"), None)
                    reason_code = first_res.reason_codes[0] if first_res and first_res.reason_codes else "INSUFFICIENT_HEALTH_HISTORY"
                    answer_text = (
                        first_res.explanation
                        if first_res and first_res.explanation
                        else f"The available history for '{ent_name}' is insufficient to calculate a Skill Health score. At least four consecutive completed monthly periods with denominators are required."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        "Skill Health requires at least four consecutive completed monthly periods with valid denominators.",
                    ]
                elif task_exposure_requested:
                    first_res = next((r for r in readiness_results if r.capability_id == "ai_task_exposure"), None)
                    reason_code = first_res.reason_codes[0] if first_res and first_res.reason_codes else "NO_MATCHING_TASK_RECORDS"
                    answer_text = (
                        first_res.explanation
                        if first_res and first_res.explanation
                        else f"No task exposure records matched '{ent_name}' in the verified reference dataset."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        "Task exposure analysis requires verified task mapping records for the target occupation or skill.",
                    ]
                elif "market_snapshot" in plan.selected_capabilities and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No stored market observations are available to verify current hiring demand for '{ent_name}'. "
                        "No demand level or trend can be inferred from static occupational taxonomy data."
                    )
                    insufficient_limitations = [
                        "A current demand conclusion requires persisted empirical market observations.",
                        "ESCO and O*NET taxonomy associations are reference relationships, not live hiring evidence.",
                        *all_limitations,
                    ]
                    reason_code = "NO_STORED_MARKET_OBSERVATIONS"
                elif trend_requested and not (shared_analysis and shared_analysis.observations):
                    answer_text = (
                        f"No measured trend observations are currently available for '{ent_name}' "
                        "with the selected filters. No trend value can be established until comparable "
                        "observations are available."
                    )
                    insufficient_limitations = [
                        "Trend direction requires at least four consecutive comparable monthly periods.",
                        *all_limitations,
                    ]
                    reason_code = "NO_OBSERVATIONS_FOR_SERIES"
                elif trend_requested:
                    trend_readiness = next(
                        (
                            result for result in readiness_results
                            if result.capability_id == "trend_velocity_analysis"
                        ),
                        None,
                    )
                    reason_code = (
                        trend_readiness.reason_codes[0]
                        if trend_readiness and trend_readiness.reason_codes
                        else "INSUFFICIENT_TREND_HISTORY"
                    )
                    answer_text = (
                        trend_readiness.explanation
                        if trend_readiness and trend_readiness.explanation
                        else (
                            f"The available history for '{ent_name}' is insufficient to calculate a "
                            "directional trend. At least four consecutive comparable completed "
                            "monthly periods are required."
                        )
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        *(
                            trend_readiness.missing_requirements
                            if trend_readiness else []
                        ),
                        "Trend direction requires at least four consecutive comparable monthly periods.",
                    ]
                elif "historical_signal_retrieval" in plan.selected_capabilities:
                    historical_readiness = next(
                        (
                            result for result in readiness_results
                            if result.capability_id == "historical_signal_retrieval"
                        ),
                        None,
                    )
                    reason_code = (
                        historical_readiness.reason_codes[0]
                        if historical_readiness and historical_readiness.reason_codes
                        else "INSUFFICIENT_HISTORICAL_PERIODS"
                    )
                    answer_text = (
                        historical_readiness.explanation
                        if historical_readiness and historical_readiness.explanation
                        else f"Historical observations for '{ent_name}' require at least two distinct periods."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        *(
                            historical_readiness.missing_requirements
                            if historical_readiness else []
                        ),
                    ]
                elif learning_requested:
                    readiness = next(
                        (
                            result for result in readiness_results
                            if result.capability_id in {
                                "action_recommendations", "skill_gap_role_fit"
                            }
                        ),
                        None,
                    )
                    reason_code = (
                        readiness.reason_codes[0]
                        if readiness and readiness.reason_codes
                        else "LEARNING_PROFILE_OR_TARGET_ROLE_REQUIRED"
                    )
                    answer_text = (
                        readiness.explanation
                        if readiness and readiness.explanation
                        else "Provide one target role to compare with your own recorded skills."
                    )
                    insufficient_limitations = [
                        *all_limitations,
                        "Without a resolved role and applicable mappings, no personalized skill-gap recommendation is produced.",
                    ]
                else:
                    answer_text = f"Insufficient empirical observation data available for '{ent_name}' to complete this analysis."
                    insufficient_limitations = all_limitations or ["At least 4 consecutive monthly periods required for trend analysis."]
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
                    limitations=insufficient_limitations,
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
                task_res = next((r for r in readiness_results if r.capability_id == "ai_task_exposure"), None)
                blocked_reason = task_res.reason_codes[0] if task_res and task_res.reason_codes else "CAPABILITY_NOT_READY"
                blocked_answer = (
                    task_res.explanation
                    if task_res and task_res.explanation
                    else "Execution cannot proceed because required capabilities did not meet runtime readiness gates."
                )
                resp = CoreIntelligenceAnswerResponse(
                    request_id=request_id,
                    user_message=request.message,
                    portal_type=portal_type,
                    domain=request.domain,
                    intent=plan.intent,
                    plan_status="blocked",
                    execution_status="blocked",
                    status="unavailable",
                    answer=blocked_answer,
                    facts=[],
                    evidence=[],
                    capabilities_used=[],
                    limitations=all_limitations,
                    reason_codes=[blocked_reason],
                    follow_up_questions=[],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
                resp = self._enrich_answer_response(resp, request, plan, authenticated_user)
                self._record_conversation_turn(request, plan, resp, authenticated_user, portal_type)
                return resp

        # 7. Execute Verified Handlers
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = list(plan.limitations)
        capabilities_used: list[str] = []
        handler_results: list[tuple[str, str, list[StructuredFact], list[EvidenceItem]]] = []

        try:
            for cap_id in executable_caps:
                handler = self._handler_registry.get(cap_id)
                if not handler:
                    limitations.append(f"Handler for registered capability '{cap_id}' is not yet mounted.")
                    continue
                handler_intent = _feature_intent(cap_id, plan.intent)
                handler_plan = plan.model_copy(update={"intent": handler_intent})
                try:
                    cap_facts, cap_evidence, cap_limits = handler(request, handler_plan)
                except (DataSourceUnavailableError, Exception) as exc:
                    if len(executable_caps) < 2:
                        raise
                    limitations.append(
                        f"Missing source for {handler_intent.replace('_', ' ')}: {type(exc).__name__}."
                    )
                    continue
                facts.extend(cap_facts)
                evidence.extend(cap_evidence)
                limitations.extend(cap_limits)
                capabilities_used.append(cap_id)
                handler_results.append((cap_id, handler_intent, cap_facts, cap_evidence))

        except DataSourceUnavailableError as exc:
            logger.warning(
                "Intelligence data source unavailable request_id=%s capability=%s error_type=%s",
                request_id,
                cap_id if "cap_id" in locals() else "unknown",
                type(exc).__name__,
            )
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
                limitations=["The configured intelligence data source could not provide this request."],
                reason_codes=["INTELLIGENCE_SOURCE_UNAVAILABLE"],
                follow_up_questions=[],
                planned_primary_capability=plan.primary_capability,
                executed_primary_capability=None,
                planned_capabilities=list(plan.selected_capabilities),
                dependency_capabilities=list(plan.dependency_capabilities),
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )
        except Exception as exc:
            failed_capability = cap_id if "cap_id" in locals() else "unknown"
            logger.error(
                "Intelligence handler failed request_id=%s capability=%s error_type=%s",
                request_id,
                failed_capability,
                type(exc).__name__,
            )
            return CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                intent=plan.intent,
                plan_status=plan.plan_status,
                execution_status="failed",
                status="error",
                answer=f"I couldn't complete this analysis. Please try again later. Reference: {request_id}.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=["The analysis stopped before verified results could be produced."],
                reason_codes=["HANDLER_EXECUTION_FAILED"],
                follow_up_questions=[],
                planned_primary_capability=plan.primary_capability,
                executed_primary_capability=None,
                planned_capabilities=list(plan.selected_capabilities),
                dependency_capabilities=list(plan.dependency_capabilities),
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )

        # 8. Synthesize Grounded Natural Language Answer
        combined_answer = len(handler_results) > 1
        if combined_answer:
            parts = []
            for index, (cap_id, handler_intent, part_facts, part_evidence) in enumerate(handler_results[:2], start=1):
                if part_facts:
                    part_text = self._synthesize_answer(
                        handler_intent, part_facts, part_evidence, [cap_id], request,
                        plan=plan.model_copy(update={"intent": handler_intent}),
                    )
                else:
                    part_text = f"Missing source: no verified results were returned by {cap_id}."
                parts.append(f"**Part {index} — {handler_intent.replace('_', ' ').title()}**\n\n{part_text}")
            combined_prompt = (
                "Synthesize the separately labelled evidence for this combined question. Keep the two parts and their "
                "sources distinct, identify any missing source, and do not add facts. Original question: " + request.message
            )
            synthesis = None
            try:
                if self.llm_service.is_available():
                    synthesis = self.llm_service.generate_grounded_explanation(
                        user_message=combined_prompt, intent=plan.intent, facts=facts,
                        evidence=evidence, portal_type=portal_type, user_id=user_id,
                    )
            except Exception as exc:
                logger.warning("Gemini combined synthesis failed error_class=%s", type(exc).__name__)
            answer_text = "\n\n".join(parts)
            if synthesis:
                answer_text += "\n\n**Synthesis**\n\n" + synthesis
            else:
                answer_text += "\n\n**Synthesis:** Cross-part synthesis is unavailable; the two evidence-backed parts are shown separately."
        else:
            answer_text = self._synthesize_answer(plan.intent, facts, evidence, capabilities_used, request, plan=plan)
        answer_text = self._append_demand_sample_note(answer_text, facts, plan)

        # Optional LLM Grounded Explanation if available
        answer_origin = "deterministic"
        if facts and not combined_answer:
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
                        answer_origin = "gemini"
            except Exception as exc:
                logger.warning(
                    "Gemini explanation failed request_id=%s error_class=%s",
                    request_id,
                    type(exc).__name__,
                )
                try:
                    self.llm_service.last_error_class = "provider_error"
                except Exception:
                    pass
        if answer_origin != "gemini" and facts:
            answer_text = "**Deterministic fallback (Gemini unavailable):**\n\n" + answer_text
            provider_failure = getattr(self.llm_service, "last_provider_error_class", None)
            if provider_failure and provider_failure not in {"offline", "missing_api_key", "no_grounding_facts"}:
                answer_text = GEMINI_DEGRADED_MESSAGE + "\n\n" + answer_text

        if plan.intent == "aggregate_posting_skills":
            aggregate = next((fact for fact in facts if fact.fact_type == "collected_posting_skills_summary"), None)
            n = int(aggregate.metric_value) if aggregate else 0
            from app.services.collected_posting_skills_service import format_collected_postings_disclosure
            answer_text += "\n\n" + format_collected_postings_disclosure(n)

        disclosures = list(dict.fromkeys(
            str(fact.details.get("mapping_disclosure"))
            for fact in facts
            if fact.details.get("mapping_disclosure")
        ))
        if disclosures:
            answer_text += "\n\nOccupation mapping: " + " ".join(disclosures)

        # 9. Deterministic Response Validation
        val_status, val_reasons = self._validate_response(
            answer_text=answer_text,
            facts=facts,
            evidence=evidence,
            capabilities_used=capabilities_used,
            plan=plan,
        )

        if val_status != "completed":
            logger.warning(
                "Intelligence response validation failed request_id=%s reason_codes=%s",
                request_id,
                ",".join(val_reasons[:5]),
            )
            return CoreIntelligenceAnswerResponse(
                request_id=request_id,
                user_message=request.message,
                portal_type=portal_type,
                intent=plan.intent,
                plan_status=plan.plan_status,
                execution_status=val_status,
                status="error",
                answer=f"I couldn't verify this analysis against its evidence. Please try again later. Reference: {request_id}.",
                facts=[],
                evidence=[],
                capabilities_used=[],
                limitations=["The response failed evidence validation; no analysis results are available."],
                reason_codes=val_reasons,
                follow_up_questions=[],
                planned_primary_capability=plan.primary_capability,
                executed_primary_capability=None,
                planned_capabilities=list(plan.selected_capabilities),
                dependency_capabilities=list(plan.dependency_capabilities),
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )

        follow_ups = self._generate_follow_up_questions(plan.intent, facts, plan, request)
        no_stored_job_postings = (
            plan.intent == "search_jobs"
            and any(
                fact.fact_type == "stored_job_postings"
                and (fact.metric_value == 0 or fact.readiness_state == "insufficient_data")
                for fact in facts
            )
        )
        no_market_snapshot = (
            plan.intent == "retrieve_snapshot"
            and any(
                fact.fact_type == "analysis_readiness"
                and fact.metric_name == "market_evidence_readiness"
                and fact.readiness_state == "insufficient_data"
                for fact in facts
            )
        )
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
        trend_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "analysis_readiness"
                and fact.metric_name in {"trend_readiness", "trend_direction_readiness"}
            ),
            None,
        )
        unavailable_focused_trend = (
            plan.intent == "analyze_trend"
            and "trend_velocity_analysis" in plan.selected_capabilities
            and not any(fact.fact_type == "trend_analysis" for fact in facts)
        )
        health_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "analysis_readiness"
                and fact.metric_name in {"skill_health_readiness", "health_readiness"}
            ),
            None,
        )
        unavailable_focused_health = (
            plan.intent == "analyze_skill_health"
            and "skill_health_analysis" in plan.selected_capabilities
            and not any(
                fact.fact_type == "skill_health_score"
                and fact.metric_value is not None
                for fact in facts
            )
            and not any(
                fact.fact_type == "skill_health_score"
                and fact.quality_state == "ambiguous_series"
                for fact in facts
            )
        )
        half_life_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "analysis_readiness"
                and fact.metric_name in {"skill_half_life_readiness", "half_life_readiness"}
            ),
            None,
        )
        unavailable_focused_half_life = (
            plan.intent == "estimate_skill_half_life"
            and "skill_half_life_analysis" in plan.selected_capabilities
            and not any(
                fact.fact_type == "skill_half_life"
                and (fact.metric_value is not None or fact.quality_state in {"ready", "not_applicable"})
                for fact in facts
            )
        )
        learning_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "learning_recommendation_readiness"
            ),
            None,
        )
        learning_summary_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "learning_recommendation_summary"
            ),
            None,
        )
        has_learning_candidates = any(
            fact.fact_type == "action_recommendation" for fact in facts
        )
        unavailable_focused_learning = (
            plan.intent in {"synthesize_actions", "analyze_skill_gap"}
            and learning_readiness_fact is not None
            and learning_readiness_fact.readiness_state == "unavailable"
        )
        insufficient_focused_learning = (
            plan.intent in {"synthesize_actions", "analyze_skill_gap"}
            and (
                (
                    learning_readiness_fact is not None
                    and learning_readiness_fact.readiness_state == "insufficient_data"
                )
                or (
                    learning_summary_fact is not None
                    and learning_summary_fact.readiness_state == "insufficient_data"
                    and not has_learning_candidates
                )
            )
        )
        evidence_summary_fact = next(
            (fact for fact in facts if fact.fact_type == "evidence_summary"), None
        )
        insufficient_evidence_retrieval = bool(
            "evidence_provenance_retrieval" in plan.selected_capabilities
            and evidence_summary_fact is not None
            and evidence_summary_fact.metric_value == 0
        )
        company_workforce_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "company_workforce_summary"
            ),
            None,
        )
        insufficient_company_workforce = bool(
            plan.intent == "analyze_company_workforce"
            and company_workforce_readiness_fact
            and company_workforce_readiness_fact.readiness_state == "insufficient_data"
        )
        insufficient_answer = (
            no_stored_job_postings
            or no_market_snapshot
            or
            is_empty_scoped_job_search
            or no_eligible_skill_trends
            or unavailable_focused_trend
            or unavailable_focused_health
            or unavailable_focused_half_life
        )
        trend_reason_code = (
            trend_readiness_fact.details.get("reason_code")
            if trend_readiness_fact and trend_readiness_fact.details else "TREND_NOT_READY"
        )
        health_reason_code = (
            health_readiness_fact.details.get("reason_code")
            if health_readiness_fact and health_readiness_fact.details else "INSUFFICIENT_HEALTH_HISTORY"
        )
        half_life_reason_code = (
            half_life_readiness_fact.details.get("reason_code")
            if half_life_readiness_fact and half_life_readiness_fact.details else "INSUFFICIENT_HALF_LIFE_HISTORY"
        )
        forecast_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "analysis_readiness"
                and fact.metric_name in {"skill_forecast_readiness", "forecast_readiness"}
            ),
            None,
        )
        unavailable_focused_forecast = (
            plan.intent == "forecast_future_demand"
            and "skill_forecasting_half_life" in plan.selected_capabilities
            and not any(
                fact.fact_type == "skill_forecast"
                and fact.quality_state == "ready"
                for fact in facts
            )
        )
        task_exp_readiness_fact = next(
            (
                fact for fact in facts
                if fact.fact_type == "analysis_readiness"
                and fact.metric_name in {"task_exposure_readiness", "ai_task_exposure_readiness"}
            ),
            None,
        )
        unavailable_focused_task_exposure = (
            plan.intent == "analyze_ai_task_exposure"
            and "ai_task_exposure" in plan.selected_capabilities
            and not any(
                fact.fact_type == "task_exposure_summary"
                and fact.quality_state == "valid"
                for fact in facts
            )
        )
        insufficient_answer = (
            no_stored_job_postings
            or is_empty_scoped_job_search
            or no_eligible_skill_trends
            or unavailable_focused_trend
            or unavailable_focused_health
            or unavailable_focused_half_life
            or unavailable_focused_forecast
            or unavailable_focused_task_exposure
            or unavailable_focused_learning
            or insufficient_focused_learning
            or insufficient_company_workforce
            or insufficient_evidence_retrieval
        )
        forecast_reason_code = (
            forecast_readiness_fact.details.get("reason_code")
            if forecast_readiness_fact and forecast_readiness_fact.details else "INSUFFICIENT_FORECAST_HISTORY"
        )
        task_exp_reason_code = (
            task_exp_readiness_fact.details.get("reason_code") or task_exp_readiness_fact.details.get("status")
            if task_exp_readiness_fact and task_exp_readiness_fact.details else "NO_MATCHING_TASK_RECORDS"
        )
        resp = CoreIntelligenceAnswerResponse(
            request_id=request_id,
            user_message=request.message,
            portal_type=portal_type,
            intent=plan.intent,
            plan_status=plan.plan_status,
            execution_status=(
                "completed" if (
                    # A zero-result stored-job search is still a successful
                    # execution: the handler queried its configured store and
                    # returned an evidence-backed count of zero. Data status
                    # remains insufficient_data below.
                    no_stored_job_postings
                    or
                    unavailable_focused_trend
                    or unavailable_focused_health
                    or unavailable_focused_half_life
                    or unavailable_focused_forecast
                    or unavailable_focused_task_exposure
                    or unavailable_focused_learning
                )
                else "insufficient_data" if insufficient_answer
                else "completed"
            ),
            status=(
                task_exp_readiness_fact.readiness_state
                if (unavailable_focused_task_exposure and task_exp_readiness_fact and task_exp_readiness_fact.readiness_state in {"unavailable", "insufficient_data", "blocked"})
                else learning_readiness_fact.readiness_state
                if unavailable_focused_learning and learning_readiness_fact
                else learning_readiness_fact.readiness_state
                if insufficient_focused_learning and learning_readiness_fact
                else learning_summary_fact.readiness_state
                if insufficient_focused_learning and learning_summary_fact
                else company_workforce_readiness_fact.readiness_state
                if insufficient_company_workforce and company_workforce_readiness_fact
                else forecast_readiness_fact.readiness_state
                if (unavailable_focused_forecast and forecast_readiness_fact and forecast_readiness_fact.readiness_state in {"unavailable", "insufficient_data"})
                else "insufficient_data" if insufficient_answer else "ready"
            ),
            answer=answer_text,
            answer_origin=answer_origin,
            facts=facts,
            evidence=evidence,
            capabilities_used=capabilities_used,
            limitations=limitations,
            reason_codes=(
                ["INSUFFICIENT_SCOPED_JOB_POSTINGS"] if is_empty_scoped_job_search
                else ["NO_STORED_JOB_POSTINGS"] if no_stored_job_postings
                else ["NO_STORED_MARKET_OBSERVATIONS"] if no_market_snapshot
                else ["NO_ELIGIBLE_SKILL_TRENDS"] if no_eligible_skill_trends
                else [trend_reason_code] if unavailable_focused_trend
                else [health_reason_code] if unavailable_focused_health
                else [half_life_reason_code] if unavailable_focused_half_life
                else [forecast_reason_code] if unavailable_focused_forecast
                else [task_exp_reason_code] if unavailable_focused_task_exposure
                else [str(
                    learning_readiness_fact.details.get("reason_code")
                    if learning_readiness_fact and learning_readiness_fact.details
                    else learning_summary_fact.details.get("reason_code")
                    if learning_summary_fact and learning_summary_fact.details
                    else "LEARNING_RECOMMENDATION_NOT_READY"
                )] if (unavailable_focused_learning or insufficient_focused_learning)
                else ["NO_VERIFIED_EVIDENCE"] if insufficient_evidence_retrieval
                else [str(
                    company_workforce_readiness_fact.details.get("reason_code")
                    if company_workforce_readiness_fact and company_workforce_readiness_fact.details
                    else "COMPANY_WORKFORCE_RECORDS_INSUFFICIENT"
                )] if insufficient_company_workforce
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
        """Populate canonical status and additive conversational response metadata."""
        assistant_fields = self._assistant_contract_fields(resp, request, plan)
        if resp.status in {"unavailable", "error"}:
            return resp.model_copy(update={
                **assistant_fields,
                "planned_primary_capability": plan.primary_capability if plan else None,
                "executed_primary_capability": None,
                "dependency_capabilities": list(plan.dependency_capabilities) if plan else [],
                "planned_capabilities": list(plan.selected_capabilities) if plan else [],
            })

        primary_ent = plan.context_summary.get("primary_entity") if plan else None

        # Applied vs Unapplied filters
        from app.services.answer_block_service import infer_assistant_domain
        filter_domain = request.filters.get("domain") if request.filters else None
        effective_domain = (
            request.domain if request.domain in {"skill", "market", "job"}
            else filter_domain if filter_domain in {"skill", "market", "job"}
            else infer_assistant_domain(plan.intent if plan else resp.intent)
        )
        disclosure_suppressed = bool(
            plan and plan.intent in {"general_explanation", "explain_concept", "lookup_skill_reference"}
        )
        applied_filters: dict[str, Any] = {
            "portal_type": resp.portal_type,
            "domain": effective_domain,
            "query": request.message,
        }
        unapplied_filters: list[dict[str, str]] = []
        if request.location and not disclosure_suppressed:
            applied_filters["location"] = request.location
        if request.time_range and not disclosure_suppressed:
            applied_filters["time_range"] = request.time_range
        if request.target_role and not disclosure_suppressed:
            applied_filters["target_role"] = request.target_role
        if request.selected_skills and not disclosure_suppressed:
            applied_filters["selected_skills"] = list(request.selected_skills)
        if request.selected_roles and not disclosure_suppressed:
            applied_filters["selected_roles"] = list(request.selected_roles)
        if request.selected_companies and not disclosure_suppressed:
            if effective_domain == "market":
                unapplied_filters.append({
                    "filter": "selected_companies",
                    "value": ", ".join(request.selected_companies),
                    "reason": "The configured market observation source contains technology signals, not company-level telemetry.",
                })
            else:
                applied_filters["selected_companies"] = list(request.selected_companies)

        if request.filters.get("country") and plan and plan.intent in {"search_jobs", "company_postings_summary"}:
            applied_filters["country"] = request.filters["country"]
        elif plan and plan.intent in {"search_jobs", "company_postings_summary"}:
            applied_filters["country"] = self._extract_question_country(request.message) or "India (default stored market)"
        if plan and plan.intent in {"search_jobs", "company_postings_summary"} and re.search(r"\bremote\b", request.message, re.IGNORECASE):
            applied_filters["remote_mode"] = "remote (title/location evidence)"

        extra_limitations: list[str] = []
        if request.filters and not disclosure_suppressed:
            for fk, fv in request.filters.items():
                if fv is None or fv == "":
                    continue
                # Routing metadata and profile skill context are not applied
                # request filters and should not produce a discarded-filter warning.
                if fk in {"selected_feature", "selected_skills", "feature_id"}:
                    continue
                if fk == "remote_mode" and fv == "remote" and plan and plan.intent in {"search_jobs", "company_postings_summary"}:
                    applied_filters[fk] = "remote (title/location evidence)"
                elif fk in {"salary_band", "seniority_level", "remote_mode", "visa_sponsorship"}:
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

        planned_capabilities = set(plan.selected_capabilities if plan else [])
        executed_capabilities = set(resp.capabilities_used or [])
        response_capabilities = planned_capabilities | executed_capabilities
        market_analysis_capabilities = {
            "market_snapshot",
            "historical_signal_retrieval",
            "trend_velocity_analysis",
            "skill_health_analysis",
            "skill_half_life_analysis",
            "skill_forecasting_half_life",
        }
        needs_market_analysis = bool(response_capabilities & market_analysis_capabilities)
        # Reference, job, profile, and general responses must not retrieve or
        # attach unrelated market analytics. Feature projections below are
        # limited to capabilities selected for this request.
        analysis = (
            self._shared_market_analysis(request, plan)
            if needs_market_analysis and plan is not None
            else SharedIntelligenceAnalysis([], [], [], history_complete=True)
        )
        obs = analysis.observations
        agg_signals = analysis.aggregated_signals
        trends = analysis.trend_results

        target_skill = primary_ent or (request.selected_skills[0] if request.selected_skills else "")
        target_canon_id = canonical_skill_id(target_skill) if target_skill else None
        sig_fam = (
            "demand" if any(s.signal_type == "demand" for s in agg_signals)
            else "adoption" if any(s.signal_type == "adoption" for s in agg_signals)
            else "interest"
        )
        skill_health_res = None
        half_life_res = None
        forecast_res = None
        capabilities_dict: dict[str, Any] = {}

        if "skill_health_analysis" in response_capabilities:
            skill_health_res = evaluate_skill_health(
                agg_signals,
                canonical_skill_id=target_canon_id,
                canonical_name=target_skill,
                history_complete=analysis.history_complete,
            )
            capabilities_dict["skill_health"] = {
                "status": skill_health_res.status,
                "payload": skill_health_res.model_dump(),
                "reason": skill_health_res.explanation,
            }
        if "skill_half_life_analysis" in response_capabilities:
            half_life_res = calculate_skill_half_life(
                agg_signals,
                canonical_skill_id=target_canon_id,
                canonical_name=target_skill,
                signal_family=sig_fam,
                min_periods=36,
                history_complete=analysis.history_complete,
            )
            capabilities_dict["skill_half_life"] = {
                "status": half_life_res.status,
                "payload": half_life_res.model_dump(),
                "reason": half_life_res.reason,
            }
        if "skill_forecasting_half_life" in response_capabilities:
            forecast_res = forecast_signal_series(
                agg_signals,
                canonical_skill_id=target_canon_id,
                canonical_name=target_skill,
                signal_family=sig_fam,
                min_periods=24,
                history_complete=analysis.history_complete,
            )
            capabilities_dict["forecast"] = {
                "status": forecast_res.status,
                "payload": forecast_res.model_dump(),
                "reason": forecast_res.reason,
            }

        latest_obs_dt = max((o.observed_at for o in obs if o.observed_at), default=None)
        latest_obs_iso = latest_obs_dt.isoformat() if latest_obs_dt else None
        max_periods = max((len(t.periods_used) for t in trends), default=len(obs))

        conf_res = compute_evidence_confidence(
            period_count=max_periods,
            ready_signal_families=(
                skill_health_res.ready_families
                if skill_health_res is not None else []
            ),
            family_directions=(
                [r.direction for r in skill_health_res.component_table if r.is_eligible_share]
                if skill_health_res is not None else []
            ),
            latest_observed_at=latest_obs_dt,
            has_valid_denominator=any(s.metric == "normalized_share" for s in agg_signals),
            quality_valid=bool(obs) or not needs_market_analysis,
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
            "signal_families_ready": len(skill_health_res.ready_families) if skill_health_res else 0,
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

        unapplied_by_filter: dict[str, dict[str, str]] = {}
        for item in unapplied_filters:
            unapplied_by_filter.setdefault(item.get("filter", "selected_option"), item)
        unapplied_filters = list(unapplied_by_filter.values())

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

        from app.services.answer_block_service import build_answer_block
        answer_block = build_answer_block(
            intent=resp.intent,
            user_message=resp.user_message,
            answer=resp.answer,
            facts=resp.facts,
            evidence=resp.evidence,
            limitations=merged_limitations,
        )
        return resp.model_copy(
            update={
                "domain": effective_domain,
                "answer_block": answer_block,
                "resolved_entity": primary_ent,
                "selected_entities": resolved_selections,
                "applied_filters": applied_filters,
                "unapplied_filters": unapplied_filters,
                "capabilities": capabilities_dict,
                "metric_results": metric_results,
                "planned_primary_capability": plan.primary_capability if plan else None,
                "executed_primary_capability": (
                    plan.primary_capability
                    if plan and plan.primary_capability in executed_capabilities
                    else next(iter(resp.capabilities_used), None)
                ),
                "dependency_capabilities": list(plan.dependency_capabilities) if plan else [],
                "planned_capabilities": list(plan.selected_capabilities) if plan else [],
                "confidence": conf_res.model_dump(),
                "freshness": freshness,
                "history_type": history_type_val,
                "source_coverage": source_coverage,
                "follow_up_suggestions": follow_up_suggestions,
                "limitations": merged_limitations,
                "status": response_status,
                "reason_codes": merged_reason_codes,
                **assistant_fields,
            }
        )

    def _assistant_contract_fields(
        self,
        resp: CoreIntelligenceAnswerResponse,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse | None,
    ) -> dict[str, Any]:
        """Build conversational metadata from the plan and executed facts/evidence."""
        degraded_reason = resp.degraded_reason or (plan.degraded_reason if plan else None)
        degraded = resp.degraded or bool(plan and plan.degraded)
        if resp.answer_origin != "gemini":
            provider_reason = getattr(self.llm_service, "last_error_class", None)
            if provider_reason and (
                resp.facts or provider_reason == "usage_ledger_unavailable"
            ):
                degraded = True
                degraded_reason = self._valid_degraded_reason(provider_reason)
        if degraded and not degraded_reason:
            degraded_reason = "unavailable"
        elif degraded_reason:
            degraded_reason = self._valid_degraded_reason(degraded_reason)

        sources: list[AssistantSource] = []
        seen: set[tuple[str, str, str]] = set()
        items: list[tuple[str, str, str]] = []
        for fact in resp.facts:
            items.append((fact.source, str(fact.details.get("source_type", "")), f"{fact.metric_name}: {fact.metric_value}"))
        for evidence in resp.evidence:
            items.append((evidence.source, evidence.signal_type, evidence.description))
        for label, type_hint, detail in items:
            hint = f"{label} {type_hint} {resp.intent} {request.message}".casefold()
            if "workforce" in hint or "company_intelligence" in hint:
                source_type = "workforce"
            elif any(token in hint for token in ("job_posting", "job posting", "jsearch", "adzuna", "vacancy")):
                source_type = "job_posting"
            elif any(token in hint for token in ("onet", "esco", "taxonomy", "occupation_reference")):
                source_type = "taxonomy"
            else:
                source_type = "market_signal"
            key = (source_type, label, detail)
            if not label or key in seen:
                continue
            seen.add(key)
            sources.append(AssistantSource(type=source_type, label=label, detail=detail[:500]))

        intent = plan.intent if plan else resp.intent
        entity = (plan.context_summary.get("primary_entity") if plan else None) or resp.resolved_entity
        understood = (plan.understood if plan and plan.understood else "") or (
            resp.understood
            or f"{intent.replace('_', ' ').capitalize()} for {entity or 'your intelligence question'}."
        )
        return {
            "understood": understood,
            "secondary_intents": list(plan.secondary_intents) if plan else list(resp.secondary_intents),
            "enough_data": bool(resp.facts) and resp.status in {"ready", "partial"},
            "sources": sources,
            "features_used": list(resp.capabilities_used),
            "degraded": degraded,
            "degraded_reason": degraded_reason,
        }

    @staticmethod
    def _job_follow_up_kind(message: str) -> str | None:
        normalized = message.casefold().strip()
        if re.search(r"\b(?:what skills|which skills)\b.*\b(?:these|those|the) jobs\b|\bskills do these jobs require\b", normalized):
            return "skills"
        if re.search(r"\b(?:show|give|list|open)\b.*\b(?:application )?links?\b|\bshow the links\b", normalized):
            return "links"
        if re.search(r"\b(?:only|just|show|which|filter)\b.*\bremote\b|\bremote only\b", normalized):
            return "remote"
        if re.search(r"\b(?:which|show|only|filter)\b.*\b(?:in|from|around)\s+[a-z][a-z .'-]{1,40}", normalized):
            return "city"
        return None

    @staticmethod
    def _looks_like_combined_question(message: str) -> bool:
        has_joiner = bool(re.search(r"\b(?:and|also|plus|as well as)\b", message, re.IGNORECASE))
        has_job_part = bool(re.search(r"\b(?:jobs?|postings?|vacancies)\b", message, re.IGNORECASE))
        has_other_part = bool(re.search(r"\b(?:skills?|trend|trends|market|adoption|role|occupation|company)\b", message, re.IGNORECASE))
        return has_joiner and has_job_part and has_other_part

    def _platform_help_response(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
        portal_type: str,
    ) -> CoreIntelligenceAnswerResponse:
        available: list[str] = []
        experimental: list[str] = []
        planned: list[str] = []
        for capability_id, record in CAPABILITY_CATALOG.items():
            name = str(getattr(record, "name", capability_id))
            status = str(getattr(record, "global_status", "unavailable"))
            has_handler = capability_id in HANDLER_METHODS and bool(getattr(record, "handler", None))
            if has_handler and status == "available":
                available.append(name)
            elif has_handler and status == "partial":
                experimental.append(name)
            else:
                planned.append(name)
        sections = [
            "**Platform help (from the registered capability and handler catalogs):**",
            "**Available:** " + (", ".join(sorted(available, key=str.casefold)) or "none recorded."),
            "**Experimental or partial:** " + (", ".join(sorted(experimental, key=str.casefold)) or "none recorded."),
            "**Planned or unavailable:** " + (", ".join(sorted(planned, key=str.casefold)) or "none recorded."),
            "Availability of data-backed answers still depends on each capability's evidence and readiness checks.",
        ]
        return CoreIntelligenceAnswerResponse(
            request_id=f"ans_{uuid.uuid4().hex[:12]}",
            user_message=request.message,
            portal_type=portal_type,
            domain=None,
            intent="platform_help",
            plan_status="ready_to_execute",
            execution_status="completed",
            status="ready",
            answer="\n\n".join(sections),
            answer_origin="deterministic",
            source_mode="platform_data",
            facts=[],
            evidence=[],
            limitations=["This catalog describes registered capabilities; it does not assert that data is currently available."],
            reason_codes=["REGISTRY_BACKED_PLATFORM_HELP"],
            follow_up_questions=[],
            conversation_id=request.conversation_id,
            client_message_id=request.client_message_id,
        )

    def _answer_saved_job_follow_up(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
        authenticated_user: AuthenticatedUser | None,
        portal_type: str,
        follow_up_kind: str,
    ) -> CoreIntelligenceAnswerResponse:
        user_id = authenticated_user.uid if authenticated_user else "anonymous"
        company_id = getattr(authenticated_user, "company_id", None) if authenticated_user else request.company_id
        state = self.conversation_store.get_conversation(
            request.conversation_id or "", user_id=user_id, company_id=company_id,
        )
        prior_turn = next(
            (turn for turn in reversed(state.turns) if turn.user_message != request.message),
            None,
        ) if state else None
        prior_payload = prior_turn.response_payload if prior_turn else None
        prior_facts = prior_payload.get("facts", []) if isinstance(prior_payload, dict) else []
        posting_fact = next(
            (fact for fact in prior_facts if isinstance(fact, dict) and fact.get("fact_type") == "stored_job_postings"),
            None,
        )
        saved_postings = (posting_fact or {}).get("details", {}).get("postings", [])
        request_id = f"ans_{uuid.uuid4().hex[:12]}"
        if not isinstance(saved_postings, list) or not saved_postings:
            response = CoreIntelligenceAnswerResponse(
                request_id=request_id, user_message=request.message, portal_type=portal_type,
                intent="search_jobs", plan_status="insufficient_data", execution_status="insufficient_data",
                status="insufficient_data",
                answer=("Saved job results are unavailable in this conversation, so I cannot safely apply that follow-up. "
                        "Please run a new stored-posting search first."),
                limitations=["No saved posting IDs and details were available; no new search was run."],
                reason_codes=["SAVED_JOB_RESULTS_MISSING"],
                conversation_id=request.conversation_id, client_message_id=request.client_message_id,
            )
            return response

        postings = [item for item in saved_postings if isinstance(item, dict) and item.get("posting_id")]
        missing_filter_evidence = 0
        filter_label = "saved matching postings"
        if follow_up_kind == "remote":
            selected = []
            for posting in postings:
                title = str(posting.get("title") or "").strip()
                location = str(posting.get("location") or "").strip()
                if not title and not location:
                    missing_filter_evidence += 1
                if re.search(r"\bremote\b", f"{title} {location}", re.IGNORECASE):
                    selected.append(posting)
            postings = selected
            filter_label = "postings with remote stated in the stored title or location"
        elif follow_up_kind == "city":
            from app.services.question_classification_service import LOCATION_ALIASES
            city_match = re.search(r"\b(?:in|from|around)\s+([a-z][a-z .'-]{1,40})", request.message, re.IGNORECASE)
            city = (city_match.group(1).strip(" .?!") if city_match else "")
            city = re.split(r"\b(?:only|with|that|and|which)\b", city, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            canonical_city = LOCATION_ALIASES.get(city.casefold(), city).casefold()
            selected = []
            for posting in postings:
                location = str(posting.get("location") or "").strip()
                if not location:
                    missing_filter_evidence += 1
                if canonical_city and canonical_city in location.casefold():
                    selected.append(posting)
            postings = selected
            filter_label = f"postings whose stored location contains {city or 'the requested city'}"

        evidence: list[EvidenceItem] = []
        for posting in postings:
            source = str(posting.get("source") or "stored_job_record")
            posting_id = str(posting["posting_id"])
            evidence.append(EvidenceItem(
                evidence_id=posting_id, source=source, signal_type="saved_stored_job_posting",
                data_origin=str((posting_fact or {}).get("data_origin") or "real"),
                provenance_id=posting_id, quality="valid",
                description=f"Saved posting {posting.get('title') or 'job'} at {posting.get('company') or 'company unavailable'}.",
                source_url=posting.get("source_url") if _valid_application_url(posting.get("source_url")) else None,
            ))

        title_lines = [
            f"- {item.get('title') or 'Title unavailable'} — {item.get('company') or 'Company unavailable'} — {item.get('location') or 'Location unavailable'}"
            for item in postings[:20]
        ]
        if follow_up_kind == "skills":
            counts: dict[str, int] = {}
            for posting in postings:
                extracted = extract_posting_skills({
                    "title": posting.get("title"),
                    "description": posting.get("summary") or "",
                    "skills_raw": posting.get("required_skills") or [],
                }, reference_store=self.reference_store)
                seen_skills: set[str] = set()
                for item in extracted:
                    name = str(item.get("normalized_name") or item.get("name") or "").strip()
                    key = name.casefold()
                    if name and key not in seen_skills:
                        counts[name] = counts.get(name, 0) + 1
                        seen_skills.add(key)
            n = len(postings)
            rows = []
            for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[:30]:
                suffix = f" ({count}/{n} postings)"
                if n >= 20:
                    suffix += f" — {count * 100 / n:.1f}%"
                rows.append(f"- {name}{suffix}")
            answer = (
                f"Skills extracted from the saved postings (n={n}):\n\n" + ("\n".join(rows) if rows else "No skills could be extracted from the saved descriptions and skill fields.")
            )
            if n < 20:
                answer += "\n\nPercentages are omitted because n is below 20."
        elif follow_up_kind == "links":
            links = []
            unavailable = 0
            for posting in postings:
                url = posting.get("source_url")
                if _valid_application_url(url):
                    links.append(f"- [{posting.get('title') or 'Application link'}]({url}) — {posting.get('company') or 'Company unavailable'}")
                else:
                    unavailable += 1
            answer = "Saved application links:\n\n" + ("\n".join(links) if links else "No valid application links were saved for these postings.")
            if unavailable:
                answer += f"\n\nApplication link unavailable for {unavailable} saved posting(s)."
        else:
            answer = f"Found **{len(postings)}** {filter_label} from the previous saved results."
            if title_lines:
                answer += "\n\n" + "\n".join(title_lines)
        if missing_filter_evidence:
            answer += f"\n\n{missing_filter_evidence} saved posting(s) were excluded because the title/location evidence needed for this filter was missing."

        saved_fact = StructuredFact(
            fact_id=f"fact_saved_jobs_{len(postings)}_{hashlib.sha256(request.message.casefold().encode()).hexdigest()[:8]}",
            fact_type="stored_job_postings", entity_name=None, canonical_entity_id=None,
            entity_type=None, metric_name="saved_postings_after_follow_up", metric_value=len(postings),
            denominator=len(postings), unit="postings", source="saved_conversation_response_payload",
            data_origin=str((posting_fact or {}).get("data_origin") or "real"),
            quality_state="valid", readiness_state="ready",
            details={"postings": postings, "follow_up_kind": follow_up_kind, "saved_from_turn_id": prior_turn.turn_id if prior_turn else None},
        )
        response = CoreIntelligenceAnswerResponse(
            request_id=request_id, user_message=request.message, portal_type=portal_type,
            intent="search_jobs", plan_status="ready_to_execute", execution_status="completed",
            status="ready", answer=answer, facts=[saved_fact], evidence=evidence,
            capabilities_used=["job_posting_search"], limitations=["This follow-up uses only the previous turn's saved posting IDs and details; no new search was run."],
            reason_codes=["SAVED_JOB_RESULTS_REUSED"],
            conversation_id=request.conversation_id, client_message_id=request.client_message_id,
        )
        return response

    @staticmethod
    def _valid_degraded_reason(reason: str) -> str:
        if reason in {
            "rate_limited",
            "provider_error",
            "unavailable",
            "usage_ledger_unavailable",
        }:
            return reason
        return "provider_error"

    @staticmethod
    def _append_demand_sample_note(
        answer_text: str,
        facts: Sequence[StructuredFact],
        plan: IntelligencePlanResponse,
    ) -> str:
        if plan.intent not in {"search_jobs", "analyze_trend", "rank_skill_trends", "retrieve_snapshot", "analyze_skill_gap"}:
            return answer_text
        job_fact = next((fact for fact in facts if fact.fact_type == "stored_job_postings"), None)
        if job_fact is not None:
            sample_size = int(job_fact.metric_value or 0)
            exclusions = job_fact.details
            note = f"Sample size (n): **{sample_size}** recent matching postings."
            note += (
                f" Excluded as older than 90 days: **{int(exclusions.get('excluded_older_than_90_days', 0))}**; "
                f"date unknown: **{int(exclusions.get('date_unknown_excluded', 0))}**."
            )
            if sample_size < 20:
                note += " Percentages are suppressed because n is below 20."
            return f"{answer_text}\n\n{note}"

        sample_sizes = plan.context_summary.get("_demand_sample_sizes") or []
        if not sample_sizes:
            return answer_text
        display = ", ".join(
            f"{item['period']} {item['source']} n={item['n']}"
            for item in sample_sizes if isinstance(item, dict)
        )
        exclusions = plan.context_summary.get("_demand_exclusions") or {}
        note = f"Sample size (n) by period: {display}."
        note += (
            f" Excluded as older than 90 days: **{int(exclusions.get('older_than_90_days', 0))}**; "
            f"date unknown: **{int(exclusions.get('date_unknown', 0))}**; "
            f"duplicate observation rows ignored: **{int(exclusions.get('duplicate_observations', 0))}**."
        )
        if any(int(item.get("n", 0)) < 20 for item in sample_sizes if isinstance(item, dict)):
            note += " Percentages are suppressed for periods with n below 20."
        return f"{answer_text}\n\n{note}"

    def apply_assistant_response_contract(
        self,
        resp: CoreIntelligenceAnswerResponse,
        request: CoreIntelligenceAnswerRequest,
    ) -> CoreIntelligenceAnswerResponse:
        """Ensure every answer path returns the additive assistant fields."""
        return resp.model_copy(update=self._assistant_contract_fields(resp, request, None))

    def _record_conversation_turn(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse | None,
        resp: CoreIntelligenceAnswerResponse,
        authenticated_user: AuthenticatedUser | None,
        portal_type: str,
    ) -> None:
        for field_name, field_value in self._assistant_contract_fields(resp, request, plan).items():
            setattr(resp, field_name, field_value)
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
            effective_domain = resp.domain or request.domain or (request.filters.get("domain") if request.filters else None) or "skill"
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
                session_state=request._session_state_update,
                regenerate_existing=request.regenerate,
            )
            if request.client_message_id:
                _IDEMPOTENT_ANSWER_CACHE[_answer_idempotency_key(
                    user_id, request.conversation_id, request.client_message_id, request.message
                )] = resp
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

        if (
            request.portal_type != "company"
            or getattr(authenticated_user, "role", None) != "company_admin"
        ):
            return (
                "UNAUTHORIZED_COMPANY_WORKFORCE_ROLE",
                "Company-wide workforce analytics require the authenticated company owner/admin portal.",
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
                        "mapping_disclosure": ce.metadata.get("mapping_disclosure"),
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

    def _handle_github_adoption(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        """Describe local GitHub Innovation Graph series at their native quarter grain."""
        entity = next((
            item.canonical_entity for item in plan.entities
            if item.canonical_entity and item.is_primary
        ), None)
        skill_name = entity.canonical_name if entity else plan.context_summary.get("primary_entity")
        if not skill_name:
            return [], [], ["A recognized skill or technology is required to select a GitHub series."]

        country = str((request.filters or {}).get("country") or "").strip().upper() or None
        requested_geography = request.location
        if not requested_geography:
            location_match = re.search(r"\b(?:in|within)\s+([A-Za-z][A-Za-z .'-]*?)\s*[?.!]*$", request.message, re.IGNORECASE)
            requested_geography = location_match.group(1).strip() if location_match else None
        if not country and requested_geography:
            country_codes = {
                "india": "IN", "in": "IN", "united states": "US", "usa": "US", "us": "US",
                "united kingdom": "GB", "uk": "GB", "great britain": "GB", "gb": "GB",
                "canada": "CA", "ca": "CA", "australia": "AU", "au": "AU",
                "germany": "DE", "de": "DE", "france": "FR", "fr": "FR",
                "brazil": "BR", "br": "BR",
            }
            country = country_codes.get(requested_geography.casefold())
        candidates = [skill_name]
        if entity and entity.entity_type in {"skill", "technology"}:
            candidates.extend(entity.aliases)
        rows: list[dict[str, Any]] = []
        for candidate in dict.fromkeys(item for item in candidates if item):
            rows = self.reference_store.get_github_adoption_series(
                language=candidate, iso2_code=country
            )
            if not rows:
                rows = self.reference_store.get_github_adoption_series(
                    language=candidate.title(), iso2_code=country
                )
            if not rows:
                rows = self.reference_store.get_github_adoption_series(
                    topic=candidate.casefold(), iso2_code=country
                )
            if rows:
                break

        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations = [
            "GitHub Innovation Graph is developer activity, not hiring demand or job-posting volume.",
            "Quarterly raw developer counts are not converted to monthly data and do not qualify for monthly Skill Health, forecast, or half-life gates.",
        ]
        if not rows:
            evidence_id = "ev_github_adoption_series_unavailable"
            facts.append(StructuredFact(
                fact_id="fact_github_adoption_series_unavailable",
                fact_type="analysis_readiness",
                entity_name=skill_name,
                metric_name="github_adoption_readiness",
                metric_value="insufficient_data",
                unit="status",
                source="ref_github_language_adoption+ref_github_topic_adoption",
                data_origin="unavailable",
                history_type="reference_dataset",
                readiness_state="insufficient_data",
                evidence_reference=evidence_id,
                details={"reason": f"No local GitHub Innovation Graph series matched {skill_name} for the requested geography."},
            ))
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source="local_github_innovation_graph",
                signal_type="evidence_readiness",
                data_origin="unavailable",
                quality="unavailable",
                description=f"No local quarterly developer-activity series matched {skill_name}.",
            ))
            return facts, evidence, limitations

        available_geographies = sorted({str(row.get("iso2_code") or "unknown") for row in rows})
        if not country and len(available_geographies) > 1:
            evidence_id = "ev_github_adoption_geography_required"
            reason = (
                "The local GitHub series contains separate country-level observations. "
                "Choose a country so unlike geographic populations are not pooled."
            )
            facts.append(StructuredFact(
                fact_id="fact_github_adoption_geography_required",
                fact_type="analysis_readiness",
                entity_name=skill_name,
                canonical_entity_id=entity.entity_id if entity else None,
                entity_type="skill" if entity else "technology",
                metric_name="github_adoption_geography_readiness",
                metric_value="geography_required",
                unit="status",
                source="ref_github_language_adoption+ref_github_topic_adoption",
                data_origin="local_reference_dataset",
                history_type="reference_dataset",
                readiness_state="requires_clarification",
                evidence_reference=evidence_id,
                details={"reason": reason, "available_country_count": len(available_geographies), "available_country_codes_sample": available_geographies[:20]},
            ))
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source="local_github_innovation_graph",
                signal_type="geography_readiness",
                data_origin="local_reference_dataset",
                history_type="reference_dataset",
                quality="valid",
                description=reason,
            ))
            return facts, evidence, [*limitations, reason]

        # Language and topic metrics, and each geography, remain separate series.
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            table = "language" if row.get("language") else "topic"
            label = str(row.get("language") or row.get("topic") or skill_name)
            grouped.setdefault((table, str(row.get("iso2_code") or "unknown")), []).append(row)

        for (kind, geo), series in grouped.items():
            series.sort(key=lambda row: str(row.get("period") or ""))
            label = str(series[-1].get("language") or series[-1].get("topic") or skill_name)
            points = [
                row for row in series
                if isinstance(row.get("num_pushers"), (int, float)) and row.get("period")
            ]
            if not points:
                continue
            latest = points[-1]
            latest_period = str(latest["period"])
            series_id = f"github_innovation_graph:{kind}:{geo}:{label.casefold()}"
            snapshot_id = f"ev_{series_id}_{latest_period}"
            facts.append(StructuredFact(
                fact_id=f"fact_{series_id}_{latest_period}",
                fact_type="developer_activity_snapshot",
                entity_name=label,
                canonical_entity_id=entity.entity_id if entity else None,
                entity_type="skill" if entity else "technology",
                metric_name="github_unique_developers",
                metric_value=int(latest["num_pushers"]),
                unit="unique developers per quarter",
                period=latest_period,
                source=f"ref_github_{kind}_adoption",
                data_origin="local_reference_dataset",
                history_type="backfill",
                series_id=series_id,
                quality_state="valid",
                readiness_state="observed",
                provenance_id=str(latest.get("id") or series_id),
                evidence_reference=snapshot_id,
                details={"time_grain": "quarter", "iso2_code": geo, "series_kind": kind},
            ))
            evidence.append(EvidenceItem(
                evidence_id=snapshot_id,
                source=f"ref_github_{kind}_adoption",
                signal_type="adoption",
                period=latest_period,
                unit="unique developers per quarter",
                data_origin="local_reference_dataset",
                history_type="backfill",
                series_id=series_id,
                provenance_id=str(latest.get("id") or series_id),
                quality="valid",
                description=f"GitHub Innovation Graph {kind} activity for {label}: {latest['num_pushers']} unique developers in {latest_period} ({geo}).",
            ))

            def quarter_index(period: str) -> int | None:
                match = re.fullmatch(r"(\d{4})-Q([1-4])", period)
                return int(match.group(1)) * 4 + int(match.group(2)) - 1 if match else None

            if len(points) >= 2:
                previous = points[-2]
                prev_idx = quarter_index(str(previous.get("period") or ""))
                curr_idx = quarter_index(latest_period)
                if prev_idx is not None and curr_idx == prev_idx + 1:
                    difference = int(latest["num_pushers"]) - int(previous["num_pushers"])
                    change_id = f"ev_{series_id}_change_{previous['period']}_{latest_period}"
                    facts.append(StructuredFact(
                        fact_id=f"fact_{series_id}_change_{latest_period}",
                        fact_type="developer_activity_change",
                        entity_name=label,
                        canonical_entity_id=entity.entity_id if entity else None,
                        entity_type="skill" if entity else "technology",
                        metric_name="quarter_over_quarter_change",
                        metric_value=difference,
                        unit="unique developers",
                        period=f"{previous['period']}_to_{latest_period}",
                        source=f"ref_github_{kind}_adoption",
                        data_origin="local_reference_dataset",
                        history_type="backfill",
                        series_id=series_id,
                        quality_state="valid",
                        provenance_id=str(latest.get("id") or series_id),
                        evidence_reference=change_id,
                        details={"previous_value": int(previous["num_pushers"]), "latest_value": int(latest["num_pushers"]), "iso2_code": geo, "time_grain": "quarter"},
                    ))
                    evidence.append(EvidenceItem(
                        evidence_id=change_id,
                        source=f"ref_github_{kind}_adoption",
                        signal_type="adoption_change",
                        period=f"{previous['period']}_to_{latest_period}",
                        unit="unique developers",
                        data_origin="local_reference_dataset",
                        history_type="backfill",
                        series_id=series_id,
                        quality="valid",
                        description=f"Quarter-over-quarter change computed from {int(previous['num_pushers'])} in {previous['period']} and {int(latest['num_pushers'])} in {latest_period}.",
                    ))

            contiguous = [points[-1]]
            for row in reversed(points[:-1]):
                if quarter_index(str(contiguous[0].get("period") or "")) is None or quarter_index(str(row.get("period") or "")) != quarter_index(str(contiguous[0]["period"])) - 1:
                    break
                contiguous.insert(0, row)
            if len(contiguous) >= 4:
                first_value = int(contiguous[0]["num_pushers"])
                last_value = int(contiguous[-1]["num_pushers"])
                direction = "increased" if last_value > first_value else "decreased" if last_value < first_value else "was unchanged"
                from app.services.answer_verdict_rules import classify_adoption_growth
                adoption_verdict = classify_adoption_growth(
                    [int(row["num_pushers"]) for row in contiguous]
                )
                trend_id = f"ev_{series_id}_trend_{contiguous[0]['period']}_{latest_period}"
                facts.append(StructuredFact(
                    fact_id=f"fact_{series_id}_trend_{latest_period}",
                    fact_type="developer_activity_trend",
                    entity_name=label,
                    canonical_entity_id=entity.entity_id if entity else None,
                    entity_type="skill" if entity else "technology",
                    metric_name="quarterly_descriptive_change",
                    metric_value=direction,
                    unit="unique developers",
                    period=f"{contiguous[0]['period']}_to_{latest_period}",
                    source=f"ref_github_{kind}_adoption",
                    data_origin="local_reference_dataset",
                    history_type="backfill",
                    series_id=series_id,
                    quality_state="valid",
                    provenance_id=series_id,
                    evidence_reference=trend_id,
                    details={"first_value": first_value, "latest_value": last_value, "periods": [str(row["period"]) for row in contiguous], "iso2_code": geo, "time_grain": "quarter", "signal_type": "adoption", "adoption_label": adoption_verdict["level"], "adoption_growth": adoption_verdict["growth"], "adoption_direction": adoption_verdict["direction"]},
                ))
                evidence.append(EvidenceItem(
                    evidence_id=trend_id,
                    source=f"ref_github_{kind}_adoption",
                    signal_type="adoption_trend",
                    period=f"{contiguous[0]['period']}_to_{latest_period}",
                    unit="unique developers per quarter",
                    data_origin="local_reference_dataset",
                    history_type="backfill",
                    series_id=series_id,
                    quality="valid",
                    description=f"Descriptive comparison of {len(contiguous)} consecutive quarterly observations; {first_value} to {last_value} unique developers.",
                ))

        return facts, evidence, limitations

    def _handle_skill_technology_reference(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        if getattr(plan, "intent", None) == "lookup_github_adoption":
            return self._handle_github_adoption(request, plan)
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        is_reference_lookup = getattr(plan, "intent", None) in {
            "lookup_skill_reference", "explain_concept",
        }
        limitations: list[str] = [] if is_reference_lookup else [
            "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
        ]

        # Gather distinct entities from plan
        entities_to_lookup: list[tuple[str, Any]] = []
        if plan.entities:
            candidate_entities = plan.entities
            if is_reference_lookup:
                # Intent planning also carries profile skills as secondary
                # context. A taxonomy answer is scoped to the explicit primary
                # entity, never every skill present in the user's profile.
                candidate_entities = [
                    item for item in plan.entities
                    if getattr(item, "is_primary", False) and item.canonical_entity
                ][:1]
                if not candidate_entities and len(plan.entities) == 1:
                    candidate_entities = [plan.entities[0]]
            for item in candidate_entities:
                if item.canonical_entity:
                    if not any(e[0] == item.canonical_entity.canonical_name for e in entities_to_lookup):
                        entities_to_lookup.append((item.canonical_entity.canonical_name, item.canonical_entity))

        if not entities_to_lookup:
            fallback_token = plan.context_summary.get("primary_entity") or request.message.strip()
            # Attempt to resolve fallback token
            resolved = self.entity_service.resolve(EntityResolutionRequest(name=fallback_token))
            ent = resolved.entity if resolved.status == "resolved" else None
            entities_to_lookup.append((fallback_token, ent))

        # Skill Reference also exposes actual ESCO occupation-to-skill taxonomy
        # links when the selected feature and question explicitly request them.
        occupation_entity = next((
            entity for _name, entity in entities_to_lookup
            if entity and entity.entity_type == "occupation"
            and entity.source == "ref_esco_occupations"
        ), None)
        if is_reference_lookup and occupation_entity and re.search(
            r"\b(?:skills?\s+(?:(?:are|is)\s+)?(?:associated|linked|related)|occupation\s+skills?)\b",
            request.message,
            re.IGNORECASE,
        ):
            occupation_uri = occupation_entity.source_record_id
            occupation_label = occupation_entity.canonical_name
            occupation_rows = self.reference_store.get_esco_occupations(
                concept_uri=occupation_uri, limit=1
            )
            if occupation_rows:
                occupation_label = occupation_rows[0]["preferred_label"]
            relation_type = (
                "essential" if re.search(r"\bessential\b", request.message, re.IGNORECASE)
                else "optional" if re.search(r"\boptional\b", request.message, re.IGNORECASE)
                else None
            )
            relations = self.reference_store.get_esco_occupation_skills(
                occupation_uri, limit=10, relation_type=relation_type
            )
            evidence_id = f"ev_esco_links_{hashlib.sha256(occupation_uri.encode()).hexdigest()[:16]}"
            for row in relations:
                skill_uri = row["skill_uri"]
                facts.append(StructuredFact(
                    fact_id=f"fact_esco_link_{hashlib.sha256((occupation_uri + skill_uri + row['relation_type']).encode()).hexdigest()[:20]}",
                    fact_type="occupation_skill_association",
                    entity_name=row["preferred_label"] or row["relation_skill_label"],
                    canonical_entity_id=f"skill:esco:{skill_uri}",
                    entity_type="skill",
                    metric_name="relation_type",
                    metric_value=row["relation_type"],
                    source="ref_esco_occupation_skill_relations",
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    provenance_id=f"{occupation_uri}|{skill_uri}|{row['relation_type']}",
                    evidence_reference=evidence_id,
                    details={
                        "occupation_title": occupation_label,
                        "occupation_uri": occupation_uri,
                        "skill_uri": skill_uri,
                        "skill_type": row["skill_type"],
                        "source_version": row["source_version"],
                    },
                ))
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source="ref_esco_occupation_skill_relations",
                signal_type="taxonomy_association",
                quality="valid" if relations else "unavailable",
                description=f"ESCO occupation-skill taxonomy associations for {occupation_label}: {len(relations)} relationships retrieved.",
            ))
            limitations.extend([
                "ESCO essential/optional associations are taxonomy mappings, not proof that a person has a skill or is qualified for the occupation.",
                "ESCO taxonomy associations are not live employer hiring demand.",
            ])
            return facts, evidence, limitations

        for token, primary_ent in entities_to_lookup:
            # GitHub observations belong to adoption/activity questions. A
            # canonical taxonomy lookup must not append them to its evidence.
            topic_token = token.lower() if token else ""
            topics = []
            languages = []
            if not is_reference_lookup:
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
            # Historical developer series are not reference taxonomy fields.
            if is_reference_lookup:
                skill_id = None
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
                    metric_value=primary_ent.category,
                    source=primary_ent.source,
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="valid",
                    provenance_id=primary_ent.source_record_id,
                    evidence_reference=ev_ent_id,
                    details={
                        "aliases": list(primary_ent.aliases),
                        **(
                            {
                                "esco_uri": primary_ent.source_record_id,
                                "taxonomy": "ESCO",
                                "source_version": primary_ent.metadata.get("source_version"),
                                "description": primary_ent.metadata.get("description"),
                            }
                            if primary_ent.source == "ref_esco_skills" else {}
                        ),
                        **(
                            {"definition": primary_ent.metadata.get("definition")}
                            if primary_ent.metadata.get("definition") else {}
                        ),
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_ent_id,
                    source=primary_ent.source or "entity_registry",
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    provenance_id=primary_ent.source_record_id,
                    description=(
                        f"ESCO {primary_ent.metadata.get('source_version')} skill taxonomy entry: {primary_ent.canonical_name}."
                        if primary_ent.source == "ref_esco_skills"
                        else f"Canonical entity registry record: {primary_ent.canonical_name} ({primary_ent.entity_type})."
                    ),
                ))
            elif is_reference_lookup:
                unavailable_evidence_id = f"ev_ref_unavailable_{canonical_skill_id(token) or 'entity'}"
                facts.append(StructuredFact(
                    fact_id=f"fact_ref_unavailable_{canonical_skill_id(token) or 'entity'}",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    entity_type="skill",
                    metric_name="canonical_reference_readiness",
                    metric_value="unavailable",
                    unit="status",
                    source="reference_taxonomy",
                    data_origin="real",
                    history_type="reference_taxonomy",
                    quality_state="unavailable",
                    readiness_state="unavailable",
                    evidence_reference=unavailable_evidence_id,
                    details={
                        "reason": "No canonical reference record was found; definition and category are unavailable.",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=unavailable_evidence_id,
                    source="reference_taxonomy",
                    signal_type="taxonomy_lookup",
                    quality="unavailable",
                    description="No canonical reference record was found; definition and category are unavailable.",
                ))
            elif not topics and not languages:
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
        esco_uri = None
        requested_title = request.target_role or ""
        closest_match = False
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                esco_uri = ent.canonical_entity.metadata.get("esco_uri")
                if not esco_uri and ent.canonical_entity.source == "ref_esco_occupations":
                    esco_uri = ent.canonical_entity.source_record_id
                target_soc = ent.canonical_entity.metadata.get("soc_code") or (None if esco_uri else ent.canonical_entity.source_record_id)
                break

        if esco_uri:
            occupation = self.reference_store.get_esco_occupations(concept_uri=esco_uri, limit=1)
            if occupation:
                row = occupation[0]
                evidence_id = f"ev_esco_occ_{hashlib.sha256(esco_uri.encode()).hexdigest()[:16]}"
                facts.append(StructuredFact(
                    fact_id=f"fact_esco_occ_{hashlib.sha256(esco_uri.encode()).hexdigest()[:16]}",
                    fact_type="occupation", entity_name=row["preferred_label"],
                    canonical_entity_id=f"occupation:esco:{esco_uri}", entity_type="occupation",
                    metric_name="esco_concept_uri", metric_value=esco_uri,
                    source="ref_esco_occupations", data_origin="real", history_type="reference_taxonomy",
                    quality_state="valid", provenance_id=esco_uri, evidence_reference=evidence_id,
                    details={"description": row["description"], "taxonomy": "ESCO", "source_version": row["source_version"], "isco_group": row["isco_group"]},
                ))
                evidence.append(EvidenceItem(evidence_id=evidence_id, source="ref_esco_occupations", signal_type="taxonomy_lookup", quality="valid", description=f"ESCO {row['source_version']} occupation taxonomy entry: {row['preferred_label']}."))
            return facts, evidence, ["ESCO is a static occupational reference taxonomy, not real-time hiring demand."]

        if not target_soc and request.target_role:
            from app.services.role_alias_service import normalize_role_alias, role_alias_soc_code
            requested_title = request.target_role
            alias_code = role_alias_soc_code(requested_title)
            if alias_code:
                alias_rows = self.reference_store.get_onet_occupations(code=alias_code)
                if alias_rows:
                    target_soc = alias_rows[0].soc_code
            if not target_soc:
                occs = self.reference_store.get_onet_occupations(title=requested_title, limit=100)
                exact = [row for row in occs if normalize_role_alias(row.title) == normalize_role_alias(requested_title)]
                if exact:
                    target_soc = exact[0].soc_code
                elif occs:
                    from difflib import SequenceMatcher
                    ranked = sorted(
                        occs,
                        key=lambda row: SequenceMatcher(
                            None, normalize_role_alias(requested_title), normalize_role_alias(row.title),
                        ).ratio(),
                        reverse=True,
                    )
                    best = ranked[0]
                    score = SequenceMatcher(None, normalize_role_alias(requested_title), normalize_role_alias(best.title)).ratio()
                    if score >= 0.45:
                        target_soc = best.soc_code
                        closest_match = True

        if not target_soc and request.target_role:
            from app.services.role_alias_service import normalize_role_alias
            from difflib import SequenceMatcher
            local_occupations = self.reference_store.get_onet_occupations(limit=1000)
            if local_occupations:
                local_occupations = [
                    row for row in local_occupations
                    if row.soc_code not in {"11-1011.03", "11-1011.00"} and "Sustainability" not in (row.title or "")
                ]
                ranked = sorted(
                    local_occupations,
                    key=lambda row: SequenceMatcher(
                        None, normalize_role_alias(request.target_role), normalize_role_alias(row.title),
                    ).ratio(),
                    reverse=True,
                )
                if ranked:
                    best = ranked[0]
                    similarity = SequenceMatcher(
                        None, normalize_role_alias(request.target_role), normalize_role_alias(best.title),
                    ).ratio()
                    if similarity >= 0.35 and best.soc_code not in {"11-1011.03", "11-1011.00"}:
                        target_soc = best.soc_code
                        closest_match = normalize_role_alias(best.title) != normalize_role_alias(request.target_role)

        if target_soc in {"11-1011.03", "11-1011.00"}:
            target_soc = None

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
                    details={
                        "description": occ.description,
                        "requested_title": requested_title,
                        "closest_match": closest_match,
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source="ref_onet_occupations",
                    signal_type="taxonomy_lookup",
                    quality="valid",
                    description=f"O*NET 2018 SOC Occupation: {occ.title} (SOC {occ.soc_code}).",
                ))
        else:
            facts.append(StructuredFact(
                fact_id=f"fact_occupation_unresolved_{hashlib.sha256((requested_title or request.message).casefold().encode()).hexdigest()[:12]}",
                fact_type="occupation_lookup_readiness", entity_name=requested_title or None,
                canonical_entity_id=None, entity_type="occupation", metric_name="local_occupation_match",
                metric_value="not_found", source="ref_onet_occupations", data_origin="unavailable",
                history_type="reference_taxonomy", quality_state="insufficient_data",
                readiness_state="insufficient_data",
                details={"requested_title": requested_title, "reason": "No sufficiently similar local occupation record was found."},
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
        esco_uri = None
        for ent in plan.entities:
            if ent.canonical_entity and ent.canonical_entity.entity_type == "occupation":
                esco_uri = ent.canonical_entity.metadata.get("esco_uri")
                if not esco_uri and ent.canonical_entity.source == "ref_esco_occupations":
                    esco_uri = ent.canonical_entity.source_record_id
                target_soc = ent.canonical_entity.metadata.get("soc_code") or (None if esco_uri else ent.canonical_entity.source_record_id)
                target_title = ent.canonical_entity.canonical_name
                break

        if esco_uri:
            occupation = self.reference_store.get_esco_occupations(concept_uri=esco_uri, limit=1)
            target_title = occupation[0]["preferred_label"] if occupation else target_title
            requested_relation = (
                "essential" if re.search(r"\bessential\b", request.message, re.IGNORECASE)
                else "optional" if re.search(r"\boptional\b", request.message, re.IGNORECASE)
                else None
            )
            rows = self.reference_store.get_esco_occupation_skills(
                esco_uri, limit=10, relation_type=requested_relation
            )
            evidence_id = f"ev_esco_links_{hashlib.sha256(esco_uri.encode()).hexdigest()[:16]}"
            for row in rows:
                uri = row["skill_uri"]
                facts.append(StructuredFact(
                    fact_id=f"fact_esco_link_{hashlib.sha256((esco_uri + uri + row['relation_type']).encode()).hexdigest()[:20]}",
                    fact_type="occupation_skill_association", entity_name=row["preferred_label"] or row["relation_skill_label"],
                    canonical_entity_id=f"skill:esco:{uri}", entity_type="skill",
                    metric_name="relation_type", metric_value=row["relation_type"],
                    source="ref_esco_occupation_skill_relations", data_origin="real", history_type="reference_taxonomy",
                    quality_state="valid", provenance_id=f"{esco_uri}|{uri}|{row['relation_type']}", evidence_reference=evidence_id,
                    details={"occupation_title": target_title, "occupation_uri": esco_uri, "skill_uri": uri, "skill_type": row["skill_type"], "source_version": row["source_version"]},
                ))
            evidence.append(EvidenceItem(evidence_id=evidence_id, source="ref_esco_occupation_skill_relations", signal_type="taxonomy_association", quality="valid", description=f"ESCO occupation-skill taxonomy associations for {target_title}: {len(rows)} relationships retrieved."))
            return facts, evidence, ["ESCO essential/optional associations are taxonomy mappings, not proof that a person has a skill or is qualified for the occupation.", "ESCO taxonomy associations are not live employer hiring demand."]

        if not target_soc and request.target_role:
            occs = self.reference_store.get_onet_occupations(title=request.target_role)
            occs = [row for row in occs if row.soc_code not in {"11-1011.03", "11-1011.00"} and "Sustainability" not in (row.title or "")]
            if occs:
                target_soc = occs[0].soc_code
                target_title = occs[0].title

        if not target_soc or target_soc in {"11-1011.03", "11-1011.00"}:
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
            occs = [row for row in occs if row.soc_code not in {"11-1011.03", "11-1011.00"} and "Sustainability" not in (row.title or "")]
            if occs:
                target_soc = occs[0].soc_code

        if not target_soc or target_soc in {"11-1011.03", "11-1011.00"}:
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
        requested_signal = (request.filters or {}).get("signal_type")
        hiring_question = bool(re.search(
            r"\b(?:hiring|job postings?|vacancies|employment demand|employer demand)\b",
            request.message,
            re.IGNORECASE,
        ))
        if isinstance(requested_signal, str):
            obs = [observation for observation in obs if observation.signal_type == requested_signal]
        elif hiring_question:
            # A hiring question can only be answered from sampled posting-demand
            # observations. Community, pageview, adoption and taxonomy records
            # must not qualify as employer hiring evidence.
            obs = [
                observation for observation in obs
                if observation.signal_type == "demand"
                and observation.source.casefold() in {
                    "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
                }
            ]

        if obs:
            from app.analytics.freshness import assess_freshness
            from app.analytics.observation_period import is_completed_month

            # Keep unlike source series separate. A snapshot summarizes the
            # records found for each identity; it does not calculate a trend.
            groups: dict[tuple[Any, ...], list[MarketObservation]] = {}
            for observation in obs:
                identity = (
                    observation.source, observation.signal_type, observation.unit,
                    observation.denominator_unit, observation.scope, observation.location,
                    observation.series_id, observation.query_id, observation.panel_version,
                    observation.skill_id,
                )
                groups.setdefault(identity, []).append(observation)

            for series_obs in groups.values():
                ordered = sorted(series_obs, key=lambda item: (item.period or "", item.observed_at))
                latest_obs = ordered[-1]
                periods = sorted({item.period for item in ordered if item.period})
                completed_periods = [period for period in periods if is_completed_month(period)]
                freshness = assess_freshness(series_obs)
                completeness_flags = [
                    item.quality.get("collection_complete")
                    for item in ordered
                    if isinstance(item.quality, dict)
                    and isinstance(item.quality.get("collection_complete"), bool)
                ]
                if any(flag is False for flag in completeness_flags):
                    completeness = "partial"
                    quality_state = "partial"
                elif completeness_flags and all(completeness_flags):
                    completeness = "complete"
                    quality_state = "valid"
                else:
                    completeness = "unknown"
                    quality_state = (
                        latest_obs.quality
                        if isinstance(latest_obs.quality, str) and latest_obs.quality
                        else "unknown"
                    )
                if completeness == "partial":
                    limitations.append(
                        f"The {latest_obs.source} {latest_obs.signal_type} series has partial collection coverage; "
                        "its observed sample is not a complete provider result set."
                    )
                observation_ids = [item.id for item in ordered if item.id]
                fetch_run_ids = sorted({item.fetch_run_id for item in ordered if item.fetch_run_id})
                details = {
                    "signal_type": latest_obs.signal_type,
                    "metric_name": "observed_metric_value",
                    "unit": latest_obs.unit,
                    "denominator_unit": latest_obs.denominator_unit,
                    "location": latest_obs.location,
                    "scope": latest_obs.scope,
                    "source": latest_obs.source,
                    "observation_count": len(ordered),
                    "period_frequency": "monthly" if periods and all(re.fullmatch(r"\d{4}-\d{2}", p) for p in periods) else "unspecified",
                    "time_coverage_start": periods[0] if periods else None,
                    "time_coverage_end": periods[-1] if periods else None,
                    "latest_completed_period": completed_periods[-1] if completed_periods else None,
                    "current_period_included": bool(periods and not is_completed_month(periods[-1])),
                    "data_origins": sorted({item.data_origin or "unavailable" for item in ordered}),
                    "history_types": sorted({item.history_type or "unavailable" for item in ordered}),
                    "collection_completeness": completeness,
                    "freshness": {
                        "state": freshness.state,
                        "fresh_count": freshness.fresh_count,
                        "stale_count": freshness.stale_count,
                        "unknown_count": freshness.unknown_count,
                        "excluded_count": freshness.excluded_count,
                    },
                    "collection_status": completeness,
                    "fetch_run_ids_available": bool(fetch_run_ids),
                    "fetch_run_ids": fetch_run_ids,
                    "sample_is_not_market_universe": True,
                }
                facts.append(StructuredFact(
                    fact_id=f"fact_snap_{latest_obs.id or latest_obs.series_id or latest_obs.source}",
                    fact_type="market_snapshot", entity_name=latest_obs.skill,
                    canonical_entity_id=latest_obs.skill_id, entity_type="skill",
                    metric_name="observed_metric_value", metric_value=latest_obs.value,
                    unit=latest_obs.unit, denominator=latest_obs.denominator,
                    period=latest_obs.period, timestamp=latest_obs.observed_at,
                    source=latest_obs.source, data_origin=latest_obs.data_origin or "unavailable",
                    history_type=latest_obs.history_type, series_id=latest_obs.series_id,
                    quality_state=quality_state, provenance_id=latest_obs.id,
                    evidence_reference=latest_obs.id, details=details,
                ))
                evidence.append(EvidenceItem(
                    evidence_id=latest_obs.id or f"snapshot-{latest_obs.source}-{latest_obs.period}",
                    source=latest_obs.source, signal_type=latest_obs.signal_type,
                    measured_signal_type=latest_obs.signal_type, period=latest_obs.period,
                    unit=latest_obs.unit, data_origin=latest_obs.data_origin or "unavailable",
                    history_type=latest_obs.history_type, series_id=latest_obs.series_id,
                    location=latest_obs.location, scope=latest_obs.scope,
                    query_id=latest_obs.query_id, panel_version=latest_obs.panel_version,
                    fetch_run_id=latest_obs.fetch_run_id, supporting_fetch_run_ids=fetch_run_ids,
                    source_url=latest_obs.source_url, provenance_id=latest_obs.id,
                    supporting_observation_ids=observation_ids,
                    supporting_source_urls=sorted({item.source_url for item in ordered if item.source_url}),
                    freshness_state=freshness.state, quality=quality_state,
                    confidence=latest_obs.confidence,
                    description=(f"Observed {latest_obs.signal_type} for '{latest_obs.skill}' "
                                 f"({latest_obs.value} {latest_obs.unit or ''}) in {latest_obs.period}; "
                                 f"{len(ordered)} observation(s) in this source-specific series."),
                ))
        else:
            source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
            missing_reason = (
                "No JSearch or Adzuna sampled job-posting demand observations matched the requested skill, geography, and time filters. Other signal families are not hiring evidence."
                if hiring_question
                else "No persisted market observations matched the canonical skill, location, and time filters."
            )
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
                evidence_reference=None,
                details={
                    "reason": missing_reason,
                    "domain": "market",
                    "reference_data_is_not_market_evidence": True,
                },
            ))

        return facts, evidence, limitations

    def _handle_historical_signal_retrieval(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        from app.analytics.historical_signals import (
            historical_series_identity,
            missing_periods,
            observation_is_eligible_history,
            period_grain,
        )

        limitations: list[str] = [
            "Only verified empirical periods are returned; missing periods are not interpolated or replaced with zero.",
            "Each source, metric, unit, geography, query, panel, and series identity remains separate.",
        ]
        history_context = plan.context_summary.get("_historical_signal_context") or {}
        selected_source = history_context.get("source")
        selected_signal = history_context.get("signal_type")
        country = history_context.get("country")

        if selected_source in {"jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters"}:
            explanation = (
                f"{selected_source} records are stored job-posting snapshots, not a source-aggregated historical "
                "skill-demand series. Historical Skill Signals cannot use them as a time series."
            )
            facts.append(StructuredFact(
                fact_id="fact_historical_source_ineligible", fact_type="analysis_readiness",
                entity_name=plan.context_summary.get("primary_entity"), metric_name="historical_series_readiness",
                metric_value="unsupported_source", unit="status", source=selected_source,
                data_origin="unavailable", readiness_state="unsupported",
                details={"signal_type": "demand", "reason": explanation},
            ))
            evidence.append(EvidenceItem(
                evidence_id="ev_historical_source_ineligible", source=selected_source,
                signal_type="demand", data_origin="unavailable", quality="unavailable",
                description=explanation,
            ))
            return facts, evidence, limitations + [explanation]

        if selected_source == "github_innovation_graph":
            if not country:
                explanation = "GitHub Innovation Graph history is country-specific; select a country before retrieving its quarterly developer-activity series."
                facts.append(StructuredFact(
                    fact_id="fact_github_country_required", fact_type="analysis_readiness",
                    entity_name=history_context.get("skill_name"), metric_name="historical_series_readiness",
                    metric_value="requires_clarification", unit="status", source=selected_source,
                    data_origin="unavailable", readiness_state="requires_clarification",
                    details={"signal_type": "adoption", "reason": explanation},
                ))
                return facts, evidence, limitations + [explanation]
            from app.analytics.skill_registry import canonical_skill_id
            from app.storage.reference_store import ReferenceDataStore

            skill_name = history_context.get("skill_name") or plan.context_summary.get("primary_entity") or ""
            skill_id = canonical_skill_id(skill_name)
            reference_store = ReferenceDataStore(self.db_path, read_only=True)
            rows = reference_store.get_github_adoption_series_for_country(country)
            rows = [row for row in rows if skill_id and row.get("canonical_skill_id") == skill_id]
            current = datetime.now(timezone.utc)
            current_quarter = (current.month - 1) // 3 + 1
            rows = [row for row in rows if re.fullmatch(r"\d{4}-Q[1-4]", str(row.get("period") or ""))
                    and tuple(map(int, re.fullmatch(r"(\d{4})-Q([1-4])", str(row["period"])).groups())) < (current.year, current_quarter)
                    and row.get("value") is not None]
            grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
            for row in rows:
                key = (str(row.get("metric") or ""), str(row.get("label") or ""), str(row.get("unit") or ""))
                grouped.setdefault(key, []).append(row)
            for (metric, label, unit), series_rows in grouped.items():
                series_id = f"github_innovation_graph:{metric}:{skill_id}:{country}:{label.casefold()}"
                ordered_rows = sorted(series_rows, key=lambda item: item["period"])
                quarter_indexes = [
                    int(row["period"][:4]) * 4 + int(row["period"][-1]) - 1
                    for row in ordered_rows
                ]
                period_gaps = [
                    f"{value // 4:04d}-Q{value % 4 + 1}"
                    for start, end in zip(quarter_indexes, quarter_indexes[1:])
                    for value in range(start + 1, end)
                ]
                for row in ordered_rows:
                    period = row["period"]
                    evidence_id = f"ev_{series_id}_{period}"
                    facts.append(StructuredFact(
                        fact_id=f"fact_{series_id}_{period}", fact_type="historical_observation",
                        entity_name=label or skill_name, canonical_entity_id=skill_id, entity_type="skill",
                        metric_name=metric, metric_value=row["value"], unit=unit, period=period,
                        source="github_innovation_graph", data_origin="real", history_type="backfill",
                        series_id=series_id, quality_state="valid", provenance_id=evidence_id,
                        evidence_reference=evidence_id,
                        details={"signal_type": "adoption", "geography": country, "location": country,
                                 "scope": "country", "frequency": "quarterly", "label": label,
                                 "missing_periods": period_gaps,
                                 "source_dataset": "local GitHub Innovation Graph reference tables"},
                    ))
                    evidence.append(EvidenceItem(
                        evidence_id=evidence_id, source="github_innovation_graph",
                        signal_type="adoption", period=period, unit=unit, data_origin="real",
                        history_type="backfill", series_id=series_id, location=country, scope="country",
                        provenance_id=evidence_id,
                        description=f"Local GitHub Innovation Graph {metric} for {label} in {country}: {row['value']} {unit} during {period}; developer activity, not hiring demand.",
                    ))
            if not facts:
                explanation = f"No mapped GitHub Innovation Graph quarterly adoption history was found for {skill_name or 'the requested skill'} in {country} in the local reference data."
                facts.append(StructuredFact(
                    fact_id="fact_github_history_unavailable", fact_type="analysis_readiness",
                    entity_name=skill_name or None, metric_name="historical_series_readiness",
                    metric_value="insufficient_data", unit="status", source="github_innovation_graph",
                    data_origin="unavailable", readiness_state="insufficient_data",
                    details={"signal_type": "adoption", "geography": country, "frequency": "quarterly", "reason": explanation},
                ))
                evidence.append(EvidenceItem(
                    evidence_id="ev_github_history_unavailable", source="github_innovation_graph",
                    signal_type="adoption", data_origin="unavailable", quality="unavailable",
                    location=country, description=explanation,
                ))
                limitations.append(explanation)
            limitations.append("GitHub Innovation Graph measures quarterly developer activity (adoption) by country; it is not hiring demand.")
            return facts, evidence, limitations

        # Use the maximum supported window here: Historical Skill Signals is a
        # history retrieval feature, independent of the default 30-day snapshot window.
        observations = self._get_market_observations(
            request_obs=request.observations, skill=plan.context_summary.get("primary_entity"),
            time_range="max", source=selected_source, signal_type=selected_signal,
        )
        eligible = [item for item in observations if observation_is_eligible_history(item)]
        if selected_source in {"stackexchange", "wikipedia"}:
            # Both configured series are global. A country request cannot turn a
            # global observation into country-level evidence.
            eligible = [item for item in eligible if not item.location]
            if country:
                limitations.append(f"{selected_source} history is global in the stored series; no {country}-specific series is available.")
        identities = {historical_series_identity(item) for item in eligible}
        observations_by_series: dict[tuple[str, ...], list[Any]] = {}
        for item in eligible:
            observations_by_series.setdefault(historical_series_identity(item), []).append(item)
        if len(identities) > 1:
            limitations.append(f"Found {len(identities)} incompatible source-specific series. Their values are shown only within their original series and are never merged or compared.")
        obs = sorted(eligible, key=lambda item: (item.period or "", item.id or ""))

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
                data_origin=o.data_origin or "unavailable",
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
                    "frequency": period_grain(o.period),
                    "signal_type": o.signal_type,
                    "data_origin": o.data_origin,
                    "history_type": o.history_type,
                    "missing_periods": missing_periods(observations_by_series[historical_series_identity(o)]),
                },
            ))

            evidence.append(EvidenceItem(
                evidence_id=o.id,
                source=o.source,
                signal_type=o.signal_type,
                period=o.period,
                unit=o.unit,
                data_origin=o.data_origin or "unavailable",
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
                description=f"Historical {o.signal_type} observation for '{o.skill}' from {o.source} in {o.period}, unit {o.unit or 'unspecified'}, series {o.series_id or 'unidentified'}.",
            ))

        if not obs:
            readiness_id = "ev_historical_series_unavailable"
            source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
            reason = (
                f"No eligible {selected_source or 'supported source'} {selected_signal or 'historical signal'} observations matched the selected skill. "
                "Eligible history consists of completed real monthly Stack Exchange question counts or Wikipedia pageviews, "
                "and completed real quarterly GitHub developer-activity series. Snapshots and incomplete or untracked series are excluded."
            )
            if selected_signal == "demand" and selected_source in {
                None, "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
            }:
                reason = (
                    f"No supported historical skill-demand series is available for '{plan.context_summary.get('primary_entity') or 'the requested skill'}'. "
                    "JSearch and Adzuna records are job-posting snapshots, not source-aggregated historical demand observations."
                )
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
                    "reason": reason,
                    "periods": [],
                },
            ))
            evidence.append(EvidenceItem(
                evidence_id=readiness_id,
                source=source,
                signal_type="evidence_readiness",
                data_origin="unavailable",
                quality="unavailable",
                description=reason,
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
        origins = {observation.data_origin for observation in obs if observation.data_origin}
        analysis_origin = (
            "real" if origins == {"real"}
            else "mixed" if len(origins) > 1
            else "demo" if origins == {"demo"}
            else "unavailable"
        )
        if len(obs) >= 4:
            trends = analysis.trend_results
            eligible_trends = [
                trend for trend in trends
                if trend.data_state in {"ready", "fresh"}
                and trend.data_origin == "real"
                and trend.history_type == "platform_collected"
                and trend.canonical_skill_id
                and (request.domain != "skill" or trend.signal_type != "interest")
            ]
            signal_priority = {"demand": 0, "adoption": 1, "interest": 2}
            eligible_trends.sort(key=lambda trend: signal_priority.get(trend.signal_type, 3))
            if eligible_trends:
                trend_res = eligible_trends[0]
                supporting_observations = [
                    observation for observation in obs
                    if observation.id in set(trend_res.observation_ids)
                ]
                if not supporting_observations:
                    supporting_observations = [
                        observation for observation in obs
                        if observation.period in trend_res.periods_used
                        and observation.source.casefold() == (trend_res.provider or "").casefold()
                        and observation.signal_type == trend_res.signal_type
                        and observation.series_id == trend_res.series_id
                        and observation.query_id == trend_res.query_id
                        and observation.panel_version == trend_res.panel_version
                        and observation.scope == trend_res.scope
                        and (observation.location or "").casefold() == (trend_res.location or "").casefold()
                    ]
                freshness = assess_freshness(supporting_observations)
                if freshness.state in {"stale", "partial"}:
                    reason = (
                        "The comparable series contains stale collection evidence; no measured trend was returned."
                    )
                    readiness_id = f"ev_trend_{trend_res.series_id or 'series'}_stale"
                    facts.append(StructuredFact(
                        fact_id=f"fact_trend_stale_{trend_res.series_id or 'series'}",
                        fact_type="analysis_readiness",
                        entity_name=trend_res.canonical_name,
                        canonical_entity_id=trend_res.canonical_skill_id,
                        entity_type="skill",
                        metric_name="trend_readiness",
                        metric_value="stale",
                        unit="status",
                        period="_to_".join(trend_res.periods_used) or None,
                        source=trend_res.provider or "configured_market_observation_store",
                        data_origin=trend_res.data_origin,
                        history_type=trend_res.history_type,
                        series_id=trend_res.series_id,
                        quality_state="stale",
                        readiness_state="stale",
                        evidence_reference=readiness_id,
                        details={
                            "reason": reason,
                            "reason_code": "STALE_TREND_EVIDENCE",
                            "freshness_state": freshness.state,
                            "stale_observation_count": freshness.stale_count,
                            "periods_used": trend_res.periods_used,
                        },
                    ))
                    evidence.append(EvidenceItem(
                        evidence_id=readiness_id,
                        source=trend_res.provider or "configured_market_observation_store",
                        signal_type=trend_res.signal_type,
                        period="_to_".join(trend_res.periods_used) or None,
                        data_origin=trend_res.data_origin,
                        history_type=trend_res.history_type,
                        series_id=trend_res.series_id,
                        location=trend_res.location,
                        scope=trend_res.scope,
                        query_id=trend_res.query_id,
                        panel_version=trend_res.panel_version,
                        supporting_observation_ids=trend_res.observation_ids,
                        supporting_fetch_run_ids=trend_res.fetch_run_ids,
                        freshness_state=freshness.state,
                        quality="stale",
                        description=reason,
                    ))
                    limitations.append(reason)
                    return facts, evidence, limitations
                ent_name = trend_res.canonical_name or obs[0].skill
                start_p = trend_res.periods_used[0] if trend_res.periods_used else ""
                end_p = trend_res.periods_used[-1] if trend_res.periods_used else ""
                slope_val = trend_res.trend_slope if trend_res.trend_slope is not None else trend_res.slope
                ev_id = f"ev_trend_{ent_name}_{end_p}"
                denominators = sorted({
                    observation.denominator
                    for observation in supporting_observations
                    if observation.denominator is not None
                })
                denominator_units = sorted({
                    observation.denominator_unit
                    for observation in supporting_observations
                    if observation.denominator_unit
                })
                trend_details = {
                    "trend_slope": slope_val,
                    "slope_unit": trend_res.slope_unit,
                    "value_unit": trend_res.unit,
                    "metric": trend_res.metric,
                    "denominator": denominators[0] if len(denominators) == 1 else None,
                    "denominator_unit": denominator_units[0] if len(denominator_units) == 1 else None,
                    "period_denominators": [
                        {
                            "period": observation.period,
                            "denominator": observation.denominator,
                            "denominator_unit": observation.denominator_unit,
                        }
                        for observation in supporting_observations
                        if observation.denominator is not None
                    ],
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
                    "series": trend_res.series,
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
                    "source_history_type": trend_res.history_type,
                    "freshness_state": (
                        "fresh" if freshness.state == "ready"
                        else "unknown" if freshness.state == "insufficient_data"
                        else freshness.state
                    ),
                    "history_complete": analysis.history_complete,
                    "series_id": trend_res.series_id,
                    "location": trend_res.location,
                    "query_id": trend_res.query_id,
                    "panel_version": trend_res.panel_version,
                    "observation_ids": [observation.id for observation in supporting_observations if observation.id],
                    "fetch_run_ids": trend_res.fetch_run_ids,
                    "source_urls": [
                        observation.source_url for observation in supporting_observations
                        if observation.source_url
                    ],
                }
                if trend_res.period_grain == "month":
                    trend_details["monthly_velocity"] = trend_res.velocity
                facts.append(StructuredFact(
                    fact_id=f"fact_trend_{ent_name}_{end_p}",
                    fact_type="trend_analysis",
                    entity_name=ent_name,
                    canonical_entity_id=trend_res.canonical_skill_id,
                    entity_type="skill",
                    metric_name="trend_direction",
                    metric_value=trend_res.trend_direction or trend_res.trend,
                    period=f"{start_p}_to_{end_p}",
                    source="theil_sen_estimator",
                    data_origin=trend_res.data_origin,
                    history_type="empirical_time_series",
                    denominator=trend_details["denominator"],
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
                    measured_signal_type=trend_res.signal_type,
                    period=f"{start_p}_to_{end_p}",
                    unit=trend_res.velocity_unit or trend_res.unit,
                    data_origin=trend_res.data_origin or "unavailable",
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    location=trend_res.location,
                    query_id=trend_res.query_id,
                    panel_version=trend_res.panel_version,
                    supporting_observation_ids=trend_details["observation_ids"],
                    supporting_fetch_run_ids=trend_res.fetch_run_ids,
                    supporting_source_urls=trend_details["source_urls"],
                    freshness_state=trend_details["freshness_state"],
                    quality="valid",
                    description=(
                        f"Theil-Sen trend calculation across {len(trend_res.periods_used)} consecutive periods: "
                        f"slope={slope_val}, velocity={trend_res.velocity}, direction={trend_res.trend_direction or trend_res.trend}."
                    ),
                ))
                if trend_res.warnings:
                    limitations.extend(trend_res.warnings)
            elif trends:
                signal_priority = {"demand": 0, "adoption": 1, "interest": 2}
                trend_res = sorted(
                    trends,
                    key=lambda trend: signal_priority.get(trend.signal_type, 3),
                )[0]
                readiness_id = f"ev_trend_{trend_res.series_id or 'series'}_blocked"
                if request.domain == "skill" and trend_res.signal_type == "interest":
                    reason = (
                        "Skill Demand Trends cannot substitute an interest series for hiring-demand evidence; "
                        "the available interest series is not eligible for this feature."
                    )
                elif trend_res.data_origin != "real":
                    reason = "Observation provenance is missing or non-production; it cannot support a measured trend."
                elif trend_res.history_type != "platform_collected":
                    reason = "Only eligible platform-collected observations can support this measured trend."
                else:
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
                    data_origin=trend_res.data_origin,
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    quality_state=trend_res.data_state,
                    readiness_state="insufficient_data",
                    evidence_reference=readiness_id,
                    details={
                        "reason": reason,
                        "reason_code": (
                            "OBSERVATION_PROVENANCE_UNAVAILABLE"
                            if trend_res.data_origin != "real"
                            else "INELIGIBLE_HISTORY_TYPE"
                            if trend_res.history_type != "platform_collected"
                            else "TREND_NOT_READY"
                        ),
                        "freshness_state": "unknown",
                        "period_grain": "month",
                        "periods_used": trend_res.periods_used,
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=trend_res.provider or "configured_market_observation_store",
                    signal_type="analysis_readiness",
                    measured_signal_type=trend_res.signal_type,
                    period="_to_".join(trend_res.periods_used) if trend_res.periods_used else None,
                    data_origin=trend_res.data_origin or "unavailable",
                    history_type=trend_res.history_type,
                    series_id=trend_res.series_id,
                    freshness_state="unknown",
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
                    data_origin=analysis_origin,
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
                    data_origin=analysis_origin,
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
                data_origin=analysis_origin,
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
                data_origin=analysis_origin,
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

    def _handle_skill_health_analysis(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Skill Health is a relative-momentum indicator; baseline 50.0 indicates neutral relative momentum, not a 50% health percentage.",
            "Higher Skill Health score does not prove higher absolute hiring volume or future market dominance.",
            "Skill Health indicates observed relative momentum and is not an outcome-calibrated probability of career success or obsolescence.",
        ]

        analysis = self._shared_market_analysis(request, plan)
        all_obs = analysis.observations

        # Determine entities
        entities_to_evaluate: list[str] = []
        if plan.context_summary.get("primary_entity"):
            entities_to_evaluate.append(plan.context_summary["primary_entity"])
        for comp in plan.context_summary.get("comparison_entities", []):
            if comp not in entities_to_evaluate:
                entities_to_evaluate.append(comp)
        if not entities_to_evaluate and plan.entities:
            for item in plan.entities:
                if item.canonical_entity and item.canonical_entity.canonical_name not in entities_to_evaluate:
                    entities_to_evaluate.append(item.canonical_entity.canonical_name)
        if not entities_to_evaluate:
            ent = plan.context_summary.get("primary_entity") or (all_obs[0].skill if all_obs else "Unknown")
            entities_to_evaluate.append(ent)

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.skill_health import evaluate_skill_health

        for token in entities_to_evaluate:
            norm_name = token
            canon_id = canonical_skill_id(token)
            skill_obs = [
                o for o in all_obs
                if (o.skill and o.skill.casefold() == token.casefold())
                or (canon_id and o.skill_id == canon_id)
            ]
            if not skill_obs and not request.observations and self.firestore_store is not None:
                skill_obs = self._get_market_observations(
                    request_obs=None,
                    skill=token,
                    location=request.location,
                    time_range=request.time_range,
                )

            if not skill_obs:
                readiness_id = f"ev_health_{token}_no_obs"
                source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
                facts.append(StructuredFact(
                    fact_id=f"fact_health_{token}_no_obs",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_health_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source=source,
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"No empirical observations found for '{token}'.",
                        "reason_code": "NO_OBSERVATIONS_FOR_SERIES",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="unavailable",
                    quality="insufficient_data",
                    description=f"Zero empirical observations found for '{token}'.",
                ))
                continue

            has_real = any(getattr(o, "data_origin", None) == "real" for o in skill_obs)
            if not has_real:
                readiness_id = f"ev_health_{token}_provenance"
                source = skill_obs[0].source if skill_obs else "observation_store"
                facts.append(StructuredFact(
                    fact_id=f"fact_health_{token}_provenance",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_health_readiness",
                    metric_value="unavailable",
                    unit="status",
                    source=source,
                    data_origin="demo",
                    readiness_state="unavailable",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"Observation provenance for '{token}' is non-production (demo/synthetic).",
                        "reason_code": "OBSERVATION_PROVENANCE_UNAVAILABLE",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="demo",
                    quality="unavailable",
                    description=f"Provenance unavailable: demo/synthetic observations for '{token}'.",
                ))
                continue

            signals = aggregate_market_signals(skill_obs)
            health_res = evaluate_skill_health(
                signals,
                canonical_skill_id=canon_id,
                canonical_name=token,
                history_complete=analysis.history_complete,
            )

            component_evidence_map: dict[int, str] = {}
            for idx, comp in enumerate(health_res.component_table):
                ev_id = f"ev_health_{token}_{comp.provider}_{comp.signal_family}_{comp.latest_period or idx}"
                component_evidence_map[idx] = ev_id
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source=comp.provider,
                    signal_type=comp.signal_family,
                    period=(
                        f"{comp.first_period}_to_{comp.latest_period}"
                        if comp.first_period and comp.latest_period
                        else comp.latest_period
                    ),
                    unit=comp.unit,
                    data_origin=comp.data_origin or "real",
                    history_type=comp.history_type or "platform_collected",
                    series_id=comp.series_id,
                    location=comp.location,
                    scope=comp.scope,
                    query_id=comp.query_id,
                    panel_version=comp.panel_version,
                    supporting_observation_ids=comp.observation_ids,
                    supporting_fetch_run_ids=comp.fetch_run_ids,
                    quality="valid" if comp.is_eligible_share else "ineligible",
                    description=(
                        f"Skill Health {comp.signal_family} component ({comp.direction}) for '{token}' "
                        f"evaluated over {comp.periods_evaluated} periods ({comp.reason})."
                    ),
                ))

            primary_ev_id = next(iter(component_evidence_map.values()), f"ev_health_{token}_summary")
            if not component_evidence_map:
                evidence.append(EvidenceItem(
                    evidence_id=primary_ev_id,
                    source=skill_obs[0].source if skill_obs else "observation_store",
                    signal_type="health_summary",
                    quality=health_res.status,
                    description=health_res.explanation,
                ))

            score_fact_id = f"fact_health_score_{token}"
            facts.append(StructuredFact(
                fact_id=score_fact_id,
                fact_type="skill_health_score",
                entity_name=token,
                canonical_entity_id=canon_id,
                entity_type="skill",
                metric_name="skill_health_score",
                metric_value=health_res.score,
                unit="score_0_100",
                source=health_res.component_table[0].provider if health_res.component_table else "skill_health_engine",
                data_origin="real",
                quality_state=health_res.score_status,
                readiness_state=health_res.score_status,
                calculation_version=health_res.calculation_version,
                evidence_reference=primary_ev_id,
                details={
                    "score_status": health_res.score_status,
                    "score_formula": health_res.score_formula,
                    "score_weights": health_res.score_weights,
                    "baseline_score": 50.0,
                    "score_range": [0.0, 100.0],
                    "thresholds": health_res.thresholds,
                    "explanation": health_res.explanation,
                },
            ))

            cat_fact_id = f"fact_health_cat_{token}"
            facts.append(StructuredFact(
                fact_id=cat_fact_id,
                fact_type="skill_health_category",
                entity_name=token,
                canonical_entity_id=canon_id,
                entity_type="skill",
                metric_name="skill_health_category",
                metric_value=health_res.health_category,
                unit="category",
                source=health_res.component_table[0].provider if health_res.component_table else "skill_health_engine",
                data_origin="real",
                quality_state=health_res.status,
                readiness_state=health_res.status,
                calculation_version=health_res.calculation_version,
                evidence_reference=primary_ev_id,
                details={
                    "status": health_res.status,
                    "eligible_family_count": health_res.eligible_family_count,
                    "ready_families": health_res.ready_families,
                },
            ))

            for idx, comp in enumerate(health_res.component_table):
                comp_ev_id = component_evidence_map.get(idx, primary_ev_id)
                facts.append(StructuredFact(
                    fact_id=f"fact_health_comp_{token}_{idx}",
                    fact_type="skill_health_component",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name=f"{comp.signal_family}_{comp.metric}",
                    metric_value=comp.direction,
                    unit="direction",
                    period=(
                        f"{comp.first_period}_to_{comp.latest_period}"
                        if comp.first_period and comp.latest_period
                        else comp.latest_period
                    ),
                    source=comp.provider,
                    data_origin=comp.data_origin or "real",
                    history_type=comp.history_type or "platform_collected",
                    series_id=comp.series_id,
                    quality_state="valid" if comp.is_eligible_share else "ineligible",
                    readiness_state="ready" if comp.is_eligible_share else "ineligible",
                    evidence_reference=comp_ev_id,
                    details={
                        "signal_family": comp.signal_family,
                        "provider": comp.provider,
                        "metric": comp.metric,
                        "is_eligible_share": comp.is_eligible_share,
                        "theil_sen_slope_per_month": comp.theil_sen_slope_per_month,
                        "relative_slope_per_month": comp.relative_slope_per_month,
                        "whole_window_change": comp.whole_window_change,
                        "whole_window_pct_change": comp.whole_window_pct_change,
                        "latest_mom_change": comp.latest_mom_change,
                        "latest_mom_pct_change": comp.latest_mom_pct_change,
                        "health_score": comp.health_score,
                        "periods_used": comp.periods_used,
                        "unit": comp.unit,
                        "denominator_unit": comp.denominator_unit,
                        "reason": comp.reason,
                    },
                ))

            if health_res.status == "insufficient_data" and health_res.score is None:
                reasons = [row.reason for row in health_res.component_table if row.reason]
                if any("Raw count series without source-specific denominator" in r for r in reasons) and not any(row.is_eligible_share for row in health_res.component_table):
                    reason_code = "MISSING_SERIES_DENOMINATOR"
                elif any("Non-consecutive" in r for r in reasons):
                    reason_code = "INSUFFICIENT_HEALTH_HISTORY"
                else:
                    reason_code = "INSUFFICIENT_HEALTH_HISTORY"
                readiness_id = f"ev_health_{token}_insufficient"
                facts.append(StructuredFact(
                    fact_id=f"fact_health_{token}_insufficient",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_health_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source=health_res.component_table[0].provider if health_res.component_table else "skill_health_engine",
                    data_origin="real",
                    readiness_state="insufficient_data",
                    evidence_reference=primary_ev_id,
                    details={
                        "reason": health_res.explanation,
                        "reason_code": reason_code,
                    },
                ))

            limitations.extend(health_res.limitations)

        return facts, evidence, list(dict.fromkeys(limitations))

    def _handle_skill_half_life_analysis(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Skill Half-Life is an empirical decay estimate under an exponential decay model (ln(2) / |b|); not an obsolescence guarantee.",
            "Half-Life applies only to statistically supported monotonic decay in normalized market share; stable or growing skills return not applicable.",
            "Historical rate of decay does not predict future disruptive changes, platform shifts, or sudden hiring shocks.",
        ]

        analysis = self._shared_market_analysis(request, plan)
        all_obs = analysis.observations

        # Determine entities
        entities_to_evaluate: list[str] = []
        if plan.context_summary.get("primary_entity"):
            entities_to_evaluate.append(plan.context_summary["primary_entity"])
        for comp in plan.context_summary.get("comparison_entities", []):
            if comp not in entities_to_evaluate:
                entities_to_evaluate.append(comp)
        if not entities_to_evaluate and plan.entities:
            for item in plan.entities:
                if item.canonical_entity and item.canonical_entity.canonical_name not in entities_to_evaluate:
                    entities_to_evaluate.append(item.canonical_entity.canonical_name)
        if not entities_to_evaluate:
            ent = plan.context_summary.get("primary_entity") or (all_obs[0].skill if all_obs else "Unknown")
            entities_to_evaluate.append(ent)

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.skill_half_life import calculate_skill_half_life

        for token in entities_to_evaluate:
            norm_name = token
            canon_id = canonical_skill_id(token)
            skill_obs = [
                o for o in all_obs
                if (o.skill and o.skill.casefold() == token.casefold())
                or (canon_id and o.skill_id == canon_id)
            ]
            if not skill_obs and not request.observations and self.firestore_store is not None:
                skill_obs = self._get_market_observations(
                    request_obs=None,
                    skill=token,
                    location=request.location,
                    time_range=request.time_range,
                )

            if not skill_obs:
                readiness_id = f"ev_half_life_{token}_no_obs"
                source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
                facts.append(StructuredFact(
                    fact_id=f"fact_half_life_{token}_no_obs",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_half_life_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source=source,
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"No empirical observations found for '{token}'.",
                        "reason_code": "NO_OBSERVATIONS_FOR_SERIES",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="unavailable",
                    quality="insufficient_data",
                    description=f"Zero empirical observations found for '{token}'.",
                ))
                continue

            has_real = any(getattr(o, "data_origin", None) == "real" for o in skill_obs)
            if not has_real:
                readiness_id = f"ev_half_life_{token}_provenance"
                source = skill_obs[0].source if skill_obs else "observation_store"
                facts.append(StructuredFact(
                    fact_id=f"fact_half_life_{token}_provenance",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_half_life_readiness",
                    metric_value="unavailable",
                    unit="status",
                    source=source,
                    data_origin="demo",
                    readiness_state="unavailable",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"Observation provenance for '{token}' is non-production (demo/synthetic).",
                        "reason_code": "OBSERVATION_PROVENANCE_UNAVAILABLE",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="demo",
                    quality="unavailable",
                    description=f"Provenance unavailable: demo/synthetic observations for '{token}'.",
                ))
                continue

            signals = aggregate_market_signals(skill_obs)
            hl_res = calculate_skill_half_life(
                signals,
                canonical_skill_id=canon_id,
                canonical_name=token,
                history_complete=analysis.history_complete,
            )

            # Generate evidence
            ev_id = f"ev_half_life_{token}_{hl_res.provider}_{hl_res.signal_family}_{hl_res.latest_period or 'summary'}"
            evidence.append(EvidenceItem(
                evidence_id=ev_id,
                source=hl_res.provider,
                signal_type=hl_res.signal_family,
                period=(
                    f"{hl_res.first_period}_to_{hl_res.latest_period}"
                    if hl_res.first_period and hl_res.latest_period
                    else hl_res.latest_period
                ),
                unit=hl_res.value_unit or "postings",
                data_origin=hl_res.data_origin or "real",
                history_type=hl_res.history_type or "platform_collected",
                series_id=hl_res.series_id,
                location=hl_res.location,
                scope=hl_res.scope,
                query_id=hl_res.query_id,
                panel_version=hl_res.panel_version,
                supporting_observation_ids=hl_res.observation_ids,
                supporting_fetch_run_ids=hl_res.fetch_run_ids,
                quality="valid" if hl_res.status in {"ready", "not_applicable"} else "ineligible",
                description=(
                    f"Skill Half-Life for '{token}' on {hl_res.provider}: {hl_res.status} "
                    f"over {hl_res.periods_evaluated} periods ({hl_res.reason or hl_res.explanation})."
                ),
            ))

            fact_id = f"fact_half_life_{token}"
            facts.append(StructuredFact(
                fact_id=fact_id,
                fact_type="skill_half_life",
                entity_name=token,
                canonical_entity_id=canon_id,
                entity_type="skill",
                metric_name="skill_half_life_months",
                metric_value=hl_res.half_life_months,
                unit="months",
                period=(
                    f"{hl_res.first_period}_to_{hl_res.latest_period}"
                    if hl_res.first_period and hl_res.latest_period
                    else hl_res.latest_period
                ),
                source=hl_res.provider,
                data_origin=hl_res.data_origin or "real",
                quality_state=hl_res.status,
                readiness_state=hl_res.status,
                calculation_version=hl_res.calculation_version,
                evidence_reference=ev_id,
                details={
                    "status": hl_res.status,
                    "half_life_months": hl_res.half_life_months,
                    "half_life_years": hl_res.half_life_years,
                    "uncertainty_range_months": list(hl_res.uncertainty_range_months) if hl_res.uncertainty_range_months else None,
                    "log_share_slope_per_month": hl_res.log_share_slope_per_month,
                    "slope_ci_95": list(hl_res.slope_ci_95) if hl_res.slope_ci_95 else None,
                    "kendall_tau": hl_res.kendall_tau,
                    "kendall_p_value": hl_res.kendall_p_value,
                    "periods_evaluated": hl_res.periods_evaluated,
                    "required_min_periods": hl_res.required_min_periods,
                    "first_period": hl_res.first_period,
                    "latest_period": hl_res.latest_period,
                    "periods_used": hl_res.periods_used,
                    "model_name": hl_res.model_name,
                    "confidence_interval": 95,
                    "formula": "half_life_months = ln(2) / abs(b)",
                    "signal_family": hl_res.signal_family,
                    "provider": hl_res.provider,
                    "reason": hl_res.reason,
                    "explanation": hl_res.explanation,
                },
            ))

            if hl_res.status in {"insufficient_data", "unavailable"}:
                reason = hl_res.reason or "Insufficient consecutive monthly observations to evaluate Skill Half-Life."
                if "without a source-specific denominator" in reason or "raw count" in reason.lower():
                    reason_code = "MISSING_SERIES_DENOMINATOR"
                elif "missing monthly periods" in reason.lower() or "requires >= 36" in reason.lower() or "consecutive" in reason.lower():
                    reason_code = "INSUFFICIENT_HALF_LIFE_HISTORY"
                else:
                    reason_code = "INSUFFICIENT_HALF_LIFE_HISTORY"
                readiness_id = f"ev_half_life_{token}_insufficient"
                facts.append(StructuredFact(
                    fact_id=f"fact_half_life_{token}_insufficient",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_half_life_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source=hl_res.provider,
                    data_origin="real",
                    readiness_state="insufficient_data",
                    evidence_reference=ev_id,
                    details={
                        "reason": hl_res.explanation or reason,
                        "reason_code": reason_code,
                        "required_min_periods": hl_res.required_min_periods,
                        "periods_evaluated": hl_res.periods_evaluated,
                    },
                ))

            limitations.extend(hl_res.limitations)

        return facts, evidence, list(dict.fromkeys(limitations))

    def _handle_skill_demand_forecasting(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Skill Demand Forecasting requires at least 24 consecutive completed monthly observations.",
            "Forecast horizon is capped at min(6, history_length // 3) months.",
            "Uses a seasonal-naive carry-forward model evaluated out-of-sample against a simple naive baseline.",
            "Prediction intervals are omitted until horizon-specific holdout coverage is sufficient.",
            "Future demand predictions are non-guaranteed estimates based on historical observations.",
        ]

        analysis = self._shared_market_analysis(request, plan)
        all_obs = analysis.observations

        # Determine entities
        entities_to_evaluate: list[str] = []
        if plan.context_summary.get("primary_entity"):
            entities_to_evaluate.append(plan.context_summary["primary_entity"])
        for comp in plan.context_summary.get("comparison_entities", []):
            if comp not in entities_to_evaluate:
                entities_to_evaluate.append(comp)
        if not entities_to_evaluate and plan.entities:
            for item in plan.entities:
                if item.canonical_entity and item.canonical_entity.canonical_name not in entities_to_evaluate:
                    entities_to_evaluate.append(item.canonical_entity.canonical_name)
        if not entities_to_evaluate:
            ent = plan.context_summary.get("primary_entity") or (all_obs[0].skill if all_obs else "Unknown")
            entities_to_evaluate.append(ent)

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.forecasting import forecast_signal_series

        for token in entities_to_evaluate:
            norm_name = token
            canon_id = canonical_skill_id(token)
            skill_obs = [
                o for o in all_obs
                if (o.skill and o.skill.casefold() == token.casefold())
                or (canon_id and o.skill_id == canon_id)
            ]
            if not skill_obs and not request.observations and self.firestore_store is not None:
                skill_obs = self._get_market_observations(
                    request_obs=None,
                    skill=token,
                    location=request.location,
                    time_range=request.time_range,
                )

            if not skill_obs:
                readiness_id = f"ev_forecast_{token}_no_obs"
                source = "firestore_skill_market_signals" if self.firestore_store is not None else "sqlite_skill_market_signals"
                facts.append(StructuredFact(
                    fact_id=f"fact_forecast_{token}_no_obs",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_forecast_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source=source,
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"No empirical observations found for '{token}'.",
                        "reason_code": "NO_OBSERVATIONS_FOR_SERIES",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="unavailable",
                    quality="insufficient_data",
                    description=f"Zero empirical observations found for '{token}'.",
                ))
                continue

            has_real = any(getattr(o, "data_origin", None) == "real" for o in skill_obs)
            if not has_real:
                readiness_id = f"ev_forecast_{token}_provenance"
                source = skill_obs[0].source if skill_obs else "observation_store"
                facts.append(StructuredFact(
                    fact_id=f"fact_forecast_{token}_provenance",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_forecast_readiness",
                    metric_value="unavailable",
                    unit="status",
                    source=source,
                    data_origin="demo",
                    readiness_state="unavailable",
                    evidence_reference=readiness_id,
                    details={
                        "reason": f"Observation provenance for '{token}' is non-production (demo/synthetic).",
                        "reason_code": "OBSERVATION_PROVENANCE_UNAVAILABLE",
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=source,
                    signal_type="analysis_readiness",
                    data_origin="demo",
                    quality="unavailable",
                    description=f"Provenance unavailable: demo/synthetic observations for '{token}'.",
                ))
                continue

            signals = aggregate_market_signals(skill_obs)
            fc_res = forecast_signal_series(
                signals,
                canonical_skill_id=canon_id,
                canonical_name=token,
                history_complete=analysis.history_complete,
            )

            # Generate evidence
            ev_id = f"ev_forecast_{token}_{fc_res.provider}_{fc_res.signal_family}_{fc_res.latest_history_period or 'summary'}"
            evidence.append(EvidenceItem(
                evidence_id=ev_id,
                source=fc_res.provider,
                signal_type=fc_res.signal_family,
                period=(
                    f"{fc_res.first_history_period}_to_{fc_res.latest_history_period}"
                    if fc_res.first_history_period and fc_res.latest_history_period
                    else fc_res.latest_history_period
                ),
                unit=fc_res.unit or "postings",
                data_origin="real" if fc_res.status == "ready" else "unavailable",
                history_type="platform_collected",
                series_id=fc_res.target_series,
                supporting_observation_ids=fc_res.observation_ids,
                supporting_fetch_run_ids=fc_res.fetch_run_ids,
                quality="valid" if fc_res.status == "ready" else "ineligible",
                description=(
                    f"Skill Demand Forecast for '{token}' on {fc_res.provider}: {fc_res.status} "
                    f"over {fc_res.history_length} periods ({fc_res.reason or fc_res.explanation})."
                ),
            ))

            fact_id = f"fact_forecast_{token}"
            first_pred = fc_res.forecasts[0].point_forecast if fc_res.forecasts else None
            facts.append(StructuredFact(
                fact_id=fact_id,
                fact_type="skill_forecast",
                entity_name=token,
                canonical_entity_id=canon_id,
                entity_type="skill",
                metric_name="point_forecast",
                metric_value=first_pred,
                unit=fc_res.unit or "share",
                period=(
                    f"{fc_res.first_history_period}_to_{fc_res.latest_history_period}"
                    if fc_res.first_history_period and fc_res.latest_history_period
                    else fc_res.latest_history_period
                ),
                source=fc_res.provider,
                data_origin="real" if fc_res.status == "ready" else "unavailable",
                quality_state=fc_res.status,
                readiness_state=fc_res.status,
                calculation_version=fc_res.calculation_version,
                evidence_reference=ev_id,
                details={
                    "status": fc_res.status,
                    "target_series": fc_res.target_series,
                    "provider": fc_res.provider,
                    "signal_family": fc_res.signal_family,
                    "metric": fc_res.metric,
                    "unit": fc_res.unit,
                    "selected_method": fc_res.selected_method,
                    "baseline_name": fc_res.baseline_name,
                    "horizon_months": fc_res.horizon_months,
                    "history_length": fc_res.history_length,
                    "required_min_periods": fc_res.required_min_periods,
                    "first_history_period": fc_res.first_history_period,
                    "latest_history_period": fc_res.latest_history_period,
                    "winner_rmse": fc_res.winner_rmse,
                    "naive_rmse": fc_res.naive_rmse,
                    "beats_naive_baseline": fc_res.beats_naive_baseline,
                    "backtest_sample_size": fc_res.backtest_sample_size,
                    "backtest_periods": fc_res.backtest_periods,
                    "backtest_scores": [s.model_dump() for s in fc_res.backtest_scores],
                    "forecasts": [pt.model_dump() for pt in fc_res.forecasts],
                    "observed_history": fc_res.observed_history,
                    "reason": fc_res.reason,
                    "explanation": fc_res.explanation,
                    "limitations": fc_res.limitations,
                },
            ))

            for pt in fc_res.forecasts:
                facts.append(StructuredFact(
                    fact_id=f"fact_forecast_{token}_{pt.period}",
                    fact_type="skill_forecast_point",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name=f"forecast_month_{pt.horizon_step}",
                    metric_value=pt.point_forecast,
                    unit=fc_res.unit or "share",
                    period=pt.period,
                    source=fc_res.provider,
                    data_origin="real",
                    quality_state="ready",
                    readiness_state="ready",
                    calculation_version=fc_res.calculation_version,
                    evidence_reference=ev_id,
                    details={
                        "horizon_step": pt.horizon_step,
                        "point_forecast": pt.point_forecast,
                        "lower_80": pt.lower_80,
                        "upper_80": pt.upper_80,
                        "lower_95": pt.lower_95,
                        "upper_95": pt.upper_95,
                    },
                ))

            if fc_res.status != "ready":
                reason = fc_res.reason or "Insufficient historical observations for forecasting."
                if "without a source-specific denominator" in reason or "raw count" in reason.lower() or "requires a value, positive denominator" in reason.lower():
                    reason_code = "MISSING_SERIES_DENOMINATOR"
                elif "incompatible" in reason.lower() or "partitions" in reason.lower():
                    reason_code = "AMBIGUOUS_SOURCE_SERIES"
                elif "missing period gaps" in reason.lower() or "requires >= 24" in reason.lower() or "consecutive" in reason.lower():
                    reason_code = "INSUFFICIENT_FORECAST_HISTORY"
                else:
                    reason_code = "INSUFFICIENT_FORECAST_HISTORY"

                readiness_id = f"ev_forecast_{token}_{reason_code.lower()}"
                facts.append(StructuredFact(
                    fact_id=f"fact_forecast_{token}_readiness",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canon_id,
                    entity_type="skill",
                    metric_name="skill_forecast_readiness",
                    metric_value=fc_res.status,
                    unit="status",
                    source=fc_res.provider or "observation_store",
                    data_origin="unavailable",
                    readiness_state=fc_res.status,
                    evidence_reference=readiness_id,
                    details={
                        "reason": reason,
                        "reason_code": reason_code,
                    },
                ))

            limitations.extend(fc_res.limitations)

        return facts, evidence, list(dict.fromkeys(limitations))

    def _handle_ai_task_exposure(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Task exposure measures theoretical capability overlap only and never implies job disappearance or headcount reduction.",
            "Workforce hiring outcomes are tracked from empirical market demand series, not task exposure scores.",
            "Requires a verified, open-licensed task exposure dataset; unverified or synthetic ratings are withheld.",
        ]

        from app.analytics.ai_disruption import evaluate_ai_task_disruption
        from app.models.entity_registry import EntityResolutionRequest

        # Determine target entities
        entities_to_evaluate: list[str] = []
        if plan.context_summary.get("primary_entity"):
            entities_to_evaluate.append(plan.context_summary["primary_entity"])
        for comp in plan.context_summary.get("comparison_entities", []):
            if comp not in entities_to_evaluate:
                entities_to_evaluate.append(comp)
        if not entities_to_evaluate and plan.entities:
            for item in plan.entities:
                if item.canonical_entity and item.canonical_entity.canonical_name not in entities_to_evaluate:
                    entities_to_evaluate.append(item.canonical_entity.canonical_name)
        if not entities_to_evaluate and request.target_role:
            entities_to_evaluate.append(request.target_role)
        for role in request.selected_roles:
            if role and role not in entities_to_evaluate:
                entities_to_evaluate.append(role)
        if not entities_to_evaluate:
            entities_to_evaluate.append("Software Developers")

        # Evaluate AI task disruption for each entity
        for token in entities_to_evaluate:
            canonical_id = None
            entity_type: Literal["occupation", "skill", "company_role"] = "occupation"
            try:
                resolution = self.entity_service.resolve(EntityResolutionRequest(name=token))
                if resolution.resolved:
                    canonical_id = resolution.canonical_id
                    if resolution.entity_type == "skill":
                        entity_type = "skill"
                    elif resolution.entity_type == "occupation":
                        entity_type = "occupation"
            except Exception:
                pass

            analysis = evaluate_ai_task_disruption(
                entity_name=token,
                entity_type=entity_type,
                canonical_id=canonical_id,
                licensed_exposure_records=request.task_exposure_records,
                dataset_provenance=request.dataset_provenance,
            )

            limitations.extend(analysis.limitations)

            if analysis.status != "ready":
                readiness_id = f"ev_task_exp_{token}_unready"
                facts.append(StructuredFact(
                    fact_id=f"fact_task_exp_{token}_readiness",
                    fact_type="analysis_readiness",
                    entity_name=token,
                    canonical_entity_id=canonical_id,
                    entity_type=entity_type,
                    metric_name="task_exposure_readiness",
                    metric_value=analysis.status,
                    unit="status",
                    source=analysis.dataset_provenance.provider,
                    data_origin="real" if analysis.dataset_provenance.license_verified else "unavailable",
                    readiness_state=analysis.status,
                    evidence_reference=readiness_id,
                    details={
                        "reason": analysis.reason,
                        "status": analysis.status,
                    },
                ))
                evidence.append(EvidenceItem(
                    evidence_id=readiness_id,
                    source=analysis.dataset_provenance.provider,
                    signal_type="analysis_readiness",
                    data_origin="real" if analysis.dataset_provenance.license_verified else "unavailable",
                    quality=analysis.status,
                    description=analysis.reason,
                ))
                continue

            # Produce primary summary evidence
            prov = analysis.dataset_provenance
            dataset_ev_id = f"ev_dataset_{prov.dataset_id}_{token}"
            evidence.append(EvidenceItem(
                evidence_id=dataset_ev_id,
                source=prov.provider,
                signal_type="task_exposure_dataset",
                data_origin="real",
                history_type="licensed_reference_dataset",
                quality="valid",
                description=(
                    f"Dataset '{prov.dataset_name}' (license: {prov.license_name}): "
                    f"{analysis.task_exposure_summary}"
                ),
            ))

            # Task exposure summary fact
            high_cnt = analysis.potential_exposure_counts.get("high", 0)
            mod_cnt = analysis.potential_exposure_counts.get("moderate", 0)
            low_cnt = analysis.potential_exposure_counts.get("low", 0)
            exposure_summary_val = f"{high_cnt} High, {mod_cnt} Moderate, {low_cnt} Low"

            facts.append(StructuredFact(
                fact_id=f"fact_task_exposure_summary_{token}",
                fact_type="task_exposure_summary",
                entity_name=token,
                canonical_entity_id=canonical_id,
                entity_type=entity_type,
                metric_name="task_exposure_levels",
                metric_value=exposure_summary_val,
                unit="tasks",
                source=prov.provider,
                data_origin="real",
                quality_state="valid",
                readiness_state="ready",
                calculation_version=analysis.calculation_version,
                evidence_reference=dataset_ev_id,
                details={
                    "tasks_evaluated_count": len(analysis.tasks_evaluated),
                    "high_exposure_count": high_cnt,
                    "moderate_exposure_count": mod_cnt,
                    "low_exposure_count": low_cnt,
                    "augmentation_task_count": analysis.observed_augmentation_task_count,
                    "automation_task_count": analysis.observed_automation_task_count,
                    "task_exposure_summary": analysis.task_exposure_summary,
                    "ai_usage_summary": analysis.ai_usage_summary,
                    "augmentation_vs_automation_summary": analysis.augmentation_vs_automation_summary,
                    "workforce_outcome_summary": analysis.workforce_outcome_summary,
                    "evidence_strength": analysis.evidence_strength,
                    "uncertainty_summary": analysis.uncertainty_summary,
                    "dataset_id": prov.dataset_id,
                    "license_name": prov.license_name,
                },
            ))

            # Individual task facts and evidence
            associated_skills_seen: set[str] = set()
            for task in analysis.tasks_evaluated:
                task_ev_id = task.evidence_source_id or f"ev_task_{task.task_id}"
                evidence.append(EvidenceItem(
                    evidence_id=task_ev_id,
                    source=task.evidence_source,
                    signal_type="task_exposure_record",
                    period=str(task.evidence_date) if task.evidence_date else None,
                    data_origin="real",
                    history_type="licensed_reference_dataset",
                    quality=task.evidence_strength if task.evidence_strength != "unknown" else "valid",
                    description=(
                        f"Task '{task.task_statement}' evaluated as {task.task_exposure_level} exposure "
                        f"({task.observed_ai_usage_mode} mode). {task.evidence_rationale or ''}".strip()
                    ),
                ))

                facts.append(StructuredFact(
                    fact_id=f"fact_task_{task.task_id}",
                    fact_type="task_exposure_record",
                    entity_name=token,
                    canonical_entity_id=canonical_id,
                    entity_type=entity_type,
                    metric_name="task_exposure_level",
                    metric_value=task.task_exposure_level,
                    unit="level",
                    period=str(task.evidence_date) if task.evidence_date else None,
                    source=task.evidence_source,
                    data_origin="real",
                    quality_state="valid",
                    readiness_state="ready",
                    provenance_id=task.task_id,
                    evidence_reference=task_ev_id,
                    details={
                        "task_id": task.task_id,
                        "task_statement": task.task_statement,
                        "occupation_code": task.occupation_code,
                        "occupation_title": task.occupation_title,
                        "task_exposure_level": task.task_exposure_level,
                        "observed_ai_usage_mode": task.observed_ai_usage_mode,
                        "human_oversight_required": task.human_oversight_required,
                        "canonical_skill_ids": task.canonical_skill_ids,
                        "evidence_rationale": task.evidence_rationale,
                        "evidence_strength": task.evidence_strength,
                    },
                ))

                # Associated canonical skills
                for skill_id in task.canonical_skill_ids:
                    if skill_id not in associated_skills_seen:
                        associated_skills_seen.add(skill_id)
                        facts.append(StructuredFact(
                            fact_id=f"fact_task_skill_{token}_{skill_id}",
                            fact_type="task_associated_skill",
                            entity_name=token,
                            canonical_entity_id=skill_id,
                            entity_type="skill",
                            metric_name="associated_skill",
                            metric_value=skill_id,
                            unit="skill_id",
                            source=task.evidence_source,
                            data_origin="real",
                            quality_state="valid",
                            readiness_state="ready",
                            evidence_reference=task_ev_id,
                            details={
                                "task_id": task.task_id,
                                "task_statement": task.task_statement,
                                "task_exposure_level": task.task_exposure_level,
                            },
                        ))

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
            if not o.id:
                continue
            evidence.append(EvidenceItem(
                evidence_id=o.id,
                source=o.source,
                signal_type=o.signal_type,
                period=o.period,
                unit=o.unit,
                data_origin=o.data_origin or "unavailable",
                history_type=o.history_type,
                series_id=o.series_id,
                location=o.location,
                scope=o.scope,
                query_id=o.query_id,
                panel_version=o.panel_version,
                fetch_run_id=o.fetch_run_id,
                supporting_fetch_run_ids=[o.fetch_run_id] if o.fetch_run_id else [],
                source_url=o.source_url,
                provenance_id=o.series_id,
                quality=o.quality or "valid",
                description=(
                    f"Stored {o.signal_type} observation {o.id} for {o.skill}: "
                    f"{o.value} {o.unit or 'units'} in {o.period or 'an unspecified period'} "
                    f"from {o.source}; {o.scope} scope, {o.location or 'unspecified geography'}, "
                    f"series {o.series_id or 'unspecified'}."
                ),
            ))

        # Taxonomy references are source records too. Include them only when a
        # caller explicitly asks about taxonomy/reference evidence.
        message = request.message.casefold()
        primary_entity = plan.context_summary.get("primary_entity")
        if re.search(r"\b(?:github|innovation graph|developer adoption|developer activity)\b", message):
            skill_id = canonical_skill_id(primary_entity or "")
            if skill_id:
                country = str((request.filters or {}).get("country") or "").strip().upper() or None
                geography_text = request.location
                if not geography_text:
                    match = re.search(r"\b(?:in|within)\s+([A-Za-z][A-Za-z .'-]*?)\s*[?.!]*$", request.message, re.IGNORECASE)
                    geography_text = match.group(1).strip() if match else None
                country_codes = {
                    "india": "IN", "in": "IN", "united states": "US", "usa": "US", "us": "US",
                    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "gb": "GB",
                    "canada": "CA", "ca": "CA", "australia": "AU", "au": "AU",
                    "germany": "DE", "de": "DE", "france": "FR", "fr": "FR",
                    "brazil": "BR", "br": "BR",
                }
                if not country and geography_text:
                    country = country_codes.get(geography_text.casefold())
                rows = self.reference_store.get_github_adoption_series(
                    canonical_skill_id=skill_id, iso2_code=country
                ) if country else []
                if not country:
                    limitations.append(
                        "GitHub Innovation Graph evidence is country-specific; specify a country to retrieve a bounded, geographically consistent series."
                    )
                for row in rows:
                    record_id = row.get("id")
                    if not record_id:
                        continue
                    kind = "language" if row.get("language") else "topic"
                    label = row.get("language") or row.get("topic")
                    metric = f"{kind}_pushers"
                    geo = str(row.get("iso2_code") or "unknown")
                    evidence.append(EvidenceItem(
                        evidence_id=f"github:{record_id}",
                        source="ref_github_language_adoption" if kind == "language" else "ref_github_topic_adoption",
                        signal_type="developer_adoption_observation",
                        measured_signal_type="adoption",
                        period=row.get("period"),
                        unit="unique developers per quarter",
                        data_origin=row.get("data_origin") or "unavailable",
                        history_type="backfill",
                        series_id=f"github_innovation_graph:{metric}:{geo}:{str(label).casefold()}",
                        location=geo,
                        scope="country",
                        provenance_id=str(record_id),
                        quality="valid",
                        description=(
                            f"GitHub Innovation Graph {metric} record for {label}, {geo}, "
                            f"{row.get('period')}: {row.get('num_pushers')} unique developers per quarter. "
                            "This is developer activity, not hiring demand."
                        ),
                    ))
        taxonomy_requested = bool(re.search(r"\b(?:taxonomy|esco|o\*?net|reference skills?|skill reference)\b", message))
        if taxonomy_requested:
            taxonomy = "esco" if re.search(r"\besco\b", message) else "onet"
            role = request.target_role or (request.selected_roles[0] if len(request.selected_roles) == 1 else None)
            if taxonomy == "esco" and role:
                occupations = self.reference_store.get_esco_occupations(query=role, limit=5)
                exact = [row for row in occupations if row["preferred_label"].casefold() == role.casefold()]
                if len(exact) == 1:
                    occupation_uri = exact[0]["concept_uri"]
                    for row in self.reference_store.get_esco_occupation_skills(occupation_uri, limit=100):
                        skill_uri = row.get("skill_uri")
                        if not skill_uri:
                            continue
                        evidence.append(EvidenceItem(
                            evidence_id=f"esco:{occupation_uri}:{skill_uri}",
                            source="ref_esco_occupation_skill_relations",
                            signal_type="occupation_skill_reference",
                            data_origin="real", history_type="reference_taxonomy",
                            provenance_id=skill_uri, quality="valid",
                            description=(
                                f"ESCO {row.get('relation_type') or 'occupation-skill'} reference: "
                                f"{row.get('preferred_label') or row.get('relation_skill_label')} "
                                f"({skill_uri}) for {role} ({occupation_uri}); "
                                f"source version {row.get('source_version') or 'not recorded'}."
                            ),
                        ))
            elif taxonomy == "esco" and primary_entity:
                # Evidence requests about a skill reference cite the exact
                # taxonomy row and do not require an occupation relation.
                rows = self.reference_store.get_esco_skills(query=primary_entity, limit=5)
                exact = [row for row in rows if row["preferred_label"].casefold() == primary_entity.casefold()]
                if len(exact) == 1:
                    row = exact[0]
                    uri = row.get("concept_uri")
                    if uri:
                        evidence.append(EvidenceItem(
                            evidence_id=f"esco_skill:{uri}",
                            source="ref_esco_skills",
                            signal_type="taxonomy_lookup",
                            data_origin="real",
                            history_type="reference_taxonomy",
                            provenance_id=uri,
                            quality="valid",
                            description=(
                                f"ESCO {row.get('source_version') or 'unknown'} skill taxonomy record: "
                                f"{row.get('preferred_label')} ({uri}); "
                                f"skill type {row.get('skill_type') or 'not specified'}."
                            ),
                        ))
            elif taxonomy == "onet" and role:
                matches = self.reference_store.get_onet_occupations(title=role, limit=100)
                exact = [row for row in matches if row.title.casefold().strip() == role.casefold().strip()]
                if len(exact) == 1:
                    for row in self.reference_store.get_onet_essential_skills_by_occupation(exact[0].soc_code, limit=100):
                        record_id = row.get("id")
                        if not record_id:
                            continue
                        evidence.append(EvidenceItem(
                            evidence_id=f"onet:{record_id}",
                            source="ref_onet_essential_skills",
                            signal_type="occupation_skill_reference",
                            data_origin="real", history_type="reference_taxonomy",
                            provenance_id=str(record_id), quality="valid",
                            description=(
                                f"O*NET essential skill {row.get('element_name')} "
                                f"({row.get('element_id')}) for {exact[0].title} "
                                f"(SOC {exact[0].soc_code}); source record {record_id}."
                            ),
                        ))

        ev_ref = evidence[0].evidence_id if evidence else None
        evidence_count = len(evidence)
        missing_reason = (
            "No matching stored observation or requested taxonomy reference record was found. "
            "No evidence item was created."
        )
        if re.search(r"\b(?:github|innovation graph|developer adoption|developer activity)\b", message) and not evidence:
            missing_reason = (
                "GitHub Innovation Graph records are grouped by country and the request did not specify one; "
                "no developer-adoption record was selected. This source measures developer activity, not hiring demand."
            )

        facts.append(StructuredFact(
            fact_id=f"fact_ev_summary_{evidence_count}",
            fact_type="evidence_summary",
            entity_name=primary_entity or "Skill Evidence",
            canonical_entity_id=None,
            entity_type="evidence",
            metric_name="verified_evidence_items_count",
            metric_value=evidence_count,
            unit="items",
            source=(evidence[0].source if evidence else "configured_evidence_stores"),
            data_origin="real" if evidence else "unavailable",
            quality_state="valid" if evidence else "insufficient_data",
            readiness_state="ready" if evidence else "insufficient_data",
            evidence_reference=ev_ref,
            details={"reason": None if evidence else missing_reason},
        ))

        if request.task_exposure_records:
            prov = request.dataset_provenance
            dataset_source = prov.dataset_name if prov else "licensed_ai_exposure_reference"
            for t in request.task_exposure_records:
                ev_id = t.evidence_source_id
                if not ev_id:
                    continue
                evidence.append(EvidenceItem(
                    evidence_id=ev_id,
                    source=t.evidence_source or dataset_source,
                    signal_type="task_exposure_reference",
                    period=str(t.evidence_date) if t.evidence_date else None,
                    data_origin="real",
                    history_type="licensed_reference_dataset",
                    quality=t.evidence_strength if t.evidence_strength != "unknown" else "valid",
                    description=f"Task exposure assessment for '{t.task_statement}' ({t.task_exposure_level} exposure; {t.evidence_rationale or 'reference evidence'}).",
                ))
            task_evidence = [item for item in evidence if item.signal_type == "task_exposure_reference"]
            if task_evidence:
                facts.append(StructuredFact(
                    fact_id=f"fact_task_ev_summary_{len(task_evidence)}",
                    fact_type="task_exposure_evidence_summary",
                    entity_name=plan.context_summary.get("primary_entity") or "Task Exposure Evidence",
                    canonical_entity_id=None,
                    entity_type="evidence",
                    metric_name="task_exposure_evidence_count",
                    metric_value=len(task_evidence),
                    unit="records",
                    source=dataset_source,
                    data_origin="real",
                    quality_state="valid",
                    readiness_state="ready",
                    evidence_reference=task_evidence[0].evidence_id,
                    details={
                        "dataset_id": prov.dataset_id if prov else "unknown",
                        "license_name": prov.license_name if prov else "unknown",
                    },
                ))

        summary_fact = next((fact for fact in facts if fact.fact_type == "evidence_summary"), None)
        if summary_fact is not None:
            summary_fact.metric_value = len(evidence)
            summary_fact.fact_id = f"fact_ev_summary_{len(evidence)}"
            summary_fact.source = evidence[0].source if evidence else "configured_evidence_stores"
            summary_fact.data_origin = "real" if evidence else "unavailable"
            summary_fact.quality_state = "valid" if evidence else "insufficient_data"
            summary_fact.readiness_state = "ready" if evidence else "insufficient_data"
            summary_fact.evidence_reference = evidence[0].evidence_id if evidence else None
            summary_fact.details = {"reason": None if evidence else missing_reason}

        return facts, evidence, limitations

    def _handle_skill_gap_role_fit(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        from app.analytics.skill_gap import calculate_skill_gap
        from app.analytics.learning_roadmap import build_learning_roadmap

        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = []
        taxonomy = str(request.context_override.get("taxonomy") or "").casefold()
        if not taxonomy:
            taxonomy_match = re.search(r"\b(esco|o\*?net)\b", request.message, re.IGNORECASE)
            taxonomy = "esco" if taxonomy_match and taxonomy_match.group(1).casefold() == "esco" else "onet"
        if taxonomy in {"o*net", "o net"}:
            taxonomy = "onet"
        if taxonomy not in {"esco", "onet"}:
            taxonomy = "onet"

        role = request.target_role or (request.selected_roles[0] if len(request.selected_roles) == 1 else None)
        resolved_occupations = []
        ambiguous_occupations = []
        for item in plan.entities:
            canonical = item.canonical_entity
            if canonical and canonical.entity_type == "occupation":
                if canonical.source == "ref_esco_occupations" and taxonomy == "esco":
                    resolved_occupations.append(canonical)
                elif canonical.metadata.get("soc_code") and taxonomy == "onet":
                    resolved_occupations.append(canonical)
            if item.resolution_status == "ambiguous" and (item.candidates or item.entity_type == "occupation"):
                ambiguous_occupations.extend(item.candidates)
        if len(resolved_occupations) == 1:
            occ = resolved_occupations[0]
            role = occ.canonical_name
            occupation_id = (occ.metadata.get("soc_code") or occ.source_record_id) if taxonomy == "onet" else occ.source_record_id
        else:
            occupation_id = None
        if not role:
            facts.append(StructuredFact(
                fact_id="fact_skill_gap_missing_occupation", fact_type="skill_gap_readiness",
                entity_name=None, entity_type="occupation", metric_name="skill_gap_readiness",
                metric_value="missing_target_occupation", unit="status", source=f"ref_{taxonomy}_occupations",
                data_origin="unavailable", quality_state="insufficient_data", readiness_state="insufficient_data",
                details={"clarification": "Which target occupation should I compare your skills with?", "taxonomy": taxonomy},
            ))
            return facts, evidence, ["A skill gap was not calculated because no target occupation was supplied."]
        if len(resolved_occupations) > 1 or (not occupation_id and ambiguous_occupations):
            facts.append(StructuredFact(
                fact_id="fact_skill_gap_ambiguous_occupation", fact_type="skill_gap_readiness",
                entity_name=role, entity_type="occupation", metric_name="skill_gap_readiness",
                metric_value="ambiguous_target_occupation", unit="status", source=f"ref_{taxonomy}_occupations",
                data_origin="unavailable", quality_state="insufficient_data", readiness_state="insufficient_data",
                details={"clarification": "Which exact occupation did you mean?", "taxonomy": taxonomy,
                         "candidates": [getattr(candidate, "canonical_name", str(candidate)) for candidate in ambiguous_occupations[:5]]},
            ))
            return facts, evidence, ["No gap calculation was made against an ambiguous occupation."]

        if not occupation_id:
            if taxonomy == "esco":
                occupations = self.reference_store.get_esco_occupations(query=role, limit=10)
                matches = [row for row in occupations if row["preferred_label"].casefold() == role.casefold()]
                if len(matches) == 1:
                    occupation_id = matches[0]["concept_uri"]
                    role = matches[0]["preferred_label"]
            else:
                matches = self.reference_store.get_onet_occupations(title=role, limit=100)
                exact = [row for row in matches if row.title.casefold().strip() == role.casefold().strip()]
                if len(exact) == 1:
                    occupation_id = exact[0].soc_code
                    role = exact[0].title
        if not occupation_id:
            facts.append(StructuredFact(
                fact_id="fact_skill_gap_unresolved_occupation", fact_type="skill_gap_readiness",
                entity_name=role, entity_type="occupation", metric_name="skill_gap_readiness",
                metric_value="unresolved_target_occupation", unit="status", source=f"ref_{taxonomy}_occupations",
                data_origin="unavailable", quality_state="insufficient_data", readiness_state="insufficient_data",
                details={"clarification": "Please choose an exact occupation label from the selected taxonomy.", "taxonomy": taxonomy},
            ))
            return facts, evidence, ["No fallback or related occupation was used."]

        if taxonomy == "esco":
            occ_rows = self.reference_store.get_esco_occupations(concept_uri=occupation_id, limit=1)
            reference_rows = [
                {**row, "source": "ref_esco_occupation_skill_relations"}
                for row in self.reference_store.get_esco_occupation_skills(occupation_id, limit=500)
            ]
            occupation = {"label": role, "taxonomy_id": occupation_id, "taxonomy": taxonomy}
        else:
            occ_rows = self.reference_store.get_onet_occupations(code=occupation_id)
            reference_rows = self.reference_store.get_onet_essential_skills_by_occupation(occupation_id, limit=500)
            occupation = {"label": role, "taxonomy_id": occupation_id, "taxonomy": taxonomy}
            reference_rows = [{**row, "preferred_label": row.get("element_name"), "source": "ref_onet_essential_skills"} for row in reference_rows]
        if not occ_rows or not reference_rows:
            facts.append(StructuredFact(
                fact_id=f"fact_skill_gap_no_reference_{hashlib.sha1(str(occupation_id).encode()).hexdigest()[:10]}",
                fact_type="skill_gap_readiness", entity_name=role, canonical_entity_id=str(occupation_id),
                entity_type="occupation", metric_name="skill_gap_readiness", metric_value="reference_skills_unavailable",
                unit="status", source=f"ref_{taxonomy}_occupation_skill_relations", data_origin="unavailable",
                quality_state="unavailable", readiness_state="insufficient_data",
                details={"taxonomy": taxonomy, "reference_record_count": len(reference_rows)},
            ))
            return facts, evidence, ["The selected occupation has no locally available reference-skill records; no gap was calculated."]

        user_skills = list(request.selected_skills)
        for item in plan.entities:
            canonical = item.canonical_entity
            if canonical and canonical.entity_type in {"skill", "technology"}:
                user_skills.append(canonical.canonical_name)
        # Recover explicitly stated skill lists in natural language while retaining labels as supplied.
        stated = re.search(r"\b(?:i\s+(?:know|have|already know)|my\s+skills\s+(?:are|include))\s+(.+?)(?=\s*[.!?]|\s+(?:what|which)\s+(?:should|can)|$)", request.message, re.IGNORECASE)
        if stated:
            user_skills.extend(re.split(r"\s*(?:,|;|\band\b|\bor\b)\s*", stated.group(1), flags=re.IGNORECASE))
        dedup_skills = list(dict.fromkeys(skill.strip() for skill in user_skills if isinstance(skill, str) and skill.strip()))
        profile = request.context_override.get("_authenticated_learning_profile")
        if not dedup_skills and isinstance(profile, dict) and request.context_override.get("_learning_profile_state") == "available":
            dedup_skills = [str(item).strip() for item in profile.get("skills", []) if isinstance(item, str) and item.strip()]
        if not dedup_skills:
            facts.append(StructuredFact(
                fact_id="fact_skill_gap_missing_user_skills", fact_type="skill_gap_readiness",
                entity_name=role, canonical_entity_id=str(occupation_id), entity_type="occupation",
                metric_name="skill_gap_readiness", metric_value="missing_user_skills", unit="status",
                source=f"ref_{taxonomy}_occupation_skill_relations", data_origin="real",
                quality_state="insufficient_data", readiness_state="insufficient_data",
                details={"clarification": "Which skills do you currently have? You can list them in your question.", "taxonomy": taxonomy},
            ))
            return facts, evidence, ["A personalized comparison requires current skills supplied in the question or an available authenticated profile."]
        source = "ref_esco_occupation_skill_relations" if taxonomy == "esco" else "ref_onet_essential_skills"
        result = calculate_skill_gap(taxonomy=taxonomy, occupation=occupation, reference_skills=reference_rows, user_skills=dedup_skills)
        if result["unresolved_user"]:
            unresolved = result["unresolved_user"]
            facts.append(StructuredFact(
                fact_id=f"fact_skill_gap_ambiguous_skill_{hashlib.sha1(str(occupation_id).encode()).hexdigest()[:10]}",
                fact_type="skill_gap_readiness", entity_name=role, canonical_entity_id=str(occupation_id),
                entity_type="occupation", metric_name="skill_gap_readiness", metric_value="ambiguous_user_skill",
                unit="status", source=source, data_origin="real", quality_state="insufficient_data",
                readiness_state="requires_clarification", provenance_id=str(occupation_id),
                details={"clarification": "One or more supplied skills match multiple taxonomy records. Which exact skill did you mean?",
                         "taxonomy": taxonomy, "unresolved_user_skills": unresolved},
            ))
            return facts, evidence, ["No gap was calculated for an ambiguous user skill until it is clarified."]
        for item in result["missing"]:
            item["source"] = source
        roadmap = build_learning_roadmap(result)
        evidence_id = f"ev_skill_gap_{hashlib.sha256(str(occupation_id).encode()).hexdigest()[:14]}"
        evidence.append(EvidenceItem(
            evidence_id=evidence_id, source=source, signal_type="occupation_skill_reference",
            data_origin="real", history_type="reference_taxonomy", provenance_id=str(occupation_id), quality="valid",
            description=f"Local {taxonomy.upper()} reference skills for {role}; comparison is label-based and does not assess proficiency.",
        ))
        facts.append(StructuredFact(
            fact_id=f"fact_skill_gap_{hashlib.sha256(str(occupation_id).encode()).hexdigest()[:14]}",
            fact_type="personalized_skill_gap", entity_name=role, canonical_entity_id=str(occupation_id),
            entity_type="occupation", metric_name="reference_skill_coverage", metric_value=result["coverage"],
            unit="fraction", denominator=result["reference_count"], source=source, data_origin="real",
            history_type="reference_taxonomy", quality_state="valid", readiness_state="ready",
            provenance_id=str(occupation_id), evidence_reference=evidence_id,
            details={**result, "user_skills": dedup_skills,
                     "coverage_numerator": result["matched_reference_count"],
                     "coverage_percent": round(result["coverage"] * 100, 2) if result["coverage"] is not None else None,
                     "learning_roadmap": roadmap,
                     "interpretation": "Reference-skill coverage only; not employability, job readiness, hiring probability, or a proficiency assessment."},
        ))
        # Keep the historic fact type available to existing API consumers while
        # giving it the new taxonomy-grounded meaning and detail contract.
        facts.append(StructuredFact(
            fact_id=f"fact_skill_gap_legacy_{hashlib.sha256(str(occupation_id).encode()).hexdigest()[:14]}",
            fact_type="skill_gap", entity_name=role, canonical_entity_id=str(occupation_id),
            entity_type="occupation", metric_name="missing_reference_skill_count",
            metric_value=len(result["missing"]), unit="reference skills", source=source,
            data_origin="real", history_type="reference_taxonomy", quality_state="valid",
            readiness_state="ready", provenance_id=str(occupation_id), evidence_reference=evidence_id,
            details={"backward_compatible_alias": True, "taxonomy": taxonomy,
                     "matched_count": result["matched_reference_count"], "reference_count": result["reference_count"],
                     "coverage_formula": result["coverage_formula"]},
        ))
        for step in roadmap["steps"]:
            rank = step["priority"]
            gap = next(item for item in result["missing"] if item["taxonomy_id"] == step["taxonomy_id"])
            gap["source"] = source
            evidence.append(EvidenceItem(
                evidence_id=f"{evidence_id}_{rank}", source=source, signal_type="occupation_skill_reference",
                data_origin="real", history_type="reference_taxonomy", provenance_id=gap["source_record_id"], quality="valid",
                description=f"{gap['label']} is listed in the selected occupation's {taxonomy.upper()} reference record.",
            ))
            facts.append(StructuredFact(
                fact_id=f"fact_gap_action_{hashlib.sha256((str(occupation_id)+gap['source_record_id']).encode()).hexdigest()[:12]}",
                fact_type="action_recommendation", entity_name=gap["label"], canonical_entity_id=gap["taxonomy_id"],
                entity_type="skill", metric_name="suggested_practice_action", metric_value=gap["label"],
                unit="suggested action", source=source, data_origin="real", history_type="reference_taxonomy",
                quality_state="valid", readiness_state="ready", provenance_id=gap["source_record_id"],
                evidence_reference=f"{evidence_id}_{rank}", details={
                    "target_role": role, "taxonomy": taxonomy, "classification": gap["classification"],
                    "reason": gap["priority_rationale"],
                    "suggested_action": step["suggested_task"],
                    "action_is_suggestion_not_verified_outcome": True,
                    "learning_roadmap_step": step,
                },
            ))
            facts.append(StructuredFact(
                fact_id=f"fact_roadmap_{hashlib.sha256((str(occupation_id)+gap['source_record_id']).encode()).hexdigest()[:12]}",
                fact_type="learning_roadmap_step", entity_name=gap["label"], canonical_entity_id=gap["taxonomy_id"],
                entity_type="skill", metric_name="suggested_practice_step", metric_value=step,
                unit="suggested step", source=source, data_origin="real", history_type="reference_taxonomy",
                quality_state="valid", readiness_state="ready", provenance_id=gap["source_record_id"],
                evidence_reference=f"{evidence_id}_{rank}", details=step,
            ))
        if len(result["missing"]) > 10:
            limitations.append(
                f"The reference set contains {len(result['missing'])} missing labels; suggested practice actions are shown for the first 10 only."
            )
        limitations.extend([
            *roadmap["limitations"],
            "Current skills are self-reported; a text match does not verify proficiency.",
            "Reference-skill coverage is not employability, job readiness, a hiring probability, or an assessment score.",
            "No current job-market evidence or verified learning-resource catalogue is used to rank or name courses.",
        ])
        return facts, evidence, limitations

    def _handle_action_recommendations(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        return self._build_learning_recommendations(request, plan)

    def _build_learning_recommendations(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        limitations = [
            "O*NET technology mappings are static occupational context, not mandatory role qualifications or current employer demand.",
            "Task exposure, job displacement, hiring outcomes, and course completion time are not inferred.",
            "No course/provider catalog or approved study-time-to-completion method is configured.",
        ]
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []

        target_role = request.target_role
        target_soc: str | None = None
        target_esco_uri: str | None = None
        for entity in plan.entities:
            canonical = entity.canonical_entity
            if canonical and canonical.entity_type == "occupation":
                if canonical.source == "ref_esco_occupations":
                    candidate_uri = canonical.source_record_id
                    if candidate_uri and (
                        not target_role
                        or target_role.casefold().strip() in {
                            canonical.canonical_name.casefold().strip(),
                            entity.raw_token.casefold().strip(),
                            *(alias.casefold().strip() for alias in canonical.aliases),
                        }
                    ):
                        target_esco_uri = str(candidate_uri)
                        target_role = canonical.canonical_name
                candidate_soc = (
                    canonical.metadata.get("soc_code")
                    or (
                        canonical.source_record_id
                        if canonical.source == "ref_onet_occupations"
                        else None
                    )
                )
                entity_tokens = {
                    canonical.canonical_name.casefold().strip(),
                    entity.raw_token.casefold().strip(),
                    *(alias.casefold().strip() for alias in canonical.aliases),
                }
                if candidate_soc and (
                    not target_role
                    or target_role.casefold().strip() in entity_tokens
                ):
                    target_soc = str(candidate_soc)
                    target_role = canonical.canonical_name
                    break

        # An explicitly resolved ESCO occupation must stay within ESCO.  When
        # O*NET has no exact occupation, exact ESCO labels are a supported
        # reference path, not an inferred crosswalk.
        if target_esco_uri:
            return self._build_esco_action_recommendations(
                request, target_role, target_esco_uri
            )

        if not target_role and len(request.selected_roles) == 1:
            target_role = request.selected_roles[0]
        if not target_role:
            profile = request.context_override.get("_authenticated_learning_profile")
            saved_roles = profile.get("target_roles", []) if isinstance(profile, dict) else []
            if len(saved_roles) == 1:
                target_role = str(saved_roles[0])

        if target_role and not target_soc:
            matches = self.reference_store.get_onet_occupations(
                title=target_role, limit=100
            )
            exact_matches = [
                occupation for occupation in matches
                if occupation.title.casefold().strip() == target_role.casefold().strip()
            ]
            if len(exact_matches) == 1:
                target_soc = exact_matches[0].soc_code
                target_role = exact_matches[0].title

        if target_role and not target_soc:
            esco_matches = self.reference_store.get_esco_occupations(
                query=target_role, limit=10
            )
            if len(esco_matches) == 1:
                return self._build_esco_action_recommendations(
                    request,
                    str(esco_matches[0]["preferred_label"]),
                    str(esco_matches[0]["concept_uri"]),
                )

        def readiness_fact(
            reason_code: str,
            message: str,
            *,
            role: str | None = target_role,
            state: str = "insufficient_data",
        ) -> StructuredFact:
            return StructuredFact(
                fact_id=f"fact_learning_readiness_{reason_code.casefold()}",
                fact_type="learning_recommendation_readiness",
                entity_name=role,
                canonical_entity_id=target_soc,
                entity_type="occupation" if role else None,
                metric_name="learning_recommendation_readiness",
                metric_value=reason_code,
                source="ref_onet_software_skills",
                data_origin="unavailable" if state == "unavailable" else "real",
                history_type="reference_taxonomy",
                quality_state=state,
                readiness_state=state,
                provenance_id=target_soc,
                details={"reason_code": reason_code, "message": message},
            )

        if not target_role:
            facts.append(readiness_fact(
                "MISSING_TARGET_ROLE",
                "Choose one target role or add a single target role to your individual profile.",
                role=None,
            ))
            return facts, evidence, [
                *limitations,
                "A personal skill gap cannot be calculated until a target role is selected.",
            ]
        if not target_soc:
            facts.append(readiness_fact(
                "UNRESOLVED_TARGET_ROLE",
                f"No exact O*NET occupation match was found for '{target_role}'.",
            ))
            return facts, evidence, [
                *limitations,
                "The role label could not be resolved to a verified occupation identifier; no fallback occupation was used.",
            ]

        occupation_rows = self.reference_store.get_onet_occupations(code=target_soc)
        if not occupation_rows:
            facts.append(readiness_fact(
                "OCCUPATION_RECORD_UNAVAILABLE",
                f"The resolved occupation record for '{target_role}' is not available locally.",
                state="unavailable",
            ))
            return facts, evidence, limitations
        occupation = occupation_rows[0]
        target_role = occupation.title
        mappings = self.reference_store.get_onet_software_skills_by_occupation(
            target_soc, limit=500
        )
        if not mappings:
            facts.append(readiness_fact(
                "NO_ROLE_TECHNOLOGY_MAPPINGS",
                f"No O*NET software/technology mappings are available for '{target_role}'.",
                state="unavailable",
            ))
            return facts, evidence, [
                *limitations,
                "No supported role-to-technology mapping was found, so no skill-gap or learning recommendation was generated.",
            ]

        profile = request.context_override.get("_authenticated_learning_profile")
        profile = profile if isinstance(profile, dict) else {}
        profile_available = bool(
            request.context_override.get("_learning_profile_state") == "available"
            and profile.get("uid")
        )
        profile_skill_source = request.context_override.get("_learning_skill_source") or (
            "authenticated_individual_profile" if profile_available else
            "request_supplied_skills" if request.selected_skills else "not_provided"
        )
        profile_skills = {
            " ".join(skill.strip().casefold().split())
            for skill in request.selected_skills
            if isinstance(skill, str) and skill.strip()
        }
        profile_skill_ids = {
            canonical_skill_id(skill)
            for skill in request.selected_skills
            if canonical_skill_id(skill)
        }
        if not profile_available and request.selected_skills:
            limitations.append(
                "The compared skills were explicitly supplied for this request and are not represented as a verified saved profile."
            )
        elif not profile_available:
            limitations.append(
                "No authenticated individual skill profile was available; these are role-associated technologies to explore, not personalized gaps."
            )
        elif request.context_override.get("_learning_profile_state") == "unavailable":
            limitations.append(
                "The authenticated profile could not be read; no saved skills or study preferences were assumed."
            )

        normalized_mappings: list[dict[str, Any]] = []
        seen_mapping_ids: set[str] = set()
        for mapping in mappings:
            name = " ".join(str(mapping.get("workplace_example") or "").split())
            if not name:
                continue
            skill_id = mapping.get("canonical_skill_id") or canonical_skill_id(name)
            normalized_name = name.casefold()
            if skill_id:
                mapping_key = f"skill:{skill_id}"
            else:
                mapping_key = f"technology:{normalized_name}"
            if mapping_key in seen_mapping_ids:
                continue
            seen_mapping_ids.add(mapping_key)
            mapping["canonical_skill_id"] = skill_id
            mapping["workplace_example"] = name
            mapping["_matched_profile"] = (
                (bool(skill_id) and skill_id in profile_skill_ids)
                or normalized_name in profile_skills
            )
            normalized_mappings.append(mapping)

        candidates = [
            mapping for mapping in normalized_mappings
            if not mapping["_matched_profile"]
        ]
        resolved_mappings = [mapping for mapping in normalized_mappings if mapping.get("canonical_skill_id")]
        matched_mappings = [mapping for mapping in resolved_mappings if mapping["_matched_profile"]]
        missing_mappings = [mapping for mapping in resolved_mappings if not mapping["_matched_profile"]]
        unresolved_mappings = [mapping for mapping in normalized_mappings if not mapping.get("canonical_skill_id")]
        has_profile_comparison = profile_available or bool(request.selected_skills)
        profile_comparison_source = (
            "authenticated_self_reported_profile"
            if profile_skill_source == "authenticated_individual_profile"
            else "request_supplied_skills"
        )
        role_associated_coverage = (
            round(len(matched_mappings) / len(resolved_mappings) * 100, 2)
            if has_profile_comparison and resolved_mappings else None
        )
        ranking_method = (
            "Deterministic lexicographic baseline: use only mappings for the resolved "
            "occupation; exclude labels already present in the compared skill list; "
            "then order by the existing O*NET Hot Technology flag (true first), "
            "O*NET In Demand flag (true first), normalized label, and mapping ID. "
            "These static source flags are occupational context, not current market "
            "demand. Verified market trends are cited separately and do not affect rank. "
            "No numeric score or weights are applied."
        )
        candidates.sort(key=lambda mapping: (
            not bool(mapping.get("hot_technology")),
            not bool(mapping.get("in_demand")),
            str(mapping["workplace_example"]).casefold(),
            str(mapping.get("id") or ""),
        ))
        selected_candidates = candidates[:10]
        evidence_by_mapping: dict[str, str] = {}
        for mapping in selected_candidates:
            evidence_id = f"ev_onet_software_{mapping.get('id') or target_soc}"
            evidence_by_mapping[str(mapping.get("id") or mapping["workplace_example"])] = evidence_id
            flags = []
            if mapping.get("hot_technology"):
                flags.append("Hot Technology")
            if mapping.get("in_demand"):
                flags.append("In Demand")
            flag_text = ", ".join(flags) if flags else "neither static flag is set"
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source="ref_onet_software_skills",
                signal_type="occupation_technology_mapping",
                data_origin="real",
                history_type="reference_taxonomy",
                provenance_id=str(mapping.get("id") or target_soc),
                source_url="https://www.onetcenter.org/database.html",
                quality="valid",
                description=(
                    f"O*NET software/technology mapping for SOC {target_soc} "
                    f"({target_role}), Database version 29.x / 30.0, CC BY 4.0: "
                    f"{mapping['workplace_example']}; "
                    f"source flags: {flag_text}."
                ),
            ))

        market_observations: list[MarketObservation] = []
        market_source_unavailable = False
        try:
            for mapping in selected_candidates:
                if not mapping.get("canonical_skill_id"):
                    continue
                market_observations.extend(self._get_market_observations(
                    request_obs=None,
                    skill=mapping["workplace_example"],
                    location=request.location,
                    time_range=request.time_range,
                    signal_type="demand",
                ))
        except DataSourceUnavailableError:
            market_source_unavailable = True
        market_analysis = analyze_market_observations(market_observations)
        valid_market_by_skill: dict[str, list[tuple[Any, str, list[str]]]] = {}
        observation_by_id = {
            observation.id: observation
            for observation in market_analysis.observations
            if observation.id
        }
        for trend in market_analysis.trend_results:
            if (
                trend.signal_type != "demand"
                or trend.data_origin != "real"
                or trend.readiness_state not in {"ready", "ready_for_trend"}
                or trend.data_state not in {"ready", "fresh"}
            ):
                continue
            relevant_ids = [
                observation_id for observation_id in trend.observation_ids
                if observation_id in observation_by_id
            ]
            if not relevant_ids:
                continue
            evidence_id = "ev_market_trend_" + hashlib.sha256(
                f"{trend.source}|{trend.canonical_skill_id}|{trend.series_id}|"
                f"{trend.query_id}|{trend.panel_version}|{','.join(trend.periods_used)}".encode()
            ).hexdigest()[:16]
            valid_market_by_skill.setdefault(
                trend.canonical_skill_id or trend.canonical_name.casefold(), []
            ).append((trend, evidence_id, relevant_ids))
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source=trend.source,
                signal_type="verified_demand_trend",
                measured_signal_type="demand",
                period=trend.latest_period,
                unit=trend.unit,
                data_origin=trend.data_origin,
                history_type=trend.history_type,
                series_id=trend.series_id,
                location=trend.location,
                scope=trend.scope,
                query_id=trend.query_id,
                panel_version=trend.panel_version,
                supporting_observation_ids=relevant_ids,
                supporting_fetch_run_ids=trend.fetch_run_ids,
                provenance_id=trend.canonical_skill_id,
                quality=trend.data_state,
                description=(
                    f"Validated {trend.trend.lower()} demand trend for "
                    f"{trend.canonical_name} from {trend.source}, covering "
                    f"{', '.join(trend.periods_used)}."
                ),
            ))

        for rank, mapping in enumerate(selected_candidates, start=1):
            name = mapping["workplace_example"]
            skill_id = mapping.get("canonical_skill_id")
            match_key = skill_id or name.casefold()
            trend_records = valid_market_by_skill.get(match_key, [])
            taxonomy_evidence_id = evidence_by_mapping[
                str(mapping.get("id") or name)
            ]
            for trend, trend_evidence_id, _ in trend_records:
                facts.append(StructuredFact(
                    fact_id=f"fact_learning_market_{hashlib.sha256(trend_evidence_id.encode()).hexdigest()[:12]}",
                    fact_type="learning_market_evidence",
                    entity_name=name,
                    canonical_entity_id=skill_id,
                    entity_type="skill" if skill_id else "technology",
                    metric_name="validated_demand_trend",
                    metric_value=trend.trend,
                    unit="trend_direction",
                    period=trend.latest_period,
                    source=trend.source,
                    data_origin=trend.data_origin,
                    history_type=trend.history_type,
                    quality_state=trend.data_state,
                    readiness_state=trend.readiness_state,
                    calculation_version=trend.calculation_version,
                    provenance_id=skill_id,
                    evidence_reference=trend_evidence_id,
                    details={
                        "periods_used": trend.periods_used,
                        "metric": trend.metric,
                        "market_relevance_is_separate_from_role_mapping": True,
                    },
                ))
            mapping_id = str(mapping.get("id") or name)
            rationale = (
                f"O*NET associates this technology with {target_role}. "
                f"Static flags: Hot Technology={bool(mapping.get('hot_technology'))}, "
                f"In Demand={bool(mapping.get('in_demand'))}."
            )
            if trend_records:
                rationale += " Separate validated demand-trend evidence is available from "
                rationale += "; ".join(
                    f"{trend.source} ({trend.trend.lower()} through {trend.latest_period})"
                    for trend, _, _ in trend_records
                )
                rationale += "."
            else:
                rationale += (
                    " No eligible market demand evidence was available; this recommendation is based on occupational "
                    "association only."
                )
            facts.append(StructuredFact(
                fact_id=f"fact_learning_candidate_{hashlib.sha256((target_soc + mapping_id).encode()).hexdigest()[:12]}",
                fact_type="action_recommendation",
                entity_name=name,
                canonical_entity_id=skill_id,
                entity_type="skill" if skill_id else "technology",
                metric_name="role_associated_learning_candidate",
                metric_value=name,
                source="ref_onet_software_skills",
                data_origin="real",
                history_type="reference_taxonomy",
                quality_state="valid",
                readiness_state="ready",
                provenance_id=mapping_id,
                evidence_reference=taxonomy_evidence_id,
                details={
                    "action_type": "explore_learning",
                    "target_role": target_role,
                    "reason": rationale,
                    "recommendation_rank": rank,
                    "next_action": (
                        "Choose a verified learning resource or define a small practice task "
                        "for this technology; no course catalog is configured."
                    ),
                    "taxonomy_hot_technology": bool(mapping.get("hot_technology")),
                    "taxonomy_in_demand": bool(mapping.get("in_demand")),
                    "taxonomy_flags_are_static": True,
                    "market_trend_available": bool(trend_records),
                    "market_trend_used_for_ranking": False,
                    "market_evidence_references": [record[1] for record in trend_records],
                    "market_evidence_limitation": (
                        None if trend_records else
                        "No eligible, comparable real demand trend was available for this skill in the selected window."
                    ),
                    "profile_comparison": (
                        "unmatched_to_authenticated_profile"
                        if profile_available
                        else "unmatched_to_request_skill_list"
                        if request.selected_skills
                        else "not_assessed"
                    ),
                    "ranking_method": ranking_method,
                    "prerequisite_data_available": False,
                    "weekly_learning_time": profile.get("weekly_learning_time"),
                    "learning_preferences": profile.get("learning_preferences", []),
                },
            ))

        summary_evidence_id = f"ev_onet_role_summary_{target_soc}"
        evidence.append(EvidenceItem(
            evidence_id=summary_evidence_id,
            source="ref_onet_software_skills",
            signal_type="occupation_technology_coverage",
            data_origin="real",
            history_type="reference_taxonomy",
            provenance_id=target_soc,
            quality="valid",
            description=(
                f"Bounded O*NET software/technology mappings retrieved for SOC {target_soc} "
                f"({target_role}); {len(normalized_mappings)} distinct mapping labels were available."
            ),
        ))
        facts.append(StructuredFact(
            fact_id=f"fact_learning_summary_{target_soc}",
            fact_type="learning_recommendation_summary",
            entity_name=target_role,
            canonical_entity_id=f"occupation:soc:{target_soc}",
            entity_type="occupation",
            metric_name="unmatched_role_technology_mapping_count",
            metric_value=len(candidates),
            unit="technology mappings",
            source="ref_onet_software_skills",
            data_origin="real",
            history_type="reference_taxonomy",
            quality_state="valid",
            readiness_state="ready" if candidates else "insufficient_data",
            provenance_id=target_soc,
            evidence_reference=summary_evidence_id,
            details={
                "profile_skill_source": profile_skill_source,
                "profile_skills_provided": bool(request.selected_skills),
                "profile_available": bool(profile_available),
                "profile_skill_levels": (
                    profile.get("skill_levels", {})
                    if profile_available and isinstance(profile.get("skill_levels"), dict)
                    else {}
                ),
                "profile_skill_levels_are_self_reported": bool(profile_available),
                "profile_skill_levels_used_for_ranking": False,
                "role_associated_skill_overlap": {
                    "status": "available" if role_associated_coverage is not None else "incomplete",
                    "score_pct": role_associated_coverage,
                    "formula": "matched canonical O*NET mappings / resolved O*NET mappings * 100",
                    "matched_count": len(matched_mappings),
                    "resolved_mapping_count": len(resolved_mappings),
                    "interpretation": (
                        "Overlap with occupation-associated software mappings only; these mappings are not mandatory qualifications and do not establish employability."
                    ),
                },
                "matched_associated_skills": [
                    {
                        "skill": item["workplace_example"],
                        "canonical_skill_id": item["canonical_skill_id"],
                        "mapping_id": item.get("id"),
                        "profile_evidence": profile_comparison_source,
                    }
                    for item in matched_mappings[:100]
                ],
                "missing_associated_skills": [
                    {
                        "skill": item["workplace_example"],
                        "canonical_skill_id": item["canonical_skill_id"],
                        "mapping_id": item.get("id"),
                        "meaning": (
                            "not present in compared skills; not a verified qualification gap"
                        ),
                    }
                    for item in missing_mappings[:100]
                ],
                "unresolved_requirements": [
                    {
                        "label": item["workplace_example"],
                        "mapping_id": item.get("id"),
                        "reason": "no canonical skill mapping is available",
                    }
                    for item in unresolved_mappings[:100]
                ],
                "level_gaps": {
                    "status": "unavailable",
                    "items": [],
                    "reason": "O*NET technology mappings do not provide required proficiency levels; saved profile levels are self-reported.",
                },
                "mapping_detail_truncated": any(
                    len(items) > 100 for items in (matched_mappings, missing_mappings, unresolved_mappings)
                ),
                "proficiency_limit": (
                    "The occupation mapping does not specify required proficiency levels; "
                    "saved levels are self-reported and are not used to score candidates."
                ),
                "mapping_count": len(normalized_mappings),
                "candidate_count": len(candidates),
                "returned_candidate_count": len(selected_candidates),
                "omitted_candidate_count": max(0, len(candidates) - len(selected_candidates)),
                "candidate_list_bounded": len(mappings) >= 500,
                "ranking_method": ranking_method,
                "prerequisite_data_available": False,
                "learning_resource_catalog_available": False,
                "role_mapping_semantics": "occupational software/technology context, not mandatory qualifications",
                "source_version": "O*NET 29.x / 30.0 as labeled by the staged manifest",
                "reason_code": (
                    "NO_UNMATCHED_ROLE_TECHNOLOGY_MAPPINGS"
                    if not candidates else None
                ),
                "weekly_learning_time": profile.get("weekly_learning_time"),
                "learning_preferences": profile.get("learning_preferences", []),
            },
        ))

        if not any(item.signal_type == "verified_demand_trend" for item in evidence):
            limitations.append(
                "No comparable, ready, real demand trend was available for the returned candidates in the selected time window; no market-based priority is asserted."
            )
        if market_source_unavailable:
            limitations.append(
                "The configured market evidence source was unavailable; role-associated taxonomy candidates were returned without a market-demand claim."
            )
        if len(mappings) >= 500:
            limitations.append(
                "The local O*NET technology mapping read reached its bounded 500-row limit; additional mappings may be omitted."
            )
        if len(candidates) > len(selected_candidates):
            limitations.append(
                "The learning-candidate list is bounded to 10 mappings in the documented source-flag and name order; remaining matches are not included."
            )
        if not candidates:
            limitations.append(
                "No unmatched O*NET technology mappings were found; this does not establish complete role readiness or prove that no other skills are needed."
            )
        if not profile.get("weekly_learning_time"):
            limitations.append(
                "No weekly study-time preference is recorded; no time allocation or completion schedule is inferred."
            )
        limitations.append(
            "O*NET mappings do not include required proficiency levels or learning prerequisites; "
            "self-reported levels do not alter the candidate order."
        )
        limitations.append(
            "The returned order is an exploration priority, not a prerequisite-based learning sequence."
        )
        return facts, evidence, limitations

    def _build_esco_action_recommendations(
        self,
        request: CoreIntelligenceAnswerRequest,
        target_role: str,
        occupation_uri: str,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        """Build evidence-linked practice suggestions from ESCO role relations.

        If the user has not supplied a skill list, suggestions are explicitly
        general role-associated practice priorities, never personalized gaps.
        """
        source = "ref_esco_occupation_skill_relations"
        occupation_rows = self.reference_store.get_esco_occupations(
            concept_uri=occupation_uri, limit=1
        )
        relationships = self.reference_store.get_esco_occupation_skills(
            occupation_uri, limit=500
        )
        limitations = [
            "ESCO relationships are static taxonomy context, not current employer demand, mandatory qualifications, or verified proficiency.",
            "No verified course or provider catalogue is configured; suggestions are practice prompts, not course recommendations.",
            "No ESCO-to-O*NET crosswalk is inferred. This result uses the exact ESCO occupation URI and its local relationships.",
        ]
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []

        def readiness(code: str, message: str, state: str = "insufficient_data") -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
            facts.append(StructuredFact(
                fact_id=f"fact_esco_learning_readiness_{hashlib.sha1((occupation_uri + code).encode()).hexdigest()[:12]}",
                fact_type="learning_recommendation_readiness",
                entity_name=target_role,
                canonical_entity_id=occupation_uri,
                entity_type="occupation",
                metric_name="learning_recommendation_readiness",
                metric_value=code,
                unit="status",
                source="ref_esco_occupations",
                data_origin="real" if occupation_rows else "unavailable",
                history_type="reference_taxonomy",
                quality_state=state,
                readiness_state=state,
                provenance_id=occupation_uri,
                details={"reason_code": code, "message": message, "taxonomy": "esco"},
            ))
            return facts, evidence, limitations

        if not occupation_rows:
            return readiness("ESCO_OCCUPATION_UNAVAILABLE", "The resolved ESCO occupation record is no longer available locally.", "unavailable")
        if not relationships:
            return readiness("ESCO_ROLE_SKILLS_UNAVAILABLE", "No ESCO occupation-skill relationships are available for this occupation.", "unavailable")

        supplied_skills = list(request.selected_skills)
        profile = request.context_override.get("_authenticated_learning_profile")
        profile = profile if isinstance(profile, dict) else {}
        profile_available = bool(
            request.context_override.get("_learning_profile_state") == "available"
            and profile.get("uid")
        )
        if not supplied_skills and profile_available:
            supplied_skills = [str(value) for value in profile.get("skills", []) if isinstance(value, str) and value.strip()]

        selected: list[dict[str, Any]]
        recommendation_basis: str
        matched_ids: set[str] = set()
        if supplied_skills:
            from app.analytics.skill_gap import calculate_skill_gap
            from app.analytics.learning_roadmap import build_learning_roadmap

            gap = calculate_skill_gap(
                taxonomy="esco",
                occupation={"label": target_role, "taxonomy_id": occupation_uri, "taxonomy": "esco"},
                reference_skills=[{**row, "source": source} for row in relationships],
                user_skills=supplied_skills,
            )
            if gap["unresolved_user"]:
                return readiness(
                    "AMBIGUOUS_USER_SKILL",
                    "One or more supplied skills match multiple ESCO records; clarify those labels before calculating personalized practice priorities.",
                )
            if gap["unmatched_user"]:
                return readiness(
                    "UNRESOLVED_USER_SKILL",
                    "One or more supplied skill labels do not match this occupation's ESCO relationship records. No personalized gap or action was inferred; provide labels that match the selected taxonomy records or request general role-associated practice priorities.",
                )
            matched_ids = {str(item["taxonomy_id"]) for item in gap["matched"]}
            selected = [row for row in relationships if str(row.get("skill_uri")) not in matched_ids]
            recommendation_basis = "unmatched_esco_reference_relationships_for_supplied_skills"
            if not selected:
                selected = []
            roadmap = build_learning_roadmap(gap)
            roadmap_by_id = {str(step.get("taxonomy_id")): step for step in roadmap["steps"]}
        else:
            selected = [row for row in relationships if str(row.get("relation_type") or "").casefold() == "essential"]
            recommendation_basis = "general_essential_esco_role_relationships_no_personal_gap_assessed"
            roadmap_by_id = {}
            limitations.append(
                "No authenticated or request-supplied skill list was available; these are general essential role-associated practice priorities, not personalized skill gaps."
            )

        # Preserve ESCO essential/optional ranking and cap the response.
        selected.sort(key=lambda row: (
            0 if str(row.get("relation_type") or "").casefold() == "essential" else 1,
            str(row.get("preferred_label") or row.get("skill_label") or "").casefold(),
            str(row.get("skill_uri") or ""),
        ))
        selected = selected[:10]
        for rank, row in enumerate(selected, start=1):
            skill_uri = str(row.get("skill_uri") or "")
            label = str(row.get("preferred_label") or row.get("skill_label") or "").strip()
            if not skill_uri or not label:
                continue
            relation = str(row.get("relation_type") or "unclassified").casefold()
            evidence_id = f"ev_esco_learning_{hashlib.sha256((occupation_uri + skill_uri).encode()).hexdigest()[:14]}"
            evidence.append(EvidenceItem(
                evidence_id=evidence_id,
                source=source,
                signal_type="occupation_skill_reference",
                data_origin="real",
                history_type="reference_taxonomy",
                provenance_id=skill_uri,
                quality="valid",
                description=(
                    f"Local ESCO v{row.get('source_version') or 'unknown'} record links {label} to "
                    f"{target_role} as {relation}; occupation URI {occupation_uri}, skill URI {skill_uri}."
                ),
            ))
            step = roadmap_by_id.get(skill_uri)
            fact_type = "action_recommendation"
            details: dict[str, Any] = {
                "action_type": "practice_skill",
                "target_role": target_role,
                "taxonomy": "esco",
                "classification": relation,
                "recommendation_basis": recommendation_basis,
                "reason": f"ESCO lists this skill as {relation} for {target_role}.",
                "next_action": (
                    step.get("suggested_task") if step else
                    f"Choose a small practice task that uses {label} in a {target_role}-related context."
                ),
                "suggestion_origin": "platform_generated_practice_suggestion",
                "is_personalized_gap": bool(supplied_skills),
                "proficiency_verified": False,
            }
            facts.append(StructuredFact(
                fact_id=f"fact_esco_learning_{hashlib.sha256((occupation_uri + skill_uri).encode()).hexdigest()[:14]}",
                fact_type=fact_type,
                entity_name=label,
                canonical_entity_id=skill_uri,
                entity_type="skill",
                metric_name="esco_role_practice_priority",
                metric_value=label,
                unit="suggested practice",
                source=source,
                data_origin="real",
                history_type="reference_taxonomy",
                quality_state="valid",
                readiness_state="ready",
                provenance_id=skill_uri,
                evidence_reference=evidence_id,
                details=details,
            ))

        if not selected:
            return readiness("NO_ELIGIBLE_PRACTICE_PRIORITIES", "No unmatched ESCO skill relationships remain for the supplied skills.")
        summary_evidence_id = f"ev_esco_learning_role_{hashlib.sha256(occupation_uri.encode()).hexdigest()[:14]}"
        evidence.append(EvidenceItem(
            evidence_id=summary_evidence_id,
            source=source,
            signal_type="occupation_skill_reference_set",
            data_origin="real",
            history_type="reference_taxonomy",
            provenance_id=occupation_uri,
            quality="valid",
            description=f"Retrieved {len(relationships)} local ESCO occupation-skill relationship rows for {target_role}.",
        ))
        facts.append(StructuredFact(
            fact_id=f"fact_esco_learning_summary_{hashlib.sha256(occupation_uri.encode()).hexdigest()[:14]}",
            fact_type="learning_recommendation_summary",
            entity_name=target_role,
            canonical_entity_id=occupation_uri,
            entity_type="occupation",
            metric_name="practice_priority_count",
            metric_value=min(len(selected), 10),
            unit="skills",
            source=source,
            data_origin="real",
            history_type="reference_taxonomy",
            quality_state="valid",
            readiness_state="ready",
            provenance_id=occupation_uri,
            evidence_reference=summary_evidence_id,
            details={
                "taxonomy": "esco",
                "relationship_count": len(relationships),
                "recommendation_basis": recommendation_basis,
                "profile_available": profile_available,
                "personalized_gap_calculated": bool(supplied_skills),
                "resource_catalog_available": False,
            },
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
        scanned_count: int | None = None
        search_matched_count: int | None = None
        stored_city_posting_count: int | None = None
        stored_related_titles: list[str] = []
        stored_requested_city: str | None = None
        missing_city_location_count = 0
        missing_remote_evidence_count = 0
        invalid_application_url_count = 0
        company_query = self._company_query_from_message(request.message) if getattr(plan, "intent", None) == "company_postings_summary" else None
        if self.job_searcher is not None or (not request.observations and self.firestore_store is not None):
            # Job postings have their own normalized Firestore collection. Reuse
            # the existing stored-job search service rather than treating a
            # locally cached observation snapshot as the live postings source.
            from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats
            from app.services.question_classification_service import extract_location

            job_source = "injected_job_search" if self.job_searcher is not None else "firestore_jobs"
            limitations.append("Search returns up to 100 matching stored postings after scanning the stored collection.")
            if self.job_searcher is not None:
                limitations.append("Injected job-search results are test data and are not evidence of real stored postings.")
            query = str(
                company_query
                or request.target_role
                or next(iter(request.selected_roles), None)
                or plan.context_summary.get("primary_entity")
                or next(iter(request.selected_companies), None)
                or ""
            ).strip()
            if request.technology and request.technology.casefold() not in query.casefold():
                query = f"{query} {request.technology}".strip()
            if not query and not re.search(
                r"\b(?:which|what)\s+skills?\b.*\b(?:postings?|jobs?)\b|\bskills?\b.*\b(?:in|from|across)\s+(?:the\s+)?postings?\b",
                request.message,
                re.IGNORECASE,
            ):
                query = request._merged_job_search_query or request.message.strip()
            if not query:
                limitations.append("No keyword was requested; the search reads the matching stored posting sample.")
            country = (request.filters or {}).get("country")
            requested_country = self._extract_question_country(request.message)
            if not requested_country and str(request.location or "").casefold() in {"india", "united states", "united kingdom"}:
                requested_country = request.location
            country_codes = {"india": "in", "united states": "us", "united kingdom": "gb"}
            if not country and requested_country:
                country = country_codes.get(str(requested_country).casefold(), requested_country)
            requested_location = (request.filters or {}).get("location") or request.location or extract_location(request.message)
            if requested_location and requested_location.casefold() in country_codes:
                requested_location = None
            stored_requested_city = requested_location
            remote_requested = bool(
                re.search(r"\bremote\b", request.message, re.IGNORECASE)
                or str((request.filters or {}).get("remote_mode") or "").casefold() == "remote"
            )
            try:
                if self.job_searcher is not None:
                    jobs = self.job_searcher(query=query, country=country, limit=100)
                    scanned_count = len(jobs)
                    search_matched_count = len(jobs)
                else:
                    search_result = search_stored_jsearch_jobs_with_stats(
                        query=query,
                        country=country,
                        location=requested_location,
                        remote=remote_requested,
                        limit=100,
                        firestore_client=getattr(self.firestore_store, "client", None),
                    )
                    jobs = list(search_result)
                    scanned_count = getattr(search_result, "scanned_count", len(jobs))
                    search_matched_count = getattr(search_result, "matched_count", len(jobs))
                    stored_city_posting_count = getattr(search_result, "city_posting_count", None)
                    if search_matched_count == 0:
                        stored_related_titles = getattr(search_result, "related_titles", [])
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
                data_origin="test" if self.job_searcher is not None else "real",
            ) for job in jobs if job.title and job.job_id]
            if requested_location and self.job_searcher is not None:
                from app.services.question_classification_service import LOCATION_ALIASES
                clean_location = LOCATION_ALIASES.get(requested_location.casefold(), requested_location)
                alias_values = {clean_location.casefold()}
                alias_values.update(
                    alias for alias, canonical in LOCATION_ALIASES.items()
                    if canonical.casefold() == clean_location.casefold()
                )
                before_location = all_obs
                missing_city_location_count = sum(1 for o in before_location if not str(o.location or "").strip())
                all_obs = [
                    o for o in before_location
                    if any(alias in (o.location or "").casefold() for alias in alias_values)
                ]
            if request.technology:
                technology_term = request.technology.casefold()
                technology_matches = []
                for observation in all_obs:
                    raw_skills = observation.metadata.get("skills_raw") or []
                    if isinstance(raw_skills, str):
                        raw_skills = [raw_skills]
                    searchable = " ".join((
                        str(observation.metadata.get("job_title") or ""),
                        str(observation.metadata.get("description") or ""),
                        " ".join(str(value) for value in raw_skills),
                    )).casefold()
                    if technology_term in searchable:
                        technology_matches.append(observation)
                all_obs = technology_matches
            date_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            old_posting_ids: set[str] = set()
            unknown_posting_ids: set[str] = set()
            recent_jobs = []
            for observation in all_obs:
                posted = observation.metadata.get("posted_at")
                try:
                    posted_at = datetime.fromisoformat(str(posted).replace("Z", "+00:00")) if posted else None
                except ValueError:
                    posted_at = None
                posting_id = str(observation.posting_id or observation.id or "unknown")
                if posted_at is None:
                    unknown_posting_ids.add(posting_id)
                    continue
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                if posted_at.astimezone(timezone.utc) < date_cutoff:
                    old_posting_ids.add(posting_id)
                    continue
                recent_jobs.append(observation)
            all_obs = recent_jobs
            if remote_requested and self.job_searcher is not None:
                remote_observations = []
                for observation in all_obs:
                    title_text = str(observation.metadata.get("job_title") or "").strip()
                    location_text = str(observation.location or observation.metadata.get("location") or "").strip()
                    remote_evidence = bool(re.search(r"\bremote\b", f"{title_text} {location_text}", re.IGNORECASE))
                    if remote_evidence:
                        remote_observations.append(observation)
                    elif not title_text or not location_text:
                        missing_remote_evidence_count += 1
                all_obs = remote_observations
            excluded_old_postings = len(old_posting_ids)
            unknown_posted_at = len(unknown_posting_ids)
        else:
            excluded_old_postings = 0
            unknown_posted_at = 0
            all_obs = self._get_market_observations(
                request_obs=request.observations,
                skill=plan.context_summary.get("primary_entity"),
                location=request.location,
                time_range=request.time_range,
            )
        raw_obs = [
            o for o in all_obs
            if o.source in {"jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters"} and o.posting_id
            and str(o.metadata.get("job_title") or "").strip()
        ]

        # Enforce Favourites / selected_companies filtering for Job Intelligence
        scope_val = str((request.filters or {}).get("scope") or "").strip().lower()
        scope_empty = bool((request.filters or {}).get("scope_empty"))
        selected_cos_norm = {c.strip().lower() for c in (request.selected_companies or []) if c and c.strip()}
        if company_query:
            selected_cos_norm.add(company_query.casefold().strip())

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
        no_match_alternatives: list[str] = []
        if postings_found == 0 and (request.location or request.technology):
            try:
                from app.services.collected_posting_skills_service import get_collected_posting_skills
                aggregate = get_collected_posting_skills(
                    firestore_client=self.firestore_store.client if self.firestore_store is not None else None,
                )
                from app.services.question_classification_service import LOCATION_ALIASES
                skill_term = str(request.technology or "").casefold()
                requested_city = LOCATION_ALIASES.get(
                    str(request.location or "").casefold(), str(request.location or "")
                ).casefold()
                location_skills = aggregate.get("location_skill_counts") or {}
                if skill_term:
                    for city, rows in location_skills.items():
                        clean_city = LOCATION_ALIASES.get(city.casefold(), city).casefold()
                        if requested_city and clean_city == requested_city:
                            continue
                        match = next((row for row in rows if skill_term in str(row.get("skill", "")).casefold()), None)
                        if match:
                            no_match_alternatives.append(
                                f"{match['skill']} appears in {city} ({match['count']} collected postings)."
                            )
                if not no_match_alternatives and request.location:
                    clean_city = requested_city
                    rows = next(
                        (values for city, values in location_skills.items()
                         if LOCATION_ALIASES.get(city.casefold(), city).casefold() == clean_city),
                        [],
                    )
                    no_match_alternatives.extend(
                        f"{row['skill']} appears in {request.location} ({row['count']} collected postings)."
                        for row in rows[:3]
                    )
                if not no_match_alternatives:
                    no_match_alternatives.extend(
                        f"{row['location']} has {row['count']} stored postings."
                        for row in aggregate.get("location_counts", [])[:3]
                    )
            except Exception as exc:
                logger.debug("Could not build stored-posting alternatives (%s)", type(exc).__name__)
        if excluded_old_postings or unknown_posted_at:
            limitations.append(
                f"Excluded {excluded_old_postings} matching postings older than 90 days and {unknown_posted_at} with unknown posting dates from demand counts."
            )
        if scanned_count is not None:
            limitations.append(
                f"Scanned {scanned_count} stored postings; {postings_found} matched the applied filters. Live provider search is off."
            )
        else:
            limitations.append("The stored scan count is unavailable for this observation-backed result. Live provider search is off.")
        if missing_city_location_count:
            limitations.append(
                f"Excluded {missing_city_location_count} matching stored postings from the city filter because location was missing."
            )
        if missing_remote_evidence_count:
            limitations.append(
                f"Excluded {missing_remote_evidence_count} stored postings from the remote filter because both title and location were missing."
            )
        observed_origins = {item.data_origin for item in obs if item.data_origin}
        job_evidence_origin = (
            "test" if self.job_searcher is not None or observed_origins == {"test"}
            else "real" if observed_origins == {"real"}
            else "mixed" if observed_origins
            else "unavailable"
        )
        sample_postings = []
        structured_postings = []
        extracted_counts: dict[str, dict[str, Any]] = {}
        for o in obs:
            title = str(o.metadata.get("job_title") or "").strip()
            employer = str(o.metadata.get("company") or o.metadata.get("employer_name") or "").strip()
            loc_str = str(o.location or o.metadata.get("location") or "").strip()
            posted_at = str(o.metadata.get("posted_at") or "").strip()[:10] or None
            raw_source_url = str(o.metadata.get("apply_link") or o.metadata.get("job_url") or o.metadata.get("url") or "").strip()
            source_url = raw_source_url if _valid_application_url(raw_source_url) else None
            if source_url is None:
                invalid_application_url_count += 1
            posting_id = o.posting_id or o.id
            extracted = extract_posting_skills({
                "title": title,
                "description": str(o.metadata.get("description") or ""),
                "skills_raw": o.metadata.get("skills_raw"),
            }, reference_store=self.reference_store)
            posting_evidence_id = str(posting_id)
            for skill in extracted:
                skill_key = str(skill.get("entity_id") or skill.get("normalized_name") or "").casefold()
                item = extracted_counts.setdefault(skill_key, {
                    "name": skill.get("normalized_name"),
                    "canonical_skill_id": skill.get("canonical_skill_id"),
                    "entity_id": skill.get("entity_id"),
                    "mapping_status": skill.get("mapping_status"),
                    "reference_source": skill.get("reference_source"),
                    "posting_ids": [],
                    "evidence": [],
                })
                if posting_id not in item["posting_ids"]:
                    item["posting_ids"].append(posting_id)
                item["evidence"].append({
                    "posting_id": posting_id,
                    "evidence_reference": posting_evidence_id,
                    "mentions": skill.get("evidence", []),
                })
            if len(structured_postings) < 100:
                sample_postings.append(f"{title} at {employer} ({loc_str})")
                structured_postings.append({
                "posting_id": o.posting_id or o.id,
                "title": title,
                "company": employer,
                "location": loc_str,
                "posting_date": posted_at,
                "source": o.source,
                "fetch_run_id": o.fetch_run_id,
                "fetched_at": o.observed_at.isoformat() if o.observed_at else None,
                "source_url": source_url,
                "application_link_unavailable": source_url is None,
                "skill": o.skill,
                "summary": str(o.metadata.get("description") or "").strip()[:1200] or None,
                "required_skills": [
                    str(value).strip()[:120]
                    for value in (o.metadata.get("skills_raw") or [])
                    if isinstance(value, str) and value.strip()
                ][:30],
                "extracted_skills": extracted,
                "employment_type": o.metadata.get("employment_type"),
                "category": o.metadata.get("category"),
                })
            evidence.append(EvidenceItem(
                evidence_id=posting_evidence_id,
                source=o.source,
                signal_type="stored_posting",
                period=o.period,
                unit="posting",
                data_origin=o.data_origin or "unavailable",
                source_url=source_url,
                provenance_id=o.posting_id or o.id,
                quality="valid",
                description=f"Stored job posting: {title} at {employer} ({loc_str}, {o.source}).",
            ))

        skill_facts: list[StructuredFact] = []
        for index, item in enumerate(extracted_counts.values()):
            skill_name = str(item["name"] or "unmatched skill text")
            posting_count = len(item["posting_ids"])
            skill_facts.append(StructuredFact(
                fact_id=f"fact_posting_skill_{index}_{hashlib.sha256(skill_name.casefold().encode()).hexdigest()[:10]}",
                fact_type="stored_posting_skill",
                entity_name=skill_name,
                canonical_entity_id=item["entity_id"],
                entity_type="skill" if item["entity_id"] else None,
                metric_name="postings_with_skill_match",
                metric_value=posting_count,
                denominator=postings_found,
                unit="postings",
                source=job_source,
                data_origin=job_evidence_origin,
                quality_state="valid",
                readiness_state="observed",
                evidence_reference=(item["evidence"][0]["evidence_reference"] if item["evidence"] else None),
                details={
                    "sample_denominator": postings_found,
                    "sample_share": round(posting_count / postings_found, 4) if postings_found >= 20 else None,
                    "sample_size": postings_found,
                    "percentage_suppressed_below_n20": postings_found < 20,
                    "mapping_status": item["mapping_status"],
                    "reference_source": item["reference_source"],
                    "posting_ids": item["posting_ids"],
                    "supporting_evidence": item["evidence"],
                    "counting_method": "distinct retrieved postings containing at least one exact matched phrase",
                },
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
            data_origin=job_evidence_origin,
            quality_state="valid",
            readiness_state="ready" if postings_found > 0 else "insufficient_data",
            provenance_id=f"cnt_{postings_found}",
            evidence_reference=ev_ref,
            details={
                "sample_postings": sample_postings[:5],
                "postings": structured_postings,
                "skills_observed": list(extracted_counts.values()),
                "company_filter": sorted(selected_cos_norm) if selected_cos_norm else [],
                "search_window_limit": 100 if job_source == "firestore_jobs" else None,
                "sample_size": postings_found,
                "excluded_older_than_90_days": excluded_old_postings,
                "date_unknown_excluded": unknown_posted_at,
                "stored_postings_scanned": scanned_count,
                "stored_postings_query_matched": search_matched_count,
                "stored_postings_matched": postings_found,
                "requested_city": stored_requested_city,
                "stored_postings_in_requested_city": stored_city_posting_count,
                "related_titles_not_exact_matches": stored_related_titles,
                "missing_city_location_excluded": missing_city_location_count,
                "missing_remote_evidence_excluded": missing_remote_evidence_count,
                "invalid_application_urls_dropped": invalid_application_url_count,
                "live_provider_search": "off",
                "company_query": company_query,
                "percentages_suppressed_below_n20": postings_found < 20,
                "no_match_alternatives": no_match_alternatives,
            },
        ))
        facts.extend(skill_facts)

        return facts, evidence, limitations

    def _handle_collected_posting_skills(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        from app.services.collected_posting_skills_service import get_collected_posting_skills

        aggregate = get_collected_posting_skills(
            firestore_client=self.firestore_store.client if self.firestore_store is not None else None,
        )
        n = aggregate["n"]
        source = "Firestore jobs.skills_raw"
        evidence_id = f"ev_collected_posting_skills_{hashlib.sha256(str(aggregate).encode()).hexdigest()[:14]}"
        evidence = [EvidenceItem(
            evidence_id=evidence_id,
            source=source,
            signal_type="collected_posting_skill_counts",
            data_origin="real",
            history_type="bounded_posting_sample",
            location="India",
            scope="sample",
            quality="valid",
            description=(
                f"Computed skill counts from {n} distinct collected India postings in jobs.skills_raw; "
                f"sources: {', '.join(aggregate['source_labels']) or 'none'}; query limit {aggregate['query_limit']}."
            ),
        )]
        facts = [StructuredFact(
            fact_id=evidence_id.replace("ev_", "fact_"),
            fact_type="collected_posting_skills_summary",
            entity_name="Collected India job postings",
            entity_type="job_posting_sample",
            metric_name="posting_count",
            metric_value=n,
            unit="postings",
            source=source,
            data_origin="real",
            history_type="bounded_posting_sample",
            quality_state="valid",
            readiness_state="ready" if n else "insufficient_data",
            evidence_reference=evidence_id,
            details={
                **aggregate,
                "skill_count_source_of_truth": "jobs.skills_raw",
                "counting_rule": "Each distinct posting and normalized skill pair is counted once.",
                "percentages_suppressed": n < 20,
                "disclosure": (
                    f"This is a sample of {n} collected India postings, "
                    "not a measure of hiring demand or the Indian market."
                ),
            },
        )]
        all_skill_counts = {
            str(item.get("skill", "")).casefold(): item
            for item in aggregate.get("skill_counts", [])
        }
        for rank, item in enumerate(aggregate["top_skills"], 1):
            computed = all_skill_counts.get(str(item["skill"]).casefold(), {})
            details = {
                "rank": rank,
                "postings_with_skill": item["count"],
                "company_count": int(computed.get("company_count", 0)),
                "demand_verdict": computed.get("verdict", "Not enough data"),
                "limited_evidence": bool(computed.get("limited_evidence", False)),
            }
            if n >= 20:
                details["sample_share_percent"] = round(item["count"] / n * 100, 1)
            facts.append(StructuredFact(
                fact_type="collected_posting_skill_count",
                entity_name=item["skill"],
                entity_type="skill",
                metric_name="posting_count",
                metric_value=item["count"],
                unit="postings",
                denominator=n,
                source=source,
                data_origin="real",
                history_type="bounded_posting_sample",
                quality_state="valid",
                readiness_state="ready",
                evidence_reference=evidence_id,
                details=details,
            ))
        limitations = [
            "Skill counts use jobs.skills_raw as the sole source of truth and count each posting-skill pair once.",
            "The collected India postings are a sample, not hiring demand or the Indian market.",
        ]
        if n < 20:
            limitations.append("Percentages are suppressed because fewer than 20 postings were observed.")
        if aggregate["sample_may_be_incomplete"]:
            limitations.append("The bounded query reached its record limit; this sample may be incomplete.")
        return facts, evidence, limitations

    def _handle_company_intelligence(
        self,
        request: CoreIntelligenceAnswerRequest,
        plan: IntelligencePlanResponse,
    ) -> tuple[list[StructuredFact], list[EvidenceItem], list[str]]:
        facts: list[StructuredFact] = []
        evidence: list[EvidenceItem] = []
        limitations: list[str] = [
            "Employee skill domains are self-reported onboarding records, not validated proficiency or proof of organizational competence.",
            "Company-declared priority skill domains are owner-provided context, not verified requirements or evidence that the skills are absent from actual work.",
            "Employee current-role fields are self-reported onboarding values; no verified employee-to-role requirement mapping is configured.",
            "Assessment history, validated skill levels, and an approved company role-to-skill requirements catalog are not available.",
        ]
        cid = (
            request.context_override.get("_authorized_company_id")
            or request.company_id
            or plan.context_summary.get("company_id")
        )
        owner_uid = request.context_override.get("_authorized_company_owner_uid")
        if not isinstance(cid, str) or not cid or not isinstance(owner_uid, str) or not owner_uid:
            raise DataSourceUnavailableError(
                "Verified company owner and tenant context are required to read workforce records."
            )
        try:
            snapshot = self.workforce_store.get_company_workforce(
                company_id=cid,
                expected_owner_uid=owner_uid,
            )
        except CompanyWorkforceStoreUnavailable as error:
            raise DataSourceUnavailableError(str(error)) from error

        workforce_evidence_id = f"ev_company_workforce_{cid}"
        evidence.append(EvidenceItem(
            evidence_id=workforce_evidence_id,
            source="company_relationships+employee_onboarding_profiles",
            signal_type="verified_company_membership_and_self_reported_skills",
            data_origin="real",
            history_type="authenticated_internal_records",
            provenance_id=cid,
            quality="valid",
            description=(
                f"Aggregated the active connected employee membership records and matching "
                f"employee onboarding profiles for the authenticated company. "
                f"{snapshot.active_employee_count} employee relationships passed both membership "
                f"and user-profile checks; {snapshot.member_profiles_with_skills} profiles contained "
                "self-reported current skill domains. No employee identifiers or names are included."
            ),
        ))
        priority_evidence_id: str | None = None
        if snapshot.declared_priority_skills:
            priority_evidence_id = f"ev_company_declared_priorities_{cid}"
            evidence.append(EvidenceItem(
                evidence_id=priority_evidence_id,
                source="company_onboarding_profile",
                signal_type="owner_declared_priority_skill_domains",
                data_origin="real",
                history_type="authenticated_internal_records",
                provenance_id=cid,
                quality="valid",
                description=(
                    "Company owner onboarding profile contains self-declared critical skill domains. "
                    "These are company-provided priorities, not independently verified role requirements."
                ),
            ))

        covered_skill_keys = set(snapshot.skill_employee_counts)
        readiness_state = (
            "ready"
            if snapshot.active_employee_count > 0 and snapshot.skill_employee_counts
            else "insufficient_data"
        )
        readiness_reason = (
            None
            if readiness_state == "ready"
            else "NO_ACTIVE_CONNECTED_EMPLOYEES"
            if snapshot.active_employee_count == 0
            else "NO_EMPLOYEE_SKILL_RECORDS"
        )
        facts.append(StructuredFact(
            fact_id=f"fact_company_workforce_summary_{cid}",
            fact_type="company_workforce_summary",
            entity_name=snapshot.company_name or cid,
            canonical_entity_id=cid,
            entity_type="company",
            metric_name="active_connected_employee_count",
            metric_value=snapshot.active_employee_count,
            unit="employees",
            source="company_relationships+employee_onboarding_profiles",
            data_origin="real",
            quality_state="valid",
            readiness_state=readiness_state,
            provenance_id=cid,
            evidence_reference=workforce_evidence_id,
            details={
                "members_with_self_reported_skill_records": snapshot.member_profiles_with_skills,
                "members_without_self_reported_skill_records": snapshot.member_profiles_without_skills,
                "unverified_or_stale_membership_records_excluded": snapshot.unverified_membership_count,
                "profiles_with_self_reported_confidence_values": (
                    snapshot.member_profiles_with_self_reported_confidence
                ),
                "profiles_with_self_reported_current_role": snapshot.member_profiles_with_current_role,
                "skill_record_source": "profile.employee.current_skill_domains",
                "skill_records_are_self_reported": True,
                "proficiency_records_are_verified": False,
                "role_assignments_are_verified": False,
                "declared_priority_domains_available": bool(snapshot.declared_priority_skills),
                "declared_priority_domains_are_requirements": False,
                "reason_code": readiness_reason,
                "roster_read_truncated": snapshot.truncated,
            },
        ))

        for key, count in sorted(
            snapshot.skill_employee_counts.items(),
            key=lambda item: (
                -item[1],
                snapshot.skill_labels[item[0]].casefold(),
            ),
        ):
            skill_name = snapshot.skill_labels[key]
            skill_id = key.removeprefix("id:")
            facts.append(StructuredFact(
                fact_id=f"fact_company_skill_{hashlib.sha256((cid + key).encode()).hexdigest()[:12]}",
                fact_type="company_skill_coverage",
                entity_name=skill_name,
                canonical_entity_id=skill_id if key.startswith("id:") else None,
                entity_type="skill",
                metric_name="employees_self_reporting_skill",
                metric_value=count,
                unit="connected employee profiles",
                denominator=float(snapshot.active_employee_count),
                source="employee_onboarding_profiles",
                data_origin="real",
                quality_state="valid",
                readiness_state="ready",
                provenance_id=cid,
                evidence_reference=workforce_evidence_id,
                details={
                    "skill_source": "profile.employee.current_skill_domains",
                    "self_reported": True,
                    "proficiency_inferred": False,
                },
            ))

        for priority in snapshot.declared_priority_skills:
            canonical_id = canonical_skill_id(priority)
            normalized_name = " ".join(priority.casefold().split())
            key = f"id:{canonical_id}" if canonical_id else f"name:{normalized_name}"
            is_recorded = key in covered_skill_keys
            facts.append(StructuredFact(
                fact_id=f"fact_company_priority_{hashlib.sha256((cid + key).encode()).hexdigest()[:12]}",
                fact_type="company_declared_priority_skill",
                entity_name=priority,
                canonical_entity_id=canonical_id,
                entity_type="skill" if canonical_id else "skill_label",
                metric_name=(
                    "company_declared_priority_recorded_in_employee_profiles"
                    if is_recorded
                    else "company_declared_priority_not_found_in_employee_profiles"
                ),
                metric_value="represented" if is_recorded else "not_represented",
                source="company_onboarding_profile+employee_onboarding_profiles",
                data_origin="real",
                quality_state="valid",
                readiness_state="ready",
                provenance_id=cid,
                evidence_reference=workforce_evidence_id,
                details={
                    "owner_declared_priority": True,
                    "verified_role_requirement": False,
                    "employee_profile_comparison": "exact_label_or_registered_canonical_skill_id",
                    "supporting_evidence_references": [
                        priority_evidence_id,
                        workforce_evidence_id,
                    ],
                },
            ))

        if readiness_state != "ready":
            facts[0].details["reason_code"] = readiness_reason
            limitations.append(
                "A recorded skill-coverage summary requires at least one active connected employee "
                "and at least one employee profile with a self-reported skill domain."
            )
        if snapshot.member_profiles_without_skills:
            limitations.append(
                f"{snapshot.member_profiles_without_skills} active connected employee profile(s) "
                "have no self-reported skill-domain records; these omissions are not treated as skill gaps."
            )
        if snapshot.member_profiles_with_self_reported_confidence:
            limitations.append(
                "Some employee profiles contain self-reported confidence values; no values are interpreted "
                "as verified proficiency."
            )
        else:
            limitations.append(
                "No self-reported skill-confidence values were present in the retrieved active employee profiles."
            )
        if snapshot.unverified_membership_count:
            limitations.append(
                f"{snapshot.unverified_membership_count} stale, disconnected, or inconsistent membership "
                "record(s) were excluded from the aggregate."
            )
        if snapshot.truncated:
            limitations.append(
                f"The connected membership read was bounded to {FirestoreCompanyWorkforceStore.MAX_MEMBERS} "
                "records; coverage may be incomplete."
            )

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
            role = request.target_role or primary
            if role:
                questions.append(f"Which O*NET technology mappings are associated with {role}?")
                questions.append("What market evidence, if any, supports the learning candidates?")
            else:
                questions.append("Which single target role should I compare with your profile?")

        elif intent == "synthesize_actions":
            role = request.target_role
            if role:
                questions.append(f"Which evidence supports the learning candidates for {role}?")
                questions.append(f"What profile skills were compared with {role}?")
            else:
                questions.append("Which target role should guide the learning suggestions?")

        elif intent in {"search_jobs", "company_postings_summary"}:
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

        elif intent in {"analyze_trend", "analyze_skill_health", "estimate_skill_half_life", "forecast_future_demand", "retrieve_history", "retrieve_snapshot"}:
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
        if intent == "aggregate_posting_skills":
            summary = next((fact for fact in facts if fact.fact_type == "collected_posting_skills_summary"), None)
            metadata = summary.details if summary else {}
            n = int(summary.metric_value) if summary else 0
            start = metadata.get("date_start")
            end = metadata.get("date_end")
            date_range = f"{start} to {end}" if start and end else "unavailable"
            source_labels = ", ".join(metadata.get("source_labels") or []) or "unavailable"
            direct_answer = (
                f"The bounded sample contains {n} collected India postings from "
                f"{metadata.get('company_count', 0)} companies, covering {date_range}. "
                f"Source labels: {source_labels}."
            )
            skill_facts = [fact for fact in facts if fact.fact_type == "collected_posting_skill_count"]
            supporting_facts = [
                f"**{fact.entity_name}**: {fact.metric_value} postings"
                + (f" ({fact.details['sample_share_percent']}% of this sample)" if n >= 20 else "")
                for fact in skill_facts
            ] or ["No skills were recorded in jobs.skills_raw for the postings in this sample."]
            interpretation = "Skill totals come only from jobs.skills_raw; duplicate posting and skill pairs are counted once."
            limitations = [
                "This sample is not hiring demand and does not represent the Indian market.",
                "The query is bounded to 500 India postings and cached for 60 seconds.",
            ]
            if metadata.get("sample_may_be_incomplete"):
                limitations.append("The query reached its limit, so the sample may be incomplete.")
            if n < 20:
                limitations.append("Percentages are suppressed because fewer than 20 postings were observed.")

        elif intent == "rank_skill_trends":
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
                signal_type = str(det.get("signal_type") or "unknown")
                provider = str(det.get("provider") or trend_fact.source)
                signal_label = {
                    "demand": (
                        "job-posting demand"
                        if provider.casefold() in {
                            "jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters",
                        }
                        else "demand"
                    ),
                    "adoption": "developer adoption/activity",
                    "interest": "community or public interest",
                }.get(signal_type, "source-specific")
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

                slope_unit_display = str(det.get("slope_unit") or trend_fact.unit or f"{unit} per {grain}")
                if not slope_unit_display.endswith(f"per {grain}") and not slope_unit_display.endswith(grain):
                    slope_unit_display = f"{slope_unit_display} per {grain}"

                period_count_text = f"{periods_count} consecutive {grain} periods" if periods_count else f"the observed {grain} periods"
                direct_answer = (
                    f"**Skill Demand Trends**: The measured {signal_label} trend for **{ent}** across {period_count_text} "
                    f"({start_p} to {end_p}) is **{direction}**, based on **{provider}**."
                )
                if slope is not None:
                    direct_answer += f" Theil-Sen Median Slope is **{slope} {slope_unit_display}**."
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
                    supporting_facts.append(f"**2. Theil-Sen Median Slope**: {slope} {slope_unit_display}")
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
                if signal_type == "adoption":
                    limitations = [
                        f"Requires >= 4 strictly consecutive {grain} periods; panel gaps or missing periods block calculation.",
                        "Developer adoption/activity is not employer hiring demand.",
                        "No forward-looking forecasting or extrapolation is applied.",
                    ]
                elif signal_type == "interest":
                    limitations = [
                        f"Requires >= 4 strictly consecutive {grain} periods; panel gaps or missing periods block calculation.",
                        "Community or public interest is not employer hiring demand.",
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
                readiness = next(
                    (fact for fact in facts if fact.fact_type == "analysis_readiness"),
                    None,
                )
                reason = (
                    readiness.details.get("reason")
                    if readiness and readiness.details
                    else "The available observations did not pass the evidence and readiness checks."
                )
                ent = readiness.entity_name if readiness else (
                    plan.context_summary.get("primary_entity") if plan else None
                )
                signal_type = next(
                    (item.measured_signal_type for item in evidence if item.measured_signal_type),
                    None,
                )
                signal_label = {
                    "interest": "developer interest",
                    "adoption": "developer activity",
                    "demand": "hiring demand",
                }.get(str(signal_type).casefold(), None) if signal_type else None
                reason_lower = str(reason).casefold()
                if "interest" in reason_lower:
                    signal_label = "developer interest"
                concise_reason = (
                    "The available data did not meet the requirements for at least four consecutive comparable completed monthly periods."
                )
                if signal_label == "developer interest":
                    concise_reason = (
                        "The available source measures developer interest, not hiring demand, and does not currently meet the comparable monthly series requirements."
                    )
                direct_answer = (
                    f"**Trend not available yet**\n\nNo verified measured trend is available for **{ent}**. {concise_reason}"
                    if ent else f"**Trend not available yet**\n\nNo verified measured trend is available. {concise_reason}"
                )
                supporting_facts = []
                interpretation = "No direction or velocity is reported because readiness requirements were not met."
                # Detailed readiness, source, period, and eligibility remain in
                # the structured fact/evidence panel instead of the answer text.
                limitations = []

        elif intent == "analyze_skill_health":
            health_score_fact = next((f for f in facts if f.fact_type == "skill_health_score"), None)
            health_cat_fact = next((f for f in facts if f.fact_type == "skill_health_category"), None)
            comp_facts = [f for f in facts if f.fact_type == "skill_health_component"]
            ent = (
                health_score_fact.entity_name if health_score_fact
                else (plan.context_summary.get("primary_entity") if plan else "Skill")
            )
            score_val = health_score_fact.metric_value if health_score_fact else None
            cat_val = health_cat_fact.metric_value if health_cat_fact else "insufficient_data"

            if score_val is not None:
                direct_answer = (
                    f"**{ent}** has a Skill Health score of **{score_val:.2f}/100** "
                    f"with a **{cat_val}** relative-momentum category."
                )
                supporting_facts.append(f"**Skill Health Score**: {score_val:.2f}/100")
                supporting_facts.append(f"**Health Category**: {cat_val}")
                for cf in comp_facts:
                    det = cf.details
                    p_used = det.get("periods_used", [])
                    period_str = f" ({p_used[0]} to {p_used[-1]})" if p_used else ""
                    rel_slope = det.get("relative_slope_per_month")
                    slope_str = f", relative slope {rel_slope:+.4f}/mo" if rel_slope is not None else ""
                    supporting_facts.append(
                        f"**{det.get('signal_family', 'signal').title()} component** ({cf.source}): "
                        f"{cf.metric_value}{slope_str}{period_str}"
                    )
                interpretation = (
                    "Skill Health evaluates relative momentum from consecutive completed normalized share series. "
                    "The baseline score of 50.0 represents neutral relative momentum, not a 50% health percentage. "
                    "A higher score is an indicator of relative share momentum and does not prove higher absolute hiring volume "
                    "or guarantee future career success."
                )
            elif health_score_fact and health_score_fact.quality_state == "ambiguous_series":
                direct_answer = (
                    f"Multiple non-interchangeable normalized share series were found for **{ent}**. "
                    "In accordance with analytical governance, separate series are reported independently and "
                    "no single combined score or overall category is computed."
                )
                for cf in comp_facts:
                    det = cf.details
                    p_used = det.get("periods_used", [])
                    period_str = f" ({p_used[0]} to {p_used[-1]})" if p_used else ""
                    score_str = f", score {det.get('health_score')}" if det.get("health_score") is not None else ""
                    supporting_facts.append(
                        f"**{det.get('provider', cf.source)} ({det.get('signal_family', 'signal')})**: "
                        f"{cf.metric_value}{score_str}{period_str}"
                    )
                interpretation = (
                    "Different sources, metrics, and collection units are never averaged or combined into a single fabricated score."
                )
            else:
                readiness = next((f for f in facts if f.fact_type == "analysis_readiness"), None)
                reason = readiness.details.get("reason") if readiness and readiness.details else "Insufficient normalized share history to calculate Skill Health."
                direct_answer = f"Skill Health for **{ent}** is currently unavailable. {reason}"
                interpretation = (
                    "Skill Health requires at least 4 strictly consecutive completed monthly periods with explicit positive denominators."
                )
            limitations = [
                "Skill Health is a relative-momentum indicator; a score of 50.0 reflects neutral relative momentum, not 50% healthy.",
                "Higher Skill Health score does not imply higher absolute job posting volume.",
                "Skill Health reflects historical empirical observations, not a predictive forecast or future outcome probability.",
            ]

        elif intent == "estimate_skill_half_life":
            hl_fact = next((f for f in facts if f.fact_type == "skill_half_life"), None)
            ent = (
                hl_fact.entity_name if hl_fact
                else (plan.context_summary.get("primary_entity") if plan else "Skill")
            )
            status_val = hl_fact.quality_state if hl_fact else "insufficient_data"
            det = hl_fact.details if hl_fact else {}

            if status_val == "ready" and hl_fact and hl_fact.metric_value is not None:
                hl_months = hl_fact.metric_value
                hl_years = det.get("half_life_years")
                provider = det.get("provider", hl_fact.source)
                sig_family = det.get("signal_family", "demand")
                unc_range = det.get("uncertainty_range_months")
                unc_str = f"[{unc_range[0]}, {unc_range[1]}]" if unc_range and unc_range[1] is not None else f"[{unc_range[0]}, inf)" if unc_range else "unavailable"
                slope = det.get("log_share_slope_per_month")
                tau = det.get("kendall_tau")
                p_val = det.get("kendall_p_value")
                p_eval = det.get("periods_evaluated", len(det.get("periods_used", [])))
                start_p = det.get("first_period")
                end_p = det.get("latest_period")

                direct_answer = (
                    f"**Skill Half-Life**: The estimated half-life for **{ent}** in {sig_family} on **{provider}** is "
                    f"**{hl_months:.2f} months** ({hl_years:.2f} years), with a 95% confidence interval uncertainty "
                    f"range of **{unc_str} months**."
                )
                supporting_facts.append(f"**Estimated Half-Life**: {hl_months:.2f} months ({hl_years:.2f} years)")
                supporting_facts.append(f"**Uncertainty Range (95% CI)**: {unc_str} months")
                if slope is not None:
                    supporting_facts.append(f"**Log-Share Theil-Sen Slope**: {slope:+.6f} per month")
                if tau is not None and p_val is not None:
                    supporting_facts.append(f"**Kendall Tau Rank Correlation**: {tau:+.4f} (decay p-value: {p_val:.4f})")
                if start_p and end_p:
                    supporting_facts.append(f"**Fitted Observation Window**: {p_eval} consecutive monthly periods ({start_p} to {end_p})")
                interpretation = (
                    "Skill Half-Life is estimated using an exponential decay model on log normalized market share (half_life = ln(2) / |b|), "
                    "where b is the Theil-Sen median slope per month. It represents the historical rate of decline across verified completed periods. "
                    "Half-life decay estimates reflect past observed trends and are not a guaranteed date of skill obsolescence or future extinction."
                )
            elif status_val == "not_applicable":
                reason = det.get("reason") or "The series is growing or flat; half-life decay is not applicable."
                slope = det.get("log_share_slope_per_month")
                tau = det.get("kendall_tau")
                direct_answer = (
                    f"Skill Half-Life is **not applicable** for **{ent}**. {reason}"
                )
                supporting_facts.append("**Half-Life Status**: Not Applicable (Non-declining series)")
                if slope is not None:
                    supporting_facts.append(f"**Theil-Sen Slope**: {slope:+.6f} per month")
                if tau is not None:
                    supporting_facts.append(f"**Kendall Tau**: {tau:+.4f}")
                interpretation = (
                    "Half-Life decay models apply strictly to series undergoing statistically supported monotonic decline "
                    "(Kendall tau <= -0.5, p-value < 0.05). Growing, stable, or flat skill shares do not exhibit half-life decay."
                )
            else:
                readiness = next((f for f in facts if f.fact_type == "analysis_readiness"), None)
                reason = readiness.details.get("reason") if readiness and readiness.details else "Insufficient normalized share history to calculate Skill Half-Life."
                direct_answer = f"Skill Half-Life for **{ent}** is currently unavailable. {reason}"
                interpretation = (
                    "Skill Half-Life requires at least 36 strictly consecutive completed monthly periods with explicit positive denominators."
                )
            limitations = [
                "Skill Half-Life is an empirical decay estimate under an exponential decay model (ln(2) / |b|); not an obsolescence guarantee.",
                "Requires >= 36 strictly consecutive completed monthly periods with valid positive denominators.",
                "Non-declining, stable, or growing series return not applicable.",
                "Half-Life reflects historical empirical observations, not a predictive forecast or future outcome probability.",
            ]

        elif intent == "forecast_future_demand":
            fc_fact = next((f for f in facts if f.fact_type == "skill_forecast"), None)
            ent = (
                fc_fact.entity_name if fc_fact
                else (plan.context_summary.get("primary_entity") if plan else "Skill")
            )
            status_val = fc_fact.quality_state if fc_fact else "insufficient_data"
            det = fc_fact.details if fc_fact else {}

            if status_val == "ready" and fc_fact and det.get("forecasts"):
                horizon = det.get("horizon_months", len(det.get("forecasts", [])))
                provider = det.get("provider", fc_fact.source)
                unit = fc_fact.unit or "share"
                metric = det.get("metric", "normalized_share")
                rmse = det.get("winner_rmse")
                naive_rmse = det.get("naive_rmse")
                beats = det.get("beats_naive_baseline", False)
                sample_size = det.get("backtest_sample_size", 0)
                history_len = det.get("history_length", 0)
                first_p = det.get("first_history_period")
                latest_p = det.get("latest_history_period")

                forecast_lines = []
                for pt in det.get("forecasts", []):
                    p = pt.get("period")
                    val = pt.get("point_forecast")
                    forecast_lines.append(f"{p}: {val:.4f}")
                points_summary = ", ".join(forecast_lines)

                direct_answer = (
                    f"**Skill Demand Forecast**: Projected {horizon}-month demand trajectory for **{ent}** on **{provider}** "
                    f"({points_summary}; unit: {unit})."
                )
                supporting_facts.append(f"**Target Metric**: {metric} ({unit})")
                supporting_facts.append(f"**Forecast Horizon**: {horizon} months")
                supporting_facts.append("**Forecasting Method**: Seasonal-naive carry-forward (12-month seasonal cycle)")
                if rmse is not None and naive_rmse is not None:
                    comparison_str = "better than" if beats else "comparable to"
                    supporting_facts.append(
                        f"**Validation Accuracy**: Chronological holdout RMSE = {rmse:.6f} {unit} ({comparison_str} simple naive baseline RMSE = {naive_rmse:.6f} {unit}; sample size: {sample_size})"
                    )
                if first_p and latest_p:
                    supporting_facts.append(f"**Historical Fit Window**: {history_len} consecutive monthly periods ({first_p} to {latest_p})")

                interpretation = (
                    f"This forecast is produced using a deterministic seasonal-naive carry-forward model that projects future "
                    f"monthly values based on the corresponding month from the prior year. Evaluated out-of-sample over "
                    f"{sample_size} chronological holdout periods, the model achieved an RMSE of {rmse:.6f} {unit}. "
                    f"Empirical prediction intervals are omitted until horizon-specific holdout coverage is sufficient. "
                    f"Forward-looking predictions are non-guaranteed estimates and must not be treated as deterministic hiring outcomes."
                )
            else:
                readiness = next((f for f in facts if f.fact_type == "analysis_readiness"), None)
                reason = readiness.details.get("reason") if readiness and readiness.details else "Insufficient consecutive monthly observations to calculate a skill demand forecast."
                direct_answer = f"Skill Demand Forecast for **{ent}** is currently unavailable. {reason}"
                interpretation = (
                    "Skill Demand Forecasting requires at least 24 strictly consecutive completed monthly observations with valid units and source provenance."
                )
            limitations = [
                "Requires >= 24 strictly consecutive completed monthly periods; gaps or truncated history block forecasting.",
                "Forecast horizon is capped at min(6, history_length // 3) months.",
                "Uses a seasonal-naive model (12-month seasonal carry-forward) evaluated against a simple naive baseline.",
                "Prediction intervals are omitted until horizon-specific holdout coverage is sufficient.",
                "Forward-looking predictions are non-guaranteed estimates based on historical data; external market shifts or hiring disruptions are not accounted for.",
            ]

        elif intent == "analyze_ai_task_exposure":
            summary_fact = next((f for f in facts if f.fact_type == "task_exposure_summary"), None)
            task_facts = [f for f in facts if f.fact_type == "task_exposure_record"]
            skill_facts = [f for f in facts if f.fact_type == "task_associated_skill"]

            ent = (
                summary_fact.entity_name if summary_fact
                else (plan.context_summary.get("primary_entity") if plan else "Occupation")
            )

            if summary_fact:
                det = summary_fact.details
                task_exp_summary = det.get("task_exposure_summary") or summary_fact.metric_value
                aug_count = det.get("augmentation_task_count", 0)
                auto_count = det.get("automation_task_count", 0)
                ai_usage = det.get("ai_usage_summary") or ""
                aug_vs_auto = det.get("augmentation_vs_automation_summary") or ""
                wf_outcome = det.get("workforce_outcome_summary") or ""

                direct_answer = (
                    f"**AI Task Exposure**: For **{ent}**, {task_exp_summary} "
                    f"Observed usage indicates {aug_count} augmentation and {auto_count} automation tasks; "
                    "human oversight remains required for complex engineering judgment."
                )
                supporting_facts.append(f"**Task Exposure Levels**: {summary_fact.metric_value}")
                if ai_usage:
                    supporting_facts.append(f"**Observed AI Usage**: {ai_usage}")
                if aug_vs_auto:
                    supporting_facts.append(f"**Augmentation vs Automation**: {aug_vs_auto}")
                if wf_outcome:
                    supporting_facts.append(f"**Workforce Outcome Context**: {wf_outcome}")

                for tf in task_facts[:5]:
                    tdet = tf.details
                    supporting_facts.append(
                        f"**Task {tdet.get('task_id')}** ({str(tf.metric_value).title()} exposure, mode: {tdet.get('observed_ai_usage_mode', 'unobserved')}): "
                        f"{tdet.get('task_statement')}"
                    )

                if skill_facts:
                    unique_skills = sorted({str(sf.metric_value) for sf in skill_facts})
                    supporting_facts.append(f"**Associated Canonical Skills**: {', '.join(unique_skills)}")

                interpretation = (
                    "Task exposure measures the theoretical overlap between AI model capabilities and discrete occupational tasks based on verified taxonomy reference datasets. "
                    "It does NOT imply job disappearance, headcount reduction, or occupation obsolescence. "
                    "Empirical workforce hiring demand is tracked independently from market observations. "
                    "Tasks exhibiting high exposure often undergo human-in-the-loop augmentation rather than discrete end-to-end automation."
                )
            else:
                readiness = next((f for f in facts if f.fact_type == "analysis_readiness"), None)
                reason = readiness.details.get("reason") if readiness and readiness.details else "Task exposure evaluation is currently unavailable."
                direct_answer = f"AI Task Exposure analysis for **{ent}** is currently unavailable. {reason}"
                interpretation = (
                    "AI Task Exposure evaluation requires a verified, open-licensed task exposure dataset and matching occupational task records."
                )
            limitations = [
                "Task exposure measures theoretical capability overlap only and never implies job disappearance or headcount reduction.",
                "Workforce hiring outcomes are tracked from empirical market demand series, not task exposure scores.",
                "Analysis is strictly grounded in verified, licensed reference datasets; zero synthetic scores are utilized.",
            ]

        elif intent == "crosswalk_occupation_software":
            soft_facts = [f for f in facts if f.fact_type == "software_skill"]
            esco_facts = [f for f in facts if f.fact_type == "occupation_skill_association"]
            if esco_facts:
                occ_name = esco_facts[0].details.get("occupation_title") or "the selected occupation"
                direct_answer = f"Retrieved {len(esco_facts)} ESCO occupation-skill associations for **{occ_name}** (up to 10 are returned)."
                for fact in esco_facts:
                    supporting_facts.append(f"**{fact.entity_name}** ({fact.metric_value})")
                interpretation = "These are static ESCO taxonomy associations, not evidence of a person's qualifications, employability, or live employer demand."
                limitations = [
                    "At most 10 matching ESCO relationships are returned for this response.",
                    "ESCO essential/optional labels describe taxonomy relationships only.",
                    "No current hiring-demand evidence is implied by these reference associations.",
                ]
            else:
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
                if occ_fact.details.get("closest_match"):
                    direct_answer = (
                        f"No exact O*NET title match was found for **{occ_fact.details.get('requested_title')}**. "
                        f"The closest matching local occupation is **{title}** (SOC **{soc}**)."
                    )
                else:
                    direct_answer = f"O*NET occupational classification for **{title}** resolves to SOC code **{soc}**."
                supporting_facts = [
                    f"**Occupation Title**: {title}",
                    f"**Standard Occupational Classification (SOC)**: {soc}",
                    f"**Definition**: {desc}",
                ]
                interpretation = "Standard Occupational Classification (SOC) provides standardized federal taxonomy definitions for labor market categorization."
                limitations = ["Reference taxonomy definition; does not reflect real-time employer hiring activity."]
            else:
                requested = next((f.entity_name for f in facts if f.fact_type == "occupation_lookup_readiness"), None) or "the requested title"
                direct_answer = f"No exact or sufficiently close local O*NET occupation record was found for **{requested}**."
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
                interpretation = (
                    "**General guidance:** occupation titles vary across employers and taxonomies. "
                    "Try a standard role title such as Data Engineer or Machine Learning Engineer; this guidance is not a verified classification."
                )
                limitations = ["No occupation was substituted because the local reference data did not provide a sufficiently close match."]

        elif intent == "lookup_github_adoption":
            snapshots = [fact for fact in facts if fact.fact_type == "developer_activity_snapshot"]
            changes = [fact for fact in facts if fact.fact_type == "developer_activity_change"]
            descriptive = [fact for fact in facts if fact.fact_type == "developer_activity_trend"]
            if snapshots:
                latest = snapshots[0]
                direct_answer = (
                    f"GitHub Innovation Graph recorded **{int(latest.metric_value)} unique developers** "
                    f"for {latest.entity_name} in **{latest.period}** ({latest.details.get('iso2_code')}); "
                    "this is developer activity, not hiring demand."
                )
                if changes:
                    change = changes[0]
                    direct_answer += (
                        f" The latest quarter-to-quarter change was **{int(change.metric_value):+}** "
                        f"({change.period.replace('_to_', ' to ')})."
                    )
                if descriptive:
                    trend = descriptive[0]
                    direct_answer += (
                        f" Across {len(trend.details.get('periods', []))} consecutive quarters "
                        f"({trend.period.replace('_to_', ' to ')}), the count {trend.metric_value} "
                        f"from {trend.details.get('first_value')} to {trend.details.get('latest_value')}."
                    )
            else:
                unavailable = next((fact for fact in facts if fact.fact_type == "analysis_readiness"), None)
                direct_answer = str((unavailable.details or {}).get("reason")) if unavailable else "No matching local GitHub developer-adoption series is available."
            interpretation = "Quarterly source counts are compared only within the same GitHub metric and geography."
            limitations = [
                "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
                "This descriptive quarterly series is not converted into monthly demand evidence.",
            ]

        elif intent in {"explain_concept", "lookup_skill_reference"}:
            reference_fact = next(
                (fact for fact in facts if fact.fact_type == "canonical_reference"),
                None,
            )
            unavailable_fact = next(
                (
                    fact for fact in facts
                    if fact.fact_type == "analysis_readiness"
                    and fact.metric_name == "canonical_reference_readiness"
                ),
                None,
            )
            if reference_fact:
                category = (
                    str(reference_fact.metric_value)
                    if reference_fact.metric_name == "taxonomy_category" and reference_fact.metric_value
                    else None
                )
                definition = reference_fact.details.get("definition") or reference_fact.details.get("description")
                entity_name = reference_fact.entity_name or "The requested entity"
                if reference_fact.source == "ref_esco_skills":
                    version = reference_fact.details.get("source_version") or "the imported release"
                    direct_answer = f"**{entity_name}** is listed in the ESCO {version} skill taxonomy."
                else:
                    direct_answer = f"**{entity_name}** is listed in the canonical reference source."
                if category:
                    direct_answer += f" Category: **{category}**."
                else:
                    direct_answer += " Category is unavailable in the current reference data."
                if definition:
                    direct_answer += f" Definition: {definition}"
                else:
                    direct_answer += " A definition is unavailable in the current reference data."
            elif unavailable_fact:
                direct_answer = str(unavailable_fact.details.get("reason"))
            else:
                direct_answer = (
                    "A canonical reference record was not found. Definition and category are unavailable "
                    "in the current reference data."
                )
            interpretation = ""
            limitations = []

        elif intent in {"search_jobs", "company_postings_summary"}:
            job_fact = next((f for f in facts if f.fact_type == "stored_job_postings"), None)
            cnt = job_fact.metric_value if job_fact else 0
            if job_fact and job_fact.details.get("stored_postings_scanned") is not None:
                direct_answer = (
                    f"Scanned **{job_fact.details['stored_postings_scanned']}** stored postings; "
                    f"**{cnt}** matched the applied filters. Live provider search is off."
                )
            else:
                direct_answer = "Live provider search is off; this answer uses the available stored posting observations."
            unavailable_links = int(job_fact.details.get("invalid_application_urls_dropped", 0)) if job_fact else 0
            if unavailable_links:
                direct_answer += f" Application link unavailable for {unavailable_links} posting(s); invalid URLs were dropped."
            if intent == "company_postings_summary":
                postings = job_fact.details.get("postings", []) if job_fact else []
                company_name = str(
                    (job_fact.details.get("company_query") if job_fact else None)
                    or (request.selected_companies[0] if request.selected_companies else "the requested company")
                )
                role_names = sorted({str(item.get("title") or "").strip() for item in postings if str(item.get("title") or "").strip()}, key=str.casefold)
                locations = sorted({str(item.get("location") or "").strip() for item in postings if str(item.get("location") or "").strip()}, key=str.casefold)
                if cnt:
                    direct_answer += (
                        f"\n\n**Stored company records — {company_name}:** {cnt} matching postings. "
                        f"Job locations: {', '.join(locations) if locations else 'unavailable'}. "
                        f"Roles: {', '.join(role_names) if role_names else 'unavailable'}. "
                    )
                else:
                    direct_answer += f"\n\nNo matching stored postings were found for {company_name}. "
                direct_answer += "Company address unavailable; no verified address is stored in these records."
                supporting_facts = [
                    f"Stored postings scanned: {job_fact.details.get('stored_postings_scanned', 'unavailable') if job_fact else 'unavailable'}.",
                    f"Stored postings matched: {cnt}.",
                    f"Job locations: {', '.join(locations) if locations else 'unavailable'}.",
                    f"Roles: {', '.join(role_names) if role_names else 'unavailable'}.",
                    "Company address unavailable.",
                ]
                interpretation = ""
                limitations = ["Company details are limited to stored job postings; no company website or outside source was fetched."]
                if unavailable_links:
                    limitations.append(f"Application link unavailable for {unavailable_links} posting(s); invalid URLs were dropped.")
                company_sections = [direct_answer]
                if supporting_facts:
                    company_sections.append("**Stored records**\n" + "\n".join(f"- {item}" for item in supporting_facts))
                if evidence_citations:
                    company_sections.append("**Sources**\n" + "\n".join(f"- {item}" for item in evidence_citations))
                company_sections.append("**Limitations:** " + " ".join(limitations))
                return "\n\n".join(company_sections)
            observed_skills = [f for f in facts if f.fact_type == "stored_posting_skill"]
            observed_skills.sort(key=lambda fact: (-int(fact.metric_value or 0), str(fact.entity_name or "").casefold()))
            if cnt == 0:
                if request.selected_companies:
                    comp_str = ", ".join(request.selected_companies)
                    direct_answer += (
                        f"No matching job postings were found in the bounded recent stored search for saved companies ({comp_str}). "
                        "An empty posting sample does not establish hiring demand or the absence of hiring demand."
                    )
                else:
                    direct_answer += (
                        "No matching job postings were found in the bounded recent stored search. "
                        "An empty posting sample does not establish hiring demand or the absence of hiring demand."
                    )
                requested_city = job_fact.details.get("requested_city") if job_fact else None
                city_posting_count = (
                    job_fact.details.get("stored_postings_in_requested_city")
                    if job_fact else None
                )
                if requested_city and city_posting_count is not None:
                    direct_answer += (
                        f" Stored postings in {requested_city}: {city_posting_count}."
                    )
                    related_titles = job_fact.details.get(
                        "related_titles_not_exact_matches", []
                    )
                    if related_titles:
                        direct_answer += (
                            " Related, not an exact match: "
                            + "; ".join(related_titles[:5])
                            + "."
                        )
            else:
                direct_answer += f" Retrieved **{cnt}** matching job postings from the stored collection runs."
                if observed_skills:
                    summaries = [
                        f"{fact.entity_name} ({fact.metric_value}/{fact.denominator} postings)"
                        for fact in observed_skills[:12]
                    ]
                    direct_answer += " Exact skill matches in this retrieved sample: " + "; ".join(summaries) + "."
                else:
                    direct_answer += " No locally matched skill phrases were found in the retrieved posting text."
            supporting_facts = [
                f"**Stored Postings Found**: {cnt} postings",
            ]
            if job_fact and int(job_fact.metric_value or 0) > 0:
                supporting_facts.extend(
                    f"**{fact.entity_name}**: {fact.metric_value} of {fact.denominator} retrieved postings; mapping {fact.details.get('mapping_status')}."
                    for fact in observed_skills[:12]
                )
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
            if unavailable_links:
                limitations.append(f"Application link unavailable for {unavailable_links} posting(s); invalid URLs were dropped.")

        elif intent == "analyze_skill_gap":
            gap_fact = next((f for f in facts if f.fact_type == "personalized_skill_gap"), None)
            old_gap_fact = next((f for f in facts if f.fact_type == "skill_gap"), None)
            readiness = next(
                (
                    fact for fact in facts
                    if fact.fact_type in {"learning_recommendation_readiness", "skill_gap_readiness"}
                ),
                None,
            )
            candidates = [
                fact for fact in facts
                if fact.fact_type == "action_recommendation"
            ]
            if readiness:
                direct_answer = str(
                    readiness.details.get("message")
                    or readiness.details.get("clarification")
                    or "A role-to-skill comparison is not available with the current information."
                )
                interpretation = (
                    "No occupation fallback or unsupported skill mapping was used."
                )
                limitations = [
                    "A target role with a verified occupational mapping is required before comparing recorded skills.",
                ]
            elif gap_fact:
                det = gap_fact.details
                role = gap_fact.entity_name or "the selected role"
                matched = det.get("matched", [])
                matched_count = det.get("coverage_numerator", len(matched))
                matched_labels = list(dict.fromkeys(item["label"] for item in matched))
                missing = det.get("missing", [])
                pct = det.get("coverage_percent")
                coverage_text = f"{pct}%" if pct is not None else "unavailable"
                essential_gaps = [item["label"] for item in missing if item.get("classification") == "essential"]
                optional_gaps = [item["label"] for item in missing if item.get("classification") == "optional"]
                unclassified_gaps = [item["label"] for item in missing if not item.get("classification")]
                direct_answer = (
                    f"For **{role}** in **{str(det.get('taxonomy', 'selected')).upper()}**, "
                    f"{matched_count} of {det.get('reference_count', 0)} distinct reference skills matched "
                    f"({coverage_text} reference-skill coverage)."
                )
                supporting_facts = [
                    f"**Matched skills**: {', '.join(matched_labels) or 'none matched by an unambiguous label'}",
                    f"**Essential gaps**: {', '.join(essential_gaps[:10]) or 'none identified'}",
                    f"**Optional gaps**: {', '.join(optional_gaps[:10]) or 'none identified'}",
                    f"**Unclassified reference gaps**: {', '.join(unclassified_gaps[:10]) or 'none'}",
                    f"**User skills not matched**: {', '.join(item.get('original_text', '') for item in det.get('unmatched_user', [])) or 'none'}",
                    f"**Coverage formula**: {det.get('coverage_formula')}",
                    *[
                        f"**Roadmap {step.get('priority')} — {step.get('target_skill')}**: {step.get('suggested_task')} Outcome: {step.get('tangible_outcome')} Self-check: {step.get('self_check_criterion')}"
                        for step in det.get("learning_roadmap", {}).get("steps", [])[:3]
                    ],
                ]
                interpretation = det.get("interpretation", "Reference-skill coverage only; proficiency is not verified.")
                limitations = list(dict.fromkeys(limitations))
            elif old_gap_fact:
                direct_answer = f"For **{old_gap_fact.entity_name or 'the selected role'}**, the existing O*NET technology mapping comparison is available."
                supporting_facts = [f"**Role-associated learning candidates**: {', '.join(f.entity_name or '' for f in candidates)}"]
                interpretation = "O*NET technology mapping context, not mandatory qualifications."
                limitations = list(dict.fromkeys(limitations))
            else:
                direct_answer = "Skill gap analysis completed."
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
                interpretation = "Baseline skill gap crosswalk."
                limitations = [
                    "O*NET occupational software mappings are not mandatory qualifications.",
                ]

        elif intent == "synthesize_actions":
            act_facts = [f for f in facts if f.fact_type == "action_recommendation"]
            readiness = next(
                (
                    fact for fact in facts
                    if fact.fact_type == "learning_recommendation_readiness"
                ),
                None,
            )
            summary = next(
                (
                    fact for fact in facts
                    if fact.fact_type == "learning_recommendation_summary"
                ),
                None,
            )
            if readiness:
                direct_answer = str(
                    readiness.details.get("message")
                    or "A target role is needed to make a role-specific learning suggestion."
                )
                interpretation = "No personalized recommendation was generated without resolved role evidence."
            elif act_facts:
                role = summary.entity_name if summary else act_facts[0].details.get("target_role", "the selected role")
                direct_answer = (
                    f"Based on O*NET's occupational technology mapping for **{role}**, "
                    "these are learning candidates to explore—not a scored or guaranteed roadmap:"
                )
                for fact in act_facts:
                    rationale = str(fact.details.get("reason") or "")
                    market_note = (
                        " A separate validated market signal is cited."
                        if fact.details.get("market_trend_available")
                        else " No validated demand trend is asserted for this candidate."
                    )
                    supporting_facts.append(
                        f"**{fact.details.get('recommendation_rank')}. {fact.entity_name}**: "
                        f"{rationale}{market_note} "
                        f"Evidence: `{fact.evidence_reference}`."
                    )
                interpretation = (
                    "This is a deterministic exploration priority, not a weighted skill score or a prerequisite-based "
                    "roadmap. O*NET's existing Hot Technology and In Demand flags determine the first ordering keys, "
                    "followed by normalized label; the flags are static occupational context, not current job-posting "
                    "evidence. Separate validated market trends are cited but do not change rank."
                )
                weekly_time = summary.details.get("weekly_learning_time") if summary else None
                if weekly_time:
                    supporting_facts.append(
                        f"**Recorded weekly learning-time preference**: {weekly_time}. "
                        "No course schedule or completion-time estimate is inferred."
                    )
            else:
                direct_answer = (
                    "No role-associated learning candidates could be produced from the available "
                    "verified occupational mappings."
                )
                interpretation = "No unsupported course, provider, completion time, or market score was inferred."

        elif intent == "compare_entities":
            ent_names = [e.canonical_entity.canonical_name for e in plan.entities if e.canonical_entity] if plan and plan.entities else []
            if not ent_names:
                ent_names = [plan.context_summary.get("primary_entity", "Entity A"), *(plan.context_summary.get("comparison_entities", []))] if plan else ["Entity A", "Entity B"]

            ent_str = " and ".join(f"**{name}**" for name in ent_names[:2]) if len(ent_names) >= 2 else "**selected entities**"
            forecast_facts = [f for f in facts if f.fact_type in {"skill_forecast", "skill_forecast_point"}]
            half_life_facts = [f for f in facts if f.fact_type in {"skill_half_life", "skill_half_life_component"}]
            health_facts = [f for f in facts if f.fact_type in {"skill_health_score", "skill_health_category", "skill_health_component"}]
            if forecast_facts:
                direct_answer = f"Comparative skill demand forecast analysis between {ent_str}."
                for f in facts:
                    val_str = f"{f.metric_value} {f.unit or ''}".strip()
                    supporting_facts.append(f"**{f.entity_name}** ({f.metric_name.replace('_', ' ').title()}): {val_str} [{f.source}]")
                interpretation = (
                    "Comparative demand forecasting projects future monthly trajectories independently per entity using a seasonal-naive baseline. "
                    "Forecasts reflect seasonal carry-forward patterns from historical data; entities with insufficient history or missing observations report insufficient data rather than fabricated projections."
                )
                limitations = [
                    "Forecast horizon is capped at min(6, history_length // 3) months.",
                    "Series from different sources, metrics, or geographies cannot be directly equated.",
                    "Predictions are non-guaranteed estimates based on historical data.",
                ]
            elif half_life_facts:
                direct_answer = f"Comparative Skill Half-Life and market decay evidence analysis between {ent_str}."
                for f in facts:
                    val_str = f"{f.metric_value} {f.unit or ''}".strip()
                    supporting_facts.append(f"**{f.entity_name}** ({f.metric_name.replace('_', ' ').title()}): {val_str} [{f.source}]")
                interpretation = (
                    "Skill Half-Life comparison evaluates historical exponential decay on normalized share series independently per entity. "
                    "Estimates are empirical decay rates on verified historical data; entities without statistically supported decline or sufficient history report not applicable or insufficient data."
                )
                limitations = [
                    "Skill Half-Life is an empirical decay estimate under an exponential decay model (ln(2) / |b|); not an obsolescence guarantee.",
                    "Series from different sources, metrics, or geographies cannot be directly equated.",
                ]
            elif health_facts:
                direct_answer = f"Comparative Skill Health and market evidence analysis between {ent_str}."
                for f in facts:
                    val_str = f"{f.metric_value} {f.unit or ''}".strip()
                    supporting_facts.append(f"**{f.entity_name}** ({f.metric_name.replace('_', ' ').title()}): {val_str} [{f.source}]")
                interpretation = (
                    "Skill Health comparison evaluates relative share momentum independently per entity. "
                    "Scores are deterministic measurements based on source-specific normalized shares; entities without eligible history report insufficient data rather than forced comparisons."
                )
                limitations = [
                    "Skill Health scores reflect relative momentum, not absolute hiring volume or guaranteed future demand.",
                    "Series from different sources or units cannot be directly equated.",
                ]
            elif any(f.fact_type in {"task_exposure_summary", "task_exposure_record"} for f in facts):
                direct_answer = f"Comparative AI task exposure and disruption analysis between {ent_str}."
                for f in facts:
                    if f.fact_type == "task_exposure_summary":
                        supporting_facts.append(f"**{f.entity_name}** ({f.metric_name.replace('_', ' ').title()}): {f.metric_value} [{f.source}]")
                    elif f.fact_type == "task_exposure_record":
                        tdet = f.details
                        supporting_facts.append(f"**{f.entity_name}** (Task {tdet.get('task_id')}): {str(f.metric_value).title()} exposure ({tdet.get('observed_ai_usage_mode')}) - {tdet.get('task_statement')}")
                interpretation = (
                    "Comparative AI task exposure evaluates theoretical task-level capability overlap independently per occupation. "
                    "Task exposure does NOT measure or imply job disappearance, headcount reduction, or occupation displacement. "
                    "Occupations with high exposure typically experience human-in-the-loop task augmentation rather than complete automation."
                )
                limitations = [
                    "Task exposure measures theoretical capability overlap only and never implies job disappearance or headcount reduction.",
                    "Workforce hiring outcomes are tracked from empirical market demand series, not task exposure scores.",
                    "Comparisons require verified, open-licensed reference records for each evaluated occupation.",
                ]
            else:
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
            summary = next(
                (fact for fact in facts if fact.fact_type == "company_workforce_summary"),
                None,
            )
            coverage_facts = [
                fact for fact in facts if fact.fact_type == "company_skill_coverage"
            ]
            declared_priorities = [
                fact for fact in facts
                if fact.fact_type == "company_declared_priority_skill"
            ]
            company_name = (
                summary.entity_name if summary else "the authenticated company"
            )
            active_count = summary.metric_value if summary else 0
            skill_profile_count = (
                summary.details.get("members_with_self_reported_skill_records", 0)
                if summary else 0
            )
            if summary and summary.readiness_state == "insufficient_data":
                if active_count == 0:
                    direct_answer = (
                        f"No active, verified connected employee records were available for "
                        f"**{company_name}**, so workforce skill coverage cannot be calculated."
                    )
                else:
                    direct_answer = (
                        f"**{company_name}** has active connected employee records, but none of the "
                        "retrieved profiles contain a self-reported skill-domain record."
                    )
            else:
                direct_answer = (
                    f"**{company_name}** has {active_count} active connected employee profile(s); "
                    f"{skill_profile_count} contain self-reported skill-domain records. "
                    "Recorded skill coverage is not a measure of organizational competence."
                )
            for fact in coverage_facts:
                supporting_facts.append(
                    f"**{fact.entity_name}**: recorded by {fact.metric_value} of "
                    f"{active_count} active connected employee profile(s) "
                    "(self-reported; proficiency not inferred)."
                )
            for fact in declared_priorities:
                if fact.metric_value == "not_represented":
                    supporting_facts.append(
                        f"**Company-declared priority not represented in retrieved skill records**: "
                        f"{fact.entity_name}. This is an exact-label/canonical-ID comparison, not proof "
                        "of an organizational skill gap or approved role requirement."
                    )
            if summary and summary.details.get("profiles_with_self_reported_confidence_values"):
                supporting_facts.append(
                    f"Self-reported confidence values were present in "
                    f"{summary.details['profiles_with_self_reported_confidence_values']} profile(s); "
                    "they are not treated as verified proficiency."
                )
            else:
                supporting_facts.append(
                    "No self-reported proficiency/confidence values were present in the retrieved profiles."
                )

            interpretation = (
                "The aggregate includes only active company membership records that also match the "
                "employee's stored company connection, and it uses employee-entered onboarding skill "
                "domains. Missing profile entries mean missing records, not proof that employees lack "
                "those skills. Company-declared priority domains are context, not generic taxonomy "
                "requirements. No individual employee identifiers are returned."
            )

        elif intent == "retrieve_evidence":
            ent_name = plan.context_summary.get("primary_entity") or "Market Evidence"
            ev_fact = next((f for f in facts if f.fact_type == "evidence_summary"), None)
            cnt = ev_fact.metric_value if ev_fact else len(evidence)
            if not cnt:
                reason = ev_fact.details.get("reason") if ev_fact and ev_fact.details else None
                direct_answer = (
                    f"No verified evidence records are available for **{ent_name}**. "
                    f"{reason or 'No matching stored evidence was found.'}"
                )
            else:
                source_names = list(dict.fromkeys(item.source for item in evidence if item.source))
                source_text = f" from {', '.join(source_names[:4])}" if source_names else ""
                direct_answer = (
                    f"Evidence retrieval for **{ent_name}** found **{cnt}** verified stored records{source_text}."
                )
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
            series = {
                (f.source, f.details.get("signal_type", f.metric_name), f.unit,
                 f.details.get("location") or f.details.get("geography"), f.series_id)
                for f in hist_facts
            }
            direct_answer = (
                f"Retrieved **{len(hist_facts)}** historical observation records for **{ent_name}** "
                f"across **{len(series)}** source-specific series."
            )
            for f in hist_facts[:5]:
                geo = f" · {f.details.get('location') or f.details.get('geography')}" if (f.details.get('location') or f.details.get('geography')) else ""
                grain = f" · {f.details.get('frequency')}" if f.details.get("frequency") else ""
                provenance = f" · {f.history_type or 'history type unavailable'} / {f.data_origin or 'origin unavailable'}"
                supporting_facts.append(
                    f"**{f.period}** · {f.source} {f.details.get('signal_type', f.metric_name)}: "
                    f"{f.metric_value} {f.unit or ''}{geo}{grain}{provenance}"
                )
            if not hist_facts:
                supporting_facts = [f"**{f.metric_name}**: {f.metric_value}" for f in facts]
            interpretation = "Historical observations retain their source, metric, unit, frequency, geography, and series provenance. GitHub developer activity, Stack Exchange questions, and Wikipedia pageviews describe different signals and are not combined."
            limitations.append("Historical observations are completed periods from source-specific series; snapshots, partial periods, and values from incompatible series are excluded from combined analysis.")

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
                readiness = next(
                    (f for f in facts if f.fact_type == "analysis_readiness" and f.metric_name == "market_evidence_readiness"),
                    None,
                )
                direct_answer = (
                    f"No stored market observation is available to verify current hiring demand for **{readiness.entity_name or 'the requested skill'}**."
                    if readiness else "No verified market snapshot is available for this request."
                )
                supporting_facts = ["**Market evidence**: unavailable in the configured observation store."]
                interpretation = "No demand level or trend can be inferred from static taxonomy references."
                limitations = [
                    "ESCO and O*NET taxonomy associations describe reference relationships; they are not evidence of current hiring demand.",
                    "A current demand conclusion requires persisted empirical market observations for the requested skill.",
                ]

        else:
            direct_answer = f"Synthesized intelligence summary based on {len(facts)} verified structured facts."
            supporting_facts = [f"**{f.metric_name}**: {f.metric_value} ({f.source})" for f in facts]
            interpretation = "Intelligence synthesis grounded in verified platform records."
            limitations = ["Data grounded strictly in internal and ingested analytical records."]

        sections = [direct_answer.strip()]
        if supporting_facts:
            sections.append("**Observed details**\n" + "\n".join(f"- {fact}" for fact in supporting_facts))
        if evidence_citations and intent not in {"explain_concept", "lookup_skill_reference"}:
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
        allowed_numbers: set[str] = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "50", "90", "100", "2018", "2024", "2025", "2026", "2027"}
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

        if plan and plan.context_summary:
            for ctx_key in ("_demand_sample_sizes", "_demand_exclusions"):
                for num_str in re.findall(r'\b\d+(?:\.\d+)?\b', str(plan.context_summary.get(ctx_key) or "")):
                    allowed_numbers.add(num_str)

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

"""Greenfield Intelligence Engine V2 — Execution Orchestrator.

Coordinates intent planning, analytical readiness checking, domain engine execution,
and structured response formatting for all 15 capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

import uuid
from app.intelligence_v2.capability_registry import V2CapabilityRegistry, canonical_capability_id
from app.intelligence_v2.contracts import V2EvidenceItem, V2StructuredFact
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.intelligence_v2.intent_planner import PlannedIntent, V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.market_intelligence import V2MarketIntelligenceEngine
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.intelligence_v2.role_actions import V2RoleActionEngine
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine, get_concept_explanation_with_example
from app.intelligence_v2.skill_mapping import V2SkillMapper
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)
from app.storage.conversation_store import ConversationStore
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


class V2Orchestrator:
    """End-to-end execution coordinator for Greenfield Intelligence Engine V2."""

    def __init__(
        self,
        store: ReferenceDataStore | None = None,
        skill_mapper: V2SkillMapper | None = None,
        evidence_retriever: V2EvidenceRetriever | None = None,
        action_engine: V2RoleActionEngine | None = None,
        capability_registry: V2CapabilityRegistry | None = None,
        intent_planner: V2IntentPlanner | None = None,
        conversation_store: ConversationStore | None = None,
        gemini_b_service: Any | None = None,
        observation_store: Any | None = None,
    ) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.skill_mapper = skill_mapper or V2SkillMapper(self.store)
        self.evidence_retriever = evidence_retriever or V2EvidenceRetriever(self.store)
        self.action_engine = action_engine or V2RoleActionEngine()
        self.capability_registry = capability_registry or V2CapabilityRegistry()
        self.intent_planner = intent_planner or V2IntentPlanner(self.skill_mapper)
        self.conversation_store = conversation_store or ConversationStore.get_instance()
        self.gemini_b_service = gemini_b_service

        # Domain engines
        self.skill_engine = V2SkillIntelligenceEngine(
            store=self.store,
            skill_mapper=self.skill_mapper,
            evidence_retriever=self.evidence_retriever,
            action_engine=self.action_engine,
        )
        self.market_engine = V2MarketIntelligenceEngine(
            store=self.store,
            evidence_retriever=self.evidence_retriever,
            observation_store=observation_store,
        )
        self.job_engine = V2JobIntelligenceEngine(
            store=self.store,
            skill_mapper=self.skill_mapper,
            evidence_retriever=self.evidence_retriever,
            action_engine=self.action_engine,
        )

    def execute_request(
        self,
        request: CoreIntelligenceAnswerRequest,
        authenticated_user: AuthenticatedUser | None = None,
    ) -> CoreIntelligenceAnswerResponse:
        """Route and execute a user request through Greenfield V2 pipelines."""
        portal = request.portal_type or "individual"
        user_id = authenticated_user.uid if authenticated_user else "anonymous"
        user_company_id = getattr(authenticated_user, "company_id", None) if authenticated_user else request.company_id

        # Company boundary guard: company portal requests require valid company membership
        if portal == "company":
            if not authenticated_user or not user_company_id:
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}",
                    user_message=request.message,
                    portal_type=portal,
                    domain="market",
                    intent=request.capability_id or "unknown",
                    plan_status="blocked",
                    execution_status="blocked",
                    status="error",
                    answer="Active company membership is required for company intelligence queries.",
                    answer_origin="deterministic",
                    limitations=["Active company membership required."],
                    reason_codes=["UNAUTHORIZED_COMPANY_ACCESS"],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

        # Conversation access guard: verify conversation belongs to user/company
        if request.conversation_id:
            allowed, deny_reason = self.conversation_store.check_conversation_access(
                request.conversation_id,
                user_id=user_id,
                company_id=user_company_id,
            )
            if not allowed:
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}",
                    user_message=request.message,
                    portal_type=portal,
                    domain=request.domain or "skill",
                    intent=request.capability_id or "unknown",
                    plan_status="blocked",
                    execution_status="blocked",
                    status="error",
                    answer="Access denied to conversation.",
                    answer_origin="deterministic",
                    limitations=["The requested conversation is unavailable or access is not authorized."],
                    reason_codes=["UNAUTHORIZED_CONVERSATION_ACCESS"],
                    conversation_id=None,
                    client_message_id=request.client_message_id,
                )
        elif request.domain and user_id is not None and authenticated_user is not None:
            # Auto-create conversation if domain provided but conversation_id absent
            try:
                created_conv = self.conversation_store.create_conversation(
                    user_id=user_id,
                    portal_type=portal,
                    company_id=user_company_id,
                    domain=request.domain,
                    filters=request.filters,
                )
                request = request.model_copy(update={"conversation_id": created_conv.conversation_id})
            except Exception as exc:
                logger.debug("Optional conversation auto-creation skipped: %s", exc)

        # Context packaging
        planner_context: dict[str, Any] = {
            "selected_skill": request.selected_skills[0] if request.selected_skills else None,
            "selected_role": request.target_role or (request.selected_roles[0] if request.selected_roles else None),
            "filters": request.filters,
        }

        # 1. Intent Planning
        planned_intent: PlannedIntent = self.intent_planner.plan(
            query=request.message,
            portal_type=portal,
            context=planner_context,
        )

        if planned_intent.capability_id is None and not request.capability_id:
            return CoreIntelligenceAnswerResponse(
                request_id=f"ans_{uuid.uuid4().hex[:12]}",
                user_message=request.message,
                portal_type=portal,
                domain=request.domain if request.domain in {"skill", "market", "job"} else None,
                intent="unsupported_or_unclear",
                plan_status="requires_clarification",
                execution_status="requires_clarification",
                status="not_applicable",
                answer=planned_intent.reason,
                answer_origin="deterministic",
                planned_capabilities=[],
                capabilities_used=[],
                limitations=["No data capability was selected because the request was not classifiable."],
                reason_codes=["INTENT_CLARIFICATION_REQUIRED"],
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
            )

        # Allow explicit capability override if client provided capability_id or domain
        if request.capability_id:
            public_capability_id = request.capability_id
            cap = canonical_capability_id(public_capability_id, request.domain)
            planned_intent.capability_id = cap
            cap_def = self.capability_registry.get_capability(cap)
            if not cap_def:
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}", user_message=request.message,
                    portal_type=portal, domain=request.domain or "skill", intent=public_capability_id,
                    plan_status="blocked", execution_status="unsupported", status="error",
                    answer=f"Unsupported capability '{public_capability_id}'. Select an enabled feature from the capability catalog.",
                    answer_origin="deterministic", limitations=["The requested capability is not registered or enabled."],
                    reason_codes=["CAPABILITY_UNSUPPORTED"], conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

            # Check domain mismatch
            domain_norm = {"skill_intelligence": "skill", "market_intelligence": "market", "job_intelligence": "job"}
            expected_domain = domain_norm.get(cap_def.domain, cap_def.domain)
            req_domain = domain_norm.get(request.domain or "", request.domain)
            if req_domain and req_domain in {"skill", "market", "job"} and expected_domain != req_domain:
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}", user_message=request.message,
                    portal_type=portal, domain=request.domain, intent=public_capability_id,
                    plan_status="blocked", execution_status="unsupported", status="error",
                    answer=f"Capability '{public_capability_id}' belongs to the '{expected_domain}' domain, but was invoked under the '{req_domain}' domain.",
                    answer_origin="deterministic", limitations=["Feature domain mismatch."],
                    reason_codes=["CAPABILITY_DOMAIN_MISMATCH"], conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

            if cap in {
                "skill_future_relevance_score",
                "skill_change_alert",
                "adaptive_skill_roadmap",
                "technology_adoption_shift_detector",
                "technology_impact_explorer",
                "skill_based_job_match",
                "career_transition_opportunity",
            }:
                feat_name = cap_def.name if cap_def else cap
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}",
                    user_message=request.message,
                    portal_type=portal,
                    domain=request.domain or expected_domain,
                    intent=cap,
                    executed_primary_capability=cap,
                    planned_primary_capability=cap,
                    capabilities_used=[],
                    planned_capabilities=[cap],
                    plan_status="ready_to_execute",
                    execution_status="blocked",
                    status="unavailable",
                    answer=f"The feature '{feat_name}' is registered in the capability catalog. Its analytical engine is pending implementation in Phase 2.",
                    answer_origin="deterministic",
                    limitations=["Feature engine implementation pending Phase 2."],
                    reason_codes=["CAPABILITY_PENDING_IMPLEMENTATION"],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )
        else:
            public_capability_id = planned_intent.capability_id
            cap = canonical_capability_id(public_capability_id, request.domain)
            planned_intent.capability_id = cap
            cap_def = self.capability_registry.get_capability(cap)
            if cap_def and cap in {
                "skill_future_relevance_score",
                "skill_change_alert",
                "adaptive_skill_roadmap",
                "technology_adoption_shift_detector",
                "technology_impact_explorer",
                "skill_based_job_match",
                "career_transition_opportunity",
            }:
                feat_name = cap_def.name if cap_def else cap
                return CoreIntelligenceAnswerResponse(
                    request_id=f"ans_{uuid.uuid4().hex[:12]}",
                    user_message=request.message,
                    portal_type=portal,
                    domain=request.domain or "skill",
                    intent=cap,
                    executed_primary_capability=cap,
                    planned_primary_capability=cap,
                    capabilities_used=[],
                    planned_capabilities=[cap],
                    plan_status="ready_to_execute",
                    execution_status="blocked",
                    status="unavailable",
                    answer=f"The feature '{feat_name}' is registered in the capability catalog. Its analytical engine is pending implementation in Phase 2.",
                    answer_origin="deterministic",
                    limitations=["Feature engine implementation pending Phase 2."],
                    reason_codes=["CAPABILITY_PENDING_IMPLEMENTATION"],
                    conversation_id=request.conversation_id,
                    client_message_id=request.client_message_id,
                )

        _PUBLIC_GUEST_CAPS = {
            # 7 Approved Phase 1 features
            "skill_future_relevance_score",
            "skill_change_alert",
            "adaptive_skill_roadmap",
            "technology_adoption_shift_detector",
            "technology_impact_explorer",
            "skill_based_job_match",
            "career_transition_opportunity",
            # Canonical registry capability IDs
            "trend_velocity_analysis",
            "skill_health_analysis",
            "skill_half_life_analysis",
            "skill_forecasting_half_life",
            "skill_technology_reference",
            "related_occupations",
            "occupation_software_skills",
            "occupation_lookup",
            "market_snapshot",
            "historical_signal_retrieval",
            "evidence_provenance_retrieval",
            "ai_task_exposure",
            # V2 engine capability IDs
            "skill_demand_trends",
            "skill_historical_signals",
            "skill_role_alignment",
            "skill_evidence_citations",
            "skill_reference_profile",
            "skill_lookup",
            "related_skills",
            "career_mobility_pathways",
            "market_intelligence_snapshot",
            "market_tech_signals",
            "market_trend_velocity",
            "market_evidence_citations",
            "job_verified_postings",
            "job_role_requirements",
            "job_mobility_pathways",
            "job_preparation_actions",
            "role_preparation_actions",
            # Additional public aliases
            "skill_health",
            "skill_half_life",
            "skill_demand_forecast",
            "emerging_skills",
            "declining_skills",
            "skill_adjacency",
            "career_pathways",
            "role_skill_profiles",
            "talent_supply_proxy",
            "hiring_demand_trends",
        }
        if authenticated_user is None and public_capability_id not in _PUBLIC_GUEST_CAPS and cap not in _PUBLIC_GUEST_CAPS:
            return CoreIntelligenceAnswerResponse(
                request_id=f"ans_{uuid.uuid4().hex[:12]}",
                user_message=request.message,
                portal_type=portal,
                domain=request.domain or "skill",
                intent=planned_intent.capability_id,
                plan_status="blocked",
                execution_status="blocked",
                status="error",
                answer="This capability requires an authenticated account. Please sign in to access personalized profile and workforce insights.",
                answer_origin="deterministic",
                limitations=["Authentication required for personalized capabilities."],
                reason_codes=["AUTHENTICATION_REQUIRED"],
                conversation_id=None,
                client_message_id=request.client_message_id,
            )

        # 2. Readiness Evaluation
        # Check hiring demand availability
        demand_months = 0
        try:
            with self.store._connect() as conn:
                r = conn.execute("SELECT COUNT(DISTINCT period) as cnt FROM market_observations").fetchone()
                if r:
                    demand_months = int(r["cnt"])
        except Exception:
            demand_months = 0

        has_profile = bool(request.selected_skills)
        readiness = self.capability_registry.evaluate_readiness(
            cap,
            months_available=demand_months,
            has_profile=has_profile,
            has_reference_data=True,
        )

        if (
            cap != "market_trend_velocity"
            and not readiness.is_executable
            and readiness.state == "insufficient_data"
        ):
            # Return truthful insufficient data response
            evidence = self.evidence_retriever.get_hiring_demand_evidence(
                planned_intent.target_skill or planned_intent.target_role or "general"
            )
            response = V2ResponseFormatter.format_response(
                user_message=request.message,
                portal_type=portal,
                intent=planned_intent,
                result=None,
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
                execution_status="insufficient_data",
                status_override="insufficient_data",
                error_message=readiness.reason,
                domain_override=request.domain,
            )
            return self._maybe_apply_gemini_b(response, cap, planned_intent.target_skill, request, user_id, portal, user_company_id)

        # 3. Domain Engine Execution
        if cap in {"skill_role_alignment", "job_profile_alignment"} and (not request.selected_skills or not (request.target_role or request.selected_roles)):
            return V2ResponseFormatter.format_response(
                user_message=request.message, portal_type=portal, intent=planned_intent, result=None,
                conversation_id=request.conversation_id, client_message_id=request.client_message_id,
                execution_status="requires_clarification", status_override="insufficient_data",
                error_message="Personalized alignment requires explicitly selected profile skills and a resolvable target role.",
                domain_override=request.domain,
            )
        target_s = planned_intent.target_skill or (request.selected_skills[0] if request.selected_skills else "Python")
        target_r = planned_intent.target_role or request.target_role or "Software Developer"
        geo = planned_intent.geography or request.location or "all"

        result = None

        try:
            # Skill Intelligence features
            if cap == "skill_demand_trends":
                result = self.skill_engine.run_demand_trends(target_s, geography=geo)
            elif cap in {"skill_health_analysis", "skill_health"}:
                result = self.skill_engine.run_skill_health(target_s, geography=geo)
            elif cap in {"skill_demand_forecast", "skill_forecasting_half_life"}:
                result = self.skill_engine.run_demand_forecast(target_s, geography=geo)
            elif cap == "hiring_demand_trends":
                result = self.skill_engine.run_hiring_demand_trends(target_s, geography=geo)
            elif cap == "skill_historical_signals":
                result = self.skill_engine.run_historical_signals(target_s, geography=geo)
            elif cap == "skill_role_alignment":
                result = self.skill_engine.run_role_alignment(target_r, request.selected_skills)
            elif cap == "skill_evidence_citations":
                result = self.skill_engine.run_evidence_citations(target_s)
            elif cap == "skill_reference_profile":
                result = self.skill_engine.run_reference_profile(target_s)
            elif cap in {"skill_lookup", "occupation_lookup"}:
                exact_occupation_query = bool(
                    planned_intent.target_role
                    and not request.selected_skills
                )
                result = self.skill_engine.run_skill_lookup(
                    target_r if exact_occupation_query else target_s or target_r,
                    entity_type="occupation" if exact_occupation_query else "all",
                    context=request.message,
                    exact_occupation=exact_occupation_query,
                )
            elif cap in {"related_skills", "skill_adjacency"}:
                result = self.skill_engine.run_related_skills(target_s)
            elif cap == "skill_action_recommendations":
                result = self.skill_engine.run_action_recommendations(target_s, target_role=target_r)

            # Market Intelligence features
            elif cap == "market_intelligence_snapshot":
                result = self.market_engine.run_snapshot(geography=geo)
            elif cap == "market_tech_signals":
                result = self.market_engine.run_tech_signals(geography=geo)
            elif cap == "market_trend_velocity":
                result = self.market_engine.run_trend_velocity(target_s, geography=geo)
            elif cap == "market_evidence_citations":
                result = self.market_engine.run_evidence_citations()

            # Job Intelligence features
            elif cap == "job_verified_postings":
                role_or_skill = target_r if target_r and target_r != "Software Developer" else (target_s or target_r or "Software Developer")
                filters = request.filters or {}
                country = filters.get("country") or (geo if geo and geo not in {"all", "global"} else None)
                location = filters.get("location") or request.location
                if not location:
                    from app.services.question_classification_service import extract_location
                    location = extract_location(request.message)
                date_posted = filters.get("date_posted")
                remote = (
                    "remote" in request.message.casefold()
                    or str(filters.get("remote_mode") or "").casefold() == "remote"
                )
                result = self.job_engine.run_verified_postings(
                    role_or_skill=role_or_skill,
                    geography=geo,
                    country=country,
                    location=location,
                    date_posted=date_posted,
                    remote=remote,
                )
            elif cap == "job_role_requirements":
                result = self.job_engine.run_role_requirements(target_r)
            elif cap in {"job_mobility_pathways", "career_mobility_pathways", "career_pathways"}:
                result = self.job_engine.run_mobility_pathways(target_r)
            elif cap == "job_profile_alignment":
                result = self.job_engine.run_profile_alignment(target_r, request.selected_skills)
            elif cap in {"job_preparation_actions", "role_preparation_actions"}:
                timeline = (
                    (request.filters or {}).get("timeline")
                    or (request.filters or {}).get("desired_timeline")
                    or (request.filters or {}).get("preparation_period")
                    or request.time_range
                )
                result = self.job_engine.run_preparation_actions(
                    target_role=target_r,
                    user_skills=request.selected_skills or None,
                    desired_timeline=timeline,
                )
            else:  # The registry and dispatch table must remain in lockstep.
                raise ValueError(f"No execution handler is registered for capability '{cap}'.")

            # Check if this is a comparison query with two or more entities
            is_comp = (
                ("compare" in request.message.lower() or " vs " in request.message.lower() or " versus " in request.message.lower())
                and len(planned_intent.entities) >= 2
            )
            if is_comp and result and len(planned_intent.entities) >= 2:
                target_s2 = planned_intent.entities[1].canonical_name
                try:
                    if cap in {"hiring_demand_trends"}:
                        result2 = self.skill_engine.run_hiring_demand_trends(target_s2, geography=geo)
                    elif cap in {"market_trend_velocity"}:
                        result2 = self.market_engine.run_trend_velocity(target_s2, geography=geo)
                    elif cap in {"skill_reference_profile"}:
                        result2 = self.skill_engine.run_reference_profile(target_s2)
                    else:
                        result2 = self.skill_engine.run_demand_trends(target_s2, geography=geo)
                    if result2:
                        result.facts.extend(result2.facts)
                        result.evidence.extend(result2.evidence)
                        result.headline = f"Comparison analysis: {target_s} vs {target_s2} across verified platform signals."
                except Exception as comp_exc:
                    logger.debug("Failed executing secondary comparison entity %s: %s", target_s2, comp_exc)

        except Exception as exc:
            logger.exception("Error executing capability %s: %s", cap, exc)
            return V2ResponseFormatter.format_response(
                user_message=request.message,
                portal_type=portal,
                intent=planned_intent,
                result=None,
                conversation_id=request.conversation_id,
                client_message_id=request.client_message_id,
                execution_status="failed",
                status_override="error",
                error_message=f"Execution error encountered: {exc}",
                domain_override=request.domain,
            )

        # 4. Format and Return Public Contract
        response = V2ResponseFormatter.format_response(
            user_message=request.message,
            portal_type=portal,
            intent=planned_intent,
            result=result,
            conversation_id=request.conversation_id,
            client_message_id=request.client_message_id,
            domain_override=request.domain,
        )
        response = self._maybe_apply_gemini_b(response, cap, planned_intent.target_skill, request, user_id, portal, user_company_id)

        # 5. Persist turn to conversation store if conversation_id exists
        if response.conversation_id:
            try:
                self.conversation_store.save_turn(
                    conversation_id=response.conversation_id,
                    user_id=user_id,
                    company_id=user_company_id,
                    portal_type=portal,
                    domain=response.domain,
                    user_message=request.message,
                    intent=response.intent,
                    primary_entity=response.resolved_entity,
                    target_role=request.target_role,
                    time_range=request.time_range,
                    selected_skills=request.selected_skills,
                    selected_companies=request.selected_companies,
                    filters=dict(response.applied_filters or {}),
                    execution_status=response.execution_status,
                    answer_summary=response.answer[:200] if response.answer else None,
                    client_message_id=request.client_message_id,
                )
            except Exception as exc:
                logger.debug("Failed to persist conversation turn: %s", exc)

        return response

    def _maybe_apply_gemini_b(
        self,
        response: CoreIntelligenceAnswerResponse,
        capability_id: str,
        planned_skill: str | None,
        request: CoreIntelligenceAnswerRequest,
        user_id: str,
        portal_type: str,
        company_id: str | None,
    ) -> CoreIntelligenceAnswerResponse:
        policy = FEATURE_ANSWER_POLICIES.get(canonical_capability_id(capability_id, request.domain))
        if (
            not policy
            or not policy.gemini_b_fallback
            or policy.provider_data_required
            or portal_type in {"company", "employee"}
            or company_id
            or response.status not in {"insufficient_data", "unavailable"}
            or any(
                fact.data_origin not in {"unavailable", "benchmark"}
                and fact.readiness_state != "insufficient_data"
                for fact in response.facts
            )
            or any(
                item.data_origin not in {"unavailable", "benchmark"}
                and item.readiness_state != "insufficient_data"
                and item.quality != "insufficient_history"
                for item in response.evidence
            )
        ):
            return response

        public_skill_name = None
        if policy.domain in {"skill", "market"} and not request.selected_skills and planned_skill:
            # Only a canonical public taxonomy label can leave the service.
            try:
                mapping = self.skill_mapper.normalize(planned_skill)
                if mapping.status == "matched" and mapping.canonical_id:
                    public_skill_name = mapping.canonical_name
            except Exception:
                public_skill_name = None

        service = self.gemini_b_service
        if service is None:
            # Avoid even loading provider configuration from local environment
            # files in tests unless an explicit mock service was injected.
            import os
            if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
                return response
            from app.services.gemini_b_guidance_service import GeminiBGuidanceService
            service = GeminiBGuidanceService()
            self.gemini_b_service = service
        guidance = service.generate(
            capability_id=capability_id,
            public_skill_name=public_skill_name,
            user_id=user_id,
        )
        if not guidance:
            concept_exp = get_concept_explanation_with_example(planned_skill or public_skill_name)
            concept_part = f"{concept_exp}\n\n" if concept_exp else ""
            unavailable_note = (
                f"{concept_part}"
                "General AI guidance is unavailable right now. This response contains no new measured market data "
                "or generated evidence. Try a narrower question or check again when verified observations are available."
            )
            existing_answer = (response.answer or "").strip()
            limitations = list(response.limitations or [])
            limitations.append("No Gemini guidance was available; no measured data or evidence was added.")
            next_actions = (
                [
                    "Choose one public signal source and a consistent geography for comparison.",
                    "Collect at least four consecutive completed periods from that same series; hiring trends need a separate verified monthly series.",
                ]
                if capability_id == "market_trend_velocity"
                else [
                    "Try a narrower question about the skill or capability.",
                    "Check again when verified observations are available.",
                ]
            )
            return response.model_copy(update={
                "answer": f"{existing_answer}\n\n{unavailable_note}".strip(),
                "next_actions": next_actions,
                "limitations": list(dict.fromkeys(limitations)),
            })
        return response.model_copy(update={
            "answer": guidance,
            "answer_origin": "gemini",
            "answer_title": policy.title,
            "answer_type": policy.answer_type,
            "source_mode": "ai_general_guidance",
            "visualization": None,
            "facts": [],
            "evidence": [],
            "metric_results": [],
            "next_actions": [],
            "status": "ready",
            "execution_status": "completed",
            "limitations": ["General AI guidance only; this is not a measured TalentScope result."],
            "reason_codes": ["AI_GENERAL_GUIDANCE_ONLY"],
        })

    answer = execute_request

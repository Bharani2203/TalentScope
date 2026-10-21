"""Capability Registry Service for G2.6.

Defines and evaluates the platform's control layer for intelligence capabilities.
Distinguishes between global implementation status and per-request runtime readiness.
Strictly preserves:
- G0-G2.5 contracts and read safety
- Zero Firestore read/writes during registry evaluation
- Zero outbound network calls
- Zero synthetic observation or period generation
- Full reuse of analytical readiness gates (trend >= 4 periods, forecast >= 6 periods)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import SKILLS, canonical_skill_id
from app.models.capability_registry import (
    CapabilityCatalogResponse,
    CapabilityEvaluationRequest,
    CapabilityEvaluationResponse,
    CapabilityEvaluationResult,
    CapabilityId,
    CapabilityRecord,
    CapabilityState,
)
from app.models.entity_registry import EntityResolutionRequest
from app.models.skill_intelligence import MarketObservation
from app.services.entity_registry_service import EntityRegistryService
from app.storage.reference_store import ReferenceDataStore


# =============================================================================
# AUTHORITATIVE CAPABILITY CATALOG (15 CANDIDATES)
# =============================================================================

CAPABILITY_CATALOG: dict[str, CapabilityRecord] = {
    "skill_future_relevance_score": CapabilityRecord(
        capability_id="skill_future_relevance_score",
        name="Skill Future Relevance Score",
        description="Assess a skill's potential future relevance using available historical and technology-adoption signals.",
        supported_domains=["skill"],
        supported_intent="assess_skill_future_relevance",
        supported_entity_types=["skill", "technology"],
        required_inputs=["skill_name"],
        optional_inputs=["target_role"],
        required_signals=["historical_observations", "technology_adoption"],
        required_sources=["internal_registry", "github_innovation_graph", "historical_observations"],
        min_readiness_periods=None,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Requires verified historical signals and adoption data; predictions are bounded by observable data.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["canonical_skill_id", "source_dataset"],
    ),
    "skill_change_alert": CapabilityRecord(
        capability_id="skill_change_alert",
        name="Skill Change Alert",
        description="Identify supported increases, decreases, or stable patterns in comparable skill signals.",
        supported_domains=["skill"],
        supported_intent="detect_skill_change_alert",
        supported_entity_types=["skill", "technology"],
        required_inputs=["skill_name"],
        required_signals=["historical_observations", "developer_adoption"],
        required_sources=["github_innovation_graph", "historical_observations"],
        min_readiness_periods=4,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Requires comparable historical periods without synthetic interpolation.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["canonical_skill_id", "period_granularity"],
    ),
    "adaptive_skill_roadmap": CapabilityRecord(
        capability_id="adaptive_skill_roadmap",
        name="Adaptive Skill Roadmap",
        description="Recommend an ordered learning plan based on current skills, a target role, and available skill relationships.",
        supported_domains=["skill"],
        supported_intent="generate_adaptive_skill_roadmap",
        supported_entity_types=["occupation", "skill"],
        required_inputs=["target_role"],
        optional_inputs=["current_skills"],
        required_signals=["reference_taxonomy", "curriculum_structure"],
        required_sources=["onet", "esco"],
        min_readiness_periods=None,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Based on standardized occupational taxonomy and reference curricula, not guaranteed placement.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["onet_soc_code", "taxonomy_version"],
    ),
    "technology_adoption_shift_detector": CapabilityRecord(
        capability_id="technology_adoption_shift_detector",
        name="Technology Adoption Shift Detector",
        description="Compare supported technology-adoption signals over comparable periods and identify meaningful changes.",
        supported_domains=["market"],
        supported_intent="detect_technology_adoption_shift",
        supported_entity_types=["technology", "skill"],
        required_inputs=["technologies"],
        required_signals=["developer_adoption", "public_interest"],
        required_sources=["github_innovation_graph", "stack_exchange", "wikipedia"],
        min_readiness_periods=2,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Preserves each source's native metric and provenance; developer activity is not conflated with employer demand.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["source_dataset", "period_granularity"],
    ),
    "technology_impact_explorer": CapabilityRecord(
        capability_id="technology_impact_explorer",
        name="Technology Impact Explorer",
        description="Explore supported relationships between technologies, skills, and occupations.",
        supported_domains=["market"],
        supported_intent="explore_technology_impact",
        supported_entity_types=["technology", "skill", "occupation"],
        required_inputs=["technology_or_skill"],
        optional_inputs=["target_occupation"],
        required_signals=["reference_taxonomy", "crosswalk"],
        required_sources=["onet", "esco"],
        min_readiness_periods=None,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Accepts a technology or skill as primary input; optionally accepts a target occupation.",
            "Reflects structured taxonomy mappings between technologies and occupations without speculative projection.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["taxonomy_version", "onet_soc_code"],
    ),
    "skill_based_job_match": CapabilityRecord(
        capability_id="skill_based_job_match",
        name="Skill-Based Job Match",
        description="Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps.",
        supported_domains=["job"],
        supported_intent="match_skills_to_jobs",
        supported_entity_types=["occupation", "skill"],
        required_inputs=["current_skills"],
        optional_inputs=["target_role", "location"],
        required_signals=["hiring_demand", "reference_taxonomy"],
        required_sources=["jsearch", "adzuna", "verified_postings"],
        min_readiness_periods=None,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Matches against retrieved and verified job postings; not an exhaustive index of all market vacancies.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["posting_id", "source_provider"],
    ),
    "career_transition_opportunity": CapabilityRecord(
        capability_id="career_transition_opportunity",
        name="Career Transition Opportunity",
        description="Identify possible related target roles and the skills that may be needed for a transition.",
        supported_domains=["job"],
        supported_intent="explore_career_transition",
        supported_entity_types=["occupation", "skill"],
        required_inputs=["current_role_or_target_role"],
        optional_inputs=["current_skills"],
        required_signals=["reference_taxonomy", "mobility_pathways"],
        required_sources=["onet", "esco"],
        min_readiness_periods=None,
        global_status="available",
        implementation_status="pending",
        reason_code="CAPABILITY_ACTIVE",
        handler=None,
        limitations=[
            "Accepts a current role or target role; accepts current skills when available.",
            "Identifies transition opportunities based on shared occupational tasks and skills in O*NET/ESCO baselines.",
            "Analytical engine is pending implementation in Phase 2; not execution-ready.",
        ],
        provenance_requirements=["onet_soc_code", "taxonomy_version"],
    ),
}

CAPABILITY_DOMAINS: dict[str, list[str]] = {
    "skill_future_relevance_score": ["skill"],
    "skill_change_alert": ["skill"],
    "adaptive_skill_roadmap": ["skill"],
    "technology_adoption_shift_detector": ["market"],
    "technology_impact_explorer": ["market"],
    "skill_based_job_match": ["job"],
    "career_transition_opportunity": ["job"],
}

for _capability_id, _domains in CAPABILITY_DOMAINS.items():
    if _capability_id in CAPABILITY_CATALOG:
        CAPABILITY_CATALOG[_capability_id].supported_domains = _domains


class CapabilityRegistryService:
    """Service providing capability catalog lookups and context-dependent runtime evaluation."""

    def __init__(
        self,
        *,
        reference_store: ReferenceDataStore | None = None,
        entity_service: EntityRegistryService | None = None,
        observation_store: Any | None = None,
        db_path: Any | None = None,
    ) -> None:
        self._entity_service = entity_service or EntityRegistryService(db_path=db_path)
        if reference_store is not None:
            self._reference_store = reference_store
        else:
            self._reference_store = ReferenceDataStore(self._entity_service.db_path)
        self._observation_store = observation_store

    def get_catalog(self) -> CapabilityCatalogResponse:
        """Return the global capability catalog without running analytical calculations."""
        caps = list(CAPABILITY_CATALOG.values())
        return CapabilityCatalogResponse(
            total_capabilities=len(caps),
            available_count=sum(1 for c in caps if c.global_status == "available"),
            partial_count=sum(1 for c in caps if c.global_status == "partial"),
            insufficient_data_count=sum(1 for c in caps if c.global_status == "insufficient_data"),
            blocked_count=sum(1 for c in caps if c.global_status == "blocked"),
            building_count=sum(1 for c in caps if c.global_status == "building"),
            capabilities=caps,
        )

    def get_capability(self, capability_id: str) -> CapabilityRecord | None:
        """Lookup a registered capability by its stable ID."""
        return CAPABILITY_CATALOG.get(capability_id.strip())

    def evaluate(self, request: CapabilityEvaluationRequest) -> CapabilityEvaluationResponse:
        """Deterministically evaluate capability readiness against the provided request context."""
        now = datetime.now(timezone.utc)
        target_ids = [request.capability_id] if request.capability_id else list(CAPABILITY_CATALOG.keys())

        results: list[CapabilityEvaluationResult] = []
        for cap_id in target_ids:
            cap = CAPABILITY_CATALOG.get(cap_id)
            if not cap:
                results.append(
                    CapabilityEvaluationResult(
                        capability_id=cap_id,
                        name=cap_id,
                        global_status="insufficient_data",
                        runtime_status="insufficient_data",
                        can_execute=False,
                        reason_codes=["UNKNOWN_CAPABILITY_ID"],
                        explanation=f"Capability '{cap_id}' is not registered in the platform catalog.",
                        missing_requirements=[f"Valid capability_id matching one of: {sorted(CAPABILITY_CATALOG.keys())}"],
                    )
                )
                continue

            result = self._evaluate_single_capability(cap, request)
            results.append(result)

        return CapabilityEvaluationResponse(
            evaluated_at=now,
            request_summary={
                "portal_type": request.portal_type,
                "entity_name": request.entity_name,
                "entity_type": request.entity_type,
                "target_role": request.target_role,
                "time_range": request.time_range,
                "observations_provided": len(request.observations),
            },
            results=results,
        )

    def _evaluate_single_capability(
        self,
        cap: CapabilityRecord,
        req: CapabilityEvaluationRequest,
    ) -> CapabilityEvaluationResult:
        """Evaluate a single registered capability against the request context."""
        # 1. Planned / Building capabilities are universally unavailable for execution
        if cap.global_status == "building":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status="building",
                runtime_status="building",
                can_execute=False,
                reason_codes=["FEATURE_NOT_IMPLEMENTED", cap.reason_code],
                explanation=f"{cap.name} is in design and scheduled for a future milestone.",
                missing_requirements=[f"Platform implementation for intent '{cap.supported_intent}'"],
                limitations=cap.limitations,
                provenance_requirements=cap.provenance_requirements,
            )

        # 2. Input contract validation and pending status for Phase 1 registered features
        if cap.capability_id == "technology_impact_explorer":
            return self._eval_technology_impact_explorer(cap, req)
        elif cap.capability_id == "career_transition_opportunity":
            return self._eval_career_transition_opportunity(cap, req)
        elif cap.capability_id in {
            "skill_future_relevance_score",
            "skill_change_alert",
            "adaptive_skill_roadmap",
            "technology_adoption_shift_detector",
            "skill_based_job_match",
        }:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status=cap.global_status,
                implementation_status="pending",
                can_execute=False,
                reason_codes=["CAPABILITY_PENDING_IMPLEMENTATION"],
                explanation=f"{cap.name} is registered. Analytical engine is pending implementation in Phase 2.",
                missing_requirements=[f"Phase 2 analytical engine for {cap.capability_id}"],
                limitations=cap.limitations,
                provenance_requirements=cap.provenance_requirements,
            )

        # 3. Dispatch to legacy capability evaluator
        if cap.capability_id == "entity_resolution":
            return self._eval_entity_resolution(cap, req)
        elif cap.capability_id == "skill_technology_reference":
            return self._eval_skill_technology_reference(cap, req)
        elif cap.capability_id == "occupation_lookup":
            return self._eval_occupation_lookup(cap, req)
        elif cap.capability_id == "occupation_software_skills":
            return self._eval_occupation_software_skills(cap, req)
        elif cap.capability_id == "related_occupations":
            return self._eval_related_occupations(cap, req)
        elif cap.capability_id == "trend_velocity_analysis":
            return self._eval_trend_velocity(cap, req)
        elif cap.capability_id == "skill_health_analysis":
            return self._eval_skill_health(cap, req)
        elif cap.capability_id == "skill_half_life_analysis":
            return self._eval_skill_half_life(cap, req)
        elif cap.capability_id == "skill_forecasting_half_life":
            return self._eval_forecasting(cap, req)
        elif cap.capability_id == "ai_task_exposure":
            return self._eval_ai_task_exposure(cap, req)
        elif cap.capability_id in {"market_snapshot", "historical_signal_retrieval"}:
            return self._eval_market_observations(cap, req)
        elif cap.capability_id == "evidence_provenance_retrieval":
            return self._eval_evidence(cap, req)
        elif cap.capability_id == "skill_gap_role_fit":
            return self._eval_skill_gap(cap, req)
        elif cap.capability_id == "action_recommendations":
            return self._eval_action_recommendations(cap, req)
        elif cap.capability_id == "job_posting_search":
            return self._eval_job_search(cap, req)
        elif cap.capability_id == "company_intelligence":
            return self._eval_company_intelligence(cap, req)

        # Default fallback
        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status=cap.global_status,
            can_execute=cap.global_status == "available",
            reason_codes=[cap.reason_code],
            explanation=cap.description,
            limitations=cap.limitations,
        )

    # -------------------------------------------------------------------------
    # INDIVIDUAL RUNTIME EVALUATION HANDLERS
    # -------------------------------------------------------------------------

    def _eval_technology_impact_explorer(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        """Validate input contract for Technology Impact Explorer (accepts technology OR skill; optional occupation)."""
        # Validate entity_type if provided
        if req.entity_type is not None:
            if not isinstance(req.entity_type, str):
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    implementation_status="pending",
                    can_execute=False,
                    reason_codes=["INVALID_INPUT_TYPE"],
                    explanation="entity_type must be a string matching 'technology', 'skill', or 'occupation'.",
                    missing_requirements=["valid_entity_type"],
                    limitations=cap.limitations,
                    provenance_requirements=cap.provenance_requirements,
                )
            if req.entity_type not in cap.supported_entity_types:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    implementation_status="pending",
                    can_execute=False,
                    reason_codes=["UNSUPPORTED_ENTITY_TYPE"],
                    explanation=f"Entity type '{req.entity_type}' is not supported for {cap.name}. Supported entity types: {cap.supported_entity_types}.",
                    missing_requirements=[f"entity_type in {cap.supported_entity_types}"],
                    limitations=cap.limitations,
                    provenance_requirements=cap.provenance_requirements,
                )

        # Primary input: technology OR skill
        has_tech = bool(
            (isinstance(req.technology, str) and req.technology.strip())
            or (isinstance(req.entity_name, str) and req.entity_name.strip() and req.entity_type in {"technology", None})
        )
        has_skill = bool(
            (isinstance(req.selected_skills, list) and any(isinstance(s, str) and s.strip() for s in req.selected_skills))
            or (isinstance(req.entity_name, str) and req.entity_name.strip() and req.entity_type in {"skill", None})
        )

        if not has_tech and not has_skill:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                implementation_status="pending",
                can_execute=False,
                reason_codes=["MISSING_TECHNOLOGY_OR_SKILL_INPUT"],
                explanation="Technology Impact Explorer requires a technology or a skill as primary input.",
                missing_requirements=["technology_or_skill"],
                limitations=cap.limitations,
                provenance_requirements=cap.provenance_requirements,
            )

        # Optional occupation input
        has_occ = bool(
            (isinstance(req.occupation, str) and req.occupation.strip())
            or (isinstance(req.target_role, str) and req.target_role.strip())
            or (isinstance(req.entity_name, str) and req.entity_name.strip() and req.entity_type == "occupation")
        )

        provenance = []
        if has_tech:
            tech_val = req.technology.strip() if req.technology else req.entity_name.strip()
            provenance.append(f"primary_input:technology:{tech_val}")
        elif has_skill:
            skill_val = req.selected_skills[0].strip() if req.selected_skills else req.entity_name.strip()
            provenance.append(f"primary_input:skill:{skill_val}")
        if has_occ:
            occ_val = (req.occupation or req.target_role or req.entity_name).strip()
            provenance.append(f"optional_input:occupation:{occ_val}")

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            implementation_status="pending",
            can_execute=False,
            reason_codes=["CAPABILITY_PENDING_IMPLEMENTATION"],
            explanation=f"{cap.name} is registered. Analytical engine is pending implementation in Phase 2.",
            missing_requirements=[f"Phase 2 analytical engine for {cap.capability_id}"],
            limitations=cap.limitations,
            provenance_references=provenance,
            provenance_requirements=cap.provenance_requirements,
        )

    def _eval_career_transition_opportunity(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        """Validate input contract for Career Transition Opportunity (accepts current_role OR target_role; optional skills)."""
        # Validate entity_type if provided
        if req.entity_type is not None:
            if not isinstance(req.entity_type, str):
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    implementation_status="pending",
                    can_execute=False,
                    reason_codes=["INVALID_INPUT_TYPE"],
                    explanation="entity_type must be a string matching 'occupation' or 'skill'.",
                    missing_requirements=["valid_entity_type"],
                    limitations=cap.limitations,
                    provenance_requirements=cap.provenance_requirements,
                )
            if req.entity_type not in cap.supported_entity_types:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    implementation_status="pending",
                    can_execute=False,
                    reason_codes=["UNSUPPORTED_ENTITY_TYPE"],
                    explanation=f"Entity type '{req.entity_type}' is not supported for {cap.name}. Supported entity types: {cap.supported_entity_types}.",
                    missing_requirements=[f"entity_type in {cap.supported_entity_types}"],
                    limitations=cap.limitations,
                    provenance_requirements=cap.provenance_requirements,
                )

        # Role input: current_role OR target_role
        has_current_role = bool(
            (isinstance(req.current_role, str) and req.current_role.strip())
            or (isinstance(req.entity_name, str) and req.entity_name.strip() and req.entity_type in {"occupation", None} and not req.target_role)
        )
        has_target_role = bool(
            (isinstance(req.target_role, str) and req.target_role.strip())
            or (isinstance(req.entity_name, str) and req.entity_name.strip() and req.entity_type in {"occupation", None} and not req.current_role)
        )

        if not has_current_role and not has_target_role:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                implementation_status="pending",
                can_execute=False,
                reason_codes=["MISSING_ROLE_INPUT"],
                explanation="Career Transition Opportunity requires either a current role or a target role.",
                missing_requirements=["current_role_or_target_role"],
                limitations=cap.limitations,
                provenance_requirements=cap.provenance_requirements,
            )

        has_skills = bool(
            isinstance(req.selected_skills, list) and any(isinstance(s, str) and s.strip() for s in req.selected_skills)
        )
        provenance = []
        if has_current_role:
            c_val = req.current_role.strip() if req.current_role else req.entity_name.strip()
            provenance.append(f"role_input:current_role:{c_val}")
        if has_target_role:
            t_val = req.target_role.strip() if req.target_role else req.entity_name.strip()
            provenance.append(f"role_input:target_role:{t_val}")
        if has_skills:
            provenance.append(f"optional_input:current_skills:{req.selected_skills}")

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            implementation_status="pending",
            can_execute=False,
            reason_codes=["CAPABILITY_PENDING_IMPLEMENTATION"],
            explanation=f"{cap.name} is registered. Analytical engine is pending implementation in Phase 2.",
            missing_requirements=[f"Phase 2 analytical engine for {cap.capability_id}"],
            limitations=cap.limitations,
            provenance_references=provenance,
            provenance_requirements=cap.provenance_requirements,
        )

    def _eval_entity_resolution(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        raw_name = req.entity_name.strip() if req.entity_name else ""
        if not raw_name:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Entity resolution requires a non-empty entity_name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        resolution = self._entity_service.resolve(
            EntityResolutionRequest(
                name=raw_name,
                context=req.context_override.get("context"),
                entity_type=req.entity_type,  # type: ignore[arg-type]
            )
        )

        if resolution.status == "resolved" and resolution.entity:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["ENTITY_RESOLVED"],
                explanation=f"Resolved '{raw_name}' to canonical {resolution.entity.entity_type} '{resolution.entity.canonical_name}' (ID: {resolution.entity.entity_id}).",
                limitations=cap.limitations,
                provenance_references=[f"entity_id:{resolution.entity.entity_id}"],
            )
        elif resolution.status == "ambiguous":
            candidate_names = [c.entity.canonical_name for c in resolution.candidates]
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="partial",
                can_execute=True,
                reason_codes=["AMBIGUOUS_ENTITY_CANDIDATES_AVAILABLE"],
                explanation=f"'{raw_name}' is ambiguous across multiple entities ({', '.join(candidate_names)}). Candidate list is available.",
                limitations=cap.limitations + ["Disambiguation context is required for canonical single-entity routing."],
                provenance_references=[f"candidate:{c.entity.entity_id}" for c in resolution.candidates],
            )
        else:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["ENTITY_NOT_FOUND"],
                explanation=f"No canonical entity matched '{raw_name}'. No fabricated entities are generated.",
                missing_requirements=["Known canonical name or recognized alias in taxonomy"],
                limitations=cap.limitations,
            )

    def _eval_skill_technology_reference(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        raw_name = req.entity_name.strip() if req.entity_name else ""
        if not raw_name:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Skill reference lookup requires a canonical skill or technology name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        if str(req.context_override.get("taxonomy") or "").casefold() == "esco":
            occupation_uri = str(req.context_override.get("occupation_uri") or "").strip()
            if occupation_uri:
                occupation = self._reference_store.get_esco_occupations(
                    concept_uri=occupation_uri, limit=1
                )
                relations = self._reference_store.get_esco_occupation_skills(
                    occupation_uri, limit=1
                ) if occupation else []
                if occupation and relations:
                    return CapabilityEvaluationResult(
                        capability_id=cap.capability_id,
                        name=cap.name,
                        global_status=cap.global_status,
                        runtime_status="available",
                        can_execute=True,
                        reason_codes=["ESCO_OCCUPATION_SKILL_RELATIONS_AVAILABLE"],
                        explanation="ESCO occupation metadata and linked skill relations are available.",
                        limitations=["ESCO taxonomy associations are not evidence of individual qualifications or live hiring demand."],
                        provenance_references=[f"esco_occupation_uri:{occupation_uri}"],
                    )
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    can_execute=False,
                    reason_codes=["ESCO_OCCUPATION_RELATIONS_NOT_FOUND"],
                    explanation="No imported ESCO occupation-skill relations matched the requested occupation.",
                    missing_requirements=["Imported ESCO occupation-skill relation"],
                    limitations=["ESCO taxonomy lookup cannot establish current hiring demand."],
                )
            skill_uri = str(req.context_override.get("skill_uri") or "").strip()
            skill = self._entity_service._resolve_esco_skill(skill_uri) if skill_uri else None
            if skill:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="available",
                    can_execute=True,
                    reason_codes=["ESCO_SKILL_REFERENCE_AVAILABLE"],
                    explanation="An ESCO skill taxonomy entry is available.",
                    limitations=["ESCO is a static reference taxonomy, not evidence of current hiring demand or individual qualifications."],
                    provenance_references=[f"esco_skill_uri:{skill_uri}"],
                )
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["ESCO_SKILL_NOT_FOUND"],
                explanation="No imported ESCO skill entry matched the requested taxonomy identity.",
                missing_requirements=["Imported ESCO skill record"],
                limitations=["ESCO taxonomy lookup cannot establish current hiring demand."],
            )

        norm = normalize_skill(raw_name)
        cid = canonical_skill_id(norm)
        if norm in SKILLS or cid is not None:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["REFERENCE_DATA_AVAILABLE"],
                explanation=f"Canonical reference record found for '{norm}'.",
                limitations=cap.limitations,
                provenance_references=[f"canonical_id:{cid or norm}"],
            )

        # Check O*NET software tool lookup
        sw_entity = self._entity_service._resolve_onet_software_tool(raw_name)
        if sw_entity:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["ONET_SOFTWARE_REFERENCE_AVAILABLE"],
                explanation=f"O*NET workplace software reference found for '{raw_name}' ({sw_entity.entity_id}).",
                limitations=cap.limitations,
                provenance_references=[f"entity_id:{sw_entity.entity_id}"],
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=["ENTITY_NOT_IN_TAXONOMY"],
            explanation=f"'{raw_name}' is not registered in internal canonical skills or O*NET software reference tables.",
            missing_requirements=["Registration in internal registry or O*NET reference data"],
            limitations=cap.limitations,
        )

    def _eval_occupation_lookup(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or req.target_role or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Occupation lookup requires a SOC code or occupation title.",
                missing_requirements=["entity_name_or_target_role"],
                limitations=cap.limitations,
            )

        occ = self._entity_service._resolve_onet_occupation(target)
        if occ:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["OCCUPATION_FOUND"],
                explanation=f"Found O*NET occupation '{occ.canonical_name}' (ID: {occ.entity_id}).",
                limitations=cap.limitations,
                provenance_references=[f"entity_id:{occ.entity_id}"],
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=["OCCUPATION_NOT_FOUND"],
            explanation=f"No O*NET occupation matched '{target}'.",
            missing_requirements=["Valid O*NET SOC code or recognized occupation title"],
            limitations=cap.limitations,
        )

    def _eval_occupation_software_skills(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or req.target_role or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Occupation software skills crosswalk requires a SOC code or occupation title.",
                missing_requirements=["soc_code_or_target_role"],
                limitations=cap.limitations,
            )

        if str(req.context_override.get("taxonomy") or "").casefold() == "esco":
            uri = str(req.context_override.get("occupation_uri") or "").strip()
            relations = self._entity_service.get_esco_occupation_skills(uri, limit=1) if uri else []
            if relations:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id, name=cap.name,
                    global_status=cap.global_status, runtime_status="available", can_execute=True,
                    reason_codes=["ESCO_TAXONOMY_ASSOCIATIONS_AVAILABLE"],
                    explanation="ESCO occupation-skill taxonomy associations are available.",
                    limitations=["ESCO essential/optional associations are taxonomy mappings, not individual qualifications or hiring demand."],
                    provenance_references=[f"esco_occupation_uri:{uri}"],
                )
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id, name=cap.name,
                global_status=cap.global_status, runtime_status="insufficient_data", can_execute=False,
                reason_codes=["NO_ESCO_OCCUPATION_SKILL_ASSOCIATIONS"],
                explanation=f"No ESCO occupation-skill associations were found for '{target}'.",
                missing_requirements=["ESCO occupation URI with imported relationship records"],
                limitations=["ESCO is a static reference taxonomy; missing associations do not imply missing real-world skills."],
            )

        soc_code = target
        if not (len(target) == 10 and target[2] == "-" and target[7] == "."):
            occ = self._entity_service._resolve_onet_occupation(target)
            if occ and occ.metadata.get("soc_code"):
                soc_code = occ.metadata["soc_code"]

        skills = self._entity_service.get_occupation_skills(soc_code)
        if skills:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["CROSSWALK_AVAILABLE"],
                explanation=f"Found {len(skills)} software tools/technologies mapped to SOC {soc_code}.",
                limitations=cap.limitations,
                provenance_references=[f"onet_soc:{soc_code}"],
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=["NO_SOFTWARE_SKILLS_FOR_SOC"],
            explanation=f"No software skills found for occupation '{target}'.",
            missing_requirements=["Valid O*NET occupation with mapped software tools"],
            limitations=cap.limitations,
        )

    def _eval_related_occupations(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or req.target_role or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Related occupations crosswalk requires a SOC code or occupation title.",
                missing_requirements=["soc_code_or_target_role"],
                limitations=cap.limitations,
            )

        soc_code = target
        if not (len(target) == 10 and target[2] == "-" and target[7] == "."):
            occ = self._entity_service._resolve_onet_occupation(target)
            if occ and occ.metadata.get("soc_code"):
                soc_code = occ.metadata["soc_code"]

        related = self._entity_service.get_related_occupations(soc_code)
        if related:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["RELATED_OCCUPATIONS_AVAILABLE"],
                explanation=f"Found {len(related)} related career pathways for SOC {soc_code}.",
                limitations=cap.limitations,
                provenance_references=[f"onet_soc:{soc_code}"],
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=["NO_RELATED_OCCUPATIONS"],
            explanation=f"No related occupations found for '{target}'.",
            missing_requirements=["Valid O*NET occupation with crosswalk links"],
            limitations=cap.limitations,
        )

    def _eval_trend_velocity(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        # Check observations provided in request
        obs = req.observations
        if not obs and self._observation_store is not None and req.entity_name:
            try:
                norm = normalize_skill(req.entity_name)
                obs = self._observation_store.get_observations_by_skills([norm])
            except Exception:
                obs = []

        if not obs:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_OBSERVATIONS_FOR_SERIES"],
                explanation="Trend and velocity calculation requires empirical market observations. Zero observations found.",
                missing_requirements=[">=4 consecutive monthly observation periods"],
                limitations=cap.limitations,
            )

        from app.analytics.shared_intelligence import analyze_market_observations

        analysis = analyze_market_observations(obs)
        trend_results = analysis.trend_results
        if not trend_results:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["SERIES_EVALUATION_EMPTY"],
                explanation=(
                    f"{len(obs)} matched observation record(s) did not produce a valid "
                    "comparable monthly series for trend calculation."
                ),
                missing_requirements=["Consistent provider panel with valid periods"],
                limitations=cap.limitations,
            )

        eligible_trends = [
            trend for trend in trend_results
            if trend.data_state in {"ready", "fresh"}
            and trend.data_origin == "real"
            and trend.history_type == "platform_collected"
            and trend.canonical_skill_id
        ]
        if eligible_trends:
            priority = {"demand": 0, "adoption": 1, "interest": 2}
            selected = min(
                eligible_trends,
                key=lambda trend: priority.get(trend.signal_type, 3),
            )
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["READY_FOR_TREND"],
                explanation=(
                    f"A comparable source-specific series has {len(selected.periods_used)} "
                    "completed consecutive periods and passes the trend calculation gates."
                ),
                limitations=cap.limitations,
                provenance_references=[
                    f"provider:{selected.provider}",
                    f"signal:{selected.signal_type}",
                ],
                readiness_state=selected.readiness_state,
            )

        def completed_periods(trend: Any) -> list[str]:
            from app.analytics.observation_period import is_completed_month

            return [
                period for period in trend.periods_used
                if is_completed_month(period)
            ]

        best_trend = max(
            trend_results,
            key=lambda trend: (
                len(completed_periods(trend)),
                trend.data_origin == "real",
                trend.history_type == "platform_collected",
            ),
        )
        matching_quality_report = next(
            (
                report for report in analysis.quality_reports
                if report.provider.casefold() == best_trend.provider.casefold()
                and report.signal_type == best_trend.signal_type
                and report.canonical_skill_id == best_trend.canonical_skill_id
            ),
            None,
        )
        valid_periods = completed_periods(best_trend)
        quality_validation_failed = any(
            reason.startswith("G1.8 quality state is 'incomplete'")
            or reason.startswith("G1.8 quality state is 'configuration_changed'")
            or reason.startswith("G1.8 quality state is 'low_coverage'")
            or reason == "Series contains observations with invalid quality states"
            or reason.startswith("Canonical skill, stable series identity")
            for reason in best_trend.blocking_reasons
        )
        if matching_quality_report and any(
            "duplicate observation IDs" in issue.lower()
            for issue in matching_quality_report.issues
        ):
            quality_validation_failed = True
        blocking_reasons = list(best_trend.blocking_reasons)
        if matching_quality_report:
            blocking_reasons.extend(
                issue for issue in matching_quality_report.issues
                if issue not in blocking_reasons
            )
        if best_trend.data_origin != "real" and not any(
            "provenance" in reason.lower() for reason in blocking_reasons
        ):
            blocking_reasons.insert(0, "Observation provenance is missing or non-production.")
        if best_trend.history_type != "platform_collected" and not any(
            "history type" in reason.lower() for reason in blocking_reasons
        ):
            blocking_reasons.insert(0, "History type is not eligible for operational trend analysis.")
        if quality_validation_failed and not any(
            "missing period gap" in reason.lower()
            for reason in blocking_reasons
        ):
            valid_periods = []
        if best_trend.data_origin != "real" or best_trend.history_type != "platform_collected":
            valid_periods = []
        retrieved_periods = sorted({
            observation.period or observation.observed_at.strftime("%Y-%m")
            for observation in obs
            if observation.period or observation.observed_at
        })
        from app.analytics.observation_period import is_completed_month

        incomplete_periods = [
            period for period in retrieved_periods
            if not is_completed_month(period)
        ]
        blocking_reasons = blocking_reasons or [
            "The source-specific series did not pass all quality and trend readiness checks."
        ]
        valid_range = (
            f" ({valid_periods[0]} through {valid_periods[-1]})"
            if valid_periods else ""
        )
        retrieved_summary = (
            f" {len(retrieved_periods)} distinct matched periods "
            f"({retrieved_periods[0]} through {retrieved_periods[-1]}) were retrieved across "
            f"{len(trend_results)} source-specific series; those series are not pooled."
            if retrieved_periods else ""
        )
        incomplete_summary = (
            f" Incomplete current or future period(s) {', '.join(incomplete_periods)} were excluded."
            if incomplete_periods else ""
        )
        has_period_gap = any(
            "missing period gap" in reason.casefold()
            or "period is missing" in reason.casefold()
            for reason in blocking_reasons
        )
        reason_code = "INSUFFICIENT_TREND_HISTORY"
        if best_trend.data_origin != "real":
            reason_code = "OBSERVATION_PROVENANCE_UNAVAILABLE"
        elif best_trend.history_type != "platform_collected":
            reason_code = "INELIGIBLE_HISTORY_TYPE"
        elif quality_validation_failed:
            reason_code = "BLOCKED_BY_QUALITY_GATE"
        elif not best_trend.series_id:
            reason_code = "SERIES_IDENTITY_UNAVAILABLE"
        elif not best_trend.unit:
            reason_code = "OBSERVATION_UNIT_UNAVAILABLE"
        elif not best_trend.canonical_skill_id:
            reason_code = "CANONICAL_SKILL_ID_UNAVAILABLE"
        elif len(valid_periods) < 4:
            reason_code = "INSUFFICIENT_TREND_HISTORY"

        if best_trend.data_origin != "real":
            primary_block = "the observations do not have verified real-data provenance"
        elif best_trend.history_type != "platform_collected":
            primary_block = (
                "this history type is not eligible for operational trend analysis, "
                f"so this series has {len(valid_periods)} eligible completed monthly periods"
            )
        elif has_period_gap:
            primary_block = "a required completed month is missing from the selected series"
        elif quality_validation_failed:
            primary_block = "the selected series failed its data-quality checks"
        elif not best_trend.series_id:
            primary_block = "the selected observations do not have a stable series identity"
        elif not best_trend.unit:
            primary_block = "the selected observations do not declare a comparable unit"
        elif not best_trend.canonical_skill_id:
            primary_block = "the selected observations do not have a canonical skill identity"
        elif len(valid_periods) < 4:
            primary_block = f"only {len(valid_periods)} eligible completed monthly periods are available"
        else:
            primary_block = "the selected series does not pass the trend readiness checks"

        detail_reasons = []
        for reason in blocking_reasons:
            normalized = reason.casefold()
            if "history type" in normalized or "provenance" in normalized:
                continue
            if "stable series identity" in normalized or "series identity" in normalized:
                if not best_trend.series_id:
                    continue
                detail_reasons.append("stable series identity is unavailable")
            elif "explicit observation unit" in normalized or "unit" in normalized:
                if not best_trend.unit:
                    continue
                detail_reasons.append("a comparable observation unit is unavailable")
            elif "canonical skill" in normalized:
                if not best_trend.canonical_skill_id:
                    continue
                detail_reasons.append("canonical skill mapping is unavailable")
            elif "duplicate observation" in normalized:
                detail_reasons.append("duplicate observations were found")
            elif "missing period" in normalized or "period gap" in normalized:
                if not has_period_gap:
                    detail_reasons.append("a required completed month is missing")
            elif "quality" in normalized or "coverage" in normalized:
                detail_reasons.append("series quality requirements were not met")
            elif "period" in normalized or "gap" in normalized or "consecutive" in normalized:
                detail_reasons.append("the completed periods are not consecutive")
            if len(detail_reasons) >= 2:
                break
        detail_reasons = list(dict.fromkeys(detail_reasons))
        provider_signal = f"{best_trend.provider} {best_trend.signal_type} series"
        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=[reason_code],
            explanation=(
                f"No trend is available from the selected {provider_signal}: {primary_block}. "
                "At least 4 consecutive comparable completed monthly periods are required. "
                f"{(' '.join(detail_reasons) + '. ') if detail_reasons else ''}"
                f"{retrieved_summary}{incomplete_summary}"
            ),
            missing_requirements=blocking_reasons,
            limitations=cap.limitations,
            readiness_state=best_trend.readiness_state or "not_ready",
        )

    def _eval_skill_health(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        obs = req.observations
        if not obs and self._observation_store is not None and req.entity_name:
            try:
                norm = normalize_skill(req.entity_name)
                obs = self._observation_store.get_observations_by_skills([norm])
            except Exception:
                obs = []

        if not obs:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_OBSERVATIONS_FOR_SERIES"],
                explanation="Skill Health calculation requires empirical market observations. Zero observations found.",
                missing_requirements=[">=4 consecutive monthly observation periods with valid denominators"],
                limitations=cap.limitations,
            )

        has_real = any(getattr(o, "data_origin", None) == "real" for o in obs)
        if not has_real:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["OBSERVATION_PROVENANCE_UNAVAILABLE"],
                explanation="Empirical observation provenance is unavailable or contains demo/synthetic records.",
                missing_requirements=["Real empirical observation records with verifiable provenance"],
                limitations=cap.limitations,
            )

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.skill_health import evaluate_skill_health

        signals = aggregate_market_signals(obs)
        if not signals:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["SERIES_EVALUATION_EMPTY"],
                explanation="Observations could not be partitioned into comparable monthly series.",
                missing_requirements=["Consistent provider panel with valid periods"],
                limitations=cap.limitations,
            )

        norm_name = req.entity_name or ""
        canon_id = canonical_skill_id(norm_name) if norm_name else None
        health_result = evaluate_skill_health(
            signals,
            canonical_skill_id=canon_id,
            canonical_name=norm_name,
        )

        if health_result.score_status == "ambiguous_series":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["AMBIGUOUS_HEALTH_SERIES"],
                explanation=health_result.explanation,
                limitations=health_result.limitations,
                provenance_references=["provider_series:multiple"],
            )

        if health_result.status in {"ready", "partial"}:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["READY_FOR_HEALTH"],
                explanation=health_result.explanation,
                limitations=health_result.limitations,
                provenance_references=[f"provider:{row.provider}" for row in health_result.component_table if row.is_eligible_share],
            )

        # Insufficient data / unavailable
        reasons = [row.reason for row in health_result.component_table if row.reason]
        if any("Raw count series without source-specific denominator" in r for r in reasons) and not any(row.is_eligible_share for row in health_result.component_table):
            reason_code = "MISSING_SERIES_DENOMINATOR"
            explanation = "Skill Health relative-momentum evaluation requires normalized shares with explicit denominators; only raw counts were found."
            missing = ["Source-specific denominator to calculate normalized share series"]
        elif any("Non-consecutive" in r for r in reasons):
            reason_code = "INSUFFICIENT_HEALTH_HISTORY"
            explanation = "Observations have non-consecutive periods. At least 4 strictly consecutive monthly periods are required."
            missing = [">=4 strictly consecutive monthly periods"]
        else:
            reason_code = "INSUFFICIENT_HEALTH_HISTORY"
            explanation = health_result.explanation or "Insufficient consecutive monthly observations to evaluate Skill Health."
            missing = [">=4 consecutive monthly observation periods with valid denominators"]

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=[reason_code],
            explanation=explanation,
            missing_requirements=missing,
            limitations=health_result.limitations or cap.limitations,
        )

    def _eval_skill_half_life(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Skill Half-Life evaluation requires a skill or technology name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        obs = req.observations
        if not obs and self._observation_store is not None and req.entity_name:
            try:
                norm = normalize_skill(req.entity_name)
                obs = self._observation_store.get_observations_by_skills([norm])
            except Exception:
                obs = []

        if not obs:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_OBSERVATIONS_FOR_SERIES"],
                explanation=f"Skill Half-Life calculation requires empirical market observations for '{target}'. Zero observations found.",
                missing_requirements=[">=36 consecutive monthly observation periods with valid denominators"],
                limitations=cap.limitations,
            )

        has_real = any(getattr(o, "data_origin", None) == "real" for o in obs)
        if not has_real:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["OBSERVATION_PROVENANCE_UNAVAILABLE"],
                explanation="Empirical observation provenance is unavailable or contains demo/synthetic records.",
                missing_requirements=["Real empirical observation records with verifiable provenance"],
                limitations=cap.limitations,
            )

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.skill_half_life import calculate_skill_half_life

        signals = aggregate_market_signals(obs)
        if not signals:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["SERIES_EVALUATION_EMPTY"],
                explanation="Observations could not be partitioned into comparable monthly series.",
                missing_requirements=["Consistent provider panel with valid periods"],
                limitations=cap.limitations,
            )

        norm_name = req.entity_name or ""
        canon_id = canonical_skill_id(norm_name) if norm_name else None
        hl_result = calculate_skill_half_life(
            signals,
            canonical_skill_id=canon_id,
            canonical_name=norm_name,
        )

        if hl_result.status in {"ready", "not_applicable"}:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["READY_FOR_HALF_LIFE" if hl_result.status == "ready" else "HALF_LIFE_NOT_APPLICABLE"],
                explanation=hl_result.explanation,
                limitations=hl_result.limitations or cap.limitations,
                provenance_references=[f"provider:{hl_result.provider}"],
            )

        # Insufficient data / unavailable
        reason = hl_result.reason or "Insufficient consecutive monthly observations to evaluate Skill Half-Life."
        if "without a source-specific denominator" in reason or "raw count" in reason.lower():
            reason_code = "MISSING_SERIES_DENOMINATOR"
            explanation = "Skill Half-Life evaluation requires normalized shares with explicit denominators; only raw counts were found."
            missing = ["Source-specific denominator to calculate normalized share series"]
        elif "missing monthly periods" in reason.lower() or "requires >= 36" in reason.lower() or "consecutive" in reason.lower():
            reason_code = "INSUFFICIENT_HALF_LIFE_HISTORY"
            explanation = hl_result.explanation or reason
            missing = [">=36 strictly consecutive monthly periods with valid denominators"]
        else:
            reason_code = "INSUFFICIENT_HALF_LIFE_HISTORY"
            explanation = hl_result.explanation or reason
            missing = [">=36 consecutive monthly observation periods with valid denominators"]

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=[reason_code],
            explanation=explanation,
            missing_requirements=missing,
            limitations=hl_result.limitations or cap.limitations,
        )

    def _eval_forecasting(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Skill Demand Forecasting requires a skill or technology name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        obs = req.observations
        if not obs and self._observation_store is not None and req.entity_name:
            try:
                norm = normalize_skill(req.entity_name)
                obs = self._observation_store.get_observations_by_skills([norm])
            except Exception:
                obs = []

        if not obs:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_OBSERVATIONS_FOR_SERIES"],
                explanation=f"Skill Demand Forecasting requires empirical market observations for '{target}'. Zero observations found.",
                missing_requirements=[">=24 consecutive monthly observation periods with valid denominators"],
                limitations=cap.limitations,
            )

        has_real = any(getattr(o, "data_origin", None) == "real" for o in obs)
        if not has_real:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["OBSERVATION_PROVENANCE_UNAVAILABLE"],
                explanation="Empirical observation provenance is unavailable or contains demo/synthetic records.",
                missing_requirements=["Real empirical observation records with verifiable provenance"],
                limitations=cap.limitations,
            )

        from app.analytics.signal_aggregation import aggregate_market_signals
        from app.analytics.forecasting import forecast_signal_series

        signals = aggregate_market_signals(obs)
        if not signals:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["SERIES_EVALUATION_EMPTY"],
                explanation="Observations could not be partitioned into comparable monthly series.",
                missing_requirements=["Consistent provider panel with valid periods"],
                limitations=cap.limitations,
            )

        norm_name = req.entity_name or ""
        canon_id = canonical_skill_id(norm_name) if norm_name else None
        fc_result = forecast_signal_series(
            signals,
            canonical_skill_id=canon_id,
            canonical_name=norm_name,
        )

        if fc_result.status == "ready":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["READY_FOR_FORECASTING"],
                explanation=fc_result.explanation,
                limitations=fc_result.limitations or cap.limitations,
                provenance_references=[f"provider:{fc_result.provider}"],
            )

        reason = fc_result.reason or "Insufficient consecutive monthly observations to evaluate Skill Demand Forecasting."
        if "without a source-specific denominator" in reason or "raw count" in reason.lower() or "requires a value, positive denominator" in reason.lower():
            reason_code = "MISSING_SERIES_DENOMINATOR"
            explanation = "Skill Demand Forecasting evaluation requires normalized shares with explicit denominators; only raw counts were found."
            missing = ["Source-specific denominator to calculate normalized share series"]
        elif "incompatible" in reason.lower() or "partitions" in reason.lower():
            reason_code = "AMBIGUOUS_SOURCE_SERIES"
            explanation = fc_result.explanation or reason
            missing = ["Select one comparable source-specific demand series before forecasting."]
        elif "missing period gaps" in reason.lower() or "requires >= 24" in reason.lower() or "consecutive" in reason.lower():
            reason_code = "INSUFFICIENT_FORECAST_HISTORY"
            explanation = fc_result.explanation or reason
            missing = [">=24 strictly consecutive monthly periods with valid denominators"]
        else:
            reason_code = "INSUFFICIENT_FORECAST_HISTORY"
            explanation = fc_result.explanation or reason
            missing = [">=24 consecutive monthly observation periods with valid denominators"]

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="insufficient_data",
            can_execute=False,
            reason_codes=[reason_code],
            explanation=explanation,
            missing_requirements=missing,
            limitations=fc_result.limitations or cap.limitations,
        )

    def _eval_ai_task_exposure(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = (req.entity_name or "").strip()
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="AI Task Exposure evaluation requires a target occupation, role, or skill name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status="blocked",
            runtime_status="blocked",
            can_execute=False,
            reason_codes=["NO_LICENSED_EXPOSURE_DATASET"],
            explanation=(
                "AI task-exposure analysis is unavailable: no approved dataset identity, "
                "documented source methodology, and verified task mappings are configured. "
                "Request-supplied records and provenance are not trusted as a data source."
            ),
            missing_requirements=[
                "Approved task-exposure dataset and license verification",
                "Documented source methodology and version",
                "Verified task-to-occupation and task-to-skill mappings",
            ],
            limitations=cap.limitations,
        )

    def _eval_market_observations(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        obs = req.observations
        if not obs and self._observation_store is not None and req.entity_name:
            try:
                norm = normalize_skill(req.entity_name)
                obs = self._observation_store.get_observations_by_skills([norm])
            except Exception:
                obs = []

        history_context = req.context_override.get("_historical_signal_context", {})
        if cap.capability_id == "historical_signal_retrieval" and history_context.get("source") == "github_innovation_graph":
            country = history_context.get("country")
            if country and req.entity_name:
                from app.analytics.skill_registry import canonical_skill_id
                skill_id = canonical_skill_id(req.entity_name)
                try:
                    rows = self._reference_store.get_github_adoption_series_for_country(country)
                except Exception:
                    rows = []
                github_groups: dict[tuple[str, str, str], set[str]] = {}
                current = datetime.now(timezone.utc)
                current_quarter = (current.month - 1) // 3 + 1
                for row in rows:
                    period = str(row.get("period") or "")
                    try:
                        year_text, quarter_text = period.split("-Q", 1)
                        completed = (int(year_text), int(quarter_text)) < (current.year, current_quarter)
                    except (ValueError, TypeError):
                        completed = False
                    if skill_id and row.get("canonical_skill_id") == skill_id and completed and row.get("value") is not None:
                        key = (str(row.get("metric") or ""), str(row.get("label") or ""), str(row.get("unit") or ""))
                        github_groups.setdefault(key, set()).add(period)
                period_count = max((len(periods) for periods in github_groups.values()), default=0)
                required_periods = cap.min_readiness_periods
                if required_periods is not None and period_count < required_periods:
                    return CapabilityEvaluationResult(
                        capability_id=cap.capability_id, name=cap.name,
                        global_status=cap.global_status, runtime_status="insufficient_data",
                        can_execute=False, reason_codes=["INSUFFICIENT_HISTORICAL_PERIODS"],
                        explanation=(f"GitHub Innovation Graph has at most {period_count} distinct completed quarterly period(s) in any one compatible series for "
                                     f"'{req.entity_name}' in {country}; historical retrieval requires at least {required_periods}."),
                        missing_requirements=[f"At least {required_periods} distinct completed quarterly periods"],
                        limitations=cap.limitations,
                    )
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id, name=cap.name,
                    global_status=cap.global_status, runtime_status="available", can_execute=True,
                    reason_codes=["OBSERVATIONS_AVAILABLE"],
                    explanation=f"Found at least {period_count} GitHub Innovation Graph quarterly periods in one compatible series for '{req.entity_name}' in {country}.",
                    limitations=cap.limitations,
                    provenance_references=[f"reference_periods:{period_count}", f"country:{country}"],
                )

        if cap.capability_id == "historical_signal_retrieval" and obs:
            from app.analytics.historical_signals import observation_is_eligible_history, historical_series_identity
            eligible = [item for item in obs if observation_is_eligible_history(item)]
            compatible: dict[tuple[str, ...], set[str]] = {}
            for item in eligible:
                compatible.setdefault(historical_series_identity(item), set()).add(str(item.period))
            period_count = max((len(periods) for periods in compatible.values()), default=0)
            required_periods = cap.min_readiness_periods or 1
            if period_count < required_periods:
                source = history_context.get("source")
                signal = history_context.get("signal_type") or ("adoption" if source == "github_innovation_graph" else "interest or demand")
                if source in {"jsearch", "adzuna"}:
                    explanation = f"{source} contains stored job-posting snapshots, not an eligible historical {signal} series."
                    reason = "HISTORICAL_SNAPSHOT_SOURCE_INELIGIBLE"
                else:
                    explanation = (f"Found at most {period_count} eligible completed period(s) in one compatible {signal} series; "
                                   f"historical retrieval requires at least {required_periods}. Snapshots, incomplete periods, "
                                   "and incompatible series do not count toward readiness.")
                    reason = "INSUFFICIENT_HISTORICAL_PERIODS"
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id, name=cap.name,
                    global_status=cap.global_status, runtime_status="insufficient_data",
                    can_execute=False, reason_codes=[reason], explanation=explanation,
                    missing_requirements=[f"At least {required_periods} eligible completed periods in one source-specific series"],
                    limitations=cap.limitations,
                )
            # Historical readiness is based only on eligible, source-specific
            # completed series. Do not fall through to the generic period-count
            # check, which could incorrectly accept platform snapshots.
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id, name=cap.name,
                global_status=cap.global_status, runtime_status="available", can_execute=True,
                reason_codes=["OBSERVATIONS_AVAILABLE"],
                explanation=f"Found {period_count} eligible completed periods in one source-specific historical series for '{req.entity_name}'.",
                limitations=cap.limitations,
                provenance_references=[f"observations_count:{len(eligible)}"],
            )

        if not obs:
            if cap.capability_id == "historical_signal_retrieval":
                explanation = (
                    f"No persisted real historical observations are available for '{req.entity_name or 'the requested skill'}'. "
                    "Supported historical families are monthly Stack Exchange question counts, monthly Wikipedia pageviews, "
                    "and quarterly GitHub Innovation Graph developer activity by country. JSearch and Adzuna records are "
                    "job-posting snapshots and do not form historical demand series."
                )
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id, name=cap.name,
                    global_status=cap.global_status, runtime_status="insufficient_data",
                    can_execute=False, reason_codes=["NO_ELIGIBLE_HISTORICAL_SERIES"],
                    explanation=explanation,
                    missing_requirements=["Completed real source-specific periods with stable series identity and provenance"],
                    limitations=cap.limitations,
                )
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_STORED_OBSERVATIONS"],
                explanation=f"No stored market observations found for '{req.entity_name or 'unspecified entity'}'.",
                missing_requirements=["Stored market observations from platform collection"],
                limitations=cap.limitations,
            )

        if cap.capability_id == "historical_signal_retrieval":
            observed_periods = {
                observation.period
                for observation in obs
                if observation.period
            }
            required_periods = cap.min_readiness_periods
            if required_periods is not None and len(observed_periods) < required_periods:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    can_execute=False,
                    reason_codes=["INSUFFICIENT_HISTORICAL_PERIODS"],
                    explanation=(
                        f"Found {len(observed_periods)} distinct observed period(s); "
                        f"historical retrieval requires at least {required_periods}."
                    ),
                    missing_requirements=[
                        f"At least {required_periods} distinct observed periods"
                    ],
                    limitations=cap.limitations,
                    provenance_references=[f"observations_count:{len(obs)}"],
                )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            can_execute=True,
            reason_codes=["OBSERVATIONS_AVAILABLE"],
            explanation=f"Found {len(obs)} market observations ready for {cap.name.lower()}.",
            limitations=cap.limitations,
            provenance_references=[f"observations_count:{len(obs)}"],
        )

    def _eval_evidence(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        target = req.entity_name.strip() if req.entity_name else ""
        if not target:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_REQUIRED_INPUT"],
                explanation="Evidence retrieval requires an entity_name.",
                missing_requirements=["entity_name"],
                limitations=cap.limitations,
            )

        norm = normalize_skill(target)
        cid = canonical_skill_id(norm)
        has_taxonomy_identity = bool(
            req.context_override.get("taxonomy") == "esco"
            and req.context_override.get("skill_uri")
        )
        if cid is None and norm not in SKILLS and not has_taxonomy_identity:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["ENTITY_UNKNOWN"],
                explanation=f"Cannot trace evidence for unregistered entity '{target}'.",
                missing_requirements=["Canonical entity definition"],
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            can_execute=True,
            reason_codes=["EVIDENCE_TRACEABLE"],
            explanation=f"Evidence chain traceable for canonical entity '{norm}'.",
            limitations=cap.limitations,
            provenance_references=[f"canonical_id:{cid}"],
        )

    def _eval_skill_gap(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        has_role = bool(req.target_role or req.entity_name)
        has_skills = bool(req.selected_skills)

        if not has_skills and not has_role:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_ROLE_AND_SKILLS"],
                explanation="Skill gap analysis requires both user skills and a target role.",
                missing_requirements=["selected_skills", "target_role"],
                limitations=cap.limitations,
            )
        elif not has_skills or not has_role:
            missing = ["selected_skills"] if not has_skills else ["target_role"]
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id, name=cap.name,
                global_status=cap.global_status, runtime_status="partial", can_execute=False,
                reason_codes=["PARTIAL_INPUT_CONTEXT"],
                explanation=f"Missing {', '.join(missing)} for complete skill gap evaluation.",
                missing_requirements=missing, limitations=cap.limitations,
            )
        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="partial",
            can_execute=True,
            reason_codes=["HEURISTIC_GAP_ANALYSIS_READY"],
            explanation=f"Taxonomy comparison can run for target role '{req.target_role or req.entity_name}'.",
            limitations=cap.limitations,
            provenance_references=["source:onet_crosswalk"],
        )

    def _eval_action_recommendations(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        if req.portal_type != "individual":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["INDIVIDUAL_LEARNING_PROFILE_REQUIRED"],
                explanation=(
                    "This conversational recommendation path is limited to an individual's "
                    "own learning context; no employee or company profile is inferred."
                ),
                limitations=cap.limitations,
            )
        if not (req.target_role or req.entity_name):
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_TARGET_ROLE"],
                explanation=(
                    "A target role is needed to compare the individual's recorded skills "
                    "with the available occupational reference mapping."
                ),
                missing_requirements=["target_role"],
                limitations=cap.limitations,
            )
        target_role = (req.target_role or req.entity_name or "").strip()
        occupation = self._entity_service._resolve_onet_occupation(target_role)
        taxonomy = "onet"
        if not occupation or not occupation.metadata.get("soc_code"):
            occupation = self._entity_service._resolve_esco_occupation(target_role)
            taxonomy = "esco"
        if not occupation:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["NO_OCCUPATION_REFERENCE_MATCH"],
                explanation=f"No exact O*NET occupation match is available for '{target_role}', so role-linked learning actions cannot be grounded.",
                missing_requirements=["Exact supported occupation reference mapping"],
                limitations=cap.limitations,
            )
        if taxonomy == "esco":
            occupation_uri = occupation.metadata.get("esco_uri") or occupation.source_record_id
            relationships = self._reference_store.get_esco_occupation_skills(
                str(occupation_uri), limit=1
            ) if occupation_uri else []
            if not relationships:
                return CapabilityEvaluationResult(
                    capability_id=cap.capability_id,
                    name=cap.name,
                    global_status=cap.global_status,
                    runtime_status="insufficient_data",
                    can_execute=False,
                    reason_codes=["ESCO_OCCUPATION_SKILLS_UNAVAILABLE"],
                    explanation=(
                        f"ESCO resolves '{target_role}', but no local occupation-skill relationships "
                        "are available to ground a practice suggestion."
                    ),
                    missing_requirements=["Local ESCO occupation-skill relationships"],
                    limitations=cap.limitations,
                )
        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            can_execute=True,
            reason_codes=["ESCO_ACTION_SYNTHESIS_READY" if taxonomy == "esco" else "ACTION_SYNTHESIS_READY"],
            explanation=(
                f"Action recommendation engine is ready to synthesize actions for '{occupation.canonical_name}' "
                f"from {taxonomy.upper()} reference relationships."
            ),
            limitations=cap.limitations,
            provenance_references=[
                f"portal:{req.portal_type}",
                f"taxonomy:{taxonomy}",
                f"occupation:{occupation.source_record_id}",
            ],
        )

    def _eval_job_search(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        query = (req.entity_name or req.target_role or "").strip()
        if not query:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_QUERY"],
                explanation="Job postings search requires a keyword query (min 2 characters).",
                missing_requirements=["query"],
                limitations=cap.limitations,
            )
        if len(query) < 2:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="blocked",
                can_execute=False,
                reason_codes=["QUERY_TOO_SHORT"],
                explanation=f"Query '{query}' is too short (minimum 2 characters required).",
                missing_requirements=["query_min_length_2"],
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            can_execute=True,
            reason_codes=["STORED_JOBS_SEARCHABLE"],
            explanation=f"Read-only search against stored job postings ready for query '{query}'.",
            limitations=cap.limitations,
            provenance_references=["source:jsearch_stored_jobs"],
        )

    def _eval_company_intelligence(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        cid = req.context_override.get("company_id") or (req.entity_name if req.entity_type == "company" else None)
        if req.portal_type != "company":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["COMPANY_ADMIN_PORTAL_REQUIRED"],
                explanation=(
                    "Company-wide workforce analytics are restricted to an authenticated "
                    "company owner/admin request; employee access to this aggregate is not enabled."
                ),
                missing_requirements=["authenticated_company_owner_portal"],
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="partial",
            can_execute=True,
            reason_codes=["VERIFIED_COMPANY_MEMBERSHIP_AND_WORKFORCE_RECORDS_REQUIRED"],
            explanation=f"Internal workforce intelligence ready for company '{cid or 'active_org'}'.",
            limitations=cap.limitations,
            provenance_references=[
                "source:company_relationships",
                "source:employee_onboarding_profiles",
            ],
        )

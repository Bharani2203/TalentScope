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
    "entity_resolution": CapabilityRecord(
        capability_id="entity_resolution",
        name="Entity Name Resolution",
        description="Resolves raw user language or source names into canonical entities across skills, technologies, occupations, and companies.",
        supported_intent="resolve_entity",
        supported_entity_types=["skill", "technology", "occupation", "company"],
        required_inputs=["entity_name"],
        required_signals=["context"],
        required_sources=["internal_registry", "onet"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.entity_registry_service.EntityRegistryService.resolve",
        limitations=[
            "Single-token polysemous keywords require context to resolve without ambiguity.",
            "Raw names without match return not_found without guessing.",
        ],
        provenance_requirements=["canonical_id", "source_taxonomy"],
    ),
    "skill_technology_reference": CapabilityRecord(
        capability_id="skill_technology_reference",
        name="Skill and Technology Reference Lookup",
        description="Retrieves canonical taxonomy definitions, categories, and developer adoption reference context.",
        supported_intent="lookup_skill_reference",
        supported_entity_types=["skill", "technology"],
        required_inputs=["canonical_name_or_id"],
        required_signals=["adoption", "context"],
        required_sources=["internal_registry", "github_innovation_graph", "onet"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.analytics.skill_registry.get_skill",
        limitations=[
            "GitHub Innovation Graph measures open-source developer activity, not employer hiring demand.",
        ],
        provenance_requirements=["registry_version", "source_dataset"],
    ),
    "occupation_lookup": CapabilityRecord(
        capability_id="occupation_lookup",
        name="Occupation Reference Lookup",
        description="Retrieves standardized O*NET 2018 SOC occupation metadata, titles, and descriptions.",
        supported_intent="lookup_occupation",
        supported_entity_types=["occupation"],
        required_inputs=["soc_code_or_title"],
        required_signals=["context"],
        required_sources=["onet"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.storage.reference_store.ReferenceDataStore.get_occupation",
        limitations=[
            "O*NET is an occupational taxonomy baseline, not real-time labor market hiring demand.",
        ],
        provenance_requirements=["onet_soc_code", "taxonomy_version"],
    ),
    "occupation_software_skills": CapabilityRecord(
        capability_id="occupation_software_skills",
        name="Occupation-to-Software-Skill Crosswalk",
        description="Maps canonical occupations to workplace software tools and technologies with Hot Tech flags.",
        supported_intent="crosswalk_occupation_software",
        supported_entity_types=["occupation"],
        required_inputs=["soc_code"],
        required_signals=["context"],
        required_sources=["onet"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.entity_registry_service.EntityRegistryService.get_occupation_skills",
        limitations=[
            "Software tool lists represent workplace survey baselines; tool frequency varies by employer.",
        ],
        provenance_requirements=["onet_soc_code", "hot_technology_flag"],
    ),
    "related_occupations": CapabilityRecord(
        capability_id="related_occupations",
        name="Related Occupations Crosswalk",
        description="Traverses career mobility pathways and related occupations based on shared work activities.",
        supported_intent="crosswalk_related_occupations",
        supported_entity_types=["occupation"],
        required_inputs=["soc_code"],
        required_signals=["context"],
        required_sources=["onet"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.entity_registry_service.EntityRegistryService.get_related_occupations",
        limitations=[
            "Occupational relatedness does not guarantee identical compensation or hiring volume.",
        ],
        provenance_requirements=["onet_soc_code", "relatedness_type"],
    ),
    "market_snapshot": CapabilityRecord(
        capability_id="market_snapshot",
        name="Current Market Snapshot Retrieval",
        description="Extracts latest point-in-time observations, posting counts, and demand shares for entities.",
        supported_intent="retrieve_snapshot",
        supported_entity_types=["skill", "technology", "role", "company"],
        required_inputs=["entity_name"],
        required_signals=["demand", "adoption", "interest"],
        required_sources=["jsearch", "adzuna", "github", "wikipedia"],
        min_readiness_periods=1,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.core_intelligence_service.CoreIntelligenceService.get_intelligence",
        limitations=[
            "Snapshots represent samples observed through provider queries, not total universe of postings.",
        ],
        provenance_requirements=["observation_id", "fetch_run_id", "observed_at"],
    ),
    "historical_signal_retrieval": CapabilityRecord(
        capability_id="historical_signal_retrieval",
        name="Historical Signal Retrieval",
        description="Retrieves multi-period historical observation time-series without synthetic imputation.",
        supported_intent="retrieve_history",
        supported_entity_types=["skill", "technology", "role"],
        required_inputs=["entity_name", "time_range"],
        required_signals=["demand", "adoption", "interest"],
        required_sources=["jsearch", "adzuna", "github", "wikipedia", "stackexchange"],
        min_readiness_periods=2,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.core_intelligence_service.CoreIntelligenceService.get_intelligence",
        limitations=[
            "Only verified empirical periods are returned; zero interpolation across missing periods.",
        ],
        provenance_requirements=["period_identifiers", "history_type", "data_origin"],
    ),
    "trend_velocity_analysis": CapabilityRecord(
        capability_id="trend_velocity_analysis",
        name="Theil-Sen Trend and Velocity Analysis",
        description="Computes robust median slopes, monthly velocity, and direction classification across comparable periods.",
        supported_intent="analyze_trend",
        supported_entity_types=["skill", "technology"],
        required_inputs=["entity_name", "historical_observations"],
        required_signals=["demand", "adoption", "interest"],
        required_sources=["jsearch", "adzuna", "github", "wikipedia"],
        min_readiness_periods=4,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.analytics.trend.calculate_trend_and_velocity",
        limitations=[
            "Requires >=4 strictly consecutive monthly periods; blocked on panel drift or missing periods.",
        ],
        provenance_requirements=["calculation_version", "consecutive_valid_periods", "quality_report"],
    ),
    "evidence_provenance_retrieval": CapabilityRecord(
        capability_id="evidence_provenance_retrieval",
        name="Traceable Evidence and Provenance Retrieval",
        description="Retrieves verifiable citations, raw archive identifiers, fetch runs, and quality reports.",
        supported_intent="retrieve_evidence",
        supported_entity_types=["skill", "technology"],
        required_inputs=["entity_name"],
        required_signals=["demand", "adoption", "interest"],
        required_sources=["raw_archive", "fetch_run", "calculation_record"],
        min_readiness_periods=1,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.evidence_service.get_skill_evidence",
        limitations=[
            "Evidence strictly mirrors stored artifacts; zero simulated or placeholder provenance.",
        ],
        provenance_requirements=["raw_archive_id", "fetch_run_id", "calculation_version"],
    ),
    "skill_gap_role_fit": CapabilityRecord(
        capability_id="skill_gap_role_fit",
        name="Skill Gap and Role Alignment Analysis",
        description="Evaluates alignment between user/workforce skill inventory and target occupation requirements.",
        supported_intent="analyze_skill_gap",
        supported_entity_types=["skill", "role", "occupation"],
        required_inputs=["selected_skills", "target_role"],
        required_signals=["context"],
        required_sources=["onet", "onboarding_profile"],
        min_readiness_periods=None,
        global_status="partial",
        reason_code="HEURISTIC_ALIGNMENT_ONLY",
        handler="app.services.action_recommendation_service.build_action_recommendations",
        limitations=[
            "Currently provides heuristic crosswalk and action prioritization; dedicated quantitative fit scoring engine is under development.",
        ],
        provenance_requirements=["onet_soc_code", "selected_skill_list"],
    ),
    "action_recommendations": CapabilityRecord(
        capability_id="action_recommendations",
        name="Contextual Action Recommendations",
        description="Synthesizes deterministic, portal-specific next steps (learn, upskill, reskill, monitor) from verified data.",
        supported_intent="synthesize_actions",
        supported_entity_types=["skill", "role", "company"],
        required_inputs=["portal_type", "core_intelligence_response"],
        required_signals=["demand", "adoption", "interest", "context"],
        required_sources=["core_intelligence_engine"],
        min_readiness_periods=None,
        global_status="available",
        reason_code="CAPABILITY_IMPLEMENTED",
        handler="app.services.action_recommendation_service.build_action_recommendations",
        limitations=[
            "Actions are advisory guidance based on empirical signals; future career/salary outcomes not guaranteed.",
        ],
        provenance_requirements=["action_id", "priority", "target_id"],
    ),
    "job_posting_search": CapabilityRecord(
        capability_id="job_posting_search",
        name="Job Postings Search",
        description="Searches normalized, previously collected job postings matching keywords and country codes.",
        supported_intent="search_jobs",
        supported_entity_types=["skill", "role", "technology"],
        required_inputs=["query"],
        required_signals=["demand"],
        required_sources=["jsearch"],
        min_readiness_periods=1,
        global_status="partial",
        reason_code="STORED_DATA_ONLY",
        handler="app.api.routes.market.search_market_jobs",
        limitations=[
            "Read-only search against stored collection runs; does not execute live external crawler queries.",
        ],
        provenance_requirements=["job_id", "source_url", "posted_at"],
    ),
    "company_intelligence": CapabilityRecord(
        capability_id="company_intelligence",
        name="Company Workforce and Market Intelligence",
        description="Aggregates internal workforce inventory, team skills, and company-specific market demand observations.",
        supported_intent="analyze_company_workforce",
        supported_entity_types=["company"],
        required_inputs=["company_id"],
        required_signals=["demand", "context"],
        required_sources=["company_relationships", "market_observations"],
        min_readiness_periods=None,
        global_status="partial",
        reason_code="INTERNAL_WORKFORCE_ONLY",
        handler="app.services.core_intelligence_service.CoreIntelligenceService._synthesize_market_domain",
        limitations=[
            "Internal company membership and workforce skills supported; external firmographics, venture capital, and SEC filings are unavailable.",
        ],
        provenance_requirements=["company_id", "invitation_or_membership_record"],
    ),
    "skill_forecasting_half_life": CapabilityRecord(
        capability_id="skill_forecasting_half_life",
        name="Skill Half-Life and Future Demand Forecasting",
        description="Projects multi-quarter skill demand trajectories and obsolescence half-life models.",
        supported_intent="forecast_future_demand",
        supported_entity_types=["skill", "technology"],
        required_inputs=["entity_name", "consecutive_historical_series"],
        required_signals=["demand", "adoption"],
        required_sources=["future_forecasting_engine"],
        min_readiness_periods=6,
        global_status="building",
        reason_code="MILESTONE_G3_PLANNED",
        handler=None,
        limitations=[
            "Forecasting engine is explicitly inactive in G2.6; synthetic projections and future predictions are forbidden.",
        ],
        provenance_requirements=["forecast_model_version", "confidence_interval"],
    ),
    "workforce_what_if_simulation": CapabilityRecord(
        capability_id="workforce_what_if_simulation",
        name="Company Workforce What-If Simulation",
        description="Simulates enterprise reskilling scenarios, attrition shock impact, and organizational skill migration.",
        supported_intent="simulate_workforce_scenarios",
        supported_entity_types=["company", "workforce"],
        required_inputs=["company_id", "simulation_parameters"],
        required_signals=["context", "demand"],
        required_sources=["future_simulation_engine"],
        min_readiness_periods=None,
        global_status="building",
        reason_code="FUTURE_ENTERPRISE_PLANNED",
        handler=None,
        limitations=[
            "Simulation engine is not implemented; scenario projection capabilities are in design.",
        ],
        provenance_requirements=["simulation_run_id", "model_assumptions"],
    ),
}

CAPABILITY_DOMAINS: dict[str, list[str]] = {
    "entity_resolution": ["skill", "market", "job"],
    "skill_technology_reference": ["skill", "market"],
    "occupation_lookup": ["job"],
    "occupation_software_skills": ["job"],
    "related_occupations": ["job"],
    "market_snapshot": ["market"],
    "historical_signal_retrieval": ["skill", "market"],
    "trend_velocity_analysis": ["skill", "market"],
    "evidence_provenance_retrieval": ["skill", "market"],
    "skill_gap_role_fit": ["skill", "job"],
    "action_recommendations": ["skill", "market", "job"],
    "job_posting_search": ["job"],
    "company_intelligence": ["market"],
    "skill_forecasting_half_life": ["skill"],
    "workforce_what_if_simulation": ["market"],
}

for _capability_id, _domains in CAPABILITY_DOMAINS.items():
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

        # 2. Dispatch to specific capability evaluator
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

        readiness_reports = assess_analytical_readiness(obs)
        if not readiness_reports:
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

        # Evaluate against the primary report
        primary = readiness_reports[0]
        if primary.is_trend_ready:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="available",
                can_execute=True,
                reason_codes=["READY_FOR_TREND"],
                explanation=f"Series has {primary.consecutive_valid_periods} consecutive valid periods and passes all analytical gates.",
                limitations=cap.limitations,
                provenance_references=[f"provider:{primary.provider}", f"signal:{primary.signal_type}"],
                readiness_state=primary.readiness_state,
            )
        elif primary.readiness_state.startswith("blocked_"):
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="blocked",
                can_execute=False,
                reason_codes=["BLOCKED_BY_READINESS_GATE", primary.readiness_state],
                explanation=f"Series blocked by analytical gate: {primary.readiness_state}.",
                missing_requirements=primary.blocking_reasons,
                limitations=cap.limitations,
                readiness_state=primary.readiness_state,
            )
        else:
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["INSUFFICIENT_PERIODS_FOR_TREND"],
                explanation=f"Series has {primary.consecutive_valid_periods} consecutive valid periods (minimum 4 required for Theil-Sen trend).",
                missing_requirements=primary.blocking_reasons or ["Minimum 4 consecutive monthly periods"],
                limitations=cap.limitations,
                readiness_state=primary.readiness_state,
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

        if not obs:
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
        if cid is None and norm not in SKILLS:
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
        has_skills = bool(req.selected_skills)
        has_role = bool(req.target_role or req.entity_name)

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
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="partial",
                can_execute=False,
                reason_codes=["PARTIAL_INPUT_CONTEXT"],
                explanation=f"Missing {', '.join(missing)} for complete skill gap evaluation.",
                missing_requirements=missing,
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="partial",
            can_execute=True,
            reason_codes=["HEURISTIC_GAP_ANALYSIS_READY"],
            explanation=f"Heuristic alignment ready between {len(req.selected_skills)} skills and target role '{req.target_role or req.entity_name}'.",
            limitations=cap.limitations,
            provenance_references=["source:onet_crosswalk"],
        )

    def _eval_action_recommendations(
        self, cap: CapabilityRecord, req: CapabilityEvaluationRequest
    ) -> CapabilityEvaluationResult:
        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="available",
            can_execute=True,
            reason_codes=["ACTION_SYNTHESIS_READY"],
            explanation=f"Action recommendation engine is ready to synthesize actions for portal '{req.portal_type}'.",
            limitations=cap.limitations,
            provenance_references=[f"portal:{req.portal_type}"],
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
        if not cid and req.portal_type != "company":
            return CapabilityEvaluationResult(
                capability_id=cap.capability_id,
                name=cap.name,
                global_status=cap.global_status,
                runtime_status="insufficient_data",
                can_execute=False,
                reason_codes=["MISSING_COMPANY_CONTEXT"],
                explanation="Company intelligence requires a company context or company_id.",
                missing_requirements=["company_id_or_company_portal"],
                limitations=cap.limitations,
            )

        return CapabilityEvaluationResult(
            capability_id=cap.capability_id,
            name=cap.name,
            global_status=cap.global_status,
            runtime_status="partial",
            can_execute=True,
            reason_codes=["INTERNAL_WORKFORCE_READY"],
            explanation=f"Internal workforce intelligence ready for company '{cid or 'active_org'}'.",
            limitations=cap.limitations,
            provenance_references=["source:company_relationships"],
        )

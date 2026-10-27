"""Greenfield Intelligence Engine V2 capability registry and readiness rules.

Defines approved selectable capabilities and internal V2 engine capabilities
with truthful data-readiness evaluation.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_v2.contracts import SignalFamily


CapabilityDomain = Literal["skill_intelligence", "market_intelligence", "job_intelligence"]
ReadinessState = Literal["ready", "insufficient_data", "disabled", "benchmark_only"]


class CapabilityDefinition(BaseModel):
    """Specification of an intelligence capability."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    domain: CapabilityDomain
    description: str
    primary_signal_family: SignalFamily
    primary_source_id: str | None = None
    min_months_required: int = 0
    requires_company_context: bool = False
    requires_profile_context: bool = False


class CapabilityReadiness(BaseModel):
    """Readiness assessment for a specific capability invocation."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    state: ReadinessState
    is_executable: bool
    months_available: int = 0
    months_required: int = 0
    reason: str


# Compatibility IDs emitted by existing frontend and assistant callers.
# The aliases are domain-sensitive because the legacy name may have different
# meanings in Skill and Market Intelligence.
LEGACY_CAPABILITY_MAP: dict[tuple[str, str], str] = {
    ("skill", "trend_velocity_analysis"): "skill_demand_trends",
    ("skill", "historical_signal_retrieval"): "skill_historical_signals",
    ("skill", "skill_gap_role_fit"): "skill_role_alignment",
    ("skill", "evidence_provenance_retrieval"): "skill_evidence_citations",
    ("skill", "skill_technology_reference"): "skill_reference_profile",
    ("skill", "action_recommendations"): "skill_action_recommendations",
    ("market", "market_snapshot"): "market_intelligence_snapshot",
    ("market", "historical_signal_retrieval"): "market_tech_signals",
    ("market", "trend_velocity_analysis"): "market_trend_velocity",
    ("market", "evidence_provenance_retrieval"): "market_evidence_citations",
    ("job", "job_posting_search"): "job_verified_postings",
    ("job", "occupation_software_skills"): "job_role_requirements",
    ("job", "related_occupations"): "job_mobility_pathways",
    ("job", "skill_gap_role_fit"): "job_profile_alignment",
    ("job", "action_recommendations"): "job_preparation_actions",
    ("job", "role_preparation_actions"): "job_preparation_actions",
    ("skill", "role_preparation_actions"): "job_preparation_actions",
    ("skill", "occupation_software_skills"): "job_role_requirements",
    ("market", "occupation_software_skills"): "job_role_requirements",
    ("job", "job_verified_postings"): "job_verified_postings",
    ("skill", "job_verified_postings"): "job_verified_postings",
    ("market", "job_verified_postings"): "job_verified_postings",
}

APPROVED_CAPABILITY_IDS: set[str] = {
    "skill_future_relevance_score",
    "skill_change_alert",
    "adaptive_skill_roadmap",
    "technology_adoption_shift_detector",
    "technology_impact_explorer",
    "skill_based_job_match",
    "career_transition_opportunity",
}


def canonical_capability_id(capability_id: str, domain: str | None = None) -> str:
    """Resolve an approved capability or a domain-specific legacy engine ID."""
    if domain is not None:
        mapped = LEGACY_CAPABILITY_MAP.get((domain, capability_id))
        if mapped:
            return mapped
    if capability_id in APPROVED_CAPABILITY_IDS:
        return capability_id
    return capability_id


CAPABILITIES: dict[str, CapabilityDefinition] = {
    # ---------------- Skill Domain (3 features) ----------------
    "skill_future_relevance_score": CapabilityDefinition(
        capability_id="skill_future_relevance_score",
        name="Skill Future Relevance Score",
        domain="skill_intelligence",
        description="Assess a skill's potential future relevance using available historical and technology-adoption signals.",
        primary_signal_family="developer_adoption",
        primary_source_id="github_innovation_graph",
        min_months_required=1,
    ),
    "skill_change_alert": CapabilityDefinition(
        capability_id="skill_change_alert",
        name="Skill Change Alert",
        domain="skill_intelligence",
        description="Identify supported increases, decreases, or stable patterns in comparable skill signals.",
        primary_signal_family="developer_adoption",
        primary_source_id="github_innovation_graph",
        min_months_required=4,
    ),
    "adaptive_skill_roadmap": CapabilityDefinition(
        capability_id="adaptive_skill_roadmap",
        name="Adaptive Skill Roadmap",
        domain="skill_intelligence",
        description="Recommend an ordered learning plan based on current skills, a target role, and available skill relationships.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="onet",
    ),

    # ---------------- Market Domain (2 features) ----------------
    "technology_adoption_shift_detector": CapabilityDefinition(
        capability_id="technology_adoption_shift_detector",
        name="Technology Adoption Shift Detector",
        domain="market_intelligence",
        description="Compare supported technology-adoption signals over comparable periods and identify meaningful changes.",
        primary_signal_family="developer_adoption",
        primary_source_id="github_innovation_graph",
        min_months_required=2,
    ),
    "technology_impact_explorer": CapabilityDefinition(
        capability_id="technology_impact_explorer",
        name="Technology Impact Explorer",
        domain="market_intelligence",
        description="Explore supported relationships between technologies, skills, and occupations.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="onet",
    ),

    # ---------------- Job Domain (2 features) ----------------
    "skill_based_job_match": CapabilityDefinition(
        capability_id="skill_based_job_match",
        name="Skill-Based Job Match",
        domain="job_intelligence",
        description="Compare a user's skills with requirements in retrieved job postings and explain matches and skill gaps.",
        primary_signal_family="hiring_demand",
        primary_source_id="jsearch",
    ),
    "career_transition_opportunity": CapabilityDefinition(
        capability_id="career_transition_opportunity",
        name="Career Transition Opportunity",
        domain="job_intelligence",
        description="Identify possible related target roles and the skills that may be needed for a transition.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="onet",
    ),
}

EXTENDED_CAPABILITIES: dict[str, CapabilityDefinition] = {
    # Internal V2 engine capabilities used by the legacy assistant API. They
    # are executable engine paths, not additional selectable Phase 1 features.
    "skill_historical_signals": CapabilityDefinition(
        capability_id="skill_historical_signals",
        name="Historical Skill Signals",
        domain="skill_intelligence",
        description="Retrieve stored historical developer-adoption observations for a skill.",
        primary_signal_family="developer_adoption",
        primary_source_id="github_innovation_graph",
        min_months_required=1,
    ),
    "skill_demand_trends": CapabilityDefinition(
        capability_id="skill_demand_trends",
        name="Skill Demand Trends",
        domain="skill_intelligence",
        description="Analyze platform-collected hiring-demand observations for a skill.",
        primary_signal_family="hiring_demand",
        min_months_required=4,
    ),
    "job_verified_postings": CapabilityDefinition(
        capability_id="job_verified_postings",
        name="Verified Job Postings",
        domain="job_intelligence",
        description="Search and retrieve verified job postings.",
        primary_signal_family="hiring_demand",
        primary_source_id="jsearch",
    ),
    "job_role_requirements": CapabilityDefinition(
        capability_id="job_role_requirements",
        name="Job Role Requirements",
        domain="job_intelligence",
        description="Retrieve skills and requirements for a target occupation.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="onet",
    ),
    "job_preparation_actions": CapabilityDefinition(
        capability_id="job_preparation_actions",
        name="Job Preparation Actions",
        domain="job_intelligence",
        description="Structured preparation actions for a target role.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="onet",
    ),
    "skill_lookup": CapabilityDefinition(
        capability_id="skill_lookup",
        name="Skill Lookup",
        domain="skill_intelligence",
        description="Lookup skills and occupations across reference taxonomies.",
        primary_signal_family="reference_taxonomy",
        primary_source_id="esco",
    ),
    "market_trend_velocity": CapabilityDefinition(
        capability_id="market_trend_velocity",
        name="Market Trend Velocity",
        domain="market_intelligence",
        description="Analyze hiring demand velocity and momentum.",
        primary_signal_family="hiring_demand",
        min_months_required=4,
    ),
}


class V2CapabilityRegistry:
    """Evaluates capability execution readiness based on data verification rules."""

    def __init__(self) -> None:
        pass

    def get_capability(self, capability_id: str) -> CapabilityDefinition | None:
        return CAPABILITIES.get(capability_id) or EXTENDED_CAPABILITIES.get(capability_id)

    def list_capabilities(self, domain: CapabilityDomain | None = None) -> list[CapabilityDefinition]:
        if domain:
            return [c for c in CAPABILITIES.values() if c.domain == domain]
        return list(CAPABILITIES.values())

    def evaluate_readiness(
        self,
        capability_id: str,
        *,
        months_available: int = 0,
        has_profile: bool = False,
        has_reference_data: bool = True,
    ) -> CapabilityReadiness:
        """Evaluate whether a capability can execute given current data."""
        defn = self.get_capability(capability_id)
        if not defn:
            return CapabilityReadiness(
                capability_id=capability_id,
                state="disabled",
                is_executable=False,
                reason=f"Unknown capability '{capability_id}'.",
            )

        # 1. Check profile requirements
        if defn.requires_profile_context and not has_profile:
            return CapabilityReadiness(
                capability_id=capability_id,
                state="insufficient_data",
                is_executable=False,
                reason="Profile context (skills or experience) is required for alignment.",
            )

        # 2. Check reference data requirements
        if defn.primary_signal_family == "reference_taxonomy" and not has_reference_data:
            return CapabilityReadiness(
                capability_id=capability_id,
                state="insufficient_data",
                is_executable=False,
                reason="Local reference taxonomies (O*NET/ESCO) are not available.",
            )

        # 3. Check hiring demand observations threshold
        if defn.capability_id == "market_trend_velocity":
            if months_available < 4:
                return CapabilityReadiness(
                    capability_id=capability_id,
                    state="insufficient_data",
                    is_executable=False,
                    months_available=months_available,
                    months_required=4,
                    reason=(
                        f"Market trend velocity requires at least 4 consecutive months of "
                        f"verified hiring demand observations; found {months_available} months."
                    ),
                )

        if defn.capability_id in {"skill_health_analysis", "skill_demand_forecast", "hiring_demand_trends"}:
            is_ready = months_available >= defn.min_months_required
            return CapabilityReadiness(
                capability_id=capability_id,
                state="ready" if is_ready else "insufficient_data",
                is_executable=True,
                months_available=months_available,
                months_required=defn.min_months_required,
                reason=(
                    "Capability is ready for execution with verified datasets."
                    if is_ready
                    else (
                        f"{defn.name} requires at least {defn.min_months_required} consecutive months of "
                        f"verified hiring demand observations; found {months_available} months."
                    )
                ),
            )

        return CapabilityReadiness(
            capability_id=capability_id,
            state="ready",
            is_executable=True,
            months_available=months_available,
            months_required=defn.min_months_required,
            reason="Capability is ready for execution with verified datasets.",
        )

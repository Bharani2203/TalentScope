"""Greenfield Intelligence Engine V2 — Job Intelligence Engine.

Executes the 5 Job Intelligence features:
1. job_verified_postings
2. job_role_requirements
3. job_mobility_pathways
4. job_profile_alignment
5. job_preparation_actions
"""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_v2.contracts import CareerMobilityResult, V2EvidenceItem, V2StructuredFact
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.occupation_names import (
    normalize_occupation_name,
    occupation_label_matches,
)
from app.intelligence_v2.reference_intelligence import CareerMobilityEngine
from app.intelligence_v2.role_actions import RolePreparationPlan, V2RoleActionEngine
from app.intelligence_v2.skill_mapping import RoleSkillAlignment, V2SkillMapper
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


class JobIntelligenceResult(BaseModel):
    """Unified output from Job Intelligence capability execution."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    headline: str
    facts: list[V2StructuredFact] = Field(default_factory=list)
    evidence: list[V2EvidenceItem] = Field(default_factory=list)
    alignment: RoleSkillAlignment | None = None
    pathways: list[dict[str, Any]] = Field(default_factory=list)
    mobility_result: CareerMobilityResult | None = None
    action_plan: RolePreparationPlan | None = None
    postings: list[dict[str, Any]] = Field(default_factory=list)
    readiness_state: str = "ready"
    metadata: dict[str, Any] = Field(default_factory=dict)


class V2JobIntelligenceEngine:
    """Executes job postings, requirements, mobility pathways, and preparation plans."""

    def __init__(
        self,
        store: ReferenceDataStore | None = None,
        skill_mapper: V2SkillMapper | None = None,
        evidence_retriever: V2EvidenceRetriever | None = None,
        action_engine: V2RoleActionEngine | None = None,
        mobility_engine: CareerMobilityEngine | None = None,
    ) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.skill_mapper = skill_mapper or V2SkillMapper(self.store)
        self.evidence_retriever = evidence_retriever or V2EvidenceRetriever(self.store)
        self.action_engine = action_engine or V2RoleActionEngine()
        self.mobility_engine = mobility_engine or CareerMobilityEngine(self.store)

    def run_verified_postings(
        self,
        role_or_skill: str | None = None,
        geography: str = "all",
        *,
        country: str | None = None,
        location: str | None = None,
        date_posted: str | None = None,
        providers: dict[str, Any] | None = None,
        settings: Any | None = None,
        remote: bool = False,
        question: str | None = None,
    ) -> JobIntelligenceResult:
        """Inspect verified job postings inventory using configured providers."""
        import uuid
        from app.services.verified_job_search_service import search_configured_job_providers

        query_str = (role_or_skill or "Software Developer").strip()
        if role_or_skill is None and question is None:
            stored_query = "Software Developer"
        else:
            stored_query = (role_or_skill or question or "").strip()
        search_res = search_configured_job_providers(
            query=query_str,
            country=country,
            location=location,
            date_posted=date_posted,
            settings=settings,
            providers=providers,
        )

        if search_res.status in {"ready", "partial"} and search_res.postings:
            fact_postings = [
                {
                    "title": p.title,
                    "company": p.company_name,
                    "location": p.location,
                    "source": p.source,
                    "source_url": p.source_url,
                    "posting_date": p.posted_at,
                    "description": p.description,
                    "posting_id": p.provider_job_id or p.posting_id,
                }
                for p in search_res.postings
            ]
            fact = V2StructuredFact(
                fact_id=f"fact:postings:{query_str.casefold().replace(' ', '_')[:24]}:{uuid.uuid4().hex[:8]}",
                fact_type="stored_job_postings",
                entity_name=query_str,
                metric_name="postings_count",
                metric_value=len(search_res.postings),
                unit="postings",
                source=", ".join(sorted(k.title() for k in search_res.providers.keys())) or "Verified Job Providers",
                data_origin="real",
                details={
                    "postings": fact_postings,
                    "providers": search_res.providers,
                    "rejected_count": search_res.rejected_count,
                    "unapplied_filters": search_res.unapplied_filters,
                },
            )
            evidence = [
                V2EvidenceItem(
                    evidence_id=f"evi:job_postings:{prov_name}:{uuid.uuid4().hex[:8]}",
                    source=prov_name.title(),
                    signal_family="hiring_demand",
                    measured_signal_type="job_posting_records",
                    time_grain="point_in_time",
                    geography=geography,
                    data_origin="real",
                    readiness_state="observed",
                    confidence_status="high",
                    quality="valid",
                    description=f"Verified real job postings retrieved from {prov_name.title()} provider matching '{query_str}'.",
                )
                for prov_name in search_res.providers.keys()
            ]
            provider_names = ", ".join(k.title() for k in search_res.providers.keys())
            headline = f"Retrieved {len(search_res.postings)} verified job listings for '{query_str}' from {provider_names}."
            return JobIntelligenceResult(
                capability_id="job_verified_postings",
                headline=headline,
                facts=[fact],
                evidence=evidence,
                postings=fact_postings,
                readiness_state="ready" if search_res.status == "ready" else "partial",
                metadata={
                    "postings_count": len(search_res.postings),
                    "listings_available": True,
                    "geography": geography,
                    "providers": search_res.providers,
                    "rejected_count": search_res.rejected_count,
                    "unapplied_filters": search_res.unapplied_filters,
                },
            )

        if search_res.status == "empty":
            fact = V2StructuredFact(
                fact_id=f"fact:postings:{query_str.casefold().replace(' ', '_')[:24]}:{uuid.uuid4().hex[:8]}",
                fact_type="stored_job_postings",
                entity_name=query_str,
                metric_name="postings_count",
                metric_value=0,
                unit="postings",
                source=", ".join(sorted(k.title() for k in search_res.providers.keys())) or "Verified Job Providers",
                data_origin="real",
                details={
                    "postings": [],
                    "providers": search_res.providers,
                    "zero_results_verified": True,
                    "unapplied_filters": search_res.unapplied_filters,
                },
            )
            provider_names = ", ".join(k.title() for k in search_res.providers.keys())
            headline = f"No verified job postings matched '{query_str}' across configured providers ({provider_names})."
            evidence = [
                V2EvidenceItem(
                    evidence_id=f"evi:job_postings:zero:{uuid.uuid4().hex[:8]}",
                    source=provider_names or "Job Providers",
                    signal_family="hiring_demand",
                    measured_signal_type="job_posting_records",
                    time_grain="point_in_time",
                    geography=geography,
                    data_origin="real",
                    readiness_state="observed",
                    confidence_status="high",
                    quality="valid",
                    description=f"Zero matching job listings confirmed by provider for '{query_str}'.",
                )
            ]
            return JobIntelligenceResult(
                capability_id="job_verified_postings",
                headline=headline,
                facts=[fact],
                evidence=evidence,
                postings=[],
                readiness_state="ready",
                metadata={
                    "postings_count": 0,
                    "listings_available": False,
                    "geography": geography,
                    "zero_results_verified": True,
                    "providers": search_res.providers,
                },
            )

        # Handle provider error or unconfigured
        errors = search_res.error_categories
        if any("rate_limit" in str(v).lower() for v in errors.values()):
            headline = "Verified job search is temporarily unavailable: provider rate limit reached. Please try again later."
            readiness = "unavailable"
        elif any("timeout" in str(v).lower() or "network" in str(v).lower() for v in errors.values()):
            headline = "Verified job search is temporarily unavailable: provider request timed out or network error."
            readiness = "unavailable"
        elif any("authentication" in str(v).lower() or "credentials" in str(v).lower() for v in errors.values()):
            headline = "Verified job search is unavailable: provider authentication failed; check configured server credentials."
            readiness = "unavailable"
        elif any("schema" in str(v).lower() for v in errors.values()):
            headline = "Verified job search is unavailable: provider returned malformed or unexpected data."
            readiness = "unavailable"
        else:
            # Fallback to stored jobs in Firestore if available
            from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

            stored = search_stored_jsearch_jobs_with_stats(
                query=stored_query,
                country=country,
                location=location,
                remote=remote,
            )
            scanned_count = stored.scanned_count
            matched_count = stored.matched_count
            city_label = location or "all"
            search_summary = (
                f"Scanned {scanned_count}, matched {matched_count}, city {city_label}. "
                "Live search is off."
            )
            fact_postings = [
                {
                    "title": job.title,
                    "company": job.company_name,
                    "location": job.location,
                    "source": job.source,
                    "source_url": job.source_url,
                    "posting_date": job.posted_at,
                    "description": job.description,
                    "posting_id": job.job_id,
                }
                for job in stored
            ]
            fact = V2StructuredFact(
                fact_id=f"fact:stored_postings:{query_str.casefold().replace(' ', '_')[:24]}:{uuid.uuid4().hex[:8]}",
                fact_type="stored_job_postings",
                entity_name=query_str,
                metric_name="postings_count",
                metric_value=matched_count,
                unit="postings",
                source="Stored Job Repository",
                data_origin="real" if matched_count else "unavailable",
                details={
                    "postings": fact_postings,
                    "scanned_count": scanned_count,
                    "matched_count": matched_count,
                    "city": city_label,
                    "search_summary": search_summary,
                },
            )
            evidence = [V2EvidenceItem(
                evidence_id=f"evi:stored_postings:{uuid.uuid4().hex[:8]}",
                source="TalentScope Stored Job Repository",
                signal_family="hiring_demand",
                measured_signal_type="job_posting_records",
                time_grain="point_in_time",
                geography=geography,
                data_origin="real" if matched_count else "unavailable",
                readiness_state="observed" if matched_count else "insufficient_data",
                confidence_status="high" if matched_count else "low",
                quality="valid" if matched_count else "insufficient_history",
                description=search_summary,
            )]
            headline = (
                f"Retrieved {matched_count} verified stored job listings for '{query_str}'. "
                f"{search_summary}"
                if matched_count
                else f"Not enough data: no stored job listings matched '{query_str}'. {search_summary}"
            )
            return JobIntelligenceResult(
                capability_id="job_verified_postings",
                headline=headline,
                facts=[fact],
                evidence=evidence,
                postings=fact_postings,
                readiness_state="ready" if matched_count else "insufficient_data",
                metadata={
                    "postings_count": matched_count,
                    "scanned_count": scanned_count,
                    "matched_count": matched_count,
                    "city": city_label,
                    "listings_available": bool(matched_count),
                    "geography": geography,
                },
            )

        return JobIntelligenceResult(
            capability_id="job_verified_postings",
            headline=headline,
            facts=[],
            evidence=[V2EvidenceItem(
                evidence_id=f"evi:job_postings:unavailable:{uuid.uuid4().hex[:8]}",
                source="Job Posting Providers",
                signal_family="hiring_demand",
                measured_signal_type="job_posting_records",
                time_grain="point_in_time",
                geography=geography,
                data_origin="unavailable",
                readiness_state=readiness,
                confidence_status="low",
                quality="insufficient_history",
                description=headline,
            )],
            postings=[],
            readiness_state=readiness,
            metadata={"postings_count": None, "listings_available": False, "geography": geography, "errors": errors},
        )

    def run_role_requirements(
        self,
        role_name: str,
    ) -> JobIntelligenceResult:
        """Extract occupation-described skills from local O*NET/ESCO taxonomies."""
        requirements: list[dict[str, Any]] = []
        soc_code = None
        source_name: str | None = None
        requested_role = role_name
        resolved_role_name = role_name
        normalized_role = normalize_occupation_name(role_name)

        try:
            with self.store._connect() as conn:
                onet_candidates = conn.execute(
                    "SELECT soc_code, title FROM ref_onet_occupations WHERE lower(title) LIKE lower(?)",
                    (f"%{normalized_role}%",),
                ).fetchall()
                occ = next(
                    (
                        candidate for candidate in onet_candidates
                        if occupation_label_matches(normalized_role, candidate["title"])
                    ),
                    None,
                )
                if occ:
                    soc_code = occ["soc_code"]
                    resolved_role_name = occ["title"]
                    rows = conn.execute(
                        """
                        SELECT workplace_example, element_name, hot_technology, in_demand
                        FROM ref_onet_software_skills
                        WHERE soc_code = ?
                        ORDER BY hot_technology DESC, in_demand DESC
                        LIMIT 20
                        """,
                        (soc_code,),
                    ).fetchall()
                    requirements = [dict(r) for r in rows]
                    if requirements:
                        source_name = "O*NET occupation taxonomy"
                if not requirements:
                    esco_candidates = conn.execute(
                        """
                        SELECT concept_uri, preferred_label, alt_labels
                        FROM ref_esco_occupations
                        WHERE lower(preferred_label) LIKE lower(?)
                           OR lower(alt_labels) LIKE lower(?)
                        ORDER BY CASE WHEN lower(preferred_label) = lower(?) THEN 0 ELSE 1 END,
                                 length(preferred_label) ASC
                        """,
                        (
                            f"%{normalized_role}%",
                            f"%{normalized_role}%",
                            normalized_role,
                        ),
                    ).fetchall()
                    esco_occ = next(
                        (
                            candidate for candidate in esco_candidates
                            if occupation_label_matches(
                                normalized_role,
                                candidate["preferred_label"],
                                candidate["alt_labels"],
                            )
                        ),
                        None,
                    )
                    if esco_occ:
                        soc_code = esco_occ["concept_uri"]
                        resolved_role_name = esco_occ["preferred_label"]
                        rows = conn.execute(
                            """
                            SELECT skill_label, skill_type, relation_type
                            FROM ref_esco_occupation_skill_relations
                            WHERE occupation_uri = ?
                            ORDER BY CASE relation_type
                                WHEN 'essential' THEN 0
                                WHEN 'optional' THEN 1
                                ELSE 2
                            END, lower(skill_label)
                            LIMIT 30
                            """,
                            (soc_code,),
                        ).fetchall()
                        requirements = [
                            {
                                "workplace_example": row["skill_label"],
                                "element_name": row["skill_type"] or "Competency",
                                "relation_type": row["relation_type"],
                                "hot_technology": row["relation_type"] == "essential",
                                "in_demand": False,
                            }
                            for row in rows
                            if row["skill_label"]
                        ]
                        if requirements:
                            source_name = "ESCO occupation taxonomy"
        except Exception as exc:
            logger.warning("Error fetching role requirements: %s", exc)

        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(resolved_role_name, soc_code)
        if not source_name or not requirements:
            return JobIntelligenceResult(
                capability_id="job_role_requirements",
                headline=f"No occupation skill records were found for '{requested_role}' in the local O*NET or ESCO reference taxonomies.",
                facts=[], evidence=evidence + [V2EvidenceItem(
                    evidence_id=f"evi:role_requirements_missing:{requested_role.casefold().replace(' ', '_')}",
                    source="Local O*NET and ESCO occupation taxonomies",
                    signal_family="reference_taxonomy",
                    measured_signal_type="role_skill_requirements",
                    time_grain="static",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    confidence_status="low",
                    quality="insufficient_history",
                    description=f"No occupation skills were found for '{requested_role}' in either local taxonomy.",
                )], readiness_state="insufficient_data", metadata={"requirements_count": 0, "resolution_status": "not_found"},
            )

        essential_skills = [
            row["workplace_example"] for row in requirements
            if row.get("relation_type") == "essential"
        ]
        optional_skills = [
            row["workplace_example"] for row in requirements
            if row.get("relation_type") == "optional"
        ]
        other_skills = [
            row["workplace_example"] for row in requirements
            if row["workplace_example"] not in essential_skills
            and row["workplace_example"] not in optional_skills
        ]
        facts = [
            V2StructuredFact(
                fact_id=f"fact:role_reqs:{resolved_role_name.casefold().replace(' ', '_')}",
                fact_type="role_skill_requirements",
                entity_name=resolved_role_name,
                canonical_entity_id=soc_code,
                entity_type="occupation",
                metric_name="occupation_skills_count",
                metric_value=len(requirements),
                unit="skills",
                source=source_name,
                data_origin="local_reference_dataset",
                details={
                    "essential_skills": essential_skills,
                    "optional_skills": optional_skills,
                    "other_skills": other_skills,
                    "skills_describe_occupation_only": True,
                },
            )
        ]

        headline = (
            (
                f"No exact match for {requested_role}; showing {resolved_role_name}. "
                if normalize_occupation_name(requested_role) != normalize_occupation_name(resolved_role_name)
                else ""
            )
            + f"Skills associated with {resolved_role_name} in the {source_name}: "
            f"{len(requirements)} occupation-description skills cataloged. "
            "These skills describe the occupation; they are not hiring demand and are not platform-collected data."
        )

        return JobIntelligenceResult(
            capability_id="job_role_requirements",
            headline=headline,
            facts=facts,
            evidence=evidence + [V2EvidenceItem(
                evidence_id=f"evi:occupation_skills:{soc_code}",
                source=source_name,
                signal_family="reference_taxonomy",
                measured_signal_type="occupation_skill_description",
                time_grain="static",
                data_origin="local_reference_dataset",
                provenance_id=f"occupation:{soc_code}",
                taxonomy_version="O*NET 28.0" if source_name.startswith("O*NET") else "ESCO v1.2.1",
                readiness_state="observed",
                confidence_status="high",
                description=f"Static {source_name} associations describe the occupation and do not measure hiring demand.",
            )],
            metadata={
                "requirements_count": len(requirements),
                "source": source_name,
                "essential_skills_count": len(essential_skills),
                "optional_skills_count": len(optional_skills),
            },
        )

    def run_mobility_pathways(
        self,
        current_or_target_role: str,
        limit: int = 10,
    ) -> JobIntelligenceResult:
        """Identify career mobility pathways using O*NET related occupations and ESCO transfers."""
        mobility_res = self.mobility_engine.get_pathways(current_or_target_role, limit=limit)

        pathways: list[dict[str, Any]] = [
            {
                "related_soc_code": p.destination_soc_code,
                "related_title": p.destination_occupation_title,
                "relatedness_tier": p.relatedness_tier,
                "shared_skills": p.shared_skills,
                "additional_destination_skills": p.additional_destination_skills,
                "relationship_nature": p.relationship_nature,
                "explanation": p.explanation,
            }
            for p in mobility_res.pathways
        ]

        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(
            current_or_target_role, mobility_res.source_soc_code
        )
        facts = [
            V2StructuredFact(
                fact_id=f"fact:mobility:{current_or_target_role.casefold().replace(' ', '_')}",
                fact_type="career_mobility_pathways",
                entity_name=current_or_target_role,
                canonical_entity_id=mobility_res.source_soc_code,
                entity_type="occupation",
                metric_name="pathways_count",
                metric_value=len(pathways),
                unit="pathways",
                period="2024",
                source="O*NET 28.0 Related Occupations",
                data_origin="local_reference_dataset",
                details={
                    "related_occupations": [p["related_title"] for p in pathways],
                    "tiers": [p["relatedness_tier"] for p in pathways],
                },
            )
        ]

        headline = (
            f"Career Mobility Pathways for {mobility_res.source_occupation_title}: Identified {len(pathways)} "
            f"adjacent and transitionary occupations grounded in official O*NET mobility data."
        )

        return JobIntelligenceResult(
            capability_id="job_mobility_pathways",
            headline=headline,
            facts=facts,
            evidence=evidence,
            pathways=pathways,
            mobility_result=mobility_res,
            metadata={"pathways_count": len(pathways), "source_soc_code": mobility_res.source_soc_code},
            readiness_state="insufficient_data" if not mobility_res.source_soc_code or not pathways else "ready",
        )

    def run_profile_alignment(
        self,
        target_role: str,
        profile_skills: list[str],
    ) -> JobIntelligenceResult:
        """Evaluate candidate profile fit for a target job role."""
        alignment = self.skill_mapper.align_role_skills(target_role, profile_skills)
        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(target_role, alignment.role_code)

        if not alignment.role_code or alignment.coverage_denominator == 0:
            return JobIntelligenceResult(
                capability_id="job_profile_alignment",
                headline=f"Profile alignment is unavailable: '{target_role}' did not resolve to role requirements in local O*NET or ESCO data.",
                facts=[], evidence=evidence + [V2EvidenceItem(
                    evidence_id=f"evi:job_alignment_missing:{target_role.casefold().replace(' ', '_')}",
                    source="Local O*NET/ESCO reference taxonomies",
                    signal_family="reference_taxonomy",
                    measured_signal_type="role_skill_requirements",
                    time_grain="static",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    confidence_status="low",
                    quality="insufficient_history",
                    description=f"'{target_role}' did not resolve to a role with reference skill requirements.",
                )], alignment=alignment, readiness_state="insufficient_data",
                metadata={"coverage": None, "resolution_status": "not_found"},
            )

        facts = [
            V2StructuredFact(
                fact_id=f"fact:job_alignment:{target_role.casefold().replace(' ', '_')}",
                fact_type="job_profile_alignment",
                entity_name=target_role,
                canonical_entity_id=alignment.role_code,
                entity_type="occupation",
                metric_name="alignment_ratio",
                metric_value=alignment.coverage_score,
                unit="ratio",
                denominator=float(alignment.coverage_denominator),
                period="2024",
                source=f"O*NET ({alignment.taxonomy_source})",
                data_origin="local_reference_dataset",
                details={
                    "matched_skills": alignment.matched_skills,
                    "not_declared_skills": alignment.not_declared_skills,
                },
            )
        ]

        headline = (
            f"Candidate profile aligns with {alignment.coverage_numerator} of {alignment.coverage_denominator} "
            f"verified core requirements for {target_role} ({int(alignment.coverage_score * 100)}% coverage)."
        )

        return JobIntelligenceResult(
            capability_id="job_profile_alignment",
            headline=headline,
            facts=facts,
            evidence=evidence,
            alignment=alignment,
            metadata={"coverage": alignment.coverage_score},
        )

    def run_preparation_actions(
        self,
        target_role: str | None = None,
        *,
        user_skills: list[str] | None = None,
        desired_timeline: str | None = None,
        gap_skills: list[str] | None = None,
    ) -> JobIntelligenceResult:
        """Generate structured role preparation actions, milestones, and practice tasks."""
        import uuid

        target_r = (target_role or "Software Developer").strip()
        plan = self.action_engine.build_role_preparation_plan(
            target_role=target_r,
            store=self.store,
            user_skills=user_skills,
            desired_timeline=desired_timeline,
            gap_skills=gap_skills,
        )
        source_name = (
            "ESCO occupation taxonomy"
            if (plan.soc_code or "").startswith("http://data.europa.eu/esco/")
            else "O*NET occupation taxonomy"
        )

        facts: list[V2StructuredFact] = []
        for action in plan.actions:
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:action:{target_r.casefold().replace(' ', '_')[:20]}:{action.order}:{uuid.uuid4().hex[:6]}",
                    fact_type="action_recommendation",
                    entity_name=action.skill_name,
                    canonical_entity_id=plan.soc_code,
                    entity_type="skill",
                    metric_name="preparation_priority",
                    metric_value=action.priority,
                    source=action.evidence_reference or "O*NET 28.0",
                    data_origin="local_reference_dataset",
                    details={
                        "action_title": action.action_title,
                        "classification": action.priority,
                        "reason": action.why_matters,
                        "next_action": action.concrete_next_step,
                        "suggested_action": action.suggested_task,
                        "self_check_criteria": action.self_check_criteria,
                        "prerequisites": action.prerequisites,
                        "order": action.order,
                        "milestone": action.milestone,
                        "recommendation_basis": action.requirement_type,
                        "proficiency_verified": False,
                    },
                )
            )

        if plan.total_actions > 0:
            headline = (
                (
                    f"No exact match for {target_r}; showing {plan.resolved_role_name}. "
                    if plan.resolved_role_name
                    and normalize_occupation_name(target_r) != normalize_occupation_name(plan.resolved_role_name)
                    else ""
                )
                + f"Deterministic Career Preparation Plan for {plan.resolved_role_name or target_r}: {plan.total_actions} technical actions "
                f"sequenced with verification checklists from the {source_name}. "
                "These actions use skills associated with the occupation; they are not hiring demand or platform-collected data."
            )
            readiness = "ready"
        else:
            headline = (
                f"Role preparation actions could not be generated for '{target_r}'. "
                "No matching occupation skills were available in the local O*NET or ESCO occupation taxonomies. "
                "Please provide a target occupation or profile skills."
            )
            readiness = "requires_clarification" if not target_role else "insufficient_data"

        summary_fact = V2StructuredFact(
            fact_id=f"fact:action_summary:{target_r.casefold().replace(' ', '_')[:20]}:{uuid.uuid4().hex[:6]}",
            fact_type="learning_recommendation_readiness",
            entity_name=target_r,
            canonical_entity_id=plan.soc_code,
            entity_type="occupation",
            metric_name="plan_status",
            metric_value=readiness,
            source=source_name if plan.role_resolved else "Local O*NET and ESCO occupation taxonomies",
            data_origin="local_reference_dataset",
            details={
                "message": headline,
                "total_actions": plan.total_actions,
                "target_role": target_r,
                "is_provisional": plan.is_provisional,
                "provisional_reason": plan.provisional_reason,
                "user_matched_skills": plan.user_matched_skills,
                "gap_skills_addressed": plan.gap_skills_addressed,
                "timeline_summary": plan.timeline_summary,
            },
        )
        facts.append(summary_fact)

        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(target_r, plan.soc_code)

        return JobIntelligenceResult(
            capability_id="job_preparation_actions",
            headline=headline,
            facts=facts,
            evidence=evidence,
            action_plan=plan,
            readiness_state=readiness,
            metadata={
                "actions_count": plan.total_actions,
                "target_role": target_r,
                "role_resolved": plan.role_resolved,
                "soc_code": plan.soc_code,
                "is_provisional": plan.is_provisional,
                "provisional_reason": plan.provisional_reason,
                "user_matched_skills": plan.user_matched_skills,
                "gap_skills_addressed": plan.gap_skills_addressed,
                "timeline": desired_timeline,
            },
        )

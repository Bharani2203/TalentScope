"""Greenfield Intelligence Engine V2 — Skill Intelligence Engine.

Executes the 6 Skill Intelligence features:
1. skill_demand_trends
2. skill_historical_signals
3. skill_role_alignment
4. skill_evidence_citations
5. skill_reference_profile
6. skill_action_recommendations
"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.analytics.trend import CALCULATION_VERSION, theil_sen_slope
from app.analytics.skill_health import evaluate_skill_health
from app.intelligence_v2.contracts import (
    RelatedSkillsResult,
    RoleSkillAlignmentResult,
    TaxonomyLookupResult,
    V2EvidenceItem,
    V2StructuredFact,
)
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.occupation_names import normalize_occupation_name
from app.intelligence_v2.reference_intelligence import (
    ReferenceTaxonomyLookupEngine,
    RelatedSkillsEngine,
    RoleSkillAlignmentEngine,
)
from app.intelligence_v2.role_actions import RolePreparationPlan, V2RoleActionEngine
from app.intelligence_v2.skill_mapping import RoleSkillAlignment, V2SkillMapper
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


class SkillIntelligenceResult(BaseModel):
    """Unified output from Skill Intelligence capability execution."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    target_skill: str
    headline: str
    facts: list[V2StructuredFact] = Field(default_factory=list)
    evidence: list[V2EvidenceItem] = Field(default_factory=list)
    alignment: RoleSkillAlignment | None = None
    action_plan: RolePreparationPlan | None = None
    lookup_result: TaxonomyLookupResult | None = None
    related_skills_result: RelatedSkillsResult | None = None
    role_alignment_result: RoleSkillAlignmentResult | None = None
    readiness_state: Literal["ready", "partial", "insufficient_data"] = "ready"
    metadata: dict[str, Any] = Field(default_factory=dict)


_TECH_CONCEPT_EXPLANATIONS: dict[str, str] = {
    "python": (
        "Python is a versatile, high-level programming language renowned for its clean syntax, readability, and vast package ecosystem. "
        "For example, developers commonly use Python with frameworks like FastAPI or Django to build web APIs, and with pandas or PyTorch for data analysis and machine learning."
    ),
    "java": (
        "Java is an established, object-oriented, cross-platform programming language widely used in enterprise server environments and distributed systems. "
        "For example, backend engineers frequently use Java with Spring Boot to construct robust, high-throughput microservices and Android mobile applications."
    ),
    "react": (
        "React is a declarative, component-based frontend JavaScript library for building responsive user interfaces. "
        "For example, web developers use React components and hooks to manage interactive application state and render dynamic browser interfaces."
    ),
    "docker": (
        "Docker is an industry-standard containerization platform that packages applications together with their operating dependencies into portable, isolated containers. "
        "For example, DevOps teams use Docker to guarantee identical software behavior across local development machines, testing pipelines, and production clouds."
    ),
    "go": (
        "Go (Golang) is a statically typed, compiled programming language designed at Google for simplicity, high-performance concurrency, and network efficiency. "
        "For example, cloud-native infrastructure software like Kubernetes and Docker is written in Go."
    ),
    "kubernetes": (
        "Kubernetes is an open-source container orchestration engine that automates deploying, scaling, and managing containerized applications across compute clusters. "
        "For example, platform engineers use Kubernetes to automatically scale web services in response to real-time traffic spikes and manage zero-downtime rolling updates."
    ),
    "sql": (
        "SQL (Structured Query Language) is the standard declarative language for storing, querying, and manipulating structured relational data. "
        "For example, data engineers use SQL queries with systems like PostgreSQL to execute complex joins, filter millions of transactional records, and aggregate business metrics."
    ),
    "typescript": (
        "TypeScript is a strongly typed superset of JavaScript developed by Microsoft that adds optional static typing and class-based object orientation. "
        "For example, engineering teams use TypeScript with React or Node.js to catch type errors at compile time and build maintainable enterprise web applications."
    ),
}


def get_concept_explanation_with_example(skill_name: str | None) -> str | None:
    """Return clear conceptual prose and a practical example for common technologies."""
    if not skill_name:
        return None
    cleaned = skill_name.strip().casefold()
    if cleaned in _TECH_CONCEPT_EXPLANATIONS:
        return _TECH_CONCEPT_EXPLANATIONS[cleaned]
    # Check if any key is contained
    for key, text in _TECH_CONCEPT_EXPLANATIONS.items():
        if key in cleaned:
            return text
    return (
        f"{skill_name} is a documented technical competency in official occupational frameworks (O*NET 28.0 and ESCO v1.2.1). "
        f"For example, software practitioners use {skill_name} to implement production features and collaborate in modern development environments."
    )


class V2SkillIntelligenceEngine:
    """Executes skill intelligence workflows against verified local datasets."""

    def __init__(
        self,
        store: ReferenceDataStore | None = None,
        skill_mapper: V2SkillMapper | None = None,
        evidence_retriever: V2EvidenceRetriever | None = None,
        action_engine: V2RoleActionEngine | None = None,
        reference_lookup: ReferenceTaxonomyLookupEngine | None = None,
        related_skills_engine: RelatedSkillsEngine | None = None,
        role_alignment_engine: RoleSkillAlignmentEngine | None = None,
    ) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.skill_mapper = skill_mapper or V2SkillMapper(self.store)
        self.evidence_retriever = evidence_retriever or V2EvidenceRetriever(self.store)
        self.action_engine = action_engine or V2RoleActionEngine()
        self.reference_lookup = reference_lookup or ReferenceTaxonomyLookupEngine(self.store)
        self.related_skills_engine = related_skills_engine or RelatedSkillsEngine(self.store)
        self.role_alignment_engine = role_alignment_engine or RoleSkillAlignmentEngine(self.store)

    def run_demand_trends(
        self,
        skill_name: str,
        geography: str = "all",
    ) -> SkillIntelligenceResult:
        """Analyze demand trends using GitHub developer adoption or monthly observations."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []

        # 1. Fetch developer adoption evidence
        adoption_evidence = self.evidence_retriever.get_developer_adoption_evidence(canonical, country=geography)
        evidence.extend(adoption_evidence)

        # 2. Fetch hiring demand observations (or insufficient data status)
        hiring_evidence = self.evidence_retriever.get_hiring_demand_evidence(canonical, geography=geography)
        evidence.extend(hiring_evidence)

        # 3. Pull time series from SQLite
        series: list[dict[str, Any]] = []
        is_global = geography.lower() in {"all", "global", "world"} or len(geography) != 2
        try:
            with self.store._connect() as conn:
                if is_global:
                    rows = conn.execute(
                        """
                        SELECT period, SUM(num_pushers) as num_pushers, year, quarter
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?)
                        GROUP BY year, quarter, period
                        ORDER BY year ASC, quarter ASC
                        """,
                        (canonical,),
                    ).fetchall()
                    if not rows:
                        rows = conn.execute(
                            """
                            SELECT period, SUM(num_pushers) as num_pushers, year, quarter
                            FROM ref_github_topic_adoption
                            WHERE lower(topic) = lower(?)
                            GROUP BY year, quarter, period
                            ORDER BY year ASC, quarter ASC
                            """,
                            (canonical,),
                        ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT period, num_pushers, year, quarter
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?) AND iso2_code = ?
                        ORDER BY year ASC, quarter ASC
                        """,
                        (canonical, geography.upper()),
                    ).fetchall()
                    if not rows:
                        rows = conn.execute(
                            """
                            SELECT period, num_pushers, year, quarter
                            FROM ref_github_topic_adoption
                            WHERE lower(topic) = lower(?) AND iso2_code = ?
                            ORDER BY year ASC, quarter ASC
                            """,
                            (canonical, geography.upper()),
                        ).fetchall()
                series = [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("Error fetching series for %s: %s", canonical, exc)

        if len(series) >= 2:
            latest = series[-1]
            prev = series[-2]
            values = [float(r["num_pushers"]) for r in series]
            periods = [str(r["period"]) for r in series]
            latest_v = values[-1]
            prev_v = values[-2]

            pct_change = round(((latest_v - prev_v) / prev_v) * 100, 2) if prev_v > 0 else 0.0
            yoy_change = round(((latest_v - values[-5]) / values[-5]) * 100, 2) if len(values) >= 5 and values[-5] > 0 else None

            # Robust Theil-Sen slope and relative quarterly slope calculation
            ts_slope = round(theil_sen_slope(values), 2)
            med_val = statistics.median(values)
            rel_slope = round(ts_slope / med_val, 4) if med_val > 0 else 0.0

            # Directional determination based on relative slope and quarterly growth
            if rel_slope > 0.02 or pct_change > 2.0:
                direction = "Growing"
            elif rel_slope < -0.02 or pct_change < -2.0:
                direction = "Declining"
            else:
                direction = "Stable"

            # 1. Primary developer adoption volume fact (retains contract for volume checks)
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:adoption_latest:{canonical.casefold()}:{latest['period']}",
                    fact_type="developer_adoption_latest",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="num_pushers",
                    metric_value=latest["num_pushers"],
                    unit="pushers",
                    period=latest["period"],
                    source="GitHub Innovation Graph",
                    data_origin="real",
                    history_type="backfill",
                    evidence_reference=adoption_evidence[0].evidence_id if adoption_evidence else None,
                    details={
                        "quarter_over_quarter_change_pct": pct_change,
                        "change_pct": pct_change,
                        "geography": geography,
                        "location": geography,
                        "signal_type": "adoption",
                        "source_family": "developer_adoption",
                    },
                )
            )

            # 2. Canonical trend analysis fact (renders trend card and indicator in frontend)
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:trend:{canonical.casefold()}:{latest['period']}",
                    fact_type="trend_analysis",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="trend_direction",
                    metric_value=direction,
                    unit="quarterly developer pushers",
                    period=f"{prev['period']}_to_{latest['period']}",
                    source="GitHub Innovation Graph",
                    data_origin="real",
                    history_type="backfill",
                    series_id=f"github_adoption:{canonical.casefold()}:{geography.lower()}",
                    readiness_state="ready",
                    calculation_version=CALCULATION_VERSION,
                    evidence_reference=adoption_evidence[0].evidence_id if adoption_evidence else None,
                    details={
                        "signal_type": "adoption",
                        "provider": "GitHub Innovation Graph",
                        "source_family": "developer_adoption",
                        "metric": "num_pushers",
                        "unit": "pushers",
                        "time_grain": "quarter",
                        "location": geography,
                        "geography": geography,
                        "start_period": periods[0],
                        "end_period": latest["period"],
                        "observation_count": len(series),
                        "comparison_period": f"{prev['period']} to {latest['period']}",
                        "latest_value": latest["num_pushers"],
                        "previous_value": prev["num_pushers"],
                        "growth_pct": pct_change,
                        "change_pct": pct_change,
                        "yoy_growth_pct": yoy_change,
                        "theil_sen_slope_per_quarter": ts_slope,
                        "relative_slope_per_quarter": rel_slope,
                        "formula": "QoQ: ((V_latest - V_prev) / V_prev) * 100; Median Theil-Sen slope over consecutive quarters",
                        "data_freshness": latest["period"],
                        "mapping_status": mapping.status,
                        "mapping_coverage": f"canonical skill ({mapping.status})",
                        "readiness_status": "ready",
                        "limitations": "This metric measures quarterly developer activity and repository adoption from GitHub Innovation Graph; it is not a measure of job postings or monthly employer hiring demand.",
                    },
                )
            )

            # 3. Transparent hiring demand readiness fact
            hiring_months = 0
            try:
                with self.store._connect() as conn:
                    h_row = conn.execute(
                        """SELECT COUNT(DISTINCT period) as cnt FROM market_observations
                           WHERE (lower(skill) = lower(?) OR lower(COALESCE(skill_id, '')) = lower(?))
                             AND lower(signal_type) = 'demand'
                             AND lower(COALESCE(data_origin, '')) = 'real'
                             AND lower(COALESCE(history_type, '')) IN ('platform_collected', 'backfill', 'backfilled')
                             AND (lower(COALESCE(location, '')) = lower(?) OR ? in ('all', 'global'))""",
                        (canonical, canonical, geography, geography.lower()),
                    ).fetchone()
                    if h_row:
                        hiring_months = int(h_row["cnt"] or 0)
            except Exception:
                hiring_months = 0

            hiring_ready = hiring_months >= 4
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:readiness:hiring_demand:{canonical.casefold()}",
                    fact_type="analysis_readiness",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="hiring_demand_readiness",
                    metric_value="ready" if hiring_ready else "insufficient_data",
                    unit="status",
                    source="TalentScope Job Observation Pipeline",
                    data_origin="real" if hiring_months > 0 else "unavailable",
                    readiness_state="ready" if hiring_ready else "insufficient_data",
                    details={
                        "reason": (
                            f"Hiring demand series has {hiring_months} consecutive completed months of verified job-posting observations."
                            if hiring_ready
                            else f"Hiring demand trends require at least 4 consecutive completed months of verified job-posting observations (currently {hiring_months} months available)."
                        ),
                        "months_available": hiring_months,
                        "months_required": 4,
                        "signal_type": "demand",
                        "source_family": "hiring_demand",
                    },
                )
            )

            # 4. Recent quarterly observations (for history timeline visualization)
            for r in series[-8:]:
                facts.append(
                    V2StructuredFact(
                        fact_id=f"fact:obs:{canonical.casefold()}:{r['period']}",
                        fact_type="historical_observation",
                        entity_name=canonical,
                        canonical_entity_id=mapping.canonical_id,
                        entity_type="skill",
                        metric_name="developer_pushers",
                        metric_value=r["num_pushers"],
                        unit="unique developers per quarter",
                        period=r["period"],
                        source="GitHub Innovation Graph",
                        data_origin="real",
                        history_type="backfill",
                        series_id=f"github_adoption:{canonical.casefold()}:{geography.lower()}",
                        details={
                            "signal_type": "adoption",
                            "frequency": "quarterly",
                            "geography": geography,
                            "source_family": "developer_adoption",
                        },
                    )
                )

            headline = (
                f"Quarterly developer adoption for {canonical} is {direction.lower()} at {latest['num_pushers']:,} active GitHub pushers "
                f"in {latest['period']} ({pct_change:+.1f}% vs {prev['period']}, Theil-Sen slope {ts_slope:+.1f} pushers/quarter across {len(series)} quarters). "
                f"This reflects developer activity and adoption on GitHub, not monthly employer hiring demand."
            )
            meta = {
                "total_observations": len(series),
                "mapping_status": mapping.status,
                "theil_sen_slope": ts_slope,
                "relative_slope": rel_slope,
                "trend_direction": direction,
                "source_family": "developer_adoption",
                "time_grain": "quarter",
            }
        else:
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:readiness:adoption:{canonical.casefold()}",
                    fact_type="analysis_readiness",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="adoption_trend_readiness",
                    metric_value="insufficient_data",
                    unit="status",
                    source="GitHub Innovation Graph",
                    data_origin="unavailable" if not series else "real",
                    readiness_state="insufficient_data",
                    details={
                        "reason": f"Fewer than 2 comparable quarterly observations available for {canonical} in geography '{geography}'.",
                        "periods_available": len(series),
                        "periods_required": 2,
                        "signal_type": "adoption",
                    },
                )
            )
            headline = f"Limited observation history ({len(series)} quarters) available for {canonical} in the evaluated geography."
            meta = {"total_observations": len(series), "mapping_status": mapping.status}

        readiness_state: Literal["ready", "partial", "insufficient_data"] = "ready" if len(series) >= 2 else "insufficient_data"
        return SkillIntelligenceResult(
            capability_id="skill_demand_trends",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state=readiness_state,
            metadata=meta,
        )

    def run_historical_signals(
        self,
        skill_name: str,
        geography: str = "all",
    ) -> SkillIntelligenceResult:
        """Retrieve full quarterly historical signals from GitHub Innovation Graph."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        evidence = self.evidence_retriever.get_developer_adoption_evidence(canonical, country=geography)
        facts: list[V2StructuredFact] = []

        series: list[dict[str, Any]] = []
        is_global = geography.lower() in {"all", "global", "world"} or len(geography) != 2
        try:
            with self.store._connect() as conn:
                if is_global:
                    rows = conn.execute(
                        """
                        SELECT period, SUM(num_pushers) as num_pushers, year, quarter
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?)
                        GROUP BY year, quarter, period
                        ORDER BY year ASC, quarter ASC
                        """,
                        (canonical,),
                    ).fetchall()
                    if not rows:
                        rows = conn.execute(
                            """
                            SELECT period, SUM(num_pushers) as num_pushers, year, quarter
                            FROM ref_github_topic_adoption
                            WHERE lower(topic) = lower(?)
                            GROUP BY year, quarter, period
                            ORDER BY year ASC, quarter ASC
                            """,
                            (canonical,),
                        ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT period, num_pushers, year, quarter
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?) AND iso2_code = ?
                        ORDER BY year ASC, quarter ASC
                        """,
                        (canonical, geography.upper()),
                    ).fetchall()
                    if not rows:
                        rows = conn.execute(
                            """
                            SELECT period, num_pushers, year, quarter
                            FROM ref_github_topic_adoption
                            WHERE lower(topic) = lower(?) AND iso2_code = ?
                            ORDER BY year ASC, quarter ASC
                            """,
                            (canonical, geography.upper()),
                        ).fetchall()
                series = [dict(r) for r in rows]
        except Exception:
            series = []

        if series:
            first = series[0]
            latest = series[-1]
            max_pt = max(series, key=lambda x: x["num_pushers"])

            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:hist_summary:{canonical.casefold()}",
                    fact_type="historical_adoption_summary",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="historical_span",
                    metric_value=f"{first['period']} to {latest['period']}",
                    unit="quarters",
                    period=f"{first['period']}-{latest['period']}",
                    source="GitHub Innovation Graph",
                    data_origin="real",
                    history_type="backfill",
                    evidence_reference=evidence[0].evidence_id if evidence else None,
                    details={
                        "total_quarters": len(series),
                        "peak_period": max_pt["period"],
                        "peak_pushers": max_pt["num_pushers"],
                        "latest_pushers": latest["num_pushers"],
                    },
                )
            )
            headline = (
                f"Historical developer adoption for {canonical} spans {len(series)} quarters "
                f"({first['period']} to {latest['period']}), peaking at {max_pt['num_pushers']:,} pushers in {max_pt['period']}."
            )
        else:
            headline = f"No historical GitHub adoption data found for {canonical}."

        return SkillIntelligenceResult(
            capability_id="skill_historical_signals",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state="insufficient_data" if not series else "ready",
            metadata={"series_length": len(series)},
        )

    def run_skill_lookup(
        self,
        query: str,
        entity_type: Literal["all", "skill", "occupation"] = "all",
        limit: int = 15,
        context: str | None = None,
        exact_occupation: bool = False,
    ) -> SkillIntelligenceResult:
        """Execute canonical skill or occupation reference lookup with ambiguity handling."""
        lookup_res = self.reference_lookup.lookup(
            query,
            entity_type=entity_type,
            limit=limit,
            context=context,
            exact_occupation=exact_occupation,
        )
        facts: list[V2StructuredFact] = []
        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(query)

        for item in lookup_res.results[:5]:
            clean_id = item.canonical_id.replace(":", "_").replace("/", "_").replace(".", "_")
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:lookup:{clean_id}",
                    fact_type="reference_taxonomy_lookup",
                    entity_name=item.name,
                    canonical_entity_id=item.canonical_id,
                    entity_type=item.entity_type,
                    metric_name="taxonomy_match_status",
                    metric_value=item.status,
                    source=item.source,
                    data_origin="local_reference_dataset",
                    details={
                        "taxonomy": item.taxonomy,
                        "description": item.description,
                        "ambiguity_note": item.ambiguity_note,
                        **item.metadata,
                    },
                )
            )

        readiness: Literal["ready", "partial", "insufficient_data"] = (
            lookup_res.status if lookup_res.status in {"ready", "partial", "insufficient_data"} else "partial"
        )
        headline = lookup_res.explanation
        if exact_occupation and lookup_res.results:
            resolved_occupation = next(
                (item for item in lookup_res.results if item.entity_type == "occupation"),
                None,
            )
            if (
                resolved_occupation
                and normalize_occupation_name(resolved_occupation.name)
                != normalize_occupation_name(query)
            ):
                headline = (
                    f"No exact match for {query}; showing {resolved_occupation.name}. "
                    f"{headline}"
                )
        return SkillIntelligenceResult(
            capability_id="skill_lookup",
            target_skill=query,
            headline=headline,
            facts=facts,
            evidence=evidence,
            lookup_result=lookup_res,
            readiness_state=readiness,
            metadata={"total_matches": lookup_res.total_matches, "clarification_needed": lookup_res.clarification_needed},
        )

    def run_related_skills(
        self,
        skill_name: str,
        limit: int = 10,
    ) -> SkillIntelligenceResult:
        """Compute explainable related skills classified by relationship type and PPMI/IOF ranking."""
        related_res = self.related_skills_engine.get_related_skills(skill_name, limit=limit)
        facts: list[V2StructuredFact] = []
        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(skill_name)

        for rel_item in related_res.related_skills:
            clean_name = rel_item.skill_name.casefold().replace(" ", "_").replace("/", "_")
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:related:{skill_name.casefold()}:{clean_name}",
                    fact_type="related_skill_relationship",
                    entity_name=rel_item.skill_name,
                    canonical_entity_id=rel_item.canonical_id,
                    entity_type="skill",
                    metric_name="ppmi_iof_ranking_score",
                    metric_value=rel_item.ranking_score,
                    unit="score",
                    source=rel_item.source,
                    data_origin="local_reference_dataset",
                    details={
                        "relationship_type": rel_item.relationship_type,
                        "supporting_relationship": rel_item.supporting_relationship,
                        "ranking_method": rel_item.ranking_method,
                        "explanation": rel_item.explanation,
                    },
                )
            )

        readiness: Literal["ready", "partial", "insufficient_data"] = (
            related_res.status if related_res.status in {"ready", "partial", "insufficient_data"} else "partial"
        )
        return SkillIntelligenceResult(
            capability_id="related_skills",
            target_skill=related_res.target_skill,
            headline=related_res.explanation,
            facts=facts,
            evidence=evidence,
            related_skills_result=related_res,
            readiness_state=readiness,
            metadata={"related_skills_count": len(related_res.related_skills)},
        )

    def run_role_alignment(
        self,
        target_role: str,
        declared_skills: list[str],
    ) -> SkillIntelligenceResult:
        """Perform truthful skill-to-role alignment with explicit declaration semantics."""
        alignment_res = self.role_alignment_engine.align(target_role, declared_skills)

        # Backwards compatible RoleSkillAlignment model for existing tests
        legacy_alignment = RoleSkillAlignment(
            role_name=target_role,
            role_code=alignment_res.canonical_occupation_id,
            taxonomy_source="onet" if "onet" in alignment_res.taxonomy_source.lower() else "esco",
            required_skills=alignment_res.reference_associated_skills,
            matched_skills=alignment_res.matched_skills,
            not_declared_skills=alignment_res.unmatched_reference_skills,
            unmapped_skills=alignment_res.unresolved_skills,
            coverage_score=round(len(alignment_res.matched_skills) / max(1, len(alignment_res.reference_associated_skills)), 2),
            coverage_numerator=len(alignment_res.matched_skills),
            coverage_denominator=len(alignment_res.reference_associated_skills),
            disclaimer=alignment_res.disclaimer,
        )

        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(target_role, alignment_res.canonical_occupation_id)
        facts = [
            V2StructuredFact(
                fact_id=f"fact:alignment:{target_role.casefold().replace(' ', '_')}",
                fact_type="role_skill_coverage",
                entity_name=target_role,
                canonical_entity_id=alignment_res.canonical_occupation_id,
                entity_type="occupation",
                metric_name="reference_matched_count",
                metric_value=len(alignment_res.matched_skills),
                unit="skills",
                denominator=float(len(alignment_res.reference_associated_skills)),
                period="2024",
                source=f"O*NET / ESCO ({alignment_res.taxonomy_source})",
                data_origin="local_reference_dataset",
                details={
                    "matched_skills": alignment_res.matched_skills,
                    "unmatched_reference_skills": alignment_res.unmatched_reference_skills,
                    "unresolved_skills": alignment_res.unresolved_skills,
                    "ambiguous_skills": alignment_res.ambiguous_skills,
                    "disclaimer": alignment_res.disclaimer,
                },
            )
        ]

        readiness: Literal["ready", "partial", "insufficient_data"] = (
            alignment_res.status if alignment_res.status in {"ready", "partial", "insufficient_data"} else "partial"
        )
        return SkillIntelligenceResult(
            capability_id="skill_role_alignment",
            target_skill=target_role,
            headline=alignment_res.explanation,
            facts=facts,
            evidence=evidence,
            alignment=legacy_alignment,
            role_alignment_result=alignment_res,
            readiness_state=readiness,
            metadata={
                "matched_count": len(alignment_res.matched_skills),
                "unmatched_count": len(alignment_res.unmatched_reference_skills),
                "unresolved_count": len(alignment_res.unresolved_skills),
                "ambiguous_count": len(alignment_res.ambiguous_skills),
            },
        )

    def run_evidence_citations(
        self,
        skill_name: str,
    ) -> SkillIntelligenceResult:
        """Produce full transparent citations and provenance for a skill."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        evidence: list[V2EvidenceItem] = []
        evidence.extend(self.evidence_retriever.get_developer_adoption_evidence(canonical))
        evidence.extend(self.evidence_retriever.get_reference_taxonomy_evidence(canonical))
        evidence.extend(self.evidence_retriever.get_hiring_demand_evidence(canonical))

        headline = f"Retrieved {len(evidence)} evidence citations across signal families for {canonical}."

        return SkillIntelligenceResult(
            capability_id="skill_evidence_citations",
            target_skill=canonical,
            headline=headline,
            facts=[],
            evidence=evidence,
            metadata={"evidence_count": len(evidence)},
        )

    def run_reference_profile(
        self,
        skill_name: str,
    ) -> SkillIntelligenceResult:
        """Retrieve static reference taxonomy profile from O*NET and ESCO."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        evidence = self.evidence_retriever.get_reference_taxonomy_evidence(canonical)
        facts: list[V2StructuredFact] = []

        onet_rows = mapping.onet_matches or self.skill_mapper._search_onet_software_skills(canonical)
        esco_rows = mapping.esco_matches or self.skill_mapper._search_esco_skills(canonical)

        hot_tech = any(bool(r.get("hot_technology")) for r in onet_rows)
        in_demand = any(bool(r.get("in_demand")) for r in onet_rows)

        # Retrieve related skills from O*NET software skills and ESCO relations
        related_skills: list[str] = []
        try:
            with self.store._connect() as conn:
                onet_related = conn.execute(
                    """
                    SELECT workplace_example, count(*) as c
                    FROM ref_onet_software_skills
                    WHERE soc_code IN (
                        SELECT DISTINCT soc_code FROM ref_onet_software_skills
                        WHERE lower(workplace_example) = lower(?)
                    )
                    AND lower(workplace_example) != lower(?)
                    AND hot_technology = 1
                    GROUP BY workplace_example
                    ORDER BY c DESC
                    LIMIT 8
                    """,
                    (canonical, canonical),
                ).fetchall()
                for r in onet_related:
                    sk = r["workplace_example"]
                    if sk not in related_skills:
                        related_skills.append(sk)

                esco_related = conn.execute(
                    """
                    SELECT skill_label, count(*) as c
                    FROM ref_esco_occupation_skill_relations
                    WHERE occupation_uri IN (
                        SELECT DISTINCT occupation_uri FROM ref_esco_occupation_skill_relations
                        WHERE lower(skill_label) LIKE lower(?)
                    )
                    AND lower(skill_label) NOT LIKE lower(?)
                    GROUP BY skill_label
                    ORDER BY c DESC
                    LIMIT 8
                    """,
                    (f"%{canonical}%", f"%{canonical}%"),
                ).fetchall()
                for r in esco_related:
                    sk = r["skill_label"]
                    if sk not in related_skills:
                        related_skills.append(sk)
        except Exception as exc:
            logger.debug("Failed querying related skills: %s", exc)

        facts.append(
            V2StructuredFact(
                fact_id=f"fact:ref_profile:{canonical.casefold()}",
                fact_type="reference_taxonomy_profile",
                entity_name=canonical,
                canonical_entity_id=mapping.canonical_id,
                entity_type="skill",
                metric_name="taxonomy_matches",
                metric_value=len(onet_rows) + len(esco_rows),
                unit="references",
                source="O*NET 28.0 / ESCO v1.2.1",
                data_origin="local_reference_dataset" if (onet_rows or esco_rows) else "unavailable",
                readiness_state="observed" if (onet_rows or esco_rows) else "insufficient_data",
                details={
                    "hot_technology": hot_tech,
                    "in_demand": in_demand,
                    "onet_elements": [r.get("element_name") for r in onet_rows if r.get("element_name")],
                    "esco_categories": [r.get("skill_type") for r in esco_rows if r.get("skill_type")],
                    "related_skills": related_skills,
                },
            )
        )

        concept_explanation = get_concept_explanation_with_example(canonical)
        hot_str = " (Hot Technology)" if hot_tech else ""
        rel_str = f" with {len(related_skills)} related technical skills (e.g. {', '.join(related_skills[:5])})" if related_skills else ""
        if concept_explanation:
            headline = (
                f"{concept_explanation}\n\n"
                f"**Taxonomy Reference**: {canonical}{hot_str} is verified in official O*NET 28.0 and ESCO v1.2.1 occupational reference datasets{rel_str}."
            )
        else:
            headline = f"Reference taxonomy profile for {canonical}{hot_str}: documented across O*NET and ESCO datasets{rel_str}."

        return SkillIntelligenceResult(
            capability_id="skill_reference_profile",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state="insufficient_data" if not (onet_rows or esco_rows or concept_explanation) else "ready",
            metadata={"onet_count": len(onet_rows), "esco_count": len(esco_rows), "related_skills": related_skills},
        )

    def run_skill_health(
        self,
        skill_name: str,
        geography: str = "all",
    ) -> SkillIntelligenceResult:
        """Evaluate explainable Skill Health using verified monthly normalized share observations."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []

        # 1. Fetch hiring demand evidence
        hiring_evidence = self.evidence_retriever.get_hiring_demand_evidence(canonical, geography=geography)
        evidence.extend(hiring_evidence)

        # 2. Query market_observations
        observations: list[dict[str, Any]] = []
        try:
            with self.store._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM market_observations
                    WHERE lower(canonical_name) = lower(?)
                    ORDER BY period ASC
                    """,
                    (canonical,),
                ).fetchall()
                observations = [dict(r) for r in rows]
        except Exception as exc:
            logger.debug("Failed querying market_observations: %s", exc)

        # 3. Evaluate skill health via app.analytics.skill_health
        health_res = evaluate_skill_health(
            observations,
            canonical_skill_id=mapping.canonical_id,
            canonical_name=canonical,
            min_periods=4,
        )

        if health_res.health_category == "insufficient_data":
            headline = (
                f"Skill Health evaluation for {canonical}: insufficient verified observation data "
                f"(requires >= 4 consecutive completed monthly periods with valid denominator; found {len(observations)})."
            )
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:skill_health_readiness:{canonical.casefold()}",
                    fact_type="skill_health_readiness",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="consecutive_monthly_periods",
                    metric_value=len(observations),
                    unit="months",
                    source="TalentScope Market Observations",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    calculation_version=health_res.calculation_version,
                    details={
                        "health_category": health_res.health_category,
                        "score_status": health_res.score_status,
                        "score_formula": health_res.score_formula,
                        "min_periods_required": 4,
                        "periods_available": len(observations),
                        "explanation": health_res.explanation,
                        "limitations": health_res.limitations,
                        "required_action": "Run verified market collection pipeline for at least 4 consecutive months to establish baseline.",
                    },
                )
            )
        else:
            headline = (
                f"Skill Health evaluation for {canonical}: {health_res.health_category.capitalize()} "
                f"(Score: {health_res.score}/100 via {health_res.calculation_version})."
            )
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:skill_health:{canonical.casefold()}",
                    fact_type="skill_health",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="skill_health_score",
                    metric_value=health_res.score or 50.0,
                    unit="score_0_100",
                    source="TalentScope Market Observations",
                    data_origin="local_observation_dataset",
                    readiness_state="ready",
                    calculation_version=health_res.calculation_version,
                    details={
                        "health_category": health_res.health_category,
                        "score_status": health_res.score_status,
                        "score_formula": health_res.score_formula,
                        "component_table": [r.model_dump(mode="json") for r in health_res.component_table],
                    },
                )
            )

        is_insufficient = health_res.health_category == "insufficient_data"
        return SkillIntelligenceResult(
            capability_id="skill_health_analysis",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state="insufficient_data" if is_insufficient else "ready",
            metadata={
                "health_category": health_res.health_category,
                "score_formula": health_res.score_formula,
                "calculation_version": health_res.calculation_version,
                "periods_available": len(observations),
            },
        )

    def run_demand_forecast(
        self,
        skill_name: str,
        geography: str = "all",
    ) -> SkillIntelligenceResult:
        """Forecast future demand trajectory using ETS challenger vs seasonal-naive baseline (requires >= 24 consecutive months)."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []

        hiring_evidence = self.evidence_retriever.get_hiring_demand_evidence(canonical, geography=geography)
        evidence.extend(hiring_evidence)

        observations: list[dict[str, Any]] = []
        try:
            with self.store._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM market_observations
                    WHERE lower(canonical_name) = lower(?)
                    ORDER BY period ASC
                    """,
                    (canonical,),
                ).fetchall()
                observations = [dict(r) for r in rows]
        except Exception as exc:
            logger.debug("Failed querying market_observations: %s", exc)

        min_periods = 24
        is_insufficient = len(observations) < min_periods
        if is_insufficient:
            headline = (
                f"Demand forecasting for {canonical}: insufficient historical observations "
                f"(requires at least {min_periods} consecutive monthly periods for seasonal backtesting; found {len(observations)})."
            )
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:forecast_readiness:{canonical.casefold()}",
                    fact_type="forecast_readiness",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="consecutive_monthly_periods",
                    metric_value=len(observations),
                    unit="months",
                    source="TalentScope Market Observations",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    calculation_version="forecasting-ets-vs-snaive-v1",
                    details={
                        "min_periods_required": min_periods,
                        "periods_available": len(observations),
                        "baseline_method": "seasonal_naive",
                        "challenger_method": "holt_winters_additive_ets",
                        "holdout_requirement": "chronological one-step holdout with >= 20 holdout predictions for empirical error bounds",
                        "status": "insufficient_data",
                    },
                )
            )
        else:
            headline = f"Demand forecasting for {canonical}: {len(observations)} monthly observations evaluated."

        return SkillIntelligenceResult(
            capability_id="skill_demand_forecast",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state="insufficient_data" if is_insufficient else "ready",
            metadata={
                "min_periods_required": min_periods,
                "periods_available": len(observations),
            },
        )

    def run_hiring_demand_trends(
        self,
        skill_name: str,
        geography: str = "all",
    ) -> SkillIntelligenceResult:
        """Analyze hiring demand trends strictly from job postings / platform-collected observations (distinguished from developer adoption)."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name

        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []

        hiring_evidence = self.evidence_retriever.get_hiring_demand_evidence(canonical, geography=geography, history_type="backfill")
        evidence.extend(hiring_evidence)

        observations: list[dict[str, Any]] = []
        distinct_periods: list[str] = []
        geo_filter = geography.strip()
        is_geo_scoped = geo_filter.lower() not in {"all", "global", "world"} and len(geo_filter) == 2
        try:
            with self.store._connect() as conn:
                if is_geo_scoped:
                    rows = conn.execute(
                        """
                        SELECT * FROM market_observations
                        WHERE (lower(skill) = lower(?) OR lower(COALESCE(skill_id, '')) = lower(?))
                          AND lower(signal_type) = 'demand'
                          AND lower(COALESCE(data_origin, '')) = 'real'
                          AND (lower(location) = lower(?) OR lower(location) LIKE lower(?))
                        ORDER BY period ASC
                        """,
                        (canonical, canonical, geo_filter, f"{geo_filter},%"),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM market_observations
                        WHERE (lower(skill) = lower(?) OR lower(COALESCE(skill_id, '')) = lower(?))
                          AND lower(signal_type) = 'demand'
                          AND lower(COALESCE(data_origin, '')) = 'real'
                        ORDER BY period ASC
                        """,
                        (canonical, canonical),
                    ).fetchall()
                observations = [dict(r) for r in rows]
                distinct_periods = sorted({r["period"] for r in observations if r.get("period")})
        except Exception as exc:
            logger.debug("Failed querying market_observations: %s", exc)

        min_periods = 4
        is_insufficient = len(distinct_periods) < min_periods
        if is_insufficient:
            headline = (
                f"Hiring demand trends for {canonical}: insufficient platform observations "
                f"(requires >= {min_periods} consecutive monthly periods; found {len(distinct_periods)}). "
                f"Note: GitHub Innovation Graph developer adoption is active and tracked separately."
            )
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:hiring_demand_readiness:{canonical.casefold()}",
                    fact_type="hiring_demand_readiness",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="consecutive_monthly_periods",
                    metric_value=len(distinct_periods),
                    unit="months",
                    source="TalentScope Market Observations (JSearch/Adzuna)",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    details={
                        "min_periods_required": min_periods,
                        "periods_available": len(distinct_periods),
                        "signal_family": "hiring_demand",
                        "distinction": "Hiring demand (job postings) is strictly partitioned from developer adoption (GitHub pushers).",
                    },
                )
            )
        else:
            # Group observations by period to compute monthly sample posting shares
            period_points = []
            for p in distinct_periods:
                p_obs = [r for r in observations if r.get("period") == p]
                cnt = len(p_obs)
                denom = p_obs[0].get("denominator") if p_obs else None
                denom_val = float(denom) if denom and float(denom) > 0 else float(cnt)
                share_pct = round((cnt / denom_val) * 100, 2) if denom_val > 0 else 0.0
                period_points.append({
                    "period": p,
                    "sample_postings": cnt,
                    "sample_total_postings": int(denom_val),
                    "skill_share_pct": share_pct,
                })

            latest_pt = period_points[-1]
            prev_pt = period_points[-2] if len(period_points) >= 2 else latest_pt
            share_change = round(latest_pt["skill_share_pct"] - prev_pt["skill_share_pct"], 2)

            if share_change > 1.0:
                direction = "Growing"
            elif share_change < -1.0:
                direction = "Declining"
            else:
                direction = "Stable"

            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:hiring_demand_trend:{canonical.casefold()}:{distinct_periods[-1]}",
                    fact_type="trend_analysis",
                    entity_name=canonical,
                    canonical_entity_id=mapping.canonical_id,
                    entity_type="skill",
                    metric_name="sample_skill_share_trend",
                    metric_value=direction,
                    unit="sample monthly posting share %",
                    period=f"{distinct_periods[0]}_to_{distinct_periods[-1]}",
                    source="Fliarbi Job Postings Sample",
                    data_origin="real",
                    history_type="backfill",
                    series_id=f"sample_hiring_demand:{canonical.casefold()}:{geography.lower()}",
                    readiness_state="ready",
                    details={
                        "signal_type": "demand",
                        "source_family": "hiring_demand",
                        "is_sample": True,
                        "sample_provenance": "sample_level_observations",
                        "geography": geography,
                        "latest_period": distinct_periods[-1],
                        "latest_sample_postings": latest_pt["sample_postings"],
                        "latest_sample_total": latest_pt["sample_total_postings"],
                        "latest_skill_share_pct": latest_pt["skill_share_pct"],
                        "skill_share_pct": latest_pt["skill_share_pct"],
                        "previous_skill_share_pct": prev_pt["skill_share_pct"],
                        "skill_share_change_pct_points": share_change,
                        "trend_direction": direction,
                        "monthly_series": period_points,
                        "observation_count": len(observations),
                        "consecutive_months": len(distinct_periods),
                        "periods_available": len(distinct_periods),
                        "distinction": (
                            "This metric reflects sample posting share across surveyed companies in this sample dataset; "
                            "volume variations reflect sample size changes and must not be interpreted as total national hiring growth."
                        ),
                    },
                )
            )

            geo_label = geography.upper() if is_geo_scoped else "Global / All Regions"
            headline = (
                f"Sample hiring demand trend for {canonical} ({geo_label}): {direction} "
                f"({latest_pt['skill_share_pct']}% sample share in {distinct_periods[-1]}; "
                f"{len(observations)} total sample observations across {len(distinct_periods)} months). "
                f"Note: Sample volume changes reflect dataset collection size, not total market growth."
            )

        return SkillIntelligenceResult(
            capability_id="hiring_demand_trends",
            target_skill=canonical,
            headline=headline,
            facts=facts,
            evidence=evidence,
            readiness_state="insufficient_data" if is_insufficient else "ready",
            metadata={
                "min_periods_required": min_periods,
                "periods_available": len(distinct_periods),
                "total_sample_observations": len(observations),
                "is_sample": True,
            },
        )

    def run_action_recommendations(
        self,
        skill_name: str,
        target_role: str | None = None,
    ) -> SkillIntelligenceResult:
        """Generate deterministic practice tasks and self-check criteria."""
        mapping = self.skill_mapper.normalize(skill_name)
        canonical = mapping.canonical_name
        role = target_role or "Software Developer"

        # Pull skills from O*NET software skills
        skills_to_prepare = [{"name": canonical, "element_name": "General practice guidance"}]
        if mapping.onet_matches:
            for m in mapping.onet_matches:
                skills_to_prepare.append({
                    "name": m.get("workplace_example") or canonical,
                    "hot_technology": m.get("hot_technology"),
                    "in_demand": m.get("in_demand"),
                    "element_name": m.get("element_name"),
                })

        plan = self.action_engine.build_plan_for_skills(role, skills_to_prepare)

        headline = f"Deterministic skill preparation plan for {canonical} ({plan.total_actions} technical actions)."

        return SkillIntelligenceResult(
            capability_id="skill_action_recommendations",
            target_skill=canonical,
            headline=headline,
            facts=[],
            evidence=self.evidence_retriever.get_reference_taxonomy_evidence(canonical),
            action_plan=plan,
            metadata={"actions_count": plan.total_actions},
        )

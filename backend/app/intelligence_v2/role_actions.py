"""Greenfield Intelligence Engine V2 — Deterministic Role Actions Engine.

Generates structured role-preparation actions, practice tasks, and self-checks
based strictly on verified taxonomy requirements without invented course catalogs.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.intelligence_v2.occupation_names import (
    normalize_occupation_name,
    occupation_label_matches,
)


ActionPriority = Literal["high", "medium", "foundation"]


# Canonical technical skill categorization layers for sensible sequencing
_LAYER_KEYWORDS: dict[int, set[str]] = {
    1: {  # Core programming languages & foundational data
        "python", "java", "c++", "c#", "c", "go", "golang", "rust", "javascript", "typescript",
        "ruby", "php", "swift", "kotlin", "scala", "r", "shell", "bash", "powershell",
        "sql", "postgresql", "mysql", "sqlite", "oracle", "nosql",
    },
    2: {  # Application frameworks, libraries & data tools
        "react", "angular", "vue", "node.js", "nodejs", "express", "django", "fastapi", "flask",
        "spring", "spring boot", "asp.net", ".net", "next.js", "graphql", "rest", "api",
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop",
        "kafka", "rabbitmq", "redis", "elasticsearch",
    },
    3: {  # Infrastructure, containers, cloud & operations
        "docker", "kubernetes", "k8s", "helm", "terraform", "ansible", "cloudformation",
        "aws", "amazon web services", "azure", "google cloud platform", "gcp",
        "ci/cd", "jenkins", "github actions", "gitlab ci", "linux", "unix",
    },
    4: {  # System design, architecture, observability & security
        "system design", "microservices", "distributed systems", "software architecture",
        "cybersecurity", "oauth", "jwt", "owasp", "penetration testing",
        "prometheus", "grafana", "opentelemetry", "datadog", "elk stack",
    },
}

_DEFAULT_PREREQUISITES: dict[str, list[str]] = {
    "react": ["JavaScript (ES6+) Fundamentals", "HTML5 & CSS3"],
    "angular": ["TypeScript Fundamentals", "JavaScript"],
    "vue": ["JavaScript Fundamentals", "HTML5"],
    "django": ["Python Language Fundamentals", "Relational Databases / SQL"],
    "fastapi": ["Python Type Annotations & AsyncIO", "HTTP / REST Concepts"],
    "flask": ["Python Language Fundamentals", "HTTP Basics"],
    "spring": ["Java Object-Oriented Fundamentals", "SQL Basics"],
    "docker": ["Linux Shell Basics", "Application Packaging"],
    "kubernetes": ["Docker / Container Fundamentals", "Networking Concepts"],
    "terraform": ["Cloud Provider Concepts (AWS/Azure/GCP)", "Infrastructure Basics"],
    "pandas": ["Python Fundamentals", "Basic Data Analysis"],
    "tensorflow": ["Python Programming", "Linear Algebra & Statistics"],
    "pytorch": ["Python Programming", "Deep Learning Fundamentals"],
}


class PreparationAction(BaseModel):
    """Deterministic skill acquisition or role preparation step."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str
    priority: ActionPriority
    reason: str
    practice_task: str
    self_check_criteria: list[str] = Field(default_factory=list)
    action_title: str | None = None
    order: int = 1
    why_matters: str | None = None
    concrete_next_step: str | None = None
    suggested_task: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    evidence_reference: str | None = None
    requirement_type: str = "validated_taxonomy_requirement"
    milestone: str | None = None

    @model_validator(mode="after")
    def _populate_derived_fields(self) -> "PreparationAction":
        if self.action_title is None:
            self.action_title = f"Phase {self.order}: Master {self.skill_name} Implementation"
        if self.why_matters is None:
            self.why_matters = self.reason
        if self.suggested_task is None:
            self.suggested_task = self.practice_task
        if self.concrete_next_step is None:
            self.concrete_next_step = (
                f"Set up an isolated workspace for {self.skill_name}, configure required dependencies, "
                "and implement a baseline proof-of-concept module."
            )
        return self


class RolePreparationPlan(BaseModel):
    """Complete role transition and skill preparation plan."""

    model_config = ConfigDict(extra="forbid")

    target_role: str
    total_actions: int
    actions: list[PreparationAction] = Field(default_factory=list)
    soc_code: str | None = None
    resolved_role_name: str | None = None
    role_resolved: bool = True
    user_matched_skills: list[str] = Field(default_factory=list)
    gap_skills_addressed: list[str] = Field(default_factory=list)
    is_provisional: bool = False
    provisional_reason: str | None = None
    timeline_summary: str | None = None
    limitations_notice: str = (
        "TalentScope does not curate commercial course catalogs or sponsored certifications. "
        "All recommended actions are grounded in verified taxonomy competencies (O*NET/ESCO) "
        "and direct software engineering tasks."
    )


def _classify_skill_layer(skill_name: str, element_name: str | None = None) -> int:
    name_clean = skill_name.strip().casefold()
    for layer, kws in _LAYER_KEYWORDS.items():
        if name_clean in kws or any(re.search(rf"\b{re.escape(kw)}\b", name_clean) for kw in kws):
            return layer
    elem = (element_name or "").casefold()
    if "programming" in elem or "language" in elem or "data base" in elem:
        return 1
    if "framework" in elem or "library" in elem or "development" in elem:
        return 2
    if "cloud" in elem or "container" in elem or "platform" in elem or "system" in elem:
        return 3
    return 2


def _get_skill_prerequisites(skill_name: str, earlier_skills: list[str]) -> list[str]:
    name_clean = skill_name.strip().casefold()
    if name_clean in _DEFAULT_PREREQUISITES:
        return _DEFAULT_PREREQUISITES[name_clean]
    for key, prereqs in _DEFAULT_PREREQUISITES.items():
        if key in name_clean:
            return prereqs
    if earlier_skills:
        return [earlier_skills[0]]
    return []


def _format_milestone(order: int, total: int, timeline: str | None) -> str:
    tl = (timeline or "").strip().casefold()
    if tl in {"30d", "30 days", "1m", "1 month"}:
        return f"Week {order}"
    if tl in {"3m", "90d", "90 days", "3 months", "quarter"}:
        weeks_per = 12 // max(1, total)
        start_w = (order - 1) * weeks_per + 1
        end_w = order * weeks_per
        return f"Weeks {start_w}-{end_w}"
    if tl in {"6m", "180d", "180 days", "6 months"}:
        return f"Month {order}"
    return f"Phase {order}"


class V2RoleActionEngine:
    """Deterministic generator for skill preparation actions."""

    def build_plan_for_skills(
        self,
        target_role: str,
        target_skills: list[dict[str, Any]],
    ) -> RolePreparationPlan:
        """Backwards-compatible builder for raw skill dictionaries."""
        actions: list[PreparationAction] = []
        for idx, item in enumerate(target_skills[:5], start=1):
            skill_name = item.get("name") or item.get("workplace_example") or "Core Skill"
            hot = bool(item.get("hot_technology"))
            in_demand = bool(item.get("in_demand"))
            elem = item.get("element_name") or "Technical Competency"

            if hot or in_demand:
                priority: ActionPriority = "high"
                reason = f"Identified as Hot Technology / In-Demand in O*NET ({elem})."
            elif "essential" in str(item.get("relation_type", "")).lower():
                priority = "high"
                reason = "Designated as an Essential Competency in ESCO occupation taxonomy."
            else:
                priority = "medium"
                reason = f"Required competency under {elem} taxonomy classification."

            practice_task = (
                f"Design, implement, and document a production-grade component or service utilizing "
                f"'{skill_name}'. Focus on architectural patterns, error handling, and end-to-end testing."
            )
            self_checks = [
                f"Implement automated unit and integration tests verifying '{skill_name}' integration.",
                "Conduct code review against official documentation and community style guides.",
                "Benchmark latency, memory consumption, or throughput under simulated workload.",
            ]
            actions.append(
                PreparationAction(
                    order=idx,
                    action_title=f"Phase {idx}: Build Core Competency in {skill_name}",
                    skill_name=skill_name,
                    priority=priority,
                    reason=reason,
                    why_matters=reason,
                    practice_task=practice_task,
                    suggested_task=practice_task,
                    concrete_next_step=f"Initialize a sandbox project to explore {skill_name} core APIs and paradigms.",
                    self_check_criteria=self_checks,
                    prerequisites=[],
                    evidence_reference="O*NET 28.0",
                )
            )

        return RolePreparationPlan(
            target_role=target_role,
            total_actions=len(actions),
            actions=actions,
        )

    def build_role_preparation_plan(
        self,
        target_role: str,
        store: Any | None = None,
        user_skills: list[str] | None = None,
        desired_timeline: str | None = None,
        gap_skills: list[str] | None = None,
    ) -> RolePreparationPlan:
        """Build structured, prioritized role preparation plan grounded in reference taxonomies.

        Inputs:
        - target_role: Target occupation name.
        - store: ReferenceDataStore containing O*NET / ESCO tables.
        - user_skills: Optional user-supplied or profile-declared skills.
        - desired_timeline: Optional desired preparation timeframe (e.g. '30d', '3m', '6m').
        - gap_skills: Optional explicit gap skills if precomputed by alignment engine.
        """
        role_clean = " ".join(target_role.split())
        normalized_role = normalize_occupation_name(role_clean)
        soc_code: str | None = None
        resolved_role_name: str | None = None
        role_resolved = False
        role_requirements: list[dict[str, Any]] = []

        # 1. Resolve target role against reference taxonomies
        if store is not None:
            try:
                with store._connect() as conn:
                    # Check O*NET occupations first
                    occ_candidates = conn.execute(
                        "SELECT soc_code, title FROM ref_onet_occupations WHERE lower(title) LIKE lower(?)",
                        (f"%{normalized_role}%",),
                    ).fetchall()
                    occ = next(
                        (
                            candidate for candidate in occ_candidates
                            if occupation_label_matches(normalized_role, candidate["title"])
                        ),
                        None,
                    )

                    if occ:
                        soc_code = occ["soc_code"]
                        resolved_role_name = occ["title"]
                        role_resolved = True
                        rows = conn.execute(
                            """
                            SELECT workplace_example, hot_technology, in_demand, element_name
                            FROM ref_onet_software_skills
                            WHERE soc_code = ?
                            ORDER BY hot_technology DESC, in_demand DESC
                            LIMIT 30
                            """,
                            (soc_code,),
                        ).fetchall()
                        role_requirements = [
                            {
                                "name": r["workplace_example"],
                                "hot_technology": r["hot_technology"],
                                "in_demand": r["in_demand"],
                                "element_name": r["element_name"],
                                "taxonomy_source": "O*NET 28.0",
                                "soc_code": soc_code,
                            }
                            for r in rows
                        ]

                    # If not in O*NET, try ESCO
                    if not role_resolved:
                        esco_candidates = conn.execute(
                            """
                            SELECT concept_uri, preferred_label, alt_labels
                            FROM ref_esco_occupations
                            WHERE lower(preferred_label) LIKE lower(?)
                               OR lower(alt_labels) LIKE lower(?)
                            ORDER BY CASE WHEN lower(preferred_label) = lower(?) THEN 0 ELSE 1 END,
                                     length(preferred_label) ASC
                            """,
                            (f"%{normalized_role}%", f"%{normalized_role}%", normalized_role),
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
                            role_resolved = True
                            soc_code = esco_occ["concept_uri"]
                            resolved_role_name = esco_occ["preferred_label"]
                            rows = conn.execute(
                                """
                                SELECT s.preferred_label, r.relation_type, s.skill_type
                                FROM ref_esco_occupation_skill_relations r
                                JOIN ref_esco_skills s ON r.skill_uri = s.concept_uri
                                WHERE r.occupation_uri = ?
                                ORDER BY CASE WHEN r.relation_type = 'essential' THEN 1 ELSE 2 END
                                LIMIT 30
                                """,
                                (esco_occ["concept_uri"],),
                            ).fetchall()
                            role_requirements = [
                                {
                                    "name": r["preferred_label"],
                                    "hot_technology": (r["relation_type"] == "essential"),
                                    "in_demand": False,
                                    "element_name": r["skill_type"] or "Competency",
                                    "relation_type": r["relation_type"],
                                    "taxonomy_source": "ESCO v1.2.1",
                                    "soc_code": esco_occ["concept_uri"],
                                }
                                for r in rows
                            ]
            except Exception:
                role_resolved = False

        # 2. Determine skills to prepare: gap skills vs matched skills
        norm_user_skills = {
            s.strip().casefold(): s.strip()
            for s in (user_skills or [])
            if s and s.strip()
        }

        user_matched: list[str] = []
        target_skills: list[dict[str, Any]] = []
        is_provisional = False
        provisional_reason: str | None = None

        if gap_skills:
            # Explicit gap skills passed directly
            target_skills = [
                {
                    "name": s,
                    "hot_technology": True,
                    "in_demand": True,
                    "element_name": "Target Skill Gap",
                    "taxonomy_source": "Platform Skill Alignment",
                }
                for s in gap_skills[:5]
            ]
        elif role_resolved and role_requirements:
            if norm_user_skills:
                # User supplied skills: separate matched from gap
                gap_items: list[dict[str, Any]] = []
                for item in role_requirements:
                    item_key = item["name"].strip().casefold()
                    if item_key in norm_user_skills or any(k in item_key or item_key in k for k in norm_user_skills):
                        user_matched.append(item["name"])
                    else:
                        gap_items.append(item)

                if gap_items:
                    target_skills = gap_items[:5]
                else:
                    # User matched all top requirements: provide advanced mastery tasks
                    target_skills = role_requirements[:5]
                    provisional_reason = (
                        f"All primary baseline requirements for {role_clean} are declared in your profile. "
                        "The plan below targets advanced production specialization and system integration."
                    )
            else:
                # No user profile skills supplied: baseline entry plan
                target_skills = role_requirements[:5]
                is_provisional = True
                provisional_reason = (
                    f"No profile skills were supplied. This plan outlines baseline entry preparation for {role_clean} "
                    "derived from verified O*NET/ESCO requirements. Select or provide your skills for personalized gap targeting."
                )
        else:
            # Role could not be resolved in O*NET or ESCO
            is_provisional = True
            if norm_user_skills:
                target_skills = [
                    {
                        "name": s,
                        "hot_technology": False,
                        "in_demand": False,
                        "element_name": "User-Supplied Skill Target",
                        "taxonomy_source": "User Context",
                    }
                    for s in list(norm_user_skills.values())[:5]
                ]
                provisional_reason = (
                    f"Target role '{role_clean}' could not be resolved in local reference taxonomies (O*NET 2018 SOC or ESCO). "
                    "A provisional practice roadmap has been constructed using your declared skills."
                )
            else:
                provisional_reason = (
                    f"Target role '{role_clean}' could not be resolved in local O*NET or ESCO taxonomies, "
                    "and no current skills were provided. A target role or profile skills are required to generate an actionable plan."
                )

        if not target_skills:
            return RolePreparationPlan(
                target_role=role_clean,
                total_actions=0,
                actions=[],
                soc_code=soc_code,
                resolved_role_name=resolved_role_name,
                role_resolved=role_resolved,
                user_matched_skills=user_matched,
                gap_skills_addressed=[],
                is_provisional=True,
                provisional_reason=provisional_reason,
            )

        # 3. Order actions by dependency layers (Foundation -> Frameworks -> Tools -> Systems)
        classified: list[tuple[int, dict[str, Any]]] = [
            (_classify_skill_layer(item["name"], item.get("element_name")), item)
            for item in target_skills
        ]
        # Sort by layer ascending, then hot_tech descending, then name
        classified.sort(key=lambda t: (t[0], 0 if t[1].get("hot_technology") else 1, t[1]["name"].casefold()))

        actions: list[PreparationAction] = []
        earlier_skills: list[str] = []
        total_items = min(5, len(classified))

        for idx, (layer, item) in enumerate(classified[:total_items], start=1):
            s_name = item["name"]
            hot = bool(item.get("hot_technology"))
            in_demand = bool(item.get("in_demand"))
            elem = item.get("element_name") or "Technical Competency"
            source_label = item.get("taxonomy_source") or "O*NET 28.0"

            if item.get("relation_type") == "essential":
                priority: ActionPriority = "high"
                why = f"Listed as an essential occupation skill for {role_clean} ({elem})."
            elif item.get("relation_type") == "optional":
                priority = "medium"
                why = f"Listed as an optional occupation skill for {role_clean} ({elem})."
            elif hot or in_demand:
                priority: ActionPriority = "high"
                why = f"Designated as a Hot Technology and in-demand requirement for {role_clean} ({elem})."
            elif layer == 1:
                priority = "foundation"
                why = f"Core foundational competency required for downstream {role_clean} toolchains."
            else:
                priority = "medium"
                why = f"Required technical competency under {elem} taxonomy classification."

            # Construct targeted engineering tasks
            if layer == 1:
                task = (
                    f"Implement an idiomatic component in '{s_name}' incorporating structured error handling, "
                    "data validation, and unit test suites verifying edge cases."
                )
                next_step = f"Configure the local toolchain for '{s_name}', review official style guides, and build a core library."
                self_checks = [
                    f"Write comprehensive automated tests for '{s_name}' implementation with >85% branch coverage.",
                    "Pass linting and static analysis without warnings under industry standard configurations.",
                    "Verify memory safety, resource lifecycle management, or concurrency semantics.",
                ]
            elif layer == 2:
                task = (
                    f"Build an end-to-end service or interactive module using '{s_name}'. Integrate API endpoints, "
                    "state management, and comprehensive integration testing."
                )
                next_step = f"Scaffold a micro-application using '{s_name}' with documented API contracts."
                self_checks = [
                    f"Execute integration test suites verifying data flows through '{s_name}'.",
                    "Benchmark service response latency under simulated load conditions.",
                    "Document interface signatures and error contracts in conformance with OpenAPI or interface specifications.",
                ]
            elif layer == 3:
                task = (
                    f"Containerize and automate deployment workflows using '{s_name}'. Configure health checks, "
                    "automated CI/CD pipelines, and environment isolation."
                )
                next_step = f"Create reproducible configuration scripts (e.g. Dockerfile / manifest) utilizing '{s_name}'."
                self_checks = [
                    f"Validate automated build, test, and container packaging using '{s_name}'.",
                    "Demonstrate automated rollbacks or zero-downtime redeployments.",
                    "Audit configuration security against standard hardening benchmarks.",
                ]
            else:
                task = (
                    f"Design and benchmark a distributed or resilient architectural workflow utilizing '{s_name}'. "
                    "Focus on observability, fault tolerance, and security."
                )
                next_step = f"Produce an architectural design document and telemetry prototype for '{s_name}'."
                self_checks = [
                    f"Simulate subsystem degradation and observe graceful recovery via '{s_name}'.",
                    "Conduct security audit verifying least-privilege access and data sanitization.",
                    "Verify telemetry metrics, distributed traces, and log aggregation.",
                ]

            prereqs = _get_skill_prerequisites(s_name, earlier_skills)
            milestone_str = _format_milestone(idx, total_items, desired_timeline)

            actions.append(
                PreparationAction(
                    order=idx,
                    action_title=f"{milestone_str}: Master {s_name} Implementation",
                    skill_name=s_name,
                    priority=priority,
                    reason=why,
                    why_matters=why,
                    practice_task=task,
                    suggested_task=task,
                    concrete_next_step=next_step,
                    self_check_criteria=self_checks,
                    prerequisites=prereqs,
                    evidence_reference=f"{source_label} ({soc_code or 'General'})",
                    requirement_type="validated_taxonomy_requirement" if role_resolved else "provisional_suggestion",
                    milestone=milestone_str,
                )
            )
            earlier_skills.append(s_name)

        tl_summary = None
        if desired_timeline:
            tl_summary = f"Structured over {desired_timeline} in {len(actions)} sequential phases."

        return RolePreparationPlan(
            target_role=role_clean,
            total_actions=len(actions),
            actions=actions,
            soc_code=soc_code,
            resolved_role_name=resolved_role_name,
            role_resolved=role_resolved,
            user_matched_skills=user_matched,
            gap_skills_addressed=[a.skill_name for a in actions],
            is_provisional=is_provisional,
            provisional_reason=provisional_reason,
            timeline_summary=tl_summary,
        )

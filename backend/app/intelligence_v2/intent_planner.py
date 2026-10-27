"""Greenfield Intelligence Engine V2 — Intent Planner.

Parses natural language requests and contextual state to determine
the intended capability, target entities, and execution parameters.
"""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_v2.capability_registry import CAPABILITIES, CapabilityDefinition
from app.intelligence_v2.occupation_names import normalize_occupation_name
from app.intelligence_v2.skill_mapping import V2SkillMapper
from app.models.execution_orchestrator import SelectedEntityResolution


class PlannedIntent(BaseModel):
    """The resolved capability execution plan for a user query."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str | None
    target_skill: str | None = None
    target_role: str | None = None
    geography: str | None = None
    portal_type: str = "individual"
    confidence: float = 1.0
    reason: str
    entities: list[SelectedEntityResolution] = Field(default_factory=list)


ROLE_KEYWORDS = {
    "software engineer", "developer", "data scientist", "data engineer",
    "cloud architect", "backend engineer", "frontend developer",
    "full stack engineer", "devops engineer", "product manager",
    "analyst", "administrator", "specialist",
}

ROLE_DESCRIPTION_QUERY = re.compile(
    r"^\s*(?:"
    r"what\s+does\s+(?:(?:a|an|the)\s+)?[\w/-]+(?:\s+[\w/-]+){0,3}\s+"
    r"(?:developer|engineer|analyst|scientist|architect|manager|designer|administrator|specialist)s?\s+do"
    r"|(?:the\s+)?role\s+of\s+(?:(?:a|an|the)\s+)?[\w/-]+(?:\s+[\w/-]+){0,3}\s+"
    r"(?:developer|engineer|analyst|scientist|architect|manager|designer|administrator|specialist)s?"
    r"|responsibilities\s+of\s+(?:(?:a|an|the)\s+)?[\w/-]+(?:\s+[\w/-]+){0,3}\s+"
    r"(?:developer|engineer|analyst|scientist|architect|manager|designer|administrator|specialist)s?"
    r"|what\s+is\s+(?:a|an)\s+[\w/-]+(?:\s+[\w/-]+){0,3}\s+"
    r"(?:developer|engineer|analyst|scientist|architect|manager|designer|administrator|specialist)s?"
    r")\s*[?.!]*$",
    re.IGNORECASE,
)


class V2IntentPlanner:
    """Plans capability invocation and resolves entity arguments."""

    def __init__(self, skill_mapper: V2SkillMapper | None = None) -> None:
        self.skill_mapper = skill_mapper or V2SkillMapper()

    def plan(
        self,
        query: str,
        portal_type: str = "individual",
        context: dict[str, Any] | None = None,
    ) -> PlannedIntent:
        """Route a natural-language request to a supported capability."""
        ctx = context or {}
        q = query.strip().casefold()
        entities: list[SelectedEntityResolution] = []

        # 1. Resolve geography if mentioned
        geography = "global"
        if "india" in q:
            geography = "IN"
        elif "united states" in q or "usa" in q or "us" in q.split():
            geography = "US"

        # 2. Extract potential skill or role entities
        target_skill: str | None = ctx.get("selected_skill")
        target_role: str | None = ctx.get("selected_role")

        role_patterns = (
            r"\bwhat\s+does\s+(?:a|an|the)\s+([\w+#./-]+(?:\s+[\w+#./-]+){0,3})\s+do\b",
            r"\bwhat\s+skills?\s+does\s+(?:a|an|the)\s+([\w+#./-]+(?:\s+[\w+#./-]+){0,3})\s+(?:need|use|required?)\b",
            r"\b(?:preparation\s+plan|plan|prepare|roadmap|learning\s+path)\s+for\s+(?:a|an|the)\s+([\w+#./-]+(?:\s+[\w+#./-]+){0,3})",
            r"\b(?:preparation\s+plan|plan|prepare|roadmap|learning\s+path)\s+for\s+([\w+#./-]+(?:\s+[\w+#./-]+){0,3})",
        )
        if not target_role:
            for pattern in role_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    target_role = " ".join(match.group(1).split())
                    break

        if target_skill:
            mapping = self.skill_mapper.normalize(target_skill)
            entities.append(
                SelectedEntityResolution(
                    entity_id=mapping.canonical_id or f"skill:{mapping.canonical_name.casefold()}",
                    entity_type="skill",
                    canonical_name=mapping.canonical_name,
                    resolution_status="resolved" if mapping.status == "matched" else "ambiguous",
                )
            )

        # Detect role mentions
        search_roles = [
            ("python developer", "Python Developer"),
            ("backend developer", "Backend Developer"),
            ("frontend developer", "Frontend Developer"),
            ("web developer", "Web Developer"),
            ("software engineer", "Software Engineer"),
            ("software developers", "Software Developers"),
            ("data analyst", "Data Analyst"),
            ("data scientist", "Data Scientist"),
            ("data engineer", "Data Engineer"),
            ("cloud architect", "Cloud Architect"),
            ("devops engineer", "DevOps Engineer"),
            ("developer", "Developer"),
        ]
        for role_phrase, canonical_occ in search_roles:
            if role_phrase in q:
                if not target_role:
                    target_role = canonical_occ
                entities.append(
                    SelectedEntityResolution(
                        entity_id=f"role:{role_phrase.replace(' ', '_')}",
                        entity_type="occupation",
                        canonical_name=target_role,
                        resolution_status="resolved",
                    )
                )
                break

        # If role mention didn't match specific phrase but general role keywords exist
        if not target_role:
            for role_kw in ROLE_KEYWORDS:
                if role_kw in q:
                    target_role = normalize_occupation_name(role_kw)
                    entities.append(
                        SelectedEntityResolution(
                            entity_id=f"role:{role_kw.replace(' ', '_')}",
                            entity_type="occupation",
                            canonical_name=target_role,
                            resolution_status="resolved",
                        )
                    )
                    break

        # Detect skill mentions using canonical registry if not already selected
        if not target_skill:
            words = re.findall(r"[A-Za-z0-9#+.]+", query)
            common_stopwords = {
                "the", "a", "an", "is", "for", "in", "and", "or", "to", "of", "my", "me", "what",
                "which", "available", "demand", "trend", "trends", "action", "actions", "prepare",
                "preparation", "learn", "how", "should", "i", "take", "role", "roles", "job", "jobs",
                "posting", "postings", "pathway", "pathways", "market", "overview", "snapshot",
                "status", "fit", "match", "align", "alignment", "score", "give", "show", "tell",
                "need", "can", "become", "relevant", "mentioned", "description", "target", "next",
                "historical", "signals", "signal", "similar", "related", "healthy", "health", "forecast", "predict",
                "explain", "overview", "definition", "current",
            }
            for raw_w in words:
                w = raw_w.strip(".!?,:;")
                if not w or w.casefold() in common_stopwords:
                    continue
                entry = self.skill_mapper.normalize(w, context=query)
                # Only accept matched registry skills or unambiguous matches
                if entry.status in {"matched", "partial"} and entry.canonical_id and not entry.canonical_id.startswith("ref:"):
                    if not target_skill:
                        target_skill = entry.canonical_name
                    status_val = "resolved" if entry.status == "matched" else "ambiguous"
                    if not any(e.entity_id == entry.canonical_id for e in entities):
                        entities.append(
                            SelectedEntityResolution(
                                entity_id=entry.canonical_id,
                                entity_type="skill",
                                canonical_name=entry.canonical_name,
                                resolution_status=status_val,
                            )
                        )
                    if len(entities) >= 3:
                        break

            # If no registry skill was detected, check if query asks to explain or define a specific technology
            if not target_skill and not target_role:
                concept_m = re.search(r"\b(?:explain|tell me about|definition of)\s+([A-Za-z0-9#+.\s\-]+?)(?:\.|\?|$)", query, re.I)
                if concept_m:
                    extracted_concept = concept_m.group(1).strip()
                    if extracted_concept and extracted_concept.casefold() not in common_stopwords:
                        target_skill = extracted_concept

        # 3. Intent routing rules
        # Historical skill signals
        if any(k in q for k in ["historical skill signals", "historical signals", "show my historical", "history"]):
            return PlannedIntent(
                capability_id="skill_historical_signals",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests historical developer adoption series.",
                entities=entities,
            )

        if ROLE_DESCRIPTION_QUERY.fullmatch(query):
            return PlannedIntent(
                capability_id="skill_lookup",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query asks for reference information about an occupation.",
                entities=entities,
            )

        if re.search(
            r"\bwhat\s+skills?\s+(?:does|do)\s+(?:(?:a|an|the)\s+)?[\w/-]+(?:\s+[\w/-]+){0,3}\s+"
            r"(?:developer|engineer|analyst|scientist|architect|manager|designer|administrator|specialist)s?\s+"
            r"(?:need|use|required?)\b",
            q,
        ):
            return PlannedIntent(
                capability_id="job_role_requirements",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query asks for occupation skill requirements from reference data.",
                entities=entities,
            )

        # Taxonomy lookup (canonical ID, exact/partial search, disambiguation)
        if any(k in q for k in ["lookup", "look up", "canonical id", "soc code", "esco uri", "definition of", "find skill", "search skill", "find occupation", "search occupation"]):
            return PlannedIntent(
                capability_id="skill_lookup",
                target_skill=target_skill or (target_role if not target_skill else "Python"),
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests taxonomy lookup by canonical ID or entity name.",
                entities=entities,
            )

        # Related skills with explicit relationship types & PPMI/IOF ranking
        if any(k in q for k in ["related skills", "related to", "skills related", "skill adjacency", "co-occurring", "adjacent skills", "associated skills"]):
            return PlannedIntent(
                capability_id="related_skills",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests explainable related skills classified by relationship type and PPMI/IOF ranking.",
                entities=entities,
            )

        # Health queries must precede the broad "what is" concept matcher.
        if any(k in q for k in ["health", "healthy", "momentum score", "health score", "strengthening", "weakening"]):
            return PlannedIntent(
                capability_id="skill_health_analysis",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests Skill Health analysis (relative-momentum evaluation).",
                entities=entities,
            )

        # Reference taxonomy profile / hot tech / concept explanation
        is_concept_query = (
            any(k in q for k in ["reference profile", "hot tech", "hot technology", "similar to", "similar skills", "similar"])
            or any(k in q for k in ["explain", "definition of", "tell me about"])
            or ("what is" in q and target_skill and not target_role and not any(w in q for w in ["roadmap", "learning path", "prepare", "preparation", "job", "career", "demand", "trend"]))
        )
        if is_concept_query:
            return PlannedIntent(
                capability_id="skill_reference_profile",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests reference taxonomy profile or educational concept explanation.",
                entities=entities,
            )

        # Demand forecasting
        if any(k in q for k in ["forecast", "forecasting", "predict", "prediction", "projected demand", "project demand", "future demand"]):
            return PlannedIntent(
                capability_id="skill_demand_forecast",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests forward-looking demand forecasting.",
                entities=entities,
            )

        # Action / preparation / learn next / career roadmap
        if any(k in q for k in [
            "action", "prepare", "preparation", "learn", "how to become", "steps to",
            "what should i learn", "learn next", "career roadmap", "roadmap for",
            "transition to", "transition into", "how to prepare", "study plan",
            "career plan", "learning path", "role preparation", "preparation plan",
            "become", "steps", "step", "how do i become", "take to become",
        ]):
            if target_role or "target role" in q or any(r in q for r in ["role", "career", "job", "become"]):
                return PlannedIntent(
                    capability_id="job_preparation_actions",
                    target_skill=target_skill,
                    target_role=target_role,
                    geography=geography,
                    portal_type=portal_type,
                    reason="Query requests preparation steps and actions for a target job role.",
                    entities=entities,
                )
            return PlannedIntent(
                capability_id="skill_action_recommendations",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests skill acquisition actions.",
                entities=entities,
            )

        # Career / mobility / pathway (pure mobility without preparation actions)
        if any(k in q for k in ["pathway", "pathways", "mobility", "switch role", "career change", "next role", "related occupation", "related role"]):
            return PlannedIntent(
                capability_id="job_mobility_pathways",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests career transition or mobility pathways between roles.",
                entities=entities,
            )

        # Role requirements / skills relevant to role / mentioned in job description / tools used
        if any(k in q for k in ["relevant to", "skills for", "skills mentioned", "mentioned in", "job description", "skills are relevant", "role requirements", "qualifications for", "software tools", "tools does", "tools used"]):
            return PlannedIntent(
                capability_id="job_role_requirements",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests skills relevant to a role or mentioned in a job description.",
                entities=entities,
            )

        # Alignment / fit
        if any(k in q for k in ["align", "alignment", "match", "fit", "compare profile", "gap"]):
            if target_role:
                return PlannedIntent(
                    capability_id="skill_role_alignment",
                    target_skill=target_skill,
                    target_role=target_role,
                    geography=geography,
                    portal_type=portal_type,
                    reason="Query requests skill-to-role alignment evaluation.",
                    entities=entities,
                )

        comparison_skills = list(dict.fromkeys(
            entity.canonical_name
            for entity in entities
            if entity.entity_type in {"skill", "technology"}
        ))
        if len(comparison_skills) >= 2 and re.search(
            r"\b(?:compare|versus|vs\.?|difference between)\b",
            q,
        ):
            return PlannedIntent(
                capability_id=None,
                target_skill=None,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason=(
                    "Direct skill comparisons are not supported yet. I can run separate "
                    f"trend lookups for {comparison_skills[0]} and {comparison_skills[1]}; "
                    "please ask about each skill separately."
                ),
                entities=entities,
            )

        # Hiring demand trends (job postings) partitioned from developer adoption (GitHub)
        if any(k in q for k in ["hiring demand", "job demand", "employer demand", "hiring trends", "hiring trend"]):
            return PlannedIntent(
                capability_id="hiring_demand_trends",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests job hiring demand trends partitioned from developer adoption.",
                entities=entities,
            )

        # Job postings / jobs available
        if any(k in q for k in ["jobs are available", "jobs available", "what jobs", "postings in", "available jobs", "job openings", "job opening", "openings", "posting", "postings", "job listing", "jobs", "hiring", "verified job", "find jobs", "search jobs"]):
            return PlannedIntent(
                capability_id="job_verified_postings",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests verified postings inventory.",
                entities=entities,
            )

        # Market trend / velocity
        if any(k in q for k in ["velocity", "acceleration", "momentum", "market trend", "market trends", "trend velocity"]):
            return PlannedIntent(
                capability_id="market_trend_velocity",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests market velocity and hiring momentum.",
                entities=entities,
            )

        # Market snapshot / tech signals
        if any(k in q for k in ["snapshot", "macro snapshot", "market snapshot", "market overview"]):
            return PlannedIntent(
                capability_id="market_intelligence_snapshot",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests market intelligence macro snapshot.",
                entities=entities,
            )
        if any(k in q for k in ["market", "overview", "macro", "landscape", "ecosystem"]):
            if any(k in q for k in ["tech", "technology", "signal", "ranking"]):
                return PlannedIntent(
                    capability_id="market_tech_signals",
                    target_skill=target_skill,
                    target_role=target_role,
                    geography=geography,
                    portal_type=portal_type,
                    reason="Query requests technology adoption ranking and signals.",
                    entities=entities,
                )
            return PlannedIntent(
                capability_id="market_intelligence_snapshot",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests market intelligence macro snapshot.",
                entities=entities,
            )

        # Evidence / citation
        if any(k in q for k in ["evidence", "citation", "provenance", "source", "origin"]):
            return PlannedIntent(
                capability_id="skill_evidence_citations",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests evidence and provenance details.",
                entities=entities,
            )

        # Historical signals vs demand trend
        if any(k in q for k in ["history", "historical", "quarterly", "pushers", "github"]):
            return PlannedIntent(
                capability_id="skill_historical_signals",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason="Query requests historical developer adoption series.",
                entities=entities,
            )

        # Default to skill demand trends or reference profile if skill is detected
        if target_skill:
            return PlannedIntent(
                capability_id="skill_demand_trends",
                target_skill=target_skill,
                target_role=target_role,
                geography=geography,
                portal_type=portal_type,
                reason=f"Skill '{target_skill}' identified for demand trend analysis.",
                entities=entities,
            )

        # Do not guess a data capability for an unrecognized question.
        return PlannedIntent(
            capability_id=None,
            target_skill=None,
            target_role=target_role,
            geography=geography,
            portal_type=portal_type,
            reason="Would you like help with skills, jobs, market signals, or role information?",
            entities=entities,
        )

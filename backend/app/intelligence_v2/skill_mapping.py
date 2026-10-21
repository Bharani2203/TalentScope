"""Greenfield Intelligence Engine V2 — Skill & Role Mapping.

Provides canonical normalization, ambiguity guarding, O*NET/ESCO taxonomy lookup,
and truthful role skill alignment with explicit declaration semantics.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.analytics.skill_registry import (
    BY_ID,
    BY_NAME,
    _ALIASES,
    SkillDefinition,
    canonical_skill_id,
    normalize_skill,
    normalize_skill_entry,
)
from app.storage.reference_store import ReferenceDataStore


MappingStatus = Literal["matched", "partial", "unmapped", "not_declared"]


class SkillMappingResult(BaseModel):
    """Result of mapping a raw skill label to canonical and reference taxonomies."""

    model_config = ConfigDict(extra="forbid")

    raw_input: str
    canonical_id: str | None = None
    canonical_name: str
    display_name: str
    category: str | None = None
    status: MappingStatus = "unmapped"
    ambiguous: bool = False
    context_required: bool = False
    notes: str | None = None
    onet_matches: list[dict[str, Any]] = Field(default_factory=list)
    esco_matches: list[dict[str, Any]] = Field(default_factory=list)


class RoleSkillAlignment(BaseModel):
    """Truthful alignment of declared skills against role requirements."""

    model_config = ConfigDict(extra="forbid")

    role_name: str
    role_code: str | None = None
    taxonomy_source: str = "reference_taxonomy"
    required_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    not_declared_skills: list[str] = Field(default_factory=list)
    unmapped_skills: list[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    coverage_numerator: int = 0
    coverage_denominator: int = 0
    disclaimer: str = (
        "Skills listed as 'not declared' reflect gaps in the evaluated profile "
        "rather than proven absence of capability. Verification requires technical "
        "assessment or interview."
    )


AMBIGUOUS_TERMS = {
    "go": "Programming language (Go/Golang) vs English verb",
    "r": "Statistical computing language (R) vs single letter",
    "c": "Programming language (C) vs single letter",
    "ts": "TypeScript vs Time Series vs other acronyms",
    "ml": "Machine Learning vs Markup Language / Milliliter",
    "node": "Node.js runtime vs general network/graph node",
    "express": "Express.js framework vs fast shipping/delivery",
    "cloud": "Cloud Computing vs meteorological term",
    "lambda": "AWS Lambda / serverless vs mathematical/Python anonymous function",
}

TECHNICAL_CONTEXT_WORDS = {
    "developer", "engineer", "programming", "code", "software", "backend",
    "frontend", "fullstack", "tech", "stack", "cloud", "aws", "framework",
    "language", "library", "runtime", "data", "pipeline", "api", "server",
}


class V2SkillMapper:
    """Canonical normalizer and reference mapper for skills and occupations."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)

    def normalize(self, query: str, context: str | None = None) -> SkillMappingResult:
        """Map a skill string to canonical form with ambiguity guards."""
        raw = query.strip()
        if not raw:
            return SkillMappingResult(
                raw_input=query,
                canonical_name=query,
                display_name=query,
                status="unmapped",
                notes="Empty input",
            )

        casefolded = raw.casefold()

        # Check for ambiguity guards
        is_ambiguous_term = casefolded in AMBIGUOUS_TERMS
        has_tech_context = False
        if context:
            ctx_tokens = set(re.findall(r"\w+", context.casefold()))
            has_tech_context = bool(ctx_tokens & TECHNICAL_CONTEXT_WORDS)

        # 1. Registry lookup
        entry = normalize_skill_entry(raw)
        if entry.is_known:
            if is_ambiguous_term and not has_tech_context and casefolded in {"go", "r", "c"}:
                # Isolated single letter or ambiguous term without context
                return SkillMappingResult(
                    raw_input=raw,
                    canonical_id=entry.canonical_skill_id,
                    canonical_name=entry.canonical_name,
                    display_name=entry.display_name,
                    category=entry.category,
                    status="partial",
                    ambiguous=True,
                    context_required=True,
                    notes=f"Ambiguous term '{raw}'. Disambiguation required: {AMBIGUOUS_TERMS[casefolded]}.",
                )
            return SkillMappingResult(
                raw_input=raw,
                canonical_id=entry.canonical_skill_id,
                canonical_name=entry.canonical_name,
                display_name=entry.display_name,
                category=entry.category,
                status="matched",
                ambiguous=is_ambiguous_term,
                context_required=False,
            )

        # 2. Check reference taxonomy in SQLite
        onet_matches = self._search_onet_software_skills(raw)
        esco_matches = self._search_esco_skills(raw)

        if onet_matches or esco_matches:
            best_name = raw
            if onet_matches:
                best_name = onet_matches[0].get("workplace_example") or raw
            elif esco_matches:
                best_name = esco_matches[0].get("preferred_label") or raw

            return SkillMappingResult(
                raw_input=raw,
                canonical_id=f"ref:{casefolded.replace(' ', '_')}",
                canonical_name=best_name,
                display_name=best_name,
                category="Reference Taxonomy",
                status="matched",
                ambiguous=False,
                onet_matches=onet_matches[:5],
                esco_matches=esco_matches[:5],
                notes="Matched via verified local reference taxonomy",
            )

        return SkillMappingResult(
            raw_input=raw,
            canonical_name=raw,
            display_name=raw,
            status="unmapped",
            notes="Not found in canonical registry or local reference datasets",
        )

    def _search_onet_software_skills(self, query: str) -> list[dict[str, Any]]:
        try:
            with self.store._connect() as conn:
                # Prioritize exact match
                rows = conn.execute(
                    """
                    SELECT soc_code, title, workplace_example, element_name, hot_technology, in_demand
                    FROM ref_onet_software_skills
                    WHERE lower(workplace_example) = lower(?)
                    LIMIT 5
                    """,
                    (query,),
                ).fetchall()
                if not rows and len(query) >= 4:
                    rows = conn.execute(
                        """
                        SELECT soc_code, title, workplace_example, element_name, hot_technology, in_demand
                        FROM ref_onet_software_skills
                        WHERE lower(workplace_example) LIKE ?
                        LIMIT 5
                        """,
                        (f"{query.lower()}%",),
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def _search_esco_skills(self, query: str) -> list[dict[str, Any]]:
        try:
            with self.store._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT concept_uri, preferred_label, skill_type, reuse_level
                    FROM ref_esco_skills
                    WHERE lower(preferred_label) = lower(?)
                    LIMIT 5
                    """,
                    (query,),
                ).fetchall()
                if not rows and len(query) >= 4:
                    rows = conn.execute(
                        """
                        SELECT concept_uri, preferred_label, skill_type, reuse_level
                        FROM ref_esco_skills
                        WHERE lower(preferred_label) LIKE ?
                        LIMIT 5
                        """,
                        (f"{query.lower()}%",),
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def align_role_skills(
        self,
        role_name: str,
        declared_skills: list[str],
        soc_code: str | None = None,
    ) -> RoleSkillAlignment:
        """Align a candidate's declared skills with role requirements from O*NET/ESCO."""
        required: list[str] = []
        role_code_resolved = soc_code

        # Attempt to find requirements in O*NET
        try:
            with self.store._connect() as conn:
                if not role_code_resolved:
                    occ = conn.execute(
                        "SELECT soc_code, title FROM ref_onet_occupations WHERE title LIKE ? LIMIT 1",
                        (f"%{role_name}%",),
                    ).fetchone()
                    if occ:
                        role_code_resolved = occ["soc_code"]

                if role_code_resolved:
                    skills = conn.execute(
                        """
                        SELECT DISTINCT workplace_example
                        FROM ref_onet_software_skills
                        WHERE soc_code = ?
                        ORDER BY hot_technology DESC, in_demand DESC
                        LIMIT 15
                        """,
                        (role_code_resolved,),
                    ).fetchall()
                    required = [s["workplace_example"] for s in skills]
        except Exception:
            pass

        if not required:
            # Fallback to ESCO if O*NET has no match
            try:
                with self.store._connect() as conn:
                    esco_occ = conn.execute(
                        "SELECT concept_uri, preferred_label FROM ref_esco_occupations WHERE preferred_label LIKE ? LIMIT 1",
                        (f"%{role_name}%",),
                    ).fetchone()
                    if esco_occ:
                        role_code_resolved = esco_occ["concept_uri"]
                        esco_skills = conn.execute(
                            """
                            SELECT DISTINCT skill_label
                            FROM ref_esco_occupation_skill_relations
                            WHERE occupation_uri = ? AND relation_type = 'essential'
                            LIMIT 15
                            """,
                            (role_code_resolved,),
                        ).fetchall()
                        required = [s["skill_label"] for s in esco_skills]
            except Exception:
                pass

        if not required:
            # If no role requirements in reference store, return empty alignment
            return RoleSkillAlignment(
                role_name=role_name,
                role_code=None,
                required_skills=[],
                matched_skills=[],
                not_declared_skills=[],
                unmapped_skills=[s for s in declared_skills],
                coverage_score=0.0,
                coverage_numerator=0,
                coverage_denominator=0,
                disclaimer="Role requirements not found in local O*NET or ESCO taxonomies.",
            )

        # Normalize declared skills
        declared_mapped = [self.normalize(s) for s in declared_skills]
        declared_canonical_names = {
            m.canonical_name.casefold() for m in declared_mapped if m.status in {"matched", "partial"}
        }
        declared_aliases = {
            m.raw_input.casefold() for m in declared_mapped
        }

        matched: list[str] = []
        not_declared: list[str] = []

        for req in required:
            req_mapped = self.normalize(req)
            req_key = req_mapped.canonical_name.casefold()
            req_raw_key = req.casefold()

            if (
                req_key in declared_canonical_names
                or req_raw_key in declared_aliases
                or any(req_key in a for a in declared_canonical_names)
            ):
                matched.append(req)
            else:
                not_declared.append(req)

        coverage_num = len(matched)
        coverage_den = len(required)
        coverage = round(coverage_num / coverage_den, 2) if coverage_den > 0 else 0.0

        return RoleSkillAlignment(
            role_name=role_name,
            role_code=role_code_resolved,
            taxonomy_source="onet" if (role_code_resolved and "-" in role_code_resolved) else "esco",
            required_skills=required,
            matched_skills=matched,
            not_declared_skills=not_declared,
            unmapped_skills=[],
            coverage_score=coverage,
            coverage_numerator=coverage_num,
            coverage_denominator=coverage_den,
        )

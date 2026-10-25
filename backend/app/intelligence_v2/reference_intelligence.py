"""Greenfield Intelligence Engine V2 — Skill & Role Reference Intelligence.

Implements Phase 2:
1. Skill & Occupation Lookup (canonical IDs, exact/partial search, supported aliases, ambiguity handling).
2. Explainable Related-Skill Intelligence (explicit relationship types, PPMI / IOF ranking, anti-generic filtering).
3. Truthful Role-Skill Alignment (reference baselines vs verified employer requirements, declaration semantics).
4. Career Mobility Pathways (adjacent occupations via O*NET related occupations and skill overlap).
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Literal

from app.analytics.skill_registry import (
    BY_ID,
    BY_NAME,
    _ALIASES,
    canonical_skill_id,
    normalize_skill_entry,
)
from app.intelligence_v2.contracts import (
    CareerMobilityPathwayItem,
    CareerMobilityResult,
    RelatedSkillItem,
    RelatedSkillsResult,
    RelationshipType,
    RoleSkillAlignmentResult,
    TaxonomyLookupItem,
    TaxonomyLookupResult,
)
from app.intelligence_v2.occupation_names import (
    normalize_occupation_name,
    occupation_label_matches,
)
from app.intelligence_v2.source_registry import V2SourceRegistry
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)

AMBIGUOUS_SKILL_TERMS: dict[str, str] = {
    "go": "Programming language (Go/Golang) vs common English verb",
    "r": "Statistical computing language (R) vs single letter",
    "c": "Programming language (C) vs single letter",
    "ts": "TypeScript language vs Time Series or TeamSpeak acronym",
    "ml": "Machine Learning vs Markup Language / Milliliter",
    "node": "Node.js JavaScript runtime vs general network/graph node",
    "express": "Express.js web framework vs fast delivery / courier service",
    "cloud": "Cloud Computing architecture vs meteorological atmospheric condition",
    "lambda": "AWS Lambda serverless service vs mathematical anonymous function",
    "word": "Microsoft Word word processor vs natural language lexical token",
    "access": "Microsoft Access database software vs permission/access control",
}

TECHNICAL_CONTEXT_WORDS: set[str] = {
    "developer", "engineer", "programming", "code", "software", "backend",
    "frontend", "fullstack", "tech", "stack", "cloud", "aws", "framework",
    "language", "library", "runtime", "data", "pipeline", "api", "server",
    "database", "architecture", "devops", "system", "computing",
}

# These pairs are direct only where the candidate is a Python implementation,
# library, framework, or tooling component that runs in or is built for Python.
# All other former allowlist pairs are retained as an explicit audit inventory
# classified as ecosystem compatibility, and receive no direct-relation bonus.
AUDITED_TECHNICAL_RELATION_INVENTORY: dict[str, set[str]] = {
    # Python ecosystem
    "python": {
        "django", "flask", "fastapi", "pandas", "numpy", "pytorch",
        "scipy", "scikit-learn", "pytest", "jupyter software", "langchain",
        "celery", "pyspark", "matplotlib", "seaborn", "sqlalchemy",
    },
    # JavaScript & TypeScript ecosystem
    "javascript": {
        "typescript", "react", "react native", "angular", "vue.js", "vue_js",
        "node.js", "express.js", "next.js", "jquery", "npm", "webpack",
    },
    "typescript": {
        "javascript", "react", "angular", "node.js", "next.js", "nest.js",
    },
    # Java ecosystem
    "java": {
        "spring", "spring boot", "spring framework", "hibernate", "maven",
        "gradle", "junit", "apache kafka",
    },
    # C++ ecosystem
    "c++": {"cmake", "boost", "qt", "unreal engine"},
    # C# / .NET ecosystem
    "c#": {".net", ".net core", "asp.net", "entity framework", "unity"},
    # Containers & Orchestration
    "docker": {"kubernetes", "containerd", "docker compose", "k8s"},
    "kubernetes": {"docker", "helm", "containerd", "k8s"},
    # Cloud Infrastructure & Managed Services
    "aws": {"aws lambda", "amazon s3", "amazon ec2", "amazon dynamodb", "cloudformation"},
    "aws_lambda": {"aws"},
    "azure": {"azure functions", "azure devops", "azure blob storage", "bicep", "arm templates"},
    "azure_functions": {"azure"},
    "google_cloud": {"google cloud platform", "google compute engine", "bigquery", "google kubernetes engine"},
    # R ecosystem
    "r": {"rstudio", "tidyverse", "ggplot2", "dplyr", "shiny"},
    # Mobile & Frontend Frameworks
    "react": {"react native", "javascript", "typescript", "redux", "next.js"},
    "react_native": {"react", "javascript", "typescript"},
}

_DIRECT_RELATION_PAIRS = {
    ("python", candidate)
    for candidate in AUDITED_TECHNICAL_RELATION_INVENTORY["python"]
}
VALIDATED_DIRECT_TECHNICAL_RELATIONS: dict[str, set[str]] = {
    "python": set(AUDITED_TECHNICAL_RELATION_INVENTORY["python"]),
}

# Every pair formerly in the broad allowlist has an explicit semantic category.
# Ecosystem compatibility is useful context but is not a direct dependency.
TECHNICAL_RELATION_CLASSIFICATIONS: dict[tuple[str, str], str] = {
    (target, candidate): (
        "verified_direct_relation"
        if (target, candidate) in _DIRECT_RELATION_PAIRS
        else "ecosystem_compatibility"
    )
    for target, candidates in AUDITED_TECHNICAL_RELATION_INVENTORY.items()
    for candidate in candidates
}


def classify_technical_relation(target: str, candidate: str) -> str:
    """Classify audited pairs, canonicalizing aliases; unknown pairs are unsupported."""
    t_entry = normalize_skill_entry(target)
    c_entry = normalize_skill_entry(candidate)
    t_name = (t_entry.canonical_name if t_entry.is_known else target).strip().casefold()
    c_name = (c_entry.canonical_name if c_entry.is_known else candidate).strip().casefold()
    # Common shorthand not represented as an alias in the shared skill registry.
    c_name = {"kafka": "apache kafka"}.get(c_name, c_name)
    t_name = {"kafka": "apache kafka"}.get(t_name, t_name)
    pair = (t_name, c_name)
    reverse = (c_name, t_name)
    return TECHNICAL_RELATION_CLASSIFICATIONS.get(
        pair, TECHNICAL_RELATION_CLASSIFICATIONS.get(reverse, "not_supported")
    )


def _ppmi_iof_intermediates(
    co_count: int | None,
    target_count: int | None,
    candidate_count: int | None,
    total_occupations: int | None,
) -> tuple[float, float, float]:
    """Return nonnegative PPMI, IOF, and co-occurrence frequency discount safely."""
    co = max(0, int(co_count or 0))
    n_target = max(0, int(target_count or 0))
    n_candidate = max(0, int(candidate_count or 0))
    total = max(0, int(total_occupations or 0))
    if not total or not n_target or not n_candidate:
        return 0.0, 0.0, co / (co + 1.0)
    ratio = (co * total) / (n_target * n_candidate)
    ppmi = max(0.0, math.log2(ratio)) if ratio > 0 else 0.0
    iof = math.log2(total / n_candidate)
    return ppmi, iof, co / (co + 1.0)


def is_validated_direct_technical_relation(target: str, candidate: str) -> bool:
    """True only for specifically documented direct technical integrations/dependencies."""
    t_raw = target.strip().casefold()
    c_raw = candidate.strip().casefold()
    if t_raw == c_raw:
        return False

    t_entry = normalize_skill_entry(t_raw)
    c_entry = normalize_skill_entry(c_raw)

    t_keys = {t_raw}
    if t_entry.canonical_skill_id:
        t_keys.add(t_entry.canonical_skill_id.casefold())
    if t_entry.canonical_name:
        t_keys.add(t_entry.canonical_name.casefold())

    c_keys = {c_raw}
    if c_entry.canonical_skill_id:
        c_keys.add(c_entry.canonical_skill_id.casefold())
    if c_entry.canonical_name:
        c_keys.add(c_entry.canonical_name.casefold())

    return classify_technical_relation(target, candidate) == "verified_direct_relation"


class ReferenceTaxonomyLookupEngine:
    """Canonical lookup engine for skills and occupations across O*NET and ESCO."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.source_registry = V2SourceRegistry()

    def lookup(
        self,
        query: str,
        entity_type: Literal["all", "skill", "occupation"] = "all",
        limit: int = 15,
        context: str | None = None,
        exact_occupation: bool = False,
    ) -> TaxonomyLookupResult:
        """Look up skills or occupations by canonical ID, exact name, supported alias, or partial search."""
        raw = query.strip()
        if not raw:
            return TaxonomyLookupResult(
                query=query,
                status="insufficient_data",
                total_matches=0,
                results=[],
                explanation="Lookup query cannot be empty.",
                limitations=["An entity name or canonical ID must be supplied."],
            )

        casefolded = raw.casefold()
        occupation_query = normalize_occupation_name(raw)

        # 1. Ambiguity Guard
        has_tech_context = False
        if context:
            tokens = set(re.findall(r"\w+", context.casefold()))
            has_tech_context = bool(tokens & TECHNICAL_CONTEXT_WORDS)

        if casefolded in AMBIGUOUS_SKILL_TERMS and not has_tech_context:
            note = AMBIGUOUS_SKILL_TERMS[casefolded]
            ambiguous_item = TaxonomyLookupItem(
                entity_type="skill",
                canonical_id=f"ambiguous:{casefolded}",
                name=raw,
                taxonomy="Ambiguous Entity Disambiguation",
                description=f"Term '{raw}' is ambiguous without technical context. {note}.",
                source="TalentScope Ambiguity Guard",
                status="ambiguous",
                ambiguity_note=note,
                metadata={"disambiguation_options": [note]},
            )
            return TaxonomyLookupResult(
                query=raw,
                status="ambiguous",
                total_matches=1,
                results=[ambiguous_item],
                clarification_needed=True,
                explanation=f"The term '{raw}' requires clarification: {note}.",
                limitations=["Disambiguation context is required before canonical matching."],
            )

        results: list[TaxonomyLookupItem] = []
        seen_ids: set[str] = set()

        # 2. Check Canonical Registry for skills
        if entity_type in {"all", "skill"}:
            lookup_key = raw
            if lookup_key.casefold().startswith("skill:"):
                lookup_key = lookup_key[6:]
            reg_entry = normalize_skill_entry(lookup_key)
            if not reg_entry.is_known and lookup_key.casefold() in BY_ID:
                d = BY_ID[lookup_key.casefold()]
                from app.analytics.skill_registry import NormalizedSkill
                reg_entry = NormalizedSkill(
                    canonical_skill_id=d.skill_id,
                    canonical_name=d.name,
                    display_name=d.name,
                    category=d.category,
                    is_known=True,
                    raw_input=raw,
                )
            if reg_entry.is_known:
                c_id = f"skill:{reg_entry.canonical_skill_id}"
                def_obj = BY_ID.get(reg_entry.canonical_skill_id) if reg_entry.canonical_skill_id else None
                aliases = list(def_obj.aliases) if def_obj else []
                item = TaxonomyLookupItem(
                    entity_type="skill",
                    canonical_id=c_id,
                    name=reg_entry.display_name,
                    taxonomy="TalentScope Canonical Skill Registry",
                    description=f"{reg_entry.category} skill with verified canonical mapping.",
                    source="TalentScope Registry",
                    status="matched",
                    metadata={"category": reg_entry.category, "aliases": aliases},
                )
                results.append(item)
                seen_ids.add(c_id)

        # 3. Check SQLite Reference Datasets
        try:
            with self.store._connect() as conn:
                # Occupations Lookup
                if entity_type in {"all", "occupation"}:
                    # O*NET Occupations: by exact SOC code or title
                    if exact_occupation:
                        onet_occs = conn.execute(
                            """
                            SELECT soc_code, title, description
                            FROM ref_onet_occupations
                            WHERE soc_code = ? OR lower(title) LIKE lower(?)
                            """,
                            (raw, f"%{occupation_query}%"),
                        ).fetchall()
                    else:
                        onet_occs = conn.execute(
                            """
                            SELECT soc_code, title, description
                            FROM ref_onet_occupations
                            WHERE soc_code = ? OR lower(title) = lower(?)
                            LIMIT ?
                            """,
                            (raw, occupation_query, limit),
                        ).fetchall()
                    if not onet_occs and len(occupation_query) >= 3:
                        onet_occs = conn.execute(
                            """
                            SELECT soc_code, title, description
                            FROM ref_onet_occupations
                            WHERE lower(title) LIKE lower(?)
                            ORDER BY length(title) ASC
                            LIMIT ?
                            """,
                            (f"%{occupation_query}%", limit),
                        ).fetchall()
                    if exact_occupation:
                        onet_occs = [
                            occ for occ in onet_occs
                            if occupation_label_matches(occupation_query, occ["title"])
                        ]

                    for occ in onet_occs:
                        soc = occ["soc_code"]
                        if soc not in seen_ids:
                            results.append(
                                TaxonomyLookupItem(
                                    entity_type="occupation",
                                    canonical_id=soc,
                                    name=occ["title"],
                                    taxonomy="O*NET 28.0 SOC",
                                    description=occ["description"],
                                    source="ONET_2024",
                                    status="matched" if occupation_label_matches(occupation_query, occ["title"]) or soc == raw else "partial",
                                    metadata={"soc_code": soc},
                                )
                            )
                            seen_ids.add(soc)

                    # ESCO Occupations: by concept_uri, code, or preferred_label / alt_labels
                    if exact_occupation:
                        esco_occs = conn.execute(
                            """
                            SELECT concept_uri, preferred_label, code, isco_group, description, alt_labels
                            FROM ref_esco_occupations
                            WHERE concept_uri = ? OR code = ? OR lower(preferred_label) LIKE lower(?)
                               OR lower(alt_labels) LIKE lower(?)
                            """,
                            (raw, raw, f"%{occupation_query}%", f"%{occupation_query}%"),
                        ).fetchall()
                    else:
                        esco_occs = conn.execute(
                            """
                            SELECT concept_uri, preferred_label, code, isco_group, description, alt_labels
                            FROM ref_esco_occupations
                            WHERE concept_uri = ? OR code = ? OR lower(preferred_label) = lower(?)
                            LIMIT ?
                            """,
                            (raw, raw, occupation_query, limit),
                        ).fetchall()
                    if not esco_occs and len(occupation_query) >= 3:
                        esco_occs = conn.execute(
                            """
                            SELECT concept_uri, preferred_label, code, isco_group, description, alt_labels
                            FROM ref_esco_occupations
                            WHERE lower(preferred_label) LIKE lower(?) OR lower(alt_labels) LIKE lower(?)
                            ORDER BY length(preferred_label) ASC
                            LIMIT ?
                            """,
                            (f"%{occupation_query}%", f"%{occupation_query}%", limit),
                        ).fetchall()
                    if exact_occupation:
                        esco_occs = [
                            occ for occ in esco_occs
                            if occupation_label_matches(
                                occupation_query,
                                occ["preferred_label"],
                                occ["alt_labels"],
                            )
                        ]

                    for eo in esco_occs:
                        uri = eo["concept_uri"]
                        if uri not in seen_ids:
                            results.append(
                                TaxonomyLookupItem(
                                    entity_type="occupation",
                                    canonical_id=uri,
                                    name=eo["preferred_label"],
                                    taxonomy="ESCO v1.2.1 Occupation",
                                    description=eo["description"],
                                    source="ESCO_V120",
                                    status="matched" if occupation_label_matches(
                                        occupation_query,
                                        eo["preferred_label"],
                                        eo["alt_labels"],
                                    ) or uri == raw else "partial",
                                    metadata={"isco_group": eo["isco_group"], "code": eo["code"]},
                                )
                            )
                            seen_ids.add(uri)

                # Skills Lookup
                if entity_type in {"all", "skill"}:
                    # O*NET Software Skills: workplace_example
                    onet_skills = conn.execute(
                        """
                        SELECT DISTINCT workplace_example, element_id, element_name, hot_technology, in_demand, canonical_skill_id
                        FROM ref_onet_software_skills
                        WHERE lower(workplace_example) = lower(?)
                        LIMIT ?
                        """,
                        (raw, limit),
                    ).fetchall()
                    if not onet_skills and len(raw) >= 3:
                        onet_skills = conn.execute(
                            """
                            SELECT DISTINCT workplace_example, element_id, element_name, hot_technology, in_demand, canonical_skill_id
                            FROM ref_onet_software_skills
                            WHERE lower(workplace_example) LIKE lower(?)
                            ORDER BY hot_technology DESC, in_demand DESC, length(workplace_example) ASC
                            LIMIT ?
                            """,
                            (f"%{raw}%", limit),
                        ).fetchall()

                    for sk in onet_skills:
                        name = sk["workplace_example"]
                        key = f"onet_skill:{name.casefold()}"
                        if key not in seen_ids:
                            results.append(
                                TaxonomyLookupItem(
                                    entity_type="skill",
                                    canonical_id=sk["canonical_skill_id"] or key,
                                    name=name,
                                    taxonomy="O*NET 28.0 Software Skills",
                                    description=f"Software skill classified under element '{sk['element_name']}' (Element ID: {sk['element_id']}).",
                                    source="ONET_2024",
                                    status="matched" if name.casefold() == casefolded else "partial",
                                    metadata={
                                        "element_id": sk["element_id"],
                                        "element_name": sk["element_name"],
                                        "hot_technology": bool(sk["hot_technology"]),
                                        "in_demand": bool(sk["in_demand"]),
                                    },
                                )
                            )
                            seen_ids.add(key)

                    # ESCO Skills: concept_uri or preferred_label / alt_labels
                    esco_skills = conn.execute(
                        """
                        SELECT concept_uri, preferred_label, skill_type, reuse_level, description, alt_labels
                        FROM ref_esco_skills
                        WHERE concept_uri = ? OR lower(preferred_label) = lower(?)
                        LIMIT ?
                        """,
                        (raw, raw, limit),
                    ).fetchall()
                    if not esco_skills and len(raw) >= 3:
                        esco_skills = conn.execute(
                            """
                            SELECT concept_uri, preferred_label, skill_type, reuse_level, description, alt_labels
                            FROM ref_esco_skills
                            WHERE lower(preferred_label) LIKE lower(?) OR lower(alt_labels) LIKE lower(?)
                            ORDER BY length(preferred_label) ASC
                            LIMIT ?
                            """,
                            (f"%{raw}%", f"%{raw}%", limit),
                        ).fetchall()

                    for esk in esco_skills:
                        uri = esk["concept_uri"]
                        if uri not in seen_ids:
                            results.append(
                                TaxonomyLookupItem(
                                    entity_type="skill",
                                    canonical_id=uri,
                                    name=esk["preferred_label"],
                                    taxonomy="ESCO v1.2.1 Skill",
                                    description=esk["description"],
                                    source="ESCO_V120",
                                    status="matched" if esk["preferred_label"].casefold() == casefolded or uri == raw else "partial",
                                    metadata={
                                        "skill_type": esk["skill_type"],
                                        "reuse_level": esk["reuse_level"],
                                    },
                                )
                            )
                            seen_ids.add(uri)

        except Exception as exc:
            logger.error("Error executing reference taxonomy lookup: %s", exc)
            return TaxonomyLookupResult(
                query=raw,
                status="insufficient_data",
                total_matches=0,
                results=[],
                explanation=f"Database lookup failed: {exc}",
                limitations=["Reference database connection error."],
            )

        if not results:
            return TaxonomyLookupResult(
                query=raw,
                status="insufficient_data",
                total_matches=0,
                results=[],
                explanation=f"No matching skill or occupation found for query '{raw}' in local O*NET or ESCO taxonomies.",
                limitations=["Entity is not present in local O*NET 28.0 or ESCO v1.2.1 reference taxonomies."],
            )

        exact_match = any(r.status == "matched" for r in results)
        return TaxonomyLookupResult(
            query=raw,
            status="ready" if exact_match else "partial",
            total_matches=len(results),
            results=results[:limit],
            explanation=(
                f"Resolved {len(results)} taxonomy matches for '{raw}' across official O*NET and ESCO reference datasets."
                if exact_match
                else f"Found {len(results)} partial/approximate taxonomy matches for '{raw}'."
            ),
            limitations=["Results reflect static O*NET 28.0 and ESCO v1.2.1 reference taxonomies."],
        )


class RelatedSkillsEngine:
    """Computes explainable related skills using documented O*NET/ESCO relationships and PPMI/IOF ranking."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)

    def get_related_skills(self, skill_name: str, limit: int = 10) -> RelatedSkillsResult:
        """Return explainable related skills with explicit relationship types and anti-generic PPMI ranking."""
        raw = skill_name.strip()
        if not raw:
            return RelatedSkillsResult(
                target_skill=skill_name,
                status="insufficient_data",
                related_skills=[],
                explanation="Skill name cannot be empty.",
                limitations=["A target skill must be specified."],
            )

        casefolded = raw.casefold()

        # Check ambiguity
        if casefolded in AMBIGUOUS_SKILL_TERMS:
            return RelatedSkillsResult(
                target_skill=raw,
                status="ambiguous",
                related_skills=[],
                explanation=f"Skill '{raw}' is ambiguous ({AMBIGUOUS_SKILL_TERMS[casefolded]}). Please provide a specific skill name.",
                limitations=["Disambiguation required."],
            )

        try:
            with self.store._connect() as conn:
                # 1. Resolve canonical name and O*NET element IDs for target skill via registry aliases
                reg_entry = normalize_skill_entry(raw)
                search_candidates = [raw]
                if reg_entry.is_known:
                    if reg_entry.display_name and reg_entry.display_name.casefold() != casefolded:
                        search_candidates.append(reg_entry.display_name)
                    if reg_entry.canonical_name and reg_entry.canonical_name.casefold() not in {s.casefold() for s in search_candidates}:
                        search_candidates.append(reg_entry.canonical_name)

                target_rows = []
                for cand_query in search_candidates:
                    target_rows = conn.execute(
                        """
                        SELECT DISTINCT workplace_example, element_id, element_name, canonical_skill_id
                        FROM ref_onet_software_skills
                        WHERE lower(workplace_example) = lower(?)
                        """,
                        (cand_query,),
                    ).fetchall()
                    if target_rows:
                        break

                if not target_rows:
                    # Try partial match if query has >= 3 chars
                    target_rows = conn.execute(
                        """
                        SELECT DISTINCT workplace_example, element_id, element_name, canonical_skill_id
                        FROM ref_onet_software_skills
                        WHERE lower(workplace_example) LIKE lower(?)
                        LIMIT 5
                        """,
                        (f"%{raw}%",),
                    ).fetchall()

                if not target_rows:
                    return RelatedSkillsResult(
                        target_skill=raw,
                        canonical_id=f"skill:{reg_entry.canonical_skill_id}" if reg_entry.is_known else None,
                        status="insufficient_data",
                        related_skills=[],
                        explanation=f"Skill '{raw}' not found in local O*NET software skills reference dataset.",
                        limitations=["Skill relationships require documented presence in O*NET software skills."],
                    )

                canonical_name = target_rows[0]["workplace_example"]
                target_element_ids = {r["element_id"] for r in target_rows if r["element_id"]}
                target_element_names = {r["element_name"] for r in target_rows if r["element_name"]}

                # 2. Total occupations in reference dataset
                total_occupations_row = conn.execute(
                    "SELECT COUNT(DISTINCT soc_code) as cnt FROM ref_onet_software_skills"
                ).fetchone()
                total_occupations = total_occupations_row["cnt"] if total_occupations_row else 923

                # 3. Occupations requiring target skill
                target_soc_rows = conn.execute(
                    """
                    SELECT DISTINCT soc_code FROM ref_onet_software_skills
                    WHERE lower(workplace_example) = lower(?)
                    """,
                    (canonical_name,),
                ).fetchall()
                target_socs = [r["soc_code"] for r in target_soc_rows]
                n_target = len(target_socs)

                if n_target == 0:
                    return RelatedSkillsResult(
                        target_skill=canonical_name,
                        status="insufficient_data",
                        related_skills=[],
                        explanation=f"No occupational software skill mappings found for '{canonical_name}'.",
                        limitations=["Zero occupational associations recorded in reference dataset."],
                    )

                # 4. Fetch candidate co-occurring skills and direct element relations
                # Placeholders for soc_codes
                placeholders = ",".join("?" for _ in target_socs)
                query_sql = f"""
                    SELECT workplace_example, element_id, element_name, hot_technology, in_demand,
                           canonical_skill_id, count(DISTINCT soc_code) as co_count
                    FROM ref_onet_software_skills
                    WHERE soc_code IN ({placeholders})
                      AND lower(workplace_example) != lower(?)
                    GROUP BY workplace_example
                    HAVING co_count >= 1
                """
                params = list(target_socs) + [canonical_name]
                candidates = conn.execute(query_sql, params).fetchall()

                # Also fetch related occupations for general_occupational_association
                related_socs_rows = conn.execute(
                    f"""
                    SELECT DISTINCT related_soc_code, relatedness_tier
                    FROM ref_onet_related_occupations
                    WHERE soc_code IN ({placeholders})
                    """,
                    target_socs,
                ).fetchall()
                related_socs_set = {r["related_soc_code"] for r in related_socs_rows}

                scored_skills: list[RelatedSkillItem] = []

                for cand in candidates:
                    cand_name = cand["workplace_example"]
                    co_cnt = cand["co_count"]
                    cand_elem_id = cand["element_id"]
                    cand_elem_name = cand["element_name"]

                    # Total occupations containing candidate skill
                    n_cand_row = conn.execute(
                        "SELECT COUNT(DISTINCT soc_code) as cnt FROM ref_onet_software_skills WHERE workplace_example = ?",
                        (cand_name,),
                    ).fetchone()
                    n_cand = n_cand_row["cnt"] if n_cand_row else 1

                    # PPMI: log2( (co_count * total_occupations) / (n_target * n_cand) )
                    ppmi, iof, freq_discount = _ppmi_iof_intermediates(
                        co_cnt, n_target, n_cand, total_occupations
                    )

                    # Determine explicit relationship type via validated direct technical dependencies
                    is_direct_tech = is_validated_direct_technical_relation(canonical_name, cand_name)
                    if is_direct_tech:
                        rel_type: RelationshipType = "direct_technical_relation"
                        supporting_rel = f"Documented direct technical integration or dependency between {canonical_name} and {cand_name}"
                        explanation = (
                            f"Direct technical relation: '{cand_name}' has a documented technical integration "
                            f"or dependency with '{canonical_name}'."
                        )
                        base_score = (ppmi * freq_discount) + (0.15 * iof) + 2.0
                        final_score = round(base_score, 3)
                    else:
                        rel_type = "same_occupation_cooccurrence"
                        if cand_elem_id in target_element_ids:
                            supporting_rel = (
                                f"Co-occurs in {co_cnt} of {n_target} target occupations; "
                                f"shares O*NET category '{cand_elem_name}'"
                            )
                            explanation = (
                                f"Occupational co-occurrence: frequently co-required with '{canonical_name}' in "
                                f"{co_cnt} shared occupations and classified under O*NET category '{cand_elem_name}'."
                            )
                        else:
                            supporting_rel = f"Co-occurs in {co_cnt} of {n_target} target occupations (PPMI: {ppmi:.2f})"
                            explanation = (
                                f"Occupational co-occurrence: frequently co-required with '{canonical_name}' in "
                                f"{co_cnt} shared occupations (e.g. Software Developers)."
                            )
                        base_score = (ppmi * freq_discount) + (0.15 * iof)
                        if n_cand > 300:
                            base_score *= 0.15
                        final_score = round(base_score, 3)

                    cand_entry = normalize_skill_entry(cand_name)
                    cand_canonical_id = (
                        f"skill:{cand_entry.canonical_skill_id}"
                        if cand_entry.is_known
                        else (cand["canonical_skill_id"] or f"onet_skill:{cand_name.casefold().replace(' ', '_')}")
                    )

                    scored_skills.append(
                        RelatedSkillItem(
                            skill_name=cand_name,
                            canonical_id=cand_canonical_id,
                            relationship_type=rel_type,
                            source="O*NET 28.0 Software Skills",
                            supporting_relationship=supporting_rel,
                            ranking_method="PPMI-IOF (Pointwise Mutual Information & Inverse Occupation Frequency)",
                            ranking_score=final_score,
                            explanation=explanation,
                            metadata={
                                "co_count": co_cnt,
                                "n_target": n_target,
                                "n_cand": n_cand,
                                "total_occupations": total_occupations,
                                "ppmi": round(ppmi, 3),
                                "iof": round(iof, 3),
                            },
                        )
                    )

                # If candidate skills are sparse, enrich with general_occupational_association
                if len(scored_skills) < limit and related_socs_set:
                    rel_placeholders = ",".join("?" for _ in list(related_socs_set)[:50])
                    gen_rows = conn.execute(
                        f"""
                        SELECT DISTINCT workplace_example, element_name, canonical_skill_id
                        FROM ref_onet_software_skills
                        WHERE soc_code IN ({rel_placeholders})
                          AND lower(workplace_example) != lower(?)
                          AND hot_technology = 1
                        LIMIT 10
                        """,
                        list(related_socs_set)[:50] + [canonical_name],
                    ).fetchall()
                    existing_names = {s.skill_name for s in scored_skills}
                    for gr in gen_rows:
                        gn = gr["workplace_example"]
                        if gn not in existing_names:
                            gr_entry = normalize_skill_entry(gn)
                            gr_canonical_id = (
                                f"skill:{gr_entry.canonical_skill_id}"
                                if gr_entry.is_known
                                else (gr["canonical_skill_id"] or f"onet_skill:{gn.casefold().replace(' ', '_')}")
                            )
                            scored_skills.append(
                                RelatedSkillItem(
                                    skill_name=gn,
                                    canonical_id=gr_canonical_id,
                                    relationship_type="general_occupational_association",
                                    source="O*NET 28.0 Related Occupations",
                                    supporting_relationship="Associated with occupations adjacent to target roles",
                                    ranking_method="Taxonomy Adjacency",
                                    ranking_score=0.5,
                                    explanation=f"General occupational association: high-priority skill in adjacent occupations sharing workflows with {canonical_name}.",
                                    metadata={
                                        "co_count": 0,
                                        "n_target": n_target,
                                        "n_cand": 0,
                                        "total_occupations": total_occupations,
                                        "ppmi": 0.0,
                                        "iof": 0.0,
                                    },
                                )
                            )

                # Sort by ranking_score descending, with deterministic tie-breaking on co_count, name, and canonical_id
                scored_skills.sort(
                    key=lambda x: (
                        -x.ranking_score,
                        -x.metadata.get("co_count", 0),
                        x.skill_name.casefold(),
                        x.canonical_id,
                    )
                )
                top_results = scored_skills[:limit]

                return RelatedSkillsResult(
                    target_skill=canonical_name,
                    canonical_id=f"skill:{reg_entry.canonical_skill_id}" if reg_entry.is_known else f"skill:{canonical_name.casefold()}",
                    status="ready",
                    related_skills=top_results,
                    explanation=(
                        f"Identified {len(top_results)} explainable related skills for '{canonical_name}' "
                        f"ranked using PPMI and Inverse Occupation Frequency against 923 O*NET occupational profiles."
                    ),
                    limitations=[
                        "Relationships are grounded in official O*NET 28.0 occupational and software taxonomy co-occurrences.",
                        "ranking_score is a heuristic ranking score, not a probability, percentage, confidence level, or validated measure of skill relevance.",
                        "IOF weight 0.15, direct-relation bonus 2.0, and common-skill multiplier 0.15 are design parameters; no empirical calibration evidence is established here.",
                        "Co-occurrence reflects occupational association rather than guaranteed functional dependency unless classified as direct_technical_relation.",
                    ],
                )

        except Exception as exc:
            logger.error("Error retrieving related skills: %s", exc)
            return RelatedSkillsResult(
                target_skill=raw,
                status="insufficient_data",
                related_skills=[],
                explanation=f"Query error encountered: {exc}",
                limitations=["Database execution error."],
            )


class RoleSkillAlignmentEngine:
    """Truthful role-skill alignment with non-qualification disclaimers and ambiguity detection."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.lookup_engine = ReferenceTaxonomyLookupEngine(self.store)

    def align(
        self,
        role_name: str | None = None,
        declared_skills: list[str] | None = None,
        *,
        target_role: str | None = None,
    ) -> RoleSkillAlignmentResult:
        """Align candidate declared skills against reference-associated role skills."""
        raw_role = (target_role or role_name or "").strip()
        declared = declared_skills or []
        if not raw_role:
            return RoleSkillAlignmentResult(
                role_name=raw_role,
                taxonomy_source="unknown",
                status="insufficient_data",
                disclaimer="Target occupation must be provided.",
                explanation="No target occupation specified.",
                limitations=["Empty role query."],
            )

        # 1. Resolve target occupation
        occ_lookup = self.lookup_engine.lookup(raw_role, entity_type="occupation", limit=1)
        if occ_lookup.status in {"insufficient_data", "ambiguous"} or not occ_lookup.results:
            return RoleSkillAlignmentResult(
                role_name=raw_role,
                taxonomy_source="unknown",
                status="insufficient_data",
                disclaimer="Target occupation was not found in official reference taxonomies.",
                explanation=f"Could not locate '{raw_role}' in local O*NET or ESCO occupation taxonomies.",
                limitations=["Role is not recognized in reference datasets."],
            )

        target_occ = occ_lookup.results[0]
        soc_code = target_occ.canonical_id if target_occ.taxonomy.startswith("O*NET") else None
        esco_uri = target_occ.canonical_id if target_occ.taxonomy.startswith("ESCO") else None
        taxonomy_source = target_occ.source

        reference_skills: list[str] = []

        try:
            with self.store._connect() as conn:
                if soc_code:
                    rows = conn.execute(
                        """
                        SELECT DISTINCT workplace_example
                        FROM ref_onet_software_skills
                        WHERE soc_code = ?
                        ORDER BY hot_technology DESC, in_demand DESC, length(workplace_example) ASC
                        LIMIT 25
                        """,
                        (soc_code,),
                    ).fetchall()
                    reference_skills = [r["workplace_example"] for r in rows]

                if not reference_skills and (esco_uri or not soc_code):
                    uri = esco_uri or target_occ.canonical_id
                    rows = conn.execute(
                        """
                        SELECT DISTINCT skill_label
                        FROM ref_esco_occupation_skill_relations
                        WHERE occupation_uri = ? AND relation_type = 'essential'
                        LIMIT 25
                        """,
                        (uri,),
                    ).fetchall()
                    reference_skills = [r["skill_label"] for r in rows]
        except Exception as exc:
            logger.error("Error retrieving occupation skills for alignment: %s", exc)

        if not reference_skills:
            return RoleSkillAlignmentResult(
                role_name=target_occ.name,
                canonical_occupation_id=target_occ.canonical_id,
                canonical_occupation_title=target_occ.name,
                taxonomy_source=taxonomy_source,
                status="insufficient_data",
                disclaimer="No reference-associated skills found for this occupation.",
                explanation=f"Occupational profile for '{target_occ.name}' contains no software or essential skill records.",
                limitations=["No skills cataloged in reference taxonomy."],
            )

        # 2. Analyze declared skills
        matched_skills: list[str] = []
        unresolved_skills: list[str] = []
        ambiguous_skills: list[dict[str, str]] = []

        ref_normalized_map: dict[str, str] = {s.casefold(): s for s in reference_skills}

        for dec in declared_skills:
            dec_clean = dec.strip()
            if not dec_clean:
                continue

            dec_case = dec_clean.casefold()

            # Ambiguity check
            if dec_case in AMBIGUOUS_SKILL_TERMS:
                ambiguous_skills.append({
                    "skill": dec_clean,
                    "reason": AMBIGUOUS_SKILL_TERMS[dec_case],
                })
                # If ambiguous term has direct match in reference skills (e.g. "R" in statistical tools),
                # we still record it as ambiguous to prevent misattribution
                continue

            # Check match against reference skills directly
            if dec_case in ref_normalized_map:
                matched_skills.append(ref_normalized_map[dec_case])
                continue

            # Check canonical normalization
            canonical_entry = normalize_skill_entry(dec_clean)
            if canonical_entry.is_known:
                matched_ref = False
                for ref_s in reference_skills:
                    if canonical_entry.canonical_name.casefold() in ref_s.casefold():
                        matched_skills.append(ref_s)
                        matched_ref = True
                        break
                if not matched_ref:
                    # Known skill, but not reference-associated for this specific occupation
                    pass
            else:
                # Skill unknown in canonical registry and reference datasets
                unresolved_skills.append(dec_clean)

        matched_set = set(matched_skills)
        unmatched_reference_skills = [s for s in reference_skills if s not in matched_set]

        disclaimer = (
            "Reference-associated skills describe baseline occupational profiles from official taxonomies (O*NET/ESCO) "
            "and must not be interpreted as verified live employer requirements. Skills listed as 'not declared' "
            "reflect omissions in the evaluated profile rather than proven candidate deficiencies or disqualifications."
        )

        explanation = (
            f"Candidate profile aligns with {len(matched_skills)} of {len(reference_skills)} reference-associated "
            f"skills for {target_occ.name} ({target_occ.canonical_id}). "
            f"{len(unmatched_reference_skills)} skills are not declared. "
            f"{len(ambiguous_skills)} skills required disambiguation, and {len(unresolved_skills)} were unresolved."
        )

        return RoleSkillAlignmentResult(
            role_name=raw_role,
            canonical_occupation_id=target_occ.canonical_id,
            canonical_occupation_title=target_occ.name,
            taxonomy_source=taxonomy_source,
            reference_associated_skills=reference_skills,
            matched_skills=matched_skills,
            unmatched_reference_skills=unmatched_reference_skills,
            unresolved_skills=unresolved_skills,
            ambiguous_skills=ambiguous_skills,
            status="ready",
            disclaimer=disclaimer,
            explanation=explanation,
            limitations=[
                "Alignment does not assess candidate proficiency, competence, job eligibility, or hiring probability.",
                "Reference skills are baseline taxonomies, not verified employer postings.",
            ],
        )


class CareerMobilityEngine:
    """Identifies adjacent career mobility pathways grounded in O*NET related occupations and skill overlap."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.lookup_engine = ReferenceTaxonomyLookupEngine(self.store)

    def get_pathways(self, occupation_query: str, limit: int = 10) -> CareerMobilityResult:
        """Find plausible adjacent occupations with shared and additional skill analysis."""
        raw = occupation_query.strip()
        if not raw:
            return CareerMobilityResult(
                source_occupation_title=occupation_query,
                status="insufficient_data",
                pathways=[],
                explanation="Occupation query cannot be empty.",
                limitations=["An occupation title or SOC code must be specified."],
            )

        # 1. Resolve source occupation
        lookup_res = self.lookup_engine.lookup(raw, entity_type="occupation", limit=1)
        if lookup_res.status in {"insufficient_data", "ambiguous"} or not lookup_res.results:
            return CareerMobilityResult(
                source_occupation_title=raw,
                status="insufficient_data",
                pathways=[],
                explanation=f"Occupation '{raw}' not found in local reference taxonomies.",
                limitations=["Unknown occupation."],
            )

        source_occ = lookup_res.results[0]
        soc_code = source_occ.canonical_id

        pathways: list[CareerMobilityPathwayItem] = []

        try:
            with self.store._connect() as conn:
                # Skills in source occupation (canonicalized via registry where known)
                source_skills_rows = conn.execute(
                    "SELECT DISTINCT workplace_example FROM ref_onet_software_skills WHERE soc_code = ?",
                    (soc_code,),
                ).fetchall()
                source_skills_raw = {r["workplace_example"] for r in source_skills_rows}
                source_canonical = {
                    normalize_skill_entry(s).display_name if normalize_skill_entry(s).is_known else s.strip()
                    for s in source_skills_raw
                }

                # Related occupations from O*NET
                rel_rows = conn.execute(
                    """
                    SELECT related_soc_code, related_title, relatedness_tier, sort_index
                    FROM ref_onet_related_occupations
                    WHERE soc_code = ?
                    ORDER BY sort_index ASC
                    LIMIT ?
                    """,
                    (soc_code, limit),
                ).fetchall()

                for rel in rel_rows:
                    dest_soc = rel["related_soc_code"]
                    dest_title = rel["related_title"]
                    tier = rel["relatedness_tier"]

                    # Skills in destination occupation (canonicalized via registry where known)
                    dest_skills_rows = conn.execute(
                        "SELECT DISTINCT workplace_example FROM ref_onet_software_skills WHERE soc_code = ?",
                        (dest_soc,),
                    ).fetchall()
                    dest_skills_raw = {r["workplace_example"] for r in dest_skills_rows}
                    dest_canonical = {
                        normalize_skill_entry(s).display_name if normalize_skill_entry(s).is_known else s.strip()
                        for s in dest_skills_raw
                    }

                    shared = sorted(source_canonical & dest_canonical)
                    additional = sorted(dest_canonical - source_canonical)

                    nature = (
                        "Primary-Short: High occupational similarity with strong overlap in documented software competencies."
                        if tier == "Primary-Short"
                        else "Primary-Long: Moderate occupational similarity requiring additional specialized domain competencies."
                        if tier == "Primary-Long"
                        else "Supplemental: Broad occupational transferability with complementary skill foundations."
                    )

                    explanation = (
                        f"Documented O*NET {tier} mobility pathway. Shares {len(shared)} software competencies "
                        f"with {source_occ.name}, requiring approximately {len(additional)} additional competencies."
                    )

                    pathways.append(
                        CareerMobilityPathwayItem(
                            destination_occupation_title=dest_title,
                            destination_soc_code=dest_soc,
                            relatedness_tier=tier,
                            shared_skills=shared,
                            additional_destination_skills=additional,
                            relationship_nature=nature,
                            explanation=explanation,
                        )
                    )

        except Exception as exc:
            logger.error("Error retrieving career mobility pathways: %s", exc)
            return CareerMobilityResult(
                source_occupation_title=source_occ.name,
                source_soc_code=soc_code,
                status="insufficient_data",
                pathways=[],
                explanation=f"Query error: {exc}",
                limitations=["Database execution error."],
            )

        if not pathways:
            return CareerMobilityResult(
                source_occupation_title=source_occ.name,
                source_soc_code=soc_code,
                status="insufficient_data",
                pathways=[],
                explanation=f"No mobility pathways documented for '{source_occ.name}' in O*NET related occupations.",
                limitations=["No related occupations found in reference database."],
            )

        return CareerMobilityResult(
            source_occupation_title=source_occ.name,
            source_soc_code=soc_code,
            status="ready",
            pathways=pathways,
            explanation=(
                f"Identified {len(pathways)} adjacent mobility pathways for {source_occ.name} ({soc_code}) "
                f"grounded in official O*NET related occupations and software competency overlap."
            ),
            limitations=[
                "Pathways describe taxonomy-based occupational skill overlap derived from official O*NET 28.0 datasets; they do not establish an individual's readiness or a guaranteed career pathway.",
                "They do NOT represent individual candidate readiness, transition probability, time-to-transition, or guaranteed hiring outcomes.",
                "Identified shared and additional competencies reflect baseline taxonomy overlap and similarity across standard occupational profiles.",
            ],
        )

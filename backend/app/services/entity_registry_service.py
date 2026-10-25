"""Entity Registry service resolving raw user language and source records to canonical entities."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.analytics.skill_registry import (
    SKILLS,
    SkillDefinition,
    _ALIASES,
    normalize_skill_entry,
)
from app.core.config import Settings, get_settings
from app.models.entity_registry import (
    CanonicalEntity,
    EntityCandidate,
    EntityMatchMethod,
    EntityResolutionRequest,
    EntityResolutionResponse,
    EntityType,
)
from app.services.role_alias_service import (
    normalize_role_alias,
    query_local_onet_occupation,
    role_alias_soc_code,
)
from app.storage.reference_store import ReferenceDataStore


def _clean_token(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().split())


class EntityRegistryService:
    def __init__(
        self,
        settings: Settings | None = None,
        db_path: str | Path | None = None,
    ):
        self.settings = settings or get_settings()
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            # Resolve relative to backend or workspace
            configured = Path(self.settings.skill_intelligence_db_path)
            if (Path("backend") / configured).exists():
                self.db_path = Path("backend") / configured
            else:
                self.db_path = configured

    def _connect_db(self) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            return None
        connection = sqlite3.connect(
            self.db_path.resolve().as_uri() + "?mode=ro",
            timeout=5,
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _skill_definition_to_entity(defn: SkillDefinition) -> CanonicalEntity:
        is_tech = defn.category in {
            "Programming", "Backend", "Frontend",
            "Cloud & Infrastructure", "Database", "Developer Tools",
        }
        entity_type: EntityType = "technology" if is_tech else "skill"
        prefix = "tech" if is_tech else "skill"

        return CanonicalEntity(
            entity_id=f"{prefix}:{defn.skill_id}",
            entity_type=entity_type,
            canonical_name=defn.name,
            aliases=list(defn.aliases),
            category=defn.category,
            source="canonical_registry",
            source_record_id=defn.skill_id,
            status="active",
            metadata={
                "github_topics": list(defn.github_topics),
                "stack_exchange_tags": list(defn.stack_exchange_tags),
                "ambiguous": defn.ambiguous,
            },
        )

    def _resolve_canonical_identifier(
        self,
        identifier: str,
        filter_type: EntityType | None,
    ) -> CanonicalEntity | None:
        normalized = identifier.casefold()
        for definition in SKILLS:
            entity = self._skill_definition_to_entity(definition)
            if normalized in {entity.entity_id.casefold(), definition.skill_id.casefold()}:
                if filter_type is None or entity.entity_type == filter_type:
                    return entity

        if normalized.startswith("occupation:soc:"):
            entity = self._resolve_onet_occupation(identifier[len("occupation:soc:"):])
            return entity if entity and (filter_type is None or filter_type == "occupation") else None

        if normalized.startswith("occupation:esco:"):
            return self._resolve_esco_occupation(identifier[len("occupation:esco:"):]) if filter_type in (None, "occupation") else None

        if normalized.startswith("skill:esco:"):
            return self._resolve_esco_skill(identifier[len("skill:esco:"):]) if filter_type in (None, "skill") else None

        if normalized.startswith("skill:onet:"):
            if filter_type not in (None, "skill"):
                return None
            element_id = identifier[len("skill:onet:"):]
            conn = self._connect_db()
            if conn:
                try:
                    row = conn.execute(
                        """
                        SELECT element_id, element_name
                        FROM ref_onet_essential_skills
                        WHERE element_id = ?
                        LIMIT 1
                        """,
                        (element_id,),
                    ).fetchone()
                    if row:
                        return CanonicalEntity(
                            entity_id=f"skill:onet:{row['element_id']}",
                            entity_type="skill",
                            canonical_name=row["element_name"],
                            aliases=[],
                            category="O*NET Basic Skills",
                            source="ref_onet_essential_skills",
                            source_record_id=row["element_id"],
                            status="active",
                            metadata={"element_id": row["element_id"]},
                        )
                except sqlite3.OperationalError:
                    return None
                finally:
                    conn.close()

        if normalized.startswith("tech:onet:"):
            if filter_type not in (None, "technology"):
                return None
            parts = identifier.split(":")
            if len(parts) == 4:
                conn = self._connect_db()
                if conn:
                    try:
                        rows = conn.execute(
                            "SELECT workplace_example FROM ref_onet_software_skills WHERE element_id = ?",
                            (parts[2],),
                        ).fetchall()
                        for row in rows:
                            entity = self._resolve_onet_software_tool(row["workplace_example"])
                            if entity and entity.entity_id.casefold() == normalized:
                                return entity
                    except sqlite3.OperationalError:
                        return None
                    finally:
                        conn.close()
        return None

    def _resolve_role_alias(self, raw_name: str) -> CanonicalEntity | None:
        """Resolve a declared role alias only when its O*NET row exists locally."""
        soc_code = role_alias_soc_code(raw_name)
        if not soc_code:
            return None
        connection = self._connect_db()
        if connection is None:
            return None
        try:
            occupation = query_local_onet_occupation(connection, soc_code)
        finally:
            connection.close()
        if occupation is None:
            return None
        title = occupation["title"]
        return CanonicalEntity(
            entity_id=f"occupation:soc:{soc_code}",
            entity_type="occupation",
            canonical_name=title,
            aliases=[raw_name],
            source="ref_onet_occupations",
            source_record_id=soc_code,
            status="active",
            metadata={
                "requested_role": raw_name,
                "mapping_disclosure": (
                    f"'{raw_name}' is mapped to O*NET {title} (SOC {soc_code}), "
                    "the closest available occupation in the local reference data."
                ),
                "mapping_source": "local O*NET SQLite reference data",
            },
        )

    def resolve(self, request: EntityResolutionRequest) -> EntityResolutionResponse:
        """Resolve a raw name or identifier to a canonical entity or ambiguous candidate set."""
        raw_name = _clean_token(request.name)
        if not raw_name:
            return EntityResolutionResponse(
                name=request.name,
                status="not_found",
                confidence=0.0,
                source_provenance={"reason": "Empty name provided."},
            )

        filter_type = request.entity_type
        context = request.context or {}

        # Bare registry slugs such as "go" are valid legacy skill IDs as well
        # as ambiguous natural-language terms. Only explicit typed IDs bypass
        # the ambiguity guard; names can still resolve canonically below.
        canonical_entity = (
            self._resolve_canonical_identifier(raw_name, filter_type)
            if ":" in raw_name
            else None
        )
        if canonical_entity:
            return EntityResolutionResponse(
                name=raw_name,
                status="resolved",
                entity=canonical_entity,
                match_method="exact",
                confidence=1.0,
                source_provenance={"source": canonical_entity.source, "canonical_id": canonical_entity.entity_id},
            )

        if filter_type in (None, "occupation") and role_alias_soc_code(raw_name):
            aliased_occupation = self._resolve_role_alias(raw_name)
            if aliased_occupation:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="resolved",
                    entity=aliased_occupation,
                    match_method="alias",
                    confidence=0.95,
                    source_provenance={
                        "source": "ref_onet_occupations",
                        "soc_code": aliased_occupation.source_record_id,
                        "mapping_disclosure": aliased_occupation.metadata["mapping_disclosure"],
                    },
                )
            return EntityResolutionResponse(
                name=raw_name,
                status="not_found",
                confidence=0.0,
                source_provenance={
                    "reason": "The configured O*NET SOC target was not found in local reference data.",
                    "requested_alias": normalize_role_alias(raw_name),
                },
            )

        # ---------------------------------------------------------------------
        # 1. Ambiguity Guard for inherently ambiguous single terms (e.g. C, Go, R, Spring)
        # ---------------------------------------------------------------------
        ambiguous_tokens = {
            "c": ("c", "C Programming Language vs letter/concept"),
            "go": ("go", "Go Programming Language vs verb/concept"),
            "r": ("r", "R Programming Language vs letter/concept"),
            "spring": ("spring_framework", "Spring Framework vs season/concept"),
        }
        casefolded = raw_name.casefold()
        if casefolded in ambiguous_tokens:
            target_skill_id, ambig_desc = ambiguous_tokens[casefolded]
            # Check context keys and values for software disambiguation
            context_tokens = {
                str(k).casefold() for k in context.keys()
                if str(k).casefold() not in {"entity_type", "taxonomy_entity_type"}
            } | {
                str(v).casefold() for k, v in context.items()
                if str(k).casefold() not in {"entity_type", "taxonomy_entity_type"}
                and isinstance(v, (str, int))
            }
            has_code_context = bool(
                context_tokens.intersection({
                    "programming", "technology", "language", "framework",
                    "software", "tech", "skill", "developer", "code",
                }) or filter_type in ("technology", "skill")
            )

            defn = next((s for s in SKILLS if s.skill_id == target_skill_id), None)
            if defn:
                entity = self._skill_definition_to_entity(defn)
                if has_code_context:
                    return EntityResolutionResponse(
                        name=raw_name,
                        status="resolved",
                        entity=entity,
                        match_method="contextual",
                        confidence=0.92,
                        source_provenance={"disambiguated_by_context": True, "note": ambig_desc},
                    )
                # Ambiguous without context
                candidate = EntityCandidate(
                    entity=entity,
                    score=0.70,
                    match_reason=f"Plausible match to {defn.name}, but ambiguous without software context.",
                )
                return EntityResolutionResponse(
                    name=raw_name,
                    status="ambiguous",
                    candidates=[candidate],
                    confidence=0.50,
                    source_provenance={"ambiguity": ambig_desc},
                )

        requested_taxonomy = str(context.get("taxonomy") or context.get("source") or "").casefold()
        if requested_taxonomy == "esco":
            requested_type = filter_type or context.get("taxonomy_entity_type")
            esco_entity = None
            if requested_type == "occupation":
                esco_entity = self._resolve_esco_occupation(raw_name)
            elif requested_type in {"skill", "technology"}:
                esco_entity = self._resolve_esco_skill(raw_name)
            if esco_entity:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="resolved",
                    entity=esco_entity,
                    match_method="exact" if esco_entity.canonical_name.casefold() == casefolded else "normalized",
                    confidence=0.98,
                    source_provenance={"source": esco_entity.source, "concept_uri": esco_entity.source_record_id},
                )
            if requested_type in {"occupation", "skill", "technology"}:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="not_found",
                    confidence=0.0,
                    source_provenance={"source": "ref_esco_occupations" if requested_type == "occupation" else "ref_esco_skills", "reason": "No exact ESCO taxonomy entry matched."},
                )

        # ---------------------------------------------------------------------
        # 2. Canonical Registry Lookup (Skills & Technologies)
        # ---------------------------------------------------------------------
        canonical_entity = self._resolve_canonical_identifier(raw_name, filter_type)
        if canonical_entity:
            return EntityResolutionResponse(
                name=raw_name,
                status="resolved",
                entity=canonical_entity,
                match_method="exact",
                confidence=1.0,
                source_provenance={"source": canonical_entity.source, "canonical_id": canonical_entity.entity_id},
            )

        if filter_type in (None, "skill", "technology"):
            # A. Exact canonical name match
            exact_defn = next((s for s in SKILLS if s.name.casefold() == casefolded), None)
            if exact_defn:
                entity = self._skill_definition_to_entity(exact_defn)
                if filter_type is None or entity.entity_type == filter_type:
                    return EntityResolutionResponse(
                        name=raw_name,
                        status="resolved",
                        entity=entity,
                        match_method="exact",
                        confidence=1.0,
                        source_provenance={"source": "canonical_registry", "match": "exact_name"},
                    )

            # B. Registered alias match
            alias_defn = _ALIASES.get(casefolded)
            if alias_defn:
                entity = self._skill_definition_to_entity(alias_defn)
                if filter_type is None or entity.entity_type == filter_type:
                    method: EntityMatchMethod = "alias" if casefolded != alias_defn.name.casefold() else "normalized"
                    return EntityResolutionResponse(
                        name=raw_name,
                        status="resolved",
                        entity=entity,
                        match_method=method,
                        confidence=0.95 if method == "alias" else 0.98,
                        source_provenance={"source": "canonical_registry", "matched_alias": raw_name},
                    )

        # ---------------------------------------------------------------------
        # 3. O*NET Occupation Resolution
        # ---------------------------------------------------------------------
        if filter_type in (None, "occupation"):
            requested_taxonomy = str(context.get("taxonomy") or context.get("source") or "").casefold()
            if requested_taxonomy == "esco":
                esco_entity = self._resolve_esco_occupation(raw_name)
                if esco_entity:
                    return EntityResolutionResponse(
                        name=raw_name, status="resolved", entity=esco_entity,
                        match_method="exact" if esco_entity.canonical_name.casefold() == casefolded else "normalized",
                        confidence=0.98,
                        source_provenance={"source": "ref_esco_occupations", "concept_uri": esco_entity.source_record_id},
                    )
            occ_entity = self._resolve_onet_occupation(raw_name)
            if occ_entity:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="resolved",
                    entity=occ_entity,
                    match_method="exact" if occ_entity.canonical_name.casefold() == casefolded else "normalized",
                    confidence=1.0 if occ_entity.canonical_name.casefold() == casefolded else 0.95,
                    source_provenance={"source": "ref_onet_occupations", "soc_code": occ_entity.source_record_id},
                )
            esco_entity = self._resolve_esco_occupation(raw_name)
            if esco_entity:
                return EntityResolutionResponse(
                    name=raw_name, status="resolved", entity=esco_entity,
                    match_method="exact" if esco_entity.canonical_name.casefold() == casefolded else "normalized",
                    confidence=0.98,
                    source_provenance={"source": "ref_esco_occupations", "concept_uri": esco_entity.source_record_id},
                )

        # ---------------------------------------------------------------------
        # 4. O*NET Software Tool / Essential Skill Resolution (from SQLite)
        # ---------------------------------------------------------------------
        if filter_type in (None, "technology"):
            soft_entity = self._resolve_onet_software_tool(raw_name)
            if soft_entity:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="resolved",
                    entity=soft_entity,
                    match_method="exact",
                    confidence=0.90,
                    source_provenance={"source": "ref_onet_software_skills", "tool": raw_name},
                )

        if filter_type in (None, "skill"):
            ess_entity = self._resolve_onet_essential_skill(raw_name)
            if ess_entity:
                return EntityResolutionResponse(
                    name=raw_name,
                    status="resolved",
                    entity=ess_entity,
                    match_method="exact",
                    confidence=0.95,
                    source_provenance={"source": "ref_onet_essential_skills", "element": ess_entity.canonical_name},
                )
            esco_skill = self._resolve_esco_skill(raw_name)
            if esco_skill:
                return EntityResolutionResponse(
                    name=raw_name, status="resolved", entity=esco_skill,
                    match_method="exact" if esco_skill.canonical_name.casefold() == casefolded else "normalized",
                    confidence=0.95,
                    source_provenance={"source": "ref_esco_skills", "concept_uri": esco_skill.source_record_id},
                )

        # ---------------------------------------------------------------------
        # 5. Multi-Candidate Partial Match Search (Ambiguity Detection)
        # ---------------------------------------------------------------------
        candidates = self._find_candidates(raw_name, filter_type)
        if len(candidates) > 1:
            return EntityResolutionResponse(
                name=raw_name,
                status="ambiguous",
                candidates=candidates,
                confidence=0.60,
                source_provenance={"reason": f"Multiple potential matches found for '{raw_name}'."},
            )
        elif len(candidates) == 1 and candidates[0].score >= 0.85:
            return EntityResolutionResponse(
                name=raw_name,
                status="resolved",
                entity=candidates[0].entity,
                match_method="candidate_ranked",
                confidence=candidates[0].score,
                source_provenance={"reason": candidates[0].match_reason},
            )

        # ---------------------------------------------------------------------
        # 6. Not Found
        # ---------------------------------------------------------------------
        return EntityResolutionResponse(
            name=raw_name,
            status="not_found",
            confidence=0.0,
            source_provenance={"reason": f"No canonical entity found for '{raw_name}'."},
        )

    # -------------------------------------------------------------------------
    # SQLite Reference Query Helpers
    # -------------------------------------------------------------------------

    def _resolve_esco_occupation(self, text: str) -> CanonicalEntity | None:
        conn = self._connect_db()
        if not conn:
            return None
        try:
            row = conn.execute(
                "SELECT * FROM ref_esco_occupations WHERE concept_uri = ? OR lower(preferred_label) = lower(?) LIMIT 1",
                (text.strip(), text.strip()),
            ).fetchone()
            if not row:
                rows = conn.execute("SELECT * FROM ref_esco_occupations").fetchall()
                row = next((
                    item for item in rows
                    if text.casefold() in {
                        alias.strip().casefold()
                        for group in json.loads(item["alt_labels"] or "[]")
                        for alias in re.split(r"[\r\n]+", str(group))
                        if alias.strip()
                    }
                ), None)
            if row:
                aliases = [
                    alias.strip()
                    for group in json.loads(row["alt_labels"] or "[]")
                    for alias in re.split(r"[\r\n]+", str(group))
                    if alias.strip()
                ]
                return CanonicalEntity(
                    entity_id=f"occupation:esco:{row['concept_uri']}", entity_type="occupation",
                    canonical_name=row["preferred_label"], aliases=aliases,
                    category="ESCO occupation taxonomy", source="ref_esco_occupations",
                    source_record_id=row["concept_uri"], status="active",
                    metadata={"esco_uri": row["concept_uri"], "isco_group": row["isco_group"], "code": row["code"], "description": row["description"], "source_version": row["source_version"]},
                )
        except (sqlite3.OperationalError, ValueError, TypeError):
            return None
        finally:
            conn.close()
        return None

    def _resolve_esco_skill(self, text: str) -> CanonicalEntity | None:
        conn = self._connect_db()
        if not conn:
            return None
        try:
            row = conn.execute(
                "SELECT * FROM ref_esco_skills WHERE concept_uri = ? OR lower(preferred_label) = lower(?) LIMIT 1",
                (text.strip(), text.strip()),
            ).fetchone()
            if not row:
                rows = conn.execute("SELECT * FROM ref_esco_skills").fetchall()
                row = next((
                    item for item in rows
                    if text.casefold() in {
                        alias.strip().casefold()
                        for group in json.loads(item["alt_labels"] or "[]")
                        for alias in re.split(r"[\r\n]+", str(group))
                        if alias.strip()
                    }
                ), None)
            if row:
                aliases = [
                    alias.strip()
                    for group in json.loads(row["alt_labels"] or "[]")
                    for alias in re.split(r"[\r\n]+", str(group))
                    if alias.strip()
                ]
                return CanonicalEntity(
                    entity_id=f"skill:esco:{row['concept_uri']}", entity_type="skill",
                    canonical_name=row["preferred_label"], aliases=aliases,
                    category=row["skill_type"] or "ESCO skill taxonomy", source="ref_esco_skills",
                    source_record_id=row["concept_uri"], status="active",
                    metadata={"esco_uri": row["concept_uri"], "reuse_level": row["reuse_level"], "description": row["description"], "source_version": row["source_version"]},
                )
        except (sqlite3.OperationalError, ValueError, TypeError):
            return None
        finally:
            conn.close()
        return None

    def _resolve_onet_occupation(self, text: str) -> CanonicalEntity | None:
        conn = self._connect_db()
        if not conn:
            return None
        try:
            # Check by exact SOC code first
            row = conn.execute(
                "SELECT * FROM ref_onet_occupations WHERE soc_code = ? LIMIT 1",
                (text.strip(),),
            ).fetchone()
            if not row:
                clean_t = text.strip()
                if clean_t.lower() in {"software development", "software engineering", "software dev"}:
                    clean_t = "Software Developers"
                t_plural = clean_t if clean_t.endswith("s") else f"{clean_t}s"
                t_singular = clean_t[:-1] if clean_t.endswith("s") else clean_t
                row = conn.execute(
                    "SELECT * FROM ref_onet_occupations WHERE lower(title) IN (lower(?), lower(?), lower(?)) LIMIT 1",
                    (clean_t, t_plural, t_singular),
                ).fetchone()
            if row:
                return CanonicalEntity(
                    entity_id=f"occupation:soc:{row['soc_code']}",
                    entity_type="occupation",
                    canonical_name=row["title"],
                    aliases=[],
                    category="Standard Occupational Classification",
                    source="ref_onet_occupations",
                    source_record_id=row["soc_code"],
                    status="active",
                    metadata={"soc_code": row["soc_code"], "description": row["description"]},
                )
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        return None

    def _resolve_onet_software_tool(self, text: str) -> CanonicalEntity | None:
        conn = self._connect_db()
        if not conn:
            return None
        try:
            row = conn.execute(
                """
                SELECT workplace_example, element_id, element_name, hot_technology, in_demand, canonical_skill_id
                FROM ref_onet_software_skills
                WHERE lower(workplace_example) = lower(?)
                LIMIT 1
                """,
                (text.strip(),),
            ).fetchone()
            if row:
                # If mapped to canonical skill, return canonical
                if row["canonical_skill_id"]:
                    defn = next((s for s in SKILLS if s.skill_id == row["canonical_skill_id"]), None)
                    if defn:
                        return self._skill_definition_to_entity(defn)

                # Otherwise return O*NET software entity
                tool_hash = hashlib.sha256(row["workplace_example"].casefold().encode("utf-8")).hexdigest()[:12]
                return CanonicalEntity(
                    entity_id=f"tech:onet:{row['element_id']}:{tool_hash}",
                    entity_type="technology",
                    canonical_name=row["workplace_example"],
                    aliases=[],
                    category=row["element_name"],
                    source="ref_onet_software_skills",
                    source_record_id=row["element_id"],
                    status="active",
                    metadata={
                        "element_name": row["element_name"],
                        "hot_technology": bool(row["hot_technology"]),
                        "in_demand": bool(row["in_demand"]),
                    },
                )
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        return None

    def _resolve_onet_essential_skill(self, text: str) -> CanonicalEntity | None:
        conn = self._connect_db()
        if not conn:
            return None
        try:
            row = conn.execute(
                """
                SELECT element_id, element_name
                FROM ref_onet_essential_skills
                WHERE lower(element_name) = lower(?)
                LIMIT 1
                """,
                (text.strip(),),
            ).fetchone()
            if row:
                return CanonicalEntity(
                    entity_id=f"skill:onet:{row['element_id']}",
                    entity_type="skill",
                    canonical_name=row["element_name"],
                    aliases=[],
                    category="O*NET Basic Skills",
                    source="ref_onet_essential_skills",
                    source_record_id=row["element_id"],
                    status="active",
                    metadata={"element_id": row["element_id"]},
                )
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        return None

    def _find_candidates(self, query: str, filter_type: EntityType | None) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        q_lower = query.casefold()

        # 1. Search canonical skills
        if filter_type in (None, "skill", "technology"):
            for defn in SKILLS:
                entity = self._skill_definition_to_entity(defn)
                if filter_type and entity.entity_type != filter_type:
                    continue
                # Prefix match
                if defn.name.casefold().startswith(q_lower):
                    candidates.append(EntityCandidate(
                        entity=entity,
                        score=0.85,
                        match_reason=f"Prefix match on canonical name '{defn.name}'.",
                    ))
                elif any(a.casefold().startswith(q_lower) for a in defn.aliases):
                    candidates.append(EntityCandidate(
                        entity=entity,
                        score=0.75,
                        match_reason=f"Prefix match on alias in '{defn.name}'.",
                    ))

        # 2. Search occupations if type matches
        if filter_type in (None, "occupation"):
            conn = self._connect_db()
            if conn:
                try:
                    rows = conn.execute(
                        "SELECT soc_code, title, description FROM ref_onet_occupations WHERE lower(title) LIKE ? LIMIT 5",
                        (f"{q_lower}%",),
                    ).fetchall()
                    for r in rows:
                        occ_entity = CanonicalEntity(
                            entity_id=f"occupation:soc:{r['soc_code']}",
                            entity_type="occupation",
                            canonical_name=r["title"],
                            source="ref_onet_occupations",
                            source_record_id=r["soc_code"],
                            status="active",
                            metadata={"soc_code": r["soc_code"], "description": r["description"]},
                        )
                        candidates.append(EntityCandidate(
                            entity=occ_entity,
                            score=0.80,
                            match_reason=f"Title prefix match on occupation '{r['title']}'.",
                        ))
                except sqlite3.OperationalError:
                    pass
                finally:
                    conn.close()

        # Deduplicate and sort by score descending
        seen_ids = set()
        unique_candidates = []
        for c in sorted(candidates, key=lambda x: x.score, reverse=True):
            if c.entity.entity_id not in seen_ids:
                seen_ids.add(c.entity.entity_id)
                unique_candidates.append(c)

        return unique_candidates[:5]

    # -------------------------------------------------------------------------
    # Relationship Graph Queries
    # -------------------------------------------------------------------------

    def get_occupation_skills(self, soc_code: str, *, limit: int = 50) -> list[CanonicalEntity]:
        """Retrieve technologies and competencies linked to an occupation."""
        conn = self._connect_db()
        if not conn:
            return []
        entities: list[CanonicalEntity] = []
        try:
            # 1. Software skills
            rows = conn.execute(
                """
                SELECT workplace_example, element_id, element_name, hot_technology, in_demand, canonical_skill_id
                FROM ref_onet_software_skills
                WHERE soc_code = ?
                ORDER BY hot_technology DESC, in_demand DESC
                LIMIT ?
                """,
                (soc_code.strip(), limit),
            ).fetchall()
            for r in rows:
                if r["canonical_skill_id"]:
                    defn = next((s for s in SKILLS if s.skill_id == r["canonical_skill_id"]), None)
                    if defn:
                        entities.append(self._skill_definition_to_entity(defn))
                        continue
                tool_hash = hashlib.sha256(r["workplace_example"].casefold().encode("utf-8")).hexdigest()[:12]
                entities.append(CanonicalEntity(
                    entity_id=f"tech:onet:{r['element_id']}:{tool_hash}",
                    entity_type="technology",
                    canonical_name=r["workplace_example"],
                    category=r["element_name"],
                    source="ref_onet_software_skills",
                    source_record_id=r["element_id"],
                    metadata={
                        "element_name": r["element_name"],
                        "hot_technology": bool(r["hot_technology"]),
                        "in_demand": bool(r["in_demand"]),
                    },
                ))
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        return entities

    def get_esco_occupation_skills(self, occupation_uri: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return ESCO taxonomy relations without mapping them to O*NET skills."""
        try:
            from app.storage.reference_store import ReferenceDataStore
            return ReferenceDataStore(self.db_path, read_only=True).get_esco_occupation_skills(occupation_uri, limit=limit)
        except (OSError, sqlite3.Error):
            return []

    def get_related_occupations(self, soc_code: str) -> list[CanonicalEntity]:
        """Retrieve crosswalk occupations linked to a given occupation."""
        conn = self._connect_db()
        if not conn:
            return []
        entities: list[CanonicalEntity] = []
        try:
            rows = conn.execute(
                """
                SELECT related_soc_code, related_title, relatedness_tier, sort_index
                FROM ref_onet_related_occupations
                WHERE soc_code = ?
                ORDER BY sort_index ASC
                """,
                (soc_code.strip(),),
            ).fetchall()
            for r in rows:
                entities.append(CanonicalEntity(
                    entity_id=f"occupation:soc:{r['related_soc_code']}",
                    entity_type="occupation",
                    canonical_name=r["related_title"],
                    category=r["relatedness_tier"],
                    source="ref_onet_related_occupations",
                    source_record_id=r["related_soc_code"],
                    metadata={
                        "soc_code": r["related_soc_code"],
                        "relatedness_tier": r["relatedness_tier"],
                        "sort_index": r["sort_index"],
                    },
                ))
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
        return entities

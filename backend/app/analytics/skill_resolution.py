"""Provenance-aware deterministic matching for local taxonomy skill labels."""

from __future__ import annotations

import json
from typing import Any

from app.analytics.skill_registry import BY_ID, normalize_skill_entry


def normalize_label(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9+#]+", " ", value.casefold()).strip()


# Reviewed product short form, intentionally scoped to the O*NET software
# technology label. It does not equate Excel with ESCO's broader spreadsheet
# skills and therefore cannot create cross-taxonomy links.
CURATED_ALIASES: dict[tuple[str, str], dict[str, str]] = {
    ("onet", "microsoft excel"): {
        "alias": "excel",
        "source": "phase15_curated_alias_registry",
        "rationale": "Excel is a common short name for the Microsoft Excel product; scoped to the exact O*NET technology label.",
    },
    ("esco", "use spreadsheets software"): {
        "alias": "excel",
        "source": "phase15_curated_alias_registry",
        "rationale": "Excel is a spreadsheet-software product; a self-report of Excel is mapped to the ESCO spreadsheet-software skill as a curated, lower-confidence association, not verified proficiency.",
    },
}


def _identity(row: dict[str, Any]) -> str:
    return str(
        row.get("skill_uri") or row.get("concept_uri") or row.get("element_id")
        or row.get("taxonomy_id") or row.get("id") or normalize_label(str(row.get("label") or row.get("preferred_label") or row.get("name") or ""))
    )


def _label(row: dict[str, Any]) -> str:
    return str(row.get("preferred_label") or row.get("skill_label") or row.get("element_name") or row.get("workplace_example") or row.get("name") or row.get("title") or "").strip()


def _aliases(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def resolve_user_skill(raw_text: str, reference_skills: list[dict[str, Any]], taxonomy: str) -> dict[str, Any]:
    """Resolve in strict evidence order; ambiguity is explicit and never guessed."""
    raw = " ".join(str(raw_text or "").split())
    taxonomy = taxonomy.casefold()
    rows = [{**row, "label": _label(row)} for row in reference_skills if _label(row)]
    stages: list[tuple[str, str, list[dict[str, Any]], float, str | None, str | None]] = []

    # 1. Exact taxonomy identity.
    exact_ids = [row for row in rows if raw == _identity(row)]
    stages.append(("exact_match", "exact_taxonomy_identifier", exact_ids, 1.0, None, None))
    # 2. Exact preferred/source label.
    key = normalize_label(raw)
    exact_labels = [row for row in rows if normalize_label(row["label"]) == key]
    stages.append(("exact_match", "exact_preferred_label", exact_labels, 1.0, None, None))
    # 3. Source-provided official taxonomy alternate labels.
    official = [row for row in rows if any(normalize_label(alias) == key for alias in _aliases(row.get("alt_labels")))]
    stages.append(("official_alias_match", "official_alternate_label", official, 0.98, "taxonomy_import", "Official alternate label from the imported taxonomy record."))
    # 4. Existing canonical registry aliases, only when the taxonomy's actual
    # label independently resolves to that registry identity.
    registry_matches = []
    registry_sources: dict[str, dict[str, str]] = {}
    for row in rows:
        entry = normalize_skill_entry(row["label"])
        definition = BY_ID.get(entry.canonical_skill_id or "")
        if not definition or definition.ambiguous:
            continue
        if any(normalize_label(alias) == key for alias in (definition.name, *definition.aliases)):
            registry_matches.append(row)
            registry_sources[_identity(row)] = {
                "source": "canonical_skill_registry",
                "rationale": f"Registered alias for {definition.name}; linked only because this taxonomy reference label independently resolves to that canonical registry entry.",
            }
    stages.append(("official_alias_match", "canonical_registry_alias", registry_matches, 0.95, "canonical_skill_registry", "Registered alias anchored to an exact taxonomy label."))
    # 5. Curated, explicit and taxonomy-scoped aliases.
    curated_matches = []
    curated_meta: dict[str, dict[str, str]] = {}
    for row in rows:
        entry = CURATED_ALIASES.get((taxonomy, normalize_label(row["label"])))
        if entry and normalize_label(entry["alias"]) == key:
            curated_matches.append(row)
            curated_meta[_identity(row)] = entry
    stages.append(("curated_alias_match", "curated_alias", curated_matches, 0.90, "phase15_curated_alias_registry", "Curated alias with recorded rationale."))

    for status, method, candidates, confidence, source, rationale in stages:
        if not candidates:
            continue
        by_id = {_identity(row): row for row in candidates}
        if len(by_id) != 1:
            return {
                "original_text": raw, "status": "ambiguous", "match_method": method,
                "confidence": None, "taxonomy": taxonomy,
                "candidates": [{"display_label": row["label"], "taxonomy_id": _identity(row), "source": row.get("source")} for row in by_id.values()],
            }
        row = next(iter(by_id.values()))
        match_source = source
        match_rationale = rationale
        if method == "canonical_registry_alias":
            meta = registry_sources[_identity(row)]
            match_source, match_rationale = meta["source"], meta["rationale"]
        elif method == "curated_alias":
            meta = curated_meta[_identity(row)]
            match_source, match_rationale = meta["source"], meta["rationale"]
        return {
            "original_text": raw, "resolved_label": row["label"], "taxonomy": taxonomy,
            "taxonomy_id": _identity(row), "status": status, "match_method": method,
            "source": row.get("source") or match_source or f"ref_{taxonomy}_occupation_skill_records",
            "provenance": match_source or row.get("source") or f"ref_{taxonomy}_occupation_skill_records",
            "rationale": match_rationale or "Input exactly matches the preferred label in the selected taxonomy.",
            "confidence": confidence,
        }
    return {"original_text": raw, "status": "unmatched", "taxonomy": taxonomy, "match_method": "no_supported_label_or_alias", "confidence": None}

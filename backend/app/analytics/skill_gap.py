"""Deterministic comparisons between self-reported skills and local taxonomies."""

from __future__ import annotations

import json
import re
from typing import Any

from app.analytics.skill_resolution import resolve_user_skill


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", value.casefold()).strip()


def calculate_skill_gap(
    *, taxonomy: str, occupation: dict[str, Any], reference_skills: list[dict[str, Any]],
    user_skills: list[str],
) -> dict[str, Any]:
    """Match only unambiguous taxonomy labels/aliases; never equate taxonomy IDs."""
    taxonomy = taxonomy.casefold()
    by_label: dict[str, list[dict[str, Any]]] = {}
    for row in reference_skills:
        label = str(row.get("preferred_label") or row.get("skill_label") or row.get("element_name") or row.get("workplace_example") or row.get("title") or row.get("name") or "").strip()
        if not label:
            continue
        item = {**row, "label": label}
        by_label.setdefault(normalize_label(label), []).append(item)

    distinct = {}
    for values in by_label.values():
        for item in values:
            identity = str(item.get("skill_uri") or item.get("concept_uri") or item.get("element_id") or item.get("id") or normalize_label(item["label"]))
            current = distinct.get(identity)
            if current is None or (
                str(item.get("relation_type") or "").casefold() == "essential"
                and str(current.get("relation_type") or "").casefold() != "essential"
            ):
                distinct[identity] = item
    ref_rows = list(distinct.values())
    supplied: dict[str, str] = {}
    for raw in user_skills:
        if isinstance(raw, str) and raw.strip():
            supplied.setdefault(normalize_label(raw), raw.strip())
    matched, unmatched_user, unresolved = [], [], []
    matched_ids: set[str] = set()
    for key, raw in supplied.items():
        resolution = resolve_user_skill(raw, ref_rows, taxonomy)
        if resolution["status"] in {"exact_match", "official_alias_match", "curated_alias_match"}:
            matched_ids.add(resolution["taxonomy_id"])
            matched.append({"user_text": raw, "label": resolution["resolved_label"], **resolution})
        elif resolution["status"] == "ambiguous":
            unresolved.append(resolution)
        else:
            unmatched_user.append(resolution)

    missing = []
    for item in ref_rows:
        identity = str(item.get("skill_uri") or item.get("concept_uri") or item.get("element_id") or item.get("id") or normalize_label(item["label"]))
        if identity in matched_ids:
            continue
        relation = str(item.get("relation_type") or "").casefold()
        classification = relation if relation in {"essential", "optional"} else None
        missing.append({
            "label": item["label"], "taxonomy_id": identity, "taxonomy": taxonomy,
            "source": item.get("source"),
            "classification": classification,
            "source_record_id": identity,
            "priority_rationale": "Source classifies this relationship as essential." if classification == "essential" else (
                "Source classifies this relationship as optional." if classification == "optional" else
                "No source-defined essential/optional ranking is available; listed as an unranked reference gap."
            ),
        })
    return {
        "taxonomy": taxonomy, "occupation": occupation, "reference_count": len(ref_rows),
        "matched": matched, "matched_reference_count": len(matched_ids), "missing": missing,
        "unmatched_user": unmatched_user, "unresolved_user": unresolved,
        "coverage": (len(matched_ids) / len(ref_rows)) if ref_rows else None,
        "coverage_formula": "distinct matched reference skill identities / distinct applicable reference skill identities",
        "proficiency_note": "User skill labels are self-reported; mentioning a skill does not verify proficiency.",
    }

"""Deterministic, evidence-preserving skill matching for stored job text.

This intentionally does not infer proficiency or requiredness. Exact phrases
are matched against the canonical registry and the locally imported ESCO/O*NET
reference labels; unmatched phrases are not promoted to canonical skills.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.analytics.skill_registry import BY_ID, extract_skills, normalize_skill_entry
from app.analytics.skill_resolution import CURATED_ALIASES


_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.]*")


def _normalize_phrase(value: str) -> str:
    value = value.casefold().replace("\u2019", "'")
    return " ".join(re.findall(r"[a-z0-9]+(?:[+#]+|\.[a-z0-9]+)?", value))


@lru_cache(maxsize=8)
def _reference_rows(database_path: str) -> tuple[dict[str, Any], ...]:
    # Imported lazily to keep the pure registry extractor usable without a DB.
    from app.storage.reference_store import ReferenceDataStore

    store = ReferenceDataStore(database_path, read_only=True)
    return tuple(store.get_reference_skill_rows())


def _scan_windows(
    text: str,
    tokens: list[re.Match[str]],
    index: dict[str, list[dict[str, Any]]],
    max_words: int,
) -> list[tuple[str, int, int]]:
    found: dict[str, tuple[int, int]] = {}
    for start_idx, start_token in enumerate(tokens):
        for width in range(1, min(max_words, len(tokens) - start_idx) + 1):
            end_token = tokens[start_idx + width - 1]
            candidate = text[start_token.start():end_token.end()]
            key = _normalize_phrase(candidate)
            if key in index and key not in found:
                found[key] = (start_token.start(), end_token.end())
    ordered = sorted(((key, *span) for key, span in found.items()), key=lambda item: (item[1], -(item[2] - item[1])))
    selected: list[tuple[str, int, int]] = []
    for candidate in ordered:
        _key, start, end = candidate
        if any(existing_start <= start and end <= existing_end for _existing_key, existing_start, existing_end in selected):
            continue
        selected.append(candidate)
    return selected


def match_job_text(
    text: str,
    *,
    reference_store: Any | None = None,
    _reference_data: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Match exact taxonomy phrases and include the supporting text excerpt."""
    if not isinstance(text, str) or not text.strip():
        return []

    registry_names = extract_skills(text)
    registry_index = {
        _normalize_phrase(name): [{"name": name, "source": "canonical_registry"}]
        for name in registry_names
    }
    combined = dict(registry_index)
    reference_rows = _reference_data or []
    if _reference_data is None and reference_store is not None:
        try:
            database_path = getattr(reference_store, "database_path", None)
            reference_rows = (
                list(_reference_rows(str(database_path)))
                if database_path
                else reference_store.get_reference_skill_rows()
            )
        except (OSError, RuntimeError, ValueError):
            reference_rows = []

    # Index just the labels returned by the configured local reference store.
    for row in reference_rows:
        if not isinstance(row, dict):
            continue
        label = " ".join(str(row.get("name") or "").split())
        if not label or (len(label) < 3 and not any(char in label for char in "+#")):
            continue
        aliases = row.get("aliases") or []
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except (TypeError, ValueError):
                aliases = []
        alias_records = [(label, "exact_preferred_label", row.get("source"), "Exact imported taxonomy label.")]
        alias_records.extend((str(alias), "official_alternate_label", "taxonomy_import", "Official alternate label from the imported taxonomy record.") for alias in (aliases if isinstance(aliases, list) else []))
        taxonomy = "esco" if str(row.get("source")) == "esco" else "onet"
        curated = CURATED_ALIASES.get((taxonomy, _normalize_phrase(label)))
        if curated:
            alias_records.append((curated["alias"], "curated_alias", curated["source"], curated["rationale"]))
        registry = normalize_skill_entry(label)
        registry_definition = BY_ID.get(registry.canonical_skill_id or "")
        if registry_definition and not registry_definition.ambiguous:
            alias_records.extend((alias, "canonical_registry_alias", "canonical_skill_registry", f"Registered alias for {registry_definition.name}; anchored to this exact taxonomy label.") for alias in registry_definition.aliases)
        for candidate, method, alias_source, alias_rationale in alias_records:
            key = _normalize_phrase(str(candidate))
            if key:
                combined.setdefault(key, []).append({
                    **row, "matched_label": str(candidate), "match_method": method,
                    "match_provenance": alias_source, "match_rationale": alias_rationale,
                })

    tokens = list(_TOKEN_RE.finditer(text))
    max_words = max((len(key.split()) for key in combined), default=1)
    hits = _scan_windows(text, tokens, combined, max_words)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, start, end in sorted(hits, key=lambda item: (item[1], -(item[2] - item[1]))):
        if key in seen:
            continue
        seen.add(key)
        records = combined[key]
        matched_text = text[start:end]
        # Prefer canonical registry identities; otherwise preserve the source
        # taxonomy identity without asserting a cross-taxonomy equivalence.
        canonical = normalize_skill_entry(matched_text)
        canonical_definition = BY_ID.get(canonical.canonical_skill_id or "")
        if canonical.is_known and canonical_definition and not canonical_definition.ambiguous:
            selected = next((r for r in records if r.get("source") == "canonical_registry"), records[0])
            mapping_status = "canonical_registry"
            entity_id = f"skill:{canonical.canonical_skill_id}"
        else:
            identities = {
                (str(item.get("source") or ""), str(item.get("taxonomy_id") or item.get("matched_label") or ""))
                for item in records
            }
            if len(identities) > 1:
                selected = records[0]
                mapping_status = "ambiguous"
                entity_id = None
            else:
                selected = records[0]
                source = str(selected.get("source") or "")
                method = selected.get("match_method") or "exact_preferred_label"
                mapping_status = "esco_exact" if source == "esco" and method == "exact_preferred_label" else (
                    "onet_exact" if source.startswith("onet") and method == "exact_preferred_label" else method
                )
                entity_id = f"skill:esco:{selected.get('taxonomy_id')}" if source == "esco" and selected.get("taxonomy_id") else None
        method = selected.get("match_method") or ("canonical_registry_exact" if mapping_status == "canonical_registry" else "ambiguous_candidates" if mapping_status == "ambiguous" else "exact_preferred_label")
        results.append({
            "candidate": matched_text,
            "normalized_name": canonical.canonical_name if canonical.is_known else str(selected.get("name") or matched_text),
            "canonical_skill_id": canonical.canonical_skill_id if canonical.is_known else None,
            "entity_id": entity_id,
            "mapping_status": mapping_status,
            "match_method": method,
            "match_status": "ambiguous" if mapping_status == "ambiguous" else "matched",
            "match_confidence": None if mapping_status == "ambiguous" else (0.90 if method == "curated_alias" else 0.98 if method in {"official_alternate_label", "canonical_registry_alias"} else 1.0),
            "match_provenance": selected.get("match_provenance") or selected.get("source") or ("canonical_skill_registry" if mapping_status == "canonical_registry" else None),
            "match_rationale": selected.get("match_rationale"),
            "reference_source": selected.get("source"),
            "taxonomy_id": selected.get("taxonomy_id"),
            "supporting_text": text[max(0, start - 80):min(len(text), end + 80)],
            "match_start": start,
            "match_end": end,
        })
    return results


def extract_posting_skills(posting: dict[str, Any], *, reference_store: Any | None = None) -> list[dict[str, Any]]:
    """Extract and deduplicate per-posting skills while retaining text provenance."""
    fields: list[tuple[str, str]] = []
    if isinstance(posting.get("title"), str):
        fields.append(("title", posting["title"]))
    if isinstance(posting.get("description"), str):
        fields.append(("description", posting["description"]))
    raw = posting.get("skills_raw")
    if isinstance(raw, list):
        fields.extend(("provider_skills", value) for value in raw if isinstance(value, str))

    reference_data: list[dict[str, Any]] = []
    if reference_store is not None:
        try:
            database_path = getattr(reference_store, "database_path", None)
            reference_data = (
                list(_reference_rows(str(database_path)))
                if database_path
                else reference_store.get_reference_skill_rows()
            )
        except (OSError, RuntimeError, ValueError):
            reference_data = []

    by_identity: dict[str, dict[str, Any]] = {}
    for field, text in fields:
        matches = match_job_text(text, _reference_data=reference_data)
        if field == "provider_skills" and not matches and text.strip():
            candidate = " ".join(text.split())
            matches = [{
                "candidate": candidate,
                "normalized_name": candidate,
                "canonical_skill_id": None,
                "entity_id": None,
                "mapping_status": "unmatched",
                "reference_source": None,
                "taxonomy_id": None,
                "supporting_text": candidate,
                "match_start": 0,
                "match_end": len(candidate),
            }]
        for match in matches:
            identity = match.get("entity_id") or f"text:{_normalize_phrase(match['normalized_name'])}"
            item = by_identity.setdefault(identity, {
                **match,
                "evidence": [],
            })
            evidence = {
                "field": field,
                "observed_text": match["candidate"],
                "supporting_text": match["supporting_text"],
            }
            if evidence not in item["evidence"]:
                item["evidence"].append(evidence)
    return list(by_identity.values())

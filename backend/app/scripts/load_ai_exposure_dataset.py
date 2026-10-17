"""Offline candidate validator for a future approved AI task-exposure dataset.

Purpose:
- Validates a candidate payload against an independently maintained dataset registry and schema.
- Keeps all candidates blocked while that registry has no approved dataset identities.
- Never treats payload self-attestation as independent license, methodology, or mapping verification.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from app.analytics.ai_disruption import AIExposureDatasetProvenance, TaskExposureRecord
from app.analytics.skill_registry import BY_ID

APPROVED_OPEN_LICENSES = {
    "CC-BY-4.0",
    "CC0-1.0",
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "ODC-By-1.0",
}
# Entries may be added only after independent review of source, license, methodology,
# version, and occupation/task/skill mappings. None is approved yet.
APPROVED_DATASET_REGISTRY: dict[str, dict[str, str]] = {}
REQUIRED_RECORD_FIELDS = {
    "task_id", "task_statement", "occupation_code", "occupation_title",
    "canonical_occupation_id", "task_exposure_level", "evidence_rationale",
}
SUPPORTED_EXPOSURE_LEVELS = {"low", "moderate", "high", "unknown"}
SUPPORTED_USAGE_MODES = {"augmentation", "automation", "mixed", "unobserved"}


def _valid_iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def verify_and_parse_ai_exposure_dataset(
    payload: dict[str, Any],
) -> tuple[AIExposureDatasetProvenance, list[TaskExposureRecord]]:
    """Validate a candidate; parse records only when a matching approved registry entry exists."""
    meta = payload.get("metadata") or {}
    explicit_dataset_id = str(meta.get("dataset_id") or "").strip() or None
    dataset_id = explicit_dataset_id or "external_ai_exposure_reference"
    dataset_name = str(meta.get("dataset_name") or "External AI Exposure Dataset").strip()
    provider = str(meta.get("provider") or "unknown").strip()
    license_name = str(meta.get("license") or "").strip() or None
    version = str(meta.get("version") or "").strip() or None
    source_url = str(meta.get("source_url") or "").strip() or None
    records_raw: Sequence[dict[str, Any]] = payload.get("records") or []

    approved = APPROVED_DATASET_REGISTRY.get(dataset_id)
    license_ok = bool(
        approved
        and license_name in APPROVED_OPEN_LICENSES
        and license_name == approved.get("license")
        and version == approved.get("version")
        and source_url == approved.get("source_url")
    )
    permitted_use = license_ok and approved.get("permitted_use") == "verified" if approved else False
    methodology_verified = bool(
        approved
        and meta.get("methodology_id") == approved.get("methodology_id")
    )
    dataset_evidence_date = meta.get("evidence_date") or meta.get("version_date")
    fields_ok = bool(records_raw) and all(
        REQUIRED_RECORD_FIELDS.issubset(set(record.keys()))
        and str(record.get("task_exposure_level") or "").strip().lower()
        in SUPPORTED_EXPOSURE_LEVELS
        and str(record.get("observed_ai_usage_mode") or "unobserved").strip().lower()
        in SUPPORTED_USAGE_MODES
        and _valid_iso_date(record.get("evidence_date") or dataset_evidence_date)
        and bool(
            record.get("evidence_url")
            or record.get("source_url")
            or record.get("evidence_source_id")
            or record.get("evidence_id")
        )
        and str(record.get("evidence_strength") or "unknown").strip().lower()
        in {"high", "moderate", "low", "unknown"}
        and bool(str(record.get("evidence_rationale") or "").strip())
        and all(str(skill_id) in BY_ID for skill_id in (record.get("canonical_skill_ids") or []))
        and record.get("canonical_occupation_id")
        == f"occupation:soc:{record.get('occupation_code')}"
        for record in records_raw
    )

    blocker_reasons: list[str] = []
    if not approved:
        blocker_reasons.append(
            "Dataset identity, source, license, methodology, and mappings are not independently approved for runtime use."
        )
    if not permitted_use:
        blocker_reasons.append(
            "Dataset commercial or academic use is not verified by an approved registry entry."
        )
    if not methodology_verified:
        blocker_reasons.append(
            "The payload methodology does not match an independently approved methodology."
        )
    if not fields_ok:
        blocker_reasons.append(
            "Records are empty, missing required schema fields, contain unsupported categories, "
            "or lack a valid evidence date/reference."
        )

    prov = AIExposureDatasetProvenance(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        provider=provider,
        license_name=license_name,
        license_verified=license_ok,
        permitted_commercial_or_academic_use=permitted_use,
        version=version,
        source_url=source_url,
        required_fields_present=fields_ok,
        blocker_reason=" ".join(blocker_reasons) if blocker_reasons else None,
    )

    if blocker_reasons:
        return prov, []

    parsed: list[TaskExposureRecord] = []
    for record in records_raw:
        exposure_level = str(record["task_exposure_level"]).strip().lower()
        usage_mode = str(record.get("observed_ai_usage_mode") or "unobserved").strip().lower()
        evidence_url = (
            record.get("evidence_url")
            or record.get("source_url")
            or source_url
        )
        parsed.append(TaskExposureRecord(
            task_id=str(record["task_id"]),
            task_statement=str(record["task_statement"]),
            occupation_code=str(record["occupation_code"]),
            occupation_title=str(record["occupation_title"]),
            canonical_occupation_id=str(record["canonical_occupation_id"]),
            canonical_skill_ids=[str(skill_id) for skill_id in (record.get("canonical_skill_ids") or [])],
            task_exposure_level=exposure_level,  # type: ignore[arg-type]
            observed_ai_usage_mode=usage_mode,  # type: ignore[arg-type]
            human_oversight_required=bool(record.get("human_oversight_required", True)),
            evidence_source=f"{dataset_name} ({version})",
            evidence_source_id=str(record.get("evidence_source_id") or record.get("evidence_id") or dataset_id),
            evidence_url=str(evidence_url) if evidence_url else None,
            evidence_date=date.fromisoformat(str(record.get("evidence_date") or dataset_evidence_date)),
            evidence_rationale=str(record["evidence_rationale"]).strip(),
            evidence_strength=str(record.get("evidence_strength") or "unknown").strip().lower(),  # type: ignore[arg-type]
            uncertainty_note=str(record.get("uncertainty_note") or "").strip() or None,
        ))

    return prov, parsed


def run_loader(input_path: Path | None = None, *, dry_run: bool = True) -> dict[str, Any]:
    if input_path is None or not input_path.exists():
        return {
            "status": "blocked",
            "dry_run": dry_run,
            "loaded_count": 0,
            "blocker_reason": (
                "No approved AI task-exposure reference dataset is present in the repository. "
                "Ingestion remains blocked until its identity, source methodology, license, and mappings are independently verified."
            ),
        }
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    prov, records = verify_and_parse_ai_exposure_dataset(payload)
    if prov.blocker_reason:
        return {
            "status": "blocked",
            "dry_run": dry_run,
            "loaded_count": 0,
            "provenance": prov.model_dump(),
            "blocker_reason": prov.blocker_reason,
        }
    return {
        "status": "ready",
        "dry_run": dry_run,
        "loaded_count": len(records),
        "provenance": prov.model_dump(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline licensed AI-exposure dataset loader.")
    parser.add_argument("--input", type=Path, default=None, help="Path to licensed AI-exposure JSON file.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Validate without writing to Firestore.")
    args = parser.parse_args()
    print(json.dumps(run_loader(args.input, dry_run=args.dry_run), indent=2))

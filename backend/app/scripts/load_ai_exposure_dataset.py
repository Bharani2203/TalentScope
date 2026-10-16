"""Offline Loader 4: Licensed AI-Exposure Reference Dataset Loader (Idempotent & Dry-Run Capable).

Purpose:
- Verifies dataset license, provenance, permitted use, and required schema fields before
  accepting any external AI task exposure records.
- If the dataset is missing, lacks an explicit open/permitted license, or omits required
  task/occupation fields, returns `status="blocked"` with an explicit blocker report and
  never fabricates task exposure scores.
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
REQUIRED_RECORD_FIELDS = {
    "task_id", "task_statement", "occupation_code", "occupation_title", "task_exposure_level",
    "evidence_rationale",
}


def _valid_iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def verify_and_parse_ai_exposure_dataset(
    payload: dict[str, Any],
) -> tuple[AIExposureDatasetProvenance, list[TaskExposureRecord]]:
    """Verify dataset provenance/license and parse TaskExposureRecord items if permitted."""
    meta = payload.get("metadata") or {}
    explicit_dataset_id = str(meta.get("dataset_id") or "").strip() or None
    dataset_id = explicit_dataset_id or "external_ai_exposure_reference"
    dataset_name = str(meta.get("dataset_name") or "External AI Exposure Dataset").strip()
    provider = str(meta.get("provider") or "unknown").strip()
    license_name = str(meta.get("license") or "").strip() or None
    version = str(meta.get("version") or "").strip() or None
    source_url = str(meta.get("source_url") or "").strip() or None
    records_raw: Sequence[dict[str, Any]] = payload.get("records") or []

    license_ok = license_name in APPROVED_OPEN_LICENSES
    permitted_use = bool(meta.get("permitted_use_verified", False)) and license_ok
    dataset_evidence_date = meta.get("evidence_date") or meta.get("version_date")
    fields_ok = bool(records_raw) and all(
        REQUIRED_RECORD_FIELDS.issubset(set(record.keys()))
        and _valid_iso_date(record.get("evidence_date") or dataset_evidence_date)
        and bool(
            record.get("evidence_url")
            or record.get("source_url")
            or source_url
            or record.get("evidence_source_id")
            or record.get("evidence_id")
            or explicit_dataset_id
        )
        and str(record.get("evidence_strength") or "unknown").strip().lower()
        in {"high", "moderate", "low", "unknown"}
        and bool(str(record.get("evidence_rationale") or "").strip())
        and all(str(skill_id) in BY_ID for skill_id in (record.get("canonical_skill_ids") or []))
        and (
            not record.get("canonical_occupation_id")
            or record["canonical_occupation_id"] == f"occupation:soc:{record.get('occupation_code')}"
        )
        for record in records_raw
    )

    blocker_reasons: list[str] = []
    if not license_ok:
        blocker_reasons.append(
            f"Dataset license '{license_name or 'unspecified'}' is not in approved open licenses ({sorted(APPROVED_OPEN_LICENSES)})."
        )
    if not permitted_use:
        blocker_reasons.append("Explicit permitted use verification flag ('permitted_use_verified') is missing or False.")
    if not fields_ok:
        blocker_reasons.append(
            "Records are empty, missing required schema fields, or lack a valid evidence date/reference."
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
    for r in records_raw:
        exp_lvl = str(r.get("task_exposure_level") or "unknown").strip().lower()
        if exp_lvl not in ("low", "moderate", "high", "unknown"):
            exp_lvl = "unknown"
        usage_mode = str(r.get("observed_ai_usage_mode") or "unobserved").strip().lower()
        if usage_mode not in ("augmentation", "automation", "mixed", "unobserved"):
            usage_mode = "unobserved"
        parsed.append(TaskExposureRecord(
            task_id=str(r["task_id"]),
            task_statement=str(r["task_statement"]),
            occupation_code=str(r["occupation_code"]),
            occupation_title=str(r["occupation_title"]),
            canonical_skill_ids=[str(s) for s in (r.get("canonical_skill_ids") or [])],
            task_exposure_level=exp_lvl,  # type: ignore[arg-type]
            observed_ai_usage_mode=usage_mode,  # type: ignore[arg-type]
            human_oversight_required=bool(r.get("human_oversight_required", True)),
            evidence_source=f"{dataset_name} ({version or 'v1'})",
            evidence_source_id=str(r.get("evidence_source_id") or r.get("evidence_id") or dataset_id),
            evidence_url=str(r.get("evidence_url") or r.get("source_url") or source_url) if (r.get("evidence_url") or r.get("source_url") or source_url) else None,
            evidence_date=date.fromisoformat(str(r.get("evidence_date") or dataset_evidence_date)),
            canonical_occupation_id=str(r.get("canonical_occupation_id") or f"occupation:soc:{r['occupation_code']}"),
            evidence_rationale=str(r["evidence_rationale"]).strip(),
            evidence_strength=str(r.get("evidence_strength") or "unknown").strip().lower(),  # type: ignore[arg-type]
            uncertainty_note=str(r.get("uncertainty_note") or "").strip() or None,
        ))

    return prov, parsed


def run_loader(input_path: Path | None = None, *, dry_run: bool = True) -> dict[str, Any]:
    if input_path is None or not input_path.exists():
        return {
            "status": "blocked",
            "dry_run": dry_run,
            "loaded_count": 0,
            "blocker_reason": (
                "No licensed AI-exposure reference dataset file is present in the repository. "
                "Ingestion is blocked until a dataset with verified license (e.g. CC-BY-4.0) and provenance metadata is supplied."
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

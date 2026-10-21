"""Read-only readiness audit for an explicitly supplied local observation snapshot.

Supported inputs are an observation CSV, JSON array/object, JSON Lines file, or a
SQLite database containing the canonical ``market_observations`` table. Native
Firestore exports are intentionally unsupported; export/convert them through an
approved offline process first.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from app.analytics.analytical_readiness import _longest_consecutive_run
from app.analytics.observation_period import is_completed_month, normalize_month_period
from app.analytics.series_validation import comparable_series_key
from app.analytics.skill_half_life import calculate_skill_half_life
from app.analytics.skill_health import evaluate_skill_health
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.analytics.forecasting import forecast_signal_series
from app.models.market_signal import AggregatedMarketSignal
from app.models.skill_intelligence import MarketObservation
from app.storage.observation_identity import stable_observation_id

TREND_MIN = 4
HEALTH_MIN = 4
HALF_LIFE_MIN = 36
FORECAST_MIN = 24
SAFE_FIELDS = {
    "id", "observation_id", "source", "signal_type", "observed_at", "provider_posted_at", "period",
    "location", "scope", "skill", "canonical_name", "skill_id", "value", "unit",
    "denominator_unit", "denominator", "history_type", "data_origin", "series_id",
    "query_id", "panel_version", "extractor_version", "posting_id", "metric",
    "normalized_value", "quality",
}
SQLITE_COLUMNS = SAFE_FIELDS | {
    "metadata_json", "quality_json", "annotations_json", "confidence",
    "observation_count", "created_at", "fetch_run_id", "source_url",
}


class AuditInputError(Exception):
    """Safe input error suitable for displaying to the operator."""


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AuditInputError("BLOCKED: supplied snapshot path does not exist.")
    if not path.is_file():
        raise AuditInputError("BLOCKED: input must be a local file, not a directory or Firestore export prefix.")
    suffix = path.suffix.casefold()
    try:
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise AuditInputError("BLOCKED: CSV has no header row.")
                return list(reader)
        if suffix in {".jsonl", ".ndjson"}:
            rows = []
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line.strip():
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise AuditInputError(f"BLOCKED: JSON Lines record {line_number} is not an object.")
                        rows.append(row)
            return rows
        if suffix == ".json":
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict) and isinstance(payload.get("observations"), list):
                rows = payload["observations"]
            else:
                raise AuditInputError(
                    "BLOCKED: JSON must be an observation array or an object with an observations array."
                )
            if any(not isinstance(row, dict) for row in rows):
                raise AuditInputError("BLOCKED: every JSON observation must be an object.")
            return rows
        if suffix in {".sqlite", ".sqlite3", ".db"}:
            uri = f"file:{path.resolve().as_posix()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True)
            try:
                tables = {
                    item[0] for item in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "market_observations" not in tables:
                    raise AuditInputError("BLOCKED: SQLite file has no canonical market_observations table.")
                columns = {
                    item[1] for item in connection.execute("PRAGMA table_info(market_observations)")
                }
                required = {"source", "signal_type", "skill", "value", "observed_at"}
                if not required.issubset(columns):
                    raise AuditInputError("BLOCKED: market_observations schema is not a supported observation dataset.")
                selected = sorted(columns & SQLITE_COLUMNS)
                projection = ", ".join(f'"{column}"' for column in selected)
                return [dict(zip(selected, record)) for record in connection.execute(
                    f'SELECT {projection} FROM market_observations'
                )]
            finally:
                connection.close()
    except AuditInputError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error, sqlite3.Error) as exc:
        raise AuditInputError(f"BLOCKED: input could not be safely parsed ({type(exc).__name__}).") from None
    raise AuditInputError(
        "BLOCKED: unsupported format. Use observation CSV, JSON, JSON Lines, or SQLite with market_observations."
    )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("observed_at is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite numeric field")
    return parsed


def _safe_observation(raw: dict[str, Any]) -> tuple[MarketObservation, str | None, float | None, bool]:
    # Whitelist canonical observation fields; never pass raw metadata or user fields on.
    row = {key: raw.get(key) for key in SAFE_FIELDS if key in raw}
    row.pop("metric", None)
    row.pop("normalized_value", None)
    if "id" not in row and raw.get("observation_id"):
        row["id"] = raw["observation_id"]
    if not row.get("skill"):
        row["skill"] = row.get("canonical_name") or row.get("skill_id")
    if "quality" not in row and raw.get("quality_json"):
        try:
            quality = json.loads(raw["quality_json"])
            if isinstance(quality, dict):
                row["quality"] = quality
        except (TypeError, json.JSONDecodeError):
            pass
    elif isinstance(row.get("quality"), str):
        try:
            quality = json.loads(row["quality"])
            row["quality"] = quality if isinstance(quality, dict) else None
        except (TypeError, json.JSONDecodeError):
            row["quality"] = None
    row["observed_at"] = _parse_datetime(row.get("observed_at"))
    if row.get("period"):
        row["period"] = normalize_month_period(str(row["period"]))
    invalid_denominator = False
    try:
        denominator = _optional_float(row.get("denominator"))
    except (TypeError, ValueError):
        denominator = None
        invalid_denominator = True
    if denominator is not None and denominator <= 0:
        denominator = None
        invalid_denominator = True
    row["denominator"] = denominator
    metric = str(raw.get("metric") or ("normalized_share" if raw.get("normalized_value") not in (None, "") else "raw_count"))
    normalized_value = _optional_float(raw.get("normalized_value"))
    if metric == "normalized_share" and normalized_value is None:
        # In explicit normalized-share exports, value is the measured share.
        normalized_value = _optional_float(raw.get("value"))
    observation = MarketObservation.model_validate(row)
    return observation, metric, normalized_value, invalid_denominator


def _max_consecutive(periods: Iterable[str]) -> int:
    ordered = sorted(set(periods), key=lambda item: int(item[:4]) * 12 + int(item[5:]))
    return _longest_consecutive_run(ordered) if ordered else 0


def _month_gaps(periods: list[str]) -> list[str]:
    if len(periods) < 2:
        return []
    present = {int(period[:4]) * 12 + int(period[5:]) for period in periods}
    gaps = []
    for index in range(min(present), max(present) + 1):
        if index not in present:
            year, month = divmod(index, 12)
            if month == 0:
                year, month = year - 1, 12
            gaps.append(f"{year:04d}-{month:02d}")
    return gaps


def _group_key(observation: MarketObservation, metric: str) -> tuple[Any, ...]:
    normalized = normalize_skill(observation.skill)
    identity = canonical_skill_id(normalized) or normalized.casefold()
    return comparable_series_key(
        source=observation.source,
        signal_type=observation.signal_type,
        canonical_skill_id=canonical_skill_id(normalized),
        unit=observation.unit,
        denominator_unit=observation.denominator_unit,
        scope=observation.scope,
        location=observation.location,
        query_id=observation.query_id,
        panel_version=observation.panel_version,
        data_origin=observation.data_origin,
        history_type=observation.history_type,
        extractor_version=observation.extractor_version,
    ) + (identity, metric)


def _configuration_root(observation: MarketObservation, metric: str) -> tuple[Any, ...]:
    normalized = normalize_skill(observation.skill)
    identity = canonical_skill_id(normalized) or normalized.casefold()
    return (
        observation.source.casefold().strip(), observation.signal_type, identity,
        (observation.unit or "").casefold().strip(),
        (observation.denominator_unit or "").casefold().strip(),
        (observation.scope or "").casefold().strip(),
        (observation.location or "").casefold().strip(), metric,
        observation.data_origin, observation.history_type,
    )


def _blocked_summary(reason: str, input_format: str | None = None) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "reason": reason,
        "input_format": input_format,
        "input_checksum_sha256": None,
        "manifest_status": "missing_or_invalid",
        "input_eligibility": "blocked",
        "total_rows": 0,
        "valid_observations": 0,
        "accepted_records": 0,
        "rejected_records": 0,
        "quarantined_records": 0,
        "duplicate_records": 0,
        "reason_counts": {},
        "genuine_hiring_demand_observations": 0,
        "series_count": 0,
        "eligible_series": {"skill_demand_trends": 0, "skill_health": 0, "skill_half_life": 0, "operational_forecasting": 0},
        "excluded_by_signal_or_origin": {},
        "series": [],
    }


MANIFEST_REQUIRED = {
    "source", "signal_family", "license_status", "approval_reference", "approved_by",
    "export_created_at", "observation_start", "observation_end", "schema_version",
    "panel_query_versions", "metric", "unit", "denominator_semantics", "denominator_unit",
    "geography", "period_grain", "collection_complete", "sampling_frame",
    "taxonomy_version", "extractor_version", "sha256", "record_count", "data_origin", "history_type",
}


def _read_manifest(snapshot_path: Path, manifest_path: Path | None) -> dict[str, Any]:
    selected = manifest_path or snapshot_path.with_suffix(snapshot_path.suffix + ".manifest.json")
    try:
        manifest = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise AuditInputError("BLOCKED: an explicit readable JSON manifest is required.") from None
    if not isinstance(manifest, dict):
        raise AuditInputError("BLOCKED: manifest must be a JSON object.")
    missing = sorted(MANIFEST_REQUIRED - manifest.keys())
    if missing:
        raise AuditInputError("BLOCKED: manifest is missing required provenance fields.")
    if manifest.get("period_grain") != "month":
        raise AuditInputError("BLOCKED: manifest period_grain must be month.")
    if type(manifest.get("record_count")) is not int or manifest["record_count"] < 0:
        raise AuditInputError("BLOCKED: manifest record_count must be a non-negative integer.")
    if not isinstance(manifest.get("sha256"), str) or len(manifest["sha256"]) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in manifest["sha256"]
    ):
        raise AuditInputError("BLOCKED: manifest sha256 must be a 64-character hexadecimal digest.")
    if not isinstance(manifest.get("collection_complete"), bool):
        raise AuditInputError("BLOCKED: manifest collection_complete must be an explicit boolean.")
    if not isinstance(manifest.get("sampling_frame"), str) or not manifest["sampling_frame"].strip():
        raise AuditInputError("BLOCKED: manifest requires a named sampling_frame.")
    if not isinstance(manifest.get("panel_query_versions"), list) or not manifest["panel_query_versions"]:
        raise AuditInputError("BLOCKED: manifest requires panel_query_versions.")
    if not isinstance(manifest.get("geography"), list) or not manifest["geography"]:
        raise AuditInputError("BLOCKED: manifest requires geography entries.")
    for field in ("source", "signal_family", "schema_version", "metric", "unit", "denominator_semantics",
                  "denominator_unit", "taxonomy_version", "extractor_version", "history_type"):
        if not _manifest_values(manifest.get(field)):
            raise AuditInputError(f"BLOCKED: manifest requires {field}.")
    try:
        _parse_datetime(manifest["export_created_at"])
        start = normalize_month_period(str(manifest["observation_start"]))
        end = normalize_month_period(str(manifest["observation_end"]))
    except (TypeError, ValueError):
        raise AuditInputError("BLOCKED: manifest timestamps or observation range are invalid.") from None
    if start > end:
        raise AuditInputError("BLOCKED: manifest observation range is reversed.")
    origin = manifest.get("data_origin")
    if origin in {"synthetic", "test"}:
        if manifest.get("license_status") != "test_only":
            raise AuditInputError("BLOCKED: synthetic/test input must declare license_status=test_only.")
    elif origin == "real":
        if (
            manifest.get("license_status") != "owner_attested_approved"
            or not str(manifest.get("approval_reference") or "").strip()
            or not str(manifest.get("approved_by") or "").strip()
        ):
            raise AuditInputError("BLOCKED: real-data manifest requires owner-attested approval metadata.")
    else:
        raise AuditInputError("BLOCKED: manifest data_origin must be real, synthetic, or test.")
    return manifest


def _manifest_values(value: Any) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {str(item).strip().casefold() for item in values if item is not None and str(item).strip()}


def _manifest_row_reason(raw: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    if manifest.get("collection_complete") is not True:
        return "manifest_collection_incomplete_or_unknown"
    checks = {
        "source": raw.get("source"),
        "signal_family": raw.get("signal_type"),
        "unit": raw.get("unit"),
        "denominator_unit": raw.get("denominator_unit"),
        "data_origin": raw.get("data_origin"),
        "history_type": raw.get("history_type"),
    }
    for field, value in checks.items():
        if str(value).strip().casefold() not in _manifest_values(manifest[field]):
            return "manifest_record_mismatch"
    versions = manifest["panel_query_versions"]
    if not isinstance(versions, list) or not versions:
        return "invalid_manifest_panel_query_versions"
    pairs = {
        (str(item.get("panel_version") or "").casefold(), str(item.get("query_id") or "").casefold())
        for item in versions if isinstance(item, dict)
    }
    if (str(raw.get("panel_version") or "").casefold(), str(raw.get("query_id") or "").casefold()) not in pairs:
        return "manifest_record_mismatch"
    geography = manifest["geography"]
    if not isinstance(geography, list) or not any(
        isinstance(item, dict)
        and str(item.get("scope") or "").casefold() == str(raw.get("scope") or "").casefold()
        and str(item.get("location") or "").casefold() == str(raw.get("location") or "").casefold()
        for item in geography
    ):
        return "manifest_record_mismatch"
    metric = str(raw.get("metric") or ("normalized_share" if raw.get("normalized_value") not in (None, "") else "raw_count"))
    if metric.casefold() not in _manifest_values(manifest["metric"]):
        return "manifest_record_mismatch"
    try:
        period = normalize_month_period(str(raw.get("period") or _parse_datetime(raw.get("observed_at")).strftime("%Y-%m")))
        start = normalize_month_period(str(manifest["observation_start"]))
        end = normalize_month_period(str(manifest["observation_end"]))
    except (TypeError, ValueError):
        return "invalid_manifest_observation_range"
    if not start <= period <= end:
        return "observation_outside_manifest_range"
    quality = raw.get("quality", raw.get("quality_json"))
    if isinstance(quality, str):
        try:
            quality = json.loads(quality)
        except (TypeError, json.JSONDecodeError):
            return "invalid_quality_metadata"
    if not isinstance(quality, dict):
        return "collection_completeness_unknown"
    if quality.get("collection_complete") is not True or quality.get("pagination_complete") is not True:
        return "collection_incomplete_or_unknown"
    if str(quality.get("sampling_frame") or "").strip() != str(manifest["sampling_frame"]).strip():
        return "sampling_frame_mismatch"
    return None


def audit_snapshot(
    path: Path, *, as_of: date | None = None, manifest_path: Path | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(timezone.utc).date()
    try:
        raw_rows = _load_rows(path)
    except AuditInputError as exc:
        return _blocked_summary(str(exc), path.suffix.casefold().lstrip(".") or None)
    try:
        input_checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return _blocked_summary("BLOCKED: snapshot bytes could not be read for checksum validation.", path.suffix.casefold().lstrip("."))
    try:
        manifest = _read_manifest(path, manifest_path)
    except AuditInputError as exc:
        report = _blocked_summary(str(exc), path.suffix.casefold().lstrip(".") or None)
        report.update({
            "input_checksum_sha256": input_checksum,
            "total_rows": len(raw_rows),
            "quarantined_records": len(raw_rows),
            "reason_counts": {"quarantined:missing_or_invalid_manifest": len(raw_rows)} if raw_rows else {},
        })
        report["quarantined_rows"] = {"missing_or_invalid_manifest": len(raw_rows)} if raw_rows else {}
        return report
    if manifest["sha256"].casefold() != input_checksum:
        report = _blocked_summary("BLOCKED: manifest checksum does not match the input snapshot.", path.suffix.casefold().lstrip("."))
        report["input_checksum_sha256"] = input_checksum
        report["total_rows"] = len(raw_rows)
        report["quarantined_records"] = len(raw_rows)
        report["quarantined_rows"] = {"manifest_checksum_mismatch": len(raw_rows)} if raw_rows else {}
        report["reason_counts"] = {"quarantined:manifest_checksum_mismatch": len(raw_rows)} if raw_rows else {}
        return report
    if manifest["record_count"] != len(raw_rows):
        report = _blocked_summary("BLOCKED: manifest record_count does not match parsed input records.", path.suffix.casefold().lstrip("."))
        report["input_checksum_sha256"] = input_checksum
        report["total_rows"] = len(raw_rows)
        report["quarantined_records"] = len(raw_rows)
        report["quarantined_rows"] = {"manifest_record_count_mismatch": len(raw_rows)} if raw_rows else {}
        report["reason_counts"] = {"quarantined:manifest_record_count_mismatch": len(raw_rows)} if raw_rows else {}
        return report
    if not raw_rows:
        report = _blocked_summary("BLOCKED: snapshot contains no observations.", path.suffix.casefold().lstrip("."))
        report["total_rows"] = 0
        return report

    valid: list[tuple[MarketObservation, str, float | None, bool]] = []
    rejected = Counter()
    quarantined = Counter()
    duplicates = 0
    seen_identity: dict[str, tuple[MarketObservation, tuple[Any, ...], int]] = {}
    conflicted_identities: set[str] = set()
    for raw in raw_rows:
        try:
            manifest_reason = _manifest_row_reason(raw, manifest)
            if manifest_reason:
                quarantined[manifest_reason] += 1
                continue
            item = _safe_observation(raw)
            observation = item[0]
            if not canonical_skill_id(observation.skill):
                quarantined["unresolved_skill_mapping"] += 1
                continue
            identity = observation.id or stable_observation_id(observation)
            signature = (
                observation.source, observation.signal_type, observation.skill_id,
                observation.period, observation.value, observation.unit,
                observation.denominator, observation.denominator_unit, observation.scope,
                observation.location, observation.panel_version, observation.query_id,
            )
            previous = seen_identity.get(identity)
            if previous:
                duplicates += 1
                if previous[1] != signature:
                    quarantined["conflicting_identity"] += 1
                    conflicted_identities.add(identity)
                continue
            seen_identity[identity] = (observation, signature, len(valid))
            valid.append(item)
        except (ValidationError, TypeError, ValueError, OverflowError):
            rejected["invalid_observation"] += 1

    if conflicted_identities:
        quarantined["conflicting_identity"] += len(conflicted_identities)
        valid = [
            item for item in valid
            if (item[0].id or stable_observation_id(item[0])) not in conflicted_identities
        ]

    if not valid:
        report = _blocked_summary(
            "BLOCKED: no rows matched the canonical observation contract.",
            path.suffix.casefold().lstrip("."),
        )
        report["total_rows"] = len(raw_rows)
        report["rejected_rows"] = dict(rejected)
        report["quarantined_rows"] = dict(quarantined)
        report["accepted_records"] = 0
        report["rejected_records"] = sum(rejected.values())
        report["quarantined_records"] = sum(quarantined.values())
        report["duplicate_records"] = duplicates
        report["input_checksum_sha256"] = input_checksum
        report["manifest_status"] = "owner_attested" if manifest["data_origin"] == "real" else "test_only"
        report["input_eligibility"] = "owner_review_eligible" if manifest["data_origin"] == "real" else "test_only"
        return report

    grouped: dict[tuple[Any, ...], list[tuple[MarketObservation, str, float | None, bool]]] = defaultdict(list)
    excluded = Counter()
    test_only = manifest["data_origin"] in {"synthetic", "test"}
    for item in valid:
        obs, metric, _, bad_denominator = item
        if obs.signal_type != "demand":
            excluded[f"signal_{obs.signal_type}"] += 1
        elif obs.data_origin != "real" or obs.history_type not in {"platform_collected", "backfill", "backfilled"}:
            excluded["non_real_or_non_historical_demand"] += 1
        if obs.signal_type == "demand":
            grouped[_group_key(obs, metric)].append(item)

    # Derive source-period denominators exactly within the existing aggregation partitions.
    posting_partition_ids: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for obs, _, _, _ in valid:
        sample_frame = obs.quality.get("sampling_frame") if isinstance(obs.quality, dict) else None
        collection_complete = (
            isinstance(obs.quality, dict)
            and obs.quality.get("collection_complete") is True
            and obs.quality.get("pagination_complete") is True
        )
        if obs.signal_type == "demand" and obs.posting_id and sample_frame and collection_complete:
            partition = (
                obs.source.casefold().strip(), obs.signal_type, obs.period or obs.observed_at.strftime("%Y-%m"),
                (obs.panel_version or "").strip(), obs.data_origin, obs.history_type,
                (obs.unit or "").casefold().strip(), (obs.denominator_unit or "").casefold().strip(),
                obs.scope, (obs.location or "").casefold().strip(), (obs.query_id or "").strip(),
                (obs.extractor_version or "").strip(), sample_frame,
            )
            posting_partition_ids[partition].add(obs.posting_id)

    configuration_sets: dict[tuple[Any, ...], set[tuple[Any, ...]]] = defaultdict(set)
    for obs, metric, _, _ in valid:
        if obs.signal_type == "demand":
            configuration_sets[_configuration_root(obs, metric)].add(
                (obs.series_id, obs.query_id, obs.panel_version, obs.extractor_version)
            )

    summaries: list[dict[str, Any]] = []
    eligible_counts = Counter({
        "skill_demand_trends": 0,
        "skill_health": 0,
        "skill_half_life": 0,
        "operational_forecasting": 0,
    })
    genuine_demand_count = 0
    for group_items in grouped.values():
        first = group_items[0][0]
        skill_label = normalize_skill(first.skill)
        c_id = canonical_skill_id(skill_label)
        metric = group_items[0][1]
        identity_flags = {
            (
                item[0].series_id, item[0].query_id, item[0].panel_version,
                item[0].extractor_version,
                item[0].quality.get("sampling_frame") if isinstance(item[0].quality, dict) else None,
            )
            for item in group_items
        }
        drift = len(identity_flags) > 1 or len(configuration_sets[_configuration_root(first, metric)]) > 1
        real_items = [
            item for item in group_items
            if item[0].data_origin == "real"
            and item[0].history_type in {"platform_collected", "backfill", "backfilled"}
            and isinstance(item[0].quality, dict)
            and item[0].quality.get("collection_complete") is True
            and item[0].quality.get("pagination_complete") is True
            and bool(item[0].quality.get("sampling_frame"))
        ]
        genuine_demand_count += len(real_items)
        current_month_rows = [
            item for item in (group_items if test_only else real_items)
            if (item[0].period or item[0].observed_at.strftime("%Y-%m")) == f"{as_of.year:04d}-{as_of.month:02d}"
        ]
        complete: dict[str, list[tuple[MarketObservation, str, float | None, bool]]] = defaultdict(list)
        for item in real_items:
            period = item[0].period or item[0].observed_at.strftime("%Y-%m")
            if is_completed_month(period, as_of=as_of):
                complete[period].append(item)
        complete_for_test: dict[str, list[tuple[MarketObservation, str, float | None, bool]]] = defaultdict(list)
        if test_only:
            for item in group_items:
                period = item[0].period or item[0].observed_at.strftime("%Y-%m")
                if is_completed_month(period, as_of=as_of):
                    complete_for_test[period].append(item)
        duplicate_periods = []
        month_points: list[AggregatedMarketSignal] = []
        invalid_denominator_months = []
        if test_only:
            for period, rows in sorted(complete_for_test.items()):
                ids = [row[0].id for row in rows if row[0].id]
                if len(ids) != len(set(ids)) or (metric == "normalized_share" and len(rows) > 1):
                    duplicate_periods.append(period)
        for period, rows in sorted(complete.items()):
            ids = [row[0].id for row in rows if row[0].id]
            explicit_share = metric == "normalized_share"
            duplicate = len(ids) != len(set(ids)) or (explicit_share and len(rows) > 1)
            if duplicate:
                duplicate_periods.append(period)
            values = [float(row[0].value) for row in rows]
            raw_value = sum(values)
            explicit_denominators = {row[0].denominator for row in rows if row[0].denominator is not None}
            if len(explicit_denominators) == 1:
                denominator = next(iter(explicit_denominators))
            else:
                obs = rows[0][0]
                partition = (
                    obs.source.casefold().strip(), obs.signal_type, period,
                    (obs.panel_version or "").strip(), obs.data_origin, obs.history_type,
                    (obs.unit or "").casefold().strip(), (obs.denominator_unit or "").casefold().strip(),
                    obs.scope, (obs.location or "").casefold().strip(), (obs.query_id or "").strip(),
                    (obs.extractor_version or "").strip(),
                    obs.quality.get("sampling_frame") if isinstance(obs.quality, dict) else None,
                )
                post_count = len(posting_partition_ids.get(partition, set()))
                denominator = float(post_count) if post_count > 1 else None
            invalid_denom = any(row[3] for row in rows)
            if invalid_denom or (explicit_denominators and len(explicit_denominators) > 1):
                invalid_denominator_months.append(period)
                denominator = None
            share_value: float | None = None
            if metric == "normalized_share":
                shares = [row[2] for row in rows if row[2] is not None]
                if len(shares) == 1 and 0 < shares[0] <= 1 and denominator and denominator > 0:
                    share_value = shares[0]
            elif denominator and denominator > 0:
                share_value = raw_value / denominator
            if metric == "normalized_share" and share_value is None:
                invalid_denominator_months.append(period)
            month_points.append(AggregatedMarketSignal(
                canonical_skill_id=c_id,
                canonical_name=skill_label,
                source=first.source,
                signal_type="demand",
                period=period,
                metric="normalized_share" if share_value is not None else "raw_count",
                raw_value=raw_value,
                normalized_value=share_value,
                denominator=denominator,
                observation_count=len(rows),
                data_origin="real",
                history_type=first.history_type or "unavailable",
                data_state="ready" if share_value is not None else "insufficient_data",
                series_id=first.series_id,
                panel_version=first.panel_version,
                unit=first.unit,
                denominator_unit=first.denominator_unit,
                scope=first.scope,
                location=first.location,
                query_id=first.query_id,
                extractor_version=first.extractor_version,
                observation_ids=[row[0].id for row in rows if row[0].id],
                fetch_run_ids=[],
            ))

        structural_normalized_periods: list[str] = []
        if test_only:
            periods = sorted(complete_for_test)
            structural_normalized_periods = sorted(
                period for period, period_rows in complete_for_test.items()
                if all(
                    item[1] == "normalized_share"
                    and item[2] is not None and 0 < item[2] <= 1
                    and item[0].denominator is not None and item[0].denominator_unit
                    for item in period_rows
                )
            )
        else:
            complete_for_test = complete
            periods = sorted(complete)
            structural_normalized_periods = [
                point.period for point in month_points
                if point.metric == "normalized_share" and point.denominator is not None
                and point.denominator > 0 and point.denominator_unit
            ]
        consecutive = _max_consecutive(periods)
        gaps = _month_gaps(periods)
        trend_ready = not test_only and not drift and not duplicate_periods and consecutive >= TREND_MIN
        normalized_points = [
            point for point in month_points
            if point.metric == "normalized_share" and point.denominator is not None
            and point.denominator > 0 and point.denominator_unit
        ]
        normalized_periods = structural_normalized_periods if test_only else [point.period for point in normalized_points]
        normalized_consecutive = _max_consecutive(normalized_periods)
        health_ready = (
            not test_only and not drift and not duplicate_periods and normalized_consecutive >= HEALTH_MIN
            and all(point.denominator is not None and point.denominator > 0 and point.denominator_unit for point in normalized_points)
        )
        half_life_ready = False
        half_life_result = None
        forecast_ready = False
        forecast_result = None
        reasons = []
        if not real_items:
            reasons.append("No real platform-collected/backfilled hiring-demand observations in this series.")
        if test_only:
            reasons.append("TEST_ONLY_INPUT: structural period counts are not operational evidence.")
        if drift:
            reasons.append("Series/query/panel/extractor identity changes within otherwise comparable dimensions.")
        if duplicate_periods:
            reasons.append("Duplicate observation identity or duplicate period-level metric rows were detected.")
        if consecutive < TREND_MIN:
            reasons.append(f"Trend requires {TREND_MIN} consecutive completed months; found {consecutive}.")
        if gaps:
            reasons.append("Missing months are preserved; no interpolation was performed.")
        if current_month_rows:
            reasons.append("Current month is incomplete and excluded from completed-period readiness.")
        if invalid_denominator_months:
            reasons.append("One or more periods lack a valid positive denominator and denominator unit.")
        if health_ready:
            try:
                health_result = evaluate_skill_health(month_points, min_periods=HEALTH_MIN)
                health_ready = health_result.score_status == "ready"
            except (ValueError, TypeError):
                health_ready = False
        if health_ready:
            eligible_counts["skill_health"] += 1
        if not health_ready:
            reasons.append("Skill Health requires 4 consecutive normalized completed months and valid positive denominators.")
        if normalized_consecutive >= HALF_LIFE_MIN and health_ready and c_id:
            try:
                half_life_result = calculate_skill_half_life(
                    month_points,
                    canonical_skill_id=c_id,
                    canonical_name=skill_label,
                    provider=first.source,
                    min_periods=HALF_LIFE_MIN,
                    as_of=as_of,
                )
                half_life_ready = half_life_result.status == "ready"
            except (ValueError, TypeError):
                half_life_ready = False
        if not half_life_ready:
            reasons.append("Half-Life requires 36 normalized consecutive months and statistically supported decline.")
        if normalized_consecutive >= FORECAST_MIN and health_ready and c_id and not drift and not duplicate_periods:
            try:
                forecast_result = forecast_signal_series(
                    month_points,
                    canonical_skill_id=c_id,
                    canonical_name=skill_label,
                    signal_family="demand",
                    provider=first.source,
                    min_periods=FORECAST_MIN,
                    as_of=as_of,
                )
                forecast_ready = forecast_result.status == "ready"
            except (ValueError, TypeError):
                forecast_ready = False
        if not forecast_ready:
            reasons.append("Operational forecasting requires 24 normalized consecutive months plus a completed chronological holdout.")
        if drift or duplicate_periods:
            trend_ready = health_ready = half_life_ready = forecast_ready = False
        if trend_ready:
            eligible_counts["skill_demand_trends"] += 1
        if half_life_ready:
            eligible_counts["skill_half_life"] += 1
        if forecast_ready:
            eligible_counts["operational_forecasting"] += 1

        summaries.append({
            "series_ref": f"series_{len(summaries) + 1:04d}",
            "source": first.source,
            "signal_family": first.signal_type,
            "skill": skill_label,
            "skill_id": c_id,
            "location": first.location,
            "scope": first.scope,
            "panel_version": first.panel_version,
            "query_id": first.query_id,
            "extractor_version": first.extractor_version,
            "period_grain": "month",
            "metric": metric,
            "unit": first.unit,
            "denominator_unit": first.denominator_unit,
            "history_types": sorted({str(item[0].history_type or "unknown") for item in group_items}),
            "data_origins": sorted({str(item[0].data_origin or "unknown") for item in group_items}),
            "observation_count": len(group_items),
            "genuine_demand_observation_count": len(real_items),
            "first_completed_period": periods[0] if periods else None,
            "latest_completed_period": periods[-1] if periods else None,
            "completed_period_count": len(periods),
            "consecutive_completed_months": consecutive,
            "normalized_consecutive_months": normalized_consecutive,
            "missing_months": gaps,
            "incomplete_current_month_observation_count": len(current_month_rows),
            "duplicate_periods": duplicate_periods,
            "invalid_denominator_periods": sorted(set(invalid_denominator_months)),
            "configuration_drift": drift,
            "readiness": {
                "skill_demand_trends": trend_ready,
                "skill_health": health_ready,
                "skill_half_life": half_life_ready,
                "operational_forecasting_data_eligible": forecast_ready,
                "forecast_holdout_sample_size": getattr(forecast_result, "backtest_sample_size", 0),
                "forecast_baseline": getattr(forecast_result, "baseline_name", None),
                "model_validated": False,
                "test_only_structural_period_gates": {
                    "trend_history_depth": not drift and not duplicate_periods and consecutive >= TREND_MIN,
                    "health_history_depth": not drift and not duplicate_periods and normalized_consecutive >= HEALTH_MIN,
                    "half_life_history_depth": normalized_consecutive >= HALF_LIFE_MIN,
                    "forecast_history_depth": normalized_consecutive >= FORECAST_MIN,
                } if test_only else None,
            },
            "half_life_status": getattr(half_life_result, "status", None),
            "half_life_reason": getattr(half_life_result, "reason", None),
            "blocking_reasons": reasons,
        })

    owner_metadata = (
        manifest["data_origin"] == "real"
        and manifest["license_status"] == "owner_attested_approved"
        and bool(str(manifest.get("approval_reference") or "").strip())
        and bool(str(manifest.get("approved_by") or "").strip())
    )
    return {
        "status": "COMPLETE" if summaries else "BLOCKED",
        "reason": None if summaries else "BLOCKED: no source-specific hiring-demand series could be formed.",
        "input_format": path.suffix.casefold().lstrip("."),
        "input_checksum_sha256": input_checksum,
        "manifest_status": "owner_attested" if owner_metadata else "test_only",
        "input_eligibility": "owner_review_eligible" if owner_metadata else "test_only",
        "approval_assessment": (
            "owner_supplied_metadata_not_independently_verified" if owner_metadata else "test_only_no_real_data_claim"
        ),
        "as_of": as_of.isoformat(),
        "total_rows": len(raw_rows),
        "valid_observations": len(valid),
        "accepted_records": len(valid),
        "rejected_records": sum(rejected.values()),
        "quarantined_records": sum(quarantined.values()),
        "duplicate_records": duplicates,
        "reason_counts": {**{f"rejected:{key}": value for key, value in rejected.items()}, **{f"quarantined:{key}": value for key, value in quarantined.items()}},
        "rejected_rows": dict(rejected),
        "quarantined_rows": dict(quarantined),
        "genuine_hiring_demand_observations": genuine_demand_count,
        "series_count": len(summaries),
        "eligible_series": dict(eligible_counts),
        "excluded_by_signal_or_origin": dict(excluded),
        "series": summaries,
        "model_validation_note": "Data eligibility is separate from model validation. No trained model was evaluated by this audit.",
    }


def _human_report(report: dict[str, Any]) -> str:
    lines = [f"Demand series readiness: {report['status']}"]
    if report.get("reason"):
        lines.append(report["reason"])
    lines.append(f"Rows inspected: {report.get('total_rows', 0)}; valid observations: {report.get('valid_observations', 0)}")
    lines.append(f"Genuine hiring-demand observations: {report.get('genuine_hiring_demand_observations', 0)}")
    eligible = report.get("eligible_series", {})
    lines.append(
        "Eligible series — Trends: {skill_demand_trends}, Health: {skill_health}, Half-Life: {skill_half_life}, Forecast data: {operational_forecasting}".format(
            skill_demand_trends=eligible.get("skill_demand_trends", 0),
            skill_health=eligible.get("skill_health", 0),
            skill_half_life=eligible.get("skill_half_life", 0),
            operational_forecasting=eligible.get("operational_forecasting", 0),
        )
    )
    for series in report.get("series", []):
        lines.append(
            f"{series['series_ref']}: {series['source']} / {series['skill']} / {series['scope']} / {series['location'] or 'unspecified'} — "
            f"{series['completed_period_count']} completed months, longest consecutive run {series['consecutive_completed_months']}"
        )
        lines.extend(f"  - {reason}" for reason in series["blocking_reasons"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_path", nargs="?", help="Explicit local CSV/JSON/JSONL/SQLite observation snapshot")
    parser.add_argument("--as-of", help="Audit date YYYY-MM-DD (defaults to current UTC date)")
    parser.add_argument("--json-output", type=Path, help="Optional path for a machine-readable aggregate report")
    args = parser.parse_args(argv)
    as_of = None
    if args.as_of:
        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError:
            report = _blocked_summary("BLOCKED: --as-of must use YYYY-MM-DD.")
            print(_human_report(report))
            return 2
    if not args.snapshot_path:
        report = _blocked_summary("BLOCKED: explicitly supply a local observation snapshot path.")
    else:
        report = audit_snapshot(Path(args.snapshot_path), as_of=as_of)
    print(_human_report(report))
    if args.json_output:
        if args.snapshot_path and Path(args.snapshot_path).resolve() == args.json_output.resolve():
            print("BLOCKED: JSON report path must not overwrite the input snapshot.", file=sys.stderr)
            return 2
        try:
            args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            print("BLOCKED: machine-readable report could not be written.", file=sys.stderr)
            return 2
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())

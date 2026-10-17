"""Idempotent Firestore persistence for deterministic calculation output with reuse and read efficiency."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from google.api_core.exceptions import AlreadyExists

from app.analytics.trend import CALCULATION_VERSION, SMOOTHING_ALPHA
from app.core.firebase import get_firestore_client
from app.models.calculation_record import CalculationRecord
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_read_guard import read_guard

# In-memory calculation cache: calculation_id -> CalculationRecord
_CALCULATION_CACHE: dict[str, CalculationRecord] = {}


def clear_calculation_cache() -> None:
    _CALCULATION_CACHE.clear()


class CalculationRecordConflict(RuntimeError):
    """A deterministic calculation identity was already bound to other evidence."""


class FirestoreCalculationRecordStore:
    collection_name = "calculation_records"

    def __init__(self, client: Any | None = None):
        self.client = client

    def _collection(self):
        client = self.client
        if client is None:
            client = get_firestore_client()
        return client.collection(self.collection_name)

    def get_trend_calculation(self, calculation_id: str) -> CalculationRecord | None:
        """Retrieve existing calculation record from cache or Firestore."""
        if calculation_id in _CALCULATION_CACHE:
            read_guard.record_calculation_reuse()
            return _CALCULATION_CACHE[calculation_id]

        ref = self._collection().document(calculation_id)
        existing = ref.get()
        read_guard.record_read(self.collection_name, 1, query_type="targeted")
        if getattr(existing, "exists", False):
            data = existing.to_dict() or {}
            record = CalculationRecord.model_validate(data)
            _CALCULATION_CACHE[calculation_id] = record
            read_guard.record_calculation_reuse()
            return record
        return None

    def find_reusable_trend_calculation(
        self,
        *,
        source: str,
        signal_type: str,
        canonical_name: str,
        latest_period: str,
        observation_ids: list[str],
        formula_id: str = CALCULATION_VERSION,
        window: str = "trend",
    ) -> CalculationRecord | None:
        """Find an existing deterministic calculation record if inputs have not changed."""
        sorted_obs_ids = sorted(set(observation_ids))
        identity = {
            "source": source,
            "signal_type": signal_type,
            "canonical_name": canonical_name,
            "latest_period": latest_period,
            "formula_id": formula_id,
            "window": window,
            "observation_ids": sorted_obs_ids,
        }
        calc_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return self.get_trend_calculation(calc_id)

    def persist_current_demand(
        self,
        snapshots: list[dict[str, Any]],
        *,
        window: str,
        observations_by_id: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        """Persist the calculation result already produced by the shared trend engine."""
        client = self.client
        if client is None:
            client = get_firestore_client()

        fetch_runs = FirestoreFetchRunStore(client)
        records: dict[str, str] = {}
        for snapshot in snapshots:
            evidence = snapshot.get("evidence") or {}
            observation_ids = sorted(set(evidence.get("observation_ids") or []))
            if (
                snapshot.get("data_origin") != "real"
                or snapshot.get("history_type") != "platform_collected"
                or not observation_ids
                or not snapshot.get("series_id")
                or not snapshot.get("period")
                or not isinstance(snapshot.get("value"), (int, float))
            ):
                continue

            formula_id = str(evidence.get("calculation_version") or CALCULATION_VERSION)
            identity = {
                "metric": snapshot["metric"],
                "source": snapshot["source"],
                "series_id": snapshot["series_id"],
                "period": snapshot["period"],
                "formula_id": formula_id,
                "window": window,
                "observation_ids": observation_ids,
            }
            calculation_id = hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            key = "|".join((str(snapshot["source"]), str(snapshot["series_id"]), str(snapshot["period"]), str(snapshot["metric"])))
            if calculation_id in _CALCULATION_CACHE:
                cached_rec = _CALCULATION_CACHE[calculation_id]
                new_res = {"value": float(snapshot["value"]), "confidence": snapshot.get("confidence")}
                if cached_rec.result != new_res:
                    raise CalculationRecordConflict("Conflicting calculation record already exists.")
                read_guard.record_calculation_reuse()
                records[key] = calculation_id
                continue

            inputs = []
            run_ids: set[str] = set()
            extractors: set[str] = set()
            for observation_id in observation_ids:
                if observations_by_id and observation_id in observations_by_id:
                    obs_item = observations_by_id[observation_id]
                    if isinstance(obs_item, dict):
                        data = obs_item
                    else:
                        data = {
                            "data_origin": obs_item.data_origin,
                            "series_id": obs_item.series_id,
                            "history_type": obs_item.history_type,
                            "fetch_run_id": obs_item.fetch_run_id,
                            "source": obs_item.source,
                            "extractor_version": getattr(obs_item, "extractor_version", None),
                        }
                else:
                    observation = client.collection("skill_market_signals").document(observation_id).get()
                    read_guard.record_read("skill_market_signals", 1, query_type="targeted")
                    data = observation.to_dict() if getattr(observation, "exists", False) else None

                if not isinstance(data, dict) or data.get("data_origin") != "real":
                    inputs = []
                    break
                if data.get("series_id") != snapshot.get("series_id") or data.get("history_type") != "platform_collected":
                    raise CalculationRecordConflict("Calculation input series or history does not match its snapshot.")
                fetch_run_id = data.get("fetch_run_id")
                if not fetch_run_id:
                    inputs = []
                    break
                run = fetch_runs.get(fetch_run_id)
                if not isinstance(run, dict) or str(run.get("source", "")).casefold() != str(snapshot.get("source", "")).casefold():
                    raise CalculationRecordConflict("Calculation input fetch-run provenance does not match its source.")
                run_ids.add(fetch_run_id)
                if data.get("extractor_version"):
                    extractors.add(data["extractor_version"])
                archive = run.get("raw_response_archive") or {}
                archive_reference = archive.get("archive_reference") if isinstance(archive, dict) else None
                if not archive_reference:
                    inputs = []
                    break
                inputs.append({
                    "observation_id": observation_id,
                    "fetch_run_id": fetch_run_id,
                    "source": data.get("source"),
                    "archive_reference": archive_reference,
                })
            if len(inputs) != len(observation_ids):
                continue

            record = CalculationRecord(
                calculation_id=calculation_id,
                metric=snapshot["metric"],
                window=window,
                formula_id=formula_id,
                formula_parameters={
                    "source": snapshot["source"],
                    "scope": evidence.get("scope"),
                    "query_id": evidence.get("query_id"),
                    "panel_version": evidence.get("panel_version"),
                    "period_count": snapshot.get("coverage", {}).get("period_count"),
                    "minimum_trend_periods": evidence.get("minimum_trend_periods"),
                    "smoothing_alpha": SMOOTHING_ALPHA,
                },
                rounding=None,
                inputs=inputs,
                result={"value": float(snapshot["value"]), "confidence": snapshot.get("confidence")},
                source=str(snapshot["source"]),
                series_id=str(snapshot["series_id"]),
                period=str(snapshot["period"]),
                fetch_run_ids=sorted(run_ids),
                observation_ids=observation_ids,
                panel_version=evidence.get("panel_version"),
                extractor_version=next(iter(extractors)) if len(extractors) == 1 else None,
                calculation_version=formula_id,
                data_state=str(snapshot.get("data_state") or "insufficient_data"),
                created_at=datetime.now(timezone.utc),
                evidence={
                    "archive_references": sorted({item["archive_reference"] for item in inputs}),
                    "coverage": snapshot.get("coverage") or {},
                    "history_type": snapshot.get("history_type"),
                    "data_origin": snapshot.get("data_origin"),
                    "collected_at": evidence.get("collected_at"),
                },
            )
            ref = self._collection().document(calculation_id)
            stored = record.model_dump(mode="python")
            existing = ref.get()
            read_guard.record_read(self.collection_name, 1, query_type="targeted")
            if getattr(existing, "exists", False):
                self._assert_same(existing.to_dict() or {}, stored)
            else:
                try:
                    ref.create(stored)
                except AlreadyExists:
                    current = ref.get()
                    read_guard.record_read(self.collection_name, 1, query_type="targeted")
                    self._assert_same(current.to_dict() or {}, stored)

            _CALCULATION_CACHE[calculation_id] = record
            records[key] = calculation_id
        return records

    def persist_trend_velocity_results(
        self,
        results: list[Any],
        *,
        window: str = "trend",
        observations_by_id: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        """Persist G1.4 trend & velocity calculation records with idempotency, caching, and provenance."""
        client = self.client
        if client is None:
            client = get_firestore_client()

        fetch_runs = FirestoreFetchRunStore(client)
        records: dict[str, str] = {}

        for item in results:
            observation_ids = sorted(set(item.observation_ids or []))
            if (
                not observation_ids
                or not item.latest_period
                or not item.source
                or getattr(item, "data_origin", None) != "real"
            ):
                continue

            formula_id = item.calculation_version
            identity = {
                "source": item.source,
                "signal_type": item.signal_type,
                "canonical_name": item.canonical_name,
                "latest_period": item.latest_period,
                "formula_id": formula_id,
                "window": window,
                "observation_ids": observation_ids,
            }
            calculation_id = hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            key = "|".join((item.source, item.signal_type, item.canonical_name, item.latest_period))
            if calculation_id in _CALCULATION_CACHE:
                cached_rec = _CALCULATION_CACHE[calculation_id]
                new_res = {
                    "latest_value": item.latest_value,
                    "previous_value": item.previous_value,
                    "velocity": item.velocity,
                    "growth_pct": item.growth_pct,
                    "slope": item.slope,
                    "trend": item.trend,
                    "confidence": item.confidence,
                }
                if cached_rec.result != new_res:
                    raise CalculationRecordConflict("Conflicting calculation record already exists.")
                read_guard.record_calculation_reuse()
                records[key] = calculation_id
                continue

            inputs = []
            run_ids: set[str] = set()
            archive_refs: set[str] = set()
            for obs_id in observation_ids:
                if observations_by_id and obs_id in observations_by_id:
                    obs_item = observations_by_id[obs_id]
                    if isinstance(obs_item, dict):
                        obs_data = obs_item
                    else:
                        obs_data = {
                            "source": obs_item.source,
                            "fetch_run_id": obs_item.fetch_run_id,
                        }
                else:
                    obs_doc = client.collection("skill_market_signals").document(obs_id).get()
                    read_guard.record_read("skill_market_signals", 1, query_type="targeted")
                    obs_data = obs_doc.to_dict() if getattr(obs_doc, "exists", False) else None

                if not isinstance(obs_data, dict):
                    continue
                fetch_run_id = obs_data.get("fetch_run_id")
                if fetch_run_id:
                    run_ids.add(fetch_run_id)
                    run_data = fetch_runs.get(fetch_run_id)
                    if isinstance(run_data, dict):
                        archive = run_data.get("raw_response_archive") or {}
                        ref = archive.get("archive_reference") if isinstance(archive, dict) else None
                        if ref:
                            archive_refs.add(ref)
                            inputs.append({
                                "observation_id": obs_id,
                                "fetch_run_id": fetch_run_id,
                                "source": obs_data.get("source"),
                                "archive_reference": ref,
                            })

            record = CalculationRecord(
                calculation_id=calculation_id,
                metric=item.metric,
                window=window,
                formula_id=formula_id,
                formula_parameters={
                    "source": item.source,
                    "signal_type": item.signal_type,
                    "canonical_skill_id": item.canonical_skill_id,
                    "canonical_name": item.canonical_name,
                    "periods_used": item.periods_used,
                    "panel_version": item.panel_version,
                },
                rounding=None,
                inputs=inputs,
                result={
                    "latest_value": item.latest_value,
                    "previous_value": item.previous_value,
                    "velocity": item.velocity,
                    "growth_pct": item.growth_pct,
                    "slope": item.slope,
                    "trend": item.trend,
                    "confidence": item.confidence,
                },
                source=item.source,
                series_id=str(item.series_id or f"{item.source}:{item.canonical_name}"),
                period=item.latest_period,
                fetch_run_ids=sorted(run_ids or item.fetch_run_ids),
                observation_ids=observation_ids,
                panel_version=item.panel_version,
                extractor_version=None,
                calculation_version=formula_id,
                data_state=item.data_state,
                created_at=datetime.now(timezone.utc),
                evidence={
                    "archive_references": sorted(archive_refs),
                    "periods_used": item.periods_used,
                    "history_type": item.history_type,
                    "data_origin": item.data_origin,
                    "observation_count": item.observation_count,
                },
            )

            ref = self._collection().document(calculation_id)
            stored = record.model_dump(mode="python")
            existing = ref.get()
            read_guard.record_read(self.collection_name, 1, query_type="targeted")
            if getattr(existing, "exists", False):
                self._assert_same(existing.to_dict() or {}, stored)
            else:
                try:
                    ref.create(stored)
                except AlreadyExists:
                    current = ref.get()
                    read_guard.record_read(self.collection_name, 1, query_type="targeted")
                    self._assert_same(current.to_dict() or {}, stored)

            _CALCULATION_CACHE[calculation_id] = record
            records[key] = calculation_id

        return records

    @staticmethod
    def _assert_same(existing: dict[str, Any], expected: dict[str, Any]) -> None:
        comparable = {key: value for key, value in expected.items() if key != "created_at"}
        prior = {key: value for key, value in existing.items() if key != "created_at"}
        if prior != comparable:
            raise CalculationRecordConflict("Conflicting calculation record already exists.")

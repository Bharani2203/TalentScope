"""Canonical, idempotent Firestore storage for market observations with read-efficiency and guards."""

from __future__ import annotations

import time
from datetime import datetime, timezone
import logging
from typing import Any, Mapping

from google.cloud.firestore_v1 import FieldFilter
from pydantic import ValidationError

from app.analytics.skill_registry import BY_ID, canonical_skill_id
from app.analytics.skill_normalization import normalize_skill
from app.core.firebase import get_firestore_client
from app.models.skill_intelligence import MarketObservation
from app.storage.firestore_read_guard import read_guard
from app.storage.observation_identity import stable_observation_id

logger = logging.getLogger(__name__)
MAX_OBSERVATIONS_PER_QUERY = 2000
_OBSERVATION_QUERY_PROBE_LIMIT = MAX_OBSERVATIONS_PER_QUERY + 1


class ObservationBatch(list[MarketObservation]):
    """List-compatible observation result carrying whether its bounded query was complete."""

    def __init__(
        self,
        observations=(),
        *,
        truncated: bool = False,
        duplicate_count: int = 0,
        excluded_old_postings: int = 0,
        unknown_posted_at: int = 0,
    ):
        super().__init__(observations)
        self.truncated = truncated
        self.duplicate_count = duplicate_count
        self.excluded_old_postings = excluded_old_postings
        self.unknown_posted_at = unknown_posted_at


def clear_observations_cache() -> None:
    """Clear observations cache for test compatibility."""
    pass


class FirestoreObservationStore:
    """Store observation documents under their existing deterministic IDs."""

    collection_name = "skill_market_signals"
    _cached_has_observations: bool | None = None

    def __init__(self, client: Any | None = None, cache_ttl_seconds: float = 60.0):
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self._query_cache: dict[str, tuple[float, list[MarketObservation]]] = {}

    def _collection(self):
        client = self.client
        if client is None:
            client = get_firestore_client()
        return client.collection(self.collection_name)

    @classmethod
    def document_for(
        cls,
        observation: MarketObservation,
        *,
        created_at: datetime | None = None,
        query_id: str | None = None,
        panel_version: str | None = None,
        fetch_run_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        observation_id = stable_observation_id(observation)
        observed_at = observation.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        observed_at = observed_at.astimezone(timezone.utc)
        period = observation.period or observed_at.strftime("%Y-%m")
        canonical_name = normalize_skill(observation.skill)
        return observation_id, {
            "observation_id": observation_id,
            "source": observation.source.casefold(),
            "signal_type": observation.signal_type,
            "observed_at": observed_at,
            "provider_posted_at": observation.provider_posted_at,
            "period": period,
            "location": observation.location,
            "scope": observation.scope,
            "skill": canonical_name,
            "skill_id": canonical_skill_id(canonical_name) or observation.skill_id,
            "value": observation.value,
            "unit": observation.unit,
            "denominator_unit": observation.denominator_unit,
            "source_url": observation.source_url,
            "posting_id": observation.posting_id,
            "metadata": observation.metadata,
            "data_origin": observation.data_origin,
            "history_type": observation.history_type or (
                "platform_collected" if observation.signal_type == "demand" else "snapshot"
            ),
            "fetch_run_id": fetch_run_id or observation.fetch_run_id,
            "panel_version": panel_version or observation.panel_version,
            "query_id": query_id or observation.query_id,
            "series_id": observation.series_id,
            "denominator": observation.denominator,
            "extractor_version": observation.extractor_version,
            "annotations": observation.annotations,
            "quality": observation.quality,
            "confidence": observation.confidence,
            "observation_count": observation.observation_count if observation.observation_count is not None else 1,
            "created_at": observation.created_at or created_at or datetime.now(timezone.utc),
        }

    def insert_observations(
        self,
        observations: list[MarketObservation],
        *,
        provenance_by_observation_id: Mapping[str, Mapping[str, str | None]] | None = None,
    ) -> int:
        if not observations:
            return 0
        collection = self._collection()
        created_at = datetime.now(timezone.utc)
        pending: dict[str, dict[str, Any]] = {}
        for observation in observations:
            doc_id = stable_observation_id(observation)
            provenance = (provenance_by_observation_id or {}).get(doc_id, {})
            _, payload = self.document_for(
                observation,
                created_at=created_at,
                query_id=provenance.get("query_id"),
                panel_version=provenance.get("panel_version"),
                fetch_run_id=provenance.get("fetch_run_id"),
            )
            prior = pending.get(doc_id)
            if prior is not None:
                compared_fields = (
                    "source", "signal_type", "period", "location", "scope", "skill",
                    "posting_id", "value", "unit", "denominator", "denominator_unit",
                )
                if any(
                    prior.get(field) != payload.get(field)
                    and not (
                        field in {"value", "denominator"}
                        and prior.get("history_type") in {"snapshot", "static_dataset"}
                        and payload.get("history_type") in {"snapshot", "static_dataset"}
                    )
                    for field in compared_fields
                ):
                    raise ValueError("Conflicting observation data for a stable Firestore ID.")
                continue
            pending[doc_id] = payload

        new_documents: list[tuple[Any, dict[str, Any]]] = []
        for doc_id, payload in pending.items():
            reference = collection.document(doc_id)
            snapshot = reference.get()
            read_guard.record_read(self.collection_name, 1, query_type="targeted_upsert_check")
            if getattr(snapshot, "exists", False):
                stored = snapshot.to_dict() or {}
                if stored.get("observation_id") not in (None, doc_id):
                    raise ValueError("Firestore observation ID does not match its document ID.")
                identity_fields = (
                    "source", "signal_type", "period", "location", "scope",
                    "skill", "posting_id", "history_type", "series_id", "data_origin",
                    "unit", "denominator_unit", "value", "denominator",
                )
                if any(
                    stored.get(field) is not None
                    and payload.get(field) is not None
                    and stored.get(field) != payload.get(field)
                    and not (field == "history_type" and stored.get(field) in {"observed_signal", "adoption_snapshot"} and payload.get(field) in {"platform_collected", "snapshot"})
                    and not (
                        field in {"value", "denominator"}
                        and payload.get("history_type") in {"snapshot", "static_dataset"}
                    )
                    for field in identity_fields
                ):
                    raise ValueError("Conflicting observation data for a stable Firestore ID.")
                backfillable_fields = (
                    "skill_id", "history_type", "series_id", "query_id", "panel_version",
                    "denominator", "extractor_version", "annotations", "quality", "confidence",
                    "observation_count", "unit", "denominator_unit", "source_url",
                )
                updates = {
                    field: payload[field]
                    for field in backfillable_fields
                    if payload.get(field) is not None
                    and (
                        stored.get(field) is None
                        or (
                            field == "skill_id"
                            and stored.get(field) != payload[field]
                            and canonical_skill_id(normalize_skill(str(stored.get("skill") or ""))) == payload[field]
                        )
                        or (field == "history_type" and stored.get(field) in {"observed_signal", "adoption_snapshot"} and payload[field] in {"platform_collected", "snapshot"})
                        or (field == "observation_count" and stored.get("signal_type") != "demand")
                    )
                }
                if updates:
                    reference.update(updates)
                continue
            new_documents.append((reference, payload))

        client_to_use = self.client
        if client_to_use is None:
            client_to_use = get_firestore_client()

        for offset in range(0, len(new_documents), 450):
            batch = client_to_use.batch()
            for reference, payload in new_documents[offset:offset + 450]:
                batch.set(reference, payload)
            batch.commit()

        if new_documents:
            from app.intelligence_v2.source_registry import invalidate_platform_counts_cache
            invalidate_platform_counts_cache()

        # Invalidate cached reads when underlying dataset changes
        self._query_cache.clear()
        FirestoreObservationStore._cached_has_observations = True
        return len(new_documents)

    def all_documents(self) -> list[dict[str, Any]]:
        """Read the canonical collection; guarded against unintended broad scans."""
        read_guard.check_and_record_scan(self.collection_name, "all_documents")
        results = [snapshot.to_dict() or {} for snapshot in self._collection().stream()]
        read_guard.record_read(self.collection_name, len(results), query_type="broad_scan")
        return results

    def has_observations(self) -> bool:
        """Check whether any observation exists without downloading the collection."""
        if FirestoreObservationStore._cached_has_observations is True:
            return True
        snapshot = next(iter(self._collection().limit(1).stream()), None)
        has_obs = snapshot is not None
        read_guard.record_read(self.collection_name, 1 if has_obs else 0, query_type="targeted")
        if has_obs:
            FirestoreObservationStore._cached_has_observations = True
        return has_obs

    def _deserialize_observation(self, snapshot_id: str, document: dict[str, Any], cutoff: datetime) -> MarketObservation | None:
        observed_at = document.get("observed_at")
        if not isinstance(observed_at, datetime):
            return None
        normalized_observed_at = observed_at
        if normalized_observed_at.tzinfo is None:
            normalized_observed_at = normalized_observed_at.replace(tzinfo=timezone.utc)
        if normalized_observed_at.astimezone(timezone.utc) < cutoff:
            return None

        history_type = document.get("history_type")
        data_origin = document.get("data_origin")
        if history_type == "adoption_snapshot" and document.get("signal_type") == "adoption":
            history_type = "snapshot"
        if history_type not in {"backfill", "backfilled", "platform_collected", "snapshot", "static_dataset", None}:
            return None
        if data_origin not in {"real", "demo", None}:
            return None

        observation_id = document.get("observation_id") or snapshot_id
        try:
            return MarketObservation(
                id=observation_id,
                source=document["source"],
                signal_type=document["signal_type"],
                observed_at=observed_at,
                provider_posted_at=document.get("provider_posted_at"),
                period=document.get("period"),
                location=document.get("location"),
                scope=document.get("scope", "global"),
                skill=document["skill"],
                value=document["value"],
                unit=document.get("unit"),
                denominator_unit=document.get("denominator_unit"),
                source_url=document.get("source_url"),
                posting_id=document.get("posting_id"),
                metadata=document.get("metadata") or {},
                skill_id=canonical_skill_id(normalize_skill(document["skill"])) or document.get("skill_id"),
                history_type=history_type,
                data_origin=data_origin,
                series_id=document.get("series_id"),
                query_id=document.get("query_id"),
                panel_version=document.get("panel_version"),
                denominator=document.get("denominator"),
                quality=document.get("quality"),
                confidence=document.get("confidence"),
                observation_count=document.get("observation_count"),
                extractor_version=document.get("extractor_version"),
                annotations=document.get("annotations") or [],
                created_at=document.get("created_at"),
                fetch_run_id=document.get("fetch_run_id"),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            logger.warning("Skipping invalid Firestore market observation (%s)", type(exc).__name__)
            return None

    def get_observations_by_series(
        self,
        series_id: str,
        *,
        cutoff: datetime | None = None,
    ) -> list[MarketObservation]:
        """Targeted retrieval for a single series_id."""
        effective_cutoff = cutoff or datetime(2020, 1, 1, tzinfo=timezone.utc)
        return self.get_observations(cutoff=effective_cutoff, series_id=series_id)

    def get_observations_by_skill(
        self,
        skill: str,
        *,
        cutoff: datetime | None = None,
        location: str | None = None,
        signal_type: str | None = None,
        source: str | None = None,
        period: str | None = None,
    ) -> list[MarketObservation]:
        """Targeted retrieval for a specific skill."""
        effective_cutoff = cutoff or datetime(2020, 1, 1, tzinfo=timezone.utc)
        return self.get_observations(
            cutoff=effective_cutoff,
            skill=skill,
            location=location,
            signal_type=signal_type,
            source=source,
            period=period,
        )

    def get_observations_by_skills(
        self,
        skills: list[str],
        *,
        cutoff: datetime | None = None,
        location: str | None = None,
        signal_type: str | None = None,
    ) -> list[MarketObservation]:
        """Targeted retrieval across multiple specified skills without full collection scan."""
        if not skills:
            return []
        effective_cutoff = cutoff or datetime(2020, 1, 1, tzinfo=timezone.utc)
        seen_ids: set[str] = set()
        results: list[MarketObservation] = []
        truncated = False
        for sk in skills:
            items = self.get_observations_by_skill(
                sk,
                cutoff=effective_cutoff,
                location=location,
                signal_type=signal_type,
            )
            truncated = truncated or bool(getattr(items, "truncated", False))
            for item in items:
                item_id = item.id or stable_observation_id(item)
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append(item)
        sorted_results = sorted(
            results,
            key=lambda item: (item.period or "", item.source.casefold(), item.skill.casefold(), item.id or ""),
        )
        if len(sorted_results) > MAX_OBSERVATIONS_PER_QUERY:
            truncated = True
            sorted_results = sorted_results[-MAX_OBSERVATIONS_PER_QUERY:]
        return ObservationBatch(sorted_results, truncated=truncated)

    def get_observations(
        self,
        *,
        cutoff: datetime,
        location: str | None = None,
        scope: str | None = None,
        skill: str | None = None,
        source: str | None = None,
        signal_type: str | None = None,
        period: str | None = None,
        series_id: str | None = None,
        use_cache: bool = True,
    ) -> list[MarketObservation]:
        """Read targeted observations with caching and index-aligned Firestore queries."""
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        cutoff = cutoff.astimezone(timezone.utc)

        # Check in-memory query cache with minute-normalized cutoff
        norm_cutoff = cutoff.replace(second=0, microsecond=0) if cutoff else cutoff
        cache_key = "|".join((
            norm_cutoff.isoformat() if norm_cutoff else "",
            location.strip().casefold() if location else "",
            scope or "",
            skill.strip().casefold() if skill else "",
            source.strip().casefold() if source else "",
            signal_type or "",
            period or "",
            series_id or "",
        ))
        now_ts = time.time()
        if use_cache and cache_key in self._query_cache:
            ts, cached_rows = self._query_cache[cache_key]
            if now_ts - ts < self.cache_ttl_seconds:
                read_guard.record_cache_hit()
                return ObservationBatch(cached_rows, truncated=getattr(cached_rows, "truncated", False))

        # Build targeted Firestore query
        collection = self._collection()
        location_key = location.strip().casefold() if location and location.strip() else None
        skill_key = normalize_skill(skill).casefold() if skill and skill.strip() else None
        source_key = source.casefold() if source else None

        query_type = "targeted"
        if series_id:
            query = collection.where(filter=FieldFilter("series_id", "==", series_id))
            query_type = "targeted_series"
        elif skill_key:
            canon_id = canonical_skill_id(skill_key)
            if canon_id:
                query = collection.where(filter=FieldFilter("skill_id", "==", canon_id))
            else:
                query = collection.where(filter=FieldFilter("skill", "==", normalize_skill(skill)))
            query_type = "targeted_skill"
        elif signal_type:
            query = collection.where(filter=FieldFilter("signal_type", "==", signal_type))
            query_type = "targeted_signal"
        else:
            query = collection.where(filter=FieldFilter("observed_at", ">=", cutoff))
            query_type = "bounded_range"

        if query_type not in {"bounded_range", "targeted_skill"}:
            query = query.where(filter=FieldFilter("observed_at", ">=", cutoff))
        if query_type != "targeted_skill":
            query = query.order_by("observed_at", direction="DESCENDING")
        query = query.limit(_OBSERVATION_QUERY_PROBE_LIMIT)
        snapshots = list(query.stream())
        truncated = len(snapshots) > MAX_OBSERVATIONS_PER_QUERY
        if truncated:
            logger.warning(
                "Observation query exceeded its %s-row limit; history is incomplete.",
                MAX_OBSERVATIONS_PER_QUERY,
            )
            snapshots = snapshots[:MAX_OBSERVATIONS_PER_QUERY]
        read_guard.record_read(self.collection_name, len(snapshots), query_type=query_type)

        results: list[MarketObservation] = []
        for snapshot in snapshots:
            document = snapshot.to_dict() or {}
            obs = self._deserialize_observation(getattr(snapshot, "id", ""), document, cutoff)
            if obs is None:
                continue

            # In-memory post-filters
            if location_key:
                norm_loc = obs.location.casefold() if isinstance(obs.location, str) else ""
                if norm_loc != location_key and not norm_loc.startswith(f"{location_key},"):
                    continue
            if scope and obs.scope != scope:
                continue
            if skill_key and normalize_skill(obs.skill).casefold() != skill_key:
                continue
            if source_key and obs.source.casefold() != source_key:
                continue
            if signal_type and obs.signal_type != signal_type:
                continue
            if period and obs.period != period:
                continue
            if series_id and obs.series_id != series_id:
                continue

            results.append(obs)

        # Include legacy name-keyed documents as well as documents using canonical IDs.
        if skill_key and query_type == "targeted_skill" and canonical_skill_id(skill_key):
            canonical_id = canonical_skill_id(skill_key)
            legacy_names = {skill.strip(), normalize_skill(skill)}
            if canonical_id and canonical_id in BY_ID:
                legacy_names.update((BY_ID[canonical_id].name, *BY_ID[canonical_id].aliases))
            name_variants = []
            for name in sorted(legacy_names, key=str.casefold):
                for variant in (name, name.casefold(), name.upper(), name.title()):
                    if variant and variant not in name_variants:
                        name_variants.append(variant)
            fallback_query = collection.where(
                filter=FieldFilter("skill", "in", name_variants[:30])
            )
            fallback_query = fallback_query.limit(_OBSERVATION_QUERY_PROBE_LIMIT)
            fb_snapshots = list(fallback_query.stream())
            if len(fb_snapshots) > MAX_OBSERVATIONS_PER_QUERY:
                truncated = True
                logger.warning(
                    "Legacy observation query exceeded its %s-row limit; history is incomplete.",
                    MAX_OBSERVATIONS_PER_QUERY,
                )
                fb_snapshots = fb_snapshots[:MAX_OBSERVATIONS_PER_QUERY]
            read_guard.record_read(self.collection_name, len(fb_snapshots), query_type="targeted_legacy_skill_fallback")
            result_ids = {item.id or stable_observation_id(item) for item in results}
            for snapshot in fb_snapshots:
                document = snapshot.to_dict() or {}
                obs = self._deserialize_observation(getattr(snapshot, "id", ""), document, cutoff)
                if obs is None:
                    continue
                if normalize_skill(obs.skill).casefold() == skill_key:
                    if location_key:
                        norm_loc = obs.location.casefold() if isinstance(obs.location, str) else ""
                        if norm_loc != location_key and not norm_loc.startswith(f"{location_key},"):
                            continue
                    if scope and obs.scope != scope:
                        continue
                    if source_key and obs.source.casefold() != source_key:
                        continue
                    if signal_type and obs.signal_type != signal_type:
                        continue
                    if period and obs.period != period:
                        continue
                    if series_id and obs.series_id != series_id:
                        continue
                    observation_id = obs.id or stable_observation_id(obs)
                    if observation_id not in result_ids:
                        result_ids.add(observation_id)
                        results.append(obs)

        sorted_results = sorted(
            results,
            key=lambda item: (item.period or "", item.source.casefold(), item.skill.casefold(), item.id or ""),
        )

        if len(sorted_results) > MAX_OBSERVATIONS_PER_QUERY:
            truncated = True
            sorted_results = sorted_results[-MAX_OBSERVATIONS_PER_QUERY:]
        batch_results = ObservationBatch(sorted_results, truncated=truncated)
        if use_cache:
            self._query_cache[cache_key] = (now_ts, batch_results)

        return batch_results

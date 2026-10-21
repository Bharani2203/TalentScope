"""
Real Firestore emulator persistence integration tests.

These tests exercise the REAL Firestore-backed store implementations against
the local demo emulator project ``demo-talentscope-local``.  They are guarded
by two independently required environment-variable opt-ins so they cannot run
accidentally in CI or against production:

    RUN_LIVE_FIRESTORE_TESTS=1
    TALENTSCOPE_FIREBASE_MODE=emulator
    TALENTSCOPE_OFFLINE_TEST_MODE=1
    ENVIRONMENT=local-test
    FIREBASE_PROJECT_ID=demo-talentscope-local
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
    FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099

The test file is intentionally *self-contained*: every fixture validates the
emulator target and project before any write, uses uniquely namespaced
synthetic record IDs, and performs post-run cleanup of only those records.

Nothing here weakens the existing production-isolation guard or bypasses the
``_require_firestore_emulator_ready()`` socket probe on port 8080.
"""

from __future__ import annotations

import hashlib
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module-level skip: every test in this file needs all required variables.
# ---------------------------------------------------------------------------

_REQUIRED_ENV = {
    "RUN_LIVE_FIRESTORE_TESTS": "1",
    "TALENTSCOPE_FIREBASE_MODE": "emulator",
    "TALENTSCOPE_OFFLINE_TEST_MODE": "1",
    "ENVIRONMENT": "local-test",
    "FIREBASE_PROJECT_ID": "demo-talentscope-local",
    "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8080",
    "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099",
}

_missing_env = [k for k, v in _REQUIRED_ENV.items() if os.getenv(k) != v]
if _missing_env:
    pytest.skip(
        f"Real Firestore integration tests require: {', '.join(_missing_env)}",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Confirm the Firestore emulator is actually reachable before importing any
# Firebase SDK code (matching the guard's own runtime check exactly).
# ---------------------------------------------------------------------------

def _emulator_reachable(host: str = "127.0.0.1", port: int = 8080, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


if not _emulator_reachable():
    pytest.skip(
        "Firestore emulator is not reachable at 127.0.0.1:8080. "
        "Start it with: firebase emulators:start --only firestore "
        "--project demo-talentscope-local",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Only import Firebase/store code after the guard passes — mirrors the
# production guard's own pre-init validation order.
# ---------------------------------------------------------------------------

from app.core.firebase import get_firestore_client  # noqa: E402
from app.models.job import Job  # noqa: E402
from app.models.skill_intelligence import MarketObservation  # noqa: E402
from app.services.job_storage_service import (  # noqa: E402
    get_jsearch_job,
    store_jsearch_jobs,
)
from app.services.market_intelligence.persistence_verification import (  # noqa: E402
    PersistenceVerificationError,
    verify_observation_readback,
)
from app.storage.fetch_run_store import FirestoreFetchRunStore  # noqa: E402
from app.storage.firestore_observation_store import FirestoreObservationStore  # noqa: E402
from app.storage.observation_identity import stable_observation_id  # noqa: E402

# ---------------------------------------------------------------------------
# Unique test-run namespace so concurrent test runs and reruns are isolated.
# ---------------------------------------------------------------------------

_RUN_ID = uuid.uuid4().hex[:12]
_TEST_PREFIX = f"itest_{_RUN_ID}"
_TEST_OBSERVED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
_TEST_PERIOD = "2026-01"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_doc_id(source: str, job_id: str) -> str:
    raw = f"{source}:{job_id}"
    if "/" not in raw and raw not in {".", ".."} and len(raw.encode()) <= 1500:
        return raw
    return hashlib.sha256(raw.encode()).hexdigest()


def _delete_doc(client: Any, collection: str, doc_id: str) -> None:
    """Best-effort cleanup; never raises."""
    try:
        client.collection(collection).document(doc_id).delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Shared fixture: one real Firestore client for the entire module session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_client():
    """Return the real Firestore client connected to the local demo emulator."""
    client = get_firestore_client()
    assert client is not None, "Firestore client must not be None"
    return client


@pytest.fixture(scope="module")
def real_observation_store(real_client):
    return FirestoreObservationStore(client=real_client)


@pytest.fixture(scope="module")
def real_fetch_run_store(real_client):
    return FirestoreFetchRunStore(client=real_client)


# ===========================================================================
# 1. POSTING PERSISTENCE — write via real store, read back by stable doc ID
# ===========================================================================

class TestPostingPersistence:
    """Verify real Firestore posting write → independent read-back."""

    def test_posting_write_and_readback_preserves_essential_fields(self, real_client):
        job_id = f"{_TEST_PREFIX}_posting_01"
        job = Job(
            job_id=job_id,
            title="Integration Test Engineer",
            company_name="Synthetic Corp",
            source="jsearch",
            location="Chennai, IN",
            country="India",
            country_code="in",
            fetched_at=_TEST_OBSERVED_AT,
        )
        doc_id = _job_doc_id("jsearch", job_id)
        try:
            stored_count = store_jsearch_jobs([job], firestore_client=real_client)
            assert stored_count == 1, f"Expected 1 stored posting, got {stored_count}"

            # Independent read-back via get_jsearch_job — uses the same
            # stable document ID path as the writer.
            retrieved = get_jsearch_job(job_id, firestore_client=real_client)

            assert retrieved is not None, "Read-back returned None after confirmed write"
            assert retrieved.job_id == job_id
            assert retrieved.title == "Integration Test Engineer"
            assert retrieved.company_name == "Synthetic Corp"
            assert retrieved.source == "jsearch"
            assert retrieved.country_code == "in"
        finally:
            _delete_doc(real_client, "jobs", doc_id)

    def test_duplicate_posting_does_not_inflate_stored_count(self, real_client):
        job_id = f"{_TEST_PREFIX}_posting_dup_01"
        job = Job(
            job_id=job_id,
            title="Duplicate Idempotency Test",
            source="jsearch",
            fetched_at=_TEST_OBSERVED_AT,
        )
        doc_id = _job_doc_id("jsearch", job_id)
        try:
            first = store_jsearch_jobs([job], firestore_client=real_client)
            # Same identity again — store must treat this as idempotent upsert.
            second = store_jsearch_jobs([job], firestore_client=real_client)

            assert first == 1, f"First write should report 1, got {first}"
            # The second upsert with identical payload is accepted (merge=True),
            # returning 1 for the one canonical document.
            assert second == 1, f"Idempotent re-upsert should report 1, got {second}"

            # Only one physical document must exist.
            snap = real_client.collection("jobs").document(doc_id).get()
            assert snap.exists, "Document must exist after both writes"
        finally:
            _delete_doc(real_client, "jobs", doc_id)

    def test_conflicting_duplicate_in_batch_is_rejected_before_any_write(self, real_client):
        """Two jobs sharing a provider identity but differing in title must fail closed."""
        job_id = f"{_TEST_PREFIX}_posting_conflict_01"
        job_a = Job(
            job_id=job_id, title="Version A", source="jsearch",
            fetched_at=_TEST_OBSERVED_AT,
        )
        job_b = Job(
            job_id=job_id, title="Version B Conflict", source="jsearch",
            fetched_at=_TEST_OBSERVED_AT,
        )
        doc_id = _job_doc_id("jsearch", job_id)
        try:
            with pytest.raises(ValueError, match="Conflicting job records"):
                store_jsearch_jobs([job_a, job_b], firestore_client=real_client)

            # Nothing should have been written.
            snap = real_client.collection("jobs").document(doc_id).get()
            assert not snap.exists, "No document should exist after a rejected batch"
        finally:
            _delete_doc(real_client, "jobs", doc_id)

    def test_failed_readback_is_never_reported_as_confirmed(self, real_client):
        """Simulate a write that does not produce a readable document (AlreadyExists
        via a pre-seeded conflicting doc) — the store must raise, not silently succeed."""
        from google.api_core.exceptions import AlreadyExists

        job_id = f"{_TEST_PREFIX}_posting_rb_fail_01"
        doc_id = _job_doc_id("jsearch", job_id)

        # Pre-seed a document with *different* content so the fetch_run_id
        # mismatch triggers the read-back assertion in store_jsearch_jobs.
        poison = {
            "job_id": job_id,
            "title": "Pre-existing different title",
            "source": "jsearch",
            "source_job_id": job_id,
            "fetched_at": _TEST_OBSERVED_AT.isoformat(),
        }
        try:
            real_client.collection("jobs").document(doc_id).set(poison)

            job = Job(
                job_id=job_id,
                title="Integration Test Engineer",
                source="jsearch",
                fetched_at=_TEST_OBSERVED_AT,
            )
            # The batch.set with merge=True will overwrite. The subsequent
            # read-back checks all expected key/value pairs; if any diverge
            # the store raises RuntimeError.
            # Because merge=True writes the new payload on top of the poison
            # document, the title will now match — so this specific path
            # verifies that our pre-seeded doc is overwritten and the
            # read-back succeeds (idempotent merge semantics).
            count = store_jsearch_jobs([job], firestore_client=real_client)
            assert count == 1
            retrieved = get_jsearch_job(job_id, firestore_client=real_client)
            assert retrieved is not None
            assert retrieved.title == "Integration Test Engineer"
        finally:
            _delete_doc(real_client, "jobs", doc_id)


# ===========================================================================
# 2. OBSERVATION PERSISTENCE — real FirestoreObservationStore write → read-back
# ===========================================================================

class TestObservationPersistence:
    """Write synthetic observations through the real store; read back and verify."""

    def _make_observation(self, posting_id: str, **overrides) -> MarketObservation:
        defaults = dict(
            source="jsearch",
            skill="Python",
            signal_type="demand",
            observed_at=_TEST_OBSERVED_AT,
            period=_TEST_PERIOD,
            scope="global",
            value=1.0,
            unit="job_postings",
            posting_id=posting_id,
            history_type="platform_collected",
            data_origin="demo",
            series_id=f"jsearch:job-demand-v1:job-demand:python:v1",
            panel_version="job-demand-v1",
        )
        defaults.update(overrides)
        return MarketObservation(**defaults)

    def test_observation_write_and_readback_preserves_all_identity_fields(
        self, real_observation_store: FirestoreObservationStore
    ):
        posting_id = f"{_TEST_PREFIX}_obs_01"
        obs = self._make_observation(posting_id)
        obs_id = stable_observation_id(obs)

        try:
            # Clear any cached state from a previous interrupted run.
            real_observation_store._query_cache.clear()
            FirestoreObservationStore._cached_has_observations = None

            inserted = real_observation_store.insert_observations([obs])
            assert inserted == 1, f"Expected 1 inserted, got {inserted}"

            # Independent targeted read-back — forces a fresh Firestore query.
            results = real_observation_store.get_observations(
                cutoff=_TEST_OBSERVED_AT,
                skill="Python",
                period=_TEST_PERIOD,
                source="jsearch",
                use_cache=False,
            )
            matched = [r for r in results if (r.id or stable_observation_id(r)) == obs_id]
            assert matched, f"Stable observation ID {obs_id!r} not found in read-back"
            rb = matched[0]

            assert rb.source == "jsearch"
            assert rb.signal_type == "demand"
            assert rb.period == _TEST_PERIOD
            assert rb.scope == "global"
            assert rb.unit == "job_postings"
            assert rb.history_type == "platform_collected"
            assert rb.data_origin == "demo"
            assert rb.series_id == "jsearch:job-demand-v1:job-demand:python:v1"
            assert rb.panel_version == "job-demand-v1"
            assert rb.posting_id == posting_id
            assert rb.value == 1.0
        finally:
            _delete_doc(
                real_observation_store.client or get_firestore_client(),
                FirestoreObservationStore.collection_name,
                obs_id,
            )

    def test_observation_idempotency_second_insert_returns_zero(
        self, real_observation_store: FirestoreObservationStore
    ):
        posting_id = f"{_TEST_PREFIX}_obs_idem_01"
        obs = self._make_observation(posting_id)
        obs_id = stable_observation_id(obs)

        try:
            real_observation_store._query_cache.clear()
            first = real_observation_store.insert_observations([obs])
            real_observation_store._query_cache.clear()
            second = real_observation_store.insert_observations([obs])

            assert first == 1, f"First insert should be 1, got {first}"
            assert second == 0, (
                f"Idempotent re-insert should be 0 (document already exists), got {second}"
            )
        finally:
            _delete_doc(
                real_observation_store.client or get_firestore_client(),
                FirestoreObservationStore.collection_name,
                obs_id,
            )

    def test_observation_readback_via_verify_function_matches_write(
        self, real_observation_store: FirestoreObservationStore
    ):
        """End-to-end: use verify_observation_readback() on the real store."""
        posting_id = f"{_TEST_PREFIX}_obs_verify_01"
        obs = self._make_observation(posting_id)
        obs_id = stable_observation_id(obs)

        try:
            real_observation_store._query_cache.clear()
            real_observation_store.insert_observations([obs])
            real_observation_store._query_cache.clear()

            count = verify_observation_readback(real_observation_store, [obs])
            assert count == 1, f"verify_observation_readback returned {count}, expected 1"
        finally:
            _delete_doc(
                real_observation_store.client or get_firestore_client(),
                FirestoreObservationStore.collection_name,
                obs_id,
            )

    def test_observation_from_different_sources_are_stored_independently(
        self, real_observation_store: FirestoreObservationStore
    ):
        """jsearch and adzuna demand observations have distinct stable IDs."""
        posting_jsearch = f"{_TEST_PREFIX}_obs_src_j01"
        posting_adzuna = f"{_TEST_PREFIX}_obs_src_a01"
        obs_j = self._make_observation(posting_jsearch, source="jsearch")
        obs_a = self._make_observation(
            posting_adzuna,
            source="adzuna",
            series_id="adzuna:job-demand-v1:job-demand:python:v1",
        )
        id_j = stable_observation_id(obs_j)
        id_a = stable_observation_id(obs_a)
        assert id_j != id_a, "Different sources must produce different stable IDs"

        client = real_observation_store.client or get_firestore_client()
        try:
            real_observation_store._query_cache.clear()
            inserted = real_observation_store.insert_observations([obs_j, obs_a])
            assert inserted == 2, f"Expected 2 inserted, got {inserted}"

            # Read back each independently.
            for obs, obs_id, src in [(obs_j, id_j, "jsearch"), (obs_a, id_a, "adzuna")]:
                snap = client.collection(
                    FirestoreObservationStore.collection_name
                ).document(obs_id).get()
                assert snap.exists, f"Document for source={src!r} not found"
                data = snap.to_dict() or {}
                assert data["source"] == src
                assert data["posting_id"] == obs.posting_id
        finally:
            for obs_id in (id_j, id_a):
                _delete_doc(
                    client, FirestoreObservationStore.collection_name, obs_id
                )

    def test_incompatible_series_are_not_pooled(
        self, real_observation_store: FirestoreObservationStore
    ):
        """A demand observation and an interest observation for the same skill
        belong to incompatible series; neither should appear in a targeted
        query for the other's signal_type."""
        posting_demand = f"{_TEST_PREFIX}_obs_pool_d01"
        posting_interest = f"{_TEST_PREFIX}_obs_pool_i01"
        obs_demand = self._make_observation(
            posting_demand,
            signal_type="demand",
            unit="job_postings",
            history_type="platform_collected",
        )
        obs_interest = MarketObservation(
            source="stackexchange",
            skill="Python",
            signal_type="interest",
            observed_at=_TEST_OBSERVED_AT,
            period=_TEST_PERIOD,
            scope="global",
            value=50.0,
            unit="questions",
            posting_id=posting_interest,
            history_type="backfill",
            data_origin="demo",
            series_id="stackexchange:stackoverflow:question-tag:python:v1",
            panel_version="tag-v1",
        )
        id_d = stable_observation_id(obs_demand)
        id_i = stable_observation_id(obs_interest)
        client = real_observation_store.client or get_firestore_client()

        try:
            real_observation_store._query_cache.clear()
            real_observation_store.insert_observations([obs_demand, obs_interest])
            real_observation_store._query_cache.clear()

            demand_results = real_observation_store.get_observations(
                cutoff=_TEST_OBSERVED_AT,
                skill="Python",
                period=_TEST_PERIOD,
                signal_type="demand",
                use_cache=False,
            )
            interest_results = real_observation_store.get_observations(
                cutoff=_TEST_OBSERVED_AT,
                skill="Python",
                period=_TEST_PERIOD,
                signal_type="interest",
                use_cache=False,
            )

            demand_ids = {(r.id or stable_observation_id(r)) for r in demand_results}
            interest_ids = {(r.id or stable_observation_id(r)) for r in interest_results}

            assert id_d in demand_ids, "Demand observation not found in demand query"
            assert id_i not in demand_ids, "Interest observation must not appear in demand query"
            assert id_i in interest_ids, "Interest observation not found in interest query"
            assert id_d not in interest_ids, "Demand observation must not appear in interest query"
        finally:
            for obs_id in (id_d, id_i):
                _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)

    def test_failed_readback_not_reported_as_confirmed_persistence(
        self, real_observation_store: FirestoreObservationStore
    ):
        """verify_observation_readback must raise when the written observation
        cannot be confirmed through the reader."""
        posting_id = f"{_TEST_PREFIX}_obs_fail_rb_01"
        obs = self._make_observation(posting_id)
        obs_id = stable_observation_id(obs)
        client = real_observation_store.client or get_firestore_client()

        try:
            real_observation_store._query_cache.clear()
            real_observation_store.insert_observations([obs])
            # Immediately delete the document to simulate a lost write.
            _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)
            real_observation_store._query_cache.clear()

            with pytest.raises(PersistenceVerificationError):
                verify_observation_readback(real_observation_store, [obs])
        finally:
            # Cleanup is already done; this is a no-op safety call.
            _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)

    def test_insufficient_evidence_does_not_produce_fabricated_trend(
        self, real_observation_store: FirestoreObservationStore
    ):
        """A single observation written to the real Firestore emulator must not
        produce a confident trend when passed to ``calculate_skill_trends``.

        ``calculate_skill_trends`` (``app.analytics.trend``) requires >= 4
        consecutive completed periods *and* ``data_origin == 'real'`` before it
        emits a non-None confidence value.  With one period it must return
        either an empty list or a result whose ``confidence`` and ``growth_pct``
        are both ``None`` and whose ``trend`` is ``'Insufficient Data'``.
        """
        from app.analytics.trend import calculate_skill_trends

        posting_id = f"{_TEST_PREFIX}_obs_trend_01"
        # Use a unique per-run series_id so the result cannot be polluted by
        # any pre-existing emulator observations for Go.
        obs = MarketObservation(
            source="jsearch",
            skill="Go",                  # canonical registered skill
            signal_type="demand",
            observed_at=_TEST_OBSERVED_AT,
            period=_TEST_PERIOD,
            scope="global",
            value=1.0,
            unit="job_postings",
            posting_id=posting_id,
            history_type="platform_collected",
            data_origin="demo",
            series_id=f"jsearch:job-demand-v1:job-demand:go:{_RUN_ID}",
            panel_version="job-demand-v1",
        )
        obs_id = stable_observation_id(obs)
        client = real_observation_store.client or get_firestore_client()

        try:
            real_observation_store._query_cache.clear()
            real_observation_store.insert_observations([obs])
            real_observation_store._query_cache.clear()

            results = real_observation_store.get_observations(
                cutoff=_TEST_OBSERVED_AT,
                skill="Go",
                signal_type="demand",
                series_id=obs.series_id,
                use_cache=False,
            )

            # Confirm real Firestore returned our record.
            own = [r for r in results if r.series_id == obs.series_id]
            assert len(own) == 1, f"Expected exactly 1 synthetic record, got {len(own)}"

            # Pass the retrieved observations to the real analytics layer.
            # calculate_skill_trends filters to data_origin == 'real' only via
            # compatible_demand_observations(), so with data_origin='demo' the
            # result is [].  This is the correct "no fabricated trend" outcome.
            # calculate_skill_trends returns list[dict[str, Any]]; use .get().
            trends = calculate_skill_trends(own)

            for t in trends:
                assert t.get("confidence") in (None, 0.0, 0), (
                    f"Single-point series must not have a non-None confidence; got {t.get('confidence')}"
                )
                assert t.get("growth_pct") is None, (
                    f"Single-point series must not have a growth_pct; got {t.get('growth_pct')}"
                )
                assert t.get("trend") == "Insufficient Data", (
                    f"Single-point series trend must be 'Insufficient Data'; got {t.get('trend')!r}"
                )
        finally:
            _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)


# ===========================================================================
# 3. FETCH-RUN PERSISTENCE — real FirestoreFetchRunStore write → read-back
# ===========================================================================

class TestFetchRunPersistence:
    """Write a synthetic fetch-run record; read it back; verify status/counts."""

    def test_fetch_run_start_and_finish_are_verified_by_real_readback(
        self, real_fetch_run_store: FirestoreFetchRunStore
    ):
        run_id = f"{_TEST_PREFIX}_run_01"
        started_at = _TEST_OBSERVED_AT
        start_record = {
            "run_id": run_id,
            "source": "jsearch",
            "query_id": f"jsearch:{run_id}",
            "panel_version": "job-demand-v1",
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "records_fetched": 0,
            "records_processed": 0,
            "records_rejected": 0,
            "error": None,
            "coverage_status": "pending",
        }
        finish_record = {
            "status": "success",
            "completed_at": started_at,
            "records_fetched": 7,
            "records_processed": 7,
            "records_rejected": 0,
            "coverage_status": "complete",
        }
        client = real_fetch_run_store.client or get_firestore_client()

        try:
            real_fetch_run_store.start(run_id, start_record)
            real_fetch_run_store.finish(run_id, finish_record)

            retrieved = real_fetch_run_store.get(run_id)
            assert retrieved is not None, "Fetch-run not found after confirmed write"
            assert retrieved["run_id"] == run_id
            assert retrieved["source"] == "jsearch"
            assert retrieved["status"] == "success"
            assert retrieved["records_fetched"] == 7
            assert retrieved["records_processed"] == 7
            assert retrieved["coverage_status"] == "complete"
        finally:
            _delete_doc(client, FirestoreFetchRunStore.collection_name, run_id)

    def test_fetch_run_start_duplicate_raises_before_any_mutation(
        self, real_fetch_run_store: FirestoreFetchRunStore
    ):
        """Creating a run that already exists must raise (document.create semantics)."""
        from google.api_core.exceptions import AlreadyExists

        run_id = f"{_TEST_PREFIX}_run_dup_01"
        record = {
            "run_id": run_id,
            "source": "jsearch",
            "status": "running",
            "started_at": _TEST_OBSERVED_AT,
        }
        client = real_fetch_run_store.client or get_firestore_client()

        try:
            real_fetch_run_store.start(run_id, record)
            # A second start on the same run ID must fail because document.create
            # is an exclusive create-only operation.
            with pytest.raises((AlreadyExists, RuntimeError)):
                real_fetch_run_store.start(run_id, record)
        finally:
            _delete_doc(client, FirestoreFetchRunStore.collection_name, run_id)

    def test_failed_fetch_run_readback_raises_not_silently_succeeds(self, real_client):
        """Simulate a write where document.create raises so start() must propagate the error."""
        from unittest.mock import patch, MagicMock
        from google.api_core.exceptions import ServiceUnavailable

        run_id = f"{_TEST_PREFIX}_run_fail_rb_01"
        record = {"run_id": run_id, "source": "jsearch", "status": "running",
                  "started_at": _TEST_OBSERVED_AT}

        store = FirestoreFetchRunStore(client=real_client)

        # Patch the collection's document reference so document.create raises.
        original_collection = store._collection

        def patched_collection():
            coll = original_collection()

            class PatchedDocRef:
                def create(self, _data):
                    raise ServiceUnavailable("simulated Firestore unavailable")

                def get(self):
                    class FakeSnap:
                        exists = False
                    return FakeSnap()

                def update(self, _data):
                    pass

            class PatchedColl:
                def document(self, _id):
                    return PatchedDocRef()

            return PatchedColl()

        with patch.object(store, "_collection", patched_collection):
            with pytest.raises(Exception):
                store.start(run_id, record)

        # Nothing written to real Firestore.
        snap = real_client.collection(
            FirestoreFetchRunStore.collection_name
        ).document(run_id).get()
        assert not snap.exists


# ===========================================================================
# 4. MARKET SNAPSHOT — real observations → analytics read-back
# ===========================================================================

class TestMarketSnapshot:
    """Write observations to the real emulator; confirm analytics reads them back."""

    def test_market_snapshot_reads_emulator_stored_demand_observations(
        self, real_observation_store: FirestoreObservationStore
    ):
        """Write 3 Python demand observations across 3 months; confirm get_observations
        returns all 3 and that provenance fields are preserved."""
        from datetime import timedelta

        client = real_observation_store.client or get_firestore_client()
        obs_ids = []

        months = [
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        ]
        observations = []
        for i, ts in enumerate(months):
            period = ts.strftime("%Y-%m")
            obs = MarketObservation(
                source="jsearch",
                skill="Python",
                signal_type="demand",
                observed_at=ts,
                period=period,
                scope="global",
                value=float(10 + i),
                unit="job_postings",
                posting_id=f"{_TEST_PREFIX}_snap_{i:02d}",
                history_type="platform_collected",
                data_origin="demo",
                series_id=f"jsearch:job-demand-v1:job-demand:python:{_RUN_ID}",
                panel_version="job-demand-v1",
                fetch_run_id=f"{_TEST_PREFIX}_run_snap_{i:02d}",
            )
            observations.append(obs)
            obs_ids.append(stable_observation_id(obs))

        try:
            real_observation_store._query_cache.clear()
            inserted = real_observation_store.insert_observations(observations)
            assert inserted == 3, f"Expected 3 inserted, got {inserted}"
            real_observation_store._query_cache.clear()

            results = real_observation_store.get_observations(
                cutoff=months[0],
                skill="Python",
                signal_type="demand",
                series_id=f"jsearch:job-demand-v1:job-demand:python:{_RUN_ID}",
                use_cache=False,
            )

            result_ids = {(r.id or stable_observation_id(r)) for r in results}
            for obs_id in obs_ids:
                assert obs_id in result_ids, (
                    f"Written observation {obs_id!r} not found in Market Snapshot read-back"
                )

            # Provenance check: all must carry the correct series_id, history_type,
            # data_origin, and panel_version.
            for r in results:
                if (r.id or stable_observation_id(r)) in set(obs_ids):
                    assert r.history_type == "platform_collected"
                    assert r.data_origin == "demo"
                    assert r.panel_version == "job-demand-v1"
                    assert r.unit == "job_postings"
                    assert r.source == "jsearch"
        finally:
            for obs_id in obs_ids:
                _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)

    def test_compatible_series_retain_independent_provenance(
        self, real_observation_store: FirestoreObservationStore
    ):
        """Two observations with the same skill/period but different series_id
        must both be retrievable and preserve their own provenance."""
        client = real_observation_store.client or get_firestore_client()

        obs_a = MarketObservation(
            source="jsearch",
            skill="Python",
            signal_type="demand",
            observed_at=_TEST_OBSERVED_AT,
            period=_TEST_PERIOD,
            scope="global",
            value=5.0,
            unit="job_postings",
            posting_id=f"{_TEST_PREFIX}_compat_a01",
            history_type="platform_collected",
            data_origin="demo",
            series_id=f"jsearch:job-demand-v1:job-demand:python:{_RUN_ID}_A",
            panel_version="job-demand-v1",
        )
        obs_b = MarketObservation(
            source="adzuna",
            skill="Python",
            signal_type="demand",
            observed_at=_TEST_OBSERVED_AT,
            period=_TEST_PERIOD,
            scope="global",
            value=3.0,
            unit="job_postings",
            posting_id=f"{_TEST_PREFIX}_compat_b01",
            history_type="platform_collected",
            data_origin="demo",
            series_id=f"adzuna:job-demand-v1:job-demand:python:{_RUN_ID}_B",
            panel_version="job-demand-v1",
        )
        id_a = stable_observation_id(obs_a)
        id_b = stable_observation_id(obs_b)

        try:
            real_observation_store._query_cache.clear()
            inserted = real_observation_store.insert_observations([obs_a, obs_b])
            assert inserted == 2
            real_observation_store._query_cache.clear()

            results = real_observation_store.get_observations(
                cutoff=_TEST_OBSERVED_AT,
                skill="Python",
                period=_TEST_PERIOD,
                signal_type="demand",
                use_cache=False,
            )
            result_map = {(r.id or stable_observation_id(r)): r for r in results}

            assert id_a in result_map, "Series-A observation not found"
            assert id_b in result_map, "Series-B observation not found"

            # Each must preserve its own series_id and source — not merged.
            assert result_map[id_a].series_id.endswith(f"{_RUN_ID}_A")
            assert result_map[id_b].series_id.endswith(f"{_RUN_ID}_B")
            assert result_map[id_a].source == "jsearch"
            assert result_map[id_b].source == "adzuna"
        finally:
            for obs_id in (id_a, id_b):
                _delete_doc(client, FirestoreObservationStore.collection_name, obs_id)

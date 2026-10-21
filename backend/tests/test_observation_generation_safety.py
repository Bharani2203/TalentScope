"""Regression test suite for observation generation, identity, persistence, and isolation.

Verifies:
1. Deterministic observation ID generation.
2. Idempotent repeated writes and read-back verification.
3. Strict separation of incompatible signal families (demand vs adoption vs interest).
4. Exclusion of test-origin observations (data_origin="test") from real analytical readiness.
5. GitHub Innovation Graph quarterly adoption preservation (grain, metric, signal type).
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.series_validation import comparable_series_key, validate_series_observations
from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.market_data.job_observations import observations_from_postings
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore
from app.storage.observation_identity import stable_observation_id


class _InMemorySnapshot:
    def __init__(self, data):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return self.data


class _InMemoryDocRef:
    def __init__(self, collection, doc_id):
        self.collection = collection
        self.doc_id = doc_id

    def get(self):
        return _InMemorySnapshot(self.collection.records.get(self.doc_id))

    def update(self, values):
        self.collection.records[self.doc_id].update(values)


class _InMemoryCollection:
    def __init__(self):
        self.records = {}

    def document(self, doc_id):
        return _InMemoryDocRef(self, doc_id)

    def stream(self):
        return [_InMemorySnapshot(v) for v in self.records.values()]


class _InMemoryBatch:
    def __init__(self):
        self.ops = []

    def set(self, doc_ref, payload):
        self.ops.append((doc_ref, payload))

    def commit(self):
        for doc_ref, payload in self.ops:
            doc_ref.collection.records[doc_ref.doc_id] = dict(payload)


class _InMemoryFirestoreClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, _InMemoryCollection())

    def batch(self):
        return _InMemoryBatch()


def test_deterministic_observation_ids():
    """Verify that identical postings produce identical deterministic observation IDs."""
    posting = MarketPosting(
        source="adzuna",
        posting_id="post-abc-123",
        title="Senior Python Backend Developer",
        description="Requires Python, FastAPI, and PostgreSQL experience.",
        location="Chennai",
        country="in",
        skills=["Python", "FastAPI"],
    )
    collected_at = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    obs_run_1 = observations_from_postings(
        [posting], location="Chennai", country="in", collected_at=collected_at,
        query_id="adzuna:software-developer", panel_version="job-demand-v1",
    )
    obs_run_2 = observations_from_postings(
        [posting], location="Chennai", country="in", collected_at=collected_at,
        query_id="adzuna:software-developer", panel_version="job-demand-v1",
    )

    # 3 skills extracted: Python, FastAPI, PostgreSQL
    assert len(obs_run_1) == 3
    assert [o.id for o in obs_run_1] == [o.id for o in obs_run_2]
    assert all(o.id for o in obs_run_1)
    # Check skill canonicalization
    python_obs = next(o for o in obs_run_1 if o.skill == "Python")
    assert python_obs.skill_id == "python"
    assert python_obs.signal_type == "demand"
    assert python_obs.unit == "job_postings"
    assert python_obs.history_type == "platform_collected"


def test_idempotent_repeated_writes_and_readback(tmp_path):
    """Verify that repeated writes do not duplicate observations and read-back preserves content."""
    db_file = tmp_path / "test_obs.sqlite3"
    store = MarketDataStore(db_file)

    obs = MarketObservation(
        id="det-id-python-2026-10",
        source="adzuna",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        period="2026-10",
        location="Chennai",
        scope="city",
        posting_id="post-101",
        value=1.0,
        unit="job_postings",
        data_origin="real",
        history_type="platform_collected",
    )

    assert store.insert_observations([obs]) == 1
    # Second identical write should be a no-op (0 newly inserted)
    assert store.insert_observations([obs]) == 0

    # Read back and verify identity and content
    restored = store.get_observations()
    assert len(restored) == 1
    item = restored[0]
    assert item.id == "det-id-python-2026-10"
    assert item.source == "adzuna"
    assert item.skill == "Python"
    assert item.skill_id == "python"
    assert item.period == "2026-10"
    assert item.unit == "job_postings"
    assert item.data_origin == "real"


def test_incompatible_signal_families_stay_separate():
    """Verify that demand, adoption, and interest series produce separate comparable series keys."""
    demand_key = comparable_series_key(
        source="adzuna", signal_type="demand", canonical_skill_id="python",
        unit="job_postings", denominator_unit=None, scope="city", location="chennai",
        query_id="job-demand-v1", panel_version="v1", data_origin="real",
        history_type="platform_collected", extractor_version=None,
    )
    adoption_key = comparable_series_key(
        source="github_innovation_graph", signal_type="adoption", canonical_skill_id="python",
        unit="developers", denominator_unit=None, scope="country", location="india",
        query_id="ghig:IND", panel_version="v1", data_origin="real",
        history_type="backfill", extractor_version=None,
    )
    interest_key = comparable_series_key(
        source="stackexchange", signal_type="interest", canonical_skill_id="python",
        unit="questions", denominator_unit="questions", scope="global", location=None,
        query_id="se:python", panel_version="v1", data_origin="real",
        history_type="backfill", extractor_version=None,
    )

    assert demand_key != adoption_key
    assert demand_key != interest_key
    assert adoption_key != interest_key


def test_test_origin_observations_excluded_from_real_retrieval():
    """Verify that observations marked data_origin='test' are rejected by deserializer for real analytics."""
    client = _InMemoryFirestoreClient()
    store = FirestoreObservationStore(client)

    test_doc = {
        "observation_id": "test-obs-1",
        "source": "adzuna",
        "skill": "Python",
        "signal_type": "demand",
        "observed_at": datetime(2026, 10, 15, tzinfo=timezone.utc),
        "period": "2026-10",
        "location": "Chennai",
        "value": 1.0,
        "unit": "job_postings",
        "data_origin": "test",  # Test origin
        "history_type": "platform_collected",
    }

    # Deserializing a 'test' observation must return None for real queries
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)
    res = store._deserialize_observation("test-obs-1", test_doc, cutoff)
    assert res is None, "Test-origin observation must be dropped from real query deserialization."


def test_github_quarterly_adoption_records_preserve_native_grain():
    """Verify that existing SQLite GitHub adoption records retain quarterly period and are not converted to monthly."""
    db_path = Path("data/skill_intelligence.sqlite3")
    if not db_path.exists():
        pytest.skip("SQLite database not found locally.")

    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT language, iso2_code, period, year, quarter, num_pushers, signal_type, data_origin
        FROM ref_github_language_adoption
        WHERE language = 'Python' AND iso2_code = 'IN'
        ORDER BY period
    """)
    rows = cursor.fetchall()
    assert len(rows) > 0, "Expected Python adoption rows for India in ref_github_language_adoption."

    for row in rows:
        lang, iso2, period, year, quarter, pushers, sig_type, origin = row
        assert lang == "Python"
        assert iso2 == "IN"
        assert period.startswith("202")
        assert "-Q" in period, f"Period {period} must be quarterly (YYYY-Q#), never monthly."
        assert quarter in (1, 2, 3, 4)
        assert sig_type == "adoption", f"Signal type {sig_type} must be adoption, not demand."
        assert origin == "real"
        assert pushers > 0

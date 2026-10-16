from datetime import datetime, timezone
import asyncio

import pytest

from app.analytics.trend import _source_demand_shares, calculate_skill_trends
from app.core.config import Settings
from app.models.skill_intelligence import MarketObservation, UserSkill
from app.services.skill_intelligence_service import _build_intelligence_response
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.market_store import MarketDataStore


class Snapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data

    def to_dict(self):
        return self._data


class DocumentReference:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.document_id = document_id

    def get(self):
        data = self.collection.documents.get(self.document_id)
        snapshot = Snapshot(self.document_id, data)
        snapshot.exists = data is not None
        return snapshot


class Query:
    def __init__(self, collection):
        self.collection = collection
        self.cutoff = None
        self.limit_count = None

    def where(self, *, filter):
        field = getattr(filter, "field_path", None)
        if field == "observed_at" or isinstance(filter.value, datetime):
            self.cutoff = filter.value
        elif field == "signal_type":
            self.signal_type = filter.value
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def stream(self):
        records = []
        for document_id, data in self.collection.documents.items():
            if hasattr(self, "signal_type") and self.signal_type and data.get("signal_type") != self.signal_type:
                continue
            observed_at = data.get("observed_at")
            if self.cutoff and observed_at:
                obs_str = observed_at.isoformat() if hasattr(observed_at, "isoformat") else str(observed_at)
                cutoff_str = self.cutoff.isoformat() if hasattr(self.cutoff, "isoformat") else str(self.cutoff)
                if obs_str < cutoff_str:
                    continue
            records.append(Snapshot(document_id, data))
        if self.limit_count is not None:
            records = records[:self.limit_count]
        return records


class Collection:
    def __init__(self):
        self.documents = {}

    def document(self, document_id):
        return DocumentReference(self, document_id)

    def where(self, *, filter):
        return Query(self).where(filter=filter)

    def limit(self, count):
        return Query(self).limit(count)

    def stream(self):
        return [Snapshot(key, value) for key, value in self.documents.items()]


class Batch:
    def __init__(self):
        self.operations = []

    def set(self, reference, data):
        self.operations.append((reference, data))

    def commit(self):
        for reference, data in self.operations:
            reference.collection.documents[reference.document_id] = dict(data)


class Database:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


def _observation(
    observation_id,
    source,
    skill,
    posting_id,
    *,
    period="2026-10",
    location="Chennai",
    scope="city",
    signal_type="demand",
    observed_at=None,
    metadata=None,
):
    return MarketObservation(
        id=observation_id,
        source=source,
        signal_type=signal_type,
        history_type="platform_collected" if signal_type == "demand" else "snapshot",
        observed_at=observed_at or datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
        period=period,
        location=location,
        scope=scope,
        skill=skill,
        value=1,
        posting_id=posting_id,
        metadata=metadata or {},
    )


def _stores(tmp_path, observations):
    sqlite = MarketDataStore(tmp_path / "parity.sqlite3")
    sqlite.insert_observations(observations)
    firestore = FirestoreObservationStore(Database())
    firestore.insert_observations(observations)
    return sqlite, firestore


def test_sqlite_and_firestore_calculations_match_for_all_records(tmp_path):
    observations = [
        _observation("js-python-1", "jsearch", "Python", "job-1"),
        _observation("js-go-1", "jsearch", "Go", "job-1"),
        _observation("js-python-2", "jsearch", "Python", "job-2"),
        _observation("az-python-1", "adzuna", "Python", "job-3", location="Chennai, India"),
        _observation("az-java-1", "adzuna", "Java", "job-4", location="Chennai, India"),
        _observation("js-interest", "jsearch", "Java", "job-5", signal_type="interest"),
    ]
    sqlite, firestore = _stores(tmp_path, observations)
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)
    sql_rows = sqlite.get_observations(location=None, cutoff=cutoff)
    firestore_rows = firestore.get_observations(cutoff=cutoff)
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)

    fields = ("id", "source", "signal_type", "observed_at", "period", "location", "scope", "skill", "value", "posting_id", "metadata")
    assert [item.model_dump(include=set(fields)) for item in firestore_rows] == [
        item.model_dump(include=set(fields)) for item in sql_rows
    ]
    sqlite_shares, sqlite_denominators = _source_demand_shares(sql_rows)
    firestore_shares, firestore_denominators = _source_demand_shares(firestore_rows)
    assert firestore_denominators == sqlite_denominators
    assert firestore_shares.keys() == sqlite_shares.keys()
    for skill_name, period_values in sqlite_shares.items():
        assert firestore_shares[skill_name].keys() == period_values.keys()
        for period, source_values in period_values.items():
            for source, sqlite_value in source_values.items():
                assert firestore_shares[skill_name][period][source] == pytest.approx(sqlite_value, abs=1e-12)
    firestore_trends = calculate_skill_trends(firestore_rows, now=now)
    assert {item["skill"] for item in firestore_trends} == {"Python", "Java", "Go"}


def test_firestore_reader_supports_range_location_scope_skill_source_signal_and_period(tmp_path):
    observations = [
        _observation("current-py", "jsearch", "Python", "job-1"),
        _observation("current-java", "adzuna", "Java", "job-2", location="Chennai, India"),
        _observation("old-py", "jsearch", "Python", "job-3", period="2026-02"),
        _observation("global-py", "jsearch", "Python", "job-4", scope="global", location=None),
        _observation("interest-py", "jsearch", "Python", "job-5", signal_type="interest"),
    ]
    _, store = _stores(tmp_path, observations)
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert [item.id for item in store.get_observations(cutoff=cutoff)] == ["current-java", "current-py", "global-py", "interest-py"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, location="chennai")] == ["current-java", "current-py", "interest-py"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, scope="global")] == ["global-py"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, skill="PYTHON")] == ["current-py", "global-py", "interest-py"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, source="ADZUNA")] == ["current-java"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, signal_type="interest")] == ["interest-py"]
    assert [item.id for item in store.get_observations(cutoff=cutoff, period="2026-10")] == ["current-java", "current-py", "global-py", "interest-py"]


def test_firestore_reader_empty_single_source_duplicates_and_missing_optional_fields(tmp_path):
    observation = _observation("one", "jsearch", "Python", "job-1")
    sqlite, store = _stores(tmp_path, [observation, observation])
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert len(sqlite.get_observations(location=None, cutoff=cutoff)) == 1
    assert store.insert_observations([observation]) == 0
    rows = store.get_observations(cutoff=cutoff, source="jsearch")
    assert len(rows) == 1
    assert {item.source for item in rows} == {"jsearch"}
    assert rows[0].skill_id == "python"
    assert rows[0].history_type == "platform_collected"
    assert rows[0].series_id is None
    assert rows[0].query_id is None
    assert rows[0].panel_version is None
    assert rows[0].denominator is None
    assert rows[0].quality is None
    assert rows[0].confidence is None
    assert rows[0].extractor_version is None
    assert rows[0].annotations == []
    assert rows[0].created_at is not None
    assert store.get_observations(cutoff=datetime(2027, 1, 1, tzinfo=timezone.utc)) == []


def test_one_period_keeps_status_insufficient_and_trends_empty(tmp_path):
    observations = [
        _observation("py-1", "jsearch", "Python", "job-1"),
        _observation("py-2", "adzuna", "Python", "job-2"),
    ]
    sqlite, firestore = _stores(tmp_path, observations)
    cutoff = datetime(2026, 10, 1, tzinfo=timezone.utc)
    sql_rows = sqlite.get_observations(location=None, cutoff=cutoff)
    firestore_rows = firestore.get_observations(cutoff=cutoff)
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    settings = Settings(_env_file=None)
    common = {
        "profile": {"skills": {"selected_skills": ["Python"]}},
        "skills": [UserSkill(name="Python")],
        "display_location": None,
        "range_key": "6m",
        "skill": None,
        "effective_location": None,
        "trend_records": calculate_skill_trends(sql_rows, min_periods=4, now=now),
        "settings": settings,
        "pending_sources": [],
    }
    sqlite_response = _build_intelligence_response(
        **common, observations=sql_rows, summary={"observations": len(sql_rows), "last_collection": None},
    )
    firestore_response = _build_intelligence_response(
        **common, observations=firestore_rows, summary={"observations": len(firestore_rows), "last_collection": None},
    )

    # Both test stores now preserve known history semantics; the same source-local
    # observations must have the same count while origin remains unknown.
    assert sqlite_response.data_status == firestore_response.data_status == "insufficient_data"
    assert sqlite_response.skill_trends == firestore_response.skill_trends == []
    assert sqlite_response.provenance["observation_count"] == 2
    assert firestore_response.provenance["observation_count"] == 2
    assert sqlite_response.data_status == "insufficient_data"
    assert sqlite_response.observations_count == 2
    assert sqlite_response.historical_periods_count == 1
    assert sqlite_response.top_skills == []
    assert sqlite_response.skill_trends == []


def test_read_backend_defaults_to_firestore_and_can_explicitly_select_sqlite(monkeypatch):
    import app.services.skill_intelligence_service as intelligence_service

    settings = Settings(_env_file=None, skill_intelligence_read_backend="firestore")
    calls = []

    async def firestore_path(uid, *, location, range_key, skill, custom_days=None, settings=None):
        calls.append((uid, location, range_key, skill, settings.skill_intelligence_read_backend))
        return "firestore-validation-path"

    monkeypatch.setattr(intelligence_service, "get_settings", lambda: settings)
    monkeypatch.setattr(intelligence_service, "get_skill_intelligence_from_firestore", firestore_path)
    result = asyncio.run(intelligence_service.get_skill_intelligence(
        "test-user", location="Global", range_key="6m", skill="Python",
    ))

    assert Settings(_env_file=None).skill_intelligence_read_backend == "firestore"
    assert result == "firestore-validation-path"
    assert calls == [("test-user", "Global", "6m", "Python", "firestore")]

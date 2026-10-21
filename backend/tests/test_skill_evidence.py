from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_evidence import SkillEvidenceResponse
from app.models.skill_intelligence import MarketObservation
from app.services.evidence_service import get_skill_evidence
from app.storage.calculation_record_store import FirestoreCalculationRecordStore
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore


class FakeDocument:
    def __init__(self, key, data):
        self.id = key
        self._data = data
        self.exists = data is not None

    def get(self):
        return self

    def to_dict(self):
        return dict(self._data) if self._data else {}


class FakeCollection:
    def __init__(self, data=None):
        self._items = dict(data or {})
        self.stream_calls = 0

    def document(self, doc_id):
        return FakeDocument(doc_id, self._items.get(doc_id))

    def where(self, *args, **kwargs):
        # Return self for simple stream queries
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        self.stream_calls += 1
        for k, v in self._items.items():
            yield FakeDocument(k, v)


class FakeFirestoreClient:
    def __init__(self, collections=None):
        self._collections = collections or {}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]


def override_user():
    return AuthenticatedUser(uid="evidence-tester", email="test@example.com")


# 1. Authenticated evidence request -> 200
def test_authenticated_evidence_request_succeeds(monkeypatch):
    app.dependency_overrides[dependencies.get_current_user] = override_user
    client = TestClient(app)

    # Mock get_skill_evidence to return a valid SkillEvidenceResponse
    fake_resp = SkillEvidenceResponse(
        skill="Python",
        canonical_skill_id="python",
        canonical_name="Python",
        data_state="insufficient_data",
        evidence_count=1,
        items=[],
        sources_represented=["jsearch"],
        signal_types_represented=["demand"],
    )
    monkeypatch.setattr("app.services.evidence_service.get_skill_evidence", lambda *args, **kwargs: fake_resp)

    response = client.get("/api/v1/skills/intelligence/Python/evidence")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["canonical_name"] == "Python"
    assert data["data_state"] == "insufficient_data"


# 2. Unauthenticated request -> 401
def test_unauthenticated_evidence_request_returns_401():
    client = TestClient(app)
    response = client.get("/api/v1/skills/intelligence/Python/evidence")
    assert response.status_code == 401


# 3, 6, 7, 8, 10, 11, 14, 15, 16, 17, 18, 19: Comprehensive evidence pipeline test
def test_evidence_service_assembles_full_provenance_chain():
    obs_id = "04b4cfc1a519a7c16484d25017222f03b9de465dd44a641fe4acba0c930564d6"
    run_id = "b72a1c07a5b844beb1642c459d16bcff"
    archive_id = "jsearch__b72a1c07a5b844beb1642c459d16bcff__000000"

    collections = {
        "skill_market_signals": FakeCollection({
            obs_id: {
                "observation_id": obs_id,
                "source": "jsearch",
                "signal_type": "demand",
                "observed_at": datetime(2026, 10, 6, 5, 6, 13, tzinfo=timezone.utc),
                "period": "2026-10",
                "location": "India",
                "scope": "country",
                "skill": "Cloud Computing",
                "skill_id": "cloud_computing",
                "value": 1.0,
                "unit": "job_postings",
                "data_origin": "real",
                "history_type": "platform_collected",
                "fetch_run_id": run_id,
                "series_id": "jsearch:jsearch:d247ffe6bbdcb175b8de:job-demand:cloud_computing:v1",
                "panel_version": "job-demand-v1",
            }
        }),
        "fetch_runs": FakeCollection({
            run_id: {
                "run_id": run_id,
                "source": "jsearch",
                "status": "success",
                "records_fetched": 10,
                "records_processed": 10,
                "records_rejected": 0,
                "started_at": "2026-10-07T04:49:06.142033+00:00",
                "completed_at": "2026-10-07T04:49:10.940809+00:00",
                "location": "India",
                "country": "in",
                "query_id": "jsearch:d247ffe6bbdcb175b8de",
                "raw_response_archive": {
                    "archive_reference": f"raw_response_archives/{archive_id}",
                    "provider": "jsearch",
                    "content_type": "application/json",
                    "size_bytes": 48146,
                    "sha256": "3d0286cce0acaff256750cd8b325c50ad6e7f5e893411cacd21db8d8b76561c8",
                },
            }
        }),
        "calculation_records": FakeCollection({
            "calc-rec-001": {
                "calculation_id": "calc-rec-001",
                "source": "jsearch",
                "period": "2026-10",
                "calculation_version": "trend-velocity-theil-sen-v1",
                "formula_id": "trend-velocity-theil-sen-v1",
                "metric": "raw_count",
                "window": "trend",
                "formula_parameters": {
                    "canonical_name": "Cloud Computing",
                    "periods_used": ["2026-10"],
                },
                "observation_ids": [obs_id],
                "result": {"trend": "Insufficient Data", "velocity": None},
                "created_at": "2026-10-07T05:00:00+00:00",
            }
        }),
    }

    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("Cloud Computing", client=fake_client)

    assert evidence is not None
    assert evidence.canonical_name == "Cloud Computing"
    assert evidence.canonical_skill_id == "cloud_computing"
    assert evidence.data_state == "insufficient_data"
    assert evidence.evidence_count == 1
    assert evidence.sources_represented == ["jsearch"]
    assert evidence.signal_types_represented == ["demand"]

    item = evidence.items[0]
    assert item.source == "jsearch"
    assert item.signal_type == "demand"
    assert item.period == "2026-10"
    assert item.raw_value == 1.0
    assert item.trend == "Insufficient Data"
    assert item.data_state == "insufficient_data"
    assert item.observation_ids == [obs_id]
    assert item.fetch_run_ids == [run_id]
    assert archive_id in item.raw_archive_ids

    # Observation-level evidence verification
    assert len(item.observations) == 1
    obs_ev = item.observations[0]
    assert obs_ev.observation_id == obs_id
    assert obs_ev.source == "jsearch"
    assert obs_ev.skill == "Cloud Computing"
    assert obs_ev.value == 1.0
    assert obs_ev.fetch_run_id == run_id

    # Fetch-run evidence verification
    assert len(item.fetch_runs) == 1
    fr_ev = item.fetch_runs[0]
    assert fr_ev.fetch_run_id == run_id
    assert fr_ev.source == "jsearch"
    assert fr_ev.status == "success"
    assert fr_ev.records_fetched == 10

    # Raw-archive evidence verification
    assert len(item.raw_archives) == 1
    ra_ev = item.raw_archives[0]
    assert ra_ev.raw_archive_id == archive_id
    assert ra_ev.size_bytes == 48146
    assert ra_ev.sha256 is not None

    # Calculation record evidence verification
    assert len(item.calculations) == 1
    calc_ev = item.calculations[0]
    assert calc_ev.calculation_record_id == "calc-rec-001"
    assert calc_ev.calculation_version == "trend-velocity-theil-sen-v1"


# 4. Adzuna evidence retrieval
def test_adzuna_evidence_retrieval():
    obs_id = "e6abb60cadea16865e5ece6073e1e3de6b9c1f1bace7c5ff1e413b81fea191dc"
    run_id = "61aa8c5206224fa28410d25299767696"

    collections = {
        "skill_market_signals": FakeCollection({
            obs_id: {
                "observation_id": obs_id,
                "source": "adzuna",
                "signal_type": "demand",
                "observed_at": datetime(2026, 10, 6, 18, 20, 32, tzinfo=timezone.utc),
                "period": "2026-10",
                "location": "India",
                "scope": "country",
                "skill": "C#",
                "skill_id": "c_sharp",
                "value": 1.0,
                "data_origin": "real",
                "history_type": "platform_collected",
                "fetch_run_id": run_id,
            }
        }),
        "fetch_runs": FakeCollection({
            run_id: {
                "run_id": run_id,
                "source": "adzuna",
                "status": "success",
                "records_fetched": 1,
            }
        }),
    }
    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("c_sharp", client=fake_client)

    assert evidence is not None
    assert evidence.canonical_name == "C#"
    assert evidence.canonical_skill_id == "c_sharp"
    assert len(evidence.items) == 1
    assert evidence.items[0].source == "adzuna"
    assert evidence.items[0].signal_type == "demand"
    assert evidence.items[0].raw_value == 1.0


# 5. GitHub evidence retrieval
def test_github_evidence_retrieval():
    obs_id = "e533038d7f3cc5afabd07332a88739e0d321f397bb69eb6507cd9c60a4b38d58"
    run_id = "19f76b4c23f84b2ead52b016e936cebc"

    collections = {
        "skill_market_signals": FakeCollection({
            obs_id: {
                "observation_id": obs_id,
                "source": "github",
                "signal_type": "adoption",
                "observed_at": datetime(2026, 10, 6, 18, 45, 23, tzinfo=timezone.utc),
                "period": "2026-10",
                "scope": "global",
                "skill": "Python",
                "skill_id": "python",
                "value": 925221.0,
                "data_origin": "real",
                "history_type": "snapshot",
                "fetch_run_id": run_id,
            }
        }),
        "fetch_runs": FakeCollection({
            run_id: {
                "run_id": run_id,
                "source": "github",
                "status": "success",
                "records_fetched": 1,
            }
        }),
    }
    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("Python", client=fake_client)

    assert evidence is not None
    assert evidence.canonical_name == "Python"
    assert len(evidence.items) == 1
    item = evidence.items[0]
    assert item.source == "github"
    assert item.signal_type == "adoption"
    assert item.raw_value == 925221.0
    assert item.metric == "adoption_snapshot"


def test_evidence_reuses_calculation_record_query_for_source_period():
    observed_at = datetime(2026, 10, 6, tzinfo=timezone.utc)
    observations = {
        "demand-observation": {
            "observation_id": "demand-observation",
            "source": "jsearch",
            "signal_type": "demand",
            "observed_at": observed_at,
            "period": "2026-10",
            "scope": "country",
            "skill": "Python",
            "skill_id": "python",
            "value": 3,
            "unit": "job_postings",
            "data_origin": "real",
            "history_type": "platform_collected",
        },
        "adoption-observation": {
            "observation_id": "adoption-observation",
            "source": "jsearch",
            "signal_type": "adoption",
            "observed_at": observed_at,
            "period": "2026-10",
            "scope": "country",
            "skill": "Python",
            "skill_id": "python",
            "value": 5,
            "unit": "job_postings",
            "data_origin": "real",
            "history_type": "platform_collected",
        },
    }
    calculation_records = FakeCollection()
    client = FakeFirestoreClient({
        "skill_market_signals": FakeCollection(observations),
        "calculation_records": calculation_records,
    })

    evidence = get_skill_evidence("Python", client=client)

    assert evidence is not None
    assert len(evidence.items) == 2
    assert calculation_records.stream_calls == 1


# 10 & 11. Source and Signal Separation
def test_evidence_maintains_strict_source_and_signal_separation():
    collections = {
        "skill_market_signals": FakeCollection({
            "jsearch-obs": {
                "observation_id": "jsearch-obs",
                "source": "jsearch",
                "signal_type": "demand",
                "observed_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
                "period": "2026-10",
                "scope": "country",
                "skill": "Python",
                "value": 1.0,
                "data_origin": "real",
                "history_type": "platform_collected",
            },
            "github-obs": {
                "observation_id": "github-obs",
                "source": "github",
                "signal_type": "adoption",
                "observed_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
                "period": "2026-10",
                "scope": "global",
                "skill": "Python",
                "value": 900000.0,
                "data_origin": "real",
                "history_type": "snapshot",
            },
        }),
    }
    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("Python", client=fake_client)

    assert evidence is not None
    assert len(evidence.items) == 2
    sources = {item.source for item in evidence.items}
    assert sources == {"jsearch", "github"}
    signals = {item.signal_type for item in evidence.items}
    assert signals == {"demand", "adoption"}


# 12. Missing evidence handling (known skill in registry, 0 observations)
def test_known_skill_with_no_observations_returns_empty_evidence():
    collections = {"skill_market_signals": FakeCollection()}
    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("Django", client=fake_client)

    assert evidence is not None
    assert evidence.canonical_name == "Django"
    assert evidence.evidence_count == 0
    assert evidence.items == []
    assert evidence.data_state == "insufficient_data"


# 13. Missing skill handling (completely unknown skill)
def test_completely_unknown_skill_returns_none():
    collections = {"skill_market_signals": FakeCollection()}
    fake_client = FakeFirestoreClient(collections)
    evidence = get_skill_evidence("completely_fictional_skill_xyz", client=fake_client)
    assert evidence is None


# 20. Read-only / idempotent behavior
def test_read_only_and_idempotent_behavior():
    collections = {
        "skill_market_signals": FakeCollection({
            "obs-1": {
                "observation_id": "obs-1",
                "source": "adzuna",
                "signal_type": "demand",
                "observed_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
                "period": "2026-10",
                "scope": "country",
                "skill": "C#",
                "value": 1.0,
            }
        })
    }
    fake_client = FakeFirestoreClient(collections)
    ev1 = get_skill_evidence("C#", client=fake_client)
    ev2 = get_skill_evidence("C#", client=fake_client)
    assert ev1 == ev2
    # Ensure no documents were written or modified
    assert len(collections["skill_market_signals"]._items) == 1

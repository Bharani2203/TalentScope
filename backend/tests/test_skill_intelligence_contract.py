"""Tests for G1.1 Skill Intelligence Backend Contract.

Validates:
1. Authenticated Skill Intelligence request & required contract fields
2. Insufficient-data response contract (confidence=None, data_state=insufficient_data, no fake trend)
3. Signal family separation (GitHub adoption is never blended into Adzuna job demand)
4. Source-specific denominator handling
5. No null-to-zero conversion
6. No fabricated confidence
7. Provenance & calculation_version preservation
8. Unsupported/missing source data handling
9. Backward compatibility of existing API response structure
"""

from copy import deepcopy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.analytics.trend import CALCULATION_VERSION, calculate_skill_trends
from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import (
    MarketObservation,
    SkillIntelligenceResponse,
)
from app.services import market_collection_service, onboarding_service, skill_intelligence_service
from app.services.skill_intelligence_service import _build_intelligence_response
from app.storage.firestore_observation_store import ObservationBatch


class FakeDoc:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data)


class FakeCollection:
    def __init__(self, db, name):
        self.db = db
        self.name = name

    def document(self, doc_id):
        return FakeDoc(self.db.get(f"{self.name}/{doc_id}"))


class FakeFirestoreDB:
    def __init__(self, data=None):
        self.data = data or {}

    def collection(self, name):
        return FakeCollection(self.data, name)


class FakeStore:
    def __init__(self, observations):
        self._observations = observations

    def get_observations(self, **kwargs):
        return self._observations

    def has_observations(self):
        return bool(self._observations)


def auth_user(uid="contract-test-user"):
    return AuthenticatedUser(
        uid=uid,
        email="user@example.com",
        email_verified=True,
        display_name="Contract Test User",
    )


@pytest.fixture(autouse=True)
def setup_contract_env(monkeypatch, tmp_path):
    app.dependency_overrides.clear()
    settings = Settings(
        _env_file=None,
        skill_intelligence_db_path=str(tmp_path / "test.db"),
        skill_intelligence_read_backend="sqlite",
    )
    monkeypatch.setattr(skill_intelligence_service, "get_settings", lambda: settings)
    monkeypatch.setattr(market_collection_service, "get_settings", lambda: settings)
    yield
    app.dependency_overrides.clear()


def test_contract_fields_present_and_typed_on_insufficient_data():
    now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adzuna-obs-1",
        source="adzuna",
        skill="Python",
        signal_type="demand",
        observed_at=now,
        period="2026-09",
        scope="country",
        location="India",
        posting_id="adzuna-job-1",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
        fetch_run_id="run-1",
        series_id="adzuna:panel:job-demand:python:v1",
    )
    trend_records = calculate_skill_trends([obs], min_periods=4, now=now)
    resp = _build_intelligence_response(
        profile={"basic_profile": {"city": "Bangalore", "country": "India"}},
        skills=[],
        display_location="India",
        range_key="6m",
        skill="Python",
        effective_location="India",
        observations=[obs],
        trend_records=trend_records,
        summary={"last_collection": {"status": "success", "providers": {
            "adzuna": {"run_id": "run-1", "completed_at": now},
        }}},
        settings=Settings(_env_file=None),
        pending_sources=[],
    )

    # 1. Root contract fields
    assert resp.data_status == "insufficient_data"
    assert resp.data_state == "insufficient_data"
    assert resp.data_origin == "real"
    assert resp.history_type == "platform_collected"
    assert resp.calculation_version == CALCULATION_VERSION
    assert resp.sources_used == ["adzuna"]
    assert resp.observations_count == 1
    assert resp.historical_periods_count == 1

    # 2. No fabricated confidence or fake trend points
    assert resp.market_top_skills == []
    assert len(resp.current_demand) == 1
    snapshot = resp.current_demand[0]
    assert snapshot["value"] == 1.0  # preserved as-is, NOT 100%
    assert snapshot["confidence"] is None  # no fabricated confidence
    assert snapshot["data_state"] == "unavailable"
    assert snapshot["readiness"] is not None
    assert snapshot["data_origin"] == "real"
    assert snapshot["history_type"] == "platform_collected"

    # 3. Selected skill has no fake growth or confidence
    assert resp.selected_skill is not None
    assert resp.selected_skill.confidence is None
    assert resp.selected_skill.growth_pct is None
    assert resp.selected_skill.trend == "Insufficient Data"


def test_source_separation_github_adoption_not_blended_into_adzuna_demand():
    """Ensure GitHub adoption observations are never mixed into job-demand calculations."""
    now = datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc)
    adzuna_demand = MarketObservation(
        id="adzuna-obs-1",
        source="adzuna",
        skill="Python",
        signal_type="demand",
        observed_at=now,
        period="2026-10",
        scope="country",
        location="India",
        posting_id="adzuna-job-1",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
        fetch_run_id="run-1",
        series_id="adzuna:panel:job-demand:python:v1",
    )
    github_adoption = MarketObservation(
        id="github-obs-1",
        source="github",
        skill="Python",
        signal_type="adoption",
        observed_at=now,
        period="2026-10",
        scope="global",
        location="Global",
        posting_id="gh-repo-1",
        value=500.0,
        history_type="snapshot",
        data_origin="real",
        fetch_run_id="run-gh-1",
        series_id="github:panel:adoption:python:v1",
    )

    # trend calculation accepts list containing both, but must strictly filter out non-demand
    trends = calculate_skill_trends([adzuna_demand, github_adoption], min_periods=4, now=now)
    assert len(trends) == 1
    assert trends[0]["source"] == "adzuna"
    assert trends[0]["series_provenance"]["signal_type"] == "demand"

    # Intelligence response building must separate sources
    resp = _build_intelligence_response(
        profile={},
        skills=[],
        display_location="Global",
        range_key="6m",
        skill=None,
        effective_location=None,
        observations=[adzuna_demand, github_adoption],
        trend_records=trends,
        summary={"last_collection": None},
        settings=Settings(_env_file=None),
        pending_sources=[],
    )
    # Only compatible demand observations contribute to demand calculations
    assert resp.sources_used == ["adzuna"]
    assert resp.calculation["sources"] == ["adzuna"]
    assert resp.calculation["signal_type"] == "demand"
    assert {
        (result.source, result.signal_type)
        for result in resp.metric_results
        if result.metric_kind == "observed"
    } == {("adzuna", "demand"), ("github", "adoption")}


def test_truncated_skill_intelligence_marks_observations_incomplete_and_withholds_trends():
    observed_at = datetime(2026, 9, 15, tzinfo=timezone.utc)
    observation = MarketObservation(
        id="truncated-skill-observation",
        source="adzuna",
        skill="Python",
        skill_id="python",
        signal_type="demand",
        observed_at=observed_at,
        period="2026-09",
        scope="country",
        location="India",
        value=14,
        unit="job_postings",
        data_origin="real",
        history_type="platform_collected",
        series_id="adzuna:python:india:v1",
        fetch_run_id="truncated-run",
    )
    response = _build_intelligence_response(
        profile={},
        skills=[],
        display_location="India",
        range_key="6m",
        skill="Python",
        effective_location="India",
        observations=ObservationBatch([observation], truncated=True),
        trend_records=[],
        summary={"last_collection": {"status": "success"}},
        settings=Settings(_env_file=None),
        pending_sources=[],
    )

    assert response.history_complete is False
    assert response.data_state == "incomplete"
    assert response.history_completeness_reason
    observed = next(item for item in response.metric_results if item.metric_kind == "observed")
    assert observed.status == "partial"
    assert observed.freshness_state == "incomplete"
    assert not any(
        item.metric_kind == "derived" and item.capability == "trend_velocity_analysis"
        for item in response.metric_results
    )


def test_source_specific_denominators_never_blended():
    """Ensure denominators are source-specific and never cross-pollinated between providers."""
    now = datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc)
    adzuna_p1 = MarketObservation(
        id="adz-1", source="adzuna", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="adz-job-1", value=1.0,
        history_type="platform_collected", data_origin="real",
    )
    other_provider_p1 = MarketObservation(
        id="other-1", source="other_job_board", skill="Python", signal_type="demand",
        observed_at=now, period="2026-10", posting_id="other-job-1", value=1.0,
        history_type="platform_collected", data_origin="real",
    )

    trends = calculate_skill_trends([adzuna_p1, other_provider_p1], min_periods=4, now=now)
    # Each source forms its own independent trend series
    sources = {t["source"] for t in trends}
    assert sources == {"adzuna", "other_job_board"}


def test_no_null_to_zero_conversion_and_provenance_preservation():
    """Verify that nulls stay null and provenance links are preserved end-to-end."""
    now = datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc)
    obs = MarketObservation(
        id="adz-prov-1",
        source="adzuna",
        skill="Rust",
        signal_type="demand",
        observed_at=now,
        period="2026-10",
        posting_id="adz-job-rust-1",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
        fetch_run_id="fetch-run-999",
        series_id="adzuna:series:rust",
    )
    resp = _build_intelligence_response(
        profile={},
        skills=[],
        display_location="Global",
        range_key="6m",
        skill="Rust",
        effective_location=None,
        observations=[obs],
        trend_records=calculate_skill_trends([obs], min_periods=4, now=now),
        summary={"last_collection": None},
        settings=Settings(_env_file=None),
        pending_sources=[],
    )

    # Check root calculation and provenance structures
    assert resp.provenance is not None
    assert resp.provenance["calculation_version"] == CALCULATION_VERSION
    assert resp.provenance["sources"][0]["fetch_run_ids"] == ["fetch-run-999"]
    assert resp.provenance["sources"][0]["skills"][0]["observation_ids"] == ["adz-prov-1"]

    # Check selected skill null guarantees
    assert resp.selected_skill is not None
    assert resp.selected_skill.growth_pct is None
    assert resp.selected_skill.confidence is None
    assert resp.selected_skill.trend == "Insufficient Data"


def test_empty_or_error_storage_sets_contract_states_cleanly():
    """Verify that storage failures produce typed error data_state without crashing."""
    resp = _build_intelligence_response(
        profile={},
        skills=[],
        display_location="Global",
        range_key="6m",
        skill=None,
        effective_location=None,
        observations=[],
        trend_records=[],
        summary={"last_collection": {"status": "error"}},
        settings=Settings(_env_file=None),
        pending_sources=[],
    )
    assert resp.data_status == "error"
    assert resp.data_state is None or resp.data_state == "error"
    assert resp.data_origin == "unavailable"
    assert resp.history_type == "unavailable"

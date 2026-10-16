import asyncio
from datetime import datetime, timezone

import pytest
import httpx
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.skill_intelligence import MarketObservation
from app.services.external_apis.stack_exchange_service import (
    QuestionsPage,
    StackExchangeError,
    StackExchangeService,
)
from app.services.historical_backfill_service import backfill
from app.services import skill_intelligence_service
from app.services.market_data.stack_exchange_historical_provider import (
    HistoricalSeriesResult,
    StackExchangeHistoricalProvider,
    _month_bounds,
)
from app.analytics.trend import calculate_skill_trends
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.firestore_observation_store import FirestoreObservationStore


class Snapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return self.value


class Document:
    def __init__(self, collection, key):
        self.collection, self.key = collection, key

    def get(self):
        return Snapshot(self.collection.records.get(self.key))

    def create(self, value):
        if self.key in self.collection.records:
            raise ValueError("already exists")
        self.collection.records[self.key] = dict(value)

    def update(self, value):
        self.collection.records[self.key].update(value)


class Collection:
    def __init__(self):
        self.records = {}

    def document(self, key):
        return Document(self, key)

    def stream(self):
        return [Snapshot(value) for value in self.records.values()]


class Batch:
    def __init__(self):
        self.ops = []

    def set(self, ref, value):
        self.ops.append((ref, value))

    def commit(self):
        for ref, value in self.ops:
            ref.collection.records[ref.key] = dict(value)


class Database:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())

    def batch(self):
        return Batch()


def _question(tag: str, question_id: int, created: int):
    return {"question_id": question_id, "creation_date": created, "tags": [tag]}


class FakeStackExchangeService:
    endpoint = "https://api.stackexchange.com/2.3/questions"
    page_size = 100
    anonymous_page_limit = 25

    def __init__(self, *, fail_month: str | None = None):
        self.fail_month = fail_month
        self.calls = []

    async def questions_page(self, *, tag, fromdate, todate, page, raw_response_callback=None):
        dt = datetime.fromtimestamp(fromdate, timezone.utc)
        period = dt.strftime("%Y-%m")
        self.calls.append((tag, period, page))
        if period == self.fail_month:
            raise StackExchangeError("safe failure", category="network")
        # One actual dated record in August and source-reported empty September.
        if period == "2026-08" and page == 1:
            payload = {"items": [_question(tag, 987, fromdate)], "has_more": False, "quota_remaining": 299}
            if raw_response_callback:
                raw_response_callback(payload, "application/json")
            return QuestionsPage(payload["items"], False, 299, None)
        payload = {"items": [], "has_more": False, "quota_remaining": 299}
        if raw_response_callback:
            raw_response_callback(payload, "application/json")
        return QuestionsPage([], False, 299, None)


def test_stackexchange_normalization_preserves_historical_provenance_and_period():
    result = asyncio.run(StackExchangeHistoricalProvider(FakeStackExchangeService()).backfill_series(
        skill="Python", start_period="2026-08", end_period="2026-09",
    ))[0]

    assert result.skill_id == "python"
    assert result.series_id == "stackexchange:stackoverflow:question-tag:python:v1"
    assert result.query_id == "stackexchange:stackoverflow:tag:python:v1"
    assert [item.period for item in result.observations] == ["2026-08", "2026-09"]
    assert [item.value for item in result.observations] == [1.0, 0.0]
    assert all(item.signal_type == "interest" for item in result.observations)
    assert all(item.history_type == "backfill" for item in result.observations)
    assert all(item.data_origin == "real" for item in result.observations)
    assert all(item.denominator is None and item.confidence is None for item in result.observations)
    assert all(item.observation_count in {0, 1} for item in result.observations)
    assert all(item.metadata["site"] == "stackoverflow" for item in result.observations)
    assert all(item.panel_version and item.extractor_version and item.annotations for item in result.observations)
    assert result.observations[0].metadata["source_created_at_min"] == _month_bounds("2026-08")[0]


def test_backfill_dry_run_writes_fetch_run_but_no_observations():
    db = Database()
    outcome = backfill(
        source="stackexchange", skills=["Python"], start_period="2026-08", end_period="2026-09",
        dry_run=True,
        provider=StackExchangeHistoricalProvider(FakeStackExchangeService()),
        fetch_run_store=FirestoreFetchRunStore(db),
        observation_store=FirestoreObservationStore(db),
    )

    assert outcome["status"] == "success"
    assert len(db.collection("fetch_runs").records) == 1
    run = next(iter(db.collection("fetch_runs").records.values()))
    assert run["dry_run"] is True and run["status"] == "success"
    assert run["records_fetched"] == run["records_normalized"] == 1
    assert run["coverage_status"] == "complete"
    assert run["periods_found"] == ["2026-08", "2026-09"]
    assert db.collection("skill_market_signals").records == {}


def test_new_backfill_observations_keep_their_actual_fetch_run_id():
    db = Database()

    class Archive:
        def archive(self, *, provider, fetch_run_id, collected_at, payload, content_type, response_index):
            return {
                "provider": provider,
                "fetch_run_id": fetch_run_id,
                "archive_reference": f"raw_response_archives/{provider}__{fetch_run_id}__{response_index:06d}",
                "content_type": content_type,
            }

    outcome = backfill(
        source="stackexchange", skills=["Python"], start_period="2026-08", end_period="2026-09",
        dry_run=False,
        provider=StackExchangeHistoricalProvider(FakeStackExchangeService()),
        fetch_run_store=FirestoreFetchRunStore(db),
        observation_store=FirestoreObservationStore(db),
        raw_response_archive=Archive(),
    )

    run_id = outcome["series"][0]["run_id"]
    stored = list(db.collection("skill_market_signals").records.values())
    archive_metadata = db.collection("fetch_runs").records[run_id]["raw_response_archive"]
    assert stored
    assert all(row["fetch_run_id"] == run_id for row in stored)
    assert all(row["source"] == "stackexchange" for row in stored)
    assert all(row["history_type"] == "backfill" for row in stored)
    assert all(row["data_origin"] == "real" for row in stored)
    assert db.collection("fetch_runs").records[run_id]["source"] == "stackexchange"
    assert archive_metadata["fetch_run_id"] == run_id
    assert archive_metadata["response_count"] == 2
    assert archive_metadata["archive_reference"].startswith(f"raw_response_archives/stackexchange__{run_id}__")
    assert archive_metadata["archive_prefix"] == f"raw_response_archives/stackexchange__{run_id}__"


def test_backfill_repeat_is_idempotent_and_keeps_monthly_series_separate():
    db = Database()
    provider = StackExchangeHistoricalProvider(FakeStackExchangeService())

    class Archive:
        def archive(self, *, provider, fetch_run_id, collected_at, payload, content_type, response_index):
            return {
                "provider": provider,
                "fetch_run_id": fetch_run_id,
                "archive_reference": f"raw_response_archives/{provider}__{fetch_run_id}__{response_index:06d}",
                "content_type": content_type,
            }

    args = dict(
        source="stackexchange", skills=["Python"], start_period="2026-08", end_period="2026-09",
        dry_run=False, provider=provider,
        fetch_run_store=FirestoreFetchRunStore(db),
        observation_store=FirestoreObservationStore(db),
        raw_response_archive=Archive(),
    )
    first = backfill(**args)
    first_ids = set(db.collection("skill_market_signals").records)
    second = backfill(**args)

    assert first["series"][0]["observations_inserted"] == 2
    assert second["series"][0]["observations_inserted"] == 0
    assert len(first_ids) == 2
    assert set(db.collection("skill_market_signals").records) == first_ids
    documents = list(db.collection("skill_market_signals").records.values())
    first_run_id = first["series"][0]["run_id"]
    second_run_id = second["series"][0]["run_id"]
    assert first_run_id != second_run_id
    assert len(db.collection("fetch_runs").records) == 2
    assert all(item["fetch_run_id"] == first_run_id for item in documents)
    assert {item["period"] for item in documents} == {"2026-08", "2026-09"}
    assert all(item["source"] == "stackexchange" for item in documents)


def test_incomplete_period_is_a_gap_and_does_not_become_zero():
    provider = StackExchangeHistoricalProvider(FakeStackExchangeService(fail_month="2026-09"))
    result = asyncio.run(provider.backfill_series(
        skill="Python", start_period="2026-08", end_period="2026-09",
    ))[0]

    assert result.periods_found == ["2026-08"]
    assert result.coverage_gaps == ["2026-09"]
    assert [item.period for item in result.observations] == ["2026-08"]
    assert [item.value for item in result.observations] == [1.0]
    assert result.error_category == "network"


def test_source_tag_series_remain_independent_and_one_tag_failure_is_isolated():
    class OneTagFails(FakeStackExchangeService):
        async def questions_page(self, *, tag, fromdate, todate, page):
            if tag == "spring":
                raise StackExchangeError("safe failure", category="network")
            return QuestionsPage([_question(tag, 321, fromdate)], False, 299, None)

    results = asyncio.run(StackExchangeHistoricalProvider(OneTagFails()).backfill_series(
        skill="Spring", start_period="2026-08", end_period="2026-08",
    ))
    assert {item.tag for item in results} == {"spring", "spring-boot"}
    assert len({item.series_id for item in results}) == 2
    assert results[0].coverage_gaps == ["2026-08"]
    assert results[0].observations == []
    assert results[1].coverage_gaps == []
    assert len(results[1].observations) == 1

    db = Database()
    outcome = backfill(
        source="stackexchange", skills=["Spring"], start_period="2026-08", end_period="2026-08",
        dry_run=True, provider=StackExchangeHistoricalProvider(OneTagFails()),
        fetch_run_store=FirestoreFetchRunStore(db), observation_store=FirestoreObservationStore(db),
    )
    assert outcome["status"] == "partial"
    assert {item["status"] for item in outcome["series"]} == {"success", "failed"}
    run = next(iter(db.collection("fetch_runs").records.values()))
    assert run["status"] == "partial"
    assert run["coverage_status"] == "partial"


def test_interest_backfill_does_not_change_existing_demand_trend_calculation():
    historical = asyncio.run(StackExchangeHistoricalProvider(FakeStackExchangeService()).backfill_series(
        skill="Terraform", start_period="2026-08", end_period="2026-09",
    ))[0].observations
    demand = MarketObservation(
        source="jsearch", skill="Terraform", skill_id="terraform", signal_type="demand",
        history_type="platform_collected",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc), period="2026-10",
        scope="global", posting_id="demand-current", value=1.0, unit="job_postings",
        series_id="jsearch:test-query:job-demand:terraform:v1", query_id="jsearch:test-query",
        panel_version="job-demand-v1", data_origin="real",
    )

    with_interest = calculate_skill_trends([demand, *historical], now=datetime(2026, 10, 6, tzinfo=timezone.utc))
    demand_only = calculate_skill_trends([demand], now=datetime(2026, 10, 6, tzinfo=timezone.utc))
    assert with_interest == demand_only
    assert len(with_interest) == 1
    assert with_interest[0]["trend"] == "Insufficient Data"
    assert with_interest[0]["growth_pct"] is None
    assert with_interest[0]["confidence"] is None
    assert with_interest[0]["ranking_score"] is None


def test_authenticated_intelligence_api_keeps_contract_with_historical_interest(monkeypatch):
    historical = asyncio.run(StackExchangeHistoricalProvider(FakeStackExchangeService()).backfill_series(
        skill="Terraform", start_period="2026-06", end_period="2026-09",
    ))[0].observations
    demand = MarketObservation(
        source="jsearch", skill="Terraform", skill_id="terraform", signal_type="demand",
        history_type="platform_collected",
        observed_at=datetime.now(timezone.utc), period=datetime.now(timezone.utc).strftime("%Y-%m"),
        scope="global", posting_id="current-demand", value=1.0, unit="job_postings",
        series_id="jsearch:test-query:job-demand:terraform:v1", query_id="jsearch:test-query",
        panel_version="job-demand-v1", data_origin="real",
    )

    class ObservationReader:
        def get_observations(self, **kwargs):
            return [*historical, demand]

        def has_observations(self):
            return True

    class RunReader:
        def collection_summary(self):
            return {"last_collection": {"status": "success", "providers": {} }}

    monkeypatch.setattr(skill_intelligence_service, "FirestoreObservationStore", ObservationReader)
    monkeypatch.setattr(skill_intelligence_service, "FirestoreFetchRunStore", RunReader)
    monkeypatch.setattr(skill_intelligence_service, "get_settings", lambda: Settings(
        _env_file=None, skill_intelligence_read_backend="firestore",
    ))
    monkeypatch.setattr(skill_intelligence_service, "get_individual_profile", lambda _uid: type(
        "Profile", (), {"profile": {
            "basic_profile": {},
            "skills": {"selected_skills": ["Terraform"], "skill_levels": {}},
        }}
    )())
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="historical-test-user", email="test@example.com", email_verified=True,
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/skills/intelligence", params={"range": "6m", "skill": "Terraform"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["observations_count"] == 5
    assert body["historical_periods_count"] == 5
    # Historical Stack Exchange interest is not a demand source.
    assert body["sources_used"] == ["jsearch"]
    assert body["provenance"]["history_type"] == "platform_collected"
    assert body["calculation"]["observation_count"] == 1
    assert body["calculation"]["historical_periods_count"] == 1
    assert body["data_status"] == "insufficient_data"
    assert body["top_skills"] == []
    assert body["skill_trends"] == []
    assert body["personal_top_skills"] == []
    assert body["selected_skill"]["trend"] == "Insufficient Data"
    assert "market_top_skills" in body and "sources_pending" in body


def test_backfill_rejects_current_period_and_unknown_registry_skill():
    db = Database()
    common = dict(fetch_run_store=FirestoreFetchRunStore(db), observation_store=FirestoreObservationStore(db))
    current = datetime.now(timezone.utc).strftime("%Y-%m")
    with pytest.raises(ValueError, match="before the current UTC month"):
        backfill(source="stackexchange", skills=["Python"], start_period=current, end_period=current, **common)
    with pytest.raises(ValueError, match="not in the canonical registry"):
        backfill(
            source="stackexchange", skills=["unknown"], start_period="2026-08", end_period="2026-08",
            provider=StackExchangeHistoricalProvider(FakeStackExchangeService()), **common,
        )


def test_page_cap_triggers_date_subdivision_without_losing_or_double_counting():
    class CappedService(FakeStackExchangeService):
        anonymous_page_limit = 1

        async def questions_page(self, *, tag, fromdate, todate, page):
            if fromdate < todate:
                return QuestionsPage([_question(tag, 42, fromdate)], True, 299, None)
            return QuestionsPage([_question(tag, fromdate, fromdate)], False, 299, None)

    provider = StackExchangeHistoricalProvider(CappedService())
    start, end = 100, 101
    result = asyncio.run(provider._fetch_complete_interval(
        tag="python", start_epoch=start, end_epoch=end,
        result=HistoricalSeriesResult("python", "Python", "python", "q", "s"),
    ))
    assert len(result) == 2


def test_application_error_response_does_not_expose_payload_or_secret():
    secret_marker = "sensitive-marker-do-not-log"

    async def handler(request):
        return httpx.Response(
            200,
            json={"error_id": 502, "error_name": "throttled", "error_message": secret_marker, "backoff": 2},
        )

    service = StackExchangeService(transport=httpx.MockTransport(handler), max_retries=0)
    with pytest.raises(StackExchangeError) as caught:
        asyncio.run(service.questions_page(tag="python", fromdate=1, todate=2, page=1))
    assert caught.value.category == "rate_limit"
    assert secret_marker not in str(caught.value)


def test_stackexchange_page_exposes_raw_response_to_archive_callback_before_normalization():
    payload = {
        "items": [{"question_id": 42, "creation_date": 10, "tags": ["python"], "owner": {"user_id": 7}}],
        "has_more": False,
        "quota_remaining": 299,
        "quota_max": 300,
    }
    captured = []
    service = StackExchangeService(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
        max_retries=0,
    )

    page = asyncio.run(service.questions_page(
        tag="python", fromdate=1, todate=2, page=1,
        raw_response_callback=lambda body, content_type: captured.append((body, content_type)),
    ))

    assert page.items == payload["items"]
    assert captured == [(payload, "application/json")]

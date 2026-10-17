from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.dependencies import get_current_user
from app.api import dependencies
from app.api.routes import core_intelligence
from app.core.config import get_settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.core_intelligence import CoreIntelligenceRequest
from app.models.entity_registry import EntityResolutionRequest
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    EvidenceItem,
    SelectedEntityResolution,
    StructuredFact,
)
from app.models.skill_intelligence import MarketObservation
from app.services import execution_orchestrator_service as orchestrator_module
from app.services import intelligence_catalog_service
from app.services.intelligence_contract_service import (
    fact_metric_results,
    observed_metric_results,
    trend_metric_results,
)
from app.analytics import shared_intelligence as shared_intelligence_module
from app.services.core_intelligence_service import CoreIntelligenceService, _range_cutoff
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.llm_explanation_service import LLMExplanationService
from app.services import job_storage_service
from app.storage.firestore_read_guard import read_guard
from app.storage.firestore_observation_store import ObservationBatch


class EmptyObservationStore:
    def get_observations_by_skill(self, *, skill, location, cutoff):
        return []


def test_answer_request_normalizes_domain_and_committed_role_filter():
    request = CoreIntelligenceAnswerRequest(
        message="Show relevant roles",
        filters={"domain": "roles", "selected_role": "Data Engineer"},
        time_range="12m",
    )

    assert request.domain == "job"
    assert request.time_range == "1y"
    assert request.selected_roles == ["Data Engineer"]
    assert request.target_role == "Data Engineer"

    committed = CoreIntelligenceAnswerRequest(
        message="Find Data Engineer roles",
        domain="job",
        filters={"domain": "job", "time_range": "12m", "location": "India", "country": "IN"},
    )
    assert committed.time_range == "1y"
    assert committed.location == "India"
    assert committed.filters["country"] == "in"

    with pytest.raises(ValidationError):
        CoreIntelligenceAnswerRequest(message="Search jobs", filters={"country": "India"})
    with pytest.raises(ValidationError):
        CoreIntelligenceAnswerRequest(
            message="Search jobs",
            time_range="3m",
            filters={"time_range": "6m"},
        )
    with pytest.raises(ValidationError):
        CoreIntelligenceAnswerRequest(
            message="Search jobs",
            time_range="30d",
            filters={"time_range": "1y"},
        )

    with pytest.raises(ValidationError):
        CoreIntelligenceAnswerRequest(
            message="Show relevant roles",
            domain="skill",
            filters={"domain": "job"},
        )
    with pytest.raises(ValidationError):
        CoreIntelligenceAnswerRequest(
            message="Analyze these",
            selected_skills=[f"skill-{index}" for index in range(21)],
        )


def test_entity_registry_resolves_canonical_skill_ids():
    resolved = EntityRegistryService().resolve(
        EntityResolutionRequest(name="tech:python", entity_type="technology")
    )

    assert resolved.status == "resolved"
    assert resolved.entity is not None
    assert resolved.entity.entity_id == "tech:python"
    assert resolved.entity.canonical_name == "Python"

    ambiguous = EntityRegistryService().resolve(EntityResolutionRequest(name="go"))
    assert ambiguous.status == "ambiguous"
    assert EntityRegistryService().resolve(
        EntityResolutionRequest(name="tech:go", entity_type="technology")
    ).entity.entity_id == "tech:go"
    assert EntityRegistryService().resolve(
        EntityResolutionRequest(name="go", entity_type="technology")
    ).entity.entity_id == "tech:go"


def test_llm_grounding_rejects_unsupported_numbers_and_opposite_direction():
    fact = StructuredFact(
        fact_type="trend_analysis",
        entity_name="Python",
        metric_name="trend_direction",
        metric_value="Rising",
        unit="unique developers per quarter",
        period="2026-Q1",
        source="github_innovation_graph",
        details={"trend_slope": 12.5},
    )

    assert LLMExplanationService.validate_generated_claims(
        "The verified result is 12.5 unique developers per quarter in 2026-Q1 from github_innovation_graph.",
        [fact],
    )
    assert not LLMExplanationService.validate_generated_claims(
        "The verified result is 77% in 2026-Q1.",
        [fact],
    )
    assert not LLMExplanationService.validate_generated_claims(
        "The overall trend is declining.",
        [fact],
    )
    assert not LLMExplanationService.validate_generated_claims(
        "The overall trend is falling.",
        [fact],
    )
    assert not LLMExplanationService.validate_generated_claims(
        "The verified result is 12.5 unique developers per quarter in 2026-Q1.",
        [fact],
    )


def test_llm_cache_is_scoped_to_user_and_cited_evidence():
    service = LLMExplanationService(api_key="not-used")
    fact = StructuredFact(
        fact_type="trend_analysis",
        entity_name="Python",
        metric_name="trend_direction",
        metric_value="Rising",
        source="github_innovation_graph",
    )
    evidence = EvidenceItem(
        evidence_id="ev-python-q1",
        source="github_innovation_graph",
        signal_type="developer_activity",
        period="2026-Q1",
        description="Observed series.",
    )

    first = service._get_cache_key("Analyze Python", "analyze_trend", [fact], [evidence], user_id="user-a")
    other_user = service._get_cache_key("Analyze Python", "analyze_trend", [fact], [evidence], user_id="user-b")
    other_evidence = service._get_cache_key(
        "Analyze Python",
        "analyze_trend",
        [fact],
        [evidence.model_copy(update={"evidence_id": "ev-python-q2", "period": "2026-Q2"})],
        user_id="user-a",
    )
    assert first != other_user
    assert first != other_evidence


def test_llm_prompt_uses_system_instruction_and_falls_back_on_invalid_output(monkeypatch):
    service = LLMExplanationService(api_key="test-key")
    monkeypatch.setattr(service, "is_available", lambda: True)
    monkeypatch.setattr(service, "reserve_durable_budget", lambda *_args: True)
    monkeypatch.setattr(service, "_MAX_INPUT_CHARS", 2000)
    fact = StructuredFact(
        fact_type="trend_analysis",
        entity_name="Python",
        metric_name="trend_direction",
        metric_value="Rising",
        unit="unique developers per quarter",
        period="2026-Q1",
        source="github_innovation_graph",
    )
    request_body = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Unsupported value 77%."}]}}]}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, _url, *, json, headers):
            request_body.update(json)
            assert headers["x-goog-api-key"] == "test-key"
            return FakeResponse()

    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", FakeClient)
    result = service.generate_grounded_explanation(
        user_message="Analyze Python",
        intent="analyze_trend",
        facts=[fact] * 15,
        evidence=[],
        user_id="test-user",
    )

    assert result is None
    assert "systemInstruction" in request_body
    assert "STRICT RULES" in request_body["systemInstruction"]["parts"][0]["text"]
    assert "STRICT RULES" not in request_body["contents"][0]["parts"][0]["text"]
    assert len(request_body["contents"][0]["parts"][0]["text"]) <= service._MAX_INPUT_CHARS


class FakeJobSnapshot:
    def __init__(self, document_id, record):
        self.id = document_id
        self._record = record

    def to_dict(self):
        return dict(self._record)


class FakeJobQuery:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.filters = []
        self.ordering = None
        self.limit_value = None

    def where(self, *, filter):
        self.filters.append(filter)
        return self

    def order_by(self, field, *, direction):
        self.ordering = (field, direction)
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def stream(self):
        assert self.limit_value is not None
        return iter(self.snapshots[:self.limit_value])


def test_stored_job_search_uses_country_filter_and_bounded_recent_query(monkeypatch):
    fetched_at = datetime(2026, 10, 12, tzinfo=timezone.utc)
    query = FakeJobQuery([
        FakeJobSnapshot("jsearch:python-1", {
            "source_job_id": "python-1",
            "job_id": "python-1",
            "source": "jsearch",
            "title": "Data Engineer",
            "company_name": "Example",
            "country_code": "in",
            "fetched_at": fetched_at,
            "source_url": "https://jobs.example/1",
        }),
        FakeJobSnapshot("jsearch:other", {
            "source_job_id": "other",
            "job_id": "other",
            "source": "jsearch",
            "title": "Designer",
            "company_name": "Other",
            "country_code": "in",
            "fetched_at": fetched_at,
        }),
    ])

    class FakeCollection:
        def __init__(self):
            self.query = query

        def where(self, *, filter):
            return self.query.where(filter=filter)

    class FakeFirestore:
        def collection(self, name):
            assert name == "jobs"
            return FakeCollection()

    read_guard.reset_metrics()
    monkeypatch.setattr(job_storage_service, "get_firestore_client", FakeFirestore)
    jobs = job_storage_service.search_stored_jsearch_jobs(
        query="Data Engineer",
        country="in",
        limit=100,
    )

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    assert query.ordering == ("fetched_at", "DESCENDING")
    assert query.limit_value == 500
    assert len(query.filters) == 1
    assert read_guard.get_metrics()["reads_by_collection"]["jobs"] == 2


def test_job_analysis_preserves_only_stored_summary_skills_and_links(tmp_path):
    service = ExecutionOrchestratorService(
        db_path=tmp_path / "skill-reference.sqlite",
        observation_store=EmptyObservationStore(),
    )
    observation = MarketObservation(
        id="job-observation-1",
        source="jsearch",
        signal_type="demand",
        observed_at=datetime(2026, 10, 12, tzinfo=timezone.utc),
        period="2026-10",
        location="Bengaluru, India",
        skill="Data Engineer",
        value=1,
        posting_id="provider-job-1",
        metadata={
            "job_title": "Data Engineer",
            "company": "Example Employer",
            "description": "Build data pipelines.",
            "skills_raw": ["Python", "SQL"],
            "apply_link": "https://jobs.example/apply",
        },
        data_origin="real",
    )
    request = CoreIntelligenceAnswerRequest(
        message="Find Data Engineer jobs",
        domain="job",
        selected_roles=["Data Engineer"],
        target_role="Data Engineer",
        observations=[observation],
    )
    plan = SimpleNamespace(context_summary={"primary_entity": "Data Engineer"})

    facts, evidence, _ = service._handle_job_posting_search(request, plan)

    posting = facts[0].details["postings"][0]
    assert posting["summary"] == "Build data pipelines."
    assert posting["required_skills"] == ["Python", "SQL"]
    assert posting["source_url"] == "https://jobs.example/apply"
    assert evidence[0].unit == "posting"
    assert evidence[0].provenance_id == "provider-job-1"


def test_shared_answer_route_requires_auth_and_preserves_canonical_contract(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides.clear()
    captured = {}
    response = CoreIntelligenceAnswerResponse(
        request_id="answer-test",
        user_message="Analyze Python",
        portal_type="individual",
        domain="skill",
        intent="analyze_trend",
        plan_status="ready_to_execute",
        execution_status="completed",
        status="ready",
        answer="Grounded analysis.",
        selected_entities=[
            SelectedEntityResolution(
                entity_id="tech:python",
                entity_type="technology",
                canonical_name="Python",
                resolution_status="resolved",
            )
        ],
        applied_filters={"domain": "skill", "time_range": "1y"},
        facts=[],
        evidence=[],
    )

    class FakeOrchestrator:
        def answer(self, request, *, authenticated_user):
            captured["request"] = request
            captured["user"] = authenticated_user
            return response

    try:
        unauthenticated = client.post(
            f"{get_settings().api_v1_prefix}/intelligence/answer",
            json={"message": "Analyze Python", "domain": "skill"},
        )
        assert unauthenticated.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="phase7-user")
        monkeypatch.setattr(core_intelligence, "ExecutionOrchestratorService", FakeOrchestrator)
        authenticated = client.post(
            f"{get_settings().api_v1_prefix}/intelligence/answer",
            json={
                "message": "Analyze Python",
                "domain": "skill",
                "filters": {"domain": "skill", "time_range": "12m"},
            },
        )

        assert authenticated.status_code == 200
        payload = authenticated.json()
        assert captured["user"].uid == "phase7-user"
        assert captured["request"].time_range == "1y"
        assert payload["domain"] == "skill"
        assert payload["selected_entities"][0]["entity_id"] == "tech:python"
        assert payload["applied_filters"]["time_range"] == "1y"
        assert payload["answer"] == "Grounded analysis."
    finally:
        app.dependency_overrides.clear()


def test_shared_answer_uses_local_quarterly_series_without_monthly_conversion(
    tmp_path, monkeypatch
):
    service = ExecutionOrchestratorService(
        db_path=tmp_path / "skill-reference.sqlite",
        observation_store=EmptyObservationStore(),
    )
    resolved = service.entity_service.resolve(
        EntityResolutionRequest(name="Python", entity_type="technology")
    )
    assert resolved.entity is not None

    service.reference_store.get_github_adoption_series = lambda **kwargs: []
    monkeypatch.setattr(
        intelligence_catalog_service,
        "get_local_github_skill_series",
        lambda skill_id: [{
            "metric": "language_pushers",
            "label": "Python",
            "unit": "unique developers per quarter",
            "location": "India",
            "latest": {"period": "2026-Q1", "value": 145},
            "latest_trend_period": "2026-Q1",
            "period_over_period_change": 12,
            "velocity_per_quarter": 8.5,
            "trend_direction": "Rising",
            "trend_ready": True,
            "trend_slope": 8.5,
            "trend_calculation": "trend-velocity-theil-sen-v1",
            "trend_periods_used": ["2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"],
            "stale": False,
        }],
    )
    plan = SimpleNamespace(
        entities=[SimpleNamespace(canonical_entity=resolved.entity)],
        context_summary={"primary_entity": "Python"},
    )
    request = CoreIntelligenceAnswerRequest(message="Analyze Python trend", domain="skill")

    facts, evidence, _ = service._handle_skill_technology_reference(request, plan)
    trend = next(fact for fact in facts if fact.fact_type == "trend_analysis")
    answer = service._synthesize_answer("analyze_trend", facts, evidence, [], request, plan)

    assert trend.source == "github_innovation_graph"
    assert trend.metric_value == "Rising"
    assert trend.unit == "unique developers per quarter"
    assert trend.details["period_grain"] == "quarter"
    assert trend.details["latest_period_change"] == 12
    assert trend.period == "2025-Q2_to_2026-Q1"
    assert "quarter periods" in answer
    assert "monthly periods" not in answer
    assert "Latest comparable-period change is **12**" in answer


def test_market_snapshot_returns_structured_insufficient_evidence(tmp_path):
    service = ExecutionOrchestratorService(
        db_path=tmp_path / "skill-reference.sqlite",
        observation_store=EmptyObservationStore(),
    )
    request = CoreIntelligenceAnswerRequest(message="Market for Python", domain="market")
    plan = SimpleNamespace(context_summary={"primary_entity": "Python"})

    facts, evidence, _ = service._handle_market_snapshot(request, plan)

    readiness = next(fact for fact in facts if fact.fact_type == "analysis_readiness")
    assert readiness.metric_value == "insufficient_data"
    assert readiness.details["reference_data_is_not_market_evidence"] is True
    assert readiness.period is None
    assert evidence[0].quality == "unavailable"


def test_core_market_aggregation_is_reused_and_custom_history_is_bounded(monkeypatch):
    now = datetime.now(timezone.utc)
    observations = []
    for index, value in enumerate((10, 14, 18, 22), start=4):
        month_index = now.year * 12 + now.month - index
        year, month_zero = divmod(month_index, 12)
        observed_at = datetime(year, month_zero + 1, 15, tzinfo=timezone.utc)
        period = observed_at.strftime("%Y-%m")
        observations.append(MarketObservation(
            id=f"core-obs-{observed_at:%Y-%m}",
            source="jsearch",
            signal_type="demand",
            observed_at=observed_at,
            period=period,
            location="India",
            scope="country",
            skill="Python",
            skill_id="python",
            value=value,
            unit="job_postings",
            source_url=f"https://source.example/{period}",
            data_origin="real",
            history_type="platform_collected",
            series_id="jsearch:python:india:v1",
            denominator=200,
            denominator_unit="all_job_postings",
            query_id="software",
            fetch_run_id=f"run-{period}",
        ))

    class ObservationStore:
        def get_observations_by_skills(self, _skills, **_kwargs):
            return observations

    calls = 0
    trend_calls = 0
    original_aggregate = shared_intelligence_module.aggregate_market_signals
    original_trend = shared_intelligence_module.calculate_trend_and_velocity

    def count_aggregate(observations):
        nonlocal calls
        calls += 1
        return original_aggregate(observations)

    def count_trend(*args, **kwargs):
        nonlocal trend_calls
        trend_calls += 1
        return original_trend(*args, **kwargs)

    monkeypatch.setattr(shared_intelligence_module, "aggregate_market_signals", count_aggregate)
    monkeypatch.setattr(shared_intelligence_module, "calculate_trend_and_velocity", count_trend)
    response = CoreIntelligenceService(observation_store=ObservationStore()).get_intelligence(
        CoreIntelligenceRequest(
            selected_skills=["Python"],
            location="India",
            time_range="custom",
            custom_days=1825,
        )
    )
    assert response.data_status == "available"
    assert calls == 1
    assert trend_calls == 1
    observed_metric = next(
        result for result in response.metric_results
        if result.metric_kind == "observed" and result.source == "jsearch"
    )
    assert observed_metric.canonical_entity_id == "python"
    assert observed_metric.metric_name == "demand"
    assert observed_metric.unit == "job_postings"
    assert observed_metric.denominator == 200
    assert observed_metric.denominator_unit == "all_job_postings"
    assert observed_metric.location == "India"
    assert observed_metric.scope == "country"
    assert observed_metric.query_id == "software"
    assert observed_metric.series_id == "jsearch:python:india:v1"
    assert observed_metric.source_urls == [f"https://source.example/{observed_metric.period}"]
    assert observed_metric.fetch_run_ids == [f"run-{observed_metric.period}"]
    trend_metric_names = {
        result.metric_name for result in response.metric_results
        if result.capability == "trend_velocity_analysis" and result.status == "ready"
    }
    assert {
        "long_term_trend_direction",
        "long_term_trend_slope",
        "latest_period_velocity",
    } <= trend_metric_names
    forecast_readiness = next(
        result for result in response.metric_results
        if result.capability == "forecast" and result.metric_kind == "readiness"
    )
    assert forecast_readiness.status in {"insufficient_data", "unavailable"}
    assert forecast_readiness.metric_name == "forecast_readiness"
    assert forecast_readiness.readiness_state in {"insufficient_history", "unavailable"}
    assert forecast_readiness.reason

    serialized = response.model_dump(mode="json")
    assert serialized["data_status"] == "available"
    assert isinstance(serialized["current_signals"], list)
    serialized_observed = next(
        result for result in serialized["metric_results"]
        if result["metric_kind"] == "observed" and result["source"] == "jsearch"
    )
    assert serialized_observed["denominator"] == 200
    assert serialized_observed["location"] == "India"
    assert serialized_observed["query_id"] == "software"

    assert _range_cutoff("custom", now, 1825) == now - timedelta(days=1825)
    with pytest.raises(ValidationError):
        CoreIntelligenceRequest(time_range="custom", custom_days=1826)
    assert CoreIntelligenceRequest().time_range == "30d"


def test_answer_reuses_trends_and_preserves_observation_provenance(monkeypatch):
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    now = datetime.now(timezone.utc)
    observations = []
    for index, value in enumerate((10, 14, 18, 22), start=4):
        month_index = now.year * 12 + now.month - index
        year, month_zero = divmod(month_index, 12)
        month = datetime(year, month_zero + 1, 15, tzinfo=timezone.utc)
        period = month.strftime("%Y-%m")
        observations.append(MarketObservation(
            id=f"obs-{period}",
            source="jsearch",
            signal_type="demand",
            observed_at=month,
            period=period,
            location="India",
            scope="country",
            skill="Python",
            skill_id="python",
            value=value,
            unit="job_postings",
            source_url=f"https://evidence.example/{period}",
            data_origin="real",
            history_type="platform_collected",
            series_id="jsearch:python:india:v1",
            query_id="software",
            fetch_run_id="run-1",
        ))

    original_aggregate = shared_intelligence_module.aggregate_market_signals
    original_trend = shared_intelligence_module.calculate_trend_and_velocity
    aggregate_calls = 0
    trend_calls = 0

    def count_aggregate(rows):
        nonlocal aggregate_calls
        aggregate_calls += 1
        return original_aggregate(rows)

    def count_trend(rows, **kwargs):
        nonlocal trend_calls
        trend_calls += 1
        return original_trend(rows, **kwargs)

    monkeypatch.setattr(shared_intelligence_module, "aggregate_market_signals", count_aggregate)
    monkeypatch.setattr(shared_intelligence_module, "calculate_trend_and_velocity", count_trend)
    request = CoreIntelligenceAnswerRequest(
        message="Analyze the Python trend",
        time_range="max",
        location="India",
        observations=observations,
    )
    plan = SimpleNamespace(context_summary={"primary_entity": "Python"})

    _, historical_evidence, _ = service._handle_historical_signal_retrieval(request, plan)
    _, trend_evidence, _ = service._handle_trend_velocity_analysis(request, plan)
    analysis = service._shared_market_analysis(request, plan)

    assert aggregate_calls == 1
    assert trend_calls == 1
    assert len(analysis.observations) == 4
    assert historical_evidence[0].unit == "job_postings"
    assert historical_evidence[0].source_url
    assert historical_evidence[0].fetch_run_id == "run-1"
    assert trend_evidence[0].source == "jsearch"
    assert trend_evidence[0].unit
    assert set(trend_evidence[0].supporting_observation_ids) == {
        observation.id for observation in observations
    }
    assert set(trend_evidence[0].supporting_source_urls) == {
        observation.source_url for observation in observations
    }


def test_shared_analysis_cache_isolated_by_request_user_and_company_scope():
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    request = CoreIntelligenceAnswerRequest(message="Analyze Python", time_range="max")
    plan = SimpleNamespace(
        request_id="plan-one",
        context_summary={
            "primary_entity": "Python",
            "_analysis_cache_scope": ("user-one", "company-one", "company"),
        },
    )

    first = service._shared_market_analysis(request, plan)
    assert service._shared_market_analysis(request, plan) is first

    plan.context_summary["_analysis_cache_scope"] = ("user-two", "company-one", "company")
    other_user = service._shared_market_analysis(request, plan)
    assert other_user is not first

    plan.context_summary["_analysis_cache_scope"] = ("user-one", "company-two", "company")
    other_company = service._shared_market_analysis(request, plan)
    assert other_company is not other_user

    plan.context_summary["_analysis_cache_scope"] = ("user-one", "company-one", "company")
    other_portal = service._shared_market_analysis(
        request.model_copy(update={"portal_type": "individual"}),
        plan,
    )
    assert other_portal is not first
    other_filters = service._shared_market_analysis(
        request.model_copy(update={"filters": {"country": "in"}}),
        plan,
    )
    assert other_filters is not first

    plan.context_summary["_analysis_cache_scope"] = ("user-one", "company-two", "company")
    plan.request_id = "plan-two"
    next_request = service._shared_market_analysis(request, plan)
    assert next_request is not other_company


def test_truncated_observation_history_is_explicit_in_answer_readiness(monkeypatch):
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    observation = MarketObservation(
        id="truncated-observation",
        source="jsearch",
        signal_type="demand",
        observed_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        period="2026-10",
        location="India",
        scope="country",
        skill="Python",
        skill_id="python",
        value=10,
        unit="job_postings",
        data_origin="real",
        history_type="platform_collected",
        series_id="jsearch:python:india:v1",
    )
    batch = ObservationBatch([observation], truncated=True)
    monkeypatch.setattr(service, "_get_market_observations", lambda **_kwargs: batch)
    original_analyze = orchestrator_module.analyze_market_observations
    analysis_calls = 0

    def count_analysis(observations):
        nonlocal analysis_calls
        analysis_calls += 1
        return original_analyze(observations)

    monkeypatch.setattr(orchestrator_module, "analyze_market_observations", count_analysis)

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Analyze the Python trend",
            time_range="max_available",
            location="India",
        ),
        authenticated_user=AuthenticatedUser(uid="truncated-user"),
    )

    readiness = next(fact for fact in response.facts if fact.fact_type == "analysis_readiness")
    assert readiness.metric_value == "incomplete_history"
    assert readiness.readiness_state == "incomplete_history"
    assert response.freshness["history_complete"] is False
    assert response.freshness["history_completeness_reason"]
    assert response.freshness["history_completeness_reason"] in response.limitations
    assert response.status == "partial"
    assert "OBSERVATION_HISTORY_INCOMPLETE" in response.reason_codes
    assert any(
        result.capability == "forecast"
        and result.metric_kind == "readiness"
        and result.status == "unavailable"
        and result.readiness_state == "incomplete_history"
        for result in response.metric_results
    )
    assert analysis_calls == 1

    class TruncatedCoreStore:
        def get_observations_by_skills(self, _skills, **_kwargs):
            return batch

    core_response = CoreIntelligenceService(
        observation_store=TruncatedCoreStore()
    ).get_intelligence(
        CoreIntelligenceRequest(selected_skills=["Python"], location="India")
    )
    assert core_response.status == "partial"
    assert core_response.data_state == "partial"
    assert core_response.readiness.overall_readiness_state == "incomplete_history"
    assert "OBSERVATION_READ_LIMIT_REACHED" in core_response.readiness.blocking_reasons
    assert core_response.readiness.ready_for_trend_count == 0
    assert core_response.readiness.ready_for_forecast_count == 0
    assert core_response.forecast["status"] == "unavailable"
    assert core_response.forecast["readiness"] == "incomplete_history"
    assert all(
        result.freshness_state == "incomplete" or result.status != "ready"
        for result in core_response.metric_results
        if result.capability in {"forecast", "skill_health", "skill_half_life", "trend_velocity_analysis"}
    )


def test_missing_provenance_is_not_reported_as_real_in_trend_readiness(monkeypatch):
    from app.analytics.shared_intelligence import SharedIntelligenceAnalysis

    observation = MarketObservation(
        id="legacy-without-provenance",
        source="jsearch",
        signal_type="demand",
        observed_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
        period="2025-10",
        skill="Python",
        value=1,
    )
    analysis = SharedIntelligenceAnalysis(
        observations=[observation],
        aggregated_signals=[],
        trend_results=[],
    )
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    monkeypatch.setattr(service, "_shared_market_analysis", lambda *_args: analysis)

    facts, evidence, _ = service._handle_trend_velocity_analysis(
        CoreIntelligenceAnswerRequest(message="Show Python trend"),
        SimpleNamespace(intent=None, context_summary={"primary_entity": "Python"}),
    )

    readiness_fact = next(fact for fact in facts if fact.fact_type == "analysis_readiness")
    readiness_evidence = next(item for item in evidence if item.signal_type == "analysis_readiness")
    assert readiness_fact.data_origin == "unavailable"
    assert readiness_evidence.data_origin == "unavailable"


def test_core_company_context_is_bound_to_authenticated_membership(monkeypatch):
    class Snapshot:
        def __init__(self, record):
            self.record = record

        def to_dict(self):
            return self.record

    class Document:
        def __init__(self, database, path):
            self.database = database
            self.path = path

        def get(self):
            return Snapshot(self.database.get(self.path))

        def collection(self, name):
            return Collection(self.database, f"{self.path}/{name}")

    class Collection:
        def __init__(self, database, path):
            self.database = database
            self.path = path

        def document(self, document_id):
            return Document(self.database, f"{self.path}/{document_id}")

    class Client:
        def __init__(self):
            self.documents = {
                "users/company-user": {"user_type": "company", "company_id": "member-company"},
                "companies/member-company": {
                    "status": "active",
                    "owner_uid": "company-user",
                },
            }

        def get(self, path):
            return self.documents.get(path)

        def collection(self, name):
            return Collection(self, name)

    client = Client()
    monkeypatch.setattr(dependencies, "get_firestore_client", lambda: client)
    with pytest.raises(HTTPException) as no_membership:
        core_intelligence._authorized_company_context(
            CoreIntelligenceRequest(portal_type="company"),
            AuthenticatedUser(uid="no-company"),
        )
    assert no_membership.value.status_code == 403

    with pytest.raises(HTTPException) as unauthorized:
        core_intelligence._authorized_company_context(
            CoreIntelligenceRequest(portal_type="employee", company_id="other-company"),
            AuthenticatedUser(uid="company-user", company_id="member-company"),
        )
    assert unauthorized.value.status_code == 403

    authorized_request, authorized_user = core_intelligence._authorized_company_context(
        CoreIntelligenceRequest(portal_type="company"),
        AuthenticatedUser(uid="company-user", company_id="member-company"),
    )
    assert authorized_request.company_id == "member-company"
    assert authorized_user.company_id == "member-company"


@pytest.mark.integration
def test_answer_keeps_validated_deterministic_fallback_when_llm_has_no_result(
    monkeypatch, local_reference_database,
):
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    monkeypatch.setattr(service.llm_service, "is_available", lambda: True)
    monkeypatch.setattr(service.llm_service, "generate_grounded_explanation", lambda **_kwargs: None)

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="What software tools does a Software Developer use?"
        ),
        authenticated_user=AuthenticatedUser(uid="fallback-user"),
    )

    assert response.execution_status == "completed"
    assert response.status == "ready"
    assert response.answer.startswith("Identified")
    assert response.facts
    assert response.evidence


@pytest.mark.integration
def test_answer_rejects_invalid_llm_output_and_returns_deterministic_fallback(
    monkeypatch, local_reference_database,
):
    service = ExecutionOrchestratorService(observation_store=EmptyObservationStore())
    monkeypatch.setattr(service.llm_service, "is_available", lambda: True)
    monkeypatch.setattr(
        service.llm_service,
        "generate_grounded_explanation",
        lambda **_kwargs: "There are 987654 current vacancies for this role.",
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="What software tools does a Software Developer use?"
        ),
        authenticated_user=AuthenticatedUser(uid="invalid-llm-user"),
    )

    assert response.execution_status == "completed"
    assert "987654" not in response.answer
    assert response.answer.startswith("Identified")
    assert response.facts
    assert response.evidence


def test_shared_metric_contract_downgrades_missing_units_and_metric_values():
    observation = MarketObservation(
        id="missing-unit",
        source="stackexchange",
        skill="Python",
        skill_id="python",
        signal_type="interest",
        observed_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        period="2026-09",
        value=10,
        quality="valid",
        series_id="stackexchange:python:v1",
    )
    observed = observed_metric_results([observation], history_complete=True)
    assert observed[0].status == "partial"
    assert observed[0].readiness_state == "incomplete_evidence"
    assert "measurement unit" in " ".join(observed[0].limitations)

    trend = SimpleNamespace(
        periods=["2026-05", "2026-06", "2026-07", "2026-08"],
        period_end="2026-08",
        is_trend_ready=True,
        canonical_skill_id="python",
        entity_name="Python",
        series_id="stackexchange:interest:python:v1",
        source="stackexchange",
        signal_type="interest",
        trend_direction="Increasing",
        trend_slope=None,
        slope=None,
        slope_unit=None,
        velocity=None,
        velocity_unit=None,
        calculation_version="test-v1",
    )
    results = trend_metric_results([trend], [observation], history_complete=True)
    by_name = {result.metric_name: result for result in results}
    assert by_name["long_term_trend_direction"].status == "ready"
    assert by_name["long_term_trend_slope_readiness"].status == "insufficient_data"
    assert by_name["latest_period_velocity_readiness"].status == "insufficient_data"


def test_fact_contract_does_not_mark_missing_or_stale_evidence_ready():
    facts = [
        StructuredFact(
            fact_type="market_snapshot",
            entity_name="Python",
            canonical_entity_id="python",
            metric_name="posting_count",
            metric_value=None,
            unit="job_postings",
            source="jsearch",
            evidence_reference="missing-value-evidence",
        ),
        StructuredFact(
            fact_type="trend_analysis",
            entity_name="Python",
            canonical_entity_id="python",
            metric_name="trend_direction",
            metric_value="Increasing",
            unit="job_postings per month",
            source="jsearch",
            evidence_reference="stale-evidence",
        ),
    ]
    evidence = [
        EvidenceItem(
            evidence_id="stale-evidence",
            source="jsearch",
            signal_type="demand",
            quality="stale",
            description="Stale fixture evidence.",
        )
    ]

    results = fact_metric_results(facts, evidence, history_complete=True)
    assert results[0].status == "insufficient_data"
    assert results[0].readiness_state == "missing_metric_value"
    assert results[1].status == "partial"
    assert results[1].freshness_state == "stale"

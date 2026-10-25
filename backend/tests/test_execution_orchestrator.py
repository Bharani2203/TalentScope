"""Offline test suite for G2.6 Task 6: Core Intelligence Execution Orchestrator.

Verifies:
1. Successful execution of implemented capabilities using real local SQLite data.
2. A blocked capability never invokes its handler.
3. Missing entity or ambiguity returns structured clarification without analytical execution.
4. Insufficient historical data does not produce a trend.
5. Missing evidence does not produce fabricated citations.
6. Numeric claims correspond to returned structured facts.
7. Handler exceptions return a safe 'failed' result without leaking tracebacks.
8. Forecasting and simulation remain non-executable.
9. Job-search results are labelled strictly as stored postings, not global totals.
10. Portal authorization prevents cross-company data exposure.
11. Identical requests produce deterministic facts and reason codes.
12. Task 5 status inconsistency regression test.
13. Read safety: zero live Firestore calls, zero network requests.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)
from app.models.intent_planner import IntelligencePlanRequest
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_orch_user_1",
        email="orchestrator@example.com",
    )


def mock_company_user(company_id: str = "comp_alpha") -> UserProfile:
    return UserProfile(
        uid="test_comp_user_1",
        email="corp@alpha.com",
        company_id=company_id,
    )


def _make_obs(
    *,
    source: str = "jsearch",
    signal_type: str = "demand",
    skill: str = "Python",
    skill_id: str = "python",
    period: str = "2026-05",
    value: float = 100.0,
    posting_id: str | None = None,
    metadata: dict | None = None,
) -> MarketObservation:
    year, month = (int(p) for p in period.split("-"))
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
    return MarketObservation(
        id=f"obs-{source}-{skill_id}-{period}",
        source=source,
        signal_type=signal_type,
        observed_at=dt,
        period=period,
        location="Global",
        scope="global",
        skill=skill,
        skill_id=skill_id,
        value=value,
        unit="job_postings" if signal_type == "demand" else "repositories" if signal_type == "adoption" else "questions",
        posting_id=posting_id,
        metadata=metadata or {},
        data_origin="real",
        history_type="platform_collected",
        series_id=f"{source}:{signal_type}:{skill_id}:v1",
        query_id=f"{source}:{signal_type}:query-v1",
        quality="valid",
        provider_posted_at=datetime.now(timezone.utc) if signal_type == "demand" else None,
    )


def test_answer_request_accepts_frontend_twelve_month_filter_label():
    """The UI's 12 Months label must normalize identically in request and filters."""
    request = CoreIntelligenceAnswerRequest.model_validate({
        "message": "Review this skill history",
        "portal_type": "individual",
        "domain": "skill",
        "time_range": "12m",
        "filters": {
            "domain": "skill",
            "requested_time_window": "12 Months",
        },
    })

    assert request.time_range == "1y"
    assert request.filters["requested_time_window"] == "12 Months"


def test_explicit_capability_overrides_intent_classification():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="Show market snapshot for Python",
            portal_type="individual",
            domain="market",
            capability_id="market_snapshot",
        ),
        authenticated_user=mock_auth_user(),
    )

    assert plan.intent == "retrieve_snapshot"
    assert plan.selected_capabilities == ["market_snapshot"]


def test_market_hiring_snapshot_excludes_newer_github_adoption_observation(monkeypatch):
    """A newer adoption observation must never satisfy an employer-demand query."""
    from types import SimpleNamespace

    service = ExecutionOrchestratorService()
    observations = [
        _make_obs(source="jsearch", signal_type="demand", period="2026-04", value=100),
        _make_obs(source="github", signal_type="adoption", period="2026-06", value=250),
    ]
    monkeypatch.setattr(
        service, "_shared_market_analysis",
        lambda *_args, **_kwargs: SimpleNamespace(observations=observations),
    )
    request = CoreIntelligenceAnswerRequest(
        message="What hiring signals are available for Python?",
        portal_type="individual", domain="market", capability_id="market_snapshot",
    )
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message=request.message, portal_type="individual", domain="market",
            capability_id="market_snapshot",
        ),
        authenticated_user=mock_auth_user(),
    )

    facts, evidence, _limitations = service._handle_market_snapshot(request, plan)

    assert [fact.source for fact in facts if fact.fact_type == "market_snapshot"] == ["jsearch"]
    assert [item.source for item in evidence] == ["jsearch"]
    assert facts[0].details["signal_type"] == "demand"


def test_market_hiring_snapshot_with_only_github_is_insufficient(monkeypatch):
    """Adoption alone cannot be promoted to hiring evidence."""
    from types import SimpleNamespace

    service = ExecutionOrchestratorService()
    monkeypatch.setattr(
        service, "_shared_market_analysis",
        lambda *_args, **_kwargs: SimpleNamespace(observations=[
            _make_obs(source="github", signal_type="adoption", period="2026-06", value=250),
        ]),
    )
    request = CoreIntelligenceAnswerRequest(
        message="What hiring signals are available for Python?",
        portal_type="individual", domain="market", capability_id="market_snapshot",
    )
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message=request.message, portal_type="individual", domain="market",
            capability_id="market_snapshot",
        ),
        authenticated_user=mock_auth_user(),
    )

    facts, evidence, _limitations = service._handle_market_snapshot(request, plan)

    assert facts[0].fact_type == "analysis_readiness"
    assert facts[0].readiness_state == "insufficient_data"
    assert "Other signal families are not hiring evidence" in facts[0].details["reason"]
    assert evidence == []


def test_market_snapshot_summarizes_series_coverage_and_preserves_provenance(monkeypatch):
    from types import SimpleNamespace
    from datetime import timedelta

    service = ExecutionOrchestratorService()
    now = datetime.now(timezone.utc)
    periods = []
    year, month = now.year, now.month
    for _ in range(3):
        periods.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    observations = []
    for index, period in enumerate(reversed(periods)):
        year, month = map(int, period.split("-"))
        observations.append(MarketObservation(
            id=f"snapshot-{period}", source="jsearch", signal_type="demand", skill="Python",
            skill_id="python", location="India", scope="country",
            observed_at=datetime(year, month, 15, tzinfo=timezone.utc), period=period,
            value=10 + index, unit="job_postings", data_origin="real",
            history_type="platform_collected", series_id="jsearch:python:india:v1",
            query_id="jsearch-python-india", fetch_run_id=f"run-{period}",
            created_at=now - timedelta(hours=1), quality="valid",
        ))
    # Same period and skill, but distinct source/metric identity: never collapse it.
    other = observations[-1].model_copy(update={
        "id": "stackoverflow-python-india", "source": "stackoverflow",
        "signal_type": "interest", "unit": "questions", "series_id": "stack:python:india:v1",
        "fetch_run_id": None,
    })
    monkeypatch.setattr(service, "_shared_market_analysis", lambda *_a, **_k: SimpleNamespace(observations=observations + [other]))
    request = CoreIntelligenceAnswerRequest(
        message="Show a market snapshot for Python", portal_type="individual", domain="market",
        capability_id="market_snapshot",
    )
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(message=request.message, portal_type="individual", domain="market", capability_id="market_snapshot"),
        authenticated_user=mock_auth_user(),
    )

    facts, evidence, _ = service._handle_market_snapshot(request, plan)

    assert len(facts) == len(evidence) == 2
    demand_fact = next(fact for fact in facts if fact.source == "jsearch")
    demand_evidence = next(item for item in evidence if item.source == "jsearch")
    assert demand_fact.details["observation_count"] == 3
    assert demand_fact.details["period_frequency"] == "monthly"
    assert demand_fact.details["time_coverage_start"] == min(periods)
    assert demand_fact.details["latest_completed_period"] == max(p for p in periods if p < f"{now.year:04d}-{now.month:02d}")
    assert len(demand_evidence.supporting_observation_ids) == 3
    assert len({fact.series_id for fact in facts}) == 2


def test_market_snapshot_surfaces_partial_collection_quality(monkeypatch):
    from types import SimpleNamespace

    service = ExecutionOrchestratorService()
    observation = _make_obs(period="2026-09").model_copy(update={
        "quality": {
            "collection_complete": False,
            "pagination_complete": False,
            "sampling_frame": "one bounded provider page",
        },
        "fetch_run_id": "partial-run-1",
    })
    monkeypatch.setattr(
        service, "_shared_market_analysis",
        lambda *_a, **_k: SimpleNamespace(observations=[observation]),
    )
    request = CoreIntelligenceAnswerRequest(
        message="Show a market snapshot for Python", portal_type="individual",
        domain="market", capability_id="market_snapshot",
    )
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message=request.message, portal_type="individual", domain="market",
            capability_id="market_snapshot",
        ),
        authenticated_user=mock_auth_user(),
    )

    facts, evidence, limitations = service._handle_market_snapshot(request, plan)

    snapshot = next(fact for fact in facts if fact.fact_type == "market_snapshot")
    assert snapshot.quality_state == "partial"
    assert snapshot.details["collection_completeness"] == "partial"
    assert snapshot.details["collection_status"] == "partial"
    assert evidence[0].quality == "partial"
    assert "partial collection coverage" in limitations[-1]


@pytest.mark.parametrize(
    "message",
    [
        "Why is Python demand changing?",
        "What demand trend is observed for Python?",
    ],
)
def test_explicit_trend_feature_accepts_both_python_question_variants(message):
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="trend_velocity_analysis",
        ),
        authenticated_user=mock_auth_user(),
    )

    assert plan.intent == "analyze_trend"
    assert plan.plan_status in {"ready_to_execute", "insufficient_data"}
    assert plan.selected_capabilities == ["trend_velocity_analysis"]


@pytest.mark.parametrize(
    "message",
    [
        "Why is Python demand changing?",
        "What demand trend is observed for Python?",
    ],
)
def test_explicit_trend_question_runs_the_selected_handler_with_fixture_observations(
    monkeypatch, message,
):
    service = ExecutionOrchestratorService()
    monkeypatch.setattr(service.llm_service, "is_available", lambda: False)
    observations = [
        _make_obs(period="2026-04", value=100.0),
        _make_obs(period="2026-05", value=115.0),
        _make_obs(period="2026-06", value=130.0),
        _make_obs(period="2026-07", value=145.0),
    ]

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="trend_velocity_analysis",
            time_range="max_available",
            observations=observations,
        ),
        authenticated_user=mock_auth_user(),
    )

    assert response.execution_status == "completed"
    assert response.intent == "analyze_trend"
    assert response.capabilities_used == ["trend_velocity_analysis"]
    assert any(fact.fact_type == "trend_analysis" for fact in response.facts)


def test_conflicting_selected_capability_clarifies_instead_of_switching():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(
            message="What evidence supports the Python trend?",
            portal_type="individual",
            domain="market",
            capability_id="market_snapshot",
        ),
        authenticated_user=mock_auth_user(),
    )

    assert plan.intent == "unsupported_or_unclear"
    assert plan.plan_status == "requires_clarification"
    assert plan.clarification_required is True
    assert plan.selected_capabilities == []


def test_general_question_with_selected_trend_feature_clarifies(monkeypatch):
    service = ExecutionOrchestratorService()
    monkeypatch.setattr(service.llm_service, "is_available", lambda: True)
    monkeypatch.setattr(
        service.llm_service,
        "generate_grounded_explanation",
        lambda **kwargs: (
            "Common design directions include clearer typography, accessible color, "
            "and interfaces that adapt to context."
            if kwargs.get("general_knowledge") and kwargs.get("facts") == [] else None
        ),
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="What are the latest UI/UX design trends?",
        portal_type="individual",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ), authenticated_user=mock_auth_user())

    assert response.intent == "unsupported_or_unclear"
    assert response.execution_status == "requires_clarification"
    assert response.capabilities_used == []
    assert "selected feature" in response.answer.lower()


def test_general_question_with_selected_feature_does_not_claim_platform_finding(monkeypatch):
    service = ExecutionOrchestratorService()
    monkeypatch.setattr(service.llm_service, "is_available", lambda: False)
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="What are the latest UI/UX design trends?",
        domain="skill",
        capability_id="trend_velocity_analysis",
        filters={"salary_band": "high"},
    ), authenticated_user=mock_auth_user())
    assert response.status == "insufficient_data"
    assert response.execution_status == "requires_clarification"
    assert response.capabilities_used == []
    assert response.facts == []
    assert response.evidence == []


def test_python_general_explanation_uses_offline_fallback_when_provider_unavailable(monkeypatch):
    service = ExecutionOrchestratorService()
    monkeypatch.setattr(service.llm_service, "is_available", lambda: False)
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="What is Python used for?", domain="skill"
    ), authenticated_user=mock_auth_user())
    assert response.intent == "general_explanation"
    assert response.status == "ready"
    assert "web services" in response.answer
    assert "not a TalentScope market finding" in response.answer
    assert response.facts == [] and response.evidence == [] and response.capabilities_used == []


def test_skill_domain_job_question_returns_safe_switch_action_without_searching():
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="Which companies are hiring Python developers?",
            domain="skill",
            capability_id="trend_velocity_analysis",
        ),
        authenticated_user=mock_auth_user(),
    )
    assert response.intent == "unsupported_or_unclear"
    assert response.capabilities_used == []
    assert response.facts == [] and response.evidence == []
    assert "Change the selected feature" in response.answer
    assert "Which companies are hiring Python developers?" in response.answer


def test_explicit_capability_ignores_domain_but_rejects_unavailable_operation():
    planner = IntentPlannerService()
    wrong_domain = planner.create_plan(
        IntelligencePlanRequest(
            message="Show postings for Python",
            portal_type="individual",
            domain="skill",
            capability_id="job_posting_search",
        ),
        authenticated_user=mock_auth_user(),
    )
    unavailable = planner.create_plan(
        IntelligencePlanRequest(
            message="Simulate workforce headcount scenario",
            portal_type="company",
            domain="market",
            capability_id="workforce_what_if_simulation",
        ),
        authenticated_user=mock_auth_user(),
    )

    assert wrong_domain.plan_status == "ready_to_execute"
    assert wrong_domain.clarification_required is False
    assert wrong_domain.selected_capabilities == ["job_posting_search"]
    assert unavailable.plan_status == "unsupported"
    assert unavailable.selected_capabilities == ["workforce_what_if_simulation"]
    assert "not currently executable" in unavailable.limitations[0].lower()


def test_cross_domain_question_clarifies_without_false_capability_attribution(monkeypatch):
    # B2 clarification options are sourced from the aggregate; keep this
    # routing test isolated from any Firestore client.
    monkeypatch.setattr(
        "app.services.collected_posting_skills_service.get_collected_posting_skills",
        lambda **_kwargs: {"title_counts": [], "location_counts": [], "skill_counts": []},
    )
    response = ExecutionOrchestratorService().answer(
        CoreIntelligenceAnswerRequest(
            message="Which companies are hiring the most?",
            portal_type="individual",
            domain="skill",
            capability_id="trend_velocity_analysis",
        ),
        authenticated_user=mock_auth_user(),
    )

    assert response.execution_status == "requires_clarification"
    assert response.capabilities_used == []
    assert response.answer_block.clarification.classification == "TOO BROAD"
    assert response.answer_block.clarification.slot == "role"
    assert response.answer == "Which job role should I search for?"


# =============================================================================
# 1. SAFETY & ISOLATION CHECKS
# =============================================================================

def test_no_firestore_imports_in_execution_orchestrator():
    """Verify ExecutionOrchestratorService does not import or call Firestore."""
    import app.services.execution_orchestrator_service as mod

    source = inspect.getsource(mod)
    assert "firebase_admin" not in source, "ExecutionOrchestratorService must not import firebase_admin"
    assert "get_firestore_client" not in source, "ExecutionOrchestratorService must not call get_firestore_client"
    assert "google.cloud.firestore" not in source, "ExecutionOrchestratorService must not import firestore"


# =============================================================================
# 2. SUCCESSFUL CAPABILITY EXECUTION (LOCAL SQLITE)
# =============================================================================

@pytest.mark.integration
def test_successful_occupation_software_skills_execution(local_reference_database):
    """Verify occupation software skills capability executes against local SQLite O*NET data."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert resp.plan_status == "ready_to_execute"
    assert "occupation_software_skills" in resp.capabilities_used
    assert len(resp.facts) > 0
    assert any(f.fact_type == "software_skill" for f in resp.facts)
    assert len(resp.evidence) > 0
    assert resp.evidence[0].source == "ref_onet_software_skills"
    assert "Software Developers" in resp.answer


@pytest.mark.integration
@pytest.mark.parametrize(("entity", "ambient_skill"), [("Python", "HTML"), ("Java", "Python")])
def test_skill_reference_is_scoped_to_primary_entity_and_taxonomy(monkeypatch, local_reference_database, entity, ambient_skill):
    service = ExecutionOrchestratorService()

    def unexpected_market_analysis(*args, **kwargs):
        raise AssertionError("reference lookup must not invoke market analytics")

    def unexpected_github_lookup(*args, **kwargs):
        raise AssertionError("reference lookup must not retrieve developer-adoption series")

    monkeypatch.setattr(service, "_shared_market_analysis", unexpected_market_analysis)
    monkeypatch.setattr(service.reference_store, "get_github_adoption_series", unexpected_github_lookup)
    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message=f"Show the canonical definition and category for {entity}.",
            domain="skill",
            selected_skills=[ambient_skill],
            filters={
                "domain": "skill",
                "scope": "My Skills",
                "selected_skill": ambient_skill,
                "selected_skills": [ambient_skill],
                "selected_feature": "skill_technology_reference",
            },
        ),
        authenticated_user=mock_auth_user(),
    )

    assert response.planned_primary_capability == "skill_technology_reference"
    assert response.executed_primary_capability == "skill_technology_reference"
    assert "skill_technology_reference" in response.capabilities_used
    assert not ({"skill_health", "skill_half_life", "forecast"} & set(response.capabilities))
    assert {fact.entity_name for fact in response.facts} == {entity}
    assert {fact.fact_type for fact in response.facts} == {"canonical_reference"}
    assert {item.signal_type for item in response.evidence} == {"taxonomy_lookup"}
    assert "developer adoption" not in response.answer.lower()
    assert "github" not in response.answer.lower()
    assert "definition is unavailable" in response.answer.lower()
    assert "Sources" not in response.answer
    assert response.unapplied_filters == []


@pytest.mark.integration
def test_successful_related_occupations_execution(local_reference_database):
    """Verify related occupations crosswalk executes against local SQLite O*NET data."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Show related occupations for Software Developers")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert "related_occupations" in resp.capabilities_used
    assert any(f.fact_type == "related_occupation" for f in resp.facts)
    assert any(f.source == "ref_onet_related_occupations" for f in resp.facts)
    assert "Related Occupations" in resp.answer


def test_successful_trend_execution_with_sufficient_periods():
    """Verify trend velocity analysis executes when >= 4 consecutive periods are provided."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(period="2026-04", value=100.0),
        _make_obs(period="2026-05", value=115.0),
        _make_obs(period="2026-06", value=130.0),
        _make_obs(period="2026-07", value=145.0),
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert "trend_velocity_analysis" in resp.capabilities_used
    trend_fact = next((f for f in resp.facts if f.fact_type == "trend_analysis"), None)
    assert trend_fact is not None
    assert trend_fact.metric_value in {"Increasing", "growing"}
    assert "Theil-Sen Median Slope" in resp.answer
    assert "15.0" in resp.answer or "15" in resp.answer


# =============================================================================
# 3. BLOCKED & GATED EXECUTION
# =============================================================================

@pytest.mark.integration
def test_blocked_capability_never_invokes_handler(monkeypatch, local_reference_database):
    """Verify that if capability readiness is blocked, the handler is never invoked."""
    service = ExecutionOrchestratorService()
    handler_invoked = False

    def mock_handler(*args, **kwargs):
        nonlocal handler_invoked
        handler_invoked = True
        return [], [], []

    monkeypatch.setitem(service._handler_registry, "occupation_software_skills", mock_handler)

    # Force plan status to blocked
    orig_create_plan = service.intent_planner.create_plan
    def mock_plan(*args, **kwargs):
        p = orig_create_plan(*args, **kwargs)
        return p.model_copy(update={"plan_status": "blocked"})

    monkeypatch.setattr(service.intent_planner, "create_plan", mock_plan)

    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "blocked"
    assert resp.plan_status == "blocked"
    assert handler_invoked is False
    assert "blocked" in resp.reason_codes[0].lower()


# =============================================================================
# 4. MISSING ENTITY & AMBIGUITY
# =============================================================================

def test_missing_entity_returns_clarification_without_execution():
    """Verify that requests missing an entity return clarification and do not execute analytical handlers."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Show its trend")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "requires_clarification"
    assert resp.plan_status == "requires_clarification"
    assert len(resp.follow_up_questions) > 0
    assert len(resp.facts) == 0
    assert len(resp.capabilities_used) == 0


def test_ambiguous_entity_returns_clarification():
    """Verify that ambiguous entity tokens prompt for clarification with candidate options."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What is the trend for c?")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "requires_clarification"
    assert resp.plan_status == "requires_clarification"
    assert any("multiple entities" in q for q in resp.follow_up_questions)
    assert len(resp.facts) == 0


# =============================================================================
# 5. INSUFFICIENT HISTORICAL DATA
# =============================================================================

def test_insufficient_historical_data_does_not_produce_trend():
    """Verify that < 4 periods does not calculate trend and returns insufficient_data status."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(period="2026-06", value=100.0),
        _make_obs(period="2026-07", value=110.0),
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "insufficient_data"
    assert "trend_velocity_analysis" not in resp.capabilities_used
    assert len(resp.facts) == 0
    assert "INSUFFICIENT_TREND_HISTORY" in resp.reason_codes
    assert resp.planned_primary_capability == "trend_velocity_analysis"
    assert resp.executed_primary_capability is None
    assert not ({"skill_health", "skill_half_life", "forecast"} & set(resp.capabilities))
    assert "only 2 eligible completed monthly periods" in resp.answer
    assert "2026-06 through 2026-07" in resp.answer
    assert "at least 4 consecutive comparable completed monthly periods" in resp.answer.lower()


# =============================================================================
# 6. EVIDENCE VALIDATION & CITATIONS
# =============================================================================

def test_missing_evidence_does_not_produce_fabricated_citations():
    """Verify that no fabricated citations are produced when evidence is unavailable."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        observations=[],
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "insufficient_data"
    assert len(resp.evidence) == 0
    assert "ev_" not in resp.answer


def test_evidence_summary_reports_empty_store_as_insufficient_without_citation():
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message="Show evidence and sources for Python",
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
        ),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_evidence_provenance_retrieval(
        CoreIntelligenceAnswerRequest(
            message="Show evidence and sources for Python",
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
        ),
        plan,
    )

    summary = next(fact for fact in facts if fact.fact_type == "evidence_summary")
    assert evidence == []
    assert summary.metric_value == 0
    assert summary.data_origin == "unavailable"
    assert summary.readiness_state == "insufficient_data"
    assert summary.evidence_reference is None
    assert "No matching stored observation" in summary.details["reason"]


def test_evidence_retrieval_reads_actual_local_onet_reference_records(local_reference_database):
    service = ExecutionOrchestratorService(db_path=local_reference_database)
    message = "Show O*NET taxonomy evidence for Software Developers"
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
        ),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_evidence_provenance_retrieval(
        CoreIntelligenceAnswerRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
            target_role="Software Developers",
        ),
        plan,
    )

    assert evidence
    assert all(item.source == "ref_onet_essential_skills" for item in evidence)
    assert all(item.history_type == "reference_taxonomy" for item in evidence)
    assert all(item.provenance_id for item in evidence)
    summary = next(fact for fact in facts if fact.fact_type == "evidence_summary")
    assert summary.metric_value == len(evidence)
    assert summary.evidence_reference in {item.evidence_id for item in evidence}


def test_evidence_retrieval_reads_actual_local_github_adoption_records(local_reference_database):
    service = ExecutionOrchestratorService(db_path=local_reference_database)
    message = "Show GitHub Innovation Graph developer adoption evidence for Python in India"
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
        ),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_evidence_provenance_retrieval(
        CoreIntelligenceAnswerRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="evidence_provenance_retrieval",
        ),
        plan,
    )

    assert evidence
    assert all(item.measured_signal_type == "adoption" for item in evidence)
    assert all(item.location == "IN" and item.scope == "country" for item in evidence)
    assert all(item.period and item.period.endswith(tuple(f"Q{quarter}" for quarter in range(1, 5))) for item in evidence)
    assert all("unique developers per quarter" in item.description for item in evidence)
    assert all("not hiring demand" in item.description for item in evidence)
    summary = next(fact for fact in facts if fact.fact_type == "evidence_summary")
    assert summary.metric_value == len(evidence)


def test_action_feature_keeps_action_intent_when_question_mentions_evidence():
    service = ExecutionOrchestratorService()
    message = "What should I learn next based on evidence?"
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message=message,
            portal_type="individual",
            domain="skill",
            capability_id="action_recommendations",
        ),
        authenticated_user=mock_auth_user(),
    )
    assert plan.intent == "synthesize_actions"
    assert plan.selected_capabilities == ["action_recommendations"]


# =============================================================================
# 7. NUMERIC CLAIMS GROUNDED IN STRUCTURED FACTS
# =============================================================================

def test_numeric_claims_grounded_in_structured_facts():
    """Verify that numerical claims in response text match structured facts."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(period="2026-04", value=200.0),
        _make_obs(period="2026-05", value=220.0),
        _make_obs(period="2026-06", value=240.0),
        _make_obs(period="2026-07", value=260.0),
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    trend_fact = next(f for f in resp.facts if f.fact_type == "trend_analysis")
    slope = trend_fact.details["trend_slope"]
    velocity = trend_fact.details["monthly_velocity"]

    assert str(slope) in resp.answer
    assert str(velocity) in resp.answer


# =============================================================================
# 8. HANDLER EXCEPTION RESILIENCE
# =============================================================================

@pytest.mark.integration
def test_handler_exception_returns_safe_failed_result(monkeypatch, local_reference_database):
    """Verify that an unexpected exception in a handler returns a safe 'failed' status."""
    service = ExecutionOrchestratorService()

    def buggy_handler(*args, **kwargs):
        raise RuntimeError("Simulated internal storage timeout")

    monkeypatch.setitem(service._handler_registry, "occupation_software_skills", buggy_handler)

    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "failed"
    assert "HANDLER_EXECUTION_FAILED" in resp.reason_codes
    assert "Simulated internal storage timeout" not in resp.answer
    assert "couldn't complete this analysis" in resp.answer
    assert f"Reference: {resp.request_id}" in resp.answer
    assert "Simulated unexpected handler failure" not in resp.answer


# =============================================================================
# 9. FORECASTING & SIMULATION REMAIN NON-EXECUTABLE
# =============================================================================

def test_forecasting_and_simulation_strictly_non_executable():
    """Verify forecasting and workforce simulation queries are rejected with unsupported status."""
    service = ExecutionOrchestratorService()

    req_fc = CoreIntelligenceAnswerRequest(message="Forecast demand for Python in 2027")
    resp_fc = service.answer(req_fc, authenticated_user=mock_auth_user())
    assert resp_fc.execution_status in {"unsupported", "insufficient_data"}
    assert resp_fc.plan_status in {"unsupported", "insufficient_data"}
    assert len(resp_fc.facts) == 0

    req_sim = CoreIntelligenceAnswerRequest(message="Simulate workforce attrition for engineering team")
    resp_sim = service.answer(req_sim, authenticated_user=mock_auth_user())
    assert resp_sim.execution_status == "unsupported"
    assert resp_sim.plan_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp_sim.reason_codes
    assert len(resp_sim.facts) == 0


# =============================================================================
# 10. JOB SEARCH LABELED AS STORED POSTINGS
# =============================================================================

def test_job_search_results_labeled_as_stored_postings_not_global_totals():
    """Verify job postings are described strictly as stored postings, not global totals."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(
            source="jsearch",
            posting_id="job_dev_101",
            skill="React",
            metadata={
                "job_title": "Frontend Engineer",
                "company": "Acme Corp",
                "apply_link": "https://jobs.example.test/frontend-engineer",
                "posted_at": "2026-07-10",
                "skills_raw": ["React", "TypeScript"],
            },
        )
    ]
    req = CoreIntelligenceAnswerRequest(
        message="Find jobs for React",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert "job_posting_search" in resp.capabilities_used
    assert "stored collection" in resp.answer
    assert "not total global vacancies" in resp.answer
    assert resp.evidence[0].source_url == "https://jobs.example.test/frontend-engineer"
    assert resp.facts[0].details["postings"][0]["posting_date"] == "2026-07-10"
    assert resp.facts[0].details["postings"][0]["required_skills"] == ["React", "TypeScript"]
    assert "React" in resp.answer
    assert "TypeScript" in resp.answer
    assert resp.facts[0].details["search_window_limit"] is None
    assert "500" not in resp.answer


def test_workforce_impact_question_does_not_claim_unsupported_simulation():
    service = ExecutionOrchestratorService()
    request = CoreIntelligenceAnswerRequest(
        message="How could changing technology requirements affect our workforce?",
        portal_type="company",
        company_id="comp_alpha",
    )

    response = service.answer(request, authenticated_user=mock_company_user("comp_alpha"))

    assert response.intent == "simulate_workforce_scenarios"
    assert response.execution_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in response.reason_codes
    assert response.facts == []


def test_empty_job_search_does_not_create_synthetic_evidence():
    service = ExecutionOrchestratorService()
    service.firestore_store = None

    class EmptyMarketStore:
        @staticmethod
        def get_observations(**_kwargs):
            return []

    service.market_store = EmptyMarketStore()
    req = CoreIntelligenceAnswerRequest(message="Find jobs for Python", time_range="max_available")
    plan = service.intent_planner.create_plan(IntelligencePlanRequest(
        message=req.message,
        domain="job",
        time_range=req.time_range,
    ))

    facts, evidence, _ = service._handle_job_posting_search(req, plan)

    assert facts[0].metric_value == 0
    assert facts[0].readiness_state == "insufficient_data"
    assert evidence == []
    assert facts[0].evidence_reference is None


def test_employer_hiring_question_uses_stored_jobs_and_reports_empty_sample(monkeypatch):
    service = ExecutionOrchestratorService()
    class EmptyObservationStore:
        @staticmethod
        def get_observations_by_skill(**_kwargs):
            return []

        @staticmethod
        def get_observations(**_kwargs):
            return []

    service.firestore_store = EmptyObservationStore()
    monkeypatch.setattr(
        "app.services.job_storage_service.search_stored_jsearch_jobs",
        lambda **_kwargs: [],
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Which companies are hiring Python developers?",
        domain="job",
        capability_id="job_posting_search",
        time_range="max_available",
    ), authenticated_user=mock_auth_user())

    assert response.intent == "search_jobs"
    assert "job_posting_search" in response.capabilities_used
    assert response.status == "insufficient_data"
    assert response.evidence == []
    assert any("stored postings" in limitation.lower() for limitation in response.limitations)


def test_firestore_job_search_limit_matches_reported_metadata(monkeypatch):
    service = ExecutionOrchestratorService()
    service.firestore_store = object()
    search_args = {}

    def fake_search(**kwargs):
        search_args.update(kwargs)
        return []

    monkeypatch.setattr(
        "app.services.job_storage_service.search_stored_jsearch_jobs",
        fake_search,
    )
    request = CoreIntelligenceAnswerRequest(
        message="Find jobs for React",
        time_range="max_available",
    )
    plan = service.intent_planner.create_plan(IntelligencePlanRequest(
        message=request.message,
        domain="job",
        time_range=request.time_range,
    ))

    facts, _, limitations = service._handle_job_posting_search(request, plan)

    assert search_args["limit"] == 100
    assert facts[0].details["search_window_limit"] == search_args["limit"]
    assert any("100 matching stored postings after scanning" in item for item in limitations)


def test_empty_saved_scope_never_falls_back_to_prompt_entity():
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        domain="skill",
        filters={"scope": "Favourites", "scope_empty": True},
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.status == "insufficient_data"
    assert resp.reason_codes == ["EMPTY_FILTER_SCOPE"]
    assert resp.facts == []
    assert "no saved entities" in resp.answer


def test_supported_time_window_aliases_keep_frontend_range_semantics():
    cutoff_three_months = ExecutionOrchestratorService._observation_cutoff("3m")
    cutoff_max = ExecutionOrchestratorService._observation_cutoff("max")

    assert (datetime.now(timezone.utc) - cutoff_three_months).days in range(89, 92)
    assert 1824 <= (datetime.now(timezone.utc) - cutoff_max).days <= 1826


# =============================================================================
# 11. PORTAL AUTHORIZATION & COMPANY DATA ISOLATION
# =============================================================================

def test_portal_authorization_prevents_cross_company_exposure():
    """Verify that requests for another company's workforce are blocked with unauthorized reason code."""
    service = ExecutionOrchestratorService()

    # User belongs to comp_alpha, but requests comp_beta
    user = mock_company_user("comp_alpha")
    req = CoreIntelligenceAnswerRequest(
        message="Show company workforce intelligence",
        portal_type="company",
        company_id="comp_beta",
    )

    resp = service.answer(req, authenticated_user=user)

    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in resp.reason_codes
    assert "Access denied" in resp.answer
    assert len(resp.facts) == 0


def test_unauthenticated_company_access_blocked():
    """Verify unauthenticated requests to company portal are blocked."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Show company workforce intelligence",
        portal_type="company",
        company_id="comp_alpha",
    )

    resp = service.answer(req, authenticated_user=None)

    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_PORTAL_ACCESS" in resp.reason_codes


# =============================================================================
# 12. DETERMINISM
# =============================================================================

def test_deterministic_execution_output():
    """Verify repeated identical queries produce identical structured facts and reason codes."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    resp1 = service.answer(req, authenticated_user=mock_auth_user())
    resp2 = service.answer(req, authenticated_user=mock_auth_user())

    assert resp1.request_id != resp2.request_id  # UUID trace is unique
    assert resp1.execution_status == resp2.execution_status
    assert resp1.plan_status == resp2.plan_status
    assert resp1.capabilities_used == resp2.capabilities_used
    assert resp1.reason_codes == resp2.reason_codes
    assert len(resp1.facts) == len(resp2.facts)
    for f1, f2 in zip(resp1.facts, resp2.facts):
        assert f1.metric_name == f2.metric_name
        assert f1.metric_value == f2.metric_value
        assert f1.source == f2.source


# =============================================================================
# 13. TASK 5 STATUS INCONSISTENCY REGRESSION TEST
# =============================================================================

def test_task_5_plan_status_inconsistency_regression():
    """Regression test: query with no missing context but insufficient observation data

    must produce plan_status = 'insufficient_data', NOT 'requires_clarification'.
    """
    planner = IntentPlannerService()
    plan = planner.create_plan(
        IntelligencePlanRequest(message="What is the trend for Python?")
    )

    assert plan.clarification_required is False
    assert plan.missing_context == []
    assert plan.plan_status == "insufficient_data"
    assert plan.plan_status != "requires_clarification"


# =============================================================================
# 14. API ENDPOINT INTEGRATION
# =============================================================================

@pytest.mark.integration
def test_answer_api_endpoint(local_reference_database):
    """Verify POST /api/v1/intelligence/answer returns validated answer response."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    try:
        resp = client.post(
            "/api/v1/intelligence/answer",
            json={"message": "What software tools does a Software Developer use?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"].startswith("ans_")
        assert data["execution_status"] == "completed"
        assert "occupation_software_skills" in data["capabilities_used"]
        assert len(data["facts"]) > 0
        assert "Software Developers" in data["answer"]

        untrusted = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "What is the trend for Python?",
                "time_range": "max_available",
                "observations": [
                    _make_obs(period="2026-04").model_dump(mode="json"),
                ],
            },
        )
        assert untrusted.status_code == 422
        assert "cannot be supplied by clients" in untrusted.json()["detail"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


@pytest.mark.integration
def test_answer_api_accepts_ui_twelve_month_filter(local_reference_database):
    """Regression: Home sends the supported 12 Months UI label in committed filters."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/intelligence/answer",
            json={
                "message": "What software tools does a Software Developer use?",
                "portal_type": "individual",
                "domain": "job",
                "time_range": "12m",
                "filters": {
                    "domain": "job",
                    "requested_time_window": "12 Months",
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["execution_status"] == "completed"
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)

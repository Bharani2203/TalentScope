"""Offline core-engine coverage for GitHub adoption and posting skill extraction."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics.job_skill_extraction import extract_posting_skills, match_job_text
from app.api.dependencies import get_current_user
from app.api.routes.core_intelligence import get_execution_orchestrator_service
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest, CoreIntelligenceAnswerResponse
from app.models.job import Job
from app.models.intent_planner import IntelligencePlanRequest
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "skill_intelligence.sqlite3"


class DisabledLLM:
    def is_available(self) -> bool:
        return False


class FakeReferenceStore:
    database_path = None

    def get_reference_skill_rows(self):
        return [
            {"name": "Data Visualization", "source": "esco", "taxonomy_id": "esco-skill-1", "aliases": '["data viz"]'},
            {"name": "Microsoft Excel", "source": "onet_software", "taxonomy_id": "2.B.3.a", "aliases": "[]"},
        ]


def test_job_skill_matcher_keeps_registry_and_taxonomy_identity_separate():
    matches = match_job_text(
        "Build APIs with Python and data visualization; use Microsoft Excel.",
        reference_store=FakeReferenceStore(),
    )
    by_name = {item["normalized_name"]: item for item in matches}

    assert by_name["Python"]["mapping_status"] == "canonical_registry"
    assert by_name["Data Visualization"]["mapping_status"] == "esco_exact"
    assert by_name["Data Visualization"]["entity_id"] == "skill:esco:esco-skill-1"
    assert by_name["Microsoft Excel"]["mapping_status"] == "onet_exact"
    assert by_name["Microsoft Excel"]["entity_id"] is None
    assert by_name["Python"]["supporting_text"]


def test_job_skill_matcher_marks_curated_excel_alias_and_keeps_provenance():
    # "Excel" is now in the canonical skill registry (added in Task 2 — skill registry expansion).
    # The canonical registry takes priority over the O*NET curated-alias path, so the
    # normalised name is "Excel" (registry canonical) rather than "Microsoft Excel" (O*NET label).
    # Taxonomy IDs come from O*NET cross-references; the registry does not store them.
    matches = match_job_text(
        "The analyst uses Excel to review tabular data.",
        reference_store=FakeReferenceStore(),
        _reference_data=[{
            "name": "Microsoft Excel", "source": "onet_software",
            "taxonomy_id": "2.E.3.a", "aliases": "[]",
        }],
    )
    assert matches[0]["normalized_name"] == "Excel"
    assert matches[0]["mapping_status"] == "canonical_registry"
    assert matches[0]["match_method"] == "canonical_registry_exact"
    assert matches[0]["taxonomy_id"] is None  # registry does not carry O*NET taxonomy IDs
    assert matches[0]["match_provenance"] == "canonical_registry"
    assert matches[0]["reference_source"] == "canonical_registry"


def test_job_skill_extraction_deduplicates_repeated_mentions_and_keeps_unmatched_candidates():
    skills = extract_posting_skills({
        "title": "Python Engineer",
        "description": "Python and Python services with FastAPI.",
        "skills_raw": ["Python", "FastAPI", "Mystery Platform"],
    }, reference_store=FakeReferenceStore())
    by_name = {item["normalized_name"]: item for item in skills}

    assert set(by_name) == {"Python", "FastAPI", "Mystery Platform"}
    assert len(by_name["Python"]["evidence"]) >= 2
    assert by_name["Mystery Platform"]["mapping_status"] == "unmatched"
    assert by_name["Mystery Platform"]["entity_id"] is None


def _local_reference_orchestrator(job_searcher=None):
    settings = Settings(
        _env_file=None,
        environment="local-test",
        firebase_project_id="demo-talentscope-phase13",
        skill_intelligence_db_path=str(DATABASE_PATH),
        skill_intelligence_read_backend="sqlite",
    )
    reference_store = ReferenceDataStore(DATABASE_PATH, read_only=True)
    market_store = MarketDataStore(DATABASE_PATH, read_only=True)
    entity_service = EntityRegistryService(settings=settings, db_path=DATABASE_PATH)
    capability_service = CapabilityRegistryService(
        entity_service=entity_service,
        reference_store=reference_store,
        db_path=DATABASE_PATH,
    )
    planner = IntentPlannerService(
        entity_service=entity_service,
        capability_service=capability_service,
    )
    service = ExecutionOrchestratorService(
        settings=settings,
        db_path=DATABASE_PATH,
        intent_planner=planner,
        capability_service=capability_service,
        entity_service=entity_service,
        reference_store=reference_store,
        market_store=market_store,
        conversation_store=ConversationStore(),
        llm_service=DisabledLLM(),
        workforce_store=object(),
        job_searcher=job_searcher,
    )
    return planner, service


def test_planner_to_answer_uses_quarterly_github_adoption_as_developer_activity():
    assert DATABASE_PATH.is_file(), "checked-out reference DB required for offline integration"
    planner, service = _local_reference_orchestrator()
    question = "How has GitHub adoption of Python changed over time?"
    plan = planner.create_plan(
        IntelligencePlanRequest(
            message=question,
            filters={"country": "IN"},
        )
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message=question,
        filters={"country": "IN"},
    ))

    assert plan.intent == "lookup_github_adoption"
    assert plan.primary_capability == "skill_technology_reference"
    assert response.execution_status == "completed"
    assert any(fact.fact_type == "developer_activity_snapshot" for fact in response.facts)
    assert any(fact.fact_type == "developer_activity_change" for fact in response.facts)
    assert all(fact.unit in {"unique developers per quarter", "unique developers"} for fact in response.facts if fact.fact_type.startswith("developer_activity"))
    assert "not hiring demand" in response.answer
    assert any("quarterly" in limitation.casefold() for limitation in response.limitations)

    unscoped = service.answer(CoreIntelligenceAnswerRequest(message=question))
    assert any(fact.metric_name == "github_adoption_geography_readiness" for fact in unscoped.facts)
    assert "Choose a country" in unscoped.answer

    natural_scope_question = "How has GitHub adoption of Python changed over time in India?"
    scoped_plan = planner.create_plan(IntelligencePlanRequest(message=natural_scope_question))
    scoped_response = service.answer(CoreIntelligenceAnswerRequest(message=natural_scope_question))
    assert scoped_plan.entities[0].raw_token == "Python"
    assert scoped_response.execution_status == "completed"
    assert any(fact.details.get("iso2_code") == "IN" for fact in scoped_response.facts)

    misuse_question = "Does GitHub adoption of Python prove hiring demand?"
    misuse_plan = planner.create_plan(IntelligencePlanRequest(message=misuse_question))
    misuse_response = service.answer(CoreIntelligenceAnswerRequest(message=misuse_question, filters={"country": "IN"}))
    assert misuse_plan.intent == "lookup_github_adoption"
    assert "not hiring demand" in misuse_response.answer
    assert not any(fact.source == "ref_github_language_adoption" and fact.unit == "postings" for fact in misuse_response.facts)


def test_planner_to_answer_resolves_essential_esco_occupation_skills():
    planner, service = _local_reference_orchestrator()
    question = "What are the essential skills for the Data Analyst occupation in ESCO?"
    plan = planner.create_plan(IntelligencePlanRequest(message=question))
    response = service.answer(CoreIntelligenceAnswerRequest(message=question))

    assert plan.intent == "crosswalk_occupation_software"
    assert plan.entities[0].canonical_entity is not None
    assert plan.entities[0].canonical_entity.source == "ref_esco_occupations"
    assert response.execution_status == "completed"
    assert response.facts
    assert {fact.metric_value for fact in response.facts if fact.fact_type == "occupation_skill_association"} == {"essential"}


@pytest.mark.parametrize("rows", [
    [
        Job(job_id="fixture-1", title="Python Engineer", company_name="Example", location="Chennai", source="adzuna", description="Python Python FastAPI; unknown QuxLang.", skills_raw=["Python", "FastAPI", "QuxLang"], posted_at="2026-10-01", fetched_at=datetime(2026, 10, 10, tzinfo=timezone.utc)),
        Job(job_id="fixture-2", title="API Engineer", company_name="Example Two", location="Chennai", source="jsearch", description="Build services with Python and PostgreSQL.", skills_raw=["PostgreSQL"], posted_at="2026-10-02", fetched_at=datetime(2026, 10, 10, tzinfo=timezone.utc)),
    ],
])
def test_planner_to_answer_extracts_skills_from_injected_job_sample(rows):
    planner, service = _local_reference_orchestrator(job_searcher=lambda **_kwargs: rows)
    question = "Which skills appear in the job postings stored in the platform?"
    plan = planner.create_plan(IntelligencePlanRequest(message=question))
    response = service.answer(CoreIntelligenceAnswerRequest(message=question, time_range="max_available"))

    assert plan.intent == "search_jobs"
    assert response.execution_status == "completed"
    base_fact = next(fact for fact in response.facts if fact.fact_type == "stored_job_postings")
    assert base_fact.metric_value == 2
    assert base_fact.data_origin == "test"
    assert base_fact.source == "injected_job_search"
    skills = {fact.entity_name: fact for fact in response.facts if fact.fact_type == "stored_posting_skill"}
    assert skills["Python"].metric_value == 2
    assert skills["Python"].denominator == 2
    assert "QuxLang" in skills
    assert skills["QuxLang"].details["mapping_status"] == "unmatched"
    assert "not evidence of real stored postings" in " ".join(response.limitations)
    assert all(ref["evidence_reference"] in {item.evidence_id for item in response.evidence} for fact in skills.values() for ref in fact.details["supporting_evidence"])


def test_empty_injected_job_search_is_insufficient_not_fabricated():
    _planner, service = _local_reference_orchestrator(job_searcher=lambda **_kwargs: [])
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Which skills appear in the job postings stored in the platform?",
        time_range="max_available",
    ))

    assert response.status == "insufficient_data"
    assert next(fact for fact in response.facts if fact.fact_type == "stored_job_postings").metric_value == 0
    assert not any(fact.fact_type == "stored_posting_skill" for fact in response.facts)


def test_answer_endpoint_preserves_response_contract_for_github_adoption():
    _planner, service = _local_reference_orchestrator()
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_service = app.dependency_overrides.get(get_execution_orchestrator_service)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="phase13-offline-test")
    app.dependency_overrides[get_execution_orchestrator_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/intelligence/answer",
            json={
                "message": "Does GitHub adoption of Python prove hiring demand?",
                "filters": {"country": "IN"},
            },
        )
    finally:
        if previous_user is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_user
        if previous_service is None:
            app.dependency_overrides.pop(get_execution_orchestrator_service, None)
        else:
            app.dependency_overrides[get_execution_orchestrator_service] = previous_service

    assert response.status_code == 200
    payload = CoreIntelligenceAnswerResponse.model_validate(response.json())
    assert payload.execution_status == "completed"
    assert "not hiring demand" in payload.answer
    assert all(fact.evidence_reference in {item.evidence_id for item in payload.evidence} for fact in payload.facts if fact.evidence_reference)

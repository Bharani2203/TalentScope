"""Read-only ESCO answer integration against the checked-out local reference DB."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.routes.core_intelligence import get_execution_orchestrator_service
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest, CoreIntelligenceAnswerResponse
from app.models.intent_planner import IntelligencePlanRequest
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "skill_intelligence.sqlite3"


class _DisabledLLM:
    def is_available(self) -> bool:
        return False


@pytest.fixture
def real_database_services(monkeypatch):
    if not DATABASE_PATH.is_file():
        pytest.fail(f"Required local ESCO reference database is missing: {DATABASE_PATH}")

    def forbid_firestore(*_args, **_kwargs):
        raise AssertionError("ESCO local integration must not initialize or access Firestore")

    monkeypatch.setattr("app.core.firebase.get_firestore_client", forbid_firestore)
    settings = Settings(
        _env_file=None,
        environment="local-test",
        firebase_project_id="demo-talentscope-local",
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
    orchestrator = ExecutionOrchestratorService(
        settings=settings,
        db_path=DATABASE_PATH,
        intent_planner=planner,
        capability_service=capability_service,
        entity_service=entity_service,
        reference_store=reference_store,
        market_store=market_store,
        conversation_store=ConversationStore(),
        llm_service=_DisabledLLM(),
        workforce_store=object(),
    )
    counts_before = reference_store.get_table_counts()
    yield planner, orchestrator, reference_store
    assert reference_store.get_table_counts() == counts_before


def _execute(planner, orchestrator, question, *, domain=None, capability_id=None):
    plan = planner.create_plan(IntelligencePlanRequest(
        message=question, domain=domain, capability_id=capability_id
    ))
    response = orchestrator.answer(CoreIntelligenceAnswerRequest(
        message=question, domain=domain, capability_id=capability_id
    ))
    return plan, response


def _post_answer(orchestrator, question, *, domain=None, capability_id=None, **request_fields):
    """Exercise the mounted HTTP route with test-only auth and service overrides."""
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_service = app.dependency_overrides.get(get_execution_orchestrator_service)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="offline-esco-test")
    app.dependency_overrides[get_execution_orchestrator_service] = lambda: orchestrator
    try:
        response = TestClient(app).post(
            "/api/v1/intelligence/answer",
            json={"message": question, "domain": domain, "capability_id": capability_id, **request_fields},
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
    CoreIntelligenceAnswerResponse.model_validate(response.json())
    return response


def test_selected_skill_reference_answers_exact_python_esco_question(real_database_services):
    planner, orchestrator, _store = real_database_services
    question = "What is the Python skill in the ESCO taxonomy?"

    plan, response = _execute(
        planner, orchestrator, question,
        domain="skill", capability_id="skill_technology_reference",
    )

    assert plan.intent == "lookup_skill_reference"
    assert plan.primary_capability == "skill_technology_reference"
    assert response.execution_status == "completed", response.model_dump()
    assert response.executed_primary_capability == "skill_technology_reference"
    fact = next(item for item in response.facts if item.source == "ref_esco_skills")
    assert fact.entity_name == "Python (computer programming)"
    assert fact.canonical_entity_id.startswith("skill:esco:")
    assert fact.provenance_id == fact.details["esco_uri"]
    assert fact.details["source_version"] == "v1.2.1"


def test_selected_skill_reference_returns_data_analyst_esco_relations(real_database_services):
    planner, orchestrator, _store = real_database_services
    question = "What skills are associated with the Data Analyst occupation in ESCO?"

    plan, response = _execute(
        planner, orchestrator, question,
        domain="skill", capability_id="skill_technology_reference",
    )
    assert plan.intent == "lookup_skill_reference"
    assert plan.primary_capability == "skill_technology_reference"
    assert response.execution_status == "completed", response.model_dump()
    assert response.executed_primary_capability == "skill_technology_reference"
    assert response.facts
    assert {fact.metric_value for fact in response.facts} <= {"essential", "optional"}
    assert all(fact.source == "ref_esco_occupation_skill_relations" for fact in response.facts)
    assert all(fact.details["source_version"] == "v1.2.1" for fact in response.facts)
    assert all(fact.details["occupation_uri"].startswith("http://data.europa.eu/esco/occupation/") for fact in response.facts)
    assert all(fact.details["skill_uri"].startswith("http://data.europa.eu/esco/skill/") for fact in response.facts)
    assert all(fact.canonical_entity_id == f"skill:esco:{fact.details['skill_uri']}" for fact in response.facts)
    assert all(fact.evidence_reference == response.evidence[0].evidence_id for fact in response.facts)


def test_real_esco_occupation_question_uses_imported_relationship_rows(real_database_services):
    planner, orchestrator, store = real_database_services
    before = store.get_table_counts()
    question = "What skills are associated with the Data Analyst occupation in ESCO?"

    plan, response = _execute(planner, orchestrator, question)

    assert plan.intent == "crosswalk_occupation_software"
    assert plan.primary_capability == "occupation_software_skills"
    assert plan.entities[0].canonical_entity.source == "ref_esco_occupations"
    assert response.execution_status == "completed"
    assert response.capabilities_used == ["occupation_software_skills"]
    assert len(response.facts) > 0
    assert all(fact.source == "ref_esco_occupation_skill_relations" for fact in response.facts)
    assert all(fact.details["source_version"] == "v1.2.1" for fact in response.facts)
    assert all(fact.details["occupation_uri"].startswith("http://data.europa.eu/esco/occupation/") for fact in response.facts)
    assert all(fact.evidence_reference == response.evidence[0].evidence_id for fact in response.facts)
    assert response.evidence[0].signal_type == "taxonomy_association"
    assert any("not proof" in item for item in response.limitations)
    assert any("not live employer hiring demand" in item for item in response.limitations)
    assert response.answer.startswith("Retrieved ")
    assert "up to 10 are returned" in response.answer
    assert "ESCO" in response.answer
    assert store.get_table_counts() == before


def test_real_esco_skill_question_preserves_uri_version_and_source(real_database_services):
    planner, orchestrator, _store = real_database_services
    question = "Find the ESCO skill Python (computer programming)."

    plan, response = _execute(planner, orchestrator, question)

    assert plan.intent == "lookup_skill_reference"
    assert plan.entities[0].canonical_entity.source == "ref_esco_skills"
    assert plan.entities[0].canonical_entity.entity_id.startswith("skill:esco:http://data.europa.eu/esco/skill/")
    assert response.execution_status == "completed"
    assert response.capabilities_used == ["skill_technology_reference"]
    fact = next(item for item in response.facts if item.source == "ref_esco_skills")
    assert fact.details["esco_uri"].startswith("http://data.europa.eu/esco/skill/")
    assert fact.details["source_version"] == "v1.2.1"
    assert fact.details["description"]
    assert any(item.provenance_id == fact.details["esco_uri"] for item in response.evidence)
    assert response.status == "ready"
    assert "ESCO v1.2.1" in response.answer
    assert fact.details["description"] in response.answer


def test_essential_esco_question_filters_optional_relationships(real_database_services):
    planner, orchestrator, _store = real_database_services
    question = "Show the essential skills associated with the Data Analyst occupation in ESCO."

    plan, response = _execute(planner, orchestrator, question)

    assert plan.intent == "crosswalk_occupation_software"
    assert response.execution_status == "completed"
    assert response.facts
    assert {fact.metric_value for fact in response.facts} == {"essential"}


def test_unknown_and_ambiguous_esco_terms_never_produce_associations(real_database_services):
    planner, orchestrator, _store = real_database_services
    unknown = "What skills are associated with a fictional occupation that does not exist in ESCO?"
    unknown_plan, unknown_response = _execute(planner, orchestrator, unknown)
    assert any(entity.resolution_status == "not_found" for entity in unknown_plan.entities)
    assert not unknown_response.facts
    assert not unknown_response.evidence
    assert unknown_response.execution_status == "requires_clarification"

    ambiguous = "Find the ESCO skill Spring."
    ambiguous_plan, ambiguous_response = _execute(planner, orchestrator, ambiguous)
    assert any(entity.resolution_status == "ambiguous" for entity in ambiguous_plan.entities)
    assert not ambiguous_response.facts
    assert not ambiguous_response.evidence
    assert ambiguous_response.execution_status == "requires_clarification"
    assert "ambiguous" in ambiguous_response.answer.casefold() or "which" in ambiguous_response.answer.casefold()


def test_current_python_demand_does_not_fall_back_to_esco_or_onet(real_database_services):
    planner, orchestrator, _store = real_database_services
    question = "Is Python currently in high hiring demand?"

    plan, response = _execute(planner, orchestrator, question)

    assert plan.intent == "retrieve_snapshot"
    assert plan.primary_capability == "market_snapshot"
    assert response.status == "insufficient_data"
    assert response.reason_codes == ["NO_STORED_MARKET_OBSERVATIONS"]
    assert not any(fact.history_type == "reference_taxonomy" for fact in response.facts)
    assert not any(item.signal_type == "taxonomy_association" for item in response.evidence)
    assert "No stored market observations" in response.answer
    assert "No demand level or trend can be inferred" in response.answer
    assert any("not live hiring evidence" in item for item in response.limitations)


def test_http_answer_returns_imported_esco_occupation_relationships(real_database_services):
    _planner, orchestrator, store = real_database_services
    before = store.get_table_counts()

    response = _post_answer(
        orchestrator,
        "What skills are associated with the Data Analyst occupation in ESCO?",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "completed", payload
    assert payload["facts"]
    assert all(fact["source"] == "ref_esco_occupation_skill_relations" for fact in payload["facts"])
    assert all(fact["details"]["source_version"] == "v1.2.1" for fact in payload["facts"])
    assert all(fact["details"]["occupation_uri"].startswith("http://data.europa.eu/esco/occupation/") for fact in payload["facts"])
    evidence_ids = {item["evidence_id"] for item in payload["evidence"]}
    assert evidence_ids
    assert all(fact["evidence_reference"] in evidence_ids for fact in payload["facts"])
    assert any(item["signal_type"] == "taxonomy_association" for item in payload["evidence"])
    assert any("not proof" in item for item in payload["limitations"])
    assert any("not live employer hiring demand" in item for item in payload["limitations"])
    assert store.get_table_counts() == before


def test_http_answer_returns_imported_esco_skill_and_static_limitations(real_database_services):
    _planner, orchestrator, _store = real_database_services

    response = _post_answer(orchestrator, "Find the ESCO skill Python (computer programming).")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "completed", payload
    fact = next(item for item in payload["facts"] if item["source"] == "ref_esco_skills")
    esco_uri = fact["details"]["esco_uri"]
    assert esco_uri.startswith("http://data.europa.eu/esco/skill/")
    assert fact["details"]["source_version"] == "v1.2.1"
    assert fact["details"]["description"]
    assert any(item["provenance_id"] == esco_uri for item in payload["evidence"])
    assert "ESCO v1.2.1" in payload["answer"]
    assert any("static" in item.casefold() or "taxonomy" in item.casefold() for item in payload["limitations"])


def test_http_selected_skill_reference_preserves_exact_question_and_esco_evidence(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "What is the Python skill in the ESCO taxonomy?"
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="skill_technology_reference"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_message"] == question
    assert payload["intent"] == "lookup_skill_reference"
    assert payload["planned_primary_capability"] == "skill_technology_reference"
    assert payload["executed_primary_capability"] == "skill_technology_reference"
    fact = next(item for item in payload["facts"] if item["source"] == "ref_esco_skills")
    assert fact["details"]["source_version"] == "v1.2.1"
    assert fact["details"]["esco_uri"] == fact["provenance_id"]
    evidence = next(item for item in payload["evidence"] if item["evidence_id"] == fact["evidence_reference"])
    assert evidence["provenance_id"] == fact["provenance_id"]


def test_http_selected_historical_feature_reads_local_github_series(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Show the historical GitHub developer-adoption signals for Python in India."
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="historical_signal_retrieval",
        location="India",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_message"] == question
    assert payload["intent"] == "retrieve_history"
    assert payload["planned_primary_capability"] == "historical_signal_retrieval"
    assert payload["executed_primary_capability"] == "historical_signal_retrieval"
    facts = [fact for fact in payload["facts"] if fact["fact_type"] == "historical_observation"]
    assert len(facts) >= 2
    assert {fact["source"] for fact in facts} == {"github_innovation_graph"}
    assert {fact["details"]["frequency"] for fact in facts} == {"quarterly"}
    assert {fact["details"]["geography"] for fact in facts} == {"IN"}
    assert {fact["unit"] for fact in facts} == {"unique developers per quarter"}
    assert {fact["series_id"] for fact in facts} == {item["series_id"] for item in payload["evidence"]}
    assert all(fact["history_type"] == "backfill" for fact in facts)
    assert "not hiring demand" in " ".join(payload["limitations"]).casefold()


def test_http_historical_stackexchange_question_does_not_substitute_github(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "What historical Stack Exchange interest data is available for Python?"
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="historical_signal_retrieval"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "historical_signal_retrieval"
    assert payload["execution_status"] == "insufficient_data"
    assert "NO_ELIGIBLE_HISTORICAL_SERIES" in payload["reason_codes"]
    assert not any(fact["source"] == "github_innovation_graph" for fact in payload["facts"])
    assert not any(item["source"].startswith("ref_github") for item in payload["evidence"])
    assert "Stack Exchange" in payload["answer"] or "Stack Exchange" in " ".join(payload["limitations"])


def test_http_selected_demand_trends_reports_no_local_market_history(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Is Python hiring demand increasing in the available market observations?"
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="trend_velocity_analysis"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "trend_velocity_analysis"
    assert payload["execution_status"] == "insufficient_data"
    assert not any(fact["fact_type"] == "trend_analysis" for fact in payload["facts"])
    assert not any(fact["history_type"] == "reference_taxonomy" for fact in payload["facts"])
    assert "No measured trend observations" in payload["answer"]


def test_http_selected_evidence_feature_cites_individual_esco_skill_record(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Show the evidence and sources supporting the Python skill reference in ESCO."
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="evidence_provenance_retrieval"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "evidence_provenance_retrieval"
    assert payload["executed_primary_capability"] == "evidence_provenance_retrieval"
    evidence = [item for item in payload["evidence"] if item["source"] == "ref_esco_skills"]
    assert len(evidence) == 1
    assert evidence[0]["history_type"] == "reference_taxonomy"
    assert evidence[0]["provenance_id"].startswith("http://data.europa.eu/esco/skill/")
    assert "ESCO" in evidence[0]["description"]


def test_http_selected_role_alignment_compares_request_skills_to_esco_data_analyst(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Compare Python, SQL and Excel with the Data Analyst occupation in ESCO."
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="skill_gap_role_fit",
        selected_skills=["Python", "SQL", "Excel"], target_role="Data Analyst",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "skill_gap_role_fit"
    assert payload["executed_primary_capability"] == "skill_gap_role_fit"
    gap = next(fact for fact in payload["facts"] if fact["fact_type"] == "personalized_skill_gap")
    assert gap["details"]["taxonomy"] == "esco"
    assert gap["details"]["reference_count"] > 0
    assert gap["details"]["unmatched_user"]
    assert "not employability" in gap["details"]["interpretation"]
    assert all(fact["evidence_reference"] in {item["evidence_id"] for item in payload["evidence"]}
               for fact in payload["facts"] if fact["fact_type"] == "action_recommendation")


def test_http_selected_action_recommendations_use_real_esco_when_onet_has_no_exact_match(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Based on the available Data Analyst skill-gap evidence, what should I practise next?"
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="action_recommendations",
        target_role="Data Analyst",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "action_recommendations"
    assert payload["execution_status"] == "completed", payload
    assert payload["executed_primary_capability"] == "action_recommendations"
    recommendations = [fact for fact in payload["facts"] if fact["fact_type"] == "action_recommendation"]
    assert recommendations
    assert all(fact["source"] == "ref_esco_occupation_skill_relations" for fact in recommendations)
    assert all(fact["details"]["taxonomy"] == "esco" for fact in recommendations)
    assert all(fact["details"]["is_personalized_gap"] is False for fact in recommendations)
    evidence = {item["evidence_id"]: item for item in payload["evidence"]}
    assert all(fact["evidence_reference"] in evidence for fact in recommendations)
    assert all(evidence[fact["evidence_reference"]]["provenance_id"] == fact["provenance_id"]
               for fact in recommendations)
    assert "not personalized skill gaps" in " ".join(payload["limitations"])
    assert not any("course" in fact["details"].get("next_action", "").casefold()
                   for fact in recommendations)


def test_esco_action_recommendations_compare_supplied_skills_against_real_relationships(real_database_services):
    _planner, orchestrator, store = real_database_services
    occupation = store.get_esco_occupations(query="Data Analyst", limit=1)[0]
    relationship = store.get_esco_occupation_skills(occupation["concept_uri"], limit=1)[0]
    supplied_label = relationship["preferred_label"] or relationship["skill_label"]
    question = "Based on my Data Analyst skill gap in ESCO, what should I practise next?"
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="action_recommendations",
        target_role="Data Analyst", selected_skills=[supplied_label],
    )

    assert response.status_code == 200
    payload = response.json()
    recommendations = [fact for fact in payload["facts"] if fact["fact_type"] == "action_recommendation"]
    assert recommendations
    assert all(fact["details"]["is_personalized_gap"] is True for fact in recommendations)
    assert all(fact["details"]["recommendation_basis"] == "unmatched_esco_reference_relationships_for_supplied_skills"
               for fact in recommendations)
    assert all(fact["evidence_reference"] in {item["evidence_id"] for item in payload["evidence"]}
               for fact in recommendations)


def test_esco_action_recommendations_do_not_turn_unresolved_skills_into_a_personal_gap(real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator,
        "What should I practise next for Data Analyst in ESCO?",
        domain="skill",
        capability_id="action_recommendations",
        target_role="Data Analyst",
        selected_skills=["made-up skill label"],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] in {"insufficient_data", "requires_clarification"}
    assert not any(fact["fact_type"] == "action_recommendation" for fact in payload["facts"])
    readiness = next(fact for fact in payload["facts"] if fact["fact_type"] == "learning_recommendation_readiness")
    assert readiness["details"]["reason_code"] == "UNRESOLVED_USER_SKILL"


@pytest.mark.parametrize("question", [
    "Give me a market snapshot for Python in India.",
    "What hiring signals are available for Python in India?",
])
def test_http_market_snapshot_and_hiring_signals_do_not_fall_back_to_reference_data(question, real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="market_snapshot",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "market_snapshot"
    assert payload["intent"] == "retrieve_snapshot"
    assert payload["execution_status"] == "insufficient_data"
    assert payload["reason_codes"] == ["NO_STORED_MARKET_OBSERVATIONS"]
    assert payload["applied_filters"].get("location") == "India"
    assert not any(fact["fact_type"] == "market_snapshot" for fact in payload["facts"])
    assert not any(item["source"].startswith("ref_github") for item in payload["evidence"])
    assert "not total universe" in " ".join(payload["limitations"])


def test_http_market_trend_question_keeps_hiring_source_and_readiness(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Is Python hiring demand increasing in India based on the available observations?"
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="trend_velocity_analysis",
        location="India",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "trend_velocity_analysis"
    assert payload["execution_status"] == "insufficient_data"
    assert not any(fact["fact_type"] == "trend_analysis" for fact in payload["facts"])
    assert "No measured trend observations" in payload["answer"]
    assert not any(item["source"].startswith("ref_github") for item in payload["evidence"])


def test_http_job_posting_search_uses_country_from_question_and_local_store_only(real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator,
        "What hiring signals are available for Python in India?",
        domain="job", capability_id="job_posting_search",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "job_posting_search"
    # Store retrieval completed successfully; data readiness remains insufficient.
    assert payload["execution_status"] == "completed"
    assert payload["status"] == "insufficient_data"
    assert payload["reason_codes"] == ["NO_STORED_JOB_POSTINGS"]
    assert payload["applied_filters"].get("location") == "India"
    assert payload["applied_filters"].get("country") == "IN"
    posting_fact = next(fact for fact in payload["facts"] if fact["fact_type"] == "stored_job_postings")
    assert posting_fact["metric_value"] == 0
    assert not payload["evidence"]
    assert "O*NET taxonomy baseline" not in payload["answer"]


def test_http_market_domain_developer_adoption_uses_github_family_not_hiring(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Show developer adoption signals for Python in India."
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="historical_signal_retrieval",
        location="India",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "historical_signal_retrieval"
    assert payload["executed_primary_capability"] == "historical_signal_retrieval"
    facts = [fact for fact in payload["facts"] if fact["fact_type"] == "historical_observation"]
    assert facts
    assert {fact["source"] for fact in facts} == {"github_innovation_graph"}
    assert {fact["details"]["signal_type"] for fact in facts} == {"adoption"}
    assert all("not hiring demand" in item["description"] for item in payload["evidence"])


def test_http_market_evidence_question_without_prior_summary_does_not_invent_citations(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "What evidence supports the Python market summary?"
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="evidence_provenance_retrieval",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["planned_primary_capability"] == "evidence_provenance_retrieval"
    assert payload["execution_status"] == "insufficient_data"
    assert payload["reason_codes"] == ["NO_VERIFIED_EVIDENCE"]
    assert payload["evidence"] == []


def test_http_market_comparison_without_observations_does_not_mix_reference_or_signal_families(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "Compare the available market signals for Python, keeping each source separate."
    response = _post_answer(orchestrator, question, domain="market", time_range="max")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] in {"insufficient_data", "requires_clarification"}
    assert not any(fact["fact_type"] in {"market_snapshot", "trend_analysis"} for fact in payload["facts"])
    assert not any(item["source"].startswith(("ref_onet", "ref_esco")) for item in payload["evidence"])


@pytest.mark.parametrize("question,expected_resolution", [
    ("Show the Python market snapshot", "resolved"),
    ("Show the made-up-language market snapshot", "not_found"),
    ("Show the Spring market snapshot", "ambiguous"),
])
def test_http_market_snapshot_entity_resolution_never_fabricates(question, expected_resolution, real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator, question, domain="market", capability_id="market_snapshot",
    )

    assert response.status_code == 200
    payload = response.json()
    if expected_resolution == "resolved":
        assert payload["planned_primary_capability"] == "market_snapshot"
    else:
        assert payload["execution_status"] == "requires_clarification"
        assert payload["facts"] == []
        assert payload["evidence"] == []
        if payload["selected_entities"]:
            assert any(item["resolution_status"] == expected_resolution for item in payload["selected_entities"])
        else:
            assert "which" in payload["answer"].casefold() or "which" in " ".join(payload["follow_up_questions"]).casefold()


def test_http_selected_skill_reference_unknown_skill_returns_clarification(real_database_services):
    _planner, orchestrator, _store = real_database_services
    question = "What is a made-up-language skill in the ESCO taxonomy?"
    response = _post_answer(
        orchestrator, question, domain="skill", capability_id="skill_technology_reference"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "requires_clarification"
    assert payload["facts"] == []
    assert payload["evidence"] == []
    assert any(item["resolution_status"] == "not_found" for item in payload["selected_entities"])


def test_http_selected_skill_reference_ambiguous_skill_requests_choice(real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator, "Find the ESCO skill Spring.",
        domain="skill", capability_id="skill_technology_reference",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "requires_clarification"
    assert payload["facts"] == []
    assert payload["evidence"] == []
    assert any(item["resolution_status"] == "ambiguous" for item in payload["selected_entities"])


def test_http_selected_skill_reference_renders_occupation_relations_in_response_contract(real_database_services):
    _planner, orchestrator, _store = real_database_services
    response = _post_answer(
        orchestrator,
        "What skills are associated with the Data Analyst occupation in ESCO?",
        domain="skill", capability_id="skill_technology_reference",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "completed"
    assert payload["executed_primary_capability"] == "skill_technology_reference"
    assert payload["facts"]
    assert all(item["source"] == "ref_esco_occupation_skill_relations" for item in payload["facts"])
    assert all(item["evidence_reference"] in {e["evidence_id"] for e in payload["evidence"]} for item in payload["facts"])


def test_http_demand_question_does_not_use_esco_as_live_hiring_evidence(real_database_services):
    _planner, orchestrator, store = real_database_services
    market_store = MarketDataStore(DATABASE_PATH, read_only=True)
    assert market_store.get_observations() == []
    counts_before = store.get_table_counts()

    response = _post_answer(orchestrator, "Is Python currently in high hiring demand?")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "insufficient_data"
    assert payload["reason_codes"] == ["NO_STORED_MARKET_OBSERVATIONS"]
    assert not any(fact["history_type"] == "reference_taxonomy" for fact in payload["facts"])
    assert not any(item["signal_type"] == "taxonomy_association" for item in payload["evidence"])
    assert "No demand level or trend can be inferred" in payload["answer"]
    assert any("not live hiring evidence" in item for item in payload["limitations"])
    assert store.get_table_counts() == counts_before
    assert market_store.get_observations() == []


@pytest.mark.parametrize(
    "question,expected_resolution",
    [
        ("What skills are associated with a fictional occupation that does not exist in ESCO?", "not_found"),
        ("Find the ESCO skill Spring.", "ambiguous"),
        ("What is a made-up-language skill in the ESCO taxonomy?", "not_found"),
    ],
)
def test_http_unknown_or_ambiguous_esco_question_does_not_fabricate(question, expected_resolution, real_database_services):
    _planner, orchestrator, _store = real_database_services

    response = _post_answer(orchestrator, question)

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "requires_clarification"
    assert any(item["resolution_status"] == expected_resolution for item in payload["selected_entities"])
    assert payload["facts"] == []
    assert payload["evidence"] == []

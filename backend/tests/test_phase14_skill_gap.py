"""Offline deterministic skill gap engine and pipeline tests."""

from pathlib import Path

import pytest

from app.analytics.skill_gap import calculate_skill_gap
from app.analytics.skill_resolution import resolve_user_skill
from app.analytics.learning_roadmap import build_learning_roadmap
from app.core.config import Settings
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "skill_intelligence.sqlite3"


class DisabledLLM:
    def is_available(self):
        return False


def _service():
    settings = Settings(
        _env_file=None, environment="local-test", firebase_project_id="demo-phase14",
        skill_intelligence_db_path=str(DATABASE_PATH), skill_intelligence_read_backend="sqlite",
    )
    reference = ReferenceDataStore(DATABASE_PATH, read_only=True)
    entity = EntityRegistryService(settings=settings, db_path=DATABASE_PATH)
    capability = CapabilityRegistryService(entity_service=entity, reference_store=reference, db_path=DATABASE_PATH)
    planner = IntentPlannerService(entity_service=entity, capability_service=capability)
    service = ExecutionOrchestratorService(
        settings=settings, db_path=DATABASE_PATH, intent_planner=planner,
        capability_service=capability, entity_service=entity, reference_store=reference,
        market_store=MarketDataStore(DATABASE_PATH, read_only=True),
        conversation_store=ConversationStore(), llm_service=DisabledLLM(),
        workforce_store=object(),
    )
    return planner, service


def test_skill_gap_matches_alias_and_reports_reference_denominator_and_unmatched_user():
    result = calculate_skill_gap(
        taxonomy="esco",
        occupation={"taxonomy_id": "occ-1"},
        reference_skills=[
            {"skill_uri": "skill-1", "preferred_label": "Data Visualization", "alt_labels": '["Data Viz"]', "relation_type": "essential"},
            {"skill_uri": "skill-2", "preferred_label": "Spreadsheet software", "alt_labels": "[]", "relation_type": "optional"},
        ],
        user_skills=["Data Viz", "Data Visualization", "MysteryLang"],
    )
    assert len(result["matched"]) == 2  # original inputs are preserved
    assert result["matched_reference_count"] == 1  # aliases count once in coverage
    assert result["matched"][0]["taxonomy_id"] == "skill-1"
    assert result["unmatched_user"][0]["original_text"] == "MysteryLang"
    assert result["unmatched_user"][0]["status"] == "unmatched"
    assert result["coverage"] == 0.5
    assert result["reference_count"] == 2
    assert [gap["classification"] for gap in result["missing"]] == ["optional"]


def test_skill_gap_all_reference_skills_matched_has_full_coverage():
    result = calculate_skill_gap(
        taxonomy="onet", occupation={"taxonomy_id": "soc:1"},
        reference_skills=[
            {"element_id": "1.A.1", "element_name": "Active Listening"},
            {"element_id": "1.A.2", "element_name": "Critical Thinking"},
        ],
        user_skills=["active-listening", "Critical Thinking", "Critical Thinking"],
    )
    assert result["reference_count"] == 2
    assert len(result["matched"]) == 2
    assert result["missing"] == []
    assert result["coverage"] == 1.0
    assert {item["taxonomy_id"] for item in result["matched"]} == {"1.A.1", "1.A.2"}


def test_skill_gap_keeps_ambiguous_labels_unresolved_and_taxonomy_ids_separate():
    result = calculate_skill_gap(
        taxonomy="esco", occupation={}, user_skills=["Shared"],
        reference_skills=[
            {"skill_uri": "esco:1", "preferred_label": "Shared", "relation_type": "essential"},
            {"skill_uri": "esco:2", "preferred_label": "Shared", "relation_type": "optional"},
        ],
    )
    assert result["unresolved_user"][0]["original_text"] == "Shared"
    assert result["unresolved_user"][0]["status"] == "ambiguous"
    assert result["coverage"] == 0
    assert {gap["taxonomy_id"] for gap in result["missing"]} == {"esco:1", "esco:2"}


def test_skill_resolver_reports_exact_official_curated_ambiguous_and_unmatched_methods():
    references = [
        {"skill_uri": "esco:excel", "preferred_label": "use spreadsheets software", "alt_labels": '["spreadsheet software"]', "source": "ref_esco_skills"},
        {"skill_uri": "esco:analytics", "preferred_label": "Data Analytics", "alt_labels": "[]", "source": "ref_esco_skills"},
    ]
    exact = resolve_user_skill("USE SPREADSHEETS SOFTWARE", references, "esco")
    official = resolve_user_skill("spreadsheet software", references, "esco")
    curated = resolve_user_skill("Excel", references, "esco")
    registry_alias = resolve_user_skill("data analysis", references, "esco")
    unmatched = resolve_user_skill("UnknownTool", references, "esco")
    assert exact["status"] == "exact_match"
    assert exact["taxonomy_id"] == "esco:excel"
    assert official["status"] == "official_alias_match"
    assert official["provenance"] == "taxonomy_import"
    assert curated["status"] == "curated_alias_match"
    assert curated["provenance"] == "phase15_curated_alias_registry"
    assert "lower-confidence" in curated["rationale"]
    assert registry_alias["status"] == "official_alias_match"
    assert registry_alias["provenance"] == "canonical_skill_registry"
    assert unmatched["status"] == "unmatched"


def test_curated_excel_alias_is_scoped_and_taxonomy_identities_stay_distinct():
    esco = resolve_user_skill("Excel", [{
        "skill_uri": "http://data.europa.eu/esco/skill/1",
        "preferred_label": "use spreadsheets software", "source": "ref_esco_occupation_skill_relations",
    }], "esco")
    onet = resolve_user_skill("Excel", [{
        "element_id": "2.E.4.i", "workplace_example": "Microsoft Excel", "source": "ref_onet_software_skills",
    }], "onet")
    assert esco["taxonomy_id"].startswith("http://data.europa.eu/esco/")
    assert onet["taxonomy_id"] == "2.E.4.i"
    assert esco["taxonomy_id"] != onet["taxonomy_id"]


@pytest.mark.parametrize("raw, taxonomy, reference, expected_status", [
    ("Python", "onet", {"element_id": "2.E.7.e", "workplace_example": "Python"}, "exact_match"),
    ("SQL", "esco", {"skill_uri": "esco:sql", "preferred_label": "SQL"}, "exact_match"),
    ("Microsoft Excel", "onet", {"element_id": "2.E.4.i", "workplace_example": "Microsoft Excel"}, "exact_match"),
    ("Excel", "esco", {"skill_uri": "esco:spreadsheet", "preferred_label": "use spreadsheets software"}, "curated_alias_match"),
    ("JavaScript", "esco", {"skill_uri": "esco:js", "preferred_label": "JavaScript"}, "exact_match"),
    ("TypeScript", "esco", {"skill_uri": "esco:ts", "preferred_label": "TypeScript"}, "exact_match"),
    ("React", "onet", {"element_id": "2.E.7.h", "workplace_example": "React"}, "exact_match"),
    ("FastAPI", "onet", {"element_id": "fastapi", "workplace_example": "Unrelated tool"}, "unmatched"),
    ("Spring Boot", "onet", {"element_id": "2.E.10.a", "workplace_example": "Spring Boot"}, "exact_match"),
    ("Data analysis", "esco", {"skill_uri": "esco:data-analytics", "preferred_label": "Data Analytics"}, "official_alias_match"),
    ("Machine learning", "esco", {"skill_uri": "esco:ml", "preferred_label": "machine learning"}, "exact_match"),
])
def test_skill_resolver_handles_requested_terms_without_cross_taxonomy_guessing(raw, taxonomy, reference, expected_status):
    reference["source"] = f"ref_{taxonomy}_fixture"
    result = resolve_user_skill(raw, [reference], taxonomy)
    assert result["status"] == expected_status
    if expected_status != "unmatched":
        assert result["original_text"] == raw
        assert result["taxonomy_id"]
        assert result["taxonomy"] == taxonomy
        assert result["source"]
        assert result["match_method"]
        assert result["confidence"] is not None


@pytest.mark.skipif(not DATABASE_PATH.is_file(), reason="optional local reference database")
def test_official_esco_alternate_label_is_resolved_from_imported_record():
    store = ReferenceDataStore(DATABASE_PATH, read_only=True)
    occupation = next(
        row for row in store.get_esco_occupations(query="Data Analyst", limit=10)
        if row["preferred_label"].casefold() == "data analyst"
    )
    rows = store.get_esco_occupation_skills(occupation["concept_uri"], limit=500)
    alias_row = next(row for row in rows if row.get("alt_labels") not in (None, "", "[]", []))
    import json
    aliases = json.loads(alias_row["alt_labels"]) if isinstance(alias_row["alt_labels"], str) else alias_row["alt_labels"]
    result = resolve_user_skill(aliases[0], [alias_row], "esco")
    assert result["status"] == "official_alias_match"
    assert result["taxonomy_id"] == alias_row["skill_uri"]
    assert result["provenance"] == "taxonomy_import"


@pytest.mark.skipif(not DATABASE_PATH.is_file(), reason="optional local reference database")
def test_python_sql_excel_regression_uses_actual_esco_occupation_relationships():
    store = ReferenceDataStore(DATABASE_PATH, read_only=True)
    occupations = store.get_esco_occupations(query="Data Analyst", limit=10)
    role = next(row for row in occupations if row["preferred_label"].casefold() == "data analyst")
    references = [
        {**row, "source": "ref_esco_occupation_skill_relations"}
        for row in store.get_esco_occupation_skills(role["concept_uri"], limit=500)
    ]
    result = calculate_skill_gap(
        taxonomy="esco", occupation={"label": role["preferred_label"], "taxonomy_id": role["concept_uri"]},
        reference_skills=references, user_skills=["Python", "SQL", "Excel", "Excel"],
    )
    matched_inputs = {item["original_text"]: item for item in result["matched"]}
    assert matched_inputs["Excel"]["status"] == "curated_alias_match"
    assert matched_inputs["Excel"]["taxonomy_id"] == next(
        row["skill_uri"] for row in references if row["preferred_label"] == "use spreadsheets software"
    )
    assert {item["original_text"] for item in result["unmatched_user"]} == {"Python", "SQL"}
    assert result["matched_reference_count"] == 1
    assert result["coverage"] == 1 / result["reference_count"]


def test_roadmap_uses_source_priority_and_truthful_self_check_state():
    roadmap = build_learning_roadmap({
        "occupation": {"label": "Data Analyst", "taxonomy_id": "esco:occ", "taxonomy": "esco"},
        "missing": [
            {"label": "Optional item", "taxonomy_id": "esco:2", "taxonomy": "esco", "classification": "optional", "source_record_id": "esco:2", "priority_rationale": "Optional source relation."},
            {"label": "SQL", "taxonomy_id": "esco:1", "taxonomy": "esco", "classification": "essential", "source_record_id": "esco:1", "priority_rationale": "Essential source relation."},
        ],
    })
    assert [step["target_skill"] for step in roadmap["steps"]] == ["SQL", "Optional item"]
    assert "queries" in roadmap["steps"][0]["suggested_task"]
    assert roadmap["steps"][0]["tangible_outcome"]
    assert roadmap["steps"][0]["self_check_criterion"]
    assert roadmap["steps"][0]["assessment_status"] == "not_assessed"
    assert roadmap["steps"][0]["proficiency_verified"] is False
    assert "not verified courses" in roadmap["limitations"][0]


@pytest.mark.skipif(not DATABASE_PATH.is_file(), reason="optional local reference database")
@pytest.mark.parametrize("message", [
    "I know Python, SQL and Excel. What am I missing for Data Analyst in ESCO?",
    "I know Python, SQL and Excel. Create a learning roadmap for my missing Data Analyst skills in ESCO.",
    "Compare my current skills with the essential skills for Software Developers in ESCO.",
])
def test_skill_gap_runs_through_planner_and_answer_pipeline(message):
    planner, service = _service()
    from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
    from app.models.intent_planner import IntelligencePlanRequest

    plan = planner.create_plan(IntelligencePlanRequest(message=message))
    response = service.answer(CoreIntelligenceAnswerRequest(message=message))
    assert plan.intent == "analyze_skill_gap"
    if "I know" in message:
        assert response.execution_status == "completed"
        fact = next(fact for fact in response.facts if fact.fact_type == "personalized_skill_gap")
        assert fact.details["taxonomy"] == "esco"
        assert fact.details["reference_count"] == fact.denominator
        assert fact.details["coverage_numerator"] == 1
        excel_match = next(item for item in fact.details["matched"] if item["original_text"] == "Excel")
        assert excel_match["status"] == "curated_alias_match"
        assert excel_match["provenance"] == "phase15_curated_alias_registry"
        assert {item["original_text"] for item in fact.details["unmatched_user"]} == {"Python", "SQL"}
        assert "not employability" in fact.details["interpretation"]
        assert fact.details["proficiency_note"].startswith("User skill labels are self-reported")
        assert all(fact.evidence_reference in {item.evidence_id for item in response.evidence} for fact in response.facts if fact.fact_type == "action_recommendation")
        assert any(fact.fact_type == "learning_roadmap_step" for fact in response.facts)


def test_skill_gap_missing_inputs_returns_clarification_not_a_gap():
    _planner, service = _service()
    from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest

    response = service.answer(CoreIntelligenceAnswerRequest(message="What am I missing for Data Analyst in ESCO?"))
    assert not any(fact.fact_type == "personalized_skill_gap" for fact in response.facts)
    assert response.execution_status == "requires_clarification"
    assert "skills" in response.answer.casefold()


def test_skill_gap_missing_target_occupation_requests_clarification():
    _planner, service = _service()
    from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest

    response = service.answer(CoreIntelligenceAnswerRequest(
        message="What skills am I missing?", selected_skills=["Python", "SQL"]
    ))
    assert response.execution_status == "requires_clarification"
    assert "occupation" in response.answer.casefold()
    assert not any(fact.fact_type == "personalized_skill_gap" for fact in response.facts)


def test_skill_gap_answer_endpoint_preserves_evidence_and_limitations():
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_current_user
    from app.api.routes.core_intelligence import get_execution_orchestrator_service
    from app.main import app
    from app.models.auth import AuthenticatedUser
    from app.models.execution_orchestrator import CoreIntelligenceAnswerResponse

    _planner, service = _service()
    service._apply_authenticated_learning_profile = lambda request, _user, *, portal_type: request.model_copy(update={
        "context_override": {**request.context_override, "_learning_profile_state": "unavailable"}
    })
    previous_user = app.dependency_overrides.get(get_current_user)
    previous_service = app.dependency_overrides.get(get_execution_orchestrator_service)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="phase14-offline-test")
    app.dependency_overrides[get_execution_orchestrator_service] = lambda: service
    try:
        response = TestClient(app).post("/api/v1/intelligence/answer", json={
            "message": "I know Python, SQL and Excel. What am I missing for Data Analyst in ESCO?"
        })
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
    gap = next(fact for fact in payload.facts if fact.fact_type == "personalized_skill_gap")
    assert payload.execution_status == "completed"
    assert gap.details["taxonomy"] == "esco"
    assert gap.details["coverage_formula"]
    assert gap.details["coverage_numerator"] == 1
    assert "self-reported" in " ".join(payload.limitations)
    assert gap.evidence_reference in {item.evidence_id for item in payload.evidence}

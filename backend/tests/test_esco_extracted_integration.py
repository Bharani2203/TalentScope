"""Offline contract tests for importing and querying an extracted ESCO fixture."""

import csv
from pathlib import Path

from app.models.entity_registry import EntityResolutionRequest
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse, ResolvedEntityItem
from app.core.config import Settings
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.reference_data_service import ingest_esco_extracted_directory
from app.storage.reference_store import ReferenceDataStore


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def _fixture(root: Path) -> Path:
    directory = root / "ESCO dataset - v1.2.1 - classification - en - csv"
    directory.mkdir()
    _write_csv(directory / "skills_en.csv", ["conceptUri", "preferredLabel", "status", "skillType", "reuseLevel", "altLabels", "description", "modifiedDate"], [
        ["http://data.europa.eu/esco/skill/skill-a", "Data analysis", "released", "skill/competence", "cross-sector", "data analytics", "Analyze data", "2024-01-01"],
        ["http://data.europa.eu/esco/skill/skill-a", "Data analysis", "released", "skill/competence", "cross-sector", "analytics", "Analyze data", "2024-02-01"],
        ["http://data.europa.eu/esco/skill/draft", "Draft", "draft", "skill/competence", "cross-sector", "", "", "2024-01-01"],
    ])
    _write_csv(directory / "occupations_en.csv", ["conceptUri", "preferredLabel", "status", "altLabels", "description", "modifiedDate", "code", "iscoGroup"], [
        ["http://data.europa.eu/esco/occupation/occupation-a", "Data analyst", "released", "data analytics specialist", "Analyzes data", "2024-01-01", "2511.1", "25"],
    ])
    _write_csv(directory / "occupationSkillRelations_en.csv", ["occupationUri", "occupationLabel", "relationType", "skillType", "skillUri", "skillLabel"], [
        ["http://data.europa.eu/esco/occupation/occupation-a", "Data analyst", "essential", "skill/competence", "http://data.europa.eu/esco/skill/skill-a", "Data analysis"],
        ["http://data.europa.eu/esco/occupation/missing", "Unknown", "essential", "skill/competence", "http://data.europa.eu/esco/skill/skill-a", "Data analysis"],
    ])
    return directory


def test_extracted_esco_import_is_validated_idempotent_and_queryable(tmp_path):
    source = _fixture(tmp_path)
    store = ReferenceDataStore(tmp_path / "reference.sqlite3")

    result = ingest_esco_extracted_directory(source, store)
    repeated = ingest_esco_extracted_directory(source, store)

    assert result["esco_skill_rows_valid"] == 1
    assert result["esco_skill_rows_rejected"] == 1
    assert result["esco_skill_rows_duplicate"] == 1
    assert result["esco_occupation_rows_valid"] == 1
    assert result["esco_relation_rows_valid"] == 1
    assert result["esco_relation_rows_rejected"] == 1
    assert repeated["esco_skills"] == repeated["esco_occupations"] == repeated["esco_occupation_skill_relations"] == 0
    assert store.get_table_counts()["ref_esco_skills"] == 1
    assert store.get_esco_occupation_skills("http://data.europa.eu/esco/occupation/occupation-a")[0]["preferred_label"] == "Data analysis"

    safe_settings = Settings(_env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local", skill_intelligence_db_path=str(store.database_path))
    entity_service = EntityRegistryService(settings=safe_settings, db_path=store.database_path)
    occupation = entity_service.resolve(EntityResolutionRequest(name="data analyst", entity_type="occupation"))
    assert occupation.status == "resolved"
    assert occupation.entity.entity_id == "occupation:esco:http://data.europa.eu/esco/occupation/occupation-a"
    alias = entity_service.resolve(EntityResolutionRequest(name="data analytics specialist", entity_type="occupation"))
    assert alias.status == "resolved"
    skill = entity_service.resolve(EntityResolutionRequest(name="skill:esco:http://data.europa.eu/esco/skill/skill-a", entity_type="skill"))
    assert skill.status == "resolved"
    assert skill.entity.source == "ref_esco_skills"


def test_esco_occupation_skill_handler_returns_taxonomy_evidence(tmp_path):
    source = _fixture(tmp_path)
    db_path = tmp_path / "reference.sqlite3"
    store = ReferenceDataStore(db_path)
    ingest_esco_extracted_directory(source, store)
    safe_settings = Settings(_env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local", skill_intelligence_db_path=str(db_path))
    entity = EntityRegistryService(settings=safe_settings, db_path=db_path).resolve(
        EntityResolutionRequest(name="data analyst", entity_type="occupation")
    ).entity
    service = ExecutionOrchestratorService(settings=safe_settings, db_path=db_path, observation_store=object(), workforce_store=object())
    natural_language_plan = service.intent_planner.create_plan(IntelligencePlanRequest(
        message="Which skills are associated with data analyst in the ESCO taxonomy?",
        target_role="data analyst",
    ))
    assert natural_language_plan.intent == "crosswalk_occupation_software"
    assert natural_language_plan.entities[0].canonical_entity.source == "ref_esco_occupations"
    plan = IntelligencePlanResponse(
        request_id="fixture", user_message="skills for data analyst", portal_type="individual",
        intent="crosswalk_occupation_software", intent_confidence=1.0, intent_explanation="test",
        entities=[ResolvedEntityItem(raw_token="data analyst", resolution_status="resolved", canonical_entity=entity)],
        plan_status="ready_to_execute",
    )
    request = CoreIntelligenceAnswerRequest(message="Which skills are associated with data analyst?")

    facts, evidence, limitations = service._handle_occupation_software_skills(request, plan)

    assert [fact.fact_type for fact in facts] == ["occupation_skill_association"]
    assert facts[0].metric_value == "essential"
    assert facts[0].source == "ref_esco_occupation_skill_relations"
    assert evidence[0].signal_type == "taxonomy_association"
    assert any("not proof" in limitation for limitation in limitations)

    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Which skills are associated with data analyst in the ESCO taxonomy?",
        target_role="data analyst",
    ))
    assert response.execution_status == "completed", (response.intent, response.plan_status, response.reason_codes, response.limitations)
    assert response.intent == "crosswalk_occupation_software"
    assert any(fact.fact_type == "occupation_skill_association" for fact in response.facts)
    assert "ESCO" in response.answer


def test_extracted_import_rejects_wrong_version_directory(tmp_path):
    source = _fixture(tmp_path)
    store = ReferenceDataStore(tmp_path / "reference.sqlite3")
    wrong_name = tmp_path / "ESCO dataset - v2 - classification - en - csv"
    source.rename(wrong_name)

    try:
        ingest_esco_extracted_directory(wrong_name, store)
    except ValueError as exc:
        assert "release version" in str(exc)
    else:
        raise AssertionError("wrong release directory should be rejected")

    assert store.get_table_counts()["ref_esco_skills"] == 0


def test_esco_only_cli_records_import_provenance_without_loading_env(tmp_path, monkeypatch):
    source = _fixture(tmp_path)
    db_path = tmp_path / "reference.sqlite3"
    monkeypatch.setattr("sys.argv", [
        "ingest_reference_data", "--ref-dir", str(tmp_path), "--db-path", str(db_path), "--esco-only",
    ])
    from app.scripts.ingest_reference_data import main

    main()

    with ReferenceDataStore(db_path)._connect() as connection:
        rows = connection.execute(
            "SELECT dataset, source_file, rows_read, rows_valid FROM ref_ingestion_log ORDER BY dataset"
        ).fetchall()
    assert [row["dataset"] for row in rows] == [
        "esco_occupation_skill_relations", "esco_occupations", "esco_skills",
    ]
    assert all("ESCO dataset - v1.2.1" in row["source_file"] for row in rows)

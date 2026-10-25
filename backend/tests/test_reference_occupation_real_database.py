"""Read-only integration coverage for occupation answers against the checked-in database."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.occupation_names import (
    normalize_occupation_name,
    occupation_label_matches,
)
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine
from app.intelligence_v2.skill_mapping import V2SkillMapper
from app.storage.reference_store import ReferenceDataStore


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "skill_intelligence.sqlite3"
EXPECTED_STATUS = {
    "Data Engineer": {
        "description": "ready",
        "requirements": "ready",
        "preparation": "ready",
    },
    "Data Analyst": {
        "description": "ready",
        "requirements": "ready",
        "preparation": "ready",
    },
    "Backend Developer": {
        "description": "insufficient_data",
        "requirements": "insufficient_data",
        "preparation": "insufficient_data",
    },
    "Web Developer": {
        "description": "ready",
        "requirements": "ready",
        "preparation": "ready",
    },
    "Python Developer": {
        "description": "insufficient_data",
        "requirements": "insufficient_data",
        "preparation": "insufficient_data",
    },
    "Software Engineer": {
        "description": "ready",
        "requirements": "ready",
        "preparation": "ready",
    },
}
QUESTION_TEMPLATES = {
    "description": "What does a {role} do?",
    "requirements": "What skills does a {role} need?",
    "preparation": "Give me a preparation plan for {role}",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  DATA   Engineers ", "data engineer"),
        ("Web Developers", "web developer"),
        ("Data Analysts", "data analyst"),
        ("Software Engineer", "software engineer"),
    ],
)
def test_occupation_name_normalization_is_case_whitespace_and_plural_safe(value: str, expected: str):
    assert normalize_occupation_name(value) == expected


def test_occupation_alias_matching_requires_a_full_normalized_alias():
    assert occupation_label_matches(
        "Software Engineer",
        "Software Developer",
        '["software engineer\\nsoftware developers"]',
    )
    assert not occupation_label_matches(
        "Software Engineer",
        "Cloud Engineer",
        '["cloud software engineer"]',
    )


@pytest.fixture(scope="module")
def real_reference_engines():
    if not DATABASE_PATH.is_file():
        pytest.skip(f"Checked-in reference database is missing: {DATABASE_PATH}")
    store = ReferenceDataStore(DATABASE_PATH, read_only=True)
    mapper = V2SkillMapper(store)
    return (
        V2IntentPlanner(mapper),
        V2SkillIntelligenceEngine(store=store, skill_mapper=mapper),
        V2JobIntelligenceEngine(store=store, skill_mapper=mapper),
        store,
    )


@pytest.mark.parametrize(
    ("role", "question_type"),
    [
        (role, question_type)
        for role in EXPECTED_STATUS
        for question_type in QUESTION_TEMPLATES
    ],
)
def test_role_answers_use_only_read_only_taxonomy_records(
    real_reference_engines,
    role: str,
    question_type: str,
):
    planner, skill_engine, job_engine, store = real_reference_engines
    question = QUESTION_TEMPLATES[question_type].format(role=role)
    intent = planner.plan(question, portal_type="individual")

    expected_capability = {
        "description": "skill_lookup",
        "requirements": "job_role_requirements",
        "preparation": "job_preparation_actions",
    }[question_type]
    assert intent.capability_id == expected_capability
    assert intent.target_role
    assert normalize_occupation_name(intent.target_role) == normalize_occupation_name(role)

    if question_type == "description":
        result = skill_engine.run_skill_lookup(
            intent.target_role,
            entity_type="occupation",
            context=question,
            exact_occupation=True,
        )
        assert not any(item.entity_type == "skill" for item in result.lookup_result.results)
        if result.lookup_result.results:
            assert all(item.entity_type == "occupation" for item in result.lookup_result.results)
    elif question_type == "requirements":
        result = job_engine.run_role_requirements(intent.target_role)
    else:
        result = job_engine.run_preparation_actions(intent.target_role)

    response = V2ResponseFormatter.format_response(
        user_message=question,
        portal_type="individual",
        intent=intent,
        result=result,
        domain_override="skill" if question_type == "description" else "job",
    )
    assert response.status == EXPECTED_STATUS[role][question_type]

    if question_type == "description":
        if response.status == "ready":
            assert result.lookup_result.results
            assert any(item.taxonomy in {"O*NET 28.0 SOC", "ESCO v1.2.1 Occupation"} for item in result.lookup_result.results)
            assert "Taxonomy Details" in response.answer
            if any(normalize_occupation_name(item.name) != normalize_occupation_name(role) for item in result.lookup_result.results):
                assert f"No exact match for {role}; showing " in result.headline
        else:
            assert any("O*NET 28.0 or ESCO v1.2.1" in limitation for limitation in result.lookup_result.limitations)
    elif question_type == "requirements":
        source = result.metadata.get("source")
        if response.status == "ready":
            assert source in {"O*NET occupation taxonomy", "ESCO occupation taxonomy"}
            assert source in response.answer
            assert "not hiring demand" in response.answer
            assert "not platform-collected data" in response.answer
            fact = next(fact for fact in result.facts if fact.fact_type == "role_skill_requirements")
            returned_skills = {
                skill
                for key in ("essential_skills", "optional_skills", "other_skills")
                for skill in fact.details[key]
            }
            taxonomy_skills = _occupation_skills(store, fact.canonical_entity_id)
            assert returned_skills <= taxonomy_skills
            if (fact.canonical_entity_id or "").startswith("http://data.europa.eu/esco/"):
                relations = _esco_skill_relations(store, fact.canonical_entity_id)
                assert set(fact.details["essential_skills"]) == {
                    skill for skill, relation in relations.items() if relation == "essential"
                } & returned_skills
                assert set(fact.details["optional_skills"]) == {
                    skill for skill, relation in relations.items() if relation == "optional"
                } & returned_skills
            else:
                assert not fact.details["essential_skills"]
                assert not fact.details["optional_skills"]
                assert set(fact.details["other_skills"]) == returned_skills
        else:
            assert "O*NET or ESCO reference taxonomies" in response.answer
            assert not result.facts
    else:
        plan = result.action_plan
        assert plan is not None
        if response.status == "ready":
            expected_source = (
                "ESCO occupation taxonomy"
                if (plan.soc_code or "").startswith("http://data.europa.eu/esco/")
                else "O*NET occupation taxonomy"
            )
            assert expected_source in response.answer
            action_skills = {action.skill_name for action in plan.actions}
            assert action_skills <= _occupation_skills(store, plan.soc_code)
            if plan.resolved_role_name and normalize_occupation_name(plan.resolved_role_name) != normalize_occupation_name(role):
                assert f"No exact match for {role}; showing {plan.resolved_role_name}." in response.answer
        else:
            assert "O*NET or ESCO occupation taxonomies" in response.answer
            assert not plan.actions


def _occupation_skills(store: ReferenceDataStore, occupation_id: str | None) -> set[str]:
    if not occupation_id:
        return set()
    with store._connect() as connection:
        if occupation_id.startswith("http://data.europa.eu/esco/"):
            rows = connection.execute(
                """
                SELECT r.skill_label, s.preferred_label
                FROM ref_esco_occupation_skill_relations r
                JOIN ref_esco_skills s ON r.skill_uri = s.concept_uri
                WHERE r.occupation_uri = ?
                """,
                (occupation_id,),
            ).fetchall()
            return {
                skill
                for row in rows
                for skill in (row["skill_label"], row["preferred_label"])
                if skill
            }
        rows = connection.execute(
            """
            SELECT workplace_example
            FROM ref_onet_software_skills
            WHERE soc_code = ?
            """,
            (occupation_id,),
        ).fetchall()
        return {row["workplace_example"] for row in rows}


def _esco_skill_relations(store: ReferenceDataStore, occupation_id: str) -> dict[str, str]:
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT r.skill_label, r.relation_type, s.preferred_label
            FROM ref_esco_occupation_skill_relations r
            JOIN ref_esco_skills s ON r.skill_uri = s.concept_uri
            WHERE r.occupation_uri = ?
            """,
            (occupation_id,),
        ).fetchall()
    return {
        skill: row["relation_type"]
        for row in rows
        for skill in (row["skill_label"], row["preferred_label"])
        if skill
    }

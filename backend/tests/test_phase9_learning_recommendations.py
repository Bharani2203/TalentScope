from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest
from app.models.reference_data import OnetOccupation, OnetSoftwareSkill
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.reference_store import ReferenceDataStore


class EmptyObservationStore:
    def __init__(self, observations=None):
        self.observations = list(observations or [])

    def get_observations_by_skill(self, *, skill, location, cutoff):
        return [
            observation for observation in self.observations
            if observation.skill.casefold() == skill.casefold()
            and observation.observed_at >= cutoff
        ]


def _seed_role(store: ReferenceDataStore) -> None:
    store.upsert_onet_occupations([
        OnetOccupation(
            soc_code="15-1252.00",
            title="Software Developers",
            description="Develop software applications.",
        )
    ])
    store.upsert_onet_software_skills([
        OnetSoftwareSkill(
            id="onet-python",
            soc_code="15-1252.00",
            title="Software Developers",
            workplace_example="Python",
            element_id="2.E.6.a",
            element_name="Development environment software",
            hot_technology=True,
            in_demand=True,
            canonical_skill_id="python",
        ),
        OnetSoftwareSkill(
            id="onet-sql",
            soc_code="15-1252.00",
            title="Software Developers",
            workplace_example="SQL",
            element_id="2.E.6.b",
            element_name="Database management system software",
            hot_technology=False,
            in_demand=False,
            canonical_skill_id="sql",
        ),
        OnetSoftwareSkill(
            id="onet-label",
            soc_code="15-1252.00",
            title="Software Developers",
            workplace_example="Example Design Suite",
            element_id="2.E.6.c",
            element_name="Graphics or photo imaging software",
            hot_technology=False,
            in_demand=False,
        ),
    ])


def _profile(*, roles=None, skills=None, skill_levels=None):
    return SimpleNamespace(profile={
        "skills": {
            "selected_skills": list(skills or []),
            "skill_levels": (
                {"Python": "Comfortable"} if skill_levels is None else skill_levels
            ),
        },
        "career": {"target_roles": list(roles or [])},
        "work_preferences": {"learning_time": "2–5 hours"},
        "learning_preferences": ["Hands-on practice"],
    })


@pytest.mark.parametrize(
    "message",
    [
        "Which skill should I learn next?",
        "Suggest a learning roadmap for my available study time",
        "What skills should I learn for this role?",
        "How can I improve my Python skills for backend development?",
        "Which skills should I prioritize for my target role?",
        "Create a learning roadmap based on my current skills",
    ],
)
def test_learning_queries_route_to_existing_action_capability(message):
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(message=message)
    )

    assert plan.intent == "synthesize_actions"
    assert "action_recommendations" in plan.selected_capabilities


def test_action_request_uses_only_authenticated_users_own_saved_profile(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    reference_store = ReferenceDataStore(db_path)
    _seed_role(reference_store)
    seen_uids = []

    def profile_for(uid):
        seen_uids.append(uid)
        return _profile(roles=["Software Developers"], skills=["Python"])

    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile", profile_for
    )
    settings = Settings(
        _env_file=None,
        skill_intelligence_db_path=str(db_path),
        skill_intelligence_read_backend="firestore",
    )
    service = ExecutionOrchestratorService(
        settings=settings,
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )
    monkeypatch.setattr(service.llm_service, "is_available", lambda: False)

    request = CoreIntelligenceAnswerRequest(
        message="Which skill should I learn next?",
        portal_type="individual",
    )
    user = AuthenticatedUser(uid="signed-in-person")
    response = service.answer(request, authenticated_user=user)
    repeated_response = service.answer(request, authenticated_user=user)

    assert seen_uids == ["signed-in-person", "signed-in-person"]
    assert response.answer == repeated_response.answer
    assert response.execution_status == "completed"
    candidates = [
        fact for fact in response.facts
        if fact.fact_type == "action_recommendation"
    ]
    assert candidates
    assert all(fact.entity_name != "Python" for fact in candidates)
    assert all(fact.evidence_reference for fact in candidates)
    evidence_ids = {evidence.evidence_id for evidence in response.evidence}
    assert all(fact.evidence_reference in evidence_ids for fact in candidates)
    assert "deterministic exploration priority" in response.answer.lower()
    assert "not current job-posting evidence" in response.answer.lower()
    assert [fact.details["recommendation_rank"] for fact in candidates] == [1, 2]
    assert all(not fact.details["market_trend_used_for_ranking"] for fact in candidates)
    assert all(not fact.details["prerequisite_data_available"] for fact in candidates)
    summary = next(
        fact for fact in response.facts
        if fact.fact_type == "learning_recommendation_summary"
    )
    assert summary.details["profile_skill_source"] == "authenticated_individual_profile"
    assert not any(
        fact.fact_type in {"task_exposure_summary", "workforce_impact"}
        for fact in response.facts
    )


def test_deterministic_rank_reuses_onet_flags_then_name_without_numeric_scores(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    _seed_role(ReferenceDataStore(db_path))
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(roles=["Software Developers"], skills=[]),
    )
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skill should I learn next?",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="ranking-person"),
    )
    candidates = [
        fact for fact in response.facts
        if fact.fact_type == "action_recommendation"
    ]

    assert [(fact.details["recommendation_rank"], fact.entity_name) for fact in candidates] == [
        (1, "Python"),
        (2, "Example Design Suite"),
        (3, "SQL"),
    ]
    assert candidates[0].details["taxonomy_hot_technology"] is True
    assert candidates[0].details["taxonomy_in_demand"] is True
    assert candidates[1].details["ranking_method"] == candidates[2].details["ranking_method"]
    assert "no numeric score or weights" in candidates[0].details["ranking_method"].lower()
    assert not candidates[0].details["market_trend_used_for_ranking"]


def test_missing_self_reported_proficiency_does_not_invent_skill_depth_or_resources(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    _seed_role(ReferenceDataStore(db_path))
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(
            roles=["Software Developers"], skills=["Python"], skill_levels={}
        ),
    )
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skill should I learn next?",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="incomplete-proficiency-person"),
    )

    summary = next(
        fact for fact in response.facts
        if fact.fact_type == "learning_recommendation_summary"
    )
    candidates = [
        fact for fact in response.facts
        if fact.fact_type == "action_recommendation"
    ]
    assert summary.details["profile_skill_levels"] == {}
    assert summary.details["profile_skill_levels_used_for_ranking"] is False
    assert summary.details["learning_resource_catalog_available"] is False
    assert all(fact.entity_name != "Python" for fact in candidates)
    assert any("required proficiency levels" in item.lower() for item in response.limitations)
    assert not any("course" in fact.fact_type for fact in response.facts)


def test_employee_context_cannot_import_a_supplied_individual_profile(
    monkeypatch,
):
    reads = []
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda uid: reads.append(uid),
    )
    request = CoreIntelligenceAnswerRequest(
        message="Which skill should I learn next?",
        portal_type="employee",
        context_override={
            "_authenticated_learning_profile": {
                "uid": "another-person",
                "target_roles": ["Software Developers"],
            },
            "_learning_profile_state": "available",
        },
    )
    service = ExecutionOrchestratorService(
        settings=Settings(_env_file=None, skill_intelligence_read_backend="sqlite"),
        observation_store=EmptyObservationStore(),
    )

    sanitized = service._apply_authenticated_learning_profile(
        request,
        AuthenticatedUser(uid="employee-person"),
        portal_type="employee",
    )

    assert reads == []
    assert "_authenticated_learning_profile" not in sanitized.context_override
    assert "_learning_profile_state" not in sanitized.context_override


def test_missing_role_returns_insufficient_data_without_static_suggestions(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    _seed_role(ReferenceDataStore(db_path))
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(),
    )
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skill should I learn next?",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="profile-with-no-role"),
    )

    assert response.status == "insufficient_data"
    assert "target role" in response.answer.lower()
    assert not any(
        fact.fact_type == "action_recommendation" for fact in response.facts
    )
    assert not any(
        evidence.source == "action_recommendation_engine"
        for evidence in response.evidence
    )


def test_unresolved_role_and_missing_mappings_do_not_use_default_occupation(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    store = ReferenceDataStore(db_path)
    store.upsert_onet_occupations([
        OnetOccupation(
            soc_code="15-1252.00",
            title="Software Developers",
            description="Develop software applications.",
        )
    ])
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(),
    )
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Suggest learning recommendations",
            target_role="Unlisted Specialist",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="unsupported-role-person"),
    )

    assert response.status == "insufficient_data"
    assert "no exact o*net occupation match" in response.answer.lower()
    assert not any(
        fact.fact_type == "action_recommendation" for fact in response.facts
    )

    mappingless = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Suggest learning recommendations",
            target_role="Software Developers",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="mappingless-role-person"),
    )
    assert mappingless.status == "unavailable"
    assert "no o*net software/technology mappings" in mappingless.answer.lower()
    assert not any(
        fact.fact_type == "action_recommendation" for fact in mappingless.facts
    )


def test_role_mapping_read_preserves_flags_and_has_a_strict_bound(tmp_path):
    store = ReferenceDataStore(tmp_path / "reference.sqlite3")
    _seed_role(store)

    mappings = store.get_onet_software_skills_by_occupation(
        "15-1252.00", limit=2
    )

    assert len(mappings) == 2
    assert all("hot_technology" in mapping for mapping in mappings)
    assert all("in_demand" in mapping for mapping in mappings)
    assert mappings[0]["workplace_example"] == "Python"


def test_valid_market_evidence_is_separate_from_role_taxonomy_candidates(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    _seed_role(ReferenceDataStore(db_path))
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(roles=["Software Developers"], skills=["Python"]),
    )
    observations = []
    for month, value in zip((5, 6, 7, 8, 9), (10, 15, 20, 25, 30)):
        period = f"2026-{month:02d}"
        observations.append(MarketObservation(
            id=f"sql-demand-{period}",
            source="jsearch",
            skill="SQL",
            skill_id="sql",
            signal_type="demand",
            observed_at=datetime(2026, month, 15, tzinfo=timezone.utc),
            period=period,
            location="Global",
            scope="global",
            value=float(value),
            denominator=100.0,
            unit="job_postings",
            denominator_unit="postings",
            data_origin="real",
            history_type="platform_collected",
            fetch_run_id=f"run-{period}",
            series_id="jsearch:demand:sql:v1",
            quality="valid",
        ))
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(observations),
    )

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skill should I learn next?",
            portal_type="individual",
        ),
        authenticated_user=AuthenticatedUser(uid="market-evidence-person"),
    )

    market_facts = [
        fact for fact in response.facts
        if fact.fact_type == "learning_market_evidence"
    ]
    candidates = [
        fact for fact in response.facts
        if fact.fact_type == "action_recommendation"
    ]
    assert market_facts, response.model_dump(mode="json")
    assert all(fact.source == "jsearch" for fact in market_facts)
    assert all(fact.evidence_reference for fact in market_facts)
    assert next(fact for fact in candidates if fact.entity_name == "SQL").details[
        "recommendation_rank"
    ] == 2
    assert not next(fact for fact in candidates if fact.entity_name == "SQL").details[
        "market_trend_used_for_ranking"
    ]


def test_why_recommendation_routes_to_evidence_follow_up():
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(message="Why are you recommending this skill?")
    )

    assert plan.intent == "retrieve_evidence"
    assert "evidence_provenance_retrieval" in plan.selected_capabilities


def test_recommendation_evidence_follow_up_reuses_only_prior_cited_evidence(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "reference.sqlite3"
    _seed_role(ReferenceDataStore(db_path))
    monkeypatch.setattr(
        "app.services.onboarding_service.get_individual_profile",
        lambda _uid: _profile(roles=["Software Developers"], skills=["Python"]),
    )
    service = ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_db_path=str(db_path),
            skill_intelligence_read_backend="firestore",
        ),
        db_path=db_path,
        observation_store=EmptyObservationStore(),
    )
    user = AuthenticatedUser(uid="recommendation-follow-up-user")
    first_response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skill should I learn next?",
            portal_type="individual",
            domain="skill",
        ),
        authenticated_user=user,
    )
    prior_state = service.conversation_store.get_conversation(
        first_response.conversation_id,
        user_id=user.uid,
    )
    assert prior_state is not None
    assert prior_state.turns
    prior_turn = prior_state.turns[-1]

    follow_up = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Why are you recommending this skill?",
            portal_type="individual",
            conversation_id=first_response.conversation_id,
        ),
        authenticated_user=user,
    )

    assert follow_up.execution_status == "completed", (
        first_response.intent,
        first_response.execution_status,
        prior_turn.intent,
        prior_turn.execution_status,
        bool(prior_turn.response_payload),
        follow_up.intent,
        follow_up.reason_codes,
    )
    assert "PRIOR_RECOMMENDATION_EVIDENCE_RETRIEVED" in follow_up.reason_codes
    assert follow_up.evidence
    assert all(
        fact.evidence_reference in {item.evidence_id for item in follow_up.evidence}
        for fact in follow_up.facts
        if fact.evidence_reference
    )
    assert "not proof" in follow_up.answer.lower()

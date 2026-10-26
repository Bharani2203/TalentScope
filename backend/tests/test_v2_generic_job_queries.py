import pytest

from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.services.question_classification_service import extract_location
from tests.test_job_search_generic_queries import fake_corpus_client


@pytest.fixture(autouse=True)
def _patch_firestore_client(monkeypatch, fake_corpus_client):
    monkeypatch.setattr(
        "app.services.job_storage_service.get_firestore_client",
        lambda: fake_corpus_client,
    )


@pytest.mark.parametrize(
    "query,expected_count",
    [
        ("jobs in Bangalore", 3),
        ("Bangalore jobs", 3),
        ("show me jobs", 5),
        ("python developer jobs in Bangalore", 1),
    ],
)
def test_v2_intent_planner_plus_job_intelligence_engine(query, expected_count):
    planner = V2IntentPlanner()
    engine = V2JobIntelligenceEngine()

    intent = planner.plan(query)
    role_or_skill = intent.target_role or intent.target_skill
    loc = extract_location(query)
    country = (
        intent.geography
        if intent.geography and intent.geography not in {"all", "global"}
        else None
    )

    result = engine.run_verified_postings(
        role_or_skill=role_or_skill,
        location=loc,
        country=country,
        question=query,
    )
    assert len(result.postings) == expected_count


@pytest.mark.parametrize(
    "query,expected_count",
    [
        ("jobs in Bangalore", 3),
        ("Bangalore jobs", 3),
        ("show me jobs", 5),
        ("python developer jobs in Bangalore", 1),
    ],
)
def test_v2_orchestrator_request_message_generic_queries(query, expected_count):
    orchestrator = V2Orchestrator()
    request = CoreIntelligenceAnswerRequest(
        message=query,
        portal_type="individual",
    )
    user = AuthenticatedUser(uid="test_user", email="test@talentscope.ai")

    response = orchestrator.execute_request(request, authenticated_user=user)
    fact = next((f for f in response.facts if f.fact_type == "stored_job_postings"), None)
    assert fact is not None, f"Expected stored_job_postings fact for '{query}'"
    assert fact.metric_value == expected_count
    assert len(fact.details["postings"]) == expected_count

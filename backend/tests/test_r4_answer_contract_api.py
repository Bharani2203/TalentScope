"""Offline API-level answer and evidence contract coverage for R4."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from app.api import dependencies
from app.api.routes import core_intelligence
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.job import Job
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.storage.conversation_store import ConversationState, ConversationStore


class EmptyObservationStore:
    @staticmethod
    def get_observations(**_kwargs):
        return []

    @staticmethod
    def get_observations_by_skill(**_kwargs):
        return []


@pytest.fixture
def answer_api(tmp_path, monkeypatch, injected_empty_firestore):
    """Exercise the real API with only temporary SQLite and in-memory stores."""
    user = AuthenticatedUser(uid="r4-offline-user", email="r4@example.test")
    conversation_store = ConversationStore()
    monkeypatch.setattr(
        ConversationStore,
        "get_instance",
        classmethod(lambda cls: conversation_store),
    )
    service = ExecutionOrchestratorService(
        db_path=tmp_path / "isolated-r4.sqlite3",
        observation_store=EmptyObservationStore(),
        workforce_store=object(),
    )
    service.llm_service.is_available = lambda: False
    monkeypatch.setattr(core_intelligence, "ExecutionOrchestratorService", lambda: service)
    monkeypatch.setitem(app.dependency_overrides, dependencies.get_current_user, lambda: user)
    return TestClient(app), service, conversation_store, user, injected_empty_firestore


@pytest.mark.parametrize(
    ("message", "domain", "intent", "capability"),
    [
        ("What is Python used for?", "skill", "general_explanation", None),
        ("Show the canonical definition and category for Python.", "skill", "lookup_skill_reference", "skill_technology_reference"),
        ("What demand trend is observed for Python?", "skill", "analyze_trend", "trend_velocity_analysis"),
        ("Which companies are hiring Python developers?", "job", "search_jobs", "job_posting_search"),
        ("What skills should I learn for a backend developer role?", "skill", "synthesize_actions", "action_recommendations"),
        ("What is the difference between Python and Java?", "skill", "general_explanation", None),
        ("Show historical observations for Python.", "skill", "retrieve_history", "historical_signal_retrieval"),
        ("What is the future demand for Python?", "skill", "forecast_future_demand", "skill_forecasting_half_life"),
    ],
)
def test_r4_api_serializes_scenario_results_without_invented_evidence(
    answer_api, message, domain, intent, capability
):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={"message": message, "domain": domain, "time_range": "max"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == intent
    assert data["planned_primary_capability"] == capability
    assert data["execution_status"] in {
        "completed", "insufficient_data", "unsupported", "requires_clarification"
    }

    if intent == "general_explanation":
        assert data["execution_status"] == "completed"
        assert "not a TalentScope" in data["answer"]
        assert data["facts"] == [] and data["evidence"] == []
        assert data["capabilities_used"] == []
    elif intent == "lookup_skill_reference":
        assert data["executed_primary_capability"] == "skill_technology_reference"
        assert not any(item["source"].startswith("ref_github") for item in data["evidence"])
        assert not any(item["fact_type"] == "technology_adoption" for item in data["facts"])
        assert "unavailable" in data["answer"].lower()
    elif intent == "analyze_trend":
        assert data["execution_status"] == "insufficient_data"
        assert data["executed_primary_capability"] is None
        assert data["facts"] == [] and data["evidence"] == []
        assert data.get("chart_data") in (None, [], {})
        assert "trend" in data["answer"].lower()
        assert "no measured trend observations" in data["answer"].lower()
        assert "no trend value can be established" in data["answer"].lower()
    elif intent == "search_jobs":
        assert data["executed_primary_capability"] == "job_posting_search"
        assert data["execution_status"] == "completed"
        assert data["evidence"] == []
        assert "no matching job postings" in data["answer"].lower()
        assert not any(word in data["answer"].lower() for word in ("acme", "google", "microsoft"))
        assert any(
            item["fact_type"] == "stored_job_postings"
            and item["metric_value"] == 0
            and item["readiness_state"] == "insufficient_data"
            for item in data["facts"]
        )
    elif intent == "synthesize_actions":
        assert "c" not in {entity.get("canonical_name", "").casefold() for entity in data.get("selected_entities", [])}
    elif intent == "retrieve_history":
        assert data["execution_status"] == "insufficient_data"
        assert data["facts"] == [] and data["evidence"] == []
        assert not any(key in data for key in ("trend", "forecast", "velocity"))
    elif intent == "forecast_future_demand":
        assert data["execution_status"] == "insufficient_data"
        assert data["facts"] == [] and data["evidence"] == []
        assert data["executed_primary_capability"] is None


def test_r4_reference_question_does_not_use_ambient_skills_as_evidence(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Show the canonical definition and category for Python.",
            "domain": "skill",
            "selected_skills": ["HTML", "Java"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert all(fact.get("entity_name") in (None, "Python") for fact in data["facts"])
    assert all(item["signal_type"] == "taxonomy_lookup" for item in data["evidence"])
    assert "unavailable" in data["answer"].lower()


def test_evidence_api_returns_explicit_empty_readiness_without_placeholder(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Show evidence and sources for Python",
            "domain": "skill",
            "capability_id": "evidence_provenance_retrieval",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["planned_primary_capability"] == "evidence_provenance_retrieval"
    assert data["intent"] == "retrieve_evidence"
    assert "ev_none" not in response.text
    summary = next(fact for fact in data["facts"] if fact["fact_type"] == "evidence_summary")
    assert summary["metric_value"] == 0
    assert summary["data_origin"] == "unavailable"
    assert summary["readiness_state"] == "insufficient_data"
    assert summary["evidence_reference"] is None
    assert data["evidence"] == []
    assert "no verified evidence records are available" in data["answer"].lower()
    assert "no matching stored observation" in data["answer"].lower()


def test_action_feature_is_not_overridden_by_evidence_wording(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What should I learn next based on evidence?",
            "domain": "skill",
            "capability_id": "action_recommendations",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["planned_primary_capability"] == "action_recommendations"
    assert data["intent"] == "synthesize_actions"
    assert data["executed_primary_capability"] in {None, "action_recommendations"}
    assert data["executed_primary_capability"] != "evidence_provenance_retrieval"


def test_historical_github_question_keeps_source_geography_and_capability_contract(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Show GitHub Innovation Graph history for Python in India.",
            "domain": "skill",
            "capability_id": "historical_signal_retrieval",
            "time_range": "max",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["planned_primary_capability"] == "historical_signal_retrieval"
    assert data["intent"] == "retrieve_history"
    assert data["execution_status"] in {"insufficient_data", "completed"}
    assert "GitHub Innovation Graph" in data["answer"] or "github" in data["answer"].lower()


def test_historical_question_naming_multiple_sources_requests_clarification(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "Show GitHub and Wikipedia history for Python.",
            "domain": "skill",
            "capability_id": "historical_signal_retrieval",
            "time_range": "max",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "retrieve_history"
    assert data["planned_primary_capability"] == "historical_signal_retrieval"
    assert data["execution_status"] == "requires_clarification"
    assert "more than one historical signal source" in data["answer"].lower()


def test_r4_provider_failure_uses_deterministic_answer_without_market_claims(answer_api, caplog):
    client, service, _conversation_store, _user, _firestore = answer_api
    service.llm_service.is_available = lambda: True

    def provider_failure(**_kwargs):
        raise RuntimeError("provider token=must-not-be-exposed")

    service.llm_service.generate_grounded_explanation = provider_failure
    response = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is Python used for?", "domain": "skill"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["execution_status"] == "failed"
    assert data["status"] == "unavailable"
    assert data["degraded"] is True
    assert data["answer_origin"] == "deterministic"
    assert data["answer"] == "The assistant is temporarily experiencing high demand. Please try again shortly."


def test_r4_usage_ledger_failure_marks_response_degraded_without_provider_request(answer_api, caplog):
    client, service, _conversation_store, _user, _firestore = answer_api
    service.llm_service.is_available = lambda: True
    provider_calls = []

    def unavailable_ledger(*_args, **_kwargs):
        raise RuntimeError("private ledger details")

    service.llm_service.reserve_durable_budget = unavailable_ledger
    service.llm_service._post_json = lambda **_kwargs: provider_calls.append("sent")

    response = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is Python used for?", "domain": "skill"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["degraded"] is True
    assert data["degraded_reason"] == "usage_ledger_unavailable"
    assert data["answer_origin"] == "deterministic"
    assert provider_calls == []
    assert "private ledger details" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert "must-not-be-exposed" not in response.text
    assert "must-not-be-exposed" not in caplog.text


def test_r4_failed_request_cannot_retain_previous_response_evidence(answer_api, monkeypatch):
    client, service, _conversation_store, _user, _firestore = answer_api
    fixture_job = Job(
        job_id="r4_fixture_job_1",
        title="Python Developer",
        company_name="Fixture Systems",
        location="Remote",
        country_code="us",
        posted_at=datetime.now(timezone.utc).date().isoformat(),
        source="jsearch",
        source_url="https://jobs.example.test/r4-fixture-job",
        skills_raw=["Python"],
        fetched_at=datetime.now(timezone.utc),
    )
    fixture_record = fixture_job.model_dump(mode="json", exclude_none=True)
    fixture_record["source_job_id"] = fixture_job.job_id
    _firestore.collection("jobs").document("jsearch:r4_fixture_job_1").set(fixture_record, merge=True)
    first = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Find jobs for Python", "domain": "job", "client_message_id": "r4-success"},
    )
    assert first.status_code == 200
    prior = first.json()
    assert prior["execution_status"] == "completed"
    assert any(item["source_url"] == "https://jobs.example.test/r4-fixture-job" for item in prior["evidence"]), prior

    def fail_handler(*_args, **_kwargs):
        raise RuntimeError("isolated handler failure")

    service._handler_registry["job_posting_search"] = fail_handler
    second = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Find jobs for Java", "domain": "job", "client_message_id": "r4-failure"},
    )

    assert second.status_code == 200
    failed = second.json()
    assert failed["execution_status"] == "failed"
    assert failed["facts"] == [] and failed["evidence"] == []
    assert failed.get("chart_data") in (None, [], {})
    assert failed["request_id"] != prior["request_id"]
    assert "isolated handler failure" not in failed["answer"]


def test_r4_clarification_and_conversation_access_are_isolated(answer_api, monkeypatch):
    client, _service, conversations, user, _firestore = answer_api
    ambiguous = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is the trend for C?", "domain": "skill"},
    )
    assert ambiguous.status_code == 200
    ambiguous_data = ambiguous.json()
    assert ambiguous_data["execution_status"] == "requires_clarification"
    assert ambiguous_data["facts"] == [] and ambiguous_data["evidence"] == []

    conversation_id = "r4-private-conversation"
    conversations.create_conversation(
        conversation_id=conversation_id,
        user_id=user.uid,
        portal_type="individual",
        domain="skill",
    )
    conversations._conversations[conversation_id].active_entity = "private-conversation-sentinel"
    current_intent = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What skills should I learn for a backend developer role?",
            "domain": "skill",
            "conversation_id": conversation_id,
        },
    )
    assert current_intent.status_code == 200
    current_data = current_intent.json()
    assert current_data["intent"] == "synthesize_actions"
    assert "C" not in {item["canonical_name"] for item in current_data["selected_entities"]}
    assert "Python" not in {item["canonical_name"] for item in current_data["selected_entities"]}
    other_user = AuthenticatedUser(uid="r4-other-user", email="other@example.test")
    monkeypatch.setitem(
        app.dependency_overrides,
        dependencies.get_current_user,
        lambda: other_user,
    )
    denied = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What skills should I learn for a backend developer role?",
            "domain": "skill",
            "conversation_id": conversation_id,
        },
    )

    assert denied.status_code == 403
    assert "private-conversation-sentinel" not in denied.text
    assert conversation_id not in denied.text


def test_r4_unauthenticated_answer_request_is_rejected(answer_api, monkeypatch):
    client, _service, _conversation_store, _user, _firestore = answer_api
    monkeypatch.setitem(app.dependency_overrides, dependencies.get_current_user, dependencies.get_current_user)
    response = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What is Python used for?", "domain": "skill"},
    )
    assert response.status_code == 401


def test_r4_api_rejects_client_supplied_market_observations(answer_api):
    client, _service, _conversation_store, _user, _firestore = answer_api
    response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What demand trend is observed for Python?",
            "domain": "skill",
            "observations": [{
                "id": "untrusted-observation",
                "source": "jsearch",
                "skill": "Python",
                "observed_at": "2026-09-15T00:00:00Z",
                "period": "2026-09",
                "signal_type": "demand",
                "value": 99999,
                "unit": "job_postings",
            }],
        },
    )

    assert response.status_code == 422
    assert "cannot be supplied by clients" in response.json()["detail"]

from __future__ import annotations

from datetime import datetime

import google.cloud.firestore as google_firestore
import pytest

from app.core.config import Settings
from app.models.execution_orchestrator import EvidenceItem, StructuredFact
from app.services.llm_explanation_service import LLMExplanationService


def _grounded_fact():
    return StructuredFact(
        fact_type="trend",
        metric_name="trend_direction",
        metric_value="stable",
        source="jsearch",
    )


def test_gemini_budget_configuration_is_bounded_and_masks_credentials():
    settings = Settings(
        _env_file=None,
        gemini_api_key="unit-test-secret",
        gemini_max_calls_per_minute=12,
        gemini_max_calls_per_day=240,
        gemini_max_calls_per_user_per_hour=8,
        gemini_max_input_chars=16000,
        gemini_max_output_tokens=2048,
        gemini_request_timeout_seconds=10,
    )
    assert settings.gemini_max_calls_per_minute == 12
    assert settings.gemini_max_calls_per_day == 240
    assert settings.gemini_max_calls_per_user_per_hour == 8
    assert settings.gemini_max_input_chars == 16000
    assert settings.gemini_max_output_tokens == 2048
    assert settings.gemini_request_timeout_seconds == 10
    assert "unit-test-secret" not in repr(settings.gemini_api_key)


class FakeSnapshot:
    def __init__(self, value):
        self.value = value
        self.exists = value is not None

    def to_dict(self):
        return dict(self.value) if self.value is not None else None


class FakeDocument:
    def __init__(self, store, document_id):
        self.store = store
        self.id = document_id


class FakeCollection:
    def __init__(self, store):
        self.store = store

    def document(self, document_id):
        return FakeDocument(self.store, document_id)


class FakeTransaction:
    def __init__(self, store):
        self.store = store

    def get(self, document):
        return FakeSnapshot(self.store.get(document.id))

    def set(self, document, value, merge=False):
        current = self.store.get(document.id, {}) if merge else {}
        self.store[document.id] = {**current, **value}


class FakeFirestore:
    def __init__(self):
        self.store = {}

    def collection(self, _name):
        return FakeCollection(self.store)

    def transaction(self, max_attempts):
        assert max_attempts == 5
        return FakeTransaction(self.store)


def test_firestore_reservation_enforces_user_global_and_duplicate_limits(monkeypatch):
    fake_firestore = FakeFirestore()
    monkeypatch.setattr(
        "app.core.firebase.get_firestore_client",
        lambda: fake_firestore,
    )
    monkeypatch.setattr(google_firestore, "transactional", lambda callback: callback)
    monkeypatch.setattr(LLMExplanationService, "_GLOBAL_MAX_CALLS_PER_MINUTE", 2)
    monkeypatch.setattr(LLMExplanationService, "_GLOBAL_MAX_CALLS_PER_DAY", 10)
    monkeypatch.setattr(LLMExplanationService, "_USER_MAX_REQUESTS_PER_WINDOW", 1)

    assert LLMExplanationService.reserve_durable_budget("private-user-id", "request-a") is True
    assert LLMExplanationService.reserve_durable_budget("private-user-id", "request-a") is False
    assert LLMExplanationService.reserve_durable_budget("private-user-id", "request-b") is False
    assert LLMExplanationService.reserve_durable_budget("another-user", "request-c") is True
    assert LLMExplanationService.reserve_durable_budget("third-user", "request-d") is False

    assert all("private-user-id" not in key for key in fake_firestore.store)
    assert sum(key.startswith("global_minute_") and value["count"] for key, value in fake_firestore.store.items()) == 2


def test_unavailable_durable_ledger_uses_deterministic_fallback(monkeypatch):
    service = LLMExplanationService(api_key="test-key")
    monkeypatch.setattr(service, "is_available", lambda: True)

    def unavailable(*_args):
        raise ConnectionError("ledger is offline")

    monkeypatch.setattr(service, "reserve_durable_budget", unavailable)

    class UnexpectedClient:
        def __init__(self, **_kwargs):
            raise AssertionError("Gemini must not be called without a quota reservation")

    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", UnexpectedClient)
    assert service.generate_grounded_explanation(
        user_message="Analyze Python",
        intent="analyze_trend",
        facts=[_grounded_fact()],
        evidence=[],
        user_id="test-user",
    ) is None


def test_empty_facts_skip_gemini_and_budget_reservation(monkeypatch):
    service = LLMExplanationService(api_key="test-key")
    monkeypatch.setattr(service, "is_available", lambda: True)

    def unexpected_reservation(*_args):
        raise AssertionError("No budget should be reserved without grounded facts")

    class UnexpectedClient:
        def __init__(self, **_kwargs):
            raise AssertionError("Gemini must not be called without grounded facts")

    monkeypatch.setattr(service, "reserve_durable_budget", unexpected_reservation)
    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", UnexpectedClient)

    assert service.generate_grounded_explanation(
        user_message="Analyze Python",
        intent="analyze_trend",
        facts=[],
        evidence=[],
        user_id="test-user",
    ) is None


@pytest.mark.parametrize(
    ("model_text", "expected"),
    [
        ("Common design directions include clearer typography and accessible color choices.", True),
        ("There are 3 leading design trends.", False),
    ],
)
def test_general_explanation_requires_opt_in_and_rejects_numeric_claims(monkeypatch, model_text, expected):
    LLMExplanationService._cache.clear()
    service = LLMExplanationService(api_key="test-key")
    monkeypatch.setattr(service, "is_available", lambda: True)
    monkeypatch.setattr(service, "reserve_durable_budget", lambda *_args: True)
    posted = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"candidates": [{"content": {"parts": [{"text": model_text}]}}]}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, _url, *, json, **_kwargs):
            posted.update(json)
            return FakeResponse()

    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", FakeClient)
    result = service.generate_grounded_explanation(
        user_message="What are the latest UI/UX design trends?",
        intent="general_explanation",
        facts=[],
        evidence=[],
        portal_type="general",
        user_id="budget-user",
        general_knowledge=True,
    )

    assert (result is not None) is expected
    assert "not a TalentScope market finding" in posted["systemInstruction"]["parts"][0]["text"]
    assert "Structured Facts:\n[]" in posted["contents"][0]["parts"][0]["text"]


def test_gemini_429_falls_back_without_retry(monkeypatch):
    service = LLMExplanationService(api_key="test-key")
    monkeypatch.setattr(service, "is_available", lambda: True)
    monkeypatch.setattr(service, "reserve_durable_budget", lambda *_args: True)
    request_count = 0

    class FakeResponse:
        status_code = 429

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            nonlocal request_count
            request_count += 1
            return FakeResponse()

    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", FakeClient)
    assert service.generate_grounded_explanation(
        user_message=f"Rate limit test {datetime.now().isoformat()}",
        intent="analyze_trend",
        facts=[_grounded_fact()],
        evidence=[],
        user_id="test-user",
    ) is None
    assert request_count == 1


def test_explanation_cache_key_tracks_model_and_complete_evidence():
    fact = _grounded_fact()
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        source="jsearch",
        signal_type="demand",
        period="2026-10",
        description="Observed postings",
    )
    service = LLMExplanationService(api_key="test-key")
    alternate_model = LLMExplanationService(
        api_key="test-key",
        model_name="gemini-test-model",
    )

    original_key = service._get_cache_key(
        "Analyze Python",
        "analyze_trend",
        [fact],
        [evidence],
    )
    assert original_key != alternate_model._get_cache_key(
        "Analyze Python",
        "analyze_trend",
        [fact],
        [evidence],
    )
    assert original_key != service._get_cache_key(
        "Analyze Python",
        "analyze_trend",
        [fact],
        [evidence.model_copy(update={"signal_type": "adoption"})],
    )

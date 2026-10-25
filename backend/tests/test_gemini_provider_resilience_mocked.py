"""Mock-only checks for bounded Gemini retries and degraded responses."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
from pydantic import SecretStr
import pytest

from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanResponse
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.llm_explanation_service import (
    GEMINI_DEGRADED_MESSAGE,
    LLMExplanationService,
)
from app.core.config import Settings


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def _service(monkeypatch, responses):
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    settings = Settings(
        _env_file=None,
        gemini_api_key=SecretStr(f"mock-key-{uuid.uuid4().hex}"),
        gemini_request_timeout_seconds=1,
    )
    service = LLMExplanationService(settings=settings)
    service.reserve_durable_budget = lambda *_args, **_kwargs: True
    calls = []
    pending = list(responses)

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            calls.append(1)
            result = pending.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result

    monkeypatch.setattr("app.services.llm_explanation_service.httpx.Client", Client)
    return service, calls


def _json_call(service):
    return service.generate_structured_json(
        system_instruction="classify",
        user_content="PRIVATE_PROMPT_SENTINEL",
        request_key="hashed-mock-key",
    )


def test_bad_request_is_not_retried_and_logs_no_prompt_or_secret(monkeypatch, caplog):
    service, calls = _service(monkeypatch, [FakeResponse(400, {"error": {"message": "private server text"}})])
    assert _json_call(service) is None
    assert calls == [1]
    assert service.last_provider_error_class == "bad_request"
    assert "PRIVATE_PROMPT_SENTINEL" not in caplog.text
    assert service.api_key not in caplog.text


@pytest.mark.parametrize("status_code", [401, 403])
def test_unauthorized_key_is_marked_unusable_without_retry(monkeypatch, status_code):
    service, calls = _service(monkeypatch, [FakeResponse(status_code, {})])
    assert _json_call(service) is None
    assert service.last_provider_error_class == "invalid_key"
    assert calls == [1]
    assert service.is_available() is False
    assert service.last_provider_error_class == "invalid_key"


def test_per_minute_429_retries_once_after_provider_delay(monkeypatch):
    service, calls = _service(monkeypatch, [
        FakeResponse(429, {"error": {"details": [
            {"quotaId": "GenerateRequestsPerMinutePerProject"},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0.75s"},
        ]}}),
        FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": '{"intent":"general_explanation"}'}]}}]}),
    ])
    delays = []
    monkeypatch.setattr("app.services.llm_explanation_service.time.sleep", delays.append)
    assert _json_call(service) == {"intent": "general_explanation"}
    assert calls == [1, 1]
    assert delays == [0.75]


def test_daily_project_429_is_not_retried(monkeypatch):
    service, calls = _service(monkeypatch, [FakeResponse(429, {"error": {"details": [
        {"quotaId": "GenerateRequestsPerDayPerProject"},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1s"},
    ]}})])
    assert _json_call(service) is None
    assert calls == [1]
    assert service.last_provider_error_class == "daily_project_quota"


def test_server_errors_retry_twice_with_bounded_backoff_then_succeed(monkeypatch):
    success = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": '{"intent":"general_explanation"}'}]}}]})
    service, calls = _service(monkeypatch, [FakeResponse(503), FakeResponse(502), success])
    delays = []
    monkeypatch.setattr("app.services.llm_explanation_service.time.sleep", delays.append)
    monkeypatch.setattr("app.services.llm_explanation_service.random.uniform", lambda *_args: 0.1)
    assert _json_call(service) == {"intent": "general_explanation"}
    assert len(calls) == 3
    assert delays == [0.35, 0.6]


def test_server_errors_stop_after_two_retries_when_all_attempts_fail(monkeypatch):
    service, calls = _service(monkeypatch, [FakeResponse(503), FakeResponse(502), FakeResponse(500)])
    delays = []
    monkeypatch.setattr("app.services.llm_explanation_service.time.sleep", delays.append)
    monkeypatch.setattr("app.services.llm_explanation_service.random.uniform", lambda *_args: 0.0)
    assert _json_call(service) is None
    assert len(calls) == 3
    assert len(delays) == 2
    assert service.last_provider_error_class == "server_error"


def test_timeout_retries_twice_then_returns_controlled_error(monkeypatch):
    service, calls = _service(monkeypatch, [
        httpx.ReadTimeout("secret endpoint detail"),
        httpx.ReadTimeout("secret endpoint detail"),
        httpx.ReadTimeout("secret endpoint detail"),
    ])
    delays = []
    monkeypatch.setattr("app.services.llm_explanation_service.time.sleep", delays.append)
    monkeypatch.setattr("app.services.llm_explanation_service.random.uniform", lambda *_args: 0.0)
    assert _json_call(service) is None
    assert len(calls) == 3
    assert service.last_provider_error_class == "timeout"
    assert len(delays) == 2


def test_blocked_and_empty_outputs_fail_without_retry(monkeypatch):
    blocked, blocked_calls = _service(monkeypatch, [FakeResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}})])
    assert _json_call(blocked) is None
    assert blocked.last_provider_error_class == "blocked_output"
    assert blocked_calls == [1]

    empty, empty_calls = _service(monkeypatch, [FakeResponse(200, {"candidates": []})])
    assert _json_call(empty) is None
    assert empty.last_provider_error_class == "empty_output"
    assert empty_calls == [1]


def test_general_provider_exhaustion_returns_degraded_friendly_message():
    plan = IntelligencePlanResponse(
        request_id="plan-mock", user_message="What is Python used for?", portal_type="individual",
        intent="general_explanation", intent_confidence=0.9, intent_explanation="mock",
        plan_status="ready_to_execute",
    )

    class FailedGemini:
        last_error_class = "provider_error"
        last_provider_error_class = "server_error"

        @staticmethod
        def is_available():
            return True

        def generate_grounded_explanation(self, **_kwargs):
            self.last_error_class = "provider_error"
            self.last_provider_error_class = "server_error"
            return None

    service = object.__new__(ExecutionOrchestratorService)
    service.conversation_store = SimpleNamespace(
        check_conversation_access=lambda *_args, **_kwargs: (True, None),
        get_conversation=lambda *_args, **_kwargs: None,
    )
    service.intent_planner = SimpleNamespace(create_plan=lambda *_args, **_kwargs: plan)
    service.llm_service = FailedGemini()
    service._record_conversation_turn = lambda *_args, **_kwargs: None
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="What is Python used for?", conversation_id="mock-conversation",
    ))
    assert response.degraded is True
    assert response.answer == GEMINI_DEGRADED_MESSAGE
    assert response.status == "unavailable"
    assert response.reason_codes == ["GEMINI_PROVIDERS_UNAVAILABLE"]

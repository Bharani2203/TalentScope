"""Mocked tests for the live-check diagnostic and primary Gemini client wiring."""

from __future__ import annotations

import logging

from pydantic import SecretStr
import pytest

from app.core.config import Settings
from app.scripts import check_gemini_live
from app.services.llm_explanation_service import LLMExplanationService


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeHTTPClient:
    response = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
    post_calls = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, *, json, headers):
        type(self).post_calls.append((url, json, headers))
        return type(self).response


def _settings():
    return Settings(
        _env_file=None,
        gemini_api_key=SecretStr("mock-secret-never-print"),
        gemini_request_timeout_seconds=1,
        gemini_model="mock-gemini-model",
    )


def test_gemini_model_setting_default_and_environment_override(monkeypatch):
    assert Settings(_env_file=None).gemini_model == "gemini-3.5-flash-lite"
    monkeypatch.setenv("GEMINI_MODEL", "mock-model-from-env")
    assert Settings(_env_file=None).gemini_model == "mock-model-from-env"


def test_assistant_client_uses_and_logs_configured_model(caplog):
    with caplog.at_level(logging.INFO, logger="app.services.llm_explanation_service"):
        service = LLMExplanationService(settings=_settings())

    assert service.model_name == "mock-gemini-model"
    assert "Gemini configured model=mock-gemini-model" in caplog.text
    assert "mock-secret-never-print" not in caplog.text


def test_check_uses_one_mocked_assistant_request_and_does_not_print_key(monkeypatch, capsys):
    FakeHTTPClient.post_calls = []
    FakeHTTPClient.response = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    monkeypatch.setattr(check_gemini_live.llm_explanation_service.httpx, "Client", FakeHTTPClient)

    result = check_gemini_live.run_check(_settings())

    assert result["success"] is True
    assert result["reply"] == "OK"
    assert len(FakeHTTPClient.post_calls) == 1
    assert "mock-secret-never-print" not in capsys.readouterr().out
    url, body, headers = FakeHTTPClient.post_calls[0]
    assert url.endswith("/models/mock-gemini-model:generateContent")
    assert "Reply with the word OK" in body["contents"][0]["parts"][0]["text"]
    assert headers["x-goog-api-key"] == "mock-secret-never-print"


def test_check_reports_mocked_quota_classification_without_response_body(monkeypatch):
    FakeHTTPClient.post_calls = []
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    FakeHTTPClient.response = FakeResponse(
        429,
        {"error": {"message": "quota exhausted", "details": [{"quotaId": "GenerateRequestsPerMinutePerProject"}]}},
    )
    monkeypatch.setattr(check_gemini_live.llm_explanation_service.httpx, "Client", FakeHTTPClient)

    result = check_gemini_live.run_check(_settings())

    assert result["success"] is False
    assert result["error_class"] == "per_minute_quota"
    assert result["http_status"] == 429
    assert result["looks_like"] == "per-minute 429"
    assert "quota exhausted" not in str(result)


def test_main_prints_only_the_allowed_mocked_result_fields(monkeypatch, capsys):
    FakeHTTPClient.post_calls = []
    FakeHTTPClient.response = FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    monkeypatch.setattr(check_gemini_live, "Settings", lambda **_kwargs: _settings())
    monkeypatch.setattr(check_gemini_live.llm_explanation_service.httpx, "Client", FakeHTTPClient)

    check_gemini_live.main()

    output = capsys.readouterr().out
    assert output.splitlines() == ["result: success", "error_class: none"]
    assert len(FakeHTTPClient.post_calls) == 1
    assert "mock-secret-never-print" not in output


@pytest.mark.parametrize("status_code", [400, 404])
def test_live_check_prints_only_mocked_google_error_message_for_400_404(monkeypatch, capsys, status_code):
    FakeHTTPClient.post_calls = []
    FakeHTTPClient.response = FakeResponse(
        status_code,
        {
            "error": {
                "code": 404,
                "message": "Model mock-secret-never-print is not available",
                "status": "NOT_FOUND",
                "details": [{"debug": "do-not-print-this-detail"}],
            }
        },
    )
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    monkeypatch.setattr(check_gemini_live, "Settings", lambda **_kwargs: _settings())
    monkeypatch.setattr(check_gemini_live.llm_explanation_service.httpx, "Client", FakeHTTPClient)

    check_gemini_live.main()

    output = capsys.readouterr().out
    assert output.splitlines() == ["result: failure", "error_class: bad_request" if status_code == 400 else "error_class: http_error"]
    assert len(FakeHTTPClient.post_calls) == 1
    assert "do-not-print-this-detail" not in output
    assert "mock-secret-never-print" not in output


def test_assistant_http_failures_log_class_and_status_at_warning_and_fall_back(monkeypatch, caplog):
    monkeypatch.setenv("RUN_LIVE_LLM_TESTS", "1")
    service = LLMExplanationService(settings=_settings())
    service.reserve_durable_budget = lambda *_args, **_kwargs: True
    FakeHTTPClient.response = FakeResponse(400, {"error": {"message": "invalid model"}})
    monkeypatch.setattr(check_gemini_live.llm_explanation_service.httpx, "Client", FakeHTTPClient)

    with caplog.at_level(logging.WARNING, logger="app.services.llm_explanation_service"):
        structured = service.generate_structured_json(
            system_instruction="extract",
            user_content="mocked input",
            request_key="mocked-request",
        )
        grounded = service.generate_grounded_explanation(
            user_message="mocked question",
            intent="general_knowledge",
            facts=[],
            evidence=[],
            general_knowledge=True,
        )

    assert structured is None
    assert grounded is None
    assert caplog.text.count("error_class=bad_request http_status=400") == 2
    assert all(record.levelno == logging.WARNING for record in caplog.records)

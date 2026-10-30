import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.learning_gemini_service import LearningGeminiService


@pytest.fixture(autouse=True)
def clear_learning_gemini_state():
    LearningGeminiService._calls.clear()
    LearningGeminiService._daily_count = 0
    LearningGeminiService._day_key = ""
    LearningGeminiService._user_calls.clear()
    LearningGeminiService._cache.clear()
    LearningGeminiService._inflight.clear()


def settings(**updates):
    values = {
        "_env_file": None,
        "learning_gemini_api_key": SecretStr("learning-test-secret"),
        "learning_gemini_model": "gemini-3.8-flash",
    }
    values.update(updates)
    return Settings(**values)


def inputs():
    return {
        "plan_type": "skill", "target_role": None, "target_duration_days": 60,
        "target_duration_weeks": None, "weekly_learning_time": "2 hours",
        "preferences": ["Practice"], "taxonomy_source": None,
        "taxonomy_reference_id": None, "taxonomy_version": "registry-v1",
        "items": [{"skill_name": "C", "skill_id": "c", "starting_level": "beginner", "level_evidence": "self_reported_onboarding", "verified_resource_ids": []}],
    }


def provider_response(text, status=200):
    class Response:
        status_code = status

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": text}]}}]}

    return Response()


def valid_json():
    return json.dumps({"items": [{
        "skill_name": "C",
        "learning_objectives": ["Use variables and expressions", "Organize a small program"],
        "practice_activity": "Write a small command-line program and test its inputs.",
        "estimated_minutes": 45,
    }]})


def test_learning_key_isolated_validated_and_cached_without_leaking_to_payload_or_logs(caplog):
    calls = []

    def sender(url, **kwargs):
        calls.append((url, kwargs))
        return provider_response(valid_json())

    service = LearningGeminiService(settings(), sender=sender)
    caplog.set_level(logging.INFO)
    first = service.enrich(user_id="user-a", inputs=inputs())
    second = service.enrich(user_id="user-b", inputs=inputs())

    assert first == second
    assert len(calls) == 1
    url, request = calls[0]
    assert "learning-test-secret" not in url
    assert request["headers"]["x-goog-api-key"] == "learning-test-secret"
    assert "learning-test-secret" not in json.dumps(request["json"])
    assert "learning-test-secret" not in caplog.text
    assert "cache_hit" in caplog.text
    assert first[0]["estimated_minutes"] == 45


def test_missing_learning_key_uses_no_provider_call():
    sent = []
    service = LearningGeminiService(settings(learning_gemini_api_key=None), sender=lambda *args, **kwargs: sent.append(1))
    assert service.enrich(user_id="user-a", inputs=inputs()) is None
    assert sent == []


@pytest.mark.parametrize("result", [
    "timeout", "quota", "provider-error", "malformed", "wrong-skill", "off-goal", "invalid-schema",
])
def test_provider_failure_quota_and_untrusted_output_return_deterministic_fallback(result):
    sent = []

    def sender(url, **kwargs):
        sent.append(url)
        if result == "timeout":
            raise httpx.TimeoutException("private timeout detail")
        if result == "quota":
            return provider_response("", status=429)
        if result == "provider-error":
            return provider_response("", status=503)
        if result == "malformed":
            return provider_response("not json")
        data = json.loads(valid_json())
        if result == "wrong-skill":
            data["items"][0]["skill_name"] = "Python"
        if result == "off-goal":
            data["items"][0]["learning_objectives"][0] = "Prepare for UI/UX Designer interviews and job applications"
        if result == "invalid-schema":
            data["items"][0]["resource_url"] = "https://untrusted.example/"
        return provider_response(json.dumps(data))

    service = LearningGeminiService(settings(), sender=sender)
    assert service.enrich(user_id=f"user-{result}", inputs=inputs()) is None
    assert len(sent) == 1  # Quota errors are never retried.


def test_zero_application_budget_blocks_provider_call():
    sent = []
    service = LearningGeminiService(settings(learning_gemini_max_calls_per_minute=0), sender=lambda *args, **kwargs: sent.append(1))
    assert service.enrich(user_id="user-a", inputs=inputs()) is None
    assert sent == []

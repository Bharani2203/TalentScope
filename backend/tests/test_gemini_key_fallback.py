"""Unit tests for sequential Gemini API key fallback and rate limit failover."""

import logging
from unittest.mock import MagicMock, patch
import pytest

from app.services.supervisor_agent import (
    get_configured_gemini_keys,
    mask_api_key,
    execute_gemini_request_with_fallback,
    synthesize_general_qa_answer,
    synthesize_tool_response_with_gemini,
    try_gemini_function_calling,
    ChatMessage,
    UserContext,
)


def test_mask_api_key():
    assert mask_api_key("") == "***"
    assert mask_api_key(None) == "***"
    assert mask_api_key("12345") == "***"
    assert mask_api_key("AIzaSyDummyTestKeyForUnitTestingOnly1234567") == "AIza...4567"
    assert mask_api_key("invalid_key_1234") == "inva...1234"


def test_get_configured_gemini_keys_priority_and_filtering(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_key_here")
    monkeypatch.setenv("GEMINI_API_A_KEY", "key_alpha_12345678")
    monkeypatch.setenv("GEMINI_API_B_KEY", "key_beta_12345678")
    monkeypatch.setenv("GEMINI_API_C_KEY", "key_gamma_12345678")
    monkeypatch.setenv("GOOGLE_API_KEY", "key_google_12345678")

    keys = get_configured_gemini_keys()
    # your_key_here must be filtered out
    assert "your_key_here" not in keys
    # Priority order must be preserved: A, B, C, Google
    assert keys == [
        "key_alpha_12345678",
        "key_beta_12345678",
        "key_gamma_12345678",
        "key_google_12345678",
    ]


def test_get_configured_gemini_keys_primary_valid(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "primary_valid_key_1234")
    monkeypatch.setenv("GEMINI_API_A_KEY", "key_alpha_12345678")
    monkeypatch.setenv("GEMINI_API_B_KEY", "key_beta_12345678")
    monkeypatch.setenv("GEMINI_API_C_KEY", "")

    keys = get_configured_gemini_keys()
    assert keys[0] == "primary_valid_key_1234"
    assert keys[1] == "key_alpha_12345678"
    assert keys[2] == "key_beta_12345678"
    assert len(keys) == 3


def test_fallback_when_primary_key_is_invalid_401(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "invalid_primary_key_9999")
    monkeypatch.setenv("GEMINI_API_A_KEY", "valid_backup_key_aaaa")
    monkeypatch.delenv("GEMINI_API_B_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_C_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    call_keys = []

    def fake_post(url, json=None, timeout=None):
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        key_used = params.get("key", [""])[0]
        call_keys.append(key_used)
        if key_used == "invalid_primary_key_9999":
            return MockResponse(401, {"error": {"message": "API key not valid"}})
        elif key_used == "valid_backup_key_aaaa":
            return MockResponse(200, {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Success from backup key A!"}]
                    }
                }]
            })
        return MockResponse(500, {})

    mock_client = MagicMock()
    mock_client.post.side_effect = fake_post
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("httpx.Client", return_value=mock_client):
        with caplog.at_level(logging.WARNING):
            result = execute_gemini_request_with_fallback({"contents": []}, candidate_models=["gemini-1.5-flash"])

    assert result is not None
    assert result["candidates"][0]["content"]["parts"][0]["text"] == "Success from backup key A!"
    assert call_keys == ["invalid_primary_key_9999", "valid_backup_key_aaaa"]
    # Check required log format: Key {masked_key} failed with status {status_code}. Trying next key...
    assert any("Key inva...9999 failed with status 401. Trying next key..." in record.message for record in caplog.records)


def test_fallback_when_rate_limited_429(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "primary_key_rate_limited_1111")
    monkeypatch.setenv("GEMINI_API_A_KEY", "backup_key_success_2222")
    monkeypatch.delenv("GEMINI_API_B_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_C_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    call_keys = []

    def fake_post(url, json=None, timeout=None):
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        key_used = params.get("key", [""])[0]
        call_keys.append(key_used)
        if key_used == "primary_key_rate_limited_1111":
            return MockResponse(429, {"error": {"message": "Resource exhausted"}})
        elif key_used == "backup_key_success_2222":
            return MockResponse(200, {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Recovered from 429!"}]
                    }
                }]
            })
        return MockResponse(500, {})

    mock_client = MagicMock()
    mock_client.post.side_effect = fake_post
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("httpx.Client", return_value=mock_client):
        with caplog.at_level(logging.WARNING):
            result = execute_gemini_request_with_fallback({"contents": []}, candidate_models=["gemini-1.5-flash"])

    assert result is not None
    assert result["candidates"][0]["content"]["parts"][0]["text"] == "Recovered from 429!"
    assert any("Key prim...1111 failed with status 429. Trying next key..." in record.message for record in caplog.records)


def test_synthesize_general_qa_with_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad_key_1111")
    monkeypatch.setenv("GEMINI_API_A_KEY", "good_key_2222")
    monkeypatch.delenv("GEMINI_API_B_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_C_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    def fake_post(url, json=None, timeout=None):
        import urllib.parse
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        key = params.get("key", [""])[0]
        if key == "bad_key_1111":
            return MockResponse(403, {})
        return MockResponse(200, {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Machine Learning is an application of AI.\n\n### Next Steps\n- How to train models?\n- What are hyperparameters?"}]
                }
            }]
        })

    mock_client = MagicMock()
    mock_client.post.side_effect = fake_post
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("httpx.Client", return_value=mock_client):
        answer = synthesize_general_qa_answer("What is machine learning?", {})

    assert "Machine Learning is an application of AI" in answer
    assert "### Next Steps" in answer


def test_synthesize_tool_response_with_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad_key_1111")
    monkeypatch.setenv("GEMINI_API_A_KEY", "good_key_2222")
    monkeypatch.delenv("GEMINI_API_B_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_C_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    def fake_post(url, json=None, timeout=None):
        import urllib.parse
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        key = params.get("key", [""])[0]
        if key == "bad_key_1111":
            return MockResponse(401, {})
        return MockResponse(200, {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "### What I Understood\nTarget\n\n### What I Checked\nSource\n\n### Results\nJobs\n\n### Next Steps\n- What certifications help?\n- How to practice?"
                    }]
                }
            }]
        })

    mock_client = MagicMock()
    mock_client.post.side_effect = fake_post
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch("httpx.Client", return_value=mock_client):
        ans, followups = synthesize_tool_response_with_gemini(
            user_query="find python jobs",
            tool_name="fetch_live_job_openings",
            answer_md="Found 3 jobs",
            role_disp="Python Developer",
            loc_disp="India",
            checked_text="ATS feeds",
            fallback_followups=["Fallback 1", "Fallback 2"],
        )

    assert "What I Understood" in ans
    assert len(followups) == 2
    assert "What certifications help?" in followups


def test_try_gemini_function_calling_with_fallback(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad_key_1111")
    monkeypatch.setenv("GEMINI_API_A_KEY", "good_key_2222")
    monkeypatch.delenv("GEMINI_API_B_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_C_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)

    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data
            self.text = str(json_data)

        def json(self):
            return self._json_data

    def fake_post(url, json=None, timeout=None):
        import urllib.parse
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        key = params.get("key", [""])[0]
        if key == "bad_key_1111":
            return MockResponse(503, {})
        return MockResponse(200, {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "### What I Understood\nHere is your general advice.\n\n### Next Steps\n- Question 1\n- Question 2"
                    }]
                }
            }]
        })

    mock_client = MagicMock()
    mock_client.post.side_effect = fake_post
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    messages = [ChatMessage(role="user", content="Give me general advice")]
    user_context = UserContext()
    resolved = {"latest_prompt": "Give me general advice"}

    with patch("httpx.Client", return_value=mock_client):
        resp = try_gemini_function_calling(messages, user_context, resolved)

    assert resp is not None
    assert "Here is your general advice" in resp.answer
    assert resp.intent == "GENERAL_QA"



def test_concept_comparison_graceful_offline_fallback(monkeypatch):
    """Verify that when external AI service fails or is unreachable,
    queries like 'AI Engineer vs data scientist' return a clean, graceful
    Markdown response with intent CONCEPT_COMPARISON and suggested_questions.
    """
    import asyncio
    from app.services.supervisor_agent import run_supervisor_agent

    # Force offline test mode so external calls are skipped
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")

    messages = [ChatMessage(role="user", content="AI Engineer vs data scientist")]
    user_context = UserContext()

    response = asyncio.run(run_supervisor_agent(messages, user_context))

    assert response.intent == "CONCEPT_COMPARISON"
    assert "### Connectivity Issue" in response.answer
    assert "**AI Engineer vs Data Scientist**" in response.answer
    assert "Error: Unable to connect" not in response.answer
    assert "What is an AI Engineer?" in response.suggested_questions
    assert "What does a Data Scientist do?" in response.suggested_questions
    assert response.suggested_questions == response.suggested_followups

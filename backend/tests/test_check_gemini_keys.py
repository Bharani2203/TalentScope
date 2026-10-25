"""Mocked tests for the Gemini API key diagnostic (no real network calls)."""

from __future__ import annotations

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.scripts import check_gemini_keys


def _settings(primary="mock-primary-secret", secondary="mock-secondary-secret"):
    return Settings(
        _env_file=None,
        gemini_api_key=SecretStr(primary) if primary else None,
        gemini_b_api_key=SecretStr(secondary) if secondary else None,
    )


def test_check_makes_one_mocked_get_per_configured_key_and_identifies_primary(monkeypatch):
    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return httpx.Response(200, json={"models": []})

    monkeypatch.setattr(check_gemini_keys.httpx, "get", fake_get)
    results, primary_status = check_gemini_keys.run_check(_settings())

    assert len(calls) == 2
    assert all(call[0] == check_gemini_keys.MODELS_URL for call in calls)
    assert calls[0][1] == {"x-goog-api-key": "mock-primary-secret"}
    assert calls[1][1] == {"x-goog-api-key": "mock-secondary-secret"}
    assert results["GEMINI_API_KEY"]["verdict"] == "valid"
    assert results["GEMINI_B_API_KEY"]["verdict"] == "valid"
    assert primary_status == "valid"


def test_error_message_redacts_key_and_403_verdict_is_specific(monkeypatch):
    key = "mock-primary-secret"

    def fake_get(_url, *, headers, timeout):
        return httpx.Response(
            403,
            json={"error": {"message": f"Rejected credential {headers['x-goog-api-key']}"}},
        )

    monkeypatch.setattr(check_gemini_keys.httpx, "get", fake_get)
    results = check_gemini_keys.check_keys(_settings(secondary=None))

    assert results["GEMINI_API_KEY"]["verdict"] == "API not enabled or key restricted (403)"
    assert results["GEMINI_API_KEY"]["error_message"] == "Rejected credential [REDACTED]"
    assert key not in results["GEMINI_API_KEY"]["error_message"]


def test_main_prints_only_key_metadata_and_primary_validity(monkeypatch, capsys):
    monkeypatch.setattr(check_gemini_keys, "run_check", lambda: ({
        "GEMINI_API_KEY": {
            "key_length": 19,
            "key_prefix": "mock",
            "http_status": 200,
            "error_message": "",
            "verdict": "valid",
        },
    }, "valid"))

    check_gemini_keys.main()
    output = capsys.readouterr().out

    assert "variable: GEMINI_API_KEY" in output
    assert "key_length: 19" in output
    assert "first_4: mock" in output
    assert "verdict: valid" in output
    assert "primary_assistant_key: GEMINI_API_KEY" in output
    assert "primary_assistant_key_validity: valid" in output
    assert "mock-primary-secret" not in output
    assert "mock-secondary-secret" not in output


def test_settings_load_backend_dotenv_path_like_live_check(monkeypatch):
    captured = {}

    def fake_settings(**kwargs):
        captured.update(kwargs)
        return _settings()

    monkeypatch.setattr(check_gemini_keys, "Settings", fake_settings)
    monkeypatch.setattr(check_gemini_keys, "check_keys", lambda _settings: {
        "GEMINI_API_KEY": {"verdict": "valid"},
    })

    results, primary_status = check_gemini_keys.run_check()

    assert captured["_env_file"].name == ".env"
    assert captured["_env_file"].parent.name == "backend"
    assert captured["_env_file_encoding"] == "utf-8"
    assert results["GEMINI_API_KEY"]["verdict"] == "valid"
    assert primary_status == "valid"

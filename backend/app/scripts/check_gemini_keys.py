"""Check configured Gemini API keys with one mocked-safe models-list GET each."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings


MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
KEY_SETTINGS = (
    ("GEMINI_API_KEY", "gemini_api_key"),
    ("GEMINI_B_API_KEY", "gemini_b_api_key"),
)


def _google_error_message(payload: Any, key: str) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return ""
    return " ".join(message.replace(key, "[REDACTED]").split())


def _verdict(status: int | None) -> str:
    if status == 200:
        return "valid"
    if status in {400, 401}:
        return "invalid key"
    if status == 403:
        return "API not enabled or key restricted (403)"
    if status == 429:
        return "quota (429)"
    return "unverified"


def check_keys(settings: Settings) -> dict[str, dict[str, Any]]:
    """Make one models-list request per configured key; never log key material."""
    results: dict[str, dict[str, Any]] = {}
    for variable_name, setting_name in KEY_SETTINGS:
        secret = getattr(settings, setting_name)
        if secret is None:
            continue
        key = secret.get_secret_value()
        status: int | None = None
        message = ""
        try:
            response = httpx.get(
                MODELS_URL,
                headers={"x-goog-api-key": key},
                timeout=10,
            )
            status = response.status_code
            if status != 200:
                try:
                    message = _google_error_message(response.json(), key)
                except (ValueError, TypeError):
                    message = ""
        except httpx.HTTPError:
            # Do not include exception text: it may contain request headers.
            pass
        results[variable_name] = {
            "key_length": len(key),
            "key_prefix": key[:4],
            "http_status": status,
            "error_message": message,
            "verdict": _verdict(status),
        }
    return results


def run_check(settings: Settings | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    if settings is None:
        settings = Settings(
            _env_file=Path(__file__).resolve().parents[2] / ".env",
            _env_file_encoding="utf-8",
        )
    results = check_keys(settings)
    primary_name = "GEMINI_API_KEY"
    primary_result = results.get(primary_name)
    primary_status = primary_result["verdict"] if primary_result else "not configured"
    return results, primary_status


def main() -> None:
    try:
        results, primary_status = run_check()
    except Exception:
        # Keep diagnostics free of settings values and request exception text.
        results, primary_status = {}, "check failed"

    for variable_name, _setting_name in KEY_SETTINGS:
        result = results.get(variable_name)
        if result is None:
            print(f"variable: {variable_name}")
            print("status: not configured")
            continue
        print(f"variable: {variable_name}")
        print(f"key_length: {result['key_length']}")
        print(f"first_4: {result['key_prefix']}")
        print(f"http_status: {result['http_status'] if result['http_status'] is not None else 'N/A'}")
        if result["error_message"]:
            print(f"error.message: {result['error_message']}")
        print(f"verdict: {result['verdict']}")

    print("primary_assistant_key: GEMINI_API_KEY")
    print(f"primary_assistant_key_validity: {primary_status}")


if __name__ == "__main__":
    main()

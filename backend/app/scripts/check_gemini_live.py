"""Make one bounded live Gemini check through the assistant's existing client."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any

from app.core.config import Settings
from app.services import llm_explanation_service


PROMPT = "Reply with the word OK"


def _failure_looks_like(status: int | None, payload: Any) -> str:
    if status == 429:
        try:
            details = json.dumps(payload, ensure_ascii=True, default=str).casefold()
        except (TypeError, ValueError):
            details = str(payload).casefold()
        if any(token in details for token in ("perday", "per_day", "per day", "daily")):
            return "daily 429"
        if any(token in details for token in ("perminute", "per_minute", "per minute", "per-minute")):
            return "per-minute 429"
        return "429 quota; daily or per-minute unclear"
    if status in {401, 403}:
        return "401/403 (bad key)"
    if status == 400:
        return "400 (bad model/request)"
    if status is not None and 500 <= status <= 599:
        return "5xx server error"
    if status == 200:
        return "none of the listed HTTP failure categories"
    if status is None:
        return "no HTTP response"
    return "other HTTP failure"


def _google_error_message(payload: Any, api_key: str | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        return None
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return " ".join(message.split())


def run_check(settings: Settings | None = None) -> dict[str, Any]:
    """Run the assistant request path while replacing only its Firestore budget gate."""
    settings = settings or Settings(
        _env_file=Path(__file__).resolve().parents[2] / ".env",
        _env_file_encoding="utf-8",
    )
    service = llm_explanation_service.LLMExplanationService(settings=settings)
    service.max_retries = 0
    service.max_rate_limit_retries = 0
    # A diagnostic invocation must not read or write the assistant's Firestore
    # usage ledger. The process is short-lived and the check is limited to one call.
    service.reserve_durable_budget = lambda *_args, **_kwargs: True
    llm_explanation_service.LLMExplanationService._cache.clear()
    llm_explanation_service.LLMExplanationService._inflight_keys.clear()

    outcome: dict[str, Any] = {"http_status": None, "error_payload": None, "transport_error_class": None}
    real_http_client = llm_explanation_service.httpx.Client

    class CapturingHTTPClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._client = real_http_client(*args, **kwargs)

        def __enter__(self):
            self._client.__enter__()
            return self

        def __exit__(self, exc_type, exc, traceback):
            return self._client.__exit__(exc_type, exc, traceback)

        def post(self, *args: Any, **kwargs: Any):
            try:
                response = self._client.post(*args, **kwargs)
            except Exception as exc:
                outcome["transport_error_class"] = type(exc).__name__
                raise
            outcome["http_status"] = getattr(response, "status_code", None)
            if outcome["http_status"] != 200:
                try:
                    outcome["error_payload"] = response.json()
                except Exception:
                    outcome["error_payload"] = None
            return response

    prior_offline_mode = os.environ.pop("TALENTSCOPE_OFFLINE_TEST_MODE", None)
    prior_logging_disable = logging.root.manager.disable
    started = time.perf_counter()
    try:
        # This is an explicitly invoked live diagnostic. Clearing the offline
        # flag only in this process allows the assistant client to send its one
        # request; no Firebase or Firestore client is initialized here.
        llm_explanation_service.httpx.Client = CapturingHTTPClient
        logging.disable(logging.CRITICAL)
        reply = service.generate_grounded_explanation(
            user_message=PROMPT,
            intent="general_knowledge",
            facts=[],
            evidence=[],
            general_knowledge=True,
            user_id="gemini-live-check",
        )
    finally:
        llm_explanation_service.httpx.Client = real_http_client
        logging.disable(prior_logging_disable)
        if prior_offline_mode is not None:
            os.environ["TALENTSCOPE_OFFLINE_TEST_MODE"] = prior_offline_mode
    latency_ms = round((time.perf_counter() - started) * 1000)

    if isinstance(reply, str) and reply.strip():
        safe_reply = reply.replace(service.api_key or "\0", "[redacted]")
        return {
            "model": service.model_name,
            "success": True,
            "latency_ms": latency_ms,
            "reply": " ".join(safe_reply.split())[:100],
        }

    status = outcome["http_status"]
    if outcome["transport_error_class"]:
        error_class = outcome["transport_error_class"]
    elif service.last_provider_error_class:
        error_class = service.last_provider_error_class
    elif status is not None and status != 200:
        error_class = "HTTPError"
    elif not service.api_key:
        error_class = "MissingAPIKey"
    else:
        error_class = service.last_provider_error_class or service.last_error_class or "ProviderError"
    result = {
        "model": service.model_name,
        "success": False,
        "latency_ms": latency_ms,
        "reply": "",
        "error_class": error_class,
        "http_status": status if status is not None else "N/A",
        "looks_like": _failure_looks_like(status, outcome["error_payload"]),
    }
    if status in {400, 404}:
        result["google_error_message"] = _google_error_message(outcome["error_payload"], service.api_key)
    return result


def main() -> None:
    prior_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    started = time.perf_counter()
    settings = None
    try:
        settings = Settings(
            _env_file=Path(__file__).resolve().parents[2] / ".env",
            _env_file_encoding="utf-8",
        )
        result = run_check(settings)
    except Exception as exc:
        result = {
            "model": settings.gemini_model if settings is not None else "unavailable",
            "success": False,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "reply": "",
            "error_class": type(exc).__name__,
            "http_status": "N/A",
            "looks_like": "local configuration or client error",
        }
    finally:
        logging.disable(prior_logging_disable)

    print(f"result: {'success' if result['success'] else 'failure'}")
    print(f"error_class: {result.get('error_class', 'none')}")


if __name__ == "__main__":
    main()

"""Isolated Gemini B provider for explicitly labelled general guidance only.

This module never uses Gemini A settings, its Firestore quota ledger, or raw
conversation text. Calls are opt-in through the dedicated GEMINI_B_API_KEY.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from app.core.config import get_settings
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.services.llm_explanation_service import sanitize_untrusted_text

logger = logging.getLogger(__name__)


class GeminiBGuidanceService:
    """Gemini B guidance with an independent, process-local usage ledger.

    Its limits apply per worker process and reset on restart. They are
    application guardrails, not shared global limits or claims about Google's quota.
    """
    _lock = threading.Lock()
    _calls: deque[float] = deque()
    _daily_count = 0
    _day_key = ""
    _user_calls: dict[str, deque[float]] = {}
    _cache: dict[str, tuple[float, str]] = {}
    _inflight: set[str] = set()
    _cache_ttl = 600

    def __init__(self, settings: Any | None = None, sender: Callable[..., Any] | None = None) -> None:
        self.settings = settings or get_settings()
        self._sender_injected = sender is not None
        self.sender = sender or self._send

    def is_available(self) -> bool:
        # The production HTTP sender is categorically disabled in tests. A
        # test may inject a deterministic local sender to exercise the contract.
        if not self._sender_injected and (
            os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1"
        ):
            return False
        key = self.settings.gemini_b_api_key
        return bool(key and key.get_secret_value().strip())

    @staticmethod
    def _send(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float) -> Any:
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, headers=headers, json=json)

    @classmethod
    def _reserve_budget(cls, user_id: str, settings: Any, now: float) -> bool:
        utc_day = datetime.now(timezone.utc).strftime("%Y%m%d")
        normalized_user_id = str(user_id or "anonymous").strip() or "anonymous"
        user_key = hashlib.sha256(normalized_user_id.encode()).hexdigest()
        with cls._lock:
            if cls._day_key != utc_day:
                cls._day_key, cls._daily_count = utc_day, 0
            while cls._calls and now - cls._calls[0] >= 60:
                cls._calls.popleft()
            for slot, events in list(cls._user_calls.items()):
                while events and now - events[0] >= 3600:
                    events.popleft()
                if not events:
                    cls._user_calls.pop(slot, None)
            if len(cls._calls) >= settings.gemini_b_max_calls_per_minute:
                return False
            if cls._daily_count >= settings.gemini_b_max_calls_per_day:
                return False
            user_events = cls._user_calls.setdefault(user_key, deque())
            while user_events and now - user_events[0] >= 3600:
                user_events.popleft()
            if len(user_events) >= settings.gemini_b_max_calls_per_user_per_hour:
                return False
            cls._calls.append(now)
            cls._daily_count += 1
            user_events.append(now)
            return True

    @staticmethod
    def _valid_text(value: Any, max_chars: int) -> str | None:
        if not isinstance(value, str):
            return None
        text = sanitize_untrusted_text(value, max_chars).strip()
        if not text or re.search(r"\d|https?://|www\.|\[[^]]+\]\(", text, re.I):
            return None
        if re.search(r"\b(?:source|citation|according to|research shows|studies show|top|rank(?:ed|ing)?|most in.demand|fastest.growing|highest.demand|best.paid)\b", text, re.I):
            return None
        return text

    def generate(self, *, capability_id: str, public_skill_name: str | None = None, user_id: str = "anonymous") -> str | None:
        from app.intelligence_v2.capability_registry import canonical_capability_id
        policy = FEATURE_ANSWER_POLICIES.get(capability_id) or FEATURE_ANSWER_POLICIES.get(canonical_capability_id(capability_id, None))
        if not policy or not policy.gemini_b_fallback or policy.provider_data_required or not self.is_available():
            return None
        public_topic = sanitize_untrusted_text(public_skill_name, 80) if public_skill_name else ""
        # Only a taxonomy-resolved skill name may be supplied. Raw user text,
        # roles, geography, profile, company, and employee information never enter this request.
        template = policy.guidance_instruction
        topic_line = f"Public skill topic: {public_topic}\n" if public_topic else ""
        prompt = (
            "Write concise general educational guidance for TalentScope.ai. This is not platform data. "
            "Do not state measurements, dates, rankings, employer hiring, salary, vacancies, or citations. "
            "Do not include URLs, numeric claims, markdown links, or invented sources. Use plain English. "
            "The answer must follow this feature-specific instruction: " + template + "\n" + topic_line
        )
        if len(prompt) > self.settings.gemini_b_max_input_chars:
            return None
        primary_model = str(self.settings.gemini_b_model).strip()
        backup_value = getattr(self.settings, "gemini_b_backup_model", None)
        backup_model = str(backup_value).strip() if backup_value else ""
        if not primary_model:
            return None
        if backup_model == primary_model:
            backup_model = ""
        cache_key = hashlib.sha256(
            f"{capability_id}|{prompt}|{primary_model}|{backup_model}".encode()
        ).hexdigest()
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] < self._cache_ttl:
                return cached[1]
            if cache_key in self._inflight:
                return None
            self._inflight.add(cache_key)
        try:
            key = self.settings.gemini_b_api_key.get_secret_value()
            if not self._reserve_budget(user_id, self.settings, now):
                return None
            text, retryable = self._request_model(primary_model, key, prompt)
            if text:
                pass
            elif retryable and backup_model and self._reserve_budget(user_id, self.settings, time.monotonic()):
                text, _ = self._request_model(backup_model, key, prompt)
            if not text:
                return None
            with self._lock:
                self._cache[cache_key] = (now, text)
                if len(self._cache) > 128:
                    self._cache.pop(next(iter(self._cache)))
            return text
        except Exception as exc:
            logger.info("Gemini B guidance failed (%s)", type(exc).__name__)
            return None
        finally:
            with self._lock:
                self._inflight.discard(cache_key)

    def _request_model(self, model: str, key: str, prompt: str) -> tuple[str | None, bool]:
        """Make one request; return whether a provider/transport failure is retryable."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = self.sender(
                url,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": "Provide general guidance only. Do not fabricate evidence."}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    # Gemini 3 models reject legacy sampling parameters such as temperature.
                    "generationConfig": {"maxOutputTokens": self.settings.gemini_b_max_output_tokens},
                },
                timeout=self.settings.gemini_b_request_timeout_seconds,
            )
        except httpx.TransportError as exc:
            logger.info("Gemini B transport failure (%s)", type(exc).__name__)
            return None, True
        except Exception as exc:
            logger.info("Gemini B request failed (%s)", type(exc).__name__)
            return None, False

        status = getattr(response, "status_code", None)
        if status != 200:
            logger.info("Gemini B guidance unavailable (HTTP %s)", status)
            retryable = status in {408, 500, 502, 503, 504}
            if status == 429:
                retryable = self._is_model_scoped_quota_error(response, model)
            return None, retryable
        try:
            payload = response.json()
            candidates = payload.get("candidates") if isinstance(payload, dict) else None
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            value = parts[0].get("text") if parts and isinstance(parts[0], dict) else None
            return self._valid_text(value, self.settings.gemini_b_max_output_tokens * 8), False
        except Exception as exc:
            logger.info("Gemini B response parse failed (%s)", type(exc).__name__)
            return None, False

    @staticmethod
    def _is_model_scoped_quota_error(response: Any, model: str) -> bool:
        """Retry 429 only when provider metadata identifies a model-specific limit."""
        try:
            payload = response.json()
            error = payload.get("error") if isinstance(payload, dict) else None
            if not isinstance(error, dict):
                return False
            safe_scope = json.dumps(error, ensure_ascii=True, default=str).casefold()
            model_name = model.casefold()
            return (
                model_name in safe_scope
                or "permodel" in safe_scope
                or "model-specific quota" in safe_scope
                or "quota for model" in safe_scope
            )
        except Exception:
            return False

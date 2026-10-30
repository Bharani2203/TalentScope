"""Optional Gemini enrichment for missing Learning roadmap content.

This service only adds objectives, a practical activity, and an explicitly
estimated effort to already selected roadmap milestones. Taxonomy IDs,
assessment evidence, resource URLs, and job-market facts always come from the
existing deterministic services.
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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_CONTENT_VERSION = "learning-roadmap-content-v1"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_MAX_CACHE_ITEMS = 256
_MAX_ENRICHED_MILESTONES = 8
_NO_URL = re.compile(r"(?:https?://|www\.|\[[^]]+\]\()", re.I)
_UNSELECTED_CAREER_CONTEXT = re.compile(
    r"\b(?:ui\s*/?\s*ux|designer|developer|software engineer|job search|first job|career goal|employer|hiring|vacancy)\b",
    re.I,
)


class LearningContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(min_length=1, max_length=160)
    learning_objectives: list[str] = Field(min_length=2, max_length=5)
    practice_activity: str = Field(min_length=10, max_length=1000)
    estimated_minutes: int = Field(ge=15, le=480)

    @field_validator("skill_name", "practice_activity")
    @classmethod
    def reject_links(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if _NO_URL.search(cleaned):
            raise ValueError("generated content must not contain links")
        return cleaned

    @field_validator("learning_objectives")
    @classmethod
    def validate_objectives(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values]
        if any(not value or len(value) > 180 or _NO_URL.search(value) for value in cleaned):
            raise ValueError("invalid generated objective")
        return cleaned


class LearningContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LearningContentItem] = Field(min_length=1, max_length=_MAX_ENRICHED_MILESTONES)


class LearningGeminiService:
    """Isolated, bounded, process-local optional roadmap content helper."""

    _lock = threading.Lock()
    _calls: deque[float] = deque()
    _daily_count = 0
    _day_key = ""
    _user_calls: dict[str, deque[float]] = {}
    _cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _inflight: set[str] = set()

    def __init__(self, settings: Any | None = None, sender: Callable[..., Any] | None = None) -> None:
        self.settings = settings or get_settings()
        self._sender_injected = sender is not None
        self.sender = sender or self._send

    @staticmethod
    def _send(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float) -> Any:
        with httpx.Client(timeout=timeout) as client:
            return client.post(url, headers=headers, json=json)

    def is_available(self) -> bool:
        if not self._sender_injected and (os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1"):
            return False
        key = self.settings.learning_gemini_api_key
        return bool(key and key.get_secret_value().strip())

    @classmethod
    def _reserve_budget(cls, user_id: str, settings: Any, now: float) -> bool:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        user_key = hashlib.sha256(str(user_id or "anonymous").encode()).hexdigest()
        with cls._lock:
            if cls._day_key != day:
                cls._day_key, cls._daily_count = day, 0
            while cls._calls and now - cls._calls[0] >= 60:
                cls._calls.popleft()
            for key, events in list(cls._user_calls.items()):
                while events and now - events[0] >= 3600:
                    events.popleft()
                if not events:
                    cls._user_calls.pop(key, None)
            events = cls._user_calls.setdefault(user_key, deque())
            if (len(cls._calls) >= settings.learning_gemini_max_calls_per_minute
                    or cls._daily_count >= settings.learning_gemini_max_calls_per_day
                    or len(events) >= settings.learning_gemini_max_calls_per_user_per_hour):
                return False
            cls._calls.append(now)
            cls._daily_count += 1
            events.append(now)
            return True

    @staticmethod
    def _cache_key(inputs: dict[str, Any]) -> str:
        normalized = json.dumps(inputs, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode()).hexdigest()

    def enrich(self, *, user_id: str, inputs: dict[str, Any]) -> list[dict[str, Any]] | None:
        if not self.is_available():
            return None
        cache_key = self._cache_key({"content_version": _CONTENT_VERSION, "model": self.settings.learning_gemini_model, **inputs})
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                logger.info("Learning Gemini outcome=cache_hit latency_ms=0")
                return [dict(item) for item in cached[1]]
            if cache_key in self._inflight:
                logger.info("Learning Gemini outcome=inflight_deterministic_fallback")
                return None
            self._inflight.add(cache_key)
        started = time.monotonic()
        outcome = "provider_error"
        try:
            if not self._reserve_budget(user_id, self.settings, now):
                outcome = "application_limit"
                return None
            key = self.settings.learning_gemini_api_key.get_secret_value()
            prompt = self._prompt(inputs)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.learning_gemini_model}:generateContent"
            try:
                response = self.sender(
                    url,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json={
                        "systemInstruction": {"parts": [{"text": "Return only valid JSON. Add learning guidance only for the supplied skills. Do not invent taxonomy IDs, links, assessment outcomes, job facts, or source claims."}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": self.settings.learning_gemini_max_output_tokens},
                    },
                    timeout=self.settings.learning_gemini_request_timeout_seconds,
                )
            except httpx.TimeoutException:
                outcome = "timeout"
                return None
            except httpx.TransportError:
                outcome = "transport_error"
                return None
            except Exception as exc:
                outcome = f"request_error:{type(exc).__name__}"
                return None
            status = getattr(response, "status_code", None)
            if status != 200:
                outcome = "quota_exhausted" if status == 429 else f"http_{status}"
                return None
            try:
                payload = response.json()
                candidates = payload.get("candidates") if isinstance(payload, dict) else None
                parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                raw = parts[0].get("text") if parts and isinstance(parts[0], dict) else None
                data = json.loads(raw) if isinstance(raw, str) else None
                result = LearningContentResponse.model_validate(data)
            except (ValueError, TypeError, IndexError, KeyError, ValidationError):
                outcome = "invalid_output"
                return None
            expected = inputs.get("items", [])
            if len(result.items) != len(expected) or any(
                generated.skill_name.casefold() != expected[index]["skill_name"].casefold()
                for index, generated in enumerate(result.items)
            ):
                outcome = "invalid_skill_mapping"
                return None
            if inputs.get("plan_type") == "skill" and any(
                _UNSELECTED_CAREER_CONTEXT.search(
                    " ".join([item.skill_name, *item.learning_objectives, item.practice_activity])
                )
                for item in result.items
            ):
                outcome = "off_goal_content"
                return None
            value = [item.model_dump() for item in result.items]
            with self._lock:
                self._cache[cache_key] = (time.monotonic(), value)
                if len(self._cache) > _MAX_CACHE_ITEMS:
                    self._cache.pop(next(iter(self._cache)))
            outcome = "success"
            return [dict(item) for item in value]
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info("Learning Gemini outcome=%s latency_ms=%d", outcome, elapsed_ms)
            with self._lock:
                self._inflight.discard(cache_key)

    @staticmethod
    def _prompt(inputs: dict[str, Any]) -> str:
        safe_inputs = json.dumps(inputs, ensure_ascii=True, separators=(",", ":"))
        return (
            "Create learning guidance for the supplied roadmap milestones. Use only the supplied skill names and context. "
            "For each item return its exact skill_name, 2 to 5 short learning_objectives, one practical practice_activity, "
            "and estimated_minutes from 15 to 480. The time is an estimate, not a guarantee. Do not include URLs, "
            "resources, taxonomy IDs, assessment questions or scores, job openings, employers, salaries, market demand, "
            "or unsupported prerequisites. Output JSON shaped as {\"items\":[{\"skill_name\":string,\"learning_objectives\":[string],\"practice_activity\":string,\"estimated_minutes\":integer}]}.\n"
            f"Input: {safe_inputs}"
        )


learning_gemini_service = LearningGeminiService()


def enrich_missing_learning_content(roadmap: Any, request: Any, *, user_id: str) -> bool:
    """Fill missing-resource milestones; never add skills or replace evidence/URLs."""
    missing = [item for item in roadmap.milestones if not any(
        resource.verification_status in {"verified_official", "verified_youtube_listing"}
        for resource in item.resources
    )][: _MAX_ENRICHED_MILESTONES]
    if not missing:
        return False
    unique_items: list[dict[str, Any]] = []
    seen_names = set()
    for item in missing:
        name_key = item.skill_name.casefold()
        if name_key not in seen_names:
            seen_names.add(name_key)
            unique_items.append({
                "skill_name": item.skill_name,
                "skill_id": item.skill_id,
                "starting_level": item.self_reported_level,
                "level_evidence": item.starting_level_source or "not_reported",
                "verified_resource_ids": [resource.resource_id for resource in item.resources
                                          if resource.verification_status in {"verified_official", "verified_youtube_listing"}],
            })
    inputs = {
        "plan_type": request.plan_type,
        "target_role": request.target_role,
        "target_duration_days": request.target_duration_days,
        "target_duration_weeks": request.target_duration_weeks,
        "weekly_learning_time": request.weekly_learning_time or roadmap.profile_context.weekly_learning_time,
        "preferences": list(request.preferences),
        "taxonomy_source": roadmap.taxonomy_source,
        "taxonomy_reference_id": roadmap.taxonomy_reference_id,
        "taxonomy_version": roadmap.taxonomy_version or _CONTENT_VERSION,
        "items": unique_items,
    }
    generated = learning_gemini_service.enrich(user_id=user_id, inputs=inputs)
    if not generated:
        for milestone in missing:
            milestone.content_source = "deterministic"
            milestone.explanation = "Platform-generated practice guidance."
        return False
    for content in generated:
        target_name = content["skill_name"].casefold()
        for milestone in missing:
            if milestone.skill_name.casefold() == target_name or (milestone.skill_id and milestone.skill_id.casefold() == target_name):
                milestone.learning_objectives = content["learning_objectives"]
                milestone.practice_activity = content["practice_activity"]
                milestone.explanation = "AI-generated learning guidance; not assessment evidence."
                milestone.content_source = "learning_gemini"
                milestone.effort = {
                    **(milestone.effort or {}),
                    "estimated_minutes": content["estimated_minutes"],
                    "basis": "AI-suggested effort estimate; not a completion guarantee.",
                    "estimate_source": "learning_gemini",
                }
    return True

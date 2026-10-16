"""Safe read-only client for date-bounded Stack Exchange questions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app.services.external_apis.retry_after import safe_retry_after_seconds


class StackExchangeError(Exception):
    def __init__(self, message: str, *, category: str, backoff: int | None = None):
        super().__init__(message)
        self.category = category
        self.backoff = backoff


@dataclass(frozen=True)
class QuestionsPage:
    items: list[dict[str, Any]]
    has_more: bool
    quota_remaining: int | None
    backoff: int | None
    quota_max: int | None = None


class StackExchangeService:
    endpoint = "https://api.stackexchange.com/2.3/questions"
    page_size = 100
    anonymous_page_limit = 25

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport

    async def questions_page(
        self, *, tag: str, fromdate: int, todate: int, page: int,
        raw_response_callback: Callable[[Any, str | None], Any] | None = None,
    ) -> QuestionsPage:
        params = {
            "site": "stackoverflow",
            "tagged": tag,
            "fromdate": fromdate,
            "todate": todate,
            "sort": "creation",
            "order": "asc",
            "pagesize": self.page_size,
            "page": page,
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(self.endpoint, params=params)
                except httpx.TimeoutException:
                    if attempt < self.max_retries:
                        await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
                        continue
                    raise StackExchangeError("Stack Exchange request timed out.", category="network") from None
                except httpx.RequestError:
                    if attempt < self.max_retries:
                        await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
                        continue
                    raise StackExchangeError("Stack Exchange could not be reached.", category="network") from None

                if response.status_code == 429:
                    retry_after = safe_retry_after_seconds(response.headers.get("Retry-After"))
                    raise StackExchangeError(
                        "Stack Exchange rate limit reached.",
                        category="rate_limit",
                        backoff=int(retry_after) if retry_after else None,
                    )
                if response.status_code in {500, 502, 503, 504} and attempt < self.max_retries:
                    await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
                    continue
                if response.status_code >= 500:
                    raise StackExchangeError("Stack Exchange is temporarily unavailable.", category="server")
                if not response.is_success:
                    raise StackExchangeError("Stack Exchange rejected the request.", category="http")
                break

        try:
            payload = response.json()
        except ValueError:
            raise StackExchangeError("Stack Exchange returned invalid data.", category="schema") from None
        if raw_response_callback is not None:
            raw_response_callback(payload, response.headers.get("content-type"))
        if not isinstance(payload, dict):
            raise StackExchangeError("Stack Exchange returned an unexpected response.", category="schema")
        if payload.get("error_id") is not None:
            error_name = str(payload.get("error_name") or "").casefold()
            category = "rate_limit" if error_name in {
                "throttled", "throttle_violation", "temporarily_unavailable",
            } else "provider"
            backoff = payload.get("backoff")
            safe_backoff = int(backoff) if isinstance(backoff, int) and 0 < backoff <= 3600 else None
            raise StackExchangeError("Stack Exchange reported an application error.", category=category, backoff=safe_backoff)
        items = payload.get("items")
        if not isinstance(items, list) or not isinstance(payload.get("has_more"), bool):
            raise StackExchangeError("Stack Exchange returned an unexpected response structure.", category="schema")
        remaining = payload.get("quota_remaining")
        quota_max = payload.get("quota_max")
        backoff = payload.get("backoff")
        return QuestionsPage(
            items=items,
            has_more=payload["has_more"],
            quota_remaining=remaining if isinstance(remaining, int) else None,
            backoff=int(backoff) if isinstance(backoff, int) and 0 < backoff <= 3600 else None,
            quota_max=quota_max if isinstance(quota_max, int) else None,
        )

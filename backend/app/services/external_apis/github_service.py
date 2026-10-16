"""Small, secret-safe client for GitHub repository topic search."""

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app.core.config import Settings, get_settings
from app.services.external_apis.retry_after import safe_retry_after_seconds


@dataclass(frozen=True)
class GitHubTopicCount:
    topic: str
    total_count: int
    returned_records: int
    authenticated: bool | None
    http_status: int
    complete: bool
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    rate_limit_reset: str | None = None


class GitHubError(Exception):
    def __init__(
        self, category: str, message: str, retry_after: str | None = None, *,
        http_status: int | None = None, rate_limit_remaining: int | None = None,
        rate_limit_reset: str | None = None, rate_limit_limit: int | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.retry_after = retry_after
        self.http_status = http_status
        self.rate_limit_remaining = rate_limit_remaining
        self.rate_limit_reset = rate_limit_reset
        self.rate_limit_limit = rate_limit_limit


class GitHubService:
    endpoint = "https://api.github.com/search/repositories"

    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport

    async def count_repositories_for_topic(
        self,
        topic: str,
        *,
        raw_response_callback: Callable[[Any, str | None], Any] | None = None,
    ) -> GitHubTopicCount:
        token = (self.settings.github_token or "").strip()
        if not token:
            raise GitHubError("configuration", "GitHub is not configured.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]{0,49}", topic.casefold()):
            raise GitHubError("configuration", "GitHub topic is invalid.")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        timeout = httpx.Timeout(self.settings.github_timeout_seconds)
        attempts = 1 + min(max(0, self.settings.github_max_retries), 2)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(
                        self.endpoint,
                        params={"q": f"topic:{topic.casefold()}", "per_page": 1},
                        headers=headers,
                    )
                except httpx.TimeoutException:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2 ** attempt), 2.0))
                        continue
                    raise GitHubError("network", "GitHub request timed out.") from None
                except httpx.RequestError:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2 ** attempt), 2.0))
                        continue
                    raise GitHubError("network", "GitHub could not be reached.") from None
                if (
                    500 <= response.status_code <= 599
                    and not response.headers.get("Retry-After")
                    and attempt + 1 < attempts
                ):
                    await asyncio.sleep(min(0.25 * (2 ** attempt), 2.0))
                    continue
                break

        retry_after = safe_retry_after_seconds(response.headers.get("Retry-After"))
        remaining = _safe_nonnegative_int(response.headers.get("X-RateLimit-Remaining"))
        rate_limit_limit = _safe_nonnegative_int(response.headers.get("X-RateLimit-Limit"))
        reset = _safe_epoch(response.headers.get("X-RateLimit-Reset"))
        if response.status_code == 429 or (
            response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
        ):
            raise GitHubError("rate_limit", "GitHub rate limit reached.", retry_after,
                              http_status=response.status_code, rate_limit_remaining=remaining,
                              rate_limit_reset=reset, rate_limit_limit=rate_limit_limit)
        if response.status_code in {401, 403}:
            raise GitHubError("authentication", "GitHub rejected the configured credentials.",
                              http_status=response.status_code, rate_limit_remaining=remaining,
                              rate_limit_reset=reset, rate_limit_limit=rate_limit_limit)
        if 500 <= response.status_code <= 599:
            raise GitHubError("server", "GitHub returned a server error.", retry_after,
                              http_status=response.status_code, rate_limit_remaining=remaining,
                              rate_limit_reset=reset, rate_limit_limit=rate_limit_limit)
        if not response.is_success:
            raise GitHubError("http", "GitHub rejected the request.", http_status=response.status_code,
                              rate_limit_remaining=remaining, rate_limit_reset=reset,
                              rate_limit_limit=rate_limit_limit)
        try:
            payload = response.json()
        except ValueError:
            raise GitHubError(
                "schema", "GitHub returned invalid data.", http_status=response.status_code,
                rate_limit_remaining=remaining, rate_limit_reset=reset, rate_limit_limit=rate_limit_limit,
            ) from None
        if raw_response_callback is not None:
            raw_response_callback(payload, response.headers.get("content-type"))
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise GitHubError(
                "schema", "GitHub returned an unexpected response structure.", http_status=response.status_code,
                rate_limit_remaining=remaining, rate_limit_reset=reset, rate_limit_limit=rate_limit_limit,
            )
        total_count = payload.get("total_count")
        items = payload["items"]
        if isinstance(total_count, bool) or not isinstance(total_count, int) or total_count < 0:
            raise GitHubError(
                "schema", "GitHub returned an invalid repository count.", http_status=response.status_code,
                rate_limit_remaining=remaining, rate_limit_reset=reset, rate_limit_limit=rate_limit_limit,
            )
        if any(not isinstance(item, dict) for item in items):
            raise GitHubError(
                "schema", "GitHub returned malformed repository records.", http_status=response.status_code,
                rate_limit_remaining=remaining, rate_limit_reset=reset, rate_limit_limit=rate_limit_limit,
            )
        incomplete = payload.get("incomplete_results", False)
        if not isinstance(incomplete, bool):
            raise GitHubError(
                "schema", "GitHub returned an invalid completeness flag.", http_status=response.status_code,
                rate_limit_remaining=remaining, rate_limit_reset=reset, rate_limit_limit=rate_limit_limit,
            )
        auth_header = response.headers.get("X-OAuth-Scopes")
        return GitHubTopicCount(
            topic=topic.casefold(), total_count=total_count,
            returned_records=len(items), authenticated=True if auth_header is not None else None,
            http_status=response.status_code, complete=not incomplete, rate_limit_remaining=remaining,
            rate_limit_limit=rate_limit_limit,
            rate_limit_reset=reset,
        )


def _safe_nonnegative_int(value: str | None) -> int | None:
    return int(value) if value and re.fullmatch(r"\d{1,12}", value) else None


def _safe_epoch(value: str | None) -> str | None:
    return value if value and re.fullmatch(r"\d{1,12}", value) else None

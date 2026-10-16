"""Safe, rate-conscious client for the Wikimedia Pageviews REST API.

API Specification:
https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}

Guarantees:
1. Strict User-Agent header compliance per Wikimedia Foundation policy.
2. Safe URL encoding of Wikipedia article titles.
3. Polite exponential backoff on transient errors (5xx) and rate limits (429).
4. Graceful handling of missing articles (HTTP 404 returns empty list).
5. No authentication required.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.external_apis.retry_after import safe_retry_after_seconds

logger = logging.getLogger(__name__)


class WikimediaError(Exception):
    def __init__(
        self,
        message: str,
        *,
        category: str,
        http_status: int | None = None,
        retry_after: str | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.http_status = http_status
        self.retry_after = retry_after


class WikimediaPageviewsService:
    base_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
    project = "en.wikipedia"
    access = "all-access"
    agent = "user"
    granularity = "monthly"

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport
        self.user_agent = self.settings.wikimedia_user_agent
        self.timeout_seconds = self.settings.wikimedia_timeout_seconds
        self.max_retries = self.settings.wikimedia_max_retries

    @staticmethod
    def encode_article_title(article: str) -> str:
        """URL-encode the Wikipedia article title safely."""
        clean = article.strip().replace(" ", "_")
        # quote with safe="" ensures all special characters like +, /, (, ) are properly encoded
        # Wikimedia accepts encoded titles like Python_%28programming_language%29 or raw parens
        # urllib.parse.quote with safe="()_:" works cleanly with MediaWiki titles
        return urllib.parse.quote(clean, safe="()_:")

    @staticmethod
    def period_to_timestamps(start_period: str, end_period: str) -> tuple[str, str]:
        """Convert YYYY-MM periods to Wikimedia YYYYMMDD00 timestamps."""
        try:
            start_year, start_month = (int(v) for v in start_period.split("-"))
            end_year, end_month = (int(v) for v in end_period.split("-"))
            if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
                raise ValueError
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid period format: start='{start_period}', end='{end_period}'. Expected YYYY-MM.")

        start_ts = f"{start_year:04d}{start_month:02d}0100"
        last_day = calendar.monthrange(end_year, end_month)[1]
        end_ts = f"{end_year:04d}{end_month:02d}{last_day:02d}00"
        return start_ts, end_ts

    def build_url(self, article: str, start_period: str, end_period: str) -> str:
        encoded_article = self.encode_article_title(article)
        start_ts, end_ts = self.period_to_timestamps(start_period, end_period)
        return (
            f"{self.base_url}/{self.project}/{self.access}/{self.agent}/"
            f"{encoded_article}/{self.granularity}/{start_ts}/{end_ts}"
        )

    async def fetch_monthly_pageviews(
        self,
        article: str,
        start_period: str,
        end_period: str,
    ) -> list[dict[str, Any]]:
        """Fetch monthly pageviews for an article across the requested range.
        
        Returns:
            List of valid item dicts with keys: project, article, granularity, timestamp, access, agent, views.
            Empty list if article has no data or returns HTTP 404.
        """
        url = self.build_url(article, start_period, end_period)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        attempts = 1 + self.max_retries

        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(url, headers=headers)
                except httpx.TimeoutException:
                    if attempt < attempts - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    raise WikimediaError(
                        f"Wikimedia request timed out after {self.timeout_seconds}s for article '{article}'.",
                        category="network_timeout",
                    )
                except httpx.RequestError as exc:
                    if attempt < attempts - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    raise WikimediaError(
                        f"Wikimedia network error: {str(exc)}",
                        category="network",
                    )

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception as err:
                        raise WikimediaError(
                            f"Invalid JSON returned from Wikimedia: {str(err)}",
                            category="malformed_data",
                            http_status=200,
                        )
                    if not isinstance(data, dict) or "items" not in data:
                        raise WikimediaError(
                            "Wikimedia response missing 'items' array.",
                            category="malformed_data",
                            http_status=200,
                        )
                    items = data.get("items")
                    if not isinstance(items, list):
                        raise WikimediaError(
                            "Wikimedia 'items' payload is not a list.",
                            category="malformed_data",
                            http_status=200,
                        )
                    if any(
                        not isinstance(item, dict)
                        or "timestamp" not in item
                        or "views" not in item
                        for item in items
                    ):
                        raise WikimediaError(
                            "Wikimedia returned a malformed pageview item.",
                            category="malformed_data",
                            http_status=200,
                        )
                    return items

                if response.status_code == 404:
                    # Article not found or no data for this date range - valid empty result
                    logger.info("Wikimedia article not found: %s", article)
                    return []

                if response.status_code == 403:
                    raise WikimediaError(
                        "Wikimedia rejected request (HTTP 403). Ensure a valid User-Agent header is configured.",
                        category="authentication",
                        http_status=403,
                    )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raw_delay = safe_retry_after_seconds(retry_after)
                    delay = float(raw_delay) if raw_delay is not None else float(1.0 * (2 ** attempt))
                    if attempt < attempts - 1:
                        await asyncio.sleep(min(delay, 10.0))
                        continue
                    raise WikimediaError(
                        "Wikimedia rate limit exceeded (HTTP 429).",
                        category="rate_limit",
                        http_status=429,
                        retry_after=str(int(delay)),
                    )

                if response.status_code >= 500:
                    if attempt < attempts - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    raise WikimediaError(
                        f"Wikimedia server error (HTTP {response.status_code}).",
                        category="server",
                        http_status=response.status_code,
                    )

                # Any other unexpected HTTP status
                raise WikimediaError(
                    f"Unexpected HTTP {response.status_code} from Wikimedia.",
                    category="http_error",
                    http_status=response.status_code,
                )

        return []

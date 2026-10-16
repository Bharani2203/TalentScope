import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from app.core.config import Settings, get_settings
from app.models.job import Job
from app.services.external_apis.retry_after import safe_retry_after_seconds


class JSearchError(Exception):
    def __init__(self, status_code: int, message: str, retry_after: str | None = None, category: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.retry_after = retry_after
        self.category = category or (
            "authentication" if "authentication" in message.casefold()
            else "rate_limit" if "rate limit" in message.casefold()
            else "schema" if "response" in message.casefold() or "application" in message.casefold()
            else "provider"
        )


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _location(record: dict[str, Any]) -> str | None:
    parts = [
        _text(record.get("job_city")),
        _text(record.get("job_state")),
        _text(record.get("job_country")),
    ]
    location = ", ".join(part for part in parts if part)
    return location or _text(record.get("job_location"))


def normalize_job(record: dict[str, Any], fetched_at: datetime) -> Job:
    required_skills = record.get("job_required_skills")
    skills_raw = (
        [skill.strip() for skill in required_skills if isinstance(skill, str) and skill.strip()]
        if isinstance(required_skills, list)
        else None
    )

    return Job(
        job_id=_text(record.get("job_id")) or _text(record.get("job_uid")),
        title=_text(record.get("job_title")),
        company_name=_text(record.get("employer_name")),
        location=_location(record),
        country=_text(record.get("job_country")),
        city=_text(record.get("job_city")),
        region=_text(record.get("job_state")),
        category=_text(record.get("job_category")),
        description=_text(record.get("job_description")),
        employment_type=_text(record.get("job_employment_type")),
        posted_at=(
            _text(record.get("job_posted_at_datetime_utc"))
            or _text(record.get("job_posted_at"))
            or _text(record.get("job_posted_at_timestamp"))
        ),
        source_url=(
            _text(record.get("job_apply_link"))
            or _text(record.get("job_google_link"))
        ),
        skills_raw=skills_raw or None,
        fetched_at=fetched_at,
    )


class JSearchService:
    base_url = "https://jsearch.p.rapidapi.com"

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport

    async def search_jobs(
        self,
        *,
        query: str,
        country: str | None = None,
        page: int = 1,
        num_pages: int = 1,
        date_posted: str | None = None,
        raw_response_callback: Callable[[Any, str | None], Any] | None = None,
    ) -> tuple[list[Job], datetime]:
        api_key = (self.settings.jsearch_api_key or "").strip()
        if not api_key:
            raise JSearchError(503, "JSearch is not configured on the server.")

        params: dict[str, str | int] = {
            "query": query.strip(),
            "page": page,
            "num_pages": num_pages,
        }
        if country:
            params["country"] = country.lower()
        if date_posted:
            params["date_posted"] = date_posted

        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": self.settings.rapidapi_host,
        }
        timeout = httpx.Timeout(self.settings.jsearch_timeout_seconds)
        attempts = max(0, self.settings.jsearch_max_retries) + 1

        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self.transport,
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(
                        f"{self.base_url}/search-v2",
                        params=params,
                        headers=headers,
                    )
                except httpx.TimeoutException:
                    if attempt + 1 < attempts:
                        await self._backoff(attempt)
                        continue
                    raise JSearchError(504, "JSearch request timed out.") from None
                except httpx.RequestError:
                    if attempt + 1 < attempts:
                        await self._backoff(attempt)
                        continue
                    raise JSearchError(502, "JSearch could not be reached.") from None

                if (
                    response.status_code in {500, 502, 503, 504}
                    and not response.headers.get("Retry-After")
                    and attempt + 1 < attempts
                ):
                    await self._backoff(attempt)
                    continue
                self._raise_for_status(response)
                break

        try:
            payload = response.json()
        except ValueError:
            raise JSearchError(502, "JSearch returned an invalid response.") from None

        if raw_response_callback is not None:
            raw_response_callback(payload, response.headers.get("content-type"))

        records = self._job_records(payload)
        if any(not isinstance(item, dict) for item in records):
            raise JSearchError(502, "JSearch returned malformed job data.")

        fetched_at = datetime.now(timezone.utc)
        jobs: list[Job] = []
        seen_ids: set[str] = set()
        for item in records:
            if not any(_text(item.get(field)) for field in (
                "job_id", "job_uid", "job_title", "employer_name", "job_posted_at_datetime_utc",
                "job_posted_at", "job_posted_at_timestamp",
            )):
                raise JSearchError(502, "JSearch returned malformed job data.")
            job = normalize_job(item, fetched_at)
            if job.job_id and job.job_id in seen_ids:
                continue
            if job.job_id:
                seen_ids.add(job.job_id)
            jobs.append(job)

        return jobs, fetched_at

    @staticmethod
    def _job_records(payload: Any) -> list[dict[str, Any]] | list[Any]:
        if not isinstance(payload, dict):
            raise JSearchError(502, "JSearch returned an unexpected response structure.")

        response_status = payload.get("status")
        if response_status is not None:
            if not isinstance(response_status, str):
                raise JSearchError(502, "JSearch returned an unexpected response status.")
            normalized_status = response_status.strip().casefold()
            if normalized_status in {"error", "failed", "failure"}:
                raise JSearchError(502, "JSearch reported an application error.")
            if normalized_status not in {"ok", "success", "successful"}:
                raise JSearchError(502, "JSearch returned an unexpected response status.")

        if payload.get("error") or payload.get("errors"):
            raise JSearchError(502, "JSearch reported an application error.")

        data = payload.get("data")
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and isinstance(data.get("jobs"), list):
            records = data["jobs"]
        else:
            raise JSearchError(502, "JSearch returned an unexpected response structure.")
        return records

    async def _backoff(self, attempt: int) -> None:
        delay = min(self.settings.jsearch_retry_backoff_seconds * (2**attempt), 2.0)
        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code in {401, 403}:
            raise JSearchError(502, "JSearch authentication failed; check server configuration.")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise JSearchError(
                503,
                "JSearch rate limit reached. Try again later.",
                retry_after=safe_retry_after_seconds(retry_after),
                category="rate_limit",
            )
        if response.status_code in {500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            raise JSearchError(
                502, "JSearch is temporarily unavailable.",
                retry_after=safe_retry_after_seconds(retry_after),
                category="server",
            )
        raise JSearchError(502, "JSearch rejected the request.")

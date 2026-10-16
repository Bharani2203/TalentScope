import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import Settings
from app.models.job import Job
from app.services.external_apis.jsearch_service import JSearchError, JSearchService
from app.services.market_data.adzuna_provider import AdzunaError, AdzunaProvider
from app.services.market_data.jsearch_provider import JSearchProvider


def settings(**values):
    return Settings(_env_file=None, **values)


def test_jsearch_adapter_reuses_existing_job_service_and_normalizes_postings():
    class StubJSearch:
        call = None

        async def search_jobs(self, **kwargs):
            self.call = kwargs
            fetched = datetime(2026, 10, 5, tzinfo=timezone.utc)
            return [
                Job(
                    job_id="j-1",
                    title="Python Developer",
                    description="Use Python and machine learning.",
                    skills_raw=["Python", "ML"],
                    fetched_at=fetched,
                )
            ], fetched

    service = StubJSearch()
    provider = JSearchProvider(service=service, settings=settings(adzuna_country="in"))
    collected = datetime(2026, 10, 5, tzinfo=timezone.utc)

    observations = asyncio.run(provider.collect_observations(
        location="Chennai",
        country=None,
        collected_at=collected,
    ))

    assert service.call == {
        "query": "software developer in Chennai",
        "country": "in",
        "num_pages": 1,
        "date_posted": "month",
    }
    assert {item.skill for item in observations} == {"Python", "Machine Learning"}
    assert all(item.signal_type == "demand" and item.location == "Chennai" for item in observations)


def test_nested_jsearch_response_reaches_market_posting_contract():
    settings_value = settings(
        jsearch_api_key="unit-test-key",
        jsearch_max_retries=0,
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "status": "OK",
        "parameters": {"num_pages": 1},
        "data": {"jobs": [{
            "job_id": "nested-market-job",
            "job_title": "Python Engineer",
            "job_description": "Use Python and FastAPI.",
            "job_city": "Chennai",
            "job_state": "Tamil Nadu",
            "job_country": "India",
            "job_posted_at_datetime_utc": "2026-10-01T12:00:00Z",
            "job_required_skills": ["Python", "FastAPI"],
        }]},
    }))
    service = JSearchService(settings=settings_value, transport=transport)
    provider = JSearchProvider(service=service, settings=settings_value)

    postings = asyncio.run(provider.fetch_market_postings(
        location=None,
        country="in",
        collected_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
    ))

    assert len(postings) == 1
    assert postings[0].source == "jsearch"
    assert postings[0].posting_id == "nested-market-job"
    assert postings[0].title == "Python Engineer"
    assert postings[0].description == "Use Python and FastAPI."
    assert postings[0].location == "Chennai, Tamil Nadu, India"
    assert postings[0].skills == ["Python", "FastAPI"]


def test_jsearch_response_archive_callback_runs_before_normalization():
    captured = []
    payload = {"status": "OK", "data": [{"job_id": "archive-job", "job_title": "Python Engineer"}]}
    service = JSearchService(
        settings=settings(jsearch_api_key="unit-test-key", jsearch_max_retries=0),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )
    provider = JSearchProvider(service=service, settings=service.settings)

    postings = asyncio.run(provider.fetch_market_postings(
        location=None, country="in", collected_at=datetime.now(timezone.utc),
        fetch_run_id="run-jsearch",
        archive_response=lambda body, content_type: captured.append((body, content_type)),
    ))

    assert len(postings) == 1
    assert captured == [(payload, "application/json")]


def test_jsearch_adapter_does_not_mask_existing_service_errors():
    class FailingJSearch:
        async def search_jobs(self, **kwargs):
            raise JSearchError(504, "JSearch request timed out.")

    provider = JSearchProvider(service=FailingJSearch(), settings=settings())

    with pytest.raises(JSearchError, match="timed out"):
        asyncio.run(provider.fetch_market_postings(
            location=None,
            country=None,
            collected_at=datetime.now(timezone.utc),
        ))


def test_adzuna_normalizes_jobs_and_deduplicates_source_records():
    payload = {
        "results": [
            {
                "id": "ad-1",
                "title": "Python Engineer",
                "description": "Python Python and ML",
                "location": {"area": ["Chennai", "Tamil Nadu", "India"]},
            },
            {
                "id": "ad-1",
                "title": "Python Engineer",
                "description": "duplicate",
            },
        ]
    }

    def handler(request):
        assert request.url.path == "/v1/api/jobs/in/search/1"
        assert request.url.params["where"] == "Chennai"
        assert request.url.params["app_id"] == "test-app-id"
        assert request.url.params["app_key"] == "test-app-secret"
        return httpx.Response(200, json=payload)

    provider = AdzunaProvider(
        settings=settings(
            adzuna_app_id="test-app-id",
            adzuna_app_key="test-app-secret",
            adzuna_max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    observations = asyncio.run(provider.collect_observations(
        location="Chennai",
        country="in",
        collected_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
    ))

    assert {item.skill for item in observations} == {"Python", "Machine Learning"}
    assert len([item for item in observations if item.skill == "Python"]) == 1
    assert all(item.source == "adzuna" and item.signal_type == "demand" for item in observations)


def test_adzuna_response_archive_callback_receives_provider_payload():
    captured = []
    payload = {"count": 1, "results": [{"id": "archive-job", "title": "Python Engineer"}]}
    provider = AdzunaProvider(
        settings=settings(adzuna_app_id="test-id", adzuna_app_key="test-key", adzuna_max_retries=0),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )

    result = asyncio.run(provider.fetch_market_postings_with_stats(
        location=None, country="in", collected_at=datetime.now(timezone.utc),
        fetch_run_id="run-adzuna",
        archive_response=lambda body, content_type: captured.append((body, content_type)),
    ))

    assert len(result.postings) == 1
    assert captured == [(payload, "application/json")]


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (lambda request: httpx.Response(429, json={"error": "secret"}), "rate limit"),
        (lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("secret")), "timed out"),
    ],
)
def test_adzuna_rate_limit_and_timeout_errors_do_not_expose_credentials(handler, message):
    provider = AdzunaProvider(
        settings=settings(
            adzuna_app_id="test-app-id",
            adzuna_app_key="test-app-secret",
            adzuna_max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AdzunaError, match=message) as error:
        asyncio.run(provider.fetch_market_postings(
            location=None,
            country=None,
            collected_at=datetime.now(timezone.utc),
        ))

    assert "test-app-secret" not in str(error.value)


def test_adzuna_requires_both_credentials_without_making_a_request():
    provider = AdzunaProvider(settings= settings(adzuna_app_id="only-id"))

    with pytest.raises(AdzunaError, match="not configured"):
        asyncio.run(provider.fetch_market_postings(
            location=None,
            country=None,
            collected_at=datetime.now(timezone.utc),
        ))


def test_adzuna_captures_retry_after_without_retrying_rate_limited_request():
    calls = []
    provider = AdzunaProvider(
        settings=settings(
            adzuna_app_id="test-app-id",
            adzuna_app_key="test-app-secret",
            adzuna_max_retries=2,
        ),
        transport=httpx.MockTransport(lambda request: (
            calls.append(request),
            httpx.Response(429, headers={"Retry-After": "60"}),
        )[1]),
    )

    with pytest.raises(AdzunaError) as error:
        asyncio.run(provider.fetch_market_postings(
            location=None, country=None, collected_at=datetime.now(timezone.utc),
        ))

    assert len(calls) == 1
    assert error.value.category == "rate_limit"
    assert error.value.retry_after == "60"

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.api.routes import market
from app.models.job import Job
from app.services.external_apis.jsearch_service import JSearchError, JSearchService


def make_service(handler, *, retries=0):
    settings = Settings(
        jsearch_api_key="unit-test-key",
        rapidapi_host="jsearch.p.rapidapi.com",
        jsearch_max_retries=retries,
        jsearch_retry_backoff_seconds=0,
    )
    return JSearchService(settings=settings, transport=httpx.MockTransport(handler))


def run_search(service, **kwargs):
    return asyncio.run(service.search_jobs(query="Python Developer", **kwargs))


def test_search_normalizes_data_and_deduplicates_by_external_id():
    job = {
        "job_id": "external-1",
        "job_title": "Python Developer",
        "employer_name": "Example Employer",
        "job_city": "Chennai",
        "job_state": "Tamil Nadu",
        "job_country": "India",
        "job_description": "Develop Python services.",
        "job_employment_type": "FULLTIME",
        "job_posted_at_datetime_utc": "2026-10-01T12:00:00Z",
        "job_apply_link": "https://jobs.example/apply",
        "job_required_skills": ["Python", "FastAPI"],
    }

    def handler(request):
        assert request.url.path == "/search-v2"
        assert request.url.params["query"] == "Python Developer"
        assert request.url.params["country"] == "in"
        assert request.url.params["page"] == "1"
        assert request.url.params["num_pages"] == "2"
        assert request.url.params["date_posted"] == "week"
        assert request.headers["X-RapidAPI-Key"] == "unit-test-key"
        assert request.headers["X-RapidAPI-Host"] == "jsearch.p.rapidapi.com"
        return httpx.Response(200, json={"data": [job, job]})

    jobs, fetched_at = run_search(
        make_service(handler), country="in", page=1, num_pages=2, date_posted="week"
    )

    assert len(jobs) == 1
    assert jobs[0].job_id == "external-1"
    assert jobs[0].title == "Python Developer"
    assert jobs[0].location == "Chennai, Tamil Nadu, India"
    assert jobs[0].skills_raw == ["Python", "FastAPI"]
    assert jobs[0].fetched_at == fetched_at
    assert jobs[0].source == "jsearch"


def test_empty_result_is_returned_as_empty_list():
    service = make_service(lambda request: httpx.Response(200, json={"data": []}))

    jobs, fetched_at = run_search(service)

    assert jobs == []
    assert fetched_at.tzinfo is not None


def test_nested_jobs_response_normalizes_and_deduplicates_external_records():
    job = {
        "job_id": "nested-job-1",
        "job_title": "Python Developer",
        "job_description": "Build Python services.",
        "job_location": "Chennai, India",
        "job_posted_at": "2026-10-01",
    }
    service = make_service(lambda request: httpx.Response(200, json={
        "status": "OK",
        "request_id": "request-id",
        "parameters": {"num_pages": 1},
        "data": {"jobs": [job, job]},
    }))

    jobs, _ = run_search(service)

    assert len(jobs) == 1
    assert jobs[0].job_id == "nested-job-1"
    assert jobs[0].title == "Python Developer"
    assert jobs[0].description == "Build Python services."
    assert jobs[0].location == "Chennai, India"
    assert jobs[0].posted_at == "2026-10-01"


def test_nested_empty_jobs_response_is_a_valid_empty_result():
    service = make_service(lambda request: httpx.Response(200, json={
        "status": "OK", "parameters": {"num_pages": 1}, "data": {"jobs": []},
    }))

    jobs, fetched_at = run_search(service)

    assert jobs == []
    assert fetched_at.tzinfo is not None


def test_missing_fields_are_not_fabricated():
    service = make_service(lambda request: httpx.Response(200, json={"data": [{"job_id": "id-1"}]}))

    jobs, _ = run_search(service)

    assert jobs[0].model_dump(exclude_none=True) == {
        "job_id": "id-1",
        "source": "jsearch",
        "fetched_at": jobs[0].fetched_at,
    }


def test_malformed_response_structure_fails_safely():
    service = make_service(lambda request: httpx.Response(200, json={"results": []}))

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == 502
    assert "unexpected response" in error.value.message


def test_pagination_metadata_without_job_list_is_not_an_empty_success():
    service = make_service(lambda request: httpx.Response(200, json={
        "status": "OK", "parameters": {"num_pages": 1}, "data": {},
    }))

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == 502
    assert "unexpected response" in error.value.message


def test_application_error_status_is_rejected_without_echoing_provider_message():
    service = make_service(lambda request: httpx.Response(200, json={
        "status": "ERROR",
        "message": "private token secret detail",
        "data": {"jobs": []},
    }))

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert "application error" in error.value.message
    assert "secret" not in error.value.message
    assert "unit-test-key" not in error.value.message


def test_unknown_application_status_is_not_accepted_as_success():
    service = make_service(lambda request: httpx.Response(200, json={
        "status": "PENDING", "data": {"jobs": []},
    }))

    with pytest.raises(JSearchError, match="unexpected response status"):
        run_search(service)


def test_malformed_job_record_fails_safely():
    service = make_service(lambda request: httpx.Response(200, json={"data": [None]}))

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == 502
    assert "malformed job data" in error.value.message


def test_empty_job_object_is_rejected_but_id_only_record_is_not_fabricated():
    with pytest.raises(JSearchError, match="malformed job data"):
        run_search(make_service(lambda request: httpx.Response(200, json={
            "status": "OK", "data": {"jobs": [{}]},
        })))

    jobs, _ = run_search(make_service(lambda request: httpx.Response(200, json={
        "status": "OK", "data": {"jobs": [{"job_id": "id-only"}]},
    })))
    assert len(jobs) == 1
    assert jobs[0].job_id == "id-only"
    assert jobs[0].title is None
    assert jobs[0].description is None


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [(401, 502), (403, 502), (429, 503)],
)
def test_upstream_auth_and_rate_limit_errors_are_mapped(status_code, expected_status):
    def handler(request):
        return httpx.Response(status_code, headers={"Retry-After": "30"}, json={"message": "secret"})

    service = make_service(handler)

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == expected_status
    assert "unit-test-key" not in error.value.message
    assert "secret" not in error.value.message
    if status_code == 429:
        assert error.value.retry_after == "30"


def test_timeout_maps_to_gateway_timeout():
    def handler(request):
        raise httpx.ReadTimeout("mock timeout")

    service = make_service(handler)

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == 504


def test_invalid_environment_key_is_reported_without_request():
    service = JSearchService(settings=Settings(jsearch_api_key=None))

    with pytest.raises(JSearchError) as error:
        run_search(service)

    assert error.value.status_code == 503


def test_response_model_rejects_unexpected_internal_fields():
    with pytest.raises(ValidationError):
        Job(job_id="id", unexpected="not allowed")


def test_market_jobs_endpoint_reads_stored_data_without_calling_jsearch(monkeypatch):
    from app.services.external_apis.jsearch_service import JSearchService
    monkeypatch.setattr(JSearchService, "search_jobs", lambda *args, **kwargs: pytest.fail("read API called JSearch"))
    monkeypatch.setattr(market, "search_stored_jsearch_jobs", lambda **kwargs: [])
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/market/jobs", params={"query": "Python Developer"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "empty"
    assert response.json()["source"] == "stored"
    assert response.json()["jobs"] == []
    assert response.json()["count"] == 0


def test_market_jobs_endpoint_returns_unavailable_when_stored_data_is_unavailable(monkeypatch):
    monkeypatch.setattr(market, "search_stored_jsearch_jobs", lambda **kwargs: (_ for _ in ()).throw(RuntimeError()))
    with TestClient(app) as client:
        response = client.get("/api/v1/market/jobs", params={"query": "Python Developer"})
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_market_jobs_endpoint_validates_country():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/market/jobs",
            params={"query": "Python Developer", "country": "India"},
        )

    assert response.status_code == 422

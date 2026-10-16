import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.analytics.skill_registry import canonical_skill_id
from app.core.config import Settings
from app.analytics.trend import calculate_skill_trends
from app.services.external_apis.github_service import GitHubError, GitHubService
from app.services.external_apis.retry_after import safe_retry_after_seconds
from app.services.market_data.github_provider import GitHubProvider


def test_github_client_authenticates_and_validates_repository_search_shape():
    seen = {}

    def handler(request):
        seen["authorization"] = request.headers.get("Authorization")
        seen["query"] = request.url.params["q"]
        return httpx.Response(
            200, headers={"X-OAuth-Scopes": ""},
            json={"total_count": 124, "items": [{"id": 7}]},
        )

    settings = Settings(_env_file=None, github_token="server-token", github_max_retries=0)
    service = GitHubService(settings, httpx.MockTransport(handler))
    result = asyncio.run(service.count_repositories_for_topic("python"))

    assert result.total_count == 124
    assert result.returned_records == 1
    assert result.authenticated is True
    assert seen["authorization"].startswith("Bearer ")
    assert seen["query"] == "topic:python"


def test_github_response_archive_callback_receives_sanitizable_payload():
    captured = []
    payload = {"total_count": 124, "incomplete_results": False, "items": [{"id": 7}]}
    service = GitHubService(
        Settings(_env_file=None, github_token="server-token", github_max_retries=0),
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )

    result = asyncio.run(service.count_repositories_for_topic(
        "python",
        raw_response_callback=lambda body, content_type: captured.append((body, content_type)),
    ))

    assert result.total_count == 124
    assert captured == [(payload, "application/json")]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"items": []}),
        httpx.Response(200, json={"total_count": "many", "items": []}),
        httpx.Response(200, json={"total_count": 2, "items": [None]}),
        httpx.Response(200, content=b"not-json"),
    ],
)
def test_github_rejects_malformed_application_responses(response):
    settings = Settings(_env_file=None, github_token="server-token", github_max_retries=0)
    service = GitHubService(settings, httpx.MockTransport(lambda request: response))

    with pytest.raises(GitHubError) as error:
        asyncio.run(service.count_repositories_for_topic("python"))

    assert error.value.category == "schema"
    assert "server-token" not in str(error.value)


def test_github_429_is_not_retried_and_retry_after_is_safe():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403, headers={"X-RateLimit-Remaining": "0", "Retry-After": "45"})

    service = GitHubService(
        Settings(_env_file=None, github_token="server-token", github_max_retries=2),
        httpx.MockTransport(handler),
    )
    with pytest.raises(GitHubError) as error:
        asyncio.run(service.count_repositories_for_topic("python"))

    assert len(calls) == 1
    assert error.value.category == "rate_limit"
    assert error.value.retry_after == "45"
    assert "server-token" not in str(error.value)


def test_github_retries_one_server_error_but_fails_authentication_immediately():
    calls = []

    def recover_once(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={"total_count": 1, "items": [{}]})

    service = GitHubService(
        Settings(_env_file=None, github_token="server-token", github_max_retries=1),
        httpx.MockTransport(recover_once),
    )
    assert asyncio.run(service.count_repositories_for_topic("python")).total_count == 1
    assert len(calls) == 2

    auth_calls = []
    auth_service = GitHubService(
        Settings(_env_file=None, github_token="server-token", github_max_retries=2),
        httpx.MockTransport(lambda request: (auth_calls.append(request), httpx.Response(401))[1]),
    )
    with pytest.raises(GitHubError) as error:
        asyncio.run(auth_service.count_repositories_for_topic("python"))
    assert len(auth_calls) == 1
    assert error.value.category == "authentication"


def test_github_incomplete_search_response_is_marked_partial():
    service = GitHubService(
        Settings(_env_file=None, github_token="server-token", github_max_retries=0),
        httpx.MockTransport(lambda request: httpx.Response(
            200, json={"total_count": 50, "incomplete_results": True, "items": [{}]},
        )),
    )
    result = asyncio.run(service.count_repositories_for_topic("python"))
    assert result.complete is False


def test_retry_after_parses_seconds_and_http_date_safely():
    from datetime import timedelta
    from email.utils import format_datetime

    future = datetime.now(timezone.utc) + timedelta(seconds=20)
    parsed = int(safe_retry_after_seconds(format_datetime(future)))
    assert 0 <= parsed <= 20
    assert safe_retry_after_seconds("999999") == "86400"
    assert safe_retry_after_seconds("not a date or duration") is None


def test_github_provider_maps_topic_to_separate_adoption_series():
    class Client:
        async def count_repositories_for_topic(self, topic):
            assert topic == "python"
            from app.services.external_apis.github_service import GitHubTopicCount
            return GitHubTopicCount(topic, 250, 1, True, 200, True)

    provider = GitHubProvider(
        service=Client(),
        settings=Settings(_env_file=None, github_token="server-token", github_topic="python"),
    )
    collected_at = datetime(2026, 10, 6, tzinfo=timezone.utc)
    result = asyncio.run(provider.collect_observations_with_stats(
        location=None, country=None, collected_at=collected_at,
    ))
    observation = result.observations[0]

    assert canonical_skill_id(observation.skill) == "python"
    assert observation.signal_type == "adoption"
    assert observation.source == "github"
    assert observation.value == 250
    assert observation.denominator is None
    assert observation.series_id == "github:repository-topic:python:v1"
    assert observation.history_type == "snapshot"
    assert observation.data_origin == "real"
    assert result.records_fetched == result.records_normalized == 1
    assert result.records_rejected == 0
    assert result.http_status == 200
    assert calculate_skill_trends(result.observations) == []


def test_github_snapshot_identity_is_stable_across_fetch_runs():
    class Client:
        async def count_repositories_for_topic(self, topic):
            from app.services.external_apis.github_service import GitHubTopicCount
            return GitHubTopicCount(topic, 250, 1, True, 200, True)

    provider = GitHubProvider(
        service=Client(),
        settings=Settings(_env_file=None, github_token="server-token", github_topic="python"),
    )
    collected_at = datetime(2026, 10, 6, tzinfo=timezone.utc)

    async def collect(run_id):
        result = await provider.collect_observations_with_stats(
            location=None, country=None, collected_at=collected_at, fetch_run_id=run_id,
        )
        return result.observations[0]

    first = asyncio.run(collect("run-a"))
    same_run = asyncio.run(collect("run-a"))
    next_run = asyncio.run(collect("run-b"))

    assert first.id == same_run.id
    assert first.id == next_run.id
    assert first.fetch_run_id == "run-a"
    assert next_run.fetch_run_id == "run-b"
    assert first.unit == "repositories"
    assert first.source_url == GitHubService.endpoint
    assert first.series_id == next_run.series_id == "github:repository-topic:python:v1"

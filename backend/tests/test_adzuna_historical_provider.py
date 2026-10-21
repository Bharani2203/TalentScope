"""Tests for Adzuna historical salary provider and Adzuna Intelligence provider."""

import asyncio
import httpx
import pytest

from app.core.config import Settings
from app.services.market_data.adzuna_historical_provider import (
    AdzunaHistoricalSalaryProvider,
    AdzunaIntelligenceProvider,
)


@pytest.fixture
def base_settings():
    return Settings(
        adzuna_app_id="test_app_id",
        adzuna_app_key="test_app_key",
        adzuna_country="gb",
        adzuna_timeout_seconds=5.0,
        adzuna_max_retries=0,
    )


# -----------------------------------------------------------------------------
# Option B1: Adzuna Standard Historical Salary Tests
# -----------------------------------------------------------------------------

def test_adzuna_salary_history_success(base_settings):
    """Verify standard historical salary parses month averages and sets signal_type='context'."""
    mock_payload = {
        "month": {
            "2025-01": 45000,
            "2025-02": 45500.5,
            "2025-03": 46000,
        }
    }

    def handler(request: httpx.Request):
        assert request.url.path == "/v1/api/jobs/gb/history"
        assert request.url.params["app_id"] == "test_app_id"
        assert request.url.params["app_key"] == "test_app_key"
        assert request.url.params["months"] == "12"
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings, transport=transport)
    result = asyncio.run(provider.fetch_salary_history(country="gb", months=12))

    assert result.status == "success"
    assert result.country == "gb"
    assert result.metric_name == "average_salary"
    assert result.signal_type == "context"
    assert result.skill_demand_eligible is False
    assert result.source == "adzuna_historical_salary"
    assert result.source_classification == "implemented_offline_not_live_verified"
    assert result.data_points == {
        "2025-01": 45000.0,
        "2025-02": 45500.5,
        "2025-03": 46000.0,
    }


def test_adzuna_salary_history_empty_series(base_settings):
    """Verify empty series for countries with no salary history (e.g. India)."""
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"month": {}})

    transport = httpx.MockTransport(handler)
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings, transport=transport)
    result = asyncio.run(provider.fetch_salary_history(country="in", months=6))

    assert result.status == "empty_series"
    assert result.data_points == {}
    assert "No salary history records" in (result.error_message or "")


def test_adzuna_salary_history_rate_limited(base_settings):
    """Verify 429 response parses Retry-After and returns safe rate_limited status."""
    def handler(request: httpx.Request):
        return httpx.Response(429, headers={"Retry-After": "45"}, content=b"Too Many Requests")

    transport = httpx.MockTransport(handler)
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings, transport=transport)
    result = asyncio.run(provider.fetch_salary_history(country="gb"))

    assert result.status == "rate_limited"
    assert result.retry_after == 45
    assert "rate limit exceeded" in (result.error_message or "")


def test_adzuna_salary_history_unauthorized_does_not_leak_key(base_settings):
    """Verify 401/403 unauthorized returns safe status and does not leak keys."""
    def handler(request: httpx.Request):
        return httpx.Response(401, content=b"Unauthorized")

    transport = httpx.MockTransport(handler)
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings, transport=transport)
    result = asyncio.run(provider.fetch_salary_history(country="gb"))

    assert result.status == "unauthorized"
    assert "test_app_key" not in (result.error_message or "")


def test_adzuna_salary_history_malformed_json(base_settings):
    """Verify malformed JSON payload is handled gracefully."""
    def handler(request: httpx.Request):
        return httpx.Response(200, content=b"<html>Bad Gateway</html>")

    transport = httpx.MockTransport(handler)
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings, transport=transport)
    result = asyncio.run(provider.fetch_salary_history(country="gb"))

    assert result.status == "malformed_json"
    assert result.data_points == {}


def test_adzuna_salary_history_invalid_country(base_settings):
    """Verify invalid country code returns invalid_country status immediately."""
    provider = AdzunaHistoricalSalaryProvider(settings=base_settings)
    result = asyncio.run(provider.fetch_salary_history(country="invalid_country"))

    assert result.status == "invalid_country"


def test_adzuna_salary_history_unconfigured():
    """Verify unconfigured credentials return unconfigured status without network call."""
    unconfigured_settings = Settings(
        adzuna_app_id=None,
        adzuna_app_key=None,
    )
    provider = AdzunaHistoricalSalaryProvider(settings=unconfigured_settings)
    result = asyncio.run(provider.fetch_salary_history(country="gb"))

    assert result.status == "unconfigured"


# -----------------------------------------------------------------------------
# Option B2: Adzuna Intelligence API Tests
# -----------------------------------------------------------------------------

def test_adzuna_intelligence_status_unconfigured():
    """Verify unconfigured Intelligence API flags BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION."""
    settings = Settings(adzuna_intelligence_api_key=None)
    provider = AdzunaIntelligenceProvider(settings=settings)
    status = provider.check_status("in")

    assert status.status == "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
    assert status.access_status == "blocked_access"
    assert status.country_status == "blocked_country_coverage"
    assert status.is_blocked is True
    assert status.can_fetch is False
    assert "India ('in') is not in standard Adzuna Intelligence coverage" in status.message


def test_adzuna_intelligence_fetch_blocked_without_network():
    """Verify calling fetch_demand_trend when blocked returns immediately without network."""
    settings = Settings(adzuna_intelligence_api_key=None)
    provider = AdzunaIntelligenceProvider(settings=settings)
    result = asyncio.run(provider.fetch_demand_trend(country="in"))

    assert result.status == "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
    assert result.access_status == "blocked_access"
    assert result.country_status == "blocked_country_coverage"
    assert result.data_points == {}


def test_adzuna_intelligence_authorized_mock_success():
    """Verify authorized mocked enterprise call parses demand-trend series."""
    settings = Settings(adzuna_intelligence_api_key="mock_enterprise_secret_key")
    mock_payload = {
        "trend": {
            "2025-01": 102.5,
            "2025-02": 105.1,
            "2025-03": 108.4,
        }
    }

    def handler(request: httpx.Request):
        assert request.url.path == "/api/v1.1/gb/reports/demand-trend/"
        assert request.headers["Authorization"] == "ApiKey mock_enterprise_secret_key"
        return httpx.Response(200, json=mock_payload)

    transport = httpx.MockTransport(handler)
    provider = AdzunaIntelligenceProvider(settings=settings, transport=transport)
    result = asyncio.run(provider.fetch_demand_trend(country="gb"))

    assert result.status == "success"
    assert result.access_status == "authorized"
    assert result.country_status == "supported"
    assert result.metric_name == "vacancy_demand_index"
    assert result.signal_type == "demand"
    assert result.source == "adzuna_intelligence"
    assert result.data_points == {
        "2025-01": 102.5,
        "2025-02": 105.1,
        "2025-03": 108.4,
    }


def test_adzuna_intelligence_authorized_rejection_handled_safely():
    """Verify 401/403 rejection from Intelligence endpoint is safely caught."""
    settings = Settings(adzuna_intelligence_api_key="invalid_enterprise_key")

    def handler(request: httpx.Request):
        return httpx.Response(403, content=b"Forbidden: Invalid API key")

    transport = httpx.MockTransport(handler)
    provider = AdzunaIntelligenceProvider(settings=settings, transport=transport)
    result = asyncio.run(provider.fetch_demand_trend(country="gb"))

    assert result.status == "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
    assert result.access_status == "blocked_access"
    assert "Commercial contract credentials rejected" in (result.error_message or "")

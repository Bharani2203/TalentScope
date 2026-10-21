"""Adzuna historical salary provider and Adzuna Intelligence provider.

Evaluates and implements Option B from the Three-Source Historical Intelligence Integration:
- Option B1: Standard Historical Salary API (GET /v1/api/jobs/{country}/history)
  Note: This API provides average salary history, NOT individual postings or skill-level demand.
  Classification: 'implemented_offline_not_live_verified' / 'not_suitable_for_skill_demand'.
- Option B2: Adzuna Intelligence API (api.intelligence.adzuna.com)
  Classification: 'BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION'
  Blocked reasons: 'blocked_access' (requires enterprise commercial license) and
  'blocked_country_coverage' (India 'in' is not covered in standard Intelligence tier).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.external_apis.retry_after import safe_retry_after_seconds


class AdzunaHistoricalError(Exception):
    """Safe provider error without exposing credentials or response payloads."""

    def __init__(self, message: str, *, category: str = "provider", retry_after: int | None = None):
        super().__init__(message)
        self.category = category
        self.retry_after = retry_after


@dataclass
class AdzunaHistoricalSalaryResult:
    """Historical salary result from Adzuna standard historical endpoint.
    
    Guarantees:
    - Metric is strictly 'average_salary'
    - Signal type is strictly 'context' (never 'demand')
    - Clearly marked as not suitable for skill demand
    - Source classification is 'implemented_offline_not_live_verified'
    """

    country: str
    category: str | None
    months_requested: int
    data_points: dict[str, float] = field(default_factory=dict)
    metric_name: str = "average_salary"
    signal_type: str = "context"
    unit: str = "currency_local"
    source: str = "adzuna_historical_salary"
    source_classification: str = "implemented_offline_not_live_verified"
    skill_demand_eligible: bool = False
    status: str = "success"
    error_message: str | None = None
    retry_after: int | None = None


class AdzunaHistoricalSalaryProvider:
    """Provider for Adzuna standard historical salary averages.
    
    Endpoint: GET https://api.adzuna.com/v1/api/jobs/{country}/history
    """

    base_url = "https://api.adzuna.com/v1/api/jobs"
    source_classification = "implemented_offline_not_live_verified"

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport

    async def fetch_salary_history(
        self,
        *,
        country: str,
        category: str | None = None,
        months: int = 12,
    ) -> AdzunaHistoricalSalaryResult:
        """Fetch historical monthly salary averages from Adzuna.
        
        Args:
            country: ISO-2 country code (e.g. 'gb', 'us', 'in').
            category: Optional Adzuna category tag (e.g. 'it-jobs').
            months: Number of historical months requested (1 to 36).
        """
        country_code = country.strip().lower()
        if not re.fullmatch(r"[a-z]{2}", country_code):
            return AdzunaHistoricalSalaryResult(
                country=country_code,
                category=category,
                months_requested=months,
                status="invalid_country",
                error_message="Adzuna requires a valid two-letter country code.",
            )

        app_id = (self.settings.adzuna_app_id or "").strip()
        app_key = (self.settings.adzuna_app_key or "").strip()
        if not app_id or not app_key:
            return AdzunaHistoricalSalaryResult(
                country=country_code,
                category=category,
                months_requested=months,
                status="unconfigured",
                error_message="Adzuna app_id or app_key is not configured.",
            )

        params: dict[str, Any] = {
            "app_id": app_id,
            "app_key": app_key,
            "content-type": "application/json",
            "months": max(1, min(int(months), 36)),
        }
        if category:
            params["category"] = category.strip()

        url = f"{self.base_url}/{country_code}/history"
        timeout = httpx.Timeout(self.settings.adzuna_timeout_seconds)
        attempts = max(0, self.settings.adzuna_max_retries) + 1

        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(url, params=params)
                except httpx.TimeoutException:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                        continue
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="network_timeout",
                        error_message="Adzuna historical salary request timed out.",
                    )
                except httpx.RequestError:
                    if attempt + 1 < attempts:
                        await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                        continue
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="network_error",
                        error_message="Adzuna historical salary endpoint could not be reached.",
                    )

                if response.status_code == 429:
                    raw_retry = response.headers.get("Retry-After")
                    retry_sec = safe_retry_after_seconds(raw_retry)
                    retry_int = int(retry_sec) if retry_sec is not None else None
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="rate_limited",
                        error_message="Adzuna historical salary rate limit exceeded.",
                        retry_after=retry_int,
                    )

                if response.status_code in (401, 403):
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="unauthorized",
                        error_message="Adzuna historical salary API returned unauthorized status.",
                    )

                if response.status_code != 200:
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="provider_error",
                        error_message=f"Adzuna historical salary returned status {response.status_code}.",
                    )

                # Parse JSON safely
                try:
                    data = response.json()
                except Exception:
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        status="malformed_json",
                        error_message="Adzuna historical salary returned malformed JSON.",
                    )

                # Month data is typically in data["month"] as { "YYYY-MM": salary_number }
                raw_month_data = data.get("month", {}) if isinstance(data, dict) else {}
                cleaned_points: dict[str, float] = {}
                for period_key, salary_val in raw_month_data.items():
                    if re.fullmatch(r"\d{4}-\d{2}", str(period_key)):
                        try:
                            val_float = float(salary_val)
                            if val_float > 0:
                                cleaned_points[str(period_key)] = round(val_float, 2)
                        except (ValueError, TypeError):
                            continue

                if not cleaned_points:
                    return AdzunaHistoricalSalaryResult(
                        country=country_code,
                        category=category,
                        months_requested=months,
                        data_points={},
                        status="empty_series",
                        error_message=f"No salary history records available for country '{country_code}'.",
                    )

                return AdzunaHistoricalSalaryResult(
                    country=country_code,
                    category=category,
                    months_requested=months,
                    data_points=cleaned_points,
                    status="success",
                )

        return AdzunaHistoricalSalaryResult(
            country=country_code,
            category=category,
            months_requested=months,
            status="network_error",
            error_message="Adzuna request attempts exhausted.",
        )


@dataclass
class AdzunaIntelligenceStatus:
    """Readiness and access status for Adzuna Intelligence API (api.intelligence.adzuna.com)."""

    status: str = "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
    access_status: str = "blocked_access"
    country_status: str = "blocked_country_coverage"
    country: str = "in"
    endpoint: str = "https://api.intelligence.adzuna.com/api/v1.1/{country_code}/reports/demand-trend/"
    auth_mechanism: str = "ApiKeyAuth header (Enterprise commercial contract required)"
    message: str = (
        "Adzuna Intelligence is a separate commercial product on api.intelligence.adzuna.com. "
        "Standard developer search keys return 401/403. India ('in') is not included in standard "
        "Adzuna Intelligence coverage (core markets: GB, US, CA, AU, FR, DE, NL)."
    )
    supported_countries: list[str] = field(
        default_factory=lambda: ["gb", "us", "ca", "au", "fr", "de", "nl", "nz", "za", "pl", "it", "at", "ch"]
    )
    is_blocked: bool = True
    can_fetch: bool = False


@dataclass
class AdzunaIntelligenceDemandResult:
    """Demand trend result from Adzuna Intelligence API if configured and authorized."""

    country: str
    category: str | None
    status: str
    access_status: str
    country_status: str
    data_points: dict[str, float] = field(default_factory=dict)
    metric_name: str = "vacancy_demand_index"
    signal_type: str = "demand"
    source: str = "adzuna_intelligence"
    source_classification: str = "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
    error_message: str | None = None


class AdzunaIntelligenceProvider:
    """Provider / adapter for Adzuna Intelligence demand-trend API.
    
    Enterprise API Base: https://api.intelligence.adzuna.com/api/v1.1
    Endpoints:
    - /api/v1.1/{country_code}/reports/demand-trend/
    - /api/v1.1/{country_code}/reports/inflow-trend/
    
    Behavior:
    - Unconfigured key: Flags 'blocked_access' and 'BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION'.
    - India ('in'): Flags 'blocked_country_coverage' (India not supported).
    - Configured enterprise key + supported country: Communicates with api.intelligence.adzuna.com.
    """

    base_url = "https://api.intelligence.adzuna.com/api/v1.1"
    supported_countries = ["gb", "us", "ca", "au", "fr", "de", "nl", "nz", "za", "pl", "it", "at", "ch"]

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.transport = transport

    def check_status(self, country: str = "in") -> AdzunaIntelligenceStatus:
        """Check the operational status of Adzuna Intelligence for a given country."""
        country_code = country.strip().lower()
        api_key = (self.settings.adzuna_intelligence_api_key or "").strip()

        has_key = bool(api_key)
        country_supported = country_code in self.supported_countries

        access_status = "authorized" if has_key else "blocked_access"
        country_status = "supported" if country_supported else "blocked_country_coverage"

        if not has_key and not country_supported:
            status = "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
            msg = (
                f"Adzuna Intelligence is blocked for country '{country_code}': requires enterprise contract "
                f"and India ('in') is not in standard Adzuna Intelligence coverage."
            )
        elif not has_key:
            status = "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
            msg = "Adzuna Intelligence requires enterprise commercial API key (ApiKeyAuth)."
        elif not country_supported:
            status = "BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION"
            msg = f"Country '{country_code}' is not covered by Adzuna Intelligence."
        else:
            status = "READY"
            msg = f"Adzuna Intelligence is configured and available for country '{country_code}'."

        return AdzunaIntelligenceStatus(
            status=status,
            access_status=access_status,
            country_status=country_status,
            country=country_code,
            endpoint=f"{self.base_url}/{country_code}/reports/demand-trend/",
            message=msg,
            supported_countries=list(self.supported_countries),
            is_blocked=(status != "READY"),
            can_fetch=(status == "READY"),
        )

    async def fetch_demand_trend(
        self,
        *,
        country: str = "in",
        category: str | None = None,
    ) -> AdzunaIntelligenceDemandResult:
        """Fetch demand trend from Adzuna Intelligence API or return safe blocked status."""
        status_info = self.check_status(country=country)
        country_code = country.strip().lower()

        if status_info.is_blocked:
            return AdzunaIntelligenceDemandResult(
                country=country_code,
                category=category,
                status=status_info.status,
                access_status=status_info.access_status,
                country_status=status_info.country_status,
                error_message=status_info.message,
            )

        # Enterprise call when authorized and country supported
        headers = {
            "Authorization": f"ApiKey {self.settings.adzuna_intelligence_api_key.strip()}",
            "Accept": "application/json",
        }
        url = f"{self.base_url}/{country_code}/reports/demand-trend/"
        params: dict[str, Any] = {}
        if category:
            params["category"] = category.strip()

        timeout = httpx.Timeout(self.settings.adzuna_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
            except httpx.TimeoutException:
                return AdzunaIntelligenceDemandResult(
                    country=country_code,
                    category=category,
                    status="network_timeout",
                    access_status="authorized",
                    country_status="supported",
                    error_message="Adzuna Intelligence request timed out.",
                )
            except httpx.RequestError:
                return AdzunaIntelligenceDemandResult(
                    country=country_code,
                    category=category,
                    status="network_error",
                    access_status="authorized",
                    country_status="supported",
                    error_message="Adzuna Intelligence endpoint could not be reached.",
                )

            if response.status_code in (401, 403):
                return AdzunaIntelligenceDemandResult(
                    country=country_code,
                    category=category,
                    status="BLOCKED_PENDING_ACCESS_OR_COVERAGE_CONFIRMATION",
                    access_status="blocked_access",
                    country_status="supported",
                    error_message="Adzuna Intelligence returned 401/403. Commercial contract credentials rejected.",
                )

            if response.status_code != 200:
                return AdzunaIntelligenceDemandResult(
                    country=country_code,
                    category=category,
                    status="provider_error",
                    access_status="authorized",
                    country_status="supported",
                    error_message=f"Adzuna Intelligence returned HTTP {response.status_code}.",
                )

            try:
                data = response.json()
            except Exception:
                return AdzunaIntelligenceDemandResult(
                    country=country_code,
                    category=category,
                    status="malformed_json",
                    access_status="authorized",
                    country_status="supported",
                    error_message="Adzuna Intelligence returned invalid JSON payload.",
                )

            # Parse trend points
            trend_data = data.get("trend", {}) if isinstance(data, dict) else {}
            points: dict[str, float] = {}
            for period_key, val in trend_data.items():
                if re.fullmatch(r"\d{4}-\d{2}", str(period_key)):
                    try:
                        points[str(period_key)] = float(val)
                    except (ValueError, TypeError):
                        continue

            return AdzunaIntelligenceDemandResult(
                country=country_code,
                category=category,
                status="success",
                access_status="authorized",
                country_status="supported",
                data_points=points,
                source_classification="usable_for_demand_trend",
            )

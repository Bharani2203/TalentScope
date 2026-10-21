"""Tests for Verified Job Postings Pipeline and Integration.

Covers:
1. Query and filter mapping for JSearch and Adzuna adapters.
2. Valid response parsing and handling of missing optional fields.
3. Preservation of original source URL and provider provenance.
4. Deduplication of identical provider job IDs.
5. Successful empty search (verified zero results, distinct from error).
6. Provider failures: timeout, rate limit (429), auth error (401/403), malformed response.
7. Partial failure handling (one provider succeeds, one provider fails).
8. Strict zero-fake-posting enforcement: Gemini B fallback prohibited by feature policy.
9. Orchestrator natural-language query routing to job_verified_postings.
10. Response contract compatibility with frontend IntelligenceResultDetails.js.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.skill_intelligence import MarketPosting
from app.services.market_data.base import PostingFetchResult
from app.services.verified_job_search_service import (
    VerifiedJobSearchResult,
    _provider_url_is_valid,
    search_configured_job_providers,
)
from app.storage.reference_store import ReferenceDataStore


# -----------------------------------------------------------------------------
# Fixtures and Helpers
# -----------------------------------------------------------------------------

def _make_mock_provider(
    postings: list[MarketPosting] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    provider = MagicMock()
    if raises:
        provider.fetch_market_postings_with_stats = AsyncMock(side_effect=raises)
    else:
        fetch_result = PostingFetchResult(
            postings=postings or [],
            records_fetched=len(postings or []),
            records_rejected=0,
            records_filtered=0,
            requested_page_count=1,
            pagination_complete=True,
            zero_results_verified=(len(postings or []) == 0),
        )
        provider.fetch_market_postings_with_stats = AsyncMock(return_value=fetch_result)
    return provider


# -----------------------------------------------------------------------------
# 1. Query & Filter Mapping
# -----------------------------------------------------------------------------

def test_provider_mapping_and_filters() -> None:
    """Verify parameters are properly routed and unapplied filters tracked."""
    jsearch_mock = _make_mock_provider([])
    adzuna_mock = _make_mock_provider([])
    mock_providers = {"jsearch": jsearch_mock, "adzuna": adzuna_mock}

    res = search_configured_job_providers(
        query="Python Engineer",
        country="us",
        location="New York, NY",
        date_posted="week",
        providers=mock_providers,
    )

    # Check JSearch received its expected kwargs
    assert jsearch_mock.fetch_market_postings_with_stats.called
    jsearch_call_kwargs = jsearch_mock.fetch_market_postings_with_stats.call_args.kwargs
    assert jsearch_call_kwargs["query"] == "Python Engineer"
    assert jsearch_call_kwargs["country"] == "us"
    assert jsearch_call_kwargs["location"] == "New York, NY"
    assert jsearch_call_kwargs["date_posted"] == "month"  # JSearch adapter bounded to month

    # Check Adzuna received its expected kwargs
    assert adzuna_mock.fetch_market_postings_with_stats.called
    adzuna_call_kwargs = adzuna_mock.fetch_market_postings_with_stats.call_args.kwargs
    assert adzuna_call_kwargs["query"] == "Python Engineer"
    assert adzuna_call_kwargs["country"] == "us"
    assert adzuna_call_kwargs["location"] == "New York, NY"
    assert adzuna_call_kwargs["result_limit"] == 50

    # Date filter unapplied notice recorded
    assert any("date_posted" in f for f in res.unapplied_filters)


# -----------------------------------------------------------------------------
# 2. Response Parsing & Missing Optional Fields Handling
# -----------------------------------------------------------------------------

def test_valid_response_parsing_and_missing_optional_fields() -> None:
    """Ensure postings with missing optional fields are parsed and invalid ones rejected."""
    valid_posting_full = MarketPosting(
        source="jsearch",
        posting_id="job-101",
        provider_job_id="jsearch-101",
        title="Full Stack Engineer",
        description="Build web applications",
        location="Austin, TX",
        company_name="TechCorp",
        source_url="https://example.com/jobs/101",
        posted_at="2026-04-01T12:00:00Z",
    )
    # Posting with missing optional fields: no description, company, location, posted_at
    valid_posting_minimal = MarketPosting(
        source="jsearch",
        posting_id="job-102",
        provider_job_id="jsearch-102",
        title="Backend Developer",
        description=None,
        location=None,
        company_name=None,
        source_url="https://example.com/jobs/102",
        posted_at=None,
    )
    # Invalid posting: missing title
    invalid_no_title = MarketPosting(
        source="jsearch",
        posting_id="job-103",
        provider_job_id="jsearch-103",
        title=None,
        source_url="https://example.com/jobs/103",
    )
    # Invalid posting: invalid non-https URL
    invalid_bad_url = MarketPosting(
        source="jsearch",
        posting_id="job-104",
        provider_job_id="jsearch-104",
        title="DevOps Engineer",
        source_url="http://insecure.com/jobs/104",
    )

    jsearch_mock = _make_mock_provider([
        valid_posting_full,
        valid_posting_minimal,
        invalid_no_title,
        invalid_bad_url,
    ])

    res = search_configured_job_providers(
        query="Software Engineer",
        country="us",
        location=None,
        providers={"jsearch": jsearch_mock},
    )

    assert res.status == "ready"
    assert len(res.postings) == 2
    assert res.postings[0].provider_job_id == "jsearch-101"
    assert res.postings[1].provider_job_id == "jsearch-102"
    assert res.postings[1].company_name is None
    assert res.postings[1].location is None
    assert res.rejected_count == 2  # Missing title and bad URL rejected


# -----------------------------------------------------------------------------
# 3. URL Validation & Provenance Preservation
# -----------------------------------------------------------------------------

def test_url_validation_and_provenance() -> None:
    """Verify that URL parser rejects invalid schemes and preserves provenance."""
    assert _provider_url_is_valid("https://careers.google.com/jobs/results/12345") is True
    assert _provider_url_is_valid("http://careers.google.com/jobs/results/12345") is False
    assert _provider_url_is_valid("javascript:alert(1)") is False
    assert _provider_url_is_valid(None) is False
    assert _provider_url_is_valid("") is False
    assert _provider_url_is_valid("https://user:pass@example.com/job") is False

    original_url = "https://www.adzuna.com/details/998877"
    adzuna_posting = MarketPosting(
        source="adzuna",
        posting_id="adz-1",
        provider_job_id="adzuna-998877",
        title="Data Analyst",
        company_name="Analytica",
        location="Chicago, IL",
        source_url=original_url,
    )
    adzuna_mock = _make_mock_provider([adzuna_posting])

    res = search_configured_job_providers(
        query="Data Analyst",
        country="us",
        location=None,
        providers={"adzuna": adzuna_mock},
    )

    assert len(res.postings) == 1
    assert res.postings[0].source_url == original_url
    assert res.postings[0].source == "adzuna"


# -----------------------------------------------------------------------------
# 4. Deduplication
# -----------------------------------------------------------------------------

def test_deduplication_of_identical_provider_job_ids() -> None:
    """Verify duplicate records with identical provider job IDs are deduplicated."""
    posting1 = MarketPosting(
        source="jsearch",
        posting_id="id-1",
        provider_job_id="dup-100",
        title="ML Engineer",
        source_url="https://example.com/jobs/dup1",
    )
    posting2 = MarketPosting(
        source="jsearch",
        posting_id="id-2",
        provider_job_id="dup-100",
        title="ML Engineer Duplicate",
        source_url="https://example.com/jobs/dup1-alt",
    )
    jsearch_mock = _make_mock_provider([posting1, posting2])

    res = search_configured_job_providers(
        query="ML Engineer",
        country="us",
        location=None,
        providers={"jsearch": jsearch_mock},
    )

    assert len(res.postings) == 1
    assert res.postings[0].title == "ML Engineer"


# -----------------------------------------------------------------------------
# 5. Successful Empty Search
# -----------------------------------------------------------------------------

def test_successful_empty_search() -> None:
    """A genuine zero-result search must return status 'empty' and not an error."""
    jsearch_mock = _make_mock_provider([])
    engine = V2JobIntelligenceEngine()

    res = engine.run_verified_postings(
        role_or_skill="NonExistentRoleXYZ",
        providers={"jsearch": jsearch_mock},
    )

    assert res.capability_id == "job_verified_postings"
    assert res.readiness_state == "ready"
    assert res.metadata["postings_count"] == 0
    assert res.metadata["zero_results_verified"] is True
    assert len(res.postings) == 0
    assert len(res.facts) == 1
    assert res.facts[0].metric_value == 0
    assert "No verified job postings matched" in res.headline


# -----------------------------------------------------------------------------
# 6. Provider Failures: Timeout, Rate Limit, Auth, Schema
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error_category,exc_message,expected_phrase",
    [
        ("rate_limit", "Rate limit exceeded (HTTP 429)", "rate limit"),
        ("timeout", "Connection timed out after 10s", "timed out"),
        ("authentication", "Invalid API Key (HTTP 401)", "authentication"),
        ("schema", "Unexpected JSON structure", "malformed"),
    ],
)
def test_provider_failures(error_category: str, exc_message: str, expected_phrase: str) -> None:
    """Verify provider failures are accurately classified and returned with clear messages."""
    class ProviderError(Exception):
        def __init__(self, msg: str, cat: str):
            super().__init__(msg)
            self.category = cat

    failing_provider = _make_mock_provider(raises=ProviderError(exc_message, error_category))
    engine = V2JobIntelligenceEngine()

    res = engine.run_verified_postings(
        role_or_skill="Software Engineer",
        providers={"jsearch": failing_provider},
    )

    assert res.capability_id == "job_verified_postings"
    assert res.readiness_state == "unavailable"
    assert expected_phrase in res.headline.lower()
    assert len(res.postings) == 0


# -----------------------------------------------------------------------------
# 7. Partial Failure Handling
# -----------------------------------------------------------------------------

def test_partial_failure_handling() -> None:
    """When one provider succeeds and one fails, status is partial and postings are kept."""
    good_posting = MarketPosting(
        source="adzuna",
        posting_id="adz-ok-1",
        provider_job_id="adz-ok-1",
        title="Cloud Architect",
        source_url="https://example.com/adz/ok",
    )
    good_provider = _make_mock_provider([good_posting])

    class AuthError(Exception):
        category = "authentication"

    bad_provider = _make_mock_provider(raises=AuthError("Auth failed"))

    engine = V2JobIntelligenceEngine()
    res = engine.run_verified_postings(
        role_or_skill="Cloud Architect",
        providers={"adzuna": good_provider, "jsearch": bad_provider},
    )

    assert res.readiness_state == "partial"
    assert len(res.postings) == 1
    assert res.metadata["providers"]["adzuna"] == "success"
    assert res.metadata["providers"]["jsearch"] == "failed"


# -----------------------------------------------------------------------------
# 8. Zero Fake Postings & Policy Enforcement
# -----------------------------------------------------------------------------

def test_zero_fake_postings_policy() -> None:
    """Confirm feature policy strictly disables Gemini B fallback and requires provider data."""
    policy = FEATURE_ANSWER_POLICIES.get("job_verified_postings")
    assert policy is not None
    assert policy.gemini_b_fallback is False
    assert policy.provider_data_required is True
    assert "never generate postings" in policy.guidance_instruction.lower()


def test_offline_test_guard_returns_unavailable() -> None:
    """In test environment with no mocked providers, offline test guard must engage."""
    engine = V2JobIntelligenceEngine()
    res = engine.run_verified_postings(role_or_skill="Data Scientist", providers=None)
    # Because of offline test guard, no network calls are made and status indicates unavailable/insufficient_data
    assert res.readiness_state in {"unavailable", "insufficient_data"}
    assert len(res.postings) == 0
    assert "unavailable" in res.headline.lower()


# -----------------------------------------------------------------------------
# 9. Orchestrator Intent Routing
# -----------------------------------------------------------------------------

def test_orchestrator_routing_job_verified_postings() -> None:
    """Verify natural-language queries about jobs and hiring route to job_verified_postings."""
    planner = V2IntentPlanner()

    intent1 = planner.plan("What jobs are available for Data Engineer in US?")
    assert intent1.capability_id == "job_verified_postings"

    intent2 = planner.plan("Show me job listings for React Developer")
    assert intent2.capability_id == "job_verified_postings"

    intent3 = planner.plan("What postings are available for Cybersecurity Analyst?")
    assert intent3.capability_id == "job_verified_postings"


# -----------------------------------------------------------------------------
# 10. Frontend Response Contract Compatibility
# -----------------------------------------------------------------------------

def test_frontend_response_contract_compatibility() -> None:
    """Verify structured facts and markdown answers match frontend UI expectations."""
    mock_postings = [
        MarketPosting(
            source="jsearch",
            posting_id="post-001",
            provider_job_id="jsearch-001",
            title="Senior Backend Engineer",
            company_name="Acme Corp",
            location="San Francisco, CA",
            source_url="https://example.com/acme/001",
            posted_at="2026-04-10T09:00:00Z",
            description="Looking for senior Python dev",
        )
    ]
    engine = V2JobIntelligenceEngine()
    result = engine.run_verified_postings(
        role_or_skill="Senior Backend Engineer",
        providers={"jsearch": _make_mock_provider(mock_postings)},
    )

    # 1. Structured Facts contract:
    facts = result.facts
    assert len(facts) >= 1
    job_fact = next(f for f in facts if f.fact_type == "stored_job_postings")
    assert job_fact.metric_value == 1
    details = job_fact.details
    assert "postings" in details
    posting_dict = details["postings"][0]

    # Required fields for frontend IntelligenceResultDetails.js renderJobs:
    assert posting_dict["title"] == "Senior Backend Engineer"
    assert posting_dict["company"] == "Acme Corp"
    assert posting_dict["location"] == "San Francisco, CA"
    assert posting_dict["source"] == "jsearch"
    assert posting_dict["source_url"] == "https://example.com/acme/001"
    assert posting_dict["posting_date"] == "2026-04-10T09:00:00Z"
    assert posting_dict["source_url"].startswith("https://")

    # 2. Markdown Answer Formatter contract:
    intent = V2IntentPlanner().plan("Show me jobs for Senior Backend Engineer")
    formatted = V2ResponseFormatter.format_response(
        user_message="Show me jobs for Senior Backend Engineer",
        portal_type="individual",
        intent=intent,
        result=result,
    )

    assert formatted.status == "ready"
    assert formatted.domain == "job"
    assert formatted.intent == "job_verified_postings"
    assert "Verified Job Postings (1 retrieved)" in formatted.answer
    assert "[View source posting](https://example.com/acme/001)" in formatted.answer
    assert any("provider-returned records" in lim for lim in formatted.limitations)

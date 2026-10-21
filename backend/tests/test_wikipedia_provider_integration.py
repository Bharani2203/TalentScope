"""Offline test suite for Wikipedia Pageviews API provider and SQLite backfill.

All HTTP requests are mocked using httpx.MockTransport.
Zero network calls and zero Firebase/Firestore operations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.skill_registry import SKILLS
from app.core.config import Settings
from app.models.skill_intelligence import MarketObservation
from app.services.external_apis.wikimedia_pageviews_service import (
    WikimediaError,
    WikimediaPageviewsService,
)
from app.services.market_data.wikipedia_provider import (
    WIKIPEDIA_CANONICAL_ARTICLE_ALLOWLIST,
    WikipediaPageviewsProvider,
    get_completed_month_range,
    resolve_wikipedia_article_for_skill,
)
from app.services.wikipedia_backfill_service import (
    get_existing_wikipedia_periods_in_sqlite,
    run_wikipedia_backfill,
)
from app.storage.market_store import MarketDataStore
from app.storage.fetch_run_store import SQLiteFetchRunStore


def _make_sample_payload(article: str, timestamps_and_views: list[tuple[str, int]]) -> dict[str, Any]:
    return {
        "items": [
            {
                "project": "en.wikipedia",
                "article": article,
                "granularity": "monthly",
                "timestamp": ts,
                "access": "all-access",
                "agent": "user",
                "views": views,
            }
            for ts, views in timestamps_and_views
        ]
    }


# -----------------------------------------------------------------------------
# 1. Firebase / Firestore Isolation Check
# -----------------------------------------------------------------------------

def test_no_firebase_or_firestore_imports_in_wikipedia_modules():
    """Verify that wikipedia modules do not import firebase_admin or firestore."""
    import app.services.external_apis.wikimedia_pageviews_service as wps
    import app.services.market_data.wikipedia_provider as wp
    import app.services.wikipedia_backfill_service as wbs

    for mod in (wps, wp, wbs):
        assert "firebase_admin" not in mod.__dict__
        assert "firestore" not in mod.__dict__


# -----------------------------------------------------------------------------
# 2. Article Encoding and Allowlist
# -----------------------------------------------------------------------------

def test_article_url_encoding():
    service = WikimediaPageviewsService()
    assert service.encode_article_title("Python (programming language)") == "Python_(programming_language)"
    assert service.encode_article_title("C++") == "C%2B%2B"
    assert service.encode_article_title("React (software)") == "React_(software)"


def test_article_allowlist_mappings():
    # Test required verification topics:
    defn1, art1 = resolve_wikipedia_article_for_skill("python")
    assert defn1.skill_id == "python"
    assert art1 == "Python_(programming_language)"

    defn2, art2 = resolve_wikipedia_article_for_skill("react")
    assert defn2.skill_id == "react"
    assert art2 == "React_(software)"

    defn3, art3 = resolve_wikipedia_article_for_skill("cloud_computing")
    assert defn3.skill_id == "cloud_computing"
    assert art3 == "Cloud_computing"

    # Unmapped canonical skill should raise ValueError
    with pytest.raises(ValueError, match="not mapped in the Wikipedia allowlist"):
        resolve_wikipedia_article_for_skill("c")  # Ambiguous, deliberately excluded

    # Unknown skill should raise ValueError
    with pytest.raises(ValueError, match="not in the canonical skill registry"):
        resolve_wikipedia_article_for_skill("nonexistent_unknown_skill")


# -----------------------------------------------------------------------------
# 3. HTTP Client Tests (Mocked Transport)
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_fetch_monthly_pageviews_success():
    payload = _make_sample_payload(
        "Python_(programming_language)",
        [("2024010100", 500000), ("2024020100", 520000)],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Python_(programming_language)" in str(request.url)
        assert request.headers.get("user-agent") is not None
        assert "TalentScope" in request.headers.get("user-agent")
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    items = await service.fetch_monthly_pageviews("Python_(programming_language)", "2024-01", "2024-02")

    assert len(items) == 2
    assert items[0]["timestamp"] == "2024010100"
    assert items[0]["views"] == 500000
    assert items[1]["timestamp"] == "2024020100"
    assert items[1]["views"] == 520000


@pytest.mark.anyio
async def test_fetch_monthly_pageviews_404_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Article not found"})

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    items = await service.fetch_monthly_pageviews("Unrecorded_Topic", "2024-01", "2024-02")
    assert items == []


@pytest.mark.anyio
async def test_fetch_monthly_pageviews_403_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden: User-Agent policy violated")

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    with pytest.raises(WikimediaError) as exc_info:
        await service.fetch_monthly_pageviews("Python_(programming_language)", "2024-01", "2024-02")

    assert exc_info.value.category == "authentication"
    assert exc_info.value.http_status == 403


@pytest.mark.anyio
async def test_fetch_monthly_pageviews_429_rate_limit_and_retry():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, text="Too Many Requests")
        payload = _make_sample_payload("Docker_(software)", [("2024-010100", 300000)])
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport, settings=Settings(_env_file=None, wikimedia_max_retries=2))
    items = await service.fetch_monthly_pageviews("Docker_(software)", "2024-01", "2024-01")

    assert call_count == 2
    assert len(items) == 1
    assert items[0]["views"] == 300000


@pytest.mark.anyio
async def test_fetch_monthly_pageviews_malformed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Not a JSON payload")

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport, settings=Settings(_env_file=None, wikimedia_max_retries=0))
    with pytest.raises(WikimediaError) as exc_info:
        await service.fetch_monthly_pageviews("Python_(programming_language)", "2024-01", "2024-02")

    assert exc_info.value.category == "malformed_data"


@pytest.mark.anyio
async def test_fetch_monthly_pageviews_rejects_malformed_item():
    payload = {"items": [{"timestamp": "2024010100"}]}
    service = WikimediaPageviewsService(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
        settings=Settings(_env_file=None, wikimedia_max_retries=0),
    )
    with pytest.raises(WikimediaError, match="malformed pageview item"):
        await service.fetch_monthly_pageviews("Python_(programming_language)", "2024-01", "2024-01")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "item",
    [
        {"timestamp": "bad", "views": 1},
        {"timestamp": "2024010100", "views": -1},
        {"timestamp": "2024010100", "views": float("nan")},
        {"timestamp": "2024010100", "views": "unknown"},
    ],
)
async def test_wikipedia_provider_rejects_invalid_timestamp_or_pageviews(item):
    class Service:
        async def fetch_monthly_pageviews(self, article, start_period, end_period):
            return [item]

    provider = WikipediaPageviewsProvider(service=Service())
    with pytest.raises(WikimediaError, match="invalid|non-numeric"):
        await provider.fetch_observations_for_skill("python", "2024-01", "2024-01")


# -----------------------------------------------------------------------------
# 4. Partial Month Exclusion & Observation Model Integrity
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_partial_current_month_is_strictly_excluded():
    # Simulate current date is 2026-10-09
    simulated_now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

    # API returns both complete past month (2026-09) and current partial month (2026-10)
    payload = _make_sample_payload(
        "Python_(programming_language)",
        [
            ("2026090100", 450000),
            ("2026100100", 120000),  # Current in-progress partial month!
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    provider = WikipediaPageviewsProvider(service=service)

    observations = await provider.fetch_observations_for_skill(
        "python", "2026-09", "2026-10", now=simulated_now,
    )

    # 2026-10 must be excluded!
    assert len(observations) == 1
    assert observations[0].period == "2026-09"
    assert observations[0].value == 450000.0
    assert observations[0].signal_type == "interest"
    assert observations[0].source == "wikipedia"
    assert observations[0].history_type == "backfill"
    assert observations[0].data_origin == "real"
    assert observations[0].unit == "pageviews"
    assert observations[0].source_url is not None


def test_completed_month_range_rejects_current_month():
    simulated_now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="not a completed month"):
        get_completed_month_range(end_period="2026-10", now=simulated_now)

    start, end, periods = get_completed_month_range(months_back=3, now=simulated_now)
    assert end == "2026-09"
    assert start == "2026-07"
    assert periods == ["2026-07", "2026-08", "2026-09"]


# -----------------------------------------------------------------------------
# 5. Missing Periods Not Fabricated or Zeroed
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_missing_periods_are_never_zeroed():
    # If API returns data for Jan and March, but NOT Feb, Feb must NOT be zeroed
    payload = _make_sample_payload(
        "React_(software)",
        [
            ("2024010100", 250000),
            ("2024030100", 270000),
        ],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    provider = WikipediaPageviewsProvider(service=service)

    observations = await provider.fetch_observations_for_skill(
        "react", "2024-01", "2024-03",
    )

    periods_present = [obs.period for obs in observations]
    assert periods_present == ["2024-01", "2024-03"]
    assert "2024-02" not in periods_present
    # No zero-value observations created
    assert all(obs.value > 0 for obs in observations)


# -----------------------------------------------------------------------------
# 6. Signal Family Separation & Deterministic IDs in SQLite
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_wikipedia_backfill_idempotence_and_signal_isolation(tmp_path):
    db_path = tmp_path / "test_market.sqlite3"
    store = MarketDataStore(db_path)

    payload = _make_sample_payload(
        "Python_(programming_language)",
        [("2024010100", 400000), ("2024020100", 410000)],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    service = WikimediaPageviewsService(transport=transport)
    provider = WikipediaPageviewsProvider(service=service)

    # Run 1: live execute
    res1 = await run_wikipedia_backfill(
        skills=["python"],
        start_period="2024-01",
        end_period="2024-02",
        db_path=db_path,
        dry_run=False,
        provider=provider,
    )
    assert res1["total_new_observations"] == 2
    assert res1["collection_status"] == "success"
    run_record = SQLiteFetchRunStore(db_path).get(res1["fetch_run_id"])
    assert run_record["status"] == "success"
    assert run_record["panel_version"] == WikipediaPageviewsProvider.panel_version
    assert run_record["extractor_version"] == WikipediaPageviewsProvider.extractor_version

    # Verify SQLite rows
    obs = store.get_observations(location=None, cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert len(obs) == 2
    assert obs[0].signal_type == "interest"
    assert obs[0].source == "wikipedia"
    assert obs[0].posting_id == "article:Python_(programming_language)"
    assert obs[0].fetch_run_id == res1["fetch_run_id"]
    assert obs[0].created_at is not None
    assert obs[0].metadata["collection_timestamp_utc"]

    # Run 2: repeat execution (should detect series is already complete in SQLite)
    res2 = await run_wikipedia_backfill(
        skills=["python"],
        start_period="2024-01",
        end_period="2024-02",
        db_path=db_path,
        dry_run=False,
        provider=provider,
    )
    assert res2["total_new_observations"] == 0
    assert res2["total_skipped_existing"] == 2
    assert res2["results"][0]["status"] == "already_complete"

    # Count in SQLite remains strictly 2!
    obs_after = store.get_observations(location=None, cutoff=datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert len(obs_after) == 2


@pytest.mark.anyio
def test_wikipedia_signal_is_isolated_from_demand_and_adoption():
    """Verify that signal_aggregation keeps Wikipedia 'interest' completely separate."""
    obs_interest = MarketObservation(
        source="wikipedia",
        skill="Python",
        skill_id="python",
        observed_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2024-01",
        signal_type="interest",
        value=500000.0,
        history_type="backfill",
        data_origin="real",
        scope="global",
    )
    obs_demand = MarketObservation(
        source="jsearch",
        skill="Python",
        skill_id="python",
        observed_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2024-01",
        signal_type="demand",
        value=1.0,
        history_type="platform_collected",
        data_origin="real",
        scope="global",
        posting_id="job_123",
    )
    obs_adoption = MarketObservation(
        source="github",
        skill="Python",
        skill_id="python",
        observed_at=datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc),
        period="2024-01",
        signal_type="adoption",
        value=15000.0,
        history_type="snapshot",
        data_origin="real",
        scope="global",
    )

    aggregated = aggregate_market_signals([obs_interest, obs_demand, obs_adoption])
    # Three separate partitions must exist!
    assert len(aggregated) == 3

    interest_signal = next(s for s in aggregated if s.source == "wikipedia")
    assert interest_signal.signal_type == "interest"
    assert interest_signal.raw_value == 500000.0

    demand_signal = next(s for s in aggregated if s.source == "jsearch")
    assert demand_signal.signal_type == "demand"

    adoption_signal = next(s for s in aggregated if s.source == "github")
    assert adoption_signal.signal_type == "adoption"

import asyncio
from datetime import datetime, timezone
import httpx
import pytest

from app.core.config import Settings
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.external_apis.jsearch_service import JSearchError, JSearchService
from app.services.market_data.jsearch_provider import JSearchProvider
from app.services.market_data.base import PostingFetchResult
from app.services.market_collection_service import collect_market_data
from app.storage.market_store import MarketDataStore


def settings(**values):
    return Settings(_env_file=None, **values)


class MemoryFetchRunStore:
    def __init__(self):
        self.records = {}

    def start(self, run_id, record):
        self.records[run_id] = dict(record)

    def finish(self, run_id, record):
        self.records[run_id].update(record)

    def collection_summary(self):
        latest = {}
        for row in sorted(self.records.values(), key=lambda item: item["started_at"], reverse=True):
            latest.setdefault(row["source"].casefold(), row)
        return {"last_collection": {"providers": latest} if latest else None}


class MemoryObservationStore:
    def __init__(self):
        self.records = {}

    def insert_observations(self, observations, **kwargs):
        added = 0
        for obs in observations:
            if obs.id not in self.records:
                self.records[obs.id] = obs
                added += 1
        return added

    def get_observations(self, **kwargs):
        return list(self.records.values())


def test_jsearch_fetch_market_postings_with_stats_counts_records():
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_id": "js-1",
                    "job_title": "Senior Python Developer",
                    "employer_name": "Tech Corp",
                    "job_city": "Bengaluru",
                    "job_country": "India",
                    "job_required_skills": ["Python", "FastAPI"],
                },
                {
                    "job_id": "js-1",  # duplicate id -> filtered
                    "job_title": "Senior Python Developer",
                    "employer_name": "Tech Corp",
                },
                {
                    "job_id": "js-2",
                    "job_title": "",  # missing title -> rejected
                    "employer_name": "Unknown",
                },
            ]
        },
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    settings_val = settings(jsearch_api_key="unit-key", jsearch_max_retries=0)
    service = JSearchService(settings=settings_val, transport=transport)
    provider = JSearchProvider(service=service, settings=settings_val)

    result = asyncio.run(provider.fetch_market_postings_with_stats(
        location="Bengaluru",
        country="in",
        collected_at=datetime.now(timezone.utc),
    ))

    assert isinstance(result, PostingFetchResult)
    assert len(result.postings) == 1
    assert result.records_fetched == 2  # JSearchService internally deduplicates/filters before returning jobs list
    assert result.postings[0].posting_id == "js-1"
    assert result.postings[0].title == "Senior Python Developer"


def test_jsearch_canonical_skill_extraction_and_series():
    payload = {
        "status": "OK",
        "data": {
            "jobs": [
                {
                    "job_id": "js-csharp",
                    "job_title": "C# .NET Developer",
                    "employer_name": "Microsoft Partner",
                    "job_description": "We need expert in C# and Azure cloud.",
                    "job_city": "Hyderabad",
                    "job_country": "India",
                    "job_required_skills": ["C#", "Azure"],
                }
            ]
        },
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    settings_val = settings(jsearch_api_key="unit-key", jsearch_max_retries=0)
    service = JSearchService(settings=settings_val, transport=transport)
    provider = JSearchProvider(service=service, settings=settings_val)

    observations = asyncio.run(provider.collect_observations(
        location="Hyderabad",
        country="in",
        collected_at=datetime.now(timezone.utc),
    ))

    skills = {obs.skill for obs in observations}
    assert "C#" in skills
    csharp_obs = next(obs for obs in observations if obs.skill == "C#")
    assert csharp_obs.source == "jsearch"
    assert csharp_obs.signal_type == "demand"
    assert csharp_obs.history_type == "platform_collected"
    assert csharp_obs.data_origin == "real"
    assert csharp_obs.value == 1.0
    assert "c_sharp" in csharp_obs.series_id or "c#" in csharp_obs.series_id.lower()


def test_jsearch_failure_does_not_block_adzuna_collection(tmp_path):
    class FailingJSearchProvider:
        name = "jsearch"
        async def fetch_market_postings_with_stats(self, **kwargs):
            raise JSearchError(504, "JSearch request timed out.")

    class WorkingAdzunaProvider:
        name = "adzuna"
        async def fetch_market_postings_with_stats(self, **kwargs):
            return PostingFetchResult(
                postings=[
                    MarketPosting(
                        source="adzuna",
                        posting_id="adz-1",
                        title="Python Developer",
                        skills=["Python"],
                    )
                ],
                records_fetched=1,
                records_rejected=0,
                records_filtered=0,
            )

    fetch_runs = MemoryFetchRunStore()
    observation_store = MemoryObservationStore()
    store = MarketDataStore(tmp_path / "market.sqlite3")
    settings_val = settings(skill_intelligence_db_path=str(tmp_path / "market.sqlite3"))

    result = asyncio.run(collect_market_data(
        location=None,
        country="in",
        settings=settings_val,
        store=store,
        providers=[FailingJSearchProvider(), WorkingAdzunaProvider()],
        fetch_run_store=fetch_runs,
        observation_store=observation_store,
    ))

    assert result.status == "partial_failure"
    assert "jsearch" in result.sources_failed
    assert result.sources_succeeded == ["adzuna"]
    assert result.observations_inserted >= 1
    assert any(obs.source == "adzuna" for obs in observation_store.records.values())

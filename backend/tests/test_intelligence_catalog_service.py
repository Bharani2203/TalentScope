from datetime import date, datetime, timezone

import pytest

from app.analytics.skill_registry import canonical_skill_id
from app.models.skill_intelligence import MarketObservation
from app.services import intelligence_catalog_service as catalog


@pytest.fixture(autouse=True)
def clear_cache():
    catalog.clear_catalog_cache()
    yield
    catalog.clear_catalog_cache()


def observation(period, value, *, signal="demand", source="jsearch", skill="Python"):
    year, month = map(int, period.split("-"))
    return MarketObservation(
        source=source, skill=skill, signal_type=signal,
        observed_at=datetime(year, month, 15, tzinfo=timezone.utc), period=period,
        scope="global", location="Global", value=value, posting_id=f"{source}-{skill}-{period}",
        denominator=100, history_type="platform_collected", data_origin="real",
        unit="job_postings" if signal == "demand" else "pageviews",
        skill_id=canonical_skill_id(skill),
        series_id=f"{source}:{signal}:{skill}", panel_version="v1",
        query_id=f"{source}:{signal}:query-v1",
    )


def test_catalog_keeps_reference_only_skills_separate_from_real_observations(monkeypatch):
    monkeypatch.setattr(catalog, "_observations", lambda: [observation("2026-01", 10)])
    result = catalog._global_catalog()
    python = next(item for item in result["skills"] if item["skill_id"] == "python")
    java = next(item for item in result["skills"] if item["skill_id"] == "java")

    assert python["status"] == "observed"
    assert python["latest"]["source"] == "jsearch"
    assert python["latest"]["signal_type"] == "demand"
    assert python["latest"]["period"] == "2026-01"
    assert python["latest"]["metric"] == "normalized_share"
    assert python["latest"]["unit"] == "share"
    assert python["latest"]["raw_value"] == 10
    assert python["trend_available"] is False
    assert python["trend"] is None
    assert java["status"] == "reference_only"
    assert java["latest"] is None
    assert result["counts"]["observed"] == 1
    assert result["counts"]["reference_only"] == len(result["skills"]) - 1


def test_catalog_trend_uses_shared_consecutive_period_readiness_and_keeps_signal_sources_separate(monkeypatch):
    rows = [observation(period, value) for period, value in zip(
        ("2026-01", "2026-02", "2026-03", "2026-04"), (10, 12, 14, 16)
    )]
    rows.append(observation("2026-04", 75, signal="interest", source="wikimedia"))
    monkeypatch.setattr(catalog, "_observations", lambda: rows)
    result = catalog._global_catalog()
    python = next(item for item in result["skills"] if item["skill_id"] == "python")

    assert python["trend_available"] is True
    assert python["trend"]["direction"] == "Increasing"
    assert python["trend"]["source"] == "jsearch"
    assert python["trend"]["signal_type"] == "demand"
    assert {item["signal_type"] for item in python["signals"]} == {"demand", "interest"}
    assert len(python["signals"]) == 5
    demand_coverage = next(item for item in result["coverage_by_signal"] if item["source"] == "jsearch" and item["signal_type"] == "demand")
    interest_coverage = next(item for item in result["coverage_by_signal"] if item["source"] == "wikimedia" and item["signal_type"] == "interest")
    assert demand_coverage["consecutive_completed_months"] == 4
    assert interest_coverage["consecutive_completed_months"] == 1


def test_catalog_keeps_open_month_snapshot_separate_from_latest_completed_trend(monkeypatch):
    rows = [observation(period, value) for period, value in zip(
        ("2026-01", "2026-02", "2026-03", "2026-04", "2026-10"), (10, 12, 14, 16, 900)
    )]
    rows[-1].denominator = 1000
    calculate = catalog.calculate_trend_and_velocity
    monkeypatch.setattr(catalog, "calculate_trend_and_velocity", lambda aggregates: calculate(aggregates, as_of=date(2026, 10, 11)))
    monkeypatch.setattr(catalog, "is_completed_month", lambda period: period != "2026-10")
    monkeypatch.setattr(catalog, "_observations", lambda: rows)
    result = catalog._global_catalog()
    python = next(item for item in result["skills"] if item["skill_id"] == "python")
    assert python["latest"]["period"] == "2026-10"
    assert python["latest"]["value"] == 0.9
    assert python["latest"]["raw_value"] == 900
    assert python["trend_available"] is True
    assert python["trend"]["period"] == "2026-04"


def test_market_catalog_does_not_promote_job_employers_to_telemetry(monkeypatch):
    class Snapshot:
        id = "job1"
        def to_dict(self):
            return {"company_name": "Example Employer", "source": "jsearch", "source_url": "https://jobs.example/listing/1", "location": "Austin", "country": "US", "posted_at": "2026-10-01"}

    class Query:
        def __init__(self, source=None): self.source = source
        def where(self, *, filter):
            # FieldFilter exposes its field/value through private attrs in the SDK;
            # this fixture returns the test provider tied to each query call.
            return self
        def limit(self, count):
            return self
        def stream(self):
            return [Snapshot()]

    class Collection:
        def where(self, *, filter):
            return Query()
        def limit(self, count):
            return Query()

    class Client:
        def collection(self, name):
            return Collection()

    monkeypatch.setattr(catalog, "_global_catalog", lambda: {
        "market": {"technologies": [], "companies_with_market_observations": [], "company_market_telemetry_available": False},
        "locations": ["Global"], "available_ranges": ["30d"],
    })
    monkeypatch.setattr(catalog, "get_firestore_client", lambda: Client())
    result = catalog.get_market_catalog("user-1")

    assert result["companies_with_job_evidence"] == [{
        "entity_id": catalog._employer_entity_id("Example Employer"),
        "name": "Example Employer", "entity_type": "employer", "evidence_type": "stored_job_postings",
        "posting_count_in_sample": 1, "company_market_telemetry": False,
        "sources": ["jsearch"], "locations": ["Austin", "US"], "latest_posted_at": "2026-10-01", "evidence_links": ["https://jobs.example/listing/1"],
    }]
    assert result["locations"] == ["Global"]
    assert result["job_locations_in_sample"] == ["Austin", "US"]
    assert result["job_coverage"]["trends_available"] is False


def test_job_catalog_uses_cursor_pagination_and_caches_the_complete_bounded_query(monkeypatch):
    class Snapshot:
        def __init__(self, key): self.id = key
        def to_dict(self): return {"company_name": self.id, "source": "jsearch"}

    class Query:
        def __init__(self, pages, cursor=None): self.pages, self.cursor = pages, cursor
        def limit(self, count): return self
        def start_after(self, snapshot): return Query(self.pages, snapshot.id)
        def stream(self): return self.pages[0] if self.cursor is None else self.pages[1]

    class Collection:
        def __init__(self, pages): self.pages = pages
        def where(self, *, filter): return Query(self.pages)
        def limit(self, count): return Query(self.pages)

    class Client:
        def collection(self, name):
            assert name == "jobs"
            return Collection([[Snapshot("first"), Snapshot("second")], [Snapshot("third")]])

    monkeypatch.setattr(catalog, "_JOB_CATALOG_PAGE_SIZE", 2)
    monkeypatch.setattr(catalog, "_JOB_CATALOG_MAX_PAGES", 2)
    monkeypatch.setattr(catalog, "get_firestore_client", lambda: Client())

    rows, _ = catalog._job_catalog_rows()
    rows_again, cache_age = catalog._job_catalog_rows()
    assert [row["company_name"] for row in rows] == ["first", "second", "third"]
    assert rows_again == rows
    assert cache_age >= 0
    assert catalog._job_catalog_may_be_incomplete is False


def test_registered_company_is_visible_only_to_its_verified_owner(monkeypatch):
    class Snapshot:
        def __init__(self, data):
            self._data = data
            self.exists = data is not None
        def to_dict(self):
            return self._data

    class Doc:
        def __init__(self, data): self.data = data
        def get(self): return Snapshot(self.data)

    class Collection:
        def __init__(self, name): self.name = name
        def limit(self, count): return self
        def where(self, **kwargs): return self
        def stream(self): return []
        def document(self, key):
            records = {
                ("users", "owner"): {"company_id": "co-1"},
                ("users", "other"): {"company_id": "co-1"},
                ("companies", "co-1"): {"owner_uid": "owner", "company_name": "Private Company", "status": "active"},
            }
            return Doc(records.get((self.name, key)))

    class Client:
        def collection(self, name): return Collection(name)

    monkeypatch.setattr(catalog, "_global_catalog", lambda: {
        "market": {"technologies": [], "companies_with_market_observations": [], "company_market_telemetry_available": False},
        "locations": [], "available_ranges": [],
    })
    monkeypatch.setattr(catalog, "get_firestore_client", lambda: Client())

    owner_result = catalog.get_market_catalog("owner")
    other_result = catalog.get_market_catalog("other")
    assert owner_result["registered_company"]["name"] == "Private Company"
    assert other_result["registered_company"] is None

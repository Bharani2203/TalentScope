"""Mocked tests for local role mapping and collected posting skill aggregation."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest

from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.entity_registry import EntityResolutionRequest
from app.services import collected_posting_skills_service as aggregate_service
from app.services.answer_verdict_rules import classify_posting_demand
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.entity_registry_service import EntityRegistryService
from app.services.intent_planner_service import IntentPlannerService
from app.services.role_alias_service import ROLE_ALIAS_SOC_CODES, query_local_onet_occupation, role_alias_soc_code
from app.storage.firestore_read_guard import read_guard


def test_mocked_role_alias_targets_are_verified_against_local_sqlite_rows():
    expected = {
        "15-1243.01": "Data Warehousing Specialists",
        "15-2051.00": "Data Scientists",
        "15-1252.00": "Software Developers",
        "15-1254.00": "Web Developers",
        "15-1244.00": "Network and Computer Systems Administrators",
        "15-2051.01": "Business Intelligence Analysts",
    }
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE ref_onet_occupations (soc_code TEXT PRIMARY KEY, title TEXT)")
    connection.executemany(
        "INSERT INTO ref_onet_occupations (soc_code, title) VALUES (?, ?)",
        expected.items(),
    )
    query_results = {code: query_local_onet_occupation(connection, code) for code in expected}
    assert query_results == {
        code: {"soc_code": code, "title": title}
        for code, title in expected.items()
    }
    assert role_alias_soc_code("ML Engineer") == "15-2051.00"
    assert role_alias_soc_code("Data Engineers") == "15-1243.01"
    assert set(ROLE_ALIAS_SOC_CODES.values()) == set(expected)
    connection.close()


def test_mocked_resolver_discloses_alias_mapping_from_sqlite(monkeypatch):
    rows = [
        ("15-1243.01", "Data Warehousing Specialists"),
        ("15-2051.00", "Data Scientists"),
        ("15-1252.00", "Software Developers"),
        ("15-1254.00", "Web Developers"),
        ("15-1244.00", "Network and Computer Systems Administrators"),
        ("15-2051.01", "Business Intelligence Analysts"),
    ]

    def mocked_connection():
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("CREATE TABLE ref_onet_occupations (soc_code TEXT PRIMARY KEY, title TEXT)")
        connection.executemany("INSERT INTO ref_onet_occupations VALUES (?, ?)", rows)
        return connection

    registry = EntityRegistryService()
    monkeypatch.setattr(registry, "_connect_db", mocked_connection)
    response = registry.resolve(EntityResolutionRequest(name="ML Engineer", entity_type="occupation"))
    assert response.status == "resolved"
    assert response.entity.canonical_name == "Data Scientists"
    assert "15-2051.00" in response.source_provenance["mapping_disclosure"]


def test_mocked_collected_postings_question_routes_to_aggregate():
    planner = IntentPlannerService.__new__(IntentPlannerService)
    intent, _, _, capabilities, _ = planner._classify_intent(
        "What skills appear in the postings you've collected?", []
    )
    assert intent == "aggregate_posting_skills"
    assert capabilities == ["collected_posting_skills"]


def test_mocked_aggregate_deduplicates_postings_and_skill_pairs():
    result = aggregate_service.compute_posting_skill_aggregate([
        ("doc-a", {
            "source": "jsearch", "source_job_id": "same-1", "country_code": "in",
            "company_name": "Acme", "posted_at": "2026-03-03T00:00:00Z",
            "skills_raw": ["Python", "python", " SQL ", "SQL"],
        }),
        ("duplicate-doc", {
            "source": "jsearch", "source_job_id": "same-1", "country_code": "in",
            "company_name": "Acme", "posted_at": "2026-03-03T00:00:00Z",
            "skills_raw": ["Python", "SQL"],
        }),
        ("doc-b", {
            "source": "adzuna", "source_job_id": "same-2", "country_code": "IN",
            "company_name": "Beta", "posted_at": "2026-04-09T00:00:00Z",
            "skills_raw": ["python", "AWS"],
        }),
    ])
    assert result["n"] == 2
    assert result["date_start"] == "2026-03-03"
    assert result["date_end"] == "2026-04-09"
    assert result["company_count"] == 2
    assert result["source_labels"] == ["adzuna", "jsearch"]
    assert result["top_skills"] == [
        {"skill": "Python", "count": 2},
        {"skill": "AWS", "count": 1},
        {"skill": "SQL", "count": 1},
    ]
    assert result["skill_counts"][0] == {
        "skill": "Python", "count": 2, "company_count": 2,
        "verdict": "Not enough data", "share": 1.0, "limited_evidence": False,
    }


def test_mocked_small_sample_suppresses_percentages_and_discloses_scope(monkeypatch):
    sample = {
        "n": 3, "date_start": "2026-01-01", "date_end": "2026-01-03",
        "company_count": 2, "source_labels": ["jsearch"],
        "top_skills": [{"skill": "Python", "count": 2}],
        "skill_counts": [{
            "skill": "Python", "count": 2, "company_count": 1,
            "verdict": "Not enough data", "share": 2 / 3, "limited_evidence": False,
        }],
        "sample_may_be_incomplete": False, "query_limit": 500,
    }
    monkeypatch.setattr(aggregate_service, "get_collected_posting_skills", lambda **_: sample)
    service = ExecutionOrchestratorService.__new__(ExecutionOrchestratorService)
    service.firestore_store = None
    facts, evidence, limitations = service._handle_collected_posting_skills(
        CoreIntelligenceAnswerRequest(message="What skills appear in postings?"),
        SimpleNamespace(intent="aggregate_posting_skills"),
    )
    skill_fact = next(fact for fact in facts if fact.fact_type == "collected_posting_skill_count")
    summary = next(fact for fact in facts if fact.fact_type == "collected_posting_skills_summary")
    assert "sample_share_percent" not in skill_fact.details
    assert summary.details["percentages_suppressed"] is True
    assert "jobs.skills_raw" == summary.details["skill_count_source_of_truth"]
    assert "percentages are suppressed" in " ".join(limitations).casefold()
    answer = service._synthesize_answer(
        "aggregate_posting_skills",
        facts,
        evidence,
        ["collected_posting_skills"],
        CoreIntelligenceAnswerRequest(message="What skills appear in postings?"),
    )
    assert "3 collected India postings" in answer
    assert "2 companies" in answer
    assert "2026-01-01 to 2026-01-03" in answer
    assert "Python**: 2 postings" in answer
    assert "%" not in answer
    disclosure = aggregate_service.format_collected_postings_disclosure(3)
    assert disclosure == (
        "This is a sample of 3 collected India postings, "
        "not a measure of hiring demand or the Indian market."
    )
    assert evidence[0].source == "Firestore jobs.skills_raw"


@pytest.mark.parametrize(
    ("n", "total", "companies", "expected"),
    [
        (4, 114, 4, "Not enough data"),
        (5, 114, 4, "Low"),
        (19, 114, 4, "Moderate"),
        (20, 114, 4, "High"),
        (10, 29, 4, "Not enough data"),
        (10, 30, 4, "Moderate"),
        (20, 134, 4, "Moderate"),  # just below 15%
        (20, 133, 4, "High"),      # just above 15%
        (10, 201, 4, "Low"),       # just below 5%
        (11, 200, 4, "Moderate"),  # above 5%
        (20, 114, 2, "Low"),
        (20, 114, 3, "High"),
    ],
)
def test_mocked_posting_verdict_threshold_boundaries(n, total, companies, expected):
    assert classify_posting_demand(n, total, companies)["level"] == expected


def test_mocked_employer_cap_discloses_limited_evidence():
    result = classify_posting_demand(20, 114, 2)
    assert result == {
        "level": "Low", "share": 20 / 114, "limited_evidence": True,
    }


class _MockSnapshot:
    def __init__(self, document_id, record):
        self.id = document_id
        self._record = record

    def to_dict(self):
        return dict(self._record)


class _MockQuery:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.filter = None
        self.query_limit = None

    def where(self, *, filter):
        self.filter = filter
        return self

    def limit(self, value):
        self.query_limit = value
        return self

    def stream(self):
        return iter(self.snapshots[:self.query_limit])


class _MockCollection:
    def __init__(self, snapshots):
        self.query = _MockQuery(snapshots)

    def where(self, *, filter):
        return self.query.where(filter=filter)


class _MockFirestore:
    def __init__(self, snapshots):
        self.collection_ref = _MockCollection(snapshots)

    def collection(self, name):
        assert name == "jobs"
        return self.collection_ref


def test_mocked_read_is_limited_cached_and_counted(monkeypatch):
    aggregate_service.clear_collected_posting_skills_cache()
    read_guard.reset_metrics()
    client = _MockFirestore([
        _MockSnapshot("doc-1", {
            "source": "jsearch", "source_job_id": "id-1", "country_code": "in",
            "skills_raw": ["Python"], "posted_at": datetime(2026, 2, 2, tzinfo=timezone.utc),
        })
    ])
    first = aggregate_service.get_collected_posting_skills(firestore_client=client)
    second = aggregate_service.get_collected_posting_skills(firestore_client=client)
    metrics = read_guard.get_metrics()
    assert first == second
    assert client.collection_ref.query.query_limit == 500
    assert metrics["reads_by_collection"]["jobs"] == 1
    assert metrics["cache_hits"] == 1

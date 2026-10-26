from datetime import datetime, timezone
import pytest

from app.services.job_storage_service import (
    _query_skill,
    search_stored_jsearch_jobs_with_stats,
)


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeQuery:
    def __init__(self, snapshots, limit_count: int | None = None):
        self._snapshots = snapshots
        self._limit = limit_count

    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, count: int):
        return _FakeQuery(self._snapshots, limit_count=count)

    def start_after(self, *args, **kwargs):
        return self

    def stream(self):
        snaps = self._snapshots
        if self._limit is not None:
            snaps = snaps[:self._limit]
        return iter(snaps)


class _FakeCollection:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    def where(self, *args, **kwargs):
        return _FakeQuery(self._snapshots).where(*args, **kwargs)

    def order_by(self, *args, **kwargs):
        return _FakeQuery(self._snapshots).order_by(*args, **kwargs)

    def limit(self, count: int):
        return _FakeQuery(self._snapshots, limit_count=count)

    def stream(self):
        return iter(self._snapshots)


class _FakeFirestoreClient:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    def collection(self, name: str):
        return _FakeCollection(self._snapshots)


@pytest.fixture
def fake_corpus_client():
    now = datetime.now(timezone.utc)
    records = [
        {
            "job_id": "job-blr-1",
            "title": "Python Developer",
            "city": "Bangalore",
            "location": "Bangalore, India",
            "country_code": "in",
            "description": "Python backend development",
            "skills_raw": ["Python"],
            "fetched_at": now,
        },
        {
            "job_id": "job-blr-2",
            "title": "Data Analyst",
            "city": "Bangalore",
            "location": "Bangalore, India",
            "country_code": "in",
            "description": "Data analysis and reporting",
            "skills_raw": ["SQL"],
            "fetched_at": now,
        },
        {
            "job_id": "job-blr-3",
            "title": "QA Engineer",
            "city": "Bangalore",
            "location": "Bangalore, India",
            "country_code": "in",
            "description": "Quality assurance and automated testing",
            "skills_raw": ["Testing"],
            "fetched_at": now,
        },
        {
            "job_id": "job-chn-1",
            "title": "DevOps Engineer",
            "city": "Chennai",
            "location": "Chennai, India",
            "country_code": "in",
            "description": "Cloud infrastructure and CI/CD pipelines",
            "skills_raw": ["AWS"],
            "fetched_at": now,
        },
        {
            "job_id": "job-rem-1",
            "title": "Senior Frontend Engineer (Remote)",
            "city": None,
            "location": "Remote",
            "country_code": "in",
            "description": "React remote frontend role",
            "skills_raw": ["React"],
            "fetched_at": now,
        },
    ]
    snapshots = [_FakeSnapshot(rec["job_id"], rec) for rec in records]
    return _FakeFirestoreClient(snapshots)


def test_generic_jobs_in_bangalore(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="jobs in Bangalore",
        location="Bangalore",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 3
    assert len(result) == 3
    assert {job.job_id for job in result} == {"job-blr-1", "job-blr-2", "job-blr-3"}


def test_generic_bangalore_jobs(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="Bangalore jobs",
        location="Bangalore",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 3
    assert len(result) == 3
    assert {job.job_id for job in result} == {"job-blr-1", "job-blr-2", "job-blr-3"}


def test_generic_show_me_jobs(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="show me jobs",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 5
    assert len(result) == 5


def test_generic_show_me_jobs_with_limit(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="show me jobs",
        limit=2,
        firestore_client=fake_corpus_client,
    )
    assert len(result) == 2
    assert result.matched_count == 5


def test_specific_python_developer_jobs_in_bangalore(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="python developer jobs in Bangalore",
        location="Bangalore",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 1
    assert len(result) == 1
    assert result[0].title == "Python Developer"
    assert result.related_titles == []


def test_related_titles_only_when_zero_matches(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="data scientist jobs in Bangalore",
        location="Bangalore",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 0
    assert "Data Analyst" in result.related_titles
    assert "QA Engineer" not in result.related_titles


def test_zero_postings_city(fake_corpus_client):
    result = search_stored_jsearch_jobs_with_stats(
        query="jobs in Mumbai",
        location="Mumbai",
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == 0
    assert result.city_posting_count == 0
    assert len(result) == 0


def test_skill_detection_java_jobs():
    skill_name, ambiguous = _query_skill(["java", "jobs"])
    assert skill_name == "Java"
    assert ambiguous is False


def test_skill_detection_python_developer_in_bangalore():
    # Demonstrates why meaningful_words (stripped location tokens) is necessary:
    # 1. With raw query_words containing city token 'bangalore', candidate is 'python bangalore', which is not a known skill:
    raw_query_words = ["python", "developer", "jobs", "in", "bangalore"]
    skill_raw, _ = _query_skill(raw_query_words)
    assert skill_raw is None

    # 2. With meaningful_words after location stripping, candidate is 'python', which is detected:
    meaningful_words = ["python", "developer"]
    skill_cleaned, ambiguous = _query_skill(meaningful_words)
    assert skill_cleaned == "Python"
    assert ambiguous is False


def test_related_titles_does_not_include_location_matched_titles():
    now = datetime.now(timezone.utc)
    records = [
        {
            "job_id": "job-blr-ops",
            "title": "Bangalore Operations Lead",
            "city": "Bangalore",
            "location": "Bangalore, India",
            "country_code": "in",
            "description": "Operations management in Bangalore",
            "skills_raw": ["Operations"],
            "fetched_at": now,
        },
        {
            "job_id": "job-blr-data",
            "title": "Data Analyst",
            "city": "Bangalore",
            "location": "Bangalore, India",
            "country_code": "in",
            "description": "Data analysis",
            "skills_raw": ["SQL"],
            "fetched_at": now,
        },
    ]
    client = _FakeFirestoreClient([_FakeSnapshot(r["job_id"], r) for r in records])
    result = search_stored_jsearch_jobs_with_stats(
        query="data scientist jobs in Bangalore",
        location="Bangalore",
        firestore_client=client,
    )
    assert result.matched_count == 0
    assert "Bangalore Operations Lead" not in result.related_titles
    assert "Data Analyst" in result.related_titles


@pytest.mark.parametrize(
    "query,expected_matches",
    [
        ("jobs in Bangalore", 3),
        ("Bangalore jobs", 3),
        ("show me jobs", 5),
    ],
)
def test_caller_path_preparation_generic_queries(fake_corpus_client, query, expected_matches):
    from app.services.question_classification_service import extract_location
    from app.services.execution_orchestrator_service import ExecutionOrchestratorService

    loc = extract_location(query)
    country = ExecutionOrchestratorService._extract_question_country(query)
    result = search_stored_jsearch_jobs_with_stats(
        query=query,
        location=loc,
        country=country,
        firestore_client=fake_corpus_client,
    )
    assert result.matched_count == expected_matches


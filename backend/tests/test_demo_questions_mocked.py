from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.routes import core_intelligence
from app.intelligence_v2.adapter import V2ExecutionOrchestratorAdapter
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.job import Job
from app.services.intent_planner_service import IntentPlannerService
from app.services.job_storage_service import store_jsearch_jobs


class _OfflineGuidance:
    def __init__(self):
        self.calls = 0

    def is_available(self):
        return False

    def generate(self, **_kwargs):
        self.calls += 1
        return None


class _OfflinePlanExplanation:
    def is_available(self):
        return False

    def generate(self, **_kwargs):
        raise AssertionError("The demo plan must not call an LLM provider.")

    def generate_structured_json(self, **_kwargs):
        return None


@pytest.fixture
def demo_api(monkeypatch, injected_empty_firestore):
    user = AuthenticatedUser(
        uid="demo-test-user",
        email="demo@example.com",
        user_type="individual",
        claims={"user_type": "individual"},
    )
    guidance = _OfflineGuidance()

    def make_plan_service():
        return IntentPlannerService(llm_service=_OfflinePlanExplanation())

    def make_answer_service():
        return V2ExecutionOrchestratorAdapter(
            orchestrator=V2Orchestrator(gemini_b_service=guidance)
        )

    monkeypatch.setattr(core_intelligence, "IntentPlannerService", make_plan_service)
    monkeypatch.setitem(app.dependency_overrides, dependencies.get_current_user, lambda: user)
    monkeypatch.setitem(
        app.dependency_overrides,
        core_intelligence.get_execution_orchestrator_service,
        make_answer_service,
    )
    return TestClient(app, raise_server_exceptions=False), injected_empty_firestore, guidance


DEMO_QUESTIONS = [
    pytest.param(
        "Find data engineer jobs in Bangalore",
        "skill",
        "job_verified_postings",
        "ready",
        "real",
        id="stored-bangalore-jobs",
    ),
    pytest.param(
        "Find python developer jobs in Chennai",
        "market",
        "job_verified_postings",
        "insufficient_data",
        "unavailable",
        id="no-chennai-match",
    ),
    pytest.param(
        "What does a data engineer do?",
        "market",
        "skill_lookup",
        "ready",
        "local_reference_dataset",
        id="occupation-reference",
    ),
    pytest.param(
        "What skills does a data engineer need?",
        "skill",
        "job_role_requirements",
        "ready",
        "local_reference_dataset",
        id="role-requirements-reference",
    ),
    pytest.param(
        "Is Python becoming more popular?",
        "job",
        "skill_demand_trends",
        "partial",
        "real",
        id="python-market-trend",
    ),
    pytest.param(
        "Compare Python and Java",
        "market",
        None,
        "not_applicable",
        "unavailable",
        id="two-skill-comparison",
    ),
    pytest.param(
        "Give me a preparation plan for Web Developer",
        "skill",
        "job_preparation_actions",
        "ready",
        "local_reference_dataset",
        id="web-developer-preparation",
    ),
    pytest.param(
        "what is the weather",
        "job",
        None,
        "not_applicable",
        "unavailable",
        id="off-topic-clarifies",
    ),
]


def _seed_bangalore_postings(firestore):
    fetched_at = datetime(2026, 10, 24, tzinfo=timezone.utc)
    return store_jsearch_jobs(
        [
            Job(
                job_id="demo-data-engineer-1",
                title="Data Engineer",
                company_name="Example Analytics",
                location="Bangalore, Karnataka",
                country="India",
                country_code="in",
                description="Build and maintain data pipelines.",
                source="jsearch",
                city="Bangalore",
                fetched_at=fetched_at,
            ),
            Job(
                job_id="demo-data-engineer-2",
                title="Senior Data Engineer",
                company_name="Example Systems",
                location="Bengaluru, Karnataka",
                country="India",
                country_code="in",
                description="Develop reliable data infrastructure.",
                source="jsearch",
                city="Bengaluru",
                fetched_at=fetched_at,
            ),
            Job(
                job_id="demo-data-engineer-3",
                title="Data Platform Engineer",
                company_name="Example Cloud",
                location="Bangalore, Karnataka",
                country="India",
                country_code="in",
                description="Operate analytics data platforms.",
                source="jsearch",
                city="Bangalore",
                fetched_at=fetched_at,
            ),
        ],
        firestore_client=firestore,
    )


def _seed_mixed_city_postings(firestore):
    fetched_at = datetime(2026, 10, 24, tzinfo=timezone.utc)
    city_counts = (
        ("Bangalore", 4),
        ("Bengaluru", 2),
        ("Chennai", 4),
        ("Mumbai", 4),
        ("Pune", 3),
        ("Hyderabad", 3),
        ("Delhi", 2),
    )
    jobs = []
    for city, count in city_counts:
        for city_index in range(count):
            job_number = len(jobs) + 1
            is_remote = city_index == 0 and city in {"Bangalore", "Bengaluru"}
            title = f"{'Remote ' if is_remote else ''}Data Engineer {job_number}"
            jobs.append(Job(
                job_id=f"mixed-city-{job_number:02}",
                title=title,
                company_name=f"Mock Company {job_number}",
                location=f"{city}, India",
                country="India",
                country_code="in",
                description="Build data pipelines and analytics systems.",
                source="jsearch",
                source_url=f"https://jobs.example/mixed-city-{job_number:02}",
                city=city,
                skills_raw=["Python", "SQL"],
                posted_at="2026-10-15T00:00:00+00:00",
                fetched_at=fetched_at,
            ))
    assert len(jobs) == 22
    assert store_jsearch_jobs(jobs, firestore_client=firestore) == 22
    return {job.job_id: job for job in jobs}


def _response_summary(answer):
    return {
        key: answer.get(key)
        for key in (
            "status",
            "execution_status",
            "intent",
            "planned_primary_capability",
            "executed_primary_capability",
            "reason_codes",
            "answer",
        )
    } | {
        "facts": [
            {
                "entity_name": fact.get("entity_name"),
                "fact_type": fact.get("fact_type"),
                "data_origin": fact.get("data_origin"),
            }
            for fact in answer.get("facts", [])
        ],
        "evidence": [
            {
                "source": evidence.get("source"),
                "data_origin": evidence.get("data_origin"),
            }
            for evidence in answer.get("evidence", [])
        ],
    }


@pytest.mark.parametrize(
    ("message", "mismatched_domain", "expected_capability", "expected_status", "expected_origin"),
    DEMO_QUESTIONS,
)
def test_demo_questions_use_real_routes_without_unsupported_or_fabricated_data(
    demo_api,
    record_property,
    message,
    mismatched_domain,
    expected_capability,
    expected_status,
    expected_origin,
):
    client, firestore, guidance = demo_api
    if message == "Find data engineer jobs in Bangalore":
        assert _seed_bangalore_postings(firestore) == 3

    plan_response = client.post(
        "/api/v1/intelligence/plan",
        json={"message": message, "domain": mismatched_domain},
    )
    assert plan_response.status_code == 200, plan_response.text
    plan = plan_response.json()

    answer_response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": message,
            "domain": mismatched_domain,
            "portal_type": "individual",
        },
    )
    assert answer_response.status_code == 200, answer_response.text
    answer = answer_response.json()

    planned_capabilities = plan.get("selected_capabilities", [])
    if plan.get("primary_capability") and plan["primary_capability"] not in planned_capabilities:
        planned_capabilities = [*planned_capabilities, plan["primary_capability"]]
    if expected_capability is None:
        if message == "Compare Python and Java":
            assert plan["intent"] == "unsupported_or_unclear"
            assert plan["primary_capability"] is None
            assert plan["plan_status"] == "requires_clarification"
            assert "clarification" in plan["understood"].casefold()
        else:
            assert not planned_capabilities
    else:
        assert planned_capabilities, plan
        assert plan["intent"] != "unsupported_or_unclear", plan
        assert plan["primary_capability"] == expected_capability
        expected_understood = {
            "Find data engineer jobs in Bangalore":
                "You want to search stored job postings for Data Engineer in Bengaluru.",
            "Find python developer jobs in Chennai":
                "You want to search stored job postings for Python Developer in Chennai.",
            "What does a data engineer do?":
                "You want to learn about the role of Data Engineer.",
            "What skills does a data engineer need?":
                "You want to find out which skills Data Engineer needs.",
            "Is Python becoming more popular?":
                "You want to understand how Python is trending.",
            "Give me a preparation plan for Web Developer":
                "You want a preparation plan for Web Developer.",
        }[message]
        assert plan["understood"] == expected_understood
        assert expected_capability not in plan["understood"]

    assert "CAPABILITY_UNSUPPORTED" not in answer["reason_codes"]
    assert answer["status"] == expected_status, _response_summary(answer)
    assert answer["execution_status"] != "unsupported"
    assert answer["executed_primary_capability"] == expected_capability, _response_summary(answer)
    assert all(
        fact.get("data_origin") in {"real", "local_reference_dataset", "unavailable"}
        for fact in answer["facts"]
    )
    assert all(
        evidence.get("data_origin") in {"real", "local_reference_dataset", "unavailable"}
        for evidence in answer["evidence"]
    )
    observed_origins = {
        item.get("data_origin")
        for item in answer["facts"] + answer["evidence"]
    }
    if expected_capability is not None:
        assert expected_origin in observed_origins
    assert guidance.calls == 0
    record_property("plan_intent", plan["intent"])
    record_property("plan_status", plan["plan_status"])
    record_property("plan_understood", plan["understood"])
    record_property(
        "plan_primary_capability",
        plan.get("primary_capability") or ",".join(plan.get("selected_capabilities", [])),
    )
    record_property("answer_status", answer["status"])
    record_property("answer_capability", answer["executed_primary_capability"] or "")
    record_property("answer_data_origins", ",".join(sorted(origin for origin in observed_origins if origin)))

    if message == "Find data engineer jobs in Bangalore":
        postings = answer["facts"][0]["details"]["postings"]
        assert len(postings) == 3
        assert {posting["posting_id"] for posting in postings} == {
            "demo-data-engineer-1",
            "demo-data-engineer-2",
            "demo-data-engineer-3",
        }
        assert answer["facts"][0]["data_origin"] == "real"
    elif message == "Find python developer jobs in Chennai":
        assert not any(fact.get("details", {}).get("postings") for fact in answer["facts"])
        assert "not enough" in answer["answer"].casefold() or "unavailable" in answer["answer"].casefold()
    elif message == "Compare Python and Java":
        assert "direct skill comparisons are not supported yet" in answer["answer"].casefold()
        assert "separate trend lookups for python and java" in answer["answer"].casefold()
        assert not answer["planned_capabilities"]
        assert not answer["facts"]
        assert not answer["evidence"]
    elif expected_capability is None:
        assert not answer["planned_capabilities"]
        assert not answer["facts"]
        assert not answer["evidence"]


@pytest.mark.parametrize(
    ("message", "expected_ids", "expected_status", "expected_matches", "expected_city"),
    [
        (
            "Find data engineer jobs in Bangalore",
            {"mixed-city-01", "mixed-city-02", "mixed-city-03", "mixed-city-04", "mixed-city-05", "mixed-city-06"},
            "ready",
            6,
            "Bengaluru",
        ),
        (
            "Find data engineer jobs in Chennai",
            {"mixed-city-07", "mixed-city-08", "mixed-city-09", "mixed-city-10"},
            "ready",
            4,
            "Chennai",
        ),
        (
            "Find data engineer jobs in Kolkata",
            set(),
            "insufficient_data",
            0,
            "Kolkata",
        ),
        (
            "Find remote data engineer jobs in Bangalore",
            {"mixed-city-01", "mixed-city-05"},
            "ready",
            2,
            "Bengaluru",
        ),
    ],
)
def test_v2_job_search_filters_city_and_remote_with_truthful_counts(
    demo_api,
    message,
    expected_ids,
    expected_status,
    expected_matches,
    expected_city,
):
    client, firestore, guidance = demo_api
    jobs_by_id = _seed_mixed_city_postings(firestore)
    plan_response = client.post(
        "/api/v1/intelligence/plan",
        json={"message": message, "domain": "skill"},
    )
    answer_response = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": message,
            "domain": "skill",
            "portal_type": "individual",
        },
    )

    assert plan_response.status_code == 200, plan_response.text
    assert answer_response.status_code == 200, answer_response.text
    answer = answer_response.json()
    assert answer["executed_primary_capability"] == "job_verified_postings"
    assert answer["status"] == expected_status, _response_summary(answer)
    assert guidance.calls == 0

    posting_fact = next(
        fact for fact in answer["facts"] if fact["fact_type"] == "stored_job_postings"
    )
    postings = posting_fact["details"]["postings"]
    assert {posting["posting_id"] for posting in postings} == expected_ids
    assert all(
        posting["source_url"] == jobs_by_id[posting["posting_id"]].source_url
        for posting in postings
    )
    assert all(
        posting["location"].split(",", 1)[0] in {"Bangalore", "Bengaluru"}
        for posting in postings
    ) if expected_city == "Bengaluru" else all(
        posting["location"].split(",", 1)[0] == expected_city
        for posting in postings
    )
    assert posting_fact["details"]["scanned_count"] == 22
    assert posting_fact["details"]["matched_count"] == expected_matches
    summary = posting_fact["details"]["search_summary"]
    assert f"scanned 22, matched {expected_matches}, city {expected_city}".casefold() in summary.casefold()
    assert "live search is off" in summary.casefold()

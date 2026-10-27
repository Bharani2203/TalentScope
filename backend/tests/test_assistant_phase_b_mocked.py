"""Phase B assistant behavior checks using only local mocks and fixtures."""

from datetime import datetime, timezone
from types import SimpleNamespace
import pytest

from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.models.job import Job
from app.models.skill_intelligence import MarketObservation
from app.services.assistant_feature_registry import INTENT_FEATURES
from app.services.execution_orchestrator_service import (
    ExecutionOrchestratorService,
    _valid_application_url,
)
from app.services.intent_planner_service import IntentPlannerService
from app.services.role_alias_service import normalize_role_alias, role_alias_soc_code


class MockGemini:
    def __init__(self, result=None, error="unavailable"):
        self.result = result
        self.last_error_class = error

    def generate_structured_json(self, **_kwargs):
        return self.result

    def is_available(self):
        return False

    def generate_grounded_explanation(self, **_kwargs):
        return None


def _plan(message="show jobs", intent="search_jobs", features=None, secondary=None):
    features = features or ["job_posting_search"]
    secondary = secondary or []
    return IntelligencePlanResponse(
        request_id="plan_test", user_message=message, portal_type="individual",
        intent=intent, intent_confidence=0.9, intent_explanation="mocked",
        selected_capabilities=features, primary_capability=features[0] if features else None,
        secondary_intents=secondary, context_summary={"primary_entity": "Data Engineer"},
        plan_status="ready_to_execute",
    )


def _mock_conversation_store():
    return SimpleNamespace(
        create_conversation=lambda **_kwargs: SimpleNamespace(conversation_id="mock-conversation"),
        check_conversation_access=lambda *_args, **_kwargs: (True, None),
        get_conversation=lambda *_args, **_kwargs: None,
        resolve_follow_up=lambda *_args, **_kwargs: (None, [], None, None),
        save_turn=lambda *_args, **_kwargs: None,
    )


def _job(
    job_id, *, title="Data Engineer", location="Bengaluru", url="https://jobs.example/apply/1",
    description="Python and SQL", country="India", country_code="in",
    skills_raw=("Python", "SQL"),
):
    return Job(
        job_id=job_id, title=title, company_name="Example Co", location=location,
        country=country, country_code=country_code, description=description, posted_at=datetime.now(timezone.utc).isoformat(),
        source="jsearch", source_url=url, skills_raw=list(skills_raw),
        fetched_at=datetime.now(timezone.utc),
    )


class _SearchSnapshot:
    def __init__(self, job):
        self.id = job.job_id
        self.record = job.model_dump(mode="json")

    def to_dict(self):
        return dict(self.record)


class _SearchQuery:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.page_size = None

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self.page_size = value
        return self

    def stream(self):
        return iter(self.snapshots[:self.page_size])


class _SearchFirestore:
    def __init__(self, jobs):
        self.query = _SearchQuery([_SearchSnapshot(job) for job in jobs])

    def collection(self, name):
        assert name == "jobs"
        return self.query


def _service_with_saved_turn(saved=True):
    postings = [
        {
            "posting_id": "job-1", "title": "Remote Data Engineer", "company": "Example Co",
            "location": "Remote", "posting_date": "2026-10-21", "source": "jsearch",
            "source_url": "https://jobs.example/1", "summary": "Python, SQL and data pipelines",
            "required_skills": ["Python", "SQL"], "extracted_skills": [
                {"normalized_name": "Python"}, {"normalized_name": "SQL"},
            ],
        },
        {
            "posting_id": "job-2", "title": "Data Engineer", "company": "Example Co",
            "location": "Bengaluru", "posting_date": "2026-10-20", "source": "adzuna",
            "source_url": "https://jobs.example/2", "summary": "Python and Spark",
            "required_skills": ["Python", "Spark"], "extracted_skills": [
                {"normalized_name": "Python"}, {"normalized_name": "Spark"},
            ],
        },
    ] if saved else []
    prior_response = {"facts": [{"fact_type": "stored_job_postings", "data_origin": "real", "details": {"postings": postings}}]} if saved else {"facts": []}
    turn = SimpleNamespace(
        user_message="find Data Engineer jobs", turn_id="turn-prior",
        response_payload=prior_response, intent="search_jobs",
    )
    service = object.__new__(ExecutionOrchestratorService)
    service.reference_store = None
    service.conversation_store = SimpleNamespace(
        get_conversation=lambda *_args, **_kwargs: SimpleNamespace(turns=[turn]),
    )
    return service


def _market_observations(*skills):
    observations = []
    for skill, skill_id, growth in skills:
        for month, value in zip((6, 7, 8, 9), (100, 110, 120, growth)):
            period = f"2026-{month:02d}"
            observations.append(MarketObservation(
                id=f"mock-{skill_id}-{period}", source="jsearch", signal_type="demand",
                observed_at=datetime(2026, month, 15, 12, tzinfo=timezone.utc),
                period=period, location="Global", scope="global", skill=skill,
                skill_id=skill_id, value=float(value), unit="job_postings",
                metadata={}, data_origin="real", history_type="platform_collected",
                series_id=f"jsearch:demand:{skill_id}:v1", query_id="jsearch:demand:mock-v1",
                quality="valid", provider_posted_at=datetime.now(timezone.utc),
            ))
    return observations


@pytest.mark.parametrize(
    ("message", "intent", "capability"),
    [
        ("Is Python becoming more popular?", "analyze_trend", "trend_velocity_analysis"),
        ("What are the latest skill trends?", "rank_skill_trends", "trend_velocity_analysis"),
        ("Compare Python and Java trends", "compare_entities", "trend_velocity_analysis"),
    ],
)
def test_trend_questions_route_with_mock_provider_and_market_evidence(message, intent, capability):
    planner = IntentPlannerService(llm_service=MockGemini())
    plan = planner.create_plan(IntelligencePlanRequest(message=message))
    assert plan.intent == intent
    assert capability in plan.selected_capabilities


def test_popularity_question_runs_trend_handler_with_mocked_observations(monkeypatch):
    from app.storage.conversation_store import ConversationStore

    monkeypatch.setattr(
        ConversationStore, "get_instance",
        classmethod(lambda _cls: _mock_conversation_store()),
    )
    observations = _market_observations(("Python", "python", 145))
    service = ExecutionOrchestratorService(
        llm_service=MockGemini(), observation_store=SimpleNamespace(client=None),
        conversation_store=_mock_conversation_store(),
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Is Python becoming more popular?", observations=observations,
    ))
    assert response.intent == "analyze_trend"
    assert response.capabilities_used == ["trend_velocity_analysis"]
    assert any(fact.fact_type == "trend_analysis" for fact in response.facts)


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("What are the latest skill trends?", "rank_skill_trends"),
        ("Compare Python and Java trends", "compare_entities"),
    ],
)
def test_rank_and_compare_routes_execute_with_mocked_observations(monkeypatch, message, expected_intent):
    from app.storage.conversation_store import ConversationStore

    monkeypatch.setattr(
        ConversationStore, "get_instance",
        classmethod(lambda _cls: _mock_conversation_store()),
    )
    observations = _market_observations(
        ("Python", "python", 145), ("Java", "java", 135),
    )
    service = ExecutionOrchestratorService(
        llm_service=MockGemini(), observation_store=SimpleNamespace(client=None),
        conversation_store=_mock_conversation_store(),
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message=message, observations=observations,
    ))
    assert response.intent == expected_intent
    assert response.facts
    assert response.evidence


def _planner_without_io(gemini):
    planner = IntentPlannerService(llm_service=gemini)
    planner._extract_and_resolve_entities = lambda *_args: []
    planner._build_context = lambda *_args: ({}, [], [])
    planner._evaluate_selected_capabilities = lambda *_args: ([], [])
    planner._determine_plan_status = lambda *_args: "ready_to_execute"
    return planner


def test_routing_guard_rejects_feature_that_does_not_match_gemini_intent():
    gemini = MockGemini({
        "intent": "search_jobs", "secondary_intents": [],
        "features": ["skill_gap_role_fit"], "skills": [], "technologies": [],
        "role": "", "location": "",
    })
    planner = _planner_without_io(gemini)
    plan = planner.create_plan(IntelligencePlanRequest(message="What is the demand trend for Python?"))
    assert plan.intent == "analyze_trend"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert "job_posting_search" not in plan.selected_capabilities


def test_routing_registry_accepts_only_registered_intent_feature_pairs():
    assert "job_posting_search" in INTENT_FEATURES["search_jobs"]
    assert "skill_gap_role_fit" not in INTENT_FEATURES["search_jobs"]


def test_stored_job_search_reports_counts_defaults_india_and_applies_city_remote_filters():
    service = object.__new__(ExecutionOrchestratorService)
    mocked_jobs = [
        _job("remote", title="Remote Data Engineer", location="Bengaluru"),
        _job("local", title="Data Engineer", location="Bengaluru"),
        _job("unknown", title="Data Engineer", location=""),
    ]
    service.firestore_store = SimpleNamespace(client=None)
    service.reference_store = None
    captured = {}

    def searcher(**kwargs):
        captured.update(kwargs)
        return mocked_jobs

    service.job_searcher = searcher
    request = CoreIntelligenceAnswerRequest(
        message="Show remote Data Engineer jobs in Bengaluru", location="Bengaluru",
    )
    facts, _evidence, limitations = service._handle_job_posting_search(request, _plan(request.message))
    job_fact = next(item for item in facts if item.fact_type == "stored_job_postings")
    assert captured["country"] is None
    assert job_fact.metric_value == 1
    assert job_fact.details["stored_postings_scanned"] == 3
    assert job_fact.details["stored_postings_query_matched"] == 3
    assert job_fact.details["missing_remote_evidence_excluded"] == 0
    assert job_fact.details["missing_city_location_excluded"] == 1
    assert job_fact.details["live_provider_search"] == "off"
    assert any("Live provider search is off" in item for item in limitations)


def test_stored_search_defaults_to_india_only_for_an_india_only_collection():
    from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

    class Snapshot:
        def __init__(self, job):
            self.id = job.job_id
            self.record = job.model_dump(mode="json")

        def to_dict(self):
            return dict(self.record)

    class Query:
        def __init__(self, snapshots):
            self.snapshots = snapshots
            self.filters = []
            self.page_size = None
            self.cursor_id = None

        def where(self, *, filter):
            self.filters.append(filter)
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def limit(self, value):
            self.page_size = value
            return self

        def start_after(self, snapshot):
            self.cursor_id = snapshot.id
            return self

        def stream(self):
            start = 0
            if self.cursor_id is not None:
                start = next(
                    (index + 1 for index, snapshot in enumerate(self.snapshots) if snapshot.id == self.cursor_id),
                    len(self.snapshots),
                )
            page = self.snapshots[start:]
            return iter(page if self.page_size is None else page[:self.page_size])

    class Firestore:
        def __init__(self, snapshots):
            self.query = Query(snapshots)

        def collection(self, _name):
            return self.query

    india = search_stored_jsearch_jobs_with_stats(
        query="Data Engineer", firestore_client=Firestore([Snapshot(_job("in-1"))]),
    )
    mixed = search_stored_jsearch_jobs_with_stats(
        query="Data Engineer",
        firestore_client=Firestore([
            Snapshot(_job("in-2")), Snapshot(_job("us-1", country="United States", country_code="us")),
        ]),
    )
    assert india.country_filter_applied == "in"
    assert mixed.country_filter_applied is None
    assert india.scanned_count == 1 and india.matched_count == 1
    assert mixed.scanned_count == 2 and mixed.matched_count == 2


def test_stored_search_requires_whole_query_words_in_title():
    from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

    firestore = _SearchFirestore([
        _job("data-engineer", title="Data Engineer"),
        _job("staff-data-engineer", title="Staff Data Engineer"),
        _job("data-engineering-manager", title="Data Engineering Manager"),
        _job("java-developer", title="Java Developer"),
        _job("javascript-developer", title="JavaScript Developer"),
        _job("description-only", title="Operations Analyst", description="Data engineer needed"),
    ])

    role_results = search_stored_jsearch_jobs_with_stats(
        query="data engineer", firestore_client=firestore,
    )
    java_results = search_stored_jsearch_jobs_with_stats(
        query="java", firestore_client=firestore,
    )

    assert {job.job_id for job in role_results} == {"data-engineer", "staff-data-engineer"}
    assert {job.job_id for job in java_results} == {"java-developer"}


# ---------------------------------------------------------------------------
# _title_matches_query: contiguous phrase and whole-word unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "title,should_match",
    [
        # MUST match: contiguous "data engineer" phrase
        ("Data Engineer", True),
        ("Senior Data Engineer", True),
        # MUST NOT match: words present but not contiguous / not in phrase order
        ("Software Engineer, Stripe Data Pipeline", False),
        ("Big Data Platform Engineer", False),
    ],
)
def test_title_matches_query_data_engineer_phrase(title, should_match):
    """Multi-word role query requires contiguous whole-phrase match."""
    from app.services.job_storage_service import _title_matches_query
    result = _title_matches_query(
        title=title,
        query="data engineer",
        meaningful_words=["data", "engineer"],
    )
    assert result is should_match, (
        f"_title_matches_query({title!r}) returned {result}, expected {should_match}"
    )


@pytest.mark.parametrize(
    "title,query,meaningful_words,should_match",
    [
        # Single-word "Go" — must not match "Google"
        ("Go Developer",           "go",     ["go"],     True),
        ("Google Cloud Engineer",  "go",     ["go"],     False),
        # Single-word "R" — must not match "Research"
        ("R Developer",            "r",      ["r"],      True),
        ("Research Analyst",       "r",      ["r"],      False),
        # Single-word "Django" — must match "Django REST Framework"
        ("Django REST Framework Developer", "django", ["django"], True),
        ("React Developer",                "django", ["django"], False),
    ],
)
def test_title_matches_query_single_word_whole_word(title, query, meaningful_words, should_match):
    """Single-word queries use whole-word boundary matching (no partial hits)."""
    from app.services.job_storage_service import _title_matches_query
    result = _title_matches_query(
        title=title,
        query=query,
        meaningful_words=meaningful_words,
    )
    assert result is should_match, (
        f"_title_matches_query({title!r}, query={query!r}) returned {result}, "
        f"expected {should_match}"
    )


def test_stored_skill_search_uses_registered_skill_and_whole_words():
    from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

    firestore = _SearchFirestore([
        _job("python-structured", title="Operations Analyst", skills_raw=["Python"]),
        _job("python-description", title="Operations Manager", description="Uses Python daily", skills_raw=[]),
        _job("javascript-only", title="Frontend Developer", description="JavaScript experience", skills_raw=[]),
    ])
    python_results = search_stored_jsearch_jobs_with_stats(
        query="Python jobs", firestore_client=firestore,
    )
    java_results = search_stored_jsearch_jobs_with_stats(
        query="Java", firestore_client=firestore,
    )

    assert {job.job_id for job in python_results} == {"python-structured", "python-description"}
    assert list(java_results) == []


def test_ambiguous_skill_search_needs_title_or_structured_skill():
    from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

    firestore = _SearchFirestore([
        _job("good-description", title="Backend Developer", description="Good engineering practices", skills_raw=[]),
        _job("go-description", title="Backend Developer", description="Uses Go language", skills_raw=[]),
        _job("go-structured", title="Backend Developer", description="Backend work", skills_raw=["Go"]),
        _job("go-title", title="Go Developer", description="Backend work", skills_raw=[]),
    ])
    results = search_stored_jsearch_jobs_with_stats(
        query="Go developer", firestore_client=firestore,
    )

    assert {job.job_id for job in results} == {"go-structured", "go-title"}


def test_stored_search_counts_city_and_keeps_related_titles_out_of_matches():
    from app.services.job_storage_service import search_stored_jsearch_jobs_with_stats

    firestore = _SearchFirestore([
        _job("related-analyst-1", title="Staff Data Analyst", location="Bengaluru-VTP, India"),
        _job("related-analyst-2", title="Staff Data Analyst", location="Bengaluru-Whitefield"),
        _job("related-scientist", title="Data Scientist", location="Bengaluru / Chennai"),
        _job("related-architect", title="Data Architect", location="Bengaluru"),
        _job("related-product", title="Data Product Manager", location="Bengaluru"),
        _job("related-operations", title="Data Operations Associate", location="Bengaluru"),
        _job("related-strategy", title="Data Strategy Lead", location="Bengaluru"),
        _job("generic-only", title="Senior Engineer", location="Bengaluru"),
        _job("outside-city", title="Data Analyst", location="Chennai"),
    ])
    result = search_stored_jsearch_jobs_with_stats(
        query="data engineer", location="Bangalore", firestore_client=firestore,
    )
    no_chennai = search_stored_jsearch_jobs_with_stats(
        query="data engineer", location="Chennai",
        firestore_client=_SearchFirestore([
            _job("chennai-no-related", title="Support Specialist", location="Chennai"),
        ]),
    )

    assert result.scanned_count == 9
    assert result.city_posting_count == 8
    assert list(result) == []
    assert result.matched_count == 0
    assert result.related_titles == [
        "Staff Data Analyst",
        "Data Scientist",
        "Data Architect",
        "Data Product Manager",
        "Data Operations Associate",
    ]
    assert no_chennai.city_posting_count == 1
    assert no_chennai.matched_count == 0
    assert no_chennai.related_titles == []


def test_city_normalization_handles_alias_segments_and_multi_city_locations():
    from app.services.job_storage_service import (
        _location_matches_city,
        _normalize_city,
    )

    assert _normalize_city("Bengaluru-VTP, India") == "bengaluru"
    assert _normalize_city("Bengaluru-Whitefield") == "bengaluru"
    assert _normalize_city("Mangalore, India") == "mangalore"
    assert not _location_matches_city("Mangalore, India", "Bangalore")
    assert _location_matches_city("Chennai / Bengaluru", "Bangalore")
    assert _location_matches_city("Chennai / Bengaluru", "Chennai")


def test_application_url_validation_requires_http_scheme_host_and_no_whitespace():
    assert _valid_application_url("https://jobs.example/apply")
    assert _valid_application_url("http://127.0.0.1:8080/job")
    assert not _valid_application_url("javascript:alert(1)")
    assert not _valid_application_url("https:///missing-host")
    assert not _valid_application_url("https://jobs.example/a path")


def test_saved_job_followups_reuse_ids_for_remote_city_skills_and_links():
    service = _service_with_saved_turn()
    for question, kind, expected in (
        ("only remote", "remote", "job-1"),
        ("which are in Bengaluru", "city", "job-2"),
        ("what skills do these jobs require", "skills", "Python"),
        ("show the links", "links", "https://jobs.example/1"),
    ):
        request = CoreIntelligenceAnswerRequest(message=question, conversation_id="conv-1")
        response = service._answer_saved_job_follow_up(
            request, _plan(question), None, "individual", kind,
        )
        if expected.startswith("job-"):
            assert expected in response.facts[0].details["postings"][0]["posting_id"]
        else:
            assert expected in response.answer
        assert "no new search was run" in response.limitations[0].casefold()


def test_saved_job_followups_without_saved_results_ask_for_a_new_search():
    service = _service_with_saved_turn(saved=False)
    for question, kind in (
        ("only remote", "remote"),
        ("which are in Bengaluru", "city"),
        ("what skills do these jobs require", "skills"),
    ):
        request = CoreIntelligenceAnswerRequest(message=question, conversation_id="conv-1")
        response = service._answer_saved_job_follow_up(
            request, _plan(question), None, "individual", kind,
        )
        assert response.status == "insufficient_data"
        assert "saved job results are unavailable" in response.answer.casefold()


def test_company_summary_uses_stored_job_fields_and_says_address_unavailable():
    service = object.__new__(ExecutionOrchestratorService)
    fact = {
        "fact_type": "stored_job_postings", "metric_value": 2,
        "metric_name": "stored_postings_found", "source": "firestore_jobs",
        "details": {
            "company_query": "Example Co", "stored_postings_scanned": 5,
            "postings": [
                {"title": "Data Engineer", "location": "Bengaluru"},
                {"title": "ML Engineer", "location": "Remote"},
            ],
        },
    }
    from app.models.execution_orchestrator import StructuredFact
    from app.models.intent_planner import IntelligencePlanResponse
    response = service._synthesize_answer(
        "company_postings_summary", [StructuredFact.model_validate(fact)], [],
        ["job_posting_search"], CoreIntelligenceAnswerRequest(message="Tell me about Example Co"),
        plan=_plan("Tell me about Example Co", intent="company_postings_summary"),
    )
    assert "2 matching postings" in response
    assert "Data Engineer" in response and "Bengaluru" in response
    assert "Company address unavailable" in response
    assert "website" in response


def test_combined_question_is_split_only_when_two_registered_features_are_selected():
    service = object.__new__(ExecutionOrchestratorService)
    question = "Show the Python trend and find Python jobs"
    assert service._looks_like_combined_question(question)
    gemini = MockGemini({
        "intent": "analyze_trend", "secondary_intents": ["search_jobs"],
        "features": ["trend_velocity_analysis", "job_posting_search"],
        "skills": ["Python"], "technologies": [], "role": "", "location": "",
    })
    plan = _planner_without_io(gemini).create_plan(IntelligencePlanRequest(message=question))
    assert plan.intent == "analyze_trend"
    assert plan.secondary_intents == ["search_jobs"]
    assert plan.selected_capabilities == ["trend_velocity_analysis", "job_posting_search"]
    assert set(plan.selected_capabilities).issubset(
        INTENT_FEATURES["analyze_trend"] | INTENT_FEATURES["search_jobs"]
    )


def test_platform_help_is_built_from_capability_and_handler_registries():
    service = object.__new__(ExecutionOrchestratorService)
    request = CoreIntelligenceAnswerRequest(message="What features are available?")
    response = service._platform_help_response(request, _plan(request.message, "platform_help", []), "individual")
    assert "registered capability and handler catalogs" in response.answer
    assert "Available:" in response.answer
    assert "Planned or unavailable:" in response.answer


def test_role_aliases_normalize_plural_and_ml_engineer():
    assert normalize_role_alias("Data Engineers") == "data engineer"
    assert normalize_role_alias("ML engineer") == "machine learning engineer"
    assert role_alias_soc_code("Data Engineers") == role_alias_soc_code("Data Engineer")
    assert role_alias_soc_code("ML engineer")

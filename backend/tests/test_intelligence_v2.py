"""Tests for Greenfield Intelligence Engine V2.

Verifies contracts, canonical skill mapping, ambiguity guards, evidence retrieval,
capability registry, intent planning, domain execution, role actions, and adapter compatibility.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from datetime import datetime, timezone
from app.intelligence_v2.adapter import V2ExecutionOrchestratorAdapter
from app.intelligence_v2.capability_registry import CAPABILITIES, V2CapabilityRegistry
from app.intelligence_v2.contracts import (
    V2EvidenceItem,
    V2StructuredFact,
)
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.india_collector_design import V2IndiaCollectorPipeline
from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.intent_planner import PlannedIntent
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.market_intelligence import V2MarketIntelligenceEngine
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.role_actions import V2RoleActionEngine
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine
from app.intelligence_v2.skill_mapping import V2SkillMapper
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.reference_data import GitHubLanguageAdoption
from app.models.skill_intelligence import MarketObservation
from app.storage.reference_store import ReferenceDataStore


@pytest.fixture(autouse=True)
def _isolate_firestore(injected_empty_firestore):
    return injected_empty_firestore


def test_non_emulator_grpc_target_fails_loudly():
    tests_dir = Path(__file__).parent
    probe_dir = tests_dir / f"network_guard_probe_{uuid.uuid4().hex}"
    probe_dir.mkdir()
    probe_file = probe_dir / "test_blocked_target.py"
    probe_file.write_text(
        "import grpc\n"
        "def test_blocked_target():\n"
        "    grpc.insecure_channel('non-emulator.example:443')\n",
        encoding="utf-8",
    )
    reports_dir = tests_dir.parent / ".test_reports"
    reports_dir.mkdir(exist_ok=True)
    output_path = reports_dir / "grpc-blocked-target-probe.log"
    try:
        child_env = os.environ.copy()
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "--tb=short", str(probe_file),
            ],
            cwd=tests_dir.parent,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        output = result.stdout + result.stderr
        output_path.write_text(output, encoding="utf-8")
        assert result.returncode != 0
        assert "Outbound network blocked by pytest guard" in output
        assert "non-emulator.example:443" in output
    finally:
        probe_file.unlink(missing_ok=True)
        probe_dir.rmdir()


# -----------------------------------------------------------------------------
# 1. Shared Contracts & Standardized Evidence
# -----------------------------------------------------------------------------

def test_v2_evidence_item_conversion() -> None:
    v2_evi = V2EvidenceItem(
        evidence_id="evi:test:1",
        source="GitHub Innovation Graph",
        signal_family="developer_adoption",
        measured_signal_type="num_pushers",
        period="2026-Q1",
        time_grain="quarter",
        unit="pushers",
        data_origin="real",
        source_url="https://github.com/github/innovationgraph",
        description="Quarterly pushers test evidence",
    )
    public_evi = v2_evi.to_public_evidence()
    assert public_evi.evidence_id == "evi:test:1"
    assert public_evi.source == "GitHub Innovation Graph"
    assert public_evi.signal_type == "developer_adoption"
    assert public_evi.measured_signal_type == "num_pushers"
    assert public_evi.period == "2026-Q1"
    assert public_evi.unit == "pushers"
    assert public_evi.data_origin == "real"
    assert public_evi.source_url == "https://github.com/github/innovationgraph"


def test_v2_structured_fact_conversion() -> None:
    v2_fact = V2StructuredFact(
        fact_id="fact:test:1",
        fact_type="developer_adoption_latest",
        entity_name="Python",
        metric_name="num_pushers",
        metric_value=450000,
        unit="pushers",
        period="2026-Q1",
        source="GitHub Innovation Graph",
        data_origin="real",
    )
    public_fact = v2_fact.to_public_fact()
    assert public_fact.fact_id == "fact:test:1"
    assert public_fact.fact_type == "developer_adoption_latest"
    assert public_fact.entity_name == "Python"
    assert public_fact.metric_name == "num_pushers"
    assert public_fact.metric_value == 450000
    assert public_fact.period == "2026-Q1"


# -----------------------------------------------------------------------------
# 2. Canonical Skill Mapping & Ambiguity Guards
# -----------------------------------------------------------------------------

def test_skill_mapper_known_unambiguous() -> None:
    mapper = V2SkillMapper()
    res = mapper.normalize("Python")
    assert res.status == "matched"
    assert res.canonical_name == "Python"
    assert res.canonical_id == "python"
    assert not res.ambiguous


def test_skill_mapper_ambiguous_isolated() -> None:
    mapper = V2SkillMapper()
    # Isolated 'go' without programming context
    res = mapper.normalize("go")
    assert res.status == "partial"
    assert res.ambiguous is True
    assert res.context_required is True
    assert "Disambiguation required" in (res.notes or "")


def test_skill_mapper_ambiguous_with_context() -> None:
    mapper = V2SkillMapper()
    # 'go' with programming context
    res = mapper.normalize("go", context="backend software engineer Go developer")
    assert res.status == "matched"
    assert res.canonical_name == "Go"


def test_skill_mapper_unmapped_token() -> None:
    mapper = V2SkillMapper()
    res = mapper.normalize("completely_unknown_fictional_tool_xyz_99")
    assert res.status == "unmapped"


def test_role_skill_alignment_declaration_semantics() -> None:
    mapper = V2SkillMapper()
    alignment = mapper.align_role_skills(
        role_name="Software Developers",
        declared_skills=["Python", "Git", "SQL"],
    )
    assert alignment.role_name == "Software Developers"
    assert alignment.coverage_denominator > 0
    assert len(alignment.matched_skills) >= 1
    # Check that not_declared skills are identified and disclaimer is present
    assert len(alignment.not_declared_skills) > 0
    assert "not declared" in alignment.disclaimer.lower()


# -----------------------------------------------------------------------------
# 3. Evidence & Provenance Retriever
# -----------------------------------------------------------------------------

def test_evidence_retriever_github_adoption() -> None:
    retriever = V2EvidenceRetriever()
    items = retriever.get_developer_adoption_evidence("Python")
    assert len(items) >= 1
    evi = items[0]
    assert evi.signal_family == "developer_adoption"
    assert evi.time_grain == "quarter"
    assert evi.unit == "pushers"
    assert evi.data_origin == "real"
    assert evi.source_url == "https://github.com/github/innovationgraph"


def test_evidence_retriever_hiring_demand_empty() -> None:
    retriever = V2EvidenceRetriever()
    # Hiring demand has 0 observations currently
    items = retriever.get_hiring_demand_evidence("Python")
    assert len(items) == 1
    evi = items[0]
    assert evi.signal_family == "hiring_demand"
    assert evi.readiness_state == "insufficient_data"
    assert evi.data_origin == "unavailable"


def test_evidence_retriever_benchmark_quarantine() -> None:
    retriever = V2EvidenceRetriever()
    items = retriever.get_benchmark_evidence()
    assert len(items) == 1
    evi = items[0]
    assert evi.signal_family == "benchmark"
    assert evi.readiness_state == "reader_unavailable"
    assert evi.quality == "quarantined"


# -----------------------------------------------------------------------------
# 4. Capability Registry & Readiness Rules
# -----------------------------------------------------------------------------

def test_all_15_capabilities_registered() -> None:
    registry = V2CapabilityRegistry()
    caps = registry.list_capabilities()
    assert len(caps) == 15
    domains = {c.domain for c in caps}
    assert domains == {"skill_intelligence", "market_intelligence", "job_intelligence"}


def test_market_trend_velocity_readiness_insufficient() -> None:
    registry = V2CapabilityRegistry()
    # 0 months available
    readiness = registry.evaluate_readiness("market_trend_velocity", months_available=0)
    assert readiness.is_executable is False
    assert readiness.state == "insufficient_data"
    assert readiness.months_required == 4
    assert readiness.months_available == 0


def test_skill_role_alignment_readiness_requires_profile() -> None:
    registry = V2CapabilityRegistry()
    readiness = registry.evaluate_readiness("skill_role_alignment", has_profile=False)
    assert readiness.is_executable is False
    assert readiness.state == "insufficient_data"


# -----------------------------------------------------------------------------
# 5. Intent Planner
# -----------------------------------------------------------------------------

def test_intent_planner_skill_demand() -> None:
    planner = V2IntentPlanner()
    intent = planner.plan("What is the demand trend for Python?")
    assert intent.capability_id == "skill_demand_trends"
    assert intent.target_skill == "Python"


def test_intent_planner_mobility_pathways() -> None:
    planner = V2IntentPlanner()
    intent = planner.plan("What are career mobility pathways for Software Developers?")
    assert intent.capability_id == "job_mobility_pathways"


def test_intent_planner_role_actions() -> None:
    planner = V2IntentPlanner()
    intent = planner.plan("What actions should I take to learn Python?")
    assert intent.capability_id == "skill_action_recommendations"
    assert intent.target_skill == "Python"


@pytest.mark.parametrize("message", ["asdfghjkl qwerty 12345", "what is the weather"])
def test_unrecognized_v2_request_returns_clarification_without_capabilities(message: str) -> None:
    orchestrator = object.__new__(V2Orchestrator)
    orchestrator.intent_planner = V2IntentPlanner()
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(message=message))

    assert response.execution_status == "requires_clarification"
    assert response.plan_status == "requires_clarification"
    assert response.planned_capabilities == []
    assert response.capabilities_used == []
    assert response.answer == "Would you like help with skills, jobs, market signals, or role information?"


def test_v2_skill_comparison_clarifies_without_comparison_handler_with_mismatched_domain(monkeypatch) -> None:
    class NoopConversations:
        pass

    orchestrator = V2Orchestrator(
        store=ReferenceDataStore(read_only=True),
        conversation_store=NoopConversations(),
    )
    executed_skills = []

    def mock_trend(skill_name, geography="global"):
        executed_skills.append(skill_name)
        return None

    monkeypatch.setattr(orchestrator.skill_engine, "run_demand_trends", mock_trend)
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="Compare Python and Java",
        domain="job",
    ))

    assert executed_skills == []
    assert response.status == "not_applicable"
    assert response.execution_status == "requires_clarification"
    assert response.planned_capabilities == []
    assert response.capabilities_used == []
    assert response.facts == []
    assert response.evidence == []
    assert "direct skill comparisons are not supported yet" in response.answer.casefold()
    assert "separate trend lookups for python and java" in response.answer.casefold()


# -----------------------------------------------------------------------------
# 6. Role Preparation Actions (Deterministic, Zero Invented Courses)
# -----------------------------------------------------------------------------

def test_deterministic_role_actions() -> None:
    engine = V2RoleActionEngine()
    skills = [
        {"name": "Python", "hot_technology": True, "in_demand": True, "element_name": "Programming"},
        {"name": "Docker", "hot_technology": False, "in_demand": False, "element_name": "DevOps"},
    ]
    plan = engine.build_plan_for_skills("Backend Developer", skills)
    assert plan.target_role == "Backend Developer"
    assert plan.total_actions == 2
    # First action is Python (Hot Tech -> High Priority)
    assert plan.actions[0].skill_name == "Python"
    assert plan.actions[0].priority == "high"
    assert len(plan.actions[0].self_check_criteria) > 0
    # No unverified course URLs
    for action in plan.actions:
        assert "http" not in action.practice_task
    assert "does not curate commercial course catalogs" in plan.limitations_notice


# -----------------------------------------------------------------------------
# 7. India Collector Design (Disabled by default, Denominator Preservation)
# -----------------------------------------------------------------------------

def test_india_collector_pipeline_disabled_status() -> None:
    pipeline = V2IndiaCollectorPipeline()
    status = pipeline.inspect_pipeline_status()
    assert status["status"] == "disabled"
    assert "Live external provider requests are disabled" in status["reason"]
    assert len(status["covered_metro_regions"]) >= 5


def test_india_collector_stable_hash_and_denominator() -> None:
    pipeline = V2IndiaCollectorPipeline()
    h1 = pipeline.compute_stable_posting_hash("jsearch", "job123", "Software Engineer", "TCS", "Bengaluru")
    h2 = pipeline.compute_stable_posting_hash("jsearch", "job123", "software engineer", "tcs", "bengaluru")
    assert h1 == h2  # Stable case-insensitive hashing

    # Test processing raw posting with zero matched skills preserves record for denominator
    raw_job = {"job_id": "job123", "job_title": "Software Engineer", "employer_name": "TCS", "job_city": "Bengaluru"}
    rec = pipeline.process_raw_posting_safely("jsearch", raw_job, matched_skills=[], unmatched_skills=["some_unmatched_kw"])
    assert rec.has_canonical_matches is False
    assert rec.unmatched_tokens == ["some_unmatched_kw"]
    assert rec.stable_posting_hash == h1


# -----------------------------------------------------------------------------
# 8. Domain Engines & Orchestrator Execution
# -----------------------------------------------------------------------------

def test_skill_intelligence_demand_trends() -> None:
    engine = V2SkillIntelligenceEngine()
    res = engine.run_demand_trends("Python")
    assert res.capability_id == "skill_demand_trends"
    assert res.target_skill == "Python"
    assert len(res.facts) >= 1
    assert len(res.evidence) >= 1
    # Check that developer adoption is quarterly and unit is pushers
    dev_evi = [e for e in res.evidence if e.signal_family == "developer_adoption"]
    assert len(dev_evi) >= 1
    assert dev_evi[0].time_grain == "quarter"
    assert dev_evi[0].unit == "pushers"


def test_market_intelligence_snapshot() -> None:
    engine = V2MarketIntelligenceEngine()
    res = engine.run_snapshot()
    assert res.capability_id == "market_intelligence_snapshot"
    assert len(res.facts) >= 1
    assert len(res.evidence) >= 1
    assert len(res.signals) > 0


def test_empty_market_views_do_not_invent_latest_period_or_source_evidence(tmp_path) -> None:
    store = ReferenceDataStore(tmp_path / "empty-market.sqlite3")
    engine = V2MarketIntelligenceEngine(store=store)

    snapshot = engine.run_snapshot(geography="IN")
    assert snapshot.facts == []
    assert snapshot.evidence == []
    assert snapshot.signals == []
    assert snapshot.readiness_state == "insufficient_data"
    assert "2026-Q1" not in snapshot.headline

    technology = engine.run_tech_signals(geography="IN")
    assert technology.facts == []
    assert technology.evidence == []
    assert technology.signals == []
    assert technology.readiness_state == "insufficient_data"
    assert "2026-Q1" not in technology.headline


def test_market_evidence_citations_only_report_sources_present_in_local_store(tmp_path) -> None:
    store = ReferenceDataStore(tmp_path / "market-evidence.sqlite3")
    engine = V2MarketIntelligenceEngine(store=store)

    empty = engine.run_evidence_citations()
    assert empty.evidence == []
    assert empty.readiness_state == "insufficient_data"
    assert "no source evidence is reported" in empty.headline.lower()

    store.upsert_github_language_adoption([GitHubLanguageAdoption(
        id="test-python-2024-q1", language="Python", language_type="programming",
        iso2_code="IN", year=2024, quarter=1, period="2024-Q1", num_pushers=25,
    )])
    populated = engine.run_evidence_citations()
    assert len(populated.evidence) == 1
    assert populated.evidence[0].source == "GitHub Innovation Graph"
    assert populated.evidence[0].period == "2024-Q1"
    assert populated.evidence[0].data_origin == "local_reference_dataset"
    assert populated.evidence[0].sample_size == 1
    assert populated.readiness_state == "observed"


def test_market_trend_velocity_insufficient_data() -> None:
    class EmptyObservationStore:
        def get_observations_by_skill(self, *args, **kwargs):
            return []

    engine = V2MarketIntelligenceEngine(observation_store=EmptyObservationStore())
    res = engine.run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert res.capability_id == "market_trend_velocity"
    assert res.readiness_state == "insufficient_data"
    assert "four consecutive completed periods" in res.headline
    assert res.facts == []
    assert res.evidence == []


def _market_trend_fixture(period: str, value: float, *, source: str = "wikipedia", series_id: str = "wikipedia:pageviews:python:v1", obs_id: str | None = None) -> MarketObservation:
    year, month = (int(part) for part in period.split("-"))
    return MarketObservation(
        id=obs_id or f"{source}-{series_id}-{period}", source=source, skill="Python",
        observed_at=datetime(year, month, 15, tzinfo=timezone.utc), period=period,
        scope="global", signal_type="interest" if source != "github" else "adoption",
        value=value, unit="pageviews" if source == "wikipedia" else "questions" if source == "stackexchange" else "repositories",
        source_url="https://example.invalid/test-fixture", history_type="backfill", data_origin="real",
        series_id=series_id, panel_version=f"{source}-fixture-v1", query_id=f"{source}:python:v1",
        extractor_version=f"{source}-extractor-v1", metadata={"metric": "test_fixture_count"},
    )


class _MarketObservationFixtureStore:
    def __init__(self, observations):
        self.observations = observations

    def get_observations_by_skill(self, *args, **kwargs):
        return list(self.observations)


def test_market_trend_velocity_measures_one_comparable_public_series():
    observations = [_market_trend_fixture(period, value) for period, value in zip(
        ("2026-05", "2026-06", "2026-07", "2026-08"), (10, 12, 13, 17)
    )]
    engine = V2MarketIntelligenceEngine(observation_store=_MarketObservationFixtureStore(observations))
    result = engine.run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))

    assert result.readiness_state == "ready"
    assert len(result.facts) == len(result.evidence) == 1
    fact = result.facts[0]
    assert fact.metric_value == 4
    assert fact.unit == "pageviews per month"
    assert fact.period == "2026-05 to 2026-08"
    assert fact.data_origin == "real"
    assert fact.details["signal_type"] == "interest"
    assert fact.details["hiring_demand_included"] is False
    assert fact.details["series"] == [
        {"period": "2026-05", "value": 10.0}, {"period": "2026-06", "value": 12.0},
        {"period": "2026-07", "value": 13.0}, {"period": "2026-08", "value": 17.0},
    ]
    assert "not hiring demand" in result.headline


def test_github_repository_adoption_velocity_stays_distinct_from_hiring():
    observations = [_market_trend_fixture(
        period, value, source="github", series_id="github:repository-topic:python:v1"
    ) for period, value in zip(("2026-05", "2026-06", "2026-07", "2026-08"), (20, 21, 23, 26))]
    result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(observations)
    ).run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "ready"
    assert result.facts[0].details["signal_type"] == "adoption"
    assert result.facts[0].source == "GitHub public repository signals"
    assert result.facts[0].details["hiring_demand_included"] is False
    assert result.evidence[0].signal_family == "developer_adoption"


def test_github_innovation_graph_quarterly_reference_series_uses_native_grain(tmp_path):
    reference_store = ReferenceDataStore(tmp_path / "github-quarterly.sqlite3")
    reference_store.upsert_github_language_adoption([
        GitHubLanguageAdoption(
            id=f"python-in-2025-q{quarter}", language="Python", language_type="programming",
            iso2_code="IN", year=2025, quarter=quarter, period=f"2025-Q{quarter}",
            num_pushers=100 + quarter * 10, canonical_skill_id="python",
        ) for quarter in range(1, 5)
    ])
    result = V2MarketIntelligenceEngine(
        store=reference_store, observation_store=_MarketObservationFixtureStore([]),
    ).run_trend_velocity("Python", geography="IN", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))

    assert result.readiness_state == "ready"
    assert result.facts[0].source == "GitHub Innovation Graph"
    assert result.facts[0].unit == "unique developers per quarter"
    assert result.facts[0].period == "2025-Q1 to 2025-Q4"
    assert result.facts[0].details["velocity_unit"] == "pushers per quarter"
    assert result.facts[0].details["hiring_demand_included"] is False
    assert result.evidence[0].time_grain == "quarter"


@pytest.mark.parametrize("observations", [
    [_market_trend_fixture(p, float(i)) for i, p in enumerate(("2026-05", "2026-06", "2026-08", "2026-09"))],
    [_market_trend_fixture("2026-05", 1), _market_trend_fixture("2026-06", 2),
     _market_trend_fixture("2026-07", 3), _market_trend_fixture("2026-08", 4),
     _market_trend_fixture("2026-08", 99, obs_id="second-august-record")],
    [_market_trend_fixture(p, float(i), series_id=f"wikipedia:python:{'left' if i < 2 else 'right'}")
     for i, p in enumerate(("2026-05", "2026-06", "2026-07", "2026-08"))],
])
def test_market_trend_velocity_rejects_gaps_duplicates_and_incompatible_series(observations):
    result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(observations)
    ).run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "insufficient_data"
    assert result.facts == []
    assert result.evidence == []


def test_market_trend_velocity_rejects_future_observations():
    observations = [_market_trend_fixture(period, 10 + index) for index, period in enumerate(
        ("2026-05", "2026-06", "2026-07", "2026-08")
    )]
    observations.append(_market_trend_fixture("2026-10", 50))
    result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(observations)
    ).run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))
    assert result.readiness_state == "ready"
    assert len(result.facts[0].details["series"]) == 4
    assert "2026-10" not in result.facts[0].period


def test_market_trend_velocity_rejects_insufficient_and_mixed_source_history():
    as_of = datetime(2026, 10, 20, tzinfo=timezone.utc)
    short = [_market_trend_fixture("2026-07", 1), _market_trend_fixture("2026-08", 2)]
    short_result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(short)
    ).run_trend_velocity("Python", as_of=as_of)
    assert short_result.readiness_state == "insufficient_data"
    assert not short_result.facts

    mixed = [
        _market_trend_fixture("2026-05", 1, source="wikipedia", series_id="wiki-python"),
        _market_trend_fixture("2026-06", 2, source="wikipedia", series_id="wiki-python"),
        _market_trend_fixture("2026-07", 8, source="stackexchange", series_id="se-python"),
        _market_trend_fixture("2026-08", 9, source="stackexchange", series_id="se-python"),
    ]
    mixed_result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(mixed)
    ).run_trend_velocity("Python", as_of=as_of)
    assert mixed_result.readiness_state == "insufficient_data"
    assert not mixed_result.facts


def test_market_trend_velocity_rejects_incompatible_denominators_and_invalid_timestamp():
    as_of = datetime(2026, 10, 20, tzinfo=timezone.utc)
    observations = [_market_trend_fixture(period, 10 + index) for index, period in enumerate(
        ("2026-05", "2026-06", "2026-07", "2026-08")
    )]
    for index, observation in enumerate(observations):
        observation.denominator = 100 + index
        observation.denominator_unit = "active_users"
    denominator_result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(observations)
    ).run_trend_velocity("Python", as_of=as_of)
    assert denominator_result.readiness_state == "insufficient_data"
    assert not denominator_result.facts

    invalid = _market_trend_fixture("2026-05", 1).model_copy(update={
        "observed_at": datetime(2026, 6, 15, tzinfo=timezone.utc),
    })
    invalid_periods = [invalid] + [_market_trend_fixture(period, value) for period, value in (
        ("2026-06", 2), ("2026-07", 3), ("2026-08", 4),
    )]
    invalid_result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(invalid_periods)
    ).run_trend_velocity("Python", as_of=as_of)
    assert invalid_result.readiness_state == "insufficient_data"
    assert not invalid_result.facts


def test_market_trend_response_contract_exposes_only_ready_real_series():
    observations = [_market_trend_fixture(period, value) for period, value in zip(
        ("2026-05", "2026-06", "2026-07", "2026-08"), (10, 12, 13, 17)
    )]
    result = V2MarketIntelligenceEngine(
        observation_store=_MarketObservationFixtureStore(observations)
    ).run_trend_velocity("Python", as_of=datetime(2026, 10, 20, tzinfo=timezone.utc))
    intent = PlannedIntent(
        capability_id="market_trend_velocity", target_skill="Python",
        target_role=None, geography="all", entities=[], confidence=1.0,
        reason="explicit market trend test",
    )
    response = V2ResponseFormatter.format_response(
        user_message="What technology interest trend is measured for Python?",
        portal_type="individual", intent=intent, result=result,
    )
    assert response.status == "ready"
    assert response.facts[0].readiness_state == "ready"
    assert response.facts[0].data_origin == "real"
    assert response.facts[0].details["series"]
    assert response.metric_results[0].readiness_state == "ready"
    assert response.evidence[0].signal_type == "public_attention"


def test_market_trend_missing_data_uses_only_labelled_gemini_b_guidance_and_safe_fallback(tmp_path):
    class EmptyObservationStore:
        def get_observations_by_skill(self, *args, **kwargs):
            return []

    class Guidance:
        def __init__(self, text):
            self.text = text
            self.calls = 0

        def generate(self, **kwargs):
            self.calls += 1
            assert kwargs["capability_id"] == "market_trend_velocity"
            return self.text

    request = CoreIntelligenceAnswerRequest(
        message="What trend is observed for Python?", domain="market",
        capability_id="market_trend_velocity",
    )
    settings = ReferenceDataStore(tmp_path / "trend-answer-reference.sqlite3")
    guidance = Guidance("AI-generated qualitative guidance: compare consistent observations from the same source over completed periods.")
    response = V2Orchestrator(
        store=settings, observation_store=EmptyObservationStore(), gemini_b_service=guidance,
    ).execute_request(request)
    assert guidance.calls == 1
    assert response.answer_origin == "gemini"
    assert response.source_mode == "ai_general_guidance"
    assert response.facts == [] and response.evidence == [] and response.metric_results == []
    assert "not a measured TalentScope result" in response.limitations[0]

    no_guidance = Guidance(None)
    fallback = V2Orchestrator(
        store=settings, observation_store=EmptyObservationStore(), gemini_b_service=no_guidance,
    ).execute_request(request)
    assert no_guidance.calls == 1
    assert fallback.answer_origin == "deterministic"
    assert "General AI guidance is unavailable" in fallback.answer
    assert "four consecutive completed periods" in fallback.next_actions[1]
    assert not fallback.facts and not fallback.evidence


def test_ready_market_adoption_series_does_not_consume_gemini_b(tmp_path):
    observations = [_market_trend_fixture(period, value) for period, value in zip(
        ("2026-05", "2026-06", "2026-07", "2026-08"), (10, 12, 13, 17)
    )]

    class Guidance:
        calls = 0
        def generate(self, **kwargs):
            self.calls += 1
            return "unexpected"

    guidance = Guidance()
    response = V2Orchestrator(
        store=ReferenceDataStore(tmp_path / "ready-trend-reference.sqlite3"),
        observation_store=_MarketObservationFixtureStore(observations),
        gemini_b_service=guidance,
    ).execute_request(CoreIntelligenceAnswerRequest(
        message="What trend is observed for Python?", domain="market",
        capability_id="market_trend_velocity",
    ))
    assert response.status == "ready"
    assert response.answer_origin == "deterministic"
    assert response.facts and response.evidence
    assert guidance.calls == 0


def test_job_intelligence_mobility_pathways() -> None:
    engine = V2JobIntelligenceEngine()
    res = engine.run_mobility_pathways("Software Developers")
    assert res.capability_id == "job_mobility_pathways"
    assert len(res.pathways) > 0
    assert len(res.facts) >= 1


def test_orchestrator_end_to_end_answer() -> None:
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Python?",
        portal_type="individual",
        selected_skills=["Python"],
    )
    user = AuthenticatedUser(uid="test_user_1", email="test@talentscope.ai")
    resp = orchestrator.execute_request(req, authenticated_user=user)

    assert resp.user_message == req.message
    assert resp.portal_type == "individual"
    assert resp.domain == "skill"
    assert resp.execution_status == "completed"
    assert len(resp.facts) >= 1
    assert len(resp.evidence) >= 1
    assert resp.answer_origin == "deterministic"


def test_v2_adapter_compatibility() -> None:
    adapter = V2ExecutionOrchestratorAdapter()
    req = CoreIntelligenceAnswerRequest(
        message="What are career mobility pathways for Software Developers?",
        portal_type="individual",
        target_role="Software Developers",
    )
    resp = adapter.answer(req)
    assert resp.domain == "job"
    assert resp.execution_status == "completed"
    assert "Career Mobility Pathways" in resp.answer


def test_explicit_feature_selection_bypasses_legacy_phrase_routing() -> None:
    class SelectedCapabilityOrchestrator:
        def __init__(self) -> None:
            self.request = None

        def execute_request(self, request, authenticated_user=None):
            self.request = request
            return "v2-selected-capability"

    orchestrator = SelectedCapabilityOrchestrator()
    adapter = V2ExecutionOrchestratorAdapter(orchestrator=orchestrator)
    req = CoreIntelligenceAnswerRequest(
        message="What should I do next?",
        portal_type="individual",
        domain="skill",
        capability_id="skill_action_recommendations",
    )

    response = adapter.answer(req)

    assert response == "v2-selected-capability"
    assert orchestrator.request is req


def test_follow_up_suggestions_match_capability_and_entity_context() -> None:
    market_prompts = V2ResponseFormatter._follow_up_suggestions(PlannedIntent(
        capability_id="market_evidence_citations",
        target_skill="Python",
        reason="Test fixture",
    ))
    assert len(market_prompts) == 2
    assert all("market snapshot" in prompt.lower() or "technology signals" in prompt.lower() for prompt in market_prompts)
    assert not any("career mobility" in prompt.lower() for prompt in market_prompts)

    role_prompts = V2ResponseFormatter._follow_up_suggestions(PlannedIntent(
        capability_id="job_role_requirements",
        target_role="Data Scientists",
        reason="Test fixture",
    ))
    assert len(role_prompts) == 2
    assert all("Data Scientists" in prompt for prompt in role_prompts)

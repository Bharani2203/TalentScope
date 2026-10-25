"""Phase 4B Tests: Data Recovery, Feature Enablement, and Question Routing.

Verifies:
1. Intent routing in V2IntentPlanner for reference questions, developer adoption,
   hiring demand, role skills, forecasting, and skill health.
2. Skill Health readiness integration with evaluate_skill_health from app.analytics.skill_health.
3. Forecasting 24-month gate and baseline/challenger specification.
4. Source-family separation: GitHub = developer adoption, JSearch/Adzuna = hiring demand.
5. Reference taxonomy related skills lookup from O*NET and ESCO.
6. Full orchestrator request-response execution.
"""

import pytest
import sqlite3
import shutil
from app.core.config import get_settings
from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.reference_store import ReferenceDataStore


@pytest.fixture
def store(injected_empty_firestore, tmp_path):
    source_path = get_settings().reference_database_path
    isolated_path = tmp_path / "reference.sqlite3"
    shutil.copy2(source_path, isolated_path)
    with sqlite3.connect(isolated_path) as connection:
        connection.execute("DELETE FROM market_observations")
    return ReferenceDataStore(isolated_path, read_only=True)


@pytest.fixture
def planner():
    return V2IntentPlanner()


@pytest.fixture
def skill_engine(store):
    return V2SkillIntelligenceEngine(store=store)


@pytest.fixture
def orchestrator(store):
    return V2Orchestrator(store=store)


def test_intent_routing_skill_health(planner):
    """Verify skill health queries route to skill_health_analysis."""
    queries = [
        "how healthy is Python?",
        "what is the skill health of Python",
        "is Python healthy",
        "Python health score",
        "evaluate skill health for TypeScript",
    ]
    for q in queries:
        plan = planner.plan(q)
        assert plan.capability_id == "skill_health_analysis", f"Failed on '{q}', got {plan.capability_id}"
        assert plan.target_skill in {"Python", "TypeScript"}


def test_intent_routing_forecasting(planner):
    """Verify forecasting and prediction queries route to skill_demand_forecast."""
    queries = [
        "forecast demand for Python",
        "predict demand for Java",
        "Python demand forecast",
        "projected demand for React",
    ]
    for q in queries:
        plan = planner.plan(q)
        assert plan.capability_id == "skill_demand_forecast", f"Failed on '{q}', got {plan.capability_id}"


def test_intent_routing_hiring_demand_vs_developer_adoption(planner):
    """Verify hiring demand is routed separately from developer adoption."""
    hiring_queries = [
        "is Python hiring demand increasing",
        "hiring demand for Python",
        "job hiring demand for React",
    ]
    for q in hiring_queries:
        plan = planner.plan(q)
        assert plan.capability_id == "hiring_demand_trends", f"Failed on '{q}', got {plan.capability_id}"

    adoption_queries = [
        "show my historical pushers for Python",
        "historical skill signals for Python",
        "quarterly github pushers for Rust",
    ]
    for q in adoption_queries:
        plan = planner.plan(q)
        assert plan.capability_id == "skill_historical_signals", f"Failed on '{q}', got {plan.capability_id}"


def test_intent_routing_distinguishes_related_skills_from_reference_profile(planner):
    """Route related-skill questions to their dedicated engine, not the static profile."""
    queries = [
        "which skills are related to Python",
        "skills related to Python",
    ]
    for q in queries:
        plan = planner.plan(q)
        assert plan.capability_id == "related_skills", f"Failed on '{q}', got {plan.capability_id}"

    for q in ("what skills are similar to TypeScript", "reference profile for Python"):
        plan = planner.plan(q)
        assert plan.capability_id == "skill_reference_profile", f"Failed on '{q}', got {plan.capability_id}"


def test_skill_health_insufficient_data_structure(skill_engine):
    """Verify Skill Health returns structured insufficient_data when observations < 4."""
    res = skill_engine.run_skill_health("Python")
    assert res.capability_id == "skill_health_analysis"
    assert res.target_skill == "Python"
    assert "insufficient verified observation data" in res.headline
    assert ">= 4 consecutive completed monthly periods" in res.headline

    # Verify structured facts
    readiness_facts = [f for f in res.facts if f.fact_type == "skill_health_readiness"]
    assert len(readiness_facts) == 1
    rf = readiness_facts[0]
    assert rf.readiness_state == "insufficient_data"
    assert rf.details["health_category"] == "insufficient_data"
    assert "round(clamp(50 + 50 * relative_slope_per_month / 0.03, 0, 100), 2)" in rf.details["score_formula"]
    assert rf.details["min_periods_required"] == 4
    assert rf.details["periods_available"] == 0

    # Verify evidence item is attached
    assert len(res.evidence) >= 1
    assert any(e.signal_family == "hiring_demand" for e in res.evidence)


def test_demand_forecast_gate(skill_engine):
    """Verify demand forecasting enforces the 24-month gate."""
    res = skill_engine.run_demand_forecast("Python")
    assert res.capability_id == "skill_demand_forecast"
    assert res.target_skill == "Python"
    assert "requires at least 24 consecutive monthly periods" in res.headline

    facts = [f for f in res.facts if f.fact_type == "forecast_readiness"]
    assert len(facts) == 1
    ff = facts[0]
    assert ff.readiness_state == "insufficient_data"
    assert ff.details["min_periods_required"] == 24
    assert ff.details["baseline_method"] == "seasonal_naive"
    assert ff.details["challenger_method"] == "holt_winters_additive_ets"


def test_hiring_demand_trends_separation(skill_engine):
    """Verify hiring demand trends explicitly partitions from developer adoption."""
    res = skill_engine.run_hiring_demand_trends("Python")
    assert res.capability_id == "hiring_demand_trends"
    assert "insufficient platform observations" in res.headline
    assert "GitHub Innovation Graph developer adoption is active and tracked separately" in res.headline

    facts = [f for f in res.facts if f.fact_type == "hiring_demand_readiness"]
    assert len(facts) == 1
    hf = facts[0]
    assert hf.details["signal_family"] == "hiring_demand"
    assert "partitioned from developer adoption" in hf.details["distinction"]


def test_reference_profile_related_skills(skill_engine):
    """Verify reference profile retrieves related technical skills from O*NET and ESCO."""
    res = skill_engine.run_reference_profile("Python")
    assert res.capability_id == "skill_reference_profile"
    assert res.target_skill == "Python"

    ref_facts = [f for f in res.facts if f.fact_type == "reference_taxonomy_profile"]
    assert len(ref_facts) == 1
    details = ref_facts[0].details
    assert "related_skills" in details
    related = details["related_skills"]
    assert len(related) > 0
    # Common technical skills co-occurring with Python in software occupations
    assert any(s in related for s in ["Linux", "C++", "Structured query language SQL", "Java (computer programming)", "computer programming"])


def test_orchestrator_skill_health_e2e(orchestrator):
    """Verify orchestrator end-to-end execution of a Skill Health query."""
    req = CoreIntelligenceAnswerRequest(
        message="how healthy is Python?",
        portal_type="individual",
        domain="skill",
    )
    resp = orchestrator.execute_request(req)
    assert resp.status == "insufficient_data"
    assert resp.execution_status == "insufficient_data"
    assert resp.domain == "skill"
    assert resp.intent == "skill_health_analysis"
    assert resp.resolved_entity == "Python"
    assert "insufficient verified observation data" in resp.answer
    assert len(resp.facts) >= 1
    assert any(f.fact_type == "skill_health_readiness" for f in resp.facts)
    assert len(resp.evidence) >= 1

"""Tests for Phase 4A: Skill Demand Trends Implementation & Truth-in-Data Verification.

Verifies:
1. Canonical skill identifier and display name.
2. Source and source family labeling (GitHub Innovation Graph, developer_adoption).
3. Metric name and unit (num_pushers, pushers, quarterly developer pushers).
4. Time grain and observation period (quarter, e.g. 2026-Q1).
5. Actual observation count and comparison period (e.g. 25 quarters).
6. Formula and calculated change (QoQ change, Theil-Sen slope per quarter).
7. Data freshness and mapping coverage.
8. Readiness status and limitations (adoption vs hiring demand separation).
9. Honest insufficient data handling when < 2 quarters exist.
10. Frontend contract compatibility with renderAdoption and IntelligenceEvidencePanel.
"""

from __future__ import annotations

import pytest
from app.intelligence_v2.contracts import V2StructuredFact
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.skill_intelligence import V2SkillIntelligenceEngine
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest


def test_phase4a_python_demand_trends_truth_in_data() -> None:
    engine = V2SkillIntelligenceEngine()
    result = engine.run_demand_trends("Python", geography="global")

    assert result.capability_id == "skill_demand_trends"
    assert result.target_skill == "Python"
    assert result.metadata["source_family"] == "developer_adoption"
    assert result.metadata["time_grain"] == "quarter"
    assert result.metadata["total_observations"] >= 20  # 25 quarters in SQLite

    # Verify primary adoption volume fact
    vol_facts = [f for f in result.facts if f.fact_type == "developer_adoption_latest"]
    assert len(vol_facts) == 1
    vf = vol_facts[0]
    assert vf.entity_name == "Python"
    assert vf.metric_name == "num_pushers"
    assert vf.unit == "pushers"
    assert vf.period == "2026-Q1"
    assert vf.source == "GitHub Innovation Graph"
    assert vf.data_origin == "real"

    # Verify canonical trend analysis fact
    trend_facts = [f for f in result.facts if f.fact_type == "trend_analysis"]
    assert len(trend_facts) == 1
    tf = trend_facts[0]
    assert tf.metric_name == "trend_direction"
    assert tf.metric_value in {"Growing", "Stable", "Declining"}
    assert tf.details["signal_type"] == "adoption"
    assert tf.details["provider"] == "GitHub Innovation Graph"
    assert tf.details["source_family"] == "developer_adoption"
    assert tf.details["time_grain"] == "quarter"
    assert tf.details["observation_count"] >= 20
    assert "start_period" in tf.details
    assert "end_period" in tf.details
    assert "comparison_period" in tf.details
    assert "theil_sen_slope_per_quarter" in tf.details
    assert "formula" in tf.details
    assert "limitations" in tf.details
    assert "not a measure of job postings or monthly employer hiring demand" in tf.details["limitations"]

    # Verify transparent hiring demand readiness fact
    hiring_facts = [f for f in result.facts if f.metric_name == "hiring_demand_readiness"]
    assert len(hiring_facts) == 1
    hf = hiring_facts[0]
    assert hf.metric_value == "insufficient_data"
    assert hf.readiness_state == "insufficient_data"
    assert hf.details["months_available"] == 0
    assert hf.details["months_required"] == 4

    # Verify headline distinguishes developer activity from hiring demand
    assert "developer adoption" in result.headline.lower()
    assert "not monthly employer hiring demand" in result.headline


def test_phase4a_geography_specific_trends_india() -> None:
    engine = V2SkillIntelligenceEngine()
    result = engine.run_demand_trends("Python", geography="IN")

    assert result.capability_id == "skill_demand_trends"
    trend_facts = [f for f in result.facts if f.fact_type == "trend_analysis"]
    assert len(trend_facts) == 1
    tf = trend_facts[0]
    assert tf.details["geography"] == "IN"
    assert tf.details["observation_count"] == 25
    assert tf.details["growth_pct"] is not None
    assert tf.details["theil_sen_slope_per_quarter"] is not None


def test_phase4a_insufficient_history_handling() -> None:
    engine = V2SkillIntelligenceEngine()
    # Query non-existent skill in GitHub adoption
    result = engine.run_demand_trends("TotallyFakeNonexistentSkillXYZ99")

    assert result.capability_id == "skill_demand_trends"
    assert "Limited observation history" in result.headline
    readiness_facts = [f for f in result.facts if f.metric_name == "adoption_trend_readiness"]
    assert len(readiness_facts) == 1
    assert readiness_facts[0].readiness_state == "insufficient_data"


def test_phase4a_orchestrator_end_to_end_response_contract() -> None:
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Python?",
        portal_type="individual",
        selected_skills=["Python"],
    )
    user = AuthenticatedUser(uid="test_user_phase4a", email="test4a@talentscope.ai")
    resp = orchestrator.execute_request(req, authenticated_user=user)

    assert resp.status in {"ready", "partial"}
    assert resp.execution_status == "completed"
    assert resp.domain == "skill"
    assert resp.intent == "skill_demand_trends"

    # Confirm facts include both developer adoption and trend direction
    fact_types = {f.fact_type for f in resp.facts}
    assert "developer_adoption_latest" in fact_types
    assert "trend_analysis" in fact_types
    assert "analysis_readiness" in fact_types

    # Confirm metric_results include trend direction for frontend evidence panel
    trend_metrics = [m for m in resp.metric_results if m.metric_name == "trend_direction"]
    assert len(trend_metrics) == 1
    assert trend_metrics[0].metric_value in {"Growing", "Stable", "Declining"}

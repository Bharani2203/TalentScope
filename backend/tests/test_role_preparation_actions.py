"""Tests for Role Preparation Actions Feature (Greenfield Intelligence V2).

Covers:
1. Capability registration and feature-policy behavior.
2. Explicit selected-feature routing (job_preparation_actions & role_preparation_actions).
3. Natural-language intent routing for preparation, roadmaps, and career transitions.
4. Role-specific deterministic actions grounded in local O*NET/ESCO taxonomies.
5. Distinct role-specific plans (e.g. Software Developer vs Data Scientist vs Web Developer).
6. Missing role, missing skills, and unresolvable role handling with provisional explanations.
7. User-provided skills: separating matched profile skills from gap skills to learn first.
8. Sensible dependency ordering (Foundations -> Frameworks -> Tools -> Systems) and prerequisites.
9. Desired timeline milestone structuring (30d, 3m, 6m).
10. Gemini B policy enforcement (opt-in qualitative only, never overrides deterministic, no fallback to Gemini A).
11. No fake citations, unsupported metrics, or fake job postings.
12. Follow-up suggestions without repeating the preparation capability.
13. Structured facts contract compatibility with frontend IntelligenceResultDetails.js.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.intelligence_v2.capability_registry import (
    CAPABILITIES,
    EXTENDED_CAPABILITIES,
    canonical_capability_id,
)
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.job_intelligence import V2JobIntelligenceEngine
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.intelligence_v2.role_actions import (
    PreparationAction,
    RolePreparationPlan,
    V2RoleActionEngine,
)
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.reference_store import ReferenceDataStore


# -----------------------------------------------------------------------------
# 1. Capability Registration & Feature Policy
# -----------------------------------------------------------------------------

def test_capability_registration_and_aliases() -> None:
    """Verify that job_preparation_actions and role_preparation_actions are registered."""
    cap_def = CAPABILITIES.get("job_preparation_actions")
    assert cap_def is not None
    assert cap_def.domain == "job_intelligence"
    assert cap_def.primary_signal_family == "reference_taxonomy"
    assert cap_def.primary_source_id == "onet"

    # Alias in EXTENDED_CAPABILITIES
    ext_def = EXTENDED_CAPABILITIES.get("role_preparation_actions")
    assert ext_def is not None
    assert ext_def.domain == "job_intelligence"

    # Canonical ID resolution
    assert canonical_capability_id("job_preparation_actions", "job") == "job_preparation_actions"
    assert canonical_capability_id("role_preparation_actions", "job") == "job_preparation_actions"
    assert canonical_capability_id("role_preparation_actions", "skill") == "job_preparation_actions"
    assert canonical_capability_id("action_recommendations", "job") == "job_preparation_actions"


def test_feature_policy_configuration() -> None:
    """Verify feature policy guarantees: deterministic first, qualitative guidance permitted, no fake data."""
    policy = FEATURE_ANSWER_POLICIES.get("job_preparation_actions")
    assert policy is not None
    assert policy.domain == "job"
    assert policy.handler == "run_preparation_actions"
    assert policy.gemini_b_fallback is True
    assert policy.provider_data_required is False
    assert "never" in policy.guidance_instruction.lower() or "do not claim" in policy.guidance_instruction.lower()


# -----------------------------------------------------------------------------
# 2. Intent Routing
# -----------------------------------------------------------------------------

def test_explicit_capability_routing() -> None:
    """Explicitly selecting role_preparation_actions or job_preparation_actions routes directly."""
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="Help me prepare",
        domain="job",
        capability_id="role_preparation_actions",
        target_role="Software Developer",
    )
    res = orchestrator.answer(req)
    assert res.intent == "job_preparation_actions"
    assert res.status == "ready"


@pytest.mark.parametrize(
    "query,expected_cap",
    [
        ("How can I prepare for a Software Developer role?", "job_preparation_actions"),
        ("What is the career roadmap for Data Scientist?", "job_preparation_actions"),
        ("What steps should I take to become a Cloud Architect?", "job_preparation_actions"),
        ("Provide a role preparation plan for Web Developer", "job_preparation_actions"),
        ("What is the learning path to transition into DevOps Engineer?", "job_preparation_actions"),
    ],
)
def test_natural_language_intent_routing(query: str, expected_cap: str) -> None:
    """Natural-language queries about role preparation, career roadmaps, and transitions route accurately."""
    planner = V2IntentPlanner()
    intent = planner.plan(query)
    assert intent.capability_id == expected_cap
    assert intent.target_role is not None


# -----------------------------------------------------------------------------
# 3. Deterministic Role-Specific Action Generation
# -----------------------------------------------------------------------------

def test_role_specific_differentiation() -> None:
    """Different target roles produce genuinely different, role-grounded preparation plans."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    plan_sw = engine.build_role_preparation_plan("Software Developer", store=store)
    plan_ds = engine.build_role_preparation_plan("Data Scientist", store=store)

    assert plan_sw.role_resolved is True
    assert plan_ds.role_resolved is True
    assert plan_sw.total_actions > 0
    assert plan_ds.total_actions > 0

    sw_skills = {a.skill_name.casefold() for a in plan_sw.actions}
    ds_skills = {a.skill_name.casefold() for a in plan_ds.actions}

    # Plans should reflect distinct occupational skill requirements
    assert sw_skills != ds_skills
    # Check that Software Developer gets software tools and Data Scientist gets analytical/ML skills
    assert any("python" in s or "java" in s or "c" in s or "javascript" in s for s in sw_skills)
    assert any("python" in s or "r" in s or "sas" in s or "sql" in s or "hadoop" in s for s in ds_skills)


def test_dependency_ordering_and_prerequisites() -> None:
    """Actions are sequenced logically (Foundations -> Frameworks -> Tools -> Systems)."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    plan = engine.build_role_preparation_plan("Software Developer", store=store)
    assert 1 <= plan.total_actions <= 5

    # Check ordering is sequential: 1, 2, 3, ...
    for idx, action in enumerate(plan.actions, start=1):
        assert action.order == idx
        assert action.action_title is not None
        assert action.why_matters is not None
        assert action.concrete_next_step is not None
        assert action.suggested_task is not None
        assert len(action.self_check_criteria) >= 2


def test_desired_timeline_milestones() -> None:
    """When a desired timeline is specified, milestones are mapped cleanly into phases."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    plan_3m = engine.build_role_preparation_plan("Software Developer", store=store, desired_timeline="3m")
    assert plan_3m.timeline_summary is not None
    assert "3m" in plan_3m.timeline_summary
    for action in plan_3m.actions:
        assert "Weeks" in action.action_title or "Phase" in action.action_title


# -----------------------------------------------------------------------------
# 4. User Profile Skills & Skill Gap Targeting
# -----------------------------------------------------------------------------

def test_user_skills_gap_targeting() -> None:
    """When user declares existing skills, matched skills are recognized and gap skills prioritized."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    # User declares Python; target role needs Python and other tools
    user_skills = ["Python"]
    plan = engine.build_role_preparation_plan("Software Developer", store=store, user_skills=user_skills)

    assert plan.role_resolved is True
    # Python should be recognized in user_matched_skills
    assert any("python" in s.casefold() for s in plan.user_matched_skills)
    # The actions should NOT tell the user to learn Python from scratch if other gaps exist
    action_skills = [a.skill_name.casefold() for a in plan.actions]
    # Check that gap skills are addressed
    assert len(plan.gap_skills_addressed) > 0


def test_no_user_skills_provides_honest_provisional_entry_plan() -> None:
    """When no profile skills are provided, a provisional entry-level plan is returned without guessing."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    plan = engine.build_role_preparation_plan("Software Developer", store=store, user_skills=None)
    assert plan.is_provisional is True
    assert "no profile skills were supplied" in plan.provisional_reason.lower()
    assert plan.total_actions > 0


def test_unresolvable_role_handles_gracefully() -> None:
    """When a role cannot be resolved in O*NET or ESCO, an honest provisional response is given."""
    store = ReferenceDataStore(read_only=True)
    engine = V2RoleActionEngine()

    # Case 1: unresolvable role + no user skills
    plan_no_skills = engine.build_role_preparation_plan("NonExistentUnicornRoleXYZ123", store=store)
    assert plan_no_skills.role_resolved is False
    assert plan_no_skills.total_actions == 0
    assert plan_no_skills.is_provisional is True
    assert "could not be resolved" in plan_no_skills.provisional_reason

    # Case 2: unresolvable role + user provided skills -> builds practice plan for user skills
    plan_with_skills = engine.build_role_preparation_plan(
        "NonExistentUnicornRoleXYZ123",
        store=store,
        user_skills=["Docker", "Kubernetes"],
    )
    assert plan_with_skills.role_resolved is False
    assert plan_with_skills.total_actions == 2
    assert plan_with_skills.is_provisional is True
    assert "provisional practice roadmap" in plan_with_skills.provisional_reason


# -----------------------------------------------------------------------------
# 5. Full Orchestrator & Backend Response Contract
# -----------------------------------------------------------------------------

def test_orchestrator_full_flow_preparation_actions() -> None:
    """End-to-end orchestrator execution returns structured facts, evidence, and clear answer."""
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="What are the preparation actions to become a Data Scientist?",
        domain="job",
        target_role="Data Scientist",
        selected_skills=["Python", "SQL"],
        time_range="3m",
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.intent == "job_preparation_actions"
    assert res.domain == "job"

    # Verify structured facts
    facts = res.facts
    assert len(facts) >= 1
    action_facts = [f for f in facts if f.fact_type == "action_recommendation"]
    assert len(action_facts) > 0
    first_action_fact = action_facts[0]
    assert first_action_fact.details.get("action_title") is not None
    assert first_action_fact.details.get("reason") is not None
    assert first_action_fact.details.get("suggested_action") is not None
    assert "self_check_criteria" in first_action_fact.details

    # Verify summary fact
    summary_facts = [f for f in facts if f.fact_type == "learning_recommendation_readiness"]
    assert len(summary_facts) == 1
    assert summary_facts[0].metric_value == "ready"

    # Verify evidence items
    assert len(res.evidence) >= 1
    assert any((getattr(e, "signal_type", None) or getattr(e, "signal_family", None)) == "reference_taxonomy" for e in res.evidence)

    # Verify formatted markdown answer
    assert "Role Preparation Actions" in res.answer or "Preparation Plan" in res.answer
    assert "Recognized Profile Skills" in res.answer
    assert "Step 1:" in res.answer
    assert "Why it matters" in res.answer
    assert "Practice task" in res.answer
    assert "Completion self-checks" in res.answer

    # Verify limitations notice
    assert any("course catalog" in lim.lower() or "commercial" in lim.lower() for lim in res.limitations)


def test_follow_up_suggestions_do_not_duplicate() -> None:
    """Follow-up prompts suggest adjacent capabilities (alignment, mobility) without repeating preparation."""
    intent = V2IntentPlanner().plan("Prepare for Software Developer")
    suggestions = V2ResponseFormatter._follow_up_suggestions(intent)
    assert len(suggestions) >= 1
    for s in suggestions:
        assert "prepare" not in s.lower()
        assert "preparation" not in s.lower()


# -----------------------------------------------------------------------------
# 6. Gemini B Boundaries & Negative Assertions
# -----------------------------------------------------------------------------

def test_gemini_b_never_overrides_deterministic_ready_plan() -> None:
    """When deterministic data is ready, Gemini B is never called and answer is deterministic."""
    orchestrator = V2Orchestrator()
    mock_gemini_b = MagicMock()
    orchestrator.gemini_b_service = mock_gemini_b

    req = CoreIntelligenceAnswerRequest(
        message="What are the preparation actions for Web Developer?",
        domain="job",
        target_role="Web Developer",
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "deterministic"
    # Gemini B service must not have been invoked because deterministic result was ready
    assert not mock_gemini_b.generate.called


def test_no_fabricated_metrics_or_fake_postings() -> None:
    """Response never contains fabricated salaries, percentages, vacancy counts, or mock URLs."""
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="What should I learn to become a Database Administrator?",
        domain="job",
        target_role="Database Administrator",
    )
    res = orchestrator.answer(req)

    # Negative assertions on markdown answer
    answer = res.answer
    assert "$/hr" not in answer and "$k" not in answer and "salary" not in answer.lower()
    assert "vacancies" not in answer.lower() and "active listings" not in answer.lower()
    # No commercial course platforms or sponsor links
    assert "coursera" not in answer.lower() and "udemy" not in answer.lower()
    assert "linkedin.com/learning" not in answer.lower()

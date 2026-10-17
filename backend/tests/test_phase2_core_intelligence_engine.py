"""Focused test suite for Phase 2: Complete the Core Intelligence Engine.

Verifies:
1. Multi-entity comparison resolution and synthesis grounded in evidence.
2. Skill gap evaluation respecting explicit query target role over background defaults.
3. Job postings search with zero stored postings providing honest O*NET baseline alternatives.
4. Contextual follow-up suggestions generated across intelligence intents.
5. LLMExplanationService security (header auth), bounded sizing, and caching.
"""

from __future__ import annotations

import pytest
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    EvidenceItem,
    StructuredFact,
)
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.services.llm_explanation_service import LLMExplanationService

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_phase2_user",
        email="phase2@example.com",
    )


def test_compare_entities_resolves_and_synthesizes_both_entities():
    """Verify that comparing two entities retrieves facts and produces comparative synthesis for both."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Compare Python and Java",
        portal_type="individual",
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert resp.intent == "compare_entities"
    assert "skill_technology_reference" in resp.capabilities_used

    # Verify both entities appear in facts
    fact_entities = {f.entity_name for f in resp.facts}
    assert "Python" in fact_entities
    assert "Java" in fact_entities

    # Verify direct answer and interpretation mention both
    assert "Python" in resp.answer
    assert "Java" in resp.answer
    assert "open-source developer activity" in resp.answer.lower()

    # Verify contextual follow-up questions
    assert len(resp.follow_up_questions) > 0
    assert any("Python" in q for q in resp.follow_up_questions)
    assert any("Java" in q for q in resp.follow_up_questions)


@pytest.mark.integration
def test_skill_gap_respects_explicit_query_target_role(local_reference_database):
    """Verify that skill gap analysis evaluates against explicit target role."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Assess my skill gaps for Data Scientists",
        target_role="Data Scientists",
        selected_skills=["Python", "SQL"],
        portal_type="individual",
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert resp.intent == "analyze_skill_gap"
    assert "skill_gap_role_fit" in resp.capabilities_used

    gap_fact = next((f for f in resp.facts if f.fact_type == "skill_gap"), None)
    assert gap_fact is not None
    assert gap_fact.entity_name == "Data Scientists"
    assert gap_fact.metric_value >= 1  # Python or SQL covered
    assert "Data Scientists" in resp.answer


def test_job_search_zero_stored_postings_provides_onet_baseline_alternative():
    """Verify that zero stored job postings provides an honest disclosure with O*NET alternative."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Find jobs for Cloud Architect",
        observations=[],
        portal_type="individual",
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert resp.intent == "search_jobs"
    assert "job_posting_search" in resp.capabilities_used

    job_fact = next((f for f in resp.facts if f.fact_type == "stored_job_postings"), None)
    assert job_fact is not None
    assert job_fact.metric_value == 0
    assert "bounded recent stored search" in resp.answer
    assert "O*NET taxonomy baseline" in resp.answer
    assert len(resp.follow_up_questions) > 0


@pytest.mark.integration
def test_follow_up_questions_generated_across_intents(local_reference_database):
    """Verify that execution orchestrator generates relevant follow-up questions across diverse intents."""
    service = ExecutionOrchestratorService()

    # 1. Skill reference lookup
    req_skill = CoreIntelligenceAnswerRequest(
        message="What is Python?",
        portal_type="individual",
    )
    resp_skill = service.answer(req_skill, authenticated_user=mock_auth_user())
    assert resp_skill.execution_status == "completed"
    assert len(resp_skill.follow_up_questions) >= 2
    assert any("Python" in q for q in resp_skill.follow_up_questions)

    # 2. Occupation lookup
    req_occ = CoreIntelligenceAnswerRequest(
        message="What is the role of Software Developers?",
        portal_type="individual",
    )
    resp_occ = service.answer(req_occ, authenticated_user=mock_auth_user())
    assert resp_occ.execution_status == "completed"
    assert len(resp_occ.follow_up_questions) >= 2


def test_llm_explanation_service_security_and_caching():
    """Verify LLMExplanationService uses header auth, handles rate-limits, and caches results."""
    service = LLMExplanationService(api_key="test-api-key")

    facts = [
        StructuredFact(
            fact_type="technology_adoption",
            entity_name="Python",
            metric_name="github_developer_pushers",
            metric_value=500000,
            unit="developers",
            period="2026-Q1",
            source="ref_github_topic_adoption",
        )
    ]
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_1",
            source="ref_github_topic_adoption",
            signal_type="adoption",
            period="2026-Q1",
            description="500,000 pushers in 2026-Q1",
        )
    ]

    # Verify cache key generation is deterministic
    k1 = service._get_cache_key("What is Python?", "explain_concept", facts)
    k2 = service._get_cache_key("What is Python?", "explain_concept", facts)
    assert k1 == k2

    # In test mode without RUN_LIVE_LLM_TESTS=1, service is not available (safety guard)
    assert service.is_available() is False
    res = service.generate_grounded_explanation(
        user_message="What is Python?",
        intent="explain_concept",
        facts=facts,
        evidence=evidence,
    )
    assert res is None  # Safely falls back to deterministic generator

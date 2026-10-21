"""Comprehensive Integration Verification for Greenfield Intelligence Engine V2.

Verifies:
1. The six required queries travel through the full request-to-response path.
2. Selected capability, engine execution, evidence provenance, and truth-in-data limits.
3. Local O*NET/ESCO reference data and GitHub adoption preservation (quarterly grain, no conflation).
4. Job-SDF quarantine (benchmark only, not mixed into hiring demand).
5. Authorization boundaries (individual, employee, company) and conversation access isolation.
"""

from __future__ import annotations

import pytest
from app.intelligence_v2.adapter import V2ExecutionOrchestratorAdapter
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.conversation_store import ConversationStore


@pytest.fixture
def orchestrator() -> V2Orchestrator:
    return V2Orchestrator()


@pytest.fixture
def auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(uid="user_int_1", email="int_user@example.com")


# =============================================================================
# STEP 2: The Six Required Queries
# =============================================================================

def test_query_1_demand_trend_python(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """1. 'What is the demand trend for Python?'"""
    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Python?",
        portal_type="individual",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "skill_demand_trends"
    assert resp.execution_status == "completed"
    assert resp.domain == "skill"
    assert resp.resolved_entity == "Python"
    assert len(resp.facts) >= 1
    # Check that facts report real GitHub pushers
    fact = resp.facts[0]
    assert fact.metric_name == "num_pushers"
    assert fact.unit == "pushers"
    assert fact.data_origin == "real"
    assert fact.source == "GitHub Innovation Graph"
    # Check evidence preserves quarterly developer adoption
    dev_evis = [e for e in resp.evidence if e.signal_type == "developer_adoption"]
    assert len(dev_evis) >= 1
    for e in dev_evis:
        assert e.period and "-Q" in e.period  # Native quarterly grain (YYYY-Q#)
        assert e.unit == "pushers"
        assert e.data_origin == "real"
    # Secondary hiring demand is reported truthfully as insufficient without fabricating postings
    demand_evis = [e for e in resp.evidence if e.signal_type == "hiring_demand"]
    assert len(demand_evis) >= 1
    assert demand_evis[0].data_origin == "unavailable"


def test_query_2_skills_relevant_to_python_developer_role(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """2. 'Which skills are relevant to a Python developer role?'"""
    req = CoreIntelligenceAnswerRequest(
        message="Which skills are relevant to a Python developer role?",
        portal_type="individual",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "job_role_requirements"
    assert resp.execution_status == "completed"
    assert resp.domain == "job"
    assert len(resp.facts) >= 1
    fact = resp.facts[0]
    assert fact.source == "O*NET 28.0"
    assert fact.data_origin in {"real", "local_reference_dataset"}
    assert fact.metric_value >= 1  # Software Developers has 20 competencies
    assert "Software Developers" in resp.answer
    assert any("O*NET" in e.source for e in resp.evidence)


def test_query_3_what_jobs_available_in_india(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """3. 'What jobs are available in India?'"""
    req = CoreIntelligenceAnswerRequest(
        message="What jobs are available in India?",
        portal_type="individual",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "job_verified_postings"
    assert resp.execution_status == "insufficient_data"
    assert resp.domain == "job"
    assert resp.applied_filters.get("geography") == "IN"
    # An unavailable posting store is not evidence of zero real postings.
    assert resp.facts == []
    assert "unavailable" in resp.answer.lower()
    assert "provider-returned posting records" in resp.answer
    assert any(e.data_origin == "unavailable" for e in resp.evidence)


def test_query_4_skills_mentioned_in_job_description(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """4. 'What skills are mentioned in this job description?'"""
    req = CoreIntelligenceAnswerRequest(
        message="What skills are mentioned in this job description?",
        portal_type="individual",
        target_role="Software Developers",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "job_role_requirements"
    assert resp.execution_status == "completed"
    assert resp.domain == "job"
    assert len(resp.facts) >= 1
    assert any("O*NET" in e.source for e in resp.evidence)


def test_query_5_what_should_i_learn_next_target_role(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """5. 'What should I learn next for my target role?'"""
    req = CoreIntelligenceAnswerRequest(
        message="What should I learn next for my target role?",
        portal_type="individual",
        target_role="Software Developers",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "job_preparation_actions"
    assert resp.execution_status == "completed"
    assert resp.domain == "job"
    # Action plan present with practice tasks and verification criteria
    assert "Deterministic Career Preparation Plan" in resp.answer
    assert "Practice Tasks" in resp.answer
    # No unverified commercial course URLs
    assert "http" not in resp.answer
    assert "does not curate commercial course catalogs" in resp.answer


def test_query_6_show_my_historical_skill_signals(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """6. 'Show my historical skill signals.'"""
    req = CoreIntelligenceAnswerRequest(
        message="Show my historical skill signals.",
        portal_type="individual",
        selected_skills=["Python"],
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    assert resp.executed_primary_capability == "skill_historical_signals"
    assert resp.execution_status == "completed"
    assert resp.domain == "skill"
    assert len(resp.facts) >= 1
    fact = resp.facts[0]
    assert fact.metric_name == "historical_span"
    assert "2020-Q1" in str(fact.metric_value)
    assert "GitHub Innovation Graph" in fact.source
    assert fact.data_origin == "real"
    assert fact.history_type == "backfill"


# =============================================================================
# STEP 3: Data Connection Integrity & Boundary Rules
# =============================================================================

def test_github_adoption_never_described_as_india_hiring_demand(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """Verify GitHub adoption pushers are strictly developer_adoption, never hiring_demand."""
    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Python?",
        portal_type="individual",
        location="India",
    )
    resp = orchestrator.execute_request(req, authenticated_user=auth_user)

    for item in resp.evidence:
        if item.source == "GitHub Innovation Graph":
            assert item.signal_type == "developer_adoption"
            assert item.unit == "pushers"
            assert item.signal_type != "hiring_demand"


def test_benchmark_data_quarantined_not_mixed_into_market(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """Verify Job-SDF benchmark is strictly isolated from market hiring analytics."""
    evidence = orchestrator.evidence_retriever.get_benchmark_evidence()
    assert len(evidence) == 1
    bench = evidence[0]
    assert bench.signal_family == "benchmark"
    assert bench.readiness_state == "reader_unavailable"
    assert bench.quality == "quarantined"


def test_ambiguous_isolated_query_surfaces_limitation_or_clarification(orchestrator: V2Orchestrator, auth_user: AuthenticatedUser) -> None:
    """Verify ambiguous isolated single-letter query 'go' triggers ambiguity guard."""
    mapping = orchestrator.skill_mapper.normalize("go")
    assert mapping.status == "partial"
    assert mapping.ambiguous is True
    assert mapping.context_required is True
    assert "Disambiguation required" in (mapping.notes or "")


def test_company_boundary_guard_enforced(orchestrator: V2Orchestrator) -> None:
    """Verify company portal queries fail closed without verified company membership."""
    req = CoreIntelligenceAnswerRequest(
        message="Show company workforce skills.",
        portal_type="company",
    )
    # User without company membership
    unauthed_user = AuthenticatedUser(uid="user_no_company", email="lone@example.com")
    resp = orchestrator.execute_request(req, authenticated_user=unauthed_user)

    assert resp.execution_status == "blocked"
    assert resp.plan_status == "blocked"
    assert resp.status == "error"
    assert "Active company membership is required" in resp.answer
    assert "UNAUTHORIZED_COMPANY_ACCESS" in resp.reason_codes


def test_conversation_access_isolation(orchestrator: V2Orchestrator) -> None:
    """Verify cross-user conversation access is blocked cleanly."""
    store = orchestrator.conversation_store
    conv = store.create_conversation(
        user_id="alice",
        portal_type="individual",
        domain="skill",
    )
    # Bob tries to access Alice's conversation
    req = CoreIntelligenceAnswerRequest(
        message="Follow up on previous query.",
        portal_type="individual",
        conversation_id=conv.conversation_id,
    )
    bob = AuthenticatedUser(uid="bob", email="bob@example.com")
    resp = orchestrator.execute_request(req, authenticated_user=bob)

    assert resp.execution_status == "blocked"
    assert resp.status == "error"
    assert "Access denied" in resp.answer
    assert "UNAUTHORIZED_CONVERSATION_ACCESS" in resp.reason_codes

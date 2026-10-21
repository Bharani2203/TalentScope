"""Test suite for G2.6 Task 10: Core Intelligence Runtime Completion.

Verifies:
1. Multi-turn conversation continuity and anaphoric pronoun resolution across 5 turns:
   - Turn 1: Entity introduced ("Show Python's historical trend.")
   - Turn 2: Pronoun reference ("Why is it declining?")
   - Turn 3: Contextual comparison ("Compare it with Java.")
   - Turn 4: Contextual evidence retrieval ("What evidence supports that?")
   - Turn 5: Contextual action recommendation ("What should I do next?")
2. Explicit context clearing (clear_context=True).
3. Multi-tenant and cross-user conversation isolation.
4. Real SQLite reference lookups (occupations, software skills, related occupations, GitHub series).
5. Honest handling of 0 market observations vs. provided observations.
6. Read-only stored provider collection checks without network calls.
7. LLM fallback to a deterministic, grounded conversational answer when unconfigured or offline.
8. End-to-end FastAPI endpoints (/plan, /answer, /entities/resolve, /capabilities).
"""

from __future__ import annotations

import uuid
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile, UserType
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
)
from app.models.intent_planner import (
    IntelligencePlanRequest,
    IntelligencePlanResponse,
)
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


# Test users
USER_ALICE = AuthenticatedUser(uid="user_alice_001")
USER_BOB = AuthenticatedUser(uid="user_bob_002")
USER_COMPANY_A = UserProfile(uid="user_comp_a", user_type=UserType.company, company_id="acme_corp")
USER_COMPANY_B = UserProfile(uid="user_comp_b", user_type=UserType.company, company_id="globex_corp")


def mock_auth_alice():
    return USER_ALICE


def mock_auth_bob():
    return USER_BOB


# =============================================================================
# 1. MULTI-TURN CONVERSATION CONTINUITY & PRONOUN RESOLUTION
# =============================================================================

def test_five_turn_conversation_continuity():
    """Verify exact 5-turn sequence maintains active entity context and resolves pronouns."""
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_5turn_{uuid.uuid4().hex[:8]}"

    # Turn 1: "Show Python's historical trend."
    req_turn1 = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        conversation_id=conv_id,
        portal_type="individual",
    )
    resp1 = orchestrator.answer(req_turn1, authenticated_user=USER_ALICE)
    assert resp1.conversation_id == conv_id
    # With 0 observations in local DB, this should return insufficient_data honestly
    assert resp1.execution_status == "insufficient_data"
    assert resp1.intent in {"analyze_trend", "retrieve_history"}

    # Verify state preserved in conversation store
    conv_store = ConversationStore.get_instance()
    state = conv_store.get_conversation(conv_id, user_id=USER_ALICE.uid)
    assert state is not None
    assert state.active_entity == "Python"
    assert len(state.turns) == 1

    # Turn 2: "Why is it declining?" -> pronoun "it" resolves to "Python"
    req_turn2 = CoreIntelligenceAnswerRequest(
        message="Why is it declining?",
        conversation_id=conv_id,
        portal_type="individual",
    )
    resp2 = orchestrator.answer(req_turn2, authenticated_user=USER_ALICE)
    assert resp2.conversation_id == conv_id
    assert resp2.intent == "analyze_trend"
    state2 = conv_store.get_conversation(conv_id, user_id=USER_ALICE.uid)
    assert state2.active_entity == "Python"
    assert len(state2.turns) == 2

    # Turn 3: "Compare it with Java." -> resolves to Python and Java comparison
    req_turn3 = CoreIntelligenceAnswerRequest(
        message="Compare it with Java.",
        conversation_id=conv_id,
        portal_type="individual",
    )
    resp3 = orchestrator.answer(req_turn3, authenticated_user=USER_ALICE)
    assert resp3.conversation_id == conv_id
    assert resp3.intent in {"compare_entities", "compare_skills", "analyze_trend"}

    # Turn 4: "What evidence supports that?" -> resolves evidence retrieval for active entity
    req_turn4 = CoreIntelligenceAnswerRequest(
        message="What evidence supports that?",
        conversation_id=conv_id,
        portal_type="individual",
    )
    resp4 = orchestrator.answer(req_turn4, authenticated_user=USER_ALICE)
    assert resp4.conversation_id == conv_id
    assert resp4.intent in {"retrieve_evidence", "retrieve_history", "explain_concept"}

    # Turn 5: "What should I do next?" -> resolves action recommendations
    req_turn5 = CoreIntelligenceAnswerRequest(
        message="What should I do next?",
        conversation_id=conv_id,
        portal_type="individual",
    )
    resp5 = orchestrator.answer(req_turn5, authenticated_user=USER_ALICE)
    assert resp5.conversation_id == conv_id
    assert resp5.intent == "synthesize_actions"
    assert resp5.execution_status == "insufficient_data"
    assert "target role" in resp5.answer.lower()
    assert not any(f.fact_type == "action_recommendation" for f in resp5.facts)


def test_bare_why_reuses_prior_conversation_intent_and_entity():
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_why_{uuid.uuid4().hex[:8]}"

    first = orchestrator.answer(
        CoreIntelligenceAnswerRequest(
            message="Is Python demand increasing or decreasing?",
            portal_type="individual",
            conversation_id=conv_id,
        ),
        authenticated_user=USER_ALICE,
    )
    assert first.intent == "analyze_trend"

    follow_up = orchestrator.answer(
        CoreIntelligenceAnswerRequest(
            message="Why?",
            portal_type="individual",
            conversation_id=conv_id,
        ),
        authenticated_user=USER_ALICE,
    )

    assert follow_up.intent == "analyze_trend"
    assert follow_up.execution_status == "insufficient_data"
    assert follow_up.conversation_id == conv_id


@pytest.mark.integration
def test_role_specific_learning_follow_up_reuses_conversation_role(local_reference_database):
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_role_{uuid.uuid4().hex[:8]}"

    orchestrator.answer(
        CoreIntelligenceAnswerRequest(
            message="What should I learn next?",
            portal_type="individual",
            target_role="Software Developer",
            selected_roles=["Software Developer"],
            conversation_id=conv_id,
        ),
        authenticated_user=USER_ALICE,
    )

    response = orchestrator.answer(
        CoreIntelligenceAnswerRequest(
            message="Which skills should I learn for this role?",
            portal_type="individual",
            conversation_id=conv_id,
        ),
        authenticated_user=USER_ALICE,
    )

    assert response.intent == "synthesize_actions"
    assert "action_recommendations" in response.capabilities_used
    assert response.execution_status == "completed"


# =============================================================================
# 2. CONTEXT CLEARING (clear_context=True)
# =============================================================================

def test_context_clearing():
    """Verify that clear_context=True removes prior session context."""
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_clear_{uuid.uuid4().hex[:8]}"

    # Step 1: Set entity
    req1 = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        conversation_id=conv_id,
    )
    orchestrator.answer(req1, authenticated_user=USER_ALICE)

    conv_store = ConversationStore.get_instance()
    assert conv_store.get_conversation(conv_id, user_id=USER_ALICE.uid) is not None

    # Step 2: Query with clear_context=True and an entity-less question
    req_clear = CoreIntelligenceAnswerRequest(
        message="Why is it declining?",
        conversation_id=conv_id,
        clear_context=True,
    )
    resp_clear = orchestrator.answer(req_clear, authenticated_user=USER_ALICE)

    # Because context was cleared, 'it' cannot be resolved to Python and requires clarification
    assert resp_clear.execution_status == "requires_clarification"
    assert resp_clear.reason_codes == ["REQUIRES_CLARIFICATION"]


# =============================================================================
# 3. MULTI-TENANT & CROSS-USER ISOLATION
# =============================================================================

def test_cross_user_isolation_denies_unauthorized_access():
    """Verify that Bob cannot access or hijack Alice's conversation."""
    orchestrator = ExecutionOrchestratorService()
    conv_id = f"conv_alice_{uuid.uuid4().hex[:8]}"

    # Alice initializes conversation
    req_alice = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        conversation_id=conv_id,
    )
    orchestrator.answer(req_alice, authenticated_user=USER_ALICE)

    # Bob attempts to query the same conversation_id
    req_bob = CoreIntelligenceAnswerRequest(
        message="Why is it declining?",
        conversation_id=conv_id,
    )
    resp_bob = orchestrator.answer(req_bob, authenticated_user=USER_BOB)

    # Must be blocked due to ownership mismatch
    assert resp_bob.execution_status == "blocked"
    assert "UNAUTHORIZED_CONVERSATION_ACCESS" in resp_bob.reason_codes
    assert "different user" in resp_bob.answer.lower()


def test_cross_company_isolation():
    """Verify that company organization data cannot cross tenant boundaries."""
    orchestrator = ExecutionOrchestratorService()

    # User from Acme Corp attempts to query workforce data for Globex Corp
    req_cross = CoreIntelligenceAnswerRequest(
        message="Analyze company workforce distribution.",
        portal_type="company",
        company_id="globex_corp",  # Target is Globex
    )
    # User belongs to Acme Corp
    resp = orchestrator.answer(req_cross, authenticated_user=USER_COMPANY_A)
    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in resp.reason_codes


# =============================================================================
# 4. REAL SQLITE REFERENCE LOOKUPS
# =============================================================================

@pytest.mark.integration
def test_real_sqlite_occupation_lookup(local_reference_database):
    """Verify lookup of real O*NET occupation from SQLite."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Tell me about the role of Database Administrators",
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "completed"
    assert resp.intent == "lookup_occupation"
    assert any(f.metric_name == "soc_code" for f in resp.facts)
    occ_facts = [f for f in resp.facts if f.metric_name == "soc_code"]
    assert len(occ_facts) > 0
    assert occ_facts[0].metric_value == "15-1242.00"


@pytest.mark.integration
def test_real_sqlite_software_skills_crosswalk(local_reference_database):
    """Verify real O*NET software skills retrieval from SQLite."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What software tools does a Software Developer use?",
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "completed"
    assert resp.intent == "crosswalk_occupation_software"
    assert len(resp.facts) > 0
    assert any(f.fact_type == "software_skill" for f in resp.facts)
    assert any("Software Developers" in f.details.get("occupation_title", "") for f in resp.facts if f.details)


@pytest.mark.integration
def test_real_sqlite_related_occupations(local_reference_database):
    """Verify real O*NET related occupations crosswalk from SQLite."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What are related occupations for Software Developers?",
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "completed"
    assert resp.intent == "crosswalk_related_occupations"
    rel_facts = [f for f in resp.facts if f.fact_type == "related_occupation"]
    assert len(rel_facts) > 0


@pytest.mark.integration
def test_generic_skill_concept_does_not_attach_unrequested_github_adoption(local_reference_database):
    """A generic concept query must not implicitly become a GitHub adoption claim."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="What is Python?",
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "completed"
    assert resp.intent == "explain_concept"
    assert not any(f.source and f.source.startswith("ref_github_") for f in resp.facts)
    assert not any(item.signal_type == "adoption" for item in resp.evidence)


# =============================================================================
# 5. MARKET OBSERVATIONS AVAILABILITY VS 0 OBSERVATIONS
# =============================================================================

def test_zero_market_observations_returns_honest_insufficient_data():
    """Verify that empty observation table in SQLite returns insufficient_data without fabricating."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "insufficient_data"
    assert resp.status == "insufficient_data"
    assert "NO_OBSERVATIONS_FOR_SERIES" in resp.reason_codes
    assert "no measured trend observations are currently available" in resp.answer.lower()
    assert len(resp.facts) == 0


def test_snapshot_observations_without_origin_do_not_compute_a_measured_trend():
    """History type alone cannot promote observations with missing origin to measured evidence."""
    orchestrator = ExecutionOrchestratorService()
    observations = [
        MarketObservation(
            id=f"obs-{i}",
            skill="Python",
            skill_id="skill:python",
            signal_type="demand",
            value=float(100 + i * 20),
            unit="job_postings",
            period=f"2026-0{i}",
            source="jsearch",
            observed_at=f"2026-0{i}-01T00:00:00Z",
            history_type="snapshot",
            series_id="series_py_us",
        )
        for i in range(1, 5)
    ]

    req = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        time_range="max_available",
        observations=observations,
        portal_type="individual",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    # Readiness rejected missing provenance before the trend capability handler ran.
    assert resp.execution_status == "insufficient_data"
    assert resp.status == "insufficient_data"
    assert resp.intent == "analyze_trend"
    assert resp.capabilities_used == []
    assert not any(f.fact_type == "trend_analysis" for f in resp.facts)
    assert resp.reason_codes == ["OBSERVATION_PROVENANCE_UNAVAILABLE"]


def test_historical_observations_respect_default_and_explicit_max_range():
    orchestrator = ExecutionOrchestratorService()
    observation = MarketObservation(
        id="historical-python-observation",
        skill="Python",
        signal_type="demand",
        value=120,
        period="2026-01",
        source="jsearch",
        observed_at="2026-01-15T00:00:00Z",
        history_type="snapshot",
        series_id="series_py_us",
    )
    observations = [observation]

    default_request = CoreIntelligenceAnswerRequest(
        message="Show Python's historical trend.",
        observations=observations,
    )
    historical_request = default_request.model_copy(update={"time_range": "max"})

    assert default_request.time_range == "30d"
    assert orchestrator._get_market_observations(
        request_obs=observations,
        skill="Python",
        time_range=default_request.time_range,
    ) == []
    assert orchestrator._get_market_observations(
        request_obs=observations,
        skill="Python",
        time_range=historical_request.time_range,
    ) == observations


# =============================================================================
# 6. ROADMAP CAPABILITY SAFEGUARDS
# =============================================================================

def test_forecasting_and_simulation_strictly_disabled():
    """Verify future demand forecasting and workforce simulation return unsupported status."""
    orchestrator = ExecutionOrchestratorService()

    req_fc = CoreIntelligenceAnswerRequest(
        message="Forecast future demand for Python over next 3 years.",
    )
    resp_fc = orchestrator.answer(req_fc, authenticated_user=USER_ALICE)
    assert resp_fc.execution_status in {"unsupported", "insufficient_data"}
    assert len(resp_fc.facts) == 0

    req_sim = CoreIntelligenceAnswerRequest(
        message="Simulate workforce what-if transition to AI engineering.",
    )
    resp_sim = orchestrator.answer(req_sim, authenticated_user=USER_ALICE)
    assert resp_sim.execution_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp_sim.reason_codes
    assert "SIMULATION_PREREQUISITES_NOT_MET" in resp_sim.reason_codes
    assert resp_sim.facts == []
    assert resp_sim.evidence == []


# =============================================================================
# 7. LLM EXPLANATION FALLBACK & GROUNDING INTEGRITY
# =============================================================================

@pytest.mark.integration
def test_deterministic_fallback_opens_with_answer_and_uses_relevant_details(local_reference_database):
    """Verify deterministic fallback leads with an answer, not a fixed section template."""
    orchestrator = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Tell me about the role of Database Administrators",
    )
    resp = orchestrator.answer(req, authenticated_user=USER_ALICE)
    assert resp.execution_status == "completed"
    assert resp.answer.startswith("O*NET occupational classification")
    assert "Database Administrators" in resp.answer
    assert "15-1242.00" in resp.answer
    assert "### 1. Direct Answer" not in resp.answer


# =============================================================================
# 8. FASTAPI ENDPOINTS INTEGRATION
# =============================================================================

@pytest.mark.integration
def test_fastapi_endpoints_plan_and_answer(local_reference_database):
    """Verify FastAPI routes /plan, /answer, /entities/resolve with conversation continuity."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_alice
    client = TestClient(app)

    conv_id = f"conv_api_{uuid.uuid4().hex[:8]}"

    # 1. /plan endpoint
    plan_resp = client.post(
        "/api/v1/intelligence/plan",
        json={
            "message": "What software tools do Software Developers use?",
            "conversation_id": conv_id,
            "portal_type": "individual",
        },
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["plan_status"] == "ready_to_execute"
    assert plan_data["intent"] == "crosswalk_occupation_software"

    # 2. /answer endpoint
    ans_resp = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What software tools do Software Developers use?",
            "conversation_id": conv_id,
            "portal_type": "individual",
        },
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["execution_status"] == "completed"
    assert ans_data["conversation_id"] == conv_id

    # 3. Follow-up via /answer
    follow_resp = client.post(
        "/api/v1/intelligence/answer",
        json={
            "message": "What should I do next?",
            "conversation_id": conv_id,
            "portal_type": "individual",
        },
    )
    assert follow_resp.status_code == 200
    follow_data = follow_resp.json()
    assert follow_data["intent"] == "synthesize_actions"
    assert follow_data["execution_status"] == "insufficient_data"
    assert "target role" in follow_data["answer"].lower()
    assert not any(fact["fact_type"] == "action_recommendation" for fact in follow_data["facts"])

    # 4. /entities/resolve endpoint
    res_resp = client.post(
        "/api/v1/intelligence/entities/resolve",
        json={"name": "golang"},
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["status"] == "resolved"
    assert res_data["entity"]["canonical_name"] == "Go"

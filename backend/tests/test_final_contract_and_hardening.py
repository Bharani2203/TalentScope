"""G2.6 Task 9: Final Contract & Regression Hardening Test Suite.

Comprehensive offline test suite validating:
1. End-to-end FastAPI API contracts (auth, validation, status codes, payload structures).
2. Regression coverage for all 5 Task 8 fixes (positive and negative cases).
3. Adversarial answer-quality and validation rejection tests (12 distinct cases).
4. Portal and multi-tenant security isolation.
5. Analytical database integrity and zero mutation assurance.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser, UserProfile
from app.models.entity_registry import EntityResolutionRequest, EntityResolutionResponse
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    StructuredFact,
    EvidenceItem,
)
from app.models.intent_planner import IntelligencePlanRequest, IntelligencePlanResponse
from app.models.reference_data import OnetOccupation
from app.models.skill_intelligence import MarketObservation
from app.services.entity_registry_service import EntityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


# =============================================================================
# AUTH FIXTURES
# =============================================================================

def mock_auth_user(uid: str = "test_user_final_1", email: str = "user@example.com") -> AuthenticatedUser:
    return AuthenticatedUser(uid=uid, email=email)


def mock_company_user(company_id: str = "comp_alpha", uid: str = "test_corp_1") -> UserProfile:
    return UserProfile(
        uid=uid,
        email="corp@alpha.com",
        company_id=company_id,
        user_type="company",
    )


# =============================================================================
# 1. API CONTRACTS END-TO-END (FASTAPI APP)
# =============================================================================

def test_api_contract_auth_rejection():
    """Verify missing authentication returns 401 on all three core endpoints."""
    # Ensure no dependency overrides are active for this test
    app.dependency_overrides.clear()
    client = TestClient(app)

    # 1. Resolve endpoint
    r1 = client.post("/api/v1/intelligence/entities/resolve", json={"name": "Python"})
    assert r1.status_code == 401
    assert "detail" in r1.json()

    # 2. Plan endpoint
    r2 = client.post("/api/v1/intelligence/plan", json={"message": "What is Python?"})
    assert r2.status_code == 401

    # 3. Answer endpoint
    r3 = client.post("/api/v1/intelligence/answer", json={"message": "What is Python?"})
    assert r3.status_code == 401


@pytest.mark.integration
def test_api_contract_valid_auth_and_response_schema(local_reference_database):
    """Verify valid authenticated requests return compliant schemas."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # 1. Resolve endpoint
    res_resp = client.post("/api/v1/intelligence/entities/resolve", json={"name": "Software Developer"})
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["status"] == "resolved"
    assert res_data["entity"]["canonical_name"] == "Software Developers"
    assert res_data["entity"]["entity_type"] == "occupation"
    assert "source_provenance" in res_data

    # 2. Plan endpoint
    plan_resp = client.post(
        "/api/v1/intelligence/plan",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    assert plan_data["intent"] == "crosswalk_occupation_software"
    assert "occupation_software_skills" in plan_data["selected_capabilities"]
    assert plan_data["plan_status"] in {"ready_to_execute", "clarification_recommended"}
    assert isinstance(plan_data["limitations"], list)

    # 3. Answer endpoint
    ans_resp = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "What software tools does a Software Developer use?"},
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["intent"] == "crosswalk_occupation_software"
    assert ans_data["execution_status"] == "completed"
    assert len(ans_data["facts"]) > 0
    assert len(ans_data["evidence"]) > 0
    assert "Software Developers" in ans_data["answer"]
    assert ans_data["answer"].startswith("Identified")


def test_api_contract_invalid_payload_error_handling():
    """Verify invalid payloads produce controlled 422 errors without tracebacks or secret exposure."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # Forbidden extra fields
    r1 = client.post(
        "/api/v1/intelligence/entities/resolve",
        json={"name": "Python", "extra_unsupported_field": "injected_value"},
    )
    assert r1.status_code == 422
    err_body = r1.text
    assert "Traceback" not in err_body
    assert "firebase" not in err_body.lower()
    assert "secret" not in err_body.lower()

    # Invalid type
    r2 = client.post(
        "/api/v1/intelligence/answer",
        json={"message": 12345, "selected_skills": "not_a_list"},
    )
    assert r2.status_code == 422


def test_api_contract_unsupported_and_ambiguous_status_codes():
    """Verify unsupported intents return blocked status and ambiguous requests return requires_clarification."""
    app.dependency_overrides[dependencies.get_current_user] = mock_auth_user
    client = TestClient(app)

    # Unsupported workforce simulation
    r_fore = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Simulate workforce reallocation across teams"},
    )
    assert r_fore.status_code == 200
    data_fore = r_fore.json()
    assert data_fore["execution_status"] == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in data_fore["reason_codes"]
    assert len(data_fore["facts"]) == 0
    assert len(data_fore["evidence"]) == 0

    # Ambiguous entity query
    r_amb = client.post(
        "/api/v1/intelligence/answer",
        json={"message": "Tell me about go"},
    )
    assert r_amb.status_code == 200
    data_amb = r_amb.json()
    assert data_amb["execution_status"] == "requires_clarification"
    assert "REQUIRES_CLARIFICATION" in data_amb["reason_codes"]
    assert len(data_amb["follow_up_questions"]) > 0


# =============================================================================
# 2. VALIDATION OF THE FIVE TASK 8 FIXES (POSITIVE & NEGATIVE)
# =============================================================================

@pytest.mark.integration
def test_fix_1_onet_lookup_signatures_and_types(local_reference_database):
    """Verify ReferenceDataStore.get_onet_occupations handles code, title, and query args with OnetOccupation models."""
    store = ReferenceDataStore(local_reference_database)

    # Positive by code
    occs_code = store.get_onet_occupations(code="15-1252.00")
    assert len(occs_code) == 1
    occ = occs_code[0]
    assert isinstance(occ, OnetOccupation)
    assert occ.soc_code == "15-1252.00"
    assert occ["soc_code"] == "15-1252.00"
    assert occ.title == "Software Developers"
    assert occ["title"] == "Software Developers"

    # Positive by title
    occs_title = store.get_onet_occupations(title="Software Developers")
    assert len(occs_title) >= 1
    assert any(o.soc_code == "15-1252.00" for o in occs_title)

    # Positive by query
    occs_query = store.get_onet_occupations(query="Software")
    assert len(occs_query) >= 1

    # Negative non-existent code
    occs_none_code = store.get_onet_occupations(code="99-9999.99")
    assert len(occs_none_code) == 0

    # Negative non-existent title
    occs_none_title = store.get_onet_occupations(title="NonExistentAstronautArchitectXYZ")
    assert len(occs_none_title) == 0


def test_fix_2_market_store_get_observations_signature():
    """Verify MarketDataStore.get_observations accepts optional cutoff, skill, and location without crashing."""
    m_store = MarketDataStore()

    # Positive: empty parameters
    obs_empty = m_store.get_observations()
    assert isinstance(obs_empty, list)

    # Positive: skill only
    obs_skill = m_store.get_observations(skill="Python")
    assert isinstance(obs_skill, list)

    # Positive: cutoff only
    obs_cutoff = m_store.get_observations(cutoff=datetime.now(timezone.utc))
    assert isinstance(obs_cutoff, list)

    # Positive: location and cutoff
    obs_loc = m_store.get_observations(location="US", cutoff=datetime.now(timezone.utc))
    assert isinstance(obs_loc, list)

    # Positive: all three parameters
    obs_all = m_store.get_observations(skill="Python", location="US", cutoff=datetime.now(timezone.utc))
    assert isinstance(obs_all, list)

    # Negative: nonexistent skill returns empty list
    obs_none = m_store.get_observations(skill="NonExistentSkillTermXYZ123")
    assert len(obs_none) == 0


@pytest.mark.parametrize(
    "query,expected_intent,is_positive",
    [
        ("Recommended learning actions for career growth", "synthesize_actions", True),
        ("What should I learn next?", "synthesize_actions", True),
        ("Action plan for upskilling in Python", "synthesize_actions", True),
        ("Career roadmap next steps", "synthesize_actions", True),
        ("What is Python?", "synthesize_actions", False),
        ("Compare Python and Java", "synthesize_actions", False),
        ("Search jobs for Python", "synthesize_actions", False),
        ("Is Python growing?", "synthesize_actions", False),
    ],
)
def test_fix_3_action_intent_patterns(query: str, expected_intent: str, is_positive: bool):
    """Verify action intent patterns match learning questions without misclassifying unrelated questions."""
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message=query)
    plan = planner.create_plan(req, authenticated_user=mock_auth_user())

    if is_positive:
        assert plan.intent == expected_intent
        assert "action_recommendations" in plan.selected_capabilities
    else:
        assert plan.intent != expected_intent


@pytest.mark.parametrize(
    "query,expected_occupation,is_positive",
    [
        pytest.param(
            "What software tools does a Software Developer use?",
            "Software Developers",
            True,
            marks=pytest.mark.integration,
        ),
        pytest.param(
            "Software Developer tools",
            "Software Developers",
            True,
            marks=pytest.mark.integration,
        ),
        pytest.param(
            "Tech stack for Data Scientists",
            "Data Scientists",
            True,
            marks=pytest.mark.integration,
        ),
        ("What is Python?", None, False),
    ],
)
def test_fix_4_occupation_entity_resolution(
    query: str, expected_occupation: str | None, is_positive: bool, request,
):
    """Verify occupation entities resolve in tools/tech questions, and non-occupation queries do not resolve them."""
    if is_positive:
        request.getfixturevalue("local_reference_database")
    planner = IntentPlannerService()
    req = IntelligencePlanRequest(message=query)
    plan = planner.create_plan(req, authenticated_user=mock_auth_user())

    occ_entities = [
        e.canonical_entity.canonical_name
        for e in plan.entities
        if e.canonical_entity and e.canonical_entity.entity_type == "occupation"
    ]
    if is_positive:
        assert expected_occupation in occ_entities
    else:
        assert len(occ_entities) == 0


@pytest.mark.integration
def test_fix_5_occupation_readiness_with_background_skills(local_reference_database):
    """Verify occupation readiness checks evaluate the occupation entity even when background skills are present."""
    service = ExecutionOrchestratorService()

    # Positive: Query mentions occupation + background skills provided
    req_pos = CoreIntelligenceAnswerRequest(
        message="Related occupations for Software Developers",
        selected_skills=["Python", "SQL", "Docker"],
    )
    plan_pos = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message="Related occupations for Software Developers",
            selected_skills=["Python", "SQL", "Docker"],
        ),
        authenticated_user=mock_auth_user(),
    )
    assert plan_pos.context_summary.get("primary_entity") == "Software Developers"

    resp_pos = service.answer(req_pos, authenticated_user=mock_auth_user())
    assert resp_pos.execution_status == "completed"
    assert "related_occupations" in resp_pos.capabilities_used
    assert len(resp_pos.facts) > 0

    # Negative: Query mentions NO occupation, only background skills
    req_neg = CoreIntelligenceAnswerRequest(
        message="Related occupations",
        selected_skills=["Python", "SQL"],
    )
    plan_neg = service.intent_planner.create_plan(
        IntelligencePlanRequest(
            message="Related occupations",
            selected_skills=["Python", "SQL"],
        ),
        authenticated_user=mock_auth_user(),
    )
    # Planner correctly marks clarification required because occupation is missing
    assert plan_neg.plan_status == "requires_clarification"
    assert any("occupation" in q.lower() for q in plan_neg.clarification_questions)


# =============================================================================
# 3. ADVERSARIAL ANSWER-QUALITY & VALIDATION TESTS
# =============================================================================

@pytest.mark.integration
def test_adversarial_case_1_taxonomy_described_as_hiring_demand(local_reference_database):
    """Validator rejects describing O*NET taxonomy as employer hiring demand."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What software tools does a Software Developer use?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_occupation_software_skills(
        CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?"),
        plan,
    )
    # Synthesize compliant answer then inject bad claim
    valid_text = service._synthesize_answer(plan.intent, facts, evidence, ["occupation_software_skills"], CoreIntelligenceAnswerRequest(message="test"))
    corrupted_text = valid_text + "\nThis represents live employer hiring demand across the nation."

    status, reasons = service._validate_response(
        corrupted_text, facts, evidence, ["occupation_software_skills"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_TAXONOMY_CONFLATED_WITH_HIRING_DEMAND" in reasons


@pytest.mark.integration
def test_adversarial_case_2_github_described_as_job_vacancies(local_reference_database):
    """Validator rejects describing GitHub developer adoption as job vacancies."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What is Python?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_skill_technology_reference(
        CoreIntelligenceAnswerRequest(message="What is Python?"),
        plan,
    )
    valid_text = service._synthesize_answer(plan.intent, facts, evidence, ["skill_technology_reference"], CoreIntelligenceAnswerRequest(message="test"))
    corrupted_text = valid_text + "\nGitHub statistics demonstrate verified job vacancies for engineers."

    status, reasons = service._validate_response(
        corrupted_text, facts, evidence, ["skill_technology_reference"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_GITHUB_CONFLATED_WITH_HIRING_DEMAND" in reasons


def test_adversarial_case_3_single_observation_described_as_trend():
    """Validator rejects claiming a trend from only a single point-in-time observation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="Market snapshot for Python"),
        authenticated_user=mock_auth_user(),
    )
    fact = StructuredFact(
        fact_id="fact_snap_single",
        fact_type="market_snapshot",
        entity_name="Python",
        metric_name="observed_demand",
        metric_value=150.0,
        period="2026-05",
        source="test_source",
        data_origin="real",
        evidence_reference="ev_snap_single",
    )
    ev = EvidenceItem(
        evidence_id="ev_snap_single",
        source="test_source",
        signal_type="snapshot",
        period="2026-05",
        data_origin="real",
        quality="valid",
        description="Single snapshot",
    )
    text = (
        "### 1. Direct Answer\nThe upward trend indicates growing adoption.\n\n"
        "### 2. Supporting Facts\n- Observed: 150.0\n\n"
        "### 3. Evidence\n- `ev_snap_single`\n\n"
        "### 4. Interpretation\nGrowing.\n\n"
        "### 5. Limitations\nSnapshot."
    )
    status, reasons = service._validate_response(text, [fact], [ev], ["market_snapshot"], plan)
    assert status == "failed"
    assert "VALIDATION_ERROR_SINGLE_OBSERVATION_TREND" in reasons


def test_adversarial_case_4_missing_value_represented_as_zero():
    """Validator rejects representing a null or missing observation as numeric zero."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="Test query"),
        authenticated_user=mock_auth_user(),
    )
    fact = StructuredFact(
        fact_id="fact_null_zero",
        fact_type="market_snapshot",
        entity_name="Python",
        metric_name="demand_metric",
        metric_value=0.0,
        details={"was_null": True},
        source="test",
        data_origin="real",
        evidence_reference="ev_1",
    )
    ev = EvidenceItem(evidence_id="ev_1", source="test", signal_type="test", quality="valid", description="Observation test")
    text = "### 1. Direct Answer\nDemand is 0.\n\n### 2. Facts\n- 0\n\n### 3. Evidence\n- `ev_1`\n\n### 4. Notes\nNone\n\n### 5. Scope\nNone"
    status, reasons = service._validate_response(text, [fact], [ev], ["market_snapshot"], plan)
    assert status == "failed"
    assert "VALIDATION_ERROR_MISSING_VALUE_ZEROED" in reasons


def test_adversarial_case_5_unsupported_future_forecast_blocked():
    """Execution orchestrator strictly blocks future forecasts without executing handlers."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Predict the future outlook for Python in 2030")

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status in {"unsupported", "insufficient_data"}
    assert len(resp.facts) == 0
    assert len(resp.evidence) == 0


def test_adversarial_case_6_ungrounded_numerical_claims():
    """Validator rejects numeric quantities in text that have no grounding fact."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What software tools does a Software Developer use?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_occupation_software_skills(
        CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?"),
        plan,
    )
    valid_text = service._synthesize_answer(plan.intent, facts, evidence, ["occupation_software_skills"], CoreIntelligenceAnswerRequest(message="test"))
    corrupted_text = valid_text + "\nFurthermore, exactly 84729 employers require these skills."

    status, reasons = service._validate_response(
        corrupted_text, facts, evidence, ["occupation_software_skills"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_UNGROUNDED_QUANTITATIVE_CLAIM" in reasons


@pytest.mark.integration
def test_adversarial_case_7_claim_altering_unit(local_reference_database):
    """Validator rejects altering unit from developers to postings."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What is Python?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_skill_technology_reference(
        CoreIntelligenceAnswerRequest(message="What is Python?"),
        plan,
    )
    dev_fact = next((f for f in facts if f.unit == "developers"), None)
    assert dev_fact is not None

    valid_text = service._synthesize_answer(plan.intent, facts, evidence, ["skill_technology_reference"], CoreIntelligenceAnswerRequest(message="test"))
    corrupted_text = valid_text + f"\nObserved {dev_fact.metric_value} postings in the market."

    status, reasons = service._validate_response(
        corrupted_text, facts, evidence, ["skill_technology_reference"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_UNIT_MISMATCH" in reasons


def test_adversarial_case_8_nonexistent_evidence_citation():
    """Validator rejects citing evidence IDs that do not exist in the evidence set."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What software tools does a Software Developer use?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_occupation_software_skills(
        CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?"),
        plan,
    )
    valid_text = service._synthesize_answer(plan.intent, facts, evidence, ["occupation_software_skills"], CoreIntelligenceAnswerRequest(message="test"))
    corrupted_text = valid_text + "\nCited provenance: `ev_completely_fake_id_999`."

    status, reasons = service._validate_response(
        corrupted_text, facts, evidence, ["occupation_software_skills"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_MISSING_EVIDENCE_CITATION" in reasons


def test_adversarial_case_9_occupation_evidence_mismatch():
    """Validator rejects occupation answers where evidence pertains to an incompatible occupation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="What software tools does a Software Developer use?"),
        authenticated_user=mock_auth_user(),
    )
    facts, evidence, _ = service._handle_occupation_software_skills(
        CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?"),
        plan,
    )
    # Corrupt evidence to reference a dentist occupation
    corrupted_evidence = copy.deepcopy(evidence)
    for e in corrupted_evidence:
        e.description = "O*NET SOC 29-1021.00 Dentists workplace tools taxonomy."

    text = service._synthesize_answer(plan.intent, facts, corrupted_evidence, ["occupation_software_skills"], CoreIntelligenceAnswerRequest(message="test"))
    status, reasons = service._validate_response(
        text, facts, corrupted_evidence, ["occupation_software_skills"], plan
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_OCCUPATION_EVIDENCE_MISMATCH" in reasons


def test_adversarial_case_10_ambiguous_skill_requires_clarification():
    """Ambiguous query returns requires_clarification with candidate options."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Tell me about go")

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "requires_clarification"
    assert "REQUIRES_CLARIFICATION" in resp.reason_codes
    assert len(resp.follow_up_questions) > 0


def test_adversarial_case_11_unknown_entity_not_found_handling():
    """Unknown entities return requires_clarification or controlled ungrounded response."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Analyze trends for GlipGlopNonExistentTechnology12345")

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status in {"requires_clarification", "insufficient_data"}
    assert len(resp.facts) == 0


def test_adversarial_case_12_job_query_rejects_global_vacancy_totals():
    """Validator rejects claiming stored postings represent total global vacancies."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        IntelligencePlanRequest(message="Search jobs for React"),
        authenticated_user=mock_auth_user(),
    )
    fact = StructuredFact(
        fact_id="fact_stored_jobs_1",
        fact_type="stored_job_postings",
        entity_name="React",
        metric_name="stored_postings_count",
        metric_value=5,
        source="jsearch",
        data_origin="real",
        evidence_reference="ev_jobs_1",
    )
    ev = EvidenceItem(
        evidence_id="ev_jobs_1",
        source="jsearch",
        signal_type="stored_posting",
        data_origin="real",
        quality="valid",
        description="Stored jobs",
    )
    text = (
        "### 1. Direct Answer\nFound 5 total global vacancies for React.\n\n"
        "### 2. Supporting Facts\n- 5 postings\n\n"
        "### 3. Evidence\n- `ev_jobs_1`\n\n"
        "### 4. Notes\nVerified.\n\n"
        "### 5. Limitations\nNone."
    )
    status, reasons = service._validate_response(text, [fact], [ev], ["job_posting_search"], plan)
    assert status == "failed"
    assert "VALIDATION_ERROR_JOB_TOTAL_CLAIM" in reasons


# =============================================================================
# 4. PORTAL AND TENANT SECURITY TESTS
# =============================================================================

def test_security_individual_cannot_access_company_workforce():
    """Individual user cannot access internal company workforce data."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(
        message="Show our company workforce skill inventory",
        portal_type="individual",
        company_id="comp_123",
    )
    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_PORTAL_ACCESS" in resp.reason_codes


def test_security_cross_company_access_blocked():
    """Company user from comp_alpha cannot access company data for comp_beta."""
    service = ExecutionOrchestratorService()
    user_alpha = mock_company_user(company_id="comp_alpha")
    req = CoreIntelligenceAnswerRequest(
        message="Show our company workforce inventory",
        portal_type="company",
        company_id="comp_beta",
    )
    resp = service.answer(req, authenticated_user=user_alpha)
    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in resp.reason_codes


def test_security_cross_request_stateless_isolation():
    """Two consecutive requests share zero facts, evidence, or mutable state."""
    service = ExecutionOrchestratorService()

    req1 = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp1 = service.answer(req1, authenticated_user=mock_auth_user(uid="user_1"))

    req2 = CoreIntelligenceAnswerRequest(message="What is Python?")
    resp2 = service.answer(req2, authenticated_user=mock_auth_user(uid="user_2"))

    assert resp1.request_id != resp2.request_id
    assert resp1.intent != resp2.intent
    ev_ids1 = {e.evidence_id for e in resp1.evidence}
    ev_ids2 = {e.evidence_id for e in resp2.evidence}
    # No shared evidence IDs between unrelated occupation tools vs python reference
    assert ev_ids1.isdisjoint(ev_ids2)


@pytest.mark.integration
def test_security_entity_resolution_does_not_expose_company_data(local_reference_database):
    """Entity resolution resolves public taxonomies without leaking company records."""
    service = EntityRegistryService()
    req = EntityResolutionRequest(name="Software Developer")
    resp = service.resolve(req)

    assert resp.status == "resolved"
    assert resp.entity is not None
    assert "comp_" not in str(resp.entity.metadata)
    assert resp.entity.source in {"ref_onet_occupations", "canonical_registry", "reference_taxonomy"}


# =============================================================================
# 5. DATA INTEGRITY AND BASELINE VERIFICATION
# =============================================================================

@pytest.mark.integration
def test_database_reference_baseline_unmutated(local_reference_database):
    """Verify all 6 analytical reference tables retain their exact Task 8 row counts."""
    ref_store = ReferenceDataStore(local_reference_database)
    counts = ref_store.get_table_counts()

    assert counts["ref_onet_occupations"] == 1016
    assert counts["ref_onet_software_skills"] == 31821
    assert counts["ref_onet_essential_skills"] == 18200
    assert counts["ref_onet_related_occupations"] == 18460
    assert counts["ref_github_language_adoption"] == 180338
    assert counts["ref_github_topic_adoption"] == 82591

    total_ref = sum(
        counts[t]
        for t in [
            "ref_onet_occupations",
            "ref_onet_software_skills",
            "ref_onet_essential_skills",
            "ref_onet_related_occupations",
            "ref_github_language_adoption",
            "ref_github_topic_adoption",
        ]
    )
    assert total_ref == 332426


@pytest.mark.integration
def test_database_empirical_tables_remain_empty(local_reference_database):
    """Verify empirical market tables contain zero records in the local analytical database."""
    m_store = MarketDataStore(local_reference_database)
    obs = m_store.get_observations()
    assert len(obs) == 0

    with m_store._connect() as conn:
        cache_cnt = conn.execute("SELECT count(*) FROM market_calculation_cache").fetchone()[0]
        runs_cnt = conn.execute("SELECT count(*) FROM market_collection_runs").fetchone()[0]
        assert cache_cnt == 0
        assert runs_cnt == 0

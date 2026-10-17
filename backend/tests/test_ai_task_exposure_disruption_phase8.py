"""Phase 8: End-to-End AI Task Exposure and Disruption Intelligence Integration Tests.

Validates the complete vertical slice:
User Question -> Intent/Entity Planning -> AI Task Exposure Capability Evaluation ->
Evidence Retrieval -> Grounded Deterministic Disruption Synthesis -> Response Validation.

Covers:
1. The 4 canonical user questions:
   - "Which tasks in software development are exposed to AI?" -> analyze_ai_task_exposure
   - "What evidence supports this task-exposure assessment?" -> retrieve_evidence (multi-turn)
   - "Which skills are associated with the affected tasks?" -> analyze_ai_task_exposure
   - "Compare task exposure across Software Developers and Database Administrators." -> compare_entities
2. Strict metric separation:
   - Task exposure (theoretical overlap) != Job displacement (actual headcount/employment change)
   - Automation potential (discrete steps) != Workforce impact (advisory upskilling/redesign)
   - Human oversight required for complex judgment (augmentation > automation)
   - Grounded answers NEVER fabricate numerical percentages of jobs lost
3. Data quality and provenance safeguards:
   - Missing dataset -> blocked with NO_LICENSED_EXPOSURE_DATASET
   - Unverified license -> blocked with DATASET_LICENSE_UNVERIFIED
   - Unmapped occupation -> insufficient_data with NO_MATCHING_TASK_RECORDS
   - Rejection of synthetic, demo, undated, or unevidenced records
4. Multi-turn conversation and tenant isolation:
   - Conversation context preservation for follow-ups
   - Strict tenant access isolation
5. Workforce simulation guard:
   - simulate_workforce_scenarios remains strictly unsupported (CAPABILITY_UNSUPPORTED_IN_G2_6)
"""

from __future__ import annotations

import uuid
from datetime import date
import pytest

from app.analytics.ai_disruption import (
    AIExposureDatasetProvenance,
    TaskExposureRecord,
    evaluate_ai_task_disruption,
)
from app.scripts import load_ai_exposure_dataset
from app.scripts.load_ai_exposure_dataset import verify_and_parse_ai_exposure_dataset
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import CapabilityEvaluationRequest
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    EvidenceItem,
    StructuredFact,
)
from app.models.intent_planner import IntelligencePlanRequest
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.conversation_store import ConversationStore

USER_PHASE8 = AuthenticatedUser(
    uid="user-phase8-ai-researcher",
    email="phase8@talentscope.ai",
    user_type="individual",
)

USER_OTHER = AuthenticatedUser(
    uid="user-other-tenant",
    email="other@talentscope.ai",
    user_type="individual",
)

pytestmark = pytest.mark.usefixtures("local_conversation_firestore")


def make_valid_provenance() -> AIExposureDatasetProvenance:
    return AIExposureDatasetProvenance(
        dataset_id="open_ai_task_exposure_2026",
        dataset_name="Open Occupational Task AI Exposure Reference",
        provider="open_research_institute",
        license_name="CC-BY-4.0",
        license_verified=True,
        permitted_commercial_or_academic_use=True,
        required_fields_present=True,
        version="2026.1",
        source_url="https://example.org/datasets/task-exposure-2026",
    )


def make_valid_task_records() -> list[TaskExposureRecord]:
    return [
        TaskExposureRecord(
            task_id="onet-15-1252.00-t1",
            task_statement="Write, update, and maintain computer programs and software packages.",
            occupation_code="15-1252.00",
            occupation_title="Software Developers",
            canonical_skill_ids=["python", "git"],
            task_exposure_level="high",
            observed_ai_usage_mode="augmentation",
            human_oversight_required=True,
            evidence_source="Empirical AI Tool Usage Reference 2026",
            evidence_source_id="ev-ai-exp-101",
            evidence_date=date(2026, 3, 15),
            evidence_rationale="Generative models assist code generation, but architectural correctness and debugging require software engineer oversight.",
            evidence_strength="high",
        ),
        TaskExposureRecord(
            task_id="onet-15-1252.00-t2",
            task_statement="Review code written by other team members for security vulnerabilities and style adherence.",
            occupation_code="15-1252.00",
            occupation_title="Software Developers",
            canonical_skill_ids=["python"],
            task_exposure_level="moderate",
            observed_ai_usage_mode="augmentation",
            human_oversight_required=True,
            evidence_source="Empirical AI Tool Usage Reference 2026",
            evidence_source_id="ev-ai-exp-102",
            evidence_date=date(2026, 3, 15),
            evidence_rationale="Static analysis AI assists pattern scanning; complex security and design decisions require human validation.",
            evidence_strength="high",
        ),
        TaskExposureRecord(
            task_id="onet-15-1252.00-t3",
            task_statement="Format boilerplate documentation and function docstrings.",
            occupation_code="15-1252.00",
            occupation_title="Software Developers",
            canonical_skill_ids=["python"],
            task_exposure_level="high",
            observed_ai_usage_mode="automation",
            human_oversight_required=False,
            evidence_source="Empirical AI Tool Usage Reference 2026",
            evidence_source_id="ev-ai-exp-103",
            evidence_date=date(2026, 3, 15),
            evidence_rationale="Routine docstring generation can be automated by language models under standard syntax templates.",
            evidence_strength="high",
        ),
        TaskExposureRecord(
            task_id="onet-15-1252.00-t4",
            task_statement="Consult with clients about software design and maintenance.",
            occupation_code="15-1252.00",
            occupation_title="Software Developers",
            canonical_skill_ids=[],
            task_exposure_level="low",
            observed_ai_usage_mode="unobserved",
            human_oversight_required=True,
            evidence_source="Empirical AI Tool Usage Reference 2026",
            evidence_source_id="ev-ai-exp-104",
            evidence_date=date(2026, 3, 15),
            evidence_rationale="Interpersonal communication and stakeholder requirement negotiation have low direct model overlap.",
            evidence_strength="high",
        ),
        TaskExposureRecord(
            task_id="onet-15-1242.00-t1",
            task_statement="Test database systems and coordinate changes for database security.",
            occupation_code="15-1242.00",
            occupation_title="Database Administrators",
            canonical_skill_ids=["sql"],
            task_exposure_level="moderate",
            observed_ai_usage_mode="augmentation",
            human_oversight_required=True,
            evidence_source="Empirical AI Tool Usage Reference 2026",
            evidence_source_id="ev-ai-exp-201",
            evidence_date=date(2026, 3, 15),
            evidence_rationale="AI tools assist query optimization and index suggestion, but disaster recovery and ACID constraints require DBA supervision.",
            evidence_strength="high",
        ),
    ]


# =============================================================================
# 1. READINESS & PROVENANCE SAFEGUARD TESTS
# =============================================================================

def test_ai_task_exposure_readiness_no_dataset():
    """Verify readiness rejects evaluation when no verified dataset is provided."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="ai_task_exposure",
        entity_name="Software Developers",
        task_exposure_records=[],
        dataset_provenance=None,
    )
    resp = service.evaluate(req)
    res = resp.results[0]
    assert res.runtime_status == "blocked"
    assert res.can_execute is False
    assert "NO_LICENSED_EXPOSURE_DATASET" in res.reason_codes


def test_ai_task_exposure_readiness_unverified_license():
    """Verify readiness blocks evaluation when dataset license is unverified."""
    service = CapabilityRegistryService()
    unverified_prov = AIExposureDatasetProvenance(
        dataset_id="proprietary_unverified",
        dataset_name="Proprietary Exposure Ratings",
        provider="unverified_vendor",
        license_name="Commercial-Unverified",
        license_verified=False,
        permitted_commercial_or_academic_use=False,
        required_fields_present=True,
        blocker_reason="Vendor license not verified for open benchmark redistribution.",
    )
    req = CapabilityEvaluationRequest(
        capability_id="ai_task_exposure",
        entity_name="Software Developers",
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=unverified_prov,
    )
    resp = service.evaluate(req)
    res = resp.results[0]
    assert res.runtime_status == "blocked"
    assert res.can_execute is False
    assert "NO_LICENSED_EXPOSURE_DATASET" in res.reason_codes


def test_ai_task_exposure_readiness_unmapped_occupation():
    """Unmapped records cannot bypass the global dataset readiness gate."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="ai_task_exposure",
        entity_name="Agricultural Equipment Operators",
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = service.evaluate(req)
    res = resp.results[0]
    assert res.runtime_status == "blocked"
    assert res.can_execute is False
    assert "NO_LICENSED_EXPOSURE_DATASET" in res.reason_codes


def test_ai_task_exposure_rejects_request_supplied_provenance():
    """Caller-supplied records and license claims cannot activate a blocked capability."""
    service = CapabilityRegistryService()
    req = CapabilityEvaluationRequest(
        capability_id="ai_task_exposure",
        entity_name="Software Developers",
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = service.evaluate(req)
    res = resp.results[0]
    assert res.global_status == "blocked"
    assert res.runtime_status == "blocked"
    assert res.can_execute is False
    assert "NO_LICENSED_EXPOSURE_DATASET" in res.reason_codes


def test_analytics_preserves_source_categories_and_task_provenance():
    """The analytical helper reports source categories and citations without job-loss claims."""
    records = make_valid_task_records()
    result = evaluate_ai_task_disruption(
        entity_name="Software Developers",
        entity_type="occupation",
        canonical_id="occupation:soc:15-1252.00",
        licensed_exposure_records=records,
        dataset_provenance=make_valid_provenance(),
    )

    assert result.status == "ready"
    assert result.dataset_provenance.dataset_id == "open_ai_task_exposure_2026"
    assert result.dataset_provenance.version == "2026.1"
    assert [task.task_exposure_level for task in result.tasks_evaluated] == [
        "high", "moderate", "high", "low",
    ]
    assert result.potential_exposure_counts == {
        "high": 2, "moderate": 1, "low": 1, "unknown": 0,
    }
    assert all(task.evidence_source_id for task in result.tasks_evaluated)
    assert all(task.evidence_date == date(2026, 3, 15) for task in result.tasks_evaluated)
    assert "job disappearance" in " ".join(result.warnings).lower()
    assert "not imply occupation disappearance" in result.workforce_outcome_summary.lower()
    assert "%" not in result.task_exposure_summary


def test_unmapped_occupation_has_no_task_records():
    """A verified analytical fixture does not claim coverage for an unsupported occupation."""
    result = evaluate_ai_task_disruption(
        entity_name="Agricultural Equipment Operators",
        entity_type="occupation",
        licensed_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    assert result.status == "insufficient_data"
    assert result.tasks_evaluated == []
    assert "No task records" in result.reason


def test_candidate_dataset_metadata_is_not_independent_verification():
    """Self-asserted open-license metadata cannot produce trusted runtime records."""
    payload = {
        "metadata": {
            "dataset_id": "self_asserted_dataset",
            "dataset_name": "Self-asserted fixture",
            "provider": "test-only",
            "license": "CC-BY-4.0",
            "permitted_use_verified": True,
            "version": "1",
            "source_url": "https://example.invalid/data",
            "evidence_date": "2026-03-15",
        },
        "records": [{
            "task_id": "task-1",
            "task_statement": "Test fixture task",
            "occupation_code": "15-1252.00",
            "occupation_title": "Software Developers",
            "canonical_occupation_id": "occupation:soc:15-1252.00",
            "task_exposure_level": "high",
            "evidence_rationale": "Test fixture only.",
            "evidence_source_id": "fixture-evidence-1",
            "canonical_skill_ids": ["python"],
        }],
    }
    provenance, records = verify_and_parse_ai_exposure_dataset(payload)

    assert provenance.license_verified is False
    assert provenance.permitted_commercial_or_academic_use is False
    assert provenance.blocker_reason
    assert records == []


def test_approved_registry_fixture_preserves_task_source_attribution(monkeypatch):
    """A mocked independently approved registry entry parses and preserves a cited record."""
    monkeypatch.setitem(
        load_ai_exposure_dataset.APPROVED_DATASET_REGISTRY,
        "approved_fixture",
        {
            "license": "CC-BY-4.0",
            "version": "test-1",
            "source_url": "https://example.invalid/approved-fixture",
            "methodology_id": "fixture-ordinal-method",
            "permitted_use": "verified",
        },
    )
    provenance, records = verify_and_parse_ai_exposure_dataset({
        "metadata": {
            "dataset_id": "approved_fixture",
            "dataset_name": "Approved test fixture",
            "provider": "test-only",
            "license": "CC-BY-4.0",
            "version": "test-1",
            "source_url": "https://example.invalid/approved-fixture",
            "methodology_id": "fixture-ordinal-method",
            "evidence_date": "2026-03-15",
        },
        "records": [{
            "task_id": "fixture-task-1",
            "task_statement": "Test-only task statement",
            "occupation_code": "15-1252.00",
            "occupation_title": "Software Developers",
            "canonical_occupation_id": "occupation:soc:15-1252.00",
            "task_exposure_level": "moderate",
            "evidence_rationale": "Test-only rationale.",
            "evidence_source_id": "fixture-source-record-1",
            "canonical_skill_ids": ["python"],
        }],
    })

    assert provenance.license_verified
    assert provenance.permitted_commercial_or_academic_use
    assert len(records) == 1
    assert records[0].task_exposure_level == "moderate"
    assert records[0].canonical_occupation_id == "occupation:soc:15-1252.00"
    assert records[0].evidence_source_id == "fixture-source-record-1"


def test_loader_rejects_unrecognized_exposure_categories():
    payload = {
        "metadata": {
            "dataset_id": "self_asserted_dataset",
            "license": "CC-BY-4.0",
            "permitted_use_verified": True,
            "evidence_date": "2026-03-15",
        },
        "records": [{
            "task_id": "task-1",
            "task_statement": "Test fixture task",
            "occupation_code": "15-1252.00",
            "occupation_title": "Software Developers",
            "canonical_occupation_id": "occupation:soc:15-1252.00",
            "task_exposure_level": "very_high",
            "evidence_rationale": "Test fixture only.",
            "evidence_source_id": "fixture-evidence-1",
        }],
    }
    provenance, records = verify_and_parse_ai_exposure_dataset(payload)
    assert provenance.required_fields_present is False
    assert provenance.blocker_reason
    assert records == []


def test_loader_rejects_unmapped_canonical_skills():
    payload = {
        "metadata": {
            "dataset_id": "self_asserted_dataset",
            "license": "CC-BY-4.0",
            "permitted_use_verified": True,
            "evidence_date": "2026-03-15",
        },
        "records": [{
            "task_id": "task-1",
            "task_statement": "Test fixture task",
            "occupation_code": "15-1252.00",
            "occupation_title": "Software Developers",
            "canonical_occupation_id": "occupation:soc:15-1252.00",
            "task_exposure_level": "high",
            "evidence_rationale": "Test fixture only.",
            "evidence_source_id": "fixture-evidence-1",
            "canonical_skill_ids": ["unregistered-skill"],
        }],
    }
    provenance, records = verify_and_parse_ai_exposure_dataset(payload)
    assert provenance.required_fields_present is False
    assert records == []


def test_response_validator_requires_task_evidence_references():
    planner = IntentPlannerService()
    plan = planner.create_plan(
        IntelligencePlanRequest(message="Which tasks are exposed to AI in software development?"),
        authenticated_user=USER_PHASE8,
    )
    orchestrator = ExecutionOrchestratorService()
    fact = StructuredFact(
        fact_type="task_exposure_record",
        entity_name="Software Developers",
        metric_name="task_exposure_level",
        metric_value="high",
        source="test fixture",
        evidence_reference="ev-task-fixture",
    )
    evidence = EvidenceItem(
        evidence_id="ev-task-fixture",
        source="test fixture",
        signal_type="task_exposure_record",
        description="Test-only source citation.",
    )
    status, reasons = orchestrator._validate_response(
        answer_text="The source category is high; this does not establish job displacement.",
        facts=[fact],
        evidence=[evidence],
        capabilities_used=["ai_task_exposure"],
        plan=plan,
    )
    assert status == "completed"
    assert reasons == []

    fact.evidence_reference = "missing-evidence"
    status, reasons = orchestrator._validate_response(
        answer_text="The source category is high.",
        facts=[fact],
        evidence=[evidence],
        capabilities_used=["ai_task_exposure"],
        plan=plan,
    )
    assert status == "failed"
    assert "VALIDATION_ERROR_UNGROUNDED_EVIDENCE_REFERENCE" in reasons


# =============================================================================
# 2. INTENT PLANNING TESTS
# =============================================================================

def test_intent_planning_tasks_in_software_development():
    """Verify query 'Which tasks in software development are exposed to AI?' plans analyze_ai_task_exposure."""
    planner = IntentPlannerService()
    prov = make_valid_provenance()
    records = make_valid_task_records()
    plan_req = IntelligencePlanRequest(
        message="Which tasks in software development are exposed to AI?",
        task_exposure_records=records,
        dataset_provenance=prov,
    )
    resp = planner.create_plan(plan_req, authenticated_user=USER_PHASE8)
    assert resp.intent == "analyze_ai_task_exposure"
    assert "ai_task_exposure" in resp.selected_capabilities
    assert resp.plan_status == "blocked"
    assert resp.context_summary.get("primary_entity") == "Software Developers"


def test_intent_planning_associated_skills_query():
    """Verify 'Which skills are associated with the affected tasks?' classifies to analyze_ai_task_exposure."""
    planner = IntentPlannerService()
    prov = make_valid_provenance()
    records = make_valid_task_records()
    plan_req = IntelligencePlanRequest(
        message="Which skills are associated with the affected tasks?",
        target_role="Software Developers",
        task_exposure_records=records,
        dataset_provenance=prov,
    )
    resp = planner.create_plan(plan_req, authenticated_user=USER_PHASE8)
    assert resp.intent == "analyze_ai_task_exposure"
    assert "ai_task_exposure" in resp.selected_capabilities


def test_intent_planning_comparative_task_exposure():
    """Verify comparison query selects compare_entities with ai_task_exposure."""
    planner = IntentPlannerService()
    prov = make_valid_provenance()
    records = make_valid_task_records()
    plan_req = IntelligencePlanRequest(
        message="Compare task exposure across Software Developers and Database Administrators.",
        task_exposure_records=records,
        dataset_provenance=prov,
    )
    resp = planner.create_plan(plan_req, authenticated_user=USER_PHASE8)
    assert resp.intent == "compare_entities"
    assert "ai_task_exposure" in resp.selected_capabilities
    assert resp.selected_capabilities == ["ai_task_exposure"]
    assert len(resp.entities) == 2
    assert all(entity.resolution_status == "resolved" for entity in resp.entities)
    assert all(entity.canonical_entity for entity in resp.entities)


# =============================================================================
# 3. END-TO-END VERTICAL SLICE & CANONICAL QUESTIONS
# =============================================================================

def test_canonical_question_1_tasks_in_software_development_exposed_to_ai():
    """User Question: 'Which tasks in software development are exposed to AI?'"""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Which tasks in software development are exposed to AI?",
        conversation_id=cid,
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.intent == "analyze_ai_task_exposure"
    assert resp.status == "unavailable"
    assert resp.plan_status == "blocked"
    assert resp.execution_status == "blocked"
    assert "ai_task_exposure" not in resp.capabilities_used
    assert resp.facts == []
    assert resp.evidence == []
    assert "approved dataset" in resp.answer.lower()
    assert "job loss" not in resp.answer.lower()


def test_canonical_question_2_multi_turn_evidence_follow_up():
    """User Question: 'What evidence supports this task-exposure assessment?' as turn 2."""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"
    records = make_valid_task_records()
    prov = make_valid_provenance()

    # Turn 1: Primary query
    ans_req_1 = CoreIntelligenceAnswerRequest(
        message="Which tasks in software development are exposed to AI?",
        conversation_id=cid,
        task_exposure_records=records,
        dataset_provenance=prov,
    )
    resp1 = orchestrator.answer(ans_req_1, authenticated_user=USER_PHASE8)
    assert resp1.intent == "analyze_ai_task_exposure"
    assert resp1.status == "unavailable"

    # Turn 2: Follow-up asking for evidence
    ans_req_2 = CoreIntelligenceAnswerRequest(
        message="What evidence supports this task-exposure assessment?",
        conversation_id=cid,
        task_exposure_records=records,
        dataset_provenance=prov,
    )
    resp2 = orchestrator.answer(ans_req_2, authenticated_user=USER_PHASE8)
    assert resp2.intent == "retrieve_evidence"
    assert resp2.status == "unavailable"
    assert resp2.execution_status == "blocked"
    assert resp2.evidence == []
    assert "no validated task-exposure assessment" in resp2.answer.lower()


def test_canonical_question_3_skills_associated_with_affected_tasks():
    """User Question: 'Which skills are associated with the affected tasks?'"""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Which skills are associated with the affected tasks?",
        target_role="Software Developers",
        conversation_id=cid,
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.intent == "analyze_ai_task_exposure"
    assert resp.status == "unavailable"
    assert resp.facts == []
    assert resp.evidence == []


def test_canonical_question_4_comparative_task_exposure_across_occupations():
    """User Question: 'Compare task exposure across Software Developers and Database Administrators.'"""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Compare task exposure across Software Developers and Database Administrators.",
        conversation_id=cid,
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.intent == "compare_entities"
    assert resp.status == "unavailable"
    assert resp.execution_status == "blocked"
    assert resp.evidence == []
    assert "compare_entities" == resp.intent


# =============================================================================
# 4. DATA GOVERNANCE & GATING TESTS
# =============================================================================

def test_missing_dataset_blocks_execution():
    """Verify asking about AI task exposure with no dataset returns blocked/unavailable."""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Which tasks in software development are exposed to AI?",
        conversation_id=cid,
        task_exposure_records=[],
        dataset_provenance=None,
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.status == "unavailable"
    assert resp.plan_status == "blocked"
    assert "NO_LICENSED_EXPOSURE_DATASET" in resp.reason_codes
    assert resp.facts == []
    assert resp.evidence == []


def test_unverified_license_blocks_execution():
    """Verify asking about AI task exposure with unverified license returns blocked/unavailable."""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"
    unverified_prov = AIExposureDatasetProvenance(
        dataset_id="proprietary_test",
        dataset_name="Proprietary AI Exposure Scores",
        provider="third_party",
        license_name="Unverified",
        license_verified=False,
        permitted_commercial_or_academic_use=False,
        required_fields_present=True,
        blocker_reason="Dataset license is not verified for production benchmarking.",
    )

    ans_req = CoreIntelligenceAnswerRequest(
        message="Which tasks in software development are exposed to AI?",
        conversation_id=cid,
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=unverified_prov,
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.status == "unavailable"
    assert resp.plan_status == "blocked"
    assert "NO_LICENSED_EXPOSURE_DATASET" in resp.reason_codes


def test_unmapped_occupation_cannot_be_inferred_from_request_records():
    """A supplied occupation record cannot establish runtime coverage."""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Which tasks in Agricultural Equipment Operators are exposed to AI?",
        conversation_id=cid,
        task_exposure_records=make_valid_task_records(),
        dataset_provenance=make_valid_provenance(),
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.status == "unavailable"
    assert resp.plan_status == "blocked"
    assert "NO_LICENSED_EXPOSURE_DATASET" in resp.reason_codes


# =============================================================================
# 5. ENTERPRISE & ARCHITECTURE SAFEGUARDS
# =============================================================================

def test_workforce_simulation_remains_strictly_disabled():
    """Verify workforce what-if simulation requests remain disabled (CAPABILITY_UNSUPPORTED_IN_G2_6)."""
    orchestrator = ExecutionOrchestratorService()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    ans_req = CoreIntelligenceAnswerRequest(
        message="Simulate our workforce attrition shock under AI displacement scenarios.",
        conversation_id=cid,
    )
    resp = orchestrator.answer(ans_req, authenticated_user=USER_PHASE8)

    assert resp.plan_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp.reason_codes
    assert resp.status == "unavailable"


def test_tenant_conversation_isolation():
    """Verify one tenant cannot access another tenant's conversation context."""
    conv_store = ConversationStore.get_instance()
    cid = f"conv-{uuid.uuid4().hex[:8]}"

    # Tenant 1 records a turn
    conv_store.save_turn(
        conversation_id=cid,
        user_message="Which tasks in software development are exposed to AI?",
        intent="analyze_ai_task_exposure",
        primary_entity="Software Developers",
        resolved_entities=["Software Developers"],
        answer_summary="Task exposure analysis for Software Developers.",
        user_id=USER_PHASE8.uid,
        portal_type="individual",
    )

    # Tenant 2 attempts to resolve follow-up in Tenant 1's conversation
    res_primary, comps, role, rew = conv_store.resolve_follow_up(
        message="What evidence supports this?",
        conversation_id=cid,
        user_id=USER_OTHER.uid,
    )

    assert res_primary is None
    assert comps == []
    assert role is None
    assert rew is None

    # Check conversation access is denied for Tenant 2
    allowed, reason = conv_store.check_conversation_access(cid, user_id=USER_OTHER.uid)
    assert allowed is False
    assert "belongs to a different user" in (reason or "")


def test_company_task_exposure_conversation_isolation():
    conv_store = ConversationStore.get_instance()
    cid = f"conv-{uuid.uuid4().hex[:8]}"
    conv_store.save_turn(
        conversation_id=cid,
        user_message="Which tasks in software development are exposed to AI?",
        intent="analyze_ai_task_exposure",
        primary_entity="Software Developers",
        user_id="company-user-a",
        company_id="company-a",
        portal_type="company",
        execution_status="blocked",
        response_payload={"status": "unavailable"},
    )

    allowed, reason = conv_store.check_conversation_access(
        cid,
        user_id="company-user-a",
        company_id="company-b",
    )
    assert allowed is False
    assert "different company" in (reason or "").lower()

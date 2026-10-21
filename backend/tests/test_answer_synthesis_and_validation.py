"""Offline test suite for G2.6 Task 7: Evidence-Grounded Answer Synthesis & Quality Validation.

Verifies all 15 synthesis and validation requirements:
1. Real local SQLite data reference answers format into standardized 5-part structure.
2. Evidence linkage: Every StructuredFact has an evidence_reference matching an EvidenceItem.
3. Rejection of ungrounded quantitative claims via deterministic validation.
4. Unit and denominator preservation (e.g. repositories vs postings).
5. Missing values not converted to zero.
6. Rejection of trend projection from single/insufficient observations.
7. Separation of overall window direction vs latest period velocity.
8. Rejection of describing stored job postings as global vacancy totals.
9. Rejection of describing O*NET taxonomy baselines as live employer hiring demand.
10. Rejection of describing GitHub developer adoption as employer hiring demand.
11. Rejection of missing/fabricated evidence citations.
12. Rejection of completed status for unsupported forecasting and workforce simulation.
13. Safe failure responses when validation fails.
14. Cross-portal and cross-company protection against unauthorized access.
15. Deterministic output for identical inputs across repeated executions.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
import pytest

from app.models.auth import AuthenticatedUser, UserProfile
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerRequest,
    CoreIntelligenceAnswerResponse,
    StructuredFact,
    EvidenceItem,
)
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test_synth_user_1",
        email="synth@example.com",
    )


def mock_company_user(company_id: str = "comp_alpha") -> UserProfile:
    return UserProfile(
        uid="test_comp_user_1",
        email="corp@alpha.com",
        company_id=company_id,
    )


@pytest.mark.parametrize("question", [
    "What is Python used for?",
    "Explain UI/UX trends in simple terms",
])
def test_general_explanations_do_not_route_to_reference_or_market_trend(question: str) -> None:
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message=question))
    assert plan.intent == "general_explanation"
    assert "skill_technology_reference" not in plan.selected_capabilities
    assert "trend_velocity_analysis" not in plan.selected_capabilities


def test_explicit_demand_trend_remains_an_operational_trend_request() -> None:
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        CoreIntelligenceAnswerRequest(message="Explain Python demand trends in simple terms")
    )
    assert plan.intent == "analyze_trend"
    assert "trend_velocity_analysis" in plan.selected_capabilities


def _make_obs(
    *,
    source: str = "jsearch",
    signal_type: str = "demand",
    skill: str = "Python",
    skill_id: str = "python",
    period: str = "2026-05",
    value: float = 100.0,
    posting_id: str | None = None,
    metadata: dict | None = None,
) -> MarketObservation:
    year, month = (int(p) for p in period.split("-"))
    dt = datetime(year, month, 15, 12, 0, 0, tzinfo=timezone.utc)
    return MarketObservation(
        id=f"obs-{source}-{skill_id}-{period}",
        source=source,
        signal_type=signal_type,
        observed_at=dt,
        period=period,
        location="Global",
        scope="global",
        skill=skill,
        skill_id=skill_id,
        value=value,
        unit={
            "interest": "tagged_questions",
            "adoption": "developers",
            "demand": "job_postings",
            "pageviews": "pageviews",
        }.get(signal_type, "observations"),
        series_id=f"{source}:{skill_id}:global:v1",
        posting_id=posting_id,
        metadata=metadata or {},
        data_origin="real",
        history_type="platform_collected",
        quality="valid",
    )


# =============================================================================
# 1. REAL LOCAL SQLITE DATA REFERENCE ANSWERS & CONVERSATIONAL STRUCTURE
# =============================================================================

@pytest.mark.integration
def test_real_sqlite_data_reference_synthesis(local_reference_database):
    """Verify grounded occupation results open with a concise answer and relevant details."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "completed"
    assert len(resp.facts) > 0
    assert len(resp.evidence) > 0

    assert resp.answer.startswith("Identified")
    assert "**Observed details**" in resp.answer
    assert "**Sources**" in resp.answer
    assert "**Limitations:**" in resp.answer
    assert "### 1. Direct Answer" not in resp.answer

    # Verify real content
    assert "Software Developers" in resp.answer
    assert "15-1252.00" in resp.answer
    assert "ref_onet_software_skills" in resp.answer


# =============================================================================
# 2. EVIDENCE LINKAGE INTEGRITY
# =============================================================================

def test_evidence_linkage_integrity():
    """Verify every StructuredFact has an evidence_reference matching an EvidenceItem."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    resp = service.answer(req, authenticated_user=mock_auth_user())

    evidence_ids = {e.evidence_id for e in resp.evidence}
    for fact in resp.facts:
        assert fact.evidence_reference is not None, f"Fact {fact.fact_id} missing evidence_reference"
        assert fact.evidence_reference in evidence_ids, (
            f"Fact {fact.fact_id} references {fact.evidence_reference} not found in evidence IDs: {evidence_ids}"
        )


# =============================================================================
# 3. REJECTION OF UNGROUNDED QUANTITATIVE CLAIMS
# =============================================================================

@pytest.mark.integration
def test_rejection_of_ungrounded_quantitative_claims(local_reference_database):
    """Verify that injecting ungrounded numeric claims triggers validation failure."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    plan = service.intent_planner.create_plan(req)

    facts, evidence, _ = service._handle_occupation_software_skills(req, plan)
    legit_answer = service._synthesize_answer(plan.intent, facts, evidence, ["occupation_software_skills"], req)

    # Legitimate answer passes validation
    st, reasons = service._validate_response(legit_answer, facts, evidence, ["occupation_software_skills"], plan)
    assert st == "completed"
    assert len(reasons) == 0

    # Tampered answer with fabricated number (987654) fails validation
    tampered_answer = legit_answer + "\n- Additionally, there are 987654 jobs available."
    st_bad, reasons_bad = service._validate_response(tampered_answer, facts, evidence, ["occupation_software_skills"], plan)
    assert st_bad == "failed"
    assert "VALIDATION_ERROR_UNGROUNDED_QUANTITATIVE_CLAIM" in reasons_bad


# =============================================================================
# 4. UNIT AND DENOMINATOR PRESERVATION
# =============================================================================

def test_unit_and_denominator_preservation():
    """Verify that mislabeling GitHub repository count as postings triggers validation failure."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="Tell me about python")
    plan = service.intent_planner.create_plan(req)

    facts, evidence, _ = service._handle_skill_technology_reference(req, plan)
    gh_fact = next((f for f in facts if f.source in {"ref_github_topic_adoption", "ref_github_language_adoption"}), None)
    if gh_fact:
        # Tamper answer to claim developers/repositories are job postings
        tampered_ans = f"Python has {gh_fact.metric_value} postings in the latest quarter."
        st, reasons = service._validate_response(tampered_ans, facts, evidence, ["skill_technology_reference"], plan)
        assert st == "failed"
        assert "VALIDATION_ERROR_UNIT_MISMATCH" in reasons


# =============================================================================
# 5. MISSING VALUES NOT CONVERTED TO ZERO
# =============================================================================

def test_missing_values_not_converted_to_zero():
    """Verify that missing values coerced to zero are detected and rejected."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="What is the trend for Python?"))

    facts = [
        StructuredFact(
            fact_id="fact_coerced_zero",
            fact_type="market_snapshot",
            entity_name="Python",
            metric_name="observed_metric_value",
            metric_value=0,
            details={"was_null": True},
            source="market_store",
            evidence_reference="ev_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_1", source="market_store", signal_type="demand", quality="valid", description="Observation record.")]

    st, reasons = service._validate_response("Observed value is 0.", facts, evidence, ["market_snapshot_retrieval"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_MISSING_VALUE_ZEROED" in reasons


# =============================================================================
# 6. REJECTION OF TREND FROM SINGLE OBSERVATION
# =============================================================================

def test_rejection_of_trend_from_single_observation():
    """Verify that single observation does not allow claiming a trend direction or slope."""
    service = ExecutionOrchestratorService()
    obs = [_make_obs(period="2026-07", value=150.0)]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status in {"insufficient_data", "blocked"}
    assert "trend_velocity_analysis" not in resp.capabilities_used
    assert not any(f.fact_type == "trend_analysis" for f in resp.facts)


def test_validation_rejects_single_obs_trend_claim():
    """Verify validation flags slope claims when observation count < 4."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="What is the trend for Python?"))

    facts = [
        StructuredFact(
            fact_id="fact_hist_1",
            fact_type="historical_observation",
            entity_name="Python",
            metric_name="demand",
            metric_value=150.0,
            period="2026-07",
            source="jsearch",
            evidence_reference="obs-1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="obs-1", source="jsearch", signal_type="demand", quality="valid", description="Single observation record.")]

    tampered_ans = "The slope is 10.0 and shows a growing trend across the market."
    st, reasons = service._validate_response(tampered_ans, facts, evidence, ["historical_signal_retrieval"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_SINGLE_OBSERVATION_TREND" in reasons


# =============================================================================
# 7. SEPARATION OF TREND DIRECTION VS LATEST VELOCITY
# =============================================================================

def test_separation_of_trend_direction_vs_latest_velocity():
    """Verify that trend analysis separates overall window direction from latest monthly velocity."""
    service = ExecutionOrchestratorService()
    obs = [
        _make_obs(period="2026-04", value=100.0),
        _make_obs(period="2026-05", value=120.0),
        _make_obs(period="2026-06", value=140.0),
        _make_obs(period="2026-07", value=160.0),
    ]
    req = CoreIntelligenceAnswerRequest(
        message="What is the trend for Python?",
        time_range="max_available",
        observations=obs,
    )

    resp = service.answer(req, authenticated_user=mock_auth_user())
    assert resp.execution_status == "completed"

    # Both metrics must be explicitly mentioned and distinguished
    assert "Theil-Sen Median Slope" in resp.answer
    assert "Overall Window Direction" in resp.answer
    assert "Monthly Velocity" in resp.answer
    assert "distinct metrics and must not be conflated" in resp.answer


def test_incidental_github_trend_facts_do_not_require_trend_answer_wording():
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(
        CoreIntelligenceAnswerRequest(message="What is Python?")
    )
    facts = [
        StructuredFact(
            fact_id="fact_github_trend",
            fact_type="trend_analysis",
            entity_name="Python",
            metric_name="trend_direction",
            metric_value="Mixed",
            period="2020-Q1_to_2026-Q1",
            source="github_innovation_graph",
            evidence_reference="ev_github_trend",
            details={"period_grain": "quarter"},
        )
    ]
    evidence = [
        EvidenceItem(
            evidence_id="ev_github_trend",
            source="github_innovation_graph",
            signal_type="trend_calculation",
            period="2020-Q1_to_2026-Q1",
            description="Quarterly public developer activity trend.",
        )
    ]

    status, reasons = service._validate_response(
        "Reference intelligence and developer adoption context retrieved for Python.",
        facts,
        evidence,
        ["skill_technology_reference"],
        plan,
    )

    assert status == "completed"
    assert "VALIDATION_ERROR_VELOCITY_TREND_CONFLATION" not in reasons


# =============================================================================
# 8. REJECTION OF GLOBAL VACANCY TOTAL CLAIMS
# =============================================================================

def test_rejection_of_global_vacancy_total_claims():
    """Verify that claiming stored postings represent total global vacancies fails validation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="Find jobs for Python"))

    facts = [
        StructuredFact(
            fact_id="fact_jobs_1",
            fact_type="stored_job_postings",
            entity_name="Python",
            metric_name="stored_postings_found",
            metric_value=5,
            unit="postings",
            source="stored_market_observations",
            evidence_reference="ev_job_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_job_1", source="stored_market_observations", signal_type="stored_posting", quality="valid", description="Stored job posting sample.")]

    # Legitimate answer stating "not total global vacancies" passes
    legit_ans = "Retrieved 5 postings from stored collection. Note: not total global vacancies."
    st, reasons = service._validate_response(legit_ans, facts, evidence, ["job_posting_search"], plan)
    assert st == "completed"

    # Conflated answer asserting global total fails
    bad_ans = "This represents 5 total global vacancies across the worldwide economy."
    st_bad, reasons_bad = service._validate_response(bad_ans, facts, evidence, ["job_posting_search"], plan)
    assert st_bad == "failed"
    assert "VALIDATION_ERROR_JOB_TOTAL_CLAIM" in reasons_bad


# =============================================================================
# 9. REJECTION OF DESCRIBING TAXONOMY AS EMPLOYER DEMAND
# =============================================================================

def test_rejection_of_describing_taxonomy_as_employer_demand():
    """Verify that conflating O*NET taxonomy baseline with live employer demand fails validation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="Software Developer software tools"))

    facts = [
        StructuredFact(
            fact_id="fact_soft_1",
            fact_type="software_skill",
            entity_name="Python",
            canonical_entity_id="tech:onet:python",
            metric_name="hot_technology",
            metric_value=True,
            source="ref_onet_software_skills",
            evidence_reference="ev_onet_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_onet_1", source="ref_onet_software_skills", signal_type="software_skill", quality="valid", description="O*NET software skill record.")]

    bad_ans = "This proves high employer hiring demand and active live job postings for software developers."
    st, reasons = service._validate_response(bad_ans, facts, evidence, ["occupation_software_skills"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_TAXONOMY_CONFLATED_WITH_HIRING_DEMAND" in reasons


# =============================================================================
# 10. REJECTION OF DESCRIBING GITHUB AS EMPLOYER DEMAND
# =============================================================================

def test_rejection_of_describing_github_as_employer_demand():
    """Verify that describing GitHub developer adoption as employer hiring demand fails validation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="Tell me about python"))

    facts = [
        StructuredFact(
            fact_id="fact_gh_1",
            fact_type="technology_adoption",
            entity_name="python",
            metric_name="github_developer_pushers",
            metric_value=50000,
            unit="developers",
            source="ref_github_topic_adoption",
            evidence_reference="ev_gh_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_gh_1", source="ref_github_topic_adoption", signal_type="adoption", quality="valid", description="GitHub developer adoption record.")]

    bad_ans = "This metric represents surging employer hiring demand in tech firms."
    st, reasons = service._validate_response(bad_ans, facts, evidence, ["skill_technology_reference"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_GITHUB_CONFLATED_WITH_HIRING_DEMAND" in reasons


# =============================================================================
# 11. REJECTION OF MISSING OR FABRICATED EVIDENCE CITATIONS
# =============================================================================

def test_rejection_of_missing_or_fabricated_evidence_citations():
    """Verify that citations in answer text not present in evidence items fail validation."""
    service = ExecutionOrchestratorService()
    plan = service.intent_planner.create_plan(CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?"))

    facts = [
        StructuredFact(
            fact_id="fact_1",
            fact_type="software_skill",
            entity_name="Docker",
            metric_name="hot_technology",
            metric_value=True,
            source="ref_onet_software_skills",
            evidence_reference="ev_real_1",
        )
    ]
    evidence = [EvidenceItem(evidence_id="ev_real_1", source="ref_onet_software_skills", signal_type="lookup", quality="valid", description="O*NET software skill record.")]

    bad_ans = "Retrieved Docker based on citation `ev_fabricated_citation_999`."
    st, reasons = service._validate_response(bad_ans, facts, evidence, ["occupation_software_skills"], plan)
    assert st == "failed"
    assert "VALIDATION_ERROR_MISSING_EVIDENCE_CITATION" in reasons


# =============================================================================
# 12. REJECTION OF COMPLETED STATUS FOR UNSUPPORTED FORECAST / SIMULATION
# =============================================================================

def test_rejection_of_completed_status_for_unsupported_forecast_or_simulation():
    """Verify forecasting and workforce simulation remain strictly unsupported."""
    service = ExecutionOrchestratorService()

    req_fc = CoreIntelligenceAnswerRequest(message="Forecast demand for React in 2027")
    resp_fc = service.answer(req_fc, authenticated_user=mock_auth_user())
    assert resp_fc.execution_status in {"unsupported", "insufficient_data"}
    assert len(resp_fc.facts) == 0

    req_sim = CoreIntelligenceAnswerRequest(message="Simulate workforce reallocation across teams")
    resp_sim = service.answer(req_sim, authenticated_user=mock_auth_user())
    assert resp_sim.execution_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in resp_sim.reason_codes
    assert len(resp_sim.facts) == 0


# =============================================================================
# 13. SAFE FAILURE RESPONSES WHEN VALIDATION FAILS
# =============================================================================

@pytest.mark.integration
def test_safe_failure_responses_when_validation_fails(monkeypatch, local_reference_database):
    """Verify that validation failures return 'failed' execution status and safe explanation."""
    service = ExecutionOrchestratorService()

    # Monkeypatch _synthesize_answer to inject ungrounded number
    def bad_synthesize(*args, **kwargs):
        return "Software developers use 777777 tools across the industry."

    monkeypatch.setattr(service, "_synthesize_answer", bad_synthesize)

    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")
    resp = service.answer(req, authenticated_user=mock_auth_user())

    assert resp.execution_status == "failed"
    assert "VALIDATION_ERROR_UNGROUNDED_QUANTITATIVE_CLAIM" in resp.reason_codes
    assert "couldn't verify this analysis" in resp.answer
    assert "777777" not in resp.answer
    assert resp.facts == []
    assert resp.evidence == []
    assert resp.capabilities_used == []


# =============================================================================
# 14. CROSS-PORTAL AND CROSS-COMPANY PROTECTION
# =============================================================================

def test_cross_portal_and_cross_company_protection():
    """Verify cross-company requests are blocked and facts remain empty."""
    service = ExecutionOrchestratorService()

    user = mock_company_user("comp_authorized")
    req = CoreIntelligenceAnswerRequest(
        message="Show company workforce intelligence",
        portal_type="company",
        company_id="comp_unauthorized_target",
    )

    resp = service.answer(req, authenticated_user=user)
    assert resp.execution_status == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in resp.reason_codes
    assert len(resp.facts) == 0
    assert "Access denied" in resp.answer


# =============================================================================
# 15. DETERMINISTIC SYNTHESIS AND VALIDATION
# =============================================================================

@pytest.mark.integration
def test_deterministic_synthesis_and_validation(local_reference_database):
    """Verify identical requests produce identical facts, evidence, and answer text."""
    service = ExecutionOrchestratorService()
    req = CoreIntelligenceAnswerRequest(message="What software tools does a Software Developer use?")

    resp_1 = service.answer(req, authenticated_user=mock_auth_user())
    resp_2 = service.answer(req, authenticated_user=mock_auth_user())

    assert resp_1.execution_status == resp_2.execution_status == "completed"
    assert resp_1.answer == resp_2.answer
    assert len(resp_1.facts) == len(resp_2.facts)
    assert [f.fact_id for f in resp_1.facts] == [f.fact_id for f in resp_2.facts]
    assert [e.evidence_id for e in resp_1.evidence] == [e.evidence_id for e in resp_2.evidence]

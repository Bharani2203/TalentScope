"""Comprehensive Verification Suite for Greenfield V2 Gemini B Fallback & Presentation.

Tests:
1. Deterministic engines bypass Gemini B when data is ready.
2. Eligible missing-data paths safely invoke Gemini B.
3. Ineligible features (verified postings, citations, alignments) NEVER invoke Gemini B.
4. Gemini B error handling (timeout, quota, invalid claims, provider failure) falls back cleanly.
5. Absolute prevention of Gemini A fallback.
6. Explicit capability override vs direct search behavior across 7 representative queries.
7. Safe rejection of unsupported capability IDs.
8. Canonical resolution of role_preparation_actions to job_preparation_actions.
9. Question-appropriate answer types (explanation, comparison, recommendations, roadmap).
"""

from unittest.mock import MagicMock
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.intelligence_v2.capability_registry import (
    CAPABILITIES,
    canonical_capability_id,
)
from app.intelligence_v2.feature_policy import (
    FEATURE_ANSWER_POLICIES,
    get_feature_answer_policy,
)
from app.intelligence_v2.intent_planner import V2IntentPlanner
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.services.gemini_b_guidance_service import GeminiBGuidanceService


def make_mock_settings(**overrides):
    values = {
        "gemini_b_api_key": SecretStr("mock-key-for-offline-test"),
        "gemini_b_model": "mock-model",
        "gemini_b_backup_model": None,
        "gemini_b_request_timeout_seconds": 2,
        "gemini_b_max_calls_per_minute": 10,
        "gemini_b_max_calls_per_day": 20,
        "gemini_b_max_calls_per_user_per_hour": 10,
        "gemini_b_max_input_chars": 2000,
        "gemini_b_max_output_tokens": 128,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


# =============================================================================
# 1. Deterministic Bypass of Gemini B
# =============================================================================

def test_ready_role_preparation_actions_bypasses_gemini_b():
    """Deterministic role preparation plan is ready from O*NET/ESCO; Gemini B must not be called."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="Give me a preparation plan for Web Developer",
        domain="job",
        capability_id="job_preparation_actions",
        target_role="Web Developer",
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "deterministic"
    assert res.source_mode == "platform_data"
    assert not mock_gemini.generate.called


def test_job_verified_postings_bypasses_gemini_b():
    """Verified job search queries platform store; Gemini B must not be called."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="Find postings for Python",
        domain="job",
        capability_id="job_verified_postings",
        selected_skills=["Python"],
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "deterministic"
    assert not mock_gemini.generate.called


def test_career_mobility_pathways_bypasses_gemini_b():
    """Career mobility uses validated O*NET related occupations; Gemini B must not be called."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="What career mobility pathways exist for Database Administrator?",
        domain="job",
        capability_id="job_mobility_pathways",
        target_role="Database Administrator",
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "deterministic"
    assert not mock_gemini.generate.called


# =============================================================================
# 2. Eligible Missing-Data Paths Invoke Gemini B
# =============================================================================

def test_skill_demand_trends_insufficient_data_invokes_gemini_b():
    """Skill demand trends lacks 4 completed months in local store; invokes Gemini B for qualitative guidance."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    mock_gemini.generate.return_value = "Public Relations focuses on managing communication and relationships between an organization and the public."
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Public Relations?",
        domain="skill",
        capability_id="skill_demand_trends",
        selected_skills=["Public Relations"],
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "gemini"
    assert res.source_mode == "ai_general_guidance"
    assert res.answer == "Public Relations focuses on managing communication and relationships between an organization and the public."
    assert mock_gemini.generate.called
    assert "General AI guidance only" in res.limitations[0]


def test_market_trend_velocity_insufficient_data_invokes_gemini_b():
    """Market trend velocity requires 4 consecutive completed periods; falls back to Gemini B."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    mock_gemini.generate.return_value = "Market interest in Go shows steady adoption in microservices and cloud tooling."
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="Show velocity for Go",
        domain="market",
        capability_id="market_trend_velocity",
        selected_skills=["Go"],
    )
    res = orchestrator.answer(req)

    assert res.status == "ready"
    assert res.answer_origin == "gemini"
    assert res.source_mode == "ai_general_guidance"
    assert mock_gemini.generate.called


# =============================================================================
# 3. Ineligible Features NEVER Invoke Gemini B
# =============================================================================

@pytest.mark.parametrize(
    "ineligible_cap,domain,kw",
    [
        ("job_verified_postings", "job", {"selected_skills": ["UnicornLanguage"]}),
        ("skill_evidence_citations", "skill", {"selected_skills": ["UnknownSkill"]}),
        ("market_evidence_citations", "market", {}),
        ("skill_role_alignment", "skill", {"target_role": "Software Developer"}),
        ("job_profile_alignment", "job", {"target_role": "Software Developer"}),
    ],
)
def test_ineligible_features_never_invoke_gemini_b(ineligible_cap: str, domain: str, kw: dict):
    """Features requiring provider records, strict deterministic comparison, or citations never call Gemini B."""
    policy = FEATURE_ANSWER_POLICIES.get(ineligible_cap)
    assert policy is not None
    assert policy.gemini_b_fallback is False

    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="Request for ineligible feature",
        domain=domain,
        capability_id=ineligible_cap,
        **kw,
    )
    res = orchestrator.answer(req)

    assert res.answer_origin != "gemini"
    assert not mock_gemini.generate.called


# =============================================================================
# 4. Gemini B Failure / Quota / Timeout Handling
# =============================================================================

def test_gemini_b_unavailable_returns_safe_explanation_without_crash():
    """When Gemini B returns None (offline, timeout, quota), response clearly explains limitation."""
    orchestrator = V2Orchestrator()
    mock_gemini = MagicMock(spec=GeminiBGuidanceService)
    mock_gemini.generate.return_value = None  # Simulates unavailable / timeout
    orchestrator.gemini_b_service = mock_gemini

    req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Public Relations?",
        domain="skill",
        capability_id="skill_demand_trends",
        selected_skills=["Public Relations"],
    )
    res = orchestrator.answer(req)

    assert res.answer_origin == "deterministic"
    assert "General AI guidance is unavailable right now" in res.answer
    assert any("No Gemini guidance was available" in lim for lim in res.limitations)
    assert len(res.next_actions) > 0


def test_gemini_b_forbidden_claims_sanitized_or_rejected():
    """Gemini B guidance containing fake citations, links, or metric numbers is rejected by service filter."""
    service = GeminiBGuidanceService(make_mock_settings())

    assert service._valid_text("According to research, Python is #1 ranked.", 500) is None
    assert service._valid_text("Source: https://example.com/fake-postings", 500) is None
    assert service._valid_text("Average salary is $150,000 with 4,000 vacancies.", 500) is None
    assert service._valid_text("[Click here](http://malicious.link)", 500) is None
    # Valid plain English guidance passes
    valid = service._valid_text("Python is a versatile programming language used widely in data science and web development.", 500)
    assert valid is not None


# =============================================================================
# 5. Gemini A Isolation
# =============================================================================

def test_system_never_invokes_gemini_a_as_fallback():
    """Orchestrator and V2 modules have zero dependency on Gemini A."""
    from app.intelligence_v2 import orchestrator as orch_module
    import inspect

    source = inspect.getsource(orch_module)
    assert "gemini_api_key" not in source
    assert "llm_explanation_service" not in source
    assert "GeminiService" not in source


# =============================================================================
# 6. Explicit Capability Override vs Direct Search
# =============================================================================

def test_explicit_capability_override_supersedes_keywords():
    """Client explicitly specifying capability_id overrides keyword heuristic routing."""
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="What are the job postings available?",
        domain="skill",
        capability_id="skill_lookup",
        selected_skills=["Python"],
    )
    res = orchestrator.answer(req)
    assert res.intent == "skill_lookup"
    assert res.status == "ready"


def test_unsupported_capability_id_returns_explicit_safe_error():
    """Unsupported capability ID returns safe 'unsupported' status without executing another feature."""
    orchestrator = V2Orchestrator()
    req = CoreIntelligenceAnswerRequest(
        message="Execute unsupported feature",
        domain="skill",
        capability_id="completely_fictitious_capability_v99",
    )
    res = orchestrator.answer(req)
    assert res.status == "error"
    assert res.execution_status == "unsupported"
    assert "Unsupported capability" in res.answer
    assert "CAPABILITY_UNSUPPORTED" in res.reason_codes


def test_canonical_capability_alias_resolution():
    """role_preparation_actions and job_preparation_actions resolve to one canonical capability."""
    assert canonical_capability_id("role_preparation_actions", "job") == "job_preparation_actions"
    assert canonical_capability_id("role_preparation_actions", "skill") == "job_preparation_actions"
    assert canonical_capability_id("job_preparation_actions", "job") == "job_preparation_actions"

    # FEATURE_ANSWER_POLICIES contains the exact canonical capabilities matching CAPABILITIES
    assert set(FEATURE_ANSWER_POLICIES) == set(CAPABILITIES)
    # Helper resolves aliases cleanly
    policy = get_feature_answer_policy("role_preparation_actions", "job")
    assert policy is not None
    assert policy.handler == "run_preparation_actions"


# =============================================================================
# 7. Verification of the 7 Representative Direct Search Queries
# =============================================================================

def test_seven_representative_queries_route_correctly():
    """Verify that direct search without selecting a capability plans appropriate capabilities and entities."""
    planner = V2IntentPlanner()

    # 1. "Explain REST APIs."
    p1 = planner.plan("Explain REST APIs.")
    assert p1.capability_id == "skill_reference_profile"
    assert p1.target_skill is not None
    assert "REST" in p1.target_skill

    # 2. "Compare Python and Java."
    p2 = planner.plan("Compare Python and Java.")
    entities_p2 = [e.canonical_name for e in p2.entities]
    assert "Python" in entities_p2
    assert "Java" in entities_p2

    # 3. "What skills should I learn for software engineering?"
    p3 = planner.plan("What skills should I learn for software engineering?")
    assert p3.capability_id == "job_preparation_actions"
    assert p3.target_role == "Software Developers"

    # 4. "Give me a roadmap to become a backend developer."
    p4 = planner.plan("Give me a roadmap to become a backend developer.")
    assert p4.capability_id == "job_preparation_actions"
    assert p4.target_role == "Software Developers"

    # 5. "Show the current market trend for Python."
    p5 = planner.plan("Show the current market trend for Python.")
    assert p5.capability_id == "market_trend_velocity"
    assert p5.target_skill == "Python"

    # 6. "Find real Java developer jobs."
    p6 = planner.plan("Find real Java developer jobs.")
    assert p6.capability_id == "job_verified_postings"
    assert p6.target_skill == "Java"

    # 7. "Prepare me for a data analyst role."
    p7 = planner.plan("Prepare me for a data analyst role.")
    assert p7.capability_id == "job_preparation_actions"
    assert p7.target_role is not None
    assert "Analyst" in p7.target_role


# =============================================================================
# 8. Frontend Presentation & Answer Types
# =============================================================================

def test_presentation_answer_types_and_comparison():
    """Formatting assigns question-appropriate answer types (comparison, roadmap, explanation)."""
    orchestrator = V2Orchestrator()

    # Comparison query gets answer_type="comparison"
    req_comp = CoreIntelligenceAnswerRequest(
        message="Compare Python and Java",
        domain="skill",
    )
    res_comp = orchestrator.answer(req_comp)
    assert res_comp.answer_type == "comparison"
    assert "Python vs Java" in (res_comp.answer_title or "")

    # Roadmap query gets answer_type="roadmap"
    req_road = CoreIntelligenceAnswerRequest(
        message="Give me a roadmap to become a backend developer",
        domain="job",
    )
    res_road = orchestrator.answer(req_road)
    assert res_road.answer_type == "roadmap"
    assert "Step 1:" in res_road.answer

    # Concept explanation gets answer_type="explanation"
    req_exp = CoreIntelligenceAnswerRequest(
        message="Explain REST APIs",
        domain="skill",
    )
    res_exp = orchestrator.answer(req_exp)
    assert res_exp.answer_type == "explanation"


# =============================================================================
# 9. Exhaustive Capability Coverage & Legacy Alias Parity
# =============================================================================

@pytest.mark.parametrize(
    "cap_id,domain,kw",
    [
        ("skill_demand_trends", "skill", {"selected_skills": ["Python"]}),
        ("skill_historical_signals", "skill", {"selected_skills": ["Python"]}),
        ("skill_role_alignment", "skill", {"selected_skills": ["Python"], "target_role": "Software Developer"}),
        ("skill_evidence_citations", "skill", {"selected_skills": ["Python"]}),
        ("skill_reference_profile", "skill", {"selected_skills": ["Python"]}),
        ("skill_action_recommendations", "skill", {"selected_skills": ["Python"]}),
        ("market_intelligence_snapshot", "market", {}),
        ("market_tech_signals", "market", {}),
        ("market_trend_velocity", "market", {"selected_skills": ["Python"]}),
        ("market_evidence_citations", "market", {}),
        ("job_verified_postings", "job", {"selected_skills": ["Python"]}),
        ("job_role_requirements", "job", {"target_role": "Software Developer"}),
        ("job_mobility_pathways", "job", {"target_role": "Software Developer"}),
        ("job_profile_alignment", "job", {"selected_skills": ["Python"], "target_role": "Software Developer"}),
        ("job_preparation_actions", "job", {"target_role": "Software Developer"}),
    ],
)
def test_all_fifteen_canonical_capabilities_execute_without_keyword_override(cap_id: str, domain: str, kw: dict):
    """Every canonical capability executes its own handler and is never hijacked by conflicting message keywords."""
    from app.models.auth import AuthenticatedUser
    user = AuthenticatedUser(uid="test-user-id", email="test@example.com")
    orchestrator = V2Orchestrator()
    # Message contains strong keywords for a different capability ("verified job postings")
    req = CoreIntelligenceAnswerRequest(
        message="Find verified job postings for Python Developer",
        domain=domain,
        capability_id=cap_id,
        **kw,
    )
    res = orchestrator.answer(req, authenticated_user=user)
    assert res.intent == cap_id
    assert res.execution_status != "unsupported"
    assert res.status != "error"


def test_all_legacy_aliases_resolve_to_canonical_capabilities():
    """Verify all 17 legacy domain pairs in LEGACY_CAPABILITY_MAP map to canonical capabilities."""
    from app.intelligence_v2.capability_registry import LEGACY_CAPABILITY_MAP, canonical_capability_id

    assert len(LEGACY_CAPABILITY_MAP) == 17
    for (legacy_domain, legacy_cap), expected_canonical in LEGACY_CAPABILITY_MAP.items():
        resolved = canonical_capability_id(legacy_cap, legacy_domain)
        assert resolved == expected_canonical, f"Failed for ({legacy_domain}, {legacy_cap})"


def test_role_preparation_actions_and_job_preparation_actions_parity():
    """role_preparation_actions and job_preparation_actions produce identical plans without duplicate execution."""
    orchestrator = V2Orchestrator()
    req1 = CoreIntelligenceAnswerRequest(
        message="Prepare for Web Developer",
        domain="job",
        capability_id="job_preparation_actions",
        target_role="Web Developer",
    )
    res1 = orchestrator.answer(req1)

    req2 = CoreIntelligenceAnswerRequest(
        message="Prepare for Web Developer",
        domain="job",
        capability_id="role_preparation_actions",
        target_role="Web Developer",
    )
    res2 = orchestrator.answer(req2)

    assert res1.intent == "job_preparation_actions"
    assert res2.intent == "job_preparation_actions"
    assert res1.status == res2.status == "ready"
    assert res1.answer == res2.answer
    assert len(res1.facts) == len(res2.facts)


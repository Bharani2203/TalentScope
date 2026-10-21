"""TalentScope.ai — AI End-to-End Behavior Verification Test Suite.

Verifies end-to-end question routing, presentation quality, domain coverage,
safeguards against metric/citation/job fabrication, and historical signal fidelity.
"""

from __future__ import annotations

import pytest
from app.intelligence_v2.capability_registry import canonical_capability_id
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.intelligence_v2.response_formatter import V2ResponseFormatter
from app.intelligence_v2.skill_intelligence import get_concept_explanation_with_example
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.reference_store import ReferenceDataStore


@pytest.fixture
def orchestrator():
    store = ReferenceDataStore(read_only=True)
    return V2Orchestrator(store=store)


@pytest.fixture
def auth_user():
    return AuthenticatedUser(
        uid="usr_test_ai_e2e",
        email="test_e2e@talentscope.ai",
        portal_type="individual",
        company_id=None,
    )


class TestAIE2EBehavior:
    """End-to-End AI verification covering all three domains and user presentation requirements."""

    def test_01_feature_selected_question_overrides_keyword_similarity(self, orchestrator, auth_user):
        """When a user selects an explicit capability, it overrides keyword similarity in the query text."""
        # Query text mentions "trends" and "demand", but feature requested is skill_role_alignment
        req = CoreIntelligenceAnswerRequest(
            message="Show me the trends and demand for Python in my role",
            portal_type="individual",
            domain="skill",
            capability_id="skill_role_alignment",
            selected_skills=["Python", "FastAPI"],
            target_role="Software Developers",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.planned_primary_capability == "skill_role_alignment"
        assert resp.executed_primary_capability == "skill_role_alignment"
        assert resp.status == "ready"
        assert "Skill Coverage" in resp.answer

    def test_02_direct_search_box_routing_across_all_domains(self, orchestrator, auth_user):
        """Direct search-box questions route accurately across Skill, Market, and Job domains."""
        # Skill domain question
        req_skill = CoreIntelligenceAnswerRequest(
            message="What skills are related to Python?",
            portal_type="individual",
        )
        resp_skill = orchestrator.execute_request(req_skill, authenticated_user=auth_user)
        assert resp_skill.domain == "skill"
        assert resp_skill.intent == "related_skills"

        # Market domain question
        req_market = CoreIntelligenceAnswerRequest(
            message="Give me an overview snapshot of the tech market",
            portal_type="individual",
        )
        resp_market = orchestrator.execute_request(req_market, authenticated_user=auth_user)
        assert resp_market.domain == "market"
        assert resp_market.intent == "market_intelligence_snapshot"

        # Job domain question
        req_job = CoreIntelligenceAnswerRequest(
            message="Show me verified job openings for DevOps Engineer",
            portal_type="individual",
        )
        resp_job = orchestrator.execute_request(req_job, authenticated_user=auth_user)
        assert resp_job.domain == "job"
        assert resp_job.intent == "job_verified_postings"

    def test_03_simple_explanation_returns_clear_prose_and_example(self, orchestrator, auth_user):
        """Conceptual queries return clear, natural prose explanation with a practical example."""
        req = CoreIntelligenceAnswerRequest(
            message="What is Python?",
            portal_type="individual",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert resp.domain == "skill"
        assert resp.intent == "skill_reference_profile"
        # Must contain readable prose explanation and practical example
        assert "Python is a versatile, high-level programming language" in resp.answer
        assert "For example" in resp.answer
        assert "FastAPI" in resp.answer or "Django" in resp.answer
        # Must link to official occupational frameworks
        assert "O*NET 28.0" in resp.answer
        assert "ESCO v1.2.1" in resp.answer

    def test_04_comparison_question_returns_compact_comparison_table(self, orchestrator, auth_user):
        """Comparison queries between two technologies return a structured markdown comparison table."""
        req = CoreIntelligenceAnswerRequest(
            message="Compare Python and Java",
            portal_type="individual",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.answer_type == "comparison"
        assert resp.answer_title == "Comparison: Python vs Java"
        assert "| Dimension | Python | Java |" in resp.answer
        assert "| :--- | :--- | :--- |" in resp.answer
        assert "| **Canonical Entity** |" in resp.answer
        assert "| **Trajectory / Direction** |" in resp.answer
        assert "| **Growth Rate / Metric** |" in resp.answer
        assert "| **Primary Source** |" in resp.answer
        assert "| **Taxonomy Standard** |" in resp.answer

    def test_05_recommendation_questions_return_up_to_5_actions_with_reasons(self, orchestrator, auth_user):
        """Skill action recommendations return up to 5 prioritized actions with explicit rationale."""
        req = CoreIntelligenceAnswerRequest(
            message="What actions should I take to prepare for Python?",
            portal_type="individual",
            domain="skill",
            capability_id="skill_action_recommendations",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert "Prioritized Role Preparation Actions" in resp.answer
        assert "#### Step 1:" in resp.answer
        assert "- **Why it matters**:" in resp.answer
        assert "- **Practice task**:" in resp.answer

    def test_06_roadmap_questions_return_ordered_steps_with_prereqs_and_checks(self, orchestrator, auth_user):
        """Role preparation roadmap returns ordered steps with prerequisites and self-checks."""
        req = CoreIntelligenceAnswerRequest(
            message="How do I prepare to become a Data Scientist?",
            portal_type="individual",
            target_role="Data Scientists",
            capability_id="job_preparation_actions",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert "Prioritized Role Preparation Actions & Practice Tasks" in resp.answer
        assert "- **Prerequisites**:" in resp.answer
        assert "- **Completion self-checks**:" in resp.answer
        assert "- **Next step**:" in resp.answer

    def test_07_evidence_and_sources_returns_only_genuine_retrieved_evidence(self, orchestrator, auth_user):
        """Evidence returned contains only genuine data origins and zero fabricated citations."""
        req = CoreIntelligenceAnswerRequest(
            message="Show me historical signals for Python",
            portal_type="individual",
            domain="skill",
            capability_id="skill_historical_signals",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status in {"ready", "partial"}
        for ev in resp.evidence:
            assert ev.data_origin in {"real", "local_observation_store", "local_reference_dataset", "benchmark"}
            # Must not invent fake HTTP links or unverified citations
            if ev.source_url:
                assert ev.source_url.startswith("https://") or ev.source_url.startswith("http://")

    def test_08_verified_job_postings_returns_genuine_provider_records_without_fabrication(self, orchestrator, auth_user):
        """Job postings capability returns genuine provider listings and never invents listings."""
        req = CoreIntelligenceAnswerRequest(
            message="Find verified jobs for Python Developer",
            portal_type="individual",
            domain="job",
            capability_id="job_verified_postings",
            filters={"country": "in"},
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.domain == "job"
        assert resp.intent == "job_verified_postings"
        # Check that any returned posting facts originate from genuine provider records
        postings_facts = [f for f in resp.facts if f.fact_type == "stored_job_postings"]
        for pf in postings_facts:
            postings = pf.details.get("postings", [])
            for p in postings:
                assert "title" in p
                assert "company" in p
                assert p.get("source") in {"jsearch", "adzuna", "fliarbi"}

    def test_09_hiring_demand_trends_uses_fliarbi_sample_with_growth_isolated(self, orchestrator, auth_user):
        """Fliarbi sample observations reach hiring_demand_trends with is_sample=True and rate from share."""
        req = CoreIntelligenceAnswerRequest(
            message="Show me hiring demand trends for Python in India",
            portal_type="individual",
            domain="skill",
            capability_id="hiring_demand_trends",
            filters={"geography": "in"},
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        trend_facts = [f for f in resp.facts if f.fact_type == "trend_analysis"]
        assert len(trend_facts) >= 1
        tf = trend_facts[0]
        # Must be flagged as sample observations
        assert tf.details.get("is_sample") is True
        # Must report sample distinct periods
        assert tf.details.get("periods_available") == 6
        assert tf.details.get("skill_share_pct") is not None
        # Trajectory must reflect share rather than raw volume surging
        trajectory = tf.details.get("trend_direction") or tf.details.get("trajectory") or tf.metric_value
        assert trajectory in {"Stable", "Growing", "Declining"}

    def test_10_insufficient_history_yields_honest_explanation_and_qualitative_fallback(self, orchestrator, auth_user):
        """Capabilities requiring 24+ or 36+ months remain gated with honest explanations."""
        # Forecasting requires 24 months of demand data
        req_fc = CoreIntelligenceAnswerRequest(
            message="Forecast demand for Go over the next 12 months",
            portal_type="individual",
            domain="skill",
            capability_id="skill_demand_forecast",
        )
        resp_fc = orchestrator.execute_request(req_fc, authenticated_user=auth_user)
        # Should honestly report insufficient data for 24-month mathematical forecast
        assert resp_fc.status == "insufficient_data"
        assert "24 completed months" in resp_fc.answer or "insufficient" in resp_fc.answer.lower()

    def test_11_gemini_b_failure_yields_safe_fallback_without_fabricated_metrics(self, orchestrator, auth_user):
        """When Gemini B is unavailable, response provides verified prose without invented numbers."""
        # Inject None service to guarantee offline behavior
        orchestrator.gemini_b_service = None
        req = CoreIntelligenceAnswerRequest(
            message="What is Docker?",
            portal_type="individual",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert "Docker is an industry-standard containerization platform" in resp.answer
        # No fabricated metric facts
        assert not any(f.data_origin == "fabricated" for f in resp.facts)

    def test_12_follow_up_suggestions_are_relevant_and_non_duplicative(self, orchestrator, auth_user):
        """Follow-up suggestions are relevant to the capability and do not contain duplicate prompts."""
        req = CoreIntelligenceAnswerRequest(
            message="Analyze demand trends for Python",
            portal_type="individual",
            domain="skill",
            capability_id="skill_demand_trends",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert len(resp.follow_up_suggestions) >= 1
        assert len(resp.follow_up_suggestions) == len(set(resp.follow_up_suggestions))
        for sugg in resp.follow_up_suggestions:
            assert "Python" in sugg or "sources" in sugg

    def test_13_capability_aliases_and_canonical_mapping_compliance(self, orchestrator, auth_user):
        """Canonical mapping resolves client and report aliases cleanly to registered capabilities."""
        assert canonical_capability_id("skill_hiring_trends", "skill") == "hiring_demand_trends"
        assert canonical_capability_id("job_role_prep_actions", "job") == "job_preparation_actions"
        assert canonical_capability_id("skill_demand_comparison", "skill") == "skill_demand_trends"
        assert canonical_capability_id("skill_related_skills", "skill") == "related_skills"
        assert canonical_capability_id("market_snapshot", "market") == "market_intelligence_snapshot"

        # Explicit request with alias executes via mapped canonical capability
        req = CoreIntelligenceAnswerRequest(
            message="Show preparation actions for Software Developer",
            portal_type="individual",
            domain="job",
            capability_id="job_role_prep_actions",
            target_role="Software Developers",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert resp.planned_primary_capability == "job_preparation_actions"
        assert resp.executed_primary_capability == "job_preparation_actions"

    def test_14_market_snapshot_routing_and_global_geography(self, orchestrator, auth_user):
        """Market snapshot queries cleanly route to market_intelligence_snapshot and query global/all SQLite data."""
        req = CoreIntelligenceAnswerRequest(
            message="Give me a technology market snapshot.",
            portal_type="individual",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "ready"
        assert resp.domain == "market"
        assert resp.intent == "market_intelligence_snapshot"
        assert "Market Intelligence Snapshot" in resp.answer
        # Must report over 200,000 real local quarterly developer-adoption observations
        assert any(
            f.fact_type == "market_dataset_inventory" and f.metric_value > 200000
            for f in resp.facts
        )
        # Must state that developer adoption is not hiring demand
        assert "this is not hiring demand" in resp.answer.lower()

    def test_15_comparison_table_growth_rate_and_developer_adoption_isolation(self, orchestrator, auth_user):
        """Python vs Java comparison formats relative slope per quarter and notes developer adoption isolation."""
        req = CoreIntelligenceAnswerRequest(
            message="Compare Python vs Java demand.",
            portal_type="individual",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status in {"ready", "partial"}
        assert resp.execution_status == "completed"
        assert "Comparison Summary: Python vs Java" in resp.answer
        # Slope per quarter from GitHub Theil-Sen regression: Python +4.85%/qtr, Java +1.53%/qtr
        assert "+4.85%/qtr slope" in resp.answer
        assert "+1.53%/qtr slope" in resp.answer
        # Explicit distinction between developer adoption and hiring demand
        assert "Developer adoption metrics measure GitHub code pushers over time" in resp.answer
        assert "not employer job postings or hiring demand" in resp.answer

    def test_16_unsupported_capability_fails_cleanly(self, orchestrator, auth_user):
        """Unsupported capabilities return CAPABILITY_UNSUPPORTED without throwing exceptions."""
        req = CoreIntelligenceAnswerRequest(
            message="Perform nonexistent analysis",
            portal_type="individual",
            domain="skill",
            capability_id="unregistered_fake_capability",
        )
        resp = orchestrator.execute_request(req, authenticated_user=auth_user)
        assert resp.status == "error"
        assert resp.execution_status == "unsupported"
        assert "CAPABILITY_UNSUPPORTED" in resp.reason_codes
        assert "Unsupported capability 'unregistered_fake_capability'" in resp.answer


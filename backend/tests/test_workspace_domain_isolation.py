"""Focused tests for domain-scoped conversation isolation and domain-specific filter validation."""

from __future__ import annotations

from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.storage.conversation_store import ConversationStore


def test_conversation_store_isolates_conversations_by_domain() -> None:
    store = ConversationStore()

    skill_conv = store.create_conversation(
        user_id="user_test_domain_iso",
        portal_type="individual",
        domain="skill",
        title="Python Skill Session",
        filters={"scope": "All Skills", "location": "Bangalore, India"},
    )
    market_conv = store.create_conversation(
        user_id="user_test_domain_iso",
        portal_type="individual",
        domain="market",
        title="Microsoft Market Session",
        filters={"scope": "All Companies", "location": "Bangalore, India"},
    )
    job_conv = store.create_conversation(
        user_id="user_test_domain_iso",
        portal_type="individual",
        domain="job",
        title="AI Engineer Job Session",
        filters={"scope": "Favourite Companies", "location": "Bangalore, India"},
    )

    skill_list = store.list_conversations(user_id="user_test_domain_iso", domain="skill")
    market_list = store.list_conversations(user_id="user_test_domain_iso", domain="market")
    job_list = store.list_conversations(user_id="user_test_domain_iso", domain="job")

    assert [c["conversation_id"] for c in skill_list] == [skill_conv.conversation_id]
    assert [c["conversation_id"] for c in market_list] == [market_conv.conversation_id]
    assert [c["conversation_id"] for c in job_list] == [job_conv.conversation_id]
    assert skill_list[0]["filters"]["scope"] == "All Skills"
    assert market_list[0]["filters"]["scope"] == "All Companies"
    assert job_list[0]["filters"]["scope"] == "Favourite Companies"


def test_domain_specific_scope_validation_and_empty_scope_handling() -> None:
    svc = ExecutionOrchestratorService()
    auth_user = AuthenticatedUser(uid="user_test_scope", email="user@example.com")

    # 1. Valid Skill scope ('My Skills') with empty profile skills reports limitation without fabricating skills
    skill_req = CoreIntelligenceAnswerRequest(
        message="How is Python demand changing?",
        portal_type="individual",
        domain="skill",
        selected_skills=["Python"],
        filters={"domain": "skill", "scope": "My Skills", "scope_empty": True},
    )
    enriched_skill = svc.answer(skill_req, authenticated_user=auth_user)
    assert enriched_skill.applied_filters.get("domain") == "skill"
    assert enriched_skill.applied_filters.get("scope") == "My Skills"
    assert any("0 saved items" in lim for lim in enriched_skill.limitations)

    # 2. Invalid cross-domain scope ('My Skills' sent to 'market' domain) is recorded in unapplied_filters
    market_req = CoreIntelligenceAnswerRequest(
        message="How is Python demand changing?",
        portal_type="individual",
        domain="market",
        selected_companies=["Microsoft"],
        filters={"domain": "market", "scope": "My Skills"},
    )
    enriched_market = svc.answer(market_req, authenticated_user=auth_user)
    assert enriched_market.applied_filters.get("domain") == "market"
    assert "scope" not in enriched_market.applied_filters
    assert any(u.get("filter") == "scope" and u.get("value") == "My Skills" for u in enriched_market.unapplied_filters)

    # 3. Valid Market/Job scopes ('All' and 'Favourites') are recorded in applied_filters
    job_req = CoreIntelligenceAnswerRequest(
        message="Find jobs for React",
        portal_type="individual",
        domain="job",
        target_role="Software Developers",
        selected_companies=["Google"],
        filters={"domain": "job", "scope": "Favourites"},
    )
    enriched_job = svc.answer(job_req, authenticated_user=auth_user)
    assert enriched_job.applied_filters.get("domain") == "job"
    assert enriched_job.applied_filters.get("scope") == "Favourites"
    assert enriched_job.applied_filters.get("selected_companies") == ["Google"]


def test_job_domain_favourites_scope_honestly_filters_by_saved_companies() -> None:
    svc = ExecutionOrchestratorService()
    auth_user = AuthenticatedUser(uid="user_test_job_favs", email="user@example.com")

    # When Favourites scope has a company with 0 matching postings in the store,
    # it must return 0 matching postings with insufficient_data rather than falling back to unrelated companies.
    req_unmatched_co = CoreIntelligenceAnswerRequest(
        message="Search stored job postings for Python",
        portal_type="individual",
        domain="job",
        selected_skills=["Python"],
        selected_companies=["NonExistentFavouriteCompanyXYZ"],
        filters={"domain": "job", "scope": "Favourites", "scope_empty": False},
    )
    res = svc.answer(req_unmatched_co, authenticated_user=auth_user)
    assert res.execution_status == "insufficient_data"
    assert "NonExistentFavouriteCompanyXYZ" in res.answer

    # When Favourites scope is empty (0 saved companies), it must also return insufficient_data honestly.
    req_empty_favs = CoreIntelligenceAnswerRequest(
        message="Search stored job postings for Python",
        portal_type="individual",
        domain="job",
        selected_skills=["Python"],
        selected_companies=[],
        filters={"domain": "job", "scope": "Favourites", "scope_empty": True},
    )
    res_empty = svc.answer(req_empty_favs, authenticated_user=auth_user)
    assert res_empty.execution_status == "insufficient_data"
    assert any("0 saved items" in lim or "0 saved favourite companies" in lim for lim in res_empty.limitations)


def test_home_to_assistant_conversation_continuity_reuses_conversation_id() -> None:
    svc = ExecutionOrchestratorService()
    auth_user = AuthenticatedUser(uid="user_test_continuity", email="user@example.com")

    # Turn 1 on Home creates a skill domain conversation
    home_req = CoreIntelligenceAnswerRequest(
        message="What is the demand trend for Python?",
        portal_type="individual",
        domain="skill",
        selected_skills=["Python"],
        filters={"domain": "skill", "scope": "All Skills"},
    )
    home_res = svc.answer(home_req, authenticated_user=auth_user)
    conv_id = home_res.conversation_id
    assert conv_id is not None

    # Turn 2 in Dedicated AI Assistant reuses the exact same conversation_id
    assistant_req = CoreIntelligenceAnswerRequest(
        message="What software tools are required for Software Developers?",
        portal_type="individual",
        domain="skill",
        conversation_id=conv_id,
        selected_skills=["Python"],
        filters={"domain": "skill", "scope": "All Skills"},
    )
    assistant_res = svc.answer(assistant_req, authenticated_user=auth_user)
    assert assistant_res.conversation_id == conv_id


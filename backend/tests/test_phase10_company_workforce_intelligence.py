from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.auth import AuthenticatedUser
from app.models.capability_registry import CapabilityEvaluationRequest
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService
from app.storage.company_workforce_store import (
    CompanyWorkforceStoreUnavailable,
    FirestoreCompanyWorkforceStore,
)


class FakeSnapshot:
    def __init__(self, data):
        self.data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class FakeDocument:
    def __init__(self, database, path):
        self.database = database
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def get(self):
        return FakeSnapshot(self.database.documents.get(self.path))

    def collection(self, name):
        return FakeCollection(self.database, f"{self.path}/{name}")


class FakeMemberRecord:
    def __init__(self, uid, data):
        self.id = uid
        self.data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class FakeCollection:
    def __init__(self, database, path):
        self.database = database
        self.path = path
        self.filters = []
        self.limit_count = None

    def document(self, document_id):
        return FakeDocument(self.database, f"{self.path}/{document_id}")

    def where(self, field, operator, value):
        assert operator == "=="
        self.filters.append((field, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def stream(self):
        prefix = f"{self.path}/"
        rows = []
        for path, data in self.database.documents.items():
            if not path.startswith(prefix) or "/" in path[len(prefix):]:
                continue
            if all(data.get(field) == value for field, value in self.filters):
                rows.append(FakeMemberRecord(path.rsplit("/", 1)[-1], data))
        return rows[:self.limit_count]


class FakeFirestore:
    def __init__(self, documents):
        self.documents = deepcopy(documents)

    def collection(self, name):
        return FakeCollection(self, name)


def _firestore_documents():
    return {
        "companies/acme": {
            "status": "active",
            "owner_uid": "owner",
            "company_name": "Acme",
        },
        "users/owner": {
            "user_type": "company",
            "company_id": "acme",
            "profile": {
                "company": {
                    "critical_skill_domains": ["Python", "Cloud Security"],
                },
            },
        },
        "companies/acme/members/employee-a": {
            "uid": "employee-a",
            "status": "connected",
        },
        "companies/acme/members/employee-b": {
            "uid": "employee-b",
            "status": "connected",
        },
        "companies/acme/members/employee-stale": {
            "uid": "employee-stale",
            "status": "connected",
        },
        "companies/acme/members/employee-disconnected": {
            "uid": "employee-disconnected",
            "status": "disconnected",
        },
        "users/employee-a": {
            "user_type": "employee",
            "company_id": "acme",
            "company_connection": {"status": "connected", "company_id": "acme"},
            "profile": {
                "employee": {
                    "current_skill_domains": ["Python", "python", "SQL"],
                    "self_reported_skill_confidence": {"Python": "comfortable"},
                    "current_role_id": "role-backend",
                },
            },
        },
        "users/employee-b": {
            "user_type": "employee",
            "company_id": "acme",
            "company_connection": {"status": "connected", "company_id": "acme"},
            "profile": {"employee": {"current_skill_domains": []}},
        },
        "users/employee-stale": {
            "user_type": "employee",
            "company_id": "acme",
            "company_connection": {"status": "disconnected", "company_id": "acme"},
            "profile": {"employee": {"current_skill_domains": ["Secret Skill"]}},
        },
        "companies/other": {
            "status": "active",
            "owner_uid": "other-owner",
            "company_name": "Other",
        },
    }


class FakeWorkforceStore:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.calls = []

    def get_company_workforce(self, *, company_id, expected_owner_uid):
        self.calls.append((company_id, expected_owner_uid))
        if self.snapshot is None:
            raise AssertionError("Workforce store must not be queried")
        return self.snapshot


def _service(store):
    return ExecutionOrchestratorService(
        settings=Settings(
            _env_file=None,
            skill_intelligence_read_backend="sqlite",
        ),
        workforce_store=store,
    )


def _owner(company_id="acme", uid="owner"):
    return AuthenticatedUser(
        uid=uid,
        company_id=company_id,
        role="company_admin",
    )


@pytest.mark.parametrize(
    "message",
    [
        "Show my company's current skill coverage",
        "Which skills are missing from our workforce records?",
        "Summarize the skills represented across our employees",
        "Which workforce skills may need further investigation?",
        "Show our company workforce skill inventory",
    ],
)
def test_company_workforce_queries_route_to_shared_capability(message):
    plan = IntentPlannerService().create_plan(
        IntelligencePlanRequest(message=message, portal_type="company")
    )

    assert plan.intent == "analyze_company_workforce"
    assert "company_intelligence" in plan.selected_capabilities


def test_capability_readiness_restricts_company_aggregate_to_company_portal():
    service = CapabilityRegistryService()
    result = service.evaluate(CapabilityEvaluationRequest(
        capability_id="company_intelligence",
        portal_type="employee",
        context_override={"company_id": "acme"},
    )).results[0]

    assert result.can_execute is False
    assert result.runtime_status == "insufficient_data"
    assert "COMPANY_ADMIN_PORTAL_REQUIRED" in result.reason_codes


def test_workforce_store_aggregates_only_double_verified_connected_profiles():
    database = FakeFirestore(_firestore_documents())
    store = FirestoreCompanyWorkforceStore(database)

    snapshot = store.get_company_workforce(
        company_id="acme",
        expected_owner_uid="owner",
    )

    assert snapshot.company_name == "Acme"
    assert snapshot.active_employee_count == 2
    assert snapshot.member_profiles_with_skills == 1
    assert snapshot.member_profiles_without_skills == 1
    assert snapshot.unverified_membership_count == 1
    assert snapshot.member_profiles_with_self_reported_confidence == 1
    assert snapshot.member_profiles_with_current_role == 1
    assert snapshot.skill_employee_counts == {"id:python": 1, "id:sql": 1}
    assert snapshot.declared_priority_skills == ["Cloud Security", "Python"]
    assert snapshot.truncated is False


def test_workforce_store_rejects_inactive_company_or_mismatched_owner():
    database = FakeFirestore(_firestore_documents())
    store = FirestoreCompanyWorkforceStore(database)

    with pytest.raises(CompanyWorkforceStoreUnavailable):
        store.get_company_workforce(
            company_id="acme",
            expected_owner_uid="unrelated-owner",
        )

    database.documents["companies/acme"]["status"] = "inactive"
    with pytest.raises(CompanyWorkforceStoreUnavailable):
        store.get_company_workforce(
            company_id="acme",
            expected_owner_uid="owner",
        )


def test_company_answer_reports_recorded_coverage_without_inference():
    snapshot = FirestoreCompanyWorkforceStore(
        FakeFirestore(_firestore_documents())
    ).get_company_workforce(company_id="acme", expected_owner_uid="owner")
    workforce_store = FakeWorkforceStore(snapshot)
    service = _service(workforce_store)
    service.llm_service.is_available = lambda: False

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Show my company's current skill coverage",
            portal_type="company",
            company_id="acme",
            context_override={
                "workforce_skill_inventory": ["Fabricated Skill"],
                "_authorized_company_owner_uid": "attacker",
            },
        ),
        authenticated_user=_owner(),
    )

    coverage = [
        fact for fact in response.facts
        if fact.fact_type == "company_skill_coverage"
    ]
    summary = next(
        fact for fact in response.facts
        if fact.fact_type == "company_workforce_summary"
    )
    absent_priorities = [
        fact for fact in response.facts
        if fact.fact_type == "company_declared_priority_skill"
        and fact.metric_value == "not_represented"
    ]
    assert response.execution_status == "completed"
    assert response.status == "ready"
    assert workforce_store.calls == [("acme", "owner")]
    assert {fact.entity_name for fact in coverage} == {"Python", "SQL"}
    assert all(fact.details["self_reported"] for fact in coverage)
    assert all(not fact.details["proficiency_inferred"] for fact in coverage)
    assert len(absent_priorities) == 1
    assert absent_priorities[0].entity_name == "Cloud Security"
    assert summary.details["members_without_self_reported_skill_records"] == 1
    assert summary.details["unverified_or_stale_membership_records_excluded"] == 1
    assert "not a measure of organizational competence" in response.answer
    assert "not proof of an organizational skill gap" in response.answer
    assert "Fabricated Skill" not in response.answer
    assert "Secret Skill" not in response.answer
    assert "employee-a" not in response.answer
    assert all(fact.evidence_reference for fact in response.facts)
    evidence_ids = {item.evidence_id for item in response.evidence}
    assert all(fact.evidence_reference in evidence_ids for fact in response.facts)
    assert not any(
        item.source == "ref_onet_software_skills" for item in response.evidence
    )


def test_missing_workforce_skill_records_return_insufficient_data():
    snapshot = SimpleNamespace(
        company_id="acme",
        company_name="Acme",
        active_employee_count=2,
        member_profiles_with_skills=0,
        member_profiles_without_skills=2,
        unverified_membership_count=0,
        member_profiles_with_self_reported_confidence=0,
        member_profiles_with_current_role=0,
        skill_employee_counts={},
        skill_labels={},
        declared_priority_skills=[],
        truncated=False,
    )
    service = _service(FakeWorkforceStore(snapshot))
    service.llm_service.is_available = lambda: False

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Summarize the skills represented across our employees",
            portal_type="company",
            company_id="acme",
        ),
        authenticated_user=_owner(),
    )

    assert response.execution_status == "insufficient_data"
    assert response.status == "insufficient_data"
    assert response.reason_codes == ["NO_EMPLOYEE_SKILL_RECORDS"]
    assert not any(fact.fact_type == "company_skill_coverage" for fact in response.facts)
    assert "none of the retrieved profiles contain" in response.answer


def test_employee_and_cross_company_requests_do_not_read_workforce_store():
    store = FakeWorkforceStore()
    service = _service(store)

    employee_response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Show our company workforce skill inventory",
            portal_type="employee",
            company_id="acme",
        ),
        authenticated_user=AuthenticatedUser(uid="employee", company_id="acme"),
    )
    cross_company_response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Show my company's current skill coverage",
            portal_type="company",
            company_id="other",
        ),
        authenticated_user=_owner(),
    )

    assert employee_response.execution_status == "blocked"
    assert "UNAUTHORIZED_COMPANY_WORKFORCE_ROLE" in employee_response.reason_codes
    assert cross_company_response.execution_status == "blocked"
    assert "UNAUTHORIZED_CROSS_COMPANY_ACCESS" in cross_company_response.reason_codes
    assert store.calls == []
    assert employee_response.facts == cross_company_response.facts == []


def test_company_evidence_follow_up_reuses_cited_records_and_is_user_isolated():
    snapshot = FirestoreCompanyWorkforceStore(
        FakeFirestore(_firestore_documents())
    ).get_company_workforce(company_id="acme", expected_owner_uid="owner")
    store = FakeWorkforceStore(snapshot)
    service = _service(store)
    service.llm_service.is_available = lambda: False
    user = _owner()
    first_response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Show my company's current skill coverage",
            portal_type="company",
            domain="skill",
            company_id="acme",
        ),
        authenticated_user=user,
    )
    follow_up = service.answer(
        CoreIntelligenceAnswerRequest(
            message="What evidence supports this workforce coverage?",
            portal_type="company",
            conversation_id=first_response.conversation_id,
        ),
        authenticated_user=user,
    )
    other_user = service.answer(
        CoreIntelligenceAnswerRequest(
            message="What evidence supports this workforce coverage?",
            portal_type="company",
            conversation_id=first_response.conversation_id,
        ),
        authenticated_user=_owner(uid="another-owner"),
    )

    assert follow_up.execution_status == "completed"
    assert "PRIOR_WORKFORCE_EVIDENCE_RETRIEVED" in follow_up.reason_codes
    assert follow_up.evidence
    assert all(
        fact.evidence_reference in {item.evidence_id for item in follow_up.evidence}
        for fact in follow_up.facts
    )
    assert "self-reported skill coverage only" in follow_up.answer
    assert other_user.execution_status == "blocked"
    assert "UNAUTHORIZED_CONVERSATION_ACCESS" in other_user.reason_codes
    assert store.calls == [("acme", "owner")]


def test_simulation_remains_unavailable_without_inputs_or_engine():
    service = _service(FakeWorkforceStore())

    response = service.answer(
        CoreIntelligenceAnswerRequest(
            message="Simulate a reskilling scenario for our workforce",
            portal_type="company",
            company_id="acme",
        ),
        authenticated_user=_owner(),
    )

    assert response.execution_status == "unsupported"
    assert "CAPABILITY_UNSUPPORTED_IN_G2_6" in response.reason_codes
    assert "SIMULATION_PREREQUISITES_NOT_MET" in response.reason_codes
    assert response.facts == []
    assert response.evidence == []
    assert "no approved simulation engine" in response.answer.lower()
    assert "verified workforce baseline" in " ".join(response.limitations).lower()

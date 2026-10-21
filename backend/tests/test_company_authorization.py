from copy import deepcopy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from firebase_admin import auth
from google.api_core.exceptions import ServiceUnavailable

from app.api import dependencies
from app.api.routes import core_intelligence
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.core_intelligence import CoreIntelligenceRequest


class Snapshot:
    def __init__(self, data):
        self.data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class Document:
    def __init__(self, database, path):
        self.database = database
        self.path = path

    def get(self):
        return Snapshot(self.database.documents.get(self.path))

    def collection(self, name):
        return Collection(self.database, f"{self.path}/{name}")


class Collection:
    def __init__(self, database, path):
        self.database = database
        self.path = path

    def document(self, document_id):
        return Document(self.database, f"{self.path}/{document_id}")


class FakeFirestore:
    def __init__(self, documents):
        self.documents = deepcopy(documents)

    def collection(self, name):
        return Collection(self, name)


@pytest.fixture(autouse=True)
def isolate_application_dependency_overrides():
    """Prevent overrides leaked by other modules from bypassing real auth dependencies."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def firestore(monkeypatch):
    database = FakeFirestore({
        "users/individual": {"user_type": "individual", "company_name": "Unverified Corp"},
        "users/owner-a": {"user_type": "company", "company_id": "company-a"},
        "companies/company-a": {
            "status": "active",
            "owner_uid": "owner-a",
        },
        "users/employee-a": {
            "user_type": "employee",
            "company_id": "company-a",
            "company_connection": {"status": "connected", "company_id": "company-a"},
        },
        "companies/company-a/members/employee-a": {
            "uid": "employee-a",
            "status": "connected",
            "role": "Engineer",
        },
        "users/owner-b": {"user_type": "company", "company_id": "company-b"},
        "companies/company-b": {
            "status": "active",
            "owner_uid": "owner-b",
        },
    })
    monkeypatch.setattr(dependencies, "get_firestore_client", lambda: database)
    return database


def test_verified_individual_cannot_use_unverified_company_profile(firestore):
    user = AuthenticatedUser(
        uid="individual",
        company_id="company-a",
        role="admin",
    )
    request = CoreIntelligenceRequest(portal_type="company")

    with pytest.raises(HTTPException) as error:
        core_intelligence._authorized_company_context(request, user)

    assert error.value.status_code == 403


def test_company_owner_membership_is_resolved_from_firestore_not_token_claims(firestore):
    user = AuthenticatedUser(uid="owner-a")
    request = CoreIntelligenceRequest(portal_type="company")

    authorized_request, authorized_user = core_intelligence._authorized_company_context(request, user)

    assert authorized_request.company_id == "company-a"
    assert authorized_user.company_id == "company-a"
    assert authorized_user.role == "company_admin"


def test_company_request_without_membership_is_denied(firestore):
    user = AuthenticatedUser(uid="user-without-company")
    request = CoreIntelligenceRequest(portal_type="company")

    with pytest.raises(HTTPException) as error:
        core_intelligence._authorized_company_context(request, user)

    assert error.value.status_code == 403


def test_approved_employee_can_use_only_its_connected_company_context(firestore):
    user = AuthenticatedUser(uid="employee-a", role="admin")
    request = CoreIntelligenceRequest(portal_type="employee")

    authorized_request, authorized_user = core_intelligence._authorized_company_context(request, user)

    assert authorized_request.company_id == "company-a"
    assert authorized_user.company_id == "company-a"
    assert authorized_user.role is None

    with pytest.raises(HTTPException) as error:
        core_intelligence._authorized_company_context(
            CoreIntelligenceRequest(portal_type="company"),
            user,
        )
    assert error.value.status_code == 403


def test_company_id_and_role_spoofing_do_not_authorize_another_tenant(firestore):
    user = AuthenticatedUser(uid="owner-a")
    request = CoreIntelligenceRequest.model_validate({
        "portal_type": "company",
        "company_id": "company-b",
        "role": "admin",
    })

    with pytest.raises(HTTPException) as error:
        core_intelligence._authorized_company_context(request, user)

    assert error.value.status_code == 403


def test_membership_store_outage_returns_service_unavailable(monkeypatch):
    def unavailable():
        raise ServiceUnavailable("membership store unavailable")

    monkeypatch.setattr(dependencies, "get_firestore_client", unavailable)

    with pytest.raises(HTTPException) as error:
        dependencies.resolve_company_membership("owner-a")

    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/v1/intelligence/answer",
            {"message": "Analyze workforce trends", "portal_type": "company", "company_id": "company-a"},
        ),
        (
            "/api/v1/intelligence/core",
            {"portal_type": "company", "company_id": "company-a", "role": "admin"},
        ),
        (
            "/api/v1/intelligence/actions",
            {"portal_type": "company", "company_id": "company-a", "role": "admin"},
        ),
    ],
)
def test_firebase_identity_and_trusted_owner_membership_are_consistent_across_routes(
    firestore, monkeypatch, path, body,
):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda *_args, **_kwargs: {
            "uid": "owner-a",
            "company_id": "company-b",
            "role": "admin",
        },
    )
    captured = {}

    def stop_after_authorization(_self, request, authenticated_user=None, **kwargs):
        captured["request"] = request
        captured["user"] = authenticated_user or kwargs.get("authenticated_uid")
        captured.update(kwargs)
        raise HTTPException(status_code=418, detail="authorization verified")

    monkeypatch.setattr(
        core_intelligence.ExecutionOrchestratorService,
        "answer",
        stop_after_authorization,
    )
    monkeypatch.setattr(
        core_intelligence.CoreIntelligenceService,
        "get_intelligence",
        stop_after_authorization,
    )
    monkeypatch.setattr(
        core_intelligence.CoreIntelligenceService,
        "get_action_recommendations",
        stop_after_authorization,
    )

    with TestClient(app) as client:
        response = client.post(
            path,
            headers={"Authorization": "Bearer mocked-firebase-token"},
            json=body,
        )

    assert response.status_code == 418
    if isinstance(captured["user"], AuthenticatedUser):
        assert captured["user"].uid == "owner-a"
        assert captured["user"].company_id == "company-a"
        assert captured["user"].role == "company_admin"
    else:
        assert captured["user"] == "owner-a"
    assert captured["request"].company_id == "company-a"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/v1/intelligence/answer",
            {"message": "Analyze my company context", "portal_type": "employee", "company_id": "company-a"},
        ),
        (
            "/api/v1/intelligence/core",
            {"portal_type": "employee", "company_id": "company-a", "role": "admin"},
        ),
        (
            "/api/v1/intelligence/actions",
            {"portal_type": "employee", "company_id": "company-a", "role": "admin"},
        ),
    ],
)
def test_connected_employee_membership_is_consistent_across_routes(
    firestore, monkeypatch, path, body,
):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda *_args, **_kwargs: {
            "uid": "employee-a",
            "company_id": "company-b",
            "role": "admin",
        },
    )
    captured = {}

    def stop_after_authorization(_self, request, authenticated_user=None, **kwargs):
        captured["request"] = request
        captured["user"] = authenticated_user or kwargs.get("authenticated_uid")
        raise HTTPException(status_code=418, detail="authorization verified")

    monkeypatch.setattr(
        core_intelligence.ExecutionOrchestratorService,
        "answer",
        stop_after_authorization,
    )
    monkeypatch.setattr(
        core_intelligence.CoreIntelligenceService,
        "get_intelligence",
        stop_after_authorization,
    )
    monkeypatch.setattr(
        core_intelligence.CoreIntelligenceService,
        "get_action_recommendations",
        stop_after_authorization,
    )

    with TestClient(app) as client:
        response = client.post(
            path,
            headers={"Authorization": "Bearer mocked-firebase-token"},
            json=body,
        )

    assert response.status_code == 418
    assert captured["request"].company_id == "company-a"
    if isinstance(captured["user"], AuthenticatedUser):
        assert captured["user"].uid == "employee-a"
        assert captured["user"].company_id == "company-a"
        assert captured["user"].role is None
    else:
        assert captured["user"] == "employee-a"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/v1/intelligence/answer",
            {"message": "Analyze workforce trends", "portal_type": "company", "company_id": "company-b"},
        ),
        (
            "/api/v1/intelligence/core",
            {"portal_type": "company", "company_id": "company-b"},
        ),
        (
            "/api/v1/intelligence/actions",
            {"portal_type": "company", "company_id": "company-b"},
        ),
    ],
)
def test_company_id_spoof_is_denied_consistently_across_routes(
    firestore, monkeypatch, path, body,
):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda *_args, **_kwargs: {
            "uid": "owner-a",
            "company_id": "company-b",
            "role": "admin",
        },
    )

    with TestClient(app) as client:
        response = client.post(
            path,
            headers={"Authorization": "Bearer mocked-firebase-token"},
            json=body,
        )

    assert response.status_code == 403
    assert "company-b" not in response.text


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/v1/intelligence/answer",
            {"message": "Analyze company workforce", "portal_type": "company", "company_id": "company-a"},
        ),
        (
            "/api/v1/intelligence/core",
            {"portal_type": "company", "company_id": "company-a"},
        ),
        (
            "/api/v1/intelligence/actions",
            {"portal_type": "company", "company_id": "company-a"},
        ),
    ],
)
def test_membership_store_outage_fails_closed_across_routes(monkeypatch, path, body):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda *_args, **_kwargs: {"uid": "owner-a"},
    )

    def unavailable():
        raise ServiceUnavailable("private membership store details")

    monkeypatch.setattr(dependencies, "get_firestore_client", unavailable)
    with TestClient(app) as client:
        response = client.post(
            path,
            headers={"Authorization": "Bearer mocked-firebase-token"},
            json=body,
        )

    assert response.status_code == 503
    assert "private membership store details" not in response.text


@pytest.mark.parametrize(
    ("document_path", "field", "value"),
    [
        ("companies/company-a", "status", "inactive"),
        ("users/employee-a", "company_connection", {"status": "requesting", "company_id": "company-a"}),
        ("companies/company-a/members/employee-a", "status", "inactive"),
        ("users/employee-a", "company_id", "company-b"),
    ],
)
def test_inactive_or_ambiguous_employee_membership_is_denied(
    firestore, document_path, field, value,
):
    firestore.documents[document_path][field] = value

    with pytest.raises(HTTPException) as error:
        core_intelligence._authorized_company_context(
            CoreIntelligenceRequest(portal_type="employee"),
            AuthenticatedUser(uid="employee-a", role="admin", company_id="company-a"),
        )

    assert error.value.status_code == 403


@pytest.mark.parametrize("authorization", [None, "Basic not-a-token"])
def test_company_endpoint_rejects_missing_or_malformed_authentication(authorization, monkeypatch):
    headers = {"Authorization": authorization} if authorization else {}
    monkeypatch.setattr(
        dependencies,
        "get_firestore_client",
        lambda: pytest.fail("membership storage must not be read before authentication"),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/intelligence/core",
            headers=headers,
            json={"portal_type": "company"},
        )

    assert response.status_code == 401


def test_company_endpoint_rejects_invalid_firebase_token(monkeypatch):
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, **kwargs: (_ for _ in ()).throw(auth.InvalidIdTokenError("invalid token")),
    )
    monkeypatch.setattr(
        dependencies,
        "get_firestore_client",
        lambda: pytest.fail("membership storage must not be read for an invalid token"),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/intelligence/core",
            headers={"Authorization": "Bearer invalid-token"},
            json={"portal_type": "company"},
        )

    assert response.status_code == 401

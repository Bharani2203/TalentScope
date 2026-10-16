from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser
from app.services import company_relationship_service as relationships


class Snapshot:
    def __init__(self, data):
        self.data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class Ref:
    def __init__(self, db, path):
        self.db, self.path, self.id = db, path, path.rsplit("/", 1)[-1]

    def get(self, transaction=None):
        return Snapshot(self.db.documents.get(self.path))

    def set(self, value, merge=False):
        current = deepcopy(self.db.documents.get(self.path, {})) if merge else {}
        current.update(deepcopy(value))
        self.db.documents[self.path] = current

    def create(self, value):
        if self.path in self.db.documents:
            raise ValueError("already exists")
        self.db.documents[self.path] = deepcopy(value)

    def update(self, value):
        self.db.documents.setdefault(self.path, {}).update(deepcopy(value))

    def collection(self, name):
        return Collection(self.db, f"{self.path}/{name}")


class Collection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, document_id=None):
        if document_id is None:
            document_id = f"generated-{len(self.db.documents) + 1}"
        return Ref(self.db, f"{self.path}/{document_id}")

    def where(self, field, operator, value):
        self.filters = getattr(self, "filters", []) + [(field, operator, value)]
        return self

    def limit(self, count):
        self.row_limit = count
        return self

    def stream(self):
        prefix = f"{self.path}/"
        rows = []
        for path, data in self.db.documents.items():
            if not path.startswith(prefix) or "/" in path[len(prefix):]:
                continue
            if any(operator == "==" and data.get(field) != expected
                   for field, operator, expected in getattr(self, "filters", [])):
                continue
            rows.append(type("Row", (), {"id": path.rsplit("/", 1)[-1], "to_dict": lambda self, data=data: deepcopy(data)})())
        return rows[:getattr(self, "row_limit", len(rows))]


class Transaction:
    def update(self, ref, value):
        ref.update(value)

    def set(self, ref, value, merge=False):
        ref.set(value, merge=merge)


class Database:
    def __init__(self, documents):
        self.documents = deepcopy(documents)

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction()


@pytest.fixture
def setup_db(monkeypatch):
    db = Database({
        "users/employee": {"user_type": "employee", "email": "e@example.com"},
        "users/admin-a": {"user_type": "company", "company_id": "company-a"},
        "users/admin-b": {"user_type": "company", "company_id": "company-b"},
        "companies/company-a": {"status": "active", "owner_uid": "admin-a"},
        "companies/company-b": {"status": "active", "owner_uid": "admin-b"},
    })
    monkeypatch.setattr(relationships, "get_firestore_client", lambda: db)
    monkeypatch.setattr(relationships.firestore, "transactional", lambda fn: (lambda tx: fn(tx)))
    return db


def user(uid, email=None):
    return AuthenticatedUser(uid=uid, email=email, email_verified=True)


def test_employee_request_is_persisted_and_repeated_request_is_idempotent(setup_db):
    first = relationships.request_company_connection(user("employee", "e@example.com"), "company-a")
    request = setup_db.documents["companies/company-a/connection_requests/employee"]
    first_created = request["created_at"]
    second = relationships.request_company_connection(user("employee", "e@example.com"), "company-a")
    assert first == second == {"status": "requesting", "company_id": "company-a", "request_status": "pending"}
    assert request["created_at"] == first_created
    assert setup_db.documents["users/employee"]["company_connection"]["status"] == "requesting"


def test_company_owner_approval_links_employee_and_is_idempotent(setup_db):
    relationships.request_company_connection(user("employee", "e@example.com"), "company-a")
    result = relationships.review_company_connection(user("admin-a"), "employee", "approve")
    repeated = relationships.review_company_connection(user("admin-a"), "employee", "approve")
    employee = setup_db.documents["users/employee"]
    assert result.status == repeated.status == "approved"
    assert result.reviewed_by == "admin-a"
    assert employee["company_id"] == "company-a"
    assert employee["company_connection"]["status"] == "connected"
    assert setup_db.documents["companies/company-a/members/employee"]["status"] == "connected"


def test_decline_leaves_employee_independent_and_other_company_cannot_review(setup_db):
    relationships.request_company_connection(user("employee", "e@example.com"), "company-a")
    with pytest.raises(HTTPException) as error:
        relationships.review_company_connection(user("admin-b"), "employee", "approve")
    assert error.value.status_code == 404
    result = relationships.review_company_connection(user("admin-a"), "employee", "decline")
    assert result.status == "declined"
    assert setup_db.documents["users/employee"]["company_id"] is None
    assert setup_db.documents["users/employee"]["company_connection"]["status"] == "independent"


def test_employee_cannot_review_own_request(setup_db):
    with pytest.raises(HTTPException) as error:
        relationships.review_company_connection(user("employee"), "employee", "approve")
    assert error.value.status_code == 403


def test_pending_requests_are_only_listed_for_verified_company_owner(setup_db):
    relationships.request_company_connection(user("employee", "e@example.com"), "company-a")
    rows = relationships.list_pending_connection_requests(user("admin-a"))
    assert rows == [{
        "employee_uid": "employee", "company_id": "company-a", "email": "e@example.com",
        "status": "pending", "created_at": rows[0]["created_at"],
    }]
    assert relationships.list_pending_connection_requests(user("admin-b")) == []


def test_company_search_returns_only_active_matching_profiles(setup_db):
    setup_db.documents["users/employee"]["user_type"] = "employee"
    setup_db.documents["companies/company-a"]["company_name"] = "Acme Systems"
    setup_db.documents["companies/company-b"]["company_name"] = "Other Company"
    rows = relationships.search_companies(user("employee"), "acme")
    assert [row["company_id"] for row in rows] == ["company-a"]


def test_owner_creates_persisted_invitation_and_rejects_duplicate(setup_db):
    from app.models.company import CompanyInvitationCreate

    request = CompanyInvitationCreate(email=" New.Employee@Example.com ", role="Engineer", team="Data")
    result = relationships.create_invitation(user("admin-a"), request)
    record = setup_db.documents[f"company_invitations/{result['invitation_id']}"]
    assert record["intended_email"] == "new.employee@example.com"
    assert record["company_id"] == "company-a"
    assert record["status"] == "invited"
    assert record["token_hash"] and record["token_hash"] != result["token"]
    with pytest.raises(HTTPException) as error:
        relationships.create_invitation(user("admin-a"), request)
    assert error.value.status_code == 409


def test_invitation_rejects_invalid_email_and_connected_employee(setup_db):
    from app.models.company import CompanyInvitationCreate

    with pytest.raises(HTTPException) as error:
        relationships.create_invitation(user("admin-a"), CompanyInvitationCreate(email="not-an-email"))
    assert error.value.status_code == 422
    setup_db.documents["users/employee"]["company_id"] = "company-a"
    with pytest.raises(HTTPException) as connected_error:
        relationships.create_invitation(user("admin-a"), CompanyInvitationCreate(email="e@example.com"))
    assert connected_error.value.status_code == 409


def test_non_owner_cannot_create_invitation(setup_db):
    from app.models.company import CompanyInvitationCreate

    setup_db.documents["companies/company-b"]["owner_uid"] = "different-user"
    with pytest.raises(HTTPException) as error:
        relationships.create_invitation(user("admin-b"), CompanyInvitationCreate(email="new@example.com"))
    assert error.value.status_code == 403


def test_expired_invitation_cannot_be_accepted(setup_db):
    import hashlib

    token = "expired-invitation-token-value"
    setup_db.documents["company_invitations/inv-expired"] = {
        "invitation_id": "inv-expired", "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "company_id": "company-a", "intended_email": "e@example.com", "status": "invited",
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    with pytest.raises(HTTPException) as error:
        relationships.change_invitation(user("employee", "e@example.com"), token, accept=True)
    assert error.value.status_code == 410
    assert "company_id" not in setup_db.documents["users/employee"]


def test_valid_invitation_acceptance_persists_company_membership(setup_db):
    import hashlib

    token = "valid-invitation-token-value"
    setup_db.documents["company_invitations/inv-valid"] = {
        "invitation_id": "inv-valid", "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "company_id": "company-a", "intended_email": "e@example.com", "status": "invited",
        "role": "Engineer", "team": "Data",
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }
    result = relationships.change_invitation(user("employee", "e@example.com"), token, accept=True)
    assert result == {"status": "accepted", "company_id": "company-a"}
    assert setup_db.documents["users/employee"]["company_id"] == "company-a"
    assert setup_db.documents["companies/company-a/members/employee"]["status"] == "connected"


def test_employee_cannot_request_arbitrary_unregistered_company(setup_db):
    with pytest.raises(HTTPException) as error:
        relationships.request_company_connection(user("employee", "e@example.com"), "invented-company")
    assert error.value.status_code == 403
    assert "company_id" not in setup_db.documents["users/employee"]


def test_company_invitation_listing_is_owner_scoped_and_never_returns_tokens(setup_db, monkeypatch):
    from app.api.routes import company_relationships

    setup_db.documents.update({
        "company_invitations/inv-a": {
            "invitation_id": "inv-a", "company_id": "company-a", "intended_email": "a@example.com",
            "status": "invited", "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=4), "token_hash": "hash-a",
        },
        "company_invitations/inv-b": {
            "invitation_id": "inv-b", "company_id": "company-b", "intended_email": "b@example.com",
            "status": "accepted", "token_hash": "hash-b",
        },
    })
    app.dependency_overrides[get_current_user] = lambda: user("admin-a")
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/company-relationships/invitations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 1
    row = response.json()[0]
    assert row["invitation_id"] == "inv-a"
    assert row["company_id"] == "company-a"
    assert row["intended_email"] == "a@example.com"
    assert "token" not in row and "token_hash" not in row


def test_company_invitation_listing_rejects_non_owner(setup_db):
    with pytest.raises(HTTPException) as error:
        relationships.list_company_invitations(user("employee"))
    assert error.value.status_code == 403

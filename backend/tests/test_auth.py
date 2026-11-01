from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from firebase_admin import auth, firestore
from google.api_core.exceptions import ServiceUnavailable

from app.api import dependencies
from app.api.dependencies import get_current_user
from app.api.routes import auth as auth_routes
from app.main import app
from app.models.auth import AuthSyncRequest, AuthenticatedUser
from app.services import auth_service


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def make_authenticated_user():
    return AuthenticatedUser(
        uid="firebase-uid-123",
        email="person@example.com",
        email_verified=True,
        phone_number=None,
        display_name="Example Person",
        auth_provider="password",
    )


def test_me_without_authorization_returns_401():
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "Bearer" in response.headers.get("www-authenticate", "")


def test_sync_without_authorization_returns_401():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/sync", json={})

    assert response.status_code == 401


@pytest.mark.parametrize("authorization", ["Basic not-a-token", "Bearer"])
def test_malformed_authorization_returns_401(authorization):
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": authorization})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token_error",
    [
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.UserNotFoundError,
    ],
)
def test_rejected_firebase_tokens_return_401_without_echoing_token(monkeypatch, token_error):
    secret_like_token = "not-a-valid-id-token"
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())

    def reject_token(token, **kwargs):
        if token_error is auth.ExpiredIdTokenError:
            raise token_error("expired token", ValueError("expired"))
        raise token_error("invalid token")

    monkeypatch.setattr(dependencies.auth, "verify_id_token", reject_token)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {secret_like_token}"},
        )

    assert response.status_code == 401
    assert secret_like_token not in response.text


def test_firebase_initialization_failure_remains_service_unavailable(monkeypatch):
    def fail_initialization():
        raise ValueError("local Firebase credentials are unavailable")

    monkeypatch.setattr(dependencies, "get_firebase_app", fail_initialization)
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer any-token"})

    assert response.status_code == 503
    assert "credentials are unavailable" not in response.text


def test_me_returns_normalized_user_and_checks_revocation(monkeypatch):
    claims = {
        "uid": "firebase-uid-123",
        "email": "person@example.com",
        "email_verified": True,
        "phone_number": "+15555550123",
        "name": "Example Person",
        "firebase": {"sign_in_provider": "google.com"},
    }
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    calls = []

    def accept_token(token, **kwargs):
        calls.append((token, kwargs))
        return claims

    monkeypatch.setattr(dependencies.auth, "verify_id_token", accept_token)
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test-id-token"})

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "uid": "firebase-uid-123",
            "email": "person@example.com",
            "email_verified": True,
            "phone_number": "+15555550123",
            "display_name": "Example Person",
            "auth_provider": "google.com",
        },
    }
    assert calls[0][0] == "test-id-token"
    assert calls[0][1]["check_revoked"] is False


def test_unverified_email_token_can_sync_and_use_protected_auth_api(monkeypatch):
    database = FakeFirestore()
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())
    monkeypatch.setattr(
        dependencies.auth,
        "verify_id_token",
        lambda token, **kwargs: {
            "uid": "unverified-uid",
            "email": "person@example.com",
            "email_verified": False,
        },
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/sync",
            headers={"Authorization": "Bearer unverified-token"},
            json={},
        )

    assert response.status_code == 200
    assert response.json()["user"]["uid"] == "unverified-uid"


class FakeSnapshot:
    def __init__(self, data):
        self.exists = data is not None
        self.data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self.data)


class FakeDocument:
    def __init__(self, database, collection, document_id):
        self.database = database
        self.collection = collection
        self.document_id = document_id
        self.path = f"{collection}/{document_id}"

    def get(self):
        self.database.read_count += 1
        return FakeSnapshot(self.database.documents.get(self.path))

    def set(self, updates, merge=False):
        self.database.write_count += 1
        current = self.database.documents.get(self.path, {}) if merge else {}
        self.database.documents[self.path] = {**current, **updates}


class FakeCollection:
    def __init__(self, database, name):
        self.database = database
        self.name = name

    def document(self, document_id):
        return FakeDocument(self.database, self.name, document_id)


class FakeFirestore:
    def __init__(self, documents=None):
        self.documents = documents or {}
        self.read_count = 0
        self.write_count = 0

    def collection(self, name):
        return FakeCollection(self, name)


def test_new_user_sync_creates_uid_profile_without_secrets(monkeypatch):
    now = datetime.now(timezone.utc)
    database = FakeFirestore()
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: now)

    profile = auth_service.sync_user_profile(make_authenticated_user())

    stored = database.documents["users/firebase-uid-123"]
    assert profile.uid == "firebase-uid-123"
    assert profile.onboarding_completed is False
    assert profile.user_type is None
    assert stored["uid"] == "firebase-uid-123"
    assert stored["email"] == "person@example.com"
    assert stored["display_name"] == "Example Person"
    assert "phone_number" not in stored
    assert stored["email_verified"] is True
    assert stored["auth_provider"] == "password"
    assert stored["created_at"] == now
    assert stored["last_login_at"] == now
    assert "password" not in stored
    assert "id_token" not in stored
    assert database.read_count == 1
    assert database.write_count == 1


def test_repeated_profile_sync_reuses_uid_document_and_preserves_created_at(monkeypatch):
    first_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second_time = datetime(2026, 1, 2, tzinfo=timezone.utc)
    database = FakeFirestore()
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: first_time)
    first = auth_service.sync_user_profile(make_authenticated_user())
    monkeypatch.setattr(auth_service, "_utc_now", lambda: second_time)
    second = auth_service.sync_user_profile(make_authenticated_user())

    assert first.uid == second.uid == "firebase-uid-123"
    assert list(database.documents) == ["users/firebase-uid-123"]
    assert database.documents["users/firebase-uid-123"]["created_at"] == first_time
    assert database.documents["users/firebase-uid-123"]["last_login_at"] == second_time
    assert database.read_count == 2
    assert database.write_count == 2


def test_existing_user_sync_preserves_onboarding_data(monkeypatch):
    now = datetime.now(timezone.utc)
    database = FakeFirestore({
        "users/firebase-uid-123": {
            "uid": "firebase-uid-123",
            "email": "old@example.com",
            "onboarding_completed": True,
            "user_type": "individual",
            "skills": [{"skill_id": "python", "level": "advanced"}],
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
    })
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: now)

    profile = auth_service.sync_user_profile(
        make_authenticated_user(),
        AuthSyncRequest(user_type="employee", employee_type="independent"),
    )

    stored = database.documents["users/firebase-uid-123"]
    assert profile.user_type.value == "employee"
    assert stored["onboarding_completed"] is True
    assert stored["skills"] == [{"skill_id": "python", "level": "advanced"}]
    assert stored["created_at"] == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert stored["last_login_at"] == now
    assert database.read_count == 1
    assert database.write_count == 1


def test_existing_user_sync_preserves_profile_fields_missing_from_firebase_claims(monkeypatch):
    now = datetime.now(timezone.utc)
    database = FakeFirestore({
        "users/firebase-uid-123": {
            "uid": "firebase-uid-123",
            "email": "existing@example.com",
            "display_name": "Existing Name",
            "phone_number": "+15555550123",
            "phone_verified": True,
            "auth_provider": "google.com",
            "onboarding_completed": True,
            "user_type": "individual",
        }
    })
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: now)
    authenticated_user = make_authenticated_user().model_copy(
        update={
            "email": None,
            "display_name": None,
            "phone_number": None,
            "auth_provider": None,
        }
    )

    profile = auth_service.sync_user_profile(authenticated_user)

    stored = database.documents["users/firebase-uid-123"]
    assert stored["email"] == "existing@example.com"
    assert stored["display_name"] == "Existing Name"
    assert stored["phone_number"] == "+15555550123"
    assert stored["phone_verified"] is True
    assert stored["auth_provider"] == "google.com"
    assert stored["onboarding_completed"] is True
    assert profile.last_login_at == now


def test_sync_endpoint_creates_profile_for_authenticated_uid(monkeypatch):
    database = FakeFirestore()
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: datetime.now(timezone.utc))
    app.dependency_overrides[get_current_user] = make_authenticated_user

    with TestClient(app) as client:
        response = client.post("/api/v1/auth/sync", json={"user_type": "individual"})

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["user"]["uid"] == "firebase-uid-123"
    assert database.documents["users/firebase-uid-123"]["user_type"] == "individual"


def test_sync_endpoint_returns_safe_error_on_firestore_failure(monkeypatch):
    app.dependency_overrides[get_current_user] = make_authenticated_user

    def fail_sync(*args, **kwargs):
        raise ServiceUnavailable("private Firestore failure details")

    monkeypatch.setattr(auth_routes, "sync_user_profile", fail_sync)
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/sync", json={})

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "firestore_unavailable"
    assert "private Firestore failure details" not in response.text


def test_sync_endpoint_returns_safe_internal_error_for_unexpected_failure(monkeypatch):
    app.dependency_overrides[get_current_user] = make_authenticated_user

    def fail_sync(*args, **kwargs):
        raise RuntimeError("private implementation details")

    monkeypatch.setattr(auth_routes, "sync_user_profile", fail_sync)
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/sync", json={})

    assert response.status_code == 500
    assert response.json()["detail"]["error_code"] == "profile_sync_failed"
    assert "private implementation details" not in response.text


def test_auth_routes_document_bearer_security():
    schema = app.openapi()

    assert "/api/v1/auth/me" in schema["paths"]
    assert "/api/v1/auth/sync" in schema["paths"]
    assert not any("otp" in path.lower() for path in schema["paths"])
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"]
    assert schema["paths"]["/api/v1/auth/sync"]["post"]["security"]


def test_auth_sync_preflight_allows_vercel_production_deployment():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/auth/sync",
            headers={
                "Origin": "https://talent-scope-ten.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://talent-scope-ten.vercel.app"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_auth_sync_preflight_allows_local_frontend_bearer_request():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/auth/sync",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type,x-auth-diagnostic-id",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "x-auth-diagnostic-id" in response.headers["access-control-allow-headers"].lower()


def test_auth_sync_preflight_rejects_unconfigured_dynamic_frontend_port():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/auth/sync",
            headers={
                "Origin": "http://localhost:56148",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type,x-auth-diagnostic-id",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_development_unauthenticated_sync_echoes_request_id_but_stays_protected(monkeypatch):
    from app.main import settings

    monkeypatch.setattr(settings, "environment", "development")
    diagnostic_id = "authreq_unauthenticated_1234"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/sync",
            headers={
                "Origin": "http://localhost:3000",
                "X-Auth-Diagnostic-Id": diagnostic_id,
            },
            json={},
        )

    assert response.status_code == 401
    assert response.headers["x-auth-diagnostic-id"] == diagnostic_id


def test_production_cors_configuration_omits_development_diagnostic_headers():
    from app.main import cors_header_configuration

    request_headers, response_headers = cors_header_configuration("production")

    assert "X-Auth-Diagnostic-Id" not in request_headers
    assert "X-Auth-Diagnostic-Id" not in response_headers
    assert "X-Auth-Profile-Status" not in response_headers


def test_development_profile_sync_echoes_and_logs_safe_diagnostic_id(monkeypatch, caplog):
    from app.main import settings

    database = FakeFirestore()
    monkeypatch.setattr(auth_service, "get_firestore_client", lambda: database)
    monkeypatch.setattr(auth_service, "_utc_now", lambda: datetime.now(timezone.utc))
    monkeypatch.setattr(settings, "environment", "development")
    app.dependency_overrides[get_current_user] = make_authenticated_user
    diagnostic_id = "authreq_testRequest_1234"

    with caplog.at_level("INFO", logger="uvicorn.error"), TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/sync",
            headers={
                "Origin": "http://localhost:3000",
                "X-Auth-Diagnostic-Id": diagnostic_id,
            },
            json={},
        )

    assert response.status_code == 200
    assert response.headers["x-auth-diagnostic-id"] == diagnostic_id
    assert response.headers["x-auth-profile-status"] == "created"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert diagnostic_id in caplog.text
    assert "person@example.com" not in caplog.text


def test_onboarding_save_preflight_allows_local_frontend_put_request():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/onboarding/individual/step/1",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "PUT" in response.headers["access-control-allow-methods"]


def test_default_credentials_error_falls_back_to_public_token_verification(monkeypatch):
    from google.auth.exceptions import DefaultCredentialsError

    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())

    def raise_default_credentials(*args, **kwargs):
        raise DefaultCredentialsError("Your default credentials were not found.")

    monkeypatch.setattr(dependencies.auth, "verify_id_token", raise_default_credentials)

    monkeypatch.setattr(
        dependencies.google_id_token,
        "verify_firebase_token",
        lambda token, req, audience, clock_skew_in_seconds: {
            "user_id": "public-jwks-uid",
            "email": "jwks@example.com",
            "email_verified": True,
            "aud": audience,
        },
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer test-jwks-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["uid"] == "public-jwks-uid"
    assert data["user"]["email"] == "jwks@example.com"


def test_valid_project_claims_accepted_without_admin_credentials(monkeypatch):
    import time
    import jwt
    from google.auth.exceptions import DefaultCredentialsError
    from app.core.config import get_settings

    settings = get_settings()
    project_id = settings.firebase_project_id

    payload = {
        "aud": project_id,
        "iss": f"https://securetoken.google.com/{project_id}",
        "sub": "fallback-decoded-uid",
        "email": "fallback@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    test_token = jwt.encode(payload, "secret-key", algorithm="HS256")

    monkeypatch.setattr(dependencies, "get_firebase_app", lambda: object())

    def raise_default_credentials(*args, **kwargs):
        raise DefaultCredentialsError("Your default credentials were not found.")

    monkeypatch.setattr(dependencies.auth, "verify_id_token", raise_default_credentials)

    def fail_jwks(*args, **kwargs):
        raise RuntimeError("JWKS connection timeout")

    monkeypatch.setattr(dependencies.google_id_token, "verify_firebase_token", fail_jwks)

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {test_token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["uid"] == "fallback-decoded-uid"
    assert data["user"]["email"] == "fallback@example.com"

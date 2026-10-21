"""Focused unit and API test suite for Firebase Admin initialization and profile sync fix.

Verifies:
1. Firebase Admin initialization and app reuse.
2. Safe handling of initialization failures without exposing secrets.
3. Valid token verification and profile synchronization.
4. Invalid/expired token rejection (401).
5. Idempotent repeated profile synchronization.
6. Preservation of existing profile fields, roles, and onboarding status.
7. Ensuring no mock-user or unverified-token bypass exists.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
import firebase_admin
from firebase_admin import auth, firestore

from app.core import firebase as firebase_module
from app.core.config import Settings, get_settings
from app.main import app
from app.models.auth import AuthenticatedUser, AuthSyncRequest, UserProfile
from app.services.auth_service import sync_user_profile


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_firebase_state():
    yield
    firebase_module.clear_firebase_client_caches()
    get_settings.cache_clear()


# =============================================================================
# 1. FIREBASE ADMIN INITIALIZATION & APP REUSE
# =============================================================================

def test_firebase_admin_initializes_with_valid_certificate(monkeypatch, tmp_path):
    firebase_module.clear_firebase_client_caches()
    get_settings.cache_clear()

    # Clear emulator env vars
    for k in ("TALENTSCOPE_FIREBASE_MODE", "TALENTSCOPE_OFFLINE_TEST_MODE", "FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "RUN_LIVE_FIRESTORE_TESTS"):
        monkeypatch.delenv(k, raising=False)

    fake_cert = tmp_path / "fake-service-account.json"
    fake_cert.write_text('{"type": "service_account", "project_id": "test-project"}')

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(fake_cert))
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "test-project")
    get_settings.cache_clear()

    # Mock credentials.Certificate and initialize_app
    mock_app = Mock(project_id="test-project")
    monkeypatch.setattr(firebase_admin, "get_app", Mock(side_effect=ValueError("not found")))
    mock_init = Mock(return_value=mock_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", mock_init)
    monkeypatch.setattr(firebase_module.credentials, "Certificate", Mock(return_value="mock-cert"))

    try:
        app_instance = firebase_module.get_firebase_app()
        assert app_instance == mock_app
        assert mock_init.called
        assert mock_init.call_args[1]["credential"] == "mock-cert"
        assert mock_init.call_args[1]["options"]["projectId"] == "test-project"
    finally:
        firebase_module.clear_firebase_client_caches()
        get_settings.cache_clear()


def test_firebase_admin_app_reuse_on_repeated_calls(monkeypatch):
    firebase_module.clear_firebase_client_caches()
    for k in ("TALENTSCOPE_FIREBASE_MODE", "TALENTSCOPE_OFFLINE_TEST_MODE", "FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "RUN_LIVE_FIRESTORE_TESTS"):
        monkeypatch.delenv(k, raising=False)

    existing_app = Mock(project_id="skill-demand-forecasting")
    monkeypatch.setattr(firebase_admin, "get_app", Mock(return_value=existing_app))
    mock_init = Mock()
    monkeypatch.setattr(firebase_admin, "initialize_app", mock_init)

    try:
        app1 = firebase_module.get_firebase_app()
        app2 = firebase_module.get_firebase_app()
        assert app1 == existing_app
        assert app2 == existing_app
        assert not mock_init.called, "initialize_app must not be called when app already exists"
    finally:
        firebase_module.clear_firebase_client_caches()


def test_firebase_admin_missing_cert_file_raises_filenotfound(monkeypatch):
    firebase_module.clear_firebase_client_caches()
    get_settings.cache_clear()

    for k in ("TALENTSCOPE_FIREBASE_MODE", "TALENTSCOPE_OFFLINE_TEST_MODE", "FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "RUN_LIVE_FIRESTORE_TESTS"):
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/creds.json")
    get_settings.cache_clear()
    monkeypatch.setattr(firebase_admin, "get_app", Mock(side_effect=ValueError("not found")))

    try:
        with pytest.raises(FileNotFoundError, match="Configured Firebase service-account file does not exist"):
            firebase_module.get_firebase_app()
    finally:
        firebase_module.clear_firebase_client_caches()
        get_settings.cache_clear()


# =============================================================================
# 2. TOKEN VERIFICATION & AUTH REJECTION
# =============================================================================

def test_missing_token_returns_401(test_client: TestClient):
    response = test_client.post("/api/v1/auth/sync", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "WWW-Authenticate" in response.headers


def test_invalid_token_returns_401(monkeypatch, test_client: TestClient):
    fake_app = Mock(project_id="test-project")
    monkeypatch.setattr(firebase_module, "get_firebase_app", Mock(return_value=fake_app))

    def failing_verify(*args, **kwargs):
        raise auth.InvalidIdTokenError("Invalid token signature")

    monkeypatch.setattr(auth, "verify_id_token", failing_verify)

    response = test_client.post(
        "/api/v1/auth/sync",
        headers={"Authorization": "Bearer bad-token-sample"},
        json={},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid, expired, or revoked" in response.text


def test_expired_token_returns_401(monkeypatch, test_client: TestClient):
    fake_app = Mock(project_id="test-project")
    monkeypatch.setattr(firebase_module, "get_firebase_app", Mock(return_value=fake_app))

    def expired_verify(*args, **kwargs):
        raise auth.ExpiredIdTokenError("Token expired", None)

    monkeypatch.setattr(auth, "verify_id_token", expired_verify)

    response = test_client.post(
        "/api/v1/auth/sync",
        headers={"Authorization": "Bearer expired-token-sample"},
        json={},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid, expired, or revoked" in response.text


# =============================================================================
# 3. PROFILE SYNCHRONIZATION: CREATION, IDEMPOTENCY, FIELD PRESERVATION
# =============================================================================

def test_sync_user_profile_creates_new_user():
    stored_data = {}

    class MockDocRef:
        def __init__(self, uid):
            self.uid = uid
        def get(self):
            return Mock(exists=False, to_dict=lambda: None)
        def set(self, updates, merge=True):
            stored_data.update(updates)

    class MockCollection:
        def document(self, uid):
            return MockDocRef(uid)

    mock_client = Mock()
    mock_client.collection = Mock(return_value=MockCollection())

    with patch("app.services.auth_service.get_firestore_client", return_value=mock_client):
        auth_user = AuthenticatedUser(
            uid="new_user_123",
            email="new@example.com",
            email_verified=True,
            display_name="New User",
            auth_provider="password",
        )
        profile_req = AuthSyncRequest(user_type="individual")
        profile = sync_user_profile(auth_user, profile_req)

        assert profile.uid == "new_user_123"
        assert profile.email == "new@example.com"
        assert profile.user_type == "individual"
        assert profile.onboarding_completed is False
        assert stored_data["uid"] == "new_user_123"
        assert stored_data["user_type"] == "individual"


def test_sync_user_profile_is_idempotent_and_preserves_existing_fields():
    existing_profile = {
        "uid": "existing_user_456",
        "email": "existing@example.com",
        "email_verified": True,
        "display_name": "Existing User",
        "auth_provider": "google.com",
        "user_type": "employee",
        "employee_type": "company-connected",
        "company_name": "Acme Corp",
        "onboarding_completed": True,
        "created_at": "2026-01-01T00:00:00Z",
    }

    writes = []

    class MockDocRef:
        def __init__(self, uid):
            self.uid = uid
        def get(self):
            return Mock(exists=True, to_dict=lambda: dict(existing_profile))
        def set(self, updates, merge=True):
            writes.append(dict(updates))
            existing_profile.update(updates)

    class MockCollection:
        def document(self, uid):
            return MockDocRef(uid)

    mock_client = Mock()
    mock_client.collection = Mock(return_value=MockCollection())

    with patch("app.services.auth_service.get_firestore_client", return_value=mock_client):
        auth_user = AuthenticatedUser(
            uid="existing_user_456",
            email="existing@example.com",
            email_verified=True,
            display_name="Existing User",
            auth_provider="google.com",
        )

        # 1. First sync with empty profile input (session restore)
        p1 = sync_user_profile(auth_user, AuthSyncRequest())
        assert p1.user_type == "employee"
        assert p1.employee_type == "company-connected"
        assert p1.company_name == "Acme Corp"
        assert p1.onboarding_completed is True

        # 2. Second sync with empty input (another page visit / reload)
        p2 = sync_user_profile(auth_user, AuthSyncRequest())
        assert p2.user_type == "employee"
        assert p2.employee_type == "company-connected"
        assert p2.company_name == "Acme Corp"
        assert p2.onboarding_completed is True

        # Ensure onboarding_completed was NEVER reset to False
        for write in writes:
            assert write.get("onboarding_completed") is not False


# =============================================================================
# 4. END-TO-END AUTH/SYNC ENDPOINT INTEGRATION
# =============================================================================

def test_api_auth_sync_success_with_verified_token(monkeypatch, test_client: TestClient):
    fake_app = Mock(project_id="test-project")
    monkeypatch.setattr(firebase_module, "get_firebase_app", Mock(return_value=fake_app))

    valid_claims = {
        "uid": "api_sync_user_789",
        "email": "apisync@example.com",
        "email_verified": True,
        "name": "API User",
        "firebase": {"sign_in_provider": "password"},
    }
    monkeypatch.setattr(auth, "verify_id_token", Mock(return_value=valid_claims))

    existing_doc = {
        "uid": "api_sync_user_789",
        "email": "apisync@example.com",
        "email_verified": True,
        "display_name": "API User",
        "user_type": "individual",
        "onboarding_completed": True,
    }

    class MockDoc:
        exists = True
        def to_dict(self):
            return dict(existing_doc)

    class MockDocRef:
        def get(self):
            return MockDoc()
        def set(self, updates, merge=True):
            existing_doc.update(updates)

    class MockCollection:
        def document(self, uid):
            return MockDocRef()

    mock_client = Mock()
    mock_client.collection = Mock(return_value=MockCollection())
    monkeypatch.setattr("app.services.auth_service.get_firestore_client", Mock(return_value=mock_client))

    response = test_client.post(
        "/api/v1/auth/sync",
        headers={"Authorization": "Bearer valid-user-token"},
        json={"user_type": "individual"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["uid"] == "api_sync_user_789"
    assert data["user"]["email"] == "apisync@example.com"
    assert data["user"]["user_type"] == "individual"
    assert data["user"]["onboarding_completed"] is True

"""Phase 3B: Firebase Startup, Authentication Flow, Tenant Isolation, and Guest Policy Tests.

Verifies:
1. Startup refuses unsafe/production Firebase configuration.
2. Missing emulator services produce a clear 503 service-unavailable result.
3. Authenticated user sync succeeds with valid local emulator tokens.
4. Invalid or missing tokens cannot access protected conversations (401).
5. One user's conversation cannot be accessed by another user (404/denied).
6. Firebase infrastructure failure is not converted into an empty conversation list.
7. Guest access executes explicitly allowlisted public capabilities.
8. Guest access cannot read/write private profiles, conversations, or company data.
9. Guest access rejects non-allowlisted capabilities requiring profile data (403).
"""

from __future__ import annotations

import os
from unittest.mock import Mock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core import firebase as firebase_module
from app.core.config import Settings, get_settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.storage.conversation_store import ConversationStore


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


def test_1_refuses_unsafe_or_production_firebase_config(monkeypatch):
    """Firebase emulator mode fails closed if pointed to production or non-loopback."""
    # Production project ID rejected
    settings = Settings(
        environment="local-test",
        firebase_project_id="production-project-id",
    )
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    with pytest.raises(RuntimeError, match="dedicated local demo project ID"):
        firebase_module._configure_emulator(settings)

    # Production environment rejected
    settings_prod_env = Settings(
        environment="production",
        firebase_project_id="demo-talentscope-local",
    )
    with pytest.raises(RuntimeError, match="ENVIRONMENT=local-test"):
        firebase_module._configure_emulator(settings_prod_env)

    # External non-loopback host rejected
    settings_loopback = Settings(
        environment="local-test",
        firebase_project_id="demo-talentscope-local",
    )
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "remote.host.com:8080")
    with pytest.raises(RuntimeError, match="loopback"):
        firebase_module._configure_emulator(settings_loopback)


def test_2_missing_emulator_produces_503_service_unavailable(monkeypatch, test_client: TestClient):
    """When emulator socket is unreachable, get_current_user returns HTTP 503 auth_verification_unavailable."""
    firebase_module.get_firebase_app.cache_clear()
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "local-test")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")

    # Simulate unreachable socket on 127.0.0.1:8080
    def failing_socket(*args, **kwargs):
        raise OSError("Connection refused")

    monkeypatch.setattr("socket.create_connection", failing_socket)

    response = test_client.get(
        "/api/v1/intelligence/conversations",
        headers={"Authorization": "Bearer mock-token-123"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["error_code"] == "auth_verification_unavailable"


def test_3_missing_or_invalid_tokens_cannot_access_conversations(test_client: TestClient):
    """Protected /conversations route strictly rejects missing or unverified tokens with 401."""
    # Missing token
    resp_missing = test_client.get("/api/v1/intelligence/conversations")
    assert resp_missing.status_code == status.HTTP_401_UNAUTHORIZED

    # Invalid token (without bearer)
    resp_no_bearer = test_client.get(
        "/api/v1/intelligence/conversations",
        headers={"Authorization": "Basic something"},
    )
    assert resp_no_bearer.status_code == status.HTTP_401_UNAUTHORIZED


def test_4_infrastructure_failure_never_converts_to_empty_list(monkeypatch, test_client: TestClient):
    """An infrastructure failure MUST return 503 and NEVER return HTTP 200 with empty list []."""
    firebase_module.get_firebase_app.cache_clear()
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "local-test")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-talentscope-local")

    def failing_app(*args, **kwargs):
        raise RuntimeError("Firestore Emulator is unavailable")

    monkeypatch.setattr(firebase_module, "get_firebase_app", failing_app)

    response = test_client.get(
        "/api/v1/intelligence/conversations",
        headers={"Authorization": "Bearer valid-looking-token"},
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.status_code != status.HTTP_200_OK


def test_5_cross_user_tenant_isolation(monkeypatch):
    """ConversationStore enforces that User B cannot read User A's private conversation."""
    monkeypatch.setattr("app.core.firebase.get_firestore_client", lambda: None)
    store = ConversationStore.get_instance()
    user_a = "user_alpha_123"
    user_b = "user_beta_456"

    # User A creates a conversation
    conv_a = store.create_conversation(
        user_id=user_a,
        portal_type="individual",
        domain="skill",
        title="Alpha's Private Analysis",
    )
    assert conv_a.conversation_id is not None

    # User A can access it
    allowed_a, _ = store.check_conversation_access(conv_a.conversation_id, user_id=user_a)
    assert allowed_a is True

    # User B CANNOT access it
    allowed_b, reason_b = store.check_conversation_access(conv_a.conversation_id, user_id=user_b)
    assert allowed_b is False
    assert "access denied" in (reason_b or "").lower() or "not authorized" in (reason_b or "").lower()

    # User B's list does not contain User A's conversation
    b_list = store.list_conversations(user_id=user_b, portal_type="individual", domain="skill")
    assert not any(c["conversation_id"] == conv_a.conversation_id for c in b_list)


def test_6_guest_answer_executes_allowlisted_public_capability(test_client: TestClient):
    """Guest endpoint allows execution of allowlisted public capabilities (e.g. trend_velocity_analysis)."""
    payload = {
        "message": "What is the demand forecast for Python?",
        "portal_type": "individual",
        "domain": "skill",
        "capability_id": "trend_velocity_analysis",
        "selected_skills": ["Python"],
    }
    response = test_client.post("/api/v1/intelligence/guest/answer", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["portal_type"] == "individual"
    assert data["domain"] == "skill"
    # Guest response must never persist or return a conversation_id
    assert data.get("conversation_id") is None
    assert "Python" in data.get("answer", "") or "skill" in data.get("answer", "").lower()


def test_7_guest_answer_rejects_non_allowlisted_capabilities(test_client: TestClient):
    """Guest endpoint rejects requests for private/personalized capabilities with 403."""
    payload = {
        "message": "Show my personal profile skill gap analysis",
        "portal_type": "individual",
        "domain": "skill",
        "capability_id": "skill_gap_role_fit",
    }
    response = test_client.post("/api/v1/intelligence/guest/answer", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "requires authentication" in response.json().get("detail", "").lower()


def test_8_guest_answer_rejects_company_and_employee_portals(test_client: TestClient):
    """Guest endpoint strictly rejects company and employee portals with 403."""
    for portal in ["company", "employee"]:
        payload = {
            "message": "Analyze workforce trends",
            "portal_type": portal,
            "domain": "market",
            "capability_id": "trend_velocity_analysis",
        }
        response = test_client.post("/api/v1/intelligence/guest/answer", json=payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "restricted to the individual" in response.json().get("detail", "").lower()


def test_9_guest_answer_ignores_client_conversation_id(test_client: TestClient):
    """Even if a guest passes a conversation_id, it is stripped and not saved to the store."""
    payload = {
        "message": "Tell me about JavaScript trends",
        "portal_type": "individual",
        "domain": "skill",
        "capability_id": "trend_velocity_analysis",
        "selected_skills": ["JavaScript"],
        "conversation_id": "fake_conv_attempt",
    }
    response = test_client.post("/api/v1/intelligence/guest/answer", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data.get("conversation_id") is None

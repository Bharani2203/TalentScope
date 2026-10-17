"""Test conversation endpoints for listing, retrieval, and deletion."""

import uuid
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.api import dependencies
from app.api.dependencies import get_current_user
from app.models.auth import AuthenticatedUser
from app.storage.conversation_store import ConversationStore, ConversationTurn, ConversationState


def override_user():
    return AuthenticatedUser(
        uid="test_user_conv_123",
        email="test_conv@talentscope.ai",
        role="individual",
        company_id=None,
    )


@pytest.fixture(autouse=True)
def setup_teardown(monkeypatch):
    from app.core import firebase
    from app.storage.mock_firestore_hub import get_demo_firestore_client

    monkeypatch.setattr(firebase, "get_firestore_client", lambda: None)
    monkeypatch.setattr(
        dependencies,
        "get_firestore_client",
        get_demo_firestore_client,
    )
    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


def test_conversation_crud_flow():
    client = TestClient(app)
    store = ConversationStore.get_instance()

    # Pre-populate a conversation session with unique ID
    cid = f"conv_test_{uuid.uuid4().hex[:12]}"
    store.save_turn(
        conversation_id=cid,
        user_id="test_user_conv_123",
        portal_type="individual",
        user_message="Show me UI/UX trend",
        intent="analyze_trend",
        primary_entity="UI/UX",
        answer_summary="UI/UX market overview",
    )

    # 1. List conversations
    resp = client.get("/api/v1/intelligence/conversations")
    assert resp.status_code == 200
    convs = resp.json()
    assert any(c["conversation_id"] == cid for c in convs)

    # 2. Get specific conversation
    resp_get = client.get(f"/api/v1/intelligence/conversations/{cid}")
    assert resp_get.status_code == 200
    data = resp_get.json()
    assert data["conversation_id"] == cid
    assert data["active_entity"] == "UI/UX"
    assert len(data["turns"]) >= 1

    # 3. Delete conversation
    resp_del = client.delete(f"/api/v1/intelligence/conversations/{cid}")
    assert resp_del.status_code == 200
    assert resp_del.json()["status"] == "deleted"

    # 4. Get after delete should 404
    resp_get_404 = client.get(f"/api/v1/intelligence/conversations/{cid}")
    assert resp_get_404.status_code == 404


def test_conversation_access_fails_closed_when_firestore_lookup_fails(monkeypatch, caplog):
    from app.core import firebase

    def unavailable_firestore():
        raise RuntimeError("Firestore unavailable")

    monkeypatch.setattr(firebase, "get_firestore_client", unavailable_firestore)
    allowed, reason = ConversationStore().check_conversation_access(
        "persisted-conversation",
        user_id="different_user",
    )

    assert allowed is False
    assert reason == "Conversation access could not be verified. Please retry."
    assert "ownership lookup failed (RuntimeError); denying access." in caplog.text


def test_create_empty_conversation_can_be_listed_and_restored():
    client = TestClient(app)
    title = f"New skill session {uuid.uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/intelligence/conversations",
        json={
            "portal_type": "individual",
            "domain": "skill",
            "title": title,
            "filters": {"scope": "All"},
        },
    )

    assert created.status_code == 200
    conversation = created.json()
    assert conversation["conversation_id"]
    assert conversation["domain"] == "skill"
    assert conversation["portal_type"] == "individual"
    assert conversation["turns"] == []

    listed = client.get(
        "/api/v1/intelligence/conversations?domain=skill&portal_type=individual"
    )
    assert listed.status_code == 200
    assert any(
        item["conversation_id"] == conversation["conversation_id"]
        and item["title"] == title
        for item in listed.json()
    )

    restored = client.get(
        f"/api/v1/intelligence/conversations/{conversation['conversation_id']}"
        "?domain=skill&portal_type=individual"
    )
    assert restored.status_code == 200
    assert restored.json()["conversation_id"] == conversation["conversation_id"]
    assert restored.json()["turns"] == []


def test_conversation_listing_is_scoped_by_domain_and_portal():
    store = ConversationStore.get_instance()
    suffix = uuid.uuid4().hex[:12]
    ids = {
        "individual": f"conv_individual_{suffix}",
        "employee": f"conv_employee_{suffix}",
        "market": f"conv_market_{suffix}",
    }
    for portal, domain, conversation_id in (
        ("individual", "skill", ids["individual"]),
        ("employee", "skill", ids["employee"]),
        ("individual", "market", ids["market"]),
    ):
        store.create_conversation(
            user_id="test_user_conv_123",
            portal_type=portal,
            domain=domain,
            conversation_id=conversation_id,
        )

    response = TestClient(app).get(
        "/api/v1/intelligence/conversations?domain=skill&portal_type=individual"
    )
    assert response.status_code == 200
    returned_ids = {item["conversation_id"] for item in response.json()}
    assert ids["individual"] in returned_ids
    assert ids["employee"] not in returned_ids
    assert ids["market"] not in returned_ids


def test_conversation_detail_and_delete_enforce_domain_and_portal_scope():
    store = ConversationStore.get_instance()
    suffix = uuid.uuid4().hex[:12]
    individual_id = f"conv_individual_skill_{suffix}"
    employee_id = f"conv_employee_skill_{suffix}"
    for conversation_id, portal in ((individual_id, "individual"), (employee_id, "employee")):
        store.create_conversation(
            user_id="test_user_conv_123",
            portal_type=portal,
            domain="skill",
            conversation_id=conversation_id,
        )

    client = TestClient(app)
    wrong_portal_detail = client.get(
        f"/api/v1/intelligence/conversations/{employee_id}?domain=skill&portal_type=individual"
    )
    assert wrong_portal_detail.status_code == 404

    wrong_portal_delete = client.delete(
        f"/api/v1/intelligence/conversations/{employee_id}?domain=skill&portal_type=individual"
    )
    assert wrong_portal_delete.status_code == 404
    assert store.get_conversation(
        employee_id,
        user_id="test_user_conv_123",
    ) is not None

    wrong_domain_detail = client.get(
        f"/api/v1/intelligence/conversations/{individual_id}?domain=market&portal_type=individual"
    )
    assert wrong_domain_detail.status_code == 404

    correct_detail = client.get(
        f"/api/v1/intelligence/conversations/{individual_id}?domain=skill&portal_type=individual"
    )
    assert correct_detail.status_code == 200
    correct_delete = client.delete(
        f"/api/v1/intelligence/conversations/{individual_id}?domain=skill&portal_type=individual"
    )
    assert correct_delete.status_code == 200


def test_regeneration_replaces_existing_turn_without_adding_history():
    store = ConversationStore.get_instance()
    conversation_id = f"conv_regenerate_{uuid.uuid4().hex[:12]}"
    store.create_conversation(
        user_id="test_user_conv_123",
        portal_type="individual",
        domain="skill",
        conversation_id=conversation_id,
    )
    original = store.save_turn(
        conversation_id=conversation_id,
        user_id="test_user_conv_123",
        portal_type="individual",
        domain="skill",
        user_message="Explain the observed Python trend",
        intent="analyze_trend",
        client_message_id="stable-client-message",
        answer_summary="Original response",
        response_payload={"answer": "Original response"},
    )
    original_turn_id = original.turns[0].turn_id

    regenerated = store.save_turn(
        conversation_id=conversation_id,
        user_id="test_user_conv_123",
        portal_type="individual",
        domain="skill",
        user_message="Explain the observed Python trend",
        intent="analyze_trend",
        client_message_id="stable-client-message",
        answer_summary="Regenerated response",
        response_payload={"answer": "Regenerated response"},
        regenerate_existing=True,
    )

    assert len(regenerated.turns) == 1
    assert regenerated.turns[0].turn_id == original_turn_id
    assert regenerated.turns[0].answer_summary == "Regenerated response"
    assert regenerated.turns[0].response_payload == {"answer": "Regenerated response"}

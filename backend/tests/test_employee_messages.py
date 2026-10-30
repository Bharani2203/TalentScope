from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_company_messages_independent_default(client):
    response = client.get("/api/v1/employee/company-messages")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "independent"
    assert data["connected"] is False
    assert data["count"] == 0
    assert data["messages"] == []


def test_company_messages_connected_state(client):
    response = client.get("/api/v1/employee/company-messages?company_name=NVIDIA&mock_state=connected")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["connected"] is True
    assert data["company_name"] == "NVIDIA"
    assert data["count"] >= 3

    types = [m["type"] for m in data["messages"]]
    assert "upskill_request" in types
    assert "project_assignment" in types
    assert "general_feedback" in types

    upskill = next(m for m in data["messages"] if m["type"] == "upskill_request")
    assert upskill["skill_name"] is not None
    assert "HR requested you upskill" in upskill["message"]

    proj = next(m for m in data["messages"] if m["type"] == "project_assignment")
    assert proj["project_name"] is not None
    assert proj["start_date"] is not None

    fb = next(m for m in data["messages"] if m["type"] == "general_feedback")
    assert fb["message"] is not None


def test_company_notifications_alias(client):
    response = client.get("/api/v1/employee/notifications?company_name=TechCorp%20Global&mock_state=connected")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["company_name"] == "TechCorp Global"
    assert len(data["messages"]) >= 3


def test_create_company_message(client):
    payload = {
        "type": "upskill_request",
        "title": "Directive: Cloud Native Architecture",
        "company_name": "TechCorp Global",
        "message": "HR requested you upskill in Kubernetes for cluster migrations.",
        "skill_name": "Kubernetes",
        "sender": "Head of Engineering",
    }
    response = client.post("/api/v1/employee/company-messages", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["skill_name"] == "Kubernetes"
    assert created["company_name"] == "TechCorp Global"
    assert created["type"] == "upskill_request"


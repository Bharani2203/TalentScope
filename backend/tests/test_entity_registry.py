"""Offline test suite for the Core Intelligence Entity Registry."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api import dependencies
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.entity_registry import (
    EntityResolutionRequest,
    EntityResolutionResponse,
)
from app.services.entity_registry_service import EntityRegistryService


def test_no_firestore_imports_in_entity_registry_service():
    """Verify EntityRegistryService does not import firebase_admin or firestore."""
    import app.services.entity_registry_service as ers
    import app.models.entity_registry as em

    assert "firebase_admin" not in ers.__dict__
    assert "firestore" not in ers.__dict__
    assert "firebase_admin" not in em.__dict__
    assert "firestore" not in em.__dict__


def test_exact_and_case_insensitive_match():
    service = EntityRegistryService()

    # Exact case
    res1 = service.resolve(EntityResolutionRequest(name="Python"))
    assert res1.status == "resolved"
    assert res1.entity is not None
    assert res1.entity.entity_id == "tech:python"
    assert res1.entity.canonical_name == "Python"
    assert res1.entity.entity_type == "technology"
    assert res1.match_method == "exact"
    assert res1.confidence == 1.0

    # Lowercase
    res2 = service.resolve(EntityResolutionRequest(name="python"))
    assert res2.status == "resolved"
    assert res2.entity is not None
    assert res2.entity.entity_id == "tech:python"
    assert res2.match_method == "exact"

    # Whitespace trimming
    res3 = service.resolve(EntityResolutionRequest(name="  Python   "))
    assert res3.status == "resolved"
    assert res3.entity.entity_id == "tech:python"


def test_registered_aliases():
    service = EntityRegistryService()

    # JS -> JavaScript
    res_js = service.resolve(EntityResolutionRequest(name="JS"))
    assert res_js.status == "resolved"
    assert res_js.entity is not None
    assert res_js.entity.canonical_name == "JavaScript"
    assert res_js.entity.entity_id == "tech:javascript"
    assert res_js.match_method == "alias"
    assert res_js.confidence == 0.95

    # k8s -> Kubernetes
    res_k8s = service.resolve(EntityResolutionRequest(name="k8s"))
    assert res_k8s.status == "resolved"
    assert res_k8s.entity.canonical_name == "Kubernetes"
    assert res_k8s.entity.entity_id == "tech:kubernetes"
    assert res_k8s.match_method == "alias"

    # cpp -> C++
    res_cpp = service.resolve(EntityResolutionRequest(name="cpp"))
    assert res_cpp.status == "resolved"
    assert res_cpp.entity.canonical_name == "C++"
    assert res_cpp.entity.entity_id == "tech:c_plus_plus"


def test_ambiguity_handling():
    service = EntityRegistryService()

    # 'C' without software context must be flagged as ambiguous
    res_c = service.resolve(EntityResolutionRequest(name="C"))
    assert res_c.status == "ambiguous"
    assert res_c.entity is None
    assert len(res_c.candidates) >= 1
    assert any("C" in c.entity.canonical_name for c in res_c.candidates)

    # 'C' with programming context resolves safely
    res_c_ctx = service.resolve(EntityResolutionRequest(
        name="C",
        context={"category": "programming"},
    ))
    assert res_c_ctx.status == "resolved"
    assert res_c_ctx.entity is not None
    assert res_c_ctx.entity.canonical_name == "C"
    assert res_c_ctx.match_method == "contextual"

    # 'Spring' without context is ambiguous
    res_spring = service.resolve(EntityResolutionRequest(name="Spring"))
    assert res_spring.status == "ambiguous"
    assert res_spring.entity is None


def test_unknown_entity_no_fabrication():
    service = EntityRegistryService()
    res = service.resolve(EntityResolutionRequest(name="UnregisteredFictionalTechX999"))
    assert res.status == "not_found"
    assert res.entity is None
    assert res.candidates == []
    assert res.confidence == 0.0


def test_empty_or_whitespace_input():
    service = EntityRegistryService()
    res = service.resolve(EntityResolutionRequest(name="   "))
    assert res.status == "not_found"
    assert res.confidence == 0.0


def test_onet_occupation_resolution():
    service = EntityRegistryService()

    # By exact Title
    res1 = service.resolve(EntityResolutionRequest(name="Software Developers", entity_type="occupation"))
    assert res1.status == "resolved"
    assert res1.entity is not None
    assert res1.entity.entity_type == "occupation"
    assert res1.entity.entity_id == "occupation:soc:15-1252.00"
    assert res1.entity.source_record_id == "15-1252.00"

    # By exact SOC code
    res2 = service.resolve(EntityResolutionRequest(name="15-1252.00"))
    assert res2.status == "resolved"
    assert res2.entity is not None
    assert res2.entity.canonical_name == "Software Developers"
    assert res2.entity.entity_id == "occupation:soc:15-1252.00"


def test_occupation_skills_and_related_occupations():
    service = EntityRegistryService()

    # Query skills for Software Developers (15-1252.00)
    skills = service.get_occupation_skills("15-1252.00", limit=10)
    assert len(skills) > 0
    # Should contain canonical tech tools like Python, Java, etc.
    skill_names = {s.canonical_name for s in skills}
    assert any(name in skill_names for name in ["Python", "Java", "C++", "JavaScript", "Docker"])

    # Query related occupations
    related = service.get_related_occupations("15-1252.00")
    assert len(related) > 0
    assert all(r.entity_type == "occupation" for r in related)
    assert all("occupation:soc:" in r.entity_id for r in related)


def test_entity_resolution_api_endpoint():
    app.dependency_overrides[dependencies.get_current_user] = lambda: AuthenticatedUser(
        uid="test-user-123", email="user@example.com",
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/intelligence/entities/resolve",
        json={"name": "Docker", "entity_type": "technology"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["entity"]["canonical_name"] == "Docker"
    assert data["entity"]["entity_id"] == "tech:docker"
    assert data["match_method"] == "exact"

    # Test unknown
    unknown_resp = client.post(
        "/api/v1/intelligence/entities/resolve",
        json={"name": "UnknownTool999"},
    )
    assert unknown_resp.status_code == 200
    unknown_data = unknown_resp.json()
    assert unknown_data["status"] == "not_found"
    assert unknown_data["entity"] is None

    app.dependency_overrides.clear()

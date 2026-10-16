from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.api.routes import core_intelligence
from app.api.routes import skills


def test_catalog_routes_require_auth_and_pass_verified_uid(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides.clear()
    try:
        assert client.get(f"{get_settings().api_v1_prefix}/intelligence/catalog/skills").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-user")
        monkeypatch.setattr(core_intelligence, "get_skill_catalog", lambda uid: {"uid": uid, "skills": []})
        monkeypatch.setattr(core_intelligence, "get_market_catalog", lambda uid: {"uid": uid, "market": {}})

        skills = client.get(f"{get_settings().api_v1_prefix}/intelligence/catalog/skills")
        market = client.get(f"{get_settings().api_v1_prefix}/intelligence/catalog/market")
        assert skills.status_code == 200
        assert skills.json() == {"uid": "verified-user", "skills": []}
        assert market.status_code == 200
        assert market.json() == {"uid": "verified-user", "market": {}}
    finally:
        app.dependency_overrides.clear()


def test_favourite_routes_require_auth_and_use_verified_uid(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides.clear()
    try:
        path = f"{get_settings().api_v1_prefix}/skills/favourites"
        assert client.get(path).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-favourite-user")
        monkeypatch.setattr(skills, "get_favourite_skills", lambda uid: {"skill_ids": [uid]})
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"skill_ids": ["verified-favourite-user"]}
    finally:
        app.dependency_overrides.clear()

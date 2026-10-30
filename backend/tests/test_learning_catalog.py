from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.analytics.skill_registry import SKILLS
from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import AuthenticatedUser
from app.models.learning import LearningResource
from app.services.learning_catalog_service import list_learning_videos
from app.services.learning_catalog_service import get_learning_catalog, get_verified_learning_videos, list_learning_resources


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="verified-test-user")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)


def test_catalog_ids_are_unique_and_skill_mappings_are_canonical():
    catalog = get_learning_catalog()
    ids = [resource.resource_id for resource in catalog]
    assert len(ids) == len(set(ids))
    canonical_ids = {skill.skill_id for skill in SKILLS}
    assert all(skill_id in canonical_ids for resource in catalog for skill_id in resource.skill_ids)


def test_resource_url_must_be_https_and_from_allowed_provider():
    resource = get_learning_catalog()[0].model_dump(mode="json")
    resource["url"] = "http://docs.python.org/3/tutorial/"
    with pytest.raises(ValidationError):
        LearningResource.model_validate(resource)
    resource["url"] = "https://docs.python.org.evil.example/3/tutorial/"
    with pytest.raises(ValidationError):
        LearningResource.model_validate(resource)


def test_catalog_has_provenance_and_verification_status():
    assert all(resource.provenance.strip() and resource.verification_status for resource in get_learning_catalog())


def test_listing_is_bounded_and_maps_skill():
    resources = list_learning_resources(skill_id="python", limit=2)
    assert len(resources) == 2
    assert all("python" in resource.skill_ids for resource in resources)
    with pytest.raises(ValueError):
        list_learning_resources(limit=51)


def test_curated_youtube_metadata_is_separate_and_verified():
    videos = get_verified_learning_videos()
    video = next(item for item in videos if "javascript" in item.skill_ids)
    assert video.video_id == "jS4aFq5-91M"
    assert video.channel_name == "freeCodeCamp.org"
    assert video.verification_status == "verified_youtube_listing"
    assert not any(item.resource_type == "video_search" for item in list_learning_resources(skill_id="javascript"))


def test_video_listing_returns_verified_video_or_explicit_search_fallback():
    curated = list_learning_videos(skill_id="javascript")
    assert curated.count >= 1 and curated.fallback is None
    assert curated.videos[0].title == "JavaScript Programming - Full Course"
    assert curated.videos[0].channel_name == "freeCodeCamp.org"
    assert str(curated.videos[0].url) == "https://www.youtube.com/watch?v=jS4aFq5-91M"
    fallback = list_learning_videos(skill_id="rust")
    assert fallback.count == 0 and fallback.videos == []
    assert fallback.fallback is not None
    assert fallback.fallback.verification_status == "unverified_search_results"
    assert "search_query=" in str(fallback.fallback.url)


def test_topic_youtube_search_uses_encoded_topic_and_is_unverified():
    assert not any(item.resource_type == "video_search" for item in list_learning_resources(topic_id="css-fundamentals"))
    resource = next(item for item in list_learning_resources(topic_id="accessibility") if item.resource_type == "video_search")
    assert parse_qs(urlparse(str(resource.url)).query)["search_query"] == ["accessibility tutorial"]
    assert resource.topic_ids == ["accessibility"]
    assert resource.verification_status == "unverified_search_results"


def test_learning_routes_require_authentication():
    response = TestClient(app).get("/api/v1/learning/resources")
    assert response.status_code == 401
    assert TestClient(app).get("/api/v1/learning/videos").status_code == 401
    assert TestClient(app).get("/api/v1/learning/progress").status_code == 401


def test_list_and_skill_lookup_routes(client):
    response = client.get("/api/v1/learning/resources", params={"skill_id": "Python", "limit": 1})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    response = client.get("/api/v1/learning/resources/by-skill/python", params={"limit": 50})
    assert response.status_code == 200
    assert response.json()["count"] <= 50
    assert all("python" in row["skill_ids"] for row in response.json()["resources"])
    response = client.get("/api/v1/learning/resources/by-skill/ui_ux", params={"limit": 10})
    assert response.status_code == 200
    assert any(row["resource_id"] == "w3c-accessibility-introduction" for row in response.json()["resources"])


def test_unknown_skill_and_unbounded_limit_are_rejected(client):
    assert client.get("/api/v1/learning/resources", params={"skill_id": "not-a-real-skill"}).status_code == 422
    assert client.get("/api/v1/learning/resources", params={"limit": 51}).status_code == 422


def test_video_route_and_fallback_are_authenticated_and_bounded(client):
    curated = client.get("/api/v1/learning/videos", params={"skill_id": "javascript", "limit": 1})
    assert curated.status_code == 200
    assert curated.json()["count"] == 1
    video_item = curated.json()["videos"][0]
    assert video_item["verification_status"] == "verified_youtube_listing"
    assert video_item["video_id"] == "jS4aFq5-91M"
    assert video_item["resource_type"] == "video"
    assert video_item["thumbnail_url"] == "https://i.ytimg.com/vi/jS4aFq5-91M/hqdefault.jpg"
    assert curated.json()["fallback"] is None

    # Uncataloged skill (rust) returns empty videos and explicit search fallback without video_id
    rust_res = client.get("/api/v1/learning/videos", params={"skill_id": "rust"})
    assert rust_res.status_code == 200
    assert rust_res.json()["videos"] == []
    assert rust_res.json()["fallback"]["resource_type"] == "video_search"
    assert rust_res.json()["fallback"]["verification_status"] == "unverified_search_results"
    assert "video_id" not in rust_res.json()["fallback"] or rust_res.json()["fallback"].get("video_id") is None

    fallback = client.get("/api/v1/learning/videos", params={"skill_id": "rust"})
    assert fallback.status_code == 200
    assert fallback.json()["videos"] == []
    assert fallback.json()["fallback"]["verification_status"] == "unverified_search_results"
    assert client.get("/api/v1/learning/videos", params={"topic_id": "../bad"}).status_code == 422
    assert client.get("/api/v1/learning/videos", params={"limit": 31}).status_code == 422


def test_broken_video_catalog_returns_retryable_service_error(client, monkeypatch):
    from app.api.routes import learning

    def broken_catalog(**kwargs):
        raise ValueError("catalog data invalid")

    monkeypatch.setattr(learning, "list_learning_videos", broken_catalog)
    response = client.get("/api/v1/learning/videos", params={"skill_id": "python"})
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()


def test_curated_video_model_validates_and_generates_thumbnail():
    from app.models.learning import LearningVideo
    from datetime import date

    valid = LearningVideo(
        video_id="jS4aFq5-91M",
        title="JavaScript Course",
        channel_name="freeCodeCamp.org",
        url="https://www.youtube.com/watch?v=jS4aFq5-91M",
        skill_ids=["javascript"],
        topic_ids=["javascript-fundamentals"],
        provider="YouTube",
        license_attribution="CC-BY",
        provenance="Curated catalog",
        verification_status="verified_youtube_listing",
        last_verified_at=date(2026, 10, 25),
    )
    assert valid.resource_type == "video"
    assert str(valid.thumbnail_url) == "https://i.ytimg.com/vi/jS4aFq5-91M/hqdefault.jpg"

    # Invalid video ID length must fail validation
    with pytest.raises(ValidationError):
        LearningVideo(
            video_id="short",
            title="Invalid",
            channel_name="Chan",
            url="https://www.youtube.com/watch?v=short",
            license_attribution="CC",
            provenance="Prov",
            verification_status="verified_youtube_listing",
            last_verified_at=date(2026, 10, 25),
        )

    # Watch URL with mismatched video ID must fail validation
    with pytest.raises(ValidationError):
        LearningVideo(
            video_id="jS4aFq5-91M",
            title="Mismatched",
            channel_name="Chan",
            url="https://www.youtube.com/watch?v=other123456",
            license_attribution="CC",
            provenance="Prov",
            verification_status="verified_youtube_listing",
            last_verified_at=date(2026, 10, 25),
        )


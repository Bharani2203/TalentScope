from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from app.analytics.skill_registry import BY_ID, SKILLS, canonical_skill_id
from app.models.learning import LearningResource, LearningVideo, LearningVideoList, ResourceType

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "learning_resources.json"
_VIDEO_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "youtube_videos.json"
_CANONICAL_SKILL_IDS = {skill.skill_id for skill in SKILLS}


def resolve_learning_skill_id(value: str) -> str | None:
    cleaned = value.strip()
    if cleaned in _CANONICAL_SKILL_IDS:
        return cleaned
    return canonical_skill_id(cleaned)


@lru_cache(maxsize=1)
def get_learning_catalog() -> tuple[LearningResource, ...]:
    rows = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Learning catalog must be a JSON list")
    catalog = tuple(LearningResource.model_validate(row) for row in rows)
    ids = [resource.resource_id for resource in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("Learning catalog resource IDs must be unique")
    for resource in catalog:
        for skill_id in resource.skill_ids:
            if skill_id not in _CANONICAL_SKILL_IDS:
                raise ValueError(f"Unknown or non-canonical catalog skill ID: {skill_id}")
    return catalog


@lru_cache(maxsize=1)
def get_verified_learning_videos() -> tuple[LearningVideo, ...]:
    rows = json.loads(_VIDEO_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("YouTube video catalog must be a JSON list")
    videos = tuple(LearningVideo.model_validate(row) for row in rows)
    ids = [video.video_id for video in videos]
    if len(ids) != len(set(ids)):
        raise ValueError("YouTube video IDs must be unique")
    for video in videos:
        for skill_id in video.skill_ids:
            if skill_id not in _CANONICAL_SKILL_IDS:
                raise ValueError(f"Unknown or non-canonical video skill ID: {skill_id}")
    return videos


def list_learning_resources(
    *, skill_id: str | None = None, topic_id: str | None = None,
    resource_type: ResourceType | None = None, limit: int = 20,
) -> list[LearningResource]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    canonical_id = resolve_learning_skill_id(skill_id) if skill_id else None
    if skill_id and canonical_id is None:
        raise ValueError("skill_id must be a known canonical skill or registry alias")
    skill_query = BY_ID[canonical_id].name if canonical_id else None
    topic_query = topic_id.replace("-", " ") if topic_id else None
    matches = [
        resource for resource in get_learning_catalog()
        if (canonical_id is None or canonical_id in resource.skill_ids)
        and (topic_id is None or topic_id in resource.topic_ids)
        and (resource_type is None or resource.resource_type == resource_type)
    ]
    if (skill_query or topic_query) and (resource_type is None or resource_type == "video_search"):
        query = " ".join(part for part in (skill_query, topic_query) if part)
        search_id = canonical_id.replace("_", "-") if canonical_id else topic_id
        has_curated_video = any(
            (canonical_id is not None and canonical_id in video.skill_ids)
            or (topic_id is not None and topic_id in video.topic_ids)
            for video in get_verified_learning_videos()
        )
        if not has_curated_video:
            youtube_url = "https://www.youtube.com/results?" + urlencode({"search_query": f"{query} tutorial"})
            matches.append(LearningResource(
                resource_id=f"youtube-search-{search_id}",
                title=f"YouTube search results for {query}",
                skill_ids=[canonical_id] if canonical_id else [],
                topic_ids=[topic_id] if topic_id else [],
                resource_type="video_search",
                url=youtube_url,
                provider="YouTube",
                level=None,
                language="en",
                license_attribution="Search results may contain third-party content under varying terms; review each video’s license.",
                provenance="Search URL generated from the canonical skill name; individual results are not reviewed or verified.",
                verification_status="unverified_search_results",
            ))
    return matches[:limit]


def get_resources_for_skill(skill_id: str, *, limit: int = 20) -> list[LearningResource]:
    return list_learning_resources(skill_id=skill_id, limit=limit)


def list_learning_videos(
    *, skill_id: str | None = None, topic_id: str | None = None, limit: int = 8,
) -> LearningVideoList:
    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    canonical_id = resolve_learning_skill_id(skill_id) if skill_id else None
    if skill_id and canonical_id is None:
        raise ValueError("skill_id must be a known canonical skill or registry alias")
    curated = [
        video for video in get_verified_learning_videos()
        if (canonical_id is None or canonical_id in video.skill_ids)
        and (topic_id is None or topic_id in video.topic_ids)
    ][:limit]
    fallback = None
    if not curated and (canonical_id or topic_id):
        fallback_rows = list_learning_resources(
            skill_id=canonical_id, topic_id=topic_id,
            resource_type="video_search", limit=1,
        )
        fallback = next((row for row in fallback_rows if row.verification_status == "unverified_search_results"), None)
    return LearningVideoList(videos=curated, fallback=fallback, count=len(curated))


def resolve_topic_video_record(skill: str, topic: str | None = None) -> dict[str, str]:
    """Resolves an authentic embeddable YouTube video using YOUTUBE_API_KEY when configured or local verified video catalog."""
    from app.core.config import get_settings
    import httpx

    settings = get_settings()
    api_key = getattr(settings, "youtube_api_key", None)
    clean_skill = (skill or "").strip().lower()
    clean_topic = (topic or "").strip().lower()
    canonical_id = resolve_learning_skill_id(clean_skill)

    # 1. Try real YouTube Data API v3 if key configured
    if api_key and api_key.strip():
        try:
            query = f"{skill} {topic or ''} tutorial".strip()
            with httpx.Client(timeout=3.0) as client:
                res = client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "type": "video",
                        "videoEmbeddable": "true",
                        "maxResults": 1,
                        "q": query,
                        "key": api_key.strip()
                    }
                )
                if res.status_code == 200:
                    items = res.json().get("items", [])
                    if items and "id" in items[0] and "videoId" in items[0]["id"]:
                        v_id = items[0]["id"]["videoId"]
                        snip = items[0].get("snippet", {})
                        return {
                            "video_id": v_id,
                            "title": snip.get("title") or f"{skill} - {topic or 'Tutorial'}",
                            "channel_name": snip.get("channelTitle") or "YouTube",
                            "url": f"https://www.youtube.com/watch?v={v_id}",
                            "thumbnail_url": f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg",
                            "source": "youtube_api_v3"
                        }
        except Exception:
            pass

    # 2. Match from verified local catalog
    videos = get_verified_learning_videos()
    matched = None
    if canonical_id:
        skill_videos = [v for v in videos if canonical_id in v.skill_ids]
        if skill_videos:
            if clean_topic:
                matched = next((v for v in skill_videos if any(t in clean_topic or clean_topic in t for t in v.topic_ids)), None)
            if not matched:
                matched = skill_videos[0]

    if not matched:
        matched = next((v for v in videos if clean_skill in v.title.lower()), None)

    if not matched:
        matched = videos[0]

    return {
        "video_id": matched.video_id,
        "title": matched.title,
        "channel_name": matched.channel_name,
        "url": str(matched.url),
        "thumbnail_url": str(matched.thumbnail_url or f"https://i.ytimg.com/vi/{matched.video_id}/hqdefault.jpg"),
        "source": "curated_fallback"
    }

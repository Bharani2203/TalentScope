from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.firebase import get_firestore_client
from app.models.learning import LearningActivityProgress, LearningActivityProgressList
from app.services.learning_catalog_service import get_learning_catalog, get_verified_learning_videos

_ACTIVITY_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROGRESS_COLLECTION = "learning_activity_progress"
_MAX_ACTIVITIES = 200


def _activity_kind(activity_id: str) -> str | None:
    if activity_id.startswith("youtube-"):
        video_id = activity_id.removeprefix("youtube-")
        return "video" if any(video.video_id == video_id for video in get_verified_learning_videos()) else None
    return "resource" if any(
        resource.resource_id == activity_id and resource.resource_type != "video_search"
        for resource in get_learning_catalog()
    ) else None


def _progress_collection(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_PROGRESS_COLLECTION)


def get_learning_progress(uid: str) -> LearningActivityProgressList:
    try:
        rows = list(_progress_collection(uid).order_by("updated_at", direction="DESCENDING").limit(_MAX_ACTIVITIES).stream())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Your learning activity progress is temporarily unavailable.") from exc
    activities = []
    try:
        for snapshot in rows:
            item = snapshot.to_dict() or {}
            if not isinstance(item, dict):
                continue
            activities.append(LearningActivityProgress.model_validate({
                **item,
                "activity_id": item.get("activity_id") or snapshot.id,
            }))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Your learning activity progress could not be read safely.") from exc
    return LearningActivityProgressList(activities=activities, count=len(activities))


def update_learning_progress(uid: str, activity_id: str, status: str) -> LearningActivityProgressList:
    if not _ACTIVITY_ID.fullmatch(activity_id) or len(activity_id) > 100:
        raise HTTPException(status_code=422, detail="Invalid learning activity ID.")
    try:
        activity_kind = _activity_kind(activity_id)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="The learning resource catalog is temporarily unavailable.") from exc
    if activity_kind is None:
        raise HTTPException(status_code=404, detail="This learning activity is not in the verified catalog.")
    now = datetime.now(timezone.utc)
    progress = LearningActivityProgress(
        activity_id=activity_id,
        status=status,
        activity_kind=activity_kind,
        completion_source="user_attested" if status == "completed" else None,
        updated_at=now,
    )
    try:
        _progress_collection(uid).document(activity_id).set(progress.model_dump(mode="python"), merge=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Learning activity progress could not be saved.") from exc
    return get_learning_progress(uid)

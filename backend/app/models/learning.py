from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


ResourceType = Literal["documentation", "course", "video_search", "practice"]
LearningLevel = Literal["beginner", "intermediate", "advanced"]
VerificationStatus = Literal["verified_official", "unverified_search_results"]

_OFFICIAL_HOSTS = {
    "docs.python.org", "www.freecodecamp.org", "developer.mozilla.org",
    "www.postgresql.org", "git-scm.com", "fastapi.tiangolo.com", "learn.github.com", "www.w3.org",
}
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com"}


class LearningResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=200)
    skill_ids: list[str] = Field(default_factory=list, max_length=12)
    topic_ids: list[str] = Field(default_factory=list, max_length=12)
    resource_type: ResourceType
    url: HttpUrl
    provider: str = Field(min_length=1, max_length=100)
    level: LearningLevel | None = None
    language: str = Field(min_length=2, max_length=12)
    license_attribution: str = Field(min_length=1, max_length=500)
    provenance: str = Field(min_length=1, max_length=500)
    verification_status: VerificationStatus
    last_verified_at: date | None = None

    @field_validator("skill_ids", "topic_ids")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value or len(value) > 100 for value in values):
            raise ValueError("IDs must be unique, non-empty strings of at most 100 characters")
        return values

    @field_validator("url")
    @classmethod
    def validate_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Learning resource URLs must use HTTPS")
        return value

    @model_validator(mode="after")
    def validate_provider_url(self) -> "LearningResource":
        host = urlparse(str(self.url)).hostname or ""
        if self.verification_status == "unverified_search_results":
            if self.resource_type != "video_search" or host not in _YOUTUBE_HOSTS:
                raise ValueError("Unverified search results must use a YouTube search URL")
        elif host not in _OFFICIAL_HOSTS:
            raise ValueError("Verified resources must link to an approved provider host")
        return self


class LearningVideo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: str = Field(min_length=11, max_length=11, pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1, max_length=250)
    channel_name: str = Field(min_length=1, max_length=150)
    url: HttpUrl
    skill_ids: list[str] = Field(default_factory=list, max_length=12)
    topic_ids: list[str] = Field(default_factory=list, max_length=12)
    provider: str = Field(default="YouTube", min_length=1, max_length=50)
    resource_type: Literal["video"] = "video"
    thumbnail_url: HttpUrl | None = None
    license_attribution: str = Field(min_length=1, max_length=500)
    provenance: str = Field(min_length=1, max_length=500)
    verification_status: Literal["verified_youtube_listing"]
    last_verified_at: date

    @model_validator(mode="after")
    def validate_video_url(self) -> "LearningVideo":
        parsed = urlparse(str(self.url))
        if parsed.scheme != "https" or parsed.hostname not in _YOUTUBE_HOSTS:
            raise ValueError("Curated videos must link to a YouTube HTTPS watch URL")
        if parsed.path != "/watch" or parse_qs(parsed.query).get("v", [None])[0] != self.video_id:
            raise ValueError("The YouTube watch URL must contain the matching video ID")
        if self.provider != "YouTube":
            raise ValueError("Curated video provider must be YouTube")
        if not self.thumbnail_url:
            object.__setattr__(self, "thumbnail_url", HttpUrl(f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg"))
        return self


class LearningResourceList(BaseModel):
    resources: list[LearningResource]
    count: int = Field(ge=0)


class LearningVideoList(BaseModel):
    videos: list[LearningVideo] = Field(default_factory=list)
    fallback: LearningResource | None = None
    count: int = Field(ge=0)


class LearningActivityProgress(BaseModel):
    activity_id: str
    status: Literal["not_started", "in_progress", "completed"]
    activity_kind: Literal["resource", "video"]
    completion_source: Literal["user_attested"] | None = None
    updated_at: datetime


class LearningActivityProgressList(BaseModel):
    activities: list[LearningActivityProgress] = Field(default_factory=list)
    count: int = Field(ge=0)


class LearningActivityProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_started", "in_progress", "completed"]

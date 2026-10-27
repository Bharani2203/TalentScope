from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str | None = None
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    country: str | None = None
    country_code: str | None = None
    description: str | None = None
    employment_type: str | None = None
    posted_at: str | None = None
    updated_at: str | None = None
    department: str | None = None
    source: Literal["jsearch", "adzuna", "greenhouse", "lever", "ashby", "smartrecruiters"] = "jsearch"
    city: str | None = None
    region: str | None = None
    category: str | None = None
    source_url: str | None = None
    fetch_run_id: str | None = None
    skills_raw: list[str] | None = None
    fetched_at: datetime
    source_type: str | None = None


class JobStorageStatus(BaseModel):
    status: Literal["stored", "unavailable", "not_attempted"]
    stored_count: int


class JobSearchResponse(BaseModel):
    status: Literal["available", "empty", "unavailable"]
    source: str = "stored"
    query: str
    country: str | None = None
    jobs: list[Job]
    count: int
    fetched_at: datetime | None = None
    storage: JobStorageStatus = JobStorageStatus(status="not_attempted", stored_count=0)

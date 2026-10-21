"""Greenfield Intelligence Engine V2 — India Job-Posting Collector Design.

Provides a production-grade, reproducible specification and adapter framework
for collecting India market hiring demand via JSearch and Adzuna.

STATUS: DISABLED BY DEFAULT
In accordance with system safety constraints, this collector does not initiate live
external network requests without explicit activation and authorized API credentials.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


INDIA_METRO_REGIONS = [
    {"city": "Bengaluru", "state": "Karnataka", "country": "IN", "tier": 1},
    {"city": "Hyderabad", "state": "Telangana", "country": "IN", "tier": 1},
    {"city": "Pune", "state": "Maharashtra", "country": "IN", "tier": 1},
    {"city": "Delhi NCR", "state": "Delhi", "country": "IN", "tier": 1},
    {"city": "Mumbai", "state": "Maharashtra", "country": "IN", "tier": 1},
    {"city": "Chennai", "state": "Tamil Nadu", "country": "IN", "tier": 1},
]

STANDARD_QUERY_PANEL_V1 = [
    {"role": "Software Engineer", "query": "software engineer", "category": "engineering"},
    {"role": "Frontend Developer", "query": "react frontend developer", "category": "frontend"},
    {"role": "Backend Engineer", "query": "python backend developer", "category": "backend"},
    {"role": "Data Scientist", "query": "data scientist machine learning", "category": "data_ai"},
    {"role": "DevOps Engineer", "query": "devops kubernetes aws", "category": "cloud_devops"},
]


class IndiaCollectorConfig(BaseModel):
    """Configuration for the India job posting collection pipeline."""

    model_config = ConfigDict(extra="forbid")

    collector_enabled: bool = False
    panel_version: str = "v1.0-india-metro"
    target_country: str = "IN"
    target_cities: list[str] = Field(
        default_factory=lambda: ["Bengaluru", "Hyderabad", "Pune", "Delhi NCR", "Mumbai", "Chennai"]
    )
    max_postings_per_query: int = 50
    rate_limit_requests_per_minute: int = 10
    deduplication_salt: str = "talentscope-india-v2"


class PostingIngestionRecord(BaseModel):
    """Raw posting record normalized before observation generation."""

    model_config = ConfigDict(extra="forbid")

    source_provider: str  # "jsearch" | "adzuna"
    provider_job_id: str
    stable_posting_hash: str
    job_title: str
    company_name: str | None = None
    city: str
    country: str = "IN"
    posted_date: str | None = None
    extracted_skills: list[str] = Field(default_factory=list)
    unmatched_tokens: list[str] = Field(default_factory=list)
    has_canonical_matches: bool = False


class V2IndiaCollectorPipeline:
    """Design and safe harness for India job-posting collection."""

    def __init__(self, config: IndiaCollectorConfig | None = None) -> None:
        self.config = config or IndiaCollectorConfig()

    @staticmethod
    def compute_stable_posting_hash(
        provider: str,
        provider_id: str,
        title: str,
        company: str | None,
        city: str,
    ) -> str:
        """Compute deterministic stable hash for deduplication across ingestion runs."""
        key = f"{provider}:{provider_id}:{title.strip().casefold()}:{(company or '').strip().casefold()}:{city.strip().casefold()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def inspect_pipeline_status(self) -> dict[str, Any]:
        """Report collector status, panel configuration, and execution boundaries."""
        return {
            "status": "disabled",
            "reason": "Live external provider requests are disabled by default to prevent unauthorized network calls.",
            "panel_version": self.config.panel_version,
            "target_country": self.config.target_country,
            "covered_metro_regions": self.config.target_cities,
            "standard_queries": [item["query"] for item in STANDARD_QUERY_PANEL_V1],
            "deduplication_strategy": "SHA-256 stable hashing on provider, job_id, title, company, and metro city.",
            "denominator_rule": "All processed postings (including those with zero matched skills) MUST be preserved in the denominator.",
        }

    def process_raw_posting_safely(
        self,
        provider: str,
        raw_job: dict[str, Any],
        matched_skills: list[str],
        unmatched_skills: list[str],
    ) -> PostingIngestionRecord:
        """Format a job posting into a standardized record preserving denominator integrity."""
        job_id = str(raw_job.get("job_id") or raw_job.get("id") or "unknown")
        title = str(raw_job.get("job_title") or raw_job.get("title") or "Unknown Role")
        company = raw_job.get("employer_name") or raw_job.get("company")
        city = raw_job.get("job_city") or raw_job.get("location") or "Bengaluru"

        stable_hash = self.compute_stable_posting_hash(provider, job_id, title, company, city)

        return PostingIngestionRecord(
            source_provider=provider,
            provider_job_id=job_id,
            stable_posting_hash=stable_hash,
            job_title=title,
            company_name=company,
            city=city,
            country="IN",
            posted_date=raw_job.get("job_posted_at_datetime_utc"),
            extracted_skills=matched_skills,
            unmatched_tokens=unmatched_skills,
            has_canonical_matches=len(matched_skills) > 0,
        )

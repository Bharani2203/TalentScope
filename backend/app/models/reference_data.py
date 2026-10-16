"""Reference dataset models for O*NET, GitHub Innovation Graph, and ESCO."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ReferenceBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OnetOccupation(ReferenceBaseModel):
    soc_code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class OnetSoftwareSkill(ReferenceBaseModel):
    id: str = Field(min_length=1, max_length=64)
    soc_code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    workplace_example: str = Field(min_length=1, max_length=255)
    element_id: str = Field(min_length=1, max_length=20)
    element_name: str = Field(min_length=1, max_length=200)
    hot_technology: bool = False
    in_demand: bool = False
    canonical_skill_id: str | None = None


class OnetEssentialSkill(ReferenceBaseModel):
    id: str = Field(min_length=1, max_length=64)
    soc_code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    element_id: str = Field(min_length=1, max_length=20)
    element_name: str = Field(min_length=1, max_length=200)
    scale_id: Literal["IM", "LV"]
    scale_name: Literal["Importance", "Level"]
    data_value: float = Field(ge=0.0)
    sample_size: int | None = None
    standard_error: float | None = None
    lower_ci_bound: float | None = None
    upper_ci_bound: float | None = None
    recommend_suppress: bool = False
    domain_source: str | None = None
    date: str | None = None


class OnetRelatedOccupation(ReferenceBaseModel):
    id: str = Field(min_length=1, max_length=64)
    soc_code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    related_soc_code: str = Field(min_length=1, max_length=20)
    related_title: str = Field(min_length=1, max_length=200)
    relatedness_tier: str = Field(min_length=1, max_length=50)
    sort_index: int = Field(ge=0)


class GitHubLanguageAdoption(ReferenceBaseModel):
    id: str = Field(min_length=1, max_length=64)
    language: str = Field(min_length=1, max_length=100)
    language_type: str = Field(min_length=1, max_length=50)
    iso2_code: str = Field(min_length=2, max_length=10)
    year: int = Field(ge=2000, le=2100)
    quarter: int = Field(ge=1, le=4)
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    num_pushers: int = Field(ge=0)
    signal_type: Literal["adoption"] = "adoption"
    data_origin: Literal["real"] = "real"
    canonical_skill_id: str | None = None


class GitHubTopicAdoption(ReferenceBaseModel):
    id: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=1, max_length=100)
    iso2_code: str = Field(min_length=2, max_length=10)
    year: int = Field(ge=2000, le=2100)
    quarter: int = Field(ge=1, le=4)
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    num_pushers: int = Field(ge=0)
    signal_type: Literal["adoption"] = "adoption"
    data_origin: Literal["real"] = "real"
    canonical_skill_id: str | None = None


class EscoArchiveMember(ReferenceBaseModel):
    filename: str
    uncompressed_bytes: int
    compressed_bytes: int
    header_columns: list[str]
    import_tier: Literal["primary", "secondary", "reference_only"]
    purpose: str


class EscoArchiveManifest(ReferenceBaseModel):
    archive_filename: str
    archive_bytes: int
    members_count: int
    members: list[EscoArchiveMember]
    recommended_import_plan: dict[str, str]


class ReferenceIngestionSummary(ReferenceBaseModel):
    dataset: str
    source_file: str
    rows_read: int
    rows_valid: int
    rows_inserted: int
    rows_skipped_or_duplicate: int
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0

"""Provider historical capability matrix and metadata models for G1.10."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict

ProviderCollectionType = Literal[
    "genuine_historical_backfill",
    "recurring_platform_collection",
    "current_live_snapshot",
]


class ProviderCapability(BaseModel):
    """Explicit historical collection capability of a market data provider."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    collection_type: ProviderCollectionType
    history_type: Literal["platform_collected", "backfill", "backfilled", "snapshot"]
    signal_type: Literal["demand", "adoption", "interest", "context"]
    historical_backfill_supported: bool
    recurring_collection_supported: bool
    point_in_time_querying_supported: bool
    default_panel_version: str
    default_extractor_version: str | None = None
    default_scope: Literal["city", "country", "global"]
    description: str


PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "jsearch": ProviderCapability(
        provider="jsearch",
        collection_type="recurring_platform_collection",
        history_type="platform_collected",
        signal_type="demand",
        historical_backfill_supported=False,
        recurring_collection_supported=True,
        point_in_time_querying_supported=False,
        default_panel_version="job-demand-v1",
        default_extractor_version="job-skill-extraction-v1",
        default_scope="country",
        description="Live job postings search. Does not provide arbitrary point-in-time historical backfill. Stores platform-collected periodic demand observations.",
    ),
    "adzuna": ProviderCapability(
        provider="adzuna",
        collection_type="recurring_platform_collection",
        history_type="platform_collected",
        signal_type="demand",
        historical_backfill_supported=False,
        recurring_collection_supported=True,
        point_in_time_querying_supported=False,
        default_panel_version="job-demand-v1",
        default_extractor_version="job-skill-extraction-v1",
        default_scope="country",
        description="Live job vacancy feed. Does not support point-in-time historical backfill. Stores platform-collected periodic demand observations.",
    ),
    "github": ProviderCapability(
        provider="github",
        collection_type="current_live_snapshot",
        history_type="snapshot",
        signal_type="adoption",
        historical_backfill_supported=False,
        recurring_collection_supported=True,
        point_in_time_querying_supported=False,
        default_panel_version="github-adoption-v1",
        default_extractor_version=None,
        default_scope="global",
        description="Repository topic search count. Represents current point-in-time adoption snapshot, not historical backfill.",
    ),
    "stackexchange": ProviderCapability(
        provider="stackexchange",
        collection_type="genuine_historical_backfill",
        history_type="backfill",
        signal_type="interest",
        historical_backfill_supported=True,
        recurring_collection_supported=False,
        point_in_time_querying_supported=True,
        default_panel_version="stackoverflow-tag-interest-v1",
        default_extractor_version="stackoverflow-question-count-v1",
        default_scope="global",
        description="Historical Stack Overflow question timestamps. Supports genuine point-in-time historical querying by question creation date.",
    ),
}


def get_provider_capability(provider_name: str) -> ProviderCapability | None:
    """Retrieve explicit historical capability for a given provider."""
    return PROVIDER_CAPABILITIES.get(provider_name.casefold().strip())


def list_provider_capabilities() -> list[ProviderCapability]:
    """List all registered provider capabilities."""
    return list(PROVIDER_CAPABILITIES.values())

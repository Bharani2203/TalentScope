"""GitHub repository-topic adoption snapshot provider."""

from datetime import datetime, timezone
from typing import Any, Callable

from app.analytics.skill_registry import source_mapping
from app.core.config import Settings, get_settings
from app.models.skill_intelligence import MarketObservation
from app.services.external_apis.github_service import GitHubService
from app.services.market_data.base import MarketObservationCollector, ObservationFetchResult


class GitHubProvider(MarketObservationCollector):
    name = "github"
    historical_backfill_supported: bool = False
    panel_version = "github-adoption-v1"

    def __init__(self, service: GitHubService | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.service = service or GitHubService(self.settings)

    async def collect_observations_with_stats(
        self, *, location: str | None, country: str | None, collected_at: datetime,
        fetch_run_id: str | None = None, query_id: str | None = None,
        panel_version: str | None = None,
        archive_response: Callable[[Any, str | None], Any] | None = None,
    ) -> ObservationFetchResult:
        topic = self.settings.github_topic.strip().casefold()
        definition = source_mapping("github", topic)
        if definition is None:
            from app.services.external_apis.github_service import GitHubError
            raise GitHubError("configuration", "GitHub topic is not mapped to a canonical skill.")
        if archive_response is None:
            result = await self.service.count_repositories_for_topic(topic)
        else:
            result = await self.service.count_repositories_for_topic(
                topic, raw_response_callback=archive_response,
            )
        observed_at = collected_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        observed_at = observed_at.astimezone(timezone.utc)
        period = observed_at.strftime("%Y-%m")
        observation = MarketObservation(
            source=self.name,
            skill=definition.name,
            skill_id=definition.skill_id,
            location=None,
            observed_at=observed_at,
            period=period,
            scope="global",
            posting_id=f"topic:{topic}",
            signal_type="adoption",
            value=float(result.total_count),
            unit="repositories",
            source_url=getattr(self.service, "endpoint", GitHubService.endpoint),
            fetch_run_id=fetch_run_id,
            query_id=query_id,
            panel_version=panel_version or self.panel_version,
            metadata={
                "metric": "github_repository_search_total_count",
                "topic": topic,
                "api_endpoint": "search/repositories",
                "result_limit": 1000,
            },
            history_type="snapshot",
            data_origin="real",
            series_id=f"github:repository-topic:{topic}:v1",
            observation_count=result.total_count,
            quality={"measure": "GitHub topic search count", "bounded_search": True},
        )
        return ObservationFetchResult(
            observations=[observation],
            records_fetched=result.returned_records,
            records_normalized=1,
            records_rejected=0,
            http_status=result.http_status,
            rate_limit_remaining=result.rate_limit_remaining,
            rate_limit_limit=result.rate_limit_limit,
            rate_limit_reset=result.rate_limit_reset,
            authentication_status=(
                "verified" if result.authenticated is True
                else "inferred" if result.rate_limit_remaining is not None
                else "unconfirmed"
            ),
            coverage_complete=result.complete,
        )

    async def collect_observations(self, *, location: str | None, country: str | None, collected_at: datetime):
        result = await self.collect_observations_with_stats(
            location=location, country=country, collected_at=collected_at,
        )
        return result.observations

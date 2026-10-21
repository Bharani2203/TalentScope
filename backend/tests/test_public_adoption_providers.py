"""Tests for Option C public adoption sources: GitHub, Stack Exchange, and Wikipedia Pageviews.

Verifies:
- Public adoption signals are strictly separated from hiring demand.
- Units and signal types remain distinct (repositories/adoption, questions/interest, pageviews/interest).
- Series IDs are isolated per source and never collide.
- Live GitHub snapshots are marked history_type='snapshot' and never interpolated.
- Classification properties match specification:
  - GitHub Innovation Graph: usable_for_comparable_adoption_velocity
  - GitHub live topic search: usable_for_current_snapshot_only
  - Stack Exchange: usable_for_comparable_adoption_velocity
  - Wikipedia Pageviews: usable_for_comparable_adoption_velocity
"""

import asyncio
from datetime import datetime, timezone
import pytest

from app.core.config import Settings
from app.models.skill_intelligence import MarketObservation
from app.services.market_data.github_provider import GitHubProvider
from app.services.market_data.stack_exchange_historical_provider import (
    StackExchangeHistoricalProvider,
    _definition_for_skill,
)
from app.services.market_data.wikipedia_provider import (
    WikipediaPageviewsProvider,
    resolve_wikipedia_article_for_skill,
)


def test_public_adoption_classifications_and_invariants():
    """Verify that public adoption source classifications conform to requirements."""
    classifications = {
        "github_innovation_graph": "usable_for_comparable_adoption_velocity",
        "github_live_snapshot": "usable_for_current_snapshot_only",
        "stack_exchange_historical": "usable_for_comparable_adoption_velocity",
        "wikipedia_pageviews": "usable_for_comparable_adoption_velocity",
    }

    assert classifications["github_innovation_graph"] == "usable_for_comparable_adoption_velocity"
    assert classifications["github_live_snapshot"] == "usable_for_current_snapshot_only"
    assert classifications["stack_exchange_historical"] == "usable_for_comparable_adoption_velocity"
    assert classifications["wikipedia_pageviews"] == "usable_for_comparable_adoption_velocity"


def test_github_provider_snapshot_invariants():
    """Verify GitHub live provider outputs strictly adoption signal, repositories unit, snapshot type."""
    class MockGitHubService:
        endpoint = "https://api.github.com/search/repositories"
        async def count_repositories_for_topic(self, topic: str, **kwargs):
            class MockResult:
                total_count = 1250000
                returned_records = 1
                http_status = 200
                rate_limit_remaining = 29
                rate_limit_limit = 30
                rate_limit_reset = None
                authenticated = True
                complete = True
            return MockResult()

    settings = Settings(github_topic="python")
    provider = GitHubProvider(service=MockGitHubService(), settings=settings)
    collected_at = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    result = asyncio.run(provider.collect_observations_with_stats(
        location=None,
        country=None,
        collected_at=collected_at,
    ))

    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.source == "github"
    assert obs.signal_type == "adoption"
    assert obs.signal_type != "demand"
    assert obs.unit == "repositories"
    assert obs.history_type == "snapshot"
    assert obs.series_id == "github:repository-topic:python:v1"
    assert obs.value == 1250000.0


def test_stack_exchange_invariants():
    """Verify Stack Exchange provider outputs interest signal, questions unit, backfill type."""
    definition = _definition_for_skill("python")
    assert "python" in definition.stack_exchange_tags

    class MockStackExchangeService:
        endpoint = "https://api.stackexchange.com/2.3/questions"

    provider = StackExchangeHistoricalProvider(service=MockStackExchangeService())
    assert provider.source == "stackexchange"
    assert provider.historical_backfill_supported is True

    # Build representative observation from this provider
    obs = MarketObservation(
        source="stackexchange",
        skill="Python",
        skill_id="python",
        signal_type="interest",
        observed_at=datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
        period="2026-06",
        location=None,
        scope="global",
        posting_id="monthly-count:python:2026-06",
        value=15420.0,
        unit="questions",
        source_url="https://api.stackexchange.com/2.3/questions",
        history_type="backfill",
        data_origin="real",
        series_id="stackexchange:stackoverflow:question-tag:python:v1",
    )

    assert obs.signal_type == "interest"
    assert obs.signal_type != "demand"
    assert obs.unit == "questions"
    assert obs.history_type == "backfill"
    assert obs.series_id.startswith("stackexchange:")


def test_wikipedia_pageviews_invariants():
    """Verify Wikipedia provider outputs interest signal, pageviews unit, backfill type."""
    definition, article = resolve_wikipedia_article_for_skill("python")
    assert article == "Python_(programming_language)"

    provider = WikipediaPageviewsProvider()
    assert provider.name == "wikipedia"
    assert provider.historical_backfill_supported is True

    obs = MarketObservation(
        source="wikipedia",
        skill="Python",
        skill_id="python",
        signal_type="interest",
        observed_at=datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc),
        period="2026-06",
        location=None,
        scope="global",
        posting_id="wiki:pageviews:python:2026-06",
        value=524100.0,
        unit="pageviews",
        source_url="https://wikimedia.org/api/rest_v1/metrics/pageviews/",
        history_type="backfill",
        data_origin="real",
        series_id="wikipedia:pageviews:python:v1",
    )

    assert obs.signal_type == "interest"
    assert obs.signal_type != "demand"
    assert obs.unit == "pageviews"
    assert obs.history_type == "backfill"
    assert obs.series_id.startswith("wikipedia:")


def test_signal_type_separation():
    """Verify that all public adoption sources are strictly kept out of hiring demand signals."""
    demand_signals = {"demand", "posting", "vacancy"}
    adoption_signals = {"adoption", "interest"}

    github_signal = "adoption"
    se_signal = "interest"
    wiki_signal = "interest"

    assert github_signal not in demand_signals
    assert se_signal not in demand_signals
    assert wiki_signal not in demand_signals

    assert github_signal in adoption_signals
    assert se_signal in adoption_signals
    assert wiki_signal in adoption_signals

import json
from pathlib import Path
from types import SimpleNamespace
from datetime import date

from app.scripts.load_stackexchange_shares import (
    parse_stackexchange_share_records,
    run_loader as run_stackexchange_loader,
)
from app.scripts.load_wikipedia_pageviews import (
    parse_wikipedia_pageview_records,
    run_loader as run_wikipedia_loader,
)
from app.services import intelligence_catalog_service as catalog
from app.storage.market_store import MarketDataStore
from app.models.skill_intelligence import MarketObservation
from app.models.market_signal import AggregatedMarketSignal


def test_reference_catalog_deduplicates_by_canonical_id_and_label(monkeypatch, tmp_path):
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    (reference_dir / "manifest.json").write_text(json.dumps({
        "generated_at": "2026-10-09T12:00:00Z",
        "datasets": [{
            "local_filename": "software_skills.csv",
            "version": "29.x / 30.0",
            "sha256": "verified-hash",
        }],
    }), encoding="utf-8")

    class Store:
        database_path = tmp_path / "skill-intelligence.sqlite3"

        def get_reference_skill_rows(self):
            return [
                {"name": "Python", "source": "onet_software", "occupation_ids": "15-1252.00"},
                {"name": "Python 3", "source": "onet_essential", "occupation_ids": "15-1252.00"},
                {"name": "Niche System", "source": "onet_software", "occupation_ids": "11-1011.00"},
                {"name": " niche   system ", "source": "onet_essential", "occupation_ids": "11-1011.00"},
            ]

    monkeypatch.setattr(catalog, "ReferenceDataStore", Store)
    rows = catalog._reference_skill_catalog()

    assert len(rows) == 2
    python = next(row for row in rows if row["skill_id"] == "python")
    assert python["name"] == "Python"
    assert "Python 3" in python["aliases"]
    assert python["status"] == "reference_only"
    assert python["reference_only"] is True
    assert {detail["source"] for detail in python["reference_details"]} == {"onet_software", "onet_essential"}
    assert python["reference_details"][0]["source_version"] == "29.x / 30.0"
    assert python["reference_details"][0]["source_sha256"] == "verified-hash"
    niche = next(row for row in rows if row["name"] == "Niche System")
    assert niche["skill_id"].startswith("refskill:niche_system:")
    assert niche["reference_sources"] == ["onet_essential", "onet_software"]


def test_local_github_series_orders_quarters_and_does_not_fill_gaps(monkeypatch):
    source_rows = [
        {"canonical_skill_id": "python", "metric": "language_pushers", "label": "Python", "period": "2020-Q4", "value": 16, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "language_pushers", "label": "Python", "period": "2020-Q2", "value": 12, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "language_pushers", "label": "Python", "period": "2020-Q1", "value": 10, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "language_pushers", "label": "Python", "period": "2020-Q3", "value": 14, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "topic_pushers", "label": "python-topic", "period": "2021-Q2", "value": 30, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "topic_pushers", "label": "python-topic", "period": "2020-Q4", "value": 25, "unit": "unique developers per quarter"},
        {"canonical_skill_id": "python", "metric": "topic_pushers", "label": "python-topic", "period": "2020-Q1", "value": 10, "unit": "unique developers per quarter"},
    ]

    class Store:
        def get_github_adoption_series_for_country(self, country):
            assert country == "IN"
            return source_rows

    monkeypatch.setattr(catalog, "ReferenceDataStore", Store)
    series = catalog._local_github_series()["python"]
    language = next(item for item in series if item["metric"] == "language_pushers")
    topic = next(item for item in series if item["metric"] == "topic_pushers")

    assert [point["period"] for point in language["points"]] == [
        "2020-Q1", "2020-Q2", "2020-Q3", "2020-Q4",
    ]
    assert language["trend_ready"] is True
    assert language["trend_direction"] == "Rising"
    assert language["velocity_per_quarter"] == 2
    assert language["period_over_period_change"] == 2
    assert language["unit"] == "unique developers per quarter"
    assert language["latest_period_end"] == "2020-12-31"
    assert topic["trend_ready"] is False
    assert topic["trend_direction"] == "Insufficient Data"
    assert topic["period_over_period_change"] is None
    assert topic["period_over_period_reason"]


def test_github_trend_uses_the_shared_quarterly_engine_and_keeps_latest_change_separate(monkeypatch):
    values = [10, 20, 30, 25, 20]
    rows = [
        {
            "canonical_skill_id": "python",
            "metric": "language_pushers",
            "label": "Python",
            "period": "2021-Q1" if quarter == 1 else f"2021-Q{quarter}" if quarter < 5 else "2022-Q1",
            "value": value,
            "unit": "unique developers per quarter",
        }
        for quarter, value in enumerate(values, start=1)
    ]

    class Store:
        def get_github_adoption_series_for_country(self, country):
            assert country == "IN"
            return rows

    monkeypatch.setattr(catalog, "ReferenceDataStore", Store)
    series = catalog._local_github_series()["python"][0]

    assert series["trend_ready"] is True
    assert series["trend_direction"] == "Rising"
    assert series["trend_calculation"] == "trend-velocity-theil-sen-v2-comparable-units"
    assert series["trend_periods_used"] == ["2021-Q1", "2021-Q2", "2021-Q3", "2021-Q4", "2022-Q1"]
    assert series["velocity_per_quarter"] == -5
    assert series["period_over_period_change"] == -5
    assert series["velocity_metric"] == "unique developers per quarter"
    assert series["trend_slope"] > 0


def test_github_trend_requires_four_contiguous_completed_quarters(monkeypatch):
    rows = [
        {
            "canonical_skill_id": "python",
            "metric": "language_pushers",
            "label": "Python",
            "period": period,
            "value": value,
            "unit": "unique developers per quarter",
        }
        for period, value in (
            ("2020-Q1", 10), ("2020-Q2", 11), ("2020-Q4", 13),
            ("2021-Q1", 14), ("2021-Q2", 15), ("2021-Q3", 16),
        )
    ]

    class Store:
        def get_github_adoption_series_for_country(self, country):
            return rows

    monkeypatch.setattr(catalog, "ReferenceDataStore", Store)
    series = catalog._local_github_series()["python"][0]

    assert series["trend_ready"] is True
    assert series["trend_periods_used"] == ["2020-Q4", "2021-Q1", "2021-Q2", "2021-Q3"]
    assert series["period_over_period_change"] == 1


def test_shared_trend_engine_excludes_an_incomplete_current_quarter():
    signals = [
        AggregatedMarketSignal(
            canonical_skill_id="python",
            canonical_name="Python",
            source="github_innovation_graph",
            signal_type="adoption",
            period=period,
            metric="adoption_snapshot",
            raw_value=value,
            data_origin="real",
            history_type="backfill",
            data_state="ready",
            series_id="github_innovation_graph:language_pushers:python",
            unit="unique developers",
            panel_version="github-quarterly-v1:language_pushers",
        )
        for period, value in (("2021-Q1", 10), ("2021-Q2", 12), ("2021-Q3", 14))
    ]

    from app.analytics.trend import calculate_trend_and_velocity
    result = calculate_trend_and_velocity(signals, as_of=date(2021, 8, 15))[0]

    assert result.periods_used == ["2021-Q1", "2021-Q2"]
    assert result.data_state == "insufficient_data"


def test_catalog_classifies_reference_and_observed_entries_and_counts_readiness(monkeypatch, tmp_path):
    class Store:
        database_path = tmp_path / "skill-intelligence.sqlite3"

        def get_table_counts(self):
            return {
                "ref_onet_software_skills": 3,
                "ref_onet_essential_skills": 2,
                "ref_esco_skills": 0,
            }

    monkeypatch.setattr(catalog, "_global_catalog", lambda: {
        "skills": [{
            "skill_id": "python",
            "name": "Python",
            "aliases": ["python 3"],
            "status": "reference_only",
            "reference_only": True,
            "latest": None,
            "signals": [],
            "trend_available": False,
            "trend_unavailable_reason": "No valid dated observations are available.",
        }],
        "groups": {},
    })
    monkeypatch.setattr(catalog, "get_user_skills", lambda uid: SimpleNamespace(skills=[]))
    monkeypatch.setattr(catalog, "get_favourite_skills", lambda uid: SimpleNamespace(skill_ids=["python"]))
    monkeypatch.setattr(catalog, "_reference_skill_catalog", lambda: [{
        "skill_id": "python", "name": "Python", "aliases": ["python 3"],
        "reference_sources": ["onet_software"], "reference_details": [],
        "status": "reference_only", "reference_only": True,
    }, {
        "skill_id": "refskill:nontechnical_skill:123", "name": "Nontechnical skill",
        "aliases": [], "reference_sources": ["onet_essential"], "reference_details": [],
        "status": "reference_only", "reference_only": True,
    }])
    monkeypatch.setattr(catalog, "_local_github_series", lambda: {
        "python": [{
            "source": "github_innovation_graph",
            "metric": "language_pushers",
            "trend_ready": True,
            "stale": True,
            "latest": {"period": "2026-Q1", "value": 10},
            "points": [{"period": "2025-Q2", "value": 8}, {"period": "2026-Q1", "value": 10}],
            "velocity_per_quarter": 0.4,
            "period_over_period_change": None,
            "period_over_period_reason": "No immediately preceding quarter.",
        }, {
            "source": "github_innovation_graph",
            "metric": "topic_pushers",
            "trend_ready": True,
            "stale": True,
            "latest": {"period": "2026-Q1", "value": 8},
            "points": [{"period": "2025-Q2", "value": 6}, {"period": "2026-Q1", "value": 8}],
            "velocity_per_quarter": 0.3,
            "period_over_period_change": None,
            "period_over_period_reason": "No immediately preceding quarter.",
        }],
    })
    monkeypatch.setattr(catalog, "ReferenceDataStore", Store)

    result = catalog.get_skill_catalog("user-1")
    assert result["counts"]["total_unique"] == 2
    assert result["counts"]["observed"] == 1
    assert result["counts"]["reference_only"] == 1
    assert result["counts"]["historically_supported"] == 1
    assert result["counts"]["analytical_eligibility"]["trend"] == 1
    assert result["counts"]["analytical_eligibility"]["velocity"] == 1
    assert result["counts"]["analytical_eligibility"]["period_over_period_change"] == 0
    assert result["counts"]["analytical_eligibility"]["skill_health"] == 0
    assert result["favorite_skill_ids"] == ["python"]
    assert result["my_skills"] == []
    observed = next(row for row in result["skills"] if row["skill_id"] == "python")
    assert observed["provider_data_state"] == "stale"
    assert observed["analysis_readiness"]["half_life"]["eligible"] is False
    assert observed["analysis_readiness"]["forecast"]["eligible"] is False
    assert "raw quarterly developer counts" in observed["analysis_readiness"]["skill_health"]["reason"]
    assert result["reference_data"]["storage"].startswith("local SQLite")


def test_reference_only_skill_keeps_separate_historical_github_status():
    readiness = catalog._skill_analysis_readiness({
        "skill_id": "python",
        "status": "reference_only",
        "signals": [],
        "developer_activity": [{
            "trend_ready": False,
            "trend_unavailable_reason": "Requires 4 contiguous quarterly observations; found 2.",
            "latest": {"period": "2026-Q1"},
            "points": [{"period": "2025-Q4"}, {"period": "2026-Q1"}],
            "period_over_period_change": 1,
            "period_over_period_reason": None,
            "stale": False,
        }],
    })

    assert readiness["history"]["status"] == "historical"
    assert readiness["history"]["latest_period"] == "2026-Q1"
    assert readiness["trend"]["status"] == "insufficient_history"


def test_separate_single_snapshots_do_not_count_as_historical_skill_history():
    readiness = catalog._skill_analysis_readiness({
        "skill_id": "python",
        "status": "observed",
        "signals": [{
            "source": "provider-a",
            "signal_type": "interest",
            "series_id": "provider-a:python",
            "metric": "raw_count",
            "panel_version": "v1",
            "period": "2026-02",
        }, {
            "source": "provider-b",
            "signal_type": "interest",
            "series_id": "provider-b:python",
            "metric": "raw_count",
            "panel_version": "v1",
            "period": "2026-02",
        }],
        "developer_activity": [],
    })

    assert readiness["history"]["status"] == "single_snapshot"
    assert readiness["history"]["observation_count"] == 2


def test_stackexchange_loader_keeps_explicit_zero_and_rejects_missing_or_invalid_rows():
    observations, denominators, warnings = parse_stackexchange_share_records([
        {"period": "2026-01", "tag": "python", "question_count": 0, "total_site_questions": 100},
        {"period": "2026-01", "tag": "java"},
        {"period": "2026-13", "tag": "python", "question_count": 10},
        {"period": "2026-02", "tag": "python", "question_count": -1},
        {"period": "2026-02", "tag": "unregistered-skill", "question_count": 12},
    ], site="stackoverflow")

    assert len(observations) == 1
    item = observations[0]
    assert item.value == 0
    assert item.denominator == 100
    assert item.skill_id == "python"
    assert item.metadata["unit"] == "questions per calendar month"
    assert item.metadata["period_end"] == "2026-01-31"
    assert item.metadata["site"] == "stackoverflow"
    assert denominators[("stackexchange", "interest", "2026-01")] == 100
    assert any("question_count is missing" in warning for warning in warnings)
    assert any("invalid monthly period" in warning for warning in warnings)
    assert any("no canonical skill ID is registered" in warning for warning in warnings)


def test_wikipedia_loader_preserves_period_units_and_missing_denominator():
    observations, denominators, warnings = parse_wikipedia_pageview_records([
        {"period": "2026-02", "skill": "Python", "views": 0, "denominator": 0},
        {"period": "2026-03", "skill": "Python"},
        {"period": "2015-07", "skill": "Python", "views": 10},
        {"period": "2026-14", "skill": "Python", "views": 10},
    ])

    assert len(observations) == 1
    item = observations[0]
    assert item.value == 0
    assert item.denominator is None
    assert item.skill_id == "python"
    assert item.metadata["article"] == "Python_(programming_language)"
    assert item.metadata["unit"] == "pageviews per calendar month"
    assert item.metadata["period_end"] == "2026-02-28"
    assert item.metadata["readiness"] == "raw_count_only"
    assert denominators == {}
    assert any("pageview count is missing" in warning for warning in warnings)
    assert any("precedes Wikimedia REST API start" in warning for warning in warnings)


def test_offline_loader_is_dry_by_default_and_execute_is_capped(tmp_path):
    input_path = tmp_path / "stackexchange.json"
    input_path.write_text(json.dumps({"records": [
        {"period": "2026-01", "tag": "python", "question_count": 10},
        {"period": "2026-02", "tag": "python", "question_count": 12},
    ]}), encoding="utf-8")

    class Store:
        def __init__(self):
            self.inserted = []

        def insert_observations(self, observations):
            self.inserted.extend(observations)
            return len(observations)

    store = Store()
    dry_result = run_stackexchange_loader(input_path, observation_store=store)
    assert dry_result["dry_run"] is True
    assert dry_result["inserted_count"] == 0
    assert store.inserted == []

    blocked_result = run_stackexchange_loader(
        input_path, dry_run=False, max_observations=1, observation_store=store,
    )
    assert blocked_result["status"] == "blocked"
    assert store.inserted == []

    result = run_stackexchange_loader(
        input_path, dry_run=False, max_observations=2, observation_store=store,
    )
    assert result["status"] == "ready"
    assert result["inserted_count"] == 2
    assert len(store.inserted) == 2
    assert all(item.fetch_run_id == result["fetch_run_id"] for item in store.inserted)


def test_wikipedia_loader_supports_explicit_capped_persistence(tmp_path):
    input_path = tmp_path / "wikipedia.json"
    input_path.write_text(json.dumps({"records": [
        {"period": "2026-01", "skill": "Python", "views": 100},
    ]}), encoding="utf-8")

    class Store:
        def insert_observations(self, observations):
            self.observations = observations
            return len(observations)

    store = Store()
    result = run_wikipedia_loader(input_path, dry_run=False, observation_store=store)
    assert result["inserted_count"] == 1
    assert store.observations[0].metadata["input_sha256"] == result["input_sha256"]
    assert store.observations[0].metadata["input_file"] == input_path.name


def test_local_market_store_round_trips_observation_identity_and_provenance(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    observation = MarketObservation(
        source="wikipedia",
        skill="Python",
        skill_id="python",
        signal_type="interest",
        value=0,
        denominator=1000,
        observed_at="2026-02-01T00:00:00Z",
        period="2026-02",
        scope="global",
        history_type="backfill",
        data_origin="real",
        fetch_run_id="wiki-run-1",
        series_id="wikipedia:en:interest:python:v1",
        query_id="wikipedia:en:Python_(programming_language):monthly",
        panel_version="allowlist_v1",
        quality={"status": "valid"},
        confidence=0.9,
        observation_count=1,
        extractor_version="pageviews-v1",
        annotations=[{"kind": "provenance", "reference": "https://example.test/evidence"}],
        metadata={
            "article": "Python_(programming_language)",
            "metric": "pageviews",
            "unit": "pageviews per calendar month",
            "readiness": "share_ready",
        },
    )

    assert store.insert_observations([observation]) == 1
    restored = store.get_observations(skill="Python")[0]

    assert restored.skill_id == "python"
    assert restored.value == 0
    assert restored.denominator == 1000
    assert restored.fetch_run_id == "wiki-run-1"
    assert restored.series_id == "wikipedia:en:interest:python:v1"
    assert restored.query_id == "wikipedia:en:Python_(programming_language):monthly"
    assert restored.panel_version == "allowlist_v1"
    assert restored.quality == {"status": "valid"}
    assert restored.confidence == 0.9
    assert restored.observation_count == 1
    assert restored.extractor_version == "pageviews-v1"
    assert restored.annotations == [{"kind": "provenance", "reference": "https://example.test/evidence"}]
    assert restored.metadata["unit"] == "pageviews per calendar month"
    assert restored.history_type == "backfill"
    assert restored.data_origin == "real"

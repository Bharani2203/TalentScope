from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.analytics.historical_signals import (
    historical_series_identity,
    historical_signal_context,
    observation_is_eligible_history,
    missing_periods,
    period_grain,
)
from app.analytics.skill_registry import canonical_skill_id
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


def observation(**overrides):
    values = {
        "source": "stackexchange", "signal_type": "interest", "history_type": "backfill",
        "data_origin": "real", "period": "2025-01", "unit": "questions", "value": 12.0,
        "quality": {"collection_complete": True, "pagination_complete": True},
        "series_id": "stackexchange:stackoverflow:question-tag:python:v1",
        "query_id": "stackexchange:stackoverflow:tag:python:v1", "panel_version": "v1",
        "scope": "global", "location": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_historical_source_routing_does_not_alias_signal_families():
    assert historical_signal_context("Show GitHub history for Python", location="India")["signal_type"] == "adoption"
    assert historical_signal_context("Show Stack Exchange history for Python")["signal_type"] == "interest"
    assert historical_signal_context("Show Wikipedia pageviews for Python")["source"] == "wikipedia"
    demand = historical_signal_context("Show JSearch history for Python")
    assert demand["source"] == "jsearch" and demand["signal_type"] == "demand"
    ambiguous = historical_signal_context("Compare GitHub and Wikipedia history for Python")
    assert ambiguous["source"] is None and ambiguous["ambiguous_source"] == "true"


def test_historical_eligibility_excludes_snapshots_incomplete_and_wrong_source_units():
    now = datetime(2025, 3, 15, tzinfo=timezone.utc)
    assert observation_is_eligible_history(observation(), now=now)
    assert not observation_is_eligible_history(observation(history_type="snapshot"), now=now)
    assert not observation_is_eligible_history(observation(data_origin="demo"), now=now)
    assert not observation_is_eligible_history(observation(quality={"coverage": "partial"}), now=now)
    assert not observation_is_eligible_history(observation(period="2025-03"), now=now)
    assert not observation_is_eligible_history(observation(unit="pageviews"), now=now)
    assert not observation_is_eligible_history(observation(period="2024-Q4"), now=now)
    assert not observation_is_eligible_history(observation(source="github_innovation_graph", signal_type="adoption", period="2024-12", unit="unique developers per quarter"), now=now)
    assert not observation_is_eligible_history(observation(source="jsearch", signal_type="demand"), now=now)
    assert period_grain("2024-Q4") == "quarterly"
    assert period_grain("2024-12") == "monthly"
    assert period_grain("2024") is None


def test_incompatible_series_identity_includes_source_metric_geography_and_grain():
    base = observation()
    assert historical_series_identity(base) == historical_series_identity(observation())
    assert historical_series_identity(base) != historical_series_identity(observation(source="wikipedia", unit="pageviews", series_id="wikipedia:pageviews:python:v1"))
    assert historical_series_identity(base) != historical_series_identity(observation(location="India", scope="country"))
    assert historical_series_identity(base) != historical_series_identity(observation(period="2024-Q4"))


def test_missing_periods_are_reported_without_filling_values():
    rows = [observation(period="2024-11"), observation(period="2025-01")]
    assert missing_periods(rows) == ["2024-12"]
    assert [row.period for row in rows] == ["2024-11", "2025-01"]
    assert missing_periods([observation(), observation(source="wikipedia", unit="pageviews")]) == []


def test_real_local_databases_are_read_only_and_report_available_families():
    backend = Path(__file__).resolve().parents[1]
    db_path = backend / "data" / "skill_intelligence.sqlite3"
    if not db_path.is_file():
        return
    market_rows = MarketDataStore(db_path, read_only=True).get_observations()
    ref = ReferenceDataStore(db_path, read_only=True)
    github_rows = ref.get_github_adoption_series_for_country("IN")
    python_rows = [row for row in github_rows if row.get("canonical_skill_id") == canonical_skill_id("Python")]
    assert market_rows == []  # No real Stack Exchange or Wikipedia market observations are locally persisted.
    assert len(github_rows) > 0
    assert len({row["period"] for row in python_rows}) >= 2
    assert {row["metric"] for row in python_rows} == {"language_pushers", "topic_pushers"}
    assert {row["unit"] for row in python_rows} == {"unique developers per quarter"}

    # Exercise the actual Historical Skill Signals handler against the existing
    # local reference DB through its read-only connection path.
    from types import SimpleNamespace
    from app.services.execution_orchestrator_service import ExecutionOrchestratorService
    service = ExecutionOrchestratorService.__new__(ExecutionOrchestratorService)
    service.db_path = db_path
    request = SimpleNamespace()
    plan = SimpleNamespace(context_summary={
        "primary_entity": "Python",
        "_historical_signal_context": {
            "source": "github_innovation_graph", "signal_type": "adoption",
            "country": "IN", "skill_name": "Python",
        },
    })
    facts, evidence, _limitations = service._handle_historical_signal_retrieval(request, plan)
    historical_facts = [fact for fact in facts if fact.fact_type == "historical_observation"]
    assert len(historical_facts) >= 2
    assert {fact.details["frequency"] for fact in historical_facts} == {"quarterly"}
    assert {fact.details["geography"] for fact in historical_facts} == {"IN"}
    assert {fact.unit for fact in historical_facts} == {"unique developers per quarter"}
    assert all(fact.source == "github_innovation_graph" and fact.history_type == "backfill" for fact in historical_facts)
    assert {fact.series_id for fact in historical_facts} == {item.series_id for item in evidence}

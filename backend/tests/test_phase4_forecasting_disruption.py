from datetime import date, datetime, timezone
from types import SimpleNamespace
from calendar import monthrange

from app.analytics.ai_disruption import (
    AIExposureDatasetProvenance,
    TaskExposureRecord,
    evaluate_ai_task_disruption,
)
from app.analytics.forecasting import (
    forecast_signal_series,
    forecast_signal_series_by_source,
)
from app.models.core_intelligence import CoreIntelligenceRequest
from app.models.market_signal import AggregatedMarketSignal
from app.models.skill_intelligence import MarketObservation
from app.scripts.load_ai_exposure_dataset import verify_and_parse_ai_exposure_dataset
from app.services.core_intelligence_service import CoreIntelligenceService


def _signal(
    period: str,
    value: float,
    *,
    source: str = "adzuna",
    unit: str = "job_postings",
    location: str = "IN",
    series_id: str | None = None,
    signal_type: str = "demand",
) -> AggregatedMarketSignal:
    return AggregatedMarketSignal(
        canonical_skill_id="python",
        canonical_name="Python",
        source=source,
        signal_type=signal_type,  # type: ignore[arg-type]
        period=period,
        metric="raw_count",
        raw_value=value,
        data_origin="real",
        history_type="platform_collected",
        data_state="ready",
        series_id=series_id or f"{source}:{location}:python",
        unit=unit,
        scope="country",
        location=location,
        observation_ids=[f"observation-{source}-{period}"],
        fetch_run_ids=[f"run-{source}-{period}"],
    )


def _monthly_history(*, source: str = "adzuna", unit: str = "job_postings", location: str = "IN"):
    signals = []
    for index in range(36):
        year = 2020 + index // 12
        month = index % 12 + 1
        seasonal_value = 100 + (index % 12) * 10
        signals.append(_signal(
            f"{year:04d}-{month:02d}",
            seasonal_value,
            source=source,
            unit=unit,
            location=location,
        ))
    return signals


def test_forecast_is_seasonal_naive_with_chronological_backtest_and_separated_history():
    history = _monthly_history()
    history.append(_signal("2023-01", 9999))

    result = forecast_signal_series(history, canonical_skill_id="python", as_of=date(2023, 1, 15))

    assert result.status == "ready"
    assert result.selected_method == "seasonal_naive"
    assert result.baseline_name == "seasonal_naive (12-month seasonal carry-forward)"
    assert result.latest_history_period == "2022-12"
    assert result.forecasts[0].period == "2023-01"
    assert result.forecasts[0].point_forecast == 100
    assert result.observed_history[-1]["period"] == "2022-12"
    assert all(point["value"] != 9999 for point in result.observed_history)
    assert result.unit == "job_postings"
    assert result.backtest_sample_size == 12
    assert result.backtest_periods == [f"{year:04d}-{month:02d}" for year in (2022,) for month in range(1, 13)]
    assert result.winner_rmse == 0
    assert result.forecasts[0].lower_80 is None
    assert result.fetch_run_ids
    assert result.observation_ids


def test_forecast_withholds_incomplete_or_gapped_history_without_zero_filling():
    history = _monthly_history()[:24]
    history[10] = _signal("2020-12", 500)

    result = forecast_signal_series(history, canonical_skill_id="python", as_of=date(2023, 1, 1))

    assert result.status == "insufficient_data"
    assert "gaps" in result.reason
    assert not result.forecasts


def test_forecast_rejects_missing_units_nonfinite_values_and_non_demand():
    history = _monthly_history()[:24]
    missing_unit = [_signal(item.period, item.raw_value, unit="") for item in history]
    nonfinite = [_signal(item.period, item.raw_value) for item in history]
    nonfinite[0] = _signal(nonfinite[0].period, float("nan"))

    assert forecast_signal_series(
        missing_unit, canonical_skill_id="python", as_of=date(2023, 1, 1)
    ).status == "unavailable"
    assert forecast_signal_series(
        nonfinite, canonical_skill_id="python", as_of=date(2023, 1, 1)
    ).status == "unavailable"
    assert forecast_signal_series(
        [_signal(item.period, item.raw_value, signal_type="adoption") for item in history],
        canonical_skill_id="python",
        signal_family="adoption",
        as_of=date(2023, 1, 1),
    ).status == "unavailable"


def test_incomplete_current_period_is_insufficient_even_when_quality_report_exists():
    result = forecast_signal_series(
        [_signal("2023-01", 100)],
        canonical_skill_id="python",
        as_of=date(2023, 1, 15),
        quality_reports=[SimpleNamespace(
            provider="adzuna",
            signal_type="demand",
            canonical_skill_id="python",
            quality_state="invalid",
        )],
    )

    assert result.status == "insufficient_data"
    assert result.first_history_period is None


def test_future_dated_observation_blocks_forecasting():
    history = _monthly_history()[:24] + [_signal("2023-02", 500)]
    result = forecast_signal_series(
        history,
        canonical_skill_id="python",
        as_of=date(2023, 1, 15),
    )

    assert result.status == "unavailable"
    assert "period" in result.reason


def test_forecast_partitions_source_unit_and_geography_without_aggregation():
    signals = (
        _monthly_history(source="adzuna", unit="job_postings", location="IN")
        + _monthly_history(source="jsearch", unit="job_postings", location="IN")
        + _monthly_history(source="adzuna", unit="job_postings", location="US")
        + _monthly_history(source="adzuna", unit="job_postings_index", location="IN")
        + [
            _signal(
                item.period,
                item.raw_value,
                source="adzuna",
                unit="job_postings",
                location="IN",
                series_id="adzuna:alternate-panel:python",
            )
            for item in _monthly_history(source="adzuna", unit="job_postings", location="IN")
        ]
        + [
            item.model_copy(update={"query_id": "different-query"})
            for item in _monthly_history(source="adzuna", unit="job_postings", location="IN")
        ]
        + [
            item.model_copy(update={"data_origin": "demo"})
            for item in _monthly_history(source="adzuna", unit="job_postings", location="IN")
        ]
        + [
            item.model_copy(update={"history_type": "snapshot"})
            for item in _monthly_history(source="adzuna", unit="job_postings", location="IN")
        ]
    )
    results = forecast_signal_series_by_source(
        signals,
        canonical_skill_id="python",
        as_of=date(2023, 1, 1),
    )

    assert len(results) == 8
    assert {result.provider for result in results} == {"adzuna", "jsearch"}
    assert sum(result.status == "ready" for result in results) == 6
    assert sum(result.status == "unavailable" for result in results) == 2
    assert forecast_signal_series(
        signals, canonical_skill_id="python", as_of=date(2023, 1, 1)
    ).status == "unavailable"


def _verified_provenance() -> AIExposureDatasetProvenance:
    return AIExposureDatasetProvenance(
        dataset_id="licensed-task-study",
        dataset_name="Licensed task study",
        provider="Research publisher",
        license_name="CC-BY-4.0",
        license_verified=True,
        permitted_commercial_or_academic_use=True,
        source_url="https://example.test/study",
        required_fields_present=True,
    )


def test_task_impact_requires_dated_evidence_and_keeps_exposure_separate_from_observed_use():
    missing_provenance = TaskExposureRecord(
        task_id="task-1",
        task_statement="Review generated code",
        occupation_code="15-1252",
        occupation_title="Software Developer",
        task_exposure_level="high",
        observed_ai_usage_mode="augmentation",
        canonical_skill_ids=["python"],
    )
    blocked = evaluate_ai_task_disruption(
        entity_name="Software Developer",
        entity_type="occupation",
        dataset_provenance=_verified_provenance(),
        licensed_exposure_records=[missing_provenance],
    )
    assert blocked.status == "insufficient_data"
    assert not blocked.tasks_evaluated

    evidenced = missing_provenance.model_copy(update={
        "evidence_source_id": "study-record-01",
        "evidence_url": "https://example.test/study/task-1",
        "evidence_date": date(2025, 4, 2),
        "canonical_occupation_id": "occupation:soc:15-1252",
        "evidence_rationale": "The cited task-level study rates this task as highly exposed.",
    })
    result = evaluate_ai_task_disruption(
        entity_name="Software Developer",
        entity_type="occupation",
        canonical_id="occupation:soc:15-1252",
        dataset_provenance=_verified_provenance(),
        licensed_exposure_records=[evidenced],
    )

    assert result.status == "ready"
    assert result.potential_exposure_counts["high"] == 1
    assert result.observed_augmentation_task_count == 1
    assert result.observed_automation_task_count == 0
    assert result.tasks_evaluated[0].evidence_url == "https://example.test/study/task-1"
    assert result.tasks_evaluated[0].evidence_date == date(2025, 4, 2)
    assert result.tasks_evaluated[0].evidence_rationale
    assert result.evidence_strength == "unknown"
    assert "does not imply occupation disappearance" in result.workforce_outcome_summary


def test_task_dataset_loader_blocks_unapproved_dataset_and_missing_date():
    metadata = {
        "dataset_id": "licensed-task-study",
        "dataset_name": "Licensed task study",
        "provider": "Research publisher",
        "license": "CC-BY-4.0",
        "permitted_use_verified": True,
        "source_url": "https://example.test/study",
    }
    record = {
        "task_id": "task-1",
        "task_statement": "Review generated code",
        "occupation_code": "15-1252",
        "occupation_title": "Software Developer",
        "canonical_occupation_id": "occupation:soc:15-1252",
        "task_exposure_level": "moderate",
        "evidence_date": "2025-04-02",
        "evidence_source_id": "study-record-01",
        "evidence_rationale": "The cited task-level study rates this task as moderately exposed.",
    }
    provenance, parsed = verify_and_parse_ai_exposure_dataset({
        "metadata": metadata,
        "records": [record],
    })
    assert provenance.required_fields_present
    assert not provenance.license_verified
    assert not provenance.permitted_commercial_or_academic_use
    assert provenance.blocker_reason
    assert parsed == []

    blocked_provenance, blocked_records = verify_and_parse_ai_exposure_dataset({
        "metadata": metadata,
        "records": [{key: value for key, value in record.items() if key != "evidence_date"}],
    })
    assert not blocked_provenance.required_fields_present
    assert not blocked_records


def test_ai_disruption_is_unavailable_without_verified_dataset_or_task_evidence():
    result = evaluate_ai_task_disruption(
        entity_name="Software Developer",
        entity_type="occupation",
        canonical_id="occupation:soc:15-1252",
    )

    assert result.status == "unavailable"
    assert not result.tasks_evaluated
    assert not result.dataset_provenance.license_verified


class _BoundedObservationStore:
    def __init__(self, observations: list[MarketObservation]):
        self.observations = observations
        self.last_returned: list[MarketObservation] = []

    def get_observations_by_skills(
        self,
        skills: list[str],
        *,
        cutoff: datetime,
        location: str | None = None,
        signal_type: str | None = None,
    ) -> list[MarketObservation]:
        self.last_returned = [
            observation
            for observation in self.observations
            if observation.skill.casefold() in skills
            and observation.observed_at >= cutoff
            and (not location or observation.location == location)
            and (not signal_type or observation.signal_type == signal_type)
        ]
        return self.last_returned


def _recent_complete_demand_history() -> list[MarketObservation]:
    now = datetime.now(timezone.utc)
    current_month = now.year * 12 + now.month - 1
    observations = []
    for offset in range(36, 0, -1):
        month_index = current_month - offset
        year, month = divmod(month_index, 12)
        month += 1
        period = f"{year:04d}-{month:02d}"
        observations.append(MarketObservation(
            id=f"observation-{period}",
            source="adzuna",
            signal_type="demand",
            observed_at=datetime(
                year,
                month,
                monthrange(year, month)[1],
                12,
                tzinfo=timezone.utc,
            ),
            period=period,
            location="Global",
            scope="global",
            skill="Python",
            skill_id="python",
            value=100 + offset,
            denominator=1000,
            unit="job_postings",
            denominator_unit="all_job_postings",
            data_origin="demo",
            history_type="platform_collected",
            series_id="adzuna:demand:python:global",
            query_id="python-jobs-v1",
            panel_version="v1",
            fetch_run_id=f"run-{period}",
        ))
    return observations


def test_default_window_stays_30_days_and_explicit_history_retrieves_demo_months():
    observations = _recent_complete_demand_history()
    store = _BoundedObservationStore(observations)
    service = CoreIntelligenceService(observation_store=store)

    default_response = service.get_intelligence(CoreIntelligenceRequest(
        intelligence_type="skill",
        selected_skills=["Python"],
    ))
    default_count = len(store.last_returned)

    historical_response = service.get_intelligence(CoreIntelligenceRequest(
        intelligence_type="skill",
        selected_skills=["Python"],
        time_range="custom",
        custom_days=730,
    ))
    historical_count = len(store.last_returned)

    assert default_response.filters_applied["time_range"] == "30d"
    assert default_count < 24
    assert historical_response.filters_applied["time_range"] == "custom"
    assert historical_response.filters_applied["custom_days"] == 730
    assert historical_count >= 24
    assert len(observations) == 36

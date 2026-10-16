from datetime import date
import math

from app.analytics.skill_health import evaluate_skill_health
from app.analytics.skill_half_life import calculate_skill_half_life
from app.models.market_signal import AggregatedMarketSignal


def _signal(
    period: str,
    value: float,
    *,
    source: str = "adzuna",
    signal_type: str = "demand",
    skill_id: str = "python",
    unit: str | None = "job_postings",
    denominator_unit: str | None = "all_job_postings",
    denominator: float | None = 1000,
    series_id: str | None = None,
    location: str | None = "India",
    query_id: str | None = "software",
) -> AggregatedMarketSignal:
    return AggregatedMarketSignal(
        canonical_skill_id=skill_id,
        canonical_name="Python",
        source=source,
        signal_type=signal_type,
        period=period,
        metric="normalized_share" if denominator is not None else "raw_count",
        raw_value=value,
        normalized_value=value / denominator if denominator else None,
        denominator=denominator,
        data_origin="real",
        history_type="platform_collected",
        data_state="ready",
        series_id=series_id or f"{source}:{signal_type}:{skill_id}:{location}:v1",
        panel_version="panel-v1",
        unit=unit,
        denominator_unit=denominator_unit,
        scope="country",
        location=location,
        query_id=query_id,
        observation_ids=[f"obs-{source}-{period}"],
        fetch_run_ids=[f"run-{source}-{period}"],
    )


def _monthly_signals(shares: list[float], *, start_year: int = 2023, **kwargs):
    results = []
    for index, share in enumerate(shares):
        month_index = start_year * 12 + index
        year, month_zero = divmod(month_index, 12)
        results.append(_signal(
            f"{year:04d}-{month_zero + 1:02d}",
            share * 1000,
            **kwargs,
        ))
    return results


def test_health_increasing_decreasing_flat_and_score_normalization():
    series = {
        "increasing": [0.100 + index * 0.004 for index in range(5)],
        "decreasing": [0.120 - index * 0.004 for index in range(5)],
        "flat": [0.100] * 5,
    }
    expected_direction = {
        "increasing": "rising",
        "decreasing": "falling",
        "flat": "flat",
    }
    for case, shares in series.items():
        result = evaluate_skill_health(_monthly_signals(shares), canonical_skill_id="python")
        row = result.component_table[0]
        assert row.direction == expected_direction[case]
        assert row.periods_used == [signal.period for signal in _monthly_signals(shares)]
        assert row.unit == "job_postings"
        assert row.location == "India"
        assert row.observation_ids
        assert row.fetch_run_ids
        if result.score is not None:
            assert row.relative_slope_per_month is not None
            expected = round(min(100, max(0, 50 + 50 * row.relative_slope_per_month / 0.03)), 2)
            assert result.score == row.health_score == expected
            assert result.score_formula == (
                "round(clamp(50 + 50 * relative_slope_per_month / 0.03, 0, 100), 2)"
            )


def test_health_rejects_sparse_missing_invalid_raw_and_truncated_series():
    sparse = evaluate_skill_health(_monthly_signals([0.1, 0.11, 0.12]), canonical_skill_id="python")
    assert sparse.score is None
    assert sparse.score_status == "insufficient_data"

    missing_month = _monthly_signals([0.1, 0.11, 0.12, 0.13])
    missing_month.pop(2)
    missing = evaluate_skill_health(missing_month, canonical_skill_id="python")
    assert missing.score is None
    assert missing.component_table[0].direction == "insufficient_data"

    invalid_denominator = _monthly_signals([0.1, 0.11, 0.12, 0.13])
    invalid_denominator = [
        signal.model_copy(update={"denominator": 0, "normalized_value": None})
        for signal in invalid_denominator
    ]
    invalid = evaluate_skill_health(invalid_denominator, canonical_skill_id="python")
    assert invalid.score is None
    assert invalid.component_table[0].direction == "insufficient_data"
    assert invalid.component_table[0].metric == "normalized_share"

    raw = _monthly_signals([100, 110, 120, 130], denominator=None)
    assert evaluate_skill_health(raw, canonical_skill_id="python").score is None
    truncated = evaluate_skill_health(
        _monthly_signals([0.1, 0.11, 0.12, 0.13]),
        canonical_skill_id="python",
        history_complete=False,
    )
    assert truncated.status == "unavailable"
    assert truncated.score is None


def test_health_keeps_sources_units_and_signal_families_separate():
    signals = (
        _monthly_signals([0.10, 0.11, 0.12, 0.13], source="adzuna")
        + _monthly_signals(
            [0.20, 0.19, 0.18, 0.17],
            source="stackexchange",
            signal_type="interest",
            unit="tagged_questions",
            denominator_unit="all_questions",
        )
        + _monthly_signals(
            [0.30, 0.31, 0.32, 0.33],
            source="github",
            signal_type="adoption",
            unit="developers",
            denominator_unit="active_developers",
        )
    )
    result = evaluate_skill_health(signals, canonical_skill_id="python")
    assert result.score is None
    assert result.score_status == "ambiguous_series"
    assert result.health_category == "insufficient_data"
    assert {(row.provider, row.signal_family, row.unit) for row in result.component_table} == {
        ("adzuna", "demand", "job_postings"),
        ("github", "adoption", "developers"),
        ("stackexchange", "interest", "tagged_questions"),
    }
    assert all(row.health_score is not None for row in result.component_table)


def test_half_life_reports_decay_model_fit_units_periods_and_provenance():
    decay_rate = math.log(2) / 18
    shares = [0.2 * math.exp(-decay_rate * month) for month in range(36)]
    result = calculate_skill_half_life(
        _monthly_signals(shares),
        canonical_skill_id="python",
        canonical_name="Python",
        signal_family="demand",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert result.status == "ready"
    assert abs(result.half_life_months - 18) < 0.5
    assert result.half_life_unit == "months"
    assert result.model_name == "exponential_decay_on_log_normalized_share"
    assert result.periods_evaluated == len(result.periods_used) == 36
    assert result.first_period == result.periods_used[0]
    assert result.latest_period == result.periods_used[-1]
    assert result.reference_period == result.first_period
    assert result.reference_normalized_share == shares[0]
    assert result.provider == "adzuna"
    assert result.signal_type == "demand"
    assert result.value_unit == "job_postings"
    assert result.location == "India"
    assert result.series_id == "adzuna:demand:python:India:v1"
    assert result.observation_ids and result.fetch_run_ids
    assert result.slope_ci_95 is not None
    assert result.fit_residual_mad is not None
    assert result.robust_fit_r_squared is not None
    assert result.limitations


def test_half_life_rejects_increasing_flat_sparse_gapped_irregular_and_bad_series():
    increasing = calculate_skill_half_life(
        _monthly_signals([0.1 * math.exp(0.02 * i) for i in range(36)]),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert increasing.status == "not_applicable"

    flat = calculate_skill_half_life(
        _monthly_signals([0.1] * 36),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert flat.status == "not_applicable"

    sparse = calculate_skill_half_life(
        _monthly_signals([0.2 * math.exp(-0.03 * i) for i in range(12)]),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert sparse.status == "insufficient_data"

    gapped = _monthly_signals([0.2 * math.exp(-0.03 * i) for i in range(36)])
    gapped.pop(12)
    assert calculate_skill_half_life(
        gapped, canonical_skill_id="python", min_periods=36, as_of=date(2026, 10, 12)
    ).status == "insufficient_data"

    irregular_shares = [
        0.2 * math.exp(-0.02 * index + (0.65 if index % 2 else -0.65))
        for index in range(36)
    ]
    irregular = calculate_skill_half_life(
        _monthly_signals(irregular_shares),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert irregular.status == "not_applicable"
    assert "tau" in irregular.reason

    wrong_unit = calculate_skill_half_life(
        _monthly_signals(
            [0.2 * math.exp(-0.03 * i) for i in range(36)],
            unit=None,
        ),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert wrong_unit.status == "insufficient_data"

    truncated = calculate_skill_half_life(
        _monthly_signals([0.2 * math.exp(-0.03 * i) for i in range(36)]),
        canonical_skill_id="python",
        history_complete=False,
    )
    assert truncated.status == "unavailable"
    assert "incomplete" in truncated.reason

    incomplete_latest_month = calculate_skill_half_life(
        _monthly_signals([0.2 * math.exp(-0.03 * i) for i in range(36)], start_year=2023),
        canonical_skill_id="python",
        min_periods=36,
        as_of=date(2025, 12, 12),
    )
    assert incomplete_latest_month.status == "insufficient_data"


def test_half_life_does_not_combine_incompatible_providers_or_signals():
    demand = _monthly_signals([0.2 * math.exp(-0.03 * i) for i in range(36)])
    github_adoption = _monthly_signals(
        [0.3 * math.exp(-0.02 * i) for i in range(36)],
        source="github",
        signal_type="adoption",
        unit="developers",
        denominator_unit="active_developers",
    )
    result = calculate_skill_half_life(
        demand + github_adoption,
        canonical_skill_id="python",
        signal_family="demand",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert result.status == "ready"
    assert result.provider == "adzuna"
    assert result.signal_type == "demand"
    assert result.half_life_unit == "months"

    incompatible = calculate_skill_half_life(
        demand + _monthly_signals(
            [0.15 * math.exp(-0.01 * i) for i in range(36)],
            source="other-provider",
        ),
        canonical_skill_id="python",
        signal_family="demand",
        min_periods=36,
        as_of=date(2026, 10, 12),
    )
    assert incompatible.status == "unavailable"
    assert "Multiple incompatible" in incompatible.reason

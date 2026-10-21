import json
import hashlib
import sqlite3
import csv
from datetime import date, datetime, timezone

import pytest

from app.scripts.audit_demand_series_readiness import audit_snapshot, main


AS_OF = date(2026, 10, 18)


def observation(period, *, index=0, **overrides):
    year, month = (int(part) for part in period.split("-"))
    values = {
        "id": f"test-observation-{period}-{index}",
        "source": "jsearch",
        "signal_type": "demand",
        "skill": "Python",
        "skill_id": "python",
        "observed_at": datetime(year, month, 15, tzinfo=timezone.utc).isoformat(),
        "period": period,
        "scope": "country",
        "location": "India",
        "value": 0.8,
        "unit": "share",
        "denominator_unit": "job_postings",
        "denominator": 100,
        "history_type": "platform_collected",
        "data_origin": "test",
        "series_id": "jsearch:panel-1:python",
        "query_id": "query-1",
        "panel_version": "panel-1",
        "extractor_version": "extractor-1",
        "metric": "normalized_share",
        "normalized_value": 0.8,
        "quality": {
            "collection_complete": True,
            "pagination_complete": True,
            "sampling_frame": "test-only-fixed-query-v1",
        },
    }
    values.update(overrides)
    if "id" not in overrides:
        values["id"] = (
            f"test-{values['source']}-{values['panel_version']}-{values['query_id']}-"
            f"{values['location']}-{period}-{index}"
        )
    return values


def consecutive_rows(count, *, start_year=2020, start_month=1, value_for_index=None, **overrides):
    rows = []
    for index in range(count):
        absolute = start_year * 12 + start_month - 1 + index
        year, month0 = divmod(absolute, 12)
        month = month0 + 1
        period = f"{year:04d}-{month:02d}"
        value = value_for_index(index) if value_for_index else 0.8
        rows.append(observation(period, index=index, value=value, normalized_value=value, **overrides))
    return rows


def write_manifest(path, rows, **overrides):
    def values(field, fallback):
        found = sorted({str(row.get(field, fallback)) for row in rows})
        return found or [fallback]

    panels = sorted({(row.get("panel_version", "panel-1"), row.get("query_id", "query-1")) for row in rows})
    geographies = sorted({(row.get("scope", "country"), row.get("location", "India")) for row in rows})
    periods = sorted({str(row.get("period", "2020-01")) for row in rows})
    manifest = {
        "source": values("source", "jsearch"),
        "signal_family": values("signal_type", "demand"),
        "license_status": "test_only",
        "approval_reference": None,
        "approved_by": None,
        "export_created_at": "2026-10-18T00:00:00Z",
        "observation_start": min(periods),
        "observation_end": max(periods),
        "schema_version": "market-observations-v1",
        "panel_query_versions": [
            {"panel_version": panel, "query_id": query} for panel, query in panels
        ],
        "metric": sorted({str(row.get("metric", "normalized_share")) for row in rows}) or ["normalized_share"],
        "unit": values("unit", "share"),
        "denominator_semantics": "test fixture denominator; no market inference",
        "denominator_unit": values("denominator_unit", "job_postings"),
        "geography": [{"scope": scope, "location": location} for scope, location in geographies],
        "period_grain": "month",
        "collection_complete": True,
        "sampling_frame": "test-only-fixed-query-v1",
        "taxonomy_version": "test-taxonomy-v1",
        "extractor_version": values("extractor_version", "extractor-1"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "record_count": len(rows),
        "data_origin": "test",
        "history_type": values("history_type", "platform_collected"),
    }
    manifest.update(overrides)
    path.with_suffix(path.suffix + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def write_json(path, rows, **manifest_overrides):
    path.write_text(json.dumps({"observations": rows}), encoding="utf-8")
    write_manifest(path, rows, **manifest_overrides)
    return path


def test_missing_input_returns_blocked_without_fallback(tmp_path):
    report = audit_snapshot(tmp_path / "absent.json", as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert "does not exist" in report["reason"]
    assert report["series_count"] == 0


def test_cli_without_snapshot_path_exits_blocked(capsys):
    assert main([]) == 2
    assert "explicitly supply" in capsys.readouterr().out


def test_missing_manifest_blocks_snapshot(tmp_path):
    path = tmp_path / "unmanifested.json"
    path.write_text(json.dumps(consecutive_rows(4)), encoding="utf-8")
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert "manifest" in report["reason"]
    assert report["total_rows"] == 4
    assert report["quarantined_records"] == 4
    assert len(report["input_checksum_sha256"]) == 64


@pytest.mark.parametrize("override,reason", [
    ({"sha256": "0" * 64}, "checksum"),
    ({"record_count": 99}, "record_count"),
])
def test_manifest_checksum_and_record_count_must_match(tmp_path, override, reason):
    path = tmp_path / "mismatch.json"
    write_json(path, consecutive_rows(4), **override)
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert reason in report["reason"]


@pytest.mark.parametrize("suffix,writer", [(".csv", "csv"), (".jsonl", "jsonl")])
def test_supported_text_formats_require_matching_manifest(tmp_path, suffix, writer):
    rows = consecutive_rows(4)
    path = tmp_path / f"supported{suffix}"
    if writer == "csv":
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            output = csv.DictWriter(handle, fieldnames=fields)
            output.writeheader()
            output.writerows([{**row, "quality": json.dumps(row["quality"])} for row in rows])
    else:
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    write_manifest(path, rows)
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "COMPLETE"
    assert report["input_eligibility"] == "test_only"
    assert report["input_checksum_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_unknown_origin_is_blocked_and_test_origin_never_counts_as_real(tmp_path):
    path = tmp_path / "unknown.json"
    write_json(path, consecutive_rows(4), data_origin="unknown")
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert "data_origin" in report["reason"]
    test_report = audit_snapshot(write_json(tmp_path / "test-only.json", consecutive_rows(4)), as_of=AS_OF)
    assert test_report["input_eligibility"] == "test_only"
    assert test_report["genuine_hiring_demand_observations"] == 0
    assert test_report["eligible_series"]["operational_forecasting"] == 0


def test_zero_requires_verified_complete_frame(tmp_path):
    complete = observation("2025-01", value=0, normalized_value=0, metric="raw_count")
    complete["denominator"] = None
    path = write_json(tmp_path / "complete-zero.json", [complete])
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "COMPLETE"
    incomplete = observation("2025-01", value=0, normalized_value=0, metric="raw_count")
    incomplete["quality"] = {"collection_complete": False, "pagination_complete": False,
                              "sampling_frame": "test-only-fixed-query-v1"}
    report = audit_snapshot(write_json(tmp_path / "incomplete-zero.json", [incomplete]), as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert report["quarantined_rows"]["collection_incomplete_or_unknown"] == 1


@pytest.mark.parametrize("suffix,contents", [
    (".csv", "not,a,valid\n"),
    (".json", "{\"users\": []}"),
    (".bin", "opaque"),
])
def test_invalid_or_unsupported_input_is_blocked(tmp_path, suffix, contents):
    path = tmp_path / f"snapshot{suffix}"
    path.write_text(contents, encoding="utf-8")
    report = audit_snapshot(path, as_of=AS_OF)
    assert report["status"] == "BLOCKED"
    assert report["series_count"] == 0


def test_month_gaps_are_preserved_and_block_trend_readiness(tmp_path):
    rows = [observation(period, index=i) for i, period in enumerate(("2025-01", "2025-02", "2025-04", "2025-05"))]
    report = audit_snapshot(write_json(tmp_path / "gaps.json", rows), as_of=AS_OF)
    series = report["series"][0]
    assert series["missing_months"] == ["2025-03"]
    assert series["consecutive_completed_months"] == 2
    assert series["readiness"]["skill_demand_trends"] is False


def test_duplicate_period_level_metric_is_reported(tmp_path):
    rows = consecutive_rows(4)
    rows.append(observation("2020-01", index=999))
    # Distinct normalized-share records for the same series-month are ambiguous aggregates.
    rows[-1]["id"] = "duplicate-monthly-share"
    report = audit_snapshot(write_json(tmp_path / "dupes.json", rows), as_of=AS_OF)
    assert "2020-01" in report["series"][0]["duplicate_periods"]
    assert report["series"][0]["readiness"]["skill_demand_trends"] is False


def test_current_month_is_excluded_as_incomplete(tmp_path):
    row = observation("2026-10", observed_at="2026-10-10T12:00:00+00:00")
    report = audit_snapshot(write_json(tmp_path / "current.json", [row]), as_of=AS_OF)
    series = report["series"][0]
    assert series["incomplete_current_month_observation_count"] == 1
    assert series["completed_period_count"] == 0


@pytest.mark.parametrize("denominator,denominator_unit", [(None, "job_postings"), (0, "job_postings"), (-1, "job_postings"), (100, None)])
def test_invalid_or_missing_denominator_blocks_health_and_normalized_eligibility(tmp_path, denominator, denominator_unit):
    rows = consecutive_rows(4, denominator=denominator, denominator_unit=denominator_unit)
    report = audit_snapshot(write_json(tmp_path / "denominator.json", rows), as_of=AS_OF)
    series = report["series"][0]
    assert series["readiness"]["skill_health"] is False
    assert series["normalized_consecutive_months"] == 0


def test_unit_and_source_mismatches_remain_separate_series(tmp_path):
    rows = consecutive_rows(4)
    rows += consecutive_rows(4, unit="repository_count", source="github")
    report = audit_snapshot(write_json(tmp_path / "sources.json", rows), as_of=AS_OF)
    assert report["series_count"] == 2
    assert {item["source"] for item in report["series"]} == {"jsearch", "github"}
    assert all(item["signal_family"] == "demand" for item in report["series"])


def test_geography_and_query_panel_changes_are_not_combined(tmp_path):
    rows = consecutive_rows(4)
    rows += consecutive_rows(4, start_year=2021, query_id="query-2", panel_version="panel-2")
    rows += consecutive_rows(4, start_year=2022, location="United States")
    report = audit_snapshot(write_json(tmp_path / "partitions.json", rows), as_of=AS_OF)
    assert report["series_count"] == 3
    assert {item["location"] for item in report["series"]} == {"India", "United States"}
    india_series = [item for item in report["series"] if item["location"] == "India"]
    us_series = next(item for item in report["series"] if item["location"] == "United States")
    assert all(item["configuration_drift"] for item in india_series)
    assert not us_series["configuration_drift"]
    assert all(not item["readiness"]["skill_demand_trends"] for item in india_series)


@pytest.mark.parametrize("signal", ["adoption", "interest", "context"])
def test_non_hiring_signals_are_excluded(signal, tmp_path):
    rows = consecutive_rows(24, signal_type=signal)
    report = audit_snapshot(write_json(tmp_path / "other-signal.json", rows), as_of=AS_OF)
    assert report["genuine_hiring_demand_observations"] == 0
    assert report["series_count"] == 0
    assert report["excluded_by_signal_or_origin"][f"signal_{signal}"] == 24


def test_static_reference_and_synthetic_demand_are_excluded(tmp_path):
    rows = consecutive_rows(4, history_type="static_dataset")
    rows += consecutive_rows(4, start_year=2021, data_origin="demo", history_type="backfill")
    report = audit_snapshot(write_json(tmp_path / "excluded.json", rows), as_of=AS_OF)
    assert report["genuine_hiring_demand_observations"] == 0
    assert all(item["genuine_demand_observation_count"] == 0 for item in report["series"])
    assert all(not item["readiness"]["skill_demand_trends"] for item in report["series"])


def test_trend_and_health_thresholds_require_four_months(tmp_path):
    three = audit_snapshot(write_json(tmp_path / "three.json", consecutive_rows(3)), as_of=AS_OF)
    four = audit_snapshot(write_json(tmp_path / "four.json", consecutive_rows(4)), as_of=AS_OF)
    assert three["eligible_series"].get("skill_demand_trends", 0) == 0
    assert four["eligible_series"]["skill_demand_trends"] == 0
    assert four["eligible_series"]["skill_health"] == 0
    assert four["input_eligibility"] == "test_only"
    assert four["series"][0]["readiness"]["test_only_structural_period_gates"]["trend_history_depth"] is True
    assert four["series"][0]["readiness"]["test_only_structural_period_gates"]["health_history_depth"] is True


def test_half_life_requires_36_months_and_significant_decline(tmp_path):
    rows = consecutive_rows(36, value_for_index=lambda index: 0.8 * (0.96 ** index))
    report = audit_snapshot(write_json(tmp_path / "decay.json", rows), as_of=AS_OF)
    assert report["eligible_series"]["skill_half_life"] == 0
    assert report["series"][0]["readiness"]["test_only_structural_period_gates"]["half_life_history_depth"] is True
    flat = audit_snapshot(write_json(tmp_path / "flat.json", consecutive_rows(36)), as_of=AS_OF)
    assert flat["eligible_series"].get("skill_half_life", 0) == 0


def test_forecast_data_threshold_is_separate_from_model_validation(tmp_path):
    rows = consecutive_rows(24)
    report = audit_snapshot(write_json(tmp_path / "forecast.json", rows), as_of=AS_OF)
    series = report["series"][0]
    assert series["readiness"]["operational_forecasting_data_eligible"] is False
    assert series["readiness"]["test_only_structural_period_gates"]["forecast_history_depth"] is True
    assert series["readiness"]["forecast_holdout_sample_size"] == 0
    assert series["readiness"]["model_validated"] is False

    short = audit_snapshot(write_json(tmp_path / "short.json", consecutive_rows(23)), as_of=AS_OF)
    assert short["eligible_series"].get("operational_forecasting", 0) == 0


def test_incomplete_collection_periods_do_not_count_toward_forecast_readiness(tmp_path):
    rows = consecutive_rows(24)
    rows[7]["quality"] = {"collection_complete": False}
    report = audit_snapshot(write_json(tmp_path / "incomplete.json", rows), as_of=AS_OF)
    assert report["eligible_series"].get("operational_forecasting", 0) == 0
    assert report["status"] == "COMPLETE"
    assert report["quarantined_records"] == 1
    assert report["quarantined_rows"]["collection_incomplete_or_unknown"] == 1


def test_conflicting_duplicate_identity_quarantines_both_records(tmp_path):
    first = observation("2025-01", index=0)
    conflicting = observation("2025-01", index=1, value=0.5)
    conflicting["id"] = first["id"]
    report = audit_snapshot(write_json(tmp_path / "conflict.json", [first, conflicting]), as_of=AS_OF)
    assert report["duplicate_records"] == 1
    assert report["quarantined_rows"]["conflicting_identity"] == 2
    assert report["accepted_records"] == 0
    assert report["status"] == "BLOCKED"


def test_posting_counts_without_declared_sampling_frame_do_not_create_denominators(tmp_path):
    rows = consecutive_rows(24)
    for row in rows:
        row["metric"] = "raw_count"
        row["normalized_value"] = None
        row["denominator"] = None
        row["posting_id"] = f"posting-{row['period']}"
    report = audit_snapshot(write_json(tmp_path / "undefined-frame.json", rows), as_of=AS_OF)
    assert report["eligible_series"].get("operational_forecasting", 0) == 0
    assert report["series"][0]["readiness"]["operational_forecasting_data_eligible"] is False


def test_report_is_read_only_and_omits_raw_private_fields(tmp_path, capsys):
    rows = consecutive_rows(4)
    for row in rows:
        row["uid"] = "private-user-sentinel"
        row["email"] = "private@example.invalid"
        row["metadata"] = {"credential": "private-token-sentinel"}
    path = write_json(tmp_path / "input.json", rows)
    before = path.read_bytes()
    output_path = tmp_path / "report.json"
    assert main([str(path), "--as-of", "2026-10-18", "--json-output", str(output_path)]) == 0
    rendered = capsys.readouterr().out + output_path.read_text(encoding="utf-8")
    assert path.read_bytes() == before
    assert "private-user-sentinel" not in rendered
    assert "private@example.invalid" not in rendered
    assert "private-token-sentinel" not in rendered


def test_report_cannot_overwrite_input_snapshot(tmp_path, capsys):
    path = write_json(tmp_path / "input.json", consecutive_rows(4))
    before = path.read_bytes()
    assert main([str(path), "--json-output", str(path)]) == 2
    assert path.read_bytes() == before
    assert "must not overwrite" in capsys.readouterr().err


def test_sqlite_snapshot_is_opened_read_only(tmp_path):
    path = tmp_path / "observations.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("""CREATE TABLE market_observations (
        id TEXT, source TEXT, signal_type TEXT, skill TEXT, skill_id TEXT, value REAL,
        observed_at TEXT, period TEXT, scope TEXT, location TEXT, unit TEXT,
        denominator_unit TEXT, denominator REAL, history_type TEXT, data_origin TEXT,
        series_id TEXT, query_id TEXT, panel_version TEXT, extractor_version TEXT,
        metric TEXT, normalized_value REAL, quality_json TEXT
    )""")
    row = observation("2020-01")
    connection.execute(
        "INSERT INTO market_observations VALUES (" + ",".join("?" for _ in range(22)) + ")",
        tuple(json.dumps(row[key]) if key == "quality" else row[key] for key in (
            "id", "source", "signal_type", "skill", "skill_id", "value", "observed_at", "period", "scope", "location", "unit", "denominator_unit", "denominator", "history_type", "data_origin", "series_id", "query_id", "panel_version", "extractor_version", "metric", "normalized_value", "quality"
        )),
    )
    connection.commit()
    connection.close()
    write_manifest(path, [row])
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    report = audit_snapshot(path, as_of=AS_OF)

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["status"] == "COMPLETE"
    assert report["input_eligibility"] == "test_only"
    assert before == after

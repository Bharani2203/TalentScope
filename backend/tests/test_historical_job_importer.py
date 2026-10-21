"""Unit and integration tests for Historical Job Postings Importer.

Verifies:
1. Schema and date validation within historical boundaries (2026-01-01 to 2026-06-30).
2. Skill extraction and canonicalization (pipe-delimited and comma-delimited).
3. Country isolation (India 'IN' and US 'US' are strictly partitioned, never merged).
4. Deduplication by posting_id and (company, title, period, country).
5. License provenance metadata (CC BY-NC 4.0, non-commercial sample flag).
6. Idempotent re-run safety against SQLite.
7. Analytical readiness gate compliance:
   - >=4 months trend gate passes (ready_for_trend)
   - >=24 months forecast gate is strictly blocked (insufficient / unavailable)
   - >=36 months half-life gate is strictly blocked (insufficient / unavailable)
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.forecasting import forecast_signal_series
from app.analytics.skill_half_life import calculate_skill_half_life
from app.analytics.trend import calculate_skill_trends
from app.services.historical_job_import_service import (
    HistoricalJobImportService,
    normalize_country_code,
    parse_and_validate_date,
    parse_posting_skills,
)
from app.storage.market_store import MarketDataStore


@pytest.fixture
def temp_db(tmp_path: Path) -> MarketDataStore:
    db_file = tmp_path / "test_market_data.sqlite3"
    return MarketDataStore(database_path=db_file)


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "sample_postings.csv"
    headers = [
        "posting_id", "posted_date", "title", "company", "role", "seniority",
        "category", "city", "region", "country", "remote", "experience_years",
        "education", "skills", "salary_annual_usd", "company_domain", "fliar_profile_url"
    ]
    rows = [
        # Valid India postings across 6 consecutive months
        ["in_01", "2026-01-15", "Software Engineer", "TechCorp", "eng", "mid", "it", "Bengaluru", "KA", "IN", "hybrid", "3", "BS", "python|sql|docker", "25000", "", ""],
        ["in_02", "2026-02-10", "Backend Developer", "Infosys", "eng", "senior", "it", "Hyderabad", "TS", "IN", "onsite", "5", "BS", "python|fastapi|aws", "30000", "", ""],
        ["in_03", "2026-03-20", "Data Engineer", "Wipro", "eng", "mid", "it", "Bengaluru", "KA", "IN", "remote", "4", "MS", "python|sql|spark", "28000", "", ""],
        ["in_04", "2026-04-05", "Python Developer", "TCS", "eng", "junior", "it", "Pune", "MH", "IN", "onsite", "2", "BS", "python|django|postgresql", "20000", "", ""],
        ["in_05", "2026-05-18", "Senior Python Engineer", "HCL", "eng", "lead", "it", "Chennai", "TN", "IN", "hybrid", "7", "BS", "python|kubernetes|aws", "45000", "", ""],
        ["in_06", "2026-06-25", "Cloud Engineer", "Cognizant", "eng", "senior", "it", "Bengaluru", "KA", "IN", "remote", "6", "BS", "python|docker|kubernetes|azure", "40000", "", ""],
        # US postings (must be partitioned, never merged with India)
        ["us_01", "2026-01-12", "Software Engineer", "Google", "eng", "mid", "it", "Mountain View", "CA", "US", "hybrid", "4", "BS", "python|go|kubernetes", "180000", "", ""],
        ["us_02", "2026-02-14", "Backend Engineer", "Meta", "eng", "senior", "it", "Menlo Park", "CA", "US", "onsite", "6", "BS", "python|c++|sql", "220000", "", ""],
        # Duplicate posting_id
        ["in_01", "2026-01-15", "Software Engineer", "TechCorp", "eng", "mid", "it", "Bengaluru", "KA", "IN", "hybrid", "3", "BS", "python|sql", "25000", "", ""],
        # Duplicate (company, title, period, country) tuple with different ID
        ["in_dup", "2026-01-20", "Software Engineer", "TechCorp", "eng", "mid", "it", "Bengaluru", "KA", "IN", "hybrid", "3", "BS", "python|sql", "25000", "", ""],
        # Invalid date (out of bounds: future/past)
        ["in_past", "2025-12-31", "Old Engineer", "OldCorp", "eng", "mid", "it", "Mumbai", "MH", "IN", "onsite", "3", "BS", "python", "20000", "", ""],
        ["in_future", "2026-07-01", "Future Engineer", "FutureCorp", "eng", "mid", "it", "Mumbai", "MH", "IN", "onsite", "3", "BS", "python", "20000", "", ""],
        # Missing skills
        ["in_noskills", "2026-03-01", "Admin", "AdminCorp", "admin", "mid", "ops", "Delhi", "DL", "IN", "onsite", "3", "BS", "", "15000", "", ""],
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_file


def test_parse_and_validate_date():
    valid, period, dt = parse_and_validate_date("2026-03-15")
    assert valid is True
    assert period == "2026-03"
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 3

    # Out of range dates
    assert parse_and_validate_date("2025-12-31")[0] is False
    assert parse_and_validate_date("2026-07-01")[0] is False
    assert parse_and_validate_date("invalid-date")[0] is False
    assert parse_and_validate_date("")[0] is False
    assert parse_and_validate_date(None)[0] is False


def test_parse_posting_skills():
    # Pipe delimited
    assert parse_posting_skills("python|fastapi|postgresql") == ["python", "fastapi", "postgresql"]
    # Comma delimited
    assert parse_posting_skills("python, react, docker") == ["python", "react", "docker"]
    # Single skill
    assert parse_posting_skills("Python") == ["Python"]
    # Empty / whitespace
    assert parse_posting_skills("") == []
    assert parse_posting_skills(None) == []


def test_normalize_country_code():
    assert normalize_country_code("IN") == "IN"
    assert normalize_country_code("India") == "IN"
    assert normalize_country_code("india") == "IN"
    assert normalize_country_code("US") == "US"
    assert normalize_country_code("USA") == "US"
    assert normalize_country_code("United States") == "US"
    assert normalize_country_code("XYZ") == None
    assert normalize_country_code(None) == None


def test_country_isolation(sample_csv: Path, temp_db: MarketDataStore):
    service = HistoricalJobImportService(store=temp_db)
    
    # Import India only
    stats_in = service.import_from_csv(sample_csv, target_country="IN", dry_run=False)
    assert stats_in["country"] == "IN"
    assert stats_in["valid_postings"] == 6
    assert stats_in["postings_inserted"] == 6

    # Verify all stored observations have location == 'IN'
    obs_in = temp_db.get_observations()
    assert len(obs_in) > 0
    assert all(o.location == "IN" for o in obs_in)
    assert not any(o.location == "US" for o in obs_in)

    # Import US separately
    stats_us = service.import_from_csv(sample_csv, target_country="US", dry_run=False)
    assert stats_us["country"] == "US"
    assert stats_us["valid_postings"] == 2
    assert stats_us["postings_inserted"] == 2

    # Verify US observations are strictly tagged as US
    obs_all = temp_db.get_observations()
    us_obs = [o for o in obs_all if o.location == "US"]
    assert len(us_obs) > 0
    assert all(o.location == "US" for o in us_obs)


def test_duplicate_and_invalid_rejection(sample_csv: Path, temp_db: MarketDataStore):
    service = HistoricalJobImportService(store=temp_db)
    stats = service.import_from_csv(sample_csv, target_country="IN", dry_run=True)

    # 2 duplicate rows in sample
    assert stats["rejected_duplicates"] == 2
    # 2 invalid date rows (past, future)
    assert stats["rejected_invalid_date"] == 2
    # 1 missing skills row
    assert stats["rejected_missing_skills"] == 1
    # 6 valid postings across 2026-01 to 2026-06
    assert stats["valid_postings"] == 6


def test_license_provenance_and_metadata(sample_csv: Path, temp_db: MarketDataStore):
    service = HistoricalJobImportService(store=temp_db)
    service.import_from_csv(sample_csv, target_country="IN", dry_run=False)

    obs = temp_db.get_observations(skill="Python")
    assert len(obs) == 6  # Present in all 6 months
    
    first = obs[0]
    assert first.source == "fliarbi"
    assert first.signal_type == "demand"
    assert first.history_type == "backfill"
    assert first.data_origin == "real"
    assert first.unit == "job_postings"
    assert first.denominator_unit == "job_postings"
    assert first.metadata.get("license") == "CC BY-NC 4.0"
    assert first.metadata.get("is_sample") is True
    assert first.metadata.get("source") == "fliarbi"


def test_idempotent_reimport(sample_csv: Path, temp_db: MarketDataStore):
    service = HistoricalJobImportService(store=temp_db)
    
    # First import
    stats1 = service.import_from_csv(sample_csv, target_country="IN", dry_run=False)
    assert stats1["observations_inserted"] > 0
    assert stats1["postings_inserted"] == 6
    obs_count_initial = len(temp_db.get_observations())

    # Second import (exact same data)
    stats2 = service.import_from_csv(sample_csv, target_country="IN", dry_run=False)
    assert stats2["observations_inserted"] == 0
    assert stats2["postings_inserted"] == 0
    obs_count_reimport = len(temp_db.get_observations())

    # Must be identical
    assert obs_count_reimport == obs_count_initial


def test_analytical_readiness_gates(sample_csv: Path, temp_db: MarketDataStore):
    service = HistoricalJobImportService(store=temp_db)
    service.import_from_csv(sample_csv, target_country="IN", dry_run=False)

    obs = temp_db.get_observations(skill="Python")
    assert len(obs) == 6  # 6 completed months: 2026-01 through 2026-06

    # 1. Analytical readiness assessment
    readiness_reports = assess_analytical_readiness(obs)
    assert len(readiness_reports) == 1
    r = readiness_reports[0]
    assert r.readiness_state == "ready_for_trend"
    assert r.is_trend_ready is True
    assert r.is_forecast_ready is False  # 6 < 24
    assert any("24" in b for b in r.blocking_reasons)

    # 2. Trend calculation (should execute and succeed with ready_for_trend)
    trends = calculate_skill_trends(obs)
    assert len(trends) == 1
    t = trends[0]
    assert t["readiness_state"] == "ready_for_trend"
    assert t["periods_used"] == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]

    # 3. Forecast calculation (should remain unavailable/insufficient because 6 < 24)
    fc = forecast_signal_series(obs, canonical_name="Python")
    assert fc.status == "unavailable"
    assert fc.required_min_periods == 24
    assert fc.beats_naive_baseline is False

    # 4. Half-life calculation (should remain unavailable/insufficient because 6 < 36)
    hl = calculate_skill_half_life(obs)
    assert hl.status in ("unavailable", "insufficient_data")
    assert hl.required_min_periods == 36

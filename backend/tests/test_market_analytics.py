from datetime import datetime, timezone
import sqlite3

import pytest

from app.analytics.skill_normalization import extract_skills, normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.analytics.trend import calculate_skill_trends, theil_sen_slope
from app.models.skill_intelligence import MarketObservation, MarketPosting
from app.services.market_data.job_observations import observations_from_postings
from app.storage.market_store import MarketDataStore


def observation(source, skill, period, posting_id, *, location="Chennai"):
    return MarketObservation(
        id=f"{source}:{period}:{skill}:{posting_id}",
        source=source,
        signal_type="demand",
        history_type="platform_collected",
        observed_at=datetime.fromisoformat(f"{period}-15T12:00:00+00:00"),
        period=period,
        location=location,
        scope="city",
        skill=skill,
        value=1,
        unit="job_postings",
        skill_id=canonical_skill_id(skill),
        posting_id=posting_id,
        series_id=f"{source}:job-demand:{canonical_skill_id(skill)}:v1",
        query_id=f"{source}:query-v1",
        panel_version="job-demand-v1",
        data_origin="real",
    )


def month_observations(period, python_count, total=100):
    postings = []
    for index in range(total):
        skill = "Python" if index < python_count else "SQL"
        postings.append(observation("jsearch", skill, period, f"{period}-job-{index}"))
    return postings


def test_aliases_are_normalized_to_canonical_taxonomy_names():
    assert normalize_skill("JS") == "JavaScript"
    assert normalize_skill("Javascript") == "JavaScript"
    assert normalize_skill("Node") == "Node.js"
    assert normalize_skill("ML") == "Machine Learning"
    assert normalize_skill("  python  ") == "Python"


def test_skill_extraction_is_deterministic_and_case_insensitive():
    assert extract_skills(
        "Build a Python service using PYTHON, ML, NodeJS and PostgreSQL."
    ) == ["Machine Learning", "Node.js", "PostgreSQL", "Python"]


def test_job_observations_preserve_real_run_and_provider_series():
    collected_at = datetime(2026, 10, 6, tzinfo=timezone.utc)
    posting = MarketPosting(
        source="adzuna", posting_id="real-job-1",
        title="C# Software Engineer", description="Build services with C# and SQL.",
    )
    observations = observations_from_postings(
        [posting], location=None, country="in", collected_at=collected_at,
        fetch_run_id="run-current", query_id="adzuna:panel-1", panel_version="job-demand-v1",
    )

    assert {item.skill for item in observations} == {"C#", "SQL"}
    assert all(item.source == "adzuna" for item in observations)
    assert all(item.signal_type == "demand" for item in observations)
    assert all(item.data_origin == "real" for item in observations)
    assert all(item.history_type == "platform_collected" for item in observations)
    assert all(item.fetch_run_id == "run-current" for item in observations)
    assert all(item.period == "2026-10" for item in observations)
    assert all(item.series_id.startswith("adzuna:adzuna:panel-1:job-demand:") for item in observations)
    assert len({item.id for item in observations}) == len(observations)


def test_one_skill_is_counted_once_per_posting():
    time = datetime(2026, 10, 5, tzinfo=timezone.utc)
    postings = [
        MarketPosting(
            source="jsearch",
            posting_id="job-1",
            title="Python developer",
            description="Python, python and Python experience required.",
        ),
        MarketPosting(
            source="jsearch",
            posting_id="job-1",
            description="Python appears again in the duplicate result.",
        ),
    ]

    results = observations_from_postings(
        postings,
        location="Chennai",
        country="in",
        collected_at=time,
    )

    assert len(results) == 1
    assert results[0].skill == "Python"
    assert results[0].posting_id == "job-1"
    assert results[0].scope == "city"
    assert results[0].data_origin == "real"


def test_demand_share_is_smoothed_and_uses_unique_skill_postings():
    observations = [
        observation("jsearch", "Python", "2026-10", "job-1"),
        observation("jsearch", "Python", "2026-10", "job-2"),
        observation("jsearch", "SQL", "2026-10", "job-1"),
    ]

    trends = calculate_skill_trends(observations)

    assert {item["skill"]: item["demand_share"] for item in trends} == {
        "Python": 0.625,
        "SQL": 0.375,
    }


def test_theil_sen_slope_is_robust_to_an_outlier():
    assert theil_sen_slope([0.1, 0.2, 0.3, 0.4, 5.0]) == pytest.approx(0.1)


def test_trend_labels_growth_confidence_and_rank_scores_use_history():
    observations = []
    for period, python_count in zip(
        ["2026-06", "2026-07", "2026-08", "2026-09"],
        [10, 20, 30, 40],
    ):
        observations.extend(month_observations(period, python_count))

    trends = {item["skill"]: item for item in calculate_skill_trends(
        observations,
        now=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )}

    assert trends["Python"]["trend"] == "Growing"
    assert trends["Python"]["growth_pct"] > 0
    assert trends["Python"]["confidence"] is not None
    assert 0 <= trends["Python"]["confidence"] <= 1
    assert trends["Python"]["ranking_score"] is not None
    assert trends["SQL"]["trend"] == "Declining"
    assert trends["SQL"]["growth_pct"] < 0


def test_stable_trend_is_labeled_from_flat_observations():
    observations = []
    for period in ["2026-06", "2026-07", "2026-08", "2026-09"]:
        observations.extend(month_observations(period, 25))

    trends = calculate_skill_trends(observations)

    assert next(item for item in trends if item["skill"] == "Python")["trend"] == "Stable"


def test_insufficient_or_gapped_history_has_no_growth_or_confidence():
    insufficient = [
        observation("jsearch", "Python", "2026-07", "a"),
        observation("jsearch", "Python", "2026-08", "b"),
        observation("jsearch", "Python", "2026-09", "c"),
    ]
    gapped = [
        observation("jsearch", "Python", period, f"job-{period}")
        for period in ["2026-05", "2026-06", "2026-08", "2026-09"]
    ]

    for results in (calculate_skill_trends(insufficient), calculate_skill_trends(gapped)):
        trend = results[0]
        assert trend["trend"] == "Insufficient Data"
        assert trend["growth_pct"] is None
        assert trend["confidence"] is None
        assert [point["period"] for point in trend["series"]] in (
            ["2026-07", "2026-08", "2026-09"],
            ["2026-05", "2026-06", "2026-08", "2026-09"],
        )


def test_sqlite_store_deduplicates_observations_and_keeps_history(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    row = observation("jsearch", "Python", "2026-10", "job-1")

    assert store.insert_observations([row, row]) == 1
    assert store.insert_observations([row]) == 0
    saved = store.get_observations(
        location="Chennai",
        cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert len(saved) == 1
    assert saved[0].posting_id == "job-1"
    assert store.collection_summary()["periods"] == 1


def test_global_observations_are_not_returned_for_city_filtered_query(tmp_path):
    store = MarketDataStore(tmp_path / "market.sqlite3")
    store.insert_observations([
        observation("jsearch", "Python", "2026-10", "city-job"),
        MarketObservation(
            id="global-observation",
            source="github",
            skill="Python",
            observed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
            period="2026-10",
            scope="global",
            signal_type="adoption",
            value=1,
        ),
    ])

    observations = store.get_observations(
        location="Chennai",
        cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert [item.source for item in observations] == ["jsearch"]


def test_multiple_provider_trends_preserve_series_and_do_not_sum_denominators():
    periods = ["2026-06", "2026-07", "2026-08", "2026-09"]

    def series_for(source, counts, series_id):
        rows = []
        for period, python_count in zip(periods, counts):
            for index in range(100):
                skill = "Python" if index < python_count else "SQL"
                rows.append(observation(source, skill, period, f"same-job-{period}-{index}").model_copy(
                    update={
                        "series_id": series_id,
                        "query_id": f"{source}:query-v1",
                        "panel_version": f"{source}-panel-v1",
                        "data_origin": "real",
                    }
                ))
        return rows

    jsearch_rows = series_for("jsearch", [10, 20, 30, 40], "jsearch-series-v1")
    adzuna_rows = series_for("adzuna", [90, 80, 70, 60], "adzuna-series-v1")
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    single = {item["skill"]: item for item in calculate_skill_trends(jsearch_rows, now=now)}
    combined = calculate_skill_trends([*jsearch_rows, *adzuna_rows], now=now)
    by_source_skill = {(item["source"], item["skill"]): item for item in combined}

    jsearch_python = by_source_skill[("jsearch", "Python")]
    adzuna_python = by_source_skill[("adzuna", "Python")]
    assert jsearch_python["series_id"] == "jsearch-series-v1"
    assert adzuna_python["series_id"] == "adzuna-series-v1"
    assert jsearch_python["series"] == single["Python"]["series"]
    assert jsearch_python["confidence"] == single["Python"]["confidence"]
    assert jsearch_python["series_provenance"]["posting_counts_by_period"] == {
        period: 100 for period in periods
    }
    assert adzuna_python["series_provenance"]["posting_counts_by_period"] == {
        period: 100 for period in periods
    }
    assert all(item["series_provenance"]["source"] == item["source"] for item in combined)


def test_one_provider_with_incomplete_series_does_not_change_another_provider_trend():
    periods = ["2026-06", "2026-07", "2026-08", "2026-09"]
    jsearch_rows = [
        observation("jsearch", "Python", period, f"j-{period}")
        for period in periods
    ]
    partial_adzuna_rows = [
        observation("adzuna", "Python", period, f"a-{period}")
        for period in periods[-2:]
    ]
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    healthy = next(item for item in calculate_skill_trends(jsearch_rows, now=now) if item["skill"] == "Python")
    both = calculate_skill_trends([*jsearch_rows, *partial_adzuna_rows], now=now)

    jsearch = next(item for item in both if item["source"] == "jsearch" and item["skill"] == "Python")
    adzuna = next(item for item in both if item["source"] == "adzuna" and item["skill"] == "Python")
    assert jsearch["confidence"] == healthy["confidence"]
    assert jsearch["series"] == healthy["series"]
    assert adzuna["trend"] == "Insufficient Data"
    assert adzuna["confidence"] is None


def test_sqlite_observation_metadata_roundtrips_without_legacy_inference(tmp_path):
    path = tmp_path / "legacy-market.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TABLE market_observations (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, signal_type TEXT NOT NULL,
                observed_at TEXT NOT NULL, period TEXT NOT NULL, location TEXT,
                scope TEXT NOT NULL, skill TEXT NOT NULL, value REAL NOT NULL,
                posting_id TEXT, metadata_json TEXT NOT NULL
            )
        """)
        connection.execute(
            """INSERT INTO market_observations
               (id, source, signal_type, observed_at, period, location, scope, skill, value, posting_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("legacy-row", "jsearch", "demand", "2026-10-05T12:00:00+00:00", "2026-10",
             "Chennai", "city", "Go", 1.0, "legacy-job", "{}"),
        )

    store = MarketDataStore(path)
    legacy = observation("jsearch", "Python", "2026-10", "legacy")
    store.insert_observations([legacy])
    results_before_new_row = store.get_observations(
        location=None, cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    existing_legacy = next(item for item in results_before_new_row if item.id == "legacy-row")
    assert existing_legacy.history_type is None
    assert existing_legacy.data_origin is None
    assert next(item for item in results_before_new_row if item.id == "legacy-row").data_origin is None

    explicit = observation("jsearch", "SQL", "2026-10", "new").model_copy(
        update={"history_type": "static_dataset", "data_origin": "demo"}
    )
    store.insert_observations([explicit])
    results = store.get_observations(location=None, cutoff=datetime(2026, 1, 1, tzinfo=timezone.utc))
    new_result = next(item for item in results if item.skill == "SQL")
    assert new_result.history_type == "static_dataset"
    assert new_result.data_origin == "demo"

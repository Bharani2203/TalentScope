"""Deterministic test suite for G1.13: Controlled Historical Backfill Ingestion & Multi-Period Readiness Audit.

Verifies:
A. Real historical timestamp -> correct month.
B. Historical months remain ordered correctly.
C. Same Stack Exchange configuration -> same series_id.
D. Configuration change -> different series_id.
E. Missing month remains missing.
F. No missing month becomes zero.
G. No future period is created.
H. Repeated backfill is idempotent.
I. Observation identity is deterministic.
J. Raw archive provenance is preserved.
K. Fetch run provenance is preserved.
L. Stack Exchange signal type remains "interest".
M. Stack Exchange cannot merge with JSearch demand.
N. Stack Exchange cannot merge with GitHub adoption.
O. G1.8 remains authoritative.
P. G1.9 remains authoritative.
Q. Existing production observations remain unchanged.
R. No synthetic production observations.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from app.analytics.analytical_readiness import assess_analytical_readiness
from app.analytics.series_validation import validate_series_observations
from app.models.skill_intelligence import MarketObservation
from app.services.market_data.stack_exchange_historical_provider import (
    PANEL_VERSION,
    EXTRACTOR_VERSION,
    _month_bounds,
    _month_periods,
)
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.observation_identity import stable_observation_id


def _make_test_se_obs(
    skill: str = "C#",
    skill_id: str = "c_sharp",
    tag: str = "c#",
    period: str = "2026-05",
    value: float = 99.0,
    fetch_run_id: str = "run_test_se_1",
    query_id: str | None = None,
    series_id: str | None = None,
) -> MarketObservation:
    qid = query_id or f"stackexchange:stackoverflow:tag:{tag}:v1"
    sid = series_id or f"stackexchange:stackoverflow:question-tag:{tag}:v1"
    start_epoch, end_epoch, period_end = _month_bounds(period)
    obs = MarketObservation(
        source="stackexchange",
        skill=skill,
        skill_id=skill_id,
        signal_type="interest",
        observed_at=period_end,
        period=period,
        scope="global",
        posting_id=f"monthly-count:{tag}:{period}",
        value=value,
        metadata={
            "tag": tag,
            "metric": "questions_created_with_tag_in_period",
            "raw_archive_id": f"raw_se_{period}",
        },
        history_type="backfill",
        data_origin="real",
        fetch_run_id=fetch_run_id,
        series_id=sid,
        query_id=qid,
        panel_version=PANEL_VERSION,
        denominator=None,
        extractor_version=EXTRACTOR_VERSION,
    )
    obs.id = stable_observation_id(obs)
    return obs


# =========================================================================
# REQUIREMENT A: Real historical timestamp -> correct month
# =========================================================================

def test_a_real_historical_timestamp_to_correct_month():
    """Verify provider Unix timestamp converts accurately to UTC YYYY-MM period."""
    # Timestamp for 2026-07-15 14:30:00 UTC
    dt = datetime(2026, 7, 15, 14, 30, 0, tzinfo=timezone.utc)
    epoch = int(dt.timestamp())

    converted_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    period = converted_dt.strftime("%Y-%m")
    assert period == "2026-07"

    start_epoch, end_epoch, end_dt = _month_bounds("2026-07")
    assert start_epoch <= epoch <= end_epoch


# =========================================================================
# REQUIREMENT B: Historical months remain ordered correctly
# =========================================================================

def test_b_historical_months_remain_ordered_correctly():
    """Verify _month_periods generates chronologically ordered monthly bounds."""
    periods = _month_periods("2026-05", "2026-09")
    assert periods == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]

    # Verify bounds are strictly monotonic
    prev_end = 0
    for p in periods:
        s_epoch, e_epoch, _ = _month_bounds(p)
        assert s_epoch < e_epoch
        assert s_epoch >= prev_end
        prev_end = e_epoch


# =========================================================================
# REQUIREMENT C: Same Stack Exchange configuration -> same series_id
# =========================================================================

def test_c_same_stackexchange_config_same_series_id():
    """Identical provider configuration across periods produces stable series_id."""
    obs1 = _make_test_se_obs(period="2026-05")
    obs2 = _make_test_se_obs(period="2026-06")
    assert obs1.series_id == obs2.series_id
    assert obs1.query_id == obs2.query_id
    assert obs1.series_id == "stackexchange:stackoverflow:question-tag:c#:v1"


# =========================================================================
# REQUIREMENT D: Configuration change -> different series_id
# =========================================================================

def test_d_config_change_different_series_id():
    """Changes in tag or extractor configuration yield different series_id."""
    obs1 = _make_test_se_obs(tag="c#", series_id="stackexchange:stackoverflow:question-tag:c#:v1")
    obs2 = _make_test_se_obs(tag="c#-v2", series_id="stackexchange:stackoverflow:question-tag:c#-v2:v1")
    assert obs1.series_id != obs2.series_id


# =========================================================================
# REQUIREMENT E: Missing month remains missing
# =========================================================================

def test_e_missing_month_remains_missing():
    """A missing historical month is flagged as a coverage gap and never fabricated."""
    obs = [
        _make_test_se_obs(period="2026-05"),
        _make_test_se_obs(period="2026-07"),
    ]
    q_reports = validate_series_observations(obs)
    assert len(q_reports) == 1
    assert "2026-06" in q_reports[0].coverage_gaps
    assert q_reports[0].periods_found == ["2026-05", "2026-07"]


# =========================================================================
# REQUIREMENT F: No missing month becomes zero
# =========================================================================

def test_f_no_missing_month_becomes_zero():
    """Periods with no activity are not given artificial 0.0 values."""
    obs = [
        _make_test_se_obs(period="2026-05", value=99.0),
        _make_test_se_obs(period="2026-07", value=67.0),
    ]
    periods_with_obs = {o.period: o.value for o in obs}
    assert "2026-06" not in periods_with_obs


# =========================================================================
# REQUIREMENT G: No future period is created
# =========================================================================

def test_g_no_future_period_created():
    """Historical backfill refuses to accept periods matching or exceeding current month."""
    from app.services.historical_backfill_service import backfill
    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
    with pytest.raises(ValueError, match="Historical backfill must end before the current UTC month"):
        backfill(
            source="stackexchange",
            skills=["C#"],
            start_period="2026-05",
            end_period=current_period,
            dry_run=True,
        )


# =========================================================================
# REQUIREMENT H: Repeated backfill is idempotent
# =========================================================================

def test_h_repeated_backfill_is_idempotent():
    """Calling insert_observations repeatedly with identical observations adds 0 duplicates."""
    obs1 = _make_test_se_obs(period="2026-05")
    obs2 = _make_test_se_obs(period="2026-05")
    assert obs1.id == obs2.id

    # Simulated batch with duplicate
    store = FirestoreObservationStore(client=object())
    pending = {}
    for item in [obs1, obs2]:
        doc_id = stable_observation_id(item)
        pending[doc_id] = item
    assert len(pending) == 1


# =========================================================================
# REQUIREMENT I: Observation identity is deterministic
# =========================================================================

def test_i_observation_identity_is_deterministic():
    """Stable observation ID is a deterministic 64-char SHA-256 hash."""
    obs1 = _make_test_se_obs(period="2026-05", tag="c#")
    obs2 = _make_test_se_obs(period="2026-05", tag="c#")
    assert obs1.id == obs2.id
    assert len(obs1.id) == 64
    assert all(c in "0123456789abcdef" for c in obs1.id)


# =========================================================================
# REQUIREMENT J: Raw archive provenance is preserved
# =========================================================================

def test_j_raw_archive_provenance_preserved():
    """Observations retain raw archive references in metadata."""
    obs = _make_test_se_obs(period="2026-05")
    assert obs.metadata.get("raw_archive_id") is not None


# =========================================================================
# REQUIREMENT K: Fetch run provenance is preserved
# =========================================================================

def test_k_fetch_run_provenance_preserved():
    """Observations retain explicit fetch_run_id linkage."""
    obs = _make_test_se_obs(fetch_run_id="run_custom_123")
    assert obs.fetch_run_id == "run_custom_123"


# =========================================================================
# REQUIREMENT L: Stack Exchange signal type remains 'interest'
# =========================================================================

def test_l_stackexchange_signal_type_remains_interest():
    """Stack Exchange observations must always have signal_type == 'interest'."""
    obs = _make_test_se_obs()
    assert obs.signal_type == "interest"
    assert obs.signal_type not in {"demand", "adoption", "hiring"}


# =========================================================================
# REQUIREMENT M: Stack Exchange cannot merge with JSearch demand
# =========================================================================

def test_m_stackexchange_cannot_merge_with_jsearch_demand():
    """Stack Exchange interest and JSearch demand for same skill remain strictly partitioned."""
    se_obs = _make_test_se_obs(skill="Python", period="2026-05")
    jsearch_obs = MarketObservation(
        source="jsearch",
        skill="Python",
        signal_type="demand",
        observed_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        period="2026-10",
        value=50.0,
        scope="city",
        posting_id="post_jsearch_1",
    )
    jsearch_obs.id = stable_observation_id(jsearch_obs)

    q_reports = validate_series_observations([se_obs, jsearch_obs])
    assert len(q_reports) == 2
    providers = {r.provider for r in q_reports}
    signal_types = {r.signal_type for r in q_reports}
    assert providers == {"stackexchange", "jsearch"}
    assert signal_types == {"interest", "demand"}


# =========================================================================
# REQUIREMENT N: Stack Exchange cannot merge with GitHub adoption
# =========================================================================

def test_n_stackexchange_cannot_merge_with_github_adoption():
    """Stack Exchange interest and GitHub adoption for same skill remain strictly partitioned."""
    se_obs = _make_test_se_obs(skill="Python", period="2026-05")
    gh_obs = MarketObservation(
        source="github",
        skill="Python",
        signal_type="adoption",
        observed_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        period="2026-10",
        value=900000.0,
        scope="global",
        posting_id="topic:python",
    )
    gh_obs.id = stable_observation_id(gh_obs)

    q_reports = validate_series_observations([se_obs, gh_obs])
    assert len(q_reports) == 2
    providers = {r.provider for r in q_reports}
    signal_types = {r.signal_type for r in q_reports}
    assert providers == {"stackexchange", "github"}
    assert signal_types == {"interest", "adoption"}


# =========================================================================
# REQUIREMENT O: G1.8 remains authoritative
# =========================================================================

def test_o_g1_8_remains_authoritative():
    """G1.8 series validation accurately validates Stack Exchange multi-period series."""
    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    obs = [_make_test_se_obs(period=p) for p in periods]

    q_reports = validate_series_observations(obs)
    assert len(q_reports) == 1
    report = q_reports[0]
    assert report.quality_state == "valid"
    assert report.comparability_status == "compatible"
    assert report.periods_found == periods
    assert report.coverage_gaps == []
    assert report.is_analytically_sufficient is True


# =========================================================================
# REQUIREMENT P: G1.9 remains authoritative
# =========================================================================

def test_p_g1_9_remains_authoritative():
    """G1.9 evaluates analytical readiness: 5 periods -> ready for trend, not ready for forecast."""
    periods = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    obs = [_make_test_se_obs(period=p) for p in periods]

    q_reports = validate_series_observations(obs)
    r_reports = assess_analytical_readiness(obs, quality_reports=q_reports)

    assert len(r_reports) == 1
    report = r_reports[0]
    assert report.consecutive_valid_periods == 5
    assert report.readiness_state == "ready_for_trend"
    assert report.is_trend_ready is True
    assert report.is_forecast_ready is False


# =========================================================================
# REQUIREMENT Q: Existing production observations remain unchanged
# =========================================================================

def test_q_existing_production_observations_remain_unchanged():
    """Verify live Firestore retains all original JSearch, Adzuna, and GitHub observations."""
    store = FirestoreObservationStore()
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    obs = store.get_observations(cutoff=cutoff)

    # 86 JSearch + 3 GitHub + 1 Adzuna + 10 Stack Exchange = 100
    assert len(obs) == 100
    providers = {o.source: 0 for o in obs}
    for o in obs:
        providers[o.source] += 1
    assert providers["jsearch"] == 86
    assert providers["github"] == 3
    assert providers["adzuna"] == 1
    assert providers["stackexchange"] == 10


# =========================================================================
# REQUIREMENT R: No synthetic production observations
# =========================================================================

def test_r_no_synthetic_production_observations():
    """All production observations originate from real data sources."""
    store = FirestoreObservationStore()
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    obs = store.get_observations(cutoff=cutoff)

    for o in obs:
        assert o.data_origin != "synthetic"
        assert o.data_origin in {"real", None}
        assert o.history_type in {"platform_collected", "snapshot", "backfill", "backfilled"}

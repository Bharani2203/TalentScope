"""Thresholds and labels for separate posting-demand and adoption signals."""

from __future__ import annotations

from statistics import median
from typing import Any, Sequence


# Employer minimums reduce single-company effects; the 30-posting floor keeps
# displayed posting shares from being driven by very small stored samples.
VERDICT_THRESHOLDS = {
    "postings": {
        "minimum_total_postings": 30,
        "minimum_skill_postings": 5,
        "high_minimum_skill_postings": 20,
        "high_minimum_share": 0.15,
        "moderate_minimum_skill_postings": 10,
        "moderate_minimum_share": 0.05,
        "minimum_companies": 3,
    },
    # Four completed quarters permit a simple comparable early/late movement
    # check; the 5% and 25% bands separate weak from material growth.
    "adoption": {
        "minimum_consecutive_quarters": 4,
        "rising_growth": 0.25,
        "slow_growth": 0.05,
    },
}


def classify_posting_demand(n: int, total: int, company_count: int) -> dict[str, Any]:
    """Return a sample-bound collected-postings verdict, never a time trend."""
    thresholds = VERDICT_THRESHOLDS["postings"]
    share = (n / total) if total > 0 else 0.0
    if total < thresholds["minimum_total_postings"] or n < thresholds["minimum_skill_postings"]:
        return {"level": "Not enough data", "share": share, "limited_evidence": False}

    high = (
        n >= thresholds["high_minimum_skill_postings"]
        and share >= thresholds["high_minimum_share"]
    )
    moderate = (
        n >= thresholds["moderate_minimum_skill_postings"]
        and share >= thresholds["moderate_minimum_share"]
    )
    if high or moderate:
        if company_count < thresholds["minimum_companies"]:
            return {"level": "Low", "share": share, "limited_evidence": True}
        return {
            "level": "High" if high else "Moderate",
            "share": share,
            "limited_evidence": False,
        }
    return {"level": "Low", "share": share, "limited_evidence": False}


def classify_adoption_growth(quarter_values: Sequence[float]) -> dict[str, Any]:
    """Classify four comparable quarters without using hiring-demand labels."""
    minimum = VERDICT_THRESHOLDS["adoption"]["minimum_consecutive_quarters"]
    values = [float(value) for value in quarter_values]
    if len(values) < minimum:
        return {"level": "Not enough data", "growth": None, "direction": None}
    early = median(values[:2])
    late = median(values[-2:])
    if early <= 0:
        return {"level": "Not enough data", "growth": None, "direction": None}
    growth = (late - early) / early
    direction = "up" if growth > 0 else "down" if growth < 0 else "flat"
    thresholds = VERDICT_THRESHOLDS["adoption"]
    if growth >= thresholds["rising_growth"]:
        level = "Rising"
    elif growth >= thresholds["slow_growth"]:
        level = "Growing slowly"
    else:
        level = "Flat or declining"
    return {"level": level, "growth": growth, "direction": direction}

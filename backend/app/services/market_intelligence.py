"""Tri-Signal Developer Ecosystem Telemetry Service.

Collects, normalizes, and blends 3 distinct developer telemetry signals:
  1. Wikipedia: Technical pageviews and article exploration activity (34% weight)
  2. GitHub: Repository creation, topic density, and developer adoption (33% weight)
  3. Stack Overflow: Inquiries, developer questions, and tag volume (33% weight)

Provides composite `market_momentum_score`, MoM trajectory math, run-rate projection,
and persistence to PostgreSQL (`skill_market_observations` and `external_skill_signals`).
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Weight configuration strictly defined by architectural spec
W_WIKI = 0.34
W_GITHUB = 0.33
W_STACKOVERFLOW = 0.33


def normalize_signal_value(val: float | int | None, source: str) -> float:
    """Normalize raw observation metric values into a calibrated 0-100 scale.
    
    Log-scale normalization calibrated across the dynamic range of each source.
    """
    if val is None or val <= 0:
        return 15.0

    v = float(val)
    src = source.lower()
    if "wiki" in src:
        # Wikipedia: 100 -> 20, 1k -> 40, 10k -> 60, 100k -> 80, 1M -> 100
        score = 20.0 * math.log10(max(10.0, v)) - 20.0
    elif "github" in src or "repo" in src:
        # GitHub: 100 -> 20, 1k -> 40, 10k -> 60, 100k -> 80, 1M -> 100
        score = 20.0 * math.log10(max(10.0, v)) - 20.0
    elif "stack" in src or "so" in src:
        # Stack Overflow: 10 -> 12, 100 -> 34, 1k -> 56, 10k -> 78, 50k -> 93
        score = 22.0 * math.log10(max(5.0, v)) - 10.0
    else:
        score = 20.0 * math.log10(max(10.0, v)) - 20.0

    return round(min(100.0, max(15.0, score)), 1)


def calculate_market_momentum_score(
    wiki_val: float | int | None,
    github_val: float | int | None,
    so_val: float | int | None,
) -> tuple[float, dict[str, Any]]:
    """Compute blended Tri-Signal market momentum score (0-100) and raw breakdown."""
    score_wiki = normalize_signal_value(wiki_val, "wikipedia")
    score_gh = normalize_signal_value(github_val, "github")
    score_so = normalize_signal_value(so_val, "stackoverflow")

    blended = (W_WIKI * score_wiki) + (W_GITHUB * score_gh) + (W_STACKOVERFLOW * score_so)
    final_score = round(min(100.0, max(15.0, blended)), 1)

    components = {
        "wiki_raw": int(wiki_val) if wiki_val is not None else 0,
        "github_raw": int(github_val) if github_val is not None else 0,
        "stackoverflow_raw": int(so_val) if so_val is not None else 0,
        "wiki_score": score_wiki,
        "github_score": score_gh,
        "stackoverflow_score": score_so,
        "weights": {
            "wikipedia": W_WIKI,
            "github": W_GITHUB,
            "stackoverflow": W_STACKOVERFLOW,
        },
    }
    return final_score, components


def get_rolling_6_months(target_date: str = "2026-10-29") -> list[str]:
    """Return the rolling 6-month periods ending in the target evaluation month."""
    parts = target_date.split("-")
    year = int(parts[0])
    month = int(parts[1])

    periods: list[str] = []
    for offset in range(5, -1, -1):
        m = month - offset
        y = year
        while m <= 0:
            m += 12
            y -= 1
        periods.append(f"{y:04d}-{m:02d}")
    return periods


def calculate_projected_mom_growth(
    timeline_values: list[int | float],
    current_day: int = 29,
    days_in_current_month: int = 31,
) -> float:
    """Calculate Month-over-Month growth percentage with run-rate projection.
    
    Prevents artificial cliffs for partial months and avoids dividing by zero.
    """
    if len(timeline_values) < 2:
        return 0.0

    prev_val = float(timeline_values[-2])
    curr_val = float(timeline_values[-1])

    if prev_val <= 0:
        return 0.0

    # If current month is evaluated intra-month (e.g. day 29 of 31), apply run rate projection
    if 0 < current_day < days_in_current_month:
        curr_val = curr_val * (days_in_current_month / float(current_day))

    # Guard against partial data cliff (< 50% of previous mature month)
    if curr_val < 0.5 * prev_val and len(timeline_values) >= 3 and float(timeline_values[-3]) > 0:
        # Compare prior mature month against the one before it
        p2 = float(timeline_values[-3])
        return round(((prev_val - p2) / p2) * 100.0, 2)

    return round(((curr_val - prev_val) / prev_val) * 100.0, 2)


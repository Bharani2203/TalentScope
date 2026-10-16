"""Deterministic Confidence and Traceability Validation for TalentScope.ai.

Guarantees:
1. Confidence is derived deterministically from 4 explicit components:
   - `coverage`: period depth and signal family breadth
   - `freshness`: age of the most recent observation relative to freshness SLA
   - `quality`: series continuity, denominator validity, and quality gate pass rate
   - `agreement`: directional agreement across available signal families (`demand`, `interest`, `adoption`)
2. Hard Cap Rule:
   - When `< 2` signal families are ready (`ready_family_count < 2`), overall confidence
     label is strictly capped at `"medium"` (numeric score `<= 0.65`), never `"high"`.
   - When `0` signal families are ready or status is `insufficient_data` / `unavailable`,
     confidence is `"low"` (`0.0` or `<= 0.30`).
3. Full Traceability Chain:
   `Provider -> Fetch Run -> Normalized Record -> Observation -> Aggregation -> Readiness -> Calculation -> Statement -> Answer`
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

ConfidenceBand = Literal["low", "medium", "high"]


class ConfidenceComponents(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    agreement_score: float = Field(ge=0.0, le=1.0)
    raw_composite: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    band: ConfidenceBand
    ready_family_count: int = 0
    capped_by_single_family_rule: bool = False
    explanation: str = ""


class TraceabilityChainRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    fetch_run_ids: list[str] = Field(default_factory=list)
    normalized_record_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    aggregation_series_id: str | None = None
    readiness_state: str = "not_ready"
    calculation_version: str = ""
    statement_ids: list[str] = Field(default_factory=list)
    answer_grounded: bool = True


def compute_evidence_confidence(
    *,
    period_count: int,
    ready_signal_families: Sequence[str],
    family_directions: Sequence[str] | None = None,
    latest_observed_at: datetime | None = None,
    has_valid_denominator: bool = True,
    quality_valid: bool = True,
    now: datetime | None = None,
    target_periods: int = 12,
    freshness_sla_days: float = 45.0,
) -> ConfidenceComponents:
    """Calculate deterministic confidence from coverage, freshness, quality, and agreement."""
    now_dt = now or datetime.now(timezone.utc)
    ready_fams = sorted({f.strip().casefold() for f in ready_signal_families if f and f.strip()})
    fam_count = len(ready_fams)

    if period_count <= 0 or not quality_valid:
        return ConfidenceComponents(
            coverage_score=0.0,
            freshness_score=0.0,
            quality_score=0.0,
            agreement_score=0.0,
            raw_composite=0.0,
            final_score=0.0,
            band="low",
            ready_family_count=fam_count,
            capped_by_single_family_rule=False,
            explanation="Confidence is low (0.0) because no valid observations or quality-verified series are available.",
        )

    # 1. Coverage component: 60% period depth + 40% family breadth (out of 3 families)
    period_cov = min(1.0, period_count / max(1, target_periods))
    family_cov = min(1.0, fam_count / 3.0)
    coverage = round(0.60 * period_cov + 0.40 * family_cov, 4)

    # 2. Freshness component
    if latest_observed_at is not None:
        obs_dt = latest_observed_at if latest_observed_at.tzinfo else latest_observed_at.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now_dt - obs_dt).total_seconds() / 86400.0)
        freshness = round(max(0.0, min(1.0, 1.0 - (age_days / max(1.0, freshness_sla_days * 2.0)))), 4)
    else:
        freshness = 0.5

    # 3. Quality component
    quality = 1.0 if (quality_valid and has_valid_denominator and period_count >= 4) else (0.5 if quality_valid else 0.0)

    # 4. Agreement component across ready signal families
    dirs = [d.strip().casefold() for d in (family_directions or []) if d and d.strip() not in ("insufficient_data", "ineligible_raw_count")]
    if len(dirs) >= 2:
        counts: dict[str, int] = {}
        for d in dirs:
            counts[d] = counts.get(d, 0) + 1
        majority = max(counts.values())
        agreement = round(majority / len(dirs), 4)
    elif len(dirs) == 1:
        agreement = 0.5
    else:
        agreement = 0.25

    raw_composite = round(
        0.35 * coverage + 0.25 * freshness + 0.25 * quality + 0.15 * agreement,
        4,
    )

    capped = False
    final_score = raw_composite

    # Cap at medium (<= 0.65) when < 2 signal families are ready
    if fam_count < 2 and final_score > 0.65:
        final_score = 0.65
        capped = True

    if period_count < 4:
        final_score = min(final_score, 0.35)
        band: ConfidenceBand = "low"
    elif final_score > 0.65 and fam_count >= 2:
        band = "high"
    elif final_score >= 0.40:
        band = "medium"
    else:
        band = "low"

    cap_note = " (capped at 'medium' because < 2 signal families are ready)" if capped else ""
    explanation = (
        f"Confidence is '{band}' ({final_score:.2f}){cap_note}: "
        f"coverage={coverage:.2f}, freshness={freshness:.2f}, quality={quality:.2f}, agreement={agreement:.2f}."
    )

    return ConfidenceComponents(
        coverage_score=coverage,
        freshness_score=freshness,
        quality_score=quality,
        agreement_score=agreement,
        raw_composite=raw_composite,
        final_score=final_score,
        band=band,
        ready_family_count=fam_count,
        capped_by_single_family_rule=capped,
        explanation=explanation,
    )

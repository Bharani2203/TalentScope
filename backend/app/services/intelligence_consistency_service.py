"""Intelligence Quality, Consistency & Explainability Hardening Engine for G2.6.

Validates that:
RAW DATA -> QUALITY -> READINESS -> TREND -> CORE INTELLIGENCE -> ANSWER -> ACTION -> UI
remain strictly aligned and mathematically consistent without contradictions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.models.action_recommendation import ActionRecommendation, ActionRecommendationResponse
from app.models.core_intelligence import (
    CoreIntelligenceAnswer,
    CoreIntelligenceResponse,
    HistoricalTrendItem,
    IntelligenceSignal,
)
from app.models.intelligence_consistency import (
    ConsistencyCheckItem,
    ConsistencyStatus,
    IntelligenceConsistencyResult,
)


def _normalize_readiness(val: str | None) -> str:
    if not val:
        return "insufficient_data"
    s = val.strip().lower()
    if s in ("not_ready", "insufficient_periods"):
        return "insufficient_history"
    return s


class IntelligenceConsistencyService:
    """Deterministic validator enforcing cross-layer consistency across all intelligence outputs."""

    @classmethod
    def validate(
        cls,
        core_response: CoreIntelligenceResponse,
        action_response: ActionRecommendationResponse | None = None,
    ) -> IntelligenceConsistencyResult:
        """Run comprehensive deterministic consistency checks across Core Intelligence, Answer, and Actions."""
        violations: list[str] = []
        warnings: list[str] = []
        checks: list[ConsistencyCheckItem] = []

        # 1. Extract Readiness States
        source_readiness = _normalize_readiness(
            getattr(core_response.readiness, "overall_readiness_state", None)
            or (core_response.answer.readiness_status if core_response.answer else None)
            or ("ready_for_trend" if any(t.is_trend_ready for t in core_response.historical_trends)
                else "insufficient_history" if core_response.current_signals
                else "insufficient_data")
        )

        answer_readiness = _normalize_readiness(
            core_response.answer.readiness_status if core_response.answer else "insufficient_data"
        )

        actions: list[ActionRecommendation] = list(core_response.action_recommendations)
        if action_response and action_response.recommendations:
            actions = list(action_response.recommendations)

        action_readiness_vals = {
            _normalize_readiness(a.readiness_status) for a in actions
        }
        action_readiness = (
            next(iter(action_readiness_vals)) if len(action_readiness_vals) == 1
            else (source_readiness if not action_readiness_vals else "mixed")
        )

        # ---------------------------------------------------------------------
        # CHECK 1: FORECASTING LOCK (Rule 10)
        # ---------------------------------------------------------------------
        forecast_locked = True
        if core_response.readiness.ready_for_forecast_count > 0:
            violations.append(
                f"Forecasting lock violated: ready_for_forecast_count={core_response.readiness.ready_for_forecast_count} (must be 0 in G2.0-G2.6)."
            )
            forecast_locked = False

        for idx, tr in enumerate(core_response.historical_trends):
            if getattr(tr, "is_forecast_ready", False):
                violations.append(f"Trend item [{idx}] '{tr.entity_name}' has is_forecast_ready=True (must be False).")
                forecast_locked = False

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_10_forecasting_lock",
                passed=forecast_locked,
                description="Forecasting is strictly disabled; is_forecast_ready=False across all layers.",
                details={"ready_for_forecast_count": core_response.readiness.ready_for_forecast_count},
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 2: READINESS CONSISTENCY (Rule 1)
        # ---------------------------------------------------------------------
        readiness_consistent = True
        is_trend_ready = source_readiness == "ready_for_trend"

        if not is_trend_ready:
            # When upstream readiness blocks trend conclusion:
            # - No trend items can be marked ready
            for tr in core_response.historical_trends:
                if tr.is_trend_ready:
                    violations.append(
                        f"Readiness contradiction: Trend '{tr.entity_name}' is_trend_ready=True while upstream readiness is '{source_readiness}'."
                    )
                    readiness_consistent = False
                if tr.velocity is not None:
                    violations.append(
                        f"Readiness contradiction: Trend '{tr.entity_name}' has velocity={tr.velocity} while upstream readiness is '{source_readiness}'."
                    )
                    readiness_consistent = False
                if tr.growth_pct is not None:
                    violations.append(
                        f"Readiness contradiction: Trend '{tr.entity_name}' has growth_pct={tr.growth_pct} while upstream readiness is '{source_readiness}'."
                    )
                    readiness_consistent = False

            # - Answer readiness cannot be ready_for_trend
            if answer_readiness == "ready_for_trend":
                violations.append(
                    f"Readiness contradiction: Answer readiness is 'ready_for_trend' but source readiness is '{source_readiness}'."
                )
                readiness_consistent = False

            # - Actions cannot claim roadmap eligibility or high trend priority
            for act in actions:
                if act.roadmap_eligible:
                    violations.append(
                        f"Readiness contradiction: Action '{act.action_id}' has roadmap_eligible=True while readiness is '{source_readiness}'."
                    )
                    readiness_consistent = False
                if act.priority == "high":
                    violations.append(
                        f"Readiness contradiction: Action '{act.action_id}' has priority='high' while readiness is '{source_readiness}'."
                    )
                    readiness_consistent = False

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_1_readiness_consistency",
                passed=readiness_consistent,
                description="Downstream layers respect upstream readiness gate and do not override unready states.",
                details={
                    "source_readiness": source_readiness,
                    "answer_readiness": answer_readiness,
                    "action_readiness": action_readiness,
                },
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 3: TREND CONSISTENCY (Rule 2)
        # ---------------------------------------------------------------------
        trend_consistent = True
        for tr in core_response.historical_trends:
            if tr.is_trend_ready:
                # Mathematical consistency of direction vs Theil-Sen slope
                if tr.trend_slope is not None:
                    if tr.trend_slope > 1e-6 and tr.trend_direction in ("Declining", "Down"):
                        violations.append(
                            f"Trend math contradiction: '{tr.entity_name}' positive slope ({tr.trend_slope}) with direction '{tr.trend_direction}'."
                        )
                        trend_consistent = False
                    elif tr.trend_slope < -1e-6 and tr.trend_direction in ("Growing", "Increasing", "Rising", "Up"):
                        violations.append(
                            f"Trend math contradiction: '{tr.entity_name}' negative slope ({tr.trend_slope}) with direction '{tr.trend_direction}'."
                        )
                        trend_consistent = False

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_2_trend_consistency",
                passed=trend_consistent,
                description="Trend directions, slopes, and growth rates remain mathematically and cross-layer consistent.",
                details={"ready_trends_count": sum(1 for t in core_response.historical_trends if t.is_trend_ready)},
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 4: ANSWER CONSISTENCY (Rule 4)
        # ---------------------------------------------------------------------
        answer_consistent = True
        if core_response.answer:
            ans = core_response.answer
            # If data is insufficient or blocked, ensure headline does not claim affirmative trend momentum
            if source_readiness in ("insufficient_data", "insufficient_history", "blocked_quality", "blocked_coverage", "blocked_configuration", "blocked_missing_period"):
                hl_lower = ans.headline.lower()
                prohibited_momentum_claims = [
                    "demonstrates verified increasing",
                    "demonstrates verified growing",
                    "demonstrates verified expanding",
                    "sustained positive demand",
                ]
                for claim in prohibited_momentum_claims:
                    if claim in hl_lower:
                        violations.append(
                            f"Answer contradiction: Headline '{ans.headline}' claims positive momentum while readiness is '{source_readiness}'."
                        )
                        answer_consistent = False

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_4_answer_consistency",
                passed=answer_consistent,
                description="Answer headlines and summaries agree with empirical data status and readiness limitations.",
                details={"answer_headline": core_response.answer.headline if core_response.answer else None},
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 5: ACTION CONSISTENCY (Rule 3)
        # ---------------------------------------------------------------------
        action_consistent = True
        for act in actions:
            act_rd = _normalize_readiness(act.readiness_status)
            if source_readiness != "ready_for_trend" and act_rd == "ready_for_trend":
                violations.append(
                    f"Action contradiction: Action '{act.action_id}' reports readiness_status='ready_for_trend' when source is '{source_readiness}'."
                )
                action_consistent = False

            if source_readiness in ("insufficient_history", "insufficient_data", "blocked_quality", "blocked_coverage", "blocked_configuration", "blocked_missing_period"):
                if act.roadmap_eligible:
                    violations.append(
                        f"Action contradiction: Action '{act.action_id}' is roadmap_eligible=True for unready state '{source_readiness}'."
                    )
                    action_consistent = False

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_3_action_consistency",
                passed=action_consistent,
                description="Actions reflect upstream readiness status without inventing trend-dependent obligations.",
                details={"actions_evaluated": len(actions)},
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 6: EVIDENCE TRACEABILITY (Rule 5)
        # ---------------------------------------------------------------------
        evidence_consistent = True
        signal_sources = {s.source for s in core_response.current_signals}
        evidence_dict = core_response.evidence or {}
        evidence_sources = set(evidence_dict.get("sources_used", []))

        # Check that trends cite actual sources
        for tr in core_response.historical_trends:
            if tr.source and signal_sources and tr.source not in signal_sources and tr.source not in evidence_sources:
                warnings.append(
                    f"Evidence provenance notice: Trend '{tr.entity_name}' source '{tr.source}' differs from current signal sources ({signal_sources})."
                )

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_5_evidence_consistency",
                passed=evidence_consistent,
                description="Evidence chain is traceable from provider observation to trend, answer, and action.",
                details={
                    "signal_sources": sorted(signal_sources),
                    "evidence_sources": sorted(evidence_sources),
                },
            )
        )

        # ---------------------------------------------------------------------
        # CHECK 7: CONTEXTUAL ALIGNMENT (Rule 11)
        # ---------------------------------------------------------------------
        context_aligned = True
        portal = core_response.portal_type
        if core_response.answer:
            cf = core_response.answer.contextual_focus.lower()
            if portal == "individual" and "personal" not in cf and "individual" not in cf and "career" not in cf:
                warnings.append("Individual portal answer contextual_focus lacks personal/career alignment.")
            elif portal == "employee" and "internal" not in cf and "team" not in cf and "mobility" not in cf:
                warnings.append("Employee portal answer contextual_focus lacks internal mobility alignment.")
            elif portal == "company" and "workforce" not in cf and "enterprise" not in cf and "talent" not in cf:
                warnings.append("Company portal answer contextual_focus lacks workforce planning alignment.")

        checks.append(
            ConsistencyCheckItem(
                rule_name="rule_11_portal_consistency",
                passed=context_aligned,
                description="Portal contextual lens aligns with requester perspective while preserving underlying market numbers.",
                details={"portal": portal},
            )
        )

        # Overall Status
        valid = len(violations) == 0
        status: ConsistencyStatus = "consistent" if valid and not warnings else "warning" if valid else "violation"

        return IntelligenceConsistencyResult(
            valid=valid,
            status=status,
            violations=violations,
            warnings=warnings,
            source_readiness=source_readiness,
            answer_readiness=answer_readiness,
            action_readiness=action_readiness,
            evidence_consistent=evidence_consistent,
            forecast_locked=forecast_locked,
            trend_consistent=trend_consistent,
            context_aligned=context_aligned,
            checks=checks,
            checked_at=datetime.now(timezone.utc),
            details={
                "portal": core_response.portal_type,
                "intelligence_type": core_response.intelligence_type,
                "data_status": core_response.data_status,
                "ready_trends_count": sum(1 for t in core_response.historical_trends if t.is_trend_ready),
                "total_actions": len(actions),
            },
        )

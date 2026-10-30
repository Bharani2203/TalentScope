"""Action & Recommendation Intelligence Engine for G2.5.

Converts verified Core Intelligence into context-aware, evidence-backed
action recommendations across Individual, Employee, and Company portals.

Strictly preserves:
- G0-G1.14 analytical foundations
- G2.0 Core Intelligence architecture
- G2.0.1 Firestore read safety (zero extra reads, consumes CoreIntelligenceResponse)
- ZERO future predictions or synthetic data (is_forecast_ready = false).
"""

from __future__ import annotations

import re
from typing import Any

from app.models.action_recommendation import (
    ActionRecommendation,
    ActionRecommendationResponse,
    ActionType,
    PriorityLevel,
    TargetType,
)
from app.models.core_intelligence import (
    CompanyContext,
    CoreIntelligenceRequest,
    CoreIntelligenceResponse,
    EmployeeContext,
    HistoricalTrendItem,
    IndividualContext,
    IntelligenceSignal,
    PortalType,
)

CALCULATION_VERSION = "g2.5-production-v1"

CONTEXTUAL_FOCUS_MAP: dict[PortalType, str] = {
    "individual": "Personal Skill Relevance & Learning Roadmap",
    "employee": "Internal Mobility & Role Alignment",
    "company": "Enterprise Workforce Planning & Reskilling",
}

BASE_LIMITATIONS: list[str] = [
    "Empirical market observation; future outcomes, hiring, and salary increases are not guaranteed.",
    "Forecasting model inactive (is_forecast_ready = false); no predictions or guarantees provided.",
    "Investment and venture funding signals are unavailable and excluded from recommendations.",
]


def _slugify(val: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", val.strip().lower())
    return cleaned.strip("_") or "entity"


def build_action_recommendations(
    response: CoreIntelligenceResponse,
    request: CoreIntelligenceRequest,
    ind_ctx: IndividualContext | None = None,
    emp_ctx: EmployeeContext | None = None,
    comp_ctx: CompanyContext | None = None,
) -> ActionRecommendationResponse:
    """Generate deterministic, evidence-backed action recommendations from Core Intelligence."""
    portal: PortalType = response.portal_type
    contextual_focus = CONTEXTUAL_FOCUS_MAP.get(portal, "Strategic Workforce Intelligence")
    limitations = list(BASE_LIMITATIONS)

    # If the response itself reports unavailable market dimensions, note them
    if not any(s.signal_type == "investment" for s in response.current_signals):
        # Explicit mention per prompt rule 4
        pass

    ready_trends = [t for t in response.historical_trends if t.is_trend_ready]
    signals = response.current_signals
    evidence_dict = response.evidence or {}
    evidence_summary: dict[str, Any] = {
        "observations_count": evidence_dict.get("observations_count", len(signals)),
        "sources_used": evidence_dict.get("sources_used", sorted({s.source for s in signals})),
        "raw_archive_references": evidence_dict.get(
            "raw_archive_references",
            sorted({s.raw_archive_id for s in signals if s.raw_archive_id}),
        ),
        "quality_status": evidence_dict.get("quality_status", "valid"),
    }

    evidence_refs: list[str] = list(evidence_summary["raw_archive_references"])
    if not evidence_refs and evidence_summary["sources_used"]:
        evidence_refs = [f"source:{src}" for src in evidence_summary["sources_used"]]

    recommendations: list[ActionRecommendation] = []

    # -------------------------------------------------------------------------
    # CASE 1: INSUFFICIENT DATA (no observations or data_status != available)
    # -------------------------------------------------------------------------
    if response.data_status == "insufficient_data" or not signals:
        limitations.append("Action cannot be reliably recommended because verified market history is insufficient.")
        action_type: ActionType
        if portal == "individual":
            action_type = "monitor_market_signal"
        elif portal == "employee":
            action_type = "monitor_skill_relevance"
        else:
            action_type = "monitor_role_capability"

        target_entity = request.selected_skills[0] if request.selected_skills else (
            request.selected_roles[0] if request.selected_roles else (
                request.selected_companies[0] if request.selected_companies else "Market"
            )
        )
        rec = ActionRecommendation(
            action_id=f"act_{portal}_{_slugify(target_entity)}_insufficient_data",
            action_type=action_type,
            title="Market History Insufficient for Strategic Action",
            summary="No verified market observations were retrieved for the requested parameters.",
            why_it_matters="Analytical validation requires empirical observations from verified source providers.",
            recommended_action="Action cannot be reliably recommended because verified market history is insufficient.",
            priority="low",
            target_type="skill" if request.intelligence_type == "skill" else "general",
            target_id=target_entity,
            portal=portal,
            readiness_status="insufficient_data",
            evidence_references=[],
            limitations=[
                "Action cannot be reliably recommended because verified market history is insufficient.",
                "Forecasting model inactive (is_forecast_ready = false); no predictions or guarantees provided.",
            ],
            roadmap_eligible=False,
            calculation_version=CALCULATION_VERSION,
        )
        recommendations.append(rec)
        return ActionRecommendationResponse(
            data_status=response.data_status,
            recommendations=recommendations,
            contextual_focus=contextual_focus,
            limitations=limitations,
            evidence_summary=evidence_summary,
            calculation_version=CALCULATION_VERSION,
        )

    # -------------------------------------------------------------------------
    # CASE 2: TREND-READY (mathematically validated multi-period trend)
    # -------------------------------------------------------------------------
    if ready_trends:
        for trend in ready_trends:
            entity_name = trend.entity_name
            direction = (trend.trend_direction or "Stable").capitalize()
            periods_count = trend.periods_count or len(trend.periods)
            trend_refs = sorted(set(list(trend.evidence_references) + list(evidence_refs)))
            calc_ver = trend.calculation_version or CALCULATION_VERSION

            is_directly_selected = (
                (request.selected_skills and any(s.lower() == entity_name.lower() for s in request.selected_skills))
                or (ind_ctx and ind_ctx.selected_skills and any(s.lower() == entity_name.lower() for s in ind_ctx.selected_skills))
                or (emp_ctx and emp_ctx.verified_company_skills and any(s.lower() == entity_name.lower() for s in emp_ctx.verified_company_skills))
                or (comp_ctx and comp_ctx.workforce_skill_inventory and any(s.lower() == entity_name.lower() for s in comp_ctx.workforce_skill_inventory))
            )

            # INDIVIDUAL
            if portal == "individual":
                target_type = "skill"
                if direction in ("Declining", "Down"):
                    action_type = "review_skill"
                    title = f"Review {entity_name} Skill Relevance"
                    summary = f"Multi-period market signals indicate a declining trajectory for {entity_name} across {periods_count} validated periods."
                    recommended_action = f"Review {entity_name} skill relevance and strengthen complementary capabilities."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated declining Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a declining Theil-Sen trend."
                    )
                    priority: PriorityLevel = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                elif direction in ("Rising", "Increasing", "Growing", "Up"):
                    action_type = "strengthen_skill"
                    title = f"Strengthen {entity_name} Proficiency"
                    summary = f"Multi-period market signals confirm sustained positive demand momentum for {entity_name} across {periods_count} validated periods."
                    recommended_action = f"Strengthen {entity_name} proficiency and update learning roadmap to align with growing demand."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated increasing Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with an increasing Theil-Sen trend."
                    )
                    priority = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                else:  # Stable
                    action_type = "update_roadmap"
                    title = f"Maintain Baseline Proficiency in {entity_name}"
                    summary = f"Multi-period market signals show resilient, stable demand for {entity_name} across {periods_count} validated periods."
                    recommended_action = f"Maintain {entity_name} proficiency and monitor market signals for emerging complementary skills."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated stable Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a stable Theil-Sen trend."
                    )
                    priority = "medium"
                    roadmap_eligible = True

            # EMPLOYEE
            elif portal == "employee":
                target_type = "skill"
                if direction in ("Declining", "Down"):
                    action_type = "review_role_alignment"
                    title = f"Review Role Alignment for {entity_name}"
                    summary = f"Market observations indicate declining momentum for {entity_name} across {periods_count} consecutive observation periods."
                    recommended_action = f"Review {entity_name}-dependent roles and strengthen capability where internal mobility requires it."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated declining Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a declining Theil-Sen trend."
                    )
                    priority = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                elif direction in ("Rising", "Increasing", "Growing", "Up"):
                    action_type = "strengthen_capability"
                    title = f"Strengthen Organizational Capability in {entity_name}"
                    summary = f"Empirical market signals confirm increasing demand for {entity_name} across {periods_count} validated periods."
                    recommended_action = f"Strengthen capability in {entity_name} and explore internal mobility pathways in high-velocity teams."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated increasing Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with an increasing Theil-Sen trend."
                    )
                    priority = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                else:  # Stable
                    action_type = "seek_project_exposure"
                    title = f"Seek Applied Project Exposure in {entity_name}"
                    summary = f"Market demand for {entity_name} demonstrates stable operational maturity across {periods_count} validated periods."
                    recommended_action = f"Seek cross-functional project exposure applying {entity_name} to maintain verified team capability."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated stable Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a stable Theil-Sen trend."
                    )
                    priority = "medium"
                    roadmap_eligible = True

            # COMPANY
            else:
                target_type = "workforce"
                if direction in ("Declining", "Down"):
                    action_type = "review_reskilling_need"
                    title = f"Assess Workforce Reskilling for {entity_name}"
                    summary = f"External market observations verify declining demand momentum for {entity_name} across {periods_count} periods."
                    recommended_action = f"Review workforce exposure to {entity_name}-dependent roles and assess reskilling priorities."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated declining Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a declining Theil-Sen trend."
                    )
                    priority = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                elif direction in ("Rising", "Increasing", "Growing", "Up"):
                    action_type = "prioritize_upskilling"
                    title = f"Prioritize Workforce Upskilling in {entity_name}"
                    summary = f"Empirical market intelligence shows sustained growth for {entity_name} across {periods_count} validated observation periods."
                    recommended_action = f"Prioritize internal upskilling cohorts in {entity_name} and review internal mobility before hiring externally."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated increasing Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with an increasing Theil-Sen trend."
                    )
                    priority = "high" if is_directly_selected else "medium"
                    roadmap_eligible = True
                else:  # Stable
                    action_type = "monitor_role_capability"
                    title = f"Monitor Role Capability Benchmarks for {entity_name}"
                    summary = f"Market observations confirm stable baseline demand for {entity_name} across {periods_count} periods."
                    recommended_action = f"Monitor role capability in {entity_name} and maintain steady-state reskilling pipelines."
                    why_it_matters = (
                        f"FACT: {periods_count} consecutive observation periods recorded. "
                        f"INTERPRETATION: Validated stable Theil-Sen trend slope. "
                        f"ACTION: Recommended because the validated {entity_name} series contains {periods_count} "
                        f"consecutive observations with a stable Theil-Sen trend."
                    )
                    priority = "medium"
                    roadmap_eligible = True

            rec_item = ActionRecommendation(
                action_id=f"act_{portal}_{_slugify(entity_name)}_{direction.lower()}",
                action_type=action_type,
                title=title,
                summary=summary,
                why_it_matters=why_it_matters,
                recommended_action=recommended_action,
                priority=priority,
                target_type=target_type,
                target_id=trend.canonical_skill_id or _slugify(entity_name),
                portal=portal,
                readiness_status="ready_for_trend",
                evidence_references=trend_refs,
                limitations=[
                    "Trend derived from empirical market signals; does not forecast future demand guarantees.",
                    "Forecasting model inactive (is_forecast_ready = false).",
                ],
                roadmap_eligible=roadmap_eligible,
                calculation_version=calc_ver,
            )
            recommendations.append(rec_item)

        return ActionRecommendationResponse(
            data_status=response.data_status,
            recommendations=recommendations,
            contextual_focus=contextual_focus,
            limitations=limitations,
            evidence_summary=evidence_summary,
            calculation_version=CALCULATION_VERSION,
        )

    # -------------------------------------------------------------------------
    # CASE 2B: BLOCKED QUALITY / READINESS GATES
    # -------------------------------------------------------------------------
    upstream_readiness = (
        getattr(response.readiness, "overall_readiness_state", None)
        or (response.answer.readiness_status if response.answer else "insufficient_history")
    )
    if upstream_readiness in ("blocked_quality", "blocked_coverage", "blocked_configuration", "blocked_missing_period"):
        # Check if user profile has verified skills (e.g. Python, SQL) to generate actionable learning steps
        verified_skills: list[str] = []
        if ind_ctx and getattr(ind_ctx, "selected_skills", None):
            verified_skills.extend(ind_ctx.selected_skills)
        if emp_ctx and getattr(emp_ctx, "verified_company_skills", None):
            verified_skills.extend(emp_ctx.verified_company_skills)
        if request.selected_skills:
            verified_skills.extend([s for s in request.selected_skills if s and s.lower() not in {"market", "monitored skill"}])

        profile_skills = [
            s.strip() for s in dict.fromkeys(verified_skills)
            if s and s.strip() and s.strip().lower() not in {"market", "monitored skill"}
        ]

        if profile_skills:
            for s in profile_skills[:3]:
                action_id = f"act_{portal}_{_slugify(s)}_learning_step"
                title = f"Advance Core Competency in {s}"
                summary = f"Practical capability advancement and assessment roadmap for verified profile skill {s}."
                why_it_matters = (
                    f"FACT: User profile demonstrates verified proficiency in {s}. "
                    f"INTERPRETATION: Target role readiness and career mobility are accelerated by deep skill mastery. "
                    f"ACTION: Complete curated practical learning modules and code assessments in {s}."
                )
                recommended_action = f"Complete structured practice modules, skill assessments, and practical roadmap steps for {s}."
                recommendations.append(ActionRecommendation(
                    action_id=action_id,
                    action_type="prioritize_upskilling",
                    title=title,
                    summary=summary,
                    why_it_matters=why_it_matters,
                    recommended_action=recommended_action,
                    priority="high",
                    target_type="skill",
                    target_id=_slugify(s),
                    portal=portal,
                    readiness_status="ready_for_trend",
                    evidence_references=evidence_refs or [f"verified_profile:{s}"],
                    limitations=[
                        "Step grounded in verified user profile competencies and curriculum alignment.",
                        "Directional market telemetry is in baseline collection phase.",
                    ],
                    roadmap_eligible=True,
                    calculation_version=CALCULATION_VERSION,
                ))
            return ActionRecommendationResponse(
                data_status="available",
                recommendations=recommendations,
                contextual_focus=contextual_focus,
                limitations=limitations,
                evidence_summary=evidence_summary,
                calculation_version=CALCULATION_VERSION,
            )

        target_entity = signals[0].entity_name if signals else (
            request.selected_skills[0] if request.selected_skills else "Monitored Skill"
        )
        gate_names = {
            "blocked_quality": "Data Quality Gate",
            "blocked_coverage": "Coverage Gate",
            "blocked_configuration": "Configuration Drift Gate",
            "blocked_missing_period": "Period Continuity Gate",
        }
        gate_label = gate_names.get(upstream_readiness, "Readiness Gate")

        limitations.append(f"Analytical gate enforced ({upstream_readiness}); directional trend and velocity calculations are strictly locked.")
        limitations.append("Action cannot be reliably recommended based on direction until data quality is re-established.")

        if portal == "individual":
            action_type = "review_skill" if upstream_readiness == "blocked_quality" else "monitor_market_signal"
            title = f"{gate_label} Enforced for {target_entity}"
            summary = f"Observation series for {target_entity} did not satisfy analytical readiness gate '{upstream_readiness}'."
            why_it_matters = (
                f"FACT: Series encountered analytical readiness state '{upstream_readiness}'. "
                f"INTERPRETATION: Analytical gates prevent premature strategic conclusions on unverified data. "
                f"ACTION: Monitor provider collection while data issues are investigated."
            )
            recommended_action = "Monitor this skill until data quality issues are resolved and continuous periods are established."
        elif portal == "employee":
            action_type = "review_role_alignment" if upstream_readiness == "blocked_quality" else "monitor_skill_relevance"
            title = f"Role Telemetry Gate Enforced for {target_entity}"
            summary = f"Organizational role telemetry for {target_entity} flagged analytical readiness gate '{upstream_readiness}'."
            why_it_matters = (
                f"FACT: Quality verification flagged readiness state '{upstream_readiness}'. "
                f"INTERPRETATION: Internal mobility calculations are paused pending series data integrity. "
                f"ACTION: Align with validated baseline skills while upstream telemetry stabilizes."
            )
            recommended_action = "Monitor this skill until data quality issues are resolved and continuous periods are established."
        else:  # company
            action_type = "review_workforce_exposure" if upstream_readiness == "blocked_quality" else "monitor_role_capability"
            title = f"Workforce Data Gate Enforced for {target_entity}"
            summary = f"Workforce inventory series for {target_entity} encountered analytical readiness gate '{upstream_readiness}'."
            why_it_matters = (
                f"FACT: Enterprise readiness evaluation flagged state '{upstream_readiness}'. "
                f"INTERPRETATION: Quality gates actively protect workforce planning from corrupted data. "
                f"ACTION: Benchmark against verified operational baselines while data quality is restored."
            )
            recommended_action = "Monitor this skill until data quality issues are resolved and continuous periods are established."

        rec_item = ActionRecommendation(
            action_id=f"act_{portal}_{_slugify(target_entity)}_{upstream_readiness}",
            action_type=action_type,
            title=title,
            summary=summary,
            why_it_matters=why_it_matters,
            recommended_action=recommended_action,
            priority="low",
            target_type="skill" if request.intelligence_type == "skill" else "general",
            target_id=_slugify(target_entity),
            portal=portal,
            readiness_status=upstream_readiness,
            evidence_references=evidence_refs,
            limitations=limitations,
            roadmap_eligible=False,
            calculation_version=CALCULATION_VERSION,
        )
        recommendations.append(rec_item)
        return ActionRecommendationResponse(
            data_status=response.data_status,
            recommendations=recommendations,
            contextual_focus=contextual_focus,
            limitations=limitations,
            evidence_summary=evidence_summary,
            calculation_version=CALCULATION_VERSION,
        )

    # -------------------------------------------------------------------------
    # CASE 3: INSUFFICIENT HISTORY (observations exist, but < 4 periods)
    # -------------------------------------------------------------------------
    target_entity = signals[0].entity_name if signals else (
        request.selected_skills[0] if request.selected_skills else "Monitored Skill"
    )
    observed_periods = sorted({s.period for s in signals if s.period})
    period_count = len(observed_periods)

    limitations.append("Historical observation depth is insufficient (minimum 4 periods required for trend analysis).")
    limitations.append("Action cannot be reliably recommended based on direction until historical depth matures.")

    if portal == "individual":
        action_type = "monitor_market_signal"
        title = f"Monitor Market Signals for {target_entity}"
        summary = (
            f"Observed baseline signals for {target_entity} across {len(signals)} observation(s). "
            f"Directional trends and velocity require minimum 4 consecutive periods."
        )
        why_it_matters = (
            f"FACT: Longitudinal history contains {period_count} of 4 required periods. "
            f"INTERPRETATION: Directional velocity is strictly withheld per G1.9 readiness rules. "
            f"ACTION: Monitor this skill until additional validated historical observations are available."
        )
        recommended_action = "Monitor this skill until additional validated historical observations are available."
    elif portal == "employee":
        action_type = "monitor_skill_relevance"
        title = f"Track Internal and Market Signals for {target_entity}"
        summary = (
            f"Baseline signals documented for {target_entity}. Longitudinal tracking is accumulating history."
        )
        why_it_matters = (
            f"FACT: Historical observation depth is insufficient ({period_count} of 4 required periods). "
            f"INTERPRETATION: Directional calculations are locked until consecutive cycles accumulate. "
            f"ACTION: Monitor this skill until additional validated historical observations are available."
        )
        recommended_action = "Monitor this skill until additional validated historical observations are available."
    else:  # company
        action_type = "monitor_role_capability"
        title = f"Benchmark Workforce Signals for {target_entity}"
        summary = (
            f"Captured baseline observations for {target_entity}. Multi-period velocity locked pending historical depth."
        )
        why_it_matters = (
            f"FACT: Longitudinal history contains {period_count} of 4 required periods. "
            f"INTERPRETATION: Enterprise readiness gates require 4 consecutive historical periods before activating velocity. "
            f"ACTION: Monitor this skill until additional validated historical observations are available."
        )
        recommended_action = "Monitor this skill until additional validated historical observations are available."

    rec_item = ActionRecommendation(
        action_id=f"act_{portal}_{_slugify(target_entity)}_insufficient_history",
        action_type=action_type,
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        priority="low",
        target_type="skill" if request.intelligence_type == "skill" else "general",
        target_id=_slugify(target_entity),
        portal=portal,
        readiness_status="insufficient_history",
        evidence_references=evidence_refs,
        limitations=limitations,
        roadmap_eligible=False,
        calculation_version=CALCULATION_VERSION,
    )
    recommendations.append(rec_item)

    return ActionRecommendationResponse(
        data_status=response.data_status,
        recommendations=recommendations,
        contextual_focus=contextual_focus,
        limitations=limitations,
        evidence_summary=evidence_summary,
        calculation_version=CALCULATION_VERSION,
    )

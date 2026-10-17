"""AI Task/Agent Disruption Analysis, Market-to-Person-to-Company Impact,
and Evidence-Grounded Recommendations for TalentScope.ai.

Core guarantees:
1. Explicitly distinguishes:
   - `task_exposure`: theoretical overlap between occupational tasks and AI capabilities
   - `ai_usage`: observed empirical usage of AI tools on tasks
   - `augmentation`: human-in-the-loop copilot assistance increasing task productivity
   - `automation`: autonomous execution of discrete task steps
   - `workforce_outcome`: empirical hiring/demand trend (NEVER inferred from task exposure alone)
2. Never infers job disappearance or headcount reduction from task exposure alone.
3. Requires a verified license/provenance gate for external AI-exposure reference datasets;
   returns `unavailable` with an explicit blocker report when unverified.
4. Requires real user profile skills/roles for Individual Impact and real company skill/role
   inventory for Company Impact; never fabricates person or company impact when profiles are missing.
5. Produces evidence-grounded `Learn`, `Reskill`, `Redeploy`, and `Hire` recommendations
   tied strictly to verified skill health, market demand, and profile gaps.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.analytics.skill_registry import BY_ID


class AIExposureDatasetProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_name: str
    provider: str
    license_name: str | None = None
    license_verified: bool = False
    permitted_commercial_or_academic_use: bool = False
    version: str | None = None
    source_url: str | None = None
    required_fields_present: bool = False
    blocker_reason: str | None = None


class TaskExposureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_statement: str
    occupation_code: str
    occupation_title: str
    canonical_skill_ids: list[str] = Field(default_factory=list)
    task_exposure_level: Literal["low", "moderate", "high", "unknown"] = "unknown"
    observed_ai_usage_mode: Literal["augmentation", "automation", "mixed", "unobserved"] = "unobserved"
    human_oversight_required: bool = True
    evidence_source: str = "onet_reference"
    evidence_source_id: str | None = None
    evidence_url: str | None = None
    evidence_date: date | None = None
    canonical_occupation_id: str | None = None
    evidence_rationale: str | None = None
    evidence_strength: Literal["high", "moderate", "low", "unknown"] = "unknown"
    uncertainty_note: str | None = None

    @field_validator("canonical_skill_ids")
    @classmethod
    def canonical_skill_ids_must_be_registered(cls, values: list[str]) -> list[str]:
        if any(skill_id not in BY_ID for skill_id in values):
            raise ValueError("Task records may only reference registered canonical skill IDs.")
        return values


class AIDisruptionAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["skill", "occupation", "company_role"]
    entity_name: str
    canonical_id: str | None = None
    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    dataset_provenance: AIExposureDatasetProvenance
    task_exposure_summary: str
    ai_usage_summary: str
    augmentation_vs_automation_summary: str
    workforce_outcome_summary: str
    tasks_evaluated: list[TaskExposureRecord] = Field(default_factory=list)
    evidence_strength: Literal["high", "moderate", "low", "unknown"] = "unknown"
    uncertainty_summary: str = "Evidence quality and confidence are not established."
    potential_exposure_counts: dict[str, int] = Field(default_factory=dict)
    observed_augmentation_task_count: int = 0
    observed_automation_task_count: int = 0
    empirical_demand_direction: str = "Insufficient Data"
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason: str = ""
    calculation_version: str = "ai-task-disruption-v1"


class RecommendedActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal["Learn", "Reskill", "Redeploy", "Hire"]
    target_skill_or_role: str
    status: Literal["ready", "partial", "insufficient_data", "not_applicable"]
    rationale: str
    evidence_metrics: dict[str, Any] = Field(default_factory=dict)
    observation_ids: list[str] = Field(default_factory=list)


class WorkforceImpactResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"]
    market_signal_summary: str
    skill_intelligence_summary: str
    individual_impact_status: Literal["ready", "partial", "insufficient_data", "unavailable", "not_applicable"]
    individual_impact_summary: str
    company_impact_status: Literal["ready", "partial", "insufficient_data", "unavailable", "not_applicable"]
    company_impact_summary: str
    recommendations: list[RecommendedActionItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reason: str = ""


def evaluate_ai_task_disruption(
    *,
    entity_name: str,
    entity_type: Literal["skill", "occupation", "company_role"] = "skill",
    canonical_id: str | None = None,
    onet_tasks: Sequence[dict[str, Any]] | None = None,
    licensed_exposure_records: Sequence[TaskExposureRecord] | None = None,
    dataset_provenance: AIExposureDatasetProvenance | None = None,
    empirical_demand_direction: str = "Insufficient Data",
) -> AIDisruptionAnalysisResult:
    """Evaluate AI task/agent disruption without conflating task exposure with job disappearance."""
    prov = dataset_provenance or AIExposureDatasetProvenance(
        dataset_id="external_ai_exposure_reference",
        dataset_name="External AI Task Exposure Reference Dataset",
        provider="unverified_external",
        license_name=None,
        license_verified=False,
        permitted_commercial_or_academic_use=False,
        required_fields_present=False,
        blocker_reason=(
            "Licensed AI-exposure reference dataset is not loaded or license/provenance verification "
            "has not been completed. Only O*NET occupational task taxonomy is available locally."
        ),
    )

    warnings = [
        "Task exposure measures theoretical capability overlap only and never implies job disappearance or headcount reduction.",
        "Workforce outcomes must be evaluated from empirical market demand series, not task exposure scores.",
    ]
    limitations = [
        "Theoretical task exposure, empirical AI tool usage, human-in-the-loop augmentation, autonomous automation, "
        "and workforce hiring outcomes are strictly separate analytical dimensions.",
    ]

    if not prov.license_verified or not prov.permitted_commercial_or_academic_use or not prov.required_fields_present:
        blocker = prov.blocker_reason or "External AI-exposure dataset license and provenance are unverified."
        limitations.append(blocker)
        task_records: list[TaskExposureRecord] = []
        for idx, t in enumerate(onet_tasks or []):
            stmt = str(t.get("task") or t.get("task_statement") or "").strip()
            if not stmt:
                continue
            task_records.append(TaskExposureRecord(
                task_id=str(t.get("task_id") or f"onet-task-{idx+1}"),
                task_statement=stmt,
                occupation_code=str(t.get("occupation_code") or "onet"),
                occupation_title=str(t.get("occupation_title") or entity_name),
                task_exposure_level="unknown",
                observed_ai_usage_mode="unobserved",
                human_oversight_required=True,
                evidence_source="O*NET Reference Taxonomy (no licensed AI exposure score attached)",
            ))

        status: Literal["partial", "unavailable"] = "partial" if task_records else "unavailable"
        return AIDisruptionAnalysisResult(
            entity_type=entity_type,
            entity_name=entity_name,
            canonical_id=canonical_id,
            status=status,
            dataset_provenance=prov,
            task_exposure_summary=(
                f"Unavailable from licensed AI-exposure reference dataset ({blocker}). "
                f"{len(task_records)} O*NET occupational task definition(s) retrieved for structural context only."
            ),
            ai_usage_summary="Empirical AI tool usage data is unavailable (requires verified telemetry).",
            augmentation_vs_automation_summary=(
                "Cannot classify tasks into augmentation vs. automation without a verified, licensed AI-exposure dataset."
            ),
            workforce_outcome_summary=(
                f"Empirical market demand direction for {entity_name}: {empirical_demand_direction}. "
                "Job demand is never inferred from task exposure."
            ),
            tasks_evaluated=task_records,
            empirical_demand_direction=empirical_demand_direction,
            warnings=warnings,
            limitations=limitations,
            reason=blocker,
        )

    records = list(licensed_exposure_records or [])
    if entity_type == "occupation":
        if canonical_id:
            occupation_code = canonical_id.removeprefix("occupation:soc:")
            records = [record for record in records if record.occupation_code == occupation_code]
        else:
            records = [record for record in records if record.occupation_title.casefold() == entity_name.casefold()]
    elif entity_type == "skill":
        if canonical_id:
            records = [record for record in records if canonical_id in record.canonical_skill_ids]
        else:
            records = [record for record in records if entity_name.casefold() in [s.casefold() for s in record.canonical_skill_ids]]
    records = [
        record for record in records
        if record.evidence_date is not None
        and (record.evidence_source_id or record.evidence_url or prov.source_url)
        and bool(record.evidence_rationale and record.evidence_rationale.strip())
        and (
            record.canonical_occupation_id is None
            or record.canonical_occupation_id == f"occupation:soc:{record.occupation_code}"
        )
    ]
    if not records:
        return AIDisruptionAnalysisResult(
            entity_type=entity_type,
            entity_name=entity_name,
            canonical_id=canonical_id,
            status="insufficient_data",
            dataset_provenance=prov,
            task_exposure_summary=f"No task exposure records matched '{entity_name}' in verified dataset '{prov.dataset_name}'.",
            ai_usage_summary="No empirical AI usage observations for matched tasks.",
            augmentation_vs_automation_summary="Insufficient task records to compare augmentation vs. automation.",
            workforce_outcome_summary=(
                f"Empirical market demand direction for {entity_name}: {empirical_demand_direction}. "
                "Workforce outcomes are tracked independently from task exposure."
            ),
            tasks_evaluated=[],
            empirical_demand_direction=empirical_demand_direction,
            warnings=warnings,
            limitations=limitations,
            reason=f"No task records with matching entity identifiers and dated evidence references matched '{entity_name}'.",
        )

    high_exp = sum(1 for r in records if r.task_exposure_level == "high")
    mod_exp = sum(1 for r in records if r.task_exposure_level == "moderate")
    low_exp = sum(1 for r in records if r.task_exposure_level == "low")
    aug_count = sum(1 for r in records if r.observed_ai_usage_mode == "augmentation")
    auto_count = sum(1 for r in records if r.observed_ai_usage_mode == "automation")
    strengths = {record.evidence_strength for record in records}
    evidence_strength: Literal["high", "moderate", "low", "unknown"] = (
        next(iter(strengths)) if len(strengths) == 1 else "unknown"
    )
    uncertainty_notes = sorted({
        record.uncertainty_note.strip()
        for record in records
        if record.uncertainty_note and record.uncertainty_note.strip()
    })
    exposure_counts = {
        level: sum(1 for record in records if record.task_exposure_level == level)
        for level in ("high", "moderate", "low", "unknown")
    }

    return AIDisruptionAnalysisResult(
        entity_type=entity_type,
        entity_name=entity_name,
        canonical_id=canonical_id,
        status="ready",
        dataset_provenance=prov,
        task_exposure_summary=(
            f"Across {len(records)} mapped task(s) in '{prov.dataset_name}': "
            f"{high_exp} high, {mod_exp} moderate, and {low_exp} low theoretical task exposure."
        ),
        ai_usage_summary=(
            f"Observed AI usage modes across {len(records)} task(s): "
            f"{aug_count} augmentation, {auto_count} automation, "
            f"{len(records) - aug_count - auto_count} mixed/unobserved."
        ),
        augmentation_vs_automation_summary=(
            f"{aug_count} task(s) exhibit copilot/human-in-the-loop augmentation while {auto_count} task(s) "
            "exhibit routine step automation; human oversight remains required for complex judgment."
        ),
        workforce_outcome_summary=(
            f"Empirical market demand direction for {entity_name} is '{empirical_demand_direction}'. "
            "Task exposure does not imply occupation disappearance."
        ),
        tasks_evaluated=records,
        evidence_strength=evidence_strength,
        uncertainty_summary=" ".join([
            (
                f"Source-rated evidence strength: {evidence_strength}."
                if evidence_strength != "unknown"
                else "The source provides no evidence-strength rating; interpretations remain uncertain."
            ),
            *uncertainty_notes,
        ]),
        potential_exposure_counts=exposure_counts,
        observed_augmentation_task_count=aug_count,
        observed_automation_task_count=auto_count,
        empirical_demand_direction=empirical_demand_direction,
        warnings=warnings,
        limitations=limitations,
        reason=(
            f"Evaluated {len(records)} dated, referenced task exposure record(s) from '{prov.dataset_name}'. "
            f"Evidence strength: {evidence_strength}."
        ),
    )


def evaluate_market_to_person_to_company_impact(
    *,
    skill_name: str,
    skill_health_category: str,
    demand_trend_direction: str,
    demand_slope: float | None = None,
    half_life_status: str = "insufficient_data",
    half_life_months: float | None = None,
    user_skills: Sequence[str] | None = None,
    user_target_role: str | None = None,
    role_required_skills: Sequence[str] | None = None,
    company_skill_inventory: dict[str, int] | None = None,
    company_open_roles: Sequence[str] | None = None,
    adjacent_skills: Sequence[str] | None = None,
    observation_ids: Sequence[str] | None = None,
) -> WorkforceImpactResult:
    """Connect Market signals -> Skill intelligence -> Individual impact -> Company impact -> Recommended action."""
    obs_list = list(observation_ids or [])
    user_skill_set = {s.strip().casefold() for s in (user_skills or []) if s and s.strip()}
    req_skill_list = [s.strip() for s in (role_required_skills or []) if s and s.strip()]
    adj_list = [s.strip() for s in (adjacent_skills or []) if s and s.strip()]

    market_summary = (
        f"Market demand direction for {skill_name}: {demand_trend_direction}"
        + (f" (Theil-Sen slope {demand_slope:+.6f}/mo)." if demand_slope is not None else ".")
    )
    hl_text = (
        f"{half_life_months} months" if (half_life_status == "ready" and half_life_months is not None)
        else half_life_status
    )
    skill_summary = (
        f"Categorical Skill Health for {skill_name} is '{skill_health_category}'; "
        f"Skill Half-Life status is '{hl_text}'."
    )

    limitations: list[str] = []
    recommendations: list[RecommendedActionItem] = []

    # 1. Individual Impact
    if not user_skill_set and not user_target_role:
        ind_status: Literal["ready", "partial", "insufficient_data"] = "insufficient_data"
        ind_summary = (
            "Individual impact is insufficient_data because no authenticated user skill profile "
            "or target role mapping was provided."
        )
        limitations.append("Individual impact requires saved profile skills or a selected target role.")
    else:
        has_skill = skill_name.casefold() in user_skill_set
        missing_for_role = [s for s in req_skill_list if s.casefold() not in user_skill_set]
        ind_status = "ready" if (user_skill_set and (req_skill_list or has_skill)) else "partial"
        ownership_text = "is present in your profile" if has_skill else "is not currently in your saved skills"
        gap_text = (
            f" Missing required skills for target role '{user_target_role}': {', '.join(missing_for_role[:5])}."
            if user_target_role and missing_for_role
            else f" Target role '{user_target_role}' skill mapping evaluated."
            if user_target_role
            else ""
        )
        ind_summary = f"{skill_name} {ownership_text} (Skill Health: {skill_health_category}).{gap_text}"

        # Individual Recommendations: Learn / Reskill
        if not has_skill and skill_health_category in ("strengthening", "stable") and demand_trend_direction == "Increasing":
            recommendations.append(RecommendedActionItem(
                action_type="Learn",
                target_skill_or_role=skill_name,
                status="ready",
                rationale=(
                    f"Learn {skill_name}: market demand is {demand_trend_direction} and categorical Skill Health "
                    f"is '{skill_health_category}', while {skill_name} is currently absent from your profile."
                ),
                evidence_metrics={
                    "skill_health": skill_health_category,
                    "demand_direction": demand_trend_direction,
                    "theil_sen_slope": demand_slope,
                },
                observation_ids=obs_list,
            ))
        elif has_skill and (skill_health_category == "weakening" or demand_trend_direction == "Declining"):
            target_adj = adj_list[0] if adj_list else (missing_for_role[0] if missing_for_role else f"Adjacent capability to {skill_name}")
            recommendations.append(RecommendedActionItem(
                action_type="Reskill",
                target_skill_or_role=target_adj,
                status="ready" if (adj_list or missing_for_role) else "partial",
                rationale=(
                    f"Reskill from {skill_name} toward {target_adj}: {skill_name} is in your profile but shows "
                    f"'{skill_health_category}' health and '{demand_trend_direction}' market demand."
                ),
                evidence_metrics={
                    "source_skill": skill_name,
                    "skill_health": skill_health_category,
                    "demand_direction": demand_trend_direction,
                    "half_life_months": half_life_months,
                },
                observation_ids=obs_list,
            ))
        elif missing_for_role:
            recommendations.append(RecommendedActionItem(
                action_type="Learn",
                target_skill_or_role=missing_for_role[0],
                status="ready",
                rationale=(
                    f"Learn {missing_for_role[0]} to close verified profile skill gap for target role '{user_target_role}'."
                ),
                evidence_metrics={
                    "target_role": user_target_role,
                    "missing_skill_count": len(missing_for_role),
                },
                observation_ids=obs_list,
            ))

    # 2. Company Impact
    if not company_skill_inventory and not company_open_roles:
        comp_status: Literal["ready", "partial", "insufficient_data"] = "insufficient_data"
        comp_summary = (
            "Company workforce impact is insufficient_data because no verified company skill inventory "
            "or open role mapping was provided."
        )
        limitations.append("Company impact (Redeploy / Hire) requires a verified company workforce skill inventory.")
    else:
        inv = {k.casefold(): v for k, v in (company_skill_inventory or {}).items()}
        staff_count = inv.get(skill_name.casefold(), 0)
        comp_status = "ready" if company_skill_inventory is not None else "partial"
        comp_summary = (
            f"Company inventory has {staff_count} mapped specialist(s) for {skill_name} "
            f"(market demand: {demand_trend_direction}, Skill Health: {skill_health_category})."
        )

        if staff_count > 0 and (skill_health_category == "weakening" or demand_trend_direction == "Declining"):
            redeploy_target = adj_list[0] if adj_list else (company_open_roles[0] if company_open_roles else "Growing adjacent practice")
            recommendations.append(RecommendedActionItem(
                action_type="Redeploy",
                target_skill_or_role=redeploy_target,
                status="ready",
                rationale=(
                    f"Redeploy {staff_count} {skill_name} specialist(s) toward {redeploy_target} due to "
                    f"'{skill_health_category}' skill health and '{demand_trend_direction}' market demand."
                ),
                evidence_metrics={
                    "affected_headcount": staff_count,
                    "skill_health": skill_health_category,
                    "demand_direction": demand_trend_direction,
                },
                observation_ids=obs_list,
            ))
        elif staff_count == 0 and skill_health_category == "strengthening" and demand_trend_direction == "Increasing":
            recommendations.append(RecommendedActionItem(
                action_type="Hire",
                target_skill_or_role=skill_name,
                status="ready",
                rationale=(
                    f"Hire or upskill for {skill_name}: company inventory has 0 mapped specialists while external "
                    f"market demand is {demand_trend_direction} and Skill Health is '{skill_health_category}'."
                ),
                evidence_metrics={
                    "current_inventory": 0,
                    "skill_health": skill_health_category,
                    "demand_direction": demand_trend_direction,
                },
                observation_ids=obs_list,
            ))

    if not recommendations:
        recommendations.append(RecommendedActionItem(
            action_type="Learn",
            target_skill_or_role=skill_name,
            status="insufficient_data",
            rationale=(
                f"Actionable Learn/Reskill/Redeploy/Hire recommendation for {skill_name} is gated until both "
                "verified market trend readiness (>= 4 periods) and user/company profile mappings are available."
            ),
            evidence_metrics={
                "skill_health": skill_health_category,
                "demand_direction": demand_trend_direction,
            },
            observation_ids=obs_list,
        ))

    overall_status: Literal["ready", "partial", "insufficient_data"] = (
        "ready" if (ind_status == "ready" or comp_status == "ready") and skill_health_category != "insufficient_data"
        else "partial" if (ind_status != "insufficient_data" or comp_status != "insufficient_data" or skill_health_category != "insufficient_data")
        else "insufficient_data"
    )

    return WorkforceImpactResult(
        status=overall_status,
        market_signal_summary=market_summary,
        skill_intelligence_summary=skill_summary,
        individual_impact_status=ind_status,
        individual_impact_summary=ind_summary,
        company_impact_status=comp_status,
        company_impact_summary=comp_summary,
        recommendations=recommendations,
        limitations=limitations,
        reason=f"Evaluated Market -> Skill -> Individual ({ind_status}) -> Company ({comp_status}) impact chain.",
    )

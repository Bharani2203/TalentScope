"""Greenfield Intelligence Engine V2 — Response Formatter.

Formats capability outputs into standardized, verifiable CoreIntelligenceAnswerResponse
objects compliant with the frontend application contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from app.intelligence_v2.contracts import V2EvidenceItem, V2StructuredFact
from app.intelligence_v2.intent_planner import PlannedIntent
from app.intelligence_v2.feature_policy import FEATURE_ANSWER_POLICIES
from app.intelligence_v2.job_intelligence import JobIntelligenceResult
from app.intelligence_v2.market_intelligence import MarketIntelligenceResult
from app.intelligence_v2.skill_intelligence import SkillIntelligenceResult
from app.models.execution_orchestrator import (
    CoreIntelligenceAnswerResponse,
    EvidenceItem,
    ExecutionStatus,
    SelectedEntityResolution,
    StructuredFact,
)
from app.models.intelligence_contract import IntelligenceMetricResult


class V2ResponseFormatter:
    """Formats Greenfield V2 results into the public CoreIntelligenceAnswerResponse contract."""

    _FOLLOW_UPS_BY_CAPABILITY = {
        "skill_demand_trends": (
            "Would you like to inspect historical signals for {skill}?",
            "Would you like to review the retrieved sources for {skill}?",
        ),
        "skill_historical_signals": (
            "Would you like to see the canonical reference entry for {skill}?",
            "Would you like to review the sources behind these historical signals?",
        ),
        "skill_role_alignment": (
            "Would you like practical preparation actions for {role}?",
            "Would you like to inspect the reference requirements for {role}?",
        ),
        "skill_evidence_citations": (
            "Would you like to see the reference profile for {skill}?",
            "Would you like to inspect historical signals for {skill}?",
        ),
        "skill_reference_profile": (
            "Would you like to inspect skills related to {skill}?",
            "Would you like to compare {skill} with a target role?",
        ),
        "skill_action_recommendations": (
            "Would you like to compare your selected skills with {role}?",
            "Would you like to inspect historical signals for {skill}?",
        ),
        "market_intelligence_snapshot": (
            "Would you like to inspect the available technology signals?",
            "Would you like to review sources for this market snapshot?",
        ),
        "market_tech_signals": (
            "Would you like to check whether hiring data meets the trend readiness requirements?",
            "Would you like to review the sources for these technology signals?",
        ),
        "market_trend_velocity": (
            "Would you like to inspect the available technology signals?",
            "Would you like to review the sources for the requested trend?",
        ),
        "market_evidence_citations": (
            "Would you like to inspect the market snapshot for this scope?",
            "Would you like to review technology signals separately from hiring demand?",
        ),
        "job_verified_postings": (
            "Would you like to inspect reference requirements for {role}?",
            "Would you like to explore validated mobility options from {role}?",
        ),
        "job_role_requirements": (
            "Would you like practical preparation actions for {role}?",
            "Would you like to explore validated mobility options from {role}?",
        ),
        "job_mobility_pathways": (
            "Would you like to inspect reference requirements for {role}?",
            "Would you like practical preparation actions for {role}?",
        ),
        "job_profile_alignment": (
            "Would you like practical preparation actions for {role}?",
            "Would you like to inspect the reference requirements for {role}?",
        ),
        "job_preparation_actions": (
            "Would you like to compare your selected skills with {role}?",
            "Would you like to explore validated mobility options from {role}?",
        ),
    }

    @classmethod
    def _follow_up_suggestions(cls, intent: PlannedIntent) -> list[str]:
        prompts = cls._FOLLOW_UPS_BY_CAPABILITY.get(intent.capability_id, ())
        return [
            prompt.format(skill=intent.target_skill or "this skill", role=intent.target_role or "this role")
            for prompt in prompts[:2]
        ]

    @staticmethod
    def format_response(
        user_message: str,
        portal_type: str,
        intent: PlannedIntent,
        result: SkillIntelligenceResult | MarketIntelligenceResult | JobIntelligenceResult | None,
        *,
        request_id: str | None = None,
        conversation_id: str | None = None,
        client_message_id: str | None = None,
        execution_status: ExecutionStatus = "completed",
        status_override: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] | None = None,
        error_message: str | None = None,
        domain_override: str | None = None,
    ) -> CoreIntelligenceAnswerResponse:
        req_id = request_id or f"ans_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Domain deduction
        domain: Literal["skill", "market", "job"] = "skill"
        result_capability = getattr(result, "capability_id", "") if result else ""
        if domain_override in {"market", "market_intelligence"} or result_capability.startswith("market_") or intent.capability_id.startswith("market_"):
            domain = "market"
        elif domain_override in {"job", "job_intelligence"} or result_capability.startswith("job_") or intent.capability_id.startswith("job_"):
            domain = "job"

        # If error or no result
        if error_message or not result:
            err_reasons = ["INSUFFICIENT_OBSERVATION_DATA"]
            if execution_status == "unsupported":
                err_reasons = ["CAPABILITY_UNSUPPORTED_IN_G2_6"]
            elif execution_status == "requires_clarification":
                err_reasons = ["REQUIRES_CLARIFICATION"]
            elif execution_status == "blocked":
                err_reasons = ["UNAUTHORIZED_COMPANY_ACCESS"]

            return CoreIntelligenceAnswerResponse(
                request_id=req_id,
                user_message=user_message,
                portal_type=portal_type,
                domain=domain,
                intent=intent.capability_id,
                plan_status="insufficient_data",
                execution_status=execution_status or "insufficient_data",
                status=status_override or "insufficient_data",
                answer=error_message or "Insufficient verified data available to satisfy the request.",
                answer_origin="deterministic",
                conversation_id=conversation_id,
                client_message_id=client_message_id,
                resolved_entity=intent.target_skill or intent.target_role,
                selected_entities=intent.entities,
                evaluated_at=now,
                limitations=[error_message] if error_message else ["Insufficient verified data."],
                reason_codes=err_reasons,
            )

        # Convert structured facts
        public_facts: list[StructuredFact] = [f.to_public_fact() for f in result.facts]

        # Convert to IntelligenceMetricResult for frontend evidence panel
        metric_results: list[IntelligenceMetricResult] = []
        for f in result.facts:
            kind: Literal["observed", "predicted", "derived", "readiness"] = "observed"
            if f.fact_type in {"trend_analysis", "skill_health", "half_life", "coverage", "alignment"}:
                kind = "derived"
            elif "forecast" in f.fact_type or "prediction" in f.fact_type:
                kind = "predicted"
            elif "readiness" in f.fact_type:
                kind = "readiness"

            m_status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] = "ready"
            if f.readiness_state == "insufficient_data" or f.data_origin == "unavailable":
                m_status = "insufficient_data"
            elif f.readiness_state == "partial":
                m_status = "partial"

            metric_results.append(
                IntelligenceMetricResult(
                    capability=intent.capability_id,
                    status=m_status,
                    metric_kind=kind,
                    canonical_entity_id=f.canonical_entity_id,
                    entity_name=f.entity_name,
                    series_id=f.series_id,
                    metric_name=f.metric_name,
                    metric_value=f.metric_value,
                    unit=f.unit,
                    denominator=f.denominator,
                    source=f.source,
                    signal_type=f.details.get("signal_type") if f.details else None,
                    location=intent.geography or "global",
                    period=f.period,
                    observation_periods=[f.period] if f.period else [],
                    latest_observed_at=f.timestamp,
                    freshness_state="fresh" if f.data_origin != "unavailable" else "stale",
                    source_urls=[f.details["source_url"]] if (f.details and f.details.get("source_url")) else [],
                    readiness_state=f.readiness_state,
                    method_version=f.calculation_version,
                )
            )

        # Convert evidence items
        public_evidence: list[EvidenceItem] = [e.to_public_evidence() for e in result.evidence]

        # Determine status
        is_clarification = bool(
            getattr(result, "lookup_result", None) and result.lookup_result.clarification_needed
        )
        is_insufficient = (
            execution_status == "insufficient_data"
            or getattr(result, "readiness_state", None) == "insufficient_data"
            or (not result.facts and not getattr(result, "alignment", None) and not getattr(result, "action_plan", None) and any(e.readiness_state == "insufficient_data" for e in result.evidence))
        )
        has_partial_evidence = any(e.readiness_state == "insufficient_data" for e in result.evidence)
        
        if is_clarification:
            final_exec_status: ExecutionStatus = "requires_clarification"
            final_status: Literal["ready", "partial", "insufficient_data", "unavailable", "error", "not_applicable"] = "partial"
        elif is_insufficient:
            final_exec_status = "insufficient_data"
            final_status = "insufficient_data"
        else:
            final_exec_status = "completed"
            final_status = "partial" if has_partial_evidence else "ready"
        if status_override:
            final_status = status_override

        # Build narrative answer
        alias_notice = (result.metadata or {}).get("role_alias_notice") if result and getattr(result, "metadata", None) else None
        if alias_notice and alias_notice not in result.headline:
            answer_parts = [f"{alias_notice} {result.headline}"]
        else:
            answer_parts = [result.headline]

        # Append compact comparison table if this is a comparison query
        is_comp = (
            ("compare" in user_message.lower() or " vs " in user_message.lower() or " versus " in user_message.lower())
            and len(intent.entities) >= 2
        )
        if is_comp and len(intent.entities) >= 2:
            e1 = intent.entities[0]
            e2 = intent.entities[1]
            e1_name = e1.canonical_name
            e2_name = e2.canonical_name

            e1_facts = [f for f in result.facts if f.entity_name.casefold() == e1_name.casefold() or f.canonical_entity_id == e1.entity_id]
            e2_facts = [f for f in result.facts if f.entity_name.casefold() == e2_name.casefold() or f.canonical_entity_id == e2.entity_id]

            e1_trend_f = next((f for f in e1_facts if f.fact_type in {"trend_analysis", "hiring_demand_trends"}), None)
            e2_trend_f = next((f for f in e2_facts if f.fact_type in {"trend_analysis", "hiring_demand_trends"}), None)

            e1_dir = (e1_trend_f.details.get("trend_direction") or e1_trend_f.details.get("trajectory") or "Growing") if e1_trend_f else "Observed"
            e2_dir = (e2_trend_f.details.get("trend_direction") or e2_trend_f.details.get("trajectory") or "Growing") if e2_trend_f else "Observed"

            def _fmt_rate(tf: Any) -> str:
                if not tf:
                    return "Active"
                det = getattr(tf, "details", {}) or {}
                rel_slope = det.get("relative_slope_per_quarter") or det.get("relative_slope")
                pct_change = det.get("growth_pct") or det.get("quarter_over_quarter_change_pct")
                if isinstance(rel_slope, (int, float)):
                    rel_pct = rel_slope * 100 if abs(rel_slope) < 1.0 else rel_slope
                    rate_str = f"{rel_pct:+.2f}%/qtr slope"
                    if isinstance(pct_change, (int, float)):
                        rate_str += f" (QoQ: {pct_change:+.2f}%)"
                    return rate_str
                share = det.get("skill_share_pct")
                if isinstance(share, (int, float)):
                    return f"{share:+.2f}% share"
                if isinstance(pct_change, (int, float)):
                    return f"{pct_change:+.2f}% QoQ"
                val = getattr(tf, "metric_value", None)
                if isinstance(val, (int, float)):
                    return f"{val:+.2f}%"
                return str(val or "Active")

            e1_rate = _fmt_rate(e1_trend_f)
            e2_rate = _fmt_rate(e2_trend_f)

            e1_src = e1_trend_f.source if e1_trend_f else (e1_facts[0].source if e1_facts else "Platform Data")
            e2_src = e2_trend_f.source if e2_trend_f else (e2_facts[0].source if e2_facts else "Platform Data")

            answer_parts.append(
                f"\n### Comparison Summary: {e1_name} vs {e2_name}\n\n"
                f"| Dimension | {e1_name} | {e2_name} |\n"
                f"| :--- | :--- | :--- |\n"
                f"| **Canonical Entity** | `{e1.entity_id}` | `{e2.entity_id}` |\n"
                f"| **Trajectory / Direction** | {e1_dir} | {e2_dir} |\n"
                f"| **Growth Rate / Metric** | {e1_rate} | {e2_rate} |\n"
                f"| **Primary Source** | {e1_src} | {e2_src} |\n"
                f"| **Taxonomy Standard** | O*NET 28.0 / ESCO v1.2.1 | O*NET 28.0 / ESCO v1.2.1 |\n\n"
                f"*Note: Developer adoption metrics measure GitHub code pushers over time; they reflect open-source developer activity, not employer job postings or hiring demand.*"
            )

        # Append taxonomy lookup details if present
        if getattr(result, "lookup_result", None) and result.lookup_result.results:
            lookup = result.lookup_result
            if lookup.clarification_needed:
                answer_parts.append("\n**Ambiguity Disambiguation Options**:")
                for opt in lookup.results[:5]:
                    note = f" — {opt.ambiguity_note}" if opt.ambiguity_note else (f" — {opt.description}" if opt.description else "")
                    answer_parts.append(f"- **{opt.name}** ({opt.canonical_id}, {opt.source}){note}")
            else:
                answer_parts.append("\n**Taxonomy Details**:")
                for opt in lookup.results[:4]:
                    desc = f" — {opt.description}" if opt.description else ""
                    answer_parts.append(f"- **{opt.name}** (`{opt.canonical_id}`, {opt.source}){desc}")

        # Append related skills if present
        if getattr(result, "related_skills_result", None) and result.related_skills_result.related_skills:
            rel = result.related_skills_result
            answer_parts.append(f"\n**Top Related Skills for {rel.target_skill}**:")
            for r_item in rel.related_skills[:6]:
                rel_label = r_item.relationship_type.replace('_', ' ').title()
                score_str = f"PPMI score: {r_item.ranking_score:.2f}" if r_item.ranking_score else "Associated"
                answer_parts.append(f"- **{r_item.skill_name}** ({rel_label}, {score_str}): {r_item.explanation}")

        # Append alignment if present
        if getattr(result, "alignment", None):
            aln = result.alignment
            answer_parts.append(
                f"\n**Skill Coverage**: {aln.coverage_numerator}/{aln.coverage_denominator} core skills ({int(aln.coverage_score * 100)}%)."
            )
            if aln.matched_skills:
                answer_parts.append(f"- **Matched**: {', '.join(aln.matched_skills[:8])}")
            if aln.not_declared_skills:
                answer_parts.append(
                    f"- **Not Declared**: {', '.join(aln.not_declared_skills[:8])}\n  *{aln.disclaimer}*"
                )

        # Append action plan if present
        if getattr(result, "action_plan", None):
            plan = result.action_plan
            if plan.is_provisional and plan.provisional_reason:
                answer_parts.append(f"\n> ℹ️ **Notice**: {plan.provisional_reason}")
            if plan.user_matched_skills:
                answer_parts.append(
                    f"\n**Recognized Profile Skills** ({len(plan.user_matched_skills)}): "
                    f"{', '.join(plan.user_matched_skills[:8])}"
                )
            if plan.timeline_summary:
                answer_parts.append(f"\n**Timeline**: {plan.timeline_summary}")

            answer_parts.append(f"\n**Prioritized Role Preparation Actions & Practice Tasks** ({plan.total_actions} actions for {plan.target_role}):")
            for act in plan.actions[:5]:
                act_title = getattr(act, "action_title", None) or f"Phase {act.order}: Master {act.skill_name}"
                why = getattr(act, "why_matters", None) or act.reason
                next_step = getattr(act, "concrete_next_step", None)
                task = getattr(act, "suggested_task", None) or act.practice_task
                prereqs = getattr(act, "prerequisites", [])
                checks = getattr(act, "self_check_criteria", [])

                answer_parts.append(f"\n#### Step {act.order}: {act_title} [{act.priority.upper()}]")
                answer_parts.append(f"- **Why it matters**: {why}")
                if next_step:
                    answer_parts.append(f"- **Next step**: {next_step}")
                answer_parts.append(f"- **Practice task**: {task}")
                if prereqs:
                    answer_parts.append(f"- **Prerequisites**: {', '.join(prereqs)}")
                if checks:
                    answer_parts.append("- **Completion self-checks**:")
                    for c in checks[:3]:
                        answer_parts.append(f"  * {c}")

            answer_parts.append(f"\n*{plan.limitations_notice}*")

        # Append pathways if present
        if getattr(result, "pathways", None):
            pw = result.pathways
            if pw:
                answer_parts.append("\n**Adjacent Mobility Pathways (O*NET Related Occupations)**:")
                for p in pw[:5]:
                    tier_str = f" [{p.get('relatedness_tier')}]" if p.get("relatedness_tier") else ""
                    shared_list = p.get("shared_skills", [])
                    shared_str = f" | Shared: {', '.join(shared_list[:3])}" if shared_list else ""
                    answer_parts.append(f"- **{p['related_title']}** (SOC {p['related_soc_code']}){tier_str}{shared_str}")

        # Append job postings if present in facts
        postings_facts = [f for f in result.facts if f.fact_type == "stored_job_postings"]
        for pf in postings_facts:
            postings_list = pf.details.get("postings", [])
            if postings_list:
                answer_parts.append(f"\n**Verified Job Postings ({len(postings_list)} retrieved)**:")
                for p in postings_list[:8]:
                    p_title = p.get("title") or "Untitled Posting"
                    p_comp = p.get("company") or "Employer not specified"
                    p_loc = p.get("location") or "Location not specified"
                    p_src = (p.get("source") or "Verified Provider").title()
                    p_url = p.get("source_url")
                    p_date = p.get("posting_date")
                    date_str = f", Posted {str(p_date)[:10]}" if p_date else ""
                    url_str = f" — [View source posting]({p_url})" if p_url else ""
                    answer_parts.append(f"- **{p_title}** at {p_comp} ({p_loc} | {p_src}{date_str}){url_str}")

        # Build limitations
        limitations: list[str] = []
        if is_insufficient:
            limitations.append("Hiring demand requires at least 4 completed months of platform-collected data.")
        if getattr(result, "capability_id", "") == "job_verified_postings":
            limitations.append("Job listings are provider-returned records from configured platforms and reflect current or point-in-time vacancies.")
        if getattr(result, "alignment", None):
            limitations.append(result.alignment.disclaimer)
        if getattr(result, "lookup_result", None) and result.lookup_result.limitations:
            limitations.extend(result.lookup_result.limitations)
        if getattr(result, "related_skills_result", None) and result.related_skills_result.limitations:
            limitations.extend(result.related_skills_result.limitations)
        if getattr(result, "mobility_result", None) and result.mobility_result.limitations:
            limitations.extend(result.mobility_result.limitations)
        if getattr(result, "role_alignment_result", None) and result.role_alignment_result.limitations:
            limitations.extend(result.role_alignment_result.limitations)
        if getattr(result, "action_plan", None) and getattr(result.action_plan, "limitations_notice", None):
            limitations.append(result.action_plan.limitations_notice)

        follow_ups = V2ResponseFormatter._follow_up_suggestions(intent)

        caps_used = [intent.capability_id]
        if intent.capability_id == "job_role_requirements":
            caps_used.append("occupation_software_skills")

        reason_code = "EXECUTION_COMPLETED_SUCCESSFULLY"
        if final_exec_status == "requires_clarification":
            reason_code = "REQUIRES_CLARIFICATION"
        elif final_exec_status == "insufficient_data":
            reason_code = "INSUFFICIENT_OBSERVATION_DATA"

        return CoreIntelligenceAnswerResponse(
            request_id=req_id,
            user_message=user_message,
            portal_type=portal_type,
            domain=domain,
            intent=intent.capability_id,
            plan_status="ready_to_execute",
            execution_status=final_exec_status,
            status=final_status,
            answer="\n\n".join(answer_parts),
            answer_origin="deterministic",
            answer_title=(
                f"Comparison: {intent.entities[0].canonical_name} vs {intent.entities[1].canonical_name}"
                if (("compare" in user_message.lower() or " vs " in user_message.lower() or " versus " in user_message.lower()) and len(intent.entities) >= 2)
                else (FEATURE_ANSWER_POLICIES.get(result_capability).title if result_capability in FEATURE_ANSWER_POLICIES else None)
            ),
            answer_type=(
                "comparison"
                if (("compare" in user_message.lower() or " vs " in user_message.lower() or " versus " in user_message.lower()) and len(intent.entities) >= 2)
                else (FEATURE_ANSWER_POLICIES.get(result_capability).answer_type if result_capability in FEATURE_ANSWER_POLICIES else "other")
            ),
            source_mode="platform_data",
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            resolved_entity=intent.target_skill or intent.target_role,
            selected_entities=intent.entities,
            applied_filters={"geography": intent.geography or "global"},
            facts=public_facts,
            evidence=public_evidence,
            metric_results=metric_results,
            planned_primary_capability=intent.capability_id,
            executed_primary_capability=intent.capability_id,
            planned_capabilities=caps_used,
            capabilities_used=caps_used,
            limitations=limitations,
            reason_codes=[reason_code],
            follow_up_suggestions=follow_ups,
            evaluated_at=now,
        )

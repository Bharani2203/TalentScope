"""Versioned conversion from presentation onboarding answers to profile fields."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ONBOARDING_SCHEMA_VERSION = 1

ROLE_QUESTION_IDS = {
    "employee": {
        1: "emp_name_and_location", 2: "emp_workplace", 3: "emp_experience_field",
        4: "emp_skills", 5: "emp_skill_confidence", 6: "emp_improvements",
        7: "emp_trajectory", 8: "emp_next_skills", 9: "emp_time", 10: "emp_internal_goals",
    },
    "company": {
        1: "cmp_organization", 2: "cmp_workforce_size", 3: "cmp_description",
        4: "cmp_business_areas", 5: "cmp_improvement_goals", 6: "cmp_challenges",
        7: "cmp_important_roles", 8: "cmp_critical_skills", 9: "cmp_future_skills",
        10: "cmp_decisions", 11: "cmp_platform_usage",
    },
}


def _value(answers: dict[str, Any], key: str, field: str | None = None) -> Any:
    answer = answers.get(key)
    return answer.get(field) if field and isinstance(answer, dict) else answer


def normalize_onboarding_answers(
    user_type: str,
    answers: dict[str, Any],
    *,
    existing_profile: dict[str, Any] | None = None,
    company_id: str | None = None,
    connection_status: str | None = None,
) -> dict[str, Any]:
    """Return canonical fields without dropping or mutating the original answers."""
    answers = answers if isinstance(answers, dict) else {}
    existing_profile = existing_profile if isinstance(existing_profile, dict) else {}
    if user_type == "employee":
        workplace = _value(answers, "emp_workplace") or {}
        identity = _value(answers, "emp_name_and_location") or {}
        trajectory = _value(answers, "emp_trajectory")
        mobility = str(trajectory or "")
        state = connection_status or ("connected" if company_id else "independent")
        return {
            "user_type": "employee",
            "employment_state": state,
            "company_id": company_id,
            "display_name": identity.get("name") if isinstance(identity, dict) else None,
            "city": identity.get("city") if isinstance(identity, dict) else None,
            "country": identity.get("country") if isinstance(identity, dict) else None,
            "employer_name_claim": workplace.get("company") if isinstance(workplace, dict) else None,
            "company_industry_claim": workplace.get("industry") if isinstance(workplace, dict) else None,
            "current_role_id": workplace.get("currentRole") if isinstance(workplace, dict) else None,
            "team_name_claim": workplace.get("department") if isinstance(workplace, dict) else None,
            # The current prompt asks time in the field, not time in the current role.
            "field_experience_band": _value(answers, "emp_experience_field"),
            "current_skill_domains": deepcopy(_value(answers, "emp_skills") or []),
            "self_reported_skill_confidence": deepcopy(_value(answers, "emp_skill_confidence") or {}),
            "growth_interests": deepcopy(_value(answers, "emp_improvements") or []),
            "target_role_name": mobility or None,
            "internal_mobility_opt_in": mobility in {
                "Move to another team", "Move into a new role", "Move to a senior role",
                "Become a specialist", "Move into management",
            },
            "mobility_interest_type": mobility or None,
            "desired_skill_domains": deepcopy(_value(answers, "emp_next_skills") or []),
            "weekly_learning_time": _value(answers, "emp_time"),
            "primary_goal": deepcopy(_value(answers, "emp_internal_goals") or []),
        }
    if user_type == "company":
        organization = _value(answers, "cmp_organization") or {}
        areas = deepcopy(_value(answers, "cmp_business_areas") or [])
        return {
            "user_type": "company",
            "company_id": company_id,
            "company_name": organization.get("companyName") if isinstance(organization, dict) else None,
            "company_size_band": _value(answers, "cmp_workforce_size"),
            "hq_region": {
                "city": organization.get("city"), "country": organization.get("country"),
            } if isinstance(organization, dict) else {},
            "company_industry": organization.get("industry") if isinstance(organization, dict) else None,
            "company_description": _value(answers, "cmp_description", "text"),
            "company_subdomains": areas,
            "departments": deepcopy(areas),
            "primary_workforce_focus": deepcopy(_value(answers, "cmp_improvement_goals") or []),
            "workforce_challenges": deepcopy(_value(answers, "cmp_challenges") or []),
            "priority_roles": deepcopy(_value(answers, "cmp_important_roles") or []),
            "critical_skill_domains": deepcopy(_value(answers, "cmp_critical_skills") or []),
            "anticipated_skill_domains": deepcopy(_value(answers, "cmp_future_skills") or []),
            "workforce_decisions": deepcopy(_value(answers, "cmp_decisions") or []),
            "preferred_platform_start": _value(answers, "cmp_platform_usage"),
        }
    raise ValueError("Onboarding normalization supports employee and company profiles only.")


def canonical_to_role_answers(user_type: str, canonical: dict[str, Any]) -> dict[str, Any]:
    """Build UI-compatible answer keys from canonical fields for older clients."""
    if user_type == "employee":
        return {
            "emp_name_and_location": {"name": canonical.get("display_name"), "city": canonical.get("city"), "country": canonical.get("country")},
            "emp_workplace": {"company": canonical.get("employer_name_claim"), "department": canonical.get("team_name_claim"), "industry": canonical.get("company_industry_claim"), "currentRole": canonical.get("current_role_id")},
            "emp_experience_field": canonical.get("field_experience_band"),
            "emp_skills": canonical.get("current_skill_domains", []),
            "emp_skill_confidence": canonical.get("self_reported_skill_confidence", {}),
            "emp_improvements": canonical.get("growth_interests", []),
            "emp_trajectory": canonical.get("mobility_interest_type"),
            "emp_next_skills": canonical.get("desired_skill_domains", []),
            "emp_time": canonical.get("weekly_learning_time"),
            "emp_internal_goals": canonical.get("primary_goal", []),
        }
    if user_type == "company":
        region = canonical.get("hq_region") or {}
        areas = canonical.get("departments", [])
        return {
            "cmp_organization": {"companyName": canonical.get("company_name"), "industry": canonical.get("company_industry"), "city": region.get("city"), "country": region.get("country")},
            "cmp_workforce_size": canonical.get("company_size_band"),
            "cmp_description": {"text": canonical.get("company_description")},
            "cmp_business_areas": areas,
            "cmp_improvement_goals": canonical.get("primary_workforce_focus", []),
            "cmp_challenges": canonical.get("workforce_challenges", []),
            "cmp_important_roles": canonical.get("priority_roles", []),
            "cmp_critical_skills": canonical.get("critical_skill_domains", []),
            "cmp_future_skills": canonical.get("anticipated_skill_domains", []),
            "cmp_decisions": canonical.get("workforce_decisions", []),
            "cmp_platform_usage": canonical.get("preferred_platform_start"),
        }
    return {}

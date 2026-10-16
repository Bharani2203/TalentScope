from app.services.onboarding_normalization import (
    ONBOARDING_SCHEMA_VERSION,
    canonical_to_role_answers,
    normalize_onboarding_answers,
)


def test_employee_answers_map_to_stable_semantic_fields_without_claiming_membership():
    answers = {
        "emp_name_and_location": {"name": "Ada", "city": "Chennai", "country": "India"},
        "emp_workplace": {"company": "Claimed Corp", "department": "Data", "currentRole": "Analyst"},
        "emp_experience_field": "3-5 years",
        "emp_skills": ["Python"],
        "emp_trajectory": "Move to another team",
    }
    profile = normalize_onboarding_answers("employee", answers)
    assert profile["user_type"] == "employee"
    assert profile["employment_state"] == "independent"
    assert profile["company_id"] is None
    assert profile["employer_name_claim"] == "Claimed Corp"
    assert profile["field_experience_band"] == "3-5 years"
    assert profile["current_role_id"] == "Analyst"
    assert profile["internal_mobility_opt_in"] is True
    assert answers["emp_workplace"]["company"] == "Claimed Corp"
    assert canonical_to_role_answers("employee", profile)["emp_skills"] == ["Python"]


def test_company_answers_map_and_round_trip_for_legacy_client():
    answers = {
        "cmp_organization": {"companyName": "Northwind", "industry": "Technology", "city": "Chennai", "country": "India"},
        "cmp_workforce_size": "500-1000",
        "cmp_business_areas": ["Data"],
        "cmp_important_roles": ["Analyst"],
    }
    profile = normalize_onboarding_answers("company", answers)
    assert profile["company_name"] == "Northwind"
    assert profile["company_size_band"] == "500-1000"
    assert profile["hq_region"] == {"city": "Chennai", "country": "India"}
    assert profile["priority_roles"] == ["Analyst"]
    assert canonical_to_role_answers("company", profile)["cmp_organization"]["companyName"] == "Northwind"


def test_onboarding_schema_is_versioned():
    assert ONBOARDING_SCHEMA_VERSION == 1

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from firebase_admin import exceptions
from google.api_core.exceptions import GoogleAPICallError

from app.analytics.skill_registry import canonical_skill_id, normalize_skill
from app.core.firebase import get_firestore_client


class CompanyWorkforceStoreUnavailable(RuntimeError):
    """Trusted company workforce records could not be read."""


@dataclass(frozen=True)
class CompanyWorkforceSnapshot:
    company_id: str
    company_name: str | None
    active_employee_count: int
    member_profiles_with_skills: int
    member_profiles_without_skills: int
    unverified_membership_count: int
    member_profiles_with_self_reported_confidence: int
    member_profiles_with_current_role: int
    skill_employee_counts: dict[str, int]
    skill_labels: dict[str, str]
    declared_priority_skills: list[str]
    truncated: bool


class FirestoreCompanyWorkforceStore:
    """Read bounded, double-checked connected employee and owner profile data."""

    MAX_MEMBERS = 1000

    def __init__(self, firestore_client: Any | None = None):
        self._firestore_client = firestore_client

    def get_company_workforce(
        self,
        *,
        company_id: str,
        expected_owner_uid: str,
    ) -> CompanyWorkforceSnapshot:
        try:
            from app.storage.firestore_read_guard import read_guard
            client = self._firestore_client or get_firestore_client()
            company_ref = client.collection("companies").document(company_id)
            company = company_ref.get().to_dict() or {}
            read_guard.record_read("companies", 1, query_type="targeted_workforce_company")
            if (
                company.get("status") != "active"
                or company.get("owner_uid") != expected_owner_uid
            ):
                raise CompanyWorkforceStoreUnavailable(
                    "The active company workforce record could not be verified."
                )

            owner = client.collection("users").document(expected_owner_uid).get().to_dict() or {}
            read_guard.record_read("users", 1, query_type="targeted_workforce_owner")
            if (
                owner.get("user_type") != "company"
                or owner.get("company_id") != company_id
            ):
                raise CompanyWorkforceStoreUnavailable(
                    "The company owner's stored profile could not be verified."
                )

            owner_profile = owner.get("profile")
            owner_profile = owner_profile if isinstance(owner_profile, dict) else {}
            company_profile = owner_profile.get("company")
            company_profile = company_profile if isinstance(company_profile, dict) else {}
            declared_priorities = company_profile.get("critical_skill_domains")
            if not isinstance(declared_priorities, list):
                declared_priorities = []
            declared_priorities = sorted({
                " ".join(value.split())
                for value in declared_priorities
                if isinstance(value, str) and value.strip()
            }, key=str.casefold)

            members_query = (
                company_ref.collection("members")
                .where("status", "==", "connected")
                .limit(self.MAX_MEMBERS + 1)
            )
            member_records = list(members_query.stream())
            read_guard.record_read("companies.members", len(member_records), query_type="targeted_workforce_members")
            truncated = len(member_records) > self.MAX_MEMBERS
            member_records = member_records[:self.MAX_MEMBERS]

            verified_count = 0
            profiles_with_skills = 0
            profiles_without_skills = 0
            profiles_with_confidence = 0
            profiles_with_role = 0
            skill_employee_counts: dict[str, int] = {}
            skill_labels: dict[str, str] = {}
            unverified_count = 0

            for member_record in member_records:
                member = member_record.to_dict() or {}
                member_uid = getattr(member_record, "id", None)
                if (
                    member.get("status") != "connected"
                    or not isinstance(member_uid, str)
                    or not member_uid
                    or member.get("uid") != member_uid
                ):
                    unverified_count += 1
                    continue

                employee = (
                    client.collection("users").document(member_uid).get().to_dict() or {}
                )
                read_guard.record_read("users", 1, query_type="targeted_workforce_employee")
                connection = employee.get("company_connection")
                if (
                    employee.get("user_type") != "employee"
                    or employee.get("company_id") != company_id
                    or not isinstance(connection, dict)
                    or connection.get("status") != "connected"
                    or connection.get("company_id") != company_id
                ):
                    unverified_count += 1
                    continue

                verified_count += 1
                employee_profile = employee.get("profile")
                employee_profile = (
                    employee_profile if isinstance(employee_profile, dict) else {}
                )
                canonical_profile = employee_profile.get("employee")
                canonical_profile = (
                    canonical_profile if isinstance(canonical_profile, dict) else {}
                )
                skill_values = canonical_profile.get("current_skill_domains")
                raw_skills = {
                    " ".join(value.split())
                    for value in skill_values
                    if isinstance(value, str) and value.strip()
                } if isinstance(skill_values, list) else set()
                skills_by_key: dict[str, str] = {}
                for skill in raw_skills:
                    canonical_id = canonical_skill_id(skill)
                    key = f"id:{canonical_id}" if canonical_id else f"name:{skill.casefold()}"
                    label = normalize_skill(skill)
                    existing_label = skills_by_key.get(key)
                    if existing_label is None or label.casefold() < existing_label.casefold():
                        skills_by_key[key] = label

                if skills_by_key:
                    profiles_with_skills += 1
                    for key, label in skills_by_key.items():
                        skill_employee_counts[key] = skill_employee_counts.get(key, 0) + 1
                        existing_label = skill_labels.get(key)
                        if existing_label is None or label.casefold() < existing_label.casefold():
                            skill_labels[key] = label
                else:
                    profiles_without_skills += 1

                confidence = canonical_profile.get("self_reported_skill_confidence")
                if isinstance(confidence, dict) and confidence:
                    profiles_with_confidence += 1
                current_role = canonical_profile.get("current_role_id")
                if isinstance(current_role, str) and current_role.strip():
                    profiles_with_role += 1

            return CompanyWorkforceSnapshot(
                company_id=company_id,
                company_name=(
                    company.get("company_name")
                    if isinstance(company.get("company_name"), str)
                    else None
                ),
                active_employee_count=verified_count,
                member_profiles_with_skills=profiles_with_skills,
                member_profiles_without_skills=profiles_without_skills,
                unverified_membership_count=unverified_count,
                member_profiles_with_self_reported_confidence=profiles_with_confidence,
                member_profiles_with_current_role=profiles_with_role,
                skill_employee_counts=skill_employee_counts,
                skill_labels=skill_labels,
                declared_priority_skills=declared_priorities,
                truncated=truncated,
            )
        except CompanyWorkforceStoreUnavailable:
            raise
        except (GoogleAPICallError, exceptions.FirebaseError) as error:
            raise CompanyWorkforceStoreUnavailable(
                "Trusted company workforce records are temporarily unavailable."
            ) from error

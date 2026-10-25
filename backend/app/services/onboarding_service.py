from typing import Any
import uuid

from fastapi import HTTPException, status
from firebase_admin import firestore
from pydantic import TypeAdapter, ValidationError

from app.core.firebase import get_firestore_client
from app.storage.firestore_read_guard import read_guard
from app.models.onboarding import (
    AgeGroup,
    BasicProfileAnswer,
    CareerGoal,
    CurrentStage,
    ExperienceAnswer,
    ExperienceLevel,
    IndividualProfileResponse,
    Interest,
    LearningStyle,
    OnboardingProgress,
    OnboardingStepRequest,
    OnboardingStepResponse,
    SkillLevel,
    WeeklyLearningTime,
    WorkPreference,
    RoleOnboardingProfileResponse,
    RoleOnboardingStepRequest,
)
from app.services.onboarding_normalization import (
    ONBOARDING_SCHEMA_VERSION,
    ROLE_QUESTION_IDS,
    canonical_to_role_answers,
    normalize_onboarding_answers,
)

STEP_QUESTION_IDS = {
    1: "name_and_location",
    2: "current_stage",
    3: "experience",
    4: "skills",
    5: "skill_levels",
    6: "career_goal",
    7: "target_role",
    8: "interest_areas",
    9: "learning_style",
    10: "weekly_time",
    11: "work_preference",
    12: "favorite_companies",
}

LIST_ADAPTERS = {
    4: TypeAdapter(list[str]),
    5: TypeAdapter(dict[str, SkillLevel]),
    6: TypeAdapter(list[CareerGoal]),
    8: TypeAdapter(list[Interest]),
    9: TypeAdapter(list[LearningStyle]),
    12: TypeAdapter(list[str]),
}


def _validate_answer(step: int, answer: Any, existing_profile: dict[str, Any]) -> Any:
    try:
        if step == 1:
            return BasicProfileAnswer.model_validate(answer).model_dump(mode="json", exclude_none=True)
        if step == 2:
            return CurrentStage(answer).value
        if step == 3:
            if isinstance(answer, str):
                answer = {"experience": answer}
            validated = ExperienceAnswer.model_validate(answer)
            return validated.model_dump(mode="json", exclude_none=True)
        if step in LIST_ADAPTERS:
            validated = LIST_ADAPTERS[step].validate_python(answer)
            if step == 4:
                return list(dict.fromkeys(skill.strip() for skill in validated if skill.strip()))
            if step == 5:
                selected_skills = set(existing_profile.get("skills", {}).get("selected_skills", []))
                if not set(validated).issubset(selected_skills):
                    raise ValueError("Skill levels must refer to skills selected in Step 4.")
                return {skill: level.value for skill, level in validated.items()}
            if step in (6, 8, 9):
                return [value.value for value in validated]
            return list(dict.fromkeys(company.strip() for company in validated if company.strip()))
        if step == 7:
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Select a target role or enter a role.")
            if len(answer.strip()) > 160:
                raise ValueError("Target role must be 160 characters or fewer.")
            return answer.strip()
        if step == 10:
            return WeeklyLearningTime(answer).value
        if step == 11:
            return WorkPreference(answer).value
    except (ValidationError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid answer for onboarding step {step}.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Onboarding step must be between 1 and 12.",
    )


def _default_profile() -> dict[str, Any]:
    return {
        "basic_profile": {},
        "current_stage": None,
        "experience": {},
        "skills": {"selected_skills": [], "skill_levels": {}},
        "career": {"career_goals": [], "target_roles": []},
        "interests": [],
        "learning_preferences": [],
        "work_preferences": {},
        "company_preferences": {"preferred_companies": []},
    }


def _profile_with_defaults(stored: Any) -> dict[str, Any]:
    profile = _default_profile()
    if not isinstance(stored, dict):
        return profile
    for key, value in stored.items():
        if key in {"skills", "career", "work_preferences", "company_preferences", "experience", "basic_profile"} and isinstance(value, dict):
            profile[key].update(value)
        else:
            profile[key] = value
    profile["skills"].setdefault("selected_skills", [])
    profile["skills"].setdefault("skill_levels", {})
    profile["career"].setdefault("career_goals", [])
    profile["career"].setdefault("target_roles", [])
    profile["company_preferences"].setdefault("preferred_companies", [])
    return profile


def _answers_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    career = profile.get("career", {})
    work = profile.get("work_preferences", {})
    companies = profile.get("company_preferences", {})
    return {
        "name_and_location": profile.get("basic_profile", {}),
        "current_stage": profile.get("current_stage") or "",
        "experience": profile.get("experience", {}),
        "skills": profile.get("skills", {}).get("selected_skills", []),
        "skill_levels": profile.get("skills", {}).get("skill_levels", {}),
        "career_goal": career.get("career_goals", []),
        "target_role": (career.get("target_roles") or [""])[0],
        "interest_areas": profile.get("interests", []),
        "learning_style": profile.get("learning_preferences", []),
        "weekly_time": work.get("learning_time", ""),
        "work_preference": work.get("work_preference", ""),
        "favorite_companies": companies.get("preferred_companies", []),
    }


def _progress_from_document(document: dict[str, Any]) -> OnboardingProgress:
    onboarding = document.get("onboarding") or {}
    completed_steps = sorted({step for step in onboarding.get("completed_steps", []) if 1 <= step <= 12})
    completed = bool(onboarding.get("completed", False) or 12 in completed_steps)
    current_step = onboarding.get("current_step", 1)
    if not isinstance(current_step, int) or not 1 <= current_step <= 12:
        current_step = 1
    return OnboardingProgress(
        current_step=current_step,
        completed_steps=completed_steps,
        completed=completed,
        last_updated_at=onboarding.get("last_updated_at"),
    )


def _next_incomplete_step(completed_steps: set[int]) -> int:
    return next((step for step in range(1, 13) if step not in completed_steps), 12)


def save_individual_step(uid: str, step: int, request: OnboardingStepRequest) -> OnboardingStepResponse:
    if step not in STEP_QUESTION_IDS:
        raise HTTPException(status_code=404, detail="Onboarding step not found.")

    client = get_firestore_client()
    document = client.collection("users").document(uid)
    try:
        snapshot = document.get()
        read_guard.record_read("users", 1, query_type="targeted_onboarding_read")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding data could not be loaded. Please retry.",
        ) from None
    stored = snapshot.to_dict() if snapshot.exists else {}
    stored_user_type = stored.get("user_type")
    if stored_user_type not in (None, "individual"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This onboarding endpoint is for Individual profiles.",
        )
    progress = _progress_from_document(stored)
    if not progress.completed and step > progress.current_step:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete earlier onboarding steps before continuing.",
        )
    profile = _profile_with_defaults(stored.get("profile"))
    answer = _validate_answer(step, request.answer, profile)

    field_by_step = {
        1: "profile.basic_profile",
        2: "profile.current_stage",
        3: "profile.experience",
        4: "profile.skills.selected_skills",
        5: "profile.skills.skill_levels",
        6: "profile.career.career_goals",
        7: "profile.career.target_roles",
        8: "profile.interests",
        9: "profile.learning_preferences",
        10: "profile.work_preferences.learning_time",
        11: "profile.work_preferences.work_preference",
        12: "profile.company_preferences.preferred_companies",
    }
    value = [answer] if step == 7 else answer
    updates: dict[str, Any] = {
        "uid": uid,
        field_by_step[step]: value,
        "onboarding_schema_version": ONBOARDING_SCHEMA_VERSION,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    if stored_user_type is None:
        updates["user_type"] = "individual"

    if step == 4:
        levels = profile["skills"].get("skill_levels", {})
        updates["profile.skills.skill_levels"] = {
            skill: level for skill, level in levels.items() if skill in answer
        }
    completed_steps = set(progress.completed_steps)
    completed_steps.add(step)
    completed = len(completed_steps) == 12
    current_step = 12 if completed else _next_incomplete_step(completed_steps)
    updates.update(
        {
            "onboarding.current_step": current_step,
            "onboarding.completed_steps": sorted(completed_steps),
            "onboarding.completed": completed,
            "onboarding.last_updated_at": firestore.SERVER_TIMESTAMP,
            "onboarding_completed": completed,
        }
    )

    try:
        if not snapshot.exists:
            document.set({"uid": uid}, merge=True)
        document.update(updates)
        saved = document.get().to_dict() or {}
        read_guard.record_read("users", 1, query_type="targeted_onboarding_readback")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding data could not be saved. Please retry.",
        ) from None

    saved_profile = _profile_with_defaults(saved.get("profile"))
    return OnboardingStepResponse(
        step=step,
        onboarding=_progress_from_document(saved),
        profile=saved_profile,
    )


def get_individual_profile(uid: str) -> IndividualProfileResponse:
    try:
        snapshot = get_firestore_client().collection("users").document(uid).get()
        read_guard.record_read("users", 1, query_type="targeted_profile_get")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Your onboarding profile is temporarily unavailable.",
        ) from None

    stored = snapshot.to_dict() if snapshot.exists else {"uid": uid}
    profile = _profile_with_defaults(stored.get("profile"))
    return IndividualProfileResponse(
        uid=uid,
        email=stored.get("email"),
        display_name=stored.get("display_name"),
        updated_at=stored.get("updated_at"),
        onboarding=_progress_from_document(stored),
        profile=profile,
        answers=_answers_from_profile(profile),
    )


ROLE_ONBOARDING_LIMITS = {"employee": 10, "company": 11}


def get_role_onboarding_profile(uid: str, user_type: str) -> RoleOnboardingProfileResponse:
    if user_type not in ROLE_ONBOARDING_LIMITS:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter"})
    try:
        snapshot = get_firestore_client().collection("users").document(uid).get()
        read_guard.record_read("users", 1, query_type="targeted_role_profile_get")
    except Exception:
        raise HTTPException(status_code=503, detail="Onboarding profile is temporarily unavailable.") from None
    stored = snapshot.to_dict() if snapshot.exists else {}
    if stored.get("user_type") != user_type:
        raise HTTPException(status_code=403, detail="This onboarding profile does not match the account type.")
    stored_profile = stored.get("profile") if isinstance(stored.get("profile"), dict) else {}
    root = stored_profile.get(f"{user_type}_onboarding_answers", {})
    root = root if isinstance(root, dict) else {}
    canonical = normalize_onboarding_answers(
        user_type,
        root,
        existing_profile=stored_profile.get(user_type),
        company_id=stored.get("company_id"),
        connection_status=(stored.get("company_connection") or {}).get("status"),
    )
    previous = stored_profile.get(user_type) if isinstance(stored_profile.get(user_type), dict) else {}
    merged = {**previous, **canonical}
    version = stored.get("onboarding_schema_version", 0)
    if version < ONBOARDING_SCHEMA_VERSION or previous != merged:
        try:
            patch = {f"profile.{user_type}.{key}": value for key, value in merged.items()}
            patch["onboarding_schema_version"] = ONBOARDING_SCHEMA_VERSION
            get_firestore_client().collection("users").document(uid).update(patch)
        except Exception:
            raise HTTPException(status_code=503, detail="Canonical onboarding profile could not be saved.") from None
    progress = _progress_from_document(stored)
    progress.current_step = min(progress.current_step, ROLE_ONBOARDING_LIMITS[user_type])
    return RoleOnboardingProfileResponse(
        uid=uid, user_type=user_type, answers={**root, **canonical_to_role_answers(user_type, merged)},
        profile=merged, onboarding_schema_version=ONBOARDING_SCHEMA_VERSION, onboarding=progress,
    )


def save_role_onboarding_step(uid: str, user_type: str, step: int, request: RoleOnboardingStepRequest) -> RoleOnboardingProfileResponse:
    limit = ROLE_ONBOARDING_LIMITS.get(user_type)
    if limit is None or not 1 <= step <= limit:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter", "message": "Invalid onboarding step."})
    if ROLE_QUESTION_IDS[user_type].get(step) != request.question_id:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter", "message": "Question does not match account type."})
    client = get_firestore_client()
    document = client.collection("users").document(uid)
    try:
        snapshot = document.get()
        read_guard.record_read("users", 1, query_type="targeted_role_profile_get")
        stored = snapshot.to_dict() if snapshot.exists else {}
        if stored.get("user_type") != user_type:
            raise HTTPException(status_code=403, detail="This onboarding profile does not match the account type.")
        progress = _progress_from_document(stored)
        completed_steps = set(progress.completed_steps)
        if not progress.completed and step > progress.current_step:
            raise HTTPException(status_code=409, detail="Complete earlier onboarding steps before continuing.")
        answers = (stored.get("profile") or {}).get(f"{user_type}_onboarding_answers", {})
        answers = dict(answers) if isinstance(answers, dict) else {}
        answers[request.question_id] = request.answer
        canonical = normalize_onboarding_answers(
            user_type,
            answers,
            existing_profile=(stored.get("profile") or {}).get(user_type),
            company_id=stored.get("company_id"),
            connection_status=(stored.get("company_connection") or {}).get("status"),
        )
        canonical_existing = (stored.get("profile") or {}).get(user_type, {})
        canonical_merged = {**canonical_existing, **canonical}
        completed_steps.add(step)
        completed = len(completed_steps) >= limit
        current_step = limit if completed else _next_incomplete_step(completed_steps)
        company_id = None
        if user_type == "company" and completed:
            company_id = stored.get("company_id") or uuid.uuid5(
                uuid.NAMESPACE_URL, f"talentscope-company-owner:{uid}"
            ).hex
            canonical_merged["company_id"] = company_id
            company_name = canonical_merged.get("company_name")
            client.collection("companies").document(company_id).set({
                "company_id": company_id,
                "owner_uid": uid,
                "company_name": company_name,
                "industry": canonical_merged.get("company_industry"),
                "company_size_band": canonical_merged.get("company_size_band"),
                "hq_region": canonical_merged.get("hq_region"),
                "departments": canonical_merged.get("departments", []),
                "priority_roles": canonical_merged.get("priority_roles", []),
                "status": "active",
                "created_at": firestore.SERVER_TIMESTAMP,
            }, merge=True)
        document.set({"uid": uid}, merge=True)
        update = {
            f"profile.{user_type}_onboarding_answers": answers,
            "onboarding.current_step": current_step,
            "onboarding.completed_steps": sorted(completed_steps),
            "onboarding.completed": completed,
            "onboarding.last_updated_at": firestore.SERVER_TIMESTAMP,
            "onboarding_completed": completed,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "onboarding_schema_version": ONBOARDING_SCHEMA_VERSION,
            **{f"profile.{user_type}.{key}": value for key, value in canonical_merged.items()},
        }
        if company_id:
            update["company_id"] = company_id
        document.update(update)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Onboarding answer could not be saved.") from None
    return get_role_onboarding_profile(uid, user_type)

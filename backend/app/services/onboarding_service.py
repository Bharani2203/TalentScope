from datetime import datetime, timezone
import json
import logging
import os
from typing import Any
import uuid

from fastapi import HTTPException, status
from firebase_admin import firestore
from pydantic import TypeAdapter, ValidationError

from app.core.firebase import get_firestore_client
from app.storage.firestore_read_guard import read_guard

logger = logging.getLogger(__name__)

_ephemeral_onboarding_store: dict[str, dict[str, Any]] = {}


def _get_firestore_document(uid: str):
    """Safely acquire Firestore document reference without crashing if credentials are unavailable."""
    try:
        client = get_firestore_client()
        if client:
            return client.collection("users").document(uid)
    except Exception as exc:
        logger.info("[ONBOARDING_FIRESTORE] Firestore client unavailable (%s): %s", type(exc).__name__, exc)
    return None


def _get_postgres_user_record(uid: str) -> dict[str, Any] | None:
    """Read user profile and onboarding progress directly from PostgreSQL / Supabase users table."""
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1" and not os.getenv("TEST_POSTGRES_ACTIVE"):
        return None
    try:
        from app.core.database import get_pg_config
        import psycopg2
        config = get_pg_config()
        conn = psycopg2.connect(**config)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT uid, email, display_name, user_type, profile, onboarding, onboarding_completed, updated_at FROM users WHERE uid = %s",
                    (uid,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "uid": row[0],
                        "email": row[1],
                        "display_name": row[2],
                        "user_type": row[3],
                        "profile": row[4] if isinstance(row[4], dict) else {},
                        "onboarding": row[5] if isinstance(row[5], dict) else {},
                        "onboarding_completed": bool(row[6]),
                        "updated_at": row[7],
                    }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[ONBOARDING_POSTGRES] Read user %s failed: %s", uid, exc)
    return None


def _save_postgres_user_record(
    uid: str,
    user_type: str,
    profile: dict[str, Any],
    onboarding_data: dict[str, Any],
    completed: bool,
    email: str | None = None,
    display_name: str | None = None,
) -> bool:
    """Persist user profile and onboarding progress directly into PostgreSQL / Supabase users table."""
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1" and not os.getenv("TEST_POSTGRES_ACTIVE"):
        return False
    try:
        from app.core.database import get_pg_config
        import psycopg2
        import json
        config = get_pg_config()
        conn = psycopg2.connect(**config)
        try:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO users (uid, email, display_name, user_type, profile, onboarding, onboarding_completed, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, NOW())
                    ON CONFLICT (uid) DO UPDATE SET
                        profile = users.profile || EXCLUDED.profile,
                        onboarding = EXCLUDED.onboarding,
                        onboarding_completed = EXCLUDED.onboarding_completed,
                        user_type = COALESCE(users.user_type, EXCLUDED.user_type),
                        updated_at = NOW();
                """
                cur.execute(
                    sql,
                    (
                        uid,
                        email or f"{uid}@placeholder.talentscope.ai",
                        display_name or "TalentScope User",
                        user_type or "individual",
                        json.dumps(profile),
                        json.dumps(onboarding_data),
                        completed,
                    )
                )
                conn.commit()
                print(f"[ONBOARDING_POSTGRES] Saved onboarding for user {uid} (step={onboarding_data.get('current_step')}, completed={completed})", flush=True)
                return True
        except Exception as exc:
            conn.rollback()
            logger.error("[ONBOARDING_POSTGRES_ERROR] Commit failed for user %s: %s", uid, exc, exc_info=True)
        finally:
            conn.close()
    except Exception as exc:
        logger.error("[ONBOARDING_POSTGRES_ERROR] Connect failed for user %s: %s", uid, exc, exc_info=True)
    return False
from app.models.onboarding import (
    AgeGroup,
    BasicProfileAnswer,
    CareerGoal,
    CurrentStage,
    EmployeeIdentityAnswer,
    EmployeeWorkplaceAnswer,
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

    doc = _get_firestore_document(uid)
    stored = None
    snapshot_exists = False
    if doc is not None:
        try:
            snapshot = doc.get()
            read_guard.record_read("users", 1, query_type="targeted_onboarding_read")
            snapshot_exists = snapshot.exists
            stored = snapshot.to_dict() if snapshot.exists else {}
        except Exception as exc:
            logger.warning("[ONBOARDING] Firestore read failed: %s", exc)
            stored = None

    if stored is None:
        stored = _get_postgres_user_record(uid) or _ephemeral_onboarding_store.get(uid) or {"uid": uid}

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

    # Apply to in-memory profile dictionary
    if step == 1:
        profile["basic_profile"] = answer
    elif step == 2:
        profile["current_stage"] = answer
    elif step == 3:
        profile["experience"] = answer
    elif step == 4:
        profile["skills"]["selected_skills"] = answer
        levels = profile["skills"].get("skill_levels", {})
        profile["skills"]["skill_levels"] = {k: v for k, v in levels.items() if k in answer}
    elif step == 5:
        profile["skills"]["skill_levels"] = answer
    elif step == 6:
        profile["career"]["career_goals"] = answer
    elif step == 7:
        profile["career"]["target_roles"] = [answer]
    elif step == 8:
        profile["interests"] = answer
    elif step == 9:
        profile["learning_preferences"] = answer
    elif step == 10:
        profile["work_preferences"]["learning_time"] = answer
    elif step == 11:
        profile["work_preferences"]["work_preference"] = answer
    elif step == 12:
        profile["company_preferences"]["preferred_companies"] = answer

    completed_steps = set(progress.completed_steps)
    completed_steps.add(step)
    completed = len(completed_steps) == 12
    current_step = 12 if completed else _next_incomplete_step(completed_steps)
    now_dt = datetime.now(timezone.utc)
    onboarding_data = {
        "current_step": current_step,
        "completed_steps": sorted(completed_steps),
        "completed": completed,
        "last_updated_at": now_dt.isoformat(),
    }

    # Save to PostgreSQL
    pg_saved = _save_postgres_user_record(
        uid=uid,
        user_type="individual",
        profile=profile,
        onboarding_data=onboarding_data,
        completed=completed,
        email=stored.get("email"),
        display_name=stored.get("display_name"),
    )

    # Save to ephemeral store
    _ephemeral_onboarding_store[uid] = {
        "uid": uid,
        "user_type": "individual",
        "profile": profile,
        "onboarding": onboarding_data,
        "onboarding_completed": completed,
        "email": stored.get("email"),
        "display_name": stored.get("display_name"),
    }

    # Update Firestore if doc available
    if doc is not None:
        try:
            updates: dict[str, Any] = {
                "uid": uid,
                field_by_step[step]: value,
                "onboarding_schema_version": ONBOARDING_SCHEMA_VERSION,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            if stored_user_type is None:
                updates["user_type"] = "individual"
            if step == 4:
                updates["profile.skills.skill_levels"] = profile["skills"]["skill_levels"]
            updates.update(
                {
                    "onboarding.current_step": current_step,
                    "onboarding.completed_steps": sorted(completed_steps),
                    "onboarding.completed": completed,
                    "onboarding.last_updated_at": firestore.SERVER_TIMESTAMP,
                    "onboarding_completed": completed,
                }
            )
            if not snapshot_exists:
                doc.set({"uid": uid}, merge=True)
            doc.update(updates)
            read_guard.record_read("users", 1, query_type="targeted_onboarding_readback")
        except Exception as exc:
            logger.warning("[ONBOARDING] Firestore write failed: %s", exc)
            if not pg_saved and os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Onboarding data could not be saved. Please retry.",
                ) from exc

    return OnboardingStepResponse(
        step=step,
        onboarding=OnboardingProgress(
            current_step=current_step,
            completed_steps=sorted(completed_steps),
            completed=completed,
            last_updated_at=now_dt,
        ),
        profile=profile,
    )


def get_individual_profile(uid: str) -> IndividualProfileResponse:
    stored = None
    doc = _get_firestore_document(uid)
    if doc is not None:
        try:
            snapshot = doc.get()
            read_guard.record_read("users", 1, query_type="targeted_profile_get")
            if snapshot.exists:
                stored = snapshot.to_dict()
        except Exception as exc:
            logger.warning("[ONBOARDING] Firestore get profile failed: %s", exc)
            stored = None

    if stored is None:
        stored = _get_postgres_user_record(uid) or _ephemeral_onboarding_store.get(uid) or {"uid": uid}

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

def _calculate_role_progress(document: dict[str, Any], user_type: str) -> OnboardingProgress:
    limit = ROLE_ONBOARDING_LIMITS.get(user_type, 11)
    role_questions = ROLE_QUESTION_IDS.get(user_type, {})
    stored_profile = document.get("profile") if isinstance(document.get("profile"), dict) else {}
    root = stored_profile.get(f"{user_type}_onboarding_answers")
    root = root if isinstance(root, dict) else {}

    # If no answers exist for this role at all, onboarding has not started yet.
    if not root:
        return OnboardingProgress(
            current_step=1,
            completed_steps=[],
            completed=False,
            last_updated_at=None,
        )

    answered_steps = {
        step for step, qid in role_questions.items()
        if qid in root and root[qid] not in (None, "", [], {})
    }

    role_ob = document.get(f"{user_type}_onboarding")
    if isinstance(role_ob, dict):
        recorded_steps = {s for s in role_ob.get("completed_steps", []) if isinstance(s, int) and 1 <= s <= limit}
        last_updated_at = role_ob.get("last_updated_at")
    elif document.get("user_type") == user_type:
        ob = document.get("onboarding")
        if isinstance(ob, dict):
            recorded_steps = {s for s in ob.get("completed_steps", []) if isinstance(s, int) and 1 <= s <= limit}
            last_updated_at = ob.get("last_updated_at")
        else:
            recorded_steps = set()
            last_updated_at = None
    else:
        recorded_steps = set()
        last_updated_at = None

    completed_steps = sorted(answered_steps | recorded_steps)
    completed = len(completed_steps) >= limit
    if completed:
        current_step = limit
    elif not completed_steps:
        current_step = 1
    else:
        current_step = next((s for s in range(1, limit + 1) if s not in completed_steps), 1)

    return OnboardingProgress(
        current_step=current_step,
        completed_steps=completed_steps,
        completed=completed,
        last_updated_at=last_updated_at,
    )



def get_role_onboarding_profile(uid: str, user_type: str) -> RoleOnboardingProfileResponse:
    if user_type not in ROLE_ONBOARDING_LIMITS:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter"})

    doc = _get_firestore_document(uid)
    stored = None
    if doc is not None:
        try:
            snapshot = doc.get()
            read_guard.record_read("users", 1, query_type="targeted_role_profile_get")
            if snapshot.exists:
                stored = snapshot.to_dict()
        except Exception as exc:
            logger.warning("[ROLE_ONBOARDING] Firestore read failed: %s", exc)
            stored = None

    if stored is None:
        stored = _get_postgres_user_record(uid) or _ephemeral_onboarding_store.get(uid) or {}

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
        if doc is not None:
            try:
                patch = {f"profile.{user_type}.{key}": value for key, value in merged.items()}
                patch["onboarding_schema_version"] = ONBOARDING_SCHEMA_VERSION
                doc.update(patch)
            except Exception as exc:
                logger.warning("[ROLE_ONBOARDING] Firestore patch failed: %s", exc)
        stored_profile[user_type] = merged
        stored["onboarding_schema_version"] = ONBOARDING_SCHEMA_VERSION
        _save_postgres_user_record(
            uid=uid,
            user_type=user_type,
            profile=stored_profile,
            onboarding_data=stored.get("onboarding", {}),
            completed=stored.get("onboarding_completed", False),
            email=stored.get("email"),
            display_name=stored.get("display_name"),
        )
    progress = _calculate_role_progress(stored, user_type)
    return RoleOnboardingProfileResponse(
        uid=uid,
        user_type=user_type,
        answers={**root, **canonical_to_role_answers(user_type, merged)},
        profile=merged,
        onboarding_schema_version=ONBOARDING_SCHEMA_VERSION,
        onboarding=progress,
    )


def save_role_onboarding_step(uid: str, user_type: str, step: int, request: RoleOnboardingStepRequest) -> RoleOnboardingProfileResponse:
    limit = ROLE_ONBOARDING_LIMITS.get(user_type)
    if limit is None or not 1 <= step <= limit:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter", "message": "Invalid onboarding step."})
    if ROLE_QUESTION_IDS[user_type].get(step) != request.question_id:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_filter", "message": "Question does not match account type."})

    doc = _get_firestore_document(uid)
    stored = None
    if doc is not None:
        try:
            snapshot = doc.get()
            read_guard.record_read("users", 1, query_type="targeted_role_profile_get")
            stored = snapshot.to_dict() if snapshot.exists else {}
        except Exception as exc:
            logger.warning("[ROLE_ONBOARDING] Firestore read failed: %s", exc)
            stored = None

    if stored is None:
        stored = _get_postgres_user_record(uid) or _ephemeral_onboarding_store.get(uid) or {}

    if stored.get("user_type") != user_type:
        raise HTTPException(status_code=403, detail="This onboarding profile does not match the account type.")
    progress = _calculate_role_progress(stored, user_type)
    completed_steps = set(progress.completed_steps)
    if not progress.completed and step > progress.current_step and step not in completed_steps:
        raise HTTPException(status_code=409, detail="Complete earlier onboarding steps before continuing.")
    answers = (stored.get("profile") or {}).get(f"{user_type}_onboarding_answers", {})
    answers = dict(answers) if isinstance(answers, dict) else {}
    answer = request.answer
    if user_type == "employee":
        answer = _validate_employee_answer(step, answer, answers)
    answers[request.question_id] = answer
    if user_type == "employee" and step == 4:
        confidence = answers.get("emp_skill_confidence")
        if isinstance(confidence, dict):
            selected = set(answer)
            answers["emp_skill_confidence"] = {
                skill: level for skill, level in confidence.items() if skill in selected
            }
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
    current_step = limit if completed else next((s for s in range(1, limit + 1) if s not in completed_steps), limit)
    company_id = None
    if user_type == "company" and completed:
        company_id = stored.get("company_id") or uuid.uuid5(
            uuid.NAMESPACE_URL, f"talentscope-company-owner:{uid}"
        ).hex
        canonical_merged["company_id"] = company_id
        company_name = canonical_merged.get("company_name")
        try:
            client = get_firestore_client()
            if client:
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
        except Exception as exc:
            logger.warning("[COMPANY_ONBOARDING] Firestore company write failed: %s", exc)

    now_dt = datetime.now(timezone.utc)
    onboarding_data = {
        "current_step": current_step,
        "completed_steps": sorted(completed_steps),
        "completed": completed,
        "last_updated_at": now_dt.isoformat(),
    }
    updated_profile = dict(stored.get("profile") or {})
    updated_profile[f"{user_type}_onboarding_answers"] = answers
    updated_profile[user_type] = canonical_merged

    # Save to PostgreSQL
    _save_postgres_user_record(
        uid=uid,
        user_type=user_type,
        profile=updated_profile,
        onboarding_data=onboarding_data,
        completed=completed,
        email=stored.get("email"),
        display_name=stored.get("display_name"),
    )

    # Save to ephemeral store
    _ephemeral_onboarding_store[uid] = {
        "uid": uid,
        "user_type": user_type,
        "profile": updated_profile,
        "onboarding": onboarding_data,
        "onboarding_completed": completed,
        "company_id": company_id or stored.get("company_id"),
        "email": stored.get("email"),
        "display_name": stored.get("display_name"),
    }

    # Attempt Firestore write if doc available
    if doc is not None:
        try:
            doc.set({"uid": uid}, merge=True)
            update = {
                f"profile.{user_type}_onboarding_answers": answers,
                f"{user_type}_onboarding.current_step": current_step,
                f"{user_type}_onboarding.completed_steps": sorted(completed_steps),
                f"{user_type}_onboarding.completed": completed,
                f"{user_type}_onboarding.last_updated_at": firestore.SERVER_TIMESTAMP,
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
            doc.update(update)
        except Exception as exc:
            logger.warning("[ROLE_ONBOARDING] Firestore write failed: %s", exc)

    return get_role_onboarding_profile(uid, user_type)


def _validate_employee_answer(step: int, answer: Any, existing_answers: dict[str, Any]) -> Any:
    """Validate the employee form's typed values before persisting either representation."""
    try:
        if step == 1:
            return EmployeeIdentityAnswer.model_validate(answer).model_dump(exclude_none=True)
        if step == 2:
            return EmployeeWorkplaceAnswer.model_validate(answer).model_dump(exclude_none=True)
        if step == 3:
            allowed = {
                "New to the field", "Less than 1 year", "1–2 years",
                "3–5 years", "5–10 years", "10+ years",
            }
            if answer not in allowed:
                raise ValueError("Invalid experience band.")
            return answer
        if step in (4, 8):
            if not isinstance(answer, list) or len(answer) > 100:
                raise ValueError("Skills must be a list with at most 100 entries.")
            skills = [item.strip() for item in answer if isinstance(item, str)]
            if len(skills) != len(answer) or any(not item or len(item) > 120 for item in skills):
                raise ValueError("Each skill must be a non-empty string of at most 120 characters.")
            return list(dict.fromkeys(skills))
        if step == 5:
            if not isinstance(answer, dict) or len(answer) > 100:
                raise ValueError("Skill confidence must be an object.")
            selected = existing_answers.get("emp_skills", [])
            if not isinstance(selected, list) or not set(answer).issubset(selected):
                raise ValueError("Confidence values must refer to skills selected in step 4.")
            levels = {"Beginner", "Comfortable", "Advanced", "Expert"}
            if any(not isinstance(skill, str) or level not in levels for skill, level in answer.items()):
                raise ValueError("Invalid skill confidence value.")
            return dict(answer)
        if step == 6:
            allowed = {
                "My technical skills", "My ability to work with AI", "My role performance",
                "My leadership", "My communication", "My career growth",
            }
            return _validate_employee_choices(answer, allowed, max_items=6)
        if step == 7:
            allowed = {
                "Grow in my current role", "Move to a senior role", "Move to another team",
                "Move into a new role", "Become a specialist", "Move into management",
                "Explore another company",
            }
            if answer not in allowed:
                raise ValueError("Invalid career direction.")
            return answer
        if step == 9:
            allowed = {"Less than 2 hours", "2–5 hours", "5–10 hours", "10+ hours"}
            if answer not in allowed:
                raise ValueError("Invalid weekly learning time.")
            return answer
        if step == 10:
            allowed = {
                "Improve my current role performance", "Prepare for promotion milestone",
                "Find another role internally", "Build verified skill evidence",
                "Understand where my role is going with AI", "Prepare for future industry changes",
            }
            return _validate_employee_choices(answer, allowed, max_items=6)
    except (TypeError, ValueError, ValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid answer for employee onboarding step {step}.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Employee onboarding step must be between 1 and 10.",
    )


def _validate_employee_choices(answer: Any, allowed: set[str], *, max_items: int) -> list[str]:
    if not isinstance(answer, list) or len(answer) > max_items:
        raise ValueError("Selections must be a list.")
    if any(not isinstance(item, str) or item not in allowed for item in answer):
        raise ValueError("Selection is not supported.")
    return list(dict.fromkeys(answer))

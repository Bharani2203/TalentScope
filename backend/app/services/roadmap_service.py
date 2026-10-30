from __future__ import annotations

import uuid
import logging
import re
import urllib.parse
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from firebase_admin import firestore
from pydantic import AnyUrl

from app.analytics.learning_roadmap import build_learning_roadmap
from app.analytics.skill_gap import calculate_skill_gap
from app.analytics.skill_registry import BY_ID, normalize_skill_entry
from app.core.config import get_settings
from app.core.firebase import get_firestore_client
from app.models.roadmap import (
    MilestoneProgressUpdate, PersonalizedRoadmap, RoadmapDraftEditRequest, RoadmapDraftResponse,
    RoadmapMilestone, RoadmapPlanRequest,
    RoadmapProfileContext, RoadmapResource, RoadmapStateResponse,
)
from app.services.learning_catalog_service import get_learning_catalog, get_verified_learning_videos, list_learning_resources
from app.services.learning_gemini_service import enrich_missing_learning_content
from app.services.onboarding_service import get_individual_profile
from app.storage.reference_store import ReferenceDataStore

_ROADMAP_COLLECTION = "learning_roadmaps"
_ROADMAP_DOCUMENT = "current"
_ASSESSMENT_COLLECTION = "learning_assessment_attempts"
_ROADMAP_DRAFT_COLLECTION = "learning_roadmap_drafts"
_MAX_MILESTONES = 30
_MAX_RESOURCES_PER_MILESTONE = 12
logger = logging.getLogger(__name__)
_SKILL_ONLY_CAREER_CONTEXT = re.compile(
    r"\b(?:ui\s*/?\s*ux|designer|developer|software engineer|job search|first job|career goal|employer|hiring|vacancy)\b",
    re.I,
)


def _roadmap_firestore_data(roadmap: PersonalizedRoadmap) -> dict[str, Any]:
    """Keep datetimes native while converting Pydantic URLs to Firestore strings."""
    document = roadmap.model_dump(mode="python")
    for milestone in document.get("milestones", []):
        for resource in milestone.get("resources", []):
            if isinstance(resource.get("url"), AnyUrl):
                resource["url"] = str(resource["url"])
            if resource.get("thumbnail_url") is not None:
                resource["thumbnail_url"] = str(resource["thumbnail_url"])
    return document


def _safe_failure_detail(stage: str, exc: Exception) -> str:
    """Return a diagnostic category without logging exception data or user input."""
    if stage == "draft_save":
        if isinstance(exc, TypeError):
            return "Firestore rejected a value with an unsupported field type."
        return "Firestore rejected the pending draft write."
    if stage == "saved_roadmap_read":
        return "Firestore could not read the current roadmap document."
    if stage == "saved_roadmap_validation":
        return "The stored roadmap did not match the current response model."
    if stage == "deterministic_generation":
        return "Profile or reference data could not be converted into a roadmap."
    if stage == "profile_read":
        return "The saved profile could not be read."
    return "The roadmap operation failed."


def _canonical_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned in BY_ID else normalize_skill_entry(cleaned).canonical_skill_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _roadmap_ref(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_ROADMAP_COLLECTION).document(_ROADMAP_DOCUMENT)


def _draft_collection(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_ROADMAP_DRAFT_COLLECTION)


def _profile_for_plan(profile_response, request: RoadmapPlanRequest):
    """Apply explicit wizard choices to a copy of the saved onboarding profile."""
    profile = deepcopy(profile_response.profile) if isinstance(profile_response.profile, dict) else {}
    answers = deepcopy(profile_response.answers) if isinstance(profile_response.answers, dict) else {}
    skills_part = profile.setdefault("skills", {})
    career = profile.setdefault("career", {})
    saved_skills = skills_part.get("selected_skills", [])
    saved_skills = saved_skills if isinstance(saved_skills, list) else []
    levels = skills_part.get("skill_levels", {})
    levels = deepcopy(levels) if isinstance(levels, dict) else {}
    selected = []
    wizard_skill_names = []
    level_override_names = []
    for skill in request.skills:
        normalized = normalize_skill_entry(skill.name)
        level_key = normalized.canonical_skill_id or normalized.display_name.casefold()
        if skill.name not in selected:
            selected.append(skill.name)
        if skill.name not in saved_skills:
            wizard_skill_names.append(skill.name)
        if skill.starting_level == "not sure":
            for existing_key in list(levels):
                existing_normalized = normalize_skill_entry(str(existing_key))
                if (
                    existing_normalized.canonical_skill_id == normalized.canonical_skill_id
                    and normalized.canonical_skill_id
                ) or str(existing_key).strip().casefold() == level_key:
                    levels.pop(existing_key, None)
        elif skill.starting_level:
            levels[level_key] = skill.starting_level
            level_override_names.append(skill.name)
    skills_part["selected_skills"] = selected[:40]
    skills_part["skill_levels"] = levels
    profile["_learning_plan_user_selected_skills"] = wizard_skill_names
    profile["_learning_plan_user_level_overrides"] = level_override_names
    role = request.target_role.strip() if request.target_role else None
    selected_role = role if role and request.plan_type in {"role", "combined"} else None
    explicit_goal = request.goal.strip() if request.goal and request.goal.strip() else None
    career["target_roles"] = [selected_role] if selected_role else []
    career["career_goals"] = [explicit_goal] if explicit_goal else []
    # The wizard is authoritative; onboarding answers must not leak into a new plan.
    answers["target_role"] = selected_role
    answers["career_goal"] = [explicit_goal] if explicit_goal else []
    profile["_learning_plan_type"] = request.plan_type
    profile["_learning_plan_target_role"] = selected_role
    profile["_learning_plan_goal"] = explicit_goal
    profile["_learning_plan_target_duration_days"] = request.target_duration_days
    profile["_learning_plan_target_duration_weeks"] = request.target_duration_weeks
    if request.weekly_learning_time:
        profile.setdefault("work_preferences", {})["learning_time"] = request.weekly_learning_time
    if request.work_preference:
        profile.setdefault("work_preferences", {})["work_preference"] = request.work_preference
    if request.location:
        profile.setdefault("basic_profile", {})["city"] = request.location
    if request.preferences:
        profile["learning_preferences"] = list(request.preferences)
    return SimpleNamespace(profile=profile, answers=answers, onboarding=profile_response.onboarding)


def preview_personalized_roadmap(uid: str, request: RoadmapPlanRequest):
    from app.models.roadmap import RoadmapDraftResponse

    valid = (request.plan_type == "skill" and bool(request.skills)) or (request.plan_type == "role" and bool(request.target_role and request.target_role.strip())) or (request.plan_type == "combined" and bool(request.skills) and bool(request.target_role and request.target_role.strip()))
    if not valid:
        raise HTTPException(status_code=422, detail="Provide a skill, role, or both to match the selected plan type.")
    existing = _saved_roadmap(uid)
    if existing:
        raise HTTPException(status_code=409, detail="An active plan already exists. Existing progress was preserved.")
    stage = "profile_read"
    try:
        base_profile = get_individual_profile(uid)
        plan_profile = _profile_for_plan(base_profile, request)
        stage = "assessment_evidence_read"
        evidence, evidence_read_ok = _assessment_evidence(uid)
        stage = "deterministic_generation"
        roadmap = build_personalized_roadmap(plan_profile, assessment_evidence=evidence)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Roadmap preview failed stage=%s error_class=%s detail=%s", stage, type(exc).__name__, _safe_failure_detail(stage, exc))
        raise HTTPException(status_code=503, detail="A plan preview could not be built from available profile and reference data.") from exc
    if not evidence_read_ok:
        roadmap.assessment_evidence_status = "unknown"
        roadmap.profile_context.evidence_note = "Assessment history could not be checked; no assessment evidence was applied. Levels remain self-reported."
        for milestone in roadmap.milestones:
            milestone.assessment_evidence = {"status": "unknown", "proficiency_verified": False, "note": "Assessment evidence is unknown."}
    roadmap.plan_type = request.plan_type
    if request.plan_type == "skill" and request.skills:
        selected_skill = request.skills[0].name.strip()
        roadmap.title = f"Learn {selected_skill}"
        roadmap.summary = (
            f"A learning plan for {selected_skill}, built from matching taxonomy and catalog records where available. "
            "Any unverified starting level and missing resources are labelled explicitly."
        )
    elif request.plan_type == "role" and request.target_role:
        roadmap.title = f"Prepare for {request.target_role.strip()}"
        if roadmap.milestones:
            roadmap.summary = (
                f"A reference-based plan for {request.target_role.strip()} using available local occupation-skill mappings. "
                "These associations do not establish qualifications, prerequisites, or job-market demand."
            )
        else:
            roadmap.summary = (
                f"No matching O*NET or ESCO occupation match was found for {request.target_role.strip()}; "
                "no role relationship was inferred."
            )
    roadmap.status = "preview"
    roadmap.plan_goal = request.goal or (
        request.skills[0].name.strip() if request.plan_type in {"skill", "combined"} and request.skills
        else request.target_role.strip() if request.target_role else None
    )
    roadmap.plan_preferences = request.preferences
    roadmap.profile_context.weekly_learning_time = request.weekly_learning_time or roadmap.profile_context.weekly_learning_time
    roadmap.profile_context.location = request.location or roadmap.profile_context.location
    roadmap.profile_context.work_preference = request.work_preference or (base_profile.profile.get("work_preferences", {}).get("work_preference") if isinstance(base_profile.profile.get("work_preferences"), dict) else None)
    roadmap.target_duration_weeks = request.target_duration_weeks
    roadmap.target_duration_days = request.target_duration_days
    roadmap.schedule_preference = request.schedule_preference
    try:
        enrich_missing_learning_content(roadmap, request, user_id=uid)
    except Exception as exc:
        # Optional AI enrichment must never prevent a valid deterministic draft.
        logger.warning("Roadmap preview failed stage=optional_enrichment error_class=%s detail=Optional enrichment was skipped; deterministic content is retained.", type(exc).__name__)
    draft_id = str(uuid.uuid4())
    try:
        _draft_collection(uid).document("pending").set({
            "draft_id": draft_id, "status": "pending_approval",
            "roadmap": _roadmap_firestore_data(roadmap),
            "created_at": _now(),
        })
    except Exception as exc:
        logger.warning("Roadmap preview failed stage=draft_save error_class=%s detail=%s", type(exc).__name__, _safe_failure_detail("draft_save", exc))
        raise HTTPException(status_code=503, detail="The plan preview could not be saved safely.") from exc
    return RoadmapDraftResponse(draft_id=draft_id, roadmap=roadmap)


def approve_personalized_roadmap(uid: str, draft_id: str) -> RoadmapStateResponse:
    if not draft_id or len(draft_id) > 80 or not all(char.isalnum() or char == "-" for char in draft_id):
        raise HTTPException(status_code=422, detail="Invalid plan preview ID.")
    try:
        client = get_firestore_client()
        draft_ref = _draft_collection(uid).document("pending")
        current_ref = _roadmap_ref(uid)
        transaction = client.transaction()

        @firestore.transactional
        def commit(tx):
            draft_snapshot = draft_ref.get(transaction=tx)
            current_snapshot = current_ref.get(transaction=tx)
            if not draft_snapshot.exists:
                raise HTTPException(status_code=404, detail="Plan preview was not found.")
            draft = draft_snapshot.to_dict() or {}
            if draft.get("draft_id") != draft_id or draft.get("status") != "pending_approval":
                raise HTTPException(status_code=409, detail="This plan preview has already been used.")
            if current_snapshot.exists:
                raise HTTPException(status_code=409, detail="An active plan already exists; its progress was preserved.")
            roadmap = PersonalizedRoadmap.model_validate(draft.get("roadmap"))
            roadmap.status = "active"
            roadmap.updated_at = _now()
            tx.set(current_ref, _roadmap_firestore_data(roadmap))
            tx.set(draft_ref, {**draft, "status": "approved", "approved_at": _now()})
            return roadmap

        roadmap = commit(transaction)
        return RoadmapStateResponse(roadmap=roadmap, created=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Roadmap operation failed stage=approval_save error_class=%s detail=Active roadmap transaction failed.", type(exc).__name__)
        raise HTTPException(status_code=503, detail="The approved plan could not be activated. No success was reported.") from exc


def update_personalized_roadmap_draft(uid: str, draft_id: str, request: RoadmapDraftEditRequest) -> RoadmapDraftResponse:
    if not draft_id or len(draft_id) > 80 or not all(char.isalnum() or char == "-" for char in draft_id):
        raise HTTPException(status_code=422, detail="Invalid plan preview ID.")
    try:
        client = get_firestore_client()
        draft_ref = _draft_collection(uid).document("pending")
        current_ref = _roadmap_ref(uid)
        transaction = client.transaction()

        @firestore.transactional
        def commit(tx):
            draft_snapshot = draft_ref.get(transaction=tx)
            current_snapshot = current_ref.get(transaction=tx)
            if not draft_snapshot.exists:
                raise HTTPException(status_code=404, detail="Plan preview was not found.")
            if current_snapshot.exists:
                raise HTTPException(status_code=409, detail="An active plan already exists; its progress was preserved.")
            stored = draft_snapshot.to_dict() or {}
            if stored.get("draft_id") != draft_id or stored.get("status") != "pending_approval":
                raise HTTPException(status_code=409, detail="This plan preview is no longer editable.")
            roadmap = PersonalizedRoadmap.model_validate(stored.get("roadmap"))
            original = {item.milestone_id: item for item in roadmap.milestones}
            requested_ids = [item.milestone_id for item in request.stages if item.milestone_id]
            if len(requested_ids) != len(set(requested_ids)):
                raise HTTPException(status_code=422, detail="A learning stage appears more than once.")
            edited = []
            for sequence, stage in enumerate(request.stages, start=1):
                source_id = stage.milestone_id or stage.based_on_milestone_id
                source = original.get(source_id or "")
                if source is None:
                    raise HTTPException(status_code=422, detail="Choose an existing stage as the basis for each new stage.")
                if roadmap.plan_type == "skill" and _SKILL_ONLY_CAREER_CONTEXT.search(
                    " ".join([stage.title, *stage.learning_objectives, stage.practice_activity])
                ):
                    raise HTTPException(status_code=422, detail="Skill-only stages must stay focused on the selected skill.")
                milestone = source.model_copy(deep=True)
                if stage.milestone_id is None:
                    milestone.milestone_id = f"milestone-{uuid.uuid4().hex[:20]}"
                    milestone.status = "not_started"
                    milestone.completion_source = None
                    milestone.completed_at = None
                milestone.sequence = sequence
                milestone.title = stage.title.strip()
                milestone.learning_objectives = [item.strip() for item in stage.learning_objectives]
                milestone.practice_activity = stage.practice_activity.strip()
                milestone.completion_criterion = stage.practice_activity.strip()
                edited.append(milestone)

            roadmap.milestones = edited
            roadmap.target_duration_days = request.target_duration_days
            if request.starting_level is not None and roadmap.plan_type in {"skill", "combined"}:
                selected_skill = next((
                    item for item in roadmap.milestones
                    if item.skill_source in {"user_selected", "onboarding_self_report", "manual_profile_skill"}
                ), None)
                if selected_skill is None:
                    raise HTTPException(status_code=422, detail="This plan has no selected skill whose starting level can be edited.")
                selected_skill.self_reported_level = None if request.starting_level == "not sure" else request.starting_level
                selected_skill.starting_level_source = None if request.starting_level == "not sure" else "user_provided"
                selected_skill.relation_note = (
                    "No starting level was provided by the learner."
                    if request.starting_level == "not sure" else
                    "Starting level provided by the learner; it is not verified proficiency."
                )
            if request.weekly_learning_time is not None:
                roadmap.profile_context.weekly_learning_time = request.weekly_learning_time.strip() or None
            roadmap.updated_at = _now()
            updated = {**stored, "roadmap": _roadmap_firestore_data(roadmap), "updated_at": _now()}
            tx.set(draft_ref, updated)
            return RoadmapDraftResponse(draft_id=draft_id, roadmap=roadmap)

        return commit(transaction)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Roadmap preview failed stage=draft_edit error_class=%s detail=Pending plan edit could not be saved.", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Your plan edits could not be saved. The previous preview remains unchanged.") from exc


def discard_personalized_roadmap_draft(uid: str, draft_id: str) -> None:
    if not draft_id or len(draft_id) > 80 or not all(char.isalnum() or char == "-" for char in draft_id):
        raise HTTPException(status_code=422, detail="Invalid plan preview ID.")
    try:
        client = get_firestore_client()
        ref = _draft_collection(uid).document("pending")
        transaction = client.transaction()

        @firestore.transactional
        def commit(tx):
            snapshot = ref.get(transaction=tx)
            draft = snapshot.to_dict() or {}
            if not snapshot.exists or draft.get("draft_id") != draft_id:
                raise HTTPException(status_code=404, detail="Plan preview was not found.")
            if draft.get("status") != "pending_approval":
                raise HTTPException(status_code=409, detail="This plan preview is no longer pending approval.")
            tx.set(ref, {**draft, "status": "discarded", "discarded_at": _now()})

        commit(transaction)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The plan preview could not be cancelled safely.") from exc


def delete_personalized_roadmap(uid: str) -> None:
    try:
        ref = _roadmap_ref(uid)
        if hasattr(ref, "collection"):
            try:
                progress_collection = ref.collection("chapter_progress")
                for snapshot in progress_collection.stream():
                    if hasattr(snapshot, "reference") and hasattr(snapshot.reference, "delete"):
                        snapshot.reference.delete()
                    elif hasattr(snapshot, "delete"):
                        snapshot.delete()
            except Exception:
                pass
        ref.delete()
    except Exception as exc:
        logger.warning("Roadmap operation failed stage=roadmap_delete error_class=%s detail=%s", type(exc).__name__, _safe_failure_detail("roadmap_delete", exc))
        raise HTTPException(status_code=503, detail="Your learning roadmap could not be deleted. Retry in a moment.") from exc


def _saved_roadmap(uid: str) -> PersonalizedRoadmap | None:
    try:
        snapshot = _roadmap_ref(uid).get()
    except Exception as exc:
        logger.warning("Roadmap operation failed stage=saved_roadmap_read error_class=%s detail=%s", type(exc).__name__, _safe_failure_detail("saved_roadmap_read", exc))
        raise HTTPException(status_code=503, detail="Your saved learning roadmap is temporarily unavailable.") from exc
    if not snapshot.exists:
        return None
    try:
        return PersonalizedRoadmap.model_validate(snapshot.to_dict())
    except Exception as exc:
        logger.warning("Roadmap operation failed stage=saved_roadmap_validation error_class=%s detail=%s", type(exc).__name__, _safe_failure_detail("saved_roadmap_validation", exc))
        raise HTTPException(status_code=503, detail="Your saved learning roadmap could not be read safely.") from exc


def _profile_values(profile_response) -> tuple[dict[str, Any], list[str], dict[str, str], str | None, list[str], list[str], str | None, bool]:
    profile = profile_response.profile if isinstance(profile_response.profile, dict) else {}
    skills_part = profile.get("skills") if isinstance(profile.get("skills"), dict) else {}
    career = profile.get("career") if isinstance(profile.get("career"), dict) else {}
    work = profile.get("work_preferences") if isinstance(profile.get("work_preferences"), dict) else {}
    answers = profile_response.answers if isinstance(profile_response.answers, dict) else {}
    raw_skills = skills_part.get("selected_skills")
    if not isinstance(raw_skills, list):
        raw_skills = answers.get("skills") if isinstance(answers.get("skills"), list) else []
    raw_skills = list(dict.fromkeys(value.strip() for value in raw_skills if isinstance(value, str) and value.strip()))[:40]
    raw_levels = skills_part.get("skill_levels")
    if not isinstance(raw_levels, dict):
        raw_levels = answers.get("skill_levels") if isinstance(answers.get("skill_levels"), dict) else {}
    levels: dict[str, str] = {}
    for label, level in raw_levels.items():
        if isinstance(label, str) and isinstance(level, str) and label.strip() and level.strip():
            normalized = normalize_skill_entry(label)
            levels[normalized.canonical_skill_id or normalized.display_name.casefold()] = level.strip()
    learning_plan_type = profile.get("_learning_plan_type")
    if learning_plan_type in {"skill", "role", "combined"}:
        selected_role = profile.get("_learning_plan_target_role")
        roles = [selected_role] if isinstance(selected_role, str) and selected_role.strip() else []
        selected_goal = profile.get("_learning_plan_goal")
        goals = [selected_goal] if isinstance(selected_goal, str) and selected_goal.strip() else []
    else:
        roles = career.get("target_roles")
        if not isinstance(roles, list) or not roles:
            target = answers.get("target_role")
            roles = [target] if isinstance(target, str) and target.strip() else []
        goals = career.get("career_goals")
        if not isinstance(goals, list):
            goal = answers.get("career_goal")
            goals = goal if isinstance(goal, list) else [goal] if isinstance(goal, str) and goal.strip() else []
    target_role = next((role.strip() for role in roles if isinstance(role, str) and role.strip()), None)
    goals = list(dict.fromkeys(value.strip() for value in goals if isinstance(value, str) and value.strip()))[:12]
    interests = profile.get("interests")
    if not isinstance(interests, list):
        interests = answers.get("interest_areas")
    interests = list(dict.fromkeys(value.strip() for value in interests if isinstance(value, str) and value.strip()))[:12] if isinstance(interests, list) else []
    preferences = profile.get("learning_preferences")
    if not isinstance(preferences, list):
        preferences = answers.get("learning_style")
    preferences = list(dict.fromkeys(value.strip() for value in preferences if isinstance(value, str) and value.strip()))[:12] if isinstance(preferences, list) else []
    weekly_time = work.get("learning_time") or answers.get("weekly_time")
    if not isinstance(weekly_time, str):
        weekly_time = None
    basic = profile.get("basic_profile") if isinstance(profile.get("basic_profile"), dict) else {}
    experience_part = profile.get("experience") if isinstance(profile.get("experience"), dict) else {}
    interests = profile.get("interests")
    if not isinstance(interests, list):
        interests = answers.get("interest_areas")
    interests = list(dict.fromkeys(value.strip() for value in interests if isinstance(value, str) and value.strip()))[:12] if isinstance(interests, list) else []
    experience = experience_part.get("experience") or (answers.get("experience", {}).get("experience") if isinstance(answers.get("experience"), dict) else None)
    study_field = experience_part.get("studyField") or (answers.get("experience", {}).get("studyField") if isinstance(answers.get("experience"), dict) else None)
    location = ", ".join(value.strip() for value in (basic.get("city"), basic.get("country")) if isinstance(value, str) and value.strip()) or None
    return profile, raw_skills, levels, target_role, goals, preferences, weekly_time, bool(profile_response.onboarding.completed), interests, experience, study_field, location


def _taxonomy_context(target_role: str | None):
    if not target_role:
        return None, None, None, None, "No target role is saved; this plan uses only declared onboarding skills."
    try:
        store = ReferenceDataStore(get_settings().reference_database_path, read_only=True)
        onet_matches = store.get_onet_occupations(title=target_role, limit=100)
        exact_onet = [item for item in onet_matches if item.title.strip().casefold() == target_role.casefold()]
        if len(exact_onet) == 1:
            occupation = exact_onet[0]
            rows = store.get_onet_essential_skills_by_occupation(occupation.soc_code, limit=500)
            references = [{**row, "label": row.get("element_name"), "source": "ref_onet_essential_skills"} for row in rows]
            if references:
                return "onet", occupation.soc_code, occupation.title, references, (
                    "O*NET identifies these as occupation-associated skills; the relation does not establish a required qualification or prerequisite."
                )

        esco_matches = store.get_esco_occupations(query=target_role, limit=20)
        exact_esco = [row for row in esco_matches if str(row.get("preferred_label", "")).strip().casefold() == target_role.casefold()]
        if len(exact_esco) == 1:
            occupation = exact_esco[0]
            rows = store.get_esco_occupation_skills(occupation["concept_uri"], limit=500)
            references = [{**row, "label": row.get("preferred_label") or row.get("relation_skill_label"), "source": "ref_esco_occupation_skill_relations"} for row in rows]
            if references:
                return "esco", occupation["concept_uri"], occupation["preferred_label"], references, (
                    "ESCO essential or optional relations are source labels, not proficiency levels or prerequisite order."
                )
    except (OSError, ValueError, RuntimeError):
        return None, None, target_role, None, "Local role taxonomy data could not be read; no role relationship was inferred."
    except Exception:
        return None, None, target_role, None, "Local role taxonomy data could not be read; no role relationship was inferred."
    return None, None, target_role, None, "No exact O*NET or ESCO occupation match was found; no role relationship was inferred."


def _assessment_evidence(uid: str) -> tuple[dict[str, dict[str, Any]], bool]:
    try:
        refs = get_firestore_client().collection("users").document(uid).collection(_ASSESSMENT_COLLECTION)
        snapshots = list(refs.order_by("started_at", direction="DESCENDING").limit(100).stream())
    except Exception:
        return {}, False
    by_skill: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        item = snapshot.to_dict() or {}
        if not isinstance(item, dict):
            continue
        skill_id = item.get("skill_id")
        score, maximum, percentage = item.get("score"), item.get("max_score"), item.get("percentage")
        if (
            item.get("status") != "completed" or not isinstance(skill_id, str)
            or not isinstance(score, int) or isinstance(score, bool)
            or not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0
            or not isinstance(percentage, int) or isinstance(percentage, bool) or not 0 <= percentage <= 100
            or not 0 <= score <= maximum or round(score * 100 / maximum) != percentage
        ):
            continue
        canonical = _canonical_id(skill_id)
        if canonical and canonical not in by_skill:
            by_skill[canonical] = {
                "status": "available_provisional", "score": score, "max_score": maximum,
                "percentage": percentage, "completed_at": item.get("completed_at"),
                "evidence_type": "assessment_derived_provisional",
                "proficiency_verified": False,
            }
    return by_skill, True


def _resource_rows(
    skill_id: str | None,
    preferences: list[str],
    milestone_title: str | None = None,
    skill_name: str | None = None,
    **kwargs: Any,
) -> tuple[list[dict[str, str]], str | None]:
    if not skill_id:
        if milestone_title or skill_name:
            query_subject = f"{skill_name or ''} {milestone_title or ''}".strip()
            encoded_query = urllib.parse.urlencode({"search_query": f"{query_subject} tutorial"})
            slug = re.sub(r"[^a-z0-9]+", "-", (milestone_title or skill_name or "stage").lower()).strip("-")[:25]
            rows = [{
                "resource_id": f"youtube-search-role-{slug}",
                "title": f"YouTube search: {milestone_title}" if milestone_title else f"YouTube search: {skill_name}",
                "url": f"https://www.youtube.com/results?{encoded_query}",
                "provider": "YouTube",
                "resource_type": "video_search",
                "verification_status": "unverified_search_results",
                "provenance": f"Search URL generated for {query_subject}; individual results are not reviewed or verified.",
                "license_attribution": "Search results may contain third-party content under varying terms; review each video's license.",
                "video_id": None,
                "thumbnail_url": None,
            }]
            return rows, None
        return [], "This skill does not map to the canonical resource catalog; no resource links were inferred."
    try:
        catalog = list(get_learning_catalog())
        videos = list(get_verified_learning_videos())
    except (OSError, ValueError):
        catalog, videos = [], []
    rows: list[dict[str, str]] = []
    for resource in catalog:
        if skill_id not in resource.skill_ids:
            continue
        rows.append({
            "resource_id": resource.resource_id, "title": resource.title, "url": str(resource.url),
            "provider": resource.provider, "resource_type": resource.resource_type,
            "verification_status": resource.verification_status, "provenance": resource.provenance,
            "license_attribution": resource.license_attribution,
        })
    matching_videos = [video for video in videos if skill_id in video.skill_ids]
    for video in matching_videos:
        rows.append({
            "resource_id": f"youtube-{video.video_id}", "title": video.title, "url": str(video.url),
            "provider": video.channel_name, "resource_type": "video",
            "verification_status": video.verification_status, "provenance": video.provenance,
            "license_attribution": video.license_attribution,
            "video_id": video.video_id,
            "thumbnail_url": f"https://i.ytimg.com/vi/{video.video_id}/hqdefault.jpg",
        })
    if not matching_videos:
        if milestone_title:
            query_subject = f"{skill_name or skill_id} {milestone_title}".strip()
            encoded_query = urllib.parse.urlencode({"search_query": f"{query_subject} tutorial"})
            slug = re.sub(r"[^a-z0-9]+", "-", milestone_title.lower()).strip("-")[:25]
            rows.append({
                "resource_id": f"youtube-search-{skill_id}-{slug}",
                "title": f"YouTube search: {milestone_title} ({skill_name or skill_id})",
                "url": f"https://www.youtube.com/results?{encoded_query}",
                "provider": "YouTube",
                "resource_type": "video_search",
                "verification_status": "unverified_search_results",
                "provenance": f"Search URL generated for {milestone_title}; individual results are not reviewed or verified.",
                "license_attribution": "Search results may contain third-party content under varying terms; review each video's license.",
                "video_id": None,
                "thumbnail_url": None,
            })
        else:
            try:
                search = [item for item in list_learning_resources(skill_id=skill_id, resource_type="video_search", limit=1)
                          if item.verification_status == "unverified_search_results"]
                for item in search:
                    rows.append({
                        "resource_id": item.resource_id, "title": item.title, "url": str(item.url),
                        "provider": item.provider, "resource_type": item.resource_type,
                        "verification_status": item.verification_status, "provenance": item.provenance,
                        "license_attribution": item.license_attribution,
                        "video_id": None,
                        "thumbnail_url": None,
                    })
            except (ValueError, OSError):
                pass
    lowered = " ".join(preferences).casefold()
    if "video" in lowered:
        rank = {"video": 0, "video_search": 1}
    elif "reading" in lowered or "documentation" in lowered:
        rank = {"documentation": 0, "course": 1}
    elif any(term in lowered for term in ("hands-on", "project", "practice", "coding", "design", "interview")):
        rank = {"practice": 0, "course": 1}
    else:
        rank = {}
    rows.sort(key=lambda item: rank.get(item["resource_type"], 5))
    rows = rows[:_MAX_RESOURCES_PER_MILESTONE]
    return rows, None if rows else "No verified resource link or curated video is available for this skill yet."


def _generate_adaptive_skill_milestones(skill_name: str, skill_id: str | None, level: str | None, duration_days: int, level_source: str | None = None) -> list[dict[str, Any]]:
    norm_level = (level or "beginner").casefold().strip()
    if norm_level in ("comfortable", "intermediate"):
        norm_level = "intermediate"
    elif norm_level in ("expert", "advanced"):
        norm_level = "advanced"
    elif norm_level in ("not sure", "not_sure", "basic", "basic knowledge", "beginner"):
        norm_level = "beginner"
    is_advanced = norm_level in {"intermediate", "advanced"}
    label = skill_name.casefold()
    target_count = 5 if duration_days <= 30 else (9 if duration_days <= 60 else 14)

    if label in {"c", "c programming", "c language", "c programming language"}:
        if is_advanced:
            c_advanced_plan = [
                ("Pointer Arithmetic, Double Pointers & Memory Models",
                 ["Master pointer arithmetic, void pointers, and dereferencing", "Analyze memory layout, stack vs heap, and data alignment"],
                 "Implement a custom dynamic array with pointer arithmetic and reallocation.",
                 "Compile with -Wall -Wextra and verify no memory leaks using valgrind or address sanitizer."),
                ("Dynamic Memory Allocators & Struct Architecture",
                 ["Structure memory layout, padding, and offset calculation", "Implement custom memory arena or pool allocator"],
                 "Write a small arena allocator in C that manages a contiguous memory buffer.",
                 "Verify allocations and deallocations succeed without fragmentation."),
                ("Function Pointers, Callbacks & Abstract Data Types",
                 ["Understand function pointer syntax and signature typing", "Implement callback patterns and table-driven dispatch"],
                 "Build an extensible event dispatcher or callback registry in C.",
                 "Test callback invocations with multiple handlers and verify clean dispatch."),
                ("Modular Architecture, Header Guards & Makefile Builds",
                 ["Organize multi-file C programs with clear interfaces", "Write a standard Makefile with compilation, linking, and clean rules"],
                 "Split a C project into headers, implementation files, and write a Makefile.",
                 "Run make and confirm incremental builds work correctly."),
                ("System Buffer Management & I/O Engine",
                 ["Use low-level file descriptors and buffered I/O", "Handle partial reads, writes, and EOF conditions robustly"],
                 "Implement a high-performance buffered file copier with error recovery.",
                 "Benchmark throughput against standard library and verify file integrity."),
                ("Dynamic Linear Data Structures: Linked Lists & Queues",
                 ["Implement singly and doubly linked lists with robust pointer manipulation", "Handle edge cases: head insertion, tail deletion, empty lists"],
                 "Build a generic doubly linked list library in C.",
                 "Pass all unit tests for insertion, deletion, searching, and memory cleanup."),
                ("Hierarchical Data Structures: Binary Trees & Heaps",
                 ["Implement binary search trees with recursive and iterative traversal", "Implement min/max heap for priority queueing"],
                 "Construct a balanced BST and verify in-order, pre-order traversals.",
                 "Demonstrate correct node removal and re-balancing."),
                ("Bitwise Manipulation, Flags & Serialization",
                 ["Use bit shifts, bitmasks, and bitfields for compact storage", "Serialize and deserialize structured binary records"],
                 "Write a binary encoder/decoder using bitwise flags for packet headers.",
                 "Confirm round-trip encoding and decoding preserves all bit patterns."),
                ("Memory Leak Profiling & Valgrind Hardening",
                 ["Identify dangling pointers, double frees, and memory leaks", "Profile cache misses and instruction counts"],
                 "Audit an existing C codebase with Valgrind and AddressSanitizer, fixing all reported issues.",
                 "Zero leaks, zero invalid reads/writes confirmed in sanitizers."),
                ("POSIX Threads & Concurrency Primitives",
                 ["Create and join threads using pthread library", "Use mutexes, condition variables, and semaphores"],
                 "Implement a producer-consumer thread pool with a thread-safe task queue.",
                 "Confirm synchronization without race conditions under thread sanitizer."),
                ("Socket Programming & Network Communication",
                 ["Create TCP client/server sockets with POSIX APIs", "Handle non-blocking I/O and select/poll event loops"],
                 "Write a lightweight TCP echo server handling concurrent connections.",
                 "Test multi-client throughput with netcat or curl."),
                ("System Calls & IPC: Pipes, Shared Memory & Signals",
                 ["Manage processes with fork, exec, waitpid", "Use pipes, named FIFOs, and POSIX shared memory for IPC"],
                 "Implement a process pipeline tool that streams data across processes.",
                 "Verify clean process termination and signal handling."),
                ("Optimization, Inlining & Compiler Flags",
                 ["Analyze compiler optimization levels (-O2, -O3)", "Use register allocation, branch prediction hints, and vectorization"],
                 "Optimize a compute-heavy algorithm and compare disassembly outputs.",
                 "Demonstrate measurable execution speedup with profiling evidence."),
                ("Production C Capstone: High-Performance Memory Cache",
                 ["Synthesize systems programming, concurrency, and dynamic data structures", "Package as a modular, tested, documented C library"],
                 "Build an in-memory key-value cache with LRU eviction and thread safety.",
                 "Run concurrent stress benchmarks and document throughput and memory usage.")
            ]
            selected_stages = c_advanced_plan[:target_count]
        else:
            c_beginner_plan = [
                ("Introduction to C and Development Setup",
                 ["What Is C Programming?", "Applications of C and How a C Program Works", "Installing and Configuring GCC or Clang", "Writing, Compiling and Running Your First Hello World Program"],
                 "Install GCC or Clang, write a Hello World program, and verify output and compilation with -Wall -Wextra.",
                 "Compile without warnings and verify output matches expected string."),
                ("C Syntax, Variables and Data Types",
                 ["Basic Syntax, Statements and Comments", "Variables, Constants and Identifiers", "Primitive Data Types and Type Modifiers", "Input and Output Using printf and scanf", "Type Conversion and Basic Operators"],
                 "Write a C program that calculates formatted temperature and currency conversions using diverse data types.",
                 "Compile cleanly with zero warnings and verify correct numerical formatting."),
                ("Operators and Control Flow",
                 ["Arithmetic, Relational and Logical Operators", "Conditional Statements: if, else and switch", "Loops: for, while and do-while", "break, continue and Nested Loops"],
                 "Write a C console program that evaluates prime numbers, generates Fibonacci numbers, and prints matrix patterns.",
                 "Test with positive, negative, and edge-case inputs (0, 1) and confirm correct branching."),
                ("Functions and Program Structure",
                 ["Function Declaration, Definition and Calling", "Parameters, Return Values and Scope", "Recursion and Modular Programming"],
                 "Create a modular math utility library with functions for factorial, power, and greatest common divisor.",
                 "Call each function from main and verify return values against expected outputs."),
                ("Arrays and Strings",
                 ["One-Dimensional and Multidimensional Arrays", "Character Arrays and String Fundamentals", "Standard String Functions", "String Input, Boundaries and Common Errors"],
                 "Write a program that processes integer arrays, computes statistics, and manipulates null-terminated strings safely.",
                 "Confirm boundary checks prevent buffer overflows on sample strings."),
                ("Pointers and Memory",
                 ["Pointer Fundamentals", "Pointers and Arrays", "Passing Arguments Using Pointers", "Dynamic Memory Allocation", "Memory Safety and Common Pointer Errors"],
                 "Implement a dynamic vector that allocates memory with malloc/calloc, resizes with realloc, and frees clean.",
                 "Compile and run without memory leaks or dangling pointers."),
                ("Structures and File Handling",
                 ["Structures, Unions and Enumerations", "File Operations and File Modes", "Reading and Writing Files", "Error Handling and Resource Management"],
                 "Build a record management system using typedef structs that serializes and loads records to a text file.",
                 "Verify records persist accurately across file open and close operations."),
                ("Practical C Programming and Final Assessment",
                 ["Problem-Solving Exercises", "Debugging and Code Quality", "Integrated Programming Project", "Comprehensive Chapter and Course Knowledge Assessment"],
                 "Build an integrated C command-line application incorporating structs, dynamic memory, safe string input, and file persistence.",
                 "Achieve 100% pass on comprehensive functional checks, clean compiler builds, and chapter assessment benchmarks."),
                ("Advanced Pointers, Double Pointers & Function Callbacks",
                 ["Work with pointers to pointers (double pointers)", "Implement function pointers for generic callbacks and sorting"],
                 "Write a generic sorting function in C that accepts a custom comparison callback.",
                 "Sort diverse data types (integers, strings, custom structs) using the same engine."),
                ("Bitwise Manipulation, Masks & Flags",
                 ["Apply bitwise operators (&, |, ^, ~, <<, >>)", "Implement bitmasking for state flags and compact permissions"],
                 "Create a compact 8-bit permission manager using bitwise operators.",
                 "Verify flag setting, clearing, and toggling logic with test bitmasks."),
                ("Preprocessor Macros, Build Systems & Makefiles",
                 ["Define object-like and function-like preprocessor macros", "Use conditional compilation (#ifdef, #ifndef)", "Write a clean Makefile with build targets"],
                 "Construct a multi-file project with headers, source files, and a robust Makefile.",
                 "Execute make, make test, and make clean to verify compilation targets."),
                ("Linear Data Structures in C: Linked Lists",
                 ["Implement node structures and dynamic pointer linking", "Perform insertion, deletion, and traversal on linked lists"],
                 "Build a dynamic singly linked list library with search and delete functions.",
                 "Verify list integrity after deleting head, middle, and tail nodes."),
                ("System Programming Capstone: POSIX Utilities",
                 ["Synthesize C memory management, file streams, and modular architecture", "Deliver a well-documented, clean production C application"],
                 "Build a lightweight Unix-like text processing utility (e.g. custom grep/cat clone).",
                 "Test against standard input, files, and verify robust command-line argument handling.")
            ]
            selected_stages = c_beginner_plan[:target_count]
    elif "python" in label:
        if is_advanced:
            py_advanced_plan = [
                ("Advanced OOP: Dunder Methods, Descriptors & Metaclasses",
                 ["Leverage __new__, __init__, and special dunder protocols", "Implement custom descriptors for attribute validation", "Understand class creation hooks and metaclasses"],
                 "Write a declarative data validation framework using descriptors.",
                 "Validate fields reject invalid types and accept valid inputs."),
                ("Iterators, Generators & Memory-Efficient Pipelines",
                 ["Build custom iterator classes using __iter__ and __next__", "Write generator functions and generator expressions", "Chain data transformations with itertools"],
                 "Construct a streaming log processor that filters large files in constant memory.",
                 "Confirm low memory usage with huge simulated log inputs."),
                ("Context Managers & Resource Management",
                 ["Implement context managers using __enter__ and __exit__", "Use contextlib.contextmanager for generator-based resource management"],
                 "Write a database transaction / file lock context manager with automatic rollback.",
                 "Verify rollback executes reliably when exceptions occur inside with blocks."),
                ("Functional Python & Decorator Architecture",
                 ["Create parameterized decorators and class-based decorators", "Preserve function metadata with functools.wraps", "Implement memoization, retry, and timing decorators"],
                 "Build a reusable caching and rate-limiting decorator suite.",
                 "Verify cached functions skip execution on identical arguments."),
                ("Concurrency: Asyncio & Non-Blocking Architecture",
                 ["Understand the asyncio event loop, coroutines, and tasks", "Run concurrent operations with asyncio.gather and TaskGroup"],
                 "Build an asynchronous web scraper or HTTP fetcher with concurrency limits.",
                 "Measure concurrent fetch latency vs sequential execution."),
                ("Multiprocessing, Threading & CPU Parallelism",
                 ["Differentiate CPU-bound vs I/O-bound tasks in Python", "Use concurrent.futures and multiprocessing.Pool to bypass GIL"],
                 "Parallelize a data processing algorithm across CPU cores.",
                 "Benchmark multi-core execution time showing speedup over single-threaded run."),
                ("Testing Architecture: Pytest, Fixtures & Mocking",
                 ["Structure enterprise test suites with pytest", "Write parameterized fixtures and mock external dependencies with unittest.mock"],
                 "Create a comprehensive test suite with 90%+ branch coverage for a core service.",
                 "Confirm all tests pass and mock assertions verify external calls."),
                ("Type Hinting, Pydantic & Static Analysis with Mypy",
                 ["Use advanced typing: Union, Optional, Protocol, TypeVar, Generic", "Enforce runtime contracts with Pydantic v2", "Run mypy in strict mode"],
                 "Refactor an untyped module with strict type annotations and Pydantic models.",
                 "Ensure mypy passes without typing errors in strict mode."),
                ("Database Architecture: SQLAlchemy & Migration Tooling",
                 ["Define declarative models and relationship mappings", "Execute complex queries with joins and subqueries", "Manage schema migrations with Alembic"],
                 "Build a persistence layer with SQLAlchemy and create database migration scripts.",
                 "Verify database migrations apply cleanly and roll back without data loss."),
                ("REST API Engineering with FastAPI",
                 ["Build modular API routers and dependency injection providers", "Handle authentication, validation, and status codes"],
                 "Develop a production-grade CRUD microservice with FastAPI and JWT auth.",
                 "Test API endpoints with pytest and HTTP client."),
                ("Profiling, Caching & Performance Optimization",
                 ["Profile bottlenecks using cProfile and memory_profiler", "Implement caching with Redis or functools.lru_cache"],
                 "Profile an API endpoint, optimize hot paths, and demonstrate latency reduction.",
                 "Document before-and-after latency and memory usage charts."),
                ("Packaging, CI/CD & Production Distribution",
                 ["Configure pyproject.toml and package dependencies with poetry/uv", "Build automated GitHub Actions workflows for linting, testing, and packaging"],
                 "Package a Python library with full CI test automation.",
                 "Verify clean build and distribution artifacts."),
                ("Security Hardening & Code Quality Standards",
                 ["Audit vulnerabilities with bandit and pip-audit", "Format and lint with ruff and black"],
                 "Audit a Python project for OWASP top vulnerabilities and sanitize inputs.",
                 "Achieve zero reported security vulnerabilities in automated scanners."),
                ("Production Python Capstone: Microservice Engine",
                 ["Synthesize async architecture, testing, API design, and persistence", "Deliver a production-ready repository with Docker and docs"],
                 "Build a complete distributed background task processing engine in Python.",
                 "Demonstrate end-to-end task submission, processing, and persistence.")
            ]
            selected_stages = py_advanced_plan[:target_count]
        else:
            py_beginner_plan = [
                ("Python Environment, Variables & Primitive Types",
                 ["Set up Python 3 runtime and interactive REPL", "Declare variables and work with integers, floats, strings, and booleans", "Perform input/output and type conversions"],
                 "Write a Python script that calculates user expenses with formatted summaries.",
                 "Run the script and verify math operations produce correct results."),
                ("Control Flow: Conditionals & Loops",
                 ["Implement if, elif, else conditional branching", "Iterate sequences using for loops and while loops", "Use break, continue, and enumerate effectively"],
                 "Create a number guessing game with input validation and score tracking.",
                 "Test all branches and verify loop termination on valid winning conditions."),
                ("Reusable Functions & Modular Architecture",
                 ["Define functions with parameters, default arguments, and return values", "Understand variable scope (local vs global)", "Import and use standard library modules (math, random, sys)"],
                 "Build a modular calculator script with separate math utility functions.",
                 "Confirm functions return correct values across diverse inputs."),
                ("Collections: Lists, Tuples, Dictionaries & Sets",
                 ["Store and manipulate ordered data with lists and tuples", "Use key-value mappings with dictionaries", "Perform set operations (unions, intersections) and list comprehensions"],
                 "Implement a student gradebook and inventory manager using dictionaries and lists.",
                 "Verify adding, updating, and querying items works accurately."),
                ("File Handling, Exceptions & Core Scripting Project",
                 ["Read and write text files using with open context managers", "Handle exceptions using try, except, finally blocks", "Deliver a foundational Python script"],
                 "Write a script that reads a CSV file, calculates column averages, and logs errors.",
                 "Verify output file contains calculated statistics."),
                ("Object-Oriented Programming: Classes & Objects",
                 ["Define classes with __init__ constructors and instance methods", "Understand instance variables vs class variables", "Implement basic encapsulation and helper methods"],
                 "Build a bank account or library management system with classes.",
                 "Instantiate objects and verify state transitions through method calls."),
                ("Modules, Packages & Virtual Environments",
                 ["Create modular packages with __init__.py", "Manage isolated dependencies using venv and pip", "Install and import external packages"],
                 "Create a multi-file Python package inside a virtual environment.",
                 "Verify clean module imports across package boundaries."),
                ("Working with External APIs & JSON Data",
                 ["Parse and generate JSON data with the json module", "Make HTTP GET and POST requests using urllib or requests", "Handle network status codes and error responses"],
                 "Build a weather or news briefing script that queries a public REST API.",
                 "Confirm valid JSON parsing and graceful fallback on network timeouts."),
                ("Intermediate Application: Automated Data Pipeline",
                 ["Integrate OOP, file I/O, error handling, and external APIs", "Produce a standalone, useful automation tool"],
                 "Develop an automated file organizer that categorizes downloads by type.",
                 "Test sorting across sample folders and confirm file integrity."),
                ("Advanced Python Concepts: Generators & Decorators",
                 ["Write generator functions using yield for lazy evaluation", "Create custom function decorators for logging and timing"],
                 "Build a log streaming generator and a function execution timer decorator.",
                 "Confirm memory efficiency and accurate timing output."),
                ("Unit Testing & Quality Assurance with Pytest",
                 ["Write test functions and assertions with pytest", "Use test fixtures and test discovery for automated suites"],
                 "Write a full unit test suite for a data processing module.",
                 "Run pytest and confirm all tests pass cleanly."),
                ("Database Operations with SQLite & Python",
                 ["Connect to SQLite databases using sqlite3 module", "Execute parameterized queries to prevent SQL injection", "Manage commits and transactions"],
                 "Build a persistent task tracking application backed by SQLite.",
                 "Verify records persist across application restarts."),
                ("Asynchronous Basics with Asyncio",
                 ["Understand async def and await syntax", "Execute concurrent tasks with asyncio.gather"],
                 "Write an asynchronous downloader that fetches multiple resources concurrently.",
                 "Measure time savings vs sequential downloads."),
                ("Production-Ready Capstone: Full Python Application",
                 ["Synthesize data structures, OOP, testing, and persistence", "Deliver a polished command-line tool with documentation"],
                 "Build a comprehensive personal finance manager CLI with database storage and unit tests.",
                 "Demonstrate end-to-end functionality from user input to persistent reports.")
            ]
            selected_stages = py_beginner_plan[:target_count]
    else:
        generic_plan = [
            (f"{skill_name} Foundations & Setup",
             [f"Configure environment and tooling for {skill_name}", f"Understand core terminology and syntax conventions in {skill_name}"],
             f"Complete a foundational setup and write a baseline exercise in {skill_name}.",
             f"Verify successful execution and record your setup configuration."),
            (f"{skill_name} Primitives & Core Operations",
             [f"Master fundamental data primitives and operations in {skill_name}", f"Apply logical structures and standard patterns"],
             f"Implement a practical logic exercise demonstrating core operations in {skill_name}.",
             f"Check output accuracy against test inputs."),
            (f"{skill_name} Modular Structure & Functions",
             [f"Organize code into reusable components/functions in {skill_name}", f"Apply parameter passing and scope rules"],
             f"Build a multi-component utility module in {skill_name}.",
             f"Verify modular reusability with unit calls."),
            (f"{skill_name} Data Handling & Collections",
             [f"Work with complex data structures and collections in {skill_name}", f"Perform data transformations and validations"],
             f"Implement a data processing task that structures and cleans sample input.",
             f"Confirm data integrity and handling of boundary conditions."),
            (f"{skill_name} Core Practical Project",
             [f"Synthesize foundational concepts into a working application", f"Review implementation against domain standards"],
             f"Build a standalone milestone project applying {skill_name} to a real-world problem.",
             f"Verify all project acceptance criteria are met."),
            (f"{skill_name} Error Handling & Robustness",
             [f"Implement defensive programming and error handling in {skill_name}", f"Debug common runtime exceptions and edge cases"],
             f"Harden an application with comprehensive error handling and logging.",
             f"Test edge cases and verify graceful failure behavior."),
            (f"{skill_name} Advanced Patterns & State Management",
             [f"Apply architectural and design patterns relevant to {skill_name}", f"Manage state transitions and component boundaries"],
             f"Refactor an implementation to use established {skill_name} design patterns.",
             f"Review design against maintainability criteria."),
            (f"{skill_name} External Integrations & I/O",
             [f"Connect {skill_name} components to external data sources or APIs", f"Handle asynchronous data transfer and persistence"],
             f"Build an integration that consumes external data and produces structured output.",
             f"Confirm robust communication and error recovery."),
            (f"{skill_name} Intermediate System Milestone",
             [f"Build a complete multi-feature application in {skill_name}", f"Incorporate data handling, error recovery, and modular architecture"],
             f"Deliver a fully functional system with documentation and clear instructions.",
             f"Demonstrate all primary use cases end-to-end."),
            (f"{skill_name} Performance Optimization & Efficiency",
             [f"Analyze execution bottlenecks in {skill_name}", f"Apply memory and speed optimization techniques"],
             f"Profile a resource-intensive task and optimize hot execution paths.",
             f"Measure and document benchmark performance improvements."),
            (f"{skill_name} Automated Testing & Verification",
             [f"Implement automated unit and integration tests for {skill_name}", f"Cover edge cases and failure paths"],
             f"Construct a comprehensive test suite with automated assertions.",
             f"Run the test suite and confirm 100% pass rate."),
            (f"{skill_name} Architectural Design & Refactoring",
             [f"Evaluate system architecture and decouple components", f"Apply separation of concerns and clean code principles"],
             f"Perform architectural refactoring on an existing codebase.",
             f"Verify backward compatibility and improved modularity."),
            (f"{skill_name} Production Readiness & Tooling",
             [f"Set up build pipelines, linting, and deployment configurations", f"Document APIs and usage guidelines"],
             f"Configure production build tooling and automated quality checks.",
             f"Verify automated pipeline passes all checks."),
            (f"{skill_name} Capstone Project & Portfolio Defense",
             [f"Deliver an end-to-end production-grade portfolio project in {skill_name}", f"Synthesize all concepts learned across the curriculum"],
             f"Build, document, and test a capstone project demonstrating mastery of {skill_name}.",
             f"Conduct a self-review against professional production standards.")
        ]
        selected_stages = generic_plan[:target_count]

    specs = []
    starting_level_source = "user_provided" if level_source == "user_provided" else ("self_reported_onboarding" if level else None)
    for idx, (title, objs, task, crit) in enumerate(selected_stages, start=1):
        try:
            stage_res, stage_note = _resource_rows(skill_id, [], milestone_title=title, skill_name=skill_name)
        except TypeError:
            stage_res, stage_note = _resource_rows(skill_id, [])
        specs.append({
            "identity": f"skill:{skill_id or label}:stage-{idx}",
            "name": title,
            "skill_name": skill_name,
            "skill_id": skill_id,
            "source": "user_selected",
            "self_reported_level": level,
            "starting_level_source": starting_level_source,
            "explanation": f"Practice guidance: Focus on {title.lower()} to build progressive capability in {skill_name}.",
            "learning_objectives": objs,
            "practice_activity": task,
            "completion_criterion": crit,
            "relation_note": f"Stage {idx} of {len(selected_stages)} in your {duration_days}-day {skill_name} roadmap ({norm_level.capitalize()} track).",
            "resources": stage_res,
            "resource_note": stage_note,
            "is_stage": True,
        })
    return specs


def _generate_adaptive_role_milestones(role_name: str, level: str | None, duration_days: int, level_source: str | None = None) -> list[dict[str, Any]]:
    norm_level = (level or "beginner").strip().lower()
    if norm_level in ("comfortable", "intermediate"):
        norm_level = "intermediate"
    elif norm_level in ("expert", "advanced"):
        norm_level = "advanced"
    elif norm_level in ("not sure", "not_sure", "basic", "basic knowledge", "beginner"):
        norm_level = "beginner"
    target_count = 12 if duration_days >= 90 else (8 if duration_days >= 50 else 5)
    is_design = any(k in role_name.casefold() for k in ["ui/ux", "ui_ux", "design", "product designer", "ux designer", "ui designer"])

    if is_design:
        role_plan = [
            ("Design Fundamentals, Nielsen Norman Heuristics & User Mental Models",
             ["Analyze user mental models and cognitive load in digital interfaces", "Master Jakob Nielsen's 10 usability heuristics and visual affordance"],
             "Audit a landing page against Nielsen's 10 usability heuristics, documenting specific friction points.",
             "Produce a structured heuristic evaluation report with actionable remediation recommendations."),
            ("User Research, Persona Modeling & Journey Mapping",
             ["Formulate user interview protocols and qualitative research plans", "Synthesize behavioral personas and end-to-end customer journey maps"],
             "Create two archetypal user personas and map an onboarding journey identifying high-dropoff steps.",
             "Validate journey map against empirical user goals and pain points."),
            ("Information Architecture, Wireframing & Low-Fidelity Layouts",
             ["Organize information hierarchies using card sorting and site trees", "Construct rapid low-fidelity paper and digital wireframes in Figma"],
             "Draft wireframes for a 3-screen core checkout or registration workflow focusing on spatial grouping.",
             "Confirm information hierarchy minimizes navigation friction."),
            ("Design Systems, Typography, Color Accessibility & Component Tokens",
             ["Establish typography scales, 8pt spatial grids, and WCAG AA contrast palettes", "Build reusable component libraries with atomic design tokens"],
             "Construct a basic Figma component system with responsive buttons, inputs, and state variants.",
             "Verify color pairings meet WCAG 2.1 AA 4.5:1 contrast ratios."),
            ("Mid-Term Milestone: Interactive High-Fidelity Prototype",
             ["Assemble an end-to-end interactive desktop and mobile prototype", "Implement smart animations, micro-interactions, and component overrides"],
             "Deliver a clickable 5-screen interactive product prototype in Figma.",
             "Verify interactive transitions simulate real user experience seamlessly."),
            ("Usability Testing, Heuristic Audit & WCAG 2.1 Accessibility",
             ["Conduct think-aloud usability testing sessions with representative participants", "Audit keyboard navigation, screen reader accessibility, and focus indicators"],
             "Conduct a 3-person usability test on your prototype and log task completion times.",
             "Synthesize test observations into an executive usability improvements matrix."),
            ("Micro-interactions, Motion Design & Developer Handoff",
             ["Design functional easing curves and micro-interaction states", "Export design specifications, CSS tokens, and asset bundles for engineering"],
             "Prepare a comprehensive Figma developer handoff document with component token specs.",
             "Confirm spacing, tokens, and typography correspond to standard CSS variables."),
            ("Responsive Layouts & Cross-Platform UX Architecture",
             ["Adapt desktop layouts to tablet and mobile viewports using auto-layout", "Optimize touch targets and mobile thumb zones"],
             "Produce responsive breakpoint variations (Mobile 375px, Tablet 768px, Desktop 1440px).",
             "Ensure minimum 48x48px touch targets across all mobile interactive controls."),
            ("Design Review, Critique & Case Study Defense",
             ["Present design decisions defending business and user experience trade-offs", "Incorporate cross-functional stakeholder feedback into iterative revisions"],
             "Write a structured case study detailing problem discovery, iteration, and design rationale.",
             "Defend design decisions against user research and technical constraints."),
            ("Advanced UX Analytics & Conversion Rate Optimization",
             ["Analyze product analytics, heatmaps, and funnel drop-off metrics", "Formulate data-backed A/B testing hypotheses to improve task completion"],
             "Analyze a conversion drop-off funnel and draft two divergent design remediation variants.",
             "Document measurable success metrics and evaluation criteria."),
            ("Enterprise Product Design & Complex Workflow Synthesis",
             ["Synthesize data-dense dashboards, tables, and enterprise permission hierarchies", "Manage complex data filtering, batch actions, and modal workflows"],
             "Design a data-dense SaaS management table with sorting, filtering, and bulk actions.",
             "Verify readability, pagination, and cognitive load management."),
            ("Design Portfolio Defense & Mock Whiteboard Challenge",
             ["Practice whiteboard product design interview challenges under time constraints", "Communicate design frameworks and problem framing clearly"],
             "Complete a 45-minute timed whiteboard design challenge solving a novel product prompt.",
             "Review structured solution against clarity, empathy, and feasibility rubrics."),
            ("Capstone Design System & Final Portfolio Review",
             ["Package complete multi-screen case studies into a professional design portfolio", "Document design systems documentation and component token architecture"],
             "Publish a polished design case study portfolio ready for hiring review.",
             "Ensure repository or Figma link includes research, wireframes, and final prototypes."),
            ("Comprehensive Industry UX Case Study Defense",
             ["Synthesize all design disciplines into an executive presentation", "Deliver oral and visual defense of an end-to-end design solution"],
             "Record or present an end-to-end walkthrough defending the complete product journey.",
             "Verify all acceptance criteria, accessibility standards, and heuristic guidelines are met.")
        ]
        assigned_skill_id = "ui_ux"
    else:
        role_plan = [
            (f"Core Technical Fundamentals for {role_name}",
             [f"Analyze foundational concepts and core competencies required for {role_name}", f"Understand role-specific architectural paradigms"],
             f"Complete a foundational skills review and baseline implementation relevant to {role_name}.",
             "Verify output against baseline domain standards."),
            (f"Professional Tooling & Workflows for {role_name}",
             [f"Configure professional development workflows, version control, and environments for {role_name}", f"Adopt industry-standard collaboration tools"],
             f"Set up a complete development environment and project template for {role_name}.",
             "Confirm tooling builds cleanly and passes initial checks."),
            (f"Applied Domain Architecture for {role_name}",
             [f"Master core patterns, data structures, and architectural standards for {role_name}", f"Implement domain business logic"],
             f"Build a core functional component applying {role_name} architecture.",
             "Verify architectural separation of concerns and correctness."),
            (f"Hands-on Implementation Task for {role_name}",
             [f"Apply practical problem-solving to realistic {role_name} tasks", f"Handle edge cases and data validation"],
             f"Implement a hands-on practical assignment reflecting real-world {role_name} responsibilities.",
             "Validate edge cases and confirm adherence to requirements."),
            (f"Mid-Term Practical Milestone Project for {role_name}",
             [f"Deliver a standalone working module demonstrating {role_name} competence", f"Conduct a self-review of code quality and structure"],
             f"Build and document a standalone milestone project tailored to {role_name}.",
             "Ensure all milestone project criteria are satisfied."),
            (f"Advanced System Integration & Design for {role_name}",
             [f"Integrate complex subsystems and external services for {role_name}", f"Apply resilience and error recovery patterns"],
             f"Build a multi-service integration demonstrating {role_name} systems thinking.",
             "Verify error recovery and robust communication across services."),
            (f"Testing, Security & Quality Standards for {role_name}",
             [f"Implement automated test suites and security best practices for {role_name}", f"Audit code against vulnerability benchmarks"],
             f"Write automated tests and conduct a security review for a {role_name} deliverable.",
             "Confirm all automated tests pass and zero security flags remain."),
            (f"Production-Grade Deliverable for {role_name}",
             [f"Assemble an end-to-end production deliverable for {role_name}", f"Implement logging, metrics, and documentation"],
             f"Deliver a production-ready application meeting professional {role_name} standards.",
             "Inspect logs, verify deployment configuration, and run acceptance tests."),
            (f"Technical Knowledge Assessment & Code Review for {role_name}",
             [f"Evaluate domain knowledge through technical review questions", f"Participate in structured code evaluation"],
             f"Complete a comprehensive technical evaluation and code walkthrough for {role_name}.",
             "Document feedback and demonstrate understanding of core decisions."),
            (f"Scalability & Performance Best Practices for {role_name}",
             [f"Analyze bottlenecks and optimize performance in {role_name} systems", f"Design for scale, caching, and concurrency"],
             f"Conduct a performance benchmark and implement optimizations for {role_name}.",
             "Demonstrate measurable throughput improvements."),
            (f"Industry Case Study & System Architecture for {role_name}",
             [f"Analyze real-world industry case studies relevant to {role_name}", f"Synthesize architectural tradeoffs"],
             f"Produce an architectural design document addressing a complex {role_name} scenario.",
             "Defend architectural choices against constraints."),
            (f"Mock Technical Interview & Problem Solving for {role_name}",
             [f"Practice live coding and technical problem solving expected in {role_name} interviews", f"Articulate trade-offs clearly"],
             f"Complete a mock technical interview session solving domain-specific challenges for {role_name}.",
             "Evaluate problem-solving clarity and accuracy against rubric."),
            (f"Viva Practice: System Design & Conceptual Defense for {role_name}",
             [f"Prepare for oral viva and deep conceptual defense of {role_name} topics", f"Explain fundamental design decisions and trade-offs"],
             f"Conduct a mock viva examination defending system choices and theoretical foundations.",
             "Provide structured, clear answers to core domain questions."),
            (f"Comprehensive Capstone & Career Portfolio for {role_name}",
             [f"Finalize a comprehensive capstone project demonstrating ready-to-hire {role_name} mastery", f"Package professional portfolio"],
             f"Publish and document a complete capstone project tailored for {role_name} job applications.",
             "Verify capstone repository is fully documented, tested, and demo-ready.")
        ]
        assigned_skill_id = _canonical_id(role_name)

    phase2_aptitude = (
        f"Company Recruitment & Aptitude Preparation for {role_name}",
        [
            "Quantitative Aptitude, Numerical Analysis & Data Interpretation",
            "Logical & Analytical Reasoning Problem Solving",
            "Verbal Ability & Professional Workplace Communication",
            "Company-Specific Recruitment Round Patterns & Online Test Tactics"
        ],
        f"Complete 30 timed aptitude practice questions covering numerical calculations, logical deduction, and verbal reasoning relevant to {role_name} hiring filters.",
        "Attain >= 75% accuracy across standardized company recruitment test patterns."
    )
    phase3_mock_interview = (
        f"Mock Technical Interview & Practical Simulation for {role_name}",
        [
            f"{role_name} Technical & System Architecture Deep Dive Scenarios",
            "Live Technical Problem Solving & Whiteboard Conceptual Defense",
            "Behavioral Interview Frameworks (STAR Method) & Cultural Alignment",
            "Production Deliverable Review & Model Answer Analysis"
        ],
        f"Participate in a complete role simulation: solve a practical {role_name} challenge under interview conditions and record structured defense.",
        "Demonstrate technical proficiency, architectural sound judgment, and structured professional communication."
    )

    core_count = max(2, target_count - 2)
    if norm_level == "advanced":
        start_idx = min(3, max(0, len(role_plan) - core_count))
        core_stages = role_plan[start_idx:start_idx + core_count]
    elif norm_level == "intermediate":
        start_idx = min(1, max(0, len(role_plan) - core_count))
        core_stages = role_plan[start_idx:start_idx + core_count]
    else:
        core_stages = role_plan[:core_count]

    selected = list(core_stages) + [phase2_aptitude, phase3_mock_interview]

    specs = []
    clean_role = role_name.casefold().replace(" ", "-")
    starting_level_source = "user_provided" if level_source == "user_provided" else ("self_reported_onboarding" if level else None)
    for idx, (title, objs, task, crit) in enumerate(selected, start=1):
        try:
            stage_res, stage_note = _resource_rows(assigned_skill_id, [], milestone_title=title, skill_name=role_name)
        except TypeError:
            stage_res, stage_note = [], None
        specs.append({
            "identity": f"role:{clean_role}:stage-{idx}",
            "name": title,
            "skill_name": role_name,
            "skill_id": assigned_skill_id,
            "source": "onet_role_association",
            "self_reported_level": level,
            "starting_level_source": starting_level_source,
            "explanation": f"Practice guidance: Career preparation module {idx} for {role_name}: {title.lower()}.",
            "learning_objectives": objs,
            "practice_activity": task,
            "completion_criterion": crit,
            "relation_note": f"Stage {idx} of {len(selected)} in your {duration_days}-day career roadmap for {role_name} ({norm_level.capitalize() or 'Beginner'} track).",
            "resources": stage_res,
            "resource_note": stage_note or "Role-specific practice and project tasks are structured for practical career readiness.",
            "is_stage": True,
        })
    return specs


def build_personalized_roadmap(profile_response, *, assessment_evidence: dict[str, dict[str, Any]] | None = None, reference_store=None) -> PersonalizedRoadmap:
    profile, raw_skills, levels, target_role, goals, preferences, weekly_time, onboarding_complete, interests, experience, study_field, location = _profile_values(profile_response)
    if reference_store is None:
        taxonomy, reference_id, resolved_role, references, relationship_note = _taxonomy_context(target_role)
    else:
        taxonomy, reference_id, resolved_role, references, relationship_note = _taxonomy_context_from_store(target_role, reference_store)

    normalized_skills = []
    seen_skill_ids: set[str] = set()
    for raw in raw_skills:
        normalized = normalize_skill_entry(raw)
        identity = normalized.canonical_skill_id or f"manual:{normalized.display_name.casefold()}"
        if not normalized.display_name or identity in seen_skill_ids:
            continue
        seen_skill_ids.add(identity)
        level_key = normalized.canonical_skill_id or normalized.display_name.casefold()
        normalized_skills.append({
            "skill_id": normalized.canonical_skill_id,
            "name": normalized.canonical_name,
            "declared_name": raw,
            "mapping_status": "canonical" if normalized.is_known else "manual",
            "level": levels.get(level_key),
            "level_source": "user_provided" if raw in (profile.get("_learning_plan_user_level_overrides") if isinstance(profile.get("_learning_plan_user_level_overrides"), list) else []) else "self_reported" if levels.get(level_key) else "not_reported",
            "user_selected": raw in (profile.get("_learning_plan_user_selected_skills") if isinstance(profile.get("_learning_plan_user_selected_skills"), list) else []),
        })

    missing_rows: list[dict[str, Any]] = []
    resolved_label = resolved_role or target_role
    if references and raw_skills:
        gap = calculate_skill_gap(
            taxonomy=taxonomy or "onet",
            occupation={"label": resolved_label, "taxonomy_id": reference_id},
            reference_skills=references,
            user_skills=raw_skills,
        )
        missing_rows = gap.get("missing") or []
    elif references:
        missing_rows = [{
            "label": row.get("label"), "taxonomy": taxonomy,
            "taxonomy_id": row.get("skill_uri") or row.get("element_id") or row.get("id"),
            "source": row.get("source"), "classification": row.get("relation_type"),
            "priority_rationale": "Associated with this occupation in the selected local taxonomy; not a verified qualification gap.",
        } for row in references]

    generated_templates = build_learning_roadmap({
        "occupation": {"label": resolved_label or "your learning goal"},
        "missing": missing_rows,
    }, limit=_MAX_MILESTONES)
    template_by_identity = {str(row.get("taxonomy_id")): row for row in generated_templates["steps"]}
    evidence_map = assessment_evidence or {}
    milestone_specs: list[dict[str, Any]] = []
    learning_plan_type = profile.get("_learning_plan_type")
    duration_days = int(profile.get("_learning_plan_target_duration_days") or 30)

    if learning_plan_type == "skill" and len(normalized_skills) == 1:
        focus = normalized_skills[0]
        milestone_specs = _generate_adaptive_skill_milestones(
            focus["name"], focus["skill_id"], focus["level"], duration_days, level_source=focus.get("level_source")
        )
    elif learning_plan_type == "role" and target_role:
        role_lower = target_role.strip().casefold()
        is_known = bool(references) or any(
            t in role_lower for t in [
                "ui/ux", "ux designer", "ui designer", "product design", "designer",
                "software", "developer", "engineer", "scientist", "architect",
                "analyst", "product manager", "manager", "devops", "cloud",
                "cybersecurity", "security"
            ]
        ) and "imaginary" not in role_lower
        if is_known:
            milestone_specs = _generate_adaptive_role_milestones(
                target_role, levels.get(target_role.casefold()), duration_days, level_source="user_provided"
            )
        else:
            milestone_specs = []
    else:
        for skill in normalized_skills:
            skill_id = skill["skill_id"]
            goal_context = None
            if learning_plan_type in {"role", "combined"}:
                goal_context = "; ".join(([resolved_label] if resolved_label else []) + ([goals[0]] if goals else [])) or None
            task, outcome, criterion = _practice_for_skill(skill["name"], goal_context)
            milestone_specs.append({
                "identity": f"profile:{skill_id or skill['name'].casefold()}",
                "name": skill["name"], "skill_id": skill_id,
                "source": "user_selected" if skill.get("user_selected") else "onboarding_self_report" if skill_id else "manual_profile_skill",
                "self_reported_level": skill["level"],
                "starting_level_source": "user_provided" if skill.get("level_source") == "user_provided" else "self_reported_onboarding" if skill["level"] else None,
                "explanation": f"Build practical ability in {skill['name']}.",
                "learning_objectives": [
                    f"Learn foundational {skill['name']} concepts",
                    f"Apply {skill['name']} in a short exercise",
                    "Review your work against the practice criteria",
                ],
                "practice_activity": task,
                "completion_criterion": f"{criterion} Expected artifact: {outcome}",
                "relation_note": ("Added in plan setup; level remains user-provided." if skill.get("user_selected") else "Listed in your onboarding profile; level remains self-reported.") if skill["level"] else ("Added in plan setup; no starting level was provided." if skill.get("user_selected") else "Listed in your onboarding profile; no level was provided."),
            })
        for row in missing_rows:
            label = str(row.get("label") or "").strip()
            if not label:
                continue
            canonical = normalize_skill_entry(label)
            identity = f"profile:{canonical.canonical_skill_id}" if canonical.canonical_skill_id else f"taxonomy:{row.get('taxonomy_id')}"
            if identity in {item["identity"] for item in milestone_specs}:
                continue
            template = template_by_identity.get(str(row.get("taxonomy_id")), {})
            classification = row.get("classification")
            relation_source = "esco_role_association" if taxonomy == "esco" else "onet_role_association"
            explanation = template.get("suggested_task") or f"Try a small practice task for {label}; this is a platform-generated suggestion linked to the selected role reference."
            criterion = template.get("self_check_criterion") or f"Compare your work with the task requirements and record what you checked."
            rationale = row.get("priority_rationale") or "Associated with this role in the local reference taxonomy; not a verified skill gap."
            rationale = rationale.replace(
                "listed as an unranked reference gap",
                "shown as an unranked role association",
            )
            if "not a verified qualification gap" not in rationale.casefold():
                rationale = f"{rationale.rstrip('.')}; this is not a verified qualification gap."
            milestone_specs.append({
                "identity": identity, "name": canonical.canonical_name if canonical.is_known else label,
                "skill_id": canonical.canonical_skill_id, "source": relation_source,
                "self_reported_level": None,
                "explanation": explanation,
                "learning_objectives": [
                    f"Understand the role-associated {label} skills",
                    f"Apply {label} in a practical task",
                ],
                "practice_activity": template.get("suggested_task") or f"Practice {label} in a short, role-relevant task.",
                "completion_criterion": criterion,
                "relation_note": f"{rationale} This relationship does not define a prerequisite or proficiency level."
                             + (f" Source classification: {classification}." if classification in {"essential", "optional"} else ""),
                "taxonomy_id": row.get("taxonomy_id"),
            })
    if not milestone_specs and learning_plan_type != "role":
        if target_role and (bool(references) or "imaginary" not in target_role.casefold()):
            milestone_specs = _generate_adaptive_role_milestones(
                target_role, levels.get(target_role.casefold()), duration_days, level_source="user_provided"
            )
        elif normalized_skills:
            focus = normalized_skills[0]
            milestone_specs = _generate_adaptive_skill_milestones(
                focus["name"], focus["skill_id"], focus["level"], duration_days, level_source=focus.get("level_source")
            )
    milestone_specs = milestone_specs[:_MAX_MILESTONES]
    milestones = []
    for sequence, spec in enumerate(milestone_specs, start=1):
        skill_id = spec["skill_id"]
        is_stage = spec.get("is_stage", False)
        title = spec["name"] if is_stage else f"Practice {spec['name']}"
        skill_name = spec.get("skill_name") or spec["name"]
        resource_rows = spec.get("resources")
        resource_note = spec.get("resource_note")
        if resource_rows is None:
            try:
                resource_rows, resource_note = _resource_rows(skill_id, preferences, milestone_title=title, skill_name=skill_name)
            except TypeError:
                resource_rows, resource_note = _resource_rows(skill_id, preferences)
        milestones.append(RoadmapMilestone(
            milestone_id=f"milestone-{uuid.uuid5(uuid.NAMESPACE_URL, spec['identity']).hex[:16]}",
            sequence=sequence,
            title=title,
            explanation=spec["explanation"],
            learning_objectives=spec.get("learning_objectives", []),
            practice_activity=spec.get("practice_activity"),
            skill_id=skill_id,
            skill_name=skill_name,
            skill_source=spec["source"],
            self_reported_level=spec["self_reported_level"],
            starting_level_source=spec.get("starting_level_source"),
            assessment_evidence=evidence_map.get(skill_id, {
                "status": "not_available", "proficiency_verified": False,
                "note": "No valid completed assessment evidence was available when this roadmap was generated.",
            }) if skill_id else {"status": "not_available", "proficiency_verified": False},
            relation_note=spec["relation_note"],
            resources=[RoadmapResource(**item) for item in resource_rows],
            resource_note=resource_note,
            effort={
                "estimated_minutes": None,
                "basis": "No source-based duration is recorded for this task or resource; effort is not estimated.",
                "weekly_learning_time": weekly_time,
            },
            completion_criterion=spec["completion_criterion"],
        ))

    if not milestones and not target_role:
        raise HTTPException(status_code=422, detail="Add a declared skill or an exact target role with local reference data before creating a roadmap.")
    career_title = resolved_label or (goals[0] if goals else "your learning goals")
    generated = _now()
    evidence_note = (
        "Assessment evidence is provisional and is included only when a valid completed attempt exists."
        if evidence_map else "No valid completed assessment evidence was found; all onboarding levels remain self-reported."
    )
    context = RoadmapProfileContext(
        target_role=target_role,
        career_goals=goals,
        interests=interests,
        learning_preferences=preferences,
        weekly_learning_time=weekly_time,
        experience=experience if isinstance(experience, str) else None,
        study_field=study_field if isinstance(study_field, str) else None,
        location=location,
        work_preference=(profile.get("work_preferences", {}).get("work_preference") if isinstance(profile.get("work_preferences"), dict) else None),
        skills=normalized_skills,
        onboarding_complete=onboarding_complete,
        evidence_note=evidence_note,
    )
    return PersonalizedRoadmap(
        roadmap_id=str(uuid.uuid4()),
        title=f"Initial learning roadmap for {career_title}",
        summary=(
            "No matching O*NET or ESCO role record was found. This preview includes no role skills or learning chapters until a supported mapping is available."
            if target_role and not milestones else
            "A first-pass learning plan based on saved onboarding information and exact local role references where available. "
            "The sequence is exploratory; no prerequisites, proficiency levels, or completion times are inferred."
        ),
        generated_at=generated,
        updated_at=generated,
        profile_context=context,
        taxonomy_source=("ref_onet_essential_skills" if taxonomy == "onet" else "ref_esco_occupation_skill_relations" if taxonomy == "esco" else None),
        taxonomy_reference_id=reference_id,
        relationship_note=relationship_note,
        prerequisites_available=False,
        assessment_evidence_status="available_provisional" if evidence_map else "not_available",
        milestones=milestones,
        completed_count=0,
    )


def _taxonomy_context_from_store(target_role: str | None, store):
    if not target_role:
        return None, None, None, None, "No target role is saved; this plan uses only declared onboarding skills."
    onet_matches = store.get_onet_occupations(title=target_role, limit=100)
    exact_onet = [item for item in onet_matches if item.title.strip().casefold() == target_role.casefold()]
    if len(exact_onet) == 1:
        occupation = exact_onet[0]
        rows = store.get_onet_essential_skills_by_occupation(occupation.soc_code, limit=500)
        references = [{**row, "label": row.get("element_name"), "source": "ref_onet_essential_skills"} for row in rows]
        if references:
            return "onet", occupation.soc_code, occupation.title, references, "O*NET role-associated skill relationships are context, not required qualifications or prerequisite order."
    esco_matches = store.get_esco_occupations(query=target_role, limit=20)
    exact_esco = [row for row in esco_matches if str(row.get("preferred_label", "")).strip().casefold() == target_role.casefold()]
    if len(exact_esco) == 1:
        occupation = exact_esco[0]
        rows = store.get_esco_occupation_skills(occupation["concept_uri"], limit=500)
        references = [{**row, "label": row.get("preferred_label") or row.get("relation_skill_label"), "source": "ref_esco_occupation_skill_relations"} for row in rows]
        if references:
            return "esco", occupation["concept_uri"], occupation["preferred_label"], references, "ESCO relation labels are not proficiency levels or prerequisite order."
    return None, None, target_role, None, "No exact O*NET or ESCO occupation match was found; no role relationship was inferred."


def _practice_for_skill(skill: str, role: str | None) -> tuple[str, str, str]:
    if not role:
        return (
            f"Complete a short {skill} exercise using a small, self-chosen practice brief.",
            f"A small artifact that demonstrates one practical use of {skill}.",
            f"Check the artifact against the brief and note one thing you would improve in {skill}.",
        )
    result = build_learning_roadmap({
        "occupation": {"label": role},
        "missing": [{"label": skill, "taxonomy": None, "taxonomy_id": skill, "classification": None}],
    }, limit=1)
    step = result["steps"][0]
    return step["suggested_task"], step["tangible_outcome"], step["self_check_criterion"]


def get_personalized_roadmap(uid: str) -> RoadmapStateResponse:
    return RoadmapStateResponse(roadmap=_saved_roadmap(uid))


def generate_personalized_roadmap(uid: str) -> RoadmapStateResponse:
    existing = _saved_roadmap(uid)
    if existing:
        return RoadmapStateResponse(roadmap=existing, created=False)
    try:
        profile = get_individual_profile(uid)
        evidence, evidence_read_ok = _assessment_evidence(uid)
        roadmap = build_personalized_roadmap(profile, assessment_evidence=evidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="A personalized roadmap could not be generated from the available profile and reference data.") from exc
    if not evidence_read_ok:
        roadmap.assessment_evidence_status = "unknown"
        roadmap.profile_context.evidence_note = "Assessment history could not be checked; no assessment evidence was applied. Onboarding levels remain self-reported."
        for milestone in roadmap.milestones:
            milestone.assessment_evidence = {
                "status": "unknown", "proficiency_verified": False,
                "note": "Assessment history could not be checked; evidence status is unknown.",
            }
    try:
        _roadmap_ref(uid).create(_roadmap_firestore_data(roadmap))
        return RoadmapStateResponse(roadmap=roadmap, created=True)
    except Exception as exc:
        # Concurrent repeat generation returns the already-created document without replacing it.
        created_after_race = _saved_roadmap(uid)
        if created_after_race:
            return RoadmapStateResponse(roadmap=created_after_race, created=False)
        raise HTTPException(status_code=503, detail="The generated roadmap could not be saved. No saved roadmap was changed.") from exc


def update_milestone_progress(uid: str, milestone_id: str, update: MilestoneProgressUpdate) -> RoadmapStateResponse:
    if not milestone_id or len(milestone_id) > 100:
        raise HTTPException(status_code=422, detail="Invalid milestone ID.")
    try:
        client = get_firestore_client()
        ref = client.collection("users").document(uid).collection(_ROADMAP_COLLECTION).document(_ROADMAP_DOCUMENT)
        transaction = client.transaction()

        @firestore.transactional
        def commit(tx):
            snapshot = ref.get(transaction=tx)
            if not snapshot.exists:
                raise HTTPException(status_code=404, detail="No saved learning roadmap was found.")
            roadmap = PersonalizedRoadmap.model_validate(snapshot.to_dict())

            target_idx = None
            for idx, milestone in enumerate(roadmap.milestones):
                if milestone.milestone_id == milestone_id:
                    target_idx = idx
                    break
            if target_idx is None:
                raise HTTPException(status_code=404, detail="Milestone was not found in this roadmap.")

            target_milestone = roadmap.milestones[target_idx]

            # Idempotency: If already in requested status, return existing roadmap without failing or double-counting
            if update.status == target_milestone.status:
                return roadmap

            # Server-enforced prerequisite verification:
            # All milestones preceding target_idx must be completed before advancing or completing this milestone.
            if update.status in ("completed", "in_progress"):
                for prior_idx in range(target_idx):
                    if roadmap.milestones[prior_idx].status != "completed":
                        raise HTTPException(
                            status_code=409,
                            detail="Complete previous milestones before advancing this one."
                        )

            # Assessment gating verification (when completing):
            if update.status == "completed" and target_milestone.skill_id:
                try:
                    from app.services.assessment_service import list_assessment_summaries
                    summaries = list_assessment_summaries(target_milestone.skill_id)
                except Exception:
                    summaries = []

                if summaries and any(s.question_count > 0 for s in summaries):
                    attempts_collection = client.collection("users").document(uid).collection(_ASSESSMENT_COLLECTION)
                    passed = False
                    try:
                        attempts = list(attempts_collection.stream())
                        for attempt_doc in attempts:
                            data = attempt_doc.to_dict() or {}
                            if data.get("skill_id") == target_milestone.skill_id and data.get("status") == "completed":
                                pct = data.get("percentage")
                                if pct is not None and pct >= 70:
                                    passed = True
                                    break
                    except Exception:
                        passed = False

                    if not passed:
                        raise HTTPException(
                            status_code=409,
                            detail=f"A server-scored assessment score of at least 70% is required for {target_milestone.skill_name} before completing this milestone."
                        )

            target_milestone.status = update.status
            if update.status == "completed":
                target_milestone.completion_source = "user_attested"
                target_milestone.completed_at = _now()
                # Automatically advance the immediately following milestone to in_progress if not_started
                if target_idx + 1 < len(roadmap.milestones):
                    next_milestone = roadmap.milestones[target_idx + 1]
                    if next_milestone.status == "not_started":
                        next_milestone.status = "in_progress"
            elif update.status == "not_started":
                target_milestone.completion_source = None
                target_milestone.completed_at = None

            roadmap.completed_count = sum(item.status == "completed" for item in roadmap.milestones)
            roadmap.updated_at = _now()
            tx.set(ref, _roadmap_firestore_data(roadmap))
            return roadmap

        roadmap = commit(transaction)
        return RoadmapStateResponse(roadmap=roadmap, created=False)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Milestone progress could not be saved. Your last saved progress remains unchanged.") from exc


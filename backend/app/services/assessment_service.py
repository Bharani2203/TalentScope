from __future__ import annotations

import hashlib
import json
import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from firebase_admin import firestore

from app.analytics.skill_registry import BY_ID, SKILLS, canonical_skill_id
from app.core.firebase import get_firestore_client
from app.models.assessment import (
    AssessmentAttemptStarted, AssessmentHistory, AssessmentHistoryItem,
    AssessmentQuestion, AssessmentResult, AssessmentSummary, PublicOption,
    AssessmentReviewItem, AssessmentReviewQueue, AssessmentReviewResult,
    AssessmentRestrictionStatus, AssessmentSuspiciousEventRequest,
)

_BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "question_bank" / "questions_public.json"
_KEYS_PATH = _BANK_PATH.parent / "private" / "answer_keys.json"
_SCORING_POLICY_PATH = _BANK_PATH.parent / "scoring_policy.json"
_MAX_QUESTIONS = 30
_ATTEMPT_COLLECTION = "learning_assessment_attempts"
_REVIEW_COLLECTION = "learning_assessment_reviews"
_REVIEW_AUDIT_COLLECTION = "learning_assessment_review_audit"
_STRIKES_COLLECTION = "assessment_strikes"
_SECURITY_DOCUMENT = "assessment_security"
_STRIKE_THRESHOLD = 3
_RESTRICTION_HOURS = 24
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MINIMUM_ROADMAP_ASSESSMENT_SCORE = 70


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Assessment data is temporarily unavailable.") from exc


@lru_cache(maxsize=1)
def _skill_names() -> dict[str, str]:
    return {skill.skill_id: skill.name for skill in SKILLS}


def _canonical_skill(value: str) -> str | None:
    cleaned = value.strip()
    if cleaned in BY_ID:
        return cleaned
    return canonical_skill_id(cleaned)


def _approval_record(row: dict[str, Any]) -> bool:
    """Only human review records with reviewer and timestamp can activate content."""
    approval = row.get("review")
    if not isinstance(approval, dict):
        return False
    reviewer = approval.get("reviewer_id")
    approved_at = approval.get("approved_at")
    return (
        approval.get("status") == "approved"
        and isinstance(reviewer, str) and bool(reviewer.strip())
        and isinstance(approved_at, str) and bool(approved_at.strip())
        and row.get("verification_status") != "rejected"
    )


def _matching_review_pair(question: dict[str, Any], answer: dict[str, Any]) -> bool:
    question_review, answer_review = question.get("review"), answer.get("review")
    if isinstance(question_review, dict) or isinstance(answer_review, dict):
        return bool(
            _approval_record(question) and _approval_record(answer)
            and question_review.get("reviewer_id") == answer_review.get("reviewer_id")
            and question_review.get("approved_at") == answer_review.get("approved_at")
            and question_review.get("content_version") == answer_review.get("content_version") == _content_version(question, answer)
        )
    try:
        snapshot = get_firestore_client().collection(_REVIEW_COLLECTION).document(question.get("question_id", "")).get()
        review = snapshot.to_dict() if snapshot.exists else None
    except Exception:
        return False
    if not isinstance(review, dict):
        return False
    reviewed_at = review.get("reviewed_at")
    return bool(
        review.get("decision") == "approved"
        and isinstance(review.get("reviewer_uid"), str) and review["reviewer_uid"].strip()
        and isinstance(reviewed_at, (datetime, str))
        and review.get("content_version") == _content_version(question, answer)
    )


def _approved_scoring_policy() -> dict[str, Any] | None:
    """No assessment goes live until a reviewed, versioned policy is configured."""
    try:
        policy = json.loads(_SCORING_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(policy, dict):
        return None
    minimum_pool = policy.get("minimum_questions_per_skill_difficulty")
    if (
        policy.get("status") != "approved"
        or not isinstance(policy.get("reviewer_uid"), str) or not policy["reviewer_uid"].strip()
        or not isinstance(policy.get("reviewed_at"), str) or not policy["reviewed_at"].strip()
        or not isinstance(policy.get("policy_version"), str) or not policy["policy_version"].strip()
        or policy.get("score_interpretation") != "provisional_only"
        or not isinstance(minimum_pool, int) or isinstance(minimum_pool, bool) or not 1 <= minimum_pool <= _MAX_QUESTIONS
    ):
        return None
    return policy


def _load_bank() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    questions = _read_json(_BANK_PATH)
    key_document = _read_json(_KEYS_PATH)
    if not isinstance(questions, list) or not isinstance(key_document, dict):
        raise HTTPException(status_code=503, detail="Assessment data is temporarily unavailable.")
    key_rows = key_document.get("answers")
    if not isinstance(key_rows, list):
        raise HTTPException(status_code=503, detail="Assessment data is temporarily unavailable.")
    keys = {row.get("question_id"): row for row in key_rows if isinstance(row, dict) and isinstance(row.get("question_id"), str)}
    digest = hashlib.sha256(
        json.dumps([questions, key_document], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return questions, keys, digest


def _content_version(question: dict[str, Any], answer: dict[str, Any]) -> str:
    source_rows = [
        {key: value for key, value in row.items() if key not in {"review", "verification_status"}}
        for row in (question, answer)
    ]
    payload = json.dumps(source_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def list_admin_review_queue() -> AssessmentReviewQueue:
    """Expose private review material only through the admin-guarded route."""
    questions, keys, _ = _load_bank()
    db = get_firestore_client()
    items: list[AssessmentReviewItem] = []
    try:
        for question in questions:
            if not isinstance(question, dict) or not isinstance(question.get("question_id"), str):
                continue
            answer = keys.get(question["question_id"])
            if not isinstance(answer, dict):
                continue
            version = _content_version(question, answer)
            snapshot = db.collection(_REVIEW_COLLECTION).document(question["question_id"]).get()
            previous = snapshot.to_dict() if snapshot.exists else None
            is_current = isinstance(previous, dict) and previous.get("content_version") == version
            status = previous.get("decision") if is_current else "re-review required" if previous else "draft_unreviewed"
            if status not in {"draft_unreviewed", "re-review required"}:
                continue
            items.append(AssessmentReviewItem(
                question_id=question["question_id"], question=question,
                private_answer_record=answer, status=status,
                content_version=version, previous_review=previous,
            ))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The assessment review queue is temporarily unavailable.") from exc
    return AssessmentReviewQueue(items=items, count=len(items))


def review_assessment_question(question_id: str, decision: str, reason: str, reviewer_uid: str) -> AssessmentReviewResult:
    if not _ID.fullmatch(question_id):
        raise HTTPException(status_code=422, detail="Invalid question ID.")
    questions, keys, _ = _load_bank()
    question = next((row for row in questions if isinstance(row, dict) and row.get("question_id") == question_id), None)
    answer = keys.get(question_id)
    if not question or not isinstance(answer, dict):
        raise HTTPException(status_code=404, detail="Question or private answer record was not found.")
    version = _content_version(question, answer)
    now = datetime.now(timezone.utc)
    record = {
        "question_id": question_id, "decision": decision, "reason": reason.strip(),
        "reviewer_uid": reviewer_uid, "reviewed_at": now,
        "content_version": version,
    }
    try:
        db = get_firestore_client()
        batch = db.batch()
        batch.set(db.collection(_REVIEW_COLLECTION).document(question_id), record)
        batch.set(db.collection(_REVIEW_AUDIT_COLLECTION).document(str(uuid.uuid4())), record)
        batch.commit()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The review decision could not be saved.") from exc
    is_live_eligible = decision == "approved" and any(
        row[0].get("question_id") == question_id for row in _eligible_pairs()
    )
    return AssessmentReviewResult(
        question_id=question_id, decision=decision, reviewer_uid=reviewer_uid,
        reviewed_at=now, content_version=version, live_eligible=is_live_eligible,
        message=("Review saved. This question meets the approved policy and reviewed-pool requirements."
                 if is_live_eligible else
                 "Review saved. This question remains excluded until the approved scoring policy and per-skill/per-difficulty reviewed-pool requirements are met."),
    )


def _objective_points(question: dict[str, Any], key: dict[str, Any]) -> int | None:
    kind = question.get("question_type")
    if kind == "mcq":
        options = question.get("options")
        correct = key.get("correct_answer")
        option_rows = options if isinstance(options, list) else []
        option_ids = [option.get("option_id") for option in option_rows if isinstance(option, dict) and isinstance(option.get("text"), str) and option["text"].strip()]
        if len(option_ids) < 2 or len(option_ids) != len(set(option_ids)) or not isinstance(correct, str) or correct not in option_ids:
            return None
        rubric = key.get("scoring_rubric")
        points = [item.get("points") for item in rubric if isinstance(item, dict)] if isinstance(rubric, list) else []
        if not points or not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in points):
            return None
        total = sum(points)
        return total if total <= 100 else None
    if kind == "scenario":
        accepted = key.get("accepted_answers")
        if not isinstance(accepted, list) or not accepted or not all(isinstance(item, str) for item in accepted):
            return None
        points = key.get("objective_points")
        return points if isinstance(points, int) and 1 <= points <= 100 else None
    return None


def _eligible_pairs(skill_id: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any], int]]:
    policy = _approved_scoring_policy()
    if policy is None:
        return []
    questions, keys, _ = _load_bank()
    eligible = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_id = question.get("question_id")
        key = keys.get(question_id)
        if not isinstance(key, dict) or not _matching_review_pair(question, key):
            continue
        question_skills = question.get("skill_ids")
        if not isinstance(question_skills, list) or not question_skills:
            continue
        canonical_skills = [_canonical_skill(value) for value in question_skills if isinstance(value, str)]
        if len(canonical_skills) != len(question_skills) or any(value is None for value in canonical_skills) or len(canonical_skills) != 1:
            continue
        if (
            not isinstance(question.get("question_text"), str) or not question["question_text"].strip()
            or question.get("difficulty") not in {"beginner", "intermediate", "advanced"}
            or not isinstance(question.get("topic_ids", []), list)
        ):
            continue
        canonical = canonical_skills[0]
        if skill_id and canonical != skill_id:
            continue
        points = _objective_points(question, key)
        if points is None or question.get("question_type") not in {"mcq", "scenario"}:
            continue
        eligible.append((question, key, points))
    minimum_pool = policy["minimum_questions_per_skill_difficulty"]
    counts: dict[tuple[str, str], int] = {}
    for question, _, _ in eligible:
        key = (_canonical_skill(question["skill_ids"][0]), question["difficulty"])
        counts[key] = counts.get(key, 0) + 1
    return [pair for pair in eligible if counts.get(
        (_canonical_skill(pair[0]["skill_ids"][0]), pair[0]["difficulty"]), 0
    ) >= minimum_pool]


def list_assessment_summaries(skill_id: str | None = None) -> list[AssessmentSummary]:
    canonical = _canonical_skill(skill_id) if skill_id else None
    if skill_id and canonical is None:
        raise HTTPException(status_code=422, detail="Unknown skill ID.")
    counts: dict[str, set[str]] = {}
    for question, _, _ in _eligible_pairs(canonical):
        skill = _canonical_skill(question["skill_ids"][0])
        counts.setdefault(skill, set()).add(question["question_type"])
    questions_by_skill: dict[str, int] = {}
    for question, _, _ in _eligible_pairs(canonical):
        skill = _canonical_skill(question["skill_ids"][0])
        questions_by_skill[skill] = questions_by_skill.get(skill, 0) + 1
    return [AssessmentSummary(skill_id=skill, skill_name=_skill_names()[skill], question_count=count, supported_types=sorted(counts[skill]))
            for skill, count in sorted(questions_by_skill.items())]


def _public_question(question: dict[str, Any], points: int) -> AssessmentQuestion:
    kind = question["question_type"]
    options = None
    if kind == "mcq":
        options = [PublicOption(option_id=row["option_id"], text=row["text"]) for row in question.get("options", [])]
    return AssessmentQuestion(
        question_id=question["question_id"],
        skill_ids=[_canonical_skill(skill) for skill in question["skill_ids"]],
        topic_ids=[topic for topic in question.get("topic_ids", []) if isinstance(topic, str) and _ID.fullmatch(topic)],
        question_type=kind,
        difficulty=question["difficulty"],
        question_text=question["question_text"],
        options=options,
        max_points=points,
    )


def _user_attempts(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_ATTEMPT_COLLECTION)


def _user_security_ref(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_SECURITY_DOCUMENT).document("status")


def _user_strikes_collection(uid: str):
    return get_firestore_client().collection("users").document(uid).collection(_STRIKES_COLLECTION)


def check_user_restriction(uid: str) -> AssessmentRestrictionStatus:
    try:
        snapshot = _user_security_ref(uid).get()
        data = snapshot.to_dict() if snapshot.exists else {}
    except Exception:
        return AssessmentRestrictionStatus(
            is_restricted=False,
            strike_count=0,
            active_strikes_remaining=_STRIKE_THRESHOLD,
        )

    strike_count = data.get("active_strike_count", 0)
    restriction_until = data.get("restriction_until")
    reason = data.get("restriction_reason")

    is_restricted = False
    now = datetime.now(timezone.utc)
    restriction_dt = None
    if restriction_until:
        if isinstance(restriction_until, str):
            try:
                restriction_dt = datetime.fromisoformat(restriction_until.replace("Z", "+00:00"))
            except ValueError:
                restriction_dt = None
        else:
            restriction_dt = restriction_until

        if restriction_dt and restriction_dt > now:
            is_restricted = True
        else:
            restriction_dt = None

    strikes_remaining = max(0, _STRIKE_THRESHOLD - strike_count) if not is_restricted else 0
    return AssessmentRestrictionStatus(
        is_restricted=is_restricted,
        strike_count=strike_count,
        restriction_until=restriction_dt if is_restricted else None,
        reason=reason if is_restricted else None,
        active_strikes_remaining=strikes_remaining,
    )


def record_suspicious_event(uid: str, event_type: str, attempt_id: str) -> AssessmentRestrictionStatus:
    now = datetime.now(timezone.utc)
    event_record = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "attempt_id": attempt_id,
        "recorded_at": now,
    }
    try:
        _user_strikes_collection(uid).document(event_record["event_id"]).set(event_record)
        sec_ref = _user_security_ref(uid)
        snap = sec_ref.get()
        sec_data = snap.to_dict() if snap.exists else {}
        current_strikes = sec_data.get("active_strike_count", 0) + 1
        update_data = {
            "active_strike_count": current_strikes,
            "last_strike_at": now,
            "last_event_type": event_type,
        }
        if current_strikes >= _STRIKE_THRESHOLD:
            until = now + timedelta(hours=_RESTRICTION_HOURS)
            update_data["restriction_until"] = until
            update_data["restriction_reason"] = (
                f"Assessment access is temporarily restricted for 24 hours due to multiple detected security policy violations ({event_type})."
            )
        sec_ref.set(update_data, merge=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not record security policy event.") from exc

    return check_user_restriction(uid)


def start_attempt(uid: str, skill_id: str, question_count: int = 10) -> AssessmentAttemptStarted:
    restriction = check_user_restriction(uid)
    if restriction.is_restricted:
        until_str = restriction.restriction_until.isoformat() if restriction.restriction_until else "24 hours"
        raise HTTPException(
            status_code=403,
            detail=f"Assessment access is temporarily restricted due to policy violations until {until_str}. {restriction.reason or ''}".strip(),
        )
    canonical = _canonical_skill(skill_id)
    if canonical is None:
        raise HTTPException(status_code=422, detail="Unknown skill ID.")
    if not 1 <= question_count <= _MAX_QUESTIONS:
        raise HTTPException(status_code=422, detail=f"question_count must be between 1 and {_MAX_QUESTIONS}.")
    pairs = _eligible_pairs(canonical)
    if not pairs:
        raise HTTPException(status_code=409, detail="No human-approved objective assessment questions are available for this skill.")
    selected = random.sample(pairs, min(question_count, len(pairs)))
    _, _, digest = _load_bank()
    now = datetime.now(timezone.utc)
    attempt_id = str(uuid.uuid4())
    try:
        _user_attempts(uid).document(attempt_id).create({
            "attempt_id": attempt_id,
            "skill_id": canonical,
            "status": "in_progress",
            "question_ids": [q["question_id"] for q, _, _ in selected],
            "question_bank_digest": digest,
            "started_at": now,
            "submitted_answers": {},
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Assessment attempt could not be saved. Please retry.") from exc
    return AssessmentAttemptStarted(
        attempt_id=attempt_id, skill_id=canonical, status="in_progress",
        question_count=len(selected), questions=[_public_question(q, p) for q, _, p in selected],
    )


def _normalize_answer(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def submit_attempt(uid: str, attempt_id: str, answers: dict[str, str]) -> AssessmentResult:
    if not _ID.fullmatch(attempt_id):
        # UUIDs are the only issued IDs; hyphens are accepted by this pattern.
        raise HTTPException(status_code=422, detail="Invalid attempt ID.")
    try:
        ref = _user_attempts(uid).document(attempt_id)
        snapshot = ref.get()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Assessment attempt storage is unavailable.") from exc
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Assessment attempt was not found.")
    attempt = snapshot.to_dict() or {}
    if attempt.get("status") != "in_progress":
        raise HTTPException(status_code=409, detail="This assessment attempt has already been submitted.")
    question_ids = attempt.get("question_ids")
    if not isinstance(question_ids, list) or set(answers) != set(question_ids):
        raise HTTPException(status_code=422, detail="Submit exactly one answer for every question in this attempt.")
    if any(not isinstance(value, str) or not value.strip() or len(value) > 10000 for value in answers.values()):
        raise HTTPException(status_code=422, detail="Each answer must be a non-empty string of at most 10000 characters.")
    questions, keys, digest = _load_bank()
    if digest != attempt.get("question_bank_digest"):
        raise HTTPException(status_code=409, detail="Assessment content changed; this attempt cannot be scored safely.")
    by_id = {row.get("question_id"): row for row in questions if isinstance(row, dict)}
    score = max_score = correct_count = 0
    for question_id in question_ids:
        question, key = by_id.get(question_id), keys.get(question_id)
        if not question or not key or not _matching_review_pair(question, key):
            raise HTTPException(status_code=409, detail="Assessment approval was withdrawn; this attempt cannot be scored.")
        points = _objective_points(question, key)
        if points is None:
            raise HTTPException(status_code=409, detail="Assessment scoring is unavailable for this question.")
        max_score += points
        answer = _normalize_answer(answers[question_id])
        if question["question_type"] == "mcq":
            option_ids = {option.get("option_id") for option in question.get("options", []) if isinstance(option, dict)}
            if answer not in option_ids:
                raise HTTPException(status_code=422, detail=f"Answer format is invalid for question {question_id}.")
            correct = answer == _normalize_answer(key["correct_answer"])
        else:
            correct = answer in {_normalize_answer(item) for item in key["accepted_answers"]}
        if correct:
            score += points
            correct_count += 1
    completed_at = datetime.now(timezone.utc)
    percentage = min(100, max(0, round(score * 100 / max_score))) if max_score else 0
    result = {
        "status": "completed", "score": score, "max_score": max_score,
        "percentage": percentage, "correct_count": correct_count,
        "question_count": len(question_ids), "completed_at": completed_at,
        "proficiency": "provisional",
        "submitted_answers": answers,
    }
    try:
        transaction = get_firestore_client().transaction()

        @firestore.transactional
        def commit(tx):
            current = ref.get(transaction=tx)
            if not current.exists or (current.to_dict() or {}).get("status") != "in_progress":
                raise HTTPException(status_code=409, detail="This assessment attempt has already been submitted.")
            tx.update(ref, result)

        commit(transaction)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Assessment result could not be saved; no result was recorded.") from exc
    return AssessmentResult(
        attempt_id=attempt_id, status="completed", skill_id=attempt["skill_id"],
        score=score, max_score=max_score, percentage=percentage,
        correct_count=correct_count, question_count=len(question_ids),
        proficiency=result["proficiency"], completed_at=completed_at,
    )


def list_attempt_history(uid: str, limit: int = 20) -> AssessmentHistory:
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50.")
    try:
        snapshots = list(_user_attempts(uid).order_by("started_at", direction="DESCENDING").limit(limit).stream())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Assessment history is temporarily unavailable.") from exc
    items = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        if data.get("status") not in {"in_progress", "completed"}:
            continue
        items.append(AssessmentHistoryItem(
            attempt_id=data.get("attempt_id", snapshot.id), skill_id=data.get("skill_id", ""),
            status=data["status"], question_count=len(data.get("question_ids", [])),
            score=data.get("score"), max_score=data.get("max_score"), percentage=data.get("percentage"),
            started_at=data["started_at"], completed_at=data.get("completed_at"),
        ))
    return AssessmentHistory(attempts=items, count=len(items))

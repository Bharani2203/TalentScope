"""Rule-based job clarification, slot filling, and scope classification."""

from __future__ import annotations

import re
from typing import Any


SLOT_NAMES = ("role", "location", "technology", "experience_level")
JOB_WORDS = re.compile(r"\b(?:jobs?|postings?|openings?|vacancies|positions|hiring)\b", re.I)
IN_SCOPE_WORDS = re.compile(
    r"\b(?:skill|technology|tech|developer|engineer|designer|analyst|job|posting|hiring|market|demand|adoption|salary|career|role|occupation|company|employer|trend|learn|learning|recommend\w*|suggest\w*|roadmap|practice|practise|study|evidence|python|excel|aws|react|sql|java|javascript|databricks|ai|ui/ux|ux|kubernetes|docker)\w*\b",
    re.I,
)
ROLE_TERMS = (
    "software developer", "software engineer", "frontend developer", "front-end developer",
    "backend developer", "back-end developer", "full stack developer", "data scientist",
    "data analyst", "data engineer", "machine learning engineer", "ui designer",
    "ux designer", "product designer", "designer", "developer", "engineer", "analyst",
    "devops", "product manager",
)
LOCATION_ALIASES = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru", "bengaluru-vtp": "Bengaluru",
    "new delhi": "Delhi", "delhi": "Delhi", "hyderabad": "Hyderabad",
    "mumbai": "Mumbai", "pune": "Pune", "chennai": "Chennai",
}


def classify_question(message: str, active_state: dict[str, Any] | None = None) -> str:
    text = (message or "").strip()
    if re.search(r"\b(?:weather|recipe|cooking|capital of|politics|election|football|basketball|movie review)\b", text, re.I):
        return "OFF-TOPIC"
    if active_state and active_state.get("active"):
        is_new_question = bool(re.search(r"\b(?:what|how|why|compare|trend|trends|demand|market|explain)\b", text, re.I))
        if len(text.split()) <= 8 and not is_new_question:
            return "FOLLOW-UP"
    technical_question = bool(re.search(
        r"\b(?:what is|explain|tell me about|how does|compare)\s+(?:the\s+)?[A-Za-z][A-Za-z0-9+#./-]+",
        text,
        re.I,
    ))
    if not IN_SCOPE_WORDS.search(text) and not technical_question:
        return "OFF-TOPIC"
    if JOB_WORDS.search(text) and not has_job_constraints(text):
        return "TOO BROAD"
    return "CLEAR"


def has_job_constraints(message: str) -> bool:
    role = extract_role(message)
    location = extract_location(message)
    technology = extract_technology(message, [])
    return bool((role and (location or technology)) or (location and technology))


def extract_role(message: str) -> str | None:
    folded = re.sub(r"\s+", " ", (message or "").strip()).casefold()
    for role in sorted(ROLE_TERMS, key=len, reverse=True):
        if role in folded:
            return role.title().replace("Ui", "UI").replace("Ux", "UX")
    before_jobs = re.search(r"\b(?:find|search|show|list|get)?\s*([a-z][a-z0-9+#./ -]{1,50}?)\s+(?:jobs?|postings?|openings?)\b", folded)
    if before_jobs:
        candidate = before_jobs.group(1).strip(" .")
        if candidate and candidate not in {"software", "tech", "technology", "all", "python", "excel", "aws", "react", "sql", "java", "javascript", "ai", "ui/ux"}:
            return candidate.title()
    return None


def extract_location(message: str) -> str | None:
    folded = (message or "").casefold()
    for alias, clean in sorted(LOCATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", folded):
            return clean
    match = re.search(r"\b(?:in|near|around|at)\s+([A-Z][A-Za-z .'-]{1,35})", message or "")
    return match.group(1).strip(" .") if match else None


def extract_technology(message: str, known_skills: list[str]) -> str | None:
    folded = (message or "").casefold()
    for skill in sorted(known_skills, key=len, reverse=True):
        name = str(skill or "").strip()
        if name and re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", folded):
            return name
    for term in ("python", "excel", "aws", "react", "sql", "java", "javascript", "databricks", "ai", "ui/ux"):
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", folded):
            return term.upper() if term in {"aws", "ai", "sql"} else term.title()
    return None


def extract_experience_level(message: str) -> str | None:
    folded = (message or "").casefold()
    for pattern, label in (
        (r"\b(?:entry[- ]level|junior|graduate|intern)\b", "Entry level"),
        (r"\bmid[- ]level\b", "Mid level"),
        (r"\b(?:senior|sr\.?|lead|principal)\b", "Senior"),
    ):
        if re.search(pattern, folded):
            return label
    return None


def merge_follow_up(
    state: dict[str, Any], reply: str, *, known_skills: list[str] | None = None,
) -> tuple[dict[str, Any], bool]:
    merged = {name: state.get("slots", {}).get(name) for name in SLOT_NAMES}
    text = (reply or "").strip()
    command = text.casefold().strip(" .!?,")
    if command in {"skip", "show everything", "show all", "everything", "all"}:
        return merged, True

    role = extract_role(text)
    location = extract_location(text)
    technology = extract_technology(text, known_skills or [])
    if role:
        merged["role"] = role
    if location:
        merged["location"] = location
    if technology:
        merged["technology"] = technology
    experience_level = extract_experience_level(text)
    if experience_level:
        merged["experience_level"] = experience_level
    if not any((role, location, technology)):
        pending = state.get("pending_slot")
        if pending == "role" and len(text.split()) <= 6:
            merged["role"] = text
        elif pending == "location" and len(text.split()) <= 5:
            # Allow a user-entered city that is absent from quick-reply options;
            # the subsequent stored-posting search will report no match honestly.
            merged["location"] = text
        elif pending == "technology" and len(text.split()) <= 5:
            merged["technology"] = text
    return merged, False


def missing_job_slot(slots: dict[str, Any]) -> str | None:
    if not slots.get("role"):
        return "role"
    if not slots.get("location") and not slots.get("technology"):
        return "location"
    return None


def next_clarification_round(round_count: int, missing_slot: str | None, escape_requested: bool) -> int | None:
    """Return the next prompt round, or None when the flow must answer now."""
    if not missing_slot or escape_requested or round_count >= 2:
        return None
    return round_count + 1


def clarification_question(slot: str, role: str | None) -> str:
    if slot == "location":
        subject = f" for {role}" if role else ""
        return f"Which location should I use{subject}?"
    if slot == "technology":
        subject = f" for {role}" if role else ""
        return f"Which skill or technology should I include{subject}?"
    return "Which job role should I search for?"


def quick_reply_options(slot: str, aggregate: dict[str, Any]) -> list[dict[str, str]]:
    if slot == "location":
        rows = aggregate.get("location_counts") or []
        options = [
            {"label": f"{row['location']} ({row['count']})", "value": row["location"]}
            for row in rows if row.get("location") and int(row.get("count") or 0) > 0
        ][:5]
    elif slot == "technology":
        rows = aggregate.get("skill_counts") or []
        options = [
            {"label": str(row["skill"]), "value": str(row["skill"])}
            for row in rows if row.get("skill")
        ][:5]
    else:
        rows = aggregate.get("title_counts") or []
        options = [
            {"label": str(row["title"]), "value": str(row["title"])}
            for row in rows if row.get("title")
        ][:5]
    return [*options, {"label": "Show everything", "value": "Show everything"}, {"label": "Skip", "value": "Skip"}]


def merged_search_query(slots: dict[str, Any]) -> str:
    role = str(slots.get("role") or "jobs").strip()
    technology = str(slots.get("technology") or "").strip()
    location = str(slots.get("location") or "").strip()
    parts = [role]
    if technology and technology.casefold() not in role.casefold():
        parts.append(technology)
    query = "Find " + " ".join(parts) + " jobs"
    if location:
        query += f" in {location}"
    return query

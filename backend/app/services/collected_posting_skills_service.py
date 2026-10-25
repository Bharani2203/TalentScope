"""Bounded, short-lived aggregate over collected India job postings."""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from datetime import datetime
from typing import Any

from google.cloud.firestore_v1 import FieldFilter

from app.core.firebase import get_firestore_client
from app.services.answer_verdict_rules import classify_posting_demand
from app.storage.firestore_read_guard import read_guard

_CACHE_TTL_SECONDS = 60
_QUERY_LIMIT = 500
_cache_lock = threading.RLock()
_cache: tuple[float, dict[str, Any]] | None = None

def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _skill_name(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("name") or value.get("skill")
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


_CITY_ALIASES = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru",
    "bengaluru-vtp": "Bengaluru", "new delhi": "Delhi",
}


def _cities_from_location(value: Any) -> list[str]:
    """Extract clean city names from stored posting location strings."""
    if not isinstance(value, str):
        return []
    cities: list[str] = []
    for segment in re.split(r"[;|]", value):
        candidate = segment.split(",", 1)[0].strip()
        if not candidate or candidate.casefold().startswith(("india", "remote", "hybrid")):
            continue
        clean = _CITY_ALIASES.get(candidate.casefold(), candidate)
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,40}", clean) and clean.casefold() not in {item.casefold() for item in cities}:
            cities.append(clean)
    return cities


def format_collected_postings_disclosure(n: int) -> str:
    return (
        f"This is a sample of {n} collected India postings, "
        "not a measure of hiring demand or the Indian market."
    )


def compute_posting_skill_aggregate(records: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Compute counts from jobs.skills_raw, counting each posting/skill pair once."""
    postings: dict[tuple[str, str], dict[str, Any]] = {}
    for document_id, record in records:
        if str(record.get("country_code") or "").casefold() not in {"in", "ind"} and str(record.get("country") or "").casefold() != "india":
            continue
        source = str(record.get("source") or "unknown").strip()
        provider_id = str(record.get("source_job_id") or record.get("job_id") or document_id)
        identity = (source.casefold(), provider_id)
        postings.setdefault(identity, record)

    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    companies_by_skill: dict[str, set[str]] = {}
    dates: list[Any] = []
    companies: set[str] = set()
    sources: set[str] = set()
    location_counts: Counter[str] = Counter()
    location_skill_counts: dict[str, Counter[str]] = {}
    title_counts: Counter[str] = Counter()
    for record in postings.values():
        source = str(record.get("source") or "unknown").strip()
        sources.add(source)
        company = str(record.get("company_name") or record.get("company") or "").strip()
        if company:
            companies.add(company.casefold())
        posted = _parse_date(record.get("posted_at"))
        if posted:
            dates.append(posted.date())
        raw_skills = record.get("skills_raw") or []
        cities = _cities_from_location(record.get("location") or record.get("city"))
        for city in cities:
            location_counts[city] += 1
        title = re.sub(r"\s+", " ", str(record.get("title") or "")).strip()
        if title:
            title_counts[title] += 1
        if isinstance(raw_skills, str):
            raw_skills = re.split(r"[,;|]", raw_skills)
        per_posting: dict[str, str] = {}
        for raw_skill in raw_skills if isinstance(raw_skills, (list, tuple, set)) else []:
            name = _skill_name(raw_skill)
            if name:
                per_posting.setdefault(name.casefold(), name)
        for normalized, display in per_posting.items():
            counts[normalized] += 1
            labels.setdefault(normalized, display)
            if record.get("company_name") or record.get("company"):
                companies_by_skill.setdefault(normalized, set()).add(
                    str(record.get("company_name") or record.get("company")).strip().casefold()
                )
            for city in cities:
                location_skill_counts.setdefault(city, Counter())[display] += 1

    skill_counts = []
    for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        company_count = len(companies_by_skill.get(key, set()))
        verdict = classify_posting_demand(count, len(postings), company_count)
        skill_counts.append({
            "skill": labels[key],
            "count": count,
            "company_count": company_count,
            "verdict": verdict["level"],
            "share": verdict["share"],
            "limited_evidence": verdict["limited_evidence"],
        })

    dated = sorted(dates)
    return {
        "n": len(postings),
        "date_start": dated[0].isoformat() if dated else None,
        "date_end": dated[-1].isoformat() if dated else None,
        "company_count": len(companies),
        "source_labels": sorted(sources, key=str.casefold),
        "top_skills": [
            {"skill": item["skill"], "count": item["count"]}
            for item in skill_counts[:20]
        ],
        "skill_counts": skill_counts,
        "location_counts": [
            {"location": name, "count": count}
            for name, count in sorted(location_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
        ],
        "location_skill_counts": {
            city: [
                {"skill": skill, "count": count}
                for skill, count in counts.most_common(20)
            ]
            for city, counts in location_skill_counts.items()
        },
        "title_counts": [
            {"title": name, "count": count}
            for name, count in title_counts.most_common(20)
        ],
    }


def clear_collected_posting_skills_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def get_collected_posting_skills(*, firestore_client=None) -> dict[str, Any]:
    """Read at most 500 India jobs, shared in-process for 60 seconds."""
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if _cache and now - _cache[0] < _CACHE_TTL_SECONDS:
            read_guard.record_cache_hit()
            return dict(_cache[1])

    client = firestore_client if firestore_client is not None else get_firestore_client()
    query = (
        client.collection("jobs")
        .where(filter=FieldFilter("country_code", "==", "in"))
        .limit(_QUERY_LIMIT)
    )
    snapshots = list(query.stream())
    read_guard.record_read("jobs", len(snapshots), query_type="bounded_collected_posting_skills")
    records = [(snapshot.id, snapshot.to_dict() or {}) for snapshot in snapshots]
    result = compute_posting_skill_aggregate(records)
    result["sample_may_be_incomplete"] = len(snapshots) == _QUERY_LIMIT
    result["query_limit"] = _QUERY_LIMIT
    with _cache_lock:
        _cache = (time.monotonic(), result)
    return dict(result)

import hashlib
from datetime import datetime, timezone

from app.analytics.skill_normalization import extract_skills, normalize_skill
from app.analytics.skill_registry import canonical_skill_id
from app.models.skill_intelligence import MarketObservation, MarketPosting


def observations_from_postings(
    postings: list[MarketPosting],
    *,
    location: str | None,
    country: str | None,
    collected_at: datetime,
    fetch_run_id: str | None = None,
    query_id: str | None = None,
    panel_version: str | None = None,
) -> list[MarketObservation]:
    observed_at = collected_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    period = observed_at.astimezone(timezone.utc).strftime("%Y-%m")
    scope = "city" if location else "country" if country else "global"
    observation_location = location or _country_name(country)
    result: list[MarketObservation] = []
    seen: set[tuple[str, str]] = set()
    for posting in postings:
        skills = extract_skills(posting.title, posting.description, *posting.skills)
        for skill in skills:
            dedupe_key = (posting.source.casefold(), f"{posting.posting_id}:{skill.casefold()}")
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            source = posting.source.casefold()
            normalized_skill = normalize_skill(skill)
            skill_key = canonical_skill_id(normalized_skill) or normalized_skill.casefold().replace(" ", "-")
            stable_key = "|".join((
                source,
                posting.posting_id,
                period,
                (observation_location or "").casefold(),
                skill_key,
                query_id or panel_version or "job-demand-v1",
            ))
            observation_id = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()
            series_id = f"{source}:{query_id or panel_version or 'job-demand-v1'}:job-demand:{skill_key}:v1"
            result.append(MarketObservation(
                id=observation_id,
                source=source,
                skill=normalized_skill,
                location=observation_location,
                observed_at=observed_at,
                period=period,
                scope=scope,
                posting_id=posting.posting_id,
                signal_type="demand",
                history_type="platform_collected",
                data_origin="real",
                fetch_run_id=fetch_run_id,
                query_id=query_id,
                panel_version=panel_version,
                series_id=series_id,
                value=1.0,
                unit="job_postings",
                source_url=posting.source_url,
                metadata={"title": posting.title} if posting.title else {},
            ))
    return result


def _country_name(country: str | None) -> str | None:
    if not country:
        return None
    names = {
        "au": "Australia",
        "ca": "Canada",
        "de": "Germany",
        "gb": "United Kingdom",
        "in": "India",
        "jp": "Japan",
        "sg": "Singapore",
        "us": "United States",
    }
    return names.get(country.casefold(), country.upper())

import hashlib
import json
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from firebase_admin import firestore

from app.analytics.skill_normalization import normalize_skill
from app.analytics.skill_registry import BY_ID, canonical_skill_id, normalize_skill_entry, reference_skill_id
from app.analytics.analytical_readiness import assess_analytical_readiness, summarize_readiness
from app.analytics.freshness import assess_freshness
from app.analytics.series_validation import summarize_quality, validate_series_observations
from app.analytics.signal_aggregation import aggregate_market_signals
from app.analytics.trend import CALCULATION_VERSION, G14_CALCULATION_VERSION, calculate_skill_trends, calculate_trend_and_velocity, compatible_demand_observations
from app.services.intelligence_contract_service import observed_metric_results, trend_metric_results
from app.core.config import get_settings
from app.core.firebase import get_firestore_client
from app.models.onboarding import SkillLevel
from app.models.skill_intelligence import (
    SelectedSkillIntelligence,
    SkillIntelligenceFilters,
    SkillIntelligenceResponse,
    SkillProfileContext,
    SkillTrend,
    SkillTrendPoint,
    TrendingSkill,
    UserSkill,
    UserSkillsResponse,
    UserSkillsUpdateRequest,
    FavouriteSkillsResponse,
    FavouriteSkillsUpdateRequest,
)
from app.services.market_collection_service import configured_market_providers, pending_market_sources
from app.services.onboarding_service import get_individual_profile
from app.storage.firestore_observation_store import FirestoreObservationStore
from app.storage.fetch_run_store import FirestoreFetchRunStore
from app.storage.calculation_record_store import FirestoreCalculationRecordStore
from app.storage.market_store import MarketDataStore


def _skill_entries(profile: dict[str, Any]) -> list[UserSkill]:
    skill_profile = profile.get("skills", {})
    if not isinstance(skill_profile, dict):
        return []

    selected = skill_profile.get("selected_skills", [])
    levels = skill_profile.get("skill_levels", {})
    if not isinstance(selected, list):
        return []
    if not isinstance(levels, dict):
        levels = {}

    entries: list[UserSkill] = []
    seen: set[str] = set()
    for value in selected:
        if not isinstance(value, str) or not value.strip():
            continue
        identity = normalize_skill_entry(value)
        name = identity.display_name
        dedupe_key = identity.canonical_skill_id or name.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        raw_level = next((
            raw for source_name, raw in levels.items()
            if isinstance(source_name, str)
            and (normalize_skill_entry(source_name).canonical_skill_id or source_name.casefold()) == dedupe_key
        ), None)
        try:
            level = SkillLevel(raw_level) if raw_level is not None else None
        except ValueError:
            level = None
        entries.append(UserSkill(name=name, level=level))
    return entries


def _profile_location(profile: dict[str, Any]) -> str | None:
    basic_profile = profile.get("basic_profile", {})
    if not isinstance(basic_profile, dict):
        return None
    city = basic_profile.get("city")
    country = basic_profile.get("country")
    if isinstance(city, str) and city.strip():
        return city.strip()
    if isinstance(country, str) and country.strip():
        return country.strip()
    return None


def _build_intelligence_response(
    *,
    profile: dict[str, Any],
    skills: list[UserSkill],
    display_location: str | None,
    range_key: str,
    custom_days: int | None = None,
    skill: str | None,
    effective_location: str | None,
    observations,
    trend_records: list[dict[str, Any]],
    summary: dict[str, Any],
    settings,
    pending_sources: list[str],
) -> SkillIntelligenceResponse:
    history_complete = not bool(getattr(observations, "truncated", False))
    analysis_observations = observations if history_complete else []
    if not history_complete:
        trend_records = []
    selected_skills = [item.name for item in skills]
    context = SkillProfileContext(
        location=_profile_location(profile),
        selected_skills=[item.name for item in skills],
    )
    filters = SkillIntelligenceFilters(
        location=display_location,
        range=range_key,
        skill=skill.strip() if skill and skill.strip() else None,
    )
    ranked_market = _rank_trends(trend_records)
    skill_lookup = {normalize_skill(item.name).casefold(): item for item in skills}
    personal_top = [
        item for item in ranked_market
        if normalize_skill(item.skill).casefold() in skill_lookup
    ][:5]
    market_top = ranked_market[:5]
    quality_reports = validate_series_observations(
        analysis_observations,
        min_periods=settings.skill_intelligence_min_periods,
    )
    quality_summary = summarize_quality(quality_reports).model_dump(mode="json")
    readiness_reports = assess_analytical_readiness(
        analysis_observations,
        quality_reports=quality_reports,
        min_trend_periods=settings.skill_intelligence_min_periods,
        min_forecast_periods=settings.skill_intelligence_min_forecast_periods,
    )
    readiness_summary = summarize_readiness(readiness_reports).model_dump(mode="json")
    readiness_by_key = {
        (r.provider.casefold().strip(), r.signal_type.strip(), r.canonical_skill_id): r
        for r in readiness_reports
    }
    agg_signals = aggregate_market_signals(analysis_observations)
    g14_trend_results = calculate_trend_and_velocity(
        agg_signals,
        min_periods=settings.skill_intelligence_min_periods,
        quality_reports=quality_reports,
        readiness_reports=readiness_reports,
    )
    production_trends = [t.model_dump(mode="json") for t in g14_trend_results]
    current_interest = [t.model_dump(mode="json") for t in g14_trend_results if t.signal_type == "interest"]
    current_adoption = [t.model_dump(mode="json") for t in g14_trend_results if t.signal_type == "adoption"]
    contributing_observations = compatible_demand_observations(analysis_observations)
    sources_used = sorted({observation.source for observation in contributing_observations})
    last_collection = summary.get("last_collection") or {}
    if market_top:
        data_status = "available"
    elif last_collection.get("status") in {"error", "failed"}:
        data_status = "error"
    elif (
        observations
        or summary.get("observations", 0) > 0
        or configured_market_providers(settings)
    ):
        data_status = "insufficient_data"
    else:
        data_status = "pending_source_data"

    # Keep the legacy data_status stable for the active frontend while exposing
    # only facts available from the stored observations and fetch_runs.
    data_state = (
        "incomplete" if not history_complete
        else
        "ready" if data_status == "available" and not pending_sources and last_collection.get("status") not in {"partial", "failed"}
        else "partial" if data_status == "available"
        else "insufficient_data" if data_status == "insufficient_data"
        else "building" if data_status == "pending_source_data"
        else None
    )
    provider_runs = last_collection.get("providers", {}) if isinstance(last_collection, dict) else {}
    run_collection_times = {
        str(run.get("run_id")): run.get("completed_at")
        for run in provider_runs.values()
        if isinstance(run, dict)
        and run.get("run_id")
        and run.get("completed_at")
        and run.get("status") in {"success", "partial"}
    } if isinstance(provider_runs, dict) else {}
    freshness = assess_freshness(
        contributing_observations,
        collection_times_by_run=run_collection_times,
    )
    if data_status == "available" and history_complete:
        if freshness.state == "stale":
            data_state = "stale"
        elif freshness.state == "ready" and (
            pending_sources or last_collection.get("status") in {"partial", "failed", "running"}
        ):
            data_state = "partial"
        else:
            data_state = freshness.state
    provenance_sources = []
    for source in sources_used:
        rows = [item for item in contributing_observations if item.source.casefold() == source.casefold()]
        run = provider_runs.get(source.casefold(), {}) if isinstance(provider_runs, dict) else {}
        run_id = run.get("run_id") if isinstance(run, dict) else None
        linked_run_ids = sorted({item.fetch_run_id for item in rows if item.fetch_run_id})
        # A latest fetch run may have failed; only attach it when observations
        # actually link to that run. Collection time otherwise comes from rows.
        if run_id not in linked_run_ids:
            run_id = None
            run = {}
        collected_at = (
            run.get("completed_at") if run_id and isinstance(run, dict)
            else max((item.created_at for item in rows if item.created_at), default=None)
        )
        provenance_sources.append({
            "source": source,
            "signal_type": "demand",
            "history_type": "platform_collected",
            **({"data_origin": next(iter({item.data_origin for item in rows}))}
               if len({item.data_origin for item in rows}) == 1 and rows[0].data_origin is not None else {}),
            "observation_count": len(rows),
            "period_count": len({item.period for item in rows if item.period}),
            "fetch_run_ids": linked_run_ids,
            "latest_fetch_run_id": run_id,
            "last_collected": collected_at,
            "skills": [
                {
                    "skill": normalized,
                    "observation_count": sum(1 for item in rows if normalize_skill(item.skill).casefold() == normalized),
                    "period_count": len({item.period for item in rows if item.period and normalize_skill(item.skill).casefold() == normalized}),
                    "observation_ids": [
                        item.id for item in rows
                        if item.id and normalize_skill(item.skill).casefold() == normalized
                    ][:20],
                    "observation_ids_truncated": sum(
                        1 for item in rows if item.id and normalize_skill(item.skill).casefold() == normalized
                    ) > 20,
                }
                for normalized in sorted({normalize_skill(item.skill).casefold() for item in rows})
            ],
        })
    latest_collection_time = max(
        (item["last_collected"] for item in provenance_sources if item["last_collected"]),
        default=None,
    )

    selected = None
    if skill and skill.strip():
        canonical = normalize_skill(skill.strip())
        user_skill = skill_lookup.get(canonical.casefold())
        matching = next(
            (record for record in trend_records if normalize_skill(record["skill"]).casefold() == canonical.casefold()),
            None,
        )
        matching_g14 = next(
            (t for t in g14_trend_results if normalize_skill(t.canonical_name).casefold() == canonical.casefold()),
            None,
        ) if matching is None else None

        if matching:
            selected = SelectedSkillIntelligence(
                skill=user_skill.name if user_skill else canonical,
                proficiency=user_skill.level.value if user_skill and user_skill.level else None,
                growth_pct=matching.get("growth_pct"),
                trend=matching.get("trend", "Insufficient Data"),
                confidence=matching.get("confidence"),
                series=[SkillTrendPoint.model_validate(point) for point in matching.get("series", [])],
                category=matching.get("category"),
                demand_share=matching.get("demand_share"),
                source=matching.get("source"),
                unit=matching.get("unit"),
                velocity=matching.get("velocity"),
                velocity_unit=matching.get("velocity_unit"),
                latest_period_change=matching.get("latest_period_change"),
                latest_period_change_pct=matching.get("latest_period_change_pct"),
                slope=matching.get("slope"),
                slope_unit=matching.get("slope_unit"),
                period_grain=matching.get("period_grain"),
                readiness_state=matching.get("readiness_state"),
                blocking_reasons=matching.get("blocking_reasons", []),
                series_provenance=matching.get("series_provenance"),
            )
        elif matching_g14:
            selected = SelectedSkillIntelligence(
                skill=user_skill.name if user_skill else canonical,
                proficiency=user_skill.level.value if user_skill and user_skill.level else None,
                growth_pct=matching_g14.growth_pct,
                trend=matching_g14.trend,
                confidence=matching_g14.confidence,
                series=[],
                category=None,
                demand_share=None,
                source=matching_g14.source,
                unit=matching_g14.unit,
                velocity=matching_g14.velocity,
                velocity_unit=matching_g14.velocity_unit,
                latest_period_change=matching_g14.latest_mom_change,
                latest_period_change_pct=matching_g14.latest_mom_pct_change,
                slope=matching_g14.slope,
                slope_unit=matching_g14.slope_unit,
                period_grain=matching_g14.period_grain,
                readiness_state=matching_g14.readiness_state,
                blocking_reasons=matching_g14.blocking_reasons,
                series_provenance=matching_g14.explanation,
            )
        else:
            selected = SelectedSkillIntelligence(
                skill=user_skill.name if user_skill else canonical,
                proficiency=user_skill.level.value if user_skill and user_skill.level else None,
                growth_pct=None,
                trend="Insufficient Data",
                confidence=None,
                series=[],
                category=None,
                demand_share=None,
                source=None,
                readiness_state="insufficient_history",
                blocking_reasons=["No comparable source-specific trend series is available."],
                series_provenance=None,
            )

    data_origins = {item.data_origin for item in observations if item.data_origin}
    root_data_origin = (
        next(iter(data_origins)) if len(data_origins) == 1
        else "mixed" if len(data_origins) > 1
        else "unavailable"
    )
    history_types = {item.history_type for item in observations if item.history_type}
    root_history_type = (
        next(iter(history_types)) if len(history_types) == 1
        else "mixed" if len(history_types) > 1
        else "unavailable"
    )

    calculation_data_origin = next(iter(data_origins)) if len(data_origins) == 1 else None
    current_demand = []
    for record in trend_records:
        points = record.get("series") or []
        provenance = record.get("series_provenance") or {}
        demand_share = record.get("demand_share")
        if not points or not isinstance(demand_share, (int, float)):
            continue
        current_period = points[-1].get("period")
        canonical_name = normalize_skill(record.get("skill"))
        canon_id = canonical_skill_id(canonical_name)
        velocity_val = record.get("velocity")
        slope_val = record.get("slope")
        raw_val = record.get("raw_value")
        denom_val = record.get("denominator")
        evidence_endpoint = f"/api/v1/skills/intelligence/{canon_id or canonical_name}/evidence"
        matching_readiness = readiness_by_key.get((record.get("source", "").casefold().strip(), "demand", canon_id))
        readiness_payload = matching_readiness.model_dump(mode="json") if matching_readiness else None
        current_demand.append({
            "skill": record.get("skill"),
            "canonical_skill_id": canon_id,
            "canonical_name": canonical_name,
            "value": demand_share,
            "raw_value": raw_val,
            "normalized_value": demand_share,
            "denominator": denom_val,
            "velocity": velocity_val,
            "velocity_unit": record.get("velocity_unit"),
            "latest_period_change": record.get("latest_period_change"),
            "latest_period_change_pct": record.get("latest_period_change_pct"),
            "slope": slope_val,
            "slope_unit": record.get("slope_unit"),
            "unit": record.get("unit"),
            "period_grain": record.get("period_grain"),
            "metric": "source_specific_demand_share",
            "source": record.get("source"),
            "provider": record.get("source"),
            "signal_type": "demand",
            "series_id": record.get("series_id"),
            "period": current_period,
            "data_origin": record.get("data_origin"),
            "history_type": "platform_collected",
            "data_state": record.get("data_state", "insufficient_data"),
            "trend": record.get("trend"),
            "confidence": record.get("confidence"),
            "readiness": readiness_payload,
            "coverage": {
                "observation_count": provenance.get("observation_count", 0),
                "source_job_count": (provenance.get("posting_counts_by_period") or {}).get(current_period, 0),
                "period_count": provenance.get("period_count", 0),
            },
            "evidence": {
                "observation_ids": provenance.get("observation_ids", []),
                "fetch_run_ids": provenance.get("fetch_run_ids", []),
                "query_id": provenance.get("query_id"),
                "panel_version": provenance.get("panel_version"),
                "scope": provenance.get("scope"),
                "location": provenance.get("location"),
                "collected_at": provenance.get("collected_at"),
                "minimum_trend_periods": settings.skill_intelligence_min_periods,
                "calculation_version": record.get("calculation_version") or CALCULATION_VERSION,
                "analytical_readiness": readiness_payload,
                "evidence_url": evidence_endpoint,
            },
            "evidence_url": evidence_endpoint,
        })
    metric_results = [
        *observed_metric_results(observations, history_complete=history_complete),
        *trend_metric_results(
            g14_trend_results,
            observations,
            history_complete=history_complete,
        ),
    ]
    return SkillIntelligenceResponse(
        profile_context=context,
        filters=filters,
        data_status=data_status,
        data_state=data_state,
        data_origin=root_data_origin,
        history_type=root_history_type,
        quality_summary=quality_summary,
        analytical_readiness=readiness_summary,
        metric_results=metric_results,
        history_complete=history_complete,
        history_completeness_reason=(
            None if history_complete
            else "Observation retrieval reached its bounded row limit; derived metrics were withheld."
        ),
        top_skills=[
            TrendingSkill(
                skill=item.skill,
                category=item.category,
                growth_pct=item.growth_pct,
                trend=item.trend,
                confidence=item.confidence,
                source=item.source,
                unit=item.unit,
                velocity=item.velocity,
                velocity_unit=item.velocity_unit,
                latest_period_change=item.latest_period_change,
                latest_period_change_pct=item.latest_period_change_pct,
                slope=item.slope,
                slope_unit=item.slope_unit,
                period_grain=item.period_grain,
                readiness_state=item.readiness_state,
                blocking_reasons=item.blocking_reasons,
            )
            for item in market_top
        ],
        skill_trends=market_top,
        current_demand=current_demand,
        current_interest=current_interest,
        current_adoption=current_adoption,
        production_trends=production_trends,
        personal_top_skills=personal_top,
        market_top_skills=market_top,
        selected_skill=selected,
        sources_used=sources_used,
        sources_pending=pending_sources,
        observations_count=len(observations),
        historical_periods_count=len({item.period for item in observations if item.period}),
        calculation={
            "sources": sources_used,
            "signal_type": "demand",
            "history_type": "platform_collected",
            **({"data_origin": calculation_data_origin} if calculation_data_origin is not None else {}),
            "period": range_key,
            "period_days": custom_days,
            "observation_count": len(contributing_observations),
            "historical_periods_count": len({item.period for item in contributing_observations if item.period}),
            "formula": CALCULATION_VERSION,
            "last_collected": latest_collection_time,
            "status": data_state,
            "fresh_observation_count": freshness.fresh_count,
            "stale_observation_count": freshness.stale_count,
            "unknown_freshness_count": freshness.unknown_count,
        },
        provenance={
            "sources": provenance_sources,
            "signal_type": "demand",
            "history_type": "platform_collected",
            **({"data_origin": calculation_data_origin} if calculation_data_origin is not None else {}),
            "calculation_version": CALCULATION_VERSION,
            "observation_count": len(contributing_observations),
            "period_count": len({item.period for item in contributing_observations if item.period}),
            "status": data_state,
            "quality_summary": quality_summary,
            "analytical_readiness": readiness_summary,
        },
        error_message=(
            "Market data collection is currently unavailable."
            if data_status == "error"
            else None
        ),
    )


def get_user_skills(uid: str) -> UserSkillsResponse:
    profile_response = get_individual_profile(uid)
    return UserSkillsResponse(
        skills=_skill_entries(profile_response.profile),
        profile_updated_at=profile_response.updated_at,
    )


def update_user_skills(uid: str, request: UserSkillsUpdateRequest) -> UserSkillsResponse:
    client = get_firestore_client()
    document = client.collection("users").document(uid)
    try:
        snapshot = document.get()
        stored = snapshot.to_dict() if snapshot.exists else {}
        stored = stored if isinstance(stored, dict) else {}
        user_type = stored.get("user_type")
        if user_type not in (None, "individual"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This skill profile endpoint is for Individual profiles.",
            )

        current_profile = stored.get("profile")
        current_profile = current_profile if isinstance(current_profile, dict) else {}
        current_skills = current_profile.get("skills")
        current_skills = current_skills if isinstance(current_skills, dict) else {}
        current_levels = current_skills.get("skill_levels")
        current_levels = current_levels if isinstance(current_levels, dict) else {}

        selected_skills: list[str] = []
        skill_levels: dict[str, str] = {}
        seen: set[str] = set()
        for submitted in request.skills:
            identity = normalize_skill_entry(submitted.name)
            name = identity.display_name
            dedupe_key = identity.canonical_skill_id or name.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            selected_skills.append(name)
            level = submitted.level
            if level is None:
                level = next(
                    (
                        SkillLevel(raw_level)
                        for old_name, raw_level in current_levels.items()
                        if isinstance(old_name, str)
                        and (normalize_skill_entry(old_name).canonical_skill_id or old_name.casefold()) == dedupe_key
                        and raw_level in {item.value for item in SkillLevel}
                    ),
                    None,
                )
            if level is not None:
                skill_levels[name] = level.value

        updates = {
            "uid": uid,
            "user_type": "individual",
            "profile.skills.selected_skills": selected_skills,
            "profile.skills.skill_levels": skill_levels,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if snapshot.exists:
            document.update(updates)
        else:
            document.set(
                {
                    "uid": uid,
                    "user_type": "individual",
                    "profile": {
                        "skills": {
                            "selected_skills": selected_skills,
                            "skill_levels": skill_levels,
                        }
                    },
                    "updated_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Your skills could not be saved. Please retry.",
        ) from None

    return get_user_skills(uid)


def get_favourite_skills(uid: str) -> FavouriteSkillsResponse:
    try:
        snapshot = get_firestore_client().collection("users").document(uid).get()
        record = snapshot.to_dict() if snapshot.exists else {}
        preferences = (record or {}).get("preferences", {})
        stored = preferences.get("favorite_skill_ids", []) if isinstance(preferences, dict) else []
        seen: set[str] = set()
        ids = []
        for skill_id in stored if isinstance(stored, list) else []:
            if isinstance(skill_id, str) and _is_supported_skill_id(skill_id) and skill_id not in seen:
                ids.append(skill_id)
                seen.add(skill_id)
        return FavouriteSkillsResponse(skill_ids=ids)
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Your saved skills could not be loaded.") from None


def update_favourite_skills(uid: str, request: FavouriteSkillsUpdateRequest) -> FavouriteSkillsResponse:
    ids: list[str] = []
    seen: set[str] = set()
    for skill_id in request.skill_ids:
        if not _is_supported_skill_id(skill_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported canonical skill ID: {skill_id}")
        if skill_id not in seen:
            ids.append(skill_id)
            seen.add(skill_id)
    client = get_firestore_client()
    document = client.collection("users").document(uid)
    try:
        snapshot = document.get()
        record = snapshot.to_dict() if snapshot.exists else {}
        user_type = (record or {}).get("user_type")
        if user_type not in (None, "individual"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Skill favourites are available to Individual profiles.")
        document.set({"uid": uid, "preferences": {"favorite_skill_ids": ids}}, merge=True)
        return FavouriteSkillsResponse(skill_ids=ids)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Your saved skills could not be updated.") from None


def _is_supported_skill_id(skill_id: str) -> bool:
    if skill_id in BY_ID:
        return True
    try:
        from app.storage.reference_store import ReferenceDataStore
        for row in ReferenceDataStore().get_reference_skill_rows():
            if canonical_skill_id(row.get("name") or "") == skill_id:
                return True
            if reference_skill_id(row.get("name") or "") == skill_id:
                return True
    except Exception:
        return False
    return False


async def get_skill_intelligence(
    uid: str,
    *,
    location: str | None,
    range_key: str,
    skill: str | None,
    custom_days: int | None = None,
    _force_backend: str | None = None,
) -> SkillIntelligenceResponse:
    settings = get_settings()
    if _force_backend != "sqlite":
        return await get_skill_intelligence_from_firestore(
            uid,
            location=location,
            range_key=range_key,
            custom_days=custom_days,
            skill=skill,
            settings=settings,
        )
    profile_response = get_individual_profile(uid)
    profile = profile_response.profile
    skills = _skill_entries(profile)
    requested_location = location.strip() if location else None
    is_global_filter = bool(requested_location and requested_location.casefold() == "global")
    effective_location = (
        None if is_global_filter
        else requested_location or _profile_location(profile)
    )
    display_location = "Global" if is_global_filter else effective_location
    context = SkillProfileContext(
        location=_profile_location(profile),
        selected_skills=[item.name for item in skills],
    )
    filters = SkillIntelligenceFilters(
        location=display_location,
        range=range_key,
        skill=skill.strip() if skill and skill.strip() else None,
    )
    pending_sources = pending_market_sources(settings)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=custom_days) if range_key == "custom" and custom_days else _range_cutoff(range_key, now)
    try:
        store = MarketDataStore(settings.skill_intelligence_db_path)
        cache_key = _calculation_cache_key(effective_location, range_key, cutoff)
        trend_records = store.get_cached(cache_key)
        if trend_records is None:
            observations = store.get_observations(location=effective_location, cutoff=cutoff)
            trend_records = calculate_skill_trends(
                observations,
                min_periods=settings.skill_intelligence_min_periods,
                now=now,
            )
            store.put_cached(cache_key, trend_records)
        else:
            observations = store.get_observations(location=effective_location, cutoff=cutoff)
        summary = store.collection_summary()
    except Exception:
        return SkillIntelligenceResponse(
            profile_context=context,
            filters=filters,
            data_status="error",
            data_state="error",
            data_origin="unavailable",
            history_type="unavailable",
            top_skills=[],
            skill_trends=[],
            error_message="Market intelligence storage is temporarily unavailable.",
            sources_pending=pending_sources,
        )

    return _build_intelligence_response(
        profile=profile,
        skills=skills,
        display_location=display_location,
        range_key=range_key,
        custom_days=custom_days,
        skill=skill,
        effective_location=effective_location,
        observations=observations,
        trend_records=trend_records,
        summary=summary,
        settings=settings,
        pending_sources=pending_sources,
    )


async def get_skill_intelligence_from_firestore(
    uid: str,
    *,
    location: str | None,
    range_key: str,
    skill: str | None,
    custom_days: int | None = None,
    settings=None,
) -> SkillIntelligenceResponse:
    """Production intelligence path backed by canonical Firestore data."""
    profile = get_individual_profile(uid).profile
    skills = _skill_entries(profile)
    requested_location = location.strip() if location else None
    is_global_filter = bool(requested_location and requested_location.casefold() == "global")
    effective_location = None if is_global_filter else requested_location or _profile_location(profile)
    display_location = "Global" if is_global_filter else effective_location
    settings = settings or get_settings()
    pending_sources = pending_market_sources(settings)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=custom_days) if range_key == "custom" and custom_days else _range_cutoff(range_key, now)
    try:
        store = FirestoreObservationStore()
        observations = store.get_observations(cutoff=cutoff, location=effective_location)
        trend_records = calculate_skill_trends(
            observations,
            min_periods=settings.skill_intelligence_min_periods,
            now=now,
        )
        # Collection status is per provider; do not imply that these are one parent run.
        summary = FirestoreFetchRunStore().collection_summary()
        summary["observations"] = int(bool(observations) or store.has_observations())
    except Exception:
        context = SkillProfileContext(
            location=_profile_location(profile),
            selected_skills=[item.name for item in skills],
        )
        filters = SkillIntelligenceFilters(
            location=display_location,
            range=range_key,
            skill=skill.strip() if skill and skill.strip() else None,
        )
        return SkillIntelligenceResponse(
            profile_context=context,
            filters=filters,
            data_status="error",
            data_state="error",
            data_origin="unavailable",
            history_type="unavailable",
            top_skills=[],
            skill_trends=[],
            error_message="Market intelligence storage is temporarily unavailable.",
            sources_pending=pending_sources,
        )
    response = _build_intelligence_response(
        profile=profile,
        skills=skills,
        display_location=display_location,
        range_key=range_key,
        custom_days=custom_days,
        skill=skill,
        effective_location=effective_location,
        observations=observations,
        trend_records=trend_records,
        summary=summary,
        settings=settings,
        pending_sources=pending_sources,
    )
    fs_client = get_firestore_client()
    try:
        calculation_ids = FirestoreCalculationRecordStore(fs_client).persist_current_demand(
            response.current_demand,
            window=range_key,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calculation provenance is temporarily unavailable.",
        ) from None
    try:
        from app.models.market_signal import SkillTrendVelocityResult
        ready_trends = [
            SkillTrendVelocityResult.model_validate(t)
            for t in response.production_trends
            if t.get("data_state") == "ready" and t.get("data_origin") == "real"
        ]
        trend_calc_ids = FirestoreCalculationRecordStore(fs_client).persist_trend_velocity_results(
            ready_trends,
            window=range_key,
        )
    except Exception:
        trend_calc_ids = {}

    snapshots = []
    for snapshot in response.current_demand:
        key = "|".join((str(snapshot.get("source")), str(snapshot.get("series_id")), str(snapshot.get("period")), str(snapshot.get("metric"))))
        snapshots.append({**snapshot, "calculation_record_id": calculation_ids.get(key)})

    updated_production_trends = []
    for tr in response.production_trends:
        t_key = "|".join((str(tr.get("source")), str(tr.get("signal_type")), str(tr.get("canonical_name")), str(tr.get("latest_period"))))
        c_id = trend_calc_ids.get(t_key)
        updated_production_trends.append({**tr, "calculation_record_id": c_id})

    updated_current_interest = [
        t for t in updated_production_trends if t.get("signal_type") == "interest"
    ]
    updated_current_adoption = [
        t for t in updated_production_trends if t.get("signal_type") == "adoption"
    ]

    return response.model_copy(update={
        "current_demand": snapshots,
        "production_trends": updated_production_trends,
        "current_interest": updated_current_interest,
        "current_adoption": updated_current_adoption,
    })


async def get_skill_intelligence_for_validation(
    uid: str,
    *,
    backend: str,
    location: str | None,
    range_key: str,
    skill: str | None,
) -> SkillIntelligenceResponse:
    """Select one internal calculation path without changing the API contract."""
    if backend == "sqlite":
        return await get_skill_intelligence(
            uid, location=location, range_key=range_key, skill=skill, _force_backend="sqlite",
        )
    if backend == "firestore":
        return await get_skill_intelligence_from_firestore(
            uid, location=location, range_key=range_key, skill=skill,
        )
    raise ValueError("Unknown intelligence validation backend.")


def _rank_trends(records: list[dict[str, Any]]) -> list[SkillTrend]:
    candidates = [
        SkillTrend.model_validate(record)
        for record in records
        if record.get("trend") in {"Growing", "Stable", "Declining"}
        and isinstance(record.get("ranking_score"), (int, float))
    ]
    return sorted(
        candidates,
        key=lambda item: item.ranking_score if item.ranking_score is not None else float("-inf"),
        reverse=True,
    )


def _range_cutoff(range_key: str, now: datetime) -> datetime:
    if range_key == "6m":
        months = 6
    elif range_key == "3m":
        months = 3
    elif range_key == "custom":
        raise ValueError("Custom window requires a day count.")
    else:
        return now - timedelta(days={"7d": 7, "30d": 30}[range_key])
    month_index = now.year * 12 + now.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(now.day, monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def _calculation_cache_key(location: str | None, range_key: str, cutoff: datetime) -> str:
    content = json.dumps({
        "location": location.casefold().strip() if location else None,
        "range": range_key,
        "cutoff": cutoff.date().isoformat(),
        "version": CALCULATION_VERSION,
    }, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

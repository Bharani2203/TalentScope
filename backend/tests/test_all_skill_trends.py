from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.skill_registry import canonical_skill_id
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.models.intent_planner import IntelligencePlanRequest
from app.models.skill_intelligence import MarketObservation
from app.services.execution_orchestrator_service import ExecutionOrchestratorService
from app.services.intent_planner_service import IntentPlannerService


def completed_periods(count: int = 4) -> list[str]:
    today = datetime.now(timezone.utc).date()
    index = today.year * 12 + today.month - 1
    periods = []
    for offset in range(count, 0, -1):
        month_index = index - offset
        year, month = divmod(month_index, 12)
        periods.append(f"{year:04d}-{month + 1:02d}")
    return periods


def observations_for(
    skill: str,
    values: list[float],
    *,
    source: str = "jsearch",
    signal_type: str = "demand",
    location: str = "India",
    history_type: str = "platform_collected",
    data_origin: str = "real",
    created_at: datetime | None = None,
    query_id: str = "shared-query-v1",
) -> list[MarketObservation]:
    skill_id = canonical_skill_id(skill)
    observations = []
    for period, value in zip(completed_periods(len(values)), values):
        year, month = (int(part) for part in period.split("-"))
        observations.append(MarketObservation(
            id=f"obs-{source}-{signal_type}-{skill_id}-{period}",
            source=source,
            skill=skill,
            skill_id=skill_id,
            signal_type=signal_type,
            observed_at=datetime(year, month, 15, tzinfo=timezone.utc),
            created_at=created_at or datetime.now(timezone.utc),
            period=period,
            location=location,
            scope="country",
            value=value,
            unit="job_postings" if signal_type == "demand" else "developers",
            denominator_unit="postings" if signal_type == "demand" else None,
            denominator=1000 if signal_type == "demand" else None,
            posting_id=f"{source}-{skill_id}-{period}",
            data_origin=data_origin,
            history_type=history_type,
            series_id=f"{source}:{signal_type}:{skill_id}:v1",
            query_id=query_id,
            panel_version="panel-v1",
            fetch_run_id=f"run-{source}-{period}",
            quality="valid",
        ))
    return observations


class InMemoryObservationStore:
    def __init__(self, observations: list[MarketObservation]):
        self.observations = observations
        self.last_query: dict[str, object] | None = None

    def get_observations(self, **kwargs):
        self.last_query = kwargs
        rows = [
            observation for observation in self.observations
            if observation.observed_at >= kwargs["cutoff"]
            and (
                not kwargs.get("location")
                or observation.location.casefold() == kwargs["location"].casefold()
                or observation.location.casefold().startswith(f"{kwargs['location'].casefold()},")
            )
            and (not kwargs.get("scope") or observation.scope == kwargs["scope"])
            and (not kwargs.get("source") or observation.source.casefold() == kwargs["source"].casefold())
            and (not kwargs.get("signal_type") or observation.signal_type == kwargs["signal_type"])
        ]
        return rows

    def get_observations_by_skill(self, skill: str, *, cutoff, location=None):
        self.last_query = {"skill": skill, "cutoff": cutoff, "location": location}
        requested_id = canonical_skill_id(skill)
        return [
            observation for observation in self.observations
            if observation.observed_at >= cutoff
            and (
                observation.skill_id == requested_id
                if requested_id
                else observation.skill.casefold() == skill.casefold()
            )
            and (
                not location
                or observation.location.casefold() == location.casefold()
                or observation.location.casefold().startswith(f"{location.casefold()},")
            )
        ]


def answer(
    store: InMemoryObservationStore,
    message: str = "What skills are currently trending?",
    *,
    filters: dict | None = None,
    time_range: str = "max_available",
    domain: str = "skill",
    capability_id: str | None = None,
    conversation_id: str | None = None,
) :
    service = ExecutionOrchestratorService(
        observation_store=store,
    )
    request = CoreIntelligenceAnswerRequest(
        message=message,
        domain=domain,
        capability_id=capability_id,
        conversation_id=conversation_id,
        time_range=time_range,
        filters=filters or {},
    )
    return service.answer(request)


@pytest.mark.parametrize(
    "message",
    [
        "What skills are currently trending?",
        "Which skills are gaining demand?",
        "Which skills are declining?",
        "Show me top trending skills in India.",
        "Compare the strongest available skill trends.",
    ],
)
def test_all_skill_trend_questions_plan_without_primary_entity(message):
    plan = IntentPlannerService().create_plan(IntelligencePlanRequest(message=message))

    assert plan.intent == "rank_skill_trends"
    assert plan.selected_capabilities == ["trend_velocity_analysis"]
    assert plan.clarification_required is False
    assert plan.plan_status == "ready_to_execute"


def test_all_skill_trends_rank_by_existing_whole_window_change_within_cohort():
    observations = (
        observations_for("Python", [10, 15, 20, 30])
        + observations_for("Java", [10, 11, 12, 13])
        + observations_for("React", [8, 8, 8, 8])
    )
    response = answer(InMemoryObservationStore(observations))
    ranked = [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]

    assert response.execution_status == "completed"
    assert [fact.entity_name for fact in ranked] == ["Python", "Java", "React"]
    assert [fact.details["rank"] for fact in ranked] == [1, 2, 3]
    assert all(fact.metric_name == "whole_window_pct_change" for fact in ranked)
    assert all(fact.unit == "%" for fact in ranked)
    assert all(fact.canonical_entity_id for fact in ranked)
    assert all(fact.details["query_id"] == "shared-query-v1" for fact in ranked)
    assert all(fact.details["periods_used"] == completed_periods() for fact in ranked)
    assert all(fact.evidence_reference for fact in ranked)


def test_all_skill_trends_keep_provider_and_signal_families_in_separate_cohorts():
    observations = (
        observations_for("Python", [10, 15, 20, 30])
        + observations_for("Java", [12, 18, 24, 36], source="github", signal_type="adoption")
    )
    response = answer(InMemoryObservationStore(observations))
    ranked = [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]

    assert {(fact.source, fact.details["signal_type"]) for fact in ranked} == {
        ("jsearch", "demand"),
        ("github", "adoption"),
    }
    assert len({fact.details["cohort_id"] for fact in ranked}) == 2
    assert all(fact.details["rank"] == 1 for fact in ranked)


def test_all_skill_trends_exclude_stale_series():
    stale_created_at = datetime.now(timezone.utc) - timedelta(days=4)
    observations = observations_for(
        "Python", [10, 15, 20, 30], created_at=stale_created_at
    )
    response = answer(InMemoryObservationStore(observations))

    assert response.execution_status == "insufficient_data"
    assert not [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]
    summary = next(fact for fact in response.facts if fact.fact_type == "trend_ranking_summary")
    assert summary.details["eligible_series_count"] == 0
    assert any("stale" in reason.lower() for reason in summary.details["excluded_series_reasons"])


def test_all_skill_trends_reject_incomplete_history_and_reference_only_rows():
    incomplete = observations_for("Python", [10, 15, 20])
    reference = observations_for(
        "Java",
        [10, 15, 20, 25],
        history_type="static_dataset",
    )
    response = answer(InMemoryObservationStore(incomplete + reference))

    assert response.execution_status == "insufficient_data"
    assert not [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]
    assert response.reason_codes[0] == "NO_ELIGIBLE_SKILL_TRENDS"
    assert "reference-only" in " ".join(response.limitations).lower()


def test_all_skill_trend_location_source_and_time_filters_reach_storage_and_response():
    observations = (
        observations_for("Python", [10, 15, 20, 30], source="jsearch")
        + observations_for("Java", [12, 18, 24, 36], source="adzuna")
        + observations_for("React", [9, 14, 19, 24], source="adzuna", location="Global")
    )
    store = InMemoryObservationStore(observations)
    response = answer(
        store,
        "Show me the top trending skills in India.",
        filters={"source": "adzuna"},
        time_range="6m",
    )
    ranked = [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]

    assert [fact.entity_name for fact in ranked] == ["Java"]
    assert store.last_query["location"] == "India"
    assert store.last_query["source"] == "adzuna"
    assert response.applied_filters["location"] == "India"
    assert response.applied_filters["source"] == "adzuna"
    assert response.applied_filters["time_range"] == "6m"


def test_all_skill_trends_support_result_limit_and_offset_without_market_wide_claim():
    observations = (
        observations_for("Python", [10, 15, 20, 30])
        + observations_for("Java", [10, 12, 14, 16])
        + observations_for("React", [10, 11, 12, 13])
    )
    response = answer(
        InMemoryObservationStore(observations),
        filters={"limit": 1, "offset": 1},
    )
    ranked = [fact for fact in response.facts if fact.fact_type == "skill_trend_rank"]
    summary = next(fact for fact in response.facts if fact.fact_type == "trend_ranking_summary")

    assert len(ranked) == 1
    assert ranked[0].entity_name == "Java"
    assert ranked[0].details["rank"] == 2
    assert summary.details["eligible_series_count"] == 3
    assert summary.details["returned_series_count"] == 1
    assert summary.details["has_more"] is True
    assert summary.details["next_offset"] == 2
    assert response.execution_status == "completed"


def test_empty_all_skill_trend_query_explains_scope_limited_missing_evidence():
    response = answer(InMemoryObservationStore([]), "Which skills are trending in India?")
    summary = next(fact for fact in response.facts if fact.fact_type == "trend_ranking_summary")

    assert response.execution_status == "insufficient_data"
    assert response.reason_codes[0] == "NO_ELIGIBLE_SKILL_TRENDS"
    assert "not a claim that no trends exist elsewhere" in response.answer
    assert summary.details["location"] == "India"
    assert summary.details["minimum_consecutive_periods"] == 4


def test_focused_ui_ux_trend_resolves_alias_routes_to_capability_and_returns_measured_series():
    store = InMemoryObservationStore(observations_for("UI/UX", [10, 14, 19, 25]))
    planner = IntentPlannerService().create_plan(IntelligencePlanRequest(
        message="ui/ux trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    ))
    response = answer(
        store,
        "ui/ux trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert planner.intent == "analyze_trend"
    assert planner.selected_capabilities == ["trend_velocity_analysis"]
    assert planner.context_summary["primary_entity"] == "UI/UX"
    assert planner.entities[0].canonical_entity.entity_id == "skill:ui_ux"
    assert response.execution_status == "completed"
    assert response.capabilities_used == ["trend_velocity_analysis"]
    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    assert trend_fact.canonical_entity_id == "ui_ux"
    assert trend_fact.metric_value == "Increasing"
    assert trend_fact.details["periods_count"] == 4
    assert response.evidence


def test_focused_trend_uses_six_month_window_only_when_no_range_was_selected():
    store = InMemoryObservationStore(observations_for("Python", [10, 14, 19, 25]))
    service = ExecutionOrchestratorService(observation_store=store)
    request = CoreIntelligenceAnswerRequest(
        message="Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    response = service.answer(request)

    assert CoreIntelligenceAnswerRequest(message="What is the default?").time_range == "30d"
    assert response.execution_status == "completed"
    assert response.applied_filters["time_range"] == "6m"
    assert response.facts[0].details["periods_count"] == 4
    assert store.last_query is not None
    assert 170 <= (datetime.now(timezone.utc) - store.last_query["cutoff"]).days <= 190


def test_focused_trend_preserves_an_explicit_short_time_range():
    store = InMemoryObservationStore(observations_for("Python", [10, 14, 19, 25]))
    service = ExecutionOrchestratorService(observation_store=store)
    request = CoreIntelligenceAnswerRequest(
        message="Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
        time_range="30d",
        filters={"requested_time_window": "30d"},
    )

    response = service.answer(request)

    assert response.execution_status == "insufficient_data"
    assert response.applied_filters["time_range"] == "30d"
    assert store.last_query is not None
    assert 25 <= (datetime.now(timezone.utc) - store.last_query["cutoff"]).days <= 35


def test_focused_trend_rejects_missing_provenance_and_backfill_history():
    missing_origin = observations_for("Python", [10, 14, 19, 25])
    for observation in missing_origin:
        observation.data_origin = None
    missing_response = answer(
        InMemoryObservationStore(missing_origin),
        "Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )
    backfill_response = answer(
        InMemoryObservationStore(
            observations_for("Python", [10, 14, 19, 25], history_type="backfill")
        ),
        "Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert missing_response.status == "insufficient_data"
    assert missing_response.reason_codes == ["OBSERVATION_PROVENANCE_UNAVAILABLE"]
    assert not any(fact.fact_type == "trend_analysis" for fact in missing_response.facts)
    assert "cannot support a measured trend" in missing_response.answer
    assert backfill_response.status == "insufficient_data"
    assert backfill_response.reason_codes == ["INELIGIBLE_HISTORY_TYPE"]
    assert not any(fact.fact_type == "trend_analysis" for fact in backfill_response.facts)


def test_focused_trend_rejects_stale_collection_evidence():
    stale_created_at = datetime.now(timezone.utc) - timedelta(days=4)
    response = answer(
        InMemoryObservationStore(
            observations_for("Python", [10, 14, 19, 25], created_at=stale_created_at)
        ),
        "Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.status == "insufficient_data"
    assert response.reason_codes == ["STALE_TREND_EVIDENCE"]
    assert not any(fact.fact_type == "trend_analysis" for fact in response.facts)
    assert any(item.freshness_state == "stale" for item in response.evidence)
    assert "stale collection evidence" in response.answer


def test_focused_github_adoption_is_never_presented_as_job_demand():
    observations = observations_for(
        "Python",
        [10, 14, 19, 25],
        source="github",
        signal_type="adoption",
    )
    response = answer(
        InMemoryObservationStore(observations),
        "Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.status == "ready"
    assert "developer adoption/activity trend" in response.answer
    assert "not employer hiring demand" in response.answer
    assert "job-posting demand trend" not in response.answer
    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    assert trend_fact.details["signal_type"] == "adoption"
    assert response.evidence[0].measured_signal_type == "adoption"


def test_focused_trend_preserves_observation_and_fetch_run_provenance(monkeypatch):
    observations = observations_for("Python", [10, 14, 19, 25])
    for observation in observations:
        observation.source_url = f"https://provider.example/{observation.id}"
    service = ExecutionOrchestratorService(
        observation_store=InMemoryObservationStore(observations)
    )
    monkeypatch.setattr(service.llm_service, "is_available", lambda: False)
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
        time_range="max",
    ))

    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    trend_evidence = next(item for item in response.evidence if item.measured_signal_type == "demand")
    assert trend_fact.canonical_entity_id == "python"
    assert len(trend_fact.details["observation_ids"]) == 4
    assert len(trend_fact.details["fetch_run_ids"]) == 4
    assert len(trend_evidence.supporting_observation_ids) == 4
    assert len(trend_evidence.supporting_fetch_run_ids) == 4
    assert len(trend_evidence.supporting_source_urls) == 4


def test_gemini_cannot_change_trend_facts_or_direction(monkeypatch):
    service = ExecutionOrchestratorService(
        observation_store=InMemoryObservationStore(observations_for("Python", [10, 14, 19, 25]))
    )
    monkeypatch.setattr(service.llm_service, "is_available", lambda: True)
    monkeypatch.setattr(
        service.llm_service,
        "generate_grounded_explanation",
        lambda **_kwargs: "The Python trend is declining.",
    )
    response = service.answer(CoreIntelligenceAnswerRequest(
        message="Python trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
        time_range="max",
    ))

    trend_fact = next(fact for fact in response.facts if fact.fact_type == "trend_analysis")
    assert trend_fact.metric_value == "Increasing"
    assert response.answer_origin == "deterministic"
    assert "Increasing" in response.answer
    assert "declining" not in response.answer.lower()


def test_focused_trend_unknown_skill_requests_canonical_name_clarification():
    response = answer(
        InMemoryObservationStore([]),
        "trend for UnregisteredFramework",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.execution_status == "requires_clarification"
    assert response.reason_codes == ["REQUIRES_CLARIFICATION"]
    assert "couldn't match 'UnregisteredFramework'" in response.answer
    assert "canonical skill name" in response.answer


def test_focused_trend_ambiguous_skill_requests_clarification():
    response = answer(
        InMemoryObservationStore([]),
        "trend for C",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.execution_status == "requires_clarification"
    assert "multiple entities" in response.answer
    assert "which specific one" in response.answer.lower()


def test_focused_trend_with_no_matching_observations_is_truthfully_unavailable():
    response = answer(
        InMemoryObservationStore([]),
        "ui/ux trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.execution_status == "insufficient_data"
    assert response.reason_codes == ["NO_OBSERVATIONS_FOR_SERIES"]
    assert "No measured trend observations" in response.answer
    assert "four consecutive comparable monthly periods" in " ".join(response.limitations)
    assert response.facts == []
    assert response.evidence == []


def test_focused_trend_with_three_periods_discloses_history_without_direction():
    response = answer(
        InMemoryObservationStore(observations_for("UI/UX", [10, 14, 19])),
        "ui/ux trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.execution_status == "insufficient_data"
    assert response.reason_codes == ["INSUFFICIENT_TREND_HISTORY"]
    assert "insufficient to calculate a directional trend" in response.answer
    assert "three distinct periods" not in response.answer
    assert "3 distinct periods" in response.answer
    assert "four consecutive comparable monthly periods" in response.answer
    assert not any(fact.fact_type == "trend_analysis" for fact in response.facts)


def test_focused_trend_provider_failure_keeps_classification_and_logs_exception(caplog):
    class FailingObservationStore:
        def get_observations_by_skill(self, *_args, **_kwargs):
            raise RuntimeError("private provider diagnostic")

    response = answer(
        FailingObservationStore(),  # type: ignore[arg-type]
        "ui/ux trend",
        domain="skill",
        capability_id="trend_velocity_analysis",
    )

    assert response.status == "unavailable"
    assert response.execution_status == "failed"
    assert response.reason_codes == ["INTELLIGENCE_SOURCE_UNAVAILABLE"]
    assert "temporarily unavailable" in response.answer
    assert "private provider diagnostic" not in response.answer
    assert "Configured observation source read failed (RuntimeError)" in caplog.text
    assert "private provider diagnostic" in caplog.text

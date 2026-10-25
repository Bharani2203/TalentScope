"""Mock-only coverage for B1 auto routing and structured answer presentation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.intent_planner import IntelligencePlanRequest
from app.services.answer_block_service import build_answer_block, infer_assistant_domain
from app.services.answer_verdict_rules import classify_adoption_growth
from app.services.capability_registry_service import CapabilityRegistryService
from app.services.entity_registry_service import EntityRegistryService
from app.services.intent_planner_service import IntentPlannerService


class _NoNetworkLLM:
    last_error_class = "unavailable"

    def generate_structured_json(self, **_kwargs):
        return None


@pytest.fixture
def offline_planner(tmp_path: Path) -> IntentPlannerService:
    entity_service = EntityRegistryService(db_path=tmp_path / "absent-reference.sqlite3")
    capabilities = CapabilityRegistryService(
        entity_service=entity_service,
        reference_store=object(),
    )
    return IntentPlannerService(
        entity_service=entity_service,
        capability_service=capabilities,
        llm_service=_NoNetworkLLM(),
    )


@pytest.mark.parametrize(
    ("message", "expected_domain", "expected_intent"),
    [
        ("software developer jobs", "job", "search_jobs"),
        ("UI/UX trends", "job", "aggregate_posting_skills"),
        ("What demand trend is observed for Python?", "skill", "analyze_trend"),
        ("What should I learn to become a backend developer?", "skill", "synthesize_actions"),
        ("What is Python used for?", "skill", "general_explanation"),
        ("Find jobs for React.", "job", "search_jobs"),
        ("Which companies are hiring Python developers?", "job", "search_jobs"),
        ("Show market snapshot for Docker.", "market", "retrieve_snapshot"),
    ],
)
def test_mocked_questions_route_from_auto_without_selected_domain(
    offline_planner, message, expected_domain, expected_intent
):
    request = IntelligencePlanRequest(message=message, domain="auto")
    plan = offline_planner.create_plan(request)
    assert plan.intent == expected_intent
    assert infer_assistant_domain(plan.intent) == expected_domain


def _posting_fact():
    return SimpleNamespace(
        fact_type="collected_posting_skills_summary",
        metric_value=114,
        details={
            "skill_counts": [{
                "skill": "Python", "count": 28, "company_count": 5,
                "verdict": "High", "share": 28 / 114, "limited_evidence": False,
            }]
        },
    )


def test_mocked_posting_answer_has_sample_verdict_and_disclosures_without_trend_claim():
    block = build_answer_block(
        intent="aggregate_posting_skills",
        user_message="Python hiring demand in collected postings",
        answer="Python was mentioned in the stored job sample.",
        facts=[_posting_fact()],
    )
    assert block["verdict"] == "Python — High demand in collected postings (28 of 114)"
    assert "trend" not in block["verdict"].casefold()
    assert block["summary"].startswith("Current snapshot only.")
    assert "all stored India postings" in block["footer"]["disclosures"][0]
    assert "firestore_request_reads" not in str(block)


def test_mocked_ui_ux_uses_calibrated_not_enough_data_verdict():
    fact = SimpleNamespace(
        fact_type="collected_posting_skills_summary",
        metric_value=114,
        details={
            "skill_counts": [{
                "skill": "UI/UX", "count": 1, "company_count": 1,
                "verdict": "Not enough data", "share": 1 / 114,
                "limited_evidence": False,
            }]
        },
    )
    block = build_answer_block(
        intent="aggregate_posting_skills",
        user_message="UI/UX trends",
        answer="One collected posting mentions UI/UX.",
        facts=[fact],
    )
    assert block["verdict"] == "UI/UX — Not enough data (1 of 114)"
    assert "trend" not in block["verdict"].casefold()


def test_mocked_both_signals_are_separate_and_named_in_the_first_line():
    adoption = SimpleNamespace(
        fact_type="skill_adoption_signal",
        entity_name="Python",
        details={"signal_type": "adoption", "adoption_label": "Rising"},
    )
    block = build_answer_block(
        intent="aggregate_posting_skills",
        user_message="Python hiring demand and developer adoption",
        answer="Python has collected posting evidence.",
        facts=[_posting_fact(), adoption],
    )
    assert block["verdict"] == (
        "Python — High demand in collected postings (28 of 114); developer adoption rising"
    )
    assert block["table"]["rows"] == [
        {"Signal": "Collected postings — hiring demand", "Result": "High"},
        {"Signal": "Developer adoption, not hiring demand", "Result": "Rising"},
    ]
    assert "Developer adoption measures developer activity, not hiring demand." in block["footer"]["disclosures"]
    assert all("demand" not in str(row["Result"]).casefold() for row in block["table"]["rows"][1:])


def test_mocked_adoption_only_answer_is_labelled_without_demand_bands():
    adoption = SimpleNamespace(
        fact_type="developer_activity_trend",
        entity_name="Python",
        details={"signal_type": "adoption", "adoption_label": "Growing slowly"},
    )
    block = build_answer_block(
        intent="analyze_trend",
        user_message="Python developer adoption",
        answer="Historical GitHub activity grew.",
        facts=[adoption],
    )
    assert block["verdict"] == "Python — Developer adoption, not hiring demand: Growing slowly"
    assert block["table"]["rows"] == [
        {"Signal": "Developer adoption, not hiring demand", "Result": "Growing slowly"}
    ]
    assert not any(word in str(block).casefold() for word in ("high demand", "low demand"))


def test_mocked_flat_or_declining_adoption_states_direction():
    adoption = SimpleNamespace(
        fact_type="developer_activity_trend",
        entity_name="Python",
        details={
            "signal_type": "adoption", "adoption_label": "Flat or declining",
            "adoption_direction": "down", "adoption_growth": -0.12,
        },
    )
    block = build_answer_block(
        intent="analyze_trend", user_message="Python adoption trend",
        answer="Historical GitHub activity declined.", facts=[adoption],
    )
    assert block["table"]["rows"][0]["Result"] == "Flat or declining (decreased 12.0%)"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1, 2, 3], "Not enough data"),
        ([100, 100, 125, 125], "Rising"),
        ([100, 100, 106, 106], "Growing slowly"),
        ([100, 100, 90, 90], "Flat or declining"),
    ],
)
def test_mocked_adoption_uses_growth_labels_not_demand_bands(values, expected):
    result = classify_adoption_growth(values)
    assert result["level"] == expected
    assert result["level"] not in {"High", "Moderate", "Low"}


def test_mocked_snapshot_caveat_is_in_footer():
    block = build_answer_block(
        intent="retrieve_snapshot",
        user_message="Market snapshot",
        answer="Market Intelligence Snapshot (2026-Q1): quarterly developer-adoption records are available; this is not hiring demand.",
        facts=[],
        evidence=[SimpleNamespace(source="GitHub Innovation Graph", description="Quarterly developer activity; not hiring demand.")],
    )
    assert "not hiring demand" not in block["summary"].casefold()
    assert any("not hiring demand" in item.casefold() for item in block["footer"]["disclosures"])

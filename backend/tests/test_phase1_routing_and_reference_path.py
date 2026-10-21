from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.intelligence_v2.capability_registry import LEGACY_CAPABILITY_MAP, canonical_capability_id
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.intelligence_v2.orchestrator import V2Orchestrator
from app.models.auth import AuthenticatedUser
from app.models.execution_orchestrator import CoreIntelligenceAnswerRequest
from app.storage.market_store import MarketDataStore
from app.storage.reference_store import ReferenceDataStore


EXPECTED_FRONTEND_ROUTES = {
    ("skill", "trend_velocity_analysis"): "skill_demand_trends",
    ("skill", "historical_signal_retrieval"): "skill_historical_signals",
    ("skill", "skill_gap_role_fit"): "skill_role_alignment",
    ("skill", "evidence_provenance_retrieval"): "skill_evidence_citations",
    ("skill", "skill_technology_reference"): "skill_reference_profile",
    ("skill", "action_recommendations"): "skill_action_recommendations",
    ("market", "market_snapshot"): "market_intelligence_snapshot",
    ("market", "historical_signal_retrieval"): "market_tech_signals",
    ("market", "trend_velocity_analysis"): "market_trend_velocity",
    ("market", "evidence_provenance_retrieval"): "market_evidence_citations",
    ("job", "job_posting_search"): "job_verified_postings",
    ("job", "occupation_software_skills"): "job_role_requirements",
    ("job", "related_occupations"): "job_mobility_pathways",
    ("job", "skill_gap_role_fit"): "job_profile_alignment",
    ("job", "action_recommendations"): "job_preparation_actions",
}


def test_all_frontend_feature_ids_have_domain_specific_v2_routes():
    assert LEGACY_CAPABILITY_MAP == EXPECTED_FRONTEND_ROUTES
    for (domain, legacy_id), canonical_id in EXPECTED_FRONTEND_ROUTES.items():
        assert canonical_capability_id(legacy_id, domain) == canonical_id


@pytest.mark.parametrize("domain", ["skill", "market", "job"])
def test_legacy_ids_do_not_cross_route_domains(domain):
    target = EXPECTED_FRONTEND_ROUTES.get((domain, "action_recommendations"))
    assert canonical_capability_id("action_recommendations", domain) == (target or "action_recommendations")


def test_unrecognized_feature_is_not_mapped_to_snapshot():
    assert canonical_capability_id("made_up_feature", "skill") == "made_up_feature"


def test_unknown_feature_returns_unsupported_without_snapshot_fallback():
    class NoopConversations:
        pass

    store = ReferenceDataStore(read_only=True)
    orchestrator = V2Orchestrator(store=store, conversation_store=NoopConversations())
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="test unsupported capability", domain="skill", capability_id="made_up_feature"
    ))
    assert response.execution_status == "unsupported"
    assert response.reason_codes == ["CAPABILITY_UNSUPPORTED"]
    assert "Unsupported capability" in response.answer


@pytest.mark.parametrize(
    ("domain", "legacy_id", "canonical_id", "engine", "handler"),
    [
        ("skill", "trend_velocity_analysis", "skill_demand_trends", "skill_engine", "run_demand_trends"),
        ("skill", "historical_signal_retrieval", "skill_historical_signals", "skill_engine", "run_historical_signals"),
        ("skill", "skill_gap_role_fit", "skill_role_alignment", "skill_engine", "run_role_alignment"),
        ("skill", "evidence_provenance_retrieval", "skill_evidence_citations", "skill_engine", "run_evidence_citations"),
        ("skill", "skill_technology_reference", "skill_reference_profile", "skill_engine", "run_reference_profile"),
        ("skill", "action_recommendations", "skill_action_recommendations", "skill_engine", "run_action_recommendations"),
        ("market", "market_snapshot", "market_intelligence_snapshot", "market_engine", "run_snapshot"),
        ("market", "historical_signal_retrieval", "market_tech_signals", "market_engine", "run_tech_signals"),
        ("market", "trend_velocity_analysis", "market_trend_velocity", "market_engine", "run_trend_velocity"),
        ("market", "evidence_provenance_retrieval", "market_evidence_citations", "market_engine", "run_evidence_citations"),
        ("job", "job_posting_search", "job_verified_postings", "job_engine", "run_verified_postings"),
        ("job", "occupation_software_skills", "job_role_requirements", "job_engine", "run_role_requirements"),
        ("job", "related_occupations", "job_mobility_pathways", "job_engine", "run_mobility_pathways"),
        ("job", "skill_gap_role_fit", "job_profile_alignment", "job_engine", "run_profile_alignment"),
        ("job", "action_recommendations", "job_preparation_actions", "job_engine", "run_preparation_actions"),
    ],
)
def test_frontend_feature_reaches_its_v2_handler(monkeypatch, domain, legacy_id, canonical_id, engine, handler):
    class NoopConversations:
        pass

    orchestrator = V2Orchestrator(store=ReferenceDataStore(read_only=True), conversation_store=NoopConversations())
    monkeypatch.setattr(
        orchestrator.capability_registry,
        "evaluate_readiness",
        lambda *args, **kwargs: SimpleNamespace(is_executable=True, state="ready", reason="test"),
    )
    reached = []

    def handler_spy(*args, **kwargs):
        reached.append(canonical_id)
        return SimpleNamespace(capability_id=canonical_id, headline="test handler reached", facts=[], evidence=[])

    monkeypatch.setattr(getattr(orchestrator, engine), handler, handler_spy)
    request = CoreIntelligenceAnswerRequest(
        message="bounded offline route test", domain=domain, capability_id=legacy_id,
        target_role="Software Developer", selected_skills=["Python"],
    )
    response = orchestrator.execute_request(request, AuthenticatedUser(uid="offline-route-test"))
    assert reached == [canonical_id]
    assert response.domain == domain


def test_unselected_direct_question_reaches_planned_v2_handler(monkeypatch):
    class NoopConversations:
        pass

    orchestrator = V2Orchestrator(store=ReferenceDataStore(read_only=True), conversation_store=NoopConversations())
    monkeypatch.setattr(
        orchestrator.capability_registry,
        "evaluate_readiness",
        lambda *args, **kwargs: SimpleNamespace(is_executable=True, state="ready", reason="test"),
    )
    reached = []

    def history_handler(*args, **kwargs):
        reached.append(True)
        return SimpleNamespace(capability_id="skill_historical_signals", headline="History handler reached", facts=[], evidence=[])

    monkeypatch.setattr(orchestrator.skill_engine, "run_historical_signals", history_handler)
    response = orchestrator.execute_request(CoreIntelligenceAnswerRequest(
        message="show historical skill signals for Python", domain="skill"
    ))
    assert reached == [True]
    assert response.intent == "skill_historical_signals"


def test_reference_database_default_points_to_backend_data_without_changing_market_path():
    settings = Settings.model_construct(skill_intelligence_db_path="data/skill_intelligence.sqlite3")
    root = Path(__file__).resolve().parents[2]
    assert settings.reference_database_path == root / "backend" / "data" / "skill_intelligence.sqlite3"
    assert settings.database_path == root / "data" / "skill_intelligence.sqlite3"


def test_read_only_reference_store_fails_clearly_when_database_missing(tmp_path):
    missing_path = tmp_path / "not-created.sqlite3"
    with pytest.raises(FileNotFoundError, match="Reference database not found"):
        ReferenceDataStore(missing_path, read_only=True)
    assert not missing_path.exists()


def test_hiring_evidence_uses_market_observation_schema_and_demand_family(tmp_path):
    db_path = tmp_path / "observations.sqlite3"
    MarketDataStore(db_path)
    with __import__("sqlite3").connect(db_path) as conn:
        base = ("jsearch", "demand", "2026-01", "India", "country", "Python", 1.0)
        conn.execute(
            """INSERT INTO market_observations
               (id, source, signal_type, observed_at, period, location, scope, skill, value,
                metadata_json, history_type, data_origin)
               VALUES (?, ?, ?, '2026-01-31T00:00:00Z', ?, ?, ?, ?, ?, '{}', 'platform_collected', 'real')""",
            ("demand-1", *base),
        )
        conn.execute(
            """INSERT INTO market_observations
               (id, source, signal_type, observed_at, period, location, scope, skill, value,
                metadata_json, history_type, data_origin)
               VALUES ('adoption-1', 'github', 'adoption', '2026-01-31T00:00:00Z',
                       '2026-01', 'India', 'country', 'Python', 99, '{}', 'backfill', 'real')"""
        )
    evidence = V2EvidenceRetriever(ReferenceDataStore(db_path, read_only=True)).get_hiring_demand_evidence("Python")
    assert evidence[0].sample_size == 1
    assert evidence[0].signal_family == "hiring_demand"

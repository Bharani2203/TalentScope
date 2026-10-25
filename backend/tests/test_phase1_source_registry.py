"""Comprehensive unit and API test suite for Phase 1 Data Foundation & Source Registry.

Covers:
1. All 10 registered sources presence, schema, and completeness.
2. Reference-only vs time-series sources distinction.
3. Monthly vs quarterly granularity integrity checks.
4. Missing values vs genuine zero observation enforcement.
5. Failed collection vs successful zero-result collection distinction.
6. Provenance and validation status preservation.
7. Prevention of GitHub developer adoption from being labeled as hiring demand.
8. Prevention of mock/test observations from being labeled live-verified.
9. V2 Capability Registry mapping to backing data sources.
10. Fast API endpoints:
    - GET /api/v1/intelligence/sources
    - GET /api/v1/intelligence/sources?domain=skill
    - GET /api/v1/intelligence/sources/{source_id}
    - GET /api/v1/intelligence/guest/sources (public/guest)
    - 404 on invalid source
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.api import dependencies
from app.models.auth import AuthenticatedUser
from app.intelligence_v2.source_registry import (
    SOURCE_REGISTRY,
    SourceDefinition,
    SourceMetricDefinition,
    StandardizedObservation,
    V2SourceRegistry,
    DataIntegrityValidator,
    IntegrityViolationError,
)
from app.intelligence_v2.capability_registry import V2CapabilityRegistry

pytestmark = pytest.mark.usefixtures("injected_empty_firestore")


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

@pytest.fixture
def registry() -> V2SourceRegistry:
    from app.storage.mock_firestore_hub import MockFirestoreClient

    return V2SourceRegistry(client=MockFirestoreClient())


@pytest.fixture
def validator() -> DataIntegrityValidator:
    return DataIntegrityValidator()


@pytest.fixture
def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="phase1_test_user",
        email="phase1@talentscope.ai",
        role="individual",
        company_id=None,
    )


def make_obs(
    observation_id: str = "obs-001",
    source_id: str = "github_innovation_graph",
    signal_family: str = "developer_adoption",
    canonical_skill_id: str | None = "python",
    geographic_scope: str = "global",
    observation_period: str = "2026-Q1",
    time_granularity: str = "quarterly",
    metric_name: str = "repo_push_count",
    metric_value: float = 100.0,
    unit: str = "pushes",
    denominator: float | None = None,
    denominator_unit: str | None = None,
    normalization_method: str | None = None,
    collected_at: datetime | None = None,
    source_freshness: str = "fresh",
    data_origin: str = "real",
    history_type: str = "platform_collected",
    provenance_status: str = "verified_local_dataset",
    validation_status: str = "valid",
    collection_run_status: str = "success",
) -> StandardizedObservation:
    return StandardizedObservation(
        observation_id=observation_id,
        source_id=source_id,
        signal_family=signal_family,
        canonical_skill_id=canonical_skill_id,
        geographic_scope=geographic_scope,
        observation_period=observation_period,
        time_granularity=time_granularity,
        metric_name=metric_name,
        metric_value=metric_value,
        unit=unit,
        denominator=denominator,
        denominator_unit=denominator_unit,
        normalization_method=normalization_method,
        collected_at=collected_at or datetime.now(timezone.utc),
        source_freshness=source_freshness,
        data_origin=data_origin,
        history_type=history_type,
        provenance_status=provenance_status,
        validation_status=validation_status,
        collection_run_status=collection_run_status,
    )


# =============================================================================
# 1. SOURCE REGISTRY COMPLETENESS & METADATA
# =============================================================================

def test_source_registry_contains_all_ten_sources(registry: V2SourceRegistry):
    expected_sources = {
        "onet",
        "esco",
        "github_innovation_graph",
        "jsearch",
        "adzuna",
        "stack_exchange",
        "wikipedia",
        "user_profile",
        "company_workforce",
        "job_sdf",
    }
    registered_keys = set(SOURCE_REGISTRY.keys())
    assert expected_sources.issubset(registered_keys), f"Missing sources: {expected_sources - registered_keys}"
    assert len(registered_keys) >= 10


def test_every_source_has_complete_required_metadata(registry: V2SourceRegistry):
    sources = registry.list_sources()
    for src in sources:
        assert src.source_id, "Source must have a non-empty source_id"
        assert src.display_name, f"Source {src.source_id} missing display_name"
        assert len(src.domains) > 0, f"Source {src.source_id} must have at least one domain"
        assert src.primary_signal_family in {
            "reference_taxonomy",
            "developer_adoption",
            "hiring_demand",
            "community_interest",
            "public_attention",
            "benchmark",
        }, f"Invalid primary signal family for {src.source_id}"
        assert src.geographic_coverage, f"Source {src.source_id} missing geographic_coverage"
        assert src.supported_time_granularity in {"reference_only", "quarterly", "monthly", "snapshot"}
        assert src.collection_method, f"Source {src.source_id} missing collection_method"
        assert src.collection_status in {"active", "ready", "empty", "quarantined", "disabled_in_local_mode", "provisional", "unverified"}
        assert src.provenance_status in {"verified_local_dataset", "verified_platform", "unverified", "academic_benchmark_only"}
        assert len(src.explicit_limitations) > 0, f"Source {src.source_id} must document explicit limitations"
        assert len(src.permitted_interpretations) > 0, f"Source {src.source_id} must document permitted interpretations"
        assert len(src.prohibited_interpretations) > 0, f"Source {src.source_id} must document prohibited interpretations"


def test_source_registry_catalog_summary(registry: V2SourceRegistry):
    catalog = registry.get_catalog()
    assert catalog["total_sources"] >= 10
    source_ids = {s["source_id"] for s in catalog["sources"]}
    assert "onet" in source_ids
    assert "github_innovation_graph" in source_ids
    assert "jsearch" in source_ids


def test_job_sources_refresh_counts_and_collection_state_from_firestore(monkeypatch):
    from types import SimpleNamespace
    from app.storage.mock_firestore_hub import MockFirestoreClient
    import app.intelligence_v2.source_registry as source_registry_module

    client = MockFirestoreClient()
    for index in range(3):
        client.collection("skill_market_signals").document(f"obs-{index}").set({
            "source": "jsearch" if index < 2 else "adzuna",
        })
    client.collection("jobs").document("job-j").set({"source": "jsearch"})
    client.collection("jobs").document("job-a").set({"source": "adzuna"})
    client.collection("fetch_runs").document("run-j").set({
        "run_id": "run-j", "source": "jsearch", "status": "success",
        "completed_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
    })
    monkeypatch.setattr(source_registry_module, "get_settings", lambda: SimpleNamespace(
        market_collection_enabled_providers=["jsearch", "adzuna"],
        jsearch_api_key="configured", adzuna_app_id="configured", adzuna_app_key="configured",
        environment="production",
    ))

    registry = V2SourceRegistry(client=client)
    jsearch = registry.get_source("jsearch")
    adzuna = registry.get_source("adzuna")
    assert (jsearch.observation_count, jsearch.job_posting_count) == (2, 1)
    assert jsearch.collection_status == "ready"
    assert jsearch.last_successful_collection == "2026-10-01T00:00:00+00:00"
    assert (adzuna.observation_count, adzuna.job_posting_count) == (1, 1)
    assert adzuna.collection_status == "ready"


# =============================================================================
# 2. REFERENCE-ONLY VS TIME-SERIES DISTINCTIONS
# =============================================================================

def test_onet_and_esco_are_reference_only(registry: V2SourceRegistry):
    onet = registry.get_source("onet")
    esco = registry.get_source("esco")

    assert onet is not None
    assert onet.primary_signal_family == "reference_taxonomy"
    assert onet.supported_time_granularity == "reference_only"
    assert onet.supports_historical_analysis is False

    assert esco is not None
    assert esco.primary_signal_family == "reference_taxonomy"
    assert esco.supported_time_granularity == "reference_only"
    assert esco.supports_historical_analysis is False


def test_github_and_job_portals_are_time_series(registry: V2SourceRegistry):
    gh = registry.get_source("github_innovation_graph")
    jsearch = registry.get_source("jsearch")
    adzuna = registry.get_source("adzuna")

    assert gh.supports_historical_analysis is True
    assert gh.supported_time_granularity == "quarterly"

    assert jsearch.supports_historical_analysis is True
    assert jsearch.supported_time_granularity == "monthly"

    assert adzuna.supports_historical_analysis is True
    assert adzuna.supported_time_granularity == "monthly"


def test_job_sdf_is_quarantined_academic_benchmark(registry: V2SourceRegistry):
    job_sdf = registry.get_source("job_sdf")
    assert job_sdf is not None
    assert job_sdf.collection_status == "quarantined"
    assert job_sdf.provenance_status == "academic_benchmark_only"
    assert job_sdf.data_origin == "benchmark"
    assert any("China" in lim or "Chinese" in lim for lim in job_sdf.explicit_limitations)
    assert any("Indian" in p for p in job_sdf.prohibited_interpretations)


# =============================================================================
# 3. DOMAIN FILTERING AND SOURCE LOOKUPS
# =============================================================================

def test_list_sources_by_domain(registry: V2SourceRegistry):
    skill_sources = registry.list_sources(domain="skill_intelligence")
    market_sources = registry.list_sources(domain="market_intelligence")
    job_sources = registry.list_sources(domain="job_intelligence")

    skill_ids = {s.source_id for s in skill_sources}
    assert "onet" in skill_ids
    assert "esco" in skill_ids
    assert "github_innovation_graph" in skill_ids

    # Also test shorthand aliases
    shorthand_skill = registry.list_sources(domain="skill")
    assert len(shorthand_skill) == len(skill_sources)


def test_get_source_with_aliases(registry: V2SourceRegistry):
    assert registry.get_source("github") == registry.get_source("github_innovation_graph")
    assert registry.get_source("stackoverflow") == registry.get_source("stack_exchange")
    assert registry.get_source("wiki") == registry.get_source("wikipedia")
    assert registry.get_source("jobsdf") == registry.get_source("job_sdf")
    assert registry.get_source("nonexistent") is None


# =============================================================================
# 4. DATA INTEGRITY VALIDATOR — ALL 12 RULES
# =============================================================================

def test_rule_1_missing_value_not_coerced_to_zero(validator: DataIntegrityValidator):
    # Rule 1: None must not be converted to 0.0
    with pytest.raises(IntegrityViolationError, match="Missing value for 'hiring_demand_share' must not be coerced to zero"):
        validator.validate_no_zero_coercion(None, metric_name="hiring_demand_share")

    # Invalid non-numeric strings
    with pytest.raises(IntegrityViolationError, match="Invalid non-numeric value"):
        validator.validate_no_zero_coercion("N/A", metric_name="hiring_demand_share")

    # Valid genuine float (including genuine 0.0)
    assert validator.validate_no_zero_coercion(0.0) == 0.0
    assert validator.validate_no_zero_coercion(42.5) == 42.5


def test_rules_2_and_3_collection_run_status(validator: DataIntegrityValidator):
    # Rule 2: Failed collection cannot report zero-result
    with pytest.raises(IntegrityViolationError, match="A failed collection run must not be recorded as a successful zero-result run"):
        validator.validate_collection_run_status("failed", record_count=0)

    # Failed collection with error
    with pytest.raises(IntegrityViolationError, match="Collection run failed"):
        validator.validate_collection_run_status("error", record_count=5)

    # Rule 3: Zero results valid only when query scope is known
    with pytest.raises(IntegrityViolationError, match="Zero results are valid only when collection completed successfully and the query scope is known"):
        validator.validate_collection_run_status("success", record_count=0, query_scope=None)

    # Valid successful zero results with query scope
    validator.validate_collection_run_status("success", record_count=0, query_scope="Skill 'Fortran' in Bangalore, IN")


def test_rule_4_cannot_mix_monthly_and_quarterly(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="Monthly .* and quarterly .* observations must not be silently mixed"):
        validator.validate_time_granularity(["2025-12", "2026-Q1"])

    # Homogeneous periods pass
    assert validator.validate_time_granularity(["2025-10", "2025-11", "2025-12"]) == "monthly"
    assert validator.validate_time_granularity(["2025-Q1", "2025-Q2", "2025-Q3"]) == "quarterly"


def test_rule_5_cannot_mix_different_signal_families(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="Different signal families .* must not be combined into a single trend"):
        validator.validate_signal_family_separation(["developer_adoption", "hiring_demand"])

    # Homogeneous family passes
    assert validator.validate_signal_family_separation(["developer_adoption", "developer_adoption"]) == "developer_adoption"


def test_rule_6_snapshot_cannot_be_represented_as_historical(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="Current job-posting snapshots must not be represented as historical time series"):
        validator.validate_snapshot_as_historical("snapshot", is_historical_series=True)

    # Non-historical snapshot passes
    validator.validate_snapshot_as_historical("snapshot", is_historical_series=False)
    validator.validate_snapshot_as_historical("monthly", is_historical_series=True)


def test_rule_7_github_adoption_must_not_be_labelled_hiring_demand(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="GitHub adoption must not be labelled as hiring demand"):
        validator.validate_signal_labeling("github_innovation_graph", "hiring_demand")

    validator.validate_signal_labeling("github_innovation_graph", "developer_adoption")


def test_rule_8_stack_exchange_and_wikipedia_not_employer_demand(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="must not be labelled as employer hiring demand"):
        validator.validate_signal_labeling("stack_exchange", "hiring_demand")

    with pytest.raises(IntegrityViolationError, match="must not be labelled as employer hiring demand"):
        validator.validate_signal_labeling("wikipedia", "hiring_demand")

    validator.validate_signal_labeling("stack_exchange", "community_interest")
    validator.validate_signal_labeling("wikipedia", "general_knowledge")


def test_rule_9_onet_and_esco_not_employer_demand(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="O\\*NET/ESCO reference relationships must not automatically be presented as verified employer requirements"):
        validator.validate_signal_labeling("onet", "hiring_demand")

    with pytest.raises(IntegrityViolationError, match="O\\*NET/ESCO reference relationships must not automatically be presented as verified employer requirements"):
        validator.validate_signal_labeling("esco", "hiring_demand")

    validator.validate_signal_labeling("onet", "reference_taxonomy")
    validator.validate_signal_labeling("esco", "reference_taxonomy")


def test_rule_10_job_sdf_academic_benchmark_only(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="Job-SDF is an academic benchmark only"):
        validator.validate_signal_labeling("job_sdf", "hiring_demand")

    validator.validate_signal_labeling("job_sdf", "benchmark")


def test_rule_11_mock_test_cannot_be_labeled_verified_platform(validator: DataIntegrityValidator):
    with pytest.raises(IntegrityViolationError, match="Test fixtures, synthetic records, or mock observations must never be labelled as live-verified provider data"):
        validator.validate_provenance_truth("test", "verified_platform")

    with pytest.raises(IntegrityViolationError, match="Test fixtures, synthetic records, or mock observations must never be labelled as live-verified provider data"):
        validator.validate_provenance_truth("synthetic", "verified_platform")

    validator.validate_provenance_truth("real", "verified_platform")
    validator.validate_provenance_truth("real", "verified_local_dataset")


def test_rule_12_freshness_explicit(validator: DataIntegrityValidator):
    assert validator.validate_freshness_explicit(None) == "unavailable"
    assert validator.validate_freshness_explicit("unknown") == "unavailable"
    assert validator.validate_freshness_explicit("fresh") == "fresh"
    assert validator.validate_freshness_explicit("stale") == "stale"


# =============================================================================
# 5. STANDARDIZED OBSERVATION PIPELINE VALIDATION
# =============================================================================

def test_validate_observation_valid_instance(validator: DataIntegrityValidator):
    obs = make_obs(
        source_id="github_innovation_graph",
        signal_family="developer_adoption",
        observation_period="2026-Q1",
        time_granularity="quarterly",
    )
    assert validator.validate_observation(obs) is True


def test_validate_observation_rejects_invalid_signal_family(validator: DataIntegrityValidator):
    obs = make_obs(
        source_id="github_innovation_graph",
        signal_family="hiring_demand",  # Illegal
        observation_period="2026-Q1",
        time_granularity="quarterly",
    )
    with pytest.raises(IntegrityViolationError, match="Signal family 'hiring_demand' is not permitted for source 'github_innovation_graph'"):
        validator.validate_observation(obs)


def test_validate_observation_rejects_empty_geography(validator: DataIntegrityValidator):
    obs = make_obs(
        geographic_scope="",  # Missing geography
    )
    with pytest.raises(IntegrityViolationError, match="must specify a non-empty geographic_scope"):
        validator.validate_observation(obs)


def test_validate_observation_rejects_missing_denominator_on_share(validator: DataIntegrityValidator):
    obs = make_obs(
        metric_name="share_metric",
        denominator=None,
        denominator_unit="total_postings",  # Missing denominator value
    )
    with pytest.raises(IntegrityViolationError, match="specifies denominator_unit 'total_postings' but has no positive denominator"):
        validator.validate_observation(obs)


def test_validate_observation_series_checks_temporal_and_signal_consistency(validator: DataIntegrityValidator):
    obs1 = make_obs(observation_id="obs-1", observation_period="2025-Q3")
    obs2 = make_obs(observation_id="obs-2", observation_period="2025-Q4")
    assert validator.validate_observation_series([obs1, obs2]) is True

    # Mixing with monthly period should fail series check
    obs3 = make_obs(
        observation_id="obs-3",
        observation_period="2026-01",
        time_granularity="monthly",
    )
    with pytest.raises(IntegrityViolationError, match="Monthly .* and quarterly .* observations must not be silently mixed"):
        validator.validate_observation_series([obs1, obs2, obs3])


# =============================================================================
# 6. V2 CAPABILITY REGISTRY INTEGRATION
# =============================================================================

def test_v2_capabilities_mapped_to_backing_sources():
    cap_registry = V2CapabilityRegistry()
    capabilities = cap_registry.list_capabilities()

    for cap in capabilities:
        assert cap.primary_source_id is not None, f"Capability {cap.capability_id} must have a primary_source_id"
        assert cap.primary_source_id in SOURCE_REGISTRY, (
            f"Capability {cap.capability_id} mapped to unknown source '{cap.primary_source_id}'"
        )


def test_v2_source_registry_resolves_capabilities(registry: V2SourceRegistry):
    onet_src = registry.resolve_source_for_capability("skill_role_alignment")
    assert onet_src is not None
    assert onet_src.source_id == "onet"

    github_src = registry.resolve_source_for_capability("skill_demand_trends")
    assert github_src is not None
    assert github_src.source_id == "github_innovation_graph"

    jsearch_src = registry.resolve_source_for_capability("job_verified_postings")
    assert jsearch_src is not None
    assert jsearch_src.source_id == "jsearch"


# =============================================================================
# 7. FASTAPI ENDPOINTS INTEGRATION
# =============================================================================

def test_api_list_sources_authenticated(mock_auth_user: AuthenticatedUser):
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_auth_user
    client = TestClient(app)

    try:
        response = client.get("/api/v1/intelligence/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 10
        source_ids = {s["source_id"] for s in data}
        assert "onet" in source_ids
        assert "github_innovation_graph" in source_ids
        assert "jsearch" in source_ids
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_api_list_sources_with_domain_filter(mock_auth_user: AuthenticatedUser):
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_auth_user
    client = TestClient(app)

    try:
        response = client.get("/api/v1/intelligence/sources?domain=skill")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        for src in data:
            assert "skill_intelligence" in src["domains"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_api_get_individual_source_authenticated(mock_auth_user: AuthenticatedUser):
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_auth_user
    client = TestClient(app)

    try:
        response = client.get("/api/v1/intelligence/sources/github_innovation_graph")
        assert response.status_code == 200
        src = response.json()
        assert src["source_id"] == "github_innovation_graph"
        assert src["primary_signal_family"] == "developer_adoption"
        assert src["supported_time_granularity"] == "quarterly"
        assert "Developer ecosystem adoption" in src["permitted_interpretations"][0]
        assert len(src["explicit_limitations"]) > 0
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_api_get_source_not_found(mock_auth_user: AuthenticatedUser):
    app.dependency_overrides[dependencies.get_current_user] = lambda: mock_auth_user
    client = TestClient(app)

    try:
        response = client.get("/api/v1/intelligence/sources/non_existent_source")
        assert response.status_code == 404
        assert "not found in registry" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(dependencies.get_current_user, None)


def test_api_guest_sources_unauthenticated():
    # Public guest endpoint must succeed without any auth headers
    client = TestClient(app)
    response = client.get("/api/v1/intelligence/guest/sources")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    source_ids = {s["source_id"] for s in data}
    assert "onet" in source_ids
    assert "github_innovation_graph" in source_ids

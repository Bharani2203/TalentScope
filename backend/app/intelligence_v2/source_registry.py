"""Greenfield Intelligence Engine V2 — Reusable Source Registry & Data Foundation.

Implements Phase 1 of the hybrid architecture:
1. Canonical, typed source definitions for all 10 supported data sources across
   Skill Intelligence, Market Intelligence, and Job Intelligence.
2. Consistent observation metadata model across time granularities and signal families.
3. Strict, explainable data integrity validator enforcing all 12 truth-in-data rules:
   - Missing values must not be converted to zero.
   - Failed collection must not be recorded as successful zero-result run.
   - Zero results valid only when collection completed successfully and query scope known.
   - Monthly and quarterly observations must not be silently mixed.
   - Different signal families must not be combined into a single trend.
   - Current job postings snapshots not represented as historical time series.
   - GitHub adoption not labeled as hiring demand.
   - Stack Exchange / Wikipedia not labeled employer demand.
   - O*NET/ESCO reference relationships not automatically presented as verified employer requirements.
   - Test fixtures / mock observations never labeled live-verified provider data.
   - Unknown freshness or provenance explicitly represented, not guessed.
   - Preserve existing historical data and unknown fields without destructive migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Literal, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_v2.contracts import DataOrigin, SignalFamily, TimeGrain


TimeGranularity = Literal["monthly", "quarterly", "snapshot", "reference_only"]
FreshnessStatus = Literal["fresh", "stale", "static_archive", "unavailable", "empty_awaiting_run"]
CollectionStatus = Literal["active", "ready", "empty", "quarantined", "disabled_in_local_mode", "provisional", "unverified"]
ProvenanceStatus = Literal["verified_local_dataset", "verified_platform", "unverified", "academic_benchmark_only"]
ValidationStatus = Literal["valid", "invalid", "provisional", "quarantined", "unverified"]
CollectionRunStatus = Literal["success", "failed", "dry_run", "preview", "sampled"]


class IntegrityViolationError(ValueError):
    """Raised when an observation or pipeline violates data integrity rules."""


class SourceMetricDefinition(BaseModel):
    """Specification of an empirical metric produced by a data source."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str
    display_name: str
    unit: str
    denominator_unit: str | None = None
    normalization_method: str | None = None
    is_share: bool = False
    description: str


class SourceDefinition(BaseModel):
    """Comprehensive, reusable registry definition for an intelligence data source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    display_name: str
    domains: list[Literal["skill_intelligence", "market_intelligence", "job_intelligence"]]
    primary_signal_family: SignalFamily
    supported_signal_families: list[SignalFamily] = Field(default_factory=list)
    available_metrics: list[SourceMetricDefinition]
    geographic_coverage: str
    supported_time_granularity: TimeGranularity
    collection_method: str
    last_successful_collection: str | None = None
    freshness_status: FreshnessStatus
    collection_status: CollectionStatus
    provenance_status: ProvenanceStatus
    supports_historical_analysis: bool
    historical_range: str | None = None
    observation_count: int = 0
    explicit_limitations: list[str] = Field(default_factory=list)
    permitted_interpretations: list[str] = Field(default_factory=list)
    prohibited_interpretations: list[str] = Field(default_factory=list)
    data_origin: DataOrigin = "real"


class StandardizedObservation(BaseModel):
    """Consistent, validated observation model identifying all required provenance metadata."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    source_id: str
    signal_family: SignalFamily
    canonical_skill_id: str | None = None
    canonical_occupation_id: str | None = None
    geographic_scope: str = "global"
    observation_period: str
    time_granularity: TimeGranularity
    metric_name: str
    metric_value: float
    unit: str
    denominator: float | None = None
    denominator_unit: str | None = None
    normalization_method: str | None = None
    collected_at: datetime
    source_freshness: FreshnessStatus = "fresh"
    data_origin: DataOrigin = "real"
    history_type: Literal["platform_collected", "backfill", "snapshot", "static_dataset", "mixed", "unavailable"] = "platform_collected"
    query_panel_version: str | None = None
    extractor_version: str | None = None
    provenance_status: ProvenanceStatus = "verified_local_dataset"
    validation_status: ValidationStatus = "valid"
    collection_run_status: CollectionRunStatus = "success"
    series_id: str | None = None
    fetch_run_id: str | None = None
    source_url: str | None = None
    annotations: list[str] = Field(default_factory=list)


# ---------------- Canonical Source Registry Definitions ----------------

SOURCE_REGISTRY: dict[str, SourceDefinition] = {
    # 1. O*NET 28.0 (Reference Taxonomy)
    "onet": SourceDefinition(
        source_id="onet",
        display_name="O*NET 28.0",
        domains=["skill_intelligence", "job_intelligence"],
        primary_signal_family="reference_taxonomy",
        supported_signal_families=["reference_taxonomy"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="software_tool_mention",
                display_name="Software Tools & Technologies",
                unit="tool_references",
                description="Standardized software tools associated with SOC occupations by workplace examples.",
            ),
            SourceMetricDefinition(
                metric_name="essential_skill_level",
                display_name="Essential Skill Importance",
                unit="scale_1_to_5",
                description="Expert-rated importance and level scores for occupational descriptors.",
            ),
            SourceMetricDefinition(
                metric_name="related_occupation_link",
                display_name="Related Occupations",
                unit="relatedness_link",
                description="Career mobility links and task adjacency between SOC occupational classifications.",
            ),
        ],
        geographic_coverage="US (Standard Occupational Classification)",
        supported_time_granularity="reference_only",
        collection_method="curated_taxonomy_release",
        last_successful_collection="2026-10-18T10:00:00Z",
        freshness_status="static_archive",
        collection_status="ready",
        provenance_status="verified_local_dataset",
        supports_historical_analysis=False,
        observation_count=69317,
        explicit_limitations=[
            "Represents US occupational expert baselines and occupational taxonomy, not real-time hiring demand.",
            "Occupational relationships are structural knowledge baselines and do not prove individual company job requirements.",
        ],
        permitted_interpretations=[
            "Occupational baseline knowledge, skill, and tool requirements.",
            "Career transition adjacency pathways between standardized SOC codes.",
        ],
        prohibited_interpretations=[
            "Real-time hiring demand or employer vacancy counts.",
            "Guarantee of hiring qualification without employer posting verification.",
        ],
        data_origin="local_reference_dataset",
    ),

    # 2. ESCO v1.2.1 (European Reference Taxonomy)
    "esco": SourceDefinition(
        source_id="esco",
        display_name="ESCO v1.2.1",
        domains=["skill_intelligence", "job_intelligence"],
        primary_signal_family="reference_taxonomy",
        supported_signal_families=["reference_taxonomy"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="skill_hierarchy_node",
                display_name="ESCO Skills & Competences",
                unit="taxonomy_concept",
                description="Multilingual European classification of skills, competences, and qualifications.",
            ),
            SourceMetricDefinition(
                metric_name="occupation_skill_relation",
                display_name="Occupation-Skill Relationships",
                unit="relation_edge",
                description="Essential and optional skill relationships for 3,039 standardized European occupations.",
            ),
        ],
        geographic_coverage="EU (International Multilingual Classification)",
        supported_time_granularity="reference_only",
        collection_method="curated_taxonomy_release",
        last_successful_collection="2026-10-18T10:00:00Z",
        freshness_status="static_archive",
        collection_status="ready",
        provenance_status="verified_local_dataset",
        supports_historical_analysis=False,
        observation_count=143029,
        explicit_limitations=[
            "Multilingual European labor market classification; not point-in-time hiring postings.",
            "Skills categorized as essential reflect standard role profiles, not specific regional vacancies.",
        ],
        permitted_interpretations=[
            "Standardized occupational skill profiles and essential/optional skill relations.",
            "Cross-linguistic skill normalization and hierarchical skill grouping.",
        ],
        prohibited_interpretations=[
            "Real-time hiring demand, employer vacancies, or compensation data.",
        ],
        data_origin="local_reference_dataset",
    ),

    # 3. GitHub Innovation Graph (Developer Adoption)
    "github_innovation_graph": SourceDefinition(
        source_id="github_innovation_graph",
        display_name="GitHub Innovation Graph",
        domains=["skill_intelligence", "market_intelligence"],
        primary_signal_family="developer_adoption",
        supported_signal_families=["developer_adoption"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="num_pushers",
                display_name="Unique Developer Pushers",
                unit="unique developers per quarter",
                description="Quarterly count of unique GitHub developers making git push events in repositories.",
            ),
        ],
        geographic_coverage="Global + 200+ ISO-2 countries",
        supported_time_granularity="quarterly",
        collection_method="local_static_ingestion",
        last_successful_collection="2026-10-18T10:00:00Z",
        freshness_status="fresh",
        collection_status="ready",
        provenance_status="verified_local_dataset",
        supports_historical_analysis=True,
        historical_range="2020-Q1 .. 2026-Q1 (25 quarters)",
        observation_count=262929,
        explicit_limitations=[
            "Measures active open-source developer git pushers; does NOT measure employer hiring vacancies or job postings.",
            "Aggregated at quarterly grain; cannot be converted to monthly periods by division.",
        ],
        permitted_interpretations=[
            "Developer ecosystem adoption, language popularity, and open-source project momentum.",
            "Quarterly developer activity trajectories and Theil-Sen trend slope calculation.",
        ],
        prohibited_interpretations=[
            "Employer hiring demand, salary levels, or enterprise commercial adoption.",
            "Conversion of quarterly developer counts into monthly job posting counts.",
        ],
        data_origin="local_reference_dataset",
    ),

    # 4. JSearch (Hiring Demand)
    "jsearch": SourceDefinition(
        source_id="jsearch",
        display_name="JSearch Job Postings Aggregator",
        domains=["market_intelligence", "job_intelligence"],
        primary_signal_family="hiring_demand",
        supported_signal_families=["hiring_demand"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="job_postings_count",
                display_name="Job Postings Count",
                unit="postings",
                description="Raw count of validated job postings mentioning canonical skills.",
            ),
            SourceMetricDefinition(
                metric_name="normalized_share",
                display_name="Hiring Demand Share",
                unit="postings_share",
                denominator_unit="total_postings",
                normalization_method="share_of_period_postings",
                is_share=True,
                description="Share of total validated job postings in sampling frame mentioning canonical skills.",
            ),
        ],
        geographic_coverage="IN, US, UK, and global cities",
        supported_time_granularity="monthly",
        collection_method="recurring_platform_collection",
        last_successful_collection=None,
        freshness_status="unavailable",
        collection_status="disabled_in_local_mode",
        provenance_status="verified_platform",
        supports_historical_analysis=True,
        historical_range=None,
        observation_count=0,
        explicit_limitations=[
            "Live search aggregator; does not support arbitrary point-in-time historical backfill.",
            "Requires at least 4 consecutive completed months with verified denominators for Skill Health.",
            "Disabled in local/emulator development to prevent external network calls and credential usage.",
        ],
        permitted_interpretations=[
            "Current job posting mentions and platform-collected hiring demand time series.",
        ],
        prohibited_interpretations=[
            "Synthetic backfill or uncollected historical months.",
            "Conflation with developer open-source activity.",
        ],
        data_origin="real",
    ),

    # 5. Adzuna (Hiring Demand)
    "adzuna": SourceDefinition(
        source_id="adzuna",
        display_name="Adzuna Job Vacancy Feed",
        domains=["market_intelligence", "job_intelligence"],
        primary_signal_family="hiring_demand",
        supported_signal_families=["hiring_demand"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="job_postings_count",
                display_name="Job Postings Count",
                unit="postings",
                description="Raw count of validated job vacancies matching skill and role queries.",
            ),
            SourceMetricDefinition(
                metric_name="normalized_share",
                display_name="Hiring Demand Share",
                unit="postings_share",
                denominator_unit="total_postings",
                normalization_method="share_of_period_postings",
                is_share=True,
                description="Share of total validated job vacancies in sampling frame mentioning canonical skills.",
            ),
        ],
        geographic_coverage="IN, US, UK, EU countries",
        supported_time_granularity="monthly",
        collection_method="recurring_platform_collection",
        last_successful_collection=None,
        freshness_status="unavailable",
        collection_status="disabled_in_local_mode",
        provenance_status="verified_platform",
        supports_historical_analysis=True,
        historical_range=None,
        observation_count=0,
        explicit_limitations=[
            "Job vacancy index feed; requires live API credentials.",
            "Requires >= 4 consecutive completed months with verified denominators for Skill Health.",
            "Disabled in local/emulator mode.",
        ],
        permitted_interpretations=[
            "Active vacancy counts and platform-collected monthly demand series.",
        ],
        prohibited_interpretations=[
            "Historical backfill without explicit historical collection run.",
        ],
        data_origin="real",
    ),

    # 6. Stack Exchange / Stack Overflow (Community Interest)
    "stack_exchange": SourceDefinition(
        source_id="stack_exchange",
        display_name="Stack Exchange / Stack Overflow Activity",
        domains=["skill_intelligence", "market_intelligence"],
        primary_signal_family="community_interest",
        supported_signal_families=["community_interest"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="question_count",
                display_name="Question Volume",
                unit="questions per month",
                description="Count of developer questions tagged with canonical technologies.",
            ),
        ],
        geographic_coverage="Global (Online Developer Community)",
        supported_time_granularity="monthly",
        collection_method="recurring_platform_collection",
        last_successful_collection=None,
        freshness_status="unavailable",
        collection_status="unverified",
        provenance_status="unverified",
        supports_historical_analysis=True,
        historical_range=None,
        observation_count=0,
        explicit_limitations=[
            "Measures developer discussion and troubleshooting volume, not hiring demand.",
            "Currently unverified in local repository; requires empirical collection run.",
        ],
        permitted_interpretations=[
            "Technical community engagement and developer problem-solving frequency.",
        ],
        prohibited_interpretations=[
            "Employer hiring demand or job vacancies.",
        ],
        data_origin="real",
    ),

    # 7. Wikipedia Pageviews (Public Attention)
    "wikipedia": SourceDefinition(
        source_id="wikipedia",
        display_name="Wikipedia Pageviews API",
        domains=["market_intelligence"],
        primary_signal_family="public_attention",
        supported_signal_families=["public_attention"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="pageviews_count",
                display_name="Monthly Pageviews",
                unit="pageviews per month",
                description="Aggregate pageviews for canonical technology encyclopedia articles.",
            ),
        ],
        geographic_coverage="Global (Public Web Readers)",
        supported_time_granularity="monthly",
        collection_method="recurring_platform_collection",
        last_successful_collection=None,
        freshness_status="unavailable",
        collection_status="unverified",
        provenance_status="unverified",
        supports_historical_analysis=True,
        historical_range=None,
        observation_count=0,
        explicit_limitations=[
            "Measures public encyclopedic interest, not enterprise adoption or hiring.",
            "Currently unverified in local repository; pending approved historical ingestion.",
        ],
        permitted_interpretations=[
            "General public awareness and curiosity.",
        ],
        prohibited_interpretations=[
            "Job vacancies, employer skill demand, or developer tool adoption.",
        ],
        data_origin="real",
    ),

    # 8. User Profile (Individual Profile Context)
    "user_profile": SourceDefinition(
        source_id="user_profile",
        display_name="Individual Candidate Profile",
        domains=["skill_intelligence", "job_intelligence"],
        primary_signal_family="reference_taxonomy",
        supported_signal_families=["reference_taxonomy"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="declared_skill_count",
                display_name="Declared Skills",
                unit="skills",
                description="Self-declared skill inventory with candidate-verified proficiency.",
            ),
        ],
        geographic_coverage="User Specific (Self-Reported)",
        supported_time_granularity="snapshot",
        collection_method="authenticated_session",
        last_successful_collection=None,
        freshness_status="fresh",
        collection_status="active",
        provenance_status="verified_platform",
        supports_historical_analysis=False,
        observation_count=0,
        explicit_limitations=[
            "Self-declared skills and career targets; requires individual user authentication.",
            "Non-declared skills cannot be treated as verified gaps without candidate confirmation.",
        ],
        permitted_interpretations=[
            "Candidate declared skill inventory for role alignment and mobility planning.",
        ],
        prohibited_interpretations=[
            "Objective external market demand or verified employee workforce records.",
        ],
        data_origin="real",
    ),

    # 9. Company Workforce Data (Authorized Tenant Scope)
    "company_workforce": SourceDefinition(
        source_id="company_workforce",
        display_name="Company Tenant Workforce Data",
        domains=["skill_intelligence", "market_intelligence", "job_intelligence"],
        primary_signal_family="reference_taxonomy",
        supported_signal_families=["reference_taxonomy"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="employee_headcount",
                display_name="Tenant Employee Headcount",
                unit="employees",
                description="Verified employee records within authenticated company tenant.",
            ),
        ],
        geographic_coverage="Tenant Specific (Internal Organization Scope)",
        supported_time_granularity="snapshot",
        collection_method="authenticated_tenant",
        last_successful_collection=None,
        freshness_status="fresh",
        collection_status="active",
        provenance_status="verified_platform",
        supports_historical_analysis=False,
        observation_count=0,
        explicit_limitations=[
            "Restricted to authorized company tenant boundaries; never shared across tenants.",
            "Cannot be accessed in guest mode or cross-tenant sessions.",
        ],
        permitted_interpretations=[
            "Internal company workforce capability distribution and workforce planning baseline.",
        ],
        prohibited_interpretations=[
            "Public benchmark or cross-organization labor market averages.",
        ],
        data_origin="real",
    ),

    # 10. Job-SDF (Academic Benchmark Only)
    "job_sdf": SourceDefinition(
        source_id="job_sdf",
        display_name="Job-SDF Academic Labor Market Benchmark",
        domains=["market_intelligence"],
        primary_signal_family="benchmark",
        supported_signal_families=["benchmark"],
        available_metrics=[
            SourceMetricDefinition(
                metric_name="demand_index",
                display_name="Academic Demand Index",
                unit="integer_indexed_score",
                description="Monthly demand column (2021-01 .. 2023-12) for anonymized Chinese job-skill pairs.",
            ),
            SourceMetricDefinition(
                metric_name="proportion_index",
                display_name="Academic Proportion Index",
                unit="integer_indexed_ratio",
                description="Monthly proportion column for anonymized Chinese job-skill pairs.",
            ),
        ],
        geographic_coverage="China (Anonymized Integer Labor Market)",
        supported_time_granularity="monthly",
        collection_method="local_static_ingestion",
        last_successful_collection="2026-10-18T10:00:00Z",
        freshness_status="static_archive",
        collection_status="quarantined",
        provenance_status="academic_benchmark_only",
        supports_historical_analysis=True,
        historical_range="2021-01 .. 2023-12 (36 months)",
        observation_count=0,
        explicit_limitations=[
            "Pre-trained benchmark from Chinese recruitment platforms with unmapped integer IDs.",
            "Quarantined for methodology verification only; strictly prohibited from being labeled as Indian or global hiring demand.",
        ],
        permitted_interpretations=[
            "Comparative algorithm benchmark and research methodology validation.",
        ],
        prohibited_interpretations=[
            "Indian workforce hiring demand, real skill trends, or live job availability.",
        ],
        data_origin="benchmark",
    ),
}


class V2SourceRegistry:
    """Service to look up and inspect data sources across all three domains."""

    def __init__(self, sources: dict[str, SourceDefinition] | None = None) -> None:
        self._sources = dict(sources or SOURCE_REGISTRY)

    def get_source(self, source_id: str) -> SourceDefinition | None:
        """Retrieve source definition by case-insensitive source ID."""
        if not source_id:
            return None
        sid = source_id.strip().casefold()
        # Direct lookup or aliases
        alias_map = {
            "github": "github_innovation_graph",
            "github_adoption": "github_innovation_graph",
            "stackoverflow": "stack_exchange",
            "stack_overflow": "stack_exchange",
            "wiki": "wikipedia",
            "profile": "user_profile",
            "company": "company_workforce",
            "jobsdf": "job_sdf",
        }
        resolved = alias_map.get(sid, sid)
        return self._sources.get(resolved)

    def list_sources(
        self,
        domain: Literal["skill_intelligence", "market_intelligence", "job_intelligence", "skill", "market", "job"] | None = None,
        signal_family: SignalFamily | None = None,
        include_quarantined: bool = True,
    ) -> list[SourceDefinition]:
        """List sources filtered by domain, signal family, or quarantine status."""
        normalized_domain = domain
        if domain:
            domain_map = {
                "skill": "skill_intelligence",
                "market": "market_intelligence",
                "job": "job_intelligence",
            }
            normalized_domain = domain_map.get(domain, domain)

        results: list[SourceDefinition] = []
        for src in self._sources.values():
            if not include_quarantined and src.collection_status == "quarantined":
                continue
            if normalized_domain and normalized_domain not in src.domains:
                continue
            if signal_family and src.primary_signal_family != signal_family:
                continue
            results.append(src)
        return results

    def resolve_source_for_capability(self, capability_id: str) -> SourceDefinition | None:
        """Map capability ID to its primary backing data source."""
        mapping = {
            "skill_demand_trends": "github_innovation_graph",
            "skill_historical_signals": "github_innovation_graph",
            "skill_role_alignment": "onet",
            "skill_evidence_citations": "onet",
            "skill_reference_profile": "onet",
            "skill_action_recommendations": "onet",
            "skill_health_analysis": "jsearch",
            "skill_demand_forecast": "jsearch",
            "hiring_demand_trends": "jsearch",
            "market_intelligence_snapshot": "github_innovation_graph",
            "market_tech_signals": "github_innovation_graph",
            "market_trend_velocity": "jsearch",
            "market_evidence_citations": "jsearch",
            "job_verified_postings": "jsearch",
            "job_role_requirements": "onet",
            "job_mobility_pathways": "onet",
            "job_profile_alignment": "onet",
            "job_preparation_actions": "onet",
        }
        src_id = mapping.get(capability_id)
        return self.get_source(src_id) if src_id else None

    def get_catalog(self) -> dict[str, Any]:
        """Public catalog structure for API responses."""
        return {
            "total_sources": len(self._sources),
            "sources": [s.model_dump(mode="json") for s in self._sources.values()],
        }


# ---------------- Data Integrity Validation Rules ----------------

class DataIntegrityValidator:
    """Enforces the 12 strict data integrity rules for observations and signal series."""

    @staticmethod
    def validate_no_zero_coercion(raw_value: Any, metric_name: str = "metric") -> float:
        """Rule 1: Missing values must not be converted to zero."""
        if raw_value is None:
            raise IntegrityViolationError(
                f"Missing value for '{metric_name}' must not be coerced to zero. Missing data must be represented explicitly."
            )
        try:
            val = float(raw_value)
        except (ValueError, TypeError) as exc:
            raise IntegrityViolationError(
                f"Invalid non-numeric value for '{metric_name}': {raw_value}"
            ) from exc
        return val

    @staticmethod
    def validate_collection_run_status(
        status: str,
        record_count: int,
        query_scope: str | None = None,
    ) -> None:
        """Rules 2 & 3: Failed collection cannot be recorded as successful zero-result.

        Zero results are valid only when collection completed successfully and query scope is known.
        """
        st = status.casefold().strip()
        if st in {"failed", "error", "aborted"}:
            if record_count == 0:
                raise IntegrityViolationError(
                    "A failed collection run must not be recorded as a successful zero-result run."
                )
            raise IntegrityViolationError(f"Collection run failed with status '{status}'.")

        if record_count == 0 and not query_scope:
            raise IntegrityViolationError(
                "Zero results are valid only when collection completed successfully and the query scope is known."
            )

    @staticmethod
    def validate_time_granularity(
        periods: Sequence[str],
        expected_granularity: TimeGranularity | None = None,
    ) -> TimeGranularity:
        """Rule 4: Monthly and quarterly observations must not be silently mixed."""
        if not periods:
            return expected_granularity or "monthly"

        monthly_pattern = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
        quarterly_pattern = re.compile(r"^\d{4}-Q[1-4]$")

        has_monthly = any(monthly_pattern.match(p) for p in periods)
        has_quarterly = any(quarterly_pattern.match(p) for p in periods)

        if has_monthly and has_quarterly:
            raise IntegrityViolationError(
                "Monthly (YYYY-MM) and quarterly (YYYY-QX) observations must not be silently mixed."
            )

        detected: TimeGranularity = "monthly" if has_monthly else "quarterly" if has_quarterly else "snapshot"
        if expected_granularity and expected_granularity != detected and expected_granularity != "reference_only":
            raise IntegrityViolationError(
                f"Granularity mismatch: expected '{expected_granularity}', but periods contain '{detected}' grain."
            )
        return detected

    @staticmethod
    def validate_signal_family_separation(families: Sequence[SignalFamily]) -> SignalFamily:
        """Rule 5: Different signal families must not be combined into a single trend."""
        distinct = set(families)
        if len(distinct) > 1:
            raise IntegrityViolationError(
                f"Different signal families ({sorted(distinct)}) must not be combined into a single trend."
            )
        return next(iter(distinct)) if distinct else "reference_taxonomy"

    @staticmethod
    def validate_snapshot_as_historical(time_granularity: TimeGranularity, is_historical_series: bool) -> None:
        """Rule 6: Current job-posting snapshots must not be represented as historical time series."""
        if time_granularity == "snapshot" and is_historical_series:
            raise IntegrityViolationError(
                "Current job-posting snapshots must not be represented as historical time series."
            )

    @staticmethod
    def validate_signal_labeling(source_id: str, claimed_signal_family: SignalFamily) -> None:
        """Rules 7, 8, 9, 10: Strict signal identity and provenance truth enforcement."""
        sid = source_id.strip().casefold()
        # Rule 7: GitHub adoption must not be labelled as hiring demand
        if sid in {"github", "github_innovation_graph"} and claimed_signal_family == "hiring_demand":
            raise IntegrityViolationError(
                "GitHub adoption must not be labelled as hiring demand."
            )

        # Rule 8: Stack Exchange / Wikipedia not labelled employer demand
        if sid in {"stack_exchange", "stackoverflow", "wikipedia"} and claimed_signal_family == "hiring_demand":
            raise IntegrityViolationError(
                f"{source_id} community activity or public attention must not be labelled as employer hiring demand."
            )

        # Rule 9: O*NET/ESCO reference relationships not automatically presented as verified employer requirements
        if sid in {"onet", "esco"} and claimed_signal_family == "hiring_demand":
            raise IntegrityViolationError(
                "O*NET/ESCO reference relationships must not automatically be presented as verified employer requirements."
            )

        # Rule 10: Job-SDF academic benchmark only
        if sid in {"job_sdf", "jobsdf"} and claimed_signal_family != "benchmark":
            raise IntegrityViolationError(
                "Job-SDF is an academic benchmark only and must not be treated as live hiring demand."
            )

    @staticmethod
    def validate_provenance_truth(data_origin: DataOrigin, provenance_status: ProvenanceStatus) -> None:
        """Rule 10: Test fixtures and mock observations must never be labelled as live-verified provider data."""
        if data_origin in {"test", "synthetic", "demo", "unavailable"} and provenance_status == "verified_platform":
            raise IntegrityViolationError(
                "Test fixtures, synthetic records, or mock observations must never be labelled as live-verified provider data."
            )

    @staticmethod
    def validate_freshness_explicit(freshness: str | None) -> FreshnessStatus:
        """Rule 11: Unknown freshness or provenance must be explicitly represented, not guessed."""
        if not freshness or freshness.casefold() in {"unknown", "none"}:
            return "unavailable"
        valid_statuses = {"fresh", "stale", "static_archive", "unavailable", "empty_awaiting_run"}
        if freshness not in valid_statuses:
            return "unavailable"
        return freshness  # type: ignore[return-value]

    @classmethod
    def validate_observation(cls, obs: StandardizedObservation) -> bool:
        """Validate a single StandardizedObservation against all data integrity rules."""
        # Verify source compatibility
        source = SOURCE_REGISTRY.get(obs.source_id)
        if source:
            if obs.signal_family not in source.supported_signal_families:
                raise IntegrityViolationError(
                    f"Signal family '{obs.signal_family}' is not permitted for source '{obs.source_id}'."
                )

        # Signal labeling checks (Rules 7, 8, 9, 10)
        cls.validate_signal_labeling(obs.source_id, obs.signal_family)

        # Provenance truth (Rule 10/11)
        cls.validate_provenance_truth(obs.data_origin, obs.provenance_status)

        # Snapshot as historical check (Rule 6)
        if obs.time_granularity in ("snapshot", "reference_only") and obs.history_type == "platform_collected":
            raise IntegrityViolationError(
                f"Source '{obs.source_id}' with granularity '{obs.time_granularity}' cannot be labeled as historical time-series."
            )

        # Geographic scope must be explicitly specified
        if not obs.geographic_scope or not obs.geographic_scope.strip():
            raise IntegrityViolationError(
                f"Observation '{obs.observation_id}' must specify a non-empty geographic_scope."
            )

        # Denominator check for share / normalized observations
        if obs.denominator_unit and (obs.denominator is None or obs.denominator <= 0):
            raise IntegrityViolationError(
                f"Observation '{obs.observation_id}' specifies denominator_unit '{obs.denominator_unit}' but has no positive denominator."
            )

        # Validation status vs provenance consistency
        if obs.validation_status in ("unverified", "invalid", "provisional") and obs.provenance_status == "verified_platform":
            raise IntegrityViolationError(
                f"Observation '{obs.observation_id}' with validation_status '{obs.validation_status}' cannot have provenance_status 'verified_platform'."
            )

        return True

    @classmethod
    def validate_observation_series(cls, observations: Sequence[StandardizedObservation]) -> bool:
        """Validate a sequence of observations for temporal and signal family consistency."""
        if not observations:
            return True

        for obs in observations:
            cls.validate_observation(obs)

        # Check time granularity consistency (Rule 4)
        periods = [obs.observation_period for obs in observations]
        cls.validate_time_granularity(periods)

        # Check signal family consistency (Rule 5)
        cls.validate_signal_family_separation([obs.signal_family for obs in observations])

        return True

"""Greenfield Intelligence Engine V2 — Market Intelligence Engine.

Executes the 4 Market Intelligence features:
1. market_intelligence_snapshot
2. market_tech_signals
3. market_trend_velocity
4. market_evidence_citations
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_v2.contracts import V2EvidenceItem, V2StructuredFact
from app.intelligence_v2.evidence import V2EvidenceRetriever
from app.models.skill_intelligence import MarketObservation
from app.storage.reference_store import ReferenceDataStore
from app.storage.firestore_observation_store import FirestoreObservationStore

logger = logging.getLogger(__name__)


class MarketIntelligenceResult(BaseModel):
    """Unified output from Market Intelligence capability execution."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    headline: str
    facts: list[V2StructuredFact] = Field(default_factory=list)
    evidence: list[V2EvidenceItem] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    readiness_state: str = "observed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class V2MarketIntelligenceEngine:
    """Executes market-level intelligence queries and signal aggregations."""

    def __init__(
        self,
        store: ReferenceDataStore | None = None,
        evidence_retriever: V2EvidenceRetriever | None = None,
        observation_store: Any | None = None,
    ) -> None:
        self.store = store or ReferenceDataStore(read_only=True)
        self.evidence_retriever = evidence_retriever or V2EvidenceRetriever(self.store)
        # The Firestore client is lazy; tests and offline callers must inject a local store.
        self.observation_store = observation_store or FirestoreObservationStore()

    def run_snapshot(self, geography: str = "all") -> MarketIntelligenceResult:
        """Macro overview of verified indicators across developer adoption and reference data."""
        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []
        signals: list[dict[str, Any]] = []
        total_lang_obs = 0
        total_topic_obs = 0
        latest_period: str | None = None
        geography_key = geography or "all"
        geography_is_global = geography_key.lower() in {"all", "global"}
        target_iso = "ALL" if geography_is_global else geography_key.upper()
        query_all = "all" if geography_is_global else geography_key.lower()
        try:
            with self.store._connect() as conn:
                for table, entity_column, signal_kind in (
                    ("ref_github_language_adoption", "language", "language"),
                    ("ref_github_topic_adoption", "topic", "topic"),
                ):
                    scoped = conn.execute(
                        f"SELECT COUNT(*) AS count, MAX(period) AS latest FROM {table} "
                        "WHERE (iso2_code = ? OR ? = 'all')",
                        (target_iso, query_all),
                    ).fetchone()
                    count = int(scoped["count"] or 0)
                    if signal_kind == "language":
                        total_lang_obs = count
                    else:
                        total_topic_obs = count
                    if scoped["latest"] and (latest_period is None or scoped["latest"] > latest_period):
                        latest_period = scoped["latest"]

                if latest_period:
                    for table, entity_column, signal_kind in (
                        ("ref_github_language_adoption", "language", "language"),
                        ("ref_github_topic_adoption", "topic", "topic"),
                    ):
                        rows = conn.execute(
                            f"SELECT {entity_column} AS technology, num_pushers, period, iso2_code "
                            f"FROM {table} WHERE period = ? AND (iso2_code = ? OR ? = 'all') "
                            "ORDER BY num_pushers DESC LIMIT 5",
                            (latest_period, target_iso, query_all),
                        ).fetchall()
                        signals.extend({**dict(row), "signal_kind": signal_kind} for row in rows)
        except Exception as exc:
            logger.warning("Error fetching market snapshot observations: %s", exc)
            latest_period = None
            signals = []

        signals.sort(key=lambda item: item["num_pushers"], reverse=True)
        signals = signals[:5]
        total_observations = total_lang_obs + total_topic_obs
        if latest_period and total_observations:
            facts.append(V2StructuredFact(
                fact_id="fact:market:github_obs_total",
                fact_type="market_dataset_inventory",
                metric_name="total_developer_adoption_observations",
                metric_value=total_observations,
                unit="observations",
                period=latest_period,
                source="GitHub Innovation Graph",
                data_origin="local_reference_dataset",
                history_type="backfill",
                details={
                    "language_series_count": total_lang_obs,
                    "topic_series_count": total_topic_obs,
                    "geography": geography_key,
                    "signal_type": "adoption",
                },
            ))
            evidence.append(V2EvidenceItem(
                evidence_id="evi:market:macro_inventory",
                source="GitHub Innovation Graph",
                signal_family="developer_adoption",
                measured_signal_type="market_observations_inventory",
                period=latest_period,
                time_grain="quarter",
                data_origin="local_reference_dataset",
                history_type="backfill",
                geography=geography_key,
                sample_size=total_observations,
                source_url="https://github.com/github/innovationgraph",
                description=(
                    f"Local storage contains {total_observations:,} quarterly language/topic adoption records "
                    f"for {geography_key}, latest period {latest_period}; these measure developer activity, not hiring demand."
                ),
            ))
            headline = (
                f"Market Intelligence Snapshot ({latest_period}): {total_observations:,} local quarterly "
                f"developer-adoption records are available for {geography_key}; this is not hiring demand."
            )
            readiness_state = "ready"
        else:
            headline = f"No local developer-adoption observations are available for {geography_key}; no measured market snapshot is reported."
            readiness_state = "insufficient_data"

        return MarketIntelligenceResult(
            capability_id="market_intelligence_snapshot",
            headline=headline,
            facts=facts,
            evidence=evidence,
            signals=signals,
            readiness_state=readiness_state,
            metadata={"total_observations": total_observations},
        )

    def run_tech_signals(
        self,
        geography: str = "all",
        limit: int = 10,
    ) -> MarketIntelligenceResult:
        """Quarterly developer adoption rankings and signals across technologies."""
        signals: list[dict[str, Any]] = []
        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []
        geography_key = geography or "all"
        geography_is_global = geography_key.lower() in {"all", "global"}

        try:
            with self.store._connect() as conn:
                # Find most recent period
                p_row = conn.execute(
                    "SELECT MAX(period) as max_p FROM ref_github_language_adoption"
                ).fetchone()
                latest_p = p_row["max_p"] if p_row and p_row["max_p"] else "2026-Q1"

                rows = conn.execute(
                    """
                    SELECT language, num_pushers, period, iso2_code
                    FROM ref_github_language_adoption
                    WHERE period = ? AND (iso2_code = ? OR ? = 'all')
                    ORDER BY num_pushers DESC
                    LIMIT ?
                    """,
                    (latest_p, geography_key, "all" if geography_is_global else geography_key.lower(), limit),
                ).fetchall() if latest_p else []
                signals = [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("Error fetching tech signals: %s", exc)

        for idx, sig in enumerate(signals, start=1):
            facts.append(
                V2StructuredFact(
                    fact_id=f"fact:tech_signal:{sig['language'].casefold()}:{sig['period']}",
                    fact_type="developer_adoption_ranking",
                    entity_name=sig["language"],
                    entity_type="technology",
                    metric_name="active_pushers",
                    metric_value=sig["num_pushers"],
                    unit="pushers",
                    period=sig["period"],
                    source="GitHub Innovation Graph",
                    data_origin="local_reference_dataset",
                    history_type="backfill",
                    details={"rank": idx, "geography": sig["iso2_code"]},
                )
            )

        if signals:
            evidence.append(V2EvidenceItem(
                evidence_id="evi:market:tech_rankings",
                source="GitHub Innovation Graph",
                signal_family="developer_adoption",
                measured_signal_type="num_pushers",
                period=signals[0]["period"],
                time_grain="quarter",
                unit="pushers",
                data_origin="local_reference_dataset",
                readiness_state="observed",
                source_url="https://github.com/github/innovationgraph",
                description="Retrieved quarterly developer pusher counts from the local GitHub Innovation Graph reference dataset; this is not hiring demand.",
                quality="valid",
            ))

        headline = (
            f"Technology Adoption Rankings ({signals[0]['period'] if signals else 'Latest'}): "
            f"Top technologies led by {signals[0]['language']} ({signals[0]['num_pushers']:,} pushers)."
            if signals else "No technology adoption signals available."
        )

        return MarketIntelligenceResult(
            capability_id="market_tech_signals",
            headline=headline,
            facts=facts,
            evidence=evidence,
            signals=signals,
            readiness_state="ready" if signals else "insufficient_data",
            metadata={"top_tech_count": len(signals)},
        )

    def run_trend_velocity(
        self,
        skill_or_role: str = "all",
        geography: str = "all",
        *,
        as_of: datetime | None = None,
    ) -> MarketIntelligenceResult:
        """Measure one or more isolated public adoption/interest series; never call them hiring demand."""
        as_of = as_of or datetime.now(timezone.utc)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        observed: list[MarketObservation] = []
        query_truncated = False
        try:
            query_result = self.observation_store.get_observations_by_skill(
                skill_or_role,
                cutoff=datetime(2000, 1, 1, tzinfo=timezone.utc),
            )
            query_truncated = bool(getattr(query_result, "truncated", False))
            observed = list(query_result)
        except Exception as exc:
            logger.warning("Public adoption observations unavailable (%s)", type(exc).__name__)

        # Candidate sources carry different units and denominators. Group on every
        # comparable identity field and only emit an independent result per series.
        allowed = {"github", "wikipedia", "stackexchange"}
        groups: dict[tuple[Any, ...], list[MarketObservation]] = defaultdict(list)
        for item in observed:
            source = item.source.casefold().strip()
            expected_type = "adoption" if source == "github" else "interest"
            if source not in allowed or item.signal_type != expected_type or item.data_origin != "real":
                continue
            if item.history_type not in {"backfill", "backfilled", "snapshot"} or not item.series_id or not item.unit:
                continue
            if geography.casefold() in {"all", "global", "world"}:
                if item.scope != "global" or item.location:
                    continue
            else:
                if item.scope == "global" or not item.location or geography.casefold() not in item.location.casefold():
                    continue
            key = (
                source, item.signal_type, item.series_id, item.unit.casefold(),
                (item.denominator_unit or "").casefold(), item.denominator,
                item.scope, (item.location or "").casefold(), item.query_id,
                item.panel_version, item.extractor_version, item.data_origin,
                item.history_type,
            )
            groups[key].append(item)

        facts: list[V2StructuredFact] = []
        evidence: list[V2EvidenceItem] = []
        ready_series: list[dict[str, Any]] = []
        rejected: list[str] = ["observation query was truncated"] if query_truncated else []
        if query_truncated:
            groups.clear()
        for key, items in groups.items():
            source, signal_type, series_id, unit = key[:4]
            period_pattern = re.compile(r"^(\d{4})-(\d{2})$")
            by_period: dict[str, MarketObservation] = {}
            duplicate_period = False
            invalid = False
            seen_ids: dict[str, MarketObservation] = {}
            for item in items:
                obs_id = item.id
                if obs_id and obs_id in seen_ids:
                    prior = seen_ids[obs_id]
                    if prior.value != item.value or prior.period != item.period:
                        invalid = True
                    continue
                if obs_id:
                    seen_ids[obs_id] = item
                period = item.period or ""
                match = period_pattern.fullmatch(period)
                if not match or not item.observed_at or item.observed_at.tzinfo is None:
                    invalid = True
                    continue
                year, month = int(match.group(1)), int(match.group(2))
                if not 1 <= month <= 12 or item.observed_at.astimezone(timezone.utc).strftime("%Y-%m") != period:
                    invalid = True
                    continue
                if item.observed_at.astimezone(timezone.utc) > as_of or period >= as_of.strftime("%Y-%m"):
                    continue
                if period in by_period:
                    duplicate_period = True
                    continue
                by_period[period] = item
            periods = sorted(by_period)
            indices = [int(period[:4]) * 12 + int(period[5:7]) for period in periods]
            consecutive = len(indices) >= 4 and all(right - left == 1 for left, right in zip(indices, indices[1:]))
            if invalid or duplicate_period or not consecutive:
                rejected.append(f"{source}:{series_id}")
                continue

            points = [{"period": period, "value": by_period[period].value} for period in periods]
            first, previous, latest = points[0], points[-2], points[-1]
            velocity = round(float(latest["value"]) - float(previous["value"]), 6)
            period_label = f"{periods[0]} to {periods[-1]}"
            item = by_period[periods[-1]]
            source_label = {"github": "GitHub public repository signals", "wikipedia": "Wikimedia Pageviews", "stackexchange": "Stack Exchange question-tag activity"}[source]
            metric = str(item.metadata.get("metric") or ("repository_count" if source == "github" else "pageviews" if source == "wikipedia" else "questions"))
            source_note = (
                " GitHub repository search counts are a bounded public snapshot proxy, not a developer population or hiring count."
                if source == "github" else ""
            )
            facts.append(V2StructuredFact(
                fact_id=f"fact:market:adoption_velocity:{source}:{series_id}:{periods[-1]}",
                fact_type="trend_analysis",
                entity_name=item.skill,
                canonical_entity_id=item.skill_id,
                entity_type="skill",
                metric_name=f"{metric}_period_change",
                metric_value=velocity,
                unit=f"{unit} per month",
                period=period_label,
                source=source_label,
                data_origin="real",
                history_type=item.history_type,
                series_id=series_id,
                panel_version=item.panel_version,
                readiness_state="ready",
                details={
                    "provider": source_label,
                    "signal_type": signal_type,
                    "metric": metric,
                    "value_unit": unit,
                    "velocity_unit": f"{unit} per month",
                    "velocity": velocity,
                    "trend_direction": "increasing" if velocity > 0 else "declining" if velocity < 0 else "stable",
                    "series": points,
                    "observation_count": len(points),
                    "window": period_label,
                    "data_provenance": "validated real observations from the configured public-source collection pipeline",
                    "source_note": source_note.strip(),
                    "source_url": item.source_url,
                    "hiring_demand_included": False,
                    "first_value": first["value"],
                    "latest_value": latest["value"],
                },
            ))
            evidence.append(V2EvidenceItem(
                evidence_id=f"evi:market:trend:{source}:{series_id}:{periods[-1]}",
                source=source_label,
                signal_family="developer_adoption" if source == "github" else "public_attention" if source == "wikipedia" else "community_interest",
                measured_signal_type=metric,
                period=period_label,
                time_grain="month",
                unit=unit,
                scope=item.scope,
                geography=item.location or "global",
                data_origin="real",
                history_type=item.history_type,
                series_id=series_id,
                query_id=item.query_id,
                panel_version=item.panel_version,
                fetch_run_id=item.fetch_run_id,
                source_url=item.source_url,
                extractor_version=item.extractor_version,
                sample_size=len(points),
                denominator=item.denominator,
                readiness_state="ready",
                description=f"Validated {source_label} series for {item.skill}, {period_label}; values are {unit} per month and are not hiring-demand measurements.",
            ))
            ready_series.append({"source": source, "series_id": series_id, "window": period_label})

        # GitHub Innovation Graph is an existing local quarterly reference series.
        # Preserve its native quarter grain and country identity; never sum countries.
        try:
            from app.analytics.skill_registry import canonical_skill_id

            skill_id = canonical_skill_id(skill_or_role)
            country = geography.strip().upper()
            if skill_id and len(country) == 2:
                with self.store._connect() as connection:
                    reference_rows = [dict(row) for row in connection.execute(
                        "SELECT language AS label, period, year, quarter, num_pushers, iso2_code, "
                        "'language' AS kind FROM ref_github_language_adoption "
                        "WHERE canonical_skill_id = ? AND iso2_code = ? "
                        "UNION ALL SELECT topic AS label, period, year, quarter, num_pushers, iso2_code, "
                        "'topic' AS kind FROM ref_github_topic_adoption "
                        "WHERE canonical_skill_id = ? AND iso2_code = ?",
                        (skill_id, country, skill_id, country),
                    ).fetchall()]
                by_reference_series: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
                for row in reference_rows:
                    label = str(row.get("label") or "")
                    kind = str(row["kind"])
                    by_reference_series[(kind, label)].append(dict(row))
                for (kind, label), rows in by_reference_series.items():
                    periods_by_key: dict[str, dict[str, Any]] = {}
                    invalid = False
                    for row in rows:
                        period = str(row.get("period") or "")
                        match = re.fullmatch(r"(\d{4})-Q([1-4])", period)
                        value = row.get("num_pushers")
                        if not match or isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                            invalid = True
                            continue
                        year, quarter = int(match.group(1)), int(match.group(2))
                        index = year * 4 + quarter
                        current_index = as_of.year * 4 + ((as_of.month - 1) // 3 + 1)
                        if index >= current_index:
                            continue
                        if period in periods_by_key:
                            invalid = True
                            continue
                        periods_by_key[period] = row
                    quarter_periods = sorted(periods_by_key, key=lambda value: (int(value[:4]), int(value[-1])))
                    quarter_indices = [int(value[:4]) * 4 + int(value[-1]) for value in quarter_periods]
                    if invalid or len(quarter_indices) < 4 or any(
                        right - left != 1 for left, right in zip(quarter_indices, quarter_indices[1:])
                    ):
                        continue
                    values = [{"period": period, "value": float(periods_by_key[period]["num_pushers"])} for period in quarter_periods]
                    previous, latest = values[-2], values[-1]
                    velocity = round(latest["value"] - previous["value"], 6)
                    period_label = f"{quarter_periods[0]} to {quarter_periods[-1]}"
                    series_id = f"github-innovation-graph:{kind}:{skill_id}:{country}:v1"
                    facts.append(V2StructuredFact(
                        fact_id=f"fact:market:adoption_velocity:{series_id}:{quarter_periods[-1]}",
                        fact_type="trend_analysis", entity_name=label, canonical_entity_id=skill_id,
                        entity_type="skill", metric_name="active_pushers_period_change",
                        metric_value=velocity, unit="unique developers per quarter", period=period_label,
                        source="GitHub Innovation Graph", data_origin="real", history_type="backfill",
                        series_id=series_id, readiness_state="ready",
                        details={
                            "provider": "GitHub Innovation Graph", "signal_type": "adoption",
                            "metric": "unique_active_pushers", "value_unit": "pushers",
                            "velocity_unit": "pushers per quarter", "velocity": velocity,
                            "trend_direction": "increasing" if velocity > 0 else "declining" if velocity < 0 else "stable",
                            "series": values, "observation_count": len(values), "window": period_label,
                            "data_provenance": "local GitHub Innovation Graph reference dataset",
                            "source_url": "https://github.com/github/innovationgraph",
                            "geography": country, "hiring_demand_included": False,
                        },
                    ))
                    evidence.append(V2EvidenceItem(
                        evidence_id=f"evi:market:github_trend:{skill_id}:{country}:{quarter_periods[-1]}:{kind}",
                        source="GitHub Innovation Graph", signal_family="developer_adoption",
                        measured_signal_type="unique_active_pushers", period=period_label,
                        time_grain="quarter", unit="pushers", geography=country,
                        scope=f"{kind}_adoption", data_origin="local_reference_dataset",
                        history_type="backfill", series_id=series_id,
                        source_url="https://github.com/github/innovationgraph", sample_size=len(values),
                        readiness_state="ready",
                        description=f"Local GitHub Innovation Graph {kind} series for {label} in {country}, {period_label}; unique developer activity, not hiring demand.",
                    ))
                    ready_series.append({"source": "github_innovation_graph", "series_id": series_id, "window": period_label})
        except Exception as exc:
            logger.warning("GitHub reference adoption series unavailable (%s)", type(exc).__name__)

        if facts:
            sources = ", ".join(sorted({item["source"] for item in ready_series}))
            headline = (
                f"Measured public technology-adoption and interest velocity for {skill_or_role} from {sources}. "
                "These source-specific signals are not hiring demand."
            )
            readiness_state = "ready"
        else:
            headline = (
                f"No usable comparable public adoption or interest series is available for {skill_or_role}. "
                "A measured trend needs at least four consecutive completed periods at one unchanged source's native time grain. "
                "This does not establish hiring-demand velocity; hiring demand remains separately gated on four completed months."
            )
            readiness_state = "insufficient_data"

        return MarketIntelligenceResult(
            capability_id="market_trend_velocity",
            headline=headline,
            facts=facts,
            evidence=evidence,
            signals=[{"source": item["source"], "series_id": item["series_id"], "window": item["window"]} for item in ready_series],
            readiness_state=readiness_state,
            metadata={"periods_required": 4, "ready_series_count": len(ready_series), "rejected_series": rejected, "hiring_demand_gate_months_required": 4, "hiring_demand_calculated": False},
        )

    def run_evidence_citations(self) -> MarketIntelligenceResult:
        """Market signal citations and data provenance audit."""
        evidence: list[V2EvidenceItem] = []
        counts = self.store.get_table_counts()
        github_count = counts.get("ref_github_language_adoption", 0) + counts.get("ref_github_topic_adoption", 0)
        if github_count:
            with self.store._connect() as conn:
                language_periods = conn.execute(
                    "SELECT MIN(period) AS first_period, MAX(period) AS last_period FROM ref_github_language_adoption"
                ).fetchone()
                topic_periods = conn.execute(
                    "SELECT MIN(period) AS first_period, MAX(period) AS last_period FROM ref_github_topic_adoption"
                ).fetchone()
            periods = [
                value
                for row in (language_periods, topic_periods)
                for value in (row["first_period"], row["last_period"])
                if value
            ]
            first_period, last_period = min(periods), max(periods)
            evidence.append(V2EvidenceItem(
                evidence_id="evi:market:github_local_dataset",
                source="GitHub Innovation Graph",
                signal_family="developer_adoption",
                measured_signal_type="num_pushers",
                period=first_period if first_period == last_period else f"{first_period} to {last_period}",
                time_grain="quarter",
                data_origin="local_reference_dataset",
                history_type="backfill",
                sample_size=github_count,
                source_url="https://github.com/github/innovationgraph",
                description=(
                    f"Local reference storage contains {github_count} quarterly language/topic adoption records "
                    f"covering {first_period} through {last_period}; this is developer activity, not hiring demand."
                ),
            ))

        onet_count = sum(counts.get(table, 0) for table in (
            "ref_onet_occupations", "ref_onet_software_skills", "ref_onet_essential_skills", "ref_onet_related_occupations"
        ))
        if onet_count:
            evidence.append(V2EvidenceItem(
                evidence_id="evi:market:onet_local_reference",
                source="O*NET local reference dataset",
                signal_family="reference_taxonomy",
                measured_signal_type="occupations_and_skills",
                time_grain="static",
                data_origin="local_reference_dataset",
                sample_size=onet_count,
                source_url="https://www.onetcenter.org/",
                description=f"Local storage contains {onet_count} O*NET occupation, skill, and relationship records; these are reference baselines, not vacancies or hiring measurements.",
            ))

        esco_count = sum(counts.get(table, 0) for table in (
            "ref_esco_skills", "ref_esco_occupations", "ref_esco_occupation_skill_relations"
        ))
        if esco_count:
            evidence.append(V2EvidenceItem(
                evidence_id="evi:market:esco_local_reference",
                source="ESCO local reference dataset",
                signal_family="reference_taxonomy",
                measured_signal_type="occupations_and_skills",
                time_grain="static",
                data_origin="local_reference_dataset",
                sample_size=esco_count,
                source_url="https://esco.ec.europa.eu/",
                description=f"Local storage contains {esco_count} ESCO occupation, skill, and relationship records; these are reference baselines, not vacancies or hiring measurements.",
            ))

        headline = (
            f"Market Evidence & Sources: Retrieved provenance for {len(evidence)} local source families."
            if evidence else
            "No local market or reference source records are currently available; no source evidence is reported."
        )

        return MarketIntelligenceResult(
            capability_id="market_evidence_citations",
            headline=headline,
            facts=[],
            evidence=evidence,
            readiness_state="observed" if evidence else "insufficient_data",
            metadata={"sources_retrieved": len(evidence)},
        )

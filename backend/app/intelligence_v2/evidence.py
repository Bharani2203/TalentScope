"""Greenfield Intelligence Engine V2 — Evidence & Provenance Engine.

Constructs standardized citations, data lineage, and truth-in-data statements
for all intelligence outputs across all signal families.
"""

from __future__ import annotations

import logging
from typing import Any
from app.intelligence_v2.contracts import (
    DataOrigin,
    SignalFamily,
    TimeGrain,
    V2EvidenceItem,
)
from app.models.execution_orchestrator import EvidenceItem
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


class V2EvidenceRetriever:
    """Retrieves and standardizes evidence from verified stores and datasets."""

    def __init__(self, store: ReferenceDataStore | None = None) -> None:
        self.store = store or ReferenceDataStore(read_only=True)

    def get_developer_adoption_evidence(
        self,
        language_or_topic: str,
        country: str = "all",
    ) -> list[V2EvidenceItem]:
        """Fetch developer adoption evidence from local GitHub Innovation Graph dataset."""
        items: list[V2EvidenceItem] = []
        name = language_or_topic.strip()

        is_global = country.lower() in {"all", "global", "world"} or len(country) != 2
        try:
            with self.store._connect() as conn:
                # Check language adoption table
                if is_global:
                    lang_rows = conn.execute(
                        """
                        SELECT period, SUM(num_pushers) as num_pushers, year, quarter, 'global' as iso2_code
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?)
                        GROUP BY year, quarter, period
                        ORDER BY year DESC, quarter DESC
                        LIMIT 12
                        """,
                        (name,),
                    ).fetchall()
                else:
                    lang_rows = conn.execute(
                        """
                        SELECT period, num_pushers, year, quarter, iso2_code
                        FROM ref_github_language_adoption
                        WHERE lower(language) = lower(?) AND iso2_code = ?
                        ORDER BY year DESC, quarter DESC
                        LIMIT 12
                        """,
                        (name, country.upper()),
                    ).fetchall()

                if lang_rows:
                    most_recent = lang_rows[0]
                    total_samples = len(lang_rows)
                    items.append(
                        V2EvidenceItem(
                            evidence_id=f"evi:github_lang:{name.casefold()}:{most_recent['period']}",
                            source="GitHub Innovation Graph",
                            signal_family="developer_adoption",
                            measured_signal_type="num_pushers",
                            period=most_recent["period"],
                            time_grain="quarter",
                            unit="pushers",
                            geography=most_recent["iso2_code"],
                            scope="language_adoption",
                            data_origin="real",
                            history_type="backfill",
                            series_id=f"github:lang:{name.casefold()}",
                            source_url="https://github.com/github/innovationgraph",
                            provenance_id="dataset:github_innovation_graph:language",
                            canonical_mapping=name,
                            sample_size=total_samples,
                            readiness_state="observed",
                            confidence_status="high",
                            quality="valid",
                            description=(
                                f"GitHub developer adoption series for '{name}' with {total_samples} "
                                f"quarterly observations through {most_recent['period']}."
                            ),
                        )
                    )

                # Check topic adoption table
                if is_global:
                    topic_rows = conn.execute(
                        """
                        SELECT period, SUM(num_pushers) as num_pushers, year, quarter, 'global' as iso2_code
                        FROM ref_github_topic_adoption
                        WHERE lower(topic) = lower(?)
                        GROUP BY year, quarter, period
                        ORDER BY year DESC, quarter DESC
                        LIMIT 12
                        """,
                        (name,),
                    ).fetchall()
                else:
                    topic_rows = conn.execute(
                        """
                        SELECT period, num_pushers, year, quarter, iso2_code
                        FROM ref_github_topic_adoption
                        WHERE lower(topic) = lower(?) AND iso2_code = ?
                        ORDER BY year DESC, quarter DESC
                        LIMIT 12
                        """,
                        (name, country.upper()),
                    ).fetchall()

                if topic_rows:
                    most_recent = topic_rows[0]
                    total_samples = len(topic_rows)
                    items.append(
                        V2EvidenceItem(
                            evidence_id=f"evi:github_topic:{name.casefold()}:{most_recent['period']}",
                            source="GitHub Innovation Graph",
                            signal_family="developer_adoption",
                            measured_signal_type="num_pushers",
                            period=most_recent["period"],
                            time_grain="quarter",
                            unit="pushers",
                            geography=most_recent["iso2_code"],
                            scope="topic_adoption",
                            data_origin="real",
                            history_type="backfill",
                            series_id=f"github:topic:{name.casefold()}",
                            source_url="https://github.com/github/innovationgraph",
                            provenance_id="dataset:github_innovation_graph:topic",
                            canonical_mapping=name,
                            sample_size=total_samples,
                            readiness_state="observed",
                            confidence_status="high",
                            quality="valid",
                            description=(
                                f"GitHub topic adoption series for '{name}' with {total_samples} "
                                f"quarterly observations through {most_recent['period']}."
                            ),
                        )
                    )
        except Exception as exc:
            logger.warning("Error fetching developer adoption evidence for %s: %s", name, exc)

        return items

    def get_reference_taxonomy_evidence(
        self,
        entity_name: str,
        soc_code: str | None = None,
    ) -> list[V2EvidenceItem]:
        """Fetch static taxonomy context evidence from O*NET and ESCO."""
        items: list[V2EvidenceItem] = []
        name = entity_name.strip()

        try:
            with self.store._connect() as conn:
                if soc_code:
                    occ = conn.execute(
                        "SELECT soc_code, title FROM ref_onet_occupations WHERE soc_code = ?",
                        (soc_code,),
                    ).fetchone()
                else:
                    occ = conn.execute(
                        "SELECT soc_code, title FROM ref_onet_occupations WHERE title LIKE ? LIMIT 1",
                        (f"%{name}%",),
                    ).fetchone()

                if occ:
                    items.append(
                        V2EvidenceItem(
                            evidence_id=f"evi:onet_occ:{occ['soc_code']}",
                            source="O*NET 28.0",
                            signal_family="reference_taxonomy",
                            measured_signal_type="occupation_definition",
                            period="2024",
                            time_grain="static",
                            data_origin="real",
                            source_url="https://www.onetcenter.org/taxonomy.html",
                            provenance_id=f"onet:soc:{occ['soc_code']}",
                            taxonomy_version="O*NET 28.0",
                            description=f"O*NET official occupation taxonomy for {occ['title']} (SOC {occ['soc_code']}).",
                        )
                    )
        except Exception as exc:
            logger.warning("Error retrieving reference taxonomy evidence for %s: %s", name, exc)

        return items

    def get_hiring_demand_evidence(
        self,
        skill_or_role: str,
        geography: str | None = None,
        history_type: str = "platform_collected",
    ) -> list[V2EvidenceItem]:
        """Generate evidence for hiring demand observations or state data readiness."""
        items: list[V2EvidenceItem] = []
        name = skill_or_role.strip()

        # Check market_observations table in SQLite
        count = 0
        distinct_periods_cnt = 0
        min_p = ""
        max_p = ""
        src = "TalentScope Market Observations"
        hist_type = history_type
        try:
            with self.store._connect() as conn:
                if history_type == "platform_collected":
                    row = conn.execute(
                        """SELECT COUNT(*) as cnt, COUNT(DISTINCT period) as p_cnt, MIN(period) as min_p, MAX(period) as max_p, history_type, source
                           FROM market_observations
                           WHERE lower(skill) = lower(?) AND lower(signal_type) = 'demand'
                             AND lower(COALESCE(data_origin, '')) = 'real'
                             AND lower(COALESCE(history_type, '')) = 'platform_collected'
                           GROUP BY history_type, source
                           ORDER BY cnt DESC""",
                        (name,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """SELECT COUNT(*) as cnt, COUNT(DISTINCT period) as p_cnt, MIN(period) as min_p, MAX(period) as max_p, history_type, source
                           FROM market_observations
                           WHERE lower(skill) = lower(?) AND lower(signal_type) = 'demand'
                             AND lower(COALESCE(data_origin, '')) = 'real'
                             AND lower(COALESCE(history_type, '')) IN ('platform_collected', 'backfill')
                           GROUP BY history_type, source
                           ORDER BY cnt DESC""",
                        (name,),
                    ).fetchone()
                if row:
                    count = int(row["cnt"])
                    distinct_periods_cnt = int(row["p_cnt"])
                    min_p = str(row["min_p"])
                    max_p = str(row["max_p"])
                    hist_type = str(row["history_type"])
                    src = "Fliarbi Job Postings Sample" if hist_type == "backfill" else str(row["source"])
        except Exception:
            count = 0

        if count == 0 or distinct_periods_cnt < 4:
            # Honest insufficient data evidence item
            items.append(
                V2EvidenceItem(
                    evidence_id=f"evi:hiring_demand_missing:{name.casefold()}",
                    source="TalentScope Market Observation Pipeline",
                    signal_family="hiring_demand",
                    measured_signal_type="job_postings",
                    time_grain="month",
                    unit="postings",
                    geography=geography or "global",
                    data_origin="unavailable",
                    readiness_state="insufficient_data",
                    confidence_status="low",
                    quality="insufficient_history",
                    description=(
                        f"Insufficient verified monthly hiring demand observations for '{name}' "
                        f"(requires >= 4 completed months of platform-collected data; found {distinct_periods_cnt})."
                    ),
                )
            )
        else:
            items.append(
                V2EvidenceItem(
                    evidence_id=f"evi:hiring_demand:{name.casefold()}",
                    source=src,
                    signal_family="hiring_demand",
                    measured_signal_type="sample_job_postings" if hist_type == "backfill" else "job_postings",
                    time_grain="month",
                    period=f"{min_p} to {max_p}",
                    unit="postings",
                    geography=geography or "global",
                    data_origin="real",
                    history_type=hist_type,
                    sample_size=count,
                    readiness_state="observed",
                    confidence_status="medium",
                    quality="sample_level" if hist_type == "backfill" else "valid",
                    description=f"{count} verified hiring demand observations across {distinct_periods_cnt} months ({min_p} to {max_p}) for '{name}'.",
                )
            )

        return items

    def get_benchmark_evidence(self) -> list[V2EvidenceItem]:
        """Evidence item recording benchmark data availability."""
        return [
            V2EvidenceItem(
                evidence_id="evi:benchmark:job_sdf",
                source="Job-SDF Benchmark",
                signal_family="benchmark",
                measured_signal_type="skill_proportion_benchmark",
                time_grain="point_in_time",
                data_origin="benchmark",
                readiness_state="reader_unavailable",
                confidence_status="low",
                quality="quarantined",
                description=(
                    "Job-SDF benchmark dataset files (.parquet) present locally; "
                    "no parquet engine (pyarrow/fastparquet/duckdb) is currently installed."
                ),
            )
        ]


def convert_v2_evidence_list(items: list[V2EvidenceItem]) -> list[EvidenceItem]:
    """Convert a list of V2EvidenceItem to public EvidenceItem instances."""
    return [item.to_public_evidence() for item in items]

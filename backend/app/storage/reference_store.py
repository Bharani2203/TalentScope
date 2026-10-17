"""SQLite storage adapter for local reference taxonomies and developer adoption series."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.reference_data import (
    GitHubLanguageAdoption,
    GitHubTopicAdoption,
    OnetEssentialSkill,
    OnetOccupation,
    OnetRelatedOccupation,
    OnetSoftwareSkill,
)


class ReferenceDataStore:
    def __init__(self, database_path: str | Path | None = None):
        if database_path is None:
            from app.core.config import get_settings
            database_path = get_settings().database_path
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 15000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS ref_onet_occupations (
                    soc_code TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ref_onet_occ_title
                    ON ref_onet_occupations(title);

                CREATE TABLE IF NOT EXISTS ref_onet_software_skills (
                    id TEXT PRIMARY KEY,
                    soc_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    workplace_example TEXT NOT NULL,
                    element_id TEXT NOT NULL,
                    element_name TEXT NOT NULL,
                    hot_technology INTEGER NOT NULL,
                    in_demand INTEGER NOT NULL,
                    canonical_skill_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (soc_code) REFERENCES ref_onet_occupations(soc_code)
                );
                CREATE INDEX IF NOT EXISTS idx_ref_onet_soft_soc
                    ON ref_onet_software_skills(soc_code);
                CREATE INDEX IF NOT EXISTS idx_ref_onet_soft_canonical
                    ON ref_onet_software_skills(canonical_skill_id);
                CREATE INDEX IF NOT EXISTS idx_ref_onet_soft_example
                    ON ref_onet_software_skills(workplace_example);

                CREATE TABLE IF NOT EXISTS ref_onet_essential_skills (
                    id TEXT PRIMARY KEY,
                    soc_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    element_id TEXT NOT NULL,
                    element_name TEXT NOT NULL,
                    scale_id TEXT NOT NULL,
                    scale_name TEXT NOT NULL,
                    data_value REAL NOT NULL,
                    sample_size INTEGER,
                    standard_error REAL,
                    lower_ci_bound REAL,
                    upper_ci_bound REAL,
                    recommend_suppress INTEGER NOT NULL,
                    domain_source TEXT,
                    date TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (soc_code) REFERENCES ref_onet_occupations(soc_code)
                );
                CREATE INDEX IF NOT EXISTS idx_ref_onet_ess_soc
                    ON ref_onet_essential_skills(soc_code, element_name);
                CREATE INDEX IF NOT EXISTS idx_ref_onet_ess_scale
                    ON ref_onet_essential_skills(scale_id);

                CREATE TABLE IF NOT EXISTS ref_onet_related_occupations (
                    id TEXT PRIMARY KEY,
                    soc_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    related_soc_code TEXT NOT NULL,
                    related_title TEXT NOT NULL,
                    relatedness_tier TEXT NOT NULL,
                    sort_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (soc_code) REFERENCES ref_onet_occupations(soc_code)
                );
                CREATE INDEX IF NOT EXISTS idx_ref_onet_rel_soc
                    ON ref_onet_related_occupations(soc_code);
                CREATE INDEX IF NOT EXISTS idx_ref_onet_rel_target
                    ON ref_onet_related_occupations(related_soc_code);

                CREATE TABLE IF NOT EXISTS ref_github_language_adoption (
                    id TEXT PRIMARY KEY,
                    language TEXT NOT NULL,
                    language_type TEXT NOT NULL,
                    iso2_code TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    num_pushers INTEGER NOT NULL,
                    signal_type TEXT NOT NULL DEFAULT 'adoption',
                    data_origin TEXT NOT NULL DEFAULT 'real',
                    canonical_skill_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ref_gh_lang_period
                    ON ref_github_language_adoption(period, canonical_skill_id);
                CREATE INDEX IF NOT EXISTS idx_ref_gh_lang_iso
                    ON ref_github_language_adoption(iso2_code, language);

                CREATE TABLE IF NOT EXISTS ref_github_topic_adoption (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    iso2_code TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    num_pushers INTEGER NOT NULL,
                    signal_type TEXT NOT NULL DEFAULT 'adoption',
                    data_origin TEXT NOT NULL DEFAULT 'real',
                    canonical_skill_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ref_gh_topic_period
                    ON ref_github_topic_adoption(period, canonical_skill_id);
                CREATE INDEX IF NOT EXISTS idx_ref_gh_topic_iso
                    ON ref_github_topic_adoption(iso2_code, topic);

                CREATE TABLE IF NOT EXISTS ref_ingestion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    rows_read INTEGER NOT NULL,
                    rows_valid INTEGER NOT NULL,
                    rows_inserted INTEGER NOT NULL,
                    rows_skipped_or_duplicate INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL,
                    ingested_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ref_esco_skills (
                    concept_uri TEXT PRIMARY KEY,
                    preferred_label TEXT NOT NULL,
                    alt_labels TEXT NOT NULL DEFAULT '[]',
                    skill_type TEXT,
                    reuse_level TEXT,
                    description TEXT,
                    modified_date TEXT,
                    source_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ref_esco_skill_label
                    ON ref_esco_skills(preferred_label);
                CREATE TABLE IF NOT EXISTS ref_esco_occupation_skill_relations (
                    occupation_uri TEXT NOT NULL,
                    occupation_label TEXT,
                    relation_type TEXT,
                    skill_uri TEXT NOT NULL,
                    skill_type TEXT,
                    skill_label TEXT,
                    PRIMARY KEY (occupation_uri, skill_uri, relation_type)
                );
                CREATE INDEX IF NOT EXISTS idx_ref_esco_relation_skill
                    ON ref_esco_occupation_skill_relations(skill_uri);
            """)

    def upsert_esco_skills(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_esco_skills
                (concept_uri, preferred_label, alt_labels, skill_type, reuse_level,
                 description, modified_date, source_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(concept_uri) DO UPDATE SET
                    preferred_label=excluded.preferred_label,
                    alt_labels=excluded.alt_labels,
                    skill_type=excluded.skill_type,
                    reuse_level=excluded.reuse_level,
                    description=excluded.description,
                    modified_date=excluded.modified_date,
                    source_version=excluded.source_version
            """, [(
                r["concept_uri"], r["preferred_label"], r.get("alt_labels", "[]"),
                r.get("skill_type"), r.get("reuse_level"), r.get("description"),
                r.get("modified_date"), r.get("source_version", "unknown"),
            ) for r in records])
            return connection.total_changes - before

    def upsert_esco_occupation_skill_relations(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_esco_occupation_skill_relations
                (occupation_uri, occupation_label, relation_type, skill_uri, skill_type, skill_label)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(occupation_uri, skill_uri, relation_type) DO UPDATE SET
                    occupation_label=excluded.occupation_label,
                    skill_type=excluded.skill_type,
                    skill_label=excluded.skill_label
            """, [(
                r["occupation_uri"], r.get("occupation_label"), r.get("relation_type"),
                r["skill_uri"], r.get("skill_type"), r.get("skill_label"),
            ) for r in records])
            return connection.total_changes - before

    def get_reference_skill_rows(self) -> list[dict[str, Any]]:
        """Read unique O*NET and ESCO skill labels with local taxonomy provenance."""
        with self._connect() as connection:
            onet = connection.execute("""
                SELECT workplace_example AS name, 'onet_software' AS source,
                       GROUP_CONCAT(DISTINCT soc_code) AS occupation_ids,
                       GROUP_CONCAT(DISTINCT element_name) AS categories,
                       MAX(hot_technology) AS hot_technology,
                       MAX(in_demand) AS in_demand
                FROM ref_onet_software_skills
                WHERE TRIM(workplace_example) <> ''
                GROUP BY LOWER(TRIM(workplace_example))
            """).fetchall()
            essential = connection.execute("""
                SELECT element_name AS name, 'onet_essential' AS source,
                       GROUP_CONCAT(DISTINCT soc_code) AS occupation_ids,
                       'Essential competency' AS categories, NULL AS hot_technology,
                       NULL AS in_demand
                FROM ref_onet_essential_skills
                WHERE TRIM(element_name) <> ''
                GROUP BY LOWER(TRIM(element_name))
            """).fetchall()
            esco = connection.execute("""
                SELECT s.preferred_label AS name, 'esco' AS source,
                       GROUP_CONCAT(DISTINCT r.occupation_uri) AS occupation_ids,
                       s.skill_type AS categories, NULL AS hot_technology, NULL AS in_demand,
                       s.concept_uri AS taxonomy_id, s.alt_labels AS aliases,
                       s.source_version AS source_version
                FROM ref_esco_skills s
                LEFT JOIN ref_esco_occupation_skill_relations r ON r.skill_uri = s.concept_uri
                WHERE TRIM(s.preferred_label) <> ''
                GROUP BY s.concept_uri
            """).fetchall()
            rows = [dict(row) for row in (*onet, *essential)]
            rows.extend(dict(row) for row in esco)
            return rows

    def upsert_onet_occupations(self, occupations: list[OnetOccupation]) -> int:
        if not occupations:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        records = [
            (item.soc_code, item.title, item.description, now_str)
            for item in occupations
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_onet_occupations (soc_code, title, description, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(soc_code) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description
            """, records)
            return connection.total_changes - before

    def upsert_onet_software_skills(self, skills: list[OnetSoftwareSkill]) -> int:
        if not skills:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        records = [
            (
                item.id,
                item.soc_code,
                item.title,
                item.workplace_example,
                item.element_id,
                item.element_name,
                1 if item.hot_technology else 0,
                1 if item.in_demand else 0,
                item.canonical_skill_id,
                now_str,
            )
            for item in skills
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_onet_software_skills
                (id, soc_code, title, workplace_example, element_id, element_name,
                 hot_technology, in_demand, canonical_skill_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    element_name = excluded.element_name,
                    hot_technology = excluded.hot_technology,
                    in_demand = excluded.in_demand,
                    canonical_skill_id = excluded.canonical_skill_id
            """, records)
            return connection.total_changes - before

    def upsert_onet_essential_skills(self, skills: list[OnetEssentialSkill]) -> int:
        if not skills:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        records = [
            (
                item.id,
                item.soc_code,
                item.title,
                item.element_id,
                item.element_name,
                item.scale_id,
                item.scale_name,
                item.data_value,
                item.sample_size,
                item.standard_error,
                item.lower_ci_bound,
                item.upper_ci_bound,
                1 if item.recommend_suppress else 0,
                item.domain_source,
                item.date,
                now_str,
            )
            for item in skills
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_onet_essential_skills
                (id, soc_code, title, element_id, element_name, scale_id, scale_name,
                 data_value, sample_size, standard_error, lower_ci_bound, upper_ci_bound,
                 recommend_suppress, domain_source, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    data_value = excluded.data_value,
                    sample_size = excluded.sample_size,
                    standard_error = excluded.standard_error,
                    lower_ci_bound = excluded.lower_ci_bound,
                    upper_ci_bound = excluded.upper_ci_bound,
                    recommend_suppress = excluded.recommend_suppress,
                    date = excluded.date
            """, records)
            return connection.total_changes - before

    def upsert_onet_related_occupations(self, relations: list[OnetRelatedOccupation]) -> int:
        if not relations:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        records = [
            (
                item.id,
                item.soc_code,
                item.title,
                item.related_soc_code,
                item.related_title,
                item.relatedness_tier,
                item.sort_index,
                now_str,
            )
            for item in relations
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_onet_related_occupations
                (id, soc_code, title, related_soc_code, related_title, relatedness_tier, sort_index, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    related_title = excluded.related_title,
                    relatedness_tier = excluded.relatedness_tier,
                    sort_index = excluded.sort_index
            """, records)
            return connection.total_changes - before

    def upsert_github_language_adoption(self, records: list[GitHubLanguageAdoption]) -> int:
        if not records:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        db_records = [
            (
                item.id,
                item.language,
                item.language_type,
                item.iso2_code,
                item.year,
                item.quarter,
                item.period,
                item.num_pushers,
                item.signal_type,
                item.data_origin,
                item.canonical_skill_id,
                now_str,
            )
            for item in records
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_github_language_adoption
                (id, language, language_type, iso2_code, year, quarter, period,
                 num_pushers, signal_type, data_origin, canonical_skill_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    num_pushers = excluded.num_pushers,
                    canonical_skill_id = excluded.canonical_skill_id
            """, db_records)
            return connection.total_changes - before

    def upsert_github_topic_adoption(self, records: list[GitHubTopicAdoption]) -> int:
        if not records:
            return 0
        now_str = datetime.now(timezone.utc).isoformat()
        db_records = [
            (
                item.id,
                item.topic,
                item.iso2_code,
                item.year,
                item.quarter,
                item.period,
                item.num_pushers,
                item.signal_type,
                item.data_origin,
                item.canonical_skill_id,
                now_str,
            )
            for item in records
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT INTO ref_github_topic_adoption
                (id, topic, iso2_code, year, quarter, period,
                 num_pushers, signal_type, data_origin, canonical_skill_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    num_pushers = excluded.num_pushers,
                    canonical_skill_id = excluded.canonical_skill_id
            """, db_records)
            return connection.total_changes - before

    def log_ingestion(
        self,
        *,
        dataset: str,
        source_file: str,
        rows_read: int,
        rows_valid: int,
        rows_inserted: int,
        rows_skipped_or_duplicate: int,
        duration_seconds: float,
    ) -> None:
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO ref_ingestion_log
                (dataset, source_file, rows_read, rows_valid, rows_inserted,
                 rows_skipped_or_duplicate, duration_seconds, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset,
                source_file,
                rows_read,
                rows_valid,
                rows_inserted,
                rows_skipped_or_duplicate,
                duration_seconds,
                datetime.now(timezone.utc).isoformat(),
            ))

    def get_table_counts(self) -> dict[str, int]:
        tables = [
            "ref_onet_occupations",
            "ref_onet_software_skills",
            "ref_onet_essential_skills",
            "ref_onet_related_occupations",
            "ref_github_language_adoption",
            "ref_github_topic_adoption",
            "ref_esco_skills",
            "ref_esco_occupation_skill_relations",
            "ref_ingestion_log",
        ]
        counts: dict[str, int] = {}
        with self._connect() as connection:
            for table in tables:
                cursor = connection.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                counts[table] = int(cursor.fetchone()["cnt"])
        return counts

    def get_onet_occupations(
        self,
        *,
        query: str | None = None,
        title: str | None = None,
        code: str | None = None,
        limit: int = 100,
    ) -> list[OnetOccupation]:
        with self._connect() as connection:
            if code:
                rows = connection.execute(
                    "SELECT soc_code, title, description FROM ref_onet_occupations WHERE soc_code = ? LIMIT ?",
                    (code, limit),
                ).fetchall()
            elif title:
                rows = connection.execute(
                    "SELECT soc_code, title, description FROM ref_onet_occupations WHERE title LIKE ? LIMIT ?",
                    (f"%{title}%", limit),
                ).fetchall()
            elif query:
                rows = connection.execute(
                    "SELECT soc_code, title, description FROM ref_onet_occupations WHERE title LIKE ? OR description LIKE ? LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT soc_code, title, description FROM ref_onet_occupations ORDER BY soc_code LIMIT ?",
                    (limit,),
                ).fetchall()
            return [
                OnetOccupation(
                    soc_code=row["soc_code"],
                    title=row["title"],
                    description=row["description"],
                )
                for row in rows
            ]

    def get_onet_software_skills_by_canonical(self, canonical_skill_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ref_onet_software_skills WHERE canonical_skill_id = ? ORDER BY hot_technology DESC, title",
                (canonical_skill_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_onet_software_skills_by_occupation(
        self, soc_code: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Read bounded occupation mappings with the original O*NET flags intact."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, soc_code, title, workplace_example, element_id, element_name,
                       hot_technology, in_demand, canonical_skill_id
                FROM ref_onet_software_skills
                WHERE soc_code = ? AND TRIM(workplace_example) <> ''
                ORDER BY hot_technology DESC, in_demand DESC, LOWER(workplace_example), id
                LIMIT ?
                """,
                (soc_code.strip(), max(1, min(limit, 500))),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_github_adoption_series(
        self,
        *,
        canonical_skill_id: str | None = None,
        language: str | None = None,
        topic: str | None = None,
        iso2_code: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = []
        params = []
        if canonical_skill_id:
            clauses.append("canonical_skill_id = ?")
            params.append(canonical_skill_id)
        if iso2_code:
            clauses.append("iso2_code = ?")
            params.append(iso2_code)
        table = "ref_github_language_adoption" if language else "ref_github_topic_adoption"
        if language:
            clauses.append("language = ?")
            params.append(language)
        elif topic:
            clauses.append("topic = ?")
            params.append(topic)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} {where_sql} ORDER BY period, iso2_code",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def get_github_adoption_series_for_country(self, iso2_code: str = "IN") -> list[dict[str, Any]]:
        """Read mapped quarterly developer activity without monthly conversion."""
        with self._connect() as connection:
            rows = connection.execute("""
                SELECT canonical_skill_id, language AS label, period, year, quarter,
                       num_pushers AS value, iso2_code, 'language_pushers' AS metric,
                       'unique developers per quarter' AS unit
                FROM ref_github_language_adoption
                WHERE canonical_skill_id IS NOT NULL AND iso2_code = ?
                UNION ALL
                SELECT canonical_skill_id, topic AS label, period, year, quarter,
                       num_pushers AS value, iso2_code, 'topic_pushers' AS metric,
                       'unique developers per quarter' AS unit
                FROM ref_github_topic_adoption
                WHERE canonical_skill_id IS NOT NULL AND iso2_code = ?
                ORDER BY canonical_skill_id, period, metric
            """, (iso2_code.upper(), iso2_code.upper())).fetchall()
            return [dict(row) for row in rows]

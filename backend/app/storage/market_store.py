import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.skill_intelligence import MarketObservation
from app.storage.observation_identity import stable_observation_id

logger = logging.getLogger(__name__)


class MarketDataStore:
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
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS market_observations (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    period TEXT NOT NULL,
                    location TEXT,
                    scope TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    denominator_unit TEXT,
                    source_url TEXT,
                    posting_id TEXT,
                    metadata_json TEXT NOT NULL,
                    history_type TEXT,
                    data_origin TEXT,
                    skill_id TEXT,
                    denominator REAL,
                    fetch_run_id TEXT,
                    series_id TEXT,
                    query_id TEXT,
                    panel_version TEXT,
                    quality_json TEXT,
                    confidence REAL,
                    observation_count INTEGER,
                    extractor_version TEXT,
                    annotations_json TEXT,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_market_observations_period
                    ON market_observations(period);
                CREATE INDEX IF NOT EXISTS idx_market_observations_location
                    ON market_observations(location, scope);
                CREATE INDEX IF NOT EXISTS idx_market_observations_source
                    ON market_observations(source, signal_type);
                CREATE TABLE IF NOT EXISTS market_calculation_cache (
                    cache_key TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_collection_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    location TEXT,
                    country TEXT,
                    observations_inserted INTEGER NOT NULL DEFAULT 0,
                    sources_succeeded_json TEXT NOT NULL DEFAULT '[]',
                    sources_failed_json TEXT NOT NULL DEFAULT '{}'
                );
            """)
            observation_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(market_observations)")
            }
            observation_migrations = {
                "history_type": "TEXT",
                "data_origin": "TEXT",
                "skill_id": "TEXT",
                "denominator": "REAL",
                "fetch_run_id": "TEXT",
                "series_id": "TEXT",
                "query_id": "TEXT",
                "panel_version": "TEXT",
                "quality_json": "TEXT",
                "confidence": "REAL",
                "observation_count": "INTEGER",
                "extractor_version": "TEXT",
                "annotations_json": "TEXT",
                "created_at": "TEXT",
                "unit": "TEXT",
                "denominator_unit": "TEXT",
                "source_url": "TEXT",
            }
            for column, column_type in observation_migrations.items():
                if column not in observation_columns:
                    connection.execute(
                        f"ALTER TABLE market_observations ADD COLUMN {column} {column_type}"
                    )

    @staticmethod
    def _stable_id(observation: MarketObservation) -> str:
        return stable_observation_id(observation)

    def insert_observations(self, observations: list[MarketObservation]) -> int:
        if not observations:
            return 0
        records = []
        for observation in observations:
            observed_at = observation.observed_at
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            records.append((
                self._stable_id(observation),
                observation.source.casefold(),
                observation.signal_type,
                observed_at.astimezone(timezone.utc).isoformat(),
                observation.period or observed_at.strftime("%Y-%m"),
                observation.location,
                observation.scope,
                observation.skill,
                observation.value,
                observation.unit,
                observation.denominator_unit,
                observation.source_url,
                observation.posting_id,
                json.dumps(observation.metadata, sort_keys=True, separators=(",", ":")),
                observation.history_type,
                observation.data_origin,
                observation.skill_id,
                observation.denominator,
                observation.fetch_run_id,
                observation.series_id,
                observation.query_id,
                observation.panel_version,
                json.dumps(observation.quality, sort_keys=True, separators=(",", ":"))
                if observation.quality is not None else None,
                observation.confidence,
                observation.observation_count,
                observation.extractor_version,
                json.dumps(observation.annotations, sort_keys=True, separators=(",", ":")),
                observation.created_at.astimezone(timezone.utc).isoformat()
                if observation.created_at and observation.created_at.tzinfo
                else observation.created_at.replace(tzinfo=timezone.utc).isoformat()
                if observation.created_at else None,
            ))
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany("""
                INSERT OR IGNORE INTO market_observations
                (id, source, signal_type, observed_at, period, location, scope,
                 skill, value, unit, denominator_unit, source_url, posting_id, metadata_json, history_type, data_origin,
                 skill_id, denominator, fetch_run_id, series_id, query_id,
                 panel_version, quality_json, confidence, observation_count,
                 extractor_version, annotations_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            inserted = connection.total_changes - before
            if inserted:
                connection.execute("DELETE FROM market_calculation_cache")
            return inserted

    def get_observations(
        self,
        *,
        location: str | None = None,
        cutoff: datetime | None = None,
        skill: str | None = None,
    ) -> list[MarketObservation]:
        clauses = []
        params: list[Any] = []
        if cutoff:
            clauses.append("observed_at >= ?")
            params.append(cutoff.astimezone(timezone.utc).isoformat())
        if skill:
            clauses.append("lower(skill) = lower(?)")
            params.append(skill.strip())
        if location:
            clauses.append(
                "(lower(location) = lower(?) OR lower(location) LIKE lower(?))"
            )
            params.extend((location.strip(), f"{location.strip()},%"))
        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM market_observations{where_clause} ORDER BY period, source, skill",
                params,
            ).fetchall()
        results = []
        for row in rows:
            if row["history_type"] not in {"backfill", "platform_collected", "snapshot", "static_dataset", None}:
                continue
            if row["data_origin"] not in {"real", "demo", None}:
                continue
            try:
                results.append(MarketObservation(
                    id=row["id"],
                    source=row["source"],
                    signal_type=row["signal_type"],
                    observed_at=datetime.fromisoformat(row["observed_at"]),
                    period=row["period"],
                    location=row["location"],
                    scope=row["scope"],
                    skill=row["skill"],
                    value=row["value"],
                    unit=row["unit"],
                    denominator_unit=row["denominator_unit"],
                    source_url=row["source_url"],
                    posting_id=row["posting_id"],
                    metadata=json.loads(row["metadata_json"]),
                    skill_id=row["skill_id"],
                    history_type=row["history_type"],
                    data_origin=row["data_origin"],
                    fetch_run_id=row["fetch_run_id"],
                    series_id=row["series_id"],
                    query_id=row["query_id"],
                    panel_version=row["panel_version"],
                    denominator=row["denominator"],
                    quality=json.loads(row["quality_json"]) if row["quality_json"] else None,
                    confidence=row["confidence"],
                    observation_count=row["observation_count"],
                    extractor_version=row["extractor_version"],
                    annotations=json.loads(row["annotations_json"]) if row["annotations_json"] else [],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                ))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping invalid SQLite market observation (%s)", type(exc).__name__)
        return results

    def get_cached(self, cache_key: str, *, max_age_seconds: int = 3600) -> list[dict[str, Any]] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at, payload_json FROM market_calculation_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        created_at = datetime.fromisoformat(row["created_at"])
        age = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()
        if age > max_age_seconds:
            return None
        return json.loads(row["payload_json"])

    def put_cached(self, cache_key: str, payload: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO market_calculation_cache (cache_key, created_at, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    created_at = excluded.created_at,
                    payload_json = excluded.payload_json
            """, (
                cache_key,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, separators=(",", ":")),
            ))

    def record_collection_start(
        self,
        *,
        run_id: str,
        started_at: datetime,
        location: str | None,
        country: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO market_collection_runs
                (run_id, started_at, status, location, country)
                VALUES (?, ?, 'running', ?, ?)
            """, (run_id, started_at.isoformat(), location, country))

    def record_collection_finish(
        self,
        *,
        run_id: str,
        completed_at: datetime,
        status: str,
        observations_inserted: int,
        sources_succeeded: list[str],
        sources_failed: dict[str, str],
    ) -> None:
        with self._connect() as connection:
            connection.execute("""
                UPDATE market_collection_runs
                SET completed_at = ?, status = ?, observations_inserted = ?,
                    sources_succeeded_json = ?, sources_failed_json = ?
                WHERE run_id = ?
            """, (
                completed_at.isoformat(),
                status,
                observations_inserted,
                json.dumps(sources_succeeded),
                json.dumps(sources_failed),
                run_id,
            ))

    def collection_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS observations,
                       COUNT(DISTINCT period) AS periods,
                       COUNT(DISTINCT source) AS sources,
                       MAX(observed_at) AS latest_observation
                FROM market_observations
            """).fetchone()
            run = connection.execute("""
                SELECT status, completed_at, observations_inserted
                FROM market_collection_runs
                ORDER BY started_at DESC LIMIT 1
            """).fetchone()
        return {
            "observations": row["observations"],
            "periods": row["periods"],
            "sources": row["sources"],
            "latest_observation": row["latest_observation"],
            "last_collection": dict(run) if run else None,
        }

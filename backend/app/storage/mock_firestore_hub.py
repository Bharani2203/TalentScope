"""In-memory Firestore client and explicitly synthetic dataset for unit tests."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from google.cloud.firestore_v1 import FieldFilter

from app.models.skill_intelligence import MarketObservation
from app.storage.observation_identity import stable_observation_id


class MockSnapshot:
    def __init__(self, document_id: str, data: dict[str, Any] | None) -> None:
        self.id = document_id
        self._data = copy.deepcopy(data) if data is not None else None
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data)


class MockDocRef:
    def __init__(self, collection: MockCollection, document_id: str) -> None:
        self._collection = collection
        self.id = document_id

    def get(self) -> MockSnapshot:
        data = self._collection.records.get(self.id)
        return MockSnapshot(self.id, data)

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if merge and self.id in self._collection.records:
            self._collection.records[self.id].update(copy.deepcopy(data))
        else:
            self._collection.records[self.id] = copy.deepcopy(data)

    def update(self, data: dict[str, Any]) -> None:
        if self.id in self._collection.records:
            self._collection.records[self.id].update(copy.deepcopy(data))
        else:
            self._collection.records[self.id] = copy.deepcopy(data)

    def create(self, data: dict[str, Any]) -> None:
        from google.api_core.exceptions import AlreadyExists
        if self.id in self._collection.records:
            raise AlreadyExists(f"Document {self.id} already exists")
        self._collection.records[self.id] = copy.deepcopy(data)

    def collection(self, name: str) -> MockCollection:
        return self._collection.client.collection(f"{self._collection.name}/{self.id}/{name}")


class MockQuery:
    def __init__(self, collection: MockCollection, filters: list[Any] | None = None, limit_val: int | None = None, order_field: str | None = None, order_desc: bool = False) -> None:
        self._collection = collection
        self._filters = list(filters or [])
        self._limit = limit_val
        self._order_field = order_field
        self._order_desc = order_desc

    def where(self, *args, **kwargs) -> MockQuery:
        filter_arg = kwargs.get("filter")
        if filter_arg is not None:
            new_filters = list(self._filters) + [filter_arg]
            return MockQuery(self._collection, new_filters, self._limit, self._order_field, self._order_desc)
        if len(args) == 3:
            field_name, op_str, value = args
            filter_arg = FieldFilter(field_name, op_str, value)
            new_filters = list(self._filters) + [filter_arg]
            return MockQuery(self._collection, new_filters, self._limit, self._order_field, self._order_desc)
        return self

    def limit(self, count: int) -> MockQuery:
        return MockQuery(self._collection, self._filters, count, self._order_field, self._order_desc)

    def order_by(self, field_name: str, direction: Any = None) -> MockQuery:
        desc = direction is not None and ("DESC" in str(direction).upper())
        return MockQuery(self._collection, self._filters, self._limit, field_name, desc)

    def stream(self) -> list[MockSnapshot]:
        matched = []
        for doc_id, data in self._collection.records.items():
            matches = True
            for f in self._filters:
                field_name = getattr(f, "field_path", None)
                op_str = getattr(f, "op_string", "==")
                target_val = getattr(f, "value", None)
                val = data.get(field_name)

                if op_str == "==":
                    if val != target_val:
                        matches = False
                        break
                elif op_str == ">=":
                    if val is None or val < target_val:
                        matches = False
                        break
                elif op_str == "<=":
                    if val is None or val > target_val:
                        matches = False
                        break
                elif op_str == ">":
                    if val is None or val <= target_val:
                        matches = False
                        break
                elif op_str == "<":
                    if val is None or val >= target_val:
                        matches = False
                        break
                elif op_str in ("in", "IN"):
                    if val not in target_val:
                        matches = False
                        break

            if matches:
                matched.append(MockSnapshot(doc_id, data))

        if self._order_field:
            matched.sort(
                key=lambda s: (s.to_dict() or {}).get(self._order_field) or "",
                reverse=self._order_desc,
            )

        if self._limit is not None:
            matched = matched[:self._limit]

        return matched


class MockCollection:
    def __init__(self, name: str, client: MockFirestoreClient) -> None:
        self.name = name
        self.client = client
        self.records: dict[str, dict[str, Any]] = {}

    def document(self, document_id: str) -> MockDocRef:
        return MockDocRef(self, document_id)

    def where(self, *args, **kwargs) -> MockQuery:
        return MockQuery(self).where(*args, **kwargs)

    def limit(self, count: int) -> MockQuery:
        return MockQuery(self).limit(count)

    def order_by(self, field_name: str, direction: Any = None) -> MockQuery:
        return MockQuery(self).order_by(field_name, direction)

    def stream(self) -> list[MockSnapshot]:
        return [MockSnapshot(doc_id, data) for doc_id, data in self.records.items()]


class MockBatch:
    def __init__(self) -> None:
        self._ops: list[tuple[MockDocRef, dict[str, Any]]] = []

    def set(self, reference: MockDocRef, payload: dict[str, Any]) -> None:
        self._ops.append((reference, payload))

    def commit(self) -> None:
        for ref, payload in self._ops:
            ref.set(payload)
        self._ops.clear()


class MockFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, MockCollection] = {}

    def collection(self, name: str) -> MockCollection:
        return self.collections.setdefault(name, MockCollection(name, self))

    def batch(self) -> MockBatch:
        return MockBatch()


def create_demo_test_snapshot() -> MockFirestoreClient:
    """Build an in-memory demo dataset for deterministic storage and analytics tests."""
    client = MockFirestoreClient()
    signals_coll = client.collection("skill_market_signals")
    runs_coll = client.collection("fetch_runs")

    now = datetime.now(timezone.utc)
    current_period = now.strftime("%Y-%m")
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. 86 JSearch demo demand observations in the current month.
    skills_for_jsearch = [
        ("Python", "python"), ("Java", "java"), ("JavaScript", "javascript"),
        ("TypeScript", "typescript"), ("C#", "c_sharp"), ("C++", "c_plus_plus"),
        ("Go", "go"), ("Rust", "rust"), ("React", "react"), ("Docker", "docker"),
        ("Kubernetes", "kubernetes"), ("AWS", "aws"), ("SQL", "sql"), ("PostgreSQL", "postgresql"),
    ]
    jsearch_count = 0
    for idx in range(86):
        skill_name, skill_id = skills_for_jsearch[idx % len(skills_for_jsearch)]
        post_id = f"post_jsearch_{current_period}_{idx}"
        obs = MarketObservation(
            id=None,
            source="jsearch",
            signal_type="demand",
            observed_at=current_month_start,
            period=current_period,
            location="Global",
            scope="global",
            skill=skill_name,
            skill_id=skill_id,
            value=1.0,
            posting_id=post_id,
            metadata={"raw_archive_id": f"raw_jsearch_{current_period}_{idx}"},
            data_origin="demo",
            history_type="platform_collected",
            series_id=f"jsearch:job-demand-v1:job-demand:{skill_id}:v1",
            panel_version="job-demand-v1",
            fetch_run_id=f"run_jsearch_{current_period}",
        )
        obs_id = stable_observation_id(obs)
        signals_coll.records[obs_id] = {
            "observation_id": obs_id,
            "source": "jsearch",
            "signal_type": "demand",
            "observed_at": current_month_start,
            "period": current_period,
            "location": "Global",
            "scope": "global",
            "skill": skill_name,
            "skill_id": skill_id,
            "value": 1.0,
            "posting_id": post_id,
            "metadata": {"raw_archive_id": f"raw_jsearch_{current_period}_{idx}"},
            "data_origin": "demo",
            "history_type": "platform_collected",
            "series_id": f"jsearch:job-demand-v1:job-demand:{skill_id}:v1",
            "panel_version": "job-demand-v1",
            "fetch_run_id": f"run_jsearch_{current_period}",
        }
        jsearch_count += 1

    # 2. 1 Adzuna demo demand observation in the current month.
    adzuna_obs = MarketObservation(
        id=None,
        source="adzuna",
        signal_type="demand",
        observed_at=current_month_start,
        period=current_period,
        location="Global",
        scope="global",
        skill="C#",
        skill_id="c_sharp",
        value=1.0,
        posting_id=f"post_adzuna_{current_period}_0",
        metadata={"raw_archive_id": f"raw_adzuna_{current_period}_0"},
        data_origin="demo",
        history_type="platform_collected",
        series_id="adzuna:job-demand-v1:job-demand:c_sharp:v1",
        panel_version="job-demand-v1",
        fetch_run_id=f"run_adzuna_{current_period}",
    )
    adzuna_id = stable_observation_id(adzuna_obs)
    signals_coll.records[adzuna_id] = {
        "observation_id": adzuna_id,
        "source": "adzuna",
        "signal_type": "demand",
        "observed_at": current_month_start,
        "period": current_period,
        "location": "Global",
        "scope": "global",
        "skill": "C#",
        "skill_id": "c_sharp",
        "value": 1.0,
        "posting_id": f"post_adzuna_{current_period}_0",
        "metadata": {"raw_archive_id": f"raw_adzuna_{current_period}_0"},
        "data_origin": "demo",
        "history_type": "platform_collected",
        "series_id": "adzuna:job-demand-v1:job-demand:c_sharp:v1",
        "panel_version": "job-demand-v1",
        "fetch_run_id": f"run_adzuna_{current_period}",
    }

    # 3. 3 GitHub demo adoption observations in distinct query/panel series.
    for idx, (sk, sid, qid, pv) in enumerate([
        ("Python", "python", "q_v1", "panel_v1"),
        ("Python", "python", "q_v2", "panel_v2"),
        ("Python", "python", "q_v3", "panel_v3"),
    ]):
        gh_obs = MarketObservation(
            id=None,
            source="github",
            signal_type="adoption",
            observed_at=current_month_start,
            period=current_period,
            location="Global",
            scope="global",
            skill=sk,
            skill_id=sid,
            value=100.0 + idx * 10,
            posting_id=f"gh_topic_python_{idx}",
            metadata={"raw_archive_id": f"raw_github_{current_period}_{idx}"},
            data_origin="demo",
            history_type="snapshot",
            series_id="github:repository-topic:python:v1",
            panel_version=pv,
            query_id=qid,
            fetch_run_id=f"run_github_{current_period}",
        )
        gh_id = stable_observation_id(gh_obs)
        signals_coll.records[gh_id] = {
            "observation_id": gh_id,
            "source": "github",
            "signal_type": "adoption",
            "observed_at": current_month_start,
            "period": current_period,
            "location": "Global",
            "scope": "global",
            "skill": sk,
            "skill_id": sid,
            "value": 100.0 + idx * 10,
            "posting_id": f"gh_topic_python_{idx}",
            "metadata": {"raw_archive_id": f"raw_github_{current_period}_{idx}"},
            "data_origin": "demo",
            "history_type": "snapshot",
            "series_id": "github:repository-topic:python:v1",
            "panel_version": pv,
            "query_id": qid,
            "fetch_run_id": f"run_github_{current_period}",
        }

    # 4. 10 Stack Exchange interest observations (5 for Python, 5 for C#)
    current_month_index = now.year * 12 + now.month - 1
    periods = []
    for offset in range(5, 0, -1):
        year, month_index = divmod(current_month_index - offset, 12)
        periods.append(f"{year:04d}-{month_index + 1:02d}")
    for i, p in enumerate(periods):
        p_dt = datetime.fromisoformat(f"{p}-15T12:00:00+00:00")
        # Python
        py_obs = MarketObservation(
            id=None,
            source="stackexchange",
            signal_type="interest",
            observed_at=p_dt,
            period=p,
            location="Global",
            scope="global",
            skill="Python",
            skill_id="python",
            value=50.0 + i * 5.0,
            posting_id=f"se_py_{p}",
            metadata={"raw_archive_id": f"raw_se_py_{p}"},
            data_origin="demo",
            history_type="backfill",
            series_id="stackexchange:stackoverflow:question-tag:python:v1",
            panel_version="tag-v1",
            fetch_run_id=f"run_se_{p}",
        )
        py_id = stable_observation_id(py_obs)
        signals_coll.records[py_id] = {
            "observation_id": py_id,
            "source": "stackexchange",
            "signal_type": "interest",
            "observed_at": p_dt,
            "period": p,
            "location": "Global",
            "scope": "global",
            "skill": "Python",
            "skill_id": "python",
            "value": 50.0 + i * 5.0,
            "posting_id": f"se_py_{p}",
            "metadata": {"raw_archive_id": f"raw_se_py_{p}"},
            "data_origin": "demo",
            "history_type": "backfill",
            "series_id": "stackexchange:stackoverflow:question-tag:python:v1",
            "panel_version": "tag-v1",
            "fetch_run_id": f"run_se_{p}",
        }

        # C#
        cs_obs = MarketObservation(
            id=None,
            source="stackexchange",
            signal_type="interest",
            observed_at=p_dt,
            period=p,
            location="Global",
            scope="global",
            skill="C#",
            skill_id="c_sharp",
            value=30.0 + i * 3.0,
            posting_id=f"se_cs_{p}",
            metadata={"raw_archive_id": f"raw_se_cs_{p}"},
            data_origin="demo",
            history_type="backfill",
            series_id="stackexchange:stackoverflow:question-tag:c#:v1",
            panel_version="tag-v1",
            fetch_run_id=f"run_se_{p}",
        )
        cs_id = stable_observation_id(cs_obs)
        signals_coll.records[cs_id] = {
            "observation_id": cs_id,
            "source": "stackexchange",
            "signal_type": "interest",
            "observed_at": p_dt,
            "period": p,
            "location": "Global",
            "scope": "global",
            "skill": "C#",
            "skill_id": "c_sharp",
            "value": 30.0 + i * 3.0,
            "posting_id": f"se_cs_{p}",
            "metadata": {"raw_archive_id": f"raw_se_cs_{p}"},
            "data_origin": "demo",
            "history_type": "backfill",
            "series_id": "stackexchange:stackoverflow:question-tag:c#:v1",
            "panel_version": "tag-v1",
            "fetch_run_id": f"run_se_{p}",
        }

    # Fetch runs summary and per-observation run provenance
    for prov in ["jsearch", "adzuna", "github", "stackexchange"]:
        # Latest runs
        r_id = f"run_{prov}_latest"
        runs_coll.records[r_id] = {
            "run_id": r_id,
            "source": prov,
            "status": "success",
            "started_at": now,
            "completed_at": now,
            "raw_response_archive": {
                "archive_reference": f"raw_response_archives/{prov}__{r_id}__meta",
            },
        }
        # Current-month run.
        p_run_id = f"run_{prov}_{current_period}"
        runs_coll.records[p_run_id] = {
            "run_id": p_run_id,
            "source": prov,
            "status": "success",
            "started_at": now,
            "completed_at": now,
            "raw_response_archive": {
                "archive_reference": f"raw_response_archives/{prov}__{p_run_id}__meta",
            },
        }

    for p in periods:
        se_run_id = f"run_se_{p}"
        runs_coll.records[se_run_id] = {
            "run_id": se_run_id,
            "source": "stackexchange",
            "status": "success",
            "started_at": datetime.fromisoformat(f"{p}-15T10:00:00+00:00"),
            "completed_at": datetime.fromisoformat(f"{p}-15T10:05:00+00:00"),
            "raw_response_archive": {
                "archive_reference": f"raw_response_archives/stackexchange__{se_run_id}__meta",
            },
        }

    return client


def get_demo_firestore_client() -> MockFirestoreClient:
    """Return a fresh demo client; each test owns its records and mutations."""
    return create_demo_test_snapshot()

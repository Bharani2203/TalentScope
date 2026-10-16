from copy import deepcopy

import pytest

from app.storage.calculation_record_store import (
    CalculationRecordConflict,
    FirestoreCalculationRecordStore,
)


class Snapshot:
    def __init__(self, value):
        self.value = deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self.value)


class Document:
    def __init__(self, collection, key):
        self.collection = collection
        self.id = key

    def get(self):
        return Snapshot(self.collection.values.get(self.id))

    def create(self, value):
        if self.id in self.collection.values:
            from google.api_core.exceptions import AlreadyExists
            raise AlreadyExists("exists")
        self.collection.values[self.id] = deepcopy(value)


class Collection:
    def __init__(self, values=None):
        self.values = values if values is not None else {}

    def document(self, key):
        return Document(self, key)


class Client:
    def __init__(self):
        self.collections = {
            "skill_market_signals": Collection({"obs-1": {
                "observation_id": "obs-1", "source": "adzuna", "data_origin": "real",
                "history_type": "platform_collected", "series_id": "adzuna:panel:job-demand:c_sharp:v1",
                "fetch_run_id": "run-1", "extractor_version": None,
            }}),
            "fetch_runs": Collection({"run-1": {
                "run_id": "run-1", "source": "adzuna",
                "raw_response_archive": {"archive_reference": "raw_response_archives/adzuna__run-1__000000"},
            }}),
            "calculation_records": Collection(),
        }

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


def snapshot():
    return {
        "metric": "source_specific_demand_share", "value": 1.0, "source": "adzuna",
        "series_id": "adzuna:panel:job-demand:c_sharp:v1", "period": "2026-10",
        "data_origin": "real", "history_type": "platform_collected",
        "data_state": "insufficient_data", "confidence": None,
        "coverage": {"observation_count": 1, "source_job_count": 1, "period_count": 1},
        "evidence": {
            "observation_ids": ["obs-1"], "fetch_run_ids": ["run-1"],
            "calculation_version": "demand-theil-sen-v2-source-specific",
            "panel_version": "job-demand-v1", "query_id": "adzuna:panel",
            "scope": "country", "minimum_trend_periods": 4,
            "collected_at": "2026-10-07T00:00:00+00:00",
        },
    }


def test_calculation_record_is_persisted_idempotently_with_provenance():
    client = Client()
    store = FirestoreCalculationRecordStore(client)

    first = store.persist_current_demand([snapshot()], window="6m")
    second = store.persist_current_demand([snapshot()], window="6m")

    assert first == second
    assert len(client.collections["calculation_records"].values) == 1
    record = next(iter(client.collections["calculation_records"].values.values()))
    assert record["result"] == {"value": 1.0, "confidence": None}
    assert record["data_state"] == "insufficient_data"
    assert record["source"] == "adzuna"
    assert record["series_id"] == snapshot()["series_id"]
    assert record["fetch_run_ids"] == ["run-1"]
    assert record["observation_ids"] == ["obs-1"]
    assert record["inputs"][0]["archive_reference"].startswith("raw_response_archives/")


def test_calculation_record_detects_changed_result_for_same_inputs():
    client = Client()
    store = FirestoreCalculationRecordStore(client)
    store.persist_current_demand([snapshot()], window="6m")
    changed = snapshot()
    changed["value"] = 0.75

    with pytest.raises(CalculationRecordConflict):
        store.persist_current_demand([changed], window="6m")

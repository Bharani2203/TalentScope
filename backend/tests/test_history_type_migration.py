from datetime import datetime, timezone

from app.services.history_type_migration import deterministic_history_type, normalize_history_types


class Snapshot:
    def __init__(self, document_id, record):
        self.id = document_id
        self.record = record

    def to_dict(self):
        return dict(self.record)


class Document:
    def __init__(self, records, document_id):
        self.records = records
        self.document_id = document_id

    def update(self, updates):
        self.records[self.document_id].update(updates)


class Collection:
    def __init__(self, records):
        self.records = records

    def stream(self):
        return [Snapshot(key, value) for key, value in self.records.items()]

    def document(self, document_id):
        return Document(self.records, document_id)


class Database:
    def __init__(self, records):
        self.records = records

    def collection(self, name):
        assert name == "skill_market_signals"
        return Collection(self.records)


def row(source, signal, history):
    return {"source": source, "signal_type": signal, "history_type": history,
            "observed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}


def test_history_alias_mappings_require_deterministic_source_and_signal():
    assert deterministic_history_type(row("github", "adoption", "adoption_snapshot")) == "snapshot"
    assert deterministic_history_type(row("jsearch", "demand", "observed_signal")) == "platform_collected"
    assert deterministic_history_type(row("stack_exchange", "interest", "observed_signal")) == "backfill"
    assert deterministic_history_type(row("unknown", "context", "observed_signal")) is None
    assert deterministic_history_type(row("github", "demand", "adoption_snapshot")) is None


def test_history_migration_dry_run_apply_and_rerun_are_auditable_and_idempotent():
    database = Database({
        "snapshot-legacy": row("github", "adoption", "adoption_snapshot"),
        "demand-legacy": row("jsearch", "demand", "observed_signal"),
        "backfill-legacy": row("stack_exchange", "interest", "observed_signal"),
        "unknown": row("unknown", "context", "made_up"),
        "ambiguous": row("github", "demand", "adoption_snapshot"),
        "normalized": row("github", "adoption", "snapshot"),
        "missing-fields": {"history_type": "adoption_snapshot"},
    })

    dry_run = normalize_history_types(client=database)
    assert dry_run["total_scanned"] == 7
    assert dry_run["already_normalized"] == 1
    assert dry_run["legacy_aliases_found"] == 4
    assert dry_run["would_normalize"] == 3
    assert dry_run["normalized"] == 0
    assert dry_run["withheld"] == 1
    assert dry_run["unknown"] == 1
    assert dry_run["skipped"] == 1
    assert dry_run["failed"] == 0
    assert database.records["snapshot-legacy"]["history_type"] == "adoption_snapshot"

    applied = normalize_history_types(apply=True, client=database)
    assert applied["normalized"] == 3
    assert database.records["snapshot-legacy"]["history_type"] == "snapshot"
    assert database.records["demand-legacy"]["history_type"] == "platform_collected"
    assert database.records["backfill-legacy"]["history_type"] == "backfill"

    rerun = normalize_history_types(apply=True, client=database)
    assert rerun["normalized"] == 0
    assert rerun["already_normalized"] == 4


def test_static_dataset_is_accepted_without_inference_or_rewrite():
    database = Database({"static": row("manual", "context", "static_dataset")})

    result = normalize_history_types(apply=True, client=database)

    assert result["already_normalized"] == 1
    assert result["normalized"] == 0
    assert database.records["static"]["history_type"] == "static_dataset"

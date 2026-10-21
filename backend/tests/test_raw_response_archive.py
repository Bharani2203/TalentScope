import asyncio
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.market_collection_service import collect_market_data
from app.storage.raw_archive_backend import (
    ArchiveConflictError,
    FirestoreRawArchiveBackend,
    RawArchiveError,
)
from app.storage.raw_response_archive import FirestoreRawResponseArchive


class Snapshot:
    def __init__(self, reference, data):
        self.reference = reference
        self.id = reference.id
        self.exists = data is not None
        self._data = deepcopy(data)

    def to_dict(self):
        return deepcopy(self._data)


class Document:
    def __init__(self, client, path):
        self.client = client
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def get(self):
        return Snapshot(self, self.client.records.get(self.path))

    def create(self, data):
        if self.path in self.client.records:
            raise RuntimeError("duplicate document")
        self.client.records[self.path] = deepcopy(data)
        self.client.transitions.append((self.path, data.get("status")))

    def set(self, data, merge=False):
        value = self.client.records.get(self.path, {}) if merge else {}
        self.client.records[self.path] = {**deepcopy(value), **deepcopy(data)}

    def update(self, data):
        if self.path not in self.client.records:
            raise RuntimeError("document missing")
        self.client.records[self.path].update(deepcopy(data))
        if "status" in data:
            self.client.transitions.append((self.path, data["status"]))

    def delete(self):
        self.client.records.pop(self.path, None)

    def collection(self, name):
        return Collection(self.client, f"{self.path}/{name}")


class Collection:
    def __init__(self, client, path):
        self.client = client
        self.path = path

    def document(self, document_id):
        return Document(self.client, f"{self.path}/{document_id}")

    def stream(self):
        prefix = self.path + "/"
        docs = []
        for path, data in self.client.records.items():
            if path.startswith(prefix) and "/" not in path[len(prefix):]:
                docs.append(Snapshot(Document(self.client, path), data))
        return iter(docs)


class Batch:
    def __init__(self, client):
        self.client = client
        self.actions = []

    def set(self, reference, data):
        self.actions.append(("set", reference, deepcopy(data)))

    def delete(self, reference):
        self.actions.append(("delete", reference, None))

    def commit(self):
        if self.client.fail_next_batch:
            self.client.fail_next_batch = False
            raise RuntimeError("simulated private firestore failure")
        for operation, reference, data in self.actions:
            if operation == "set":
                reference.set(data)
            else:
                reference.delete()


class FakeFirestore:
    def __init__(self):
        self.records = {}
        self.transitions = []
        self.fail_next_batch = False

    def collection(self, name):
        return Collection(self, name)

    def batch(self):
        return Batch(self)


def make_archive(*, chunk_size=None):
    client = FakeFirestore()
    backend = FirestoreRawArchiveBackend(client)
    if chunk_size is not None:
        backend.chunk_size = chunk_size
    return FirestoreRawResponseArchive(backend), client


def write_archive(archive, payload=None, *, response_index=0, fetch_run_id="run-123", provider="github"):
    return archive.archive(
        provider=provider,
        fetch_run_id=fetch_run_id,
        collected_at=datetime(2026, 10, 6, 3, 15, tzinfo=timezone.utc),
        payload=payload if payload is not None else {"total_count": 1, "items": [{"id": 7, "name": "sample"}]},
        content_type="application/json; charset=utf-8",
        response_index=response_index,
    )


def test_deterministic_archive_id_and_response_index():
    archive, _ = make_archive()
    first = write_archive(archive)
    replay, _ = make_archive()
    same = write_archive(replay)
    other_index = write_archive(archive, response_index=1)

    assert first["archive_reference"] == same["archive_reference"]
    assert first["archive_reference"] == "raw_response_archives/github__run-123__000000"
    assert other_index["archive_reference"] != first["archive_reference"]
    assert other_index["fetch_run_id"] == first["fetch_run_id"]


def test_sanitization_and_compact_sorted_utf8_contract():
    archive, _ = make_archive()
    reference = write_archive(archive, {
        "total_count": 1,
        "items": [{"id": 7, "name": "café", "token": "must-not-be-kept"}],
        "Authorization": "Bearer must-not-be-kept",
        "headers": {"X-API-Key": "must-not-be-kept"},
    })
    read = archive.read(reference["archive_reference"])
    expected = '{"items":[{"id":7,"name":"café"}],"total_count":1}'.encode("utf-8")

    assert read["payload_bytes"] == expected
    assert read["payload"] == {"items": [{"id": 7, "name": "café"}], "total_count": 1}
    assert b"must-not-be-kept" not in read["payload_bytes"]
    assert reference["sha256"] == hashlib.sha256(expected).hexdigest()


def test_small_payload_metadata_and_write_lifecycle():
    archive, client = make_archive()
    reference = write_archive(archive)
    metadata_path = reference["archive_reference"]
    metadata = client.records[metadata_path]
    chunks = [value for key, value in client.records.items() if key.startswith(metadata_path + "/chunks/")]

    assert metadata["status"] == "complete"
    assert metadata["size_bytes"] == reference["size_bytes"]
    assert metadata["chunk_count"] == len(chunks) == 1
    assert metadata["provider"] == metadata["source"] == "github"
    assert metadata["fetch_run_id"] == "run-123"
    assert metadata["response_index"] == 0
    assert metadata["archive_reference"] == metadata_path
    assert "payload_bytes" not in metadata
    assert client.transitions[-2:] == [(metadata_path, "writing"), (metadata_path, "complete")]


def test_large_unicode_payload_round_trips_across_256_kib_chunks():
    archive, client = make_archive()
    value = "A🙂漢字" * 50_000
    reference = write_archive(archive, {"total_count": 1, "items": [{"id": 8, "name": value}]})
    read = archive.read(reference["archive_reference"])
    chunk_docs = [value for key, value in client.records.items()
                  if key.startswith(reference["archive_reference"] + "/chunks/")]
    chunk_count = client.records[reference["archive_reference"]]["chunk_count"]
    expected = json.dumps(
        {"total_count": 1, "items": [{"id": 8, "name": value}]},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")

    assert len(read["payload_bytes"]) > 256 * 1024
    assert len(chunk_docs) == chunk_count > 1
    assert read["payload_bytes"] == expected
    assert b"".join(chunk["payload_bytes"] for chunk in sorted(
        chunk_docs, key=lambda item: item["index"],
    )) == expected
    assert all(len(chunk["payload_bytes"]) <= 256 * 1024 for chunk in chunk_docs)
    assert client.records[reference["archive_reference"]]["checksum"] == hashlib.sha256(expected).hexdigest()
    assert client.records[reference["archive_reference"]]["size_bytes"] == len(expected)


def test_incomplete_archive_is_not_readable_and_can_be_cleaned_up():
    archive, client = make_archive()
    reference = write_archive(archive)
    metadata_path = reference["archive_reference"]
    client.records[metadata_path]["status"] = "writing"
    with pytest.raises(RawArchiveError, match="incomplete"):
        archive.read(metadata_path)
    archive.delete(metadata_path)
    assert metadata_path not in client.records
    assert not any(path.startswith(metadata_path + "/chunks/") for path in client.records)


@pytest.mark.parametrize("corruption, message", [
    ("missing", "chunk count"),
    ("wrong_index", "chunk index"),
    ("checksum", "checksum"),
    ("size", "size"),
])
def test_read_detects_corrupt_or_missing_archive_data(corruption, message):
    archive, client = make_archive()
    reference = write_archive(archive)
    archive_path = reference["archive_reference"]
    chunk_path = archive_path + "/chunks/00000000"
    if corruption == "missing":
        del client.records[chunk_path]
    elif corruption == "wrong_index":
        client.records[chunk_path]["index"] = 1
    elif corruption == "checksum":
        client.records[archive_path]["checksum"] = "0" * 64
    else:
        client.records[archive_path]["size_bytes"] += 1

    with pytest.raises(RawArchiveError, match=message):
        archive.read(archive_path)


def test_idempotent_write_validates_existing_complete_archive():
    archive, client = make_archive()
    first = write_archive(archive)
    original_chunk_count = len(client.records)
    second = write_archive(archive)

    assert second["archive_reference"] == first["archive_reference"]
    assert len(client.records) == original_chunk_count


def test_conflicting_deterministic_archive_is_rejected_without_leaking_data():
    archive, _ = make_archive()
    first = write_archive(archive)
    with pytest.raises(ArchiveConflictError, match="Conflicting raw response archive") as error:
        write_archive(archive, {"total_count": 2, "items": []})
    assert "sample" not in str(error.value)
    assert "secret" not in str(error.value)
    assert first["archive_reference"] == "raw_response_archives/github__run-123__000000"


def test_failed_chunk_write_stays_incomplete_and_returns_safe_error():
    archive, client = make_archive()
    client.fail_next_batch = True
    with pytest.raises(RawArchiveError, match="could not be stored") as error:
        write_archive(archive)
    metadata = next(iter(client.records.values()))
    assert metadata["status"] == "writing"
    assert metadata["last_error"] == "archive_write_failed"
    assert "simulated private" not in str(error.value)


def test_delete_removes_complete_and_partial_archive_documents():
    archive, client = make_archive()
    reference = write_archive(archive)
    archive_path = reference["archive_reference"]
    archive.delete(archive_path)
    assert not any(path == archive_path or path.startswith(archive_path + "/") for path in client.records)

    # A partial archive with matching metadata can also be cleaned up safely.
    partial_path = "raw_response_archives/github__partial-run__000000"
    client.records[partial_path] = {"archive_id": "github__partial-run__000000", "status": "writing"}
    client.records[partial_path + "/chunks/00000000"] = {"index": 0, "payload_bytes": b"partial"}
    archive.delete(partial_path)
    assert not any(path == partial_path or path.startswith(partial_path + "/") for path in client.records)


def test_delete_rejects_archive_identity_mismatch_without_removing_documents():
    archive, client = make_archive()
    reference = write_archive(archive)
    archive_path = reference["archive_reference"]
    client.records[archive_path]["archive_id"] = "different__archive__000000"

    with pytest.raises(RawArchiveError, match="identity verification failed"):
        archive.delete(archive_path)
    assert archive_path in client.records
    assert archive_path + "/chunks/00000000" in client.records


def test_firestore_config_exempts_chunk_payload_from_indexing():
    config_path = Path(__file__).resolve().parents[2] / "firestore.indexes.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    exemption = next(
        item for item in config["fieldOverrides"]
        if item["collectionGroup"] == "chunks" and item["fieldPath"] == "payload_bytes"
    )
    assert exemption["indexes"] == []


def test_fetch_run_keeps_archive_reference_and_existing_call_contract():
    """Archive retention does not turn an unverified empty result into a complete run."""
    class FetchRuns:
        def __init__(self):
            self.records = {}

        def start(self, run_id, record):
            self.records[run_id] = dict(record)

        def finish(self, run_id, record):
            self.records[run_id].update(record)

        def collection_summary(self):
            return {"last_collection": {"providers": {}}}

    class Observations:
        def insert_observations(self, observations, **kwargs):
            return len(observations)

    class Collector:
        name = "github"

        async def collect_observations(self, **kwargs):
            kwargs["archive_response"]({"total_count": 1, "items": []}, "application/json")
            return []

    fetch_runs = FetchRuns()
    archive, _ = make_archive()
    result = asyncio.run(collect_market_data(
        settings=Settings(_env_file=None), providers=[Collector()],
        fetch_run_store=fetch_runs, observation_store=Observations(),
        raw_response_archive=archive,
    ))
    run_id, run = next(iter(fetch_runs.records.items()))
    stored_archive = run["raw_response_archive"]
    assert result.status == "partial_failure"
    assert result.providers[0].status == "partial"
    assert result.providers[0].coverage_status == "partial"
    assert stored_archive["fetch_run_id"] == run_id
    assert stored_archive["provider"] == "github"
    assert stored_archive["archive_reference"].startswith("raw_response_archives/github__")
    assert stored_archive["size_bytes"] > 0

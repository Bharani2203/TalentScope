import json
from types import SimpleNamespace

import pytest
from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, ServiceUnavailable
from google.cloud import firestore
from google.oauth2 import service_account

from app.core.firestore_status import firestore_runtime_label
from app.scripts import copy_firestore_real_to_emulator as real_to_emulator
from app.scripts import sync_firestore_emulator_to_real as emulator_to_real
from app.scripts import firestore_copy_common as copy_common


class Snapshot:
    def __init__(self, doc_id, data=None):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class DocumentRef:
    def __init__(self, collection, doc_id):
        self.collection_name = collection
        self.id = doc_id


class Collection:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def list_documents(self):
        return iter(DocumentRef(self.name, key) for key in self.client.data.get(self.name, {}))

    def document(self, doc_id):
        return DocumentRef(self.name, doc_id)


class Batch:
    def __init__(self, client):
        self.client = client
        self.pending = []

    def create(self, ref, data):
        self.pending.append((ref.collection_name, ref.id, data))

    def commit(self):
        self.client.batch_number += 1
        self.client.batch_sizes.append(len(self.pending))
        if self.client.fail_on_batch == self.client.batch_number:
            raise ResourceExhausted("mock quota exhausted")
        for collection, doc_id, data in self.pending:
            if doc_id not in self.client.data.setdefault(collection, {}):
                self.client.data[collection][doc_id] = data


class Client:
    def __init__(self, data=None, *, fail_on_batch=None):
        self.data = data or {}
        self.fail_on_batch = fail_on_batch
        self.batch_number = 0
        self.batch_sizes = []
        self.get_all_calls = []

    def collection(self, name):
        return Collection(self, name)

    def get_all(self, refs, **kwargs):
        self.get_all_calls.append((len(refs), kwargs))
        for ref in refs:
            data = self.data.get(ref.collection_name, {}).get(ref.id)
            yield Snapshot(ref.id, data)

    def batch(self):
        return Batch(self)


@pytest.mark.parametrize("module", [emulator_to_real, real_to_emulator])
def test_both_copy_scripts_default_to_dry_run_and_skip_existing(module):
    source = Client({
        "jobs": {"job-1": {"title": "Data Engineer"}, "job-2": {"title": "Analyst"}},
        "skill_market_signals": {"signal-1": {"skill": "Python"}},
    })
    target = Client({"jobs": {"job-1": {"title": "existing"}}})
    output = []

    report = module.run_sync(source, target, emit=output.append)

    assert report["status"] == "dry_run_ready"
    assert report["collections"]["jobs"] == {
        "source_documents": 2, "already_present_at_target": 1, "to_copy": 1,
    }
    assert report["remaining_to_copy"] == 2
    assert target.data["jobs"]["job-1"]["title"] == "existing"
    assert any("Preflight counts" in line for line in output)
    summary_json = next(line for line in output if line.startswith("{"))
    assert json.loads(summary_json)["copied"] == 0


@pytest.mark.parametrize("module", [emulator_to_real, real_to_emulator])
def test_both_copy_scripts_apply_missing_documents_idempotently(module):
    source = Client({"jobs": {"j1": {"value": 1}, "j2": {"value": 2}}})
    target = Client({"jobs": {"j1": {"value": 99}}})

    report = module.run_sync(source, target, dry_run=False, emit=lambda _line: None)

    assert report["status"] == "copied"
    assert report["copied"] == 1
    assert report["remaining_to_copy"] == 0
    assert target.data["jobs"] == {"j1": {"value": 99}, "j2": {"value": 2}}
    assert target.data.get("skill_market_signals", {}) == {}


def test_copy_writes_in_chunks_of_200():
    source = Client({"jobs": {f"j{i}": {"n": i} for i in range(401)}})
    target = Client()

    report = emulator_to_real.run_sync(source, target, dry_run=False, emit=lambda _line: None)

    assert report["copied"] == 401
    assert target.batch_sizes == [200, 200, 1]


def test_resource_exhausted_stops_after_committed_batches_and_reports_remaining():
    source = Client({"jobs": {f"j{i}": {"n": i} for i in range(405)}})
    target = Client(fail_on_batch=2)
    output = []

    report = emulator_to_real.run_sync(source, target, dry_run=False, emit=output.append)

    assert report["status"] == "resource_exhausted_during_write"
    assert report["copied"] == 200
    assert report["remaining_to_copy"] == 205
    assert len(target.data["jobs"]) == 200
    assert "resource_exhausted_during_write" in output[-1]


@pytest.mark.parametrize("module", [emulator_to_real, real_to_emulator])
def test_copy_clis_require_explicit_source_and_target_configuration(module, monkeypatch, capsys):
    monkeypatch.setattr(module, "make_emulator_client", lambda *_a, **_k: pytest.fail("must validate args first"))
    monkeypatch.setattr(module, "make_real_client", lambda *_a, **_k: pytest.fail("must validate args first"))

    with pytest.raises(SystemExit) as exc:
        module.main([])

    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err


def test_firestore_mode_log_is_nonconnecting_and_redacts_project_in_emulator(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    assert firestore_runtime_label("skill-demand-forecasting") == "FIRESTORE: EMULATOR"
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST")
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "production")
    assert firestore_runtime_label("skill-demand-forecasting") == "FIRESTORE: REAL (skill-demand-forecasting)"


def test_real_target_reads_are_batched_with_timeout_and_bounded_retry():
    source = Client({"jobs": {f"j{i}": {"n": i} for i in range(401)}})
    target = Client()

    report = emulator_to_real.run_sync(source, target, emit=lambda _line: None)

    assert report["status"] == "dry_run_ready"
    real_reads = target.get_all_calls
    assert [count for count, _kwargs in real_reads] == [200, 200, 1]
    for _count, kwargs in real_reads:
        assert kwargs["timeout"] == copy_common.REAL_READ_TIMEOUT_SECONDS == 30
        retry = kwargs["retry"]
        assert retry.timeout == 30
        assert retry._predicate(ServiceUnavailable("first")) is True
        assert retry._predicate(ServiceUnavailable("second")) is True
        assert retry._predicate(ServiceUnavailable("third")) is False
        assert retry._predicate(ResourceExhausted("quota")) is False


def test_dry_run_emits_progress_and_finishes_with_no_write_notice():
    source = Client({"jobs": {f"j{i}": {"n": i} for i in range(201)}})
    target = Client()
    output = []

    emulator_to_real.run_sync(source, target, emit=output.append)

    assert output[0] == "Reading source IDs for jobs..."
    assert "Checking target batch 1/2..." in output
    assert "Checking target batch 2/2..." in output
    assert "DRY RUN: nothing written" in output[-1]
    assert target.data == {}


def test_real_read_timeout_is_reported_and_does_not_write():
    class TimedOutClient(Client):
        def get_all(self, refs, **kwargs):
            self.get_all_calls.append((len(refs), kwargs))
            raise DeadlineExceeded("mock read timeout")

    source = Client({"jobs": {"j1": {"title": "Engineer"}}})
    target = TimedOutClient()
    output = []

    report = emulator_to_real.run_sync(source, target, emit=output.append)

    assert report["status"] == "timeout_during_preflight"
    assert any("Real Firestore did not respond in time" in line for line in output)
    assert target.data == {}


def test_source_emulator_and_real_target_client_endpoints_are_isolated(monkeypatch):
    class EndpointClient:
        def __init__(self, *, project=None, credentials=None, client_options=None):
            self._emulator_host = __import__("os").environ.get("FIRESTORE_EMULATOR_HOST")
            self._target = self._emulator_host or client_options["api_endpoint"]
            self.project = project
            self.credentials = credentials

    original_host = "other-emulator:9999"
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", original_host)
    monkeypatch.setattr(firestore, "Client", EndpointClient)
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        staticmethod(lambda _path: SimpleNamespace(project_id="skill-demand-forecasting")),
    )

    source = copy_common.make_emulator_client("127.0.0.1:8080")
    assert source._emulator_host == "127.0.0.1:8080"
    assert source._target == "127.0.0.1:8080"
    target = copy_common.make_real_client("skill-demand-forecasting", "unused-test-path")
    assert target._emulator_host is None
    assert target._target == "firestore.googleapis.com"
    assert __import__("os").environ["FIRESTORE_EMULATOR_HOST"] == original_host


def test_target_endpoint_mismatch_fails_closed():
    with pytest.raises(RuntimeError, match="not pinned to the real service"):
        copy_common.check_real_firestore_connection(SimpleNamespace(
            _emulator_host="127.0.0.1:8080",
            _target="127.0.0.1:8080",
        ))


def test_real_connection_check_uses_bounded_timeout_and_is_read_only():
    class RealEndpoint:
        _emulator_host = None
        _target = "firestore.googleapis.com"

        def collections(self, *, timeout, retry):
            self.timeout = timeout
            self.retry = retry
            return iter(())

    client = RealEndpoint()
    copy_common.check_real_firestore_connection(client)

    assert client.timeout == 30
    assert client.retry.timeout == 30
    assert client.retry._predicate(ServiceUnavailable("first"))
    assert client.retry._predicate(ServiceUnavailable("second"))
    assert not client.retry._predicate(ServiceUnavailable("third"))
    assert not client.retry._predicate(ResourceExhausted("quota"))


def test_emulator_to_real_cli_prints_endpoints_and_connection_progress(monkeypatch, tmp_path, capsys):
    credentials = tmp_path / "empty-test-credential-path.json"
    credentials.touch()
    source = SimpleNamespace(_target="127.0.0.1:8080")
    target = SimpleNamespace(_target="firestore.googleapis.com")
    monkeypatch.setattr(emulator_to_real, "make_emulator_client", lambda _host: source)
    monkeypatch.setattr(emulator_to_real, "make_real_client", lambda *_args: target)
    monkeypatch.setattr(emulator_to_real, "check_real_firestore_connection", lambda _client: None)
    monkeypatch.setattr(emulator_to_real, "run_sync", lambda *_args, **_kwargs: {"status": "dry_run_ready"})

    code = emulator_to_real.main([
        "--source-emulator-host", "127.0.0.1:8080",
        "--target-project", "skill-demand-forecasting",
        "--target-credentials", str(credentials),
        "--dry-run",
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert "Creating emulator client..." in output
    assert "Creating real client for project skill-demand-forecasting..." in output
    assert "Checking real Firestore connection..." in output
    assert "FIRESTORE TARGET: REAL (skill-demand-forecasting)" in output
    assert "SOURCE ENDPOINT: 127.0.0.1:8080" in output
    assert "TARGET ENDPOINT: firestore.googleapis.com" in output


def test_error_messages_redact_credential_paths_and_key_values():
    secret_path = r"D:\secrets\talentscope-sa.json"
    message = emulator_to_real._safe_error_message(
        ValueError(f"Failed reading {secret_path}: private_key=do-not-print"),
        secret_path,
    )

    assert secret_path not in message
    assert "do-not-print" not in message
    assert "[REDACTED]" in message

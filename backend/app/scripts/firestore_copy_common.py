"""Safe, resumable Firestore collection copy primitives shared by sync CLIs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Iterable

from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted
from google.api_core.retry import Retry, if_transient_error

COLLECTIONS = ("jobs", "skill_market_signals")
BATCH_SIZE = 200
REAL_READ_TIMEOUT_SECONDS = 30
MAX_REAL_READ_RETRIES = 2


def _bounded_retry():
    """Return a retry policy that permits no more than two retries."""
    retry_count = 0

    def retry_transient_errors(exc: Exception) -> bool:
        nonlocal retry_count
        if isinstance(exc, ResourceExhausted) or retry_count >= MAX_REAL_READ_RETRIES or not if_transient_error(exc):
            return False
        retry_count += 1
        return True

    return Retry(
        predicate=retry_transient_errors,
        initial=0.25,
        maximum=1.0,
        multiplier=2.0,
        timeout=REAL_READ_TIMEOUT_SECONDS,
    )


def _emit(emit: Callable[[str], Any] | None, message: str) -> None:
    if emit is None:
        print(message, flush=True)
    else:
        emit(message)


@dataclass
class CollectionCopyPlan:
    collection: str
    source_count: int
    already_exists: int
    documents_to_copy: list[tuple[str, dict[str, Any]]]


def _chunks(values: list[Any], size: int = BATCH_SIZE) -> Iterable[list[Any]]:
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def _read_snapshots(
    client: Any,
    refs: list[Any],
    *,
    is_real: bool = False,
    emit: Callable[[str], Any] | None = None,
    progress_label: str = "Checking batch",
) -> list[Any]:
    snapshots: list[Any] = []
    groups = list(_chunks(refs))
    for index, group in enumerate(groups, start=1):
        if progress_label == "Checking target batch":
            _emit(emit, f"{progress_label} {index}/{len(groups)}...")
        if is_real:
            snapshots.extend(client.get_all(
                group,
                timeout=REAL_READ_TIMEOUT_SECONDS,
                retry=_bounded_retry(),
            ))
        else:
            snapshots.extend(client.get_all(group))
    return snapshots


def build_copy_plans(
    source: Any,
    target: Any,
    *,
    source_is_real: bool = False,
    target_is_real: bool = True,
    emit: Callable[[str], Any] | None = None,
) -> list[CollectionCopyPlan]:
    """Read both sides in bounded get_all calls; no writes occur in this phase."""
    plans = []
    for name in COLLECTIONS:
        _emit(emit, f"Reading source IDs for {name}...")
        source_refs = list(source.collection(name).list_documents())
        source_snapshots = _read_snapshots(
            source,
            source_refs,
            is_real=source_is_real,
            emit=emit,
            progress_label="Reading source batch",
        )
        source_docs = {
            snapshot.id: snapshot.to_dict()
            for snapshot in source_snapshots
            if snapshot.exists and isinstance(snapshot.to_dict(), dict)
        }
        target_refs = [target.collection(name).document(doc_id) for doc_id in source_docs]
        target_snapshots = _read_snapshots(
            target,
            target_refs,
            is_real=target_is_real,
            emit=emit,
            progress_label="Checking target batch",
        )
        existing_ids = {snapshot.id for snapshot in target_snapshots if snapshot.exists}
        documents_to_copy = [
            (doc_id, data) for doc_id, data in source_docs.items()
            if doc_id not in existing_ids
        ]
        plans.append(CollectionCopyPlan(
            collection=name,
            source_count=len(source_docs),
            already_exists=len(existing_ids),
            documents_to_copy=documents_to_copy,
        ))
    return plans


def _preflight_report(plans: list[CollectionCopyPlan]) -> dict[str, Any]:
    return {
        "status": "dry_run_ready",
        "collections": {
            plan.collection: {
                "source_documents": plan.source_count,
                "already_present_at_target": plan.already_exists,
                "to_copy": len(plan.documents_to_copy),
            }
            for plan in plans
        },
        "copied": 0,
        "remaining_to_copy": sum(len(plan.documents_to_copy) for plan in plans),
    }


def sync_collections(
    source: Any,
    target: Any,
    *,
    dry_run: bool = True,
    emit: Callable[[str], Any] | None = None,
    source_is_real: bool = False,
    target_is_real: bool = True,
) -> dict[str, Any]:
    """Print all counts before writing and stop cleanly if Firestore exhausts quota."""
    try:
        plans = build_copy_plans(
            source,
            target,
            source_is_real=source_is_real,
            target_is_real=target_is_real,
            emit=emit,
        )
    except ResourceExhausted:
        report = {
            "status": "resource_exhausted_during_preflight",
            "copied": 0,
            "remaining_to_copy": None,
            "note": "No writes started; counts are incomplete because a batched read was rate-limited.",
        }
        _emit(emit, "Real Firestore quota exhausted; nothing was written; try again after the quota resets.")
        _emit(emit, json.dumps(report, indent=2))
        return report
    except (DeadlineExceeded, TimeoutError):
        report = {
            "status": "timeout_during_preflight",
            "copied": 0,
            "remaining_to_copy": None,
        }
        _emit(emit, "Real Firestore did not respond in time (possible quota exhaustion or network issue); nothing was written")
        _emit(emit, json.dumps(report, indent=2))
        return report

    report = _preflight_report(plans)
    _emit(emit, "Preflight counts (all reads complete; no writes have started):")
    for collection_name, counts in report["collections"].items():
        _emit(
            emit,
            f"{collection_name}: source={counts['source_documents']}, "
            f"already existing={counts['already_present_at_target']}, "
            f"would copy={counts['to_copy']}",
        )
    _emit(emit, json.dumps(report, indent=2))
    if dry_run:
        _emit(emit, "DRY RUN: nothing written")
        return report

    copied = 0
    for plan in plans:
        try:
            for group in _chunks(plan.documents_to_copy):
                batch = target.batch()
                for doc_id, data in group:
                    batch.create(target.collection(plan.collection).document(doc_id), data)
                batch.commit()
                copied += len(group)
        except ResourceExhausted:
            report.update({
                "status": "resource_exhausted_during_write",
                "copied": copied,
                "remaining_to_copy": sum(len(item.documents_to_copy) for item in plans) - copied,
            })
            _emit(emit, json.dumps(report, indent=2))
            return report

    report.update({"status": "copied", "copied": copied, "remaining_to_copy": 0})
    _emit(emit, json.dumps(report, indent=2))
    return report


def validate_loopback_emulator_host(host: str) -> str:
    normalized = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
    if normalized not in {"127.0.0.1:8080", "localhost:8080"}:
        raise ValueError("Emulator host must be loopback at port 8080 (127.0.0.1:8080).")
    return normalized


def make_emulator_client(host: str, project_id: str = "demo-talentscope-local"):
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore

    normalized = validate_loopback_emulator_host(host)
    previous_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    os.environ["FIRESTORE_EMULATOR_HOST"] = normalized
    try:
        client = firestore.Client(
            project=project_id,
            credentials=AnonymousCredentials(),
        )
    finally:
        if previous_host is None:
            os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
        else:
            os.environ["FIRESTORE_EMULATOR_HOST"] = previous_host
    if getattr(client, "_emulator_host", None) != normalized or getattr(client, "_target", None) != normalized:
        raise RuntimeError("Could not verify that the source Firestore client is pinned to the emulator.")
    return client


def make_real_client(project_id: str, credentials_path: str):
    from google.cloud import firestore
    from google.oauth2 import service_account

    if not project_id.strip() or project_id == "demo-talentscope-local":
        raise ValueError("A real Firestore project ID must be explicitly provided.")
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    credential_project = getattr(credentials, "project_id", None)
    if credential_project and credential_project != project_id:
        raise ValueError("The credential file project does not match the explicitly selected target project.")
    # The Firestore Python client also honors FIRESTORE_EMULATOR_HOST. Clear it
    # only while constructing an explicitly real client, then restore process
    # configuration for any emulator client still in use.
    emulator_host = os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
    try:
        client = firestore.Client(
            project=project_id,
            credentials=credentials,
            client_options={"api_endpoint": "firestore.googleapis.com"},
        )
    finally:
        if emulator_host is not None:
            os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host
    if getattr(client, "_emulator_host", None) is not None or getattr(client, "_target", None) != "firestore.googleapis.com":
        raise RuntimeError("Could not verify that the target Firestore client is pinned to the real service.")
    return client


def check_real_firestore_connection(client: Any) -> None:
    """Perform a bounded, read-only API call after verifying the real endpoint."""
    if getattr(client, "_emulator_host", None) is not None or getattr(client, "_target", None) != "firestore.googleapis.com":
        raise RuntimeError("Refusing connection check because the target is not pinned to the real service.")
    # ListCollectionIds validates credentials, endpoint reachability, and read access
    # without fetching documents or changing data.
    list(client.collections(timeout=REAL_READ_TIMEOUT_SECONDS, retry=_bounded_retry()))

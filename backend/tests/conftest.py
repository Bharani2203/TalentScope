import os
import socket
import threading
from pathlib import Path

import grpc
import pytest


class _BlockedNetworkAttempt(OSError):
    """Raised when a test attempts an unapproved outbound socket connection."""


@pytest.fixture(autouse=True)
def block_outbound_network(monkeypatch):
    """Fail tests that try to access the network outside local Firebase emulators.

    httpx, requests, and urllib all ultimately use Python sockets, so guarding
    name resolution and socket connection methods covers their real transports
    without interfering with mocked HTTP transports. Only the two explicitly
    approved emulator endpoints are reachable.
    """
    blocked_attempts: list[str] = []
    allowed = {("127.0.0.1", 8080), ("127.0.0.1", 9099)}
    original_getaddrinfo = socket.getaddrinfo
    original_gethostbyname = socket.gethostbyname
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_grpc_secure_channel = grpc.secure_channel
    original_grpc_insecure_channel = grpc.insecure_channel
    socketpair_state = threading.local()

    def describe(address) -> str:
        if isinstance(address, tuple) and len(address) >= 2:
            return f"{address[0]}:{address[1]}"
        return repr(address)

    def is_allowed(address) -> bool:
        return isinstance(address, tuple) and len(address) >= 2 and (address[0], address[1]) in allowed

    def blocked(address):
        detail = describe(address)
        blocked_attempts.append(detail)
        return _BlockedNetworkAttempt(
            f"Outbound network blocked by pytest guard: {detail}; "
            "only 127.0.0.1:8080 and 127.0.0.1:9099 are allowed"
        )

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        # DNS is not needed for emulator access; disallow it before any lookup.
        if host != "127.0.0.1":
            raise blocked((host, port))
        return original_getaddrinfo(host, port, *args, **kwargs)

    def guarded_gethostbyname(host):
        if host != "127.0.0.1":
            raise blocked((host, "DNS lookup"))
        return original_gethostbyname(host)

    def guarded_connect(sock, address):
        # Unix-domain sockets are local IPC, not outbound network traffic.
        unix_family = getattr(socket, "AF_UNIX", None)
        if unix_family is not None and sock.family == unix_family:
            return original_connect(sock, address)
        if (
            getattr(socketpair_state, "active", False)
            and isinstance(address, tuple)
            and address[0] == "127.0.0.1"
        ):
            return original_connect(sock, address)
        if not is_allowed(address):
            raise blocked(address)
        return original_connect(sock, address)

    def guarded_connect_ex(sock, address):
        unix_family = getattr(socket, "AF_UNIX", None)
        if unix_family is not None and sock.family == unix_family:
            return original_connect_ex(sock, address)
        if (
            getattr(socketpair_state, "active", False)
            and isinstance(address, tuple)
            and address[0] == "127.0.0.1"
        ):
            return original_connect_ex(sock, address)
        if not is_allowed(address):
            raise blocked(address)
        return original_connect_ex(sock, address)

    original_socketpair = socket.socketpair

    def guarded_socketpair(*args, **kwargs):
        if getattr(socket, "AF_UNIX", None) is not None:
            return original_socketpair(*args, **kwargs)
        socketpair_state.active = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            socketpair_state.active = False

    def guarded_sendto(sock, data, *args):
        address = args[-1] if args and isinstance(args[-1], tuple) else None
        if address is None or not is_allowed(address):
            raise blocked(address if address is not None else "UDP destination unavailable")
        return original_sendto(sock, data, *args)

    def guarded_grpc_channel(channel_factory, target, *args, **kwargs):
        target_text = target.decode("utf-8") if isinstance(target, bytes) else str(target)
        if target_text not in {"127.0.0.1:8080", "127.0.0.1:9099"}:
            raise blocked(("gRPC", target_text))
        return channel_factory(target, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", guarded_gethostbyname)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "socketpair", guarded_socketpair)
    monkeypatch.setattr(
        grpc, "secure_channel",
        lambda target, *args, **kwargs: guarded_grpc_channel(
            original_grpc_secure_channel, target, *args, **kwargs
        ),
    )
    monkeypatch.setattr(
        grpc, "insecure_channel",
        lambda target, *args, **kwargs: guarded_grpc_channel(
            original_grpc_insecure_channel, target, *args, **kwargs
        ),
    )
    yield
    if blocked_attempts:
        pytest.fail(
            "Outbound network blocked by pytest guard; attempted destination(s): "
            + ", ".join(blocked_attempts),
            pytrace=False,
        )


@pytest.fixture
def live_firestore_store():
    if os.getenv("RUN_LIVE_FIRESTORE_TESTS") != "1":
        pytest.skip("set RUN_LIVE_FIRESTORE_TESTS=1 to opt in to Firestore integration tests")
    expected_local_config = {
        "TALENTSCOPE_FIREBASE_MODE": "emulator",
        "TALENTSCOPE_OFFLINE_TEST_MODE": "1",
        "ENVIRONMENT": "local-test",
        "FIREBASE_PROJECT_ID": "demo-talentscope-local",
        "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8080",
        "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099",
    }
    if any(os.getenv(name) != expected for name, expected in expected_local_config.items()):
        pytest.skip("Firestore integration tests require the complete isolated demo-project emulator configuration")
    from app.core.firebase import get_firestore_client
    from app.storage.firestore_observation_store import FirestoreObservationStore

    return FirestoreObservationStore(get_firestore_client())


@pytest.fixture
def injected_empty_firestore(monkeypatch):
    """Inject an isolated empty Firestore client for unit tests that exercise storage wiring."""
    from importlib import import_module

    from app.storage.mock_firestore_hub import MockFirestoreClient

    client = MockFirestoreClient()
    modules = (
        "app.core.firebase",
        "app.api.dependencies",
        "app.services.auth_service",
        "app.services.company_relationship_service",
        "app.services.evidence_service",
        "app.services.intelligence_catalog_service",
        "app.services.job_storage_service",
        "app.services.market_favourites_service",
        "app.services.onboarding_service",
        "app.services.skill_intelligence_service",
        "app.intelligence_v2.source_registry",
        "app.storage.calculation_record_store",
        "app.storage.conversation_store",
        "app.storage.fetch_run_store",
        "app.storage.firestore_observation_store",
        "app.storage.raw_archive_backend",
    )
    for module_name in modules:
        module = import_module(module_name)
        if hasattr(module, "get_firestore_client"):
            monkeypatch.setattr(module, "get_firestore_client", lambda client=client: client)
    return client


@pytest.fixture
def local_conversation_firestore(monkeypatch):
    """Inject isolated Firestore for tests that pass new conversation IDs directly."""
    from app.core import firebase
    from app.storage.mock_firestore_hub import MockFirestoreClient

    client = MockFirestoreClient()
    monkeypatch.setattr(firebase, "get_firestore_client", lambda: client)
    return client


@pytest.fixture
def approve_company_membership(injected_empty_firestore):
    """Seed trusted owner or connected-employee membership documents for auth tests."""
    def approve_owner(uid: str, company_id: str) -> None:
        injected_empty_firestore.collection("users").document(uid).set({
            "user_type": "company",
            "company_id": company_id,
        })
        injected_empty_firestore.collection("companies").document(company_id).set({
            "status": "active",
            "owner_uid": uid,
        })

    def approve_employee(uid: str, company_id: str, *, role: str = "Employee") -> None:
        injected_empty_firestore.collection("users").document(uid).set({
            "user_type": "employee",
            "company_id": company_id,
            "company_connection": {
                "status": "connected",
                "company_id": company_id,
            },
        })
        injected_empty_firestore.collection("companies").document(company_id).set({
            "status": "active",
            "owner_uid": f"owner-of-{company_id}",
        })
        injected_empty_firestore.collection("companies").document(company_id) \
            .collection("members").document(uid).set({
                "uid": uid,
                "status": "connected",
                "role": role,
            })

    return {"owner": approve_owner, "employee": approve_employee}


@pytest.fixture
def local_reference_database():
    path = Path(__file__).resolve().parents[1] / "data" / "skill_intelligence.sqlite3"
    if not path.is_file():
        pytest.skip(
            "requires the optional local reference database; excluded from clean clones"
        )
    return path


@pytest.fixture
def staged_reference_data_directory():
    backend_root = Path(__file__).resolve().parents[1]
    candidates = (backend_root / "data" / "reference", backend_root.parent / "data" / "reference")
    for directory in candidates:
        if (directory / "manifest.json").is_file():
            return directory
    pytest.skip(
        "requires the optional staged reference-data files; excluded from clean clones"
    )

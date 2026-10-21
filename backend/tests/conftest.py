import os
from pathlib import Path

import pytest


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

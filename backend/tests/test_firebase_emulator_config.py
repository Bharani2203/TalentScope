import asyncio

import pytest
import firebase_admin

from app.core import firebase as firebase_module
from app.core.config import Settings


def _select_emulator(monkeypatch, *, project_id="demo-talentscope-local", environment="local-test"):
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("FIREBASE_PROJECT_ID", project_id)
    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = Settings(environment=environment, firebase_project_id=project_id)
    monkeypatch.setattr(firebase_module, "get_settings", lambda: settings)
    return settings


def test_firebase_emulator_mode_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TALENTSCOPE_FIREBASE_MODE", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)
    settings = Settings()

    with pytest.raises(RuntimeError, match="disabled unless"):
        firebase_module._configure_emulator(settings)


def test_firebase_emulator_requires_explicit_isolated_environment(monkeypatch):
    settings = _select_emulator(monkeypatch)

    assert firebase_module._configure_emulator(settings) is True


@pytest.mark.parametrize("project_id,environment", [
    ("skill-demand-forecasting", "local-test"),
    ("demo-talentscope-local", "production"),
])
def test_firebase_emulator_rejects_production_or_inconsistent_environment(monkeypatch, project_id, environment):
    settings = _select_emulator(monkeypatch, project_id=project_id, environment=environment)

    with pytest.raises(RuntimeError):
        firebase_module._configure_emulator(settings)


def test_firebase_emulator_rejects_non_loopback_or_missing_hosts(monkeypatch):
    settings = _select_emulator(monkeypatch)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "firestore.googleapis.com:443")

    with pytest.raises(RuntimeError, match="loopback"):
        firebase_module._configure_emulator(settings)


@pytest.mark.parametrize("missing_name", [
    "TALENTSCOPE_FIREBASE_MODE",
    "TALENTSCOPE_OFFLINE_TEST_MODE",
    "ENVIRONMENT",
    "FIREBASE_PROJECT_ID",
    "FIRESTORE_EMULATOR_HOST",
    "FIREBASE_AUTH_EMULATOR_HOST",
])
def test_incomplete_local_configuration_fails_before_admin_initialization(monkeypatch, missing_name):
    firebase_module.get_firebase_app.cache_clear()
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "local-test")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.delenv(missing_name, raising=False)
    monkeypatch.setattr(firebase_admin, "get_app", lambda: pytest.fail("Firebase Admin app lookup occurred"))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda **_: pytest.fail("Firebase Admin initialized"))

    try:
        with pytest.raises(RuntimeError):
            firebase_module.get_firebase_app()
    finally:
        firebase_module.get_firebase_app.cache_clear()
        get_settings.cache_clear()


@pytest.mark.parametrize("name,value", [
    ("TALENTSCOPE_FIREBASE_MODE", "production"),
    ("ENVIRONMENT", "production"),
    ("FIREBASE_PROJECT_ID", "skill-demand-forecasting"),
    ("FIRESTORE_EMULATOR_HOST", "firestore.googleapis.com:443"),
    ("FIREBASE_AUTH_EMULATOR_HOST", "identitytoolkit.googleapis.com:443"),
])
def test_inconsistent_local_configuration_fails_before_admin_initialization(monkeypatch, name, value):
    firebase_module.get_firebase_app.cache_clear()
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "local-test")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(firebase_admin, "get_app", lambda: pytest.fail("Firebase Admin app lookup occurred"))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda **_: pytest.fail("Firebase Admin initialized"))

    try:
        with pytest.raises(RuntimeError):
            firebase_module.get_firebase_app()
    finally:
        firebase_module.get_firebase_app.cache_clear()
        get_settings.cache_clear()


def test_missing_emulator_mode_without_offline_opt_in_preserves_normal_settings(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    for name in (
        "TALENTSCOPE_FIREBASE_MODE", "TALENTSCOPE_OFFLINE_TEST_MODE", "FIRESTORE_EMULATOR_HOST",
        "FIREBASE_AUTH_EMULATOR_HOST", "ENVIRONMENT", "FIREBASE_PROJECT_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = get_settings()
    get_settings.cache_clear()

    assert settings is not None


def test_valid_local_configuration_selects_emulator_endpoints_without_env_file(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("TALENTSCOPE_FIREBASE_MODE", "emulator")
    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "local-test")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")

    try:
        settings = get_settings()
        assert settings.firebase_project_id == "demo-talentscope-local"
        assert firebase_module._configure_emulator(settings) is True
        assert __import__("os").environ["FIRESTORE_EMULATOR_HOST"] == "127.0.0.1:8080"
        assert __import__("os").environ["FIREBASE_AUTH_EMULATOR_HOST"] == "127.0.0.1:9099"
    finally:
        get_settings.cache_clear()


def test_firebase_admin_uses_anonymous_emulator_credential_without_service_account(monkeypatch):
    firebase_module.get_firebase_app.cache_clear()
    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    monkeypatch.setattr(firebase_admin, "get_app", lambda: (_ for _ in ()).throw(ValueError("not initialized")))
    initialized = {}

    def initialize_app(**kwargs):
        initialized.update(kwargs)
        return object()

    monkeypatch.setattr(firebase_admin, "initialize_app", initialize_app)
    monkeypatch.setattr(firebase_module.credentials, "Certificate", lambda *_: pytest.fail("service account used"))
    try:
        firebase_module.get_firebase_app()
    finally:
        firebase_module.get_firebase_app.cache_clear()

    assert isinstance(initialized["credential"], firebase_module._EmulatorCredential)
    assert initialized["options"]["projectId"] == "demo-talentscope-local"


def test_existing_app_with_non_emulator_credentials_is_rejected(monkeypatch):
    firebase_module.get_firebase_app.cache_clear()
    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    existing_app = type("ExistingApp", (), {
        "project_id": "demo-talentscope-local", "credential": object(),
    })()
    monkeypatch.setattr(firebase_admin, "get_app", lambda: existing_app)
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda **_: pytest.fail("fallback initialized"))

    with pytest.raises(RuntimeError, match="emulator-only credentials"):
        firebase_module.get_firebase_app()


def test_firestore_emulator_unavailable_fails_without_fallback(monkeypatch):
    firebase_module.get_firestore_client.cache_clear()
    _select_emulator(monkeypatch)
    monkeypatch.setattr(
        firebase_module.socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    monkeypatch.setattr(firebase_module.firestore, "client", lambda **_: pytest.fail("Firestore fallback used"))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda **_: pytest.fail("Firebase app initialized"))
    monkeypatch.setattr(firebase_admin, "get_app", lambda **_: pytest.fail("Firebase app lookup occurred"))
    try:
        with pytest.raises(RuntimeError, match="production Firestore was not selected"):
            firebase_module.get_firestore_client()
    finally:
        firebase_module.get_firestore_client.cache_clear()


def test_firestore_without_emulator_opt_in_fails_before_settings_or_sdk(monkeypatch):
    firebase_module.clear_firebase_client_caches()
    monkeypatch.delenv("TALENTSCOPE_FIREBASE_MODE", raising=False)
    monkeypatch.delenv("TALENTSCOPE_OFFLINE_TEST_MODE", raising=False)
    monkeypatch.setenv("RUN_LIVE_FIRESTORE_TESTS", "1")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setattr(firebase_module, "get_settings", lambda: pytest.fail("settings loaded before opt-in"))
    monkeypatch.setattr(firebase_module.firestore, "client", lambda **_: pytest.fail("Firestore client initialized"))
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda **_: pytest.fail("Firebase app initialized"))
    monkeypatch.setattr(firebase_admin, "get_app", lambda **_: pytest.fail("Firebase app lookup occurred"))

    with pytest.raises(RuntimeError, match="explicitly set"):
        firebase_module.get_firestore_client()


def test_offline_test_mode_disables_gemini_even_with_an_explicit_key(monkeypatch):
    from app.services.llm_explanation_service import LLMExplanationService

    monkeypatch.setenv("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
    # This unit test covers Gemini suppression only. Inject settings so it does
    # not enter get_settings()'s separate Firebase emulator configuration path.
    isolated_settings = Settings(_env_file=None)
    assert LLMExplanationService(
        api_key="synthetic-test-key",
        settings=isolated_settings,
    ).is_available() is False


def test_empty_local_provider_allowlist_prevents_provider_construction():
    from app.services.market_collection_service import configured_market_providers

    settings = Settings(
        market_collection_enabled_providers=[],
        jsearch_api_key="synthetic-test-key",
        adzuna_app_id="synthetic-test-id",
        adzuna_app_key="synthetic-test-key",
        github_token="synthetic-test-token",
    )

    assert configured_market_providers(settings) == []


def test_local_market_service_selects_firestore_factories_without_connecting(monkeypatch, tmp_path):
    from app.services import market_collection_service
    from app.services.execution_orchestrator_service import ExecutionOrchestratorService
    from app.services.entity_registry_service import EntityRegistryService
    from app.services.llm_explanation_service import LLMExplanationService
    from app.storage.conversation_store import ConversationStore
    from app.storage.fetch_run_store import FirestoreFetchRunStore
    from app.storage.firestore_observation_store import FirestoreObservationStore
    from app.storage.market_store import MarketDataStore
    from app.storage.raw_response_archive import FirestoreRawResponseArchive

    _select_emulator(monkeypatch)
    settings = Settings(
        _env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local",
        skill_intelligence_read_backend="firestore", market_collection_enabled_providers=[],
    )
    constructed = {}

    class FetchRunStore(FirestoreFetchRunStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["fetch_runs"] = self

    class ObservationStore(FirestoreObservationStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["observations"] = self

    class ArchiveStore(FirestoreRawResponseArchive):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["archives"] = self

    monkeypatch.setattr(market_collection_service, "FirestoreFetchRunStore", FetchRunStore)
    monkeypatch.setattr(market_collection_service, "FirestoreObservationStore", ObservationStore)
    monkeypatch.setattr(market_collection_service, "FirestoreRawResponseArchive", ArchiveStore)
    asyncio.run(market_collection_service.collect_market_data(settings=settings, providers=[]))

    assert isinstance(constructed["fetch_runs"], FirestoreFetchRunStore)
    assert isinstance(constructed["observations"], FirestoreObservationStore)
    assert isinstance(constructed["archives"], FirestoreRawResponseArchive)
    assert constructed["fetch_runs"].client is None
    assert constructed["observations"].client is None
    assert constructed["archives"].backend.client is None

    service = ExecutionOrchestratorService(
        settings=settings, db_path=tmp_path / "market-factory.sqlite3",
        entity_service=EntityRegistryService(settings=settings, db_path=tmp_path / "market-factory.sqlite3"),
        conversation_store=ConversationStore(),
        llm_service=LLMExplanationService(settings=settings),
    )
    assert isinstance(service.firestore_store, FirestoreObservationStore)
    assert isinstance(service.market_store, MarketDataStore)
    assert service.firestore_store.client is None


def test_sqlite_read_backend_is_an_explicit_observation_only_storage_mix(monkeypatch, tmp_path):
    from app.services import market_collection_service
    from app.storage.fetch_run_store import FirestoreFetchRunStore
    from app.storage.firestore_observation_store import FirestoreObservationStore
    from app.storage.market_store import MarketDataStore
    from app.storage.raw_response_archive import FirestoreRawResponseArchive

    _select_emulator(monkeypatch)
    settings = Settings(
        _env_file=None, environment="local-test", firebase_project_id="demo-talentscope-local",
        skill_intelligence_read_backend="sqlite", market_collection_enabled_providers=[],
        skill_intelligence_db_path=str(tmp_path / "market-observations.sqlite3"),
    )
    constructed = {}

    class CaptureFetchRunStore(FirestoreFetchRunStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["fetch_runs"] = self

    class CaptureArchive(FirestoreRawResponseArchive):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["archives"] = self

    class CaptureSQLiteObservationStore(MarketDataStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            constructed["observations"] = self

    monkeypatch.setattr(market_collection_service, "FirestoreFetchRunStore", CaptureFetchRunStore)
    monkeypatch.setattr(market_collection_service, "FirestoreRawResponseArchive", CaptureArchive)
    monkeypatch.setattr(market_collection_service, "MarketDataStore", CaptureSQLiteObservationStore)
    asyncio.run(market_collection_service.collect_market_data(settings=settings, providers=[]))

    assert isinstance(constructed["fetch_runs"], FirestoreFetchRunStore)
    assert isinstance(constructed["archives"], FirestoreRawResponseArchive)
    assert constructed["fetch_runs"].client is None
    assert constructed["archives"].backend.client is None
    assert isinstance(constructed["observations"], MarketDataStore)
    assert constructed["observations"].database_path == settings.database_path


def test_auth_rejection_missing_bearer_token(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Firebase ID token is required" in response.text


def test_auth_rejection_invalid_token(monkeypatch):
    from fastapi.testclient import TestClient
    from firebase_admin import auth
    from app.main import app

    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    app.dependency_overrides.clear()

    # When token is invalid, verify_id_token raises InvalidIdTokenError
    monkeypatch.setattr(
        auth, "verify_id_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(auth.InvalidIdTokenError("Invalid token")),
    )
    client = TestClient(app)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token-sample"})
    assert response.status_code == 401
    assert "invalid, expired, or revoked" in response.text


def test_auth_rejection_expired_token(monkeypatch):
    from fastapi.testclient import TestClient
    from firebase_admin import auth
    from app.main import app

    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    app.dependency_overrides.clear()

    monkeypatch.setattr(
        auth, "verify_id_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(auth.ExpiredIdTokenError("Token expired", None)),
    )
    client = TestClient(app)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer expired-token-sample"})
    assert response.status_code == 401
    assert "invalid, expired, or revoked" in response.text


def test_auth_emulator_unreachable_fails_closed_without_production_fallback(monkeypatch):
    from fastapi.testclient import TestClient
    from firebase_admin import auth, exceptions
    from app.main import app

    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    app.dependency_overrides.clear()

    # When Auth emulator host is unreachable, FirebaseError is raised
    monkeypatch.setattr(
        auth, "verify_id_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(exceptions.FirebaseError(503, "Failed to reach emulator")),
    )
    client = TestClient(app)
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer emulator-test-token"})
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "auth_verification_unavailable"


def test_authenticated_request_succeeds_without_dependency_overrides(monkeypatch):
    from fastapi.testclient import TestClient
    from firebase_admin import auth
    from app.main import app

    _select_emulator(monkeypatch)
    monkeypatch.setattr(firebase_module, "_require_firestore_emulator_ready", lambda: None)
    app.dependency_overrides.clear()

    valid_claims = {
        "uid": "demo-test-user-123",
        "email": "demo-test@example.test",
        "email_verified": True,
        "firebase": {"sign_in_provider": "password"},
    }
    monkeypatch.setattr(auth, "verify_id_token", lambda *args, **kwargs: valid_claims)
    client = TestClient(app)
    response = client.get("/api/v1/intelligence/capabilities", headers={"Authorization": "Bearer valid-demo-token"})
    assert response.status_code == 200
    assert "capabilities" in response.json()

import base64
import json
import logging
import os
from pathlib import Path
import socket
from threading import Lock
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_firebase_app_lock = Lock()
_firestore_client_lock = Lock()
_firestore_clients: dict[int, Any] = {}
_LOCAL_FIREBASE_PROJECT_ID = "demo-talentscope-local"
_LOCAL_FIRESTORE_HOST = "127.0.0.1:8080"
_LOCAL_AUTH_HOST = "127.0.0.1:9099"


class _EmulatorCredential(credentials.Base):
    """Anonymous credential used only for the explicitly selected local emulator."""

    def get_credential(self):
        return AnonymousCredentials()


def _is_emulator_mode() -> bool:
    """Determine whether local emulator execution is requested or in-progress."""
    mode = os.getenv("TALENTSCOPE_FIREBASE_MODE", "").strip().lower()
    offline = os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE", "").strip()
    firestore_host = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
    auth_host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
    live_tests = os.getenv("RUN_LIVE_FIRESTORE_TESTS", "").strip()
    return bool(mode == "emulator" or offline == "1" or firestore_host or auth_host or live_tests == "1")


def _configure_emulator(settings) -> bool:
    mode = os.getenv("TALENTSCOPE_FIREBASE_MODE", "").strip().lower()
    if mode not in {"production", "emulator"}:
        raise RuntimeError("Firebase access is disabled unless isolated local emulator mode is explicitly enabled.")
    if mode != "emulator":
        raise RuntimeError(
            "Firebase access is disabled unless the isolated local emulator mode is explicitly enabled."
        )
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") not in {"0", "1"}:
        raise RuntimeError("Firebase Emulator mode requires TALENTSCOPE_OFFLINE_TEST_MODE=1.")
    if settings.environment != "local-test":
        raise RuntimeError("Firebase Emulator mode requires ENVIRONMENT=local-test.")
    if settings.firebase_project_id != _LOCAL_FIREBASE_PROJECT_ID:
        raise RuntimeError("Firebase Emulator mode requires the dedicated local demo project ID.")

    firestore_host = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
    auth_host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "").strip()
    if firestore_host != _LOCAL_FIRESTORE_HOST:
        raise RuntimeError("Firebase Emulator mode requires the approved loopback Firestore endpoint 127.0.0.1:8080.")
    if auth_host != _LOCAL_AUTH_HOST:
        raise RuntimeError("Firebase Emulator mode requires the approved loopback Auth endpoint 127.0.0.1:9099.")

    # Firebase Admin and Google Auth use these supported emulator selectors.
    os.environ["FIRESTORE_EMULATOR_HOST"] = firestore_host
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = auth_host
    return True


def _is_emulator_reachable(host: str = "127.0.0.1", port: int = 8080, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _require_firestore_emulator_ready() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8080), timeout=0.5):
            return
    except OSError as exc:
        raise RuntimeError(
            "Firestore Emulator is unavailable at 127.0.0.1:8080; production Firestore was not selected."
        ) from exc


def _validated_emulator_settings():
    """Validate opt-in before reading settings or invoking any Firebase SDK API."""
    if os.getenv("TALENTSCOPE_FIREBASE_MODE", "").strip().lower() != "emulator":
        raise RuntimeError(
            "Firebase access is disabled unless TALENTSCOPE_FIREBASE_MODE=emulator is explicitly set."
        )
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") not in {"0", "1"}:
        raise RuntimeError("Firebase Emulator mode requires TALENTSCOPE_OFFLINE_TEST_MODE=1.")
    # get_settings() avoids loading backend/.env whenever explicit local mode is
    # requested; this prevents credentials there from entering the local path.
    settings = get_settings()
    _configure_emulator(settings)
    _require_firestore_emulator_ready()
    return settings


def _resolve_certificate_path(configured_path: str) -> Path:
    path = Path(os.path.expandvars(configured_path)).expanduser()
    if path.is_absolute():
        return path
    candidates = (
        Path.cwd() / path,
        Path.cwd().parent / path,
        Path(__file__).resolve().parents[2] / path,
        Path(__file__).resolve().parents[3] / path,
        Path.cwd() / "backend" / path,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def get_firebase_app() -> firebase_admin.App:
    """Return the configured Firebase Admin app (local emulator or verified credentials)."""
    with _firebase_app_lock:
        if _is_emulator_mode():
            _validated_emulator_settings()
            try:
                app = firebase_admin.get_app()
            except ValueError:
                return firebase_admin.initialize_app(
                    credential=_EmulatorCredential(),
                    options={
                        "projectId": _LOCAL_FIREBASE_PROJECT_ID,
                    }
                )
            if app.project_id != _LOCAL_FIREBASE_PROJECT_ID:
                raise RuntimeError("An existing non-emulator Firebase app prevents local emulator startup.")
            if not isinstance(app.credential, _EmulatorCredential):
                raise RuntimeError("An existing Firebase app without emulator-only credentials is not allowed.")
            return app

        # Standard / service-account credentials mode
        settings = get_settings()

        # Check for Base64 or inline JSON service account credentials
        cred_dict = None
        b64_cred = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
            or getattr(settings, "firebase_service_account_base64", None)
        )
        if b64_cred and b64_cred.strip():
            raw_b64 = b64_cred.strip().strip("'\"")
            if raw_b64.startswith("{") and raw_b64.endswith("}"):
                try:
                    cred_dict = json.loads(raw_b64)
                    print("[FIREBASE_INIT] Successfully parsed JSON from FIREBASE_SERVICE_ACCOUNT_BASE64", flush=True)
                except Exception as exc:
                    print(f"[FIREBASE_INIT] Failed to parse JSON from FIREBASE_SERVICE_ACCOUNT_BASE64: {exc}", flush=True)
                    logger.error("Failed to parse JSON from FIREBASE_SERVICE_ACCOUNT_BASE64: %s", exc)
            else:
                try:
                    clean_b64 = raw_b64.replace(" ", "").replace("\n", "").replace("\r", "")
                    missing_padding = len(clean_b64) % 4
                    if missing_padding:
                        clean_b64 += "=" * (4 - missing_padding)
                    decoded = base64.b64decode(clean_b64).decode("utf-8")
                    cred_dict = json.loads(decoded)
                    print(f"[FIREBASE_INIT] Successfully decoded FIREBASE_SERVICE_ACCOUNT_BASE64 for project: {cred_dict.get('project_id')}", flush=True)
                except Exception as exc:
                    print(f"[FIREBASE_INIT] Failed to decode FIREBASE_SERVICE_ACCOUNT_BASE64: {type(exc).__name__}: {exc}", flush=True)
                    logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_BASE64: %s", exc, exc_info=True)

        raw_json_cred = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_RAW")
            or os.getenv("FIREBASE_SERVICE_ACCOUNT_RAW")
            or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        )
        if not cred_dict and raw_json_cred and raw_json_cred.strip():
            raw_stripped = raw_json_cred.strip().strip("'\"")
            if raw_stripped.startswith("{") and raw_stripped.endswith("}"):
                try:
                    cred_dict = json.loads(raw_stripped)
                    print(f"[FIREBASE_INIT] Successfully parsed raw JSON credentials for project: {cred_dict.get('project_id')}", flush=True)
                except Exception as exc:
                    print(f"[FIREBASE_INIT] Failed to parse raw JSON credentials: {type(exc).__name__}: {exc}", flush=True)
                    logger.error("Failed to parse raw JSON credentials: %s", exc, exc_info=True)

        credential = None
        detected_project_id = None
        if cred_dict:
            try:
                credential = credentials.Certificate(cred_dict)
                detected_project_id = cred_dict.get("project_id")
                print(f"[FIREBASE_INIT] Created Certificate credential for project: {detected_project_id}", flush=True)
            except Exception as cert_exc:
                print(f"[FIREBASE_INIT] Certificate creation failed from parsed dictionary: {cert_exc}", flush=True)
                logger.error("Certificate creation failed: %s", cert_exc, exc_info=True)
        else:
            cred_path = (
                settings.google_application_credentials
                or getattr(settings, "firebase_service_account_json", None)
                or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
                or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                or "./secrets/firebase-service-account.json"
            )
            certificate_path = (
                _resolve_certificate_path(cred_path)
                if cred_path
                else None
            )
            if certificate_path is not None and not certificate_path.is_file():
                if _is_emulator_mode():
                    _validated_emulator_settings()
                if cred_path != "./secrets/firebase-service-account.json":
                    raise FileNotFoundError(f"Configured Firebase service-account file does not exist: {certificate_path}")

            if certificate_path is not None and certificate_path.is_file():
                try:
                    credential = credentials.Certificate(str(certificate_path))
                    print(f"[FIREBASE_INIT] Loaded Certificate from file: {certificate_path}", flush=True)
                except Exception as file_cert_exc:
                    print(f"[FIREBASE_INIT] Failed to load certificate from file: {file_cert_exc}", flush=True)

        target_project_id = detected_project_id or settings.firebase_project_id or os.getenv("FIREBASE_PROJECT_ID")

        try:
            app = firebase_admin.get_app()
            if not target_project_id or app.project_id == target_project_id:
                return app
        except ValueError:
            pass

        if credential is None:
            # Fallback to Google Application Default Credentials in cloud hosting environments
            try:
                import google.auth
                default_cred, default_project = google.auth.default()
                print(f"[FIREBASE_INIT] Using Google Application Default Credentials (project: {default_project})", flush=True)
                return firebase_admin.initialize_app(
                    credential=default_cred,
                    options={"projectId": target_project_id or default_project} if (target_project_id or default_project) else None,
                )
            except Exception as adc_err:
                print(f"[FIREBASE_INIT] Google Application Default Credentials fallback failed: {adc_err}", flush=True)

            if _is_emulator_mode():
                _validated_emulator_settings()
            raise RuntimeError(
                "Firebase initialization requires either local emulator mode (TALENTSCOPE_FIREBASE_MODE=emulator) "
                "or a configured GOOGLE_APPLICATION_CREDENTIALS / FIREBASE_SERVICE_ACCOUNT_JSON / FIREBASE_SERVICE_ACCOUNT_BASE64 service-account credential."
            )

        return firebase_admin.initialize_app(
            credential=credential,
            options={
                "projectId": target_project_id,
            } if target_project_id else None,
        )


def get_firestore_client():
    """Return a Firestore client associated with the active Firebase app."""
    if _is_emulator_mode():
        _validated_emulator_settings()
    app = get_firebase_app()
    key = id(app)
    with _firestore_client_lock:
        client = _firestore_clients.get(key)
        if client is None:
            client = firestore.client(app=app)
            _firestore_clients[key] = client
        return client


def clear_firebase_client_caches() -> None:
    """Clear process-local clients for isolated configuration tests only."""
    with _firebase_app_lock, _firestore_client_lock:
        _firestore_clients.clear()
        for app in list(firebase_admin._apps.values()):
            try:
                firebase_admin.delete_app(app)
            except Exception:
                pass
        firebase_admin._apps.clear()


# Keep the former cache-clear hooks available to existing isolated tests.
get_firebase_app.cache_clear = clear_firebase_client_caches  # type: ignore[attr-defined]
get_firestore_client.cache_clear = clear_firebase_client_caches  # type: ignore[attr-defined]

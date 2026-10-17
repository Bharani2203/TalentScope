import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
import sys

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import get_settings

_firebase_app_lock = Lock()
_firestore_client_factory = firestore.client


def _resolve_certificate_path(configured_path: str) -> Path:
    path = Path(os.path.expandvars(configured_path)).expanduser()
    if path.is_absolute():
        return path
    candidates = (Path.cwd() / path, Path(__file__).resolve().parents[2] / path)
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), candidates[0].resolve())


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    """Initialize Firebase Admin once, using Application Default Credentials."""
    with _firebase_app_lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            settings = get_settings()
            certificate_path = (
                _resolve_certificate_path(settings.google_application_credentials)
                if settings.google_application_credentials
                else None
            )
            if certificate_path is not None and not certificate_path.is_file():
                raise FileNotFoundError("Configured Firebase service-account file does not exist.")
            credential = (
                credentials.Certificate(str(certificate_path))
                if certificate_path is not None
                else None
            )
            return firebase_admin.initialize_app(
                credential=credential,
                options={
                    "projectId": settings.firebase_project_id,
                }
            )


@lru_cache
def get_firestore_client():
    """Return the Firestore client associated with the configured Firebase app."""
    is_test = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
    emulator_opt_in = (
        os.getenv("RUN_LIVE_FIRESTORE_TESTS") == "1"
        and bool(os.getenv("FIRESTORE_EMULATOR_HOST"))
    )
    if is_test and not emulator_opt_in and firestore.client is _firestore_client_factory:
        raise RuntimeError(
            "Unit tests must inject a Firestore client; live integration tests require the Firestore emulator."
        )
    return firestore.client(app=get_firebase_app())

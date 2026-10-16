import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
import sys

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import get_settings

_firebase_app_lock = Lock()


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
    import os
    from unittest.mock import Mock
    if isinstance(firestore.client, Mock):
        return firestore.client(app=get_firebase_app())
    is_test = os.getenv("RUN_LIVE_FIRESTORE_TESTS") != "1" and ("pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"))
    if is_test:
        from app.storage.mock_firestore_hub import get_mock_firestore_client
        return get_mock_firestore_client()
    return firestore.client(app=get_firebase_app())

"""Safe, non-connecting description of the configured Firestore destination."""

import os


def firestore_runtime_label(project_id: str | None = None) -> str:
    """Return a startup label without initializing Firebase or exposing credentials."""
    emulator_selected = bool(
        os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
        or os.getenv("TALENTSCOPE_FIREBASE_MODE", "").strip().casefold() == "emulator"
        or os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE", "").strip() == "1"
    )
    if emulator_selected:
        return "FIRESTORE: EMULATOR"
    configured_project = project_id or os.getenv("FIREBASE_PROJECT_ID") or "unconfigured"
    return f"FIRESTORE: REAL ({configured_project})"

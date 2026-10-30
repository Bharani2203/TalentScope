"""Firestore Synchronization Script for TalentScope.ai (Phase 5).

Syncs processed skill intelligence data from local JSON artifacts to the Firestore emulator:
  1. sync_role_profiles(): Writes backend/data/processed/role_profiles.json to 'role_requirements'
  2. sync_skill_trends(): Writes backend/data/processed/skill_trends.json to 'skill_market_signals'
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials

# ==============================================================================
# Mandatory Firestore emulator environment variables (Section 6 Constraints)
# ==============================================================================
os.environ.setdefault("TALENTSCOPE_FIREBASE_MODE", "emulator")
os.environ.setdefault("TALENTSCOPE_OFFLINE_TEST_MODE", "1")
os.environ.setdefault("ENVIRONMENT", "local-test")
os.environ.setdefault("FIREBASE_PROJECT_ID", "demo-talentscope-local")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
os.environ.setdefault("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("sync_to_firestore")

# Path resolutions
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"


class _EmulatorCredential(credentials.Base):
    """Anonymous credential used exclusively for the local Firebase emulator."""

    def get_credential(self) -> AnonymousCredentials:
        return AnonymousCredentials()


def get_firestore_client() -> firestore.firestore.Client:
    """Initialize Firebase Admin app in local emulator mode and return Firestore client."""
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "demo-talentscope-local")
    emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")

    logger.info("Initializing Firebase Admin with emulator host: %s (Project: %s)...", emulator_host, project_id)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credential=_EmulatorCredential(),
            options={"projectId": project_id},
        )
    return firestore.client()


def slugify(text: str) -> str:
    """Convert a human-readable title into a clean URL/doc slug."""
    text_clean = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text_clean or "unknown"


def resolve_file(rel_path_str: str) -> Path:
    """Find JSON artifact across root or inner directory structures."""
    p = Path(rel_path_str)
    if p.is_file():
        return p.resolve()

    candidates = [
        Path.cwd() / p,
        BACKEND_DIR / p,
        BACKEND_DIR / "data" / "processed" / p.name,
        PROCESSED_DIR / p.name,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    return (PROCESSED_DIR / p.name).resolve()


def sync_role_profiles(db: firestore.firestore.Client) -> int:
    """Read role_profiles.json and write records to 'role_requirements' collection."""
    json_path = resolve_file("role_profiles.json")
    if not json_path.exists():
        raise FileNotFoundError(f"Role profiles file not found at: {json_path}")

    logger.info("Reading role profiles from %s...", json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        profiles: dict[str, dict[str, Any]] = json.load(f)

    logger.info("Syncing %d role profiles to 'role_requirements' collection...", len(profiles))
    batch = db.batch()
    collection_ref = db.collection("role_requirements")
    count = 0

    for role_name, data in profiles.items():
        doc_id = slugify(role_name)
        doc_ref = collection_ref.document(doc_id)

        payload = {
            "role_id": doc_id,
            "role_name": data.get("role", role_name),
            "top_skills": data.get("top_skills", []),
            "total_top_skills": len(data.get("top_skills", [])),
            "source": "talentscope_intelligence_hybrid",
            "data_origin": "imported_historical",
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        batch.set(doc_ref, payload)
        count += 1

    batch.commit()
    logger.info("Successfully committed %d documents to 'role_requirements'.", count)
    return count


def sync_skill_trends(db: firestore.firestore.Client) -> int:
    """Read skill_trends.json and write records to 'skill_market_signals' collection."""
    json_path = resolve_file("skill_trends.json")
    if not json_path.exists():
        raise FileNotFoundError(f"Skill trends file not found at: {json_path}")

    logger.info("Reading skill trends from %s...", json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        trends: dict[str, dict[str, Any]] = json.load(f)

    logger.info("Syncing %d skill trends to 'skill_market_signals' collection...", len(trends))
    batch = db.batch()
    collection_ref = db.collection("skill_market_signals")
    count = 0

    for skill_name, data in trends.items():
        # Avoid forward slashes in Firestore doc IDs (e.g. 'ci/cd' -> 'ci-cd')
        doc_id = skill_name.strip().replace("/", "-")
        doc_ref = collection_ref.document(doc_id)

        payload = {
            "skill_id": doc_id,
            "skill_name": data.get("skill_name", skill_name),
            "display_skill": data.get("display_skill", skill_name.title()),
            "total_observations": data.get("total_observations", 0),
            "timeline": data.get("timeline", []),
            "source": "talentscope_intelligence_hybrid",
            "data_origin": "imported_historical",
            "signal_family": "hiring_demand",
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        batch.set(doc_ref, payload)
        count += 1

    batch.commit()
    logger.info("Successfully committed %d documents to 'skill_market_signals'.", count)
    return count


def main() -> int:
    try:
        db = get_firestore_client()

        role_count = sync_role_profiles(db)
        skill_count = sync_skill_trends(db)

        # Verification query directly against the emulator
        roles_in_firestore = list(db.collection("role_requirements").stream())
        skills_in_firestore = list(db.collection("skill_market_signals").stream())

        print("\n" + "=" * 70)
        print("TALENTSCOPE.AI FIRESTORE SYNC REPORT (PHASE 5)")
        print("=" * 70)
        print(f"Target Host:                 {os.environ.get('FIRESTORE_EMULATOR_HOST')}")
        print(f"Project ID:                  {db.project}")
        print(f"Status:                      SUCCESS\n")

        print("Verified Collections & Document Counts:")
        print(f"  - Collection: role_requirements    | Documents: {len(roles_in_firestore)}")
        print(f"  - Collection: skill_market_signals | Documents: {len(skills_in_firestore)}")

        print("\nSample Role Documents in Firestore:")
        for doc in roles_in_firestore[:3]:
            data = doc.to_dict()
            top_skills = [s["skill_name"] for s in data.get("top_skills", [])[:3]]
            print(f"  - [{doc.id}] {data.get('role_name')} -> Skills: {', '.join(top_skills)}")

        print("\nSample Skill Documents in Firestore:")
        for doc in skills_in_firestore[:3]:
            data = doc.to_dict()
            print(f"  - [{doc.id}] Total Obs: {data.get('total_observations')} | Timeline months: {len(data.get('timeline', []))}")

        print("=" * 70)
        print("[Verified] Phase 5 Firestore Sync Completed Successfully.")
        print("=" * 70 + "\n")
        return 0

    except Exception as exc:
        logger.error("Firestore sync failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


"""Production Firestore Migration Script for TalentScope.ai.

Transfers local PostgreSQL data, processed JSON intelligence artifacts,
and local emulator records to the live production Google Cloud Firestore project.

Safety & Quota Compliance:
  - Explicitly removes all Firestore/Auth emulator environment variables before live writes.
  - Interactive terminal confirmation gate ('YES' required to proceed).
  - Firestore batch writes chunked strictly at 450 items (below the 500 document limit).
  - Rate-limited with 2.5s pause between batch commits to prevent write quota exhaustion.
  - Section 6 Constraints: Authentic enterprise data only, verifiable provenance, 0 hallucinated listings.
"""

from __future__ import annotations

import argparse
import base64
from datetime import date, datetime
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

# Ensure project backend paths are importable
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("sync_local_to_live_firestore")

# Quota safety parameters
BATCH_CHUNK_SIZE = 450
RATE_LIMIT_SLEEP_SECONDS = 2.5


class _LocalEmulatorCredential(credentials.Base):
    """Anonymous credential used exclusively to extract data from local emulator."""

    def get_credential(self) -> AnonymousCredentials:
        return AnonymousCredentials()


def slugify(text: str) -> str:
    """Convert string into clean document slug."""
    text_clean = re.sub(r"[^a-zA-Z0-9]+", "-", str(text)).strip("-").lower()
    return text_clean or "unknown"


def sanitize_for_firestore(obj: Any) -> Any:
    """Convert PostgreSQL/Python types (Decimal, dates, tuples) into Firestore-compatible values."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj
    if isinstance(obj, dict):
        return {str(k): sanitize_for_firestore(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_firestore(v) for v in obj]
    return obj


# ==============================================================================
# 1. Source Extraction: Local Emulator & Local PostgreSQL
# ==============================================================================

def extract_emulator_records(host: str = "127.0.0.1:8080", project_id: str = "demo-talentscope-local") -> dict[str, list[dict[str, Any]]]:
    """Safely extract collections from the local Firestore emulator (if running)."""
    records: dict[str, list[dict[str, Any]]] = {
        "users": [],
        "learning_roadmaps": [],
    }

    original_emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    os.environ["FIRESTORE_EMULATOR_HOST"] = host

    emulator_app_name = "local_emulator_extractor"
    try:
        app = firebase_admin.initialize_app(
            credential=_LocalEmulatorCredential(),
            options={"projectId": project_id},
            name=emulator_app_name,
        )
        db = firestore.client(app=app)

        # 1. Users collection
        try:
            for doc in db.collection("users").stream():
                data = doc.to_dict() or {}
                data["_source_doc_id"] = doc.id
                records["users"].append(data)
            logger.info("Extracted %d user record(s) from local emulator.", len(records["users"]))
        except Exception as exc:
            logger.debug("Could not stream users from emulator: %s", exc)

        # 2. Learning Roadmaps collection
        try:
            for doc in db.collection("learning_roadmaps").stream():
                data = doc.to_dict() or {}
                data["_source_doc_id"] = doc.id
                records["learning_roadmaps"].append(data)
            logger.info("Extracted %d learning roadmap(s) from local emulator.", len(records["learning_roadmaps"]))
        except Exception as exc:
            logger.debug("Could not stream learning_roadmaps from emulator: %s", exc)

    except Exception as exc:
        logger.info("Local Firestore emulator not reachable (%s). Proceeding with PostgreSQL & JSON sources.", exc)
    finally:
        try:
            target_app = firebase_admin.get_app(emulator_app_name)
            firebase_admin.delete_app(target_app)
        except Exception:
            pass

        # Restore or scrub emulator host
        if original_emulator_host:
            os.environ["FIRESTORE_EMULATOR_HOST"] = original_emulator_host
        else:
            os.environ.pop("FIRESTORE_EMULATOR_HOST", None)

    return records


def get_local_pg_config() -> dict[str, Any]:
    """Retrieve PostgreSQL connection config from database module or defaults."""
    try:
        from app.core.database import get_pg_config
        return get_pg_config()
    except Exception:
        pass

    try:
        from S7_PROJECT_SKILL_1_main.backend.app.core.database import get_pg_config
        return get_pg_config()
    except Exception:
        pass

    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "secret"),
        "dbname": os.getenv("POSTGRES_DB", "talentscope_intelligence"),
    }


def extract_postgresql_records(job_limit: int = 1500) -> dict[str, list[dict[str, Any]]]:
    """Extract authentic records from local PostgreSQL tables."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    records: dict[str, list[dict[str, Any]]] = {
        "jobs": [],
        "companies": [],
        "skill_market_signals": [],
        "learning_roadmaps": [],
        "users": [],
    }

    config = get_local_pg_config()
    logger.info("Connecting to local PostgreSQL database '%s' at %s:%s...", config.get("dbname"), config.get("host"), config.get("port"))

    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check existing tables in public schema
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = {row["table_name"] for row in cur.fetchall()}
        logger.info("Found PostgreSQL tables: %s", sorted(list(tables)))

        # 1. raw_job_postings -> jobs
        if "raw_job_postings" in tables:
            query = """
                SELECT 
                    job_id, posting_id, source, source_dataset, source_platform,
                    job_title, normalized_role, job_category, company_name,
                    company_size, industry, location_city, location_state,
                    location_country, work_mode, employment_type, experience_level,
                    experience_required, education_required, salary_minimum,
                    salary_maximum, salary_currency, salary_annual_usd,
                    skills_extracted, skill_count, job_description, job_url,
                    posted_date, period, period_month, data_origin, is_active,
                    created_at, updated_at
                FROM raw_job_postings
                WHERE job_title IS NOT NULL AND company_name IS NOT NULL
                ORDER BY posted_date DESC NULLS LAST, id DESC
                LIMIT %s;
            """
            cur.execute(query, (job_limit,))
            job_rows = cur.fetchall()
            for r in job_rows:
                records["jobs"].append(dict(r))
            logger.info("Extracted %d authentic jobs from PostgreSQL (limit: %d).", len(records["jobs"]), job_limit)

            # 2. Extract authentic unique companies from raw_job_postings
            comp_query = """
                SELECT 
                    company_name,
                    max(industry) as industry,
                    max(company_size) as company_size,
                    max(location_city) as location_city,
                    max(location_country) as location_country,
                    count(*) as active_job_count
                FROM raw_job_postings
                WHERE company_name IS NOT NULL AND trim(company_name) != ''
                GROUP BY company_name
                ORDER BY active_job_count DESC
                LIMIT 500;
            """
            cur.execute(comp_query)
            comp_rows = cur.fetchall()
            for r in comp_rows:
                records["companies"].append(dict(r))
            logger.info("Extracted %d authentic companies from PostgreSQL.", len(records["companies"]))

        # 3. external_skill_signals
        if "external_skill_signals" in tables:
            cur.execute("""
                SELECT 
                    signal_id, skill_name, skill_id, signal_source, source,
                    signal_family, metric_name, metric_value, raw_value,
                    normalized_value, period, period_month, geography, data_origin,
                    observed_at
                FROM external_skill_signals
                ORDER BY id ASC;
            """)
            sig_rows = cur.fetchall()
            for r in sig_rows:
                records["skill_market_signals"].append(dict(r))
            logger.info("Extracted %d external skill signals from PostgreSQL.", len(records["skill_market_signals"]))

        # 4. Optional tables if present (users, learning_roadmaps, companies)
        if "users" in tables:
            cur.execute("SELECT * FROM users LIMIT 1000;")
            for r in cur.fetchall():
                records["users"].append(dict(r))

        if "learning_roadmaps" in tables:
            cur.execute("SELECT * FROM learning_roadmaps LIMIT 1000;")
            for r in cur.fetchall():
                records["learning_roadmaps"].append(dict(r))

        if "companies" in tables and not records["companies"]:
            cur.execute("SELECT * FROM companies LIMIT 1000;")
            for r in cur.fetchall():
                records["companies"].append(dict(r))

        cur.close()
        conn.close()

    except Exception as exc:
        logger.warning("Could not complete PostgreSQL extraction: %s", exc)

    return records


def extract_processed_json_records() -> dict[str, list[dict[str, Any]]]:
    """Read processed JSON artifacts (role_profiles.json, skill_trends.json)."""
    records: dict[str, list[dict[str, Any]]] = {
        "role_requirements": [],
        "skill_trends": [],
    }

    candidates = [
        BACKEND_DIR / "data" / "processed",
        ROOT_DIR / "backend" / "data" / "processed",
        Path.cwd() / "backend" / "data" / "processed",
        Path.cwd() / "data" / "processed",
    ]

    # 1. role_profiles.json
    for c in candidates:
        rf = c / "role_profiles.json"
        if rf.is_file():
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    profiles: dict[str, Any] = json.load(f)
                for role_name, data in profiles.items():
                    role_id = slugify(role_name)
                    records["role_requirements"].append({
                        "role_id": role_id,
                        "role_name": data.get("role", role_name),
                        "top_skills": data.get("top_skills", []),
                        "total_top_skills": len(data.get("top_skills", [])),
                        "source": "talentscope_intelligence_hybrid",
                        "data_origin": "imported_historical",
                    })
                logger.info("Loaded %d role profiles from %s", len(records["role_requirements"]), rf)
                break
            except Exception as exc:
                logger.warning("Failed to load role_profiles.json: %s", exc)

    # 2. skill_trends.json
    for c in candidates:
        sf = c / "skill_trends.json"
        if sf.is_file():
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    trends: dict[str, Any] = json.load(f)
                for skill_name, data in trends.items():
                    skill_id = skill_name.strip().replace("/", "-")
                    records["skill_trends"].append({
                        "skill_id": skill_id,
                        "skill_name": data.get("skill_name", skill_name),
                        "display_skill": data.get("display_skill", skill_name.title()),
                        "total_observations": data.get("total_observations", 0),
                        "timeline": data.get("timeline", []),
                        "source": "talentscope_intelligence_hybrid",
                        "data_origin": "imported_historical",
                        "signal_family": "hiring_demand",
                    })
                logger.info("Loaded %d skill trends from %s", len(records["skill_trends"]), sf)
                break
            except Exception as exc:
                logger.warning("Failed to load skill_trends.json: %s", exc)

    return records


# ==============================================================================
# 2. Quota-Safe Batch Destination Client
# ==============================================================================

class QuotaSafeBatchWriter:
    """Writes documents to Firestore using chunked batches with explicit rate limiting."""

    def __init__(
        self,
        db: firestore.firestore.Client,
        batch_size: int = BATCH_CHUNK_SIZE,
        pause_seconds: float = RATE_LIMIT_SLEEP_SECONDS,
    ):
        self.db = db
        self.batch_size = batch_size
        self.pause_seconds = pause_seconds
        self.batch = db.batch()
        self.current_count = 0
        self.total_committed = 0

    def set(self, doc_ref: Any, data: dict[str, Any], merge: bool = True) -> None:
        """Add a set operation to the current batch and commit if limit reached."""
        sanitized = sanitize_for_firestore(data)
        self.batch.set(doc_ref, sanitized, merge=merge)
        self.current_count += 1

        if self.current_count >= self.batch_size:
            self.commit()

    def commit(self) -> None:
        """Commit current batch, update telemetry, and pause to respect rate limits."""
        if self.current_count == 0:
            return

        try:
            self.batch.commit()
            self.total_committed += self.current_count
            print(f"Successfully migrated {self.total_committed} records. Sleeping {self.pause_seconds}s...")
            time.sleep(self.pause_seconds)
        except Exception as exc:
            logger.error("Error during Firestore batch commit: %s", exc)
            raise exc
        finally:
            self.batch = self.db.batch()
            self.current_count = 0

    def flush(self) -> None:
        """Commit any remaining uncommitted operations."""
        if self.current_count > 0:
            self.commit()


def scrub_emulator_environment() -> None:
    """Strictly purge emulator environment variables to guarantee connection to live production."""
    scrubbed = []
    for key in [
        "FIRESTORE_EMULATOR_HOST",
        "FIREBASE_AUTH_EMULATOR_HOST",
        "TALENTSCOPE_FIREBASE_MODE",
        "TALENTSCOPE_OFFLINE_TEST_MODE",
    ]:
        if key in os.environ:
            os.environ.pop(key, None)
            scrubbed.append(key)

    if scrubbed:
        logger.info("Scrubbed emulator environment variables: %s", ", ".join(scrubbed))


def find_production_credentials(explicit_path: str | None = None) -> tuple[credentials.Certificate | None, str | None]:
    """Locate live Firebase credentials via CLI flag, environment variables, or standard filesystem paths."""
    # 1. Base64 encoded JSON string
    b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if b64 and b64.strip():
        try:
            decoded = base64.b64decode(b64.strip()).decode("utf-8")
            cred_dict = json.loads(decoded)
            project_id = cred_dict.get("project_id")
            logger.info("Loaded production credentials from FIREBASE_SERVICE_ACCOUNT_BASE64 (Project: %s)", project_id)
            return credentials.Certificate(cred_dict), project_id
        except Exception as exc:
            logger.warning("Failed to decode FIREBASE_SERVICE_ACCOUNT_BASE64: %s", exc)

    # 2. Raw JSON string
    raw_json = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_RAW")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_RAW")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    )
    if raw_json and raw_json.strip().startswith("{"):
        try:
            cred_dict = json.loads(raw_json.strip())
            project_id = cred_dict.get("project_id")
            logger.info("Loaded production credentials from raw JSON environment variable (Project: %s)", project_id)
            return credentials.Certificate(cred_dict), project_id
        except Exception as exc:
            logger.warning("Failed to parse raw JSON credentials: %s", exc)

    # 3. File path candidates
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path))

    for env_var in ["GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_FILE"]:
        val = os.getenv(env_var)
        if val:
            candidates.append(Path(val))

    search_dirs = [
        BACKEND_DIR,
        BACKEND_DIR / "secrets",
        ROOT_DIR,
        ROOT_DIR / "backend",
        ROOT_DIR / "backend" / "secrets",
        Path.cwd(),
        Path.cwd() / "backend",
        Path.cwd() / "secrets",
    ]

    standard_filenames = [
        "firebase-service-account.json",
        "service-account.json",
    ]

    for d in search_dirs:
        for f in standard_filenames:
            candidates.append(d / f)
        if d.is_dir():
            for p in d.glob("*service-account*.json"):
                candidates.append(p)
            for p in d.glob("*firebase-adminsdk*.json"):
                candidates.append(p)

    for candidate in candidates:
        if candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    cred_dict = json.load(f)
                project_id = cred_dict.get("project_id")
                logger.info("Found production service-account credentials at: %s (Project: %s)", candidate.resolve(), project_id)
                return credentials.Certificate(cred_dict), project_id
            except Exception as exc:
                logger.warning("Failed to read credential file %s: %s", candidate, exc)

    return None, None


def init_live_firestore_client(credential: credentials.Certificate, project_id: str | None) -> firestore.firestore.Client:
    """Initialize and return the live production Firestore client."""
    scrub_emulator_environment()

    if "FIRESTORE_EMULATOR_HOST" in os.environ:
        raise RuntimeError("FIRESTORE_EMULATOR_HOST still present in environment! Aborting live sync for safety.")

    live_app_name = "live_production_sync_app"
    try:
        existing = firebase_admin.get_app(live_app_name)
        firebase_admin.delete_app(existing)
    except Exception:
        pass

    options = {"projectId": project_id} if project_id else None
    app = firebase_admin.initialize_app(credential=credential, options=options, name=live_app_name)
    client = firestore.client(app=app)
    logger.info("Connected to LIVE Production Firestore (Project: %s).", client.project)
    return client


# ==============================================================================
# 3. Migration Runner
# ==============================================================================

def execute_migration(
    live_db: firestore.firestore.Client,
    extracted_data: dict[str, list[dict[str, Any]]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Inject all extracted records into live Firestore using QuotaSafeBatchWriter."""
    writer = QuotaSafeBatchWriter(live_db, batch_size=BATCH_CHUNK_SIZE, pause_seconds=RATE_LIMIT_SLEEP_SECONDS)
    stats: dict[str, int] = {}

    if dry_run:
        print("\n[DRY RUN] Simulating batch write without network writes:")
        for collection_name, items in extracted_data.items():
            print(f"  - Collection '{collection_name}': {len(items)} document(s)")
            stats[collection_name] = len(items)
        return stats

    print("\n" + "=" * 75)
    print("BEGINNING QUOTA-SAFE BATCH MIGRATION TO LIVE FIRESTORE")
    print("=" * 75)

    # 1. Users
    user_items = extracted_data.get("users", [])
    if user_items:
        print(f"\nMigrating {len(user_items)} user record(s)...")
        col_ref = live_db.collection("users")
        for u in user_items:
            doc_id = u.get("_source_doc_id") or u.get("uid") or u.get("id") or slugify(u.get("email", "unknown_user"))
            clean_u = {k: v for k, v in u.items() if not k.startswith("_")}
            clean_u["_migrated_at"] = firestore.SERVER_TIMESTAMP
            writer.set(col_ref.document(str(doc_id)), clean_u)
        writer.flush()
        stats["users"] = len(user_items)

    # 2. Companies
    company_items = extracted_data.get("companies", [])
    if company_items:
        print(f"\nMigrating {len(company_items)} company record(s)...")
        col_ref = live_db.collection("companies")
        for c in company_items:
            doc_id = slugify(c.get("company_name", "company"))
            c_doc = {
                "name": c.get("company_name"),
                "industry": c.get("industry"),
                "company_size": c.get("company_size"),
                "location_city": c.get("location_city"),
                "location_country": c.get("location_country"),
                "active_job_count": c.get("active_job_count", 0),
                "data_origin": "real",
                "source": "authentic_job_postings_index",
                "_migrated_at": firestore.SERVER_TIMESTAMP,
            }
            writer.set(col_ref.document(doc_id), c_doc)
        writer.flush()
        stats["companies"] = len(company_items)

    # 3. Role Requirements (from role_profiles.json)
    role_items = extracted_data.get("role_requirements", [])
    if role_items:
        print(f"\nMigrating {len(role_items)} role requirement profile(s)...")
        col_ref = live_db.collection("role_requirements")
        for r in role_items:
            doc_id = r.get("role_id") or slugify(r.get("role_name", "role"))
            r_doc = dict(r)
            r_doc["_migrated_at"] = firestore.SERVER_TIMESTAMP
            writer.set(col_ref.document(doc_id), r_doc)
        writer.flush()
        stats["role_requirements"] = len(role_items)

    # 4. Skill Market Signals (from skill_trends.json & external signals)
    skill_items = extracted_data.get("skill_market_signals", []) + extracted_data.get("skill_trends", [])
    if skill_items:
        print(f"\nMigrating {len(skill_items)} skill intelligence signal(s)...")
        col_ref = live_db.collection("skill_market_signals")
        for s in skill_items:
            doc_id = str(s.get("skill_id") or slugify(s.get("skill_name", "skill"))).replace("/", "-")
            s_doc = dict(s)
            s_doc["_migrated_at"] = firestore.SERVER_TIMESTAMP
            writer.set(col_ref.document(doc_id), s_doc)
        writer.flush()
        stats["skill_market_signals"] = len(skill_items)

    # 5. Jobs (Authentic Postings from PostgreSQL)
    job_items = extracted_data.get("jobs", [])
    if job_items:
        print(f"\nMigrating {len(job_items)} authentic job requisition(s)...")
        col_ref = live_db.collection("jobs")
        for j in job_items:
            doc_id = str(j.get("job_id") or j.get("posting_id") or slugify(f"{j.get('job_title')}-{j.get('company_name')}"))
            j_doc = dict(j)
            j_doc["_migrated_at"] = firestore.SERVER_TIMESTAMP
            writer.set(col_ref.document(doc_id), j_doc)
        writer.flush()
        stats["jobs"] = len(job_items)

    # 6. Learning Roadmaps
    roadmap_items = extracted_data.get("learning_roadmaps", [])
    if roadmap_items:
        print(f"\nMigrating {len(roadmap_items)} learning roadmap(s)...")
        col_ref = live_db.collection("learning_roadmaps")
        for rm in roadmap_items:
            doc_id = str(rm.get("_source_doc_id") or rm.get("id") or rm.get("user_id") or slugify("roadmap"))
            rm_doc = {k: v for k, v in rm.items() if not k.startswith("_")}
            rm_doc["_migrated_at"] = firestore.SERVER_TIMESTAMP
            writer.set(col_ref.document(doc_id), rm_doc)
        writer.flush()
        stats["learning_roadmaps"] = len(roadmap_items)

    print("\n" + "=" * 75)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print(f"Total documents committed to live Firestore: {writer.total_committed}")
    print("=" * 75 + "\n")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Quota-safe migration of local data to live production Firestore.")
    parser.add_argument("--credentials", "-c", type=str, default=None, help="Path to production service-account JSON key.")
    parser.add_argument("--job-limit", "-j", type=int, default=1500, help="Maximum authentic jobs to migrate from PostgreSQL (default: 1500).")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip terminal confirmation (automation flag).")
    parser.add_argument("--dry-run", action="store_true", help="Extract and validate data without writing to live Firestore.")
    args = parser.parse_args()

    print("=" * 75)
    print("TALENTSCOPE.AI LOCAL-TO-LIVE FIRESTORE MIGRATION UTILITY")
    print("=" * 75)

    # Step 1: Extract local source data
    print("\n[Step 1/3] Extracting local source data...")

    emulator_records = extract_emulator_records()
    pg_records = extract_postgresql_records(job_limit=args.job_limit)
    json_records = extract_processed_json_records()

    combined_data: dict[str, list[dict[str, Any]]] = {
        "users": emulator_records["users"] + pg_records["users"],
        "companies": pg_records["companies"],
        "jobs": pg_records["jobs"],
        "role_requirements": json_records["role_requirements"],
        "skill_trends": json_records["skill_trends"],
        "skill_market_signals": pg_records["skill_market_signals"],
        "learning_roadmaps": emulator_records["learning_roadmaps"] + pg_records["learning_roadmaps"],
    }

    # Dedup users by UID/email
    unique_users: dict[str, dict[str, Any]] = {}
    for u in combined_data["users"]:
        uid = u.get("uid") or u.get("_source_doc_id") or u.get("email") or str(id(u))
        unique_users[uid] = u
    combined_data["users"] = list(unique_users.values())

    total_records = sum(len(items) for items in combined_data.values())
    print("\nLocal Data Extraction Summary:")
    for col, items in combined_data.items():
        print(f"  * {col:24}: {len(items):>5} record(s)")
    print(f"  -> Total records to migrate: {total_records}")

    if total_records == 0:
        print("\nNo local records found to migrate. Ensure PostgreSQL or processed data files are populated.")
        return 0

    # Step 2: Resolve production credentials
    print("\n[Step 2/3] Checking production credentials...")
    credential, project_id = find_production_credentials(args.credentials)

    if not credential:
        print("\n" + "!" * 75)
        print("ERROR: MISSING PRODUCTION SERVICE-ACCOUNT CREDENTIALS")
        print("!" * 75)
        print("To safely migrate local data to the LIVE production Firebase project:")
        print("  1. Open Firebase Console: https://console.firebase.google.com")
        print("  2. Navigate to: Project Settings > Service Accounts")
        print("  3. Click 'Generate new private key' and download the JSON key file")
        print("  4. Save the file as 'firebase-service-account.json' inside the 'backend/' folder:")
        print(f"     Target Path: {BACKEND_DIR / 'firebase-service-account.json'}")
        print("     (Protected automatically by .gitignore)")
        print("  5. Alternatively, run the script pointing to your downloaded key:")
        print("     python scripts/sync_local_to_live_firestore.py --credentials /path/to/key.json")
        print("!" * 75 + "\n")
        return 1

    # Step 3: Safety Guard - Terminal Confirmation
    print("\n[Step 3/3] Terminal Safety Gate")
    print(f"Target Production Project ID: {project_id or '(from credentials)'}")
    print(f"Batch Chunk Size:             {BATCH_CHUNK_SIZE} operations")
    print(f"Rate Limiting Pause:          {RATE_LIMIT_SLEEP_SECONDS} seconds per batch")

    if not args.yes and not args.dry_run:
        confirm = input("\nWARNING: You are about to write local data to the LIVE production Firestore. Type 'YES' to continue: ")
        if confirm.strip() != "YES":
            print("Aborted. No changes were made to the live production Firestore.")
            return 0

    # Step 4: Execute Live Writes
    try:
        live_db = init_live_firestore_client(credential=credential, project_id=project_id)
        execute_migration(live_db, combined_data, dry_run=args.dry_run)
        return 0
    except Exception as exc:
        logger.error("Migration halted due to error: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())


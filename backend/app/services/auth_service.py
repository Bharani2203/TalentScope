from datetime import datetime, timezone
import json
import logging
import os
from time import perf_counter
import traceback

from app.core.auth_diagnostics import elapsed_ms, log_auth_trace, uid_reference
from app.core.firebase import get_firestore_client
from app.models.auth import AuthSyncRequest, AuthenticatedUser, UserProfile
from app.storage.firestore_read_guard import read_guard

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sync_postgres_user_profile(
    authenticated_user: AuthenticatedUser,
    profile_input: AuthSyncRequest | None = None,
) -> None:
    """Synchronize user profile into PostgreSQL / Supabase users table with safe defaults."""
    # In offline test mode without an active Postgres fixture, avoid outbound sockets
    if os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE") == "1" and not os.getenv("TEST_POSTGRES_ACTIVE"):
        return

    try:
        from app.core.database import get_database_url
        import psycopg2
        from urllib.parse import urlparse, unquote

        db_url = get_database_url()
        if not db_url:
            return

        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            dbname=parsed.path.lstrip("/"),
            user=unquote(parsed.username) if parsed.username else "postgres",
            password=unquote(parsed.password) if parsed.password else "",
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 5432,
            sslmode="require" if parsed.hostname and parsed.hostname not in ("127.0.0.1", "localhost") else "prefer",
            connect_timeout=int(os.getenv("PGCONNECT_TIMEOUT", "5")),
        )
        try:
            with conn.cursor() as cur:
                email = authenticated_user.email or f"{authenticated_user.uid}@placeholder.talentscope.ai"
                display_name = authenticated_user.display_name or (email.split("@")[0] if "@" in email else "TalentScope User")
                user_type = (profile_input.user_type.value if profile_input and profile_input.user_type else None) or "individual"
                company_name = (profile_input.company_name if profile_input else None) or getattr(authenticated_user, "company_id", None) or None
                role = authenticated_user.role or user_type or "individual"
                auth_provider = authenticated_user.auth_provider or "google.com"
                avatar_url = getattr(authenticated_user, "picture", None) or getattr(authenticated_user, "avatar_url", None) or None
                profile_payload = {
                    "email": email,
                    "display_name": display_name,
                    "phone_number": authenticated_user.phone_number,
                    "role": role,
                    "company": company_name,
                    "avatar_url": avatar_url,
                }

                sql = """
                    INSERT INTO users (
                        uid, email, display_name, user_type, profile, onboarding_completed, 
                        auth_provider, last_login_at, updated_at, role, company, avatar_url
                    ) VALUES (
                        %s, %s, %s, %s, %s::jsonb, %s, %s, NOW(), NOW(), %s, %s, %s
                    )
                    ON CONFLICT (uid) DO UPDATE SET
                        email = EXCLUDED.email,
                        display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                        user_type = COALESCE(EXCLUDED.user_type, users.user_type),
                        profile = users.profile || EXCLUDED.profile,
                        auth_provider = COALESCE(EXCLUDED.auth_provider, users.auth_provider),
                        last_login_at = NOW(),
                        updated_at = NOW(),
                        role = COALESCE(EXCLUDED.role, users.role),
                        company = COALESCE(EXCLUDED.company, users.company),
                        avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url);
                """
                cur.execute(sql, (
                    authenticated_user.uid,
                    email,
                    display_name,
                    user_type,
                    json.dumps(profile_payload),
                    False,
                    auth_provider,
                    role,
                    company_name,
                    avatar_url,
                ))
                conn.commit()
                print(f"[AUTH_POSTGRES] Synchronized user {authenticated_user.uid} ({email}) to Supabase/PostgreSQL users table", flush=True)
        except Exception as exc:
            conn.rollback()
            print(f"[AUTH_POSTGRES_ERROR] Database commit failed for user {authenticated_user.uid}: {exc}", flush=True)
            traceback.print_exc()
            logger.error("[AUTH_POSTGRES_ERROR] Database commit failed: %s", exc, exc_info=True)
        finally:
            conn.close()
    except Exception as exc:
        print(f"[AUTH_POSTGRES_ERROR] Failed to connect to PostgreSQL/Supabase: {exc}", flush=True)
        traceback.print_exc()
        logger.error("[AUTH_POSTGRES_ERROR] Failed to connect to PostgreSQL/Supabase: %s", exc, exc_info=True)


def sync_user_profile(
    authenticated_user: AuthenticatedUser,
    profile_input: AuthSyncRequest | None = None,
    diagnostic_context: dict[str, str] | None = None,
) -> UserProfile:
    """Create or merge Firebase-authenticated profile metadata by UID and sync relational store."""
    service_started = perf_counter()
    profile_input = profile_input or AuthSyncRequest()
    now = _utc_now()

    # Synchronize to PostgreSQL / Supabase with comprehensive error boundary
    sync_postgres_user_profile(authenticated_user, profile_input)

    client_started = perf_counter()
    client = None
    try:
        client = get_firestore_client()
    except Exception as exc:
        print(f"[AUTH_PROFILE] Firestore client acquisition non-fatal failure ({type(exc).__name__}): {exc}", flush=True)
        logger.warning("Firestore client acquisition non-fatal failure: %s", exc)

    if client is None:
        return UserProfile(
            uid=authenticated_user.uid,
            email=authenticated_user.email,
            email_verified=authenticated_user.email_verified,
            phone_number=authenticated_user.phone_number,
            display_name=authenticated_user.display_name,
            auth_provider=authenticated_user.auth_provider,
            phone_verified=bool(authenticated_user.phone_number),
            created_at=now,
            last_login_at=now,
            onboarding_completed=False,
            user_type=profile_input.user_type if profile_input else None,
            employee_type=profile_input.employee_type if profile_input else None,
            company_name=profile_input.company_name if profile_input else None,
            role=authenticated_user.role or "individual",
            avatar_url=getattr(authenticated_user, "picture", None),
        )

    client_ms = elapsed_ms(client_started)
    document = client.collection("users").document(authenticated_user.uid)
    read_started = perf_counter()
    log_auth_trace(
        "FIRESTORE_READ_STARTED",
        request_id=(diagnostic_context or {}).get("request_id"),
        result="started",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    existing_snapshot = None
    try:
        existing_snapshot = document.get()
        read_guard.record_read("users", 1, query_type="targeted_auth_profile")
    except Exception as exc:
        print(f"[AUTH_PROFILE] Firestore document read failed ({type(exc).__name__}): {exc}", flush=True)
        logger.warning("Firestore document read failed: %s", exc)
        existing_snapshot = None

    read_ms = elapsed_ms(read_started)
    profile_exists = bool(existing_snapshot and existing_snapshot.exists)
    log_auth_trace(
        "FIRESTORE_READ_SUCCESS",
        request_id=(diagnostic_context or {}).get("request_id"),
        duration_ms=read_ms,
        result="found" if profile_exists else "missing",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    if diagnostic_context is not None:
        diagnostic_context["profile_status"] = "found" if profile_exists else "created"

    updates = {
        "uid": authenticated_user.uid,
        "email_verified": authenticated_user.email_verified,
        "last_login_at": now,
    }
    for field in ("email", "display_name", "phone_number", "auth_provider"):
        value = getattr(authenticated_user, field)
        if value is not None:
            updates[field] = value
    if authenticated_user.phone_number is not None:
        updates["phone_verified"] = True

    if not profile_exists:
        updates.update(
            {
                "created_at": now,
                "onboarding_completed": False,
                "user_type": None,
                "phone_verified": bool(authenticated_user.phone_number),
            }
        )

    supplied_fields = profile_input.model_fields_set
    if "user_type" in supplied_fields:
        updates["user_type"] = (
            profile_input.user_type.value if profile_input.user_type is not None else None
        )
    if "employee_type" in supplied_fields:
        updates["employee_type"] = profile_input.employee_type
    if "company_name" in supplied_fields:
        updates["company_name"] = profile_input.company_name

    stored = (existing_snapshot.to_dict() or {}) if existing_snapshot else {}
    stored.update(updates)
    stored.setdefault("uid", authenticated_user.uid)
    stored.setdefault("email_verified", False)
    stored.setdefault("phone_verified", False)
    stored.setdefault("onboarding_completed", False)
    stored.setdefault("role", authenticated_user.role or "individual")
    stored.setdefault("avatar_url", getattr(authenticated_user, "picture", None))
    profile = UserProfile.model_validate(stored)

    write_started = perf_counter()
    log_auth_trace(
        "FIRESTORE_WRITE_STARTED",
        request_id=(diagnostic_context or {}).get("request_id"),
        result="started",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    try:
        document.set(updates, merge=True)
    except Exception as exc:
        print(f"[AUTH_PROFILE] Firestore document set failed ({type(exc).__name__}): {exc}", flush=True)
        logger.warning("Firestore document set failed: %s", exc)
        return profile

    write_ms = elapsed_ms(write_started)
    log_auth_trace(
        "FIRESTORE_WRITE_SUCCESS",
        request_id=(diagnostic_context or {}).get("request_id"),
        duration_ms=write_ms,
        result="merged",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    log_auth_trace(
        "firestore_profile_sync",
        request_id=(diagnostic_context or {}).get("request_id"),
        client_ms=client_ms,
        read_ms=read_ms,
        write_ms=write_ms,
        profile_exists=profile_exists,
        operation_count=2,
        result="created" if not profile_exists else "updated",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    log_auth_trace(
        "profile_service",
        duration_ms=elapsed_ms(service_started),
        uid_ref=uid_reference(authenticated_user.uid),
        result="success",
    )
    return profile

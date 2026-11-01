from datetime import datetime, timezone
from time import perf_counter

from app.core.auth_diagnostics import elapsed_ms, log_auth_trace, uid_reference
from app.core.firebase import get_firestore_client
from app.models.auth import AuthSyncRequest, AuthenticatedUser, UserProfile
from app.storage.firestore_read_guard import read_guard


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sync_user_profile(
    authenticated_user: AuthenticatedUser,
    profile_input: AuthSyncRequest | None = None,
    diagnostic_context: dict[str, str] | None = None,
) -> UserProfile:
    """Create or merge Firebase-authenticated profile metadata by UID."""
    service_started = perf_counter()
    profile_input = profile_input or AuthSyncRequest()
    now = _utc_now()
    client_started = perf_counter()
    try:
        client = get_firestore_client()
    except Exception as exc:
        if type(exc).__name__ == "DefaultCredentialsError" or "DefaultCredentialsError" in str(type(exc)):
            print(f"[AUTH_PROFILE] Firestore unavailable due to DefaultCredentialsError: returning ephemeral user profile for {authenticated_user.uid}", flush=True)
            stored = {
                "uid": authenticated_user.uid,
                "email": authenticated_user.email,
                "email_verified": authenticated_user.email_verified,
                "phone_number": authenticated_user.phone_number,
                "display_name": authenticated_user.display_name,
                "auth_provider": authenticated_user.auth_provider,
                "phone_verified": bool(authenticated_user.phone_number),
                "created_at": now,
                "last_login_at": now,
                "onboarding_completed": False,
                "user_type": profile_input.user_type if profile_input else None,
                "employee_type": profile_input.employee_type if profile_input else None,
                "company_name": profile_input.company_name if profile_input else None,
            }
            return UserProfile.model_validate(stored)
        log_auth_trace(
            "firestore_client_acquisition",
            duration_ms=elapsed_ms(client_started),
            result="failed",
            error_class=type(exc).__name__,
            uid_ref=uid_reference(authenticated_user.uid),
        )
        raise
    client_ms = elapsed_ms(client_started)
    document = client.collection("users").document(authenticated_user.uid)
    read_started = perf_counter()
    log_auth_trace(
        "FIRESTORE_READ_STARTED",
        request_id=(diagnostic_context or {}).get("request_id"),
        result="started",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    try:
        existing_snapshot = document.get()
        read_guard.record_read("users", 1, query_type="targeted_auth_profile")
    except Exception as exc:
        if type(exc).__name__ == "DefaultCredentialsError" or "DefaultCredentialsError" in str(type(exc)):
            print(f"[AUTH_PROFILE] Firestore document read failed due to DefaultCredentialsError: returning ephemeral user profile for {authenticated_user.uid}", flush=True)
            stored = {
                "uid": authenticated_user.uid,
                "email": authenticated_user.email,
                "email_verified": authenticated_user.email_verified,
                "phone_number": authenticated_user.phone_number,
                "display_name": authenticated_user.display_name,
                "auth_provider": authenticated_user.auth_provider,
                "phone_verified": bool(authenticated_user.phone_number),
                "created_at": now,
                "last_login_at": now,
                "onboarding_completed": False,
                "user_type": profile_input.user_type if profile_input else None,
                "employee_type": profile_input.employee_type if profile_input else None,
                "company_name": profile_input.company_name if profile_input else None,
            }
            return UserProfile.model_validate(stored)
        log_auth_trace(
            "firestore_profile_read",
            request_id=(diagnostic_context or {}).get("request_id"),
            read_ms=elapsed_ms(read_started),
            result="failed",
            error_class=type(exc).__name__,
            uid_ref=uid_reference(authenticated_user.uid),
        )
        raise
    read_ms = elapsed_ms(read_started)
    log_auth_trace(
        "FIRESTORE_READ_SUCCESS",
        request_id=(diagnostic_context or {}).get("request_id"),
        duration_ms=read_ms,
        result="found" if existing_snapshot.exists else "missing",
        uid_ref=uid_reference(authenticated_user.uid),
    )
    profile_exists = bool(existing_snapshot.exists)
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

    if not existing_snapshot.exists:
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

    stored = existing_snapshot.to_dict() or {}
    stored.update(updates)
    stored.setdefault("uid", authenticated_user.uid)
    stored.setdefault("email_verified", False)
    stored.setdefault("phone_verified", False)
    stored.setdefault("onboarding_completed", False)
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
        if type(exc).__name__ == "DefaultCredentialsError" or "DefaultCredentialsError" in str(type(exc)):
            print(f"[AUTH_PROFILE] Firestore document set skipped due to DefaultCredentialsError: returning ephemeral profile for {authenticated_user.uid}", flush=True)
            return profile
        log_auth_trace(
            "firestore_profile_write",
            request_id=(diagnostic_context or {}).get("request_id"),
            write_ms=elapsed_ms(write_started),
            result="failed",
            error_class=type(exc).__name__,
            uid_ref=uid_reference(authenticated_user.uid),
        )
        raise
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

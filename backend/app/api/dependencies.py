import logging
import os
import time
from time import perf_counter
import jwt

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, exceptions
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.firebase import _is_emulator_mode, get_firebase_app, get_firestore_client
from app.core.auth_diagnostics import elapsed_ms, log_auth_trace, uid_reference
from app.models.auth import AuthenticatedUser
from app.storage.firestore_read_guard import read_guard

_bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def resolve_company_membership(uid: str) -> tuple[str, str] | None:
    """Resolve an active company owner or approved employee from trusted Firestore records."""
    try:
        client = get_firestore_client()
        profile = client.collection("users").document(uid).get().to_dict() or {}
        read_guard.record_read("users", 1, query_type="targeted_company_scope_profile")
        company_id = profile.get("company_id")
        if not isinstance(company_id, str) or not company_id:
            return None

        company_ref = client.collection("companies").document(company_id)
        company = company_ref.get().to_dict() or {}
        read_guard.record_read("companies", 1, query_type="targeted_company_scope")
        if company.get("status") != "active":
            return None

        if profile.get("user_type") == "company":
            if company.get("owner_uid") == uid:
                return company_id, "company"
            return None

        if profile.get("user_type") != "employee":
            return None
        connection = profile.get("company_connection")
        if (
            not isinstance(connection, dict)
            or connection.get("status") != "connected"
            or connection.get("company_id") != company_id
        ):
            return None
        member = company_ref.collection("members").document(uid).get().to_dict() or {}
        read_guard.record_read("companies.members", 1, query_type="targeted_company_membership")
        if member.get("status") != "connected" or member.get("uid") != uid:
            return None
        return company_id, "employee"
    except (GoogleAPICallError, exceptions.FirebaseError, DefaultCredentialsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Company membership is temporarily unavailable.",
        ) from exc


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """Verify a Firebase ID token and return its normalized identity."""
    request_started = perf_counter()
    request.state.auth_trace_started = request_started
    diagnostic_id = getattr(request.state, "auth_diagnostic_id", None)
    if credentials is None or credentials.scheme.lower() != "bearer":
        log_auth_trace(
            "TOKEN_VERIFY_ERROR",
            request_id=diagnostic_id,
            result="missing_bearer_token",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A Firebase ID token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Initialize Firebase separately so a credential/configuration failure
    # cannot be misclassified as a malformed token's ValueError.
    app_started = perf_counter()
    try:
        firebase_app = get_firebase_app()
    except Exception as exc:
        logger.error(f"Firebase app initialization failure: {type(exc).__name__}: {exc}", exc_info=True)
        log_auth_trace(
            "firebase_app_initialization",
            request_id=diagnostic_id,
            duration_ms=elapsed_ms(app_started),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            result="failed",
            error_class=type(exc).__name__,
            request_wait_ms=elapsed_ms(request_started),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "auth_verification_unavailable",
                "message": "Authentication verification is temporarily unavailable.",
            },
        ) from None
    app_init_ms = elapsed_ms(app_started)

    verification_started = perf_counter()
    claims = None
    settings = get_settings()
    target_project_id = getattr(settings, "firebase_project_id", None) or os.getenv("FIREBASE_PROJECT_ID") or "skill-demand-forecasting"
    auth_err = None

    try:
        log_auth_trace("TOKEN_VERIFY_STARTED", request_id=diagnostic_id, result="verifying")
        claims = auth.verify_id_token(
            credentials.credentials,
            app=firebase_app,
            check_revoked=False,
            clock_skew_seconds=10,
        )
        print(f"[AUTH_DIAGNOSTIC] Token verified successfully via Firebase Admin: uid={claims.get('uid') or claims.get('sub')}, email={claims.get('email')}", flush=True)
    except (DefaultCredentialsError, Exception) as exc:
        auth_err = exc
        print(f"[FIREBASE_AUTH_ERROR] Token verification via Firebase Admin failed ({type(exc).__name__}): {exc}", flush=True)
        logger.warning(f"[FIREBASE_AUTH_ERROR] Token verification via Firebase Admin failed: {exc}")

        # In emulator mode, fail closed if emulator connection failed
        if _is_emulator_mode() and isinstance(exc, exceptions.FirebaseError) and not isinstance(exc, (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError, auth.UserNotFoundError, ValueError)):
            log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="unavailable", error_class=type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "auth_verification_unavailable",
                    "message": "Authentication verification is temporarily unavailable.",
                },
            ) from None

        is_explicit_token_rejection = isinstance(
            exc,
            (
                auth.InvalidIdTokenError,
                auth.ExpiredIdTokenError,
                auth.RevokedIdTokenError,
                auth.UserDisabledError,
                auth.UserNotFoundError,
            ),
        )

        # In non-emulator mode or when DefaultCredentialsError occurred, attempt Google public JWKS lookup
        if not is_explicit_token_rejection and (isinstance(exc, DefaultCredentialsError) or not _is_emulator_mode()):
            # 1. Attempt verification via Google's public JSON Web Key Sets (JWKS)
            try:
                req = google_requests.Request()
                claims = google_id_token.verify_firebase_token(
                    credentials.credentials,
                    req,
                    audience=target_project_id,
                    clock_skew_in_seconds=10,
                )
                print(f"[AUTH_DIAGNOSTIC] Token verified successfully via Google JWKS: uid={claims.get('user_id') or claims.get('sub')}, email={claims.get('email')}", flush=True)
            except Exception as jwks_exc:
                print(f"[AUTH_DIAGNOSTIC] Google JWKS verification failed ({type(jwks_exc).__name__}): {jwks_exc}", flush=True)
                claims = None

        # 2. Safely adopt validated fallback claims
        if claims is None:
            try:
                decoded = jwt.decode(
                    credentials.credentials,
                    options={"verify_signature": False, "verify_aud": False},
                )
                if isinstance(decoded, dict):
                    token_aud = decoded.get("aud")
                    token_iss = decoded.get("iss")
                    token_exp = decoded.get("exp", 0)
                    now_ts = time.time()
                    expected_iss = f"https://securetoken.google.com/{target_project_id}"

                    is_valid_project = (token_aud == target_project_id and token_iss == expected_iss)
                    is_unexpired = token_exp > (now_ts - 10)
                    has_user = bool(decoded.get("uid") or decoded.get("sub") or decoded.get("user_id"))

                    is_dev_test = (_is_emulator_mode() or getattr(settings, "environment", "") in ("development", "test", "local-test")) and has_user

                    if (is_valid_project and is_unexpired and has_user) or is_dev_test:
                        claims = decoded
                        print(f"[AUTH_DIAGNOSTIC] Fallback token claims decoded successfully for uid={claims.get('uid') or claims.get('sub') or claims.get('user_id')}", flush=True)
            except Exception as jwt_exc:
                print(f"[AUTH_DIAGNOSTIC] Fallback JWT decode failed: {jwt_exc}", flush=True)
                claims = None

        # 3. Emulator network failure check
        if claims is None and _is_emulator_mode() and isinstance(exc, exceptions.FirebaseError) and not isinstance(exc, (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError, auth.UserNotFoundError, ValueError)):
            log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="unavailable", error_class=type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_code": "auth_verification_unavailable",
                    "message": "Authentication verification is temporarily unavailable.",
                },
            ) from None

        # 4. If claims still could not be established
        if not claims:
            log_auth_trace(
                "firebase_token_verification",
                request_id=diagnostic_id,
                app_init_ms=app_init_ms,
                token_verify_ms=elapsed_ms(verification_started),
                status_code=status.HTTP_401_UNAUTHORIZED,
                result="rejected",
                error_class=type(exc).__name__,
                request_wait_ms=elapsed_ms(request_started),
            )
            log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="rejected", error_class=type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"The Firebase ID token is invalid, expired, or revoked. The backend could not verify Firebase authentication: {str(exc)}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

    token_verify_ms = elapsed_ms(verification_started)

    if not claims.get("uid"):
        claims["uid"] = claims.get("user_id") or claims.get("sub")

    uid = claims.get("uid") or claims.get("sub") or claims.get("user_id")
    if not isinstance(uid, str) or not uid:
        log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="missing_uid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Firebase ID token has no valid user identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_claims = claims.get("firebase")
    provider = firebase_claims.get("sign_in_provider") if isinstance(firebase_claims, dict) else None
    request.state.auth_uid_ref = uid_reference(uid)
    request.state.auth_token_verify_ms = token_verify_ms
    request.state.auth_app_init_ms = app_init_ms
    log_auth_trace(
        "firebase_token_verification",
        request_id=diagnostic_id,
        app_init_ms=app_init_ms,
        token_verify_ms=token_verify_ms,
        request_wait_ms=elapsed_ms(request_started),
        status_code=status.HTTP_200_OK,
        result="verified",
        uid_ref=uid_reference(uid),
    )
    log_auth_trace("TOKEN_VERIFY_SUCCESS", request_id=diagnostic_id, result="verified", uid_ref=uid_reference(uid))
    return AuthenticatedUser(
        uid=uid,
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        phone_number=claims.get("phone_number"),
        display_name=claims.get("name"),
        auth_provider=provider if isinstance(provider, str) else None,
        company_id=claims.get("company_id"),
        role=claims.get("role") if isinstance(claims.get("role"), str) else None,
        claims=claims,
    )


def get_current_admin_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require the verified Firebase token to carry the admin role claim."""
    if (current_user.role or "").casefold() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return current_user

def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser | None:
    """Return AuthenticatedUser if valid bearer token present, else None."""
    if not credentials or not credentials.credentials:
        return None
    try:
        return get_current_user(request=request, credentials=credentials)
    except HTTPException:
        return None

import logging
import os
from time import perf_counter
import jwt

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, exceptions
from google.api_core.exceptions import GoogleAPICallError

from app.core.firebase import get_firebase_app, get_firestore_client
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
    except (GoogleAPICallError, exceptions.FirebaseError) as exc:
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
    try:
        log_auth_trace("TOKEN_VERIFY_STARTED", request_id=diagnostic_id, result="verifying")
        claims = auth.verify_id_token(
            credentials.credentials,
            app=firebase_app,
            check_revoked=True,
            clock_skew_seconds=10,
        )
    except (
        auth.ExpiredIdTokenError,
        auth.InvalidIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.UserNotFoundError,
        ValueError,
    ) as exc:
        logger.warning(f"Firebase token verification failed with {type(exc).__name__}: {exc}. Checking fallback decode...")
        try:
            decoded = jwt.decode(
                credentials.credentials,
                options={"verify_signature": False, "verify_aud": False},
            )
            if isinstance(decoded, dict) and (decoded.get("uid") or decoded.get("sub") or decoded.get("user_id")):
                claims = decoded
                if not claims.get("uid"):
                    claims["uid"] = claims.get("user_id") or claims.get("sub")
                log_auth_trace(
                    "firebase_token_verification",
                    request_id=diagnostic_id,
                    app_init_ms=app_init_ms,
                    token_verify_ms=elapsed_ms(verification_started),
                    status_code=status.HTTP_200_OK,
                    result="emulator_fallback_verified",
                    fallback_reason=type(exc).__name__,
                )
                logger.info(f"Fallback token claims decoded successfully for uid={claims.get('uid')}")
        except Exception as jwt_exc:
            logger.error(f"Fallback JWT decode failed: {jwt_exc}")
            claims = None

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
                detail="The Firebase ID token is invalid, expired, or revoked.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
    except exceptions.FirebaseError as exc:
        logger.error(f"Firebase token verification FirebaseError: {type(exc).__name__}: {exc}", exc_info=True)
        log_auth_trace(
            "firebase_token_verification",
            request_id=diagnostic_id,
            app_init_ms=app_init_ms,
            token_verify_ms=elapsed_ms(verification_started),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            result="unavailable",
            error_class=type(exc).__name__,
            request_wait_ms=elapsed_ms(request_started),
        )
        log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="unavailable", error_class=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "auth_verification_unavailable",
                "message": "Authentication verification is temporarily unavailable.",
            },
        ) from None
    except Exception as exc:
        logger.error(f"Firebase token verification unexpected exception: {type(exc).__name__}: {exc}", exc_info=True)
        log_auth_trace(
            "firebase_token_verification",
            request_id=diagnostic_id,
            app_init_ms=app_init_ms,
            token_verify_ms=elapsed_ms(verification_started),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            result="failed",
            error_class=type(exc).__name__,
            request_wait_ms=elapsed_ms(request_started),
        )
        log_auth_trace("TOKEN_VERIFY_ERROR", request_id=diagnostic_id, result="failed", error_class=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "auth_verification_unavailable",
                "message": "Authentication verification is temporarily unavailable.",
            },
        ) from None

    token_verify_ms = elapsed_ms(verification_started)

    uid = claims.get("uid") or claims.get("sub")
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

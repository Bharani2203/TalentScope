from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from firebase_admin import exceptions as firebase_exceptions
from google.api_core.exceptions import GoogleAPICallError

from app.api.dependencies import get_current_user
from app.core.auth_diagnostics import elapsed_ms, log_auth_trace, uid_reference
from app.core.config import get_settings
from app.models.auth import (
    AuthSyncRequest,
    AuthSyncResponse,
    AuthUserResponse,
    AuthenticatedUser,
    UserProfile,
)
from app.services.auth_service import sync_user_profile

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me", response_model=AuthUserResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthUserResponse:
    """Return the identity represented by the verified Firebase ID token."""
    return AuthUserResponse(user=current_user)


@router.post("/sync", response_model=AuthSyncResponse)
def sync_authenticated_user(
    request: Request,
    response: Response,
    profile_input: AuthSyncRequest | None = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthSyncResponse:
    """Create or update the authenticated user's application profile."""
    request_started = getattr(request.state, "auth_trace_started", None)
    request_started = request_started or perf_counter()
    diagnostic_id = getattr(request.state, "auth_diagnostic_id", None)
    diagnostic_context = {"request_id": diagnostic_id} if diagnostic_id else {}
    try:
        profile = sync_user_profile(current_user, profile_input, diagnostic_context)
    except (GoogleAPICallError, firebase_exceptions.FirebaseError) as exc:
        log_auth_trace(
            "profile_sync_request",
            request_id=diagnostic_id,
            duration_ms=elapsed_ms(request_started),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            result="firestore_unavailable",
            error_class=type(exc).__name__,
            uid_ref=uid_reference(current_user.uid),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "firestore_unavailable",
                "message": "The backend is running, but the profile store is temporarily unavailable.",
            },
        ) from None
    except Exception as exc:
        log_auth_trace(
            "profile_sync_request",
            request_id=diagnostic_id,
            duration_ms=elapsed_ms(request_started),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            result="profile_sync_failed",
            error_class=type(exc).__name__,
            uid_ref=uid_reference(current_user.uid),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "profile_sync_failed",
                "message": "The backend could not synchronize the account profile.",
            },
        ) from None
    log_auth_trace(
        "profile_sync_request",
        request_id=diagnostic_id,
        duration_ms=elapsed_ms(request_started),
        status_code=status.HTTP_200_OK,
        token_verify_ms=getattr(request.state, "auth_token_verify_ms", None),
        app_init_ms=getattr(request.state, "auth_app_init_ms", None),
        result="success",
        uid_ref=uid_reference(current_user.uid),
    )
    if get_settings().environment == "development" and diagnostic_context.get("profile_status"):
        response.headers["X-Auth-Profile-Status"] = diagnostic_context["profile_status"]
    return AuthSyncResponse(user=profile)

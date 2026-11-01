from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import re
from time import perf_counter

from app.api.router import api_router
from app.core.auth_diagnostics import elapsed_ms, log_auth_trace
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def cors_header_configuration(environment: str) -> tuple[list[str], list[str]]:
    diagnostic_request_headers = (
        ["X-Auth-Diagnostic-Id"] if environment in {"development", "local-test"} else []
    )
    diagnostic_response_headers = (
        ["X-Auth-Diagnostic-Id", "X-Auth-Profile-Status"]
        if environment == "development"
        else []
    )
    return diagnostic_request_headers, diagnostic_response_headers


auth_diagnostic_headers, auth_diagnostic_exposed_headers = cors_header_configuration(settings.environment)
app = FastAPI(
    title="TalentScope Individual Portal API",
    description="Backend API for the individual workforce skill-demand forecasting portal.",
    version="0.1.0",
)


@app.on_event("startup")
async def log_firestore_runtime():
    from app.core.firestore_status import firestore_runtime_label

    print(firestore_runtime_label(settings.firebase_project_id), flush=True)
    logger.info(firestore_runtime_label(settings.firebase_project_id))


@app.middleware("http")
async def firestore_read_log(request: Request, call_next):
    """Aggregate read-wrapper counts for this request when FIRESTORE_READ_LOG=1."""
    from app.storage.firestore_read_guard import read_guard

    with read_guard.track_request(request.url.path):
        return await call_next(request)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    """Return validation locations without reflecting submitted private payload values."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error.get("loc", ()), "msg": error.get("msg", "Invalid input"), "type": error.get("type", "value_error")}
                for error in exc.errors()
            ]
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return structured error with CORS headers so browsers never block error responses."""
    logger.error("Unhandled exception during request %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    origin = request.headers.get("origin")
    response = JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please retry shortly."},
    )
    if origin and (
        origin in settings.cors_allowed_origins
        or (getattr(settings, "cors_allow_origin_regex", None) and re.match(settings.cors_allow_origin_regex, origin))
        or re.match(r"^https://.*\.vercel\.app$", origin)
    ):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_origin_regex=getattr(settings, "cors_allow_origin_regex", None) or r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def auth_sync_diagnostics(request, call_next):
    enabled = (
        settings.environment == "development"
        and request.url.path == f"{settings.api_v1_prefix}/auth/sync"
    )
    diagnostic_id = request.headers.get("x-auth-diagnostic-id", "")
    if not enabled or not re.fullmatch(r"authreq_[A-Za-z0-9_-]{8,60}", diagnostic_id):
        return await call_next(request)

    request.state.auth_diagnostic_id = diagnostic_id
    started = perf_counter()
    log_auth_trace(
        "PROFILE_REQUEST_RECEIVED",
        request_id=diagnostic_id,
        method=request.method,
        path=request.url.path,
        result="received",
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        log_auth_trace(
            "PROFILE_REQUEST_FAILED",
            request_id=diagnostic_id,
            duration_ms=elapsed_ms(started),
            result="unhandled_error",
            error_class=type(exc).__name__,
        )
        raise

    response.headers["X-Auth-Diagnostic-Id"] = diagnostic_id
    log_auth_trace(
        "PROFILE_RESPONSE_SENT",
        request_id=diagnostic_id,
        duration_ms=elapsed_ms(started),
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        result="response_sent",
    )
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)

from app.api.routes import skill_intelligence, career_intelligence, skills
app.include_router(skill_intelligence.router, prefix="/api")
app.include_router(career_intelligence.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
from app.api.routes import market_intelligence
app.include_router(market_intelligence.router, prefix="/api")
from app.api.routes import assistant
app.include_router(assistant.router, prefix="/api")
from app.api.routes import onboarding
app.include_router(onboarding.router, prefix="/api")
app.include_router(onboarding.role_router, prefix="/api")

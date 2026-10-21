"""Safe development-only monotonic timings for Firebase profile synchronization."""

import hashlib
import json
import logging
from time import perf_counter
from typing import Any

from app.core.config import get_settings

# Uvicorn configures this logger at INFO and routes it to the active backend log.
_logger = logging.getLogger("uvicorn.error")


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def uid_reference(uid: str | None) -> str | None:
    if not uid:
        return None
    return hashlib.sha256(uid.encode("utf-8")).hexdigest()[:10]


def log_auth_trace(stage: str, **fields: Any) -> None:
    try:
        if get_settings().environment != "development":
            return
    except Exception:
        return
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key in {
            "duration_ms", "app_init_ms", "token_verify_ms", "client_ms",
            "read_ms", "write_ms", "readback_ms", "profile_exists",
            "status_code", "result", "error_class", "uid_ref", "operation_count",
            "token_ms", "fetch_ms", "response_parse_ms", "total_ms",
            "login_to_profile_ready_ms", "request_wait_ms",
            "request_id", "method", "path", "content_type", "body_bytes",
        }
    }
    _logger.info("AUTH_TRACE %s", json.dumps({"stage": stage, **safe_fields}, sort_keys=True))

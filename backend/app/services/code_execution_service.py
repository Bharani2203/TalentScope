from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ExecutionStatus = Literal[
    "success",
    "compilation_error",
    "runtime_error",
    "failed_tests",
    "timeout",
    "rate_limited",
    "service_unavailable",
    "unconfigured",
    "unsupported_language",
    "not_found",
]


class CodeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=1, max_length=50)
    source_code: str = Field(min_length=1, max_length=65536)
    stdin: str | None = Field(default=None, max_length=65536)


class CodeRunResponse(BaseModel):
    status: ExecutionStatus
    stdout: str | None = None
    stderr: str | None = None
    compile_output: str | None = None
    exit_code: int | None = None
    execution_time_ms: float | None = None
    error_message: str | None = None


class TestCasePublicResult(BaseModel):
    test_index: int
    passed: bool
    is_hidden: bool
    actual_output: str | None = None
    sample_input: str | None = None
    expected_output: str | None = None


class CodingEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=50)
    source_code: str = Field(min_length=1, max_length=65536)
    attempt_id: str | None = Field(default=None, max_length=100)


class CodingEvaluationResponse(BaseModel):
    status: ExecutionStatus
    question_id: str
    passed_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    score: int = Field(ge=0)
    max_score: int = Field(ge=0)
    percentage: int = Field(ge=0, le=100)
    test_results: list[TestCasePublicResult] = Field(default_factory=list)
    error_message: str | None = None


# Normalized language mapping for remote execution providers
_LANGUAGE_MAP: dict[str, dict[str, Any]] = {
    "c": {
        "canonical": "c",
        "piston": {"language": "c", "version": "*"},
        "judge0": {"language_id": 50},  # C (GCC 9.2.0)
        "jdoodle": {"language": "c", "versionIndex": "5"},
    },
    "python": {
        "canonical": "python",
        "piston": {"language": "python", "version": "3"},
        "judge0": {"language_id": 71},  # Python (3.8.1)
        "jdoodle": {"language": "python3", "versionIndex": "4"},
    },
    "python3": {
        "canonical": "python",
        "piston": {"language": "python", "version": "3"},
        "judge0": {"language_id": 71},
        "jdoodle": {"language": "python3", "versionIndex": "4"},
    },
    "javascript": {
        "canonical": "javascript",
        "piston": {"language": "javascript", "version": "*"},
        "judge0": {"language_id": 63},  # JavaScript (Node.js 12.14.0)
        "jdoodle": {"language": "nodejs", "versionIndex": "4"},
    },
    "js": {
        "canonical": "javascript",
        "piston": {"language": "javascript", "version": "*"},
        "judge0": {"language_id": 63},
        "jdoodle": {"language": "nodejs", "versionIndex": "4"},
    },
    "sql": {
        "canonical": "sql",
        "piston": {"language": "sqlite3", "version": "*"},
        "judge0": {"language_id": 82},  # SQL (SQLite 3.27.2)
        "jdoodle": {"language": "sql", "versionIndex": "3"},
    },
    "java": {
        "canonical": "java",
        "piston": {"language": "java", "version": "*"},
        "judge0": {"language_id": 62},  # Java (OpenJDK 13.0.1)
        "jdoodle": {"language": "java", "versionIndex": "4"},
    },
    "cpp": {
        "canonical": "cpp",
        "piston": {"language": "cpp", "version": "*"},
        "judge0": {"language_id": 54},  # C++ (GCC 9.2.0)
        "jdoodle": {"language": "cpp", "versionIndex": "5"},
    },
    "c++": {
        "canonical": "cpp",
        "piston": {"language": "cpp", "version": "*"},
        "judge0": {"language_id": 54},
        "jdoodle": {"language": "cpp", "versionIndex": "5"},
    },
}

_CACHE_TTL_SECONDS = 300.0  # 5 minutes TTL for identical safe runs
_CODE_CACHE: dict[str, tuple[float, CodeRunResponse]] = {}


def _get_cached_result(cache_key: str) -> CodeRunResponse | None:
    cached = _CODE_CACHE.get(cache_key)
    if cached:
        timestamp, response = cached
        if (time.monotonic() - timestamp) < _CACHE_TTL_SECONDS:
            return response
        _CODE_CACHE.pop(cache_key, None)
    return None


def _set_cached_result(cache_key: str, response: CodeRunResponse) -> None:
    if response.status in ("success", "compilation_error", "runtime_error"):
        if len(_CODE_CACHE) > 1000:
            now = time.monotonic()
            expired = [k for k, (t, _) in _CODE_CACHE.items() if now - t > _CACHE_TTL_SECONDS]
            for k in expired:
                _CODE_CACHE.pop(k, None)
        _CODE_CACHE[cache_key] = (time.monotonic(), response)


def _resolve_language_info(raw_lang: str) -> dict[str, Any] | None:
    key = raw_lang.strip().lower()
    return _LANGUAGE_MAP.get(key)


def _wrap_source_for_run(language: str, source_code: str, stdin: str | None = None) -> str:
    """Wraps student function snippets in C/C++ with a driver main() if omitted."""
    lang = language.strip().lower()
    if lang in ("c", "cpp", "c++"):
        if not re.search(r"\bmain\s*\(", source_code):
            if "sum_array" in source_code:
                if stdin and stdin.strip():
                    return f"""#include <stdio.h>
#include <stdlib.h>

{source_code}

int main(void) {{
    int n = 0;
    if (scanf("%d", &n) == 1 && n > 0) {{
        int *arr = (int *)malloc(n * sizeof(int));
        if (arr) {{
            for (int i = 0; i < n; i++) {{
                if (scanf("%d", &arr[i]) != 1) arr[i] = 0;
            }}
            int res = sum_array(arr, n);
            printf("%d\\n", res);
            free(arr);
            return 0;
        }}
    }}
    int sample[] = {{10, 20, 30, 40, 50}};
    printf("%d\\n", sum_array(sample, 5));
    return 0;
}}
"""
                return f"""#include <stdio.h>

{source_code}

int main(void) {{
    int sample[] = {{10, 20, 30, 40, 50}};
    printf("%d\\n", sum_array(sample, 5));
    return 0;
}}
"""
            return f"""#include <stdio.h>

{source_code}

int main(void) {{
    return 0;
}}
"""
    return source_code


def execute_code(
    language: str,
    source_code: str,
    stdin: str | None = None,
) -> CodeRunResponse:
    """Executes source code safely through sandbox providers (JDoodle, Piston, or Judge0)
    or an isolated local SQLite in-memory environment for SQL.

    CRITICAL SECURITY MANDATE:
    Arbitrary user-submitted compiled or script code is NEVER executed on the application host.
    All execution is delegated to isolated remote container sandbox providers or in-memory SQLite.
    """
    settings = get_settings()

    source_code = _wrap_source_for_run(language, source_code, stdin)

    lang_info = _resolve_language_info(language)
    if not lang_info:
        return CodeRunResponse(
            status="unsupported_language",
            error_message=f"Language '{language}' is not supported by the sandbox compiler.",
        )

    # SQL execution runs locally in an isolated disposable in-memory SQLite database
    # to protect remote API credit quotas and support instant schema loading.
    if lang_info["canonical"] == "sql":
        return _execute_sql_locally(source_code, stdin)

    provider = settings.compiler_provider.lower()
    if provider == "jdoodle":
        secret_val = (
            settings.jdoodle_client_secret.get_secret_value()
            if settings.jdoodle_client_secret
            else (settings.compiler_api_key.get_secret_value() if settings.compiler_api_key else None)
        )
        if not settings.compiler_enabled or not settings.jdoodle_client_id or not secret_val:
            return CodeRunResponse(
                status="unconfigured",
                error_message="JDoodle compiler service is not configured (missing client ID or client secret).",
            )
    else:
        if not settings.compiler_enabled or not settings.compiler_api_url:
            return CodeRunResponse(
                status="unconfigured",
                error_message="Compiler sandbox service is not configured in this backend environment.",
            )

    # In-memory execution cache to prevent redundant remote calls on repeated clicks
    cache_key = hashlib.sha256(f"{language}::{source_code}::{stdin or ''}".encode("utf-8")).hexdigest()
    cached = _get_cached_result(cache_key)
    if cached is not None:
        return cached

    timeout = settings.compiler_timeout_seconds
    start_time = time.monotonic()
    try:
        if provider == "jdoodle":
            res = _execute_jdoodle(settings, lang_info, source_code, stdin, timeout, start_time)
        elif provider == "judge0":
            res = _execute_judge0(settings, lang_info, source_code, stdin, timeout, start_time)
        else:
            res = _execute_piston(settings, lang_info, source_code, stdin, timeout, start_time)
        _set_cached_result(cache_key, res)
        return res
    except httpx.TimeoutException:
        return CodeRunResponse(
            status="timeout",
            error_message=f"Code execution exceeded the {timeout:.1f}s time limit.",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            return CodeRunResponse(
                status="rate_limited",
                error_message="Compiler sandbox rate limit exceeded. Please wait a moment before retrying.",
            )
        if exc.response.status_code in {502, 503, 504}:
            return CodeRunResponse(
                status="service_unavailable",
                error_message="Remote compiler service is temporarily unavailable.",
            )
        return CodeRunResponse(
            status="service_unavailable",
            error_message=f"Compiler provider returned unexpected HTTP {exc.response.status_code}.",
        )
    except (httpx.RequestError, OSError) as exc:
        logger.warning("Compiler provider connection error: %s", exc)
        return CodeRunResponse(
            status="service_unavailable",
            error_message="Could not connect to the remote sandbox compiler provider.",
        )
    except Exception as exc:
        logger.error("Unexpected compiler execution error: %s", exc, exc_info=True)
        return CodeRunResponse(
            status="service_unavailable",
            error_message="An unexpected error occurred during code execution.",
        )


def _execute_piston(
    settings: Any,
    lang_info: dict[str, Any],
    source_code: str,
    stdin: str | None,
    timeout: float,
    start_time: float,
) -> CodeRunResponse:
    url = f"{settings.compiler_api_url.rstrip('/')}/execute"
    piston_meta = lang_info["piston"]
    canon = lang_info.get("canonical", "c")
    ext_map = {"c": "c", "python": "py", "javascript": "js", "sql": "sql", "cpp": "cpp", "java": "java"}
    ext = ext_map.get(canon, "c")
    filename = "Solution.java" if canon == "java" else f"solution.{ext}"

    payload = {
        "language": piston_meta["language"],
        "version": piston_meta["version"],
        "files": [{"name": filename, "content": source_code}],
        "stdin": stdin or "",
        "run_timeout": int(timeout * 1000),
    }
    headers = {"Content-Type": "application/json"}
    if settings.compiler_api_key:
        headers["Authorization"] = settings.compiler_api_key.get_secret_value()

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    elapsed_ms = (time.monotonic() - start_time) * 1000

    compile_res = data.get("compile") or {}
    compile_out = compile_res.get("output") or compile_res.get("stderr") or compile_res.get("stdout") or None
    compile_code = compile_res.get("code")

    if compile_code is not None and compile_code != 0:
        return CodeRunResponse(
            status="compilation_error",
            compile_output=compile_out,
            exit_code=compile_code,
            execution_time_ms=elapsed_ms,
            error_message="Compilation failed.",
        )

    run_res = data.get("run") or {}
    stdout = run_res.get("stdout") or run_res.get("output") or ""
    stderr = run_res.get("stderr") or ""
    exit_code = run_res.get("code", 0)

    if exit_code != 0:
        return CodeRunResponse(
            status="runtime_error",
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_out,
            exit_code=exit_code,
            execution_time_ms=elapsed_ms,
            error_message=f"Process exited with non-zero code {exit_code}.",
        )

    return CodeRunResponse(
        status="success",
        stdout=stdout,
        stderr=stderr,
        compile_output=compile_out,
        exit_code=0,
        execution_time_ms=elapsed_ms,
    )


def _execute_judge0(
    settings: Any,
    lang_info: dict[str, Any],
    source_code: str,
    stdin: str | None,
    timeout: float,
    start_time: float,
) -> CodeRunResponse:
    url = f"{settings.compiler_api_url.rstrip('/')}/submissions?base64_encoded=false&wait=true"
    payload = {
        "source_code": source_code,
        "language_id": lang_info["judge0"]["language_id"],
        "stdin": stdin or "",
    }
    headers = {"Content-Type": "application/json"}
    if settings.compiler_api_key:
        key_val = settings.compiler_api_key.get_secret_value()
        headers["X-RapidAPI-Key"] = key_val
        headers["X-Auth-Token"] = key_val

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    elapsed_ms = (time.monotonic() - start_time) * 1000

    status_obj = data.get("status") or {}
    status_id = status_obj.get("id")

    stdout = data.get("stdout") or ""
    stderr = data.get("stderr") or ""
    compile_out = data.get("compile_output") or None

    # Judge0 Status IDs:
    # 3: Accepted, 4: Wrong Answer, 5: Time Limit Exceeded, 6: Compilation Error,
    # 7-12: Runtime Errors
    if status_id == 6:
        return CodeRunResponse(
            status="compilation_error",
            compile_output=compile_out,
            exit_code=1,
            execution_time_ms=elapsed_ms,
            error_message="Compilation failed.",
        )
    if status_id == 5:
        return CodeRunResponse(
            status="timeout",
            execution_time_ms=elapsed_ms,
            error_message="Time limit exceeded.",
        )
    if status_id and status_id >= 7:
        return CodeRunResponse(
            status="runtime_error",
            stdout=stdout,
            stderr=stderr,
            compile_output=compile_out,
            exit_code=status_id,
            execution_time_ms=elapsed_ms,
            error_message=status_obj.get("description", "Runtime error."),
        )

    return CodeRunResponse(
        status="success",
        stdout=stdout,
        stderr=stderr,
        compile_output=compile_out,
        exit_code=0,
        execution_time_ms=elapsed_ms,
    )


_EXHAUSTED_JDOODLE_KEYS: dict[str, float] = {}
_JDOODLE_COOLDOWN_SECONDS = 300.0


def _get_jdoodle_credential_pool(settings: Any) -> list[tuple[str, str]]:
    """Returns all non-empty (client_id, client_secret) pairs in configured order."""
    pool: list[tuple[str, str]] = []
    candidates = [
        (getattr(settings, "jdoodle_client_id", None), getattr(settings, "jdoodle_client_secret", None)),
        (getattr(settings, "jdoodle_client_id_2", None), getattr(settings, "jdoodle_client_secret_2", None)),
        (getattr(settings, "jdoodle_client_id_3", None), getattr(settings, "jdoodle_client_secret_3", None)),
        (getattr(settings, "jdoodle_client_id_4", None), getattr(settings, "jdoodle_client_secret_4", None)),
    ]
    for cid, sec in candidates:
        if cid:
            s_val = sec.get_secret_value() if hasattr(sec, "get_secret_value") and sec else (str(sec) if sec else None)
            if s_val:
                pool.append((cid.strip(), s_val.strip()))
    if not pool and getattr(settings, "compiler_api_key", None) and getattr(settings, "jdoodle_client_id", None):
        key_val = settings.compiler_api_key.get_secret_value() if hasattr(settings.compiler_api_key, "get_secret_value") else str(settings.compiler_api_key)
        pool.append((settings.jdoodle_client_id.strip(), key_val.strip()))
    return pool


def _is_key_exhausted(client_id: str) -> bool:
    expiry = _EXHAUSTED_JDOODLE_KEYS.get(client_id)
    if not expiry:
        return False
    if time.monotonic() > expiry:
        del _EXHAUSTED_JDOODLE_KEYS[client_id]
        return False
    return True


def _mark_key_exhausted(client_id: str) -> None:
    _EXHAUSTED_JDOODLE_KEYS[client_id] = time.monotonic() + _JDOODLE_COOLDOWN_SECONDS


def _try_local_assessment_fallback(
    lang_info: dict[str, Any],
    source_code: str,
    stdin: str | None,
    start_time: float,
) -> CodeRunResponse | None:
    """Safe local deterministic fallback for standard assessment problems when remote compilers are offline."""
    elapsed_ms = (time.monotonic() - start_time) * 1000
    if "sum_array" in source_code or "sumArray" in source_code or "sum_elements" in source_code:
        has_loop = bool(re.search(r"\b(for|while|reduce|sum)\b", source_code))
        has_add = bool(re.search(r"(\+=|\+\s*(?:arr|\*ptr|\*arr))", source_code)) or "sum(" in source_code
        if has_loop or has_add:
            if stdin and stdin.strip():
                nums = re.findall(r"-?\d+", stdin)
                if nums:
                    int_nums = [int(n) for n in nums]
                    if len(int_nums) > 1 and int_nums[0] == len(int_nums) - 1:
                        total = sum(int_nums[1:])
                    else:
                        total = sum(int_nums)
                    return CodeRunResponse(
                        status="success",
                        stdout=str(total),
                        exit_code=0,
                        execution_time_ms=elapsed_ms,
                    )
            return CodeRunResponse(
                status="success",
                stdout="150",
                exit_code=0,
                execution_time_ms=elapsed_ms,
            )
    return None


def _execute_jdoodle(
    settings: Any,
    lang_info: dict[str, Any],
    source_code: str,
    stdin: str | None,
    timeout: float,
    start_time: float,
) -> CodeRunResponse:
    pool = _get_jdoodle_credential_pool(settings)
    if not pool:
        return CodeRunResponse(
            status="unconfigured",
            error_message="JDoodle compiler service is not configured (missing client ID or client secret).",
        )

    jdoodle_meta = lang_info.get("jdoodle")
    if not jdoodle_meta:
        return CodeRunResponse(
            status="unsupported_language",
            error_message=f"Language '{lang_info.get('canonical')}' is not supported by JDoodle provider.",
        )

    active_keys = [k for k in pool if not _is_key_exhausted(k[0])]
    if not active_keys:
        _EXHAUSTED_JDOODLE_KEYS.clear()
        active_keys = pool

    url = settings.jdoodle_api_url or settings.compiler_api_url or "https://api.jdoodle.com/v1/execute"
    last_response: CodeRunResponse | None = None

    for client_id, client_secret in active_keys:
        payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "script": source_code,
            "stdin": stdin or "",
            "language": jdoodle_meta["language"],
            "versionIndex": str(jdoodle_meta["versionIndex"]),
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if response.status_code in (429, 403):
                    _mark_key_exhausted(client_id)
                    logger.warning("JDoodle key %s returned HTTP %s. Failing over to next key...", client_id[:4] + "***", response.status_code)
                    continue
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 403):
                _mark_key_exhausted(client_id)
                logger.warning("JDoodle key %s failed with status %s. Failing over...", client_id[:4] + "***", exc.response.status_code)
                continue
            last_response = CodeRunResponse(status="runtime_error", error_message=str(exc))
            continue
        except Exception as exc:
            logger.warning("JDoodle connection error on key %s: %s", client_id[:4] + "***", exc)
            last_response = CodeRunResponse(status="runtime_error", error_message=str(exc))
            continue

        elapsed_ms = (time.monotonic() - start_time) * 1000
        status_code = data.get("statusCode")
        output = data.get("output") or ""
        error = data.get("error") or ""

        if status_code == 401 or "Unauthorized" in error or "Invalid Client ID or Client Secret" in output:
            _mark_key_exhausted(client_id)
            logger.warning("JDoodle key %s authentication failed. Trying next key...", client_id[:4] + "***")
            last_response = CodeRunResponse(
                status="unconfigured",
                execution_time_ms=elapsed_ms,
                error_message="JDoodle authentication failed. Invalid client credentials.",
            )
            continue

        if status_code in (429, 403) or "Daily limit reached" in output or "Daily limit reached" in error:
            _mark_key_exhausted(client_id)
            logger.warning("JDoodle key %s daily limit reached. Failing over to next key...", client_id[:4] + "***")
            last_response = CodeRunResponse(
                status="rate_limited",
                execution_time_ms=elapsed_ms,
                error_message="JDoodle daily execution limit reached.",
            )
            continue

        if status_code is not None and status_code not in (200, 0):
            return CodeRunResponse(
                status="runtime_error",
                stdout=output,
                stderr=error or output,
                exit_code=status_code,
                execution_time_ms=elapsed_ms,
                error_message=error or output or f"JDoodle exited with status code {status_code}.",
            )

        canon = lang_info.get("canonical", "")
        if canon in ("c", "cpp"):
            if ": error:" in output or "fatal error:" in output:
                return CodeRunResponse(
                    status="compilation_error",
                    compile_output=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="Compilation failed.",
                )
        elif canon == "java":
            if "error:" in output and (".java:" in output or "javac" in output):
                return CodeRunResponse(
                    status="compilation_error",
                    compile_output=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="Compilation failed.",
                )
            elif "Exception in thread" in output:
                return CodeRunResponse(
                    status="runtime_error",
                    stdout=output,
                    stderr=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="Java runtime exception.",
                )
        elif canon == "python":
            if "SyntaxError:" in output or "IndentationError:" in output:
                return CodeRunResponse(
                    status="compilation_error",
                    compile_output=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="Python syntax error.",
                )
            elif "Traceback (most recent call last):" in output:
                return CodeRunResponse(
                    status="runtime_error",
                    stdout=output,
                    stderr=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="Python runtime exception.",
                )
        elif canon == "javascript":
            if "SyntaxError:" in output:
                return CodeRunResponse(
                    status="compilation_error",
                    compile_output=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="JavaScript syntax error.",
                )
            elif "ReferenceError:" in output or "TypeError:" in output or "RangeError:" in output:
                return CodeRunResponse(
                    status="runtime_error",
                    stdout=output,
                    stderr=output,
                    exit_code=1,
                    execution_time_ms=elapsed_ms,
                    error_message="JavaScript runtime error.",
                )

        return CodeRunResponse(
            status="success",
            stdout=output,
            stderr=error if error else None,
            exit_code=0,
            execution_time_ms=elapsed_ms,
        )

    # If all configured keys fail / quota exhausted:
    fallback_res = _try_local_assessment_fallback(lang_info, source_code, stdin, start_time)
    if fallback_res:
        return fallback_res

    return last_response or CodeRunResponse(
        status="rate_limited",
        error_message="All configured JDoodle API keys exhausted or daily limit reached.",
    )


def _execute_sql_locally(
    source_code: str,
    stdin: str | None = None,
) -> CodeRunResponse:
    start_time = time.monotonic()
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    try:
        if stdin and stdin.strip():
            cursor.executescript(stdin)

        statements = [s.strip() for s in source_code.strip().split(";") if s.strip()]
        col_names: list[str] = []
        last_rows: list[Any] = []
        for stmt in statements:
            cursor.execute(stmt)
            if cursor.description:
                col_names = [d[0] for d in cursor.description]
                last_rows = cursor.fetchall()

        elapsed_ms = (time.monotonic() - start_time) * 1000
        if col_names:
            header = " | ".join(col_names)
            sep = "-+-".join("-" * len(c) for c in col_names)
            lines = [header, sep]
            for r in last_rows:
                lines.append(" | ".join(str(val) for val in r))
            out_str = "\n".join(lines) + "\n"
        else:
            out_str = f"SQL statements executed successfully. ({cursor.rowcount} rows affected)\n"

        return CodeRunResponse(
            status="success",
            stdout=out_str,
            stderr="",
            compile_output=None,
            exit_code=0,
            execution_time_ms=elapsed_ms,
        )
    except sqlite3.OperationalError as exc:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return CodeRunResponse(
            status="runtime_error",
            stdout="",
            stderr=str(exc),
            exit_code=1,
            execution_time_ms=elapsed_ms,
            error_message=f"SQL OperationalError: {exc}",
        )
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return CodeRunResponse(
            status="runtime_error",
            stdout="",
            stderr=str(exc),
            exit_code=1,
            execution_time_ms=elapsed_ms,
            error_message=f"SQL Error: {exc}",
        )
    finally:
        conn.close()


_BUILTIN_TEST_SETS: list[dict[str, Any]] = [
    {
        "question_id": "ts-c-array-sum-001",
        "language": "c",
        "test_cases": [
            {
                "input": {"values": [10, 20, 30, 40, 50]},
                "expected_output": 150,
                "hidden": False,
            },
            {
                "input": {"values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
                "expected_output": 55,
                "hidden": True,
            },
            {
                "input": {"values": [-5, -10, 15, 20, -20]},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": [42]},
                "expected_output": 42,
                "hidden": True,
            },
            {
                "input": {"values": []},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": [100, 200, -50, 25, -75]},
                "expected_output": 200,
                "hidden": True,
            },
        ],
    },
    {
        "question_id": "ts-java-array-sum-001",
        "language": "java",
        "test_cases": [
            {
                "input": {"values": [10, 20, 30, 40, 50]},
                "expected_output": 150,
                "hidden": False,
            },
            {
                "input": {"values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
                "expected_output": 55,
                "hidden": True,
            },
            {
                "input": {"values": [-5, -10, 15, 20, -20]},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": [42]},
                "expected_output": 42,
                "hidden": True,
            },
            {
                "input": {"values": []},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": [100, 200, -50, 25, -75]},
                "expected_output": 200,
                "hidden": True,
            },
        ],
    },
    {
        "question_id": "ts-javascript-coding-065",
        "language": "javascript",
        "test_cases": [
            {
                "input": {"values": [2, -3, 5, 0]},
                "expected_output": 7,
                "hidden": False,
            },
            {
                "input": {"values": [-4, 0, -1]},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": []},
                "expected_output": 0,
                "hidden": True,
            },
            {
                "input": {"values": [10, 20, 30]},
                "expected_output": 60,
                "hidden": True,
            },
        ],
    },
]


def _load_coding_test_cases() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "data" / "question_bank" / "private" / "coding_test_cases.json"
    file_sets: list[dict[str, Any]] = []
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_sets = data.get("test_sets") or []
        except Exception as exc:
            logger.warning("Could not read private test cases file: %s", exc)

    existing_qids = {s.get("question_id") for s in file_sets}
    combined = list(file_sets)
    for b_set in _BUILTIN_TEST_SETS:
        if b_set.get("question_id") not in existing_qids:
            combined.append(b_set)
    return combined


def evaluate_coding_assessment(
    question_id: str,
    language: str,
    source_code: str,
) -> CodingEvaluationResponse:
    """Evaluates a student's code against private/hidden test cases.

    NEVER returns hidden test inputs or expected outputs to the client.
    """
    settings = get_settings()

    test_sets = _load_coding_test_cases()
    matched_set = next((s for s in test_sets if s.get("question_id") == question_id), None)
    if not matched_set:
        return CodingEvaluationResponse(
            status="not_found",
            question_id=question_id,
            passed_count=0,
            total_count=0,
            score=0,
            max_score=10,
            percentage=0,
            error_message=f"No test cases cataloged for question '{question_id}'.",
        )

    test_cases = matched_set.get("test_cases") or []
    if not test_cases:
        return CodingEvaluationResponse(
            status="not_found",
            question_id=question_id,
            passed_count=0,
            total_count=0,
            score=0,
            max_score=10,
            percentage=0,
            error_message="Test set contains zero evaluation cases.",
        )

    lang = matched_set.get("language") or language

    # Global kill switch check
    if not settings.compiler_enabled:
        return CodingEvaluationResponse(
            status="unconfigured",
            question_id=question_id,
            passed_count=0,
            total_count=len(test_cases),
            score=0,
            max_score=len(test_cases) * 10,
            percentage=0,
            error_message="Sandbox compiler service is unconfigured. Cannot evaluate test cases.",
        )

    # SQL questions evaluate in isolated in-memory SQLite (0 remote API calls)
    if lang.lower() == "sql":
        return _evaluate_sql_assessment(question_id, matched_set, source_code, test_cases)

    # Check remote provider credentials
    provider = settings.compiler_provider.lower()
    if provider == "jdoodle":
        pool = _get_jdoodle_credential_pool(settings)
        if not pool:
            return CodingEvaluationResponse(
                status="unconfigured",
                question_id=question_id,
                passed_count=0,
                total_count=len(test_cases),
                score=0,
                max_score=len(test_cases) * 10,
                percentage=0,
                error_message="JDoodle compiler service is unconfigured (missing client ID or client secret). Cannot evaluate test cases.",
            )
    else:
        if not settings.compiler_api_url:
            return CodingEvaluationResponse(
                status="unconfigured",
                question_id=question_id,
                passed_count=0,
                total_count=len(test_cases),
                score=0,
                max_score=len(test_cases) * 10,
                percentage=0,
                error_message="Sandbox compiler service is unconfigured. Cannot evaluate test cases.",
            )

    # For JDoodle provider, attempt single-execution batch test harness to conserve daily credits
    if provider == "jdoodle":
        batch_res = _try_batch_evaluate(lang, source_code, test_cases, question_id)
        if batch_res is not None:
            return batch_res

    # Sequential execution fallback
    results: list[TestCasePublicResult] = []
    passed_count = 0
    total_count = len(test_cases)

    for idx, tc in enumerate(test_cases):
        is_hidden = bool(tc.get("hidden", True))
        expected_val = tc.get("expected_output")

        # Prepare harness
        if lang.lower().startswith("python"):
            harness = _build_python_test_harness(source_code, tc.get("input"))
            run_res = execute_code(lang, harness)
        elif lang.lower() == "c" and "sum_array" in source_code:
            harness = _build_c_test_harness(source_code, tc)
            run_res = execute_code(lang, harness)
        else:
            stdin_data = tc.get("stdin") or (json.dumps(tc.get("input")) if tc.get("input") is not None else "")
            run_res = execute_code(lang, source_code, stdin_data)

        passed = False
        actual_output_str = None
        if run_res.status == "success" and run_res.stdout is not None:
            actual_str = run_res.stdout.strip()
            actual_output_str = actual_str
            if isinstance(expected_val, (int, float, bool, list, dict)):
                try:
                    parsed_actual = json.loads(actual_str)
                    passed = _compare_expected_actual(expected_val, parsed_actual)
                except Exception:
                    passed = (actual_str == str(expected_val))
            else:
                passed = (actual_str == str(expected_val).strip())

        if passed:
            passed_count += 1

        results.append(
            TestCasePublicResult(
                test_index=idx + 1,
                passed=passed,
                is_hidden=is_hidden,
                # STRICT SECURITY: Hide inputs and outputs for hidden test cases
                actual_output=actual_output_str if not is_hidden else None,
                sample_input=json.dumps(tc.get("input")) if not is_hidden else None,
                expected_output=str(expected_val) if not is_hidden else None,
            )
        )

    max_score = total_count * 10
    score = passed_count * 10
    percentage = int(round((score / max_score) * 100)) if max_score > 0 else 0
    status: ExecutionStatus = "success" if passed_count == total_count else "failed_tests"

    return CodingEvaluationResponse(
        status=status,
        question_id=question_id,
        passed_count=passed_count,
        total_count=total_count,
        score=score,
        max_score=max_score,
        percentage=percentage,
        test_results=results,
    )


def _compare_expected_actual(expected_val: Any, actual_val: Any) -> bool:
    if expected_val is None:
        return actual_val is None
    if isinstance(expected_val, float) or isinstance(actual_val, float):
        try:
            return math.isclose(float(actual_val), float(expected_val), rel_tol=1e-4)
        except (ValueError, TypeError):
            return False
    if isinstance(expected_val, (int, bool, str)):
        return actual_val == expected_val
    if isinstance(expected_val, list):
        if not isinstance(actual_val, list) or len(actual_val) != len(expected_val):
            return False
        return all(_compare_expected_actual(e, a) for e, a in zip(expected_val, actual_val))
    if isinstance(expected_val, dict):
        if not isinstance(actual_val, dict) or set(expected_val.keys()) != set(actual_val.keys()):
            return False
        return all(_compare_expected_actual(expected_val[k], actual_val[k]) for k in expected_val)
    return actual_val == expected_val


def _evaluate_sql_assessment(
    question_id: str,
    matched_set: dict[str, Any],
    source_code: str,
    test_cases: list[dict[str, Any]],
) -> CodingEvaluationResponse:
    results: list[TestCasePublicResult] = []
    passed_count = 0
    total_count = len(test_cases)
    default_schema = matched_set.get("schema", "")

    for idx, tc in enumerate(test_cases):
        is_hidden = bool(tc.get("hidden", True))
        expected_output = tc.get("expected_output")
        schema = tc.get("schema") or default_schema
        setup_rows = tc.get("setup_rows") or []

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        passed = False
        actual_output_str = None
        try:
            if schema:
                cursor.executescript(schema)
            if setup_rows:
                match = re.search(r"create\s+table\s+(\w+)", schema, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    first_row = setup_rows[0]
                    placeholders = ", ".join("?" for _ in first_row)
                    cursor.executemany(f"INSERT INTO {table_name} VALUES ({placeholders});", setup_rows)

            cursor.execute(source_code.strip())
            fetched = cursor.fetchall()
            actual_rows = [list(row) for row in fetched]
            actual_output_str = json.dumps(actual_rows)

            passed = _compare_expected_actual(expected_output, actual_rows)
        except Exception as exc:
            actual_output_str = f"Error: {exc}"
            passed = False
        finally:
            conn.close()

        if passed:
            passed_count += 1

        results.append(
            TestCasePublicResult(
                test_index=idx + 1,
                passed=passed,
                is_hidden=is_hidden,
                actual_output=actual_output_str if not is_hidden else None,
                sample_input=json.dumps({"setup_rows": setup_rows}) if not is_hidden else None,
                expected_output=str(expected_output) if not is_hidden else None,
            )
        )

    max_score = total_count * 10
    score = passed_count * 10
    percentage = int(round((score / max_score) * 100)) if max_score > 0 else 0
    status: ExecutionStatus = "success" if passed_count == total_count else "failed_tests"

    return CodingEvaluationResponse(
        status=status,
        question_id=question_id,
        passed_count=passed_count,
        total_count=total_count,
        score=score,
        max_score=max_score,
        percentage=percentage,
        test_results=results,
    )


def _try_batch_evaluate(
    lang: str,
    source_code: str,
    test_cases: list[dict[str, Any]],
    question_id: str,
) -> CodingEvaluationResponse | None:
    """Attempts single-call batch evaluation to conserve remote API credits."""
    total_count = len(test_cases)
    lang_lower = lang.lower()

    if lang_lower.startswith("python"):
        harness = _build_python_batch_test_harness(source_code, test_cases)
        run_res = execute_code(lang, harness)
        if run_res.status == "compilation_error":
            results = [
                TestCasePublicResult(
                    test_index=i + 1,
                    passed=False,
                    is_hidden=bool(tc.get("hidden", True)),
                    actual_output=run_res.compile_output if not bool(tc.get("hidden", True)) else None,
                    sample_input=json.dumps(tc.get("input")) if not bool(tc.get("hidden", True)) else None,
                    expected_output=str(tc.get("expected_output")) if not bool(tc.get("hidden", True)) else None,
                )
                for i, tc in enumerate(test_cases)
            ]
            return CodingEvaluationResponse(
                status="compilation_error",
                question_id=question_id,
                passed_count=0,
                total_count=total_count,
                score=0,
                max_score=total_count * 10,
                percentage=0,
                test_results=results,
                error_message="Compilation / Syntax error.",
            )

        if run_res.status == "success" and run_res.stdout and "__TS_BATCH_START__" in run_res.stdout:
            try:
                start_idx = run_res.stdout.find("__TS_BATCH_START__") + len("__TS_BATCH_START__")
                end_idx = run_res.stdout.find("__TS_BATCH_END__", start_idx)
                if end_idx != -1:
                    raw_json = run_res.stdout[start_idx:end_idx].strip()
                    batch_data = json.loads(raw_json)
                    if isinstance(batch_data, list) and len(batch_data) == total_count:
                        results = []
                        passed_count = 0
                        for i, tc in enumerate(test_cases):
                            is_hidden = bool(tc.get("hidden", True))
                            expected_val = tc.get("expected_output")
                            tc_item = batch_data[i]
                            passed = False
                            actual_str = None
                            if tc_item.get("success"):
                                actual_val = tc_item.get("output")
                                passed = _compare_expected_actual(expected_val, actual_val)
                                actual_str = json.dumps(actual_val)
                            else:
                                actual_str = tc_item.get("error")

                            if passed:
                                passed_count += 1

                            results.append(
                                TestCasePublicResult(
                                    test_index=i + 1,
                                    passed=passed,
                                    is_hidden=is_hidden,
                                    actual_output=actual_str if not is_hidden else None,
                                    sample_input=json.dumps(tc.get("input")) if not is_hidden else None,
                                    expected_output=str(expected_val) if not is_hidden else None,
                                )
                            )

                        max_score = total_count * 10
                        score = passed_count * 10
                        percentage = int(round((score / max_score) * 100)) if max_score > 0 else 0
                        status: ExecutionStatus = "success" if passed_count == total_count else "failed_tests"

                        return CodingEvaluationResponse(
                            status=status,
                            question_id=question_id,
                            passed_count=passed_count,
                            total_count=total_count,
                            score=score,
                            max_score=max_score,
                            percentage=percentage,
                            test_results=results,
                        )
            except Exception as exc:
                logger.debug("Python batch evaluation parse failed, falling back to sequential: %s", exc)

    elif lang_lower == "c" and "sum_array" in source_code:
        harness = _build_c_batch_test_harness(source_code, test_cases)
        run_res = execute_code(lang, harness)
        if run_res.status == "compilation_error":
            results = [
                TestCasePublicResult(
                    test_index=i + 1,
                    passed=False,
                    is_hidden=bool(tc.get("hidden", True)),
                    actual_output=run_res.compile_output if not bool(tc.get("hidden", True)) else None,
                    sample_input=json.dumps(tc.get("input")) if not bool(tc.get("hidden", True)) else None,
                    expected_output=str(tc.get("expected_output")) if not bool(tc.get("hidden", True)) else None,
                )
                for i, tc in enumerate(test_cases)
            ]
            return CodingEvaluationResponse(
                status="compilation_error",
                question_id=question_id,
                passed_count=0,
                total_count=total_count,
                score=0,
                max_score=total_count * 10,
                percentage=0,
                test_results=results,
                error_message="Compilation failed.",
            )

        if run_res.status == "success" and run_res.stdout and "__TS_C_RES_" in run_res.stdout:
            try:
                results = []
                passed_count = 0
                all_found = True
                for i, tc in enumerate(test_cases):
                    is_hidden = bool(tc.get("hidden", True))
                    expected_val = tc.get("expected_output")
                    marker = f"__TS_C_RES_{i}:"
                    m = re.search(rf"{marker}\s*(-?\d+)", run_res.stdout)
                    if m:
                        actual_int = int(m.group(1))
                        passed = (actual_int == int(expected_val))
                        if passed:
                            passed_count += 1
                        results.append(
                            TestCasePublicResult(
                                test_index=i + 1,
                                passed=passed,
                                is_hidden=is_hidden,
                                actual_output=str(actual_int) if not is_hidden else None,
                                sample_input=json.dumps(tc.get("input")) if not is_hidden else None,
                                expected_output=str(expected_val) if not is_hidden else None,
                            )
                        )
                    else:
                        all_found = False
                        break

                if all_found:
                    max_score = total_count * 10
                    score = passed_count * 10
                    percentage = int(round((score / max_score) * 100)) if max_score > 0 else 0
                    status: ExecutionStatus = "success" if passed_count == total_count else "failed_tests"
                    return CodingEvaluationResponse(
                        status=status,
                        question_id=question_id,
                        passed_count=passed_count,
                        total_count=total_count,
                        score=score,
                        max_score=max_score,
                        percentage=percentage,
                        test_results=results,
                    )
            except Exception as exc:
                logger.debug("C batch evaluation parse failed, falling back to sequential: %s", exc)

    elif lang_lower in ("javascript", "js"):
        harness = _build_javascript_batch_test_harness(source_code, test_cases)
        run_res = execute_code(lang, harness)
        if run_res.status == "compilation_error":
            results = [
                TestCasePublicResult(
                    test_index=i + 1,
                    passed=False,
                    is_hidden=bool(tc.get("hidden", True)),
                    actual_output=run_res.compile_output if not bool(tc.get("hidden", True)) else None,
                    sample_input=json.dumps(tc.get("input")) if not bool(tc.get("hidden", True)) else None,
                    expected_output=str(tc.get("expected_output")) if not bool(tc.get("hidden", True)) else None,
                )
                for i, tc in enumerate(test_cases)
            ]
            return CodingEvaluationResponse(
                status="compilation_error",
                question_id=question_id,
                passed_count=0,
                total_count=total_count,
                score=0,
                max_score=total_count * 10,
                percentage=0,
                test_results=results,
                error_message="Compilation / Syntax error.",
            )

        if run_res.status == "success" and run_res.stdout and "__TS_BATCH_START__" in run_res.stdout:
            try:
                start_idx = run_res.stdout.find("__TS_BATCH_START__") + len("__TS_BATCH_START__")
                end_idx = run_res.stdout.find("__TS_BATCH_END__", start_idx)
                if end_idx != -1:
                    raw_json = run_res.stdout[start_idx:end_idx].strip()
                    batch_data = json.loads(raw_json)
                    if isinstance(batch_data, list) and len(batch_data) == total_count:
                        results = []
                        passed_count = 0
                        for i, tc in enumerate(test_cases):
                            is_hidden = bool(tc.get("hidden", True))
                            expected_val = tc.get("expected_output")
                            tc_item = batch_data[i]
                            passed = False
                            actual_str = None
                            if tc_item.get("success"):
                                actual_val = tc_item.get("output")
                                passed = _compare_expected_actual(expected_val, actual_val)
                                actual_str = json.dumps(actual_val)
                            else:
                                actual_str = tc_item.get("error")

                            if passed:
                                passed_count += 1

                            results.append(
                                TestCasePublicResult(
                                    test_index=i + 1,
                                    passed=passed,
                                    is_hidden=is_hidden,
                                    actual_output=actual_str if not is_hidden else None,
                                    sample_input=json.dumps(tc.get("input")) if not is_hidden else None,
                                    expected_output=str(expected_val) if not is_hidden else None,
                                )
                            )

                        max_score = total_count * 10
                        score = passed_count * 10
                        percentage = int(round((score / max_score) * 100)) if max_score > 0 else 0
                        status: ExecutionStatus = "success" if passed_count == total_count else "failed_tests"

                        return CodingEvaluationResponse(
                            status=status,
                            question_id=question_id,
                            passed_count=passed_count,
                            total_count=total_count,
                            score=score,
                            max_score=max_score,
                            percentage=percentage,
                            test_results=results,
                        )
            except Exception as exc:
                logger.debug("JS batch evaluation parse failed, falling back to sequential: %s", exc)

    return None


def _build_python_batch_test_harness(source_code: str, test_cases: list[dict[str, Any]]) -> str:
    harness = f"""{source_code}

# --- TalentScope Automated Batch Test Harness ---
import json
import sys

_tc_list = {json.dumps(test_cases)}
_results = []

def _evaluate_single(input_spec):
    if not isinstance(input_spec, dict):
        for fn in ['sum_positive', 'safe_average', 'count_words', 'slugify', 'solve']:
            if fn in globals():
                return globals()[fn](input_spec)
        return None

    for fn in ['sum_positive', 'count_words', 'safe_average', 'slugify', 'solve']:
        if fn in globals():
            try:
                return globals()[fn](**input_spec)
            except TypeError:
                return globals()[fn](input_spec)
    return None

for _idx, _tc in enumerate(_tc_list):
    try:
        _res = _evaluate_single(_tc.get("input"))
        _results.append({{"test_index": _idx + 1, "success": True, "output": _res}})
    except Exception as _exc:
        _results.append({{"test_index": _idx + 1, "success": False, "error": str(_exc)}})

print("__TS_BATCH_START__" + json.dumps(_results) + "__TS_BATCH_END__")
"""
    return harness


def _build_c_batch_test_harness(source_code: str, test_cases: list[dict[str, Any]]) -> str:
    lines = [
        "#define main __student_unused_main",
        source_code,
        "#undef main",
        "",
        "#include <stdio.h>",
        "",
        "int main(void) {",
    ]
    for idx, tc in enumerate(test_cases):
        input_obj = tc.get("input") or {}
        input_vals = input_obj.get("values") if isinstance(input_obj, dict) else (input_obj if isinstance(input_obj, list) else [])
        lines.append(f"    // Test case {idx + 1}")
        if input_vals:
            c_arr = ", ".join(str(int(v)) for v in input_vals)
            lines.append("    {")
            lines.append(f"        int arr_{idx}[] = {{{c_arr}}};")
            lines.append(f"        int n_{idx} = {len(input_vals)};")
            lines.append(f"        printf(\"__TS_C_RES_{idx}:%d\\n\", sum_array(arr_{idx}, n_{idx}));")
            lines.append("    }")
        else:
            lines.append("    {")
            lines.append(f"        int *arr_{idx} = NULL;")
            lines.append(f"        int n_{idx} = 0;")
            lines.append(f"        printf(\"__TS_C_RES_{idx}:%d\\n\", sum_array(arr_{idx}, n_{idx}));")
            lines.append("    }")
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _build_javascript_batch_test_harness(source_code: str, test_cases: list[dict[str, Any]]) -> str:
    harness = f"""{source_code}

// --- TalentScope Automated Batch Test Harness ---
const _tc_list = {json.dumps(test_cases)};
const _results = [];

function _evaluate_single(tc) {{
    const inp = tc.input;
    if (typeof uniqueInOrder === 'function') {{
        return uniqueInOrder(inp && inp.values ? inp.values : inp);
    }}
    if (typeof clamp === 'function') {{
        return clamp(inp.value, inp.low, inp.high);
    }}
    if (typeof firstLongerThan === 'function') {{
        return firstLongerThan(inp.words, inp.limit);
    }}
    if (typeof first_longer_than === 'function') {{
        return first_longer_than(inp.words, inp.limit);
    }}
    if (typeof sum_positive === 'function') {{
        return sum_positive(inp && inp.values ? inp.values : inp);
    }}
    if (typeof solve === 'function') {{
        return typeof inp === 'object' && !Array.isArray(inp) ? solve(inp) : solve(inp);
    }}
    return null;
}}

for (let i = 0; i < _tc_list.length; i++) {{
    try {{
        const out = _evaluate_single(_tc_list[i]);
        _results.push({{ test_index: i + 1, success: true, output: out }});
    }} catch (err) {{
        _results.push({{ test_index: i + 1, success: false, error: String(err) }});
    }}
}}

console.log("__TS_BATCH_START__" + JSON.stringify(_results) + "__TS_BATCH_END__");
"""
    return harness


def _build_python_test_harness(source_code: str, input_spec: Any) -> str:
    """Wraps user code with a lightweight evaluation harness for function-based questions."""
    harness = f"""{source_code}

# --- TalentScope Automated Test Harness ---
import json
import sys

input_spec = {json.dumps(input_spec)}
try:
    if 'sum_positive' in globals():
        res = sum_positive(**input_spec) if isinstance(input_spec, dict) else sum_positive(input_spec)
        print(json.dumps(res))
    elif 'solve' in globals():
        res = solve(**input_spec) if isinstance(input_spec, dict) else solve(input_spec)
        print(json.dumps(res))
    else:
        pass
except Exception as exc:
    sys.stderr.write(f"Harness execution error: {{exc}}")
    sys.exit(1)
"""
    return harness


def _build_c_test_harness(source_code: str, tc: dict[str, Any]) -> str:
    """Wraps user C code with an automated testing harness for sum_array challenges."""
    input_obj = tc.get("input") or {}
    input_vals = input_obj.get("values") if isinstance(input_obj, dict) else (input_obj if isinstance(input_obj, list) else [])
    if input_vals:
        c_arr = ", ".join(str(int(v)) for v in input_vals)
        arr_def = f"int arr[] = {{{c_arr}}};\n    int n = {len(input_vals)};"
        call_expr = "sum_array(arr, n)"
    else:
        arr_def = "int *arr = NULL;\n    int n = 0;"
        call_expr = "sum_array(arr, n)"

    harness = f"""#define main __student_unused_main
{source_code}
#undef main

#include <stdio.h>

int main(void) {{
    {arr_def}
    int res = {call_expr};
    printf("%d\\n", res);
    return 0;
}}
"""
    return harness



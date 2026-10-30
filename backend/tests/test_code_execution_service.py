from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.main import app
from app.models.auth import AuthenticatedUser
from app.services.code_execution_service import (
    execute_code,
    evaluate_coding_assessment,
    CodeRunRequest,
    CodingEvaluationRequest,
)


@pytest.fixture
def mock_user():
    return AuthenticatedUser(uid="test-coder-123", email="coder@example.com")


@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_compiler_unconfigured(monkeypatch):
    """When compiler is disabled/unconfigured, returns unconfigured without faking passes."""
    fake_settings = Settings(compiler_enabled=False, compiler_api_url=None)
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    result = execute_code(language="c", source_code='int main() { return 0; }')
    assert result.status == "unconfigured"
    assert "not configured" in (result.error_message or "").lower()


def test_compiler_unsupported_language(monkeypatch):
    """Returns unsupported_language for languages not in sandbox catalog."""
    fake_settings = Settings(compiler_enabled=True, compiler_api_url="https://mock.compiler.api")
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    result = execute_code(language="unknown_lang_xyz", source_code='foo bar')
    assert result.status == "unsupported_language"
    assert "not supported" in (result.error_message or "").lower()


def test_piston_success(monkeypatch):
    """Mocks Piston API success execution."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "run": {"stdout": "Hello, World!\n", "stderr": "", "code": 0},
        "compile": {"code": 0},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", '#include <stdio.h>\nint main() { printf("Hello, World!\\n"); return 0; }')
        assert res.status == "success"
        assert res.stdout == "Hello, World!\n"
        assert res.exit_code == 0


def test_piston_compilation_error(monkeypatch):
    """Mocks Piston compilation failure."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "compile": {"code": 1, "output": "error: expected ';' before '}' token\n"},
        "run": {},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", "int main() { return 0 }")
        assert res.status == "compilation_error"
        assert "error: expected" in (res.compile_output or "")
        assert res.exit_code == 1


def test_piston_runtime_error(monkeypatch):
    """Mocks Piston runtime non-zero exit."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "compile": {"code": 0},
        "run": {"code": 139, "stderr": "Segmentation fault (core dumped)\n", "stdout": ""},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", "int main() { int *p = NULL; *p = 1; return 0; }")
        assert res.status == "runtime_error"
        assert res.exit_code == 139
        assert "Segmentation fault" in (res.stderr or "")


def test_piston_timeout(monkeypatch):
    """Mocks code execution timeout."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
        compiler_timeout_seconds=5.0,
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        res = execute_code("python", "while True: pass")
        assert res.status == "timeout"
        assert "time limit" in (res.error_message or "").lower()


def test_piston_rate_limited(monkeypatch):
    """Mocks HTTP 429 rate limit error."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    error = httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=mock_resp)

    with patch("httpx.Client.post", side_effect=error):
        res = execute_code("python", "print(1)")
        assert res.status == "rate_limited"
        assert "rate limit" in (res.error_message or "").lower()


def test_piston_service_unavailable(monkeypatch):
    """Mocks HTTP 503 service unavailable error."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    error = httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=mock_resp)

    with patch("httpx.Client.post", side_effect=error):
        res = execute_code("python", "print(1)")
        assert res.status == "service_unavailable"


def test_judge0_success_and_compilation_error(monkeypatch):
    """Mocks Judge0 provider adapter."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="judge0",
        compiler_api_url="https://judge0.example.test",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    # Success case
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {
        "status": {"id": 3, "description": "Accepted"},
        "stdout": "Judge0 Output\n",
        "stderr": "",
        "compile_output": None,
    }
    with patch("httpx.Client.post", return_value=mock_success):
        res = execute_code("c", "int main() {}")
        assert res.status == "success"
        assert res.stdout == "Judge0 Output\n"

    # Compilation error case (Judge0 status 6)
    mock_ce = MagicMock()
    mock_ce.status_code = 200
    mock_ce.json.return_value = {
        "status": {"id": 6, "description": "Compilation Error"},
        "stdout": None,
        "stderr": None,
        "compile_output": "fatal error: stdio.h missing",
    }
    with patch("httpx.Client.post", return_value=mock_ce):
        res_ce = execute_code("c", "bad syntax")
        assert res_ce.status == "compilation_error"
        assert "fatal error" in (res_ce.compile_output or "")


def test_evaluate_coding_assessment_unconfigured(monkeypatch):
    """When compiler is unconfigured, evaluation returns unconfigured and 0 marks."""
    fake_settings = Settings(compiler_enabled=False, compiler_api_url=None)
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    eval_res = evaluate_coding_assessment(
        question_id="ts-python-positive-sum-001",
        language="python",
        source_code="def sum_positive(values): return sum(v for v in values if v > 0)",
    )
    assert eval_res.status == "unconfigured"
    assert eval_res.score == 0
    assert eval_res.passed_count == 0


def test_evaluate_coding_assessment_success_and_hidden_test_masking(monkeypatch):
    """Evaluates code against test cases and ensures hidden test inputs/outputs are NEVER leaked."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    # Mock execute_code to return correct outputs for ts-python-positive-sum-001
    # Test cases: [2, -3, 5, 0] -> 7; [-4, 0, -1] -> 0; [] -> 0; [1, 1, 3] -> 5
    mock_responses = [
        {"run": {"stdout": "7\n", "code": 0}},
        {"run": {"stdout": "0\n", "code": 0}},
        {"run": {"stdout": "0\n", "code": 0}},
        {"run": {"stdout": "5\n", "code": 0}},
    ]
    call_idx = 0

    def mock_post(url, json=None, headers=None):
        nonlocal call_idx
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = mock_responses[call_idx % len(mock_responses)]
        call_idx += 1
        return resp

    with patch("httpx.Client.post", side_effect=mock_post):
        eval_res = evaluate_coding_assessment(
            question_id="ts-python-positive-sum-001",
            language="python",
            source_code="def sum_positive(values): return sum(v for v in values if v > 0)",
        )
        assert eval_res.status == "success"
        assert eval_res.passed_count == 4
        assert eval_res.total_count == 4
        assert eval_res.percentage == 100
        assert eval_res.score == 40

        # CRITICAL SECURITY VERIFICATION:
        # Every hidden test case must have sample_input=None, expected_output=None, actual_output=None
        for test_result in eval_res.test_results:
            if test_result.is_hidden:
                assert test_result.sample_input is None
                assert test_result.expected_output is None
                assert test_result.actual_output is None
                assert test_result.passed is True


def test_compiler_api_routes(client, monkeypatch):
    """Verifies FastAPI /compiler/run and /compiler/evaluate endpoints."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_exec_res = MagicMock()
    mock_exec_res.status = "success"
    mock_exec_res.stdout = "Executed\n"
    mock_exec_res.stderr = ""
    mock_exec_res.exit_code = 0
    mock_exec_res.compile_output = None
    mock_exec_res.execution_time_ms = 45.0
    mock_exec_res.error_message = None

    with patch("app.services.code_execution_service._execute_piston", return_value=mock_exec_res):
        # 1. Run sample
        resp = client.post(
            "/api/v1/learning/compiler/run",
            json={"language": "python", "source_code": "print('hello')", "stdin": None},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["stdout"] == "Executed\n"

        # 2. Evaluate
        eval_resp = client.post(
            "/api/v1/learning/compiler/evaluate",
            json={"question_id": "ts-python-positive-sum-001", "language": "python", "source_code": "def sum_positive(): pass"},
        )
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert eval_data["question_id"] == "ts-python-positive-sum-001"
        assert "passed_count" in eval_data


def test_jdoodle_unconfigured_missing_credentials(monkeypatch):
    """When compiler_provider is jdoodle but credentials are empty, returns unconfigured."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id=None,
        jdoodle_client_secret=None,
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    result = execute_code("python", "print('hello')")
    assert result.status == "unconfigured"
    assert "missing client id or client secret" in (result.error_message or "").lower()


def test_jdoodle_success_python(monkeypatch):
    """Mocks successful code execution on JDoodle."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id",
        jdoodle_client_secret="mock_secret",
        jdoodle_api_url="https://api.jdoodle.com/v1/execute",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "Hello from JDoodle!\n",
        "statusCode": 200,
        "memory": "12000",
        "cpuTime": "0.05",
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("python", "print('Hello from JDoodle!')")
        assert res.status == "success"
        assert "Hello from JDoodle!" in (res.stdout or "")
        assert res.exit_code == 0


def test_jdoodle_compilation_error_c(monkeypatch):
    """Mocks C compilation error on JDoodle."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id",
        jdoodle_client_secret="mock_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "/tmp/12345.c: In function 'main':\n/tmp/12345.c:2:1: error: expected ';' before '}' token\n",
        "statusCode": 200,
        "memory": None,
        "cpuTime": None,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", "int main() { return 0 }")
        assert res.status == "compilation_error"
        assert "error: expected" in (res.compile_output or "")


def test_jdoodle_syntax_error_python(monkeypatch):
    """Mocks Python syntax error on JDoodle."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id",
        jdoodle_client_secret="mock_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "  File \"solution.py\", line 1\n    print(\n          ^\nSyntaxError: unexpected EOF while parsing\n",
        "statusCode": 200,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("python", "print(")
        assert res.status == "compilation_error"
        assert "SyntaxError" in (res.compile_output or "")


def test_jdoodle_runtime_error_python(monkeypatch):
    """Mocks Python runtime exception on JDoodle."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id",
        jdoodle_client_secret="mock_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "Traceback (most recent call last):\n  File \"solution.py\", line 1, in <module>\n    1 / 0\nZeroDivisionError: division by zero\n",
        "statusCode": 200,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("python", "1 / 0")
        assert res.status == "runtime_error"
        assert "ZeroDivisionError" in (res.stderr or "")


def test_jdoodle_auth_failure_401(monkeypatch):
    """Mocks HTTP 401 Unauthorized from JDoodle."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="bad_id",
        jdoodle_client_secret="bad_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "",
        "statusCode": 401,
        "error": "Unauthorized : Invalid Client ID or Client Secret",
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("python", "print('hi')")
        assert res.status == "unconfigured"
        assert "invalid client credentials" in (res.error_message or "").lower()


def test_jdoodle_rate_limited_429(monkeypatch):
    """Mocks JDoodle daily limit reached."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="valid_id",
        jdoodle_client_secret="valid_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": "Daily limit reached\n",
        "statusCode": 429,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("python", "print('hi')")
        assert res.status == "rate_limited"
        assert "daily execution limit" in (res.error_message or "").lower()


def test_sql_local_execution_select():
    """SQL runs locally in isolated in-memory SQLite and returns formatted tabular output."""
    res = execute_code(
        language="sql",
        source_code="CREATE TABLE users(id INT, name TEXT); INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob'); SELECT * FROM users ORDER BY id ASC;",
    )
    assert res.status == "success"
    assert "Alice" in (res.stdout or "")
    assert "Bob" in (res.stdout or "")
    assert res.exit_code == 0


def test_sql_evaluation_in_memory(monkeypatch):
    """SQL evaluation verifies queries against schema and setup rows locally without remote API calls."""
    fake_settings = Settings(compiler_enabled=True, compiler_provider="jdoodle")
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    # ts-sql-active-users-001 tests active users sorted by email
    eval_res = evaluate_coding_assessment(
        question_id="ts-sql-active-users-001",
        language="sql",
        source_code="SELECT email FROM users WHERE active = 1 ORDER BY email ASC;",
    )
    assert eval_res.status == "success"
    assert eval_res.passed_count == 2
    assert eval_res.total_count == 2
    assert eval_res.percentage == 100
    assert eval_res.score == 20


def test_jdoodle_batch_evaluation_conserves_credits(monkeypatch):
    """JDoodle batch evaluation executes all test cases in a single remote call."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id",
        jdoodle_client_secret="mock_secret",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    # Batch test harness returns JSON array of all results in one call
    batch_json = json.dumps([
        {"test_index": 1, "success": True, "output": 7},
        {"test_index": 2, "success": True, "output": 0},
        {"test_index": 3, "success": True, "output": 0},
        {"test_index": 4, "success": True, "output": 5},
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": f"__TS_BATCH_START__{batch_json}__TS_BATCH_END__\n",
        "statusCode": 200,
    }

    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        eval_res = evaluate_coding_assessment(
            question_id="ts-python-positive-sum-001",
            language="python",
            source_code="def sum_positive(values): return sum(v for v in values if v > 0)",
        )
        # Exactly 1 call was made to JDoodle!
        assert call_count == 1
        assert eval_res.status == "success"
        assert eval_res.passed_count == 4
        assert eval_res.total_count == 4
        assert eval_res.score == 40


def test_practice_code_cache(monkeypatch):
    """Identical runs are returned from in-memory cache without hitting remote compiler twice."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "run": {"stdout": "Cached output 12345\n", "code": 0},
        "compile": {"code": 0},
    }

    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        # 1st execution
        res1 = execute_code("python", "print('cached_test_unique_payload')")
        # 2nd execution of identical code
        res2 = execute_code("python", "print('cached_test_unique_payload')")

        assert call_count == 1  # Only called once!
        assert res1.stdout == res2.stdout == "Cached output 12345\n"


def test_jdoodle_multi_key_rotation_on_429_failover(monkeypatch):
    """When Key 1 hits 429 daily limit, JDoodle service automatically rotates to Key 2."""
    from app.services.code_execution_service import _EXHAUSTED_JDOODLE_KEYS
    _EXHAUSTED_JDOODLE_KEYS.clear()

    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="jdoodle",
        jdoodle_client_id="mock_id_1",
        jdoodle_client_secret="mock_sec_1",
        jdoodle_client_id_2="mock_id_2",
        jdoodle_client_secret_2="mock_sec_2",
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    attempted_keys = []

    def mock_jdoodle_post(url, *args, **kwargs):
        payload = kwargs.get("json") or {}
        cid = payload.get("clientId")
        attempted_keys.append(cid)
        resp = MagicMock()
        if cid == "mock_id_1":
            resp.status_code = 200
            resp.json.return_value = {
                "statusCode": 429,
                "output": "Daily limit reached\n",
                "error": "Daily limit reached",
            }
        else:
            resp.status_code = 200
            resp.json.return_value = {
                "statusCode": 200,
                "output": "Execution successful with failover Key 2\n",
            }
        return resp

    with patch("httpx.Client.post", side_effect=mock_jdoodle_post):
        res = execute_code("python", "print('failover_test_payload_123')")
        assert res.status == "success"
        assert "Execution successful with failover Key 2" in (res.stdout or "")
        assert attempted_keys == ["mock_id_1", "mock_id_2"]



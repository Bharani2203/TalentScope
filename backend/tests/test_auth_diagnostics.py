from types import SimpleNamespace

from app.core import auth_diagnostics


def test_auth_trace_logs_timing_and_redacted_uid_but_filters_credentials(monkeypatch, caplog):
    uid = "private-user-identifier"
    monkeypatch.setattr(
        auth_diagnostics,
        "get_settings",
        lambda: SimpleNamespace(environment="development"),
    )

    with caplog.at_level("INFO", logger="uvicorn.error"):
        auth_diagnostics.log_auth_trace(
            "profile_sync_request",
            duration_ms=18.25,
            status_code=200,
            result="success",
            uid_ref=auth_diagnostics.uid_reference(uid),
            id_token="never-log-this-token",
            authorization="Bearer never-log-this-token",
            email="private@example.test",
        )

    output = caplog.text
    assert "AUTH_TRACE" in output
    assert "18.25" in output
    assert auth_diagnostics.uid_reference(uid) in output
    assert uid not in output
    assert "never-log-this-token" not in output
    assert "private@example.test" not in output

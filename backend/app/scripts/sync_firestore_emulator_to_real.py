"""Copy jobs and skill signals from an explicit local emulator to real Firestore."""

import argparse
import json
from pathlib import Path
import re
import sys

from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted

from app.scripts.firestore_copy_common import (
    check_real_firestore_connection,
    make_emulator_client,
    make_real_client,
    sync_collections,
    validate_loopback_emulator_host,
)


def run_sync(source, target, *, dry_run=True, emit=None):
    return sync_collections(
        source,
        target,
        dry_run=dry_run,
        emit=emit,
        source_is_real=False,
        target_is_real=True,
    )


def _print(message: str) -> None:
    print(message, flush=True)


def _safe_error_message(exc: Exception, credential_path: str) -> str:
    message = str(exc).splitlines()[0] if str(exc) else "operation failed"
    message = message.replace(credential_path, "[credentials path]")
    if "-----BEGIN " in message:
        return "key material redacted"
    message = re.sub(
        r'(?i)(private[_ -]?key|client[_ -]?secret|access[_ -]?token|refresh[_ -]?token|password)(\s*[=:]\s*)(?:"(?:\\.|[^"\\])*"|\S+)',
        r"\1\2[REDACTED]",
        message,
    )
    return message[:200]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Copy jobs and skill_market_signals from emulator to real Firestore.")
    parser.add_argument("--source-emulator-host", required=True, help="Explicit loopback emulator endpoint, normally 127.0.0.1:8080.")
    parser.add_argument("--target-project", required=True, help="Explicit real Firebase project ID.")
    parser.add_argument("--target-credentials", required=True, help="Path to the real target service-account JSON file.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Count and report; default mode, never writes.")
    mode.add_argument("--apply", action="store_true", help="Write missing documents in batches of 200.")
    args = parser.parse_args(argv)
    try:
        emulator_host = validate_loopback_emulator_host(args.source_emulator_host)
        credentials_path = Path(args.target_credentials)
        if not credentials_path.is_file():
            raise ValueError("Target credential file does not exist.")
        _print(f"FIRESTORE SOURCE: EMULATOR ({emulator_host})")
        _print(f"FIRESTORE TARGET: REAL ({args.target_project})")
        _print("Creating emulator client...")
        source = make_emulator_client(emulator_host)
        _print(f"Creating real client for project {args.target_project}...")
        target = make_real_client(args.target_project, str(credentials_path))
        _print(f"SOURCE ENDPOINT: {source._target}")
        _print(f"TARGET ENDPOINT: {target._target}")
        _print("Checking real Firestore connection...")
        check_real_firestore_connection(target)
        _print("Real Firestore connection check passed.")
        report = run_sync(source, target, dry_run=not args.apply, emit=_print)
        return 1 if report["status"].startswith(("resource_exhausted", "timeout")) else 0
    except (OSError, ValueError) as exc:
        message = _safe_error_message(exc, str(args.target_credentials))
        print(f"Firestore sync refused or failed: {type(exc).__name__}: {message}", file=sys.stderr, flush=True)
        return 2
    except ResourceExhausted:
        _print("Real Firestore quota exhausted; nothing was written; try again after the quota resets.")
        return 1
    except (DeadlineExceeded, TimeoutError):
        _print("Real Firestore did not respond in time (possible quota exhaustion or network issue); nothing was written")
        return 1
    except Exception as exc:
        message = _safe_error_message(exc, str(args.target_credentials))
        print(f"Firestore sync failed: {type(exc).__name__}: {message}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

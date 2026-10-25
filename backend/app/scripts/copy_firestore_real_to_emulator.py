"""Copy existing jobs and skill signals from real Firestore into the local emulator."""

import argparse
from pathlib import Path
import sys

from app.scripts.firestore_copy_common import (
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
        source_is_real=True,
        target_is_real=False,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Copy jobs and skill_market_signals from real Firestore to the emulator.")
    parser.add_argument("--source-project", required=True, help="Explicit real Firebase project ID.")
    parser.add_argument("--source-credentials", required=True, help="Path to the real source service-account JSON file.")
    parser.add_argument("--target-emulator-host", required=True, help="Explicit loopback emulator endpoint, normally 127.0.0.1:8080.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Count and report; default mode, never writes.")
    mode.add_argument("--apply", action="store_true", help="Write missing documents in batches of 200.")
    args = parser.parse_args(argv)
    try:
        emulator_host = validate_loopback_emulator_host(args.target_emulator_host)
        credentials_path = Path(args.source_credentials)
        if not credentials_path.is_file():
            raise ValueError("Source credential file does not exist.")
        source = make_real_client(args.source_project, str(credentials_path))
        target = make_emulator_client(emulator_host)
        report = run_sync(source, target, dry_run=not args.apply)
        return 1 if report["status"].startswith("resource_exhausted") else 0
    except (OSError, ValueError) as exc:
        print(f"Firestore copy refused or failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

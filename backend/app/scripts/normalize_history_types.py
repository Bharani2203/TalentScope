"""Dry-run by default; pass --apply to normalize known Firestore aliases."""

import argparse
import json

from app.services.history_type_migration import normalize_history_types


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize known skill_market_signals history_type aliases.")
    parser.add_argument("--apply", action="store_true", help="Write deterministic mappings to Firestore (default is dry-run).")
    args = parser.parse_args()
    result = normalize_history_types(apply=args.apply)
    print(json.dumps({"mode": "apply" if args.apply else "dry_run", **result}, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

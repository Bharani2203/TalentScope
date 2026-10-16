"""Run a controlled historical backfill. Dry-run is the default."""

import argparse
import json

from app.services.historical_backfill_service import backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill genuine dated Stack Overflow tag history.")
    parser.add_argument("--source", choices=["stackexchange"], required=True)
    parser.add_argument("--skill", action="append", required=True, help="Canonical registry skill; repeatable.")
    parser.add_argument("--start", required=True, help="Inclusive start month (YYYY-MM).")
    parser.add_argument("--end", required=True, help="Inclusive end month (YYYY-MM), before current month.")
    parser.add_argument("--execute", action="store_true", help="Persist observations. Default performs a dry run.")
    args = parser.parse_args()
    try:
        result = backfill(
            source=args.source,
            skills=args.skill,
            start_period=args.start,
            end_period=args.end,
            dry_run=not args.execute,
        )
    except ValueError as error:
        parser.error(str(error))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())


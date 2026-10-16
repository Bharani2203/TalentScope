"""CLI command for controlled Wikipedia pageviews technical-interest backfills into local SQLite.

By default, this tool performs a safe DRY-RUN planning pass.
To execute live network requests and persist observations, pass the explicit `--execute` flag.

GUARANTEES:
1. Zero Firebase Admin initialization.
2. Zero Firestore operations.
3. Strictly local SQLite persistence.
4. Dry-run by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add backend directory to sys.path if running directly
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.services.market_data.wikipedia_provider import (
    WIKIPEDIA_CANONICAL_ARTICLE_ALLOWLIST,
    get_completed_month_range,
    resolve_wikipedia_article_for_skill,
)
from app.services.wikipedia_backfill_service import run_wikipedia_backfill


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill genuine historical Wikipedia monthly pageviews into local SQLite."
    )
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        help="Canonical skill name or ID to backfill (repeatable). Default: python, react, cloud_computing.",
    )
    parser.add_argument(
        "--start",
        dest="start_period",
        help="Inclusive start month (YYYY-MM). Default: 12 complete months ago.",
    )
    parser.add_argument(
        "--end",
        dest="end_period",
        help="Inclusive end month (YYYY-MM). Must precede the current UTC month.",
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        help="Path to SQLite database. Default: configured skill_intelligence_db_path.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute genuine network requests and persist observations to SQLite. Without this, only a dry-run is performed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format.",
    )

    args = parser.parse_args()
    settings = get_settings()

    skills_to_backfill = args.skills or ["python", "react", "cloud_computing"]
    db_path = Path(args.db_path) if args.db_path else (backend_dir / settings.skill_intelligence_db_path)

    try:
        start_period, end_period, target_periods = get_completed_month_range(
            args.start_period, args.end_period,
        )
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    # Pre-execution plan display
    print("=" * 65)
    print("   TalentScope.ai -- Wikipedia Pageviews Backfill Runner")
    print("=" * 65)
    print(f"Mode:          {'LIVE EXECUTION' if args.execute else 'DRY-RUN (Safe Planning Mode)'}")
    print(f"SQLite Target: {db_path}")
    print(f"Date Range:    {start_period} to {end_period} ({len(target_periods)} complete monthly periods)")
    print(f"Skills Selected ({len(skills_to_backfill)}):")

    for sk in skills_to_backfill:
        try:
            defn, art = resolve_wikipedia_article_for_skill(sk)
            print(f"  * {defn.name:20} (ID: {defn.skill_id:15}) -> Wikipedia Article: '{art}'")
        except ValueError as err:
            print(f"  * {sk:20} -> [ERROR: {err}]")

    print("=" * 65)

    if not args.execute:
        print("\nNotice: Running in DRY-RUN mode. No network calls or SQLite modifications will be made.")
        print("To execute live retrieval, re-run with '--execute'.\n")

    result = asyncio.run(
        run_wikipedia_backfill(
            skills=skills_to_backfill,
            start_period=start_period,
            end_period=end_period,
            db_path=db_path,
            dry_run=not args.execute,
        )
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print("\n=== Backfill Summary ===")
    for item in result["results"]:
        status = item.get("status", "unknown").upper()
        skill_name = item.get("skill", "unknown")
        if status == "SUCCESS":
            fetched = item.get("observations_fetched", 0)
            inserted = item.get("observations_inserted", 0)
            print(f"  [SUCCESS] {skill_name:20} | Fetched: {fetched:3d} | Inserted: {inserted:3d} observations")
        elif status == "ALREADY_COMPLETE":
            print(f"  [SKIPPED] {skill_name:20} | Series already complete in SQLite ({item.get('existing_periods_count')} periods)")
        elif status == "DRY_RUN":
            to_fetch = len(item.get("periods_to_fetch", []))
            print(f"  [DRY-RUN] {skill_name:20} | Planned periods to fetch: {to_fetch:3d}")
        elif status == "UNMAPPED":
            print(f"  [UNMAPPED] {skill_name:20} | {item.get('error')}")
        else:
            print(f"  [FAILED]  {skill_name:20} | {item.get('error')}")

    print(f"\nTotal new observations inserted: {result['total_new_observations']}")
    print(f"Total existing periods skipped:  {result['total_skipped_existing']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

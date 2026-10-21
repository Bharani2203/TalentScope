"""CLI command to import historical job-demand datasets into local SQLite.

Usage:
    # Dry run (default):
    python -m app.scripts.import_historical_jobs --country IN --dry-run

    # Execute import with explicit commit:
    python -m app.scripts.import_historical_jobs --country IN --commit
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.historical_job_import_service import HistoricalJobImportService
from app.storage.market_store import MarketDataStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_historical_jobs")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idempotently import historical job observations into TalentScope local SQLite."
    )
    parser.add_argument(
        "--file",
        type=str,
        default="data/external_data/fliarbi/job_postings_2026_sample.csv",
        help="Path to CSV dataset file (relative to backend or absolute).",
    )
    parser.add_argument(
        "--country",
        type=str,
        default="IN",
        choices=["IN", "US"],
        help="Target country code (India 'IN' or United States 'US'). Never merged.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit observations to SQLite (default is dry-run unless --commit is specified).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run validation without writing to SQLite.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit for test validation.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to SQLite database file (defaults to configured database_path).",
    )

    args = parser.parse_args()

    # Default to dry-run unless --commit is explicitly passed and --dry-run is not passed
    is_dry_run = args.dry_run or not args.commit

    csv_path = Path(args.file)
    if not csv_path.is_absolute():
        # Check relative to backend directory
        candidate = Path(__file__).resolve().parent.parent.parent / csv_path
        if candidate.is_file():
            csv_path = candidate

    if not csv_path.is_file():
        logger.error("Dataset file not found at %s", csv_path)
        sys.exit(1)

    settings = get_settings()
    default_db = settings.reference_database_path if settings.reference_database_path.is_file() else settings.database_path
    db_path = Path(args.db_path) if args.db_path else default_db
    logger.info("Target SQLite database: %s", db_path)
    logger.info("Dataset CSV: %s (Dry run: %s, Country: %s)", csv_path, is_dry_run, args.country)

    store = MarketDataStore(database_path=db_path)
    service = HistoricalJobImportService(store=store)

    stats = service.import_from_csv(
        file_path=csv_path,
        target_country=args.country,
        dry_run=is_dry_run,
        limit_rows=args.limit,
    )

    print("\n" + "=" * 60)
    print("HISTORICAL JOB IMPORT SUMMARY")
    print("=" * 60)
    print(json.dumps(stats, indent=2))
    print("=" * 60)

    if is_dry_run:
        print("\n[NOTE] Dry run complete. No database changes were made. Use --commit to persist.")
    else:
        print(f"\n[SUCCESS] Successfully committed {stats['observations_inserted']} observations to SQLite.")


if __name__ == "__main__":
    main()

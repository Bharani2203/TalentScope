import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from app.core.config import Settings
from app.models.skill_intelligence import MarketCollectionRequest
from app.services.market_collection_service import OfflineFixtureProvider, collect_market_data
from app.storage.fetch_run_store import SQLiteFetchRunStore
from app.storage.market_store import MarketDataStore


def _successful_exit(result) -> bool:
    if result.status == "success":
        return True
    if result.status == "dry_run":
        if "preview_mode_zero_network_calls" in result.status_reasons:
            return not result.sources_failed
        return (
            not result.sources_failed
            and not [
                r for r in result.status_reasons
                if r not in {"offline_test", "zero_database_writes"}
            ]
            and all(provider.status in {"success", "preview"} for provider in result.providers)
        )
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one market-data snapshot.")
    parser.add_argument("--location", help="Optional city/location filter for job-market sources.")
    parser.add_argument("--country", help="Optional two-letter country code, such as in.")
    parser.add_argument("--provider", choices=("jsearch", "adzuna"), help="Collect from only this enabled, configured job-posting source.")
    parser.add_argument("--query", default="software developer", help="Job search phrase; defaults to 'software developer'.")
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Adzuna page size (1-50); JSearch uses its single-page provider default.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the proposed collection plan without contacting external providers or writing to storage.",
    )
    parser.add_argument(
        "--offline-test",
        action="store_true",
        help="Run a local offline simulation with safe test fixtures without contacting external providers or writing to storage.",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Persist test-labelled fixture observations and run metadata to a new SQLite file under the OS temporary directory.",
    )
    parser.add_argument(
        "--database-path",
        help="Required with --fixture; must name a new .sqlite3 file under the OS temporary directory.",
    )
    parser.add_argument("--trigger-type", choices=("schedule", "workflow_dispatch", "local"), default="local")
    parser.add_argument("--workflow-run-id", help="GitHub Actions run ID; provenance only, no credentials.")
    parser.add_argument("--workflow-attempt", type=int, help="GitHub Actions attempt number.")
    args = parser.parse_args()
    if sum((args.dry_run, args.offline_test, args.fixture)) > 1:
        parser.error("Choose only one of --dry-run, --offline-test, or --fixture.")
    if args.database_path and not args.fixture:
        parser.error("--database-path is only valid with --fixture.")
    fixture_database = None
    if args.fixture:
        if not args.database_path:
            parser.error("--fixture requires --database-path.")
        fixture_database = Path(args.database_path).expanduser().resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if not fixture_database.is_relative_to(temp_root) or fixture_database.suffix.casefold() != ".sqlite3":
            parser.error("Fixture database must be a .sqlite3 file under the OS temporary directory.")
        if fixture_database.exists():
            parser.error("Fixture database must not already exist.")
    try:
        request = MarketCollectionRequest(location=args.location, country=args.country)
    except ValueError as error:
        parser.error(str(error))
        return 2
    if request.country:
        request.country = request.country.lower()
    if args.limit < 1 or args.limit > 50:
        parser.error("--limit must be between 1 and 50")
    if not args.query.strip():
        parser.error("--query must not be empty")
    if args.fixture:
        assert fixture_database is not None
        # model_construct avoids consulting process environment or dotenv values in fixture mode.
        settings = Settings.model_construct(
            environment="local-test",
            skill_intelligence_read_backend="sqlite",
            skill_intelligence_db_path=str(fixture_database),
            market_collection_enabled_providers=[],
            market_collection_panel_version="fixture-panel-v1",
            market_collection_cron="fixture-manual",
        )
        market_store = MarketDataStore(fixture_database)
        run_store = SQLiteFetchRunStore(fixture_database)

        class FixtureArchive:
            def archive(self, **_kwargs):
                return {"archive_reference": "fixture-payload-not-retained"}

        result = asyncio.run(collect_market_data(
            settings=settings,
            providers=[OfflineFixtureProvider(args.provider or "adzuna")],
            store=market_store,
            fetch_run_store=run_store,
            observation_store=market_store,
            raw_response_archive=FixtureArchive(),
            fixture_mode=True,
            posting_persister=market_store.persist_fixture_postings,
            trigger_type=args.trigger_type,
            scheduler_run_id=args.workflow_run_id,
            scheduler_attempt=args.workflow_attempt,
            location=request.location,
            country=request.country,
            provider_name=args.provider or "adzuna",
            query=args.query,
            result_limit=args.limit,
        ))
    else:
        result = asyncio.run(collect_market_data(
        location=request.location,
        country=request.country,
        dry_run=args.dry_run or args.offline_test,
        offline_test=args.offline_test,
        preview_only=args.dry_run,
        provider_name=args.provider,
        query=args.query,
        result_limit=args.limit,
        ))
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if _successful_exit(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())

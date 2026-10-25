"""Collect configured public India ATS postings and persist them through existing stores."""

import argparse
import json
import logging
import sys

from app.core.config import get_settings
from app.core.firestore_status import firestore_runtime_label
from app.services.public_company_job_board_service import (
    DEFAULT_BOARD_CONFIG,
    collect_and_store_public_job_boards,
    load_public_boards,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect recent India postings from configured public ATS boards.")
    parser.add_argument("--config", default=str(DEFAULT_BOARD_CONFIG), help="JSON config containing {\"boards\":[{\"ats\",\"slug\"}]}.")
    parser.add_argument("--skill-extraction-cap", type=int, default=None, help="Maximum technical postings to extract this run (default 60; can also use PUBLIC_JOB_BOARD_SKILL_EXTRACTION_CAP).")
    parser.add_argument("--non-technical-keywords", default=None, help="Comma-separated title/department exclusions; overrides PUBLIC_JOB_BOARD_NON_TECHNICAL_KEYWORDS.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Fetch and filter boards without skill extraction or persistence.")
    mode.add_argument("--validate-config", action="store_true", help="Validate config and exit without network access.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger(__name__).info(firestore_runtime_label(get_settings().firebase_project_id))
    if args.validate_config:
        try:
            boards = load_public_boards(args.config)
        except (OSError, ValueError) as exc:
            print(f"Invalid config: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"config_valid": True, "board_count": len(boards), "boards": [
            {"ats": board.ats, "slug": board.slug} for board in boards
        ]}, indent=2))
        return 0
    try:
        keywords = args.non_technical_keywords.split(",") if args.non_technical_keywords is not None else None
        result = collect_and_store_public_job_boards(
            args.config,
            dry_run=args.dry_run,
            skill_extraction_cap=args.skill_extraction_cap,
            non_technical_keywords=keywords,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.as_dict(), indent=2))
    return 1 if result.boards_failed or result.persistence_status == "resource_exhausted" else 0


if __name__ == "__main__":
    raise SystemExit(main())

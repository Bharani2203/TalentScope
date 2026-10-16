"""Offline CLI runner for reference data ingestion and inspection.

GUARANTEES:
1. Zero Firebase Admin initialization.
2. Zero Firestore network operations.
3. Operates strictly on local SQLite and local CSV/ZIP files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend directory to path if running directly
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.services.reference_data_service import (
    ingest_all_reference_datasets,
    inspect_esco_archive,
)
from app.storage.reference_store import ReferenceDataStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and inspect local reference datasets.")
    parser.add_argument(
        "--ref-dir",
        default=str(backend_dir / "data" / "reference"),
        help="Path to directory containing reference datasets",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to SQLite database (defaults to skill_intelligence_db_path)",
    )
    parser.add_argument(
        "--inspect-esco-only",
        action="store_true",
        help="Only inspect ESCO archive manifest without ingesting other data",
    )
    args = parser.parse_args()

    ref_dir = Path(args.ref_dir)
    if not ref_dir.is_dir():
        print(f"Error: Reference directory not found: {ref_dir}", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    db_path = Path(args.db_path) if args.db_path else (backend_dir / settings.skill_intelligence_db_path)

    print(f"=== Reference Data Ingestion ===")
    print(f"Reference Directory: {ref_dir}")
    print(f"SQLite Store:        {db_path}")

    # ESCO Inspection
    esco_zip = ref_dir / "ESCO dataset - v1.2.1 - classification - en - csv.zip"
    if esco_zip.is_file():
        print(f"\n[ESCO] Inspecting archive manifest: {esco_zip.name}...")
        manifest = inspect_esco_archive(esco_zip)
        print(f"  Archive Size: {manifest.archive_bytes:,} bytes")
        print(f"  Total Members: {manifest.members_count}")
        for member in manifest.members:
            tier_badge = f"[{member.import_tier.upper()}]"
            print(f"  - {member.filename:35} {tier_badge:16} ({member.uncompressed_bytes:,} bytes)")
    else:
        print(f"\n[ESCO] Archive not found in {ref_dir}")

    if args.inspect_esco_only:
        print("\nCompleted ESCO inspection only.")
        return

    # Ingest Datasets
    store = ReferenceDataStore(db_path)
    print("\n[INGESTION] Beginning local reference data import...")
    summaries = ingest_all_reference_datasets(ref_dir, store)

    print("\n=== Ingestion Summary ===")
    for summary in summaries:
        print(
            f"  {summary.dataset:30} | "
            f"Read: {summary.rows_read:7,d} | "
            f"Valid: {summary.rows_valid:7,d} | "
            f"Inserted: {summary.rows_inserted:7,d} | "
            f"Time: {summary.duration_seconds:.2f}s"
        )
        if summary.errors:
            print(f"    Warnings/Errors (first {len(summary.errors)}): {summary.errors[:3]}")

    counts = store.get_table_counts()
    print("\n=== SQLite Table Counts ===")
    for tbl, count in counts.items():
        print(f"  {tbl:32}: {count:,d}")


if __name__ == "__main__":
    main()

"""Offline CLI runner for reference data ingestion and inspection.

GUARANTEES:
1. Zero Firebase Admin initialization.
2. Zero Firestore network operations.
3. Operates strictly on local SQLite and local CSV/ZIP files.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add backend directory to path if running directly
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.services.reference_data_service import (
    ingest_all_reference_datasets,
    ingest_esco_archive,
    ingest_esco_extracted_directory,
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
        help="Only inspect the staged ESCO archive or extracted directory",
    )
    parser.add_argument(
        "--esco-only",
        action="store_true",
        help="Import only the validated ESCO release; leave other reference tables untouched",
    )
    args = parser.parse_args()

    ref_dir = Path(args.ref_dir)
    if not ref_dir.is_dir():
        print(f"Error: Reference directory not found: {ref_dir}", file=sys.stderr)
        sys.exit(1)

    if args.db_path:
        db_path = Path(args.db_path)
    else:
        settings = get_settings()
        db_path = backend_dir / settings.skill_intelligence_db_path

    print(f"=== Reference Data Ingestion ===")
    print(f"Reference Directory: {ref_dir}")
    print(f"SQLite Store:        {db_path}")

    # ESCO Inspection
    esco_zip = ref_dir / "ESCO dataset - v1.2.1 - classification - en - csv.zip"
    esco_directory = ref_dir / "ESCO dataset - v1.2.1 - classification - en - csv"
    if esco_zip.is_file():
        print(f"\n[ESCO] Inspecting archive manifest: {esco_zip.name}...")
        manifest = inspect_esco_archive(esco_zip)
        print(f"  Archive Size: {manifest.archive_bytes:,} bytes")
        print(f"  Total Members: {manifest.members_count}")
        for member in manifest.members:
            tier_badge = f"[{member.import_tier.upper()}]"
            print(f"  - {member.filename:35} {tier_badge:16} ({member.uncompressed_bytes:,} bytes)")
    elif esco_directory.is_dir():
        source_files = sorted(path for path in esco_directory.iterdir() if path.is_file())
        print(f"\n[ESCO] Extracted release: {esco_directory.name}")
        print(f"  Files: {len(source_files)}")
        for source_file in source_files:
            print(f"  - {source_file.name} ({source_file.stat().st_size:,} bytes)")
    else:
        print(f"\n[ESCO] Archive or extracted release not found in {ref_dir}")

    if args.inspect_esco_only:
        print("\nCompleted ESCO inspection only.")
        return

    if args.esco_only:
        if esco_zip.is_file() and esco_directory.is_dir():
            print("Both archived and extracted ESCO releases exist; refusing ambiguous import.", file=sys.stderr)
            sys.exit(2)
        store = ReferenceDataStore(db_path)
        started = time.perf_counter()
        if esco_zip.is_file():
            source = esco_zip
            summary = ingest_esco_archive(esco_zip, store)
        elif esco_directory.is_dir():
            source = esco_directory
            summary = ingest_esco_extracted_directory(esco_directory, store)
        else:
            print("No supported ESCO source was found; nothing imported.", file=sys.stderr)
            sys.exit(2)
        duration = time.perf_counter() - started
        for dataset, filename, valid_key, inserted_key, read_key, rejected_key, duplicate_key in (
            ("esco_skills", "skills_en.csv", "esco_skill_rows_valid", "esco_skills", "esco_skill_rows_read", "esco_skill_rows_rejected", "esco_skill_rows_duplicate"),
            ("esco_occupations", "occupations_en.csv", "esco_occupation_rows_valid", "esco_occupations", "esco_occupation_rows_read", "esco_occupation_rows_rejected", "esco_occupation_rows_duplicate"),
            ("esco_occupation_skill_relations", "occupationSkillRelations_en.csv", "esco_relation_rows_valid", "esco_occupation_skill_relations", "esco_relation_rows_read", "esco_relation_rows_rejected", "esco_relation_rows_duplicate"),
        ):
            store.log_ingestion(
                dataset=dataset,
                source_file=f"{source.name}{'!' if source.is_file() else '/'}{filename}",
                rows_read=summary[read_key], rows_valid=summary[valid_key],
                rows_inserted=summary[inserted_key],
                rows_skipped_or_duplicate=summary[rejected_key] + summary[duplicate_key],
                duration_seconds=duration,
            )
        print("\n=== ESCO Import Summary ===")
        for key, value in sorted(summary.items()):
            print(f"  {key}: {value}")
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

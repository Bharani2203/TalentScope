"""Ingestion, parsing, and inspection service for local reference datasets."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import time
import zipfile
from pathlib import Path
from typing import Any

from app.analytics.skill_normalization import canonical_skill_id, normalize_skill
from app.analytics.skill_registry import normalize_skill_entry, source_mapping
from app.models.reference_data import (
    EscoArchiveManifest,
    EscoArchiveMember,
    GitHubLanguageAdoption,
    GitHubTopicAdoption,
    OnetEssentialSkill,
    OnetOccupation,
    OnetRelatedOccupation,
    OnetSoftwareSkill,
    ReferenceIngestionSummary,
)
from app.storage.reference_store import ReferenceDataStore

logger = logging.getLogger(__name__)


def _stable_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# O*NET Parsers
# -----------------------------------------------------------------------------

def parse_onet_occupations(csv_path: str | Path) -> tuple[list[OnetOccupation], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"O*NET occupations file not found: {path}")

    occupations: list[OnetOccupation] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {"O*NET-SOC Code", "Title", "Description"}
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid O*NET occupations CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            soc = (row.get("O*NET-SOC Code") or "").strip()
            title = (row.get("Title") or "").strip()
            desc = (row.get("Description") or "").strip()
            if not soc or not title:
                errors.append(f"Line {line_num}: missing SOC code or Title")
                continue
            occupations.append(OnetOccupation(soc_code=soc, title=title, description=desc))

    return occupations, errors


def parse_onet_software_skills(csv_path: str | Path) -> tuple[list[OnetSoftwareSkill], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"O*NET software skills file not found: {path}")

    skills: list[OnetSoftwareSkill] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {
            "O*NET-SOC Code", "Title", "Workplace Example",
            "Element ID", "Element Name", "Hot Technology", "In Demand",
        }
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid O*NET software skills CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            soc = (row.get("O*NET-SOC Code") or "").strip()
            title = (row.get("Title") or "").strip()
            example = (row.get("Workplace Example") or "").strip()
            elem_id = (row.get("Element ID") or "").strip()
            elem_name = (row.get("Element Name") or "").strip()
            hot = (row.get("Hot Technology") or "").strip().upper() == "Y"
            in_demand = (row.get("In Demand") or "").strip().upper() == "Y"

            if not soc or not example or not elem_id:
                errors.append(f"Line {line_num}: missing mandatory fields")
                continue

            entry = normalize_skill_entry(example)
            cid = entry.canonical_skill_id if entry.is_known else None
            record_id = _stable_hash(f"onet:software:{soc}:{example.casefold()}:{elem_id}")

            skills.append(OnetSoftwareSkill(
                id=record_id,
                soc_code=soc,
                title=title,
                workplace_example=example,
                element_id=elem_id,
                element_name=elem_name,
                hot_technology=hot,
                in_demand=in_demand,
                canonical_skill_id=cid,
            ))

    return skills, errors


def parse_onet_essential_skills(csv_path: str | Path) -> tuple[list[OnetEssentialSkill], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"O*NET essential skills file not found: {path}")

    skills: list[OnetEssentialSkill] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {
            "O*NET-SOC Code", "Title", "Element ID", "Element Name",
            "Scale ID", "Scale Name", "Data Value",
        }
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid O*NET essential skills CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            soc = (row.get("O*NET-SOC Code") or "").strip()
            title = (row.get("Title") or "").strip()
            elem_id = (row.get("Element ID") or "").strip()
            elem_name = (row.get("Element Name") or "").strip()
            scale_id = (row.get("Scale ID") or "").strip()
            scale_name = (row.get("Scale Name") or "").strip()
            raw_val = (row.get("Data Value") or "").strip()

            if scale_id not in ("IM", "LV"):
                errors.append(f"Line {line_num}: invalid scale_id '{scale_id}'")
                continue

            try:
                data_val = float(raw_val)
            except (ValueError, TypeError):
                errors.append(f"Line {line_num}: invalid Data Value '{raw_val}'")
                continue

            sample_size = None
            raw_n = (row.get("N") or "").strip()
            if raw_n:
                try:
                    sample_size = int(raw_n)
                except ValueError:
                    pass

            def _parse_float(field: str) -> float | None:
                val = (row.get(field) or "").strip()
                if val:
                    try:
                        return float(val)
                    except ValueError:
                        return None
                return None

            se = _parse_float("Standard Error")
            lower_ci = _parse_float("Lower CI Bound")
            upper_ci = _parse_float("Upper CI Bound")
            suppress = (row.get("Recommend Suppress") or "").strip().upper() == "Y"
            domain = (row.get("Domain Source") or "").strip() or None
            date = (row.get("Date") or "").strip() or None

            record_id = _stable_hash(f"onet:essential:{soc}:{elem_id}:{scale_id}")

            skills.append(OnetEssentialSkill(
                id=record_id,
                soc_code=soc,
                title=title,
                element_id=elem_id,
                element_name=elem_name,
                scale_id=scale_id,  # type: ignore[arg-type]
                scale_name="Importance" if scale_id == "IM" else "Level",
                data_value=data_val,
                sample_size=sample_size,
                standard_error=se,
                lower_ci_bound=lower_ci,
                upper_ci_bound=upper_ci,
                recommend_suppress=suppress,
                domain_source=domain,
                date=date,
            ))

    return skills, errors


def parse_onet_related_occupations(csv_path: str | Path) -> tuple[list[OnetRelatedOccupation], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"O*NET related occupations file not found: {path}")

    relations: list[OnetRelatedOccupation] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {
            "O*NET-SOC Code", "Title", "Related O*NET-SOC Code",
            "Related Title", "Relatedness Tier", "Index",
        }
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid O*NET related occupations CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            soc = (row.get("O*NET-SOC Code") or "").strip()
            title = (row.get("Title") or "").strip()
            rel_soc = (row.get("Related O*NET-SOC Code") or "").strip()
            rel_title = (row.get("Related Title") or "").strip()
            tier = (row.get("Relatedness Tier") or "").strip()
            raw_idx = (row.get("Index") or "").strip()

            if not soc or not rel_soc or not tier:
                errors.append(f"Line {line_num}: missing mandatory fields")
                continue

            try:
                idx = int(raw_idx)
            except ValueError:
                idx = 0

            record_id = _stable_hash(f"onet:related:{soc}:{rel_soc}:{tier}")

            relations.append(OnetRelatedOccupation(
                id=record_id,
                soc_code=soc,
                title=title,
                related_soc_code=rel_soc,
                related_title=rel_title,
                relatedness_tier=tier,
                sort_index=idx,
            ))

    return relations, errors


# -----------------------------------------------------------------------------
# GitHub Innovation Graph Parsers (Adoption Signals)
# -----------------------------------------------------------------------------

def parse_github_languages(csv_path: str | Path) -> tuple[list[GitHubLanguageAdoption], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"GitHub languages file not found: {path}")

    records: list[GitHubLanguageAdoption] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {"num_pushers", "language", "language_type", "iso2_code", "year", "quarter"}
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid GitHub languages CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            raw_pushers = (row.get("num_pushers") or "").strip()
            lang = (row.get("language") or "").strip()
            lang_type = (row.get("language_type") or "").strip()
            iso = (row.get("iso2_code") or "").strip().upper()
            raw_yr = (row.get("year") or "").strip()
            raw_q = (row.get("quarter") or "").strip()

            try:
                pushers = int(raw_pushers)
                year = int(raw_yr)
                quarter = int(raw_q)
            except (ValueError, TypeError):
                errors.append(f"Line {line_num}: invalid integer in pushers/year/quarter")
                continue

            if not (1 <= quarter <= 4):
                errors.append(f"Line {line_num}: quarter {quarter} out of bounds")
                continue

            entry = normalize_skill_entry(lang)
            cid = entry.canonical_skill_id if entry.is_known else None
            period = f"{year}-Q{quarter}"
            record_id = _stable_hash(f"github:lang:{lang.casefold()}:{iso}:{year}:Q{quarter}")

            records.append(GitHubLanguageAdoption(
                id=record_id,
                language=lang,
                language_type=lang_type,
                iso2_code=iso,
                year=year,
                quarter=quarter,
                period=period,
                num_pushers=pushers,
                signal_type="adoption",
                data_origin="real",
                canonical_skill_id=cid,
            ))

    return records, errors


def parse_github_topics(csv_path: str | Path) -> tuple[list[GitHubTopicAdoption], list[str]]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"GitHub topics file not found: {path}")

    records: list[GitHubTopicAdoption] = []
    errors: list[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        required_cols = {"num_pushers", "topic", "iso2_code", "year", "quarter"}
        if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid GitHub topics CSV header: {reader.fieldnames}")

        for line_num, row in enumerate(reader, start=2):
            raw_pushers = (row.get("num_pushers") or "").strip()
            topic = (row.get("topic") or "").strip()
            iso = (row.get("iso2_code") or "").strip().upper()
            raw_yr = (row.get("year") or "").strip()
            raw_q = (row.get("quarter") or "").strip()

            try:
                pushers = int(raw_pushers)
                year = int(raw_yr)
                quarter = int(raw_q)
            except (ValueError, TypeError):
                errors.append(f"Line {line_num}: invalid integer in pushers/year/quarter")
                continue

            if not (1 <= quarter <= 4):
                errors.append(f"Line {line_num}: quarter {quarter} out of bounds")
                continue

            mapped = source_mapping("github", topic.casefold())
            cid = mapped.skill_id if mapped else None
            if not cid:
                entry = normalize_skill_entry(topic)
                cid = entry.canonical_skill_id if entry.is_known else None

            period = f"{year}-Q{quarter}"
            record_id = _stable_hash(f"github:topic:{topic.casefold()}:{iso}:{year}:Q{quarter}")

            records.append(GitHubTopicAdoption(
                id=record_id,
                topic=topic,
                iso2_code=iso,
                year=year,
                quarter=quarter,
                period=period,
                num_pushers=pushers,
                signal_type="adoption",
                data_origin="real",
                canonical_skill_id=cid,
            ))

    return records, errors


# -----------------------------------------------------------------------------
# ESCO Archive Inspection (No Full Extraction)
# -----------------------------------------------------------------------------

def inspect_esco_archive(zip_path: str | Path) -> EscoArchiveManifest:
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"ESCO ZIP archive not found: {path}")

    total_bytes = path.stat().st_size
    members: list[EscoArchiveMember] = []

    primary_files = {
        "skills_en.csv",
        "occupations_en.csv",
        "occupationSkillRelations_en.csv",
        "digitalSkillsCollection_en.csv",
    }
    secondary_files = {
        "transversalSkillsCollection_en.csv",
        "greenSkillsCollection_en.csv",
        "ISCOGroups_en.csv",
        "skillSkillRelations_en.csv",
        "skillGroups_en.csv",
    }

    purpose_map = {
        "skills_en.csv": "Taxonomy of 13,890+ skills/competencies with preferred and alternative labels.",
        "occupations_en.csv": "Taxonomy of 3,000+ European occupations classified under ISCO-08.",
        "occupationSkillRelations_en.csv": "Bipartite graph mapping occupations to skills (essential vs optional).",
        "digitalSkillsCollection_en.csv": "Curated European ICT and digital competencies subset.",
        "transversalSkillsCollection_en.csv": "Foundational transversal and interpersonal competencies.",
        "greenSkillsCollection_en.csv": "Environmental sustainability and green transition competencies.",
        "ISCOGroups_en.csv": "International Standard Classification of Occupations hierarchy.",
        "skillSkillRelations_en.csv": "Prerequisite and hierarchical relations between skills.",
        "skillGroups_en.csv": "High-level skill category pillars.",
        "dictionary_en.csv": "Data dictionary and column definitions.",
    }

    with zipfile.ZipFile(path, "r") as zf:
        infolist = zf.infolist()
        for info in infolist:
            fn = info.filename
            uncompressed = info.file_size
            compressed = info.compress_size

            header_cols: list[str] = []
            if fn.endswith(".csv") and uncompressed > 0:
                with zf.open(fn) as member_file:
                    first_line = member_file.readline().decode("utf-8", errors="replace")
                    reader = csv.reader(io.StringIO(first_line))
                    parsed = next(reader, [])
                    header_cols = [c.strip() for c in parsed]

            tier: Any = (
                "primary" if fn in primary_files
                else "secondary" if fn in secondary_files
                else "reference_only"
            )
            purpose = purpose_map.get(fn, f"Reference table: {fn}")

            members.append(EscoArchiveMember(
                filename=fn,
                uncompressed_bytes=uncompressed,
                compressed_bytes=compressed,
                header_columns=header_cols,
                import_tier=tier,
                purpose=purpose,
            ))

    plan = {
        "Phase 1 (Current)": "Archive verified and staged intact. Manifest inspected without full extraction.",
        "Phase 2 (Future)": "Targeted streaming extraction of primary tables (skills_en.csv, occupations_en.csv, occupationSkillRelations_en.csv, digitalSkillsCollection_en.csv) directly into SQLite reference tables.",
        "Phase 3 (Future)": "Synonym dictionary enrichment for canonical skills and transversal competency badges.",
    }

    return EscoArchiveManifest(
        archive_filename=path.name,
        archive_bytes=total_bytes,
        members_count=len(members),
        members=members,
        recommended_import_plan=plan,
    )


def ingest_esco_archive(zip_path: str | Path, store: ReferenceDataStore, *, source_version: str = "v1.2.1") -> dict[str, int]:
    """Stream the ESCO skill and occupation-skill tables into local SQLite."""
    path = Path(zip_path)
    if not path.is_file():
        raise FileNotFoundError(f"ESCO ZIP archive not found: {path}")
    manifest_path = path.parent / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        entry = next((item for item in manifest.get("datasets", []) if item.get("local_filename") == path.name), None)
        if entry:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash.casefold() != str(entry.get("sha256") or "").casefold():
                raise ValueError("ESCO archive hash does not match the local dataset manifest.")
            source_version = str(entry.get("version") or source_version)
    skill_rows: list[dict[str, Any]] = []
    relation_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        with archive.open("skills_en.csv") as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")):
                uri, label = (row.get("conceptUri") or "").strip(), (row.get("preferredLabel") or "").strip()
                if not uri or not label or (row.get("status") or "").strip().casefold() not in {"", "released"}:
                    continue
                aliases = [v.strip() for v in (row.get("altLabels") or "").split("|") if v.strip()]
                skill_rows.append({
                    "concept_uri": uri, "preferred_label": label,
                    "alt_labels": json.dumps(aliases, ensure_ascii=False),
                    "skill_type": row.get("skillType"), "reuse_level": row.get("reuseLevel"),
                    "description": row.get("description") or row.get("definition"),
                    "modified_date": row.get("modifiedDate"), "source_version": source_version,
                })
        with archive.open("occupationSkillRelations_en.csv") as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")):
                occupation_uri = (row.get("occupationUri") or "").strip()
                skill_uri = (row.get("skillUri") or "").strip()
                if not occupation_uri or not skill_uri:
                    continue
                relation_rows.append({
                    "occupation_uri": occupation_uri, "occupation_label": row.get("occupationLabel"),
                    "relation_type": row.get("relationType"), "skill_uri": skill_uri,
                    "skill_type": row.get("skillType"), "skill_label": row.get("skillLabel"),
                })
    return {
        "esco_skills": store.upsert_esco_skills(skill_rows),
        "esco_occupation_skill_relations": store.upsert_esco_occupation_skill_relations(relation_rows),
        "esco_skill_rows_valid": len(skill_rows),
        "esco_relation_rows_valid": len(relation_rows),
    }


# -----------------------------------------------------------------------------
# Ingestion Orchestration
# -----------------------------------------------------------------------------

def ingest_all_reference_datasets(
    reference_dir: str | Path,
    store: ReferenceDataStore,
) -> list[ReferenceIngestionSummary]:
    ref_path = Path(reference_dir)
    summaries: list[ReferenceIngestionSummary] = []

    esco_archive = ref_path / "ESCO dataset - v1.2.1 - classification - en - csv.zip"
    if esco_archive.is_file():
        t0 = time.perf_counter()
        counts = ingest_esco_archive(esco_archive, store)
        duration = time.perf_counter() - t0
        for dataset, source_file, valid_key, inserted_key in (
            ("esco_skills", esco_archive.name + "!skills_en.csv", "esco_skill_rows_valid", "esco_skills"),
            ("esco_occupation_skill_relations", esco_archive.name + "!occupationSkillRelations_en.csv", "esco_relation_rows_valid", "esco_occupation_skill_relations"),
        ):
            valid, inserted = counts[valid_key], counts[inserted_key]
            store.log_ingestion(dataset=dataset, source_file=source_file, rows_read=valid, rows_valid=valid,
                                rows_inserted=inserted, rows_skipped_or_duplicate=valid-inserted,
                                duration_seconds=duration)
            summaries.append(ReferenceIngestionSummary(
                dataset=dataset, source_file=source_file, rows_read=valid, rows_valid=valid,
                rows_inserted=inserted, rows_skipped_or_duplicate=valid-inserted,
                errors=[], duration_seconds=duration,
            ))

    # 1. O*NET Occupations
    occ_file = ref_path / "occupation_data.csv"
    if occ_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_onet_occupations(occ_file)
        inserted = store.upsert_onet_occupations(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="onet_occupations",
            source_file=occ_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="onet_occupations",
            source_file=occ_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    # 2. O*NET Related Occupations
    rel_file = ref_path / "related_occupations.csv"
    if rel_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_onet_related_occupations(rel_file)
        inserted = store.upsert_onet_related_occupations(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="onet_related_occupations",
            source_file=rel_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="onet_related_occupations",
            source_file=rel_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    # 3. O*NET Software Skills
    soft_file = ref_path / "software_skills.csv"
    if soft_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_onet_software_skills(soft_file)
        inserted = store.upsert_onet_software_skills(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="onet_software_skills",
            source_file=soft_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="onet_software_skills",
            source_file=soft_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    # 4. O*NET Essential Skills
    ess_file = ref_path / "essential_skills.csv"
    if ess_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_onet_essential_skills(ess_file)
        inserted = store.upsert_onet_essential_skills(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="onet_essential_skills",
            source_file=ess_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="onet_essential_skills",
            source_file=ess_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    # 5. GitHub Topics Adoption
    top_file = ref_path / "topics.csv"
    if top_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_github_topics(top_file)
        inserted = store.upsert_github_topic_adoption(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="github_topic_adoption",
            source_file=top_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="github_topic_adoption",
            source_file=top_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    # 6. GitHub Languages Adoption
    lang_file = ref_path / "languages.csv"
    if lang_file.is_file():
        t0 = time.perf_counter()
        records, errs = parse_github_languages(lang_file)
        inserted = store.upsert_github_language_adoption(records)
        dur = time.perf_counter() - t0
        skipped = len(records) - inserted
        store.log_ingestion(
            dataset="github_language_adoption",
            source_file=lang_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            duration_seconds=dur,
        )
        summaries.append(ReferenceIngestionSummary(
            dataset="github_language_adoption",
            source_file=lang_file.name,
            rows_read=len(records) + len(errs),
            rows_valid=len(records),
            rows_inserted=inserted,
            rows_skipped_or_duplicate=skipped,
            errors=errs[:10],
            duration_seconds=dur,
        ))

    return summaries

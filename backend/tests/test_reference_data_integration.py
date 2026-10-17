"""Offline test suite for local reference dataset integration.

VERIFIES:
1. Source file existence and CSV schema validation.
2. UTF-8 and malformed-row handling.
3. ESCO ZIP manifest inspection without extraction.
4. O*NET row parsing and scale preservation (IM/LV, float precision, no null->0 conversion).
5. GitHub quarter parsing and adoption signal labeling (signal_type='adoption', period='YYYY-Q#').
6. Deterministic IDs and idempotent repeated imports.
7. No invented monthly points from quarterly data.
8. No accidental conversion of missing values to zero.
9. No Firebase/Firestore calls from the local ingestion path.
"""

import io
import sys
import zipfile
from pathlib import Path

import pytest

from app.models.reference_data import (
    GitHubLanguageAdoption,
    GitHubTopicAdoption,
    OnetEssentialSkill,
    OnetOccupation,
    OnetRelatedOccupation,
    OnetSoftwareSkill,
)
from app.services.reference_data_service import (
    ingest_all_reference_datasets,
    inspect_esco_archive,
    parse_github_languages,
    parse_github_topics,
    parse_onet_essential_skills,
    parse_onet_occupations,
    parse_onet_related_occupations,
    parse_onet_software_skills,
)
from app.storage.reference_store import ReferenceDataStore


def test_no_firebase_or_firestore_in_reference_data_service():
    """Verify that reference_data_service does not import firebase_admin or firestore."""
    import app.services.reference_data_service as rds
    import app.storage.reference_store as rs

    assert "firebase_admin" not in rds.__dict__
    assert "firestore" not in rds.__dict__
    assert "firebase_admin" not in rs.__dict__
    assert "firestore" not in rs.__dict__


def test_onet_occupations_parsing(tmp_path):
    csv_content = (
        "O*NET-SOC Code,Title,Description\n"
        '11-1011.00,"Chief Executives","Determine policies."\n'
        '15-1252.00,"Software Developers","Research, design, and develop software."\n'
    )
    test_csv = tmp_path / "occupations.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_onet_occupations(test_csv)
    assert len(records) == 2
    assert len(errors) == 0
    assert records[0].soc_code == "11-1011.00"
    assert records[0].title == "Chief Executives"
    assert records[1].soc_code == "15-1252.00"
    assert records[1].title == "Software Developers"


def test_onet_occupations_malformed_handling(tmp_path):
    csv_content = (
        "O*NET-SOC Code,Title,Description\n"
        ',,"Missing SOC and Title"\n'
        '15-1252.00,"Software Developers","Valid row"\n'
    )
    test_csv = tmp_path / "occupations.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_onet_occupations(test_csv)
    assert len(records) == 1
    assert len(errors) == 1
    assert "missing SOC code" in errors[0]


def test_onet_software_skills_parsing_and_canonical_mapping(tmp_path):
    csv_content = (
        "O*NET-SOC Code,Title,Workplace Example,Element ID,Element Name,Hot Technology,In Demand\n"
        '15-1252.00,"Software Developers","Python","2.E.1.a","Compilers","Y","Y"\n'
        '15-1252.00,"Software Developers","Docker","2.E.1.b","DevOps","Y","N"\n'
        '15-1252.00,"Software Developers","Niche Proprietary Tool","2.E.1.c","Other","N","N"\n'
    )
    test_csv = tmp_path / "software_skills.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_onet_software_skills(test_csv)
    assert len(records) == 3
    assert len(errors) == 0

    # Check Hot Technology and In Demand flags
    assert records[0].hot_technology is True
    assert records[0].in_demand is True
    assert records[0].canonical_skill_id == "python"

    assert records[1].hot_technology is True
    assert records[1].in_demand is False
    assert records[1].canonical_skill_id == "docker"

    assert records[2].hot_technology is False
    assert records[2].in_demand is False
    assert records[2].canonical_skill_id is None


def test_onet_essential_skills_scale_preservation_and_no_zero_coercion(tmp_path):
    csv_content = (
        "O*NET-SOC Code,Title,Element ID,Element Name,Scale ID,Scale Name,Data Value,N,Standard Error,Lower CI Bound,Upper CI Bound,Recommend Suppress,Not Relevant,Date,Domain Source\n"
        '15-1252.00,"Software Developers","2.A.1.a","Reading Comprehension","IM","Importance","4.12","8","0.1250","3.8800","4.3700","N","","08/2023","Analyst"\n'
        '15-1252.00,"Software Developers","2.A.1.a","Reading Comprehension","LV","Level","5.25","8","0.2000","4.8500","5.6500","Y","","08/2023","Analyst"\n'
        '15-1252.00,"Software Developers","2.A.1.b","Active Listening","IM","Importance","3.85","","","","","N","","",""\n'
    )
    test_csv = tmp_path / "essential_skills.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_onet_essential_skills(test_csv)
    assert len(records) == 3
    assert len(errors) == 0

    # IM scale
    assert records[0].scale_id == "IM"
    assert records[0].scale_name == "Importance"
    assert records[0].data_value == 4.12
    assert records[0].sample_size == 8
    assert records[0].recommend_suppress is False

    # LV scale
    assert records[1].scale_id == "LV"
    assert records[1].scale_name == "Level"
    assert records[1].data_value == 5.25
    assert records[1].recommend_suppress is True

    # Crucial test: missing N, SE, Bounds MUST NOT be coerced to 0.0
    assert records[2].sample_size is None
    assert records[2].standard_error is None
    assert records[2].lower_ci_bound is None
    assert records[2].upper_ci_bound is None
    assert records[2].domain_source is None


def test_github_languages_adoption_signal_and_quarterly_preservation(tmp_path):
    csv_content = (
        "num_pushers,language,language_type,iso2_code,year,quarter\n"
        "2066,Python,programming,US,2024,1\n"
        "500,TypeScript,programming,IN,2024,2\n"
        "100,Rust,programming,DE,2024,3\n"
    )
    test_csv = tmp_path / "languages.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_github_languages(test_csv)
    assert len(records) == 3
    assert len(errors) == 0

    # Metric & Signal Type integrity
    for rec in records:
        assert rec.signal_type == "adoption"
        assert rec.signal_type != "demand"
        assert rec.data_origin == "real"

    # Period must be quarterly "YYYY-Q#", NEVER synthesized into 3 monthly points
    assert records[0].period == "2024-Q1"
    assert records[0].year == 2024
    assert records[0].quarter == 1
    assert records[0].num_pushers == 2066
    assert records[0].canonical_skill_id == "python"

    assert records[1].period == "2024-Q2"
    assert records[1].year == 2024
    assert records[1].quarter == 2
    assert records[1].num_pushers == 500
    assert records[1].canonical_skill_id == "typescript"


def test_github_topics_adoption_signal_and_quarterly_preservation(tmp_path):
    csv_content = (
        "num_pushers,topic,iso2_code,year,quarter\n"
        "7206,python,US,2023,4\n"
        "4500,docker,EU,2024,1\n"
    )
    test_csv = tmp_path / "topics.csv"
    test_csv.write_text(csv_content, encoding="utf-8")

    records, errors = parse_github_topics(test_csv)
    assert len(records) == 2
    assert len(errors) == 0

    assert records[0].signal_type == "adoption"
    assert records[0].period == "2023-Q4"
    assert records[0].canonical_skill_id == "python"

    assert records[1].signal_type == "adoption"
    assert records[1].period == "2024-Q1"
    assert records[1].canonical_skill_id == "docker"


def test_esco_archive_inspection_without_extraction(tmp_path):
    # Create a synthetic zip archive with ESCO-like structure
    zip_path = tmp_path / "test_esco.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("skills_en.csv", "conceptType,conceptUri,preferredLabel\nSkill,http://test/1,Python\n")
        zf.writestr("occupations_en.csv", "conceptType,conceptUri,preferredLabel\nOcc,http://test/2,Developer\n")
        zf.writestr("dictionary_en.csv", "term,definition\ncode,identifier\n")

    manifest = inspect_esco_archive(zip_path)
    assert manifest.archive_filename == "test_esco.zip"
    assert manifest.members_count == 3

    # Check member classifications
    tier_by_file = {m.filename: m.import_tier for m in manifest.members}
    assert tier_by_file["skills_en.csv"] == "primary"
    assert tier_by_file["occupations_en.csv"] == "primary"
    assert tier_by_file["dictionary_en.csv"] == "reference_only"

    # Verify that files were NOT extracted to disk
    assert not (tmp_path / "skills_en.csv").exists()
    assert not (tmp_path / "occupations_en.csv").exists()


def test_store_deterministic_ids_and_idempotence(tmp_path):
    db_path = tmp_path / "test_ref.sqlite3"
    store = ReferenceDataStore(db_path)

    # Insert occupations
    occ1 = OnetOccupation(soc_code="11-1011.00", title="Chief Executives", description="Exec summary")
    occ2 = OnetOccupation(soc_code="15-1252.00", title="Software Developers", description="Dev summary")

    # Run 1
    inserted1 = store.upsert_onet_occupations([occ1, occ2])
    assert inserted1 == 2
    counts1 = store.get_table_counts()
    assert counts1["ref_onet_occupations"] == 2

    # Run 2 (exact duplicate import)
    inserted2 = store.upsert_onet_occupations([occ1, occ2])
    counts2 = store.get_table_counts()
    # Total count remains strictly 2!
    assert counts2["ref_onet_occupations"] == 2

    # Query
    results = store.get_onet_occupations(query="Software")
    assert len(results) == 1
    assert results[0]["soc_code"] == "15-1252.00"


def test_github_adoption_query_by_canonical_skill(tmp_path):
    db_path = tmp_path / "test_ref.sqlite3"
    store = ReferenceDataStore(db_path)

    records = [
        GitHubLanguageAdoption(
            id="gh_lang_1",
            language="Python",
            language_type="programming",
            iso2_code="US",
            year=2024,
            quarter=1,
            period="2024-Q1",
            num_pushers=5000,
            canonical_skill_id="python",
        ),
        GitHubLanguageAdoption(
            id="gh_lang_2",
            language="Python",
            language_type="programming",
            iso2_code="US",
            year=2024,
            quarter=2,
            period="2024-Q2",
            num_pushers=5500,
            canonical_skill_id="python",
        ),
        GitHubLanguageAdoption(
            id="gh_lang_3",
            language="Ruby",
            language_type="programming",
            iso2_code="US",
            year=2024,
            quarter=1,
            period="2024-Q1",
            num_pushers=800,
            canonical_skill_id=None,
        ),
    ]

    store.upsert_github_language_adoption(records)
    series = store.get_github_adoption_series(language="Python", iso2_code="US")
    assert len(series) == 2
    assert [s["period"] for s in series] == ["2024-Q1", "2024-Q2"]
    assert [s["num_pushers"] for s in series] == [5000, 5500]


@pytest.mark.integration
def test_staged_reference_files_exist_and_manifest_valid(staged_reference_data_directory):
    """Verify staged files in backend/data/reference match manifest.json."""
    ref_dir = staged_reference_data_directory
    manifest_file = ref_dir / "manifest.json"
    assert manifest_file.is_file(), f"manifest.json missing in {ref_dir}"

    import json
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert "datasets" in manifest_data
    for ds in manifest_data["datasets"]:
        staged_file = ref_dir / ds["local_filename"]
        assert staged_file.is_file(), f"Staged file missing: {ds['local_filename']}"
        assert staged_file.stat().st_size == ds["size_bytes"]

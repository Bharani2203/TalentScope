import csv
import json
from pathlib import Path

from app.analytics.skill_registry import SKILLS
from app.services.learning_catalog_service import get_learning_catalog, get_verified_learning_videos

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_resource_manifest_paths_and_record_counts_are_valid():
    manifest = read_json(DATA_DIR / "resource_manifest.json")
    seen_paths = set()
    for dataset in manifest["datasets"]:
        assert dataset["source"] and dataset["license_attribution"] and dataset["intended_use"]
        for file_entry in dataset["files"]:
            relative_path = file_entry["path"]
            assert relative_path not in seen_paths
            seen_paths.add(relative_path)
            project_path = DATA_DIR.parents[2] / relative_path
            assert project_path.is_file(), relative_path
            assert project_path.stat().st_size == file_entry["size_bytes"], relative_path
            assert file_entry["format"] and file_entry["import_status"]
            if file_entry["format"] == "CSV":
                csv.field_size_limit(20_000_000)
                with project_path.open(encoding="utf-8-sig", newline="") as source:
                    reader = csv.DictReader(source)
                    assert reader.fieldnames and all(reader.fieldnames)
                    assert sum(1 for _ in reader) == file_entry["records"]


def test_resource_catalog_has_unique_ids_canonical_skills_and_provenance():
    catalog = get_learning_catalog()
    ids = [resource.resource_id for resource in catalog]
    assert len(ids) == len(set(ids))
    assert len(catalog) == 14
    for resource in catalog:
        assert resource.provenance and resource.license_attribution
        assert resource.verification_status == "verified_official"
        assert resource.last_verified_at
        assert all(skill_id in {skill.skill_id for skill in SKILLS} for skill_id in resource.skill_ids)


def test_curated_videos_have_verified_metadata_and_canonical_mappings():
    videos = get_verified_learning_videos()
    assert len(videos) >= 5
    assert len({video.video_id for video in videos}) == len(videos)
    canonical_ids = {skill.skill_id for skill in SKILLS}
    for video in videos:
        assert video.title and video.channel_name and video.provenance and video.license_attribution
        assert video.verification_status == "verified_youtube_listing"
        assert all(skill_id in canonical_ids for skill_id in video.skill_ids)


def test_question_bank_is_original_and_keeps_answers_and_tests_private():
    public = read_json(DATA_DIR / "question_bank" / "questions_public.json")
    answer_file = read_json(DATA_DIR / "question_bank" / "private" / "answer_keys.json")
    coding_file = read_json(DATA_DIR / "question_bank" / "private" / "coding_test_cases.json")
    questions = {question["question_id"]: question for question in public}
    answers = {answer["question_id"]: answer for answer in answer_file["answers"]}
    test_sets = {test_set["question_id"]: test_set for test_set in coding_file["test_sets"]}
    canonical_ids = {skill.skill_id for skill in SKILLS}

    assert len(public) == len(questions) == 80
    assert set(answers) == set(questions)
    assert set(test_sets) == {question_id for question_id, question in questions.items() if question["question_type"] == "coding"}
    assert answer_file["visibility"] == coding_file["visibility"] == "backend_only"
    assert {kind: sum(question["question_type"] == kind for question in public) for kind in {q["question_type"] for q in public}} == {
        "coding": 10, "mcq": 30, "scenario": 24, "practical_task": 16
    }
    for question_id, question in questions.items():
        assert question_id.startswith("ts-")
        assert question["question_type"] in {"mcq", "scenario", "coding", "practical_task"}
        assert question["difficulty"] in {"beginner", "intermediate", "advanced"}
        assert question["provenance"] and question["license"]
        assert question["verification_status"] == "draft_unreviewed"
        assert not ({"correct_answer", "explanation", "expected_output", "test_cases"} & question.keys())
        assert all(skill_id in canonical_ids for skill_id in question["skill_ids"])
        assert answers[question_id]["provenance"] and answers[question_id]["license"]
        assert answers[question_id]["correct_answer"] and answers[question_id]["explanation"]
        assert answers[question_id]["scoring_rubric"]
        if question["question_type"] == "mcq":
            option_ids = [option["option_id"] for option in question["options"]]
            assert len(option_ids) == len(set(option_ids))
            assert answers[question_id]["correct_answer"] in option_ids
    for question_id, test_set in test_sets.items():
        assert questions[question_id]["question_type"] == "coding"
        assert all(case.get("hidden") is True and "expected_output" in case for case in test_set["test_cases"])


def test_question_bank_covers_non_coding_uiux_assessment():
    public = read_json(DATA_DIR / "question_bank" / "questions_public.json")
    uiux = [question for question in public if "ui_ux" in question["skill_ids"]]
    assert len(uiux) >= 2
    assert any(question["question_type"] == "practical_task" for question in uiux)
    assert any("no code is required" in question["question_text"] for question in uiux)

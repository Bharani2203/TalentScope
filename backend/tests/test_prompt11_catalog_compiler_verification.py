from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.core.config import Settings
from app.services.code_execution_service import (
    execute_code,
    evaluate_coding_assessment,
)
from app.services.learning_catalog_service import (
    get_learning_catalog,
    get_verified_learning_videos,
)
from app.services.roadmap_service import (
    _generate_adaptive_skill_milestones,
    _generate_adaptive_role_milestones,
)


def test_catalog_verification_9_skills():
    """Verify loading, milestones, and resources for 9 core technical and design skills:
    Python, JavaScript, HTML, CSS, C, Java, SQL, UI/UX Design, Figma.
    """
    skill_definitions = [
        ("Python", "python"),
        ("JavaScript", "javascript"),
        ("HTML", "html"),
        ("CSS", "html"),
        ("C", "c"),
        ("Java", "java"),
        ("SQL", "sql"),
        ("UI/UX Design", "ui_ux"),
        ("Figma", "ui_ux"),
    ]

    catalog = get_learning_catalog()
    assert len(catalog) > 0, "Learning catalog must not be empty"

    videos = get_verified_learning_videos()
    assert len(videos) > 0, "Video catalog must not be empty"

    # Check verified videos exist for primary domains
    all_video_ids = {v.video_id for v in videos}
    expected_sample_ids = {
        "KJgsSFOSQv0",  # C
        "rfscVS0vtbw",  # Python
        "PkZNo7MFNFg",  # JavaScript
        "pQN-pnXPaVg",  # HTML/CSS
        "eIrMbAQSU34",  # Java
        "HXV3zeQKqGY",  # SQL
        "c9Wg6Cb_YlU",  # UI/UX & Figma
    }
    for sample_id in expected_sample_ids:
        assert sample_id in all_video_ids, f"Expected verified video ID {sample_id} in youtube_videos.json"

    # Verify milestone generation for all 9 skills
    for skill_name, skill_id in skill_definitions:
        milestones = _generate_adaptive_skill_milestones(
            skill_name=skill_name,
            skill_id=skill_id,
            level="beginner",
            duration_days=30,
        )
        assert len(milestones) >= 3, f"Skill {skill_name} must generate at least 3 milestones"
        for m in milestones:
            assert m["name"], f"Milestone in {skill_name} must have a name"
            assert len(m["learning_objectives"]) >= 2, f"Milestone in {skill_name} must have learning objectives"
            assert m["practice_activity"], f"Milestone in {skill_name} must have practice activity"
            assert m["completion_criterion"], f"Milestone in {skill_name} must have completion criteria"


def test_role_verification_5_roles():
    """Verify loading, milestones, aptitude prep, and mock interviews for 5 career roles:
    Full Stack Developer, AI/ML Engineer, Data Analyst, Cloud Architect, Cybersecurity Specialist.
    """
    roles = [
        "Full Stack Developer",
        "AI/ML Engineer",
        "Data Analyst",
        "Cloud Architect",
        "Cybersecurity Specialist",
    ]

    for role_name in roles:
        milestones = _generate_adaptive_role_milestones(
            role_name=role_name,
            level="beginner",
            duration_days=60,
        )
        assert len(milestones) >= 5, f"Role {role_name} must generate at least 5 stages"

        titles = [m["name"] for m in milestones]
        # Must include company recruitment / aptitude phase
        assert any("Aptitude Preparation" in t or "Recruitment" in t for t in titles), (
            f"Role {role_name} must include company recruitment & aptitude phase"
        )
        # Must include mock technical interview / simulation phase
        assert any("Mock Technical Interview" in t or "Simulation" in t for t in titles), (
            f"Role {role_name} must include mock technical interview phase"
        )

        for m in milestones:
            assert m["name"], f"Stage in {role_name} must have a title"
            assert len(m["learning_objectives"]) >= 2, f"Stage in {role_name} must have learning objectives"
            assert m["practice_activity"], f"Stage in {role_name} must have practice task"
            assert m["completion_criterion"], f"Stage in {role_name} must have completion criteria"


def test_compiler_pass_sum_array(monkeypatch):
    """Test 1: Submit correct sum_array in C -> verify output matches expected (150) and test passes."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
        compiler_timeout_seconds=5.0,
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    c_correct_code = """#include <stdio.h>
int sum_array(int arr[], int n) {
    int sum = 0;
    for (int i = 0; i < n; i++) sum += arr[i];
    return sum;
}
int main() {
    int arr[] = {10, 20, 30, 40, 50};
    printf("%d", sum_array(arr, 5));
    return 0;
}"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "run": {
            "stdout": "150\n",
            "stderr": "",
            "code": 0,
            "signal": None,
        },
        "compile": {"code": 0, "output": ""},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", c_correct_code)
        assert res.status == "success"
        assert res.stdout.strip() == "150"
        assert res.exit_code == 0


def test_compiler_fail_sum_array(monkeypatch):
    """Test 2: Submit incorrect sum_array -> verify output mismatch causes test failure."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
        compiler_timeout_seconds=5.0,
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    c_incorrect_code = """#include <stdio.h>
int sum_array(int arr[], int n) {
    return 0; // Incorrect solution
}
int main() {
    int arr[] = {10, 20, 30, 40, 50};
    printf("%d", sum_array(arr, 5));
    return 0;
}"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "run": {
            "stdout": "0\n",
            "stderr": "",
            "code": 0,
            "signal": None,
        },
        "compile": {"code": 0, "output": ""},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", c_incorrect_code)
        assert res.status == "success"
        # Output is 0, which does NOT match the expected 150
        assert res.stdout.strip() != "150"
        assert res.stdout.strip() == "0"


def test_compiler_compile_error(monkeypatch):
    """Test 3: Submit code with intentional syntax error -> verify compilation_error status and error diagnostics."""
    fake_settings = Settings(
        compiler_enabled=True,
        compiler_provider="piston",
        compiler_api_url="https://emkc.org/api/v2/piston",
        compiler_timeout_seconds=5.0,
    )
    monkeypatch.setattr("app.services.code_execution_service.get_settings", lambda: fake_settings)

    c_broken_syntax = """#include <stdio.h>
int main() {
    printf("Missing semicolon and closing brace"
"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "run": None,
        "compile": {
            "code": 1,
            "output": "solution.c: In function 'main':\nsolution.c:3:5: error: expected ')' before '}' token",
        },
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = execute_code("c", c_broken_syntax)
        assert res.status == "compilation_error"
        assert res.exit_code == 1
        assert "expected ')'" in (res.compile_output or "")

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gitignore_excludes_environment_files_but_allows_example():
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in rules
    assert ".env.*" in rules
    assert "!.env.example" in rules
    assert "**/secrets/" in rules


def test_example_has_no_provider_or_gemini_secret_values():
    example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    values = dict(
        line.split("=", 1)
        for line in example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    )
    for key in ("JSEARCH_API_KEY", "GITHUB_TOKEN", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "GEMINI_API_KEY"):
        assert values.get(key) == ""


def test_collection_admin_allowlist_was_removed_with_user_triggered_route():
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert "MARKET_COLLECTION_ADMIN_UIDS" not in config
    assert "MARKET_COLLECTION_ADMIN_UIDS" not in example

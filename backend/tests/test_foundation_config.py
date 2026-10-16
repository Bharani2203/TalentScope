from pathlib import Path

from app.core.config import Settings


def test_settings_env_path_is_absolute_and_independent_of_working_directory(monkeypatch, tmp_path):
    env_path = Path(Settings.model_config["env_file"])
    assert env_path.is_absolute()
    assert env_path.name == ".env"
    assert env_path.parent.name == "backend"

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    test_env = tmp_path / "settings.env"
    test_env.write_text(
        "ENVIRONMENT=development\nFIREBASE_PROJECT_ID=isolated-test-project\n",
        encoding="utf-8",
    )

    class IsolatedSettings(Settings):
        model_config = {**Settings.model_config, "env_file": test_env}

    monkeypatch.chdir(tmp_path)

    settings = IsolatedSettings()

    assert settings.environment == "development"
    assert settings.firebase_project_id == "isolated-test-project"

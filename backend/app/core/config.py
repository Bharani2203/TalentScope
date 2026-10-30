from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_TEST_FIREBASE_PROJECT_ID = "demo-talentscope-local"
LOCAL_TEST_FIRESTORE_EMULATOR_HOST = "127.0.0.1:8080"
LOCAL_TEST_AUTH_EMULATOR_HOST = "127.0.0.1:9099"


class Settings(BaseSettings):
    environment: str = "production"
    firebase_project_id: str = "skill-demand-forecasting"
    google_application_credentials: str | None = None
    firebase_service_account_json: str | None = None
    firebase_service_account_base64: str | None = None
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL", "SQLALCHEMY_DATABASE_URI")
    )
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    gemini_model: str = "gemini-1.5-flash"
    # Separate, opt-in provider for general guidance when a V2 result is unavailable.
    gemini_b_api_key: SecretStr | None = None
    gemini_b_model: str = "gemini-3.5-flash"
    gemini_b_backup_model: str | None = None
    # Learning roadmap enrichment is an isolated, opt-in Gemini integration.
    learning_gemini_api_key: SecretStr | None = None
    youtube_api_key: str | None = None
    learning_gemini_model: str = Field(default="gemini-3.8-flash", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    learning_gemini_request_timeout_seconds: float = Field(default=8, ge=1, le=20)
    learning_gemini_max_calls_per_minute: int = Field(default=4, ge=0, le=60)
    learning_gemini_max_calls_per_day: int = Field(default=60, ge=0, le=5000)
    learning_gemini_max_calls_per_user_per_hour: int = Field(default=3, ge=0, le=100)
    learning_gemini_max_output_tokens: int = Field(default=1200, ge=128, le=4096)
    gemini_b_request_timeout_seconds: float = Field(
        default=5,
        ge=1,
        le=15,
        validation_alias=AliasChoices("GEMINI_B_REQUEST_TIMEOUT_SECONDS", "GEMINI_B_TIMEOUT_SECONDS"),
    )
    gemini_b_max_calls_per_minute: int = Field(default=10, ge=0)
    gemini_b_max_calls_per_day: int = Field(default=100, ge=0)
    gemini_b_max_calls_per_user_per_hour: int = Field(default=10, ge=0)
    gemini_b_max_input_chars: int = Field(default=3000, ge=500, le=6000)
    gemini_b_max_output_tokens: int = Field(default=512, ge=64, le=1024)
    gemini_max_calls_per_minute: int = Field(default=60, ge=0)
    gemini_max_calls_per_day: int = Field(default=1500, ge=0)
    gemini_max_calls_per_user_per_hour: int = Field(default=30, ge=0)
    gemini_max_input_chars: int = Field(default=12000, ge=2000, le=30000)
    gemini_max_output_tokens: int = Field(default=1024, ge=64, le=2048)
    gemini_request_timeout_seconds: float = Field(default=5, ge=1, le=15)
    api_v1_prefix: str = "/api/v1"
    jsearch_api_key: str | None = None
    rapidapi_host: str = "jsearch.p.rapidapi.com"
    jsearch_timeout_seconds: float = Field(default=12.0, gt=0, le=120)
    jsearch_max_retries: int = Field(default=1, ge=0, le=3)
    jsearch_retry_backoff_seconds: float = Field(default=0.25, ge=0, le=5)
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "in"
    adzuna_timeout_seconds: float = Field(default=12.0, gt=0, le=120)
    adzuna_max_retries: int = Field(default=1, ge=0, le=3)
    adzuna_intelligence_api_key: str | None = None
    # On-demand assistant searches are opt-in; scheduled/admin collection is unchanged.
    job_search_live_enabled: bool = False
    github_token: str | None = None
    github_topic: str = "python"
    github_timeout_seconds: float = Field(default=12.0, gt=0, le=120)
    github_max_retries: int = Field(default=1, ge=0, le=2)
    skill_intelligence_db_path: str = "data/skill_intelligence.sqlite3"
    skill_intelligence_min_periods: int = Field(default=4, ge=3, le=12)
    skill_intelligence_min_forecast_periods: int = Field(default=6, ge=4, le=24)
    skill_intelligence_read_backend: Literal["sqlite", "firestore"] = "firestore"
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    # G1.7 Collection and scheduling configuration
    market_collection_cadence_hours: float = Field(default=24.0, ge=1.0, le=168.0)
    market_collection_cron: str = "15 3 * * *"
    market_collection_enabled_providers: list[str] = ["jsearch", "adzuna", "github"]
    market_collection_query: str = "software developer"
    market_collection_target_country: str = "in"
    market_collection_target_location: str | None = None
    market_collection_panel_version: str = "job-demand-v1"
    market_collection_max_pages: int = Field(default=1, ge=1, le=10)
    market_collection_historical_backfill_mode: bool = False
    market_scheduler_enabled: bool = False
    # Wikimedia Pageviews API configuration
    wikimedia_user_agent: str = "TalentScope/1.0.0 (https://github.com/akash/S7_PROJECT_SKILL_1-main; workforce-skill-intelligence)"
    wikimedia_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    wikimedia_max_retries: int = Field(default=2, ge=0, le=5)
    # Remote compiler sandbox configuration (Piston, Judge0, or JDoodle)
    compiler_enabled: bool = False
    compiler_provider: Literal["piston", "judge0", "jdoodle"] = "piston"
    compiler_api_url: str | None = None
    compiler_api_key: SecretStr | None = None
    compiler_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    jdoodle_client_id: str | None = None
    jdoodle_client_secret: SecretStr | None = None
    jdoodle_client_id_2: str | None = None
    jdoodle_client_secret_2: SecretStr | None = None
    jdoodle_client_id_3: str | None = None
    jdoodle_client_secret_3: SecretStr | None = None
    jdoodle_client_id_4: str | None = None
    jdoodle_client_secret_4: SecretStr | None = None
    jdoodle_api_url: str = "https://api.jdoodle.com/v1/execute"

    @property
    def database_path(self) -> Path:
        configured = Path(self.skill_intelligence_db_path)
        if configured.is_absolute():
            return configured
        # Anchor relative paths at the repository root; resolving against the
        # current working directory could select a different developer DB.
        repository_root = Path(__file__).resolve().parents[3]
        return repository_root / configured

    @property
    def reference_database_path(self) -> Path:
        """Path to the checked-in local reference taxonomy database.

        Market observations retain ``database_path`` and its configured write
        destination. Only the default reference store uses this local path.
        """
        configured = Path(self.skill_intelligence_db_path)
        if configured.is_absolute():
            return configured
        repository_root = Path(__file__).resolve().parents[3]
        if self.skill_intelligence_db_path == "data/skill_intelligence.sqlite3":
            return repository_root / "backend" / "data" / "skill_intelligence.sqlite3"
        return repository_root / configured

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    firebase_mode = os.getenv("TALENTSCOPE_FIREBASE_MODE", "").strip().lower()
    offline_mode = os.getenv("TALENTSCOPE_OFFLINE_TEST_MODE", "")
    local_mode_requested = offline_mode == "1" or firebase_mode not in {"", "production"}
    if local_mode_requested:
        # Never read backend/.env after local/offline mode is requested. That
        # file may contain production credentials and must not fill missing
        # local settings.
        settings = Settings(_env_file=None)
        if firebase_mode != "emulator" or offline_mode not in {"0", "1"}:
            raise RuntimeError(
                "Offline test mode requires explicit Firebase Emulator mode and TALENTSCOPE_OFFLINE_TEST_MODE=1."
            )
        if settings.environment != "local-test":
            raise RuntimeError("Firebase Emulator mode requires ENVIRONMENT=local-test.")
        if settings.firebase_project_id != LOCAL_TEST_FIREBASE_PROJECT_ID:
            raise RuntimeError("Firebase Emulator mode requires the dedicated local demo project ID.")
        if os.getenv("FIRESTORE_EMULATOR_HOST", "").strip() != LOCAL_TEST_FIRESTORE_EMULATOR_HOST:
            raise RuntimeError("Firebase Emulator mode requires the configured loopback Firestore host.")
        if os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "").strip() != LOCAL_TEST_AUTH_EMULATOR_HOST:
            raise RuntimeError("Firebase Emulator mode requires the configured loopback Auth host.")
        return settings
    return Settings()

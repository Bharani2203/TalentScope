from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "production"
    firebase_project_id: str = "skill-demand-forecasting"
    google_application_credentials: str | None = None
    gemini_api_key: SecretStr | None = None
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

    @property
    def database_path(self) -> Path:
        configured = Path(self.skill_intelligence_db_path)
        if (Path("backend") / configured).exists():
            return Path("backend") / configured
        return configured

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Typed application configuration, loaded from environment variables / .env.

`.env` lives at the repository root, but backend commands are documented to
run from `backend/` (README, scripts/) as well as from the repo root and,
for Alembic, from wherever `alembic` is invoked. A plain `env_file=".env"`
resolves relative to the process's current working directory, so it would
silently miss the repo-root `.env` whenever a command runs from `backend/`.
`_REPO_ROOT_ENV` computes the repo-root `.env` path from this file's own
location instead, so config loads consistently regardless of CWD.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# settings.py -> config/ -> wealthpilot/ -> backend/ -> repo root
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "WealthPilot AI"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # CORS — the Vite dev server's default origin.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = Field(default="")
    test_database_url: str = Field(default="")
    gemini_api_key: str = Field(default="")
    gemini_project_number: str = Field(default="")
    gemini_model: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — read once, reused across the app."""
    return Settings()

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

from pydantic import Field, SecretStr
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

    # Sensitive-data protection (ADR-047). No default key exists anywhere: an unset value means "protected storage is
    # not configured" and every protected route fails closed with 503. `SecretStr` keeps the value out of reprs/logs.
    # Format: PROTECTED_DATA_KEYS=<key_id>:<base64 of 32 random bytes>[,<key_id>:<base64>...]
    protected_data_keys: SecretStr = Field(default=SecretStr(""))
    protected_data_active_key_id: str = Field(default="")

    # Trained sentiment model (ADR-052). OFF by default: the rules baseline is the method until an approved, validated artifact exists under models/sentiment/. The numeric values are
    # strings so that an empty environment value (as in .env.example) means "not set"; `api/services/personalized_insight_service.py` parses and validates them.
    sentiment_model_enabled: bool = Field(default=False)
    sentiment_model_name: str = Field(default="")
    sentiment_model_path: str = Field(default="")          # a directory inside models/sentiment/ (relative to it, or absolute inside it); anything else is refused
    sentiment_model_version: str = Field(default="")
    sentiment_model_min_confidence: str = Field(default="")   # may only RAISE the artifact's own calibrated minimum; never invented
    sentiment_model_allow_fallback: bool = Field(default=True)
    sentiment_model_max_tokens: str = Field(default="")
    sentiment_model_device: str = Field(default="cpu")
    sentiment_model_timeout_seconds: str = Field(default="")
    # Research-only comparison of two PRETRAINED classifiers (ADR-053). OFF by default and display-only: it never replaces `user_text_rules_v1` and nothing financial reads it. Even when
    # switched on it runs only for a candidate whose licence is verified in code AND whose safetensors weights were placed, with a manifest, under models/sentiment_pretrained/<key>/ by an operator.
    sentiment_transformers_enabled: bool = Field(default=False)
    sentiment_transformers_max_tokens: str = Field(default="")
    sentiment_transformers_timeout_seconds: str = Field(default="")
    sentiment_transformers_device: str = Field(default="cpu")
    sentiment_transformers_threads: str = Field(default="")      # optional torch thread cap (1-64); blank leaves torch's own default untouched (ADR-055)
    # DEMO_MODE_ENABLED: serves FICTIONAL, fixed demonstration data from `POST /api/demo/financial-behaviour` for the Financial Behaviour & Sentiment page. It never touches the database, a
    # customer record, any record store or any model, and it is OFF unless a developer switches it on. Production leaves it false (the route then answers 404).
    demo_mode_enabled: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — read once, reused across the app."""
    return Settings()

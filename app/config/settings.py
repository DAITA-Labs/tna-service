"""Typed application config via pydantic-settings.

Env files are layered (highest priority first):
  .env.{APP_ENV}.local > .env.{APP_ENV} > .env.local > .env

`get_settings()` returns a cached singleton — call from anywhere in the service.
"""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.enums.environment import Environment


def _candidate_env_files() -> list[str]:
    """Return existing env files in priority order (highest first)."""
    app_env = os.getenv("APP_ENV", "development").lower()
    # Climb from this file: app/config/settings.py -> app/config -> app -> tna-service
    base = Path(__file__).resolve().parents[2]
    candidates = [
        base / f".env.{app_env}.local",
        base / f".env.{app_env}",
        base / ".env.local",
        base / ".env",
    ]
    return [str(p) for p in candidates if p.exists()]


class Settings(BaseSettings):
    """Typed config. Read once via `get_settings()`."""

    model_config = SettingsConfigDict(
        env_file=_candidate_env_files(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"

    anthropic_api_key: str = Field(default="", min_length=0)
    anthropic_model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.0
    retry_limit: int = 1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""Tuning base class plus pipeline-level cross-agent knobs."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Tuning(BaseSettings):
    """Base class for every tuning block — per-agent and pipeline-level."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class PipelineTuning(Tuning):
    """Cross-agent thresholds shared by every component of the extract pipeline."""

    extract_confidence_gate: float = 0.85
    coverage_floor: float = 0.80
    dropout_floor: float = 0.50

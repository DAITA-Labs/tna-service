"""FIELD_NAMER prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import FIELD_NAMER
from app.prompts.field_namer import FIELD_NAMER as FIELD_NAMER_DIRECT


def test_field_namer_prompt_importable_from_package() -> None:
    assert FIELD_NAMER is FIELD_NAMER_DIRECT


def test_field_namer_prompt_contains_role_heading() -> None:
    assert "FieldNamer" in FIELD_NAMER


def test_field_namer_prompt_mentions_io_number() -> None:
    assert "io_number" in FIELD_NAMER


def test_field_namer_prompt_mentions_stage_names() -> None:
    assert "stage_names" in FIELD_NAMER


def test_field_namer_prompt_mentions_ignore() -> None:
    assert "ignore" in FIELD_NAMER

"""LAYOUT_HINTER prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import LAYOUT_HINTER
from app.prompts.layout_hinter import LAYOUT_HINTER as LAYOUT_HINTER_DIRECT


def test_layout_hinter_prompt_importable_from_package() -> None:
    assert LAYOUT_HINTER is LAYOUT_HINTER_DIRECT


def test_layout_hinter_prompt_contains_role_heading() -> None:
    assert "LayoutHinter" in LAYOUT_HINTER


def test_layout_hinter_prompt_mentions_identity_column() -> None:
    assert "identity_column" in LAYOUT_HINTER


def test_layout_hinter_prompt_mentions_pli_mode() -> None:
    assert "pli_mode" in LAYOUT_HINTER

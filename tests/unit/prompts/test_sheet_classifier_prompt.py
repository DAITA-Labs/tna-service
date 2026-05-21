"""SHEET_CLASSIFIER prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import SHEET_CLASSIFIER
from app.prompts.sheet_classifier import SHEET_CLASSIFIER as SHEET_CLASSIFIER_DIRECT


def test_sheet_classifier_prompt_importable_from_package() -> None:
    assert SHEET_CLASSIFIER is SHEET_CLASSIFIER_DIRECT


def test_sheet_classifier_prompt_contains_role_heading() -> None:
    assert "SheetClassifier" in SHEET_CLASSIFIER


def test_sheet_classifier_prompt_mentions_relevant_sheets() -> None:
    assert "relevant_sheets" in SHEET_CLASSIFIER

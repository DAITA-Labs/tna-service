"""IDENTIFIER_FINDING_JUDGE prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import IDENTIFIER_FINDING_JUDGE
from app.prompts.judges.identifier_finding import (
    IDENTIFIER_FINDING_JUDGE as DIRECT,
)


def test_prompt_importable_from_package() -> None:
    assert IDENTIFIER_FINDING_JUDGE is DIRECT


def test_prompt_contains_role_heading() -> None:
    assert "IdentifierFindingJudge" in IDENTIFIER_FINDING_JUDGE


def test_prompt_names_three_decisions() -> None:
    for decision in ("keep", "drop", "rewrite"):
        assert decision in IDENTIFIER_FINDING_JUDGE


def test_prompt_mentions_alternative_coord() -> None:
    assert "alternative_coord" in IDENTIFIER_FINDING_JUDGE


def test_prompt_references_spec_snippet_and_excerpt() -> None:
    assert "spec_snippet" in IDENTIFIER_FINDING_JUDGE
    assert "sheet_excerpt" in IDENTIFIER_FINDING_JUDGE

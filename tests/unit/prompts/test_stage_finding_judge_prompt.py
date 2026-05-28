"""STAGE_FINDING_JUDGE prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import STAGE_FINDING_JUDGE
from app.prompts.judges.stage_finding import STAGE_FINDING_JUDGE as DIRECT


def test_prompt_importable_from_package() -> None:
    assert STAGE_FINDING_JUDGE is DIRECT


def test_prompt_contains_role_heading() -> None:
    assert "StageFindingJudge" in STAGE_FINDING_JUDGE


def test_prompt_names_three_decisions() -> None:
    for decision in ("keep", "drop", "rewrite"):
        assert decision in STAGE_FINDING_JUDGE


def test_prompt_mentions_stage_specs_and_aliases() -> None:
    assert "STAGE_SPECS" in STAGE_FINDING_JUDGE
    assert "aliases" in STAGE_FINDING_JUDGE


def test_prompt_mentions_alternative_canonical() -> None:
    assert "alternative_canonical" in STAGE_FINDING_JUDGE

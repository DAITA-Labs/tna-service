"""STAGE_PHASE_JUDGE prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import STAGE_PHASE_JUDGE
from app.prompts.judges.stage_phase import STAGE_PHASE_JUDGE as DIRECT


def test_prompt_importable_from_package() -> None:
    assert STAGE_PHASE_JUDGE is DIRECT


def test_prompt_contains_role_heading() -> None:
    assert "StagePhaseJudge" in STAGE_PHASE_JUDGE


def test_prompt_describes_three_decisions() -> None:
    for decision in ("keep", "drop", "rewrite"):
        assert decision in STAGE_PHASE_JUDGE


def test_prompt_mentions_raw_stages_and_audits() -> None:
    assert "raw_stages_per_row" in STAGE_PHASE_JUDGE
    assert "audits" in STAGE_PHASE_JUDGE


def test_prompt_mentions_stage_specs() -> None:
    assert "STAGE_SPECS" in STAGE_PHASE_JUDGE


def test_prompt_requires_unique_pair() -> None:
    assert "unique" in STAGE_PHASE_JUDGE.lower()

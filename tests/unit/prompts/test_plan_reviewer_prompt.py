"""PLAN_REVIEWER prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import PLAN_REVIEWER
from app.prompts.plan_reviewer import PLAN_REVIEWER as PLAN_REVIEWER_DIRECT


def test_plan_reviewer_prompt_importable_from_package() -> None:
    assert PLAN_REVIEWER is PLAN_REVIEWER_DIRECT


def test_plan_reviewer_prompt_contains_role_heading() -> None:
    assert "PlanReviewer" in PLAN_REVIEWER


def test_plan_reviewer_prompt_mentions_row_corrections() -> None:
    assert "row_corrections" in PLAN_REVIEWER


def test_plan_reviewer_prompt_mentions_verdict() -> None:
    assert "verdict" in PLAN_REVIEWER

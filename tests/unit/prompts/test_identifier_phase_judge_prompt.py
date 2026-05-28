"""IDENTIFIER_PHASE_JUDGE prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import IDENTIFIER_PHASE_JUDGE
from app.prompts.judges.identifier_phase import IDENTIFIER_PHASE_JUDGE as DIRECT


def test_prompt_importable_from_package() -> None:
    assert IDENTIFIER_PHASE_JUDGE is DIRECT


def test_prompt_contains_role_heading() -> None:
    assert "IdentifierPhaseJudge" in IDENTIFIER_PHASE_JUDGE


def test_prompt_describes_three_decisions() -> None:
    for decision in ("keep", "drop", "rewrite"):
        assert decision in IDENTIFIER_PHASE_JUDGE


def test_prompt_mentions_raw_findings_and_audits() -> None:
    assert "raw_findings" in IDENTIFIER_PHASE_JUDGE
    assert "audits" in IDENTIFIER_PHASE_JUDGE


def test_prompt_mentions_cardinality() -> None:
    assert "cardinality" in IDENTIFIER_PHASE_JUDGE.lower()


def test_prompt_requires_unique_finding_index() -> None:
    assert "unique" in IDENTIFIER_PHASE_JUDGE.lower()

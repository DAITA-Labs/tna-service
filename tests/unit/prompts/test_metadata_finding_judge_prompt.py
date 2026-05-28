"""METADATA_FINDING_JUDGE prompt is importable and contains expected keywords."""
from __future__ import annotations

from app.prompts import METADATA_FINDING_JUDGE
from app.prompts.judges.metadata import METADATA_FINDING_JUDGE as DIRECT


def test_prompt_importable_from_package() -> None:
    assert METADATA_FINDING_JUDGE is DIRECT


def test_prompt_contains_role_heading() -> None:
    assert "MetadataFindingJudge" in METADATA_FINDING_JUDGE


def test_prompt_names_three_decisions() -> None:
    for decision in ("keep", "drop", "rewrite"):
        assert decision in METADATA_FINDING_JUDGE


def test_prompt_mentions_metadata_specs() -> None:
    assert "METADATA_SPECS" in METADATA_FINDING_JUDGE


def test_prompt_prefers_keep_for_open_vocab() -> None:
    """The prompt explicitly leans toward `keep` since metadata is open-vocab."""
    assert "open-vocab" in METADATA_FINDING_JUDGE.lower() or \
           "prefer `keep`" in METADATA_FINDING_JUDGE.lower()

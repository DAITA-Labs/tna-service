"""Schema-shape tests for FindingForJudge and IdentifierVerdict."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.judges.identifier_finding.schema import (
    FindingForJudge,
    IdentifierVerdict,
)
from app.artifacts.finding import Confidence, Finding


def _finding(canonical: str = "io_number") -> Finding:
    return Finding(
        canonical=canonical, label_coord=("A", 2),
        value_coord=("A", 3), value="IO-1",
        confidence=Confidence.LOW, evidence=["TABULAR_HEADER_MATCH"],
    )


# ─── FindingForJudge ─────────────────────────────────────────────────────


def test_finding_for_judge_minimal_inputs() -> None:
    """Only the finding + excerpt + spec snippet are mandatory."""
    payload = FindingForJudge(
        finding=_finding(),
        sheet_excerpt="A3: IO-1",
        spec_snippet="io_number — primary order identifier",
    )
    assert payload.alternative_candidates == []
    assert payload.validator_warnings == []
    assert payload.cluster_context == ""


def test_finding_for_judge_accepts_alternatives_and_warnings() -> None:
    """Optional fields populate cleanly."""
    payload = FindingForJudge(
        finding=_finding(),
        sheet_excerpt="...",
        spec_snippet="...",
        alternative_candidates=[_finding("style_code")],
        cluster_context="cluster_id=c0 sheet=Plan",
    )
    assert payload.alternative_candidates[0].canonical == "style_code"
    assert "cluster_id" in payload.cluster_context


# ─── IdentifierVerdict ────────────────────────────────────────────────────


def test_verdict_keep_with_no_coord_is_valid() -> None:
    v = IdentifierVerdict(decision="keep", reason="value matches spec", confidence="high")
    assert v.alternative_coord is None


def test_verdict_rewrite_with_coord_is_valid() -> None:
    v = IdentifierVerdict(
        decision="rewrite", alternative_coord=("B", 3),
        reason="header on B reads STYLE NO", confidence="medium",
    )
    assert v.alternative_coord == ("B", 3)


def test_verdict_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        IdentifierVerdict(decision="maybe", reason="x", confidence="high")


def test_verdict_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        IdentifierVerdict(decision="keep", reason="x", confidence="extreme")


def test_verdict_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        IdentifierVerdict(decision="keep", reason="", confidence="high")


def test_verdict_carries_decision_notes() -> None:
    """AgentOutput's decision_notes field is inherited."""
    v = IdentifierVerdict(
        decision="keep", reason="x", confidence="high",
        decision_notes="Long-form reasoning here.",
    )
    assert v.decision_notes == "Long-form reasoning here."

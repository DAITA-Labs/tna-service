"""Schema tests for IdentifierPhaseForJudge + IdentifierPhaseVerdict."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.judges.identifier_phase.schema import (
    FindingDecision,
    IdentifierPhaseForJudge,
    IdentifierPhaseVerdict,
)


def test_inputs_minimal_construction() -> None:
    p = IdentifierPhaseForJudge(raw_findings=[])
    assert p.audits == []
    assert p.warnings == []


def test_decision_keep_no_coord() -> None:
    d = FindingDecision(finding_index=0, decision="keep", reason="x")
    assert d.alternative_coord is None


def test_decision_rewrite_with_coord() -> None:
    d = FindingDecision(finding_index=2, decision="rewrite",
                          alternative_coord=("B", 3), reason="x")
    assert d.alternative_coord == ("B", 3)


def test_decision_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        FindingDecision(finding_index=0, decision="maybe", reason="x")


def test_decision_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        FindingDecision(finding_index=0, decision="keep", reason="")


def test_verdict_with_no_decisions_is_valid() -> None:
    v = IdentifierPhaseVerdict(decisions=[], summary="nothing to change", confidence="high")
    assert v.decisions == []


def test_verdict_requires_summary() -> None:
    with pytest.raises(ValidationError):
        IdentifierPhaseVerdict(decisions=[], summary="", confidence="high")

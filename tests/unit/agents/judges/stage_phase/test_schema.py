"""Schema tests for StagePhaseForJudge + StagePhaseVerdict."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.judges.stage_phase.schema import (
    StageDecision,
    StagePhaseForJudge,
    StagePhaseVerdict,
)


def test_inputs_minimal_construction() -> None:
    p = StagePhaseForJudge(raw_stages_per_row={})
    assert p.audits == []
    assert p.warnings == []


def test_decision_keep_no_canonical() -> None:
    d = StageDecision(row=3, stage_index=0, decision="keep", reason="x")
    assert d.alternative_canonical is None


def test_decision_rewrite_with_canonical() -> None:
    d = StageDecision(row=3, stage_index=0, decision="rewrite",
                       alternative_canonical="fabric", reason="x")
    assert d.alternative_canonical == "fabric"


def test_decision_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        StageDecision(row=3, stage_index=0, decision="maybe", reason="x")


def test_decision_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        StageDecision(row=3, stage_index=0, decision="keep", reason="")


def test_verdict_requires_summary() -> None:
    with pytest.raises(ValidationError):
        StagePhaseVerdict(decisions=[], summary="", confidence="high")

"""Schema-shape tests for StageFindingForJudge + StageVerdict."""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.agents.judges.stage_finding.schema import StageFindingForJudge, StageVerdict
from app.specs.schemas import FinalStage


def _stage(**overrides):
    base = dict(
        name="Sample Inspection",
        canonical=None,
        plan_date=dt.date(2026, 5, 1),
        plan_date_col=4,
        column_range=(4, 6),
        stage_metadata={},
    )
    base.update(overrides)
    return FinalStage(**base)


def test_finding_for_judge_minimal_inputs() -> None:
    p = StageFindingForJudge(stage=_stage(), row=3,
                              stage_catalog="catalog", sheet_excerpt="...")
    assert p.cluster_context == ""


def test_verdict_keep_no_canonical() -> None:
    v = StageVerdict(decision="keep", reason="genuinely novel", confidence="high")
    assert v.alternative_canonical is None


def test_verdict_rewrite_with_canonical() -> None:
    v = StageVerdict(decision="rewrite", alternative_canonical="fabric",
                      reason="alias matches", confidence="high")
    assert v.alternative_canonical == "fabric"


def test_verdict_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        StageVerdict(decision="maybe", reason="x", confidence="high")


def test_verdict_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        StageVerdict(decision="keep", reason="x", confidence="???")


def test_verdict_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        StageVerdict(decision="keep", reason="", confidence="high")

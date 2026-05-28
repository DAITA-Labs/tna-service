"""validate_stage_phase_verdict — catalog membership + cross-decision invariants."""
from __future__ import annotations

from app.agents.judges.stage_phase.schema import (
    StageDecision,
    StagePhaseVerdict,
)
from app.agents.judges.stage_phase.validators import validate_stage_phase_verdict


def _verdict(decisions: list[StageDecision], summary: str = "ok") -> StagePhaseVerdict:
    return StagePhaseVerdict(decisions=decisions, summary=summary, confidence="medium")


def test_empty_decisions_passes() -> None:
    assert validate_stage_phase_verdict(_verdict([]), ctx=None).is_ok


def test_single_keep_passes() -> None:
    v = _verdict([StageDecision(row=3, stage_index=0, decision="keep", reason="x")])
    assert validate_stage_phase_verdict(v, ctx=None).is_ok


def test_single_rewrite_with_valid_canonical_passes() -> None:
    v = _verdict([StageDecision(row=3, stage_index=0, decision="rewrite",
                                   alternative_canonical="fabric", reason="x")])
    assert validate_stage_phase_verdict(v, ctx=None).is_ok


def test_rewrite_without_canonical_retries() -> None:
    v = _verdict([StageDecision(row=3, stage_index=0, decision="rewrite", reason="x")])
    out = validate_stage_phase_verdict(v, ctx=None)
    assert out.is_retry
    assert "alternative_canonical" in out.reason


def test_rewrite_with_hallucinated_canonical_retries() -> None:
    v = _verdict([StageDecision(row=3, stage_index=0, decision="rewrite",
                                   alternative_canonical="made_up_stage", reason="x")])
    out = validate_stage_phase_verdict(v, ctx=None)
    assert out.is_retry
    assert "STAGE_SPECS" in out.reason


def test_keep_with_canonical_retries() -> None:
    v = _verdict([StageDecision(row=3, stage_index=0, decision="keep",
                                   alternative_canonical="fabric", reason="x")])
    out = validate_stage_phase_verdict(v, ctx=None)
    assert out.is_retry


def test_duplicate_row_index_pair_retries() -> None:
    v = _verdict([
        StageDecision(row=3, stage_index=0, decision="keep", reason="x"),
        StageDecision(row=3, stage_index=0, decision="drop", reason="y"),
    ])
    out = validate_stage_phase_verdict(v, ctx=None)
    assert out.is_retry
    assert "more than one" in out.reason


def test_same_index_in_different_rows_passes() -> None:
    """(3, 0) and (5, 0) are different keys."""
    v = _verdict([
        StageDecision(row=3, stage_index=0, decision="keep", reason="x"),
        StageDecision(row=5, stage_index=0, decision="keep", reason="y"),
    ])
    assert validate_stage_phase_verdict(v, ctx=None).is_ok

"""validate_identifier_phase_verdict — cross-decision invariants."""
from __future__ import annotations

from app.agents.judges.identifier_phase.schema import (
    FindingDecision,
    IdentifierPhaseVerdict,
)
from app.agents.judges.identifier_phase.validators import (
    validate_identifier_phase_verdict,
)


def _verdict(decisions: list[FindingDecision], summary: str = "ok") -> IdentifierPhaseVerdict:
    return IdentifierPhaseVerdict(decisions=decisions, summary=summary, confidence="medium")


def test_empty_decisions_passes() -> None:
    assert validate_identifier_phase_verdict(_verdict([]), ctx=None).is_ok


def test_single_keep_passes() -> None:
    v = _verdict([FindingDecision(finding_index=0, decision="keep", reason="x")])
    assert validate_identifier_phase_verdict(v, ctx=None).is_ok


def test_single_rewrite_with_coord_passes() -> None:
    v = _verdict([FindingDecision(finding_index=1, decision="rewrite",
                                     alternative_coord=("B", 3), reason="x")])
    assert validate_identifier_phase_verdict(v, ctx=None).is_ok


def test_rewrite_without_coord_retries() -> None:
    v = _verdict([FindingDecision(finding_index=0, decision="rewrite", reason="x")])
    out = validate_identifier_phase_verdict(v, ctx=None)
    assert out.is_retry
    assert "alternative_coord" in out.reason


def test_keep_with_coord_retries() -> None:
    v = _verdict([FindingDecision(finding_index=0, decision="keep",
                                     alternative_coord=("B", 3), reason="x")])
    out = validate_identifier_phase_verdict(v, ctx=None)
    assert out.is_retry


def test_duplicate_finding_index_retries() -> None:
    """Each finding may get at most one phase decision."""
    v = _verdict([
        FindingDecision(finding_index=0, decision="keep", reason="x"),
        FindingDecision(finding_index=0, decision="drop", reason="y"),
    ])
    out = validate_identifier_phase_verdict(v, ctx=None)
    assert out.is_retry
    assert "more than one" in out.reason


def test_unique_indices_pass() -> None:
    v = _verdict([
        FindingDecision(finding_index=0, decision="keep", reason="x"),
        FindingDecision(finding_index=2, decision="drop", reason="y"),
        FindingDecision(finding_index=5, decision="rewrite",
                          alternative_coord=("C", 4), reason="z"),
    ])
    assert validate_identifier_phase_verdict(v, ctx=None).is_ok

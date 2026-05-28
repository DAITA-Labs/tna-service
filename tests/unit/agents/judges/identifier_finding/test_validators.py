"""validate_identifier_verdict — cross-field semantic checks."""
from __future__ import annotations

from app.agents.judges.identifier_finding.schema import IdentifierVerdict
from app.agents.judges.identifier_finding.validators import validate_identifier_verdict


def test_keep_without_coord_passes() -> None:
    v = IdentifierVerdict(decision="keep", reason="x", confidence="high")
    assert validate_identifier_verdict(v, ctx=None).is_ok


def test_drop_without_coord_passes() -> None:
    v = IdentifierVerdict(decision="drop", reason="x", confidence="medium")
    assert validate_identifier_verdict(v, ctx=None).is_ok


def test_rewrite_with_coord_passes() -> None:
    v = IdentifierVerdict(
        decision="rewrite", alternative_coord=("B", 3),
        reason="x", confidence="medium",
    )
    assert validate_identifier_verdict(v, ctx=None).is_ok


def test_rewrite_without_coord_retries() -> None:
    """The LLM said rewrite but didn't point to a cell → semantic retry."""
    v = IdentifierVerdict(decision="rewrite", reason="x", confidence="medium")
    verdict = validate_identifier_verdict(v, ctx=None)
    assert verdict.is_retry
    assert "alternative_coord" in verdict.reason


def test_keep_with_coord_retries() -> None:
    """keep + coord is contradictory; semantic retry."""
    v = IdentifierVerdict(
        decision="keep", alternative_coord=("B", 3),
        reason="x", confidence="high",
    )
    verdict = validate_identifier_verdict(v, ctx=None)
    assert verdict.is_retry
    assert "keep" in verdict.reason


def test_drop_with_coord_retries() -> None:
    v = IdentifierVerdict(
        decision="drop", alternative_coord=("B", 3),
        reason="x", confidence="low",
    )
    verdict = validate_identifier_verdict(v, ctx=None)
    assert verdict.is_retry
    assert "drop" in verdict.reason

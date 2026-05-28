"""validate_stage_verdict — catalog membership + cross-field invariants."""
from __future__ import annotations

from app.agents.judges.stage_finding.schema import StageVerdict
from app.agents.judges.stage_finding.validators import validate_stage_verdict


def test_keep_without_canonical_passes() -> None:
    v = StageVerdict(decision="keep", reason="x", confidence="high")
    assert validate_stage_verdict(v, ctx=None).is_ok


def test_drop_without_canonical_passes() -> None:
    v = StageVerdict(decision="drop", reason="x", confidence="medium")
    assert validate_stage_verdict(v, ctx=None).is_ok


def test_rewrite_with_valid_canonical_passes() -> None:
    v = StageVerdict(decision="rewrite", alternative_canonical="fabric",
                      reason="x", confidence="high")
    assert validate_stage_verdict(v, ctx=None).is_ok


def test_rewrite_without_canonical_retries() -> None:
    v = StageVerdict(decision="rewrite", reason="x", confidence="high")
    out = validate_stage_verdict(v, ctx=None)
    assert out.is_retry
    assert "alternative_canonical" in out.reason


def test_rewrite_with_hallucinated_canonical_retries() -> None:
    """A canonical the LLM made up isn't in STAGE_SPECS — semantic retry."""
    v = StageVerdict(decision="rewrite", alternative_canonical="totally_made_up_stage",
                      reason="x", confidence="high")
    out = validate_stage_verdict(v, ctx=None)
    assert out.is_retry
    assert "not in STAGE_SPECS" in out.reason


def test_keep_with_canonical_retries() -> None:
    v = StageVerdict(decision="keep", alternative_canonical="fabric",
                      reason="x", confidence="high")
    out = validate_stage_verdict(v, ctx=None)
    assert out.is_retry
    assert "keep" in out.reason


def test_drop_with_canonical_retries() -> None:
    v = StageVerdict(decision="drop", alternative_canonical="fabric",
                      reason="x", confidence="medium")
    out = validate_stage_verdict(v, ctx=None)
    assert out.is_retry
    assert "drop" in out.reason

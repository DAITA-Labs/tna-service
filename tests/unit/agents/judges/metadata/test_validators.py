"""validate_metadata_verdict — catalog membership + cross-field invariants."""
from __future__ import annotations

from app.agents.judges.metadata.schema import MetadataVerdict
from app.agents.judges.metadata.validators import validate_metadata_verdict


def test_keep_without_canonical_passes() -> None:
    v = MetadataVerdict(decision="keep", reason="x", confidence="medium")
    assert validate_metadata_verdict(v, ctx=None).is_ok


def test_drop_without_canonical_passes() -> None:
    v = MetadataVerdict(decision="drop", reason="x", confidence="medium")
    assert validate_metadata_verdict(v, ctx=None).is_ok


def test_rewrite_with_valid_canonical_passes() -> None:
    v = MetadataVerdict(decision="rewrite", alternative_canonical="buyer",
                          reason="x", confidence="high")
    assert validate_metadata_verdict(v, ctx=None).is_ok


def test_rewrite_without_canonical_retries() -> None:
    v = MetadataVerdict(decision="rewrite", reason="x", confidence="high")
    assert validate_metadata_verdict(v, ctx=None).is_retry


def test_rewrite_with_hallucinated_canonical_retries() -> None:
    v = MetadataVerdict(decision="rewrite", alternative_canonical="invented_canonical",
                          reason="x", confidence="high")
    out = validate_metadata_verdict(v, ctx=None)
    assert out.is_retry
    assert "METADATA_SPECS" in out.reason


def test_keep_with_canonical_retries() -> None:
    v = MetadataVerdict(decision="keep", alternative_canonical="buyer",
                          reason="x", confidence="high")
    out = validate_metadata_verdict(v, ctx=None)
    assert out.is_retry


def test_drop_with_canonical_retries() -> None:
    v = MetadataVerdict(decision="drop", alternative_canonical="buyer",
                          reason="x", confidence="medium")
    out = validate_metadata_verdict(v, ctx=None)
    assert out.is_retry

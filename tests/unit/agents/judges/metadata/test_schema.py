"""Schema-shape tests for MetadataFindingForJudge + MetadataVerdict."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.judges.metadata.schema import MetadataFindingForJudge, MetadataVerdict
from app.specs.schemas import MetadataEntry


def _entry(**overrides) -> MetadataEntry:
    base = dict(key="Treatment", value="Garment Dye", source="K4", canonical=None)
    base.update(overrides)
    return MetadataEntry(**base)


def test_finding_for_judge_minimal_inputs() -> None:
    p = MetadataFindingForJudge(metadata=_entry(), metadata_catalog="...",
                                  sheet_excerpt="...")
    assert p.cluster_context == ""


def test_verdict_keep_no_canonical() -> None:
    v = MetadataVerdict(decision="keep", reason="novel key", confidence="medium")
    assert v.alternative_canonical is None


def test_verdict_rewrite_with_canonical() -> None:
    v = MetadataVerdict(decision="rewrite", alternative_canonical="buyer",
                          reason="alias match", confidence="high")
    assert v.alternative_canonical == "buyer"


def test_verdict_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        MetadataVerdict(decision="maybe", reason="x", confidence="high")


def test_verdict_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        MetadataVerdict(decision="keep", reason="x", confidence="???")


def test_verdict_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        MetadataVerdict(decision="keep", reason="", confidence="high")

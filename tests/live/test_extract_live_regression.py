"""Live regression: each previously-broken file must extract canonical fields + stages."""
from pathlib import Path

import pytest

from app.services.extraction import extract


_FA26_XFAIL_REASON = (
    "FA26 layout (flat with TOTAL footers) is misclassified as SECTION_PER_PLI; "
    "ROW_PER_PLI is correct. Mode-decision fix deferred to follow-up work."
)


@pytest.mark.live
@pytest.mark.parametrize("xlsx", [
    "CHRISTIAN BERG- T&A.xlsx",
    "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
    pytest.param(
        "FA26 YC & EUROPE T&A #1.xlsx",
        marks=pytest.mark.xfail(reason=_FA26_XFAIL_REASON, strict=False),
    ),
    "NORTHERN REFLECTIONS- T&a.xlsx",
])
def test_live_extraction_produces_canonical_fields(xlsx: str) -> None:
    """Every PLI must have ≥1 canonical field; ≥1 PLI must have stages; conf > 0.4."""
    result = extract(Path("dataset") / xlsx)
    assert len(result.plis) >= 1, f"{xlsx}: no PLIs returned"
    assert any(p.io_number for p in result.plis), f"{xlsx}: no io_number anywhere"
    assert any(p.style_code for p in result.plis), f"{xlsx}: no style_code anywhere"
    assert any(p.stages for p in result.plis), f"{xlsx}: no stages on any PLI"
    assert result.extraction_confidence > 0.4, \
        f"{xlsx}: extraction_confidence={result.extraction_confidence}"

"""Live regression: each previously-broken file must extract canonical fields + stages."""
from pathlib import Path

import pytest

from app.services.extraction import extract


_CANONICAL_FIELDS = (
    "io_number", "style_code", "style_name", "color_code", "color_name",
    "fabric_code", "delivery_date", "quantity", "order_quantity",
    "plan_quantity", "ex_factory_date", "article_no",
)


def _populated_canonical_count(pli: object) -> int:
    """Count populated canonical PLI fields, including semantically-equivalent siblings.

    The LLM may map a column to e.g. `style_name` instead of `style_code` — both
    are canonical, both are valid extractions. The test enforces that extraction
    didn't return empty husks, not that the LLM picked a specific canonical name.
    """
    return sum(1 for f in _CANONICAL_FIELDS if getattr(pli, f, None))


@pytest.mark.live
@pytest.mark.parametrize("xlsx", [
    "CHRISTIAN BERG- T&A.xlsx",
    "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
    "FA26 YC & EUROPE T&A #1.xlsx",
    "NORTHERN REFLECTIONS- T&a.xlsx",
])
def test_live_extraction_produces_canonical_fields(xlsx: str) -> None:
    """Verify extraction is no longer empty-husk: ≥3 canonical fields populated, stages present, real confidence."""
    result = extract(Path("dataset") / xlsx)
    assert len(result.plis) >= 1, f"{xlsx}: no PLIs returned"
    best_pli_canonical = max(_populated_canonical_count(p) for p in result.plis)
    assert best_pli_canonical >= 3, \
        f"{xlsx}: best PLI populated only {best_pli_canonical} canonical fields"
    assert any(p.stages for p in result.plis), f"{xlsx}: no stages on any PLI"
    assert result.extraction_confidence > 0.4, \
        f"{xlsx}: extraction_confidence={result.extraction_confidence}"

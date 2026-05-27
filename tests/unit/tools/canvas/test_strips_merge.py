"""MergeSpan / NonMergedStrip / MergedColumnStrip detectors."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import MergedColumnStrip, MergeSpan, NonMergedStrip
from app.tools.canvas.build import build_canvas
from app.tools.canvas.strips_merge import (
    find_merge_spans,
    find_merged_column_strips,
    find_non_merged_strips_horizontal,
    find_non_merged_strips_vertical,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN has 31 merge ranges (header bands + identifier carry)."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_merge_spans_returned_as_records(dkn_canvas) -> None:
    """find_merge_spans returns one MergeSpan per merge_ranges entry."""
    spans = find_merge_spans(dkn_canvas)
    assert all(isinstance(s, MergeSpan) for s in spans)
    assert len(spans) == len(dkn_canvas.merge_ranges)


def test_merge_span_orientations_are_valid(dkn_canvas) -> None:
    """Every MergeSpan has orientation horizontal / vertical / block."""
    spans = find_merge_spans(dkn_canvas)
    for s in spans:
        assert s.orientation in ("horizontal", "vertical", "block")


def test_merge_span_orientation_classification() -> None:
    """Orientation classification follows row × col dimensions."""
    from app.tools.canvas.strips_merge import _classify_orientation

    # 1 row × N cols → horizontal
    assert _classify_orientation(1, 1, 1, 5) == "horizontal"
    # N rows × 1 col → vertical
    assert _classify_orientation(1, 1, 5, 1) == "vertical"
    # M rows × N cols → block
    assert _classify_orientation(1, 1, 3, 3) == "block"


def test_non_merged_strips_vertical(dkn_canvas) -> None:
    """Non-merged columns are reported as vertical NonMergedStrips."""
    strips = find_non_merged_strips_vertical(dkn_canvas)
    assert all(isinstance(s, NonMergedStrip) for s in strips)
    assert all(s.orientation == "vertical" for s in strips)
    # A column with no merges spans the full sheet height
    for s in strips:
        assert s.rect.r0 == 1
        assert s.rect.r1 == dkn_canvas.n_rows


def test_non_merged_strips_horizontal(dkn_canvas) -> None:
    """Non-merged rows are reported as horizontal NonMergedStrips."""
    strips = find_non_merged_strips_horizontal(dkn_canvas)
    assert all(s.orientation == "horizontal" for s in strips)


def test_merged_column_strips_min_merges_filter(dkn_canvas) -> None:
    """Raising min_merges drops columns with few vertical merges."""
    permissive = find_merged_column_strips(dkn_canvas, min_merges=1)
    strict = find_merged_column_strips(dkn_canvas, min_merges=100)
    assert len(strict) <= len(permissive)


def test_merged_column_strip_has_merge_count(dkn_canvas) -> None:
    """MergedColumnStrip carries a merge_count ≥ min_merges."""
    strips = find_merged_column_strips(dkn_canvas, min_merges=1)
    assert all(isinstance(s, MergedColumnStrip) for s in strips)
    for s in strips:
        assert s.merge_count >= 1


def test_tools_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "find_merge_spans" in names
    assert "find_non_merged_strips_vertical" in names
    assert "find_non_merged_strips_horizontal" in names
    assert "find_merged_column_strips" in names

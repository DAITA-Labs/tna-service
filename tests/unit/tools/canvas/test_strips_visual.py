"""ColorStrip, BoldStrip, BorderedBox detectors."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import BoldStrip, BorderedBox, ColorStrip
from app.tools.canvas.build import build_canvas
from app.tools.canvas.strips_visual import (
    find_bold_strips,
    find_bold_strips_horizontal,
    find_bold_strips_vertical,
    find_bordered_boxes,
    find_color_strips,
    find_color_strips_horizontal,
    find_color_strips_vertical,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN has coloured header rows + bold labels."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_color_strips_returned_as_records(dkn_canvas) -> None:
    """find_color_strips returns ColorStrip records with orientation + color."""
    strips = find_color_strips(dkn_canvas)
    assert all(isinstance(s, ColorStrip) for s in strips)
    for s in strips:
        assert s.orientation in ("horizontal", "vertical")
        assert s.color != ""


def test_color_strips_combined_equals_union(dkn_canvas) -> None:
    """The unified entry returns horizontal + vertical strips."""
    horiz = find_color_strips_horizontal(dkn_canvas)
    vert = find_color_strips_vertical(dkn_canvas)
    combined = find_color_strips(dkn_canvas)
    assert len(combined) == len(horiz) + len(vert)


def test_color_skip_unfilled_cells(dkn_canvas) -> None:
    """No ColorStrip carries color '0' — color_id 0 means no fill."""
    strips = find_color_strips(dkn_canvas)
    assert all(s.color != "0" for s in strips)


def test_bold_strips_returned_as_records(dkn_canvas) -> None:
    """find_bold_strips returns BoldStrip records with orientation."""
    strips = find_bold_strips(dkn_canvas)
    assert all(isinstance(s, BoldStrip) for s in strips)


def test_bold_strips_horizontal_vs_vertical_disjoint(dkn_canvas) -> None:
    """Combined bold strips equal sum of horizontal + vertical (no double counting)."""
    horiz = find_bold_strips_horizontal(dkn_canvas)
    vert = find_bold_strips_vertical(dkn_canvas)
    combined = find_bold_strips(dkn_canvas)
    assert len(combined) == len(horiz) + len(vert)


def test_bold_min_run_threshold(dkn_canvas) -> None:
    """A higher min_run drops short bold runs."""
    permissive = find_bold_strips(dkn_canvas, min_run=2)
    strict = find_bold_strips(dkn_canvas, min_run=20)
    assert len(strict) <= len(permissive)


def test_bordered_boxes_returned_as_records(dkn_canvas) -> None:
    """find_bordered_boxes returns BorderedBox records (may be empty if DKN has no boxes)."""
    boxes = find_bordered_boxes(dkn_canvas)
    assert all(isinstance(b, BorderedBox) for b in boxes)
    for b in boxes:
        assert b.rect.area >= 1


def test_tools_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "find_color_strips" in names
    assert "find_bold_strips" in names
    assert "find_bordered_boxes" in names

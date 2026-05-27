"""SameLengthStrip + LongTextStrip detection — string-column shape signals."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import LongTextStrip, SameLengthStrip
from app.tools.canvas.build import build_canvas
from app.tools.canvas.strips_text import (
    find_long_text_strips,
    find_same_length_strips,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN has fixed-format style codes + long fabric descriptions."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_same_length_strips_returned_as_records(dkn_canvas) -> None:
    """find_same_length_strips returns SameLengthStrip records."""
    strips = find_same_length_strips(dkn_canvas)
    assert isinstance(strips, list)
    assert all(isinstance(s, SameLengthStrip) for s in strips)
    for s in strips:
        assert s.length > 0
        assert 0.0 <= s.density <= 1.0


def test_long_text_strips_returned_as_records(dkn_canvas) -> None:
    """find_long_text_strips returns LongTextStrip records with mean_length >= 20."""
    strips = find_long_text_strips(dkn_canvas)
    assert all(isinstance(s, LongTextStrip) for s in strips)
    for s in strips:
        assert s.mean_length >= 20.0


def test_same_length_density_threshold(dkn_canvas) -> None:
    """Raising min_density should not increase the strip count."""
    permissive = find_same_length_strips(dkn_canvas, min_density=0.5)
    strict = find_same_length_strips(dkn_canvas, min_density=0.99)
    assert len(strict) <= len(permissive)


def test_long_text_mean_threshold(dkn_canvas) -> None:
    """Raising min_mean should not increase the strip count."""
    permissive = find_long_text_strips(dkn_canvas, min_mean=10.0)
    strict = find_long_text_strips(dkn_canvas, min_mean=100.0)
    assert len(strict) <= len(permissive)


def test_min_non_blank_filters_thin_columns(dkn_canvas) -> None:
    """A demanding min_non_blank drops columns with too few strings."""
    permissive = find_same_length_strips(dkn_canvas, min_non_blank=1)
    strict = find_same_length_strips(dkn_canvas, min_non_blank=50)
    assert len(strict) <= len(permissive)


def test_rect_is_1_indexed(dkn_canvas) -> None:
    """Strip rects use 1-indexed inclusive coordinates."""
    for strip in find_same_length_strips(dkn_canvas):
        assert strip.rect.r0 >= 1
        assert strip.rect.c0 == strip.rect.c1   # vertical strip


def test_tools_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "find_same_length_strips" in names
    assert "find_long_text_strips" in names

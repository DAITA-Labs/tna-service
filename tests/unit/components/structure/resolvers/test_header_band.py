"""HeaderBandResolver — multi-row band absorption."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import HeaderBand, StructureBag
from app.components.structure.resolvers.header_band import resolve_header_band
from app.tools.canvas.build import build_canvas


DATASET = Path(__file__).resolve().parents[5] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN — header rows around row 2, with adjacent scored sub-header at row 3."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_resolver_emits_header_band(dkn_canvas) -> None:
    """A tabular sheet produces a HeaderBand record."""
    bag = StructureBag()
    band = resolve_header_band(dkn_canvas, bag)
    assert isinstance(band, HeaderBand)
    assert bag.header_band is band


def test_band_covers_full_column_width(dkn_canvas) -> None:
    """The HeaderBand rect spans c0=1 to c1=n_cols."""
    bag = StructureBag()
    band = resolve_header_band(dkn_canvas, bag)
    assert band.rect.c0 == 1
    assert band.rect.c1 == dkn_canvas.n_cols


def test_band_score_above_min(dkn_canvas) -> None:
    """The HeaderBand carries the anchor row's spec-hit score."""
    bag = StructureBag()
    band = resolve_header_band(dkn_canvas, bag, min_score=1.0)
    assert band.score >= 1.0


def test_high_min_score_returns_none(dkn_canvas) -> None:
    """A very high min_score threshold returns None and clears bag.header_band."""
    bag = StructureBag()
    band = resolve_header_band(dkn_canvas, bag, min_score=1e9)
    assert band is None
    assert bag.header_band is None


def test_idempotent(dkn_canvas) -> None:
    """Calling the resolver twice yields the same result."""
    bag = StructureBag()
    band_a = resolve_header_band(dkn_canvas, bag)
    band_b = resolve_header_band(dkn_canvas, bag)
    assert band_a.rect == band_b.rect
    assert band_a.score == band_b.score

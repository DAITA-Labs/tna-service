"""DataRowRangeResolver — contiguous PLI rows under a header band."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import DataRowRange, StructureBag
from app.components.structure.resolvers.data_row_range import resolve_data_row_ranges
from app.components.structure.resolvers.header_band import resolve_header_band
from app.tools.canvas.build import build_canvas


DATASET = Path(__file__).resolve().parents[5] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN — small tabular sheet."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_no_header_means_empty_ranges(dkn_canvas) -> None:
    """If bag.header_band is None, no DataRowRanges are emitted."""
    bag = StructureBag()
    bag.header_band = None
    ranges = resolve_data_row_ranges(dkn_canvas, bag)
    assert ranges == []
    assert bag.data_row_ranges == []


def test_ranges_returned_as_records(dkn_canvas) -> None:
    """With a header band, resolver emits DataRowRange records."""
    bag = StructureBag()
    resolve_header_band(dkn_canvas, bag)
    ranges = resolve_data_row_ranges(dkn_canvas, bag)
    assert all(isinstance(r, DataRowRange) for r in ranges)


def test_ranges_start_after_header(dkn_canvas) -> None:
    """Every DataRowRange begins on or after the row following header_band.r1."""
    bag = StructureBag()
    header = resolve_header_band(dkn_canvas, bag)
    ranges = resolve_data_row_ranges(dkn_canvas, bag)
    for r in ranges:
        assert r.row_start > header.rect.r1


def test_total_rows_terminate_ranges(dkn_canvas) -> None:
    """A Total/Subtotal/Grand-Total row breaks a range without becoming part of it."""
    from app.components.structure.resolvers.data_row_range import _row_is_total

    # Construct a minimal canvas with a Total row in cell A4
    from app.artifacts.canvas import GridCanvas
    canvas = GridCanvas(
        n_rows=4, n_cols=1,
        cell_values=[["Header"], ["data 1"], ["data 2"], ["Grand Total"]],
        channels={"empty_row": [[0], [0], [0], [0]]},
    )
    assert _row_is_total(canvas, 3) is True
    assert _row_is_total(canvas, 1) is False


def test_idempotent(dkn_canvas) -> None:
    """Calling the resolver twice yields the same ranges."""
    bag = StructureBag()
    resolve_header_band(dkn_canvas, bag)
    ranges_a = resolve_data_row_ranges(dkn_canvas, bag)
    ranges_b = resolve_data_row_ranges(dkn_canvas, bag)
    assert ranges_a == ranges_b

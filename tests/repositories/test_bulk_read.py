"""Tests for app/repositories/workbook_tools/bulk_read."""
from app.repositories.workbook_repo import register_workbook
from app.repositories.workbook_tools.bulk_read import (
    peek_sheet, sample_rows, read_range,
)


def test_peek_sheet_bounded(dkn_file):
    ctx = register_workbook(dkn_file)
    grid = peek_sheet(ctx, "Sheet 1", rows=5, cols=8)
    for c in grid.cells:
        assert c.row <= 5
        assert c.col <= 8


def test_sample_rows_returns_requested(dkn_file):
    ctx = register_workbook(dkn_file)
    rows = sample_rows(ctx, "Sheet 1", [4, 5])
    assert len(rows) == 2


def test_read_range_inclusive(dkn_file):
    ctx = register_workbook(dkn_file)
    grid = read_range(ctx, "Sheet 1", row_range=(4, 4), col_range=(11, 11))
    # K4 holds the io_number / Buyer Po No for DKN row 4.
    assert any(c.address == "K4" for c in grid.cells)

"""Tests for app/tools/targeted."""
from app.repositories.workbook_repo import register_workbook
from app.tools.targeted import read_row, read_relative, get_cell_at


def test_read_row_full_width(dkn_file):
    ctx = register_workbook(dkn_file)
    cells = read_row(ctx, "Sheet 1", 2, col_range=(1, 40))
    assert any(c.value for c in cells)


def test_read_row_col_subset(dkn_file):
    ctx = register_workbook(dkn_file)
    cells = read_row(ctx, "Sheet 1", 4, col_range=(11, 11))
    addrs = {c.address for c in cells}
    assert "K4" in addrs


def test_read_relative_offset(dkn_file):
    ctx = register_workbook(dkn_file)
    cell = read_relative(ctx, "Sheet 1", "K4", dy=1, dx=0)
    assert cell.address == "K5"


def test_get_cell_at_address(dkn_file):
    ctx = register_workbook(dkn_file)
    cell = get_cell_at(ctx, "Sheet 1", "K4")
    assert cell.address == "K4"

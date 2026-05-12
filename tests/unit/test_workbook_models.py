"""Tests for app/models/workbook + app/repositories/workbook_repo."""
from openpyxl import Workbook
from app.enums.cell_dtype import CellDtype
from app.models.workbook import Cell, MergedRegion
from app.repositories.workbook_repo import register_workbook, clear_cache


def test_cell_address_and_dtype():
    c = Cell(row=4, col=11, address="K4", value="131673", dtype=CellDtype.STR)
    assert c.address == "K4"
    assert c.dtype == CellDtype.STR


def test_merged_region_shape():
    m = MergedRegion(cell_range="A4:A7", anchor="A4", anchor_value="1063")
    assert m.cell_range == "A4:A7"


def test_register_workbook_caches(tmp_path):
    wb = Workbook()
    wb.active["A1"] = "hello"
    p = tmp_path / "x.xlsx"
    wb.save(p)
    clear_cache()
    ctx1 = register_workbook(p)
    ctx2 = register_workbook(p)
    assert ctx1 is ctx2, "second call should return cached ctx"
    assert ctx1.path == p.resolve()

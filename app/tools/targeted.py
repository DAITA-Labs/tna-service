"""Targeted tools — single cell or single row reads."""
from __future__ import annotations
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from app.models.workbook import WorkbookCtx, Cell
from app.tools._decorator import tool
from app.tools.bulk_read import _cell


@tool("read_row")
def read_row(
    ctx: WorkbookCtx, sheet: str, row: int,
    col_range: tuple[int, int] | None = None,
) -> list[Cell]:
    """Read every non-empty cell in `row` within [col_range] inclusive."""
    ws = ctx.wb[sheet]
    if col_range is None:
        col_range = (1, ws.max_column or 1)
    c0, c1 = col_range
    out: list[Cell] = []
    for c in range(c0, c1 + 1):
        cell = _cell(ws, row, c)
        if cell.value is not None:
            out.append(cell)
    return out


@tool("read_relative")
def read_relative(
    ctx: WorkbookCtx, sheet: str, anchor: str, dy: int, dx: int,
) -> Cell:
    """Read the cell at (anchor + dy rows, anchor + dx cols)."""
    col_letter, row = coordinate_from_string(anchor)
    col = column_index_from_string(col_letter)
    return _cell(ctx.wb[sheet], row + dy, col + dx)


@tool("get_cell_at")
def get_cell_at(ctx: WorkbookCtx, sheet: str, address: str) -> Cell:
    """Read the cell at an exact A1 address. Used by SourceCellVerifier."""
    col_letter, row = coordinate_from_string(address)
    col = column_index_from_string(col_letter)
    return _cell(ctx.wb[sheet], row, col)

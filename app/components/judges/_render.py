"""Shared rendering helpers for judge gates.

Every gate has to turn `(canvas, coord)` into a prompt-ready cell grid
for the LLM. The helper here is the single source of truth — the
identifier, stage, and metadata gates all import it. Adding a new
gate should NOT duplicate this logic.
"""
from __future__ import annotations

from openpyxl.utils import column_index_from_string, get_column_letter

from app.artifacts.canvas import GridCanvas


_CELL_WIDTH = 14


def render_sheet_excerpt(
    canvas: GridCanvas,
    center: tuple[str, int],
    *,
    half_rows: int = 3,
    half_cols: int = 3,
) -> str:
    """Render the cells around `center` as a fixed-width grid string for the LLM.

    `center` is `(column_letter, row_1idx)`. The output is a 2-D grid
    showing rows `[row-half_rows, row+half_rows]` × columns
    `[col-half_cols, col+half_cols]`, clipped to canvas bounds. The
    centre row is prefixed with `*` so the judge can see at a glance
    which row is under review.
    """
    col_letter, row = center
    col = column_index_from_string(col_letter)
    r0 = max(1, row - half_rows)
    r1 = min(canvas.n_rows, row + half_rows)
    c0 = max(1, col - half_cols)
    c1 = min(canvas.n_cols, col + half_cols)

    lines: list[str] = []
    header_cells = [
        f"({get_column_letter(c)})".center(_CELL_WIDTH) for c in range(c0, c1 + 1)
    ]
    lines.append(" " * 6 + "".join(header_cells))
    for r in range(r0, r1 + 1):
        marker = "*" if r == row else " "
        row_cells = [_format_cell(canvas.cell_values[r - 1][c - 1])
                     for c in range(c0, c1 + 1)]
        lines.append(f"{marker}{r:>4} " + "".join(row_cells))
    return "\n".join(lines)


def _format_cell(value: object) -> str:
    """Format one cell value into the fixed-width slot."""
    text = "" if value is None else str(value)
    if len(text) > _CELL_WIDTH - 2:
        text = text[: _CELL_WIDTH - 5] + "..."
    return text.ljust(_CELL_WIDTH)

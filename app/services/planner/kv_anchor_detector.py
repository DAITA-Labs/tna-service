"""Detect scattered key-value identity blocks (Family 5 layouts).

For each label cell flagged by SheetSurveyor, look at (row, col+1) and
(row+1, col). If exactly one is non-empty and the other is empty (or both
are non-empty but the offset+1 cell is clearly a value), prefer (0,+1).
"""
from __future__ import annotations
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.cell import coordinate_from_string
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, KVAnchor


def detect_kv_anchors(
    ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
) -> list[KVAnchor]:
    ws = ctx.wb[sheet]
    out: list[KVAnchor] = []
    for label, addr in signals.kv_label_hits:
        col_letter, row = coordinate_from_string(addr)
        col = column_index_from_string(col_letter)
        right = ws.cell(row=row, column=col + 1).value if col + 1 <= signals.max_col else None
        below = ws.cell(row=row + 1, column=col).value if row + 1 <= signals.max_row else None

        if right is not None and not isinstance(right, str):
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col + 1)}{row}",
                field=label,
            ))
        elif right is not None and isinstance(right, str) and below is None:
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col + 1)}{row}",
                field=label,
            ))
        elif below is not None:
            out.append(KVAnchor(
                label_cell=addr,
                value_cell=f"{get_column_letter(col)}{row + 1}",
                field=label,
            ))
    return out

"""Classify each row of a sheet into a RowRole.

Rules (in priority order):
  1. Row is entirely empty -> BLANK.
  2. Row sits in the header band and contains vocabulary terms -> HEADER.
  3. Row's identity-column value matches a known header term -> REPEAT_HEADER.
  4. Row's identity column has a value (directly or via merge anchor) -> ANCHOR.
  5. Identity blank, sits inside a merge whose anchor has identity -> CHILD.
  6. Identity blank, no merge, qty matches sum of recent rows' qty -> TOTAL.
  7. Otherwise -> BLANK.
"""
from __future__ import annotations
from openpyxl.utils import column_index_from_string
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, RowSpec
from app.enums.row_role import RowRole
from app.core.logs import get_logger

log = get_logger(__name__)


def _norm(v: object) -> str:
    return "" if v is None else " ".join(str(v).strip().lower().split())


def classify_rows(
    ctx: WorkbookCtx,
    sheet: str,
    signals: SheetSignals,
    identity_column: str | None,
    quantity_column_hint: str | None = None,
) -> list[RowSpec]:
    ws = ctx.wb[sheet]
    rows: list[RowSpec] = []
    if identity_column is None:
        for r in range(1, signals.max_row + 1):
            rows.append(RowSpec(idx=r, role=RowRole.BLANK))
        return rows

    id_col = column_index_from_string(identity_column)
    qty_col = column_index_from_string(quantity_column_hint) if quantity_column_hint else None

    merge_anchor_of: dict[int, tuple[int, int]] = {}
    for (r1, c1, r2, c2) in signals.merges:
        if c1 <= id_col <= c2:
            for r in range(r1, r2 + 1):
                merge_anchor_of[r] = (r1, c1)

    header_vocab_set = {
        _norm(h)
        for hits in signals.header_vocab_hits.values()
        for h in hits
    }

    first_data_row: int | None = None
    last_known_anchor: int | None = None
    last_known_anchor_group: int | None = None
    next_group_id = 0
    recent_qtys: list[tuple[int, float]] = []

    for r in range(1, signals.max_row + 1):
        row_blank = all(
            ws.cell(row=r, column=c).value is None
            for c in range(1, signals.max_col + 1)
        )
        if row_blank:
            rows.append(RowSpec(idx=r, role=RowRole.BLANK))
            continue

        id_val = ws.cell(row=r, column=id_col).value
        merged = merge_anchor_of.get(r)
        merge_anchor_value = (
            ws.cell(row=merged[0], column=merged[1]).value if merged else None
        )

        if first_data_row is None:
            row_strs = [
                _norm(ws.cell(row=r, column=c).value)
                for c in range(1, signals.max_col + 1)
                if isinstance(ws.cell(row=r, column=c).value, str)
            ]
            if any(s in header_vocab_set for s in row_strs):
                rows.append(RowSpec(idx=r, role=RowRole.HEADER))
                continue

        if isinstance(id_val, str) and _norm(id_val) in header_vocab_set:
            rows.append(RowSpec(idx=r, role=RowRole.REPEAT_HEADER))
            continue

        if id_val is not None and (merged is None or merged[0] == r):
            if first_data_row is None:
                first_data_row = r
            last_known_anchor = r
            last_known_anchor_group = next_group_id
            next_group_id += 1
            rows.append(RowSpec(idx=r, role=RowRole.ANCHOR,
                               group_id=last_known_anchor_group))
            if qty_col:
                q = ws.cell(row=r, column=qty_col).value
                if isinstance(q, (int, float)):
                    recent_qtys.append((last_known_anchor_group, float(q)))
            continue

        if id_val is None and merged is not None and merge_anchor_value is not None and last_known_anchor is not None:
            rows.append(RowSpec(idx=r, role=RowRole.CHILD,
                               anchor_idx=last_known_anchor,
                               group_id=last_known_anchor_group))
            if qty_col:
                q = ws.cell(row=r, column=qty_col).value
                if isinstance(q, (int, float)):
                    recent_qtys.append((last_known_anchor_group, float(q)))
            continue

        if qty_col is not None and id_val is None:
            q = ws.cell(row=r, column=qty_col).value
            if isinstance(q, (int, float)):
                target = float(q)
                if last_known_anchor_group is not None:
                    group_sum = sum(
                        v for g, v in recent_qtys
                        if g == last_known_anchor_group
                    )
                    if abs(group_sum - target) < 0.5:
                        rows.append(RowSpec(idx=r, role=RowRole.TOTAL))
                        continue
                grand_sum = sum(v for _, v in recent_qtys)
                if abs(grand_sum - target) < 0.5:
                    rows.append(RowSpec(idx=r, role=RowRole.GRAND_TOTAL))
                    continue

        rows.append(RowSpec(idx=r, role=RowRole.BLANK))

    anchors = sum(1 for r in rows if r.role.value == "anchor")
    children = sum(1 for r in rows if r.role.value == "child")
    totals = sum(1 for r in rows if r.role.value in ("total", "grand_total"))
    log.info("rows_classified", sheet=sheet, anchors=anchors, children=children,
             totals=totals, total_rows=len(rows))
    return rows

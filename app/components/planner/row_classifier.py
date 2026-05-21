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

from app.core.logs import get_logger
from app.enums.row_role import RowRole
from app.models.artifacts import RowSpec, SheetSignals
from app.models.workbook import WorkbookCtx

log = get_logger(__name__)


def _norm(v: object) -> str:
    """Normalise a cell value to a lowercase, collapsed-whitespace string."""
    return "" if v is None else " ".join(str(v).strip().lower().split())


def _build_merge_anchor_map(
    signals: SheetSignals, id_col: int
) -> dict[int, tuple[int, int]]:
    """Map every row inside a vertical merge that spans id_col to its anchor cell."""
    merge_anchor_of: dict[int, tuple[int, int]] = {}
    for (r1, c1, r2, c2) in signals.merges:
        if c1 <= id_col <= c2:
            for r in range(r1, r2 + 1):
                merge_anchor_of[r] = (r1, c1)
    return merge_anchor_of


def _build_header_vocab_set(signals: SheetSignals) -> set[str]:
    """Flatten all header vocabulary hits into a single normalised set."""
    return {
        _norm(h)
        for hits in signals.header_vocab_hits.values()
        for h in hits
    }


def _classify_single_row(
    r: int,
    ws: object,
    id_col: int,
    qty_col: int | None,
    merge_anchor_of: dict[int, tuple[int, int]],
    header_vocab_set: set[str],
    signals: SheetSignals,
    first_data_row: int | None,
    last_known_anchor: int | None,
    last_known_anchor_group: int | None,
    next_group_id: int,
    recent_qtys: list[tuple[int, float]],
) -> tuple[RowSpec, int | None, int | None, int | None, int]:
    """Classify row `r` and return the updated planner state.

    Returns (row_spec, first_data_row, last_known_anchor,
             last_known_anchor_group, next_group_id).
    """
    row_blank = all(
        ws.cell(row=r, column=c).value is None
        for c in range(1, signals.max_col + 1)
    )
    if row_blank:
        return (
            RowSpec(idx=r, role=RowRole.BLANK),
            first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
        )

    id_val = ws.cell(row=r, column=id_col).value
    merged = merge_anchor_of.get(r)
    merge_anchor_value = (
        ws.cell(row=merged[0], column=merged[1]).value if merged else None
    )

    if first_data_row is None:
        id_cell_str = _norm(ws.cell(row=r, column=id_col).value)
        if id_cell_str and id_cell_str in header_vocab_set:
            return (
                RowSpec(idx=r, role=RowRole.HEADER),
                first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
            )

    if isinstance(id_val, str) and _norm(id_val) in header_vocab_set:
        return (
            RowSpec(idx=r, role=RowRole.REPEAT_HEADER),
            first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
        )

    if id_val is not None and (merged is None or merged[0] == r):
        if first_data_row is None:
            first_data_row = r
        last_known_anchor = r
        last_known_anchor_group = next_group_id
        next_group_id += 1
        if qty_col:
            q = ws.cell(row=r, column=qty_col).value
            if isinstance(q, (int, float)):
                recent_qtys.append((last_known_anchor_group, float(q)))
        return (
            RowSpec(idx=r, role=RowRole.ANCHOR, group_id=last_known_anchor_group),
            first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
        )

    if id_val is None and merged is not None and merge_anchor_value is not None and last_known_anchor is not None:
        if qty_col:
            q = ws.cell(row=r, column=qty_col).value
            if isinstance(q, (int, float)):
                recent_qtys.append((last_known_anchor_group, float(q)))
        return (
            RowSpec(idx=r, role=RowRole.CHILD,
                    anchor_idx=last_known_anchor,
                    group_id=last_known_anchor_group),
            first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
        )

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
                    return (
                        RowSpec(idx=r, role=RowRole.TOTAL),
                        first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
                    )
            grand_sum = sum(v for _, v in recent_qtys)
            if abs(grand_sum - target) < 0.5:
                return (
                    RowSpec(idx=r, role=RowRole.GRAND_TOTAL),
                    first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
                )

    return (
        RowSpec(idx=r, role=RowRole.BLANK),
        first_data_row, last_known_anchor, last_known_anchor_group, next_group_id,
    )


def classify_rows(
    ctx: WorkbookCtx,
    sheet: str,
    signals: SheetSignals,
    identity_column: str | None,
    quantity_column_hint: str | None = None,
) -> list[RowSpec]:
    """Classify every row in `sheet` into a RowRole using structural signals.

    Returns one RowSpec per row, ordered by row index. When identity_column
    is None every row is classified BLANK.
    """
    ws = ctx.wb[sheet]
    rows: list[RowSpec] = []
    if identity_column is None:
        for r in range(1, signals.max_row + 1):
            rows.append(RowSpec(idx=r, role=RowRole.BLANK))
        return rows

    id_col = column_index_from_string(identity_column)
    qty_col = column_index_from_string(quantity_column_hint) if quantity_column_hint else None

    merge_anchor_of = _build_merge_anchor_map(signals, id_col)
    header_vocab_set = _build_header_vocab_set(signals)

    first_data_row: int | None = None
    last_known_anchor: int | None = None
    last_known_anchor_group: int | None = None
    next_group_id = 0
    recent_qtys: list[tuple[int, float]] = []

    for r in range(1, signals.max_row + 1):
        row_spec, first_data_row, last_known_anchor, last_known_anchor_group, next_group_id = (
            _classify_single_row(
                r, ws, id_col, qty_col, merge_anchor_of, header_vocab_set,
                signals, first_data_row, last_known_anchor, last_known_anchor_group,
                next_group_id, recent_qtys,
            )
        )
        rows.append(row_spec)

    anchors = sum(1 for r in rows if r.role.value == "anchor")
    children = sum(1 for r in rows if r.role.value == "child")
    totals = sum(1 for r in rows if r.role.value in ("total", "grand_total"))
    log.info("rows_classified", sheet=sheet, anchors=anchors, children=children,
             totals=totals, total_rows=len(rows))
    return rows

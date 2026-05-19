"""Detect stage-band rectangles on a sheet.

Two layout modes:
- WIDE_SUB_COLUMNS: stage name in row N, sub-headers (plan/actual) in row N+1,
  data rows below. One column per stage's primary + zero or more sub-cols.
- TALL_SUB_ROWS: stage names spread across columns in a single 'sub_header_row',
  with a left-of-band label column (column B typically) holding sub-row roles
  like 'Plan' / 'Action' / 'Deviation' for the rows below the header.
"""
from __future__ import annotations

from datetime import date, datetime

from openpyxl.utils import get_column_letter

from app.core.logs import get_logger
from app.models.artifacts import SheetSignals, StageBandSpec, StageColumn
from app.models.workbook import WorkbookCtx

log = get_logger(__name__)


_SUB_ROW_LABELS = {"plan": "plan", "action": "action",
                   "actual": "actual", "actl": "actual",
                   "deviation": "deviation", "dev": "deviation"}


def _is_date(v: object) -> bool:
    """Return True when `v` is a date or datetime instance."""
    return isinstance(v, (date, datetime))


def _find_date_cols(ws: object, r: int, max_col: int) -> list[int]:
    """Return column indices where the cell in row `r` holds a date value."""
    return [c for c in range(1, max_col + 1) if _is_date(ws.cell(row=r, column=c).value)]


def _find_sub_header_row(ws: object, r: int, date_cols: list[int]) -> int | None:
    """Locate the nearest string-labelled row above `r` that aligns with date_cols.

    Probes r-1 and r-2. Returns the row index, or None if no candidate found.
    """
    for prev in (r - 1, r - 2):
        if prev < 1:
            break
        str_count = sum(
            1 for c in date_cols
            if isinstance(ws.cell(row=prev, column=c).value, str)
        )
        if str_count >= max(2, len(date_cols) // 2):
            return prev
    return None


def _collect_stage_cols(ws: object, sub_header_row: int, date_cols: list[int]) -> dict[str, str]:
    """Map stage name strings in sub_header_row to their column letters."""
    stage_cols: dict[str, str] = {}
    for c in date_cols:
        name = ws.cell(row=sub_header_row, column=c).value
        if isinstance(name, str) and name.strip():
            stage_cols[name.strip()] = get_column_letter(c)
    return stage_cols


def _resolve_section_title(
    ws: object, sub_header_row: int, date_cols: list[int], max_col: int
) -> tuple[str, str]:
    """Find a section title and name-cell address for a stage band.

    Prefers a string value in sub_header_row outside the date columns;
    falls back to the row above; finally defaults to 'stage_band'.
    Returns (section_title, name_cell_address).
    """
    date_col_set = set(date_cols)
    for c in range(1, max_col + 1):
        if c in date_col_set:
            continue
        v = ws.cell(row=sub_header_row, column=c).value
        if isinstance(v, str) and v.strip():
            return v.strip(), f"{get_column_letter(c)}{sub_header_row}"

    if sub_header_row >= 2:
        title_row = sub_header_row - 1
        for c in range(1, max_col + 1):
            v = ws.cell(row=title_row, column=c).value
            if isinstance(v, str) and v.strip():
                return v.strip(), f"{get_column_letter(c)}{title_row}"

    return "stage_band", f"{get_column_letter(1)}{sub_header_row}"


def _collect_sub_rows(ws: object, r: int, max_row: int) -> dict[str, int]:
    """Probe rows starting at `r` for sub-row role labels (plan/action/deviation).

    Returns a mapping of canonical role name -> row index. Empty when none found.
    """
    sub_rows: dict[str, int] = {}
    for probe in range(r, min(max_row, r + 5) + 1):
        label = ws.cell(row=probe, column=2).value
        if not isinstance(label, str):
            label = ws.cell(row=probe, column=1).value
        if isinstance(label, str):
            key = _SUB_ROW_LABELS.get(label.strip().lower())
            if key:
                sub_rows.setdefault(key, probe)
    return sub_rows


def _build_stage_columns(
    stage_cols: dict[str, str], sub_header_row: int,
) -> list[StageColumn]:
    """Build a StageColumn per (stage_name, col) pair with empty sub_columns.

    Structural-only mirror of `stage_cols`. Sub-columns are filled by
    `_collect_sub_columns` in a subsequent step (wide_sub_columns code path).
    """
    return [
        StageColumn(
            name=name,
            name_cell=f"{col_letter}{sub_header_row}",
            primary_col=col_letter,
        )
        for name, col_letter in stage_cols.items()
    ]


def detect_stage_bands(
    ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
) -> list[StageBandSpec]:
    """Detect all stage-band rectangles in `sheet` and return their specs."""
    ws = ctx.wb[sheet]
    bands: list[StageBandSpec] = []
    seen_name_cells: set[str] = set()

    for r in range(1, signals.max_row + 1):
        date_cols = _find_date_cols(ws, r, signals.max_col)
        if len(date_cols) < 2:
            continue

        sub_header_row = _find_sub_header_row(ws, r, date_cols)
        if sub_header_row is None:
            continue

        stage_cols = _collect_stage_cols(ws, sub_header_row, date_cols)
        if not stage_cols:
            continue

        section_title, name_cell = _resolve_section_title(
            ws, sub_header_row, date_cols, signals.max_col
        )

        if name_cell in seen_name_cells:
            continue
        seen_name_cells.add(name_cell)

        sub_rows = _collect_sub_rows(ws, r, signals.max_row)

        if sub_rows:
            layout_mode = "tall_sub_rows"
            if "plan" not in sub_rows:
                sub_rows["plan"] = r
        else:
            layout_mode = "wide_sub_columns"
            sub_rows = {"plan": r}

        bands.append(StageBandSpec(
            name=section_title,
            name_cell=name_cell,
            sub_header_row=sub_header_row,
            sub_rows=sub_rows,
            stage_cols=stage_cols,
            stage_columns=_build_stage_columns(stage_cols, sub_header_row),
            layout_mode=layout_mode,
        ))

    log.info("stage_bands_detected", sheet=sheet, count=len(bands))
    return bands

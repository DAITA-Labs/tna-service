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
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals, StageBandSpec


_SUB_ROW_LABELS = {"plan": "plan", "action": "action",
                   "actual": "actual", "actl": "actual",
                   "deviation": "deviation", "dev": "deviation"}


def _is_date(v: object) -> bool:
    return isinstance(v, (date, datetime))


def detect_stage_bands(
    ctx: WorkbookCtx, sheet: str, signals: SheetSignals,
) -> list[StageBandSpec]:
    ws = ctx.wb[sheet]
    bands: list[StageBandSpec] = []
    seen_name_cells: set[str] = set()

    for r in range(1, signals.max_row + 1):
        date_cols: list[int] = []
        for c in range(1, signals.max_col + 1):
            if _is_date(ws.cell(row=r, column=c).value):
                date_cols.append(c)
        if len(date_cols) < 2:
            continue

        sub_header_row = None
        for prev in (r - 1, r - 2):
            if prev < 1:
                break
            str_count = sum(
                1 for c in date_cols
                if isinstance(ws.cell(row=prev, column=c).value, str)
            )
            if str_count >= max(2, len(date_cols) // 2):
                sub_header_row = prev
                break
        if sub_header_row is None:
            continue

        stage_cols: dict[str, str] = {}
        for c in date_cols:
            name = ws.cell(row=sub_header_row, column=c).value
            if isinstance(name, str) and name.strip():
                stage_cols[name.strip()] = get_column_letter(c)

        if not stage_cols:
            continue

        # Determine title: prefer same row as sub_header (column outside date_cols),
        # fall back to the row above.
        section_title = None
        name_cell = None
        date_col_set = set(date_cols)
        for c in range(1, signals.max_col + 1):
            if c in date_col_set:
                continue
            v = ws.cell(row=sub_header_row, column=c).value
            if isinstance(v, str) and v.strip():
                section_title = v.strip()
                name_cell = f"{get_column_letter(c)}{sub_header_row}"
                break

        if section_title is None and sub_header_row >= 2:
            title_row = sub_header_row - 1
            for c in range(1, signals.max_col + 1):
                v = ws.cell(row=title_row, column=c).value
                if isinstance(v, str) and v.strip():
                    section_title = v.strip()
                    name_cell = f"{get_column_letter(c)}{title_row}"
                    break

        if section_title is None:
            section_title = "stage_band"
            name_cell = name_cell or f"{get_column_letter(1)}{sub_header_row}"

        if name_cell in seen_name_cells:
            continue
        seen_name_cells.add(name_cell)

        sub_rows: dict[str, int] = {}
        for probe in range(r, min(signals.max_row, r + 5) + 1):
            label = ws.cell(row=probe, column=2).value
            if not isinstance(label, str):
                label = ws.cell(row=probe, column=1).value
            if isinstance(label, str):
                key = _SUB_ROW_LABELS.get(label.strip().lower())
                if key:
                    sub_rows.setdefault(key, probe)

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
            layout_mode=layout_mode,
        ))

    return bands

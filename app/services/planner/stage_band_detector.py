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

from openpyxl.utils import column_index_from_string, get_column_letter

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


def _is_sub_label_only_row(ws: object, row: int, date_cols: list[int]) -> bool:
    """Return True when every non-empty string in `row` at `date_cols` is a sub-label.

    Used to skip an intermediate Plan/Actual row and find the true stage-name row.
    """
    values = [
        ws.cell(row=row, column=c).value
        for c in date_cols
        if isinstance(ws.cell(row=row, column=c).value, str)
    ]
    return bool(values) and all(
        v.strip().lower() in _SUB_ROW_LABELS for v in values
    )


# allow-long: dual-probe row scan with sub-label fallthrough is one nameable concept
def _find_sub_header_row(ws: object, r: int, date_cols: list[int]) -> int | None:
    """Locate the nearest string-labelled row above `r` that aligns with date_cols.

    Probes r-1 and r-2. When r-1 contains only sub-field vocabulary (Plan/Actual
    etc.), skips it and prefers r-2 as the true stage-name row, using a threshold
    of at least 1 non-sub-label string. Returns the row index, or None if no
    candidate found.
    """
    threshold = max(2, len(date_cols) // 2)

    prev1 = r - 1
    if prev1 < 1:
        return None

    str_count1 = sum(
        1 for c in date_cols
        if isinstance(ws.cell(row=prev1, column=c).value, str)
    )

    if str_count1 >= threshold:
        # r-1 qualifies; check if it is entirely sub-field vocabulary.
        if _is_sub_label_only_row(ws, prev1, date_cols):
            # Try r-2 with a relaxed threshold of 1 (stage name may span fewer cols).
            prev2 = r - 2
            if prev2 >= 1:
                str_count2 = sum(
                    1 for c in date_cols
                    if isinstance(ws.cell(row=prev2, column=c).value, str)
                )
                if str_count2 >= 1:
                    return prev2
            # Fall through to returning r-1 if r-2 also has no strings.
        return prev1

    # r-1 below threshold; try r-2.
    prev2 = r - 2
    if prev2 >= 1:
        str_count2 = sum(
            1 for c in date_cols
            if isinstance(ws.cell(row=prev2, column=c).value, str)
        )
        if str_count2 >= threshold:
            return prev2

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


def _collect_sub_columns(
    ws: object, stage_name_row: int, sub_label_row: int, max_col: int,
    stage_cols: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Map each stage to its sub-column labels read from `sub_label_row`.

    For each adjacent column after a stage's primary column, if the cell at
    (sub_label_row, col) is a non-stage-vocab string, attribute it to the nearest
    preceding stage. Returns {stage_name: {sub_label: col_letter}}.
    """
    if sub_label_row == stage_name_row:
        return {name: {} for name in stage_cols}

    primary_cols_by_idx = {
        column_index_from_string(col): name for name, col in stage_cols.items()
    }
    sorted_idx = sorted(primary_cols_by_idx)
    result: dict[str, dict[str, str]] = {name: {} for name in stage_cols}

    for c in range(1, max_col + 1):
        if c in primary_cols_by_idx:
            continue
        preceding = [i for i in sorted_idx if i < c]
        if not preceding:
            continue
        owner_stage = primary_cols_by_idx[preceding[-1]]
        # Stop attributing to a stage once we cross the next stage's column.
        following = [i for i in sorted_idx if i > preceding[-1]]
        if following and c >= following[0]:
            continue
        v = ws.cell(row=sub_label_row, column=c).value
        # Only accept recognised sub-field vocabulary (Plan/Actual/Deviation …).
        # Arbitrary strings at sub_label_row (e.g. data-row product names) are
        # not sub-column labels and must be excluded.
        if isinstance(v, str) and v.strip() and v.strip().lower() in _SUB_ROW_LABELS:
            result[owner_stage][v.strip()] = get_column_letter(c)

    return result


def _merge_anchors_at_row(
    merges: list[tuple[int, int, int, int]], row: int
) -> set[int]:
    """Return the set of column indices that start a multi-column merge at `row`."""
    return {
        min_col
        for (min_row, min_col, max_row, max_col) in merges
        if min_row == row == max_row and max_col > min_col
    }


def _build_stage_columns(
    stage_cols: dict[str, str], sub_header_row: int,
    sub_columns_by_stage: dict[str, dict[str, str]] | None = None,
) -> list[StageColumn]:
    """Build a StageColumn per (stage_name, col) pair, with sub_columns when known."""
    sub_columns_by_stage = sub_columns_by_stage or {}
    return [
        StageColumn(
            name=name,
            name_cell=f"{col_letter}{sub_header_row}",
            primary_col=col_letter,
            sub_columns=sub_columns_by_stage.get(name, {}),
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

        sub_columns_by_stage: dict[str, dict[str, str]] = {}
        if layout_mode == "wide_sub_columns":
            sub_label_row = sub_header_row + 1
            if sub_label_row <= signals.max_row:
                sub_columns_by_stage = _collect_sub_columns(
                    ws, stage_name_row=sub_header_row,
                    sub_label_row=sub_label_row, max_col=signals.max_col,
                    stage_cols=stage_cols,
                )
            # When the sub_label_row carries real sub-field labels (i.e. at least
            # one stage obtained sub_columns), exclude stage candidates that have
            # neither sub-columns nor a multi-column merge anchor — those are
            # identity date fields that happen to sit in the date-column band.
            has_real_sub_labels = any(
                bool(sub_columns_by_stage.get(name)) for name in stage_cols
            )
            if has_real_sub_labels:
                merge_anchors = _merge_anchors_at_row(signals.merges, sub_header_row)
                stage_cols = {
                    name: col for name, col in stage_cols.items()
                    if sub_columns_by_stage.get(name)
                    or column_index_from_string(col) in merge_anchors
                }

        bands.append(StageBandSpec(
            name=section_title,
            name_cell=name_cell,
            sub_header_row=sub_header_row,
            sub_rows=sub_rows,
            stage_cols=stage_cols,
            stage_columns=_build_stage_columns(
                stage_cols, sub_header_row, sub_columns_by_stage
            ),
            layout_mode=layout_mode,
        ))

    log.info("stage_bands_detected", sheet=sheet, count=len(bands))
    return bands

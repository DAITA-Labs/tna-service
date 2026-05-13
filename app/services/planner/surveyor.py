"""Deterministic single-pass survey of a sheet — collects raw structural signals
that downstream planner components consume.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import get_column_letter
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetSignals


_IDENTITY_VOCAB = (
    "io no", "io number", "io",
    "job no", "job number",
    "po no", "po number", "buyer po", "buyer po no",
    "style no", "style code", "style",
)

_KV_LABEL_VOCAB = (
    "job no", "io no", "io number", "po no", "buyer po no",
    "quantity", "qty", "order qty", "plan qty",
    "ex-fac date", "ex-fty date", "ex fac date", "ex factory",
    "delivery date", "order receipt", "shipment date",
    "style", "fabric", "color", "colour",
)


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def survey_sheet(ctx: WorkbookCtx, sheet: str) -> SheetSignals:
    ws = ctx.wb[sheet]
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0

    merges: list[tuple[int, int, int, int]] = [
        (mr.min_row, mr.min_col, mr.max_row, mr.max_col)
        for mr in ws.merged_cells.ranges
    ]

    header_vocab_hits: dict[str, list[str]] = {}
    kv_label_hits: list[tuple[str, str]] = []
    for r in range(1, min(max_row, 15) + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            v_norm = _norm(v)
            col_letter = get_column_letter(c)
            if any(term in v_norm for term in _IDENTITY_VOCAB):
                header_vocab_hits.setdefault(col_letter, []).append(v)
            if any(term == v_norm or v_norm.endswith(term) or v_norm.startswith(term)
                   for term in _KV_LABEL_VOCAB):
                kv_label_hits.append((v, f"{col_letter}{r}"))

    identity_col_candidates = list(header_vocab_hits.keys())

    blank_run_gaps: list[tuple[int, int]] = []
    run_start: int | None = None
    for r in range(1, max_row + 1):
        row_empty = all(
            ws.cell(row=r, column=c).value is None
            for c in range(1, max_col + 1)
        )
        if row_empty and run_start is None:
            run_start = r
        elif not row_empty and run_start is not None:
            if r - 1 >= run_start:
                blank_run_gaps.append((run_start, r - 1))
            run_start = None
    if run_start is not None and max_row >= run_start:
        blank_run_gaps.append((run_start, max_row))

    date_typed_cols: list[str] = []
    for c in range(1, max_col + 1):
        seen = 0
        date_count = 0
        for r in range(1, max_row + 1):
            v = ws.cell(row=r, column=c).value
            if v is None:
                continue
            seen += 1
            if isinstance(v, (date, datetime)):
                date_count += 1
        if seen >= 2 and date_count / seen >= 0.5:
            date_typed_cols.append(get_column_letter(c))

    return SheetSignals(
        sheet=sheet, max_row=max_row, max_col=max_col,
        merges=merges,
        identity_col_candidates=identity_col_candidates,
        header_vocab_hits=header_vocab_hits,
        date_typed_cols=date_typed_cols,
        blank_run_gaps=blank_run_gaps,
        kv_label_hits=kv_label_hits,
    )

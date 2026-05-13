"""Tier 2 plan validators — statistical sanity of a SheetPlan against the sheet.

Warnings here cause PlanReviewer to fire; errors trigger re-plan with hints.
"""
from __future__ import annotations
from datetime import date, datetime
from openpyxl.utils import column_index_from_string
from app.models.workbook import WorkbookCtx
from app.models.artifacts import SheetPlan, ValidationFinding
from app.enums.row_role import RowRole
from app.enums.validation_severity import ValidationSeverity
from app.core.logs import get_logger

log = get_logger(__name__)


def _w(check: str, msg: str) -> ValidationFinding:
    return ValidationFinding(check=check, severity=ValidationSeverity.WARN, message=msg)


def validate_statistics(ctx: WorkbookCtx, plan: SheetPlan) -> list[ValidationFinding]:
    out: list[ValidationFinding] = []
    ws = ctx.wb[plan.sheet]
    anchors = [r for r in plan.rows if r.role is RowRole.ANCHOR]

    sno_col = None
    for c in range(1, (ws.max_column or 0) + 1):
        for h_row in plan.header_rows:
            v = ws.cell(row=h_row, column=c).value
            if isinstance(v, str) and v.strip().lower() in ("s no", "s.no", "sno", "s. no", "sl no"):
                sno_col = c
                break
        if sno_col:
            break
    if sno_col is not None and anchors:
        sno_vals = [ws.cell(row=a.idx, column=sno_col).value for a in anchors]
        sno_ints = [int(v) for v in sno_vals if isinstance(v, (int, float))]
        if sno_ints:
            expected = max(sno_ints)
            if expected != len(anchors):
                out.append(_w("sequence_match",
                              f"S.NO max={expected} vs ANCHOR count={len(anchors)}"))

    max_row = ws.max_row or 0
    if max_row >= 10 and len(anchors) == 0 and len(plan.pli_blocks) == 0 and len(plan.kv_anchors) == 0:
        out.append(_w("pli_count_sanity",
                      f"sheet has {max_row} rows but plan emits 0 PLIs"))

    if plan.identity_column and plan.rows:
        id_col = column_index_from_string(plan.identity_column)
        data_rows = [r for r in plan.rows
                     if r.role in (RowRole.ANCHOR, RowRole.CHILD)]
        if data_rows:
            populated = sum(
                1 for r in data_rows
                if ws.cell(row=r.idx, column=id_col).value is not None
                or r.anchor_idx is not None
            )
            ratio = populated / len(data_rows)
            if ratio < 0.8:
                out.append(_w("identity_column_coverage",
                              f"identity coverage {ratio:.2f} < 0.80"))

    for band in plan.stage_bands:
        sub_rows = list(band.sub_rows.values())
        if not sub_rows:
            continue
        total = 0; dates = 0
        for col_letter in band.stage_cols.values():
            c_idx = column_index_from_string(col_letter)
            for r in sub_rows:
                v = ws.cell(row=r, column=c_idx).value
                if v is None:
                    continue
                total += 1
                if isinstance(v, (date, datetime)):
                    dates += 1
        if total >= 2 and dates / total < 0.5:
            out.append(_w("date_band_density",
                          f"stage band '{band.name}' is only {dates}/{total} date-typed"))

    if out:
        log.info("plan_statistics_warns", sheet=plan.sheet, count=len(out),
                 checks=[f.check for f in out])
    return out

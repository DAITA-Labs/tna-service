"""SheetRowPlanner — deterministic component producing a SheetPlan per sheet.

Composes SheetSurveyor, row_classifier, kv_anchor_detector, stage_band_detector,
and block_segmenter. Decides pli_mode from the collected signals.
"""
from __future__ import annotations
from typing import Any
from openpyxl.utils import get_column_letter
from haystack import component
from app.models.artifacts import (
    SheetPlan, SheetSignals, RowSpec, KVAnchor, StageBandSpec, PliBlock,
)
from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.enums.stage_scope import StageScope
from app.services.planner.surveyor import survey_sheet
from app.services.planner.row_classifier import classify_rows
from app.services.planner.kv_anchor_detector import detect_kv_anchors
from app.services.planner.stage_band_detector import detect_stage_bands
from app.services.planner.block_segmenter import segment_blocks
from app.core.logs import get_logger

log = get_logger(__name__)


def _decide_pli_mode(signals: SheetSignals) -> PliMode:
    # Collect the cell addresses of all KV label hits so we can check whether
    # an identity column candidate is a column header (row 1-2) or a KV label
    # embedded in the sheet body (row > 2).
    kv_cells: set[str] = {cell for _, cell in signals.kv_label_hits}

    # An identity candidate column is "real" (tabular header) when the hit
    # lives in the first two rows.  If every hit for that column only appears
    # as a KV label deeper in the body, it is not a true column identity.
    from openpyxl.utils.cell import coordinate_from_string
    real_identity_cols: list[str] = []
    for col in signals.identity_col_candidates:
        col_hits = signals.header_vocab_hits.get(col, [])
        for hit_text in col_hits:
            matching_cells = [c for _, c in signals.kv_label_hits
                              if c.startswith(col) and c[1:].isdigit()
                              or (len(c) >= 2 and c[0] == col and c[1:].isdigit())]
            # Check if any hit for this column is at a low row number (header band)
            col_kv_rows = [
                int(c[len(col):]) for _, c in signals.kv_label_hits
                if c.startswith(col) and c[len(col):].isdigit()
            ]
            # A column is a real identity column when it has no KV hits in the
            # header band, OR when its vocabulary hit IS a column header (row ≤ 2)
        # Simpler: check if the column appears in kv_label_hits only at row > 2
        low_row_kv = any(
            int(c[len(col):]) <= 2
            for _, c in signals.kv_label_hits
            if c.startswith(col) and c[len(col):].isdigit()
        )
        if not low_row_kv:
            # All KV hits for this col are deep in the body — it's a label, not a header
            continue
        real_identity_cols.append(col)

    has_identity_col = len(real_identity_cols) >= 1
    n_kv_hits = len(signals.kv_label_hits)
    n_blank_gaps = len(signals.blank_run_gaps)

    if has_identity_col:
        if n_blank_gaps >= 2 and n_kv_hits >= 3:
            return PliMode.SECTION_PER_PLI
        return PliMode.ROW_PER_PLI
    if n_kv_hits >= 2:
        return PliMode.SHEET_IS_PLI
    return PliMode.ROW_PER_PLI


def _pick_identity_column(signals: SheetSignals) -> str | None:
    if not signals.identity_col_candidates:
        return None
    for col in signals.identity_col_candidates:
        for hit in signals.header_vocab_hits.get(col, []):
            h = hit.lower()
            if "io" in h or "job" in h or "buyer po" in h:
                return col
    return signals.identity_col_candidates[0]


def _pick_quantity_column(workbook_ctx: Any, sheet: str, signals: SheetSignals) -> str | None:
    ws = workbook_ctx.wb[sheet]
    for c in range(1, signals.max_col + 1):
        for r in range(1, min(signals.max_row, 10) + 1):
            v = ws.cell(row=r, column=c).value
            if isinstance(v, str):
                vn = " ".join(v.strip().lower().split())
                if any(t in vn for t in ("qty", "quantity", "order qty", "plan qty")):
                    return get_column_letter(c)
    return None


@component
class SheetRowPlanner:
    """Haystack component — emits a SheetPlan for one sheet."""

    @component.output_types(plan=SheetPlan)
    def run(self, workbook_ctx: Any, sheet: str) -> dict:
        log.info("planner_start", sheet=sheet)
        signals = survey_sheet(workbook_ctx, sheet)
        pli_mode = _decide_pli_mode(signals)
        identity_column = (
            _pick_identity_column(signals) if pli_mode is not PliMode.SHEET_IS_PLI else None
        )
        log.info("planner_mode_decided", sheet=sheet,
                 pli_mode=pli_mode.value, identity_column=identity_column)

        stage_bands = detect_stage_bands(workbook_ctx, sheet, signals)
        kv_anchors = detect_kv_anchors(workbook_ctx, sheet, signals)

        rows: list[RowSpec] = []
        blocks: list[PliBlock] = []
        if pli_mode is PliMode.SHEET_IS_PLI:
            rows = []
        else:
            qty_col = _pick_quantity_column(workbook_ctx, sheet, signals)
            rows = classify_rows(
                workbook_ctx, sheet, signals,
                identity_column=identity_column,
                quantity_column_hint=qty_col,
            )

        header_rows = [r.idx for r in rows if r.role is RowRole.HEADER] if rows else []

        if pli_mode is PliMode.SECTION_PER_PLI:
            blocks = segment_blocks(rows, kv_anchors, signals.blank_run_gaps, stage_bands)
            stage_bands_sheet: list[StageBandSpec] = []
            stage_scope = StageScope.PLI_LOCAL
        else:
            stage_bands_sheet = stage_bands
            stage_scope = StageScope.SHEET_LEVEL

        confidence = 0.9 if pli_mode is not PliMode.SHEET_IS_PLI else 0.85
        if pli_mode is PliMode.SHEET_IS_PLI and len(kv_anchors) >= 3:
            confidence = 0.92

        plan = SheetPlan(
            sheet=sheet,
            pli_mode=pli_mode,
            identity_column=identity_column,
            header_rows=header_rows,
            rows=rows,
            pli_blocks=blocks,
            kv_anchors=kv_anchors if pli_mode is PliMode.SHEET_IS_PLI else [],
            stage_bands=stage_bands_sheet,
            stage_scope=stage_scope,
            confidence=confidence,
        )
        log.info("planner_complete", sheet=sheet, pli_mode=plan.pli_mode.value,
                 rows=len(plan.rows), blocks=len(plan.pli_blocks),
                 kv=len(plan.kv_anchors), bands=len(plan.stage_bands),
                 confidence=plan.confidence)
        return {"plan": plan}

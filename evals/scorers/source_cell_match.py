"""Source cell match — fraction of source_cells that resolve to the extracted value.

Independent of the label; only needs the extracted result + WorkbookCtx."""
from __future__ import annotations
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from app.models.extraction import ExtractionResult
from app.models.workbook import WorkbookCtx


def score_source_cell_match(actual: ExtractionResult, ctx: WorkbookCtx) -> float:
    total = 0
    matched = 0
    for pli in actual.plis:
        if not pli.source_sheet:
            continue
        ws = ctx.wb[pli.source_sheet]
        for field, addr in pli.source_cells.items():
            total += 1
            extracted = getattr(pli, field, None) or pli.metadata.get(field)
            if extracted is None:
                continue
            col, row = coordinate_from_string(addr)
            actual_val = ws.cell(row=row, column=column_index_from_string(col)).value
            if str(actual_val) == str(extracted):
                matched += 1
    return matched / total if total else 1.0

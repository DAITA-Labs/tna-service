"""Source cell match — fraction of source.cells that resolve to the extracted value.

Independent of the label; only needs the extracted result + WorkbookCtx."""
from __future__ import annotations
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from app.models.extraction import ExtractionResult
from app.models.workbook import WorkbookCtx
from evals.scorers._compare import values_equal


def score_source_cell_match(actual: ExtractionResult, ctx: WorkbookCtx) -> float:
    """Score the fraction of source.cells entries whose workbook cell matches the extracted value.

    Uses type-tolerant comparison so that date / datetime / ISO-string
    representations of the same calendar date are treated as equal.  This
    ensures live and replay runs produce the same score even though
    ``dict[str, Any]`` metadata fields lose their ``datetime`` type after a
    ``model_dump_json`` → ``model_validate_json`` round-trip.
    """
    total = 0
    matched = 0
    for pli in actual.plis:
        if not pli.source.sheet:
            continue
        ws = ctx.wb[pli.source.sheet]
        for field, addr in pli.source.cells.items():
            total += 1
            extracted = getattr(pli, field, None) or pli.metadata.get(field)
            if extracted is None:
                continue
            col, row = coordinate_from_string(addr)
            actual_val = ws.cell(row=row, column=column_index_from_string(col)).value
            if values_equal(actual_val, extracted):
                matched += 1
    return matched / total if total else 1.0

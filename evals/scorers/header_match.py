"""Header match — fraction of source columns whose header text relates to
the canonical field's vocabulary."""
from __future__ import annotations
from openpyxl.utils import column_index_from_string
from openpyxl.utils.cell import coordinate_from_string
from app.models.extraction import ExtractionResult
from app.models.workbook import WorkbookCtx


_VOCAB = {
    "io_number": ("po", "buyer", "io", "job", "order"),
    "style_code": ("style",),
    "color_code": ("color", "colour"),
    "fabric_code": ("fabric", "material", "quality"),
    "delivery_date": ("delivery", "ex factory", "etd", "ship"),
    "quantity": ("qty", "quantity"),
}


def score_header_match(actual: ExtractionResult, ctx: WorkbookCtx) -> float:
    """Score the fraction of source columns whose header relates to the canonical field.

    Meaningful only for row_per_pli layouts (the only layout with traditional
    column headers in rows 1-5). For sheet_is_pli (KV-anchor) and
    section_per_pli layouts, header rows hold data values not column labels,
    so the metric does not meaningfully apply and we return 1.0 (skip).
    """
    if actual.format_detected and actual.format_detected != "row_per_pli":
        return 1.0
    seen: set[tuple[str, str, str]] = set()
    matched = 0
    total = 0
    for pli in actual.plis:
        if not pli.source.sheet:
            continue
        ws = ctx.wb[pli.source.sheet]
        for field, addr in pli.source.cells.items():
            if field not in _VOCAB:
                continue
            col, _ = coordinate_from_string(addr)
            key = (pli.source.sheet, col, field)
            if key in seen:
                continue
            seen.add(key)
            total += 1
            col_idx = column_index_from_string(col)
            header_text = " ".join(
                str(ws.cell(row=r, column=col_idx).value or "").lower()
                for r in range(1, min(6, (ws.max_row or 1) + 1))
            )
            if any(t in header_text for t in _VOCAB[field]):
                matched += 1
    return matched / total if total else 1.0

"""Data rows interleaved with TOTAL summary rows; drop by indicator."""
from openpyxl.utils import column_index_from_string
from app.models.artifacts import PLIBoundaries
from app.services.applier._registry import pattern_handler


@pattern_handler("data_then_total")
def pli_rows(ctx, boundaries: PLIBoundaries) -> list[int]:
    start = boundaries.data_start_row or 2
    end = boundaries.data_end_row or start
    if not (boundaries.total_row_indicator_col and boundaries.total_row_indicator_value):
        return list(range(start, end + 1))
    ws = ctx.wb[boundaries.sheet]
    col_idx = column_index_from_string(boundaries.total_row_indicator_col)
    target = boundaries.total_row_indicator_value.upper()
    return [
        r for r in range(start, end + 1)
        if (v := ws.cell(row=r, column=col_idx).value) is None
        or str(v).strip().upper() != target
    ]

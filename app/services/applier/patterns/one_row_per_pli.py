"""Contiguous data rows — each row is one PLI."""
from app.models.artifacts import PLIBoundaries
from app.services.applier._registry import pattern_handler


@pattern_handler("one_row_per_pli")
def pli_rows(ctx, boundaries: PLIBoundaries) -> list[int]:
    start = boundaries.data_start_row or 2
    end = boundaries.data_end_row or start
    return list(range(start, end + 1))

"""one_sheet_per_pli — applier branches on sheet_iter elsewhere; this returns []."""
from app.models.artifacts import PLIBoundaries
from app.services.applier._registry import pattern_handler


@pattern_handler("one_sheet_per_pli")
def pli_rows(ctx, boundaries: PLIBoundaries) -> list[int]:
    return []

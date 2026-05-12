"""How PLIs are organized in a TNA sheet — drives applier dispatch."""
from enum import Enum


class BoundaryPattern(str, Enum):
    """Four patterns the PLI Boundary Finder can identify."""

    ONE_ROW_PER_PLI = "one_row_per_pli"
    ONE_SHEET_PER_PLI = "one_sheet_per_pli"
    VERTICAL_MERGE = "vertical_merge"
    DATA_THEN_TOTAL = "data_then_total"

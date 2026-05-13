"""Whether a sheet contains one PLI per row, one PLI per section, or is itself one PLI."""
from __future__ import annotations
from enum import Enum


class PliMode(str, Enum):
    ROW_PER_PLI = "row_per_pli"
    SECTION_PER_PLI = "section_per_pli"
    SHEET_IS_PLI = "sheet_is_pli"

"""ReadDirection — how CanvasApplier walks from a PLI anchor to a field's value cell.

SAME_ROW    — value lives at (pli_anchor_row, fixed_col).
              Used when pli_axis=ROW and field is PLI-scoped.
SAME_COLUMN — value lives at (fixed_row, pli_anchor_col).
              Used when pli_axis=COLUMN (transposed) and field is PLI-scoped.
OFFSET      — value lives at (pli_anchor + delta_row, pli_anchor + delta_col).
              Used when value is at a constant offset from the PLI anchor
              (e.g. SECTION_PER_PLI where each section has identifier cells
              at fixed (+1, +2) from the section header).
FIXED       — value lives at a hard-coded cell, ignoring PLI anchor.
              Used for SHEET-scoped fields.
"""
from __future__ import annotations

from enum import Enum


class ReadDirection(str, Enum):
    SAME_ROW    = "same_row"
    SAME_COLUMN = "same_column"
    OFFSET      = "offset"
    FIXED       = "fixed"

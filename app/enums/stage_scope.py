"""Where stage bands live relative to PLIs."""
from __future__ import annotations
from enum import Enum


class StageScope(str, Enum):
    """Classify where a stage band lives relative to PLI nesting."""
    SHEET_LEVEL = "sheet_level"
    SECTION_LOCAL = "section_local"
    PLI_LOCAL = "pli_local"

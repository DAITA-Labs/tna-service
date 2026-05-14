"""How a FieldLocation points at the workbook."""
from enum import Enum


class LocationPattern(str, Enum):
    """Patterns describing how a FieldLocation reads values from the workbook."""

    COLUMN = "column"
    ANCHOR = "anchor"
    MERGED_PROPAGATING = "merged_propagating"

"""How a FieldLocation points at the workbook."""
from enum import Enum


class LocationPattern(str, Enum):
    """column: read down a column. anchor: scattered-KV (label cell + offset).
    merged_propagating: vertical-merge layouts — value walks down merge anchor."""

    COLUMN = "column"
    ANCHOR = "anchor"
    MERGED_PROPAGATING = "merged_propagating"

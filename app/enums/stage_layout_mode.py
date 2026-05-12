"""How stages sub-fields are laid out within a stage band."""
from enum import Enum


class StageLayoutMode(str, Enum):
    """wide_sub_columns: Plan/Actual/Approved columns to the right of stage name.
    tall_sub_rows:   Plan/Action/Deviation rows beneath the stage name."""

    WIDE_SUB_COLUMNS = "wide_sub_columns"
    TALL_SUB_ROWS = "tall_sub_rows"
    MIXED = "mixed"
    UNKNOWN = "unknown"

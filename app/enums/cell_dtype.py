"""Cell data type — closed set of types we let through to the agent layer."""
from enum import Enum


class CellDtype(str, Enum):
    """Cell value classification; unmatched values fall back to STR at tool layer."""

    STR = "str"
    INT = "int"
    FLOAT = "float"
    DATE = "date"
    BOOL = "bool"
    EMPTY = "empty"
    ERROR = "error"

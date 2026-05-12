"""Cell data type — closed set of types we let through to the agent layer."""
from enum import Enum


class CellDtype(str, Enum):
    """Cell value classification. Anything not matching falls back to STR
    at the tool layer."""

    STR = "str"
    INT = "int"
    FLOAT = "float"
    DATE = "date"
    BOOL = "bool"
    EMPTY = "empty"
    ERROR = "error"

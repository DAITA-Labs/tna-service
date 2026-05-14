"""Per-row classification for SheetPlan.

`RowRole` is what kind of row it is (data, header, total, etc.). `SubRowRole`
is which value layer the row represents within a multi-row PLI (plan vs action
vs deviation).
"""
from __future__ import annotations
from enum import Enum


class RowRole(str, Enum):
    """Classify a row's role in the sheet (data, header, total, etc.)."""
    TITLE = "title"
    HEADER = "header"
    ANCHOR = "anchor"
    CHILD = "child"
    TOTAL = "total"
    GRAND_TOTAL = "grand_total"
    REPEAT_HEADER = "repeat_header"
    BLANK = "blank"
    SEPARATOR = "separator"


class SubRowRole(str, Enum):
    """Identify the value layer within a multi-row PLI (plan, action, actual, or deviation)."""
    PLAN = "plan"
    ACTION = "action"
    ACTUAL = "actual"
    DEVIATION = "deviation"

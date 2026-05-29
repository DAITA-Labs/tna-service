"""PliAxis — direction along which PLIs are laid out in the sheet.

Each value implies a different iteration pattern for apply_plan:
  ROW         — apply_plan iterates rows; each row anchors one PLI
  COLUMN      — apply_plan iterates columns; each column anchors one PLI
  WHOLE_SHEET — exactly one PLI; the entire sheet describes it
  SECTION     — multiple PLI sub-sheets; apply_plan recurses per section

A sheet's PliAxis may differ from PliMode classification — e.g. a sheet
classified as ROW_PER_PLI mode might still be COLUMN_WISE in direction
(transposed table). The axis is the authoritative iteration signal.
"""
from __future__ import annotations

from enum import Enum


class PliAxis(str, Enum):
    ROW         = "row"
    COLUMN      = "column"
    WHOLE_SHEET = "whole_sheet"
    SECTION     = "section"

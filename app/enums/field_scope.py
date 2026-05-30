"""FieldScope — at what level a field's value applies across PLIs.

SHEET — one value applies to ALL PLIs in the sheet. Read once; broadcast.
        Typical for buyer, season, ex_factory_date (when sheet-level).
GROUP — one value applies to a GROUP of consecutive PLIs in the sheet.
        Typical for hybrid layouts: first 3 PLIs share an io_number;
        next 4 share a different io_number; etc. Groups are themselves
        detected and named (group_id).
PLI   — one value per PLI. The default for most identifiers and stages.

A single sheet can have fields at MULTIPLE scopes simultaneously.
"""
from __future__ import annotations

from enum import Enum


class FieldScope(str, Enum):
    SHEET = "sheet"
    GROUP = "group"
    PLI   = "pli"

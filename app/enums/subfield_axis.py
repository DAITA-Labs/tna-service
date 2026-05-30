"""SubfieldAxis — how a stage's subfields (planned/actual/etc.) lay out.

HORIZONTAL — subfields are sub-columns to the right of the stage anchor
             (typical for tabular sheets with horizontal stage bands)
VERTICAL   — subfields are sub-rows below the stage anchor
             (typical for SHEET_IS_PLI with stages stacked down rows)
IMPLICIT   — the band carries a single value; no explicit subfield layout
NONE       — sheet has no detectable subfield structure
"""
from __future__ import annotations

from enum import Enum


class SubfieldAxis(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    IMPLICIT   = "implicit"
    NONE       = "none"

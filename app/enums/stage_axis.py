"""StageAxis — how stage bands lay out across the canvas."""
from __future__ import annotations

from enum import Enum


class StageAxis(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL   = "vertical"
    NONE       = "none"

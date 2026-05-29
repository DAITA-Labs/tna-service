"""SubfieldAxis — how a stage's subfields (planned/actual/etc.) lay out."""
from __future__ import annotations

from enum import Enum


class SubfieldAxis(str, Enum):
    HORIZONTAL = "horizontal"
    IMPLICIT   = "implicit"
    NONE       = "none"

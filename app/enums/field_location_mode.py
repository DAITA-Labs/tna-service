"""FieldLocationMode — where a canonical field's value is read from."""
from __future__ import annotations

from enum import Enum


class FieldLocationMode(str, Enum):
    COLUMN   = "column"
    KV_BLOCK = "kv_block"
    MISSING  = "missing"

"""FieldLocationMode — where a canonical field's value is read from.

COLUMN   — values down a column (typical for tabular ROW_PER_PLI fields)
ROW      — values across a row (transposed COLUMN-axis layouts)
KV_BLOCK — single label-value pair (SHEET-scoped metadata + KV identifiers)
MISSING  — canonical not located in this cluster
"""
from __future__ import annotations

from enum import Enum


class FieldLocationMode(str, Enum):
    COLUMN   = "column"
    ROW      = "row"
    KV_BLOCK = "kv_block"
    MISSING  = "missing"

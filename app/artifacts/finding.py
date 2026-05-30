"""ValidationWarning — structural validator output across the canvas chain.

A `ValidationWarning` is the unit of currency between validators, the
plan assembler, and the reviewer gate. Each warning carries a stable
`name` (so downstream policies can recognise it), a `severity`, and a
human-readable `message`.

Filename kept as `finding.py` for import-path stability; the legacy
`Finding` / `Verdict` / `Confidence` types and the v1 canvas chain
that operated on them were retired alongside the per-canonical
extractor pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class ValidationWarning:
    """Structural validator output flagging a constraint violation.

    Severities follow standard log levels: 'info' for advisory signals,
    'warning' for likely issues, 'error' for hard contract violations.
    """

    name:     str
    severity: Literal["info", "warning", "error"]
    message:  str

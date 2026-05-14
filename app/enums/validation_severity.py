"""Severity of a ValidationFinding."""
from __future__ import annotations

from enum import Enum


class ValidationSeverity(str, Enum):
    """Classify validation finding severity levels."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

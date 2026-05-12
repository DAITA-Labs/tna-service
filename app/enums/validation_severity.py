"""Severity of a ValidationFinding."""
from enum import Enum


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

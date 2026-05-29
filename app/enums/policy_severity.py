"""PolicySeverity — optional severity tag a policy may attach to its verdict."""
from __future__ import annotations

from enum import Enum


class PolicySeverity(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"

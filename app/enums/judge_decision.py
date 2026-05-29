"""JudgeDecision — terminal decision emitted by CanvasPlanReviewer."""
from __future__ import annotations

from enum import Enum


class JudgeDecision(str, Enum):
    APPROVE  = "approve"
    MODIFY   = "modify"
    ESCALATE = "escalate"

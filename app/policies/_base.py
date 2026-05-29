"""PolicyVerdict + aggregation helper — universal return shape for any policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyVerdict:
    """One policy's vote on one candidate.

    The `candidate` is opaque to the verdict — each picker defines its own
    candidate shape (a row index, a column index, a KvBlock, a canonical
    name, etc.). The picker is responsible for interpreting it.
    """

    name:        str
    candidate:   Any
    score_delta: float = 0.0
    eliminate:   bool  = False
    message:     str   = ""


def aggregate_verdicts(verdicts: list[PolicyVerdict]) -> tuple[float, bool]:
    """Combine a candidate's per-policy verdicts into (total_score, eliminated).

    Score deltas sum; elimination is OR (any single policy can disqualify).
    The caller compares total scores across surviving candidates to pick
    a winner.
    """
    if not verdicts:
        return 0.0, False
    total = sum(v.score_delta for v in verdicts)
    eliminated = any(v.eliminate for v in verdicts)
    return total, eliminated

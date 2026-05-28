"""IdentifierFindingJudge I/O schemas.

The judge takes a `FindingForJudge` describing one ambiguous identifier
Finding plus its context (sheet excerpt, spec snippet, competing claims,
validator warnings) and returns an `IdentifierVerdict` saying whether to
keep, drop, or rewrite the finding.

`IdentifierFindingAudit` is the trace record the gate emits for each
finding the judge reviewed — consumed downstream by `IdentifierPhaseGate`
so the phase judge can see what per-finding judging decided.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.artifacts.finding import Finding, ValidationWarning


# Coordinate type is the same `(column_letter, row_index)` shape used
# everywhere else in the codebase. Pydantic accepts tuples as input.
Coord = tuple[str, int]


class FindingForJudge(BaseModel):
    """Inputs to the IdentifierFindingJudge — one ambiguous finding + its context.

    `sheet_excerpt` is a pre-rendered string view of the cells around the
    finding's `value_coord`. The judge consumes the excerpt as text; it
    does not navigate the canvas itself. Likewise `spec_snippet` is the
    canonical's FieldSpec description + patterns + anti-patterns, already
    formatted for the LLM.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    finding:                Finding
    sheet_excerpt:          str
    spec_snippet:           str
    alternative_candidates: list[Finding] = Field(default_factory=list)
    validator_warnings:     list[ValidationWarning] = Field(default_factory=list)
    cluster_context:        str = ""


class IdentifierVerdict(AgentOutput):
    """The judge's decision for one Finding.

    `alternative_coord` is required when `decision == "rewrite"` and
    forbidden otherwise. The post-LLM validator enforces this invariant
    so callers can trust it without re-checking.
    """

    decision:           Literal["keep", "drop", "rewrite"]
    alternative_coord:  Coord | None = None
    reason:             str = Field(min_length=1, max_length=500)
    confidence:         Literal["high", "medium", "low"]


@dataclass(frozen=True)
class IdentifierFindingAudit:
    """One row in the per-finding judging trail, parallel to the input bag.

    The gate emits one of these for every input finding it considered.
    `verdict` is `None` when the finding was never routed to the judge
    (no ambiguity trigger); `judge_failed=True` when the judge produced
    an `AgentRunFailure` and the original finding was kept (fail-safe).
    """

    finding_index: int
    verdict:       IdentifierVerdict | None = None
    judge_failed:  bool = False

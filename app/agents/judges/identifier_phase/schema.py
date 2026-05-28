"""IdentifierPhaseJudge I/O schemas.

The phase judge sees the entire identifier bag plus the per-finding
judging trail (audits) plus the warnings still present after per-finding
adjudication. It emits one decision per raw finding — its decisions
override the per-finding outcomes when they conflict.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.judges.identifier_finding.schema import (
    Coord,
    IdentifierFindingAudit,
)
from app.artifacts.agent_io import AgentOutput
from app.artifacts.finding import Finding, ValidationWarning


class IdentifierPhaseForJudge(BaseModel):
    """Inputs to the phase judge — full bag, audits, warnings, context."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    raw_findings:  list[Finding]
    audits:        list[IdentifierFindingAudit] = Field(default_factory=list)
    warnings:      list[ValidationWarning] = Field(default_factory=list)
    pli_rows:      list[int] = Field(default_factory=list)
    spec_snippets: dict[str, str] = Field(default_factory=dict)
    sheet_summary: str = ""


class FindingDecision(BaseModel):
    """One phase-level decision for a single raw finding."""

    finding_index:      int
    decision:           Literal["keep", "drop", "rewrite"]
    alternative_coord:  Coord | None = None
    reason:             str = Field(min_length=1, max_length=400)


class IdentifierPhaseVerdict(AgentOutput):
    """The phase judge's final decision set across the identifier bag."""

    decisions:   list[FindingDecision] = Field(default_factory=list)
    summary:     str = Field(min_length=1, max_length=1000)
    confidence:  Literal["high", "medium", "low"]

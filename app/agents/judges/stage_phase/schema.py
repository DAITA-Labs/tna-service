"""StagePhaseJudge I/O schemas.

The phase judge sees the entire stages_per_row map + per-stage audits
+ warnings still affecting stages, and emits decisions keyed by
`(row, stage_index)` into the raw stages_per_row map.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.judges.stage_finding.schema import StageFindingAudit
from app.artifacts.agent_io import AgentOutput
from app.artifacts.finding import ValidationWarning
from app.specs.schemas import FinalStage


class StagePhaseForJudge(BaseModel):
    """Inputs to the phase judge — full stage map + audits + warnings."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    raw_stages_per_row: dict[int, list[FinalStage]]
    audits:             list[StageFindingAudit] = Field(default_factory=list)
    warnings:           list[ValidationWarning] = Field(default_factory=list)
    stage_catalog:      str = ""
    sheet_summary:      str = ""


class StageDecision(BaseModel):
    """One phase-level decision for a single (row, stage_index) pair."""

    row:                    int
    stage_index:            int
    decision:               Literal["keep", "drop", "rewrite"]
    alternative_canonical:  str | None = None
    reason:                 str = Field(min_length=1, max_length=400)


class StagePhaseVerdict(AgentOutput):
    """The phase judge's final decision set across the stages_per_row map."""

    decisions:   list[StageDecision] = Field(default_factory=list)
    summary:     str = Field(min_length=1, max_length=1000)
    confidence:  Literal["high", "medium", "low"]

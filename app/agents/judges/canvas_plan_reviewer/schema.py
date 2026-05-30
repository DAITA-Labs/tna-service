"""CanvasPlanReviewer I/O schemas.

The reviewer takes the assembled `CanvasPlan` (plus pre-rendered
summaries of its scoreboards and warnings) and emits a
`PlanReviewVerdict` saying whether to approve the plan, re-pick one or
more canonicals from their scoreboards, or escalate (operator review).

Why a literal discriminator over an enum: keeps the JSON schema flat
and matches the existing canvas judges' wire format.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.artifacts.finding import ValidationWarning


class CanvasPlanReviewerInputs(BaseModel):
    """Inputs to the reviewer — pre-rendered summaries + cluster context.

    Rendering happens in the gate so the agent stays cheap to test. The
    gate is also where evidence access (canvas peeks, scoreboard reads)
    lives; the agent itself just sees text.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    plan_summary:       str
    scoreboard_summary: str
    warnings:           list[ValidationWarning] = Field(default_factory=list)
    cluster_context:    str = ""


class CanonicalRepick(BaseModel):
    """One canonical that the reviewer wants relocated.

    The reviewer picks an alternative `LocationCandidate` mode + coord
    from the scoreboard it was shown. The gate matches `(mode, coord)`
    against `plan.scoreboards[canonical]` to confirm the candidate
    exists; unmatched repicks become validation warnings, not silent
    drops.
    """

    canonical: str = Field(min_length=1)
    mode:      Literal["column", "row", "kv_block"]
    column:    int | None = None
    row:       int | None = None
    # 1-indexed (column_letter, row) coord of the KvBlock's label cell.
    kv_label_coord: tuple[str, int] | None = None


class PlanReviewVerdict(AgentOutput):
    """Reviewer's decision on the assembled CanvasPlan.

    - `approve`   — plan flows through unchanged.
    - `repick`    — each `CanonicalRepick` swaps one canonical's winner
                     for an alternative the scoreboard already considered.
    - `escalate`  — reviewer can't make a defensible call; gate attaches
                     a warning so an operator can investigate.
    """

    decision:   Literal["approve", "repick", "escalate"]
    repicks:    list[CanonicalRepick] = Field(default_factory=list)
    reason:     str = Field(min_length=1, max_length=500)
    confidence: Literal["high", "medium", "low"]

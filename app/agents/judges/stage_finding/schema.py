"""StageFindingJudge I/O schemas.

The judge reviews one `FinalStage` whose `canonical` is `None` — a
novel label the deterministic alias matcher couldn't catalog-resolve.
The judge decides whether the label should map to a known canonical
from `STAGE_SPECS`, get dropped entirely, or stay as open-vocab.

`StageFindingAudit` is the trace record the gate emits for each
stage the judge reviewed — consumed downstream by `StagePhaseGate`
so the phase judge can see what per-finding judging decided.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.specs.schemas import FinalStage


class StageFindingForJudge(BaseModel):
    """Inputs to the StageFindingJudge — one open-vocab stage + context.

    The judge consumes the catalog snippet as text; it does not navigate
    the spec module itself. `sheet_excerpt` is the rendered cell grid
    around the stage's name cell.
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    stage:            FinalStage
    row:              int             # which PLI row this stage belongs to
    stage_catalog:    str
    sheet_excerpt:    str
    cluster_context:  str = ""


class StageVerdict(AgentOutput):
    """The judge's decision for one stage.

    `alternative_canonical` is required when `decision == "rewrite"` and
    forbidden otherwise. The post-LLM validator enforces this.
    """

    decision:               Literal["keep", "drop", "rewrite"]
    alternative_canonical:  str | None = None
    reason:                 str = Field(min_length=1, max_length=500)
    confidence:             Literal["high", "medium", "low"]


@dataclass(frozen=True)
class StageFindingAudit:
    """One row in the per-stage judging trail.

    `row` is the PLI row this stage lives in; `stage_index` is its
    position in `stages_per_row[row]`. `verdict` is None when the
    stage was never routed to the judge (canonical was already set
    or name was blank); `judge_failed` flags `AgentRunFailure` cases
    where the gate kept the original stage as fail-safe.
    """

    row:          int
    stage_index:  int
    verdict:      StageVerdict | None = None
    judge_failed: bool = False

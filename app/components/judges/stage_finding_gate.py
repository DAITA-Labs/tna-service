"""StageFindingGate — routes open-vocab stages to StageFindingJudge.

A pipeline-facing Haystack component that owns one StageFindingJudge
agent privately and decides which FinalStages need adjudication. The
trigger is purely the open-vocab signal:

    stage.canonical is None AND stage.name

A stage whose name didn't match any STAGE_SPECS alias gets routed to
the judge. Stages with a canonical already set flow through unchanged.

Verdict application:
  - keep    → stage unchanged (legitimately novel)
  - drop    → stage removed from the row's list
  - rewrite → stage.canonical = alternative_canonical;
              stage.judge_action = f"canonical_set_to_{alt}"

AgentRunFailure (LLM down / repeated schema failures) keeps the
original stage — fail-safe.
"""
from __future__ import annotations

from openpyxl.utils import column_index_from_string, get_column_letter

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.judges.stage_finding import StageFindingJudge
from app.agents.judges.stage_finding.schema import (
    StageFindingForJudge,
    StageVerdict,
)
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.judges._render import render_sheet_excerpt
from app.inferencing._base import BaseProvider
from app.specs.schemas import FinalStage
from app.specs.stages import STAGE_SPECS


@component
class StageFindingGate(Component):
    """Adjudicate every novel-canonical FinalStage via StageFindingJudge."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = StageFindingJudge()
        self._llm = llm

    @component.output_types(stages_per_row=dict[int, list[FinalStage]])
    def run(
        self,
        stages_per_row: dict[int, list[FinalStage]],
        bundle: ClusterAnchorBundle,
    ) -> dict:
        if not stages_per_row:
            return {"stages_per_row": {}}

        out: dict[int, list[FinalStage]] = {}
        for row, stages in stages_per_row.items():
            adjudicated: list[FinalStage] = []
            for stage in stages:
                if not _is_novel(stage):
                    adjudicated.append(stage)
                    continue
                kept = self._judge_one(stage, row, bundle)
                if kept is not None:
                    adjudicated.append(kept)
            out[row] = adjudicated
        return {"stages_per_row": out}

    def _judge_one(
        self,
        stage: FinalStage,
        row: int,
        bundle: ClusterAnchorBundle,
    ) -> FinalStage | None:
        """Invoke the judge; return the adjudicated stage (or None to drop)."""
        inputs = StageFindingForJudge(
            stage=stage,
            row=row,
            stage_catalog=_render_stage_catalog(),
            sheet_excerpt=_render_stage_excerpt(bundle, stage),
            cluster_context=(
                f"cluster_id={bundle.cluster.cluster_id} sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("judge_fallback_kept_stage",
                              stage_name=stage.name, reason=verdict.reason)
            return stage
        return _apply_verdict(stage, verdict)


def _is_novel(stage: FinalStage) -> bool:
    """A stage needing the judge: no canonical, but has a non-empty name."""
    return stage.canonical is None and bool(stage.name and stage.name.strip())


def _apply_verdict(stage: FinalStage, verdict: StageVerdict) -> FinalStage | None:
    """Return the adjudicated stage, or None when the verdict says drop."""
    if verdict.decision == "drop":
        return None
    if verdict.decision == "keep":
        return stage
    return stage.model_copy(update={
        "canonical": verdict.alternative_canonical,
        "judge_action": f"canonical_set_to_{verdict.alternative_canonical}",
    })


def _render_stage_catalog() -> str:
    """Render every STAGE_SPECS entry as a prompt-ready block."""
    lines: list[str] = []
    for spec in STAGE_SPECS:
        aliases = ", ".join(spec.aliases) if spec.aliases else "(no aliases)"
        lines.append(f"- {spec.canonical} — {spec.description}")
        lines.append(f"    aliases: {aliases}")
    return "\n".join(lines)


def _render_stage_excerpt(bundle: ClusterAnchorBundle, stage: FinalStage) -> str:
    """Show the cells around the stage's column range and plan_date row.

    The "center" cell is the stage's plan_date column (or the start of
    column_range as a fallback). We use a wider column window than
    identifier findings since stages live in their own band.
    """
    canvas = bundle.canvas
    if stage.plan_date_col is not None:
        col_letter = get_column_letter(stage.plan_date_col)
    elif stage.column_range is not None:
        col_letter = get_column_letter(stage.column_range[0])
    else:
        col_letter = "A"
    # Anchor row: prefer the band's header row when known, else the first canvas row.
    row = max(1, canvas.n_rows // 4)
    return render_sheet_excerpt(canvas, (col_letter, row), half_rows=3, half_cols=4)

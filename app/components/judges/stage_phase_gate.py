"""StagePhaseGate — bag-level arbiter for stages_per_row.

Runs AFTER `StageFindingGate` and reads two parallel inputs: the raw
stages_per_row map (pre per-stage judging) and the audits that per-stage
judging emitted. The phase judge sees both plus residual warnings and
emits decisions keyed by `(row, stage_index)` that override per-stage.

Trigger: invoke the LLM only when there's residual signal worth
arbitrating — any warning still in `warnings`, OR any audit with
`judge_failed=True`. Otherwise return the post-per-stage map as a
pass-through.

AgentRunFailure on the phase judge → return the post-per-stage map
unchanged (per-stage outcomes win by default).
"""
from __future__ import annotations

from haystack import component

from app.agents._base import AgentRunFailure
from app.agents.judges.stage_finding.schema import StageFindingAudit, StageVerdict
from app.agents.judges.stage_phase import StagePhaseJudge
from app.agents.judges.stage_phase.schema import (
    StageDecision,
    StagePhaseForJudge,
)
from app.artifacts.finding import ValidationWarning
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.inferencing._base import BaseProvider
from app.specs.schemas import FinalStage
from app.specs.stages import STAGE_SPECS


@component
class StagePhaseGate(Component):
    """Run StagePhaseJudge when residual warnings or per-stage failures remain."""

    def __init__(self, llm: BaseProvider) -> None:
        Component.__init__(self)
        self._agent = StagePhaseJudge()
        self._llm = llm

    @component.output_types(stages_per_row=dict[int, list[FinalStage]])
    def run(
        self,
        raw_stages_per_row: dict[int, list[FinalStage]],
        audits:             list[StageFindingAudit],
        warnings:           list[ValidationWarning],
        bundle:             ClusterAnchorBundle,
    ) -> dict:
        post_stage = _apply_audits(raw_stages_per_row, audits)
        if not _should_invoke(warnings, audits):
            return {"stages_per_row": post_stage}

        inputs = StagePhaseForJudge(
            raw_stages_per_row=raw_stages_per_row,
            audits=audits,
            warnings=warnings,
            stage_catalog=_render_stage_catalog(),
            sheet_summary=(
                f"cluster_id={bundle.cluster.cluster_id} sheet={bundle.anchor_sheet_name}"
            ),
        )
        verdict = self._agent.run(ctx=bundle, inputs=inputs, provider=self._llm)
        if isinstance(verdict, AgentRunFailure):
            self.log.warning("phase_judge_fallback_kept_bag",
                              phase="stage", reason=verdict.reason)
            return {"stages_per_row": post_stage}
        return {"stages_per_row": _apply_phase_decisions(
            raw_stages_per_row, verdict.decisions, post_stage,
        )}


# ── module-level pure helpers ───────────────────────────────────────────


def _should_invoke(
    warnings: list[ValidationWarning],
    audits:   list[StageFindingAudit],
) -> bool:
    """The phase judge fires when there's residual signal worth arbitrating."""
    if warnings:
        return True
    return any(a.judge_failed for a in audits)


def _apply_audits(
    raw_stages_per_row: dict[int, list[FinalStage]],
    audits:             list[StageFindingAudit],
) -> dict[int, list[FinalStage]]:
    """Reconstruct the post-per-stage map from raw + audits."""
    audits_by_key = {(a.row, a.stage_index): a for a in audits}
    out: dict[int, list[FinalStage]] = {}
    for row, stages in raw_stages_per_row.items():
        kept: list[FinalStage] = []
        for idx, stage in enumerate(stages):
            audit = audits_by_key.get((row, idx))
            if audit is None:
                kept.append(stage)
                continue
            if audit.judge_failed or audit.verdict is None:
                kept.append(stage)
                continue
            adjudicated = _apply_single_verdict(stage, audit.verdict)
            if adjudicated is not None:
                kept.append(adjudicated)
        out[row] = kept
    return out


def _apply_phase_decisions(
    raw_stages_per_row: dict[int, list[FinalStage]],
    decisions:          list[StageDecision],
    post_stage:         dict[int, list[FinalStage]],
) -> dict[int, list[FinalStage]]:
    """Override post-per-stage outcomes with the phase judge's decisions."""
    decisions_by_key = {(d.row, d.stage_index): d for d in decisions}
    out: dict[int, list[FinalStage]] = {}

    for row, stages in raw_stages_per_row.items():
        kept: list[FinalStage] = []
        for idx, stage in enumerate(stages):
            decision = decisions_by_key.get((row, idx))
            if decision is None:
                # No phase override → use the post-per-stage version, if any.
                surviving = _find_surviving(post_stage, row, stage, idx)
                if surviving is not None:
                    kept.append(surviving)
                continue
            if decision.decision == "drop":
                continue
            if decision.decision == "keep":
                kept.append(stage)
                continue
            kept.append(stage.model_copy(update={
                "canonical": decision.alternative_canonical,
                "judge_action": f"phase_canonical_set_to_{decision.alternative_canonical}",
            }))
        out[row] = kept
    return out


def _find_surviving(
    post_stage: dict[int, list[FinalStage]],
    row:        int,
    raw_stage:  FinalStage,
    raw_index:  int,
) -> FinalStage | None:
    """Look up the post-per-stage version of a raw stage; None if dropped."""
    row_stages = post_stage.get(row, [])
    # Best-effort match: same name + same plan_date_col. If multiple match,
    # pick by position-ish (we maintain order in _apply_audits).
    for candidate in row_stages:
        if candidate.name == raw_stage.name and candidate.plan_date_col == raw_stage.plan_date_col:
            return candidate
    return None


def _apply_single_verdict(
    stage:   FinalStage,
    verdict: StageVerdict,
) -> FinalStage | None:
    """Apply one StageVerdict (mirror of stage_finding_gate._apply_verdict)."""
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

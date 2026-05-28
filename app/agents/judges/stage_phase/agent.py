"""StagePhaseJudge — single LLM call adjudicating the stages_per_row map."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.stage_phase.schema import (
    StagePhaseForJudge,
    StagePhaseVerdict,
)
from app.agents.judges.stage_phase.tuning import StagePhaseJudgeTuning
from app.agents.judges.stage_phase.validators import validate_stage_phase_verdict
from app.prompts.judges import STAGE_PHASE_JUDGE


class StagePhaseJudge(Agent):
    """Final-call arbiter over stages_per_row + per-stage audits + warnings."""

    name = "stage_phase_judge"
    prompt = STAGE_PHASE_JUDGE
    output_schema = StagePhaseVerdict
    tuning = StagePhaseJudgeTuning()

    def build_input(self, ctx: Any, inputs: StagePhaseForJudge) -> str:
        """Render the per-call prompt body from the StagePhaseForJudge bundle."""
        lines: list[str] = ["## Stages per row"]
        audits_by_key = {(a.row, a.stage_index): a for a in inputs.audits}

        for row in sorted(inputs.raw_stages_per_row):
            stages = inputs.raw_stages_per_row[row]
            lines.append(f"### Row {row}")
            for idx, stage in enumerate(stages):
                audit = audits_by_key.get((row, idx))
                lines.append(
                    f"  [{idx}] name={stage.name!r} canonical={stage.canonical} "
                    f"plan_date={stage.plan_date} — {_format_audit(audit)}"
                )

        if inputs.warnings:
            lines.append("")
            lines.append("## Residual validator warnings")
            for w in inputs.warnings:
                lines.append(f"  [{w.severity}] {w.name}: {w.message}")

        if inputs.stage_catalog:
            lines.append("")
            lines.append("## Stage catalog")
            lines.append(inputs.stage_catalog.strip())

        if inputs.sheet_summary:
            lines.append("")
            lines.append("## Sheet summary")
            lines.append(f"  {inputs.sheet_summary}")

        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """Pydantic enforces input shape; nothing extra to check pre-LLM."""
        return InputVerdict.ok()

    def validate_output(self, output: StagePhaseVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the cross-decision invariant validator."""
        return validate_stage_phase_verdict(output, ctx)


def _format_audit(audit) -> str:
    """One-line description of what per-stage judging did to this stage."""
    if audit is None:
        return "(not routed to per-stage judge)"
    if audit.judge_failed:
        return "(per-stage judge failed; original kept as fail-safe)"
    v = audit.verdict
    if v is None:
        return "(no verdict recorded)"
    if v.decision == "rewrite":
        return (
            f"per-stage said REWRITE→canonical={v.alternative_canonical} "
            f"({v.confidence}): {v.reason}"
        )
    return f"per-stage said {v.decision.upper()} ({v.confidence}): {v.reason}"

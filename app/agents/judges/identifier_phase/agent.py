"""IdentifierPhaseJudge — single LLM call adjudicating the identifier bag."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.identifier_phase.schema import (
    IdentifierPhaseForJudge,
    IdentifierPhaseVerdict,
)
from app.agents.judges.identifier_phase.tuning import IdentifierPhaseJudgeTuning
from app.agents.judges.identifier_phase.validators import (
    validate_identifier_phase_verdict,
)
from app.prompts.judges import IDENTIFIER_PHASE_JUDGE


class IdentifierPhaseJudge(Agent):
    """Final-call arbiter over the full identifier bag + per-finding audits + warnings."""

    name = "identifier_phase_judge"
    prompt = IDENTIFIER_PHASE_JUDGE
    output_schema = IdentifierPhaseVerdict
    tuning = IdentifierPhaseJudgeTuning()

    def build_input(self, ctx: Any, inputs: IdentifierPhaseForJudge) -> str:
        """Render the per-call prompt body from the IdentifierPhaseForJudge bundle."""
        lines: list[str] = ["## Raw findings (index → finding)"]
        audit_by_index = {a.finding_index: a for a in inputs.audits}

        for idx, finding in enumerate(inputs.raw_findings):
            audit = audit_by_index.get(idx)
            audit_text = _format_audit(audit)
            lines.append(
                f"  [{idx}] {finding.canonical}={finding.value!r} at "
                f"{finding.value_coord[0]}{finding.value_coord[1]} "
                f"(confidence={finding.confidence.value}) — {audit_text}"
            )

        lines.append("")
        lines.append(f"## PLI rows ({len(inputs.pli_rows)})")
        lines.append(f"  {sorted(inputs.pli_rows)}")

        if inputs.warnings:
            lines.append("")
            lines.append("## Residual validator warnings")
            for w in inputs.warnings:
                affects = [
                    f"[{i}]" for i, f in enumerate(inputs.raw_findings) if w.affects(f)
                ]
                affects_text = f" affects: {','.join(affects)}" if affects else ""
                lines.append(f"  [{w.severity}] {w.name}: {w.message}{affects_text}")

        if inputs.spec_snippets:
            lines.append("")
            lines.append("## Spec snippets")
            for canonical, snippet in inputs.spec_snippets.items():
                lines.append(f"### {canonical}")
                lines.append(snippet.strip())

        if inputs.sheet_summary:
            lines.append("")
            lines.append("## Sheet summary")
            lines.append(f"  {inputs.sheet_summary}")

        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """Pydantic enforces input shape; nothing extra to check pre-LLM."""
        return InputVerdict.ok()

    def validate_output(self, output: IdentifierPhaseVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the cross-decision invariant validator."""
        return validate_identifier_phase_verdict(output, ctx)


def _format_audit(audit) -> str:
    """One-line description of what per-finding judging did to this finding."""
    if audit is None:
        return "(not routed to per-finding judge)"
    if audit.judge_failed:
        return "(per-finding judge failed; original kept as fail-safe)"
    v = audit.verdict
    if v is None:
        return "(no verdict recorded)"
    if v.decision == "rewrite":
        coord_text = (
            f"{v.alternative_coord[0]}{v.alternative_coord[1]}"
            if v.alternative_coord else "?"
        )
        return f"per-finding said REWRITE→{coord_text} ({v.confidence}): {v.reason}"
    return f"per-finding said {v.decision.upper()} ({v.confidence}): {v.reason}"

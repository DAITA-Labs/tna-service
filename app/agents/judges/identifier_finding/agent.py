"""IdentifierFindingJudge — single LLM call reviewing one ambiguous identifier Finding."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.identifier_finding.schema import (
    FindingForJudge,
    IdentifierVerdict,
)
from app.agents.judges.identifier_finding.tuning import IdentifierJudgeTuning
from app.agents.judges.identifier_finding.validators import validate_identifier_verdict
from app.prompts.judges import IDENTIFIER_FINDING_JUDGE


class IdentifierFindingJudge(Agent):
    """LLM as reviewer: judge one ambiguous identifier Finding → keep / drop / rewrite."""

    name = "identifier_finding_judge"
    prompt = IDENTIFIER_FINDING_JUDGE
    output_schema = IdentifierVerdict
    tuning = IdentifierJudgeTuning()

    def build_input(self, ctx: Any, inputs: FindingForJudge) -> str:
        """Render the per-call prompt body from the FindingForJudge bundle."""
        f = inputs.finding
        lines: list[str] = [
            "## Finding under review",
            f"  canonical:  {f.canonical}",
            f"  value:      {f.value!r}",
            f"  value_coord: {f.value_coord[0]}{f.value_coord[1]}",
            f"  label_coord: {f.label_coord[0]}{f.label_coord[1]}",
            f"  confidence: {f.confidence.value}",
            f"  evidence:   {f.evidence}",
            "",
            "## Spec snippet",
            inputs.spec_snippet.strip() or "(no spec snippet)",
            "",
            "## Sheet excerpt",
            inputs.sheet_excerpt.strip() or "(no excerpt)",
            "",
        ]

        if inputs.alternative_candidates:
            lines.append("## Alternative candidates")
            for alt in inputs.alternative_candidates:
                lines.append(
                    f"  {alt.canonical} = {alt.value!r} at "
                    f"{alt.value_coord[0]}{alt.value_coord[1]} "
                    f"(confidence={alt.confidence.value})"
                )
            lines.append("")

        if inputs.validator_warnings:
            lines.append("## Validator warnings")
            for w in inputs.validator_warnings:
                lines.append(f"  [{w.severity}] {w.name}: {w.message}")
            lines.append("")

        if inputs.cluster_context:
            lines.append("## Cluster context")
            lines.append(f"  {inputs.cluster_context}")

        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """Pydantic enforces input shape; nothing extra to check pre-LLM."""
        return InputVerdict.ok()

    def validate_output(self, output: IdentifierVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the cross-field semantic validator."""
        return validate_identifier_verdict(output, ctx)

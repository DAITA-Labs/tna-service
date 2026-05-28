"""StageFindingJudge — single LLM call mapping a novel stage label onto STAGE_SPECS."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.stage_finding.schema import (
    StageFindingForJudge,
    StageVerdict,
)
from app.agents.judges.stage_finding.tuning import StageJudgeTuning
from app.agents.judges.stage_finding.validators import validate_stage_verdict
from app.prompts.judges import STAGE_FINDING_JUDGE


class StageFindingJudge(Agent):
    """Map one open-vocab `FinalStage` onto a STAGE_SPECS canonical (or keep / drop)."""

    name = "stage_finding_judge"
    prompt = STAGE_FINDING_JUDGE
    output_schema = StageVerdict
    tuning = StageJudgeTuning()

    def build_input(self, ctx: Any, inputs: StageFindingForJudge) -> str:
        """Render the per-call prompt body from the StageFindingForJudge bundle."""
        s = inputs.stage
        lines: list[str] = [
            "## Stage under review",
            f"  name:           {s.name!r}",
            f"  canonical:      {s.canonical}",
            f"  plan_date:      {s.plan_date}",
            f"  plan_date_col:  {s.plan_date_col}",
            f"  column_range:   {s.column_range}",
            f"  pli_row:        {inputs.row}",
        ]
        if s.stage_metadata:
            lines.append(f"  stage_metadata: {dict(s.stage_metadata)}")
        lines.extend([
            "",
            "## Stage catalog (known canonicals + aliases)",
            inputs.stage_catalog.strip() or "(catalog unavailable)",
            "",
            "## Sheet excerpt around the stage name cell",
            inputs.sheet_excerpt.strip() or "(no excerpt)",
        ])
        if inputs.cluster_context:
            lines.append("")
            lines.append("## Cluster context")
            lines.append(f"  {inputs.cluster_context}")
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """Pydantic enforces input shape; nothing extra to check pre-LLM."""
        return InputVerdict.ok()

    def validate_output(self, output: StageVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the cross-field + catalog-membership validator."""
        return validate_stage_verdict(output, ctx)

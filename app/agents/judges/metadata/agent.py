"""MetadataFindingJudge — single LLM call adjudicating one novel metadata entry."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.judges.metadata.schema import (
    MetadataFindingForJudge,
    MetadataVerdict,
)
from app.agents.judges.metadata.tuning import MetadataJudgeTuning
from app.agents.judges.metadata.validators import validate_metadata_verdict
from app.prompts.judges import METADATA_FINDING_JUDGE


class MetadataFindingJudge(Agent):
    """Map one open-vocab `MetadataEntry` onto a METADATA_SPECS canonical (or keep / drop)."""

    name = "metadata_finding_judge"
    prompt = METADATA_FINDING_JUDGE
    output_schema = MetadataVerdict
    tuning = MetadataJudgeTuning()

    def build_input(self, ctx: Any, inputs: MetadataFindingForJudge) -> str:
        """Render the per-call prompt body from the MetadataFindingForJudge bundle."""
        m = inputs.metadata
        lines: list[str] = [
            "## Metadata entry under review",
            f"  key:        {m.key!r}",
            f"  value:      {m.value!r}",
            f"  source:     {m.source}",
            f"  canonical:  {m.canonical}",
            f"  scope:      {m.scope.value if hasattr(m.scope, 'value') else m.scope}",
            "",
            "## Metadata catalog (known canonical hints + aliases)",
            inputs.metadata_catalog.strip() or "(catalog unavailable)",
            "",
            "## Sheet excerpt around the source cell",
            inputs.sheet_excerpt.strip() or "(no excerpt)",
        ]
        if inputs.cluster_context:
            lines.append("")
            lines.append("## Cluster context")
            lines.append(f"  {inputs.cluster_context}")
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """Pydantic enforces input shape; nothing extra to check pre-LLM."""
        return InputVerdict.ok()

    def validate_output(self, output: MetadataVerdict, ctx: Any) -> OutputVerdict:
        """Delegate to the cross-field + catalog-membership validator."""
        return validate_metadata_verdict(output, ctx)

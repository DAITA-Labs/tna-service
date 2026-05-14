"""FieldNamer agent — maps detected labels and stage column headers to canonical field names."""
from __future__ import annotations

from pathlib import Path

from haystack import component

from app.core.logs import get_logger
from app.core.prompt_loader import load_prompt
from app.models.artifacts import CanonicalNameMap, SheetPlan
from app.services.agents._base import AgentRunFailure, AgentRunner, AgentSpec
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from a SheetPlan's detected labels and stage headers.

    Collects all KV-anchor fields, PLI identity fields, and stage-band column
    headers from `inputs["plan"]`, then formats them as a markdown block the
    field_namer system prompt expects.
    """
    plan: SheetPlan = inputs["plan"]
    labels = {kv.field for kv in plan.kv_anchors}
    for blk in plan.pli_blocks:
        for kv in blk.identity:
            labels.add(kv.field)
    stage_headers: set[str] = set()
    for band in plan.stage_bands:
        stage_headers.update(band.stage_cols.keys())
    for blk in plan.pli_blocks:
        for band in blk.stage_bands:
            stage_headers.update(band.stage_cols.keys())

    lines = [f"# Sheet: {plan.sheet}",
             "## Detected labels:"]
    for label in sorted(labels):
        lines.append(f"  - {label!r}")
    lines.append("")
    lines.append("## Detected stage column headers:")
    for header in sorted(stage_headers):
        lines.append(f"  - {header!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="field_namer",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "field_namer.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=CanonicalNameMap,
    build_user_input=_build_user_input,
)


@component
class FieldNamer:
    """Haystack component that resolves raw cell labels to canonical field names.

    Accepts a SheetPlan and produces a CanonicalNameMap; fires once per sheet
    during the field-naming phase of the pipeline.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Wire up the underlying AgentRunner with the field_namer spec."""
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(name_map=CanonicalNameMap)
    def run(self, workbook_ctx: object, plan: SheetPlan) -> dict:
        """Run the field-namer agent and return a canonical name mapping.

        Falls back to an empty CanonicalNameMap on agent failure so the
        pipeline can continue with best-effort names.
        """
        result = self.runner.run(workbook_ctx, {"plan": plan})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="field_namer")
            return {"name_map": CanonicalNameMap()}
        return {"name_map": result}

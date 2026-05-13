"""FieldNamer — map detected labels and stage column headers to canonical names."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import CanonicalNameMap, SheetPlan
from app.services.llm_provider import LLMProvider
from app.core.prompt_loader import load_prompt
from app.core.logs import get_logger

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
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
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(name_map=CanonicalNameMap)
    def run(self, workbook_ctx: Any, plan: SheetPlan) -> dict:
        result = self.runner.run(workbook_ctx, {"plan": plan})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="field_namer")
            return {"name_map": CanonicalNameMap()}
        return {"name_map": result}

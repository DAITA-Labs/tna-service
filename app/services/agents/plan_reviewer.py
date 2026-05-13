"""PlanReviewer — LLM judge of SheetPlan correctness.

Fires only when Tier 1/2 validators warned, plan confidence is low, or mode
is one of the rarer modes (SECTION_PER_PLI / SHEET_IS_PLI).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import PlanVerdict, SheetPlan, ValidationFinding
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt
from app.core.logs import get_logger

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    plan: SheetPlan = inputs["plan"]
    findings: list[ValidationFinding] = inputs.get("findings", [])
    sheet = plan.sheet
    peek = TOOL_REGISTRY.get("peek_sheet")
    grid = peek(ctx, sheet, rows=20, cols=15)

    lines = [
        f"# Sheet: {sheet}",
        "## Plan summary:",
        str(plan.model_dump(exclude_none=True)),
        "",
        "## Tier 1/2 warnings:",
    ]
    for f in findings:
        lines.append(f"  - [{f.severity}] {f.check}: {f.message}")
    lines.append("")
    lines.append("## Sheet peek (rows 1..20, cols 1..15):")
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="plan_reviewer",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "plan_reviewer.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=PlanVerdict,
    build_user_input=_build_user_input,
)


@component
class PlanReviewer:
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(verdict=PlanVerdict)
    def run(self, workbook_ctx: Any, plan: SheetPlan,
            findings: list[ValidationFinding] | None = None) -> dict:
        result = self.runner.run(workbook_ctx,
                                 {"plan": plan, "findings": findings or []})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="plan_reviewer")
            return {"verdict": PlanVerdict(verdict="looks_correct", confidence=0.0)}
        return {"verdict": result}

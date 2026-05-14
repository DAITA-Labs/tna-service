"""PlanReviewer agent — LLM judge of SheetPlan correctness.

Fires only when Tier 1/2 validators warned, plan confidence is low, or mode
is one of the rarer modes (SECTION_PER_PLI / SHEET_IS_PLI).
"""
from __future__ import annotations

from pathlib import Path

from haystack import component

from app.core.logs import get_logger
from app.core.prompt_loader import load_prompt
from app.models.artifacts import PlanVerdict, SheetPlan, ValidationFinding
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.services.agents._base import AgentRunFailure, AgentRunner, AgentSpec
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from a SheetPlan, validator findings, and a cell peek.

    Serialises the plan summary and Tier 1/2 warning findings, then appends a
    20-row × 15-col sheet peek so the LLM can verify the plan against raw data.
    """
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
    """Haystack component that reviews a SheetPlan for correctness and returns a verdict.

    Accepts a SheetPlan and optional validator findings; produces a PlanVerdict
    indicating whether the plan looks correct and at what confidence level.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Wire up the underlying AgentRunner with the plan_reviewer spec."""
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(verdict=PlanVerdict)
    def run(self, workbook_ctx: object, plan: SheetPlan,
            findings: list[ValidationFinding] | None = None) -> dict:
        """Run the plan-reviewer agent and return a correctness verdict.

        Falls back to a low-confidence looks_correct verdict on agent failure
        so the pipeline can continue without blocking on LLM unavailability.
        """
        result = self.runner.run(workbook_ctx,
                                 {"plan": plan, "findings": findings or []})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="plan_reviewer")
            return {"verdict": PlanVerdict(verdict="looks_correct", confidence=0.0)}
        return {"verdict": result}

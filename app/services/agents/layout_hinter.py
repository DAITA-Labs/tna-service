"""LayoutHinter — LLM disambiguator for identity_column / pli_mode."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import LayoutHints, SheetSignals
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt
from app.core.logs import get_logger

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sig: SheetSignals = inputs["signals"]
    sheet = inputs["sheet"]
    peek = TOOL_REGISTRY.get("peek_sheet")
    grid = peek(ctx, sheet, rows=10, cols=15)

    lines = [
        f"# Sheet: {sheet}",
        "## Signals:",
        str(sig.model_dump()),
        "",
        "## Top-left peek (rows 1..10, cols 1..15):",
    ]
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="layout_hinter",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "layout_hinter.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=LayoutHints,
    build_user_input=_build_user_input,
)


@component
class LayoutHinter:
    """Haystack Component wrapper around the LayoutHinter agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(hints=LayoutHints)
    def run(self, workbook_ctx: Any, sheet: str, signals: SheetSignals) -> dict:
        result = self.runner.run(workbook_ctx, {"sheet": sheet, "signals": signals})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="layout_hinter")
            return {"hints": LayoutHints()}
        return {"hints": result}

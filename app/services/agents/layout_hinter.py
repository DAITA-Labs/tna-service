"""LayoutHinter agent — LLM disambiguator for identity_column and pli_mode layout signals."""
from __future__ import annotations

from pathlib import Path

from haystack import component

from app.core.logs import get_logger
from app.core.prompt_loader import load_prompt
from app.models.artifacts import LayoutHints, SheetSignals
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.services.agents._base import AgentRunFailure, AgentRunner, AgentSpec
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from sheet signals and a top-left cell peek.

    Fetches the top-left 10×15 grid via the peek_sheet tool and formats it
    together with the SheetSignals model-dump so the LLM can disambiguate
    identity_column and pli_mode from concrete evidence.
    """
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
    """Haystack component that resolves ambiguous layout signals into LayoutHints.

    Accepts sheet signals and a workbook context; produces LayoutHints used by
    downstream deterministic planners to select the correct parsing strategy.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Wire up the underlying AgentRunner with the layout_hinter spec."""
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(hints=LayoutHints)
    def run(self, workbook_ctx: object, sheet: str, signals: SheetSignals) -> dict:
        """Run the layout-hinter agent and return resolved layout hints.

        Falls back to an empty LayoutHints (all fields None) on agent failure
        so the pipeline can continue with deterministic defaults.
        """
        result = self.runner.run(workbook_ctx, {"sheet": sheet, "signals": signals})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="layout_hinter")
            return {"hints": LayoutHints()}
        return {"hints": result}

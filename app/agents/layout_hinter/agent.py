"""LayoutHinter Agent — disambiguates identity_column / pli_mode from sheet signals."""
from __future__ import annotations

from typing import Any

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.layout_hinter.schema import LayoutHinterInputs, LayoutHints
from app.agents.layout_hinter.tuning import LayoutHinterTuning
from app.agents.layout_hinter.validators import validate_layout_hints
from app.prompts import LAYOUT_HINTER
from app.tools._registry import TOOL_REGISTRY


class LayoutHinterAgent(Agent):
    """Single-call LLM agent: SheetSignals + cell peek → LayoutHints."""

    name = "layout_hinter"
    prompt = LAYOUT_HINTER
    output_schema = LayoutHints
    tuning = LayoutHinterTuning()

    def build_input(self, ctx: Any, inputs: LayoutHinterInputs) -> str:
        """Assemble the prompt body from sheet signals + top-left peek."""
        peek = TOOL_REGISTRY.get("peek_sheet")
        grid = peek(ctx, inputs.sheet, rows=10, cols=15)
        lines = [
            f"# Sheet: {inputs.sheet}",
            "## Signals:",
            str(inputs.signals.model_dump()),
            "",
            "## Top-left peek (rows 1..10, cols 1..15):",
        ]
        for c in grid.cells:
            lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        """No-op input validation — input shape is Pydantic-enforced."""
        return InputVerdict.ok()

    def validate_output(self, output: LayoutHints, ctx: Any) -> OutputVerdict:
        """Delegate to the module-level layout-hints validator."""
        return validate_layout_hints(output, ctx)

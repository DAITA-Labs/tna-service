"""LayoutFingerprinter — emits a StructuralFingerprint for one sheet."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import StructuralFingerprint
from app.enums.stage_layout_mode import StageLayoutMode
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sheet = inputs["sheet"]
    peek = TOOL_REGISTRY.get("peek_sheet")
    merges = TOOL_REGISTRY.get("get_merged_regions")
    grid = peek(ctx, sheet, rows=12, cols=15)
    merge_list = merges(ctx, sheet)[:15]
    lines = [f"# Sheet: {sheet}", "", "## Top-left peek (12x15):"]
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    lines.append("")
    lines.append(f"## Merged regions (first {len(merge_list)}):")
    for m in merge_list:
        lines.append(f"  {m.cell_range} anchor={m.anchor_value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="layout_fingerprinter",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "layout_fingerprinter.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=StructuralFingerprint,
    build_user_input=_build_user_input,
)


@component
class LayoutFingerprinter:
    """Haystack Component wrapper around the LayoutFingerprinter agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(fingerprint=StructuralFingerprint)
    def run(self, workbook_ctx: Any, sheet: str) -> dict:
        result = self.runner.run(workbook_ctx, {"sheet": sheet})
        if isinstance(result, AgentRunFailure):
            # Fallback: conservative defaults — narrow detection is better than false positives.
            return {
                "fingerprint": StructuralFingerprint(
                    sheets_appear_parallel=False,
                    has_scattered_metadata=False,
                    has_tabular_header_band=True,
                    multi_row_headers=False,
                    has_vertical_merges_in_data=False,
                    has_totals_rows=False,
                    has_noise_sheets=False,
                    multi_band_stages_per_pli=False,
                    stage_layout_mode=StageLayoutMode.UNKNOWN,
                    sample_evidence={},
                )
            }
        return {"fingerprint": result}

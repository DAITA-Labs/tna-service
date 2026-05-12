"""BoundaryFinder — emits PLIBoundaries for one sheet."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import PLIBoundaries, StructuralFingerprint
from app.enums.boundary_pattern import BoundaryPattern
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sheet = inputs["sheet"]
    fp: StructuralFingerprint = inputs["fingerprint"]
    list_sheets = TOOL_REGISTRY.get("list_sheets")
    peek = TOOL_REGISTRY.get("peek_sheet")
    sample = TOOL_REGISTRY.get("sample_rows")
    merges = TOOL_REGISTRY.get("get_merged_regions")

    all_sheets = [s.name for s in list_sheets(ctx)]
    sheet_meta = next(s for s in list_sheets(ctx) if s.name == sheet)
    max_row = sheet_meta.max_row

    lines: list[str] = [f"# Sheet: {sheet}", f"workbook_sheets: {all_sheets}",
                        "", "## Inspector fingerprint:"]
    for k, v in fp.model_dump().items():
        if k != "sample_evidence":
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("## Top-left peek (rows 1..10, cols 1..15):")
    grid = peek(ctx, sheet, rows=10, cols=15)
    for c in grid.cells:
        lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    lines.append("")

    merge_list = merges(ctx, sheet)
    cap = 50
    lines.append(f"## Merged regions (first {min(cap, len(merge_list))} of {len(merge_list)}):")
    for m in merge_list[:cap]:
        lines.append(f"  {m.cell_range} anchor={m.anchor_value!r}")
    lines.append("")

    if max_row > 10:
        mid = max_row // 2
        for row_cells in sample(ctx, sheet, sorted({mid, max_row})):
            if row_cells:
                rno = row_cells[0].row
                vals = ", ".join(f"{c.address}={c.value!r}" for c in row_cells)
                lines.append(f"  row {rno}: {vals}")

    return "\n".join(lines)


SPEC = AgentSpec(
    name="boundary_finder",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "boundary_finder.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=PLIBoundaries,
    build_user_input=_build_user_input,
)


@component
class BoundaryFinder:
    """Haystack Component wrapper around the BoundaryFinder agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(boundaries=PLIBoundaries)
    def run(self, workbook_ctx: Any, sheet: str,
            fingerprint: StructuralFingerprint) -> dict:
        result = self.runner.run(workbook_ctx,
                                 {"sheet": sheet, "fingerprint": fingerprint})
        if isinstance(result, AgentRunFailure):
            # Fallback: conservative defaults — assume one row per PLI.
            return {"boundaries": PLIBoundaries(
                sheet=sheet, pattern=BoundaryPattern.ONE_ROW_PER_PLI,
                data_start_row=2, data_end_row=2, confidence=0.0,
            )}
        return {"boundaries": result}

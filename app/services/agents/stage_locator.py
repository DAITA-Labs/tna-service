"""StageLocator — identifies stage bands + canonicalizes variant columns."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import StageBandSet, PLIBoundaries, StructuralFingerprint
from app.enums.stage_layout_mode import StageLayoutMode
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sheet = inputs["sheet"]
    fp: StructuralFingerprint = inputs["fingerprint"]
    boundaries: PLIBoundaries = inputs["boundaries"]
    list_sheets = TOOL_REGISTRY.get("list_sheets")
    read_row = TOOL_REGISTRY.get("read_row")
    peek = TOOL_REGISTRY.get("peek_sheet")
    merges = TOOL_REGISTRY.get("get_merged_regions")

    sheet_meta = next(s for s in list_sheets(ctx) if s.name == sheet)
    max_col = sheet_meta.max_col or 40
    max_row = sheet_meta.max_row or 0

    full_sheet = (fp.multi_band_stages_per_pli
                  or fp.stage_layout_mode == StageLayoutMode.TALL_SUB_ROWS)

    lines = [f"# Sheet: {sheet}", "", "## Inspector fingerprint:"]
    for k, v in fp.model_dump().items():
        if k != "sample_evidence":
            lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("## PLI Boundaries:")
    for k, v in boundaries.model_dump().items():
        if v not in (None, [], ""):
            lines.append(f"  {k}: {v}")
    lines.append("")

    if full_sheet and max_row:
        lines.append(f"## Full sheet (rows 1..{max_row}, cols 1..{max_col}):")
        for r in range(1, max_row + 1):
            for c in read_row(ctx, sheet, r, col_range=(1, max_col)):
                lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    else:
        header_rows = [2, 3] if fp.multi_row_headers else [1]
        lines.append(f"## Header rows {header_rows} (cols 1..{max_col}):")
        for hr in header_rows:
            for c in read_row(ctx, sheet, hr, col_range=(1, max_col)):
                lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
        if boundaries.data_start_row:
            lines.append("")
            lines.append(f"## Sample data row {boundaries.data_start_row}:")
            for c in read_row(ctx, sheet, boundaries.data_start_row,
                              col_range=(1, max_col)):
                lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
        lines.append("")
        lines.append("## Top-left peek (rows 1..10, cols 1..15):")
        for c in peek(ctx, sheet, rows=10, cols=15).cells:
            lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")

    lines.append("")
    lines.append("## Merged regions (first 15):")
    for m in merges(ctx, sheet)[:15]:
        lines.append(f"  {m.cell_range} anchor={m.anchor_value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="stage_locator",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "stage_locator.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=StageBandSet,
    build_user_input=_build_user_input,
)


@component
class StageLocator:
    """Haystack Component wrapper around the StageLocator agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(stage_band_set=StageBandSet)
    def run(self, workbook_ctx: Any, sheet: str,
            fingerprint: StructuralFingerprint,
            boundaries: PLIBoundaries) -> dict:
        result = self.runner.run(
            workbook_ctx,
            {"sheet": sheet, "fingerprint": fingerprint, "boundaries": boundaries},
        )
        if isinstance(result, AgentRunFailure):
            return {"stage_band_set": StageBandSet(sheet=sheet, confidence=0.0)}
        return {"stage_band_set": result}

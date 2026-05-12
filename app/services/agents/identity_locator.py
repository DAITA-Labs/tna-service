"""IdentityLocator — locates io/style/color/fabric columns + PLI metadata."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from openpyxl.utils import column_index_from_string
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.models.artifacts import FieldMap, PLIBoundaries
from app.enums.boundary_pattern import BoundaryPattern
from app.services.llm_provider import LLMProvider
from app.repositories.workbook_tools._registry import TOOL_REGISTRY
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
_SAMPLE_DATA_ROWS = 2


def _vertical_merge_witness_rows(ctx: Any, sheet: str, boundaries: PLIBoundaries) -> list[int]:
    """Anchor + sub-rows of merge groups inside the data range — where per-PLI
    columns diverge from aggregate columns."""
    if boundaries.pattern != BoundaryPattern.VERTICAL_MERGE or not boundaries.grouping_columns:
        return []
    ws = ctx.wb[sheet]
    grouping_cols = {column_index_from_string(c) for c in boundaries.grouping_columns}
    start = boundaries.data_start_row or 1
    end = boundaries.data_end_row or start
    witness: set[int] = set()
    for mr in ws.merged_cells.ranges:
        if mr.max_row < start or mr.min_row > end:
            continue
        if not any(mr.min_col <= c <= mr.max_col for c in grouping_cols):
            continue
        for r in range(mr.min_row, mr.max_row + 1):
            if start <= r <= end:
                witness.add(r)
    return sorted(witness)


def _build_user_input(ctx: Any, inputs: dict) -> str:
    sheet = inputs["sheet"]
    boundaries: PLIBoundaries = inputs["boundaries"]
    list_sheets = TOOL_REGISTRY.get("list_sheets")
    read_row = TOOL_REGISTRY.get("read_row")
    merges = TOOL_REGISTRY.get("get_merged_regions")

    sheet_meta = next(s for s in list_sheets(ctx) if s.name == sheet)
    max_col = sheet_meta.max_col or 40

    lines = [f"# Sheet: {sheet}", "", "## Boundaries:"]
    for k, v in boundaries.model_dump().items():
        if v not in (None, [], ""):
            lines.append(f"  {k}: {v}")
    lines.append("")

    header_rows = [2, 3] if boundaries.data_start_row and boundaries.data_start_row > 3 else [1]
    lines.append(f"## Header rows (cols 1..{max_col}):")
    for hr in header_rows:
        for c in read_row(ctx, sheet, hr, col_range=(1, max_col)):
            lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    lines.append("")

    if boundaries.data_start_row:
        start = boundaries.data_start_row
        sample = list(range(start, min(start + _SAMPLE_DATA_ROWS,
                                       (boundaries.data_end_row or start) + 1)))
        witness = [r for r in _vertical_merge_witness_rows(ctx, sheet, boundaries)
                   if r not in sample]
        lines.append(f"## Sample data rows {sample}:")
        for r in sample:
            for c in read_row(ctx, sheet, r, col_range=(1, max_col)):
                lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
        if witness:
            lines.append("")
            lines.append(f"## Vertical-merge witness rows {witness}:")
            for r in witness:
                for c in read_row(ctx, sheet, r, col_range=(1, max_col)):
                    lines.append(f"  {c.address} [{c.dtype}]: {c.value!r}")
    lines.append("")
    lines.append("## Merged regions (first 15):")
    for m in merges(ctx, sheet)[:15]:
        lines.append(f"  {m.cell_range} anchor={m.anchor_value!r}")
    return "\n".join(lines)


SPEC = AgentSpec(
    name="identity_locator",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "identity_locator.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=FieldMap,
    build_user_input=_build_user_input,
)


@component
class IdentityLocator:
    """Haystack Component wrapper around the IdentityLocator agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(field_map=FieldMap)
    def run(self, workbook_ctx: Any, sheet: str, boundaries: PLIBoundaries) -> dict:
        result = self.runner.run(workbook_ctx, {"sheet": sheet, "boundaries": boundaries})
        if isinstance(result, AgentRunFailure):
            return {"field_map": FieldMap(sheet=sheet)}
        return {"field_map": result}

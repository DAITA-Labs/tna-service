"""QuantityDateLocator — finds quantity + delivery_date columns.

Reuses _build_user_input from IdentityLocator: both agents need the same
view of the sheet (headers + sample + vertical-merge witness rows + merges).
"""
from __future__ import annotations
from pathlib import Path
from haystack import component
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.services.agents.identity_locator import _build_user_input as _shared_input
from app.models.artifacts import FieldMap, PLIBoundaries
from app.services.llm_provider import LLMProvider
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Same input as IdentityLocator — exposed as module-level for clarity.
_build_user_input = _shared_input


SPEC = AgentSpec(
    name="quantity_date_locator",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "quantity_date_locator.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=FieldMap,
    build_user_input=_build_user_input,
)


@component
class QuantityDateLocator:
    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(field_map=FieldMap)
    def run(self, workbook_ctx, sheet: str, boundaries: PLIBoundaries) -> dict:
        result = self.runner.run(workbook_ctx, {"sheet": sheet, "boundaries": boundaries})
        if isinstance(result, AgentRunFailure):
            return {"field_map": FieldMap(sheet=sheet)}
        return {"field_map": result}

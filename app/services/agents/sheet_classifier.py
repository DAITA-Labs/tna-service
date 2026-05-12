"""SheetClassifier — decides which sheets are TNA-relevant."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from haystack import component
from pydantic import BaseModel, ConfigDict, Field
from app.services.agents._base import AgentSpec, AgentRunner, AgentRunFailure
from app.services.llm_provider import LLMProvider
from app.core.prompt_loader import load_prompt

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


class SheetClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    relevant_sheets: list[str] = Field(default_factory=list)
    notes: str | None = None


def _build_user_input(ctx: Any, inputs: dict) -> str:
    summary = inputs["workbook_summary"]
    lines = [
        f"# Workbook: {summary.sheet_count} sheets, {summary.file_size_kb} KB",
        f"sheet_names: {summary.sheet_names}",
        "",
        "Classify each sheet as TNA-relevant or noise.",
    ]
    return "\n".join(lines)


SPEC = AgentSpec(
    name="sheet_classifier",
    system_prompt=load_prompt(
        _PROMPT_DIR / "workflow" / "sheet_classifier.md",
        shared_fragment=_PROMPT_DIR / "_shared.md",
    ),
    output_schema=SheetClassifierOutput,
    build_user_input=_build_user_input,
)


@component
class SheetClassifier:
    """Haystack Component wrapper around the SheetClassifier agent."""

    def __init__(self, llm: LLMProvider):
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(relevant_sheets=list)
    def run(self, workbook_ctx, workbook_summary) -> dict:
        result = self.runner.run(workbook_ctx, {"workbook_summary": workbook_summary})
        if isinstance(result, AgentRunFailure):
            # Fallback: include all sheets — false positives are cheap.
            return {"relevant_sheets": list(workbook_summary.sheet_names)}
        return {"relevant_sheets": result.relevant_sheets}

"""SheetClassifier agent — decides which sheets in a workbook are TNA-relevant."""
from __future__ import annotations

from pathlib import Path

from haystack import component
from pydantic import BaseModel, ConfigDict, Field

from app.core.logs import get_logger
from app.core.prompt_loader import load_prompt
from app.services.agents._base import AgentRunFailure, AgentRunner, AgentSpec
from app.services.llm_provider import LLMProvider

log = get_logger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


class SheetClassifierOutput(BaseModel):
    """Structured output produced by the SheetClassifier agent."""

    model_config = ConfigDict(extra="ignore")
    relevant_sheets: list[str] = Field(default_factory=list)
    notes: str | None = None


def _build_user_input(ctx: object, inputs: dict) -> str:
    """Assemble the LLM prompt body from a WorkbookSummary."""
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
    """Haystack component that filters a workbook down to TNA-relevant sheet names.

    Accepts a WorkbookSummary and produces the list of sheet names that contain
    TNA data; fires once per workbook at the start of the extraction pipeline.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Wire up the underlying AgentRunner with the sheet_classifier spec."""
        self.runner = AgentRunner(SPEC, llm)

    @component.output_types(relevant_sheets=list)
    def run(self, workbook_ctx: object, workbook_summary: object) -> dict:
        """Run the sheet-classifier agent and return the relevant sheet names.

        Falls back to all sheet names on agent failure — false positives are
        cheap and downstream agents can discard irrelevant sheets.
        """
        result = self.runner.run(workbook_ctx, {"workbook_summary": workbook_summary})
        if isinstance(result, AgentRunFailure):
            log.warning("agent_fallback_used", agent="sheet_classifier")
            # Fallback: include all sheets — false positives are cheap.
            return {"relevant_sheets": list(workbook_summary.sheet_names)}
        return {"relevant_sheets": result.relevant_sheets}

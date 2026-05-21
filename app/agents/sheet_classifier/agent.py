"""SheetClassifierAgent — decides which sheets in a workbook are TNA-relevant."""
from __future__ import annotations

from app.agents._base import Agent, InputVerdict, OutputVerdict
from app.agents.sheet_classifier.schema import SheetClassifierInputs, SheetClassifierOutput
from app.agents.sheet_classifier.tuning import SheetClassifierTuning
from app.agents.sheet_classifier.validators import validate_input, validate_output
from app.prompts.sheet_classifier import SHEET_CLASSIFIER


class SheetClassifierAgent(Agent):
    """Classifies workbook sheets as TNA-relevant or noise.

    Accepts a WorkbookSummary and produces the list of sheet names that contain
    TNA data; fires once per workbook at the start of the extraction pipeline.
    """

    name = "sheet_classifier"
    prompt = SHEET_CLASSIFIER
    output_schema = SheetClassifierOutput
    tuning = SheetClassifierTuning()

    def build_input(self, ctx: object, inputs: SheetClassifierInputs) -> str:
        """Assemble the LLM prompt body from a WorkbookSummary."""
        summary = inputs.workbook_summary
        lines = [
            f"# Workbook: {summary.sheet_count} sheets, {summary.file_size_kb} KB",
            f"sheet_names: {summary.sheet_names}",
            "",
            "Classify each sheet as TNA-relevant or noise.",
        ]
        return "\n".join(lines)

    def validate_input(self, user_text: str) -> InputVerdict:
        return validate_input(user_text)

    def validate_output(self, output: SheetClassifierOutput, ctx: object) -> OutputVerdict:
        return validate_output(output, ctx)

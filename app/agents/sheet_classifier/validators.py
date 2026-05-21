"""SheetClassifier lifecycle validators."""
from __future__ import annotations

from app.agents._base import InputVerdict, OutputVerdict
from app.agents.sheet_classifier.schema import SheetClassifierOutput


def validate_input(user_text: str) -> InputVerdict:
    """Input is structurally enforced by Pydantic; no semantic check needed."""
    return InputVerdict.ok()


def validate_output(output: SheetClassifierOutput, ctx: object) -> OutputVerdict:
    """Reject entries that are not strings or not known workbook sheet names."""
    known = set(getattr(ctx, "sheet_names", []) or [])
    for entry in output.relevant_sheets:
        if not isinstance(entry, str):
            return OutputVerdict.retry(
                reason=f"relevant_sheets entry {entry!r} is not a string"
            )
        if known and entry not in known:
            return OutputVerdict.retry(
                reason=f"relevant_sheets entry {entry!r} is not a workbook sheet name"
            )
    return OutputVerdict.ok()

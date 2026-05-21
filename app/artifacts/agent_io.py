"""Base output model carrying the optional decision_notes field."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


DECISION_NOTES_DIRECTIVE = (
    "\n\n# Decision notes\n"
    "Include a `decision_notes` field with a one-paragraph explanation of "
    "the mappings you produced and why. Mention any ambiguous cases."
)


class AgentOutput(BaseModel):
    """Common base for agent output schemas; carries optional decision_notes."""

    model_config = ConfigDict(extra="ignore")
    decision_notes: str | None = Field(default=None)

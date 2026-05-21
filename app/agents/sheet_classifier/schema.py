"""SheetClassifier input/output schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.artifacts.agent_io import AgentOutput


class SheetClassifierInputs(BaseModel):
    """Inputs consumed by SheetClassifierAgent.build_input."""

    workbook_summary: object


class SheetClassifierOutput(AgentOutput):
    """Structured output produced by the SheetClassifier agent."""

    relevant_sheets: list[str] = Field(default_factory=list)
    notes: str | None = None

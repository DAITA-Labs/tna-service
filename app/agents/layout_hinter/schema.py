"""LayoutHinter I/O schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.models.artifacts import SheetSignals


class LayoutHinterInputs(BaseModel):
    """Inputs to the LayoutHinter agent — sheet name + signals."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
    sheet: str
    signals: SheetSignals


class LayoutHints(AgentOutput):
    """LayoutHinter's output — disambiguation hints for the planner."""

    identity_column_suggestion: str | None = None
    mode_suggestion: str | None = None
    notes: list[str] = Field(default_factory=list)

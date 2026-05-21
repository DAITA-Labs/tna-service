"""FieldNamer I/O schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.models.artifacts import SheetPlan


class FieldNamerInputs(BaseModel):
    """Inputs to the FieldNamer agent — wraps the SheetPlan being named."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
    plan: SheetPlan


class CanonicalNameMap(AgentOutput):
    """FieldNamer's output — maps raw labels/headers to canonical names.

    Adds optional stage_subfield_labels for wide_sub_columns sub-columns,
    plus field_confidence / stage_confidence so the LLM can self-report
    per-mapping uncertainty (used by the apply step's confidence calibration).
    """

    field_labels: dict[str, str] = Field(default_factory=dict)
    stage_names: dict[str, str] = Field(default_factory=dict)
    stage_subfield_labels: dict[str, str] = Field(default_factory=dict)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    stage_confidence: dict[str, float] = Field(default_factory=dict)

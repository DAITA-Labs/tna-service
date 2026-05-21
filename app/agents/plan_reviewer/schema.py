"""PlanReviewer I/O schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.artifacts.agent_io import AgentOutput
from app.models.artifacts import SheetPlan, ValidationFinding


class PlanReviewerInputs(BaseModel):
    """Inputs to the PlanReviewer agent — plan + optional findings."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)
    plan: SheetPlan
    findings: list[ValidationFinding] = Field(default_factory=list)


class PlanVerdict(AgentOutput):
    """PlanReviewer's output — verdict on a draft SheetPlan with optional corrections."""

    verdict: str = "looks_correct"
    row_corrections: list[dict[str, Any]] = Field(default_factory=list)
    identity_column_suggestion: str | None = None
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 1.0

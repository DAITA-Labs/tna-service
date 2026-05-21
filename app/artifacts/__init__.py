"""Artifact primitives — re-exports of pipeline-shared Pydantic models.

This package is a bridge during the architecture redesign: imports
from `app.artifacts` keep working as the underlying types are
eventually split out of `app.models.artifacts` in sub-plan 5.
"""
from __future__ import annotations

from app.models.artifacts import (
    CanonicalNameMap,
    HeaderLabel,
    KVAnchor,
    LayoutHints,
    PlanVerdict,
    PliBlock,
    RowSpec,
    SheetPlan,
    SheetSignals,
    StageBandSpec,
    StageColumn,
    ValidationFinding,
    ValidationFindings,
)


__all__ = [
    "CanonicalNameMap",
    "HeaderLabel",
    "KVAnchor",
    "LayoutHints",
    "PlanVerdict",
    "PliBlock",
    "RowSpec",
    "SheetPlan",
    "SheetSignals",
    "StageBandSpec",
    "StageColumn",
    "ValidationFinding",
    "ValidationFindings",
]

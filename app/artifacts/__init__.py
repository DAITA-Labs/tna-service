"""Artifact primitives — typed records shared across the pipeline.

Two families of artifacts live here:

  CANVAS ARCHITECTURE (direct imports)
    Canvas / structure / layout / finding records used by the new canvas
    extraction path. Imported eagerly because they have no dependency on
    `app.models.artifacts`.

  LEGACY (lazy via __getattr__)
    Pre-redesign Pydantic models re-exported from `app.models.artifacts`.
    Loaded on attribute access to avoid a circular-import cycle:
    `app.models.artifacts` imports `app.artifacts.agent_io`, so importing
    `app.models.artifacts` here at module load time would close the cycle.
"""
from __future__ import annotations

from typing import Any

# ─── Canvas-architecture artifacts (direct re-exports) ──────────────────────

from app.artifacts.canvas import GridCanvas
from app.artifacts.finding import Confidence, Coord, Finding, ValidationWarning, Verdict
from app.artifacts.layout import Direction, LayoutAxes, LayoutHint
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    LocationCandidate,
    MetadataPlan,
    PliKey,
    StageBandPlan,
)
from app.artifacts.structure import (
    BoldStrip,
    BorderedBox,
    ColDtypeProfile,
    ColorStrip,
    DataRowRange,
    DateStrip,
    FloatStrip,
    HeaderBand,
    IntStrip,
    KvBlock,
    LongTextStrip,
    MergeSpan,
    MergedColumnStrip,
    NonMergedStrip,
    PlanMarkerCluster,
    Rect,
    RepeatingRowGroup,
    RowDtypeProfile,
    SameLengthStrip,
    SectionBoundary,
    StageArena,
    StageBand,
    StructureBag,
    SubfieldCluster,
)


# ─── Legacy artifacts (lazy via __getattr__) ────────────────────────────────

_LEGACY_NAMES = (
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
)


def __getattr__(name: str) -> Any:
    """Lazy-load legacy Pydantic re-exports to break a circular-import cycle."""
    if name in _LEGACY_NAMES:
        import app.models.artifacts as _mod  # noqa: PLC0415
        return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # ─ Canvas: substrate ───────────────────────────────────────────────
    "GridCanvas",
    # ─ Canvas: structure records ───────────────────────────────────────
    "Rect", "Direction",
    "DateStrip", "IntStrip", "FloatStrip",
    "SameLengthStrip", "LongTextStrip",
    "ColorStrip", "BoldStrip", "BorderedBox",
    "MergeSpan", "NonMergedStrip", "MergedColumnStrip",
    "KvBlock", "RepeatingRowGroup", "PlanMarkerCluster",
    "HeaderBand", "DataRowRange", "SectionBoundary",
    "StageArena", "StageBand", "SubfieldCluster",
    "RowDtypeProfile", "ColDtypeProfile",
    "StructureBag",
    # ─ Canvas: layout ──────────────────────────────────────────────────
    "LayoutAxes", "LayoutHint",
    # ─ Canvas: findings ────────────────────────────────────────────────
    "Confidence", "Coord", "Finding", "Verdict", "ValidationWarning",
    # ─ Canvas: plan ─────────────────────────────────────────────────────
    "CanvasPlan", "FieldLocation", "LocationCandidate",
    "MetadataPlan", "PliKey", "StageBandPlan",
    # ─ Legacy ──────────────────────────────────────────────────────────
    *_LEGACY_NAMES,
]

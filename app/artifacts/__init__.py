"""Artifact primitives — re-exports of pipeline-shared Pydantic models.

This package is a bridge during the architecture redesign: imports
from `app.artifacts` keep working as the underlying types are
eventually split out of `app.models.artifacts` in sub-plan 5.

Imports are deferred via __getattr__ to avoid a circular-import cycle:
app.models.artifacts imports app.artifacts.agent_io (a submodule of this
package), and app/artifacts/__init__.py importing app.models.artifacts at
module load time would close the cycle.
"""
from __future__ import annotations

from typing import Any

_NAMES = [
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


__all__ = _NAMES


def __getattr__(name: str) -> Any:
    if name in _NAMES:
        import app.models.artifacts as _mod  # noqa: PLC0415
        return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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

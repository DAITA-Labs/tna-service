"""Smoke test for app.artifacts package-level re-exports.

Asserts both canvas-architecture artifacts and the legacy lazy-loaded
Pydantic models are importable from the package root.
"""
from __future__ import annotations


def test_canvas_artifacts_direct_reexport() -> None:
    """Canvas-architecture types are importable directly from app.artifacts."""
    from app.artifacts import (
        Confidence,
        DataRowRange,
        DateStrip,
        Finding,
        GridCanvas,
        HeaderBand,
        IntStrip,
        KvBlock,
        LayoutAxes,
        LayoutHint,
        Rect,
        StageArena,
        StructureBag,
        ValidationWarning,
        Verdict,
    )

    # Construct one of each to prove they're real types not strings
    assert GridCanvas(n_rows=1, n_cols=1, cell_values=[[None]]).n_rows == 1
    assert StructureBag().date_strips == []
    assert LayoutAxes(
        pli_axis="vertical", stage_axis="horizontal", subfield_axis="horizontal"
    ).pli_axis == "vertical"


def test_legacy_artifacts_lazy_reexport() -> None:
    """Legacy Pydantic models still resolve via __getattr__ lazy-loader."""
    from app.artifacts import SheetPlan

    assert SheetPlan is not None


def test_dir_includes_both_families() -> None:
    """__all__ exposes both canvas and legacy names."""
    import app.artifacts as artifacts

    exported = set(artifacts.__all__)
    # canvas
    assert "GridCanvas" in exported
    assert "Finding" in exported
    assert "LayoutHint" in exported
    # legacy
    assert "SheetPlan" in exported
    assert "ValidationFinding" in exported


def test_attribute_error_on_unknown() -> None:
    """Unknown attributes raise AttributeError (not silently None)."""
    import app.artifacts as artifacts

    try:
        _ = artifacts.NotAThing
    except AttributeError:
        return
    raise AssertionError("expected AttributeError")

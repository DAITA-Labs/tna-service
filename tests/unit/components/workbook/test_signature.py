"""Signature similarity — score_signatures returns a [0, 1] blend."""
from __future__ import annotations

import openpyxl

from app.components.workbook.profiler import compute_sheet_signature
from app.components.workbook.signature import score_signatures


def _ws(title: str, cells):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    for r, c, v in cells:
        ws.cell(row=r, column=c, value=v)
    return ws


def test_identical_sheets_score_one() -> None:
    cells = [(1, 1, "IO"), (1, 2, "Qty"), (2, 1, "X"), (2, 2, 10)]
    a = compute_sheet_signature(_ws("A", cells))
    b = compute_sheet_signature(_ws("B", cells))
    assert abs(score_signatures(a, b) - 1.0) < 1e-9


def test_completely_different_sheets_score_near_zero() -> None:
    """Disjoint masks / dtypes / labels → score collapses toward 0."""
    a = compute_sheet_signature(_ws("A", [(1, 1, "Header1")]))
    b = compute_sheet_signature(_ws("B", [(5, 9, 42.5)]))
    score = score_signatures(a, b)
    assert score < 0.2


def test_score_in_unit_interval() -> None:
    a = compute_sheet_signature(_ws("A", [(1, 1, "x"), (1, 2, "y"), (2, 1, 1)]))
    b = compute_sheet_signature(_ws("B", [(1, 1, "x"), (1, 2, "z"), (2, 1, 2)]))
    score = score_signatures(a, b)
    assert 0.0 <= score <= 1.0


def test_same_template_clears_cluster_threshold() -> None:
    """Same headers + same dtype shape + minor content differences → score ≥ 0.8."""
    template = [
        (1, 1, "IO No"), (1, 2, "Style"), (1, 3, "Qty"), (1, 4, "Delivery"),
        (2, 1, "IO-1"), (2, 2, "S001"), (2, 3, 100), (2, 4, "2026-05-01"),
        (3, 1, "IO-2"), (3, 2, "S002"), (3, 3, 200), (3, 4, "2026-05-15"),
    ]
    variant = [
        (1, 1, "IO No"), (1, 2, "Style"), (1, 3, "Qty"), (1, 4, "Delivery"),
        (2, 1, "IO-9"), (2, 2, "S009"), (2, 3, 500), (2, 4, "2026-06-01"),
        (3, 1, "IO-10"), (3, 2, "S010"), (3, 3, 600), (3, 4, "2026-06-15"),
    ]
    a = compute_sheet_signature(_ws("A", template))
    b = compute_sheet_signature(_ws("B", variant))
    assert score_signatures(a, b) >= 0.8


def test_different_templates_fall_below_threshold() -> None:
    """Different header columns + different dtype shape → score < 0.8."""
    template_a = [
        (1, 1, "IO No"), (1, 2, "Qty"),
        (2, 1, "IO-1"), (2, 2, 100),
    ]
    template_b = [
        (1, 1, "Buyer"), (1, 2, "Season"), (1, 3, "Style"),
        (2, 1, "Acme"), (2, 2, "FW26"), (2, 3, "S001"),
    ]
    a = compute_sheet_signature(_ws("A", template_a))
    b = compute_sheet_signature(_ws("B", template_b))
    assert score_signatures(a, b) < 0.8


def test_empty_signatures_score_zero() -> None:
    """Two empty signatures score 0 by convention (vacuous overlap)."""
    a = compute_sheet_signature(_ws("A", []))
    b = compute_sheet_signature(_ws("B", []))
    assert score_signatures(a, b) == 0.0

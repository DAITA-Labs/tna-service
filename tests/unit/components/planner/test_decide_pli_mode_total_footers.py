"""Unit tests for _decide_pli_mode with tabular-plus-TOTAL-footer layouts.

Guards the tightening of the SECTION_PER_PLI branch: a tabular sheet whose KV
label hits all land on the same header row must stay ROW_PER_PLI even when
blank_run_gaps and n_kv_hits would otherwise trigger the SECTION_PER_PLI path.
"""
from __future__ import annotations

import pytest

from app.enums.pli_mode import PliMode
from app.models.artifacts import SheetSignals
from app.components.planner.plan import _decide_pli_mode


def _tabular_signals_fa26_shape() -> SheetSignals:
    """Return SheetSignals mimicking FA26's tabular-with-TOTAL-footers layout.

    Row 1 holds all column headers; TOTAL footer rows (rows 3, 5, 7) create
    blank_run_gaps that previously pushed the mode into SECTION_PER_PLI.
    All kv_label_hits are on row 1 — the distinguishing structural feature.
    """
    return SheetSignals(
        sheet="T&A",
        max_row=8,
        max_col=10,
        identity_col_candidates=["C"],
        header_vocab_hits={"C": ["IO"]},
        kv_label_hits=[
            ("PO DATE", "A1"),
            ("SHIPMENT DATE", "B1"),
            ("IO", "C1"),
            ("STYLE", "E1"),
            ("COLOR", "F1"),
        ],
        blank_run_gaps=[(3, 3), (5, 5), (7, 7)],
    )


def _section_per_pli_signals() -> SheetSignals:
    """Return SheetSignals mimicking a genuine SECTION_PER_PLI layout.

    The identity column has a single KV hit on a header row (row 1), making it
    a real identity column (single-row concentration). Additional KV label hits
    appear on rows belonging to distinct PLI sections (rows 5 and 15), spanning
    multiple rows — the structural hallmark of a SECTION_PER_PLI sheet.
    Two blank-run gaps separate the sections.
    """
    return SheetSignals(
        sheet="Orders Plan",
        max_row=20,
        max_col=10,
        identity_col_candidates=["A"],
        header_vocab_hits={"A": ["IO"]},
        kv_label_hits=[
            ("IO", "A1"),     # identity col on header row (single-row concentration)
            ("STYLE", "B5"),  # section 1 KV label
            ("COLOR", "C5"),  # section 1 KV label
            ("STYLE", "B15"), # section 2 KV label (different row)
        ],
        blank_run_gaps=[(9, 10), (14, 14)],
    )


def test_tabular_with_total_footers_stays_row_per_pli():
    """FA26-shaped signals: all KV hits on one row must yield ROW_PER_PLI.

    Before the fix the SECTION_PER_PLI branch fired because has_identity_col,
    n_blank_gaps >= 2, and n_kv_hits >= 3 were all True. The fix adds the
    requirement that KV hits span >= 2 distinct rows.
    """
    signals = _tabular_signals_fa26_shape()
    assert _decide_pli_mode(signals) is PliMode.ROW_PER_PLI


def test_scattered_kv_still_returns_section_per_pli():
    """Genuine SECTION_PER_PLI signals must still yield SECTION_PER_PLI.

    Guards against the new kv_hit_rows guard accidentally suppressing the
    SECTION_PER_PLI path for layouts that legitimately have KV labels spread
    across many rows.
    """
    signals = _section_per_pli_signals()
    assert _decide_pli_mode(signals) is PliMode.SECTION_PER_PLI

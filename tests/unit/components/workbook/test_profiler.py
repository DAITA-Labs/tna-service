"""Profiler — compute_sheet_signature on openpyxl worksheets."""
from __future__ import annotations

import datetime as dt

import openpyxl

from app.artifacts.workbook import SIGNATURE_LABEL_ROWS, SIGNATURE_SAMPLE_ROWS
from app.components.workbook.profiler import compute_sheet_signature


def _sheet_with(title: str, cells):
    """Build a one-sheet workbook with the given title and (row, col, value) cells."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    for r, c, v in cells:
        ws.cell(row=r, column=c, value=v)
    return ws


def test_signature_records_sheet_title_and_dimensions() -> None:
    ws = _sheet_with("MainSheet", [(1, 1, "Header"), (2, 2, 5)])
    sig = compute_sheet_signature(ws)
    assert sig.sheet_name == "MainSheet"
    assert sig.n_rows == 2
    assert sig.n_cols == 2


def test_non_blank_mask_captures_populated_cells_only() -> None:
    ws = _sheet_with("S", [(1, 1, "Hello"), (1, 3, "World"), (2, 2, 42)])
    sig = compute_sheet_signature(ws)
    assert (1, 1) in sig.non_blank_mask
    assert (1, 3) in sig.non_blank_mask
    assert (2, 2) in sig.non_blank_mask
    # Blank cells absent
    assert (1, 2) not in sig.non_blank_mask
    assert (2, 1) not in sig.non_blank_mask


def test_dtype_per_row_counts_by_slot() -> None:
    """Row 1: 2 strings + 1 int + 1 blank. Slot order: (blank, str, int, float, date)."""
    ws = _sheet_with("S", [(1, 1, "A"), (1, 2, "B"), (1, 3, 10), (1, 5, None)])
    sig = compute_sheet_signature(ws)
    # max_column is 3 (None doesn't extend column count)
    blank, n_str, n_int, n_float, n_date = sig.dtype_per_row[0]
    assert n_str == 2
    assert n_int == 1
    assert n_float == 0
    assert n_date == 0


def test_date_cell_recognised_from_native_date() -> None:
    ws = _sheet_with("S", [(1, 1, dt.date(2026, 5, 27))])
    sig = compute_sheet_signature(ws)
    _, _, _, _, n_date = sig.dtype_per_row[0]
    assert n_date == 1


def test_date_string_recognised_via_regex() -> None:
    ws = _sheet_with("S", [(1, 1, "2026-05-27")])
    sig = compute_sheet_signature(ws)
    _, _, _, _, n_date = sig.dtype_per_row[0]
    assert n_date == 1


def test_label_positions_normalise_and_truncate() -> None:
    """Label scan stays in first SIGNATURE_LABEL_ROWS rows; text lowercased + whitespace collapsed."""
    label_row_inside = 1  # always inside
    row_outside = SIGNATURE_LABEL_ROWS + 1
    ws = _sheet_with("S", [
        (label_row_inside, 1, "  Job   No  "),
        (row_outside, 1, "ShouldNotAppear"),
    ])
    sig = compute_sheet_signature(ws)
    assert (label_row_inside, 1, "job no") in sig.label_positions
    assert all(text != "shouldnotappear" for (_, _, text) in sig.label_positions)


def test_signature_truncates_to_sample_rows() -> None:
    """Rows beyond SIGNATURE_SAMPLE_ROWS contribute neither mask nor dtype."""
    deep_row = SIGNATURE_SAMPLE_ROWS + 1
    ws = _sheet_with("S", [
        (1, 1, "Hdr"),
        (deep_row, 1, "DeepData"),
    ])
    sig = compute_sheet_signature(ws)
    assert (1, 1) in sig.non_blank_mask
    assert (deep_row, 1) not in sig.non_blank_mask
    assert len(sig.dtype_per_row) <= SIGNATURE_SAMPLE_ROWS


def test_two_clones_produce_identical_signatures() -> None:
    """Identical content + same title yields equal signatures (hashable, frozen)."""
    cells = [(1, 1, "IO"), (1, 2, "Qty"), (2, 1, "X"), (2, 2, 10)]
    sig_a = compute_sheet_signature(_sheet_with("A", cells))
    sig_b = compute_sheet_signature(_sheet_with("A", cells))
    assert sig_a == sig_b

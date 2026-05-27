"""Per-row + per-column dtype profile aggregators."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.artifacts.structure import ColDtypeProfile, RowDtypeProfile
from app.tools.canvas.build import build_canvas
from app.tools.canvas.dtype_profiles import (
    compute_col_dtype_profiles,
    compute_row_dtype_profiles,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """DKN baseline — has header + data rows + stage date columns."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_row_profiles_one_per_row(dkn_canvas) -> None:
    """compute_row_dtype_profiles emits exactly one profile per row."""
    profiles = compute_row_dtype_profiles(dkn_canvas)
    assert len(profiles) == dkn_canvas.n_rows
    assert all(isinstance(p, RowDtypeProfile) for p in profiles)


def test_col_profiles_one_per_col(dkn_canvas) -> None:
    """compute_col_dtype_profiles emits exactly one profile per column."""
    profiles = compute_col_dtype_profiles(dkn_canvas)
    assert len(profiles) == dkn_canvas.n_cols
    assert all(isinstance(p, ColDtypeProfile) for p in profiles)


def test_row_profile_counts_sum_to_n_cols(dkn_canvas) -> None:
    """Per-row counts (blank+date+int+float+str+formula) sum to n_cols."""
    for p in compute_row_dtype_profiles(dkn_canvas):
        total = p.n_blank + p.n_date + p.n_int + p.n_float + p.n_str + p.n_formula
        assert total == p.n_cols == dkn_canvas.n_cols


def test_col_profile_counts_sum_to_n_rows(dkn_canvas) -> None:
    """Per-col counts (blank+date+int+float+str+formula) sum to n_rows."""
    for p in compute_col_dtype_profiles(dkn_canvas):
        total = p.n_blank + p.n_date + p.n_int + p.n_float + p.n_str + p.n_formula
        assert total == p.n_rows == dkn_canvas.n_rows


def test_row_indices_are_1_indexed(dkn_canvas) -> None:
    """Row indices in profiles match 1-indexed sheet rows."""
    profiles = compute_row_dtype_profiles(dkn_canvas)
    indices = [p.row_idx for p in profiles]
    assert indices == list(range(1, dkn_canvas.n_rows + 1))


def test_col_indices_are_1_indexed(dkn_canvas) -> None:
    """Col indices in profiles match 1-indexed sheet columns."""
    profiles = compute_col_dtype_profiles(dkn_canvas)
    indices = [p.col_idx for p in profiles]
    assert indices == list(range(1, dkn_canvas.n_cols + 1))


def test_header_row_has_high_string_count(dkn_canvas) -> None:
    """The DKN header row (row 2) should be string-dominant."""
    profiles = compute_row_dtype_profiles(dkn_canvas)
    header = next(p for p in profiles if p.row_idx == 2)
    # Row 2 of DKN has the column labels — mostly strings, not blanks
    assert header.n_str >= header.n_int + header.n_float + header.n_date


def test_tools_registered() -> None:
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    assert "compute_row_dtype_profiles" in names
    assert "compute_col_dtype_profiles" in names

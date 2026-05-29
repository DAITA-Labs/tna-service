"""PliAxisPicker — drop-in coverage for the four legacy decision branches."""
from __future__ import annotations

from app.components.pickers.pli_axis import PliAxisPicker


def test_picks_sheet_for_kv_blocks_small_data_small_sheet() -> None:
    """kv≥3 + n_data_rows<5 + sheet_size<600 → 'sheet' (high confidence)."""
    out = PliAxisPicker().run(
        kv_count=4, repeating_count=0,
        n_data_rows=3, n_data_cols=15, sheet_size=300,
    )
    assert out["pli_axis"]   == "sheet"
    assert out["confidence"] == 0.9


def test_picks_sectional_for_repeating_groups() -> None:
    """repeating≥3 + n_data_rows≥10 → 'sectional'."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=5,
        n_data_rows=30, n_data_cols=10, sheet_size=1500,
    )
    assert out["pli_axis"]   == "sectional"
    assert out["confidence"] == 0.9


def test_picks_vertical_when_more_rows_than_cols() -> None:
    """n_data_rows > n_data_cols * 2 → 'vertical'."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=50, n_data_cols=10, sheet_size=2000,
    )
    assert out["pli_axis"]   == "vertical"
    assert out["confidence"] == 0.9


def test_picks_horizontal_when_more_cols_than_rows() -> None:
    """n_data_cols > n_data_rows * 2 → 'horizontal' (transposed table)."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=5, n_data_cols=20, sheet_size=400,
    )
    assert out["pli_axis"]   == "horizontal"
    assert out["confidence"] == 0.9


def test_falls_back_to_vertical_low_confidence_when_no_policy_fires() -> None:
    """No signal qualifies → 'vertical' with low confidence (matches legacy fallback)."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=5, n_data_cols=5, sheet_size=100,
    )
    assert out["pli_axis"]   == "vertical"
    assert out["confidence"] == 0.5


def test_verdict_trail_records_every_policy_per_candidate() -> None:
    """4 candidates × 4 policies = 16 verdicts."""
    out = PliAxisPicker().run(
        kv_count=4, repeating_count=0,
        n_data_rows=3, n_data_cols=15, sheet_size=300,
    )
    assert len(out["verdicts"]) == 16
    names = {v.name for v in out["verdicts"]}
    assert names == {
        "prefer_sheet_for_kv_blocks",
        "prefer_sectional_for_repeating_groups",
        "prefer_vertical_when_more_rows_than_cols",
        "prefer_horizontal_when_more_cols_than_rows",
    }

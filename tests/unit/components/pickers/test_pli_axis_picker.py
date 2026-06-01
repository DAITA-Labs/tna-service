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


def test_horizontal_header_band_pulls_decision_back_to_vertical() -> None:
    """A wide-short header band beats the col/row ratio rule.

    Scenario: 5 PLI rows × 30 stage columns. Without the header policy
    this scores 'horizontal' (transposed). With a horizontal header
    band (height 2, width 30) it scores 'vertical' — the right answer
    for a real TNA with PLI rows under a stage-column header.
    """
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=5, n_data_cols=30, sheet_size=200,
        header_band_height=2, header_band_width=30,
    )
    assert out["pli_axis"] == "vertical"


def test_horizontal_header_below_threshold_does_not_fire() -> None:
    """A 1-cell-wide header band doesn't qualify as 'horizontal' enough."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=5, n_data_cols=30, sheet_size=200,
        header_band_height=2, header_band_width=4,  # below MIN_WIDTH
    )
    # Without the header policy firing, the col/row ratio wins → horizontal.
    assert out["pli_axis"] == "horizontal"


def test_default_header_band_zero_means_policy_skips() -> None:
    """Header-band kwargs default to 0; the policy must not fire on zeros."""
    out = PliAxisPicker().run(
        kv_count=0, repeating_count=0,
        n_data_rows=5, n_data_cols=30, sheet_size=200,
    )
    assert out["pli_axis"] == "horizontal"  # the col/row rule wins


def test_verdict_trail_records_every_policy_per_candidate() -> None:
    """4 candidates × 5 policies = 20 verdicts."""
    out = PliAxisPicker().run(
        kv_count=4, repeating_count=0,
        n_data_rows=3, n_data_cols=15, sheet_size=300,
    )
    assert len(out["verdicts"]) == 20
    names = {v.name for v in out["verdicts"]}
    assert names == {
        "prefer_sheet_for_kv_blocks",
        "prefer_sectional_for_repeating_groups",
        "prefer_vertical_when_more_rows_than_cols",
        "prefer_horizontal_when_more_cols_than_rows",
        "prefer_vertical_when_header_band_is_horizontal",
    }

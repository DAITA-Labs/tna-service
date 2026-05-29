"""HeaderBandPicker — composition tests with mocked policies."""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.artifacts.structure import HeaderBand
from app.components.pickers.header_band import HeaderBandPicker
from app.policies._base import PolicyVerdict


# ── Helpers ────────────────────────────────────────────────────────────────


def _minimal_canvas(n_rows: int = 6, n_cols: int = 4) -> GridCanvas:
    """Build a tiny canvas with `empty_row` channel all-zero (rows non-empty)."""
    return GridCanvas(
        n_rows=n_rows,
        n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
        channels={
            "empty_row": [[0] * n_cols for _ in range(n_rows)],
        },
    )


def _verdict_for(row: int, score: float, eliminated: bool = False) -> PolicyVerdict:
    return PolicyVerdict(
        name="stub_policy", candidate=row,
        score_delta=score, eliminate=eliminated,
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_run_returns_none_band_when_no_candidates(monkeypatch) -> None:
    """Empty candidate list → None header_band + empty verdicts."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: set()
    )
    picker = HeaderBandPicker()
    result = picker.run(canvas=canvas)
    assert result["header_band"] is None
    assert result["verdicts"] == []


def test_run_picks_highest_scoring_row_as_anchor(monkeypatch) -> None:
    """Three candidates with different scores — top one anchors the band."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {1, 2, 3}
    )
    # Replace the picker's policies with deterministic stubs.
    picker = HeaderBandPicker(score_floor=1.0, adjacency_window=0)
    picker.policies = [
        lambda row, **kw: _verdict_for(row, {1: 1.0, 2: 3.0, 3: 2.0}[row]),
    ]
    result = picker.run(canvas=canvas)
    assert result["header_band"] is not None
    assert result["header_band"].rect.r0 == 2
    assert result["header_band"].rect.r1 == 2
    assert result["header_band"].score == 3.0


def test_run_absorbs_adjacent_qualifying_rows(monkeypatch) -> None:
    """Rows 2, 3, 4 all score above the floor → band spans 2-4."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {2, 3, 4, 5}
    )
    picker = HeaderBandPicker(score_floor=1.0, adjacency_window=2)
    picker.policies = [
        lambda row, **kw: _verdict_for(row, {2: 2.0, 3: 4.0, 4: 1.5, 5: 0.5}[row]),
    ]
    result = picker.run(canvas=canvas)
    band = result["header_band"]
    assert band is not None
    # Anchor is row 3 (highest score). Rows 2 and 4 qualify (above floor).
    # Row 5 scores 0.5, below floor → stops absorption downward.
    assert band.rect.r0 == 2
    assert band.rect.r1 == 4


def test_run_stops_absorbing_at_eliminated_row(monkeypatch) -> None:
    """An eliminated row breaks the adjacency walk."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {2, 3, 4}
    )
    picker = HeaderBandPicker(score_floor=1.0, adjacency_window=2)
    picker.policies = [
        lambda row, **kw: _verdict_for(
            row,
            score={2: 5.0, 3: 2.0, 4: 2.0}[row],
            eliminated=(row == 2),
        ),
    ]
    result = picker.run(canvas=canvas)
    band = result["header_band"]
    assert band is not None
    # Row 2 was eliminated even though it scored high — disqualified.
    # Anchor is row 3 or 4 (both score 2.0; max() picks the first).
    # Row 2 is excluded from absorption.
    assert band.rect.r0 in {3, 4}
    assert 2 not in range(band.rect.r0, band.rect.r1 + 1)


def test_run_respects_score_floor(monkeypatch) -> None:
    """Top candidate below the floor → None band."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {2, 3}
    )
    picker = HeaderBandPicker(score_floor=5.0)
    picker.policies = [
        lambda row, **kw: _verdict_for(row, {2: 1.0, 3: 2.0}[row]),
    ]
    result = picker.run(canvas=canvas)
    assert result["header_band"] is None
    # Verdicts still recorded for audit.
    assert len(result["verdicts"]) == 2


def test_run_emits_full_verdict_trail(monkeypatch) -> None:
    """The verdict trail contains every (policy, candidate) pair."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {1, 2, 3}
    )
    picker = HeaderBandPicker(score_floor=0.0)
    picker.policies = [
        lambda row, **kw: _verdict_for(row, 1.0),
        lambda row, **kw: PolicyVerdict("second_policy", row, 0.5),
    ]
    result = picker.run(canvas=canvas)
    assert len(result["verdicts"]) == 6  # 3 candidates × 2 policies
    names = {v.name for v in result["verdicts"]}
    assert names == {"stub_policy", "second_policy"}


def test_run_handles_single_candidate(monkeypatch) -> None:
    """Single candidate above floor → 1-row band."""
    canvas = _minimal_canvas()
    monkeypatch.setattr(
        "app.components.pickers.header_band.text_dense_rows", lambda *a, **kw: {3}
    )
    picker = HeaderBandPicker(score_floor=1.0, adjacency_window=2)
    picker.policies = [
        lambda row, **kw: _verdict_for(row, 2.0),
    ]
    result = picker.run(canvas=canvas)
    assert result["header_band"] is not None
    assert result["header_band"].rect.r0 == 3
    assert result["header_band"].rect.r1 == 3
    assert result["header_band"].rect.c1 == canvas.n_cols



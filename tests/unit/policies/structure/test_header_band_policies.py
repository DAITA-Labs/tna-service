"""Header-band policy units — score + elimination logic with synthetic canvas."""
from __future__ import annotations

from typing import Any

from app.artifacts.canvas import GridCanvas
from app.policies.structure.header_band import (
    eliminate_empty_rows,
    prefer_spec_label_hits,
)


# ── Fixture helpers ────────────────────────────────────────────────────────


def _blank_canvas(n_rows: int = 5, n_cols: int = 4) -> GridCanvas:
    """Build an empty canvas with `empty_row` channel set to all-empty."""
    return GridCanvas(
        n_rows=n_rows,
        n_cols=n_cols,
        cell_values=[[None] * n_cols for _ in range(n_rows)],
        channels={
            "empty_row": [[1] * n_cols for _ in range(n_rows)],
        },
    )


# ── eliminate_empty_rows ───────────────────────────────────────────────────


def test_eliminate_empty_rows_kills_empty_row() -> None:
    canvas = _blank_canvas()
    v = eliminate_empty_rows(row=2, canvas=canvas)
    assert v.eliminate is True
    assert v.candidate == 2
    assert v.score_delta == 0.0
    assert "empty" in v.message.lower()


def test_eliminate_empty_rows_passes_non_empty_row() -> None:
    canvas = _blank_canvas()
    canvas.channels["empty_row"][1] = [0] * canvas.n_cols  # row 2 → not empty
    v = eliminate_empty_rows(row=2, canvas=canvas)
    assert v.eliminate is False
    assert v.candidate == 2
    assert v.score_delta == 0.0


def test_eliminate_empty_rows_handles_missing_channel() -> None:
    """If the canvas hasn't computed `empty_row` yet, the policy is permissive."""
    canvas = GridCanvas(
        n_rows=3, n_cols=4,
        cell_values=[[None] * 4 for _ in range(3)],
        channels={},
    )
    v = eliminate_empty_rows(row=1, canvas=canvas)
    assert v.eliminate is False


# ── prefer_spec_label_hits ─────────────────────────────────────────────────


def test_prefer_spec_label_hits_scores_zero_when_no_matches(monkeypatch) -> None:
    """No spec matches → score_delta 0, message 'no matches'."""
    canvas = _blank_canvas()

    monkeypatch.setattr(
        "app.policies.structure.header_band.query_all", lambda *a, **kw: []
    )
    monkeypatch.setattr(
        "app.policies.structure.header_band.aggregate_by_row", lambda *a, **kw: {}
    )
    v = prefer_spec_label_hits(row=1, canvas=canvas)
    assert v.score_delta == 0.0
    assert v.eliminate is False
    assert "no matches" in v.message.lower()
    assert v.candidate == 1


def test_prefer_spec_label_hits_applies_phase_weights(monkeypatch) -> None:
    """Identifier hits (weight 2.0) should outscore stage hits (weight 1.0)."""
    canvas = _blank_canvas()

    monkeypatch.setattr(
        "app.policies.structure.header_band.query_all", lambda *a, **kw: ["dummy"]
    )
    monkeypatch.setattr(
        "app.policies.structure.header_band.aggregate_by_row",
        lambda *a, **kw: {3: {"phases": {"identifier": 2, "stage": 1}}},
    )
    v = prefer_spec_label_hits(row=3, canvas=canvas)
    # 2 identifier × 2.0 + 1 stage × 1.0 = 5.0
    assert v.score_delta == 5.0
    assert v.candidate == 3
    assert v.eliminate is False
    assert "identifier" in v.message


def test_prefer_spec_label_hits_respects_custom_phase_weights(monkeypatch) -> None:
    canvas = _blank_canvas()

    monkeypatch.setattr(
        "app.policies.structure.header_band.query_all", lambda *a, **kw: ["dummy"]
    )
    monkeypatch.setattr(
        "app.policies.structure.header_band.aggregate_by_row",
        lambda *a, **kw: {5: {"phases": {"identifier": 1, "metadata": 3}}},
    )
    v = prefer_spec_label_hits(
        row=5, canvas=canvas,
        phase_weights={"identifier": 10.0, "metadata": 0.1},
    )
    # 1 × 10.0 + 3 × 0.1 = 10.3
    assert v.score_delta == 10.3

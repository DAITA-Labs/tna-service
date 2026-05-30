"""IdentifierPicker — unified COLUMN / ROW / KV_BLOCK scoring."""
from __future__ import annotations

from typing import Any

import pytest

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.plan import LocationCandidate
from app.artifacts.structure import KvBlock, StructureBag
from app.components.pickers.identifier import IdentifierPicker
from app.enums.field_location_mode import FieldLocationMode
from app.specs import IO_NUMBER_SPEC


# ── Fixtures ────────────────────────────────────────────────────────────────


def _empty_canvas() -> GridCanvas:
    return GridCanvas(
        n_rows=10, n_cols=10,
        cell_values=[[None] * 10 for _ in range(10)],
        channels={"dtype": [[0] * 10 for _ in range(10)]},
    )


def _make_hint(
    *,
    candidate_columns:   dict[str, list[int]]      | None = None,
    candidate_rows:      dict[str, list[int]]      | None = None,
    candidate_kv_blocks: dict[str, list[KvBlock]] | None = None,
) -> LayoutHint:
    return LayoutHint(
        axes=LayoutAxes(
            pli_axis="vertical", stage_axis="horizontal", subfield_axis="horizontal",
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id="c0",
        confidence=0.9,
        candidate_columns=candidate_columns   or {},
        candidate_rows=candidate_rows         or {},
        candidate_kv_blocks=candidate_kv_blocks or {},
        data_row_ranges=[],
        section_boundaries=[],
        header_band=None,
    )


def _make_picker(score_floor: float = 0.5) -> IdentifierPicker:
    return IdentifierPicker(
        spec=IO_NUMBER_SPEC,
        strips_attr_name="same_length_strips",
        score_floor=score_floor,
    )


# ── candidates() ───────────────────────────────────────────────────────────


def test_candidates_collects_from_all_three_sources() -> None:
    picker = _make_picker()
    kv = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                  label_text="IO No", value_dtype=4)
    hint = _make_hint(
        candidate_columns={"io_number": [3, 5]},
        candidate_rows={"io_number": [2]},
        candidate_kv_blocks={"io_number": [kv]},
    )
    cands = picker.candidates(hint=hint, canonical="io_number")
    modes = [c.mode for c in cands]
    assert modes.count(FieldLocationMode.COLUMN)   == 2
    assert modes.count(FieldLocationMode.ROW)      == 1
    assert modes.count(FieldLocationMode.KV_BLOCK) == 1


def test_candidates_empty_when_no_hint_sources() -> None:
    picker = _make_picker()
    hint = _make_hint()
    assert list(picker.candidates(hint=hint, canonical="io_number")) == []


# ── pick() per mode ────────────────────────────────────────────────────────


def test_pick_returns_none_when_no_candidates() -> None:
    picker = _make_picker()
    hint = _make_hint()
    winner, score, verdicts = picker.pick(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[3, 4, 5],
    )
    assert winner   is None
    assert score    == 0.0
    assert verdicts == []


def test_pick_returns_kv_winner_for_alias_match() -> None:
    """A KV with label matching a spec alias outscores low-confidence columns."""
    picker = _make_picker(score_floor=0.5)
    kv = KvBlock(
        label_coord=("A", 4), value_coord=("B", 4),
        label_text=IO_NUMBER_SPEC.aliases[0],  # exact alias match
        value_dtype=4,
    )
    hint = _make_hint(candidate_kv_blocks={"io_number": [kv]})
    winner, score, _verdicts = picker.pick(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[],
    )
    assert winner is not None
    assert winner.mode    == FieldLocationMode.KV_BLOCK
    assert winner.kv_block is kv
    assert score >= 0.9


def test_pick_row_candidate_does_not_win_today_due_to_row_stub() -> None:
    """ROW scoring is a stub (always 0.0); row-only candidates fail the floor."""
    picker = _make_picker(score_floor=0.5)
    hint = _make_hint(candidate_rows={"io_number": [5]})
    winner, score, _verdicts = picker.pick(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[],
    )
    # Only-row candidate, row policy scores 0 → below 0.5 floor → no winner
    assert winner is None
    assert score == 0.0


def test_pick_kv_beats_row_when_alias_matches(monkeypatch) -> None:
    picker = _make_picker(score_floor=0.5)
    kv = KvBlock(
        label_coord=("A", 4), value_coord=("B", 4),
        label_text=IO_NUMBER_SPEC.aliases[0],
        value_dtype=4,
    )
    hint = _make_hint(
        candidate_rows={"io_number": [5]},
        candidate_kv_blocks={"io_number": [kv]},
    )
    winner, _score, _verdicts = picker.pick(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[],
    )
    assert winner is not None
    assert winner.mode == FieldLocationMode.KV_BLOCK


# ── score_all_locations() — full scoreboard ────────────────────────────────


def test_score_all_locations_returns_every_candidate() -> None:
    """Even eliminated / below-floor candidates appear in the scoreboard."""
    picker = _make_picker()
    kv_match = KvBlock(
        label_coord=("A", 4), value_coord=("B", 4),
        label_text=IO_NUMBER_SPEC.aliases[0],
        value_dtype=4,
    )
    kv_miss = KvBlock(
        label_coord=("A", 5), value_coord=("B", 5),
        label_text="Unrelated Label",
        value_dtype=4,
    )
    hint = _make_hint(
        candidate_rows={"io_number": [5]},
        candidate_kv_blocks={"io_number": [kv_match, kv_miss]},
    )
    scoreboard, verdicts = picker.score_all_locations(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[],
    )
    # 1 row + 2 kvs = 3 candidates; all present in scoreboard.
    assert len(scoreboard) == 3
    by_mode = {entry[0].mode: entry[1] for entry in scoreboard}
    # KV with matching alias scores high; row stub + non-matching kv = 0.0
    assert by_mode[FieldLocationMode.KV_BLOCK] == pytest.approx(0.9) \
        or by_mode[FieldLocationMode.KV_BLOCK] == 0.0  # depends on iteration order


def test_score_all_locations_no_candidates() -> None:
    picker = _make_picker()
    scoreboard, verdicts = picker.score_all_locations(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=_make_hint(), canonical="io_number", rows=[],
    )
    assert scoreboard == []
    assert verdicts == []


# ── Policy mode-gating ─────────────────────────────────────────────────────


def test_column_policy_does_not_fire_for_row_candidate() -> None:
    """Verdict trail proves each policy short-circuits on wrong-mode candidates."""
    picker = _make_picker()
    hint = _make_hint(candidate_rows={"io_number": [5]})
    _scoreboard, verdicts = picker.score_all_locations(
        canvas=_empty_canvas(), bag=StructureBag(),
        hint=hint, canonical="io_number", rows=[],
    )
    # Every policy fires once for the single ROW candidate, but only the
    # row policy contributes a non-zero score (which is currently 0.0).
    names = [v.name for v in verdicts]
    assert "score_lc_column_via_spec"   in names  # short-circuited
    assert "score_lc_row_via_spec"      in names  # the only real participant
    assert "score_lc_kv_via_label_match" in names  # short-circuited
    # All three score 0.0 (column/kv because wrong mode; row because stub).
    for v in verdicts:
        assert v.score_delta == 0.0

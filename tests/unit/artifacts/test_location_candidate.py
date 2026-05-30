"""LocationCandidate — tagged-union candidate type for IdentifierPicker."""
from __future__ import annotations

import dataclasses

import pytest

from app.artifacts.plan import LocationCandidate
from app.artifacts.structure import KvBlock
from app.enums.field_location_mode import FieldLocationMode


# ── Construction per mode ──────────────────────────────────────────────────


def test_column_mode_carries_column_index() -> None:
    lc = LocationCandidate(mode=FieldLocationMode.COLUMN, column=3)
    assert lc.mode == FieldLocationMode.COLUMN
    assert lc.column == 3
    assert lc.row is None
    assert lc.kv_block is None


def test_row_mode_carries_row_index() -> None:
    lc = LocationCandidate(mode=FieldLocationMode.ROW, row=5)
    assert lc.mode == FieldLocationMode.ROW
    assert lc.row == 5
    assert lc.column is None
    assert lc.kv_block is None


def test_kv_block_mode_carries_kv() -> None:
    kv = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                  label_text="Buyer", value_dtype=4)
    lc = LocationCandidate(mode=FieldLocationMode.KV_BLOCK, kv_block=kv)
    assert lc.mode == FieldLocationMode.KV_BLOCK
    assert lc.kv_block is kv
    assert lc.column is None
    assert lc.row is None


def test_construction_with_mode_only_leaves_all_coords_none() -> None:
    """Useful for sentinel candidates before any coord is known."""
    lc = LocationCandidate(mode=FieldLocationMode.MISSING)
    assert lc.column is None
    assert lc.row is None
    assert lc.kv_block is None


# ── Hashability + equality (required for scoreboard dict keys) ────────────


def test_is_hashable() -> None:
    lc = LocationCandidate(mode=FieldLocationMode.COLUMN, column=1)
    assert hash(lc) == hash(LocationCandidate(mode=FieldLocationMode.COLUMN, column=1))


def test_works_as_dict_key() -> None:
    lc_a = LocationCandidate(mode=FieldLocationMode.COLUMN, column=1)
    lc_b = LocationCandidate(mode=FieldLocationMode.COLUMN, column=2)
    lc_c = LocationCandidate(mode=FieldLocationMode.ROW,    row=5)
    scores: dict[LocationCandidate, float] = {lc_a: 0.5, lc_b: 0.9, lc_c: 0.7}
    assert scores[lc_b] == 0.9


def test_structural_equality() -> None:
    a = LocationCandidate(mode=FieldLocationMode.COLUMN, column=3)
    b = LocationCandidate(mode=FieldLocationMode.COLUMN, column=3)
    c = LocationCandidate(mode=FieldLocationMode.COLUMN, column=4)
    assert a == b
    assert a != c


def test_different_modes_at_same_coord_are_not_equal() -> None:
    """Mode is part of identity — column 5 ≠ row 5."""
    col_5 = LocationCandidate(mode=FieldLocationMode.COLUMN, column=5)
    row_5 = LocationCandidate(mode=FieldLocationMode.ROW,    row=5)
    assert col_5 != row_5


def test_kv_block_candidates_compare_by_kv_identity() -> None:
    kv1 = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                   label_text="Buyer", value_dtype=4)
    kv2 = KvBlock(label_coord=("A", 4), value_coord=("B", 4),
                   label_text="Buyer", value_dtype=4)
    a = LocationCandidate(mode=FieldLocationMode.KV_BLOCK, kv_block=kv1)
    b = LocationCandidate(mode=FieldLocationMode.KV_BLOCK, kv_block=kv2)
    # KvBlock is a frozen dataclass — equal-by-fields, so candidates match.
    assert a == b


# ── Frozenness ─────────────────────────────────────────────────────────────


def test_is_frozen() -> None:
    lc = LocationCandidate(mode=FieldLocationMode.COLUMN, column=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lc.column = 2  # type: ignore[misc]


# ── Package re-export ──────────────────────────────────────────────────────


def test_reexported_from_artifacts_package() -> None:
    from app.artifacts import LocationCandidate as Reexp
    assert Reexp is LocationCandidate

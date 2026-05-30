"""PlanAssembler — scoreboard-flow integration tests."""
from __future__ import annotations

import pytest

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.plan import LocationCandidate
from app.artifacts.structure import DataRowRange, KvBlock, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.plan.plan_assembler import PlanAssembler
from app.components.pickers.identifier_picker_registry import (
    IDENTIFIER_PICKER_CONFIGS,
)
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.specs import IO_NUMBER_SPEC


# ── Fixture helpers ────────────────────────────────────────────────────────


def _make_bundle(
    *,
    pli_axis:            str = "vertical",
    candidate_columns:   dict[str, list[int]] | None = None,
    candidate_rows:      dict[str, list[int]] | None = None,
    candidate_kv_blocks: dict[str, list[KvBlock]] | None = None,
    data_row_ranges:     list[DataRowRange] | None = None,
    cluster_id:          str = "c0",
    anchor_sheet_name:   str = "TNA",
) -> ClusterAnchorBundle:
    canvas = GridCanvas(
        n_rows=20, n_cols=10,
        cell_values=[[None] * 10 for _ in range(20)],
        channels={},
    )
    bag = StructureBag()
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis=pli_axis, stage_axis="horizontal", subfield_axis="horizontal",
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id=cluster_id,
        confidence=0.9,
        candidate_columns=candidate_columns   or {},
        candidate_rows=candidate_rows         or {},
        candidate_kv_blocks=candidate_kv_blocks or {},
        data_row_ranges=data_row_ranges or [DataRowRange(row_start=4, row_end=8)],
        section_boundaries=[],
        header_band=None,
    )
    cluster = PliCluster(cluster_id=cluster_id, sheet_names=[anchor_sheet_name])
    return ClusterAnchorBundle(
        cluster=cluster, anchor_sheet_name=anchor_sheet_name,
        canvas=canvas, bag=bag, hint=hint,
    )


# ── Plan-level identity + axis + rows ──────────────────────────────────────


def test_plan_carries_cluster_identity() -> None:
    bundle = _make_bundle(cluster_id="cluster-42", anchor_sheet_name="MAIN FALL")
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.cluster_id        == "cluster-42"
    assert plan.anchor_sheet_name == "MAIN FALL"


def test_plan_resolves_pli_axis_vertical_to_row() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle(pli_axis="vertical"))["plan"]
    assert plan.pli_axis == PliAxis.ROW


def test_plan_resolves_sheet_axis_to_whole_sheet() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle(pli_axis="sheet"))["plan"]
    assert plan.pli_axis == PliAxis.WHOLE_SHEET


def test_plan_flattens_data_row_ranges() -> None:
    bundle = _make_bundle(data_row_ranges=[
        DataRowRange(row_start=4, row_end=6),
        DataRowRange(row_start=10, row_end=11),
    ])
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.pli_rows == [4, 5, 6, 10, 11]


# ── Field locations: one entry per registered canonical ────────────────────


def test_every_registered_canonical_has_a_field_location() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle())["plan"]
    for canonical in IDENTIFIER_PICKER_CONFIGS:
        assert canonical in plan.field_locations


def test_canonicals_without_candidates_are_marked_missing() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle(candidate_columns={}))["plan"]
    io_loc = plan.field_locations["io_number"]
    assert io_loc.mode == FieldLocationMode.MISSING


# ── KV-mode winner: a KvBlock matching a spec alias wins ───────────────────


def test_kv_block_winner_produces_sheet_scoped_fixed_field_location() -> None:
    kv = KvBlock(
        label_coord=("A", 4), value_coord=("B", 4),
        label_text=IO_NUMBER_SPEC.aliases[0],  # exact alias match → high score
        value_dtype=4,
    )
    bundle = _make_bundle(candidate_kv_blocks={"io_number": [kv]})
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    io_loc = plan.field_locations["io_number"]

    assert io_loc.mode           == FieldLocationMode.KV_BLOCK
    assert io_loc.scope          == FieldScope.SHEET
    assert io_loc.read_direction == ReadDirection.FIXED
    assert io_loc.kv_block       is kv


# ── Scoreboards on the plan ────────────────────────────────────────────────


def test_plan_carries_per_canonical_scoreboards() -> None:
    kv = KvBlock(
        label_coord=("A", 4), value_coord=("B", 4),
        label_text=IO_NUMBER_SPEC.aliases[0],
        value_dtype=4,
    )
    bundle = _make_bundle(
        candidate_columns={"io_number": [1, 2]},
        candidate_kv_blocks={"io_number": [kv]},
    )
    plan = PlanAssembler().run(bundle=bundle)["plan"]

    io_scoreboard = plan.scoreboards["io_number"]
    # Two column candidates + one kv candidate = 3 entries
    assert len(io_scoreboard) == 3
    modes_in_scoreboard = {entry[0].mode for entry in io_scoreboard}
    assert FieldLocationMode.COLUMN   in modes_in_scoreboard
    assert FieldLocationMode.KV_BLOCK in modes_in_scoreboard


def test_scoreboard_present_for_every_registered_canonical() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle())["plan"]
    for canonical in IDENTIFIER_PICKER_CONFIGS:
        assert canonical in plan.scoreboards


# ── Cross-field warnings on the plan ───────────────────────────────────────


def test_empty_scoreboards_produce_cross_field_warnings() -> None:
    """No candidates anywhere → mandatory + trio warnings fire."""
    plan = PlanAssembler().run(bundle=_make_bundle())["plan"]
    warning_names = {w.name for w in plan.warnings}

    # Mandatory canonicals (io_number, quantity) are missing
    assert "mandatory_missing_io_number" in warning_names
    assert "mandatory_missing_quantity"  in warning_names
    # Date trio all missing
    assert "date_trio_all_missing"       in warning_names


def test_cross_field_verdicts_carried_in_all_verdicts() -> None:
    plan = PlanAssembler().run(bundle=_make_bundle())["plan"]
    verdict_names = {v.name for v in plan.all_verdicts}
    assert "at_least_one_date_trio_member_present" in verdict_names
    assert "mandatory_canonicals_must_be_located"   in verdict_names


# ── Score floor gating ─────────────────────────────────────────────────────


def test_below_floor_winner_becomes_missing(monkeypatch) -> None:
    """A picker that returns scores below the floor → FieldLocation.mode = MISSING."""
    # Stub all IdentifierPicker.score_all_locations to return one low-score entry.
    def fake_score_all_locations(self, **kw):
        canonical = kw["canonical"]
        return (
            [(
                LocationCandidate(mode=FieldLocationMode.COLUMN, column=1),
                0.3,    # below the 0.5 floor
                False,
            )],
            [],
        )
    monkeypatch.setattr(
        "app.components.pickers.identifier.IdentifierPicker.score_all_locations",
        fake_score_all_locations,
    )

    plan = PlanAssembler().run(bundle=_make_bundle())["plan"]
    for canonical in IDENTIFIER_PICKER_CONFIGS:
        assert plan.field_locations[canonical].mode == FieldLocationMode.MISSING

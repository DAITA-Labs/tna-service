"""PlanAssembler — registry-driven CanvasPlan construction tests."""
from __future__ import annotations

from typing import Any

import pytest

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.plan import FieldLocation
from app.artifacts.structure import DataRowRange, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.plan.plan_assembler import PlanAssembler
from app.components.pickers.identifier_picker_registry import (
    IDENTIFIER_PICKER_CONFIGS,
)
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection


# ── Fixture helpers ────────────────────────────────────────────────────────


def _make_bundle(
    *,
    pli_axis: str = "vertical",
    candidate_columns: dict[str, list[int]] | None = None,
    data_row_ranges:   list[DataRowRange] | None = None,
    cluster_id: str = "c0",
    anchor_sheet_name: str = "TNA",
) -> ClusterAnchorBundle:
    canvas = GridCanvas(
        n_rows=20, n_cols=10,
        cell_values=[[None] * 10 for _ in range(20)],
        channels={},
    )
    bag = StructureBag()
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis=pli_axis,
            stage_axis="horizontal",
            subfield_axis="horizontal",
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id=cluster_id,
        confidence=0.9,
        candidate_columns=candidate_columns or {},
        candidate_rows={},
        data_row_ranges=data_row_ranges or [DataRowRange(row_start=4, row_end=8)],
        section_boundaries=[],
        header_band=None,
    )
    cluster = PliCluster(cluster_id=cluster_id, sheet_names=[anchor_sheet_name])
    return ClusterAnchorBundle(
        cluster=cluster,
        anchor_sheet_name=anchor_sheet_name,
        canvas=canvas, bag=bag, hint=hint,
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_plan_carries_cluster_identity() -> None:
    bundle = _make_bundle(cluster_id="cluster-42", anchor_sheet_name="MAIN FALL")
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.cluster_id        == "cluster-42"
    assert plan.anchor_sheet_name == "MAIN FALL"


def test_plan_resolves_pli_axis_from_layout_hint() -> None:
    """The legacy axis string 'vertical' maps to PliAxis.ROW."""
    bundle = _make_bundle(pli_axis="vertical")
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.pli_axis == PliAxis.ROW


def test_plan_resolves_horizontal_axis_to_column() -> None:
    bundle = _make_bundle(pli_axis="horizontal")
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.pli_axis == PliAxis.COLUMN


def test_plan_resolves_sheet_axis_to_whole_sheet() -> None:
    bundle = _make_bundle(pli_axis="sheet")
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.pli_axis == PliAxis.WHOLE_SHEET


def test_plan_flattens_data_row_ranges_into_pli_rows() -> None:
    bundle = _make_bundle(data_row_ranges=[
        DataRowRange(row_start=4, row_end=7),
        DataRowRange(row_start=10, row_end=12),
    ])
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    assert plan.pli_rows == [4, 5, 6, 7, 10, 11, 12]


def test_plan_emits_field_location_for_every_registered_canonical() -> None:
    """Every entry in IDENTIFIER_PICKER_CONFIGS produces a FieldLocation,
    even when no candidate columns means the picker returns MISSING."""
    bundle = _make_bundle()
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    for canonical in IDENTIFIER_PICKER_CONFIGS:
        assert canonical in plan.field_locations


def test_plan_marks_canonicals_without_candidates_as_missing() -> None:
    """No candidate_columns → FieldLocation.mode = MISSING."""
    bundle = _make_bundle(candidate_columns={})
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    io_loc = plan.field_locations["io_number"]
    assert io_loc.mode == FieldLocationMode.MISSING
    assert io_loc.column is None


def test_plan_field_locations_default_to_pli_scope_and_same_row(monkeypatch) -> None:
    """For ROW_PER_PLI layouts, defaults are scope=PLI + dir=SAME_ROW."""
    # Stub IdentifierColumnPicker.pick to return a winner for io_number only.
    def fake_pick(self, **kw):
        # spec.canonical is bound via the picker's __init__ — use it to gate.
        if self._spec.canonical == "io_number":
            return (1, 0.9, [])
        return (None, 0.0, [])

    monkeypatch.setattr(
        "app.components.pickers.identifier_column.IdentifierColumnPicker.pick",
        fake_pick,
    )
    bundle = _make_bundle(candidate_columns={"io_number": [1, 2]})
    plan = PlanAssembler().run(bundle=bundle)["plan"]
    io_loc = plan.field_locations["io_number"]
    assert io_loc.mode           == FieldLocationMode.COLUMN
    assert io_loc.column         == 1
    assert io_loc.scope          == FieldScope.PLI
    assert io_loc.read_direction == ReadDirection.SAME_ROW
    assert io_loc.score          == pytest.approx(0.9)

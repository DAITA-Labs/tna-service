"""CanvasApplier — CanvasPlan + canvas → list[PLI]."""
from __future__ import annotations

from datetime import date

from app.artifacts.canvas import GridCanvas
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    MetadataPlan,
    StageBandPlan,
)
from app.artifacts.structure import KvBlock, Rect
from app.components.plan.canvas_applier import CanvasApplier
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.enums.subfield_axis import SubfieldAxis


# ── Fixture helpers ────────────────────────────────────────────────────────


def _canvas(cells: list[list]) -> GridCanvas:
    return GridCanvas(
        n_rows=len(cells),
        n_cols=len(cells[0]) if cells else 0,
        cell_values=cells,
        channels={},
    )


def _row_plan(
    *,
    pli_rows:         list[int],
    field_locations:  dict[str, FieldLocation] | None = None,
    stage_bands:      list[StageBandPlan] | None      = None,
    metadata_entries: list[MetadataPlan] | None       = None,
) -> CanvasPlan:
    return CanvasPlan(
        cluster_id="c0",
        anchor_sheet_name="TNA",
        pli_axis=PliAxis.ROW,
        pli_rows=pli_rows,
        field_locations=field_locations or {},
        stage_bands=stage_bands or [],
        metadata_entries=metadata_entries or [],
    )


# ── Top-level shape ────────────────────────────────────────────────────────


def test_empty_plan_yields_no_plis() -> None:
    plan   = _row_plan(pli_rows=[])
    canvas = _canvas([[None]])
    out    = CanvasApplier().run(plan=plan, canvas=canvas)
    assert out["plis"] == []


def test_one_pli_per_row_in_pli_rows() -> None:
    plan   = _row_plan(pli_rows=[4, 5, 6])
    canvas = _canvas([[None] * 5 for _ in range(10)])
    out    = CanvasApplier().run(plan=plan, canvas=canvas)
    assert len(out["plis"]) == 3


# ── COLUMN-mode field locations ────────────────────────────────────────────


def test_column_mode_reads_per_row_value() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[3][1] = "ION-1063"   # row 4, col B
    cells[4][1] = "ION-1064"   # row 5, col B
    plan = _row_plan(
        pli_rows=[4, 5],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=2, score=0.92,
        )},
    )
    out = CanvasApplier().run(plan=plan, canvas=_canvas(cells))
    plis = out["plis"]
    assert plis[0].io_number == "ION-1063"
    assert plis[1].io_number == "ION-1064"


def test_column_mode_records_confidence_and_source_cell() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[3][1] = "ION-1063"
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=2, score=0.92,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.confidence["io_number"]   == 0.92
    assert pli.source.cells["io_number"] == "B4"
    assert pli.source.sheet              == "TNA"
    assert pli.source.rows               == [4]


# ── KV_BLOCK-mode field locations ──────────────────────────────────────────


def test_kv_block_mode_broadcasts_to_every_pli() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[1][1] = "MAIN-FALL"   # value at B2
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Style", value_dtype=4)
    plan = _row_plan(
        pli_rows=[4, 5],
        field_locations={"style_code": FieldLocation(
            canonical="style_code",
            mode=FieldLocationMode.KV_BLOCK,
            scope=FieldScope.SHEET,
            read_direction=ReadDirection.FIXED,
            kv_block=kv, score=0.88,
        )},
    )
    plis = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"]
    assert plis[0].style_code == "MAIN-FALL"
    assert plis[1].style_code == "MAIN-FALL"
    assert plis[0].source.cells["style_code"] == "B2"


# ── MISSING is dropped ─────────────────────────────────────────────────────


def test_missing_field_location_yields_no_attribute() -> None:
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.MISSING,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas([[None]]))["plis"][0]
    assert pli.io_number is None
    assert "io_number" not in pli.confidence
    assert "io_number" not in pli.source.cells


# ── Blank cells skip cleanly ───────────────────────────────────────────────


def test_blank_cell_does_not_emit_value() -> None:
    cells = [[None] * 5 for _ in range(10)]
    # row 4 has no value at col B → skip
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=2, score=0.9,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.io_number is None


# ── Off-PLI identifiers go to metadata ─────────────────────────────────────


def test_off_pli_identifier_falls_through_to_metadata() -> None:
    """ex_fty_date / shipment_date / fabric_name have no flat PLI field — metadata."""
    cells = [[None] * 5 for _ in range(10)]
    cells[3][2] = date(2026, 6, 1)
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"ex_fty_date": FieldLocation(
            canonical="ex_fty_date",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=3, score=0.85,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.metadata["ex_fty_date"]      == date(2026, 6, 1)
    assert pli.source.cells["ex_fty_date"]  == "C4"


# ── Stage bands → Stage objects ────────────────────────────────────────────


def test_stage_band_reads_planned_date_at_anchor_column() -> None:
    cells = [[None] * 6 for _ in range(10)]
    cells[3][4] = date(2026, 6, 10)   # row 4, col E
    band = StageBandPlan(
        name="Sewing", canonical="sewing",
        anchor_coord=(3, 5),           # name at (row 3, col E)
        anchor_rect=Rect(r0=3, c0=5, r1=15, c1=5),
        scope=FieldScope.PLI,
        subfield_axis=SubfieldAxis.HORIZONTAL,
        read_direction=ReadDirection.SAME_ROW,
        score=0.9,
    )
    plan = _row_plan(pli_rows=[4], stage_bands=[band])
    pli  = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert len(pli.stages)          == 1
    assert pli.stages[0].name       == "Sewing"
    assert pli.stages[0].planned_date == date(2026, 6, 10)
    assert pli.stages[0].source.cells["planned_date"] == "E4"


def test_stage_band_subfield_indices_override_anchor_column() -> None:
    cells = [[None] * 6 for _ in range(10)]
    cells[3][3] = date(2026, 6, 15)   # planned at col D
    cells[3][4] = "Sewing"
    band = StageBandPlan(
        name="Sewing", canonical="sewing",
        anchor_coord=(3, 5),
        anchor_rect=Rect(r0=3, c0=4, r1=15, c1=5),
        scope=FieldScope.PLI,
        subfield_axis=SubfieldAxis.HORIZONTAL,
        read_direction=ReadDirection.SAME_ROW,
        subfield_indices={"planned_date": 4},
        score=0.9,
    )
    plan = _row_plan(pli_rows=[4], stage_bands=[band])
    pli  = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.stages[0].planned_date == date(2026, 6, 15)


def test_stage_extra_subfields_land_in_stage_metadata() -> None:
    cells = [[None] * 6 for _ in range(10)]
    cells[3][4] = date(2026, 6, 10)
    cells[3][5] = 500              # qty at col F
    band = StageBandPlan(
        name="Cutting", canonical="cutting",
        anchor_coord=(3, 5),
        anchor_rect=Rect(r0=3, c0=5, r1=15, c1=6),
        scope=FieldScope.PLI,
        subfield_axis=SubfieldAxis.HORIZONTAL,
        read_direction=ReadDirection.SAME_ROW,
        subfield_indices={"planned_date": 5, "quantity": 6},
        score=0.9,
    )
    plan  = _row_plan(pli_rows=[4], stage_bands=[band])
    pli   = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    stage = pli.stages[0]
    assert stage.planned_date         == date(2026, 6, 10)
    assert stage.metadata["quantity"] == 500


# ── Metadata entries ───────────────────────────────────────────────────────


def test_column_metadata_reads_per_row() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[3][3] = "rush"   # row 4, col D
    entry = MetadataPlan(
        header_text="Comments",
        mode=FieldLocationMode.COLUMN,
        scope=FieldScope.PLI,
        read_direction=ReadDirection.SAME_ROW,
        column=4,
    )
    plan = _row_plan(pli_rows=[4], metadata_entries=[entry])
    pli  = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.metadata["Comments"]      == "rush"
    assert pli.source.cells["Comments"]  == "D4"


def test_kv_block_metadata_broadcasts() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[1][1] = "Acme Buyer"
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Buyer", value_dtype=4)
    entry = MetadataPlan(
        header_text="Buyer", canonical="buyer",
        mode=FieldLocationMode.KV_BLOCK,
        scope=FieldScope.SHEET,
        read_direction=ReadDirection.FIXED,
        kv_block=kv,
    )
    plan = _row_plan(pli_rows=[4, 5], metadata_entries=[entry])
    plis = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"]
    assert plis[0].metadata["buyer"] == "Acme Buyer"
    assert plis[1].metadata["buyer"] == "Acme Buyer"


# ── WHOLE_SHEET PLI axis ───────────────────────────────────────────────────


def test_whole_sheet_axis_produces_one_pli() -> None:
    cells = [[None] * 5 for _ in range(10)]
    cells[1][1] = "MAIN-FALL"
    kv = KvBlock(label_coord=("A", 2), value_coord=("B", 2),
                  label_text="Style", value_dtype=4)
    plan = CanvasPlan(
        cluster_id="c0", anchor_sheet_name="TNA",
        pli_axis=PliAxis.WHOLE_SHEET,
        field_locations={"style_code": FieldLocation(
            canonical="style_code",
            mode=FieldLocationMode.KV_BLOCK,
            scope=FieldScope.SHEET,
            read_direction=ReadDirection.FIXED,
            kv_block=kv, score=0.95,
        )},
    )
    plis = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"]
    assert len(plis)            == 1
    assert plis[0].style_code   == "MAIN-FALL"
    assert plis[0].source.rows  == []
    assert plis[0].stages       == []


# ── Out-of-bounds coords are tolerated ─────────────────────────────────────


def test_out_of_bounds_column_yields_no_value() -> None:
    cells = [[None] * 3 for _ in range(5)]
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=99, score=0.9,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas(cells))["plis"][0]
    assert pli.io_number is None
    assert "io_number" not in pli.confidence


# ── Sheet name resolution ──────────────────────────────────────────────────


def test_explicit_sheet_arg_overrides_plan_anchor_sheet() -> None:
    cells = [[None] * 3 for _ in range(5)]
    cells[3][1] = "ION-1"
    plan = _row_plan(
        pli_rows=[4],
        field_locations={"io_number": FieldLocation(
            canonical="io_number",
            mode=FieldLocationMode.COLUMN,
            scope=FieldScope.PLI,
            read_direction=ReadDirection.SAME_ROW,
            column=2, score=0.9,
        )},
    )
    pli = CanvasApplier().run(plan=plan, canvas=_canvas(cells), sheet="OVERRIDE")["plis"][0]
    assert pli.source.sheet == "OVERRIDE"

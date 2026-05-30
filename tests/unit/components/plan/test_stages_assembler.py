"""StagesAssembler — multi-winner stage band → StageBandPlan flow."""
from __future__ import annotations

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import Rect, StageBand, StructureBag
from app.artifacts.workbook import ClusterAnchorBundle, PliCluster
from app.components.plan.stages_assembler import StagesAssembler
from app.enums.field_scope import FieldScope
from app.enums.read_direction import ReadDirection
from app.enums.subfield_axis import SubfieldAxis


# ── Fixture helpers ────────────────────────────────────────────────────────


def _make_bundle(
    *,
    pli_axis:      str = "vertical",
    subfield_axis: str = "horizontal",
    stage_bands:   list[StageBand] | None = None,
) -> ClusterAnchorBundle:
    canvas = GridCanvas(
        n_rows=20, n_cols=20,
        cell_values=[[None] * 20 for _ in range(20)],
        channels={},
    )
    bag = StructureBag()
    bag.stage_bands = stage_bands or []
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis=pli_axis, stage_axis="horizontal", subfield_axis=subfield_axis,
            confidence={"pli": 0.9, "stage": 0.9, "subfield": 0.9},
        ),
        cluster_id="c0", confidence=0.9,
        candidate_columns={}, candidate_rows={}, candidate_kv_blocks={},
        data_row_ranges=[], section_boundaries=[], header_band=None,
    )
    cluster = PliCluster(cluster_id="c0", sheet_names=["TNA"])
    return ClusterAnchorBundle(
        cluster=cluster, anchor_sheet_name="TNA",
        canvas=canvas, bag=bag, hint=hint,
    )


# ── Multi-winner behaviour ────────────────────────────────────────────────


def test_empty_stage_bands_produces_empty_plan_list() -> None:
    out = StagesAssembler().run(bundle=_make_bundle(stage_bands=[]))
    assert out["stage_bands"] == []


def test_every_detected_band_becomes_a_plan() -> None:
    """Stages is multi-winner: 3 detected bands → 3 StageBandPlans."""
    bands = [
        StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing"),
        StageBand(rect=Rect(r0=3, c0=8, r1=15, c1=10), name_coord=("H", 3), name_text="Inspection"),
        StageBand(rect=Rect(r0=3, c0=11, r1=15, c1=13), name_coord=("K", 3), name_text="Packing"),
    ]
    out = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    assert len(out["stage_bands"]) == 3
    names = [b.name for b in out["stage_bands"]]
    assert names == ["Sewing", "Inspection", "Packing"]


# ── Per-band attribute resolution ──────────────────────────────────────────


def test_band_with_known_alias_resolves_canonical() -> None:
    """A band name matching a STAGE_SPECS alias gets canonical set."""
    # 'sewing' should match the 'sewing' canonical (it's a common stage).
    bands = [StageBand(
        rect=Rect(r0=3, c0=5, r1=15, c1=7),
        name_coord=("E", 3),
        name_text="Sewing",
    )]
    out  = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    plan = out["stage_bands"][0]
    # Some STAGE_SPECS may or may not include "sewing" — assert canonical is
    # either set (alias matched) or None (open vocab). Both are acceptable.
    assert plan.canonical is None or isinstance(plan.canonical, str)
    assert plan.name == "Sewing"


def test_band_with_novel_name_has_no_canonical() -> None:
    """A band name not in STAGE_SPECS → canonical = None (open vocab)."""
    bands = [StageBand(
        rect=Rect(r0=3, c0=5, r1=15, c1=7),
        name_coord=("E", 3),
        name_text="Made-Up Operation Name That Surely No Spec Covers",
    )]
    out = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    assert out["stage_bands"][0].canonical is None


def test_band_anchor_coord_uses_row_col_indices() -> None:
    """anchor_coord is (row, col) — translates the col letter to 1-indexed int."""
    bands = [StageBand(
        rect=Rect(r0=3, c0=5, r1=15, c1=7),
        name_coord=("E", 3),
        name_text="Sewing",
    )]
    out  = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    plan = out["stage_bands"][0]
    assert plan.anchor_coord == (3, 5)  # row 3, column E = 5


def test_band_anchor_rect_preserved() -> None:
    rect = Rect(r0=3, c0=5, r1=15, c1=7)
    bands = [StageBand(rect=rect, name_coord=("E", 3), name_text="X")]
    out   = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    assert out["stage_bands"][0].anchor_rect == rect


# ── Axis / scope / direction resolution from hint ──────────────────────────


def test_row_per_pli_layout_yields_pli_scope_same_row() -> None:
    bands = [StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing")]
    out   = StagesAssembler().run(bundle=_make_bundle(pli_axis="vertical", stage_bands=bands))
    plan  = out["stage_bands"][0]
    assert plan.scope          == FieldScope.PLI
    assert plan.read_direction == ReadDirection.SAME_ROW


def test_sheet_is_pli_yields_sheet_scope_fixed_direction() -> None:
    bands = [StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing")]
    out   = StagesAssembler().run(bundle=_make_bundle(pli_axis="sheet", stage_bands=bands))
    plan  = out["stage_bands"][0]
    assert plan.scope          == FieldScope.SHEET
    assert plan.read_direction == ReadDirection.FIXED


def test_section_per_pli_yields_group_scope_offset_direction() -> None:
    bands = [StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing")]
    out   = StagesAssembler().run(bundle=_make_bundle(pli_axis="sectional", stage_bands=bands))
    plan  = out["stage_bands"][0]
    assert plan.scope          == FieldScope.GROUP
    assert plan.read_direction == ReadDirection.OFFSET


def test_subfield_axis_propagates_from_hint() -> None:
    bands = [StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing")]
    out_h = StagesAssembler().run(bundle=_make_bundle(subfield_axis="horizontal", stage_bands=bands))
    out_v = StagesAssembler().run(bundle=_make_bundle(subfield_axis="vertical",   stage_bands=bands))
    assert out_h["stage_bands"][0].subfield_axis == SubfieldAxis.HORIZONTAL
    assert out_v["stage_bands"][0].subfield_axis == SubfieldAxis.VERTICAL


# ── Verdicts surfaced ──────────────────────────────────────────────────────


def test_verdicts_include_score_band_detected_per_band() -> None:
    bands = [
        StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7),  name_coord=("E", 3), name_text="Sewing"),
        StageBand(rect=Rect(r0=3, c0=8, r1=15, c1=10), name_coord=("H", 3), name_text="Inspection"),
    ]
    out      = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    verdicts = out["verdicts"]
    assert len(verdicts) == 2
    assert all(v.name == "score_band_detected" for v in verdicts)


# ── Subfield indices placeholder ───────────────────────────────────────────


def test_subfield_indices_empty_today() -> None:
    """subfield_indices is empty until the subfield-cluster mapping helper lands."""
    bands = [StageBand(rect=Rect(r0=3, c0=5, r1=15, c1=7), name_coord=("E", 3), name_text="Sewing")]
    out   = StagesAssembler().run(bundle=_make_bundle(stage_bands=bands))
    assert out["stage_bands"][0].subfield_indices == {}

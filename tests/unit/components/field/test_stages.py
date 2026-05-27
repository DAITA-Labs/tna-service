"""StageExtractor — per-PLI stages from StageBands + SubfieldClusters."""
from __future__ import annotations

import datetime as dt

from haystack import Pipeline

from app.artifacts.structure import Rect, StageBand, SubfieldCluster
from app.components.field.stages import StageExtractor
from tests.unit.components.field._bundles import make_bundle


# Helper: build a bundle with N PLI rows + the given stage_bands / clusters.
def _bundle_with_stages(values, bands, clusters):
    return make_bundle(
        values, "stages",
        columns={}, rows={},
        stage_bands=bands, subfield_clusters=clusters,
    )


# ─── No-data paths ──────────────────────────────────────────────────────────


def test_no_stage_bands_yields_empty_dict() -> None:
    bundle = make_bundle([[None] * 4 for _ in range(5)], "stages",
                         columns={}, rows={})
    out = StageExtractor().run(bundle=bundle)
    assert out["stages_per_row"] == {}


def test_no_data_rows_yields_empty_dict() -> None:
    """A bundle whose hint has no data_row_ranges → empty output."""
    bundle = make_bundle([[None] * 4 for _ in range(5)], "stages",
                         columns={}, rows={})
    bundle.hint.data_row_ranges = []
    bundle.bag.stage_bands = [StageBand(
        rect=Rect(4, 3, 7, 3), name_coord=("C", 2), name_text="PPS",
    )]
    assert StageExtractor().run(bundle=bundle)["stages_per_row"] == {}


# ─── Single-column band (band rect IS the plan_date column) ────────────────


def test_single_column_band_band_rect_is_plan_date() -> None:
    """A band with no SubfieldCluster: the band's column carries plan_date directly."""
    values = [
        [None, None, None],         # row 1
        [None, None, "PPS"],        # row 2 — band name above
        [None, None, dt.date(2026, 5, 27)],   # row 3 — data row 1
        [None, None, dt.date(2026, 6, 1)],    # row 4 — data row 2
    ]
    band = StageBand(rect=Rect(3, 3, 4, 3), name_coord=("C", 2), name_text="PPS")
    bundle = _bundle_with_stages(values, [band], [])

    out = StageExtractor().run(bundle=bundle)
    assert set(out["stages_per_row"].keys()) == {3, 4}
    s3 = out["stages_per_row"][3][0]
    assert s3.name == "PPS"
    assert s3.plan_date == dt.date(2026, 5, 27)
    assert s3.plan_date_col == 3
    assert s3.stage_metadata == {}


# ─── Multi-column band with Plan / Actual sub-headers ──────────────────────


def test_multi_column_band_plan_and_actual() -> None:
    """A band with Plan + Actual sub-headers — plan_date first-class, actual_date in metadata."""
    values = [
        [None, None, None, None],
        [None, None, "PP Send", None],             # band name (exact alias)
        [None, None, "Plan", "Actual"],            # sub-headers — row 3 (band.rect.r0 - 1)
        [None, None, dt.date(2026, 5, 1), dt.date(2026, 5, 5)],
        [None, None, dt.date(2026, 5, 8), None],
    ]
    band = StageBand(rect=Rect(4, 3, 5, 4), name_coord=("C", 2), name_text="PP Send")
    cluster = SubfieldCluster(parent_band_id=0, subfield_coords=((3, 3), (3, 4)))
    bundle = _bundle_with_stages(values, [band], [cluster])

    out = StageExtractor().run(bundle=bundle)
    s4 = out["stages_per_row"][4][0]
    assert s4.name == "PP Send"
    assert s4.canonical == "pre_production_send"
    assert s4.plan_date == dt.date(2026, 5, 1)
    assert s4.plan_date_col == 3
    assert s4.stage_metadata == {"actual_date": dt.date(2026, 5, 5)}

    s5 = out["stages_per_row"][5][0]
    assert s5.plan_date == dt.date(2026, 5, 8)
    assert s5.stage_metadata == {}   # Actual was blank


# ─── Open vocab: novel sub-header text → stays in metadata under raw key ───


def test_unknown_subfield_header_stored_under_raw_key() -> None:
    values = [
        [None, None, None, None],
        [None, None, "Cutting", None],
        [None, None, "Plan", "Treatment Tag"],     # novel header
        [None, None, dt.date(2026, 6, 1), "Stone wash"],
    ]
    band = StageBand(rect=Rect(4, 3, 4, 4), name_coord=("C", 2), name_text="Cutting")
    cluster = SubfieldCluster(parent_band_id=0, subfield_coords=((3, 3), (3, 4)))
    bundle = _bundle_with_stages(values, [band], [cluster])

    s = StageExtractor().run(bundle=bundle)["stages_per_row"][4][0]
    assert s.plan_date == dt.date(2026, 6, 1)
    assert s.stage_metadata == {"Treatment Tag": "Stone wash"}


# ─── Unknown stage name keeps canonical=None ───────────────────────────────


def test_unknown_stage_name_canonical_is_none() -> None:
    values = [
        [None, None],
        [None, "Custom Stage"],
        [None, dt.date(2026, 5, 1)],
    ]
    band = StageBand(rect=Rect(3, 2, 3, 2), name_coord=("B", 2), name_text="Custom Stage")
    bundle = _bundle_with_stages(values, [band], [])

    s = StageExtractor().run(bundle=bundle)["stages_per_row"][3][0]
    assert s.name == "Custom Stage"
    assert s.canonical is None


# ─── No plan_date AND no metadata → no stage emitted for that row ──────────


def test_empty_row_for_band_yields_no_stage() -> None:
    values = [
        [None, None, None, None],
        [None, None, "PPS", None],
        [None, None, "Plan", "Actual"],
        [None, None, dt.date(2026, 5, 1), dt.date(2026, 5, 5)],
        [None, None, None, None],   # blank row → no stage
    ]
    band = StageBand(rect=Rect(4, 3, 5, 4), name_coord=("C", 2), name_text="PPS")
    cluster = SubfieldCluster(parent_band_id=0, subfield_coords=((3, 3), (3, 4)))
    bundle = _bundle_with_stages(values, [band], [cluster])

    out = StageExtractor().run(bundle=bundle)
    assert 4 in out["stages_per_row"]
    assert 5 not in out["stages_per_row"]


# ─── Multiple stages per PLI ───────────────────────────────────────────────


def test_multiple_stages_per_pli_row() -> None:
    """Two bands → one PLI row carries two FinalStages."""
    values = [
        [None, None, None, None, None],
        [None, None, "PPS", None, "Cutting"],
        [None, None, dt.date(2026, 5, 1), None, dt.date(2026, 6, 1)],
    ]
    bands = [
        StageBand(rect=Rect(3, 3, 3, 3), name_coord=("C", 2), name_text="PPS"),
        StageBand(rect=Rect(3, 5, 3, 5), name_coord=("E", 2), name_text="Cutting"),
    ]
    bundle = _bundle_with_stages(values, bands, [])

    stages = StageExtractor().run(bundle=bundle)["stages_per_row"][3]
    assert [s.name for s in stages] == ["PPS", "Cutting"]
    assert stages[0].canonical == "pre_production_send"
    assert stages[1].canonical == "cutting"


# ─── String coercion for status / remarks subfields ────────────────────────


def test_string_subfield_values_stripped() -> None:
    values = [
        [None, None, None, None],
        [None, None, "Sewing", None],
        [None, None, "Plan", "Status"],
        [None, None, dt.date(2026, 7, 1), "  in progress  "],
    ]
    band = StageBand(rect=Rect(4, 3, 4, 4), name_coord=("C", 2), name_text="Sewing")
    cluster = SubfieldCluster(parent_band_id=0, subfield_coords=((3, 3), (3, 4)))
    bundle = _bundle_with_stages(values, [band], [cluster])

    s = StageExtractor().run(bundle=bundle)["stages_per_row"][4][0]
    assert s.stage_metadata == {"status": "in progress"}


# ─── Component plumbing ────────────────────────────────────────────────────


def test_extractor_sockets_registered() -> None:
    comp = StageExtractor()
    assert "bundle" in comp.__haystack_input__._sockets_dict
    assert "stages_per_row" in comp.__haystack_output__._sockets_dict


def test_extractor_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("stages", StageExtractor())
    assert "stages" in pipeline.graph.nodes

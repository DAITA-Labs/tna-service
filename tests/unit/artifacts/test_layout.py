"""LayoutHint + LayoutAxes contract."""
from __future__ import annotations

from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import HeaderBand, KvBlock, Rect, StageArena


def test_layout_axes_construction() -> None:
    """LayoutAxes accepts the three axis values and per-axis confidence."""
    axes = LayoutAxes(
        pli_axis="vertical",
        stage_axis="horizontal",
        subfield_axis="horizontal",
        confidence={"pli": 0.9, "stage": 0.8, "subfield": 0.7},
    )

    assert axes.pli_axis == "vertical"
    assert axes.confidence["pli"] == 0.9


def test_layout_axes_unknown_value() -> None:
    """An axis can be marked 'unknown' when signals are inconclusive."""
    axes = LayoutAxes(
        pli_axis="unknown",
        stage_axis="horizontal",
        subfield_axis="implicit",
    )
    assert axes.pli_axis == "unknown"
    # Confidence dict defaults to empty when not provided
    assert axes.confidence == {}


def test_layout_hint_default_candidates_empty() -> None:
    """A fresh LayoutHint has empty candidate dicts and empty record lists."""
    hint = LayoutHint(
        axes=LayoutAxes(
            pli_axis="vertical",
            stage_axis="horizontal",
            subfield_axis="horizontal",
        ),
        cluster_id="cluster-A",
        confidence=0.9,
    )

    assert hint.candidate_columns == {}
    assert hint.candidate_kv_blocks == {}
    assert hint.stage_arenas == []
    assert hint.header_band is None


def test_layout_hint_carries_structural_records() -> None:
    """LayoutHint can store header_band, stage_arenas, and kv_blocks."""
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis="sheet", stage_axis="horizontal", subfield_axis="vertical"),
        cluster_id="63261",
        confidence=0.95,
        header_band=HeaderBand(rect=Rect(2, 1, 2, 40), score=63.45),
        stage_arenas=[StageArena(rect=Rect(8, 3, 11, 15))],
        kv_blocks=[
            KvBlock(
                label_coord=("A", 4),
                value_coord=("B", 4),
                label_text="Job No",
                value_dtype=2,
            )
        ],
    )

    assert hint.header_band is not None
    assert hint.header_band.score == 63.45
    assert len(hint.stage_arenas) == 1
    assert hint.kv_blocks[0].label_text == "Job No"


def test_candidate_columns_dict_per_canonical() -> None:
    """candidate_columns is keyed by canonical name with a list of int cols."""
    hint = LayoutHint(
        axes=LayoutAxes(pli_axis="vertical", stage_axis="horizontal", subfield_axis="horizontal"),
        cluster_id="dkn",
        confidence=0.92,
        candidate_columns={
            "io_number": [11],
            "style_code": [6],
            "quantity": [13],
        },
    )

    assert hint.candidate_columns["io_number"] == [11]
    assert "fabric_code" not in hint.candidate_columns

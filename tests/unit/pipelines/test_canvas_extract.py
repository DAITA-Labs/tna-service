"""Tests for the canvas-architecture extraction pipeline factory."""
from __future__ import annotations

from haystack import Pipeline

from app.pipelines.canvas_extract import make_canvas_extract_pipeline


def test_factory_returns_pipeline_with_all_components() -> None:
    pipeline = make_canvas_extract_pipeline()
    assert isinstance(pipeline, Pipeline)
    expected = {
        "io_number", "quantity", "style_code", "color_code", "fabric_code",
        "style_name", "color_name", "fabric_name",
        "delivery_date", "shipment_date", "ex_fty_date",
        "combiner", "arbiter", "stages", "metadata",
    }
    assert set(pipeline.graph.nodes) == expected


def test_factory_wires_extractors_to_combiner() -> None:
    pipeline = make_canvas_extract_pipeline()
    edges = {(u, v) for (u, v, _key) in pipeline.graph.edges}
    for canonical in ("io_number", "quantity", "style_code", "color_code",
                       "fabric_code", "style_name", "color_name", "fabric_name",
                       "delivery_date", "shipment_date", "ex_fty_date"):
        assert (canonical, "combiner") in edges, f"{canonical} → combiner missing"


def test_factory_wires_combiner_through_arbiter_to_metadata() -> None:
    pipeline = make_canvas_extract_pipeline()
    edges = {(u, v) for (u, v, _key) in pipeline.graph.edges}
    assert ("combiner", "arbiter") in edges
    assert ("arbiter",  "metadata") in edges


def test_factory_is_idempotent() -> None:
    p1 = make_canvas_extract_pipeline()
    p2 = make_canvas_extract_pipeline()
    assert p1 is not p2
    assert set(p1.graph.nodes) == set(p2.graph.nodes)

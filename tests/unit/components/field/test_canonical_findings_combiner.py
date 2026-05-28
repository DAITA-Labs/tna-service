"""CanonicalFindingsCombiner — concat the 11 extractor outputs into one bag."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.field.canonical_findings_combiner import (
    CanonicalFindingsCombiner,
)


def _f(canonical: str, col: str = "A", row: int = 3) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(col, 2),
        value_coord=(col, row), value="v",
        confidence=Confidence.HIGH, evidence=[],
    )


def _empty_inputs(**overrides):
    base = {
        "io_number_findings":     [],
        "quantity_findings":      [],
        "style_code_findings":    [],
        "color_code_findings":    [],
        "fabric_code_findings":   [],
        "style_name_findings":    [],
        "color_name_findings":    [],
        "fabric_name_findings":   [],
        "delivery_date_findings": [],
        "shipment_date_findings": [],
        "ex_fty_date_findings":   [],
    }
    base.update(overrides)
    return base


def test_all_empty_yields_empty_list() -> None:
    out = CanonicalFindingsCombiner().run(**_empty_inputs())
    assert out["findings"] == []


def test_concatenation_preserves_socket_order() -> None:
    """Output order follows the declaration order in the run signature."""
    out = CanonicalFindingsCombiner().run(**_empty_inputs(
        io_number_findings=[_f("io_number")],
        ex_fty_date_findings=[_f("ex_fty_date")],
        quantity_findings=[_f("quantity")],
    ))
    canonicals = [f.canonical for f in out["findings"]]
    # io_number is declared before quantity, which is before ex_fty_date.
    assert canonicals == ["io_number", "quantity", "ex_fty_date"]


def test_multiple_findings_per_canonical_all_pass_through() -> None:
    out = CanonicalFindingsCombiner().run(**_empty_inputs(
        io_number_findings=[_f("io_number", "A", 3), _f("io_number", "A", 4)],
    ))
    assert len(out["findings"]) == 2


def test_combiner_sockets_registered() -> None:
    comp = CanonicalFindingsCombiner()
    inputs = comp.__haystack_input__._sockets_dict
    for canonical in ("io_number", "quantity", "style_code", "color_code",
                       "fabric_code", "style_name", "color_name", "fabric_name",
                       "delivery_date", "shipment_date", "ex_fty_date"):
        assert f"{canonical}_findings" in inputs


def test_combiner_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("combiner", CanonicalFindingsCombiner())
    assert "combiner" in pipeline.graph.nodes

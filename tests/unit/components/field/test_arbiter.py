"""IdentifierArbiter — cross-canonical conflict resolution."""
from __future__ import annotations

from haystack import Pipeline

from app.artifacts.finding import Confidence, Finding
from app.components.field.arbiter import IdentifierArbiter


def _f(canonical: str, coord: tuple[str, int], confidence: Confidence) -> Finding:
    return Finding(
        canonical=canonical, label_coord=(coord[0], 2), value_coord=coord,
        value="x", confidence=confidence, evidence=["HEADER_BAND_MEMBER"],
    )


def test_empty_input_yields_empty_output() -> None:
    assert IdentifierArbiter().run(findings=[])["findings"] == []


def test_single_finding_passes_through() -> None:
    f = _f("io_number", ("A", 3), Confidence.MEDIUM)
    out = IdentifierArbiter().run(findings=[f])
    assert out["findings"] == [f]


def test_findings_at_different_coords_all_kept() -> None:
    a = _f("io_number", ("A", 3), Confidence.MEDIUM)
    b = _f("io_number", ("A", 4), Confidence.MEDIUM)
    c = _f("style_code", ("B", 3), Confidence.MEDIUM)
    out = IdentifierArbiter().run(findings=[a, b, c])
    assert sorted(out["findings"], key=lambda f: f.value_coord) == [a, b, c]


def test_same_coord_higher_confidence_wins() -> None:
    """Two findings on the same cell — the HIGH-confidence one wins."""
    high = _f("io_number", ("A", 3), Confidence.HIGH)
    medium = _f("style_code", ("A", 3), Confidence.MEDIUM)
    out = IdentifierArbiter().run(findings=[medium, high])
    assert out["findings"] == [high]


def test_same_coord_same_confidence_code_beats_name() -> None:
    """Tied confidence → *_code wins over *_name (spec catalog priority)."""
    style_code = _f("style_code", ("A", 3), Confidence.MEDIUM)
    style_name = _f("style_name", ("A", 3), Confidence.MEDIUM)
    out = IdentifierArbiter().run(findings=[style_name, style_code])
    assert out["findings"] == [style_code]


def test_same_coord_both_code_picks_alphabetically_earlier_canonical() -> None:
    """Two *_code findings at same confidence → alphabetically-earlier canonical wins (stable)."""
    color = _f("color_code", ("A", 3), Confidence.MEDIUM)
    style = _f("style_code", ("A", 3), Confidence.MEDIUM)
    out = IdentifierArbiter().run(findings=[style, color])
    assert out["findings"] == [color]   # 'color_code' < 'style_code'


def test_low_confidence_loses_to_high_even_for_code_vs_name() -> None:
    """Confidence ordering supersedes code-vs-name priority."""
    name_high = _f("style_name", ("A", 3), Confidence.HIGH)
    code_low = _f("style_code", ("A", 3), Confidence.LOW)
    out = IdentifierArbiter().run(findings=[code_low, name_high])
    assert out["findings"] == [name_high]


def test_output_sorted_by_coord_then_canonical() -> None:
    """Output is stably sorted so reruns produce identical lists."""
    findings = [
        _f("io_number",  ("A", 5), Confidence.MEDIUM),
        _f("style_code", ("B", 3), Confidence.MEDIUM),
        _f("io_number",  ("A", 3), Confidence.MEDIUM),
    ]
    out = IdentifierArbiter().run(findings=findings)
    coords = [f.value_coord for f in out["findings"]]
    assert coords == [("A", 3), ("A", 5), ("B", 3)]


def test_component_sockets_registered() -> None:
    comp = IdentifierArbiter()
    assert "findings" in comp.__haystack_input__._sockets_dict
    assert "findings" in comp.__haystack_output__._sockets_dict


def test_addable_to_pipeline() -> None:
    pipeline = Pipeline()
    pipeline.add_component("arbiter", IdentifierArbiter())
    assert "arbiter" in pipeline.graph.nodes

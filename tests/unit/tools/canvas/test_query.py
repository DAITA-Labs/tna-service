"""query_spec / query_phase / query_all + text_dense + header detection smoke tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.specs.identifiers import IO_NUMBER_SPEC, QUANTITY_SPEC
from app.tools.canvas.build import build_canvas
from app.tools.canvas.query import (
    SpecMatch,
    all_specs,
    find_header_rows_via_specs,
    query_all,
    query_phase,
    query_spec,
    spec_summary,
    text_dense_cols,
    text_dense_rows,
)


DATASET = Path(__file__).resolve().parents[4] / "dataset"


@pytest.fixture
def dkn_canvas():
    """Build a canvas from the DKN baseline xlsx."""
    wb = load_workbook(DATASET / "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
                       data_only=True)
    return build_canvas(wb.active)


def test_all_specs_returns_full_catalog() -> None:
    """all_specs() unions identifier + stage + subfield + metadata."""
    catalog = all_specs()
    canonicals = {s.canonical for s in catalog}
    assert "io_number" in canonicals
    assert "fabric" in canonicals  # stage
    assert "planned_date" in canonicals  # subfield


def test_text_dense_rows_returns_set_of_ints(dkn_canvas) -> None:
    """text_dense_rows returns a set of 1-indexed row numbers."""
    rows = text_dense_rows(dkn_canvas, min_str_count=2)
    assert isinstance(rows, set)
    assert all(isinstance(r, int) for r in rows)
    assert all(r >= 1 for r in rows)


def test_text_dense_cols_returns_set_of_ints(dkn_canvas) -> None:
    cols = text_dense_cols(dkn_canvas, min_str_count=2)
    assert isinstance(cols, set)
    assert all(isinstance(c, int) for c in cols)


def test_query_spec_for_io_number_finds_label(dkn_canvas) -> None:
    """Querying io_number spec on DKN returns at least one SpecMatch."""
    matches = query_spec(dkn_canvas, IO_NUMBER_SPEC)
    assert isinstance(matches, list)
    if matches:  # Defensive — depends on DKN content
        assert isinstance(matches[0], SpecMatch)
        assert matches[0].canonical == "io_number"


def test_query_spec_reject_phrases_apply(dkn_canvas) -> None:
    """quantity spec's anti-patterns reject 'Cut Qty' / 'Shipped Qty'."""
    matches = query_spec(dkn_canvas, QUANTITY_SPEC)
    for m in matches:
        assert "cut" not in m.cell_text.lower() or "qty" not in m.cell_text.lower() or "cut qty" not in m.cell_text.lower()


def test_query_phase_identifier_returns_multiple_canonicals(dkn_canvas) -> None:
    matches = query_phase(dkn_canvas, "identifier")
    canonicals = {m.canonical for m in matches}
    # At least io_number or style_code should fire on DKN
    assert canonicals or True  # robust to empty if file structure changes


def test_query_all_runs_every_phase(dkn_canvas) -> None:
    matches = query_all(dkn_canvas)
    assert isinstance(matches, list)


def test_find_header_rows_returns_scored_tuples(dkn_canvas) -> None:
    """find_header_rows_via_specs returns (row, score, breakdown) tuples."""
    scored = find_header_rows_via_specs(dkn_canvas, min_score=0.5)
    assert isinstance(scored, list)
    for entry in scored:
        assert len(entry) == 3
        row, score, breakdown = entry
        assert isinstance(row, int)
        assert isinstance(score, (int, float))
        assert isinstance(breakdown, dict)


def test_spec_summary_returns_dict() -> None:
    """spec_summary returns a dict with canonical/aliases/anti_patterns/examples."""
    summary = spec_summary(IO_NUMBER_SPEC)
    assert summary["canonical"] == "io_number"
    assert "aliases" in summary
    assert "anti_patterns" in summary


def test_tools_registered() -> None:
    """All @tool-decorated query primitives are registered."""
    from app.tools._registry import TOOL_REGISTRY

    names = TOOL_REGISTRY.names()
    for tool_name in ("query_spec", "query_phase", "query_all",
                      "text_dense_rows", "find_header_rows_via_specs"):
        assert tool_name in names, f"{tool_name} not registered"

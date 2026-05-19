"""Round-trip fidelity: every scorer produces the same EvalRow before and after
model_dump_json → model_validate_json.

This test catches the class of bug where ``dict[str, Any]`` metadata fields
lose their ``datetime`` type during JSON serialisation — the reloaded value
becomes an ISO-string, and a naive ``str()`` comparison breaks.

The workbook is a minimal openpyxl in-memory file whose cells match the
addresses recorded in ``source.cells``, so ``source_cell_match`` and
``header_match`` are exercised in addition to the label-based scorers.
"""
from __future__ import annotations
import json
from datetime import date, datetime
from pathlib import Path

import openpyxl
import pytest

from app.models.extraction import ExtractionResult, PLI, Source, Stage
from app.models.workbook import WorkbookCtx
from evals.runner import EvalRow, _score_one


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABEL_STEM = "roundtrip_test"
_SHEET = "Orders"


def _build_extraction() -> ExtractionResult:
    """Build a representative ExtractionResult exercising all fragile type paths.

    Includes:
      - ``PLI.delivery_date`` (FlexibleDate → ``date``)
      - ``PLI.metadata`` with a ``datetime`` value (→ ISO string after round-trip)
      - ``PLI.metadata`` with a ``date`` value     (→ ISO string after round-trip)
      - ``Stage.planned_date`` (FlexibleDate → ``date``)
      - ``Stage.metadata`` with a ``datetime`` value
      - ``source.cells`` entries for all of the above
    """
    return ExtractionResult(
        plis=[
            PLI(
                io_number="IO-001",
                style_code="STYLE-A",
                color_code="RED",
                delivery_date=date(2026, 5, 15),
                quantity=42,
                metadata={
                    "ship_date": datetime(2026, 3, 10, 0, 0, 0),
                    "order_date": date(2026, 1, 15),
                    "buyer_ref": "BR-999",
                },
                source=Source(
                    sheet=_SHEET,
                    rows=[4],
                    cells={
                        "io_number": "A4",
                        "style_code": "B4",
                        "delivery_date": "C4",
                        "quantity": "D4",
                        "ship_date": "E4",
                        "order_date": "F4",
                    },
                ),
                stages=[
                    Stage(
                        name="Sewing",
                        planned_date=date(2026, 4, 1),
                        metadata={
                            "milestone_date": datetime(2026, 4, 15, 0, 0, 0),
                        },
                    ),
                    Stage(name="Inspection"),
                ],
            ),
        ],
    )


def _make_workbook(tmp_path: Path) -> WorkbookCtx:
    """Build a minimal openpyxl workbook whose data row matches ``source.cells``.

    Row 1 contains header text so ``header_match`` can exercise vocabulary
    lookups.  Row 4 contains the actual values from the extraction result.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _SHEET

    # Header row — vocabulary terms for header_match
    ws["A1"] = "IO Number"
    ws["B1"] = "Style"
    ws["C1"] = "Delivery"
    ws["D1"] = "Quantity"
    ws["E1"] = "Ship Date"
    ws["F1"] = "Order Date"

    # Data row matching the extraction values
    ws["A4"] = "IO-001"
    ws["B4"] = "STYLE-A"
    ws["C4"] = datetime(2026, 5, 15, 0, 0, 0)   # openpyxl stores dates as datetime
    ws["D4"] = 42
    ws["E4"] = datetime(2026, 3, 10, 0, 0, 0)
    ws["F4"] = datetime(2026, 1, 15, 0, 0, 0)

    wb_path = tmp_path / f"{_LABEL_STEM}.xlsx"
    wb.save(wb_path)
    # Reload from disk so openpyxl populates cell types the same way as real files
    wb2 = openpyxl.load_workbook(wb_path, data_only=True)
    return WorkbookCtx(wb_path, wb2)


def _make_label(tmp_path: Path) -> Path:
    """Write a minimal label JSON that allows PLI-matching against the extraction."""
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    label_path = labels_dir / f"{_LABEL_STEM}.json"
    label_data = {
        "plis": [
            {
                "io_number": "IO-001",
                "style_code": "STYLE-A",
                "color_code": "RED",
                "delivery_date": "2026-05-15",
                "quantity": 42,
                "stages": [{"name": "Sewing"}, {"name": "Inspection"}],
            }
        ]
    }
    label_path.write_text(json.dumps(label_data), encoding="utf-8")
    return label_path


# ---------------------------------------------------------------------------
# Round-trip fidelity test
# ---------------------------------------------------------------------------

def test_round_trip_produces_identical_eval_row(tmp_path: Path) -> None:
    """Scoring before vs after JSON round-trip must give exactly the same EvalRow.

    Regression: ``source_cell_match`` used ``str()`` equality, which broke when
    ``dict[str, Any]`` metadata ``datetime`` values were serialised to ISO-8601
    strings with a T separator while openpyxl returns them with a space separator.
    """
    live = _build_extraction()
    ctx = _make_workbook(tmp_path)
    label_path = _make_label(tmp_path)

    # Score the live (pre-round-trip) result
    live_row: EvalRow = _score_one(
        label_path=label_path,
        actual=live,
        ctx=ctx,
        duration_seconds=1.0,
    )

    # Round-trip through JSON (simulates --replay loading a frozen output file)
    reloaded = ExtractionResult.model_validate_json(live.model_dump_json(indent=2))

    replay_row: EvalRow = _score_one(
        label_path=label_path,
        actual=reloaded,
        ctx=ctx,
        duration_seconds=0.0,  # replay duration differs but scores must match
    )

    # Every metric score must be identical — only duration_seconds may differ
    assert live_row.pli_recall == replay_row.pli_recall, (
        f"pli_recall diverged: live={live_row.pli_recall}, replay={replay_row.pli_recall}"
    )
    assert live_row.field_precision == replay_row.field_precision, (
        f"field_precision diverged: live={live_row.field_precision}, replay={replay_row.field_precision}"
    )
    assert live_row.field_recall == replay_row.field_recall, (
        f"field_recall diverged: live={live_row.field_recall}, replay={replay_row.field_recall}"
    )
    assert live_row.stage_recall == replay_row.stage_recall, (
        f"stage_recall diverged: live={live_row.stage_recall}, replay={replay_row.stage_recall}"
    )
    assert live_row.source_cell_match == replay_row.source_cell_match, (
        f"source_cell_match diverged: live={live_row.source_cell_match}, "
        f"replay={replay_row.source_cell_match}"
    )
    assert live_row.header_match == replay_row.header_match, (
        f"header_match diverged: live={live_row.header_match}, replay={replay_row.header_match}"
    )
    # Sanity: scores are non-trivially correct (not all-zero from a broken workbook)
    assert live_row.pli_recall == 1.0
    assert live_row.stage_recall == 1.0
    assert live_row.source_cell_match > 0.0


def test_values_equal_normalises_date_representations() -> None:
    """values_equal treats datetime / date / ISO-string as equivalent."""
    from evals.scorers._compare import values_equal

    dt = datetime(2026, 5, 15, 0, 0, 0)
    d = date(2026, 5, 15)
    iso_t = "2026-05-15T00:00:00"
    iso_space = "2026-05-15 00:00:00"
    iso_date = "2026-05-15"

    # All representations of the same calendar date must be equal to each other
    for a, b in [
        (dt, d), (dt, iso_t), (dt, iso_space), (dt, iso_date),
        (d, iso_t), (d, iso_space), (d, iso_date),
        (iso_t, iso_space), (iso_t, iso_date),
    ]:
        assert values_equal(a, b), f"Expected values_equal({a!r}, {b!r}) to be True"
        assert values_equal(b, a), f"Expected values_equal({b!r}, {a!r}) to be True (symmetry)"

    # Different dates must not be equal
    assert not values_equal(date(2026, 5, 15), date(2026, 5, 16))
    assert not values_equal(datetime(2026, 5, 15, 0, 0, 0), date(2026, 5, 16))
    assert not values_equal("2026-05-15", "2026-05-16")

    # None comparisons
    assert values_equal(None, None)
    assert not values_equal(None, date(2026, 5, 15))
    assert not values_equal(date(2026, 5, 15), None)

    # Non-date values fall back to plain equality
    assert values_equal("hello", "hello")
    assert values_equal("  hello  ", "hello")   # strips whitespace
    assert not values_equal("hello", "world")
    assert values_equal(42, 42)
    assert not values_equal(42, 43)

"""CanvasApplier — walk a CanvasPlan + GridCanvas → list[PLI].

Deterministic. Reads each `FieldLocation` to pull the source cell value,
materialises stages from `StageBandPlan`s, attaches per-PLI metadata
from `MetadataPlan` entries, and stamps every value with its A1 origin
on `PLI.source.cells`. Per-field confidence on `PLI.confidence` carries
the picker score; SHEET-scoped (KV_BLOCK / WHOLE_SHEET) values are
broadcast across every PLI in the cluster.

Scope (today): `PliAxis.ROW` and `PliAxis.WHOLE_SHEET`. The COLUMN and
SECTION axes are wired when the planner begins emitting them.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string, get_column_letter

from app.artifacts.canvas import GridCanvas
from app.artifacts.plan import (
    CanvasPlan,
    FieldLocation,
    MetadataPlan,
    StageBandPlan,
)
from app.components._base import Component
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.models.extraction import PLI, Source, Stage


# Canonicals that map onto a flat PLI attribute (mirror of CanvasReconciler).
_CANONICAL_TO_PLI_FIELD: dict[str, str] = {
    "io_number":     "io_number",
    "style_code":    "style_code",
    "style_name":    "style_name",
    "color_code":    "color_code",
    "color_name":    "color_name",
    "fabric_code":   "fabric_code",
    "quantity":      "quantity",
    "delivery_date": "delivery_date",
}


@component
class CanvasApplier(Component):
    """Walk a CanvasPlan + canvas → list[PLI] (one cluster's worth)."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(plis=list[PLI])
    def run(
        self,
        plan:    CanvasPlan,
        canvas:  GridCanvas,
        sheet:   str | None = None,
    ) -> dict:
        sheet_name = sheet or plan.anchor_sheet_name
        if plan.pli_axis == PliAxis.ROW:
            plis = [
                _build_pli_for_row(row, plan, canvas, sheet_name)
                for row in plan.pli_rows
            ]
        elif plan.pli_axis == PliAxis.WHOLE_SHEET:
            plis = [_build_whole_sheet_pli(plan, canvas, sheet_name)]
        else:
            # COLUMN and SECTION wait on the planner emitting them.
            plis = []
        return {"plis": plis}


# ── row-per-PLI ────────────────────────────────────────────────────────────


def _build_pli_for_row(
    row:     int,
    plan:    CanvasPlan,
    canvas:  GridCanvas,
    sheet:   str,
) -> PLI:
    flat:          dict[str, Any]   = {}
    confidence:    dict[str, float] = {}
    source_cells:  dict[str, str]   = {}
    metadata:      dict[str, Any]   = {}

    for canonical, fl in plan.field_locations.items():
        value, coord = _read_field_location(fl, row, canvas)
        if value is None:
            continue
        _stash_canonical_value(
            canonical, value, coord, fl.score,
            flat=flat, metadata=metadata,
            confidence=confidence, source_cells=source_cells,
        )

    for entry in plan.metadata_entries:
        value, coord = _read_metadata_entry(entry, row, canvas)
        if value is None:
            continue
        key = entry.canonical or entry.header_text
        metadata[key] = value
        if coord is not None:
            source_cells[key] = coord

    stages = [
        _build_stage(band, row, canvas, sheet)
        for band in plan.stage_bands
    ]

    return PLI(
        **flat,
        stages=stages,
        confidence=confidence,
        metadata=metadata,
        source=Source(sheet=sheet, rows=[row], cells=source_cells),
    )


# ── whole-sheet-is-PLI ─────────────────────────────────────────────────────


def _build_whole_sheet_pli(
    plan:    CanvasPlan,
    canvas:  GridCanvas,
    sheet:   str,
) -> PLI:
    flat:          dict[str, Any]   = {}
    confidence:    dict[str, float] = {}
    source_cells:  dict[str, str]   = {}
    metadata:      dict[str, Any]   = {}

    for canonical, fl in plan.field_locations.items():
        value, coord = _read_field_location(fl, row=None, canvas=canvas)
        if value is None:
            continue
        _stash_canonical_value(
            canonical, value, coord, fl.score,
            flat=flat, metadata=metadata,
            confidence=confidence, source_cells=source_cells,
        )

    for entry in plan.metadata_entries:
        value, coord = _read_metadata_entry(entry, row=None, canvas=canvas)
        if value is None:
            continue
        key = entry.canonical or entry.header_text
        metadata[key] = value
        if coord is not None:
            source_cells[key] = coord

    return PLI(
        **flat,
        stages=[],
        confidence=confidence,
        metadata=metadata,
        source=Source(sheet=sheet, rows=[], cells=source_cells),
    )


# ── reading helpers ────────────────────────────────────────────────────────


def _read_field_location(
    fl:     FieldLocation,
    row:    int | None,
    canvas: GridCanvas,
) -> tuple[Any, str | None]:
    """Pull (value, A1) for one FieldLocation; (None, None) when unreadable."""
    if fl.mode == FieldLocationMode.MISSING:
        return None, None
    if fl.mode == FieldLocationMode.KV_BLOCK and fl.kv_block is not None:
        col_letter, r = fl.kv_block.value_coord
        return _read_cell(canvas, r, column_index_from_string(col_letter))
    if fl.mode == FieldLocationMode.COLUMN and fl.column is not None and row is not None:
        return _read_cell(canvas, row, fl.column)
    if fl.mode == FieldLocationMode.ROW and fl.row is not None:
        # ROW-mode lookup is column-per-PLI territory — not in scope yet.
        return None, None
    return None, None


def _read_metadata_entry(
    entry:  MetadataPlan,
    row:    int | None,
    canvas: GridCanvas,
) -> tuple[Any, str | None]:
    """Pull (value, A1) for one MetadataPlan; (None, None) when unreadable."""
    if entry.mode == FieldLocationMode.KV_BLOCK and entry.kv_block is not None:
        col_letter, r = entry.kv_block.value_coord
        return _read_cell(canvas, r, column_index_from_string(col_letter))
    if entry.mode == FieldLocationMode.COLUMN and entry.column is not None and row is not None:
        return _read_cell(canvas, row, entry.column)
    return None, None


def _read_cell(canvas: GridCanvas, row_1: int, col_1: int) -> tuple[Any, str | None]:
    """Read (value, A1) at 1-indexed (row, col); (None, None) if out of bounds or blank."""
    r0 = row_1 - 1
    c0 = col_1 - 1
    if r0 < 0 or r0 >= canvas.n_rows or c0 < 0 or c0 >= canvas.n_cols:
        return None, None
    value = canvas.cell_values[r0][c0]
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    return value, f"{get_column_letter(col_1)}{row_1}"


# ── PLI/metadata stashing ──────────────────────────────────────────────────


def _stash_canonical_value(
    canonical:    str,
    value:        Any,
    coord:        str | None,
    score:        float,
    *,
    flat:         dict[str, Any],
    metadata:     dict[str, Any],
    confidence:   dict[str, float],
    source_cells: dict[str, str],
) -> None:
    """Route a canonical value to its PLI attribute or into metadata."""
    pli_field = _CANONICAL_TO_PLI_FIELD.get(canonical)
    if pli_field is None:
        # Off-PLI identifiers (shipment_date, ex_fty_date, fabric_name, etc.)
        # ride along as metadata so the value isn't silently dropped.
        metadata[canonical] = value
        if coord is not None:
            source_cells[canonical] = coord
        return
    flat[pli_field]       = value
    confidence[pli_field] = score
    if coord is not None:
        source_cells[pli_field] = coord


# ── stage assembly ─────────────────────────────────────────────────────────


def _build_stage(
    band:   StageBandPlan,
    row:    int,
    canvas: GridCanvas,
    sheet:  str,
) -> Stage:
    """Build one Stage from a StageBandPlan at the given PLI row."""
    planned_col = band.subfield_indices.get("planned_date", band.anchor_coord[1])
    value, coord = _read_cell(canvas, row, planned_col)
    source_cells = {"planned_date": coord} if coord is not None else {}

    stage_metadata: dict[str, Any] = {}
    for subfield, col in band.subfield_indices.items():
        if subfield == "planned_date":
            continue
        sub_value, sub_coord = _read_cell(canvas, row, col)
        if sub_value is None:
            continue
        stage_metadata[subfield] = sub_value
        if sub_coord is not None:
            source_cells[subfield] = sub_coord

    return Stage(
        name=band.name,
        planned_date=value,
        metadata=stage_metadata,
        confidence=band.score if band.score else 1.0,
        source=Source(
            sheet=sheet,
            rows=[row] if band.scope == FieldScope.PLI else [],
            cells=source_cells,
        ),
    )

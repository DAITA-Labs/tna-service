"""Deterministic field applier — turns FieldMap + boundaries into PLIs.

Responsibilities:
- iterate PLI rows via the pattern registry
- read each canonical field's value (with merge propagation for vertical_merge)
- record source_cells per PLI (A1 address for every field read)
- skip repeat-header rows mid-data (NORTHERN REFLECTIONS pattern)
- defensive: is_real_pli filter — drop rows with no canonical identity
- tolerant Pydantic construction — drop fields that fail validation
"""
from __future__ import annotations
import logging
from typing import Any
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.utils.cell import coordinate_from_string
from pydantic import ValidationError
from app.models.extraction import PLI
from app.models.workbook import WorkbookCtx
from app.models.artifacts import (
    FieldMap, FieldLocation, PLIMetadataLocation, PLIBoundaries,
)
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.location_pattern import LocationPattern
from app.services.applier._registry import get_pattern_handler

log = logging.getLogger(__name__)

_PLI_IDENTITY_FIELDS = ("io_number", "style_code", "color_code", "fabric_code")


def is_real_pli(pli: PLI) -> bool:
    """True if at least one identity field is populated."""
    return any(getattr(pli, f, None) for f in _PLI_IDENTITY_FIELDS)


def _coerce_for_field(field: str, val: Any) -> Any:
    string_fields = {"io_number", "style_code", "style_name",
                     "color_code", "color_name", "fabric_code"}
    if field in string_fields and val is not None:
        return str(val)
    return val


def _read_field_value(
    ctx: WorkbookCtx, sheet: str,
    loc: FieldLocation | PLIMetadataLocation,
    pli_row: int, propagate_merges: bool = False,
) -> tuple[Any, str | None]:
    """Return (value, source_address). source_address is None if no read."""
    ws = ctx.wb[sheet]
    if loc.pattern == LocationPattern.COLUMN:
        if not loc.column:
            return None, None
        col_idx = column_index_from_string(loc.column)
        if propagate_merges:
            for mr in ws.merged_cells.ranges:
                if (mr.min_row <= pli_row <= mr.max_row
                        and mr.min_col <= col_idx <= mr.max_col):
                    addr = f"{get_column_letter(mr.min_col)}{mr.min_row}"
                    return ws.cell(row=mr.min_row, column=mr.min_col).value, addr
        return ws.cell(row=pli_row, column=col_idx).value, f"{loc.column}{pli_row}"

    if loc.pattern == LocationPattern.ANCHOR:
        if not loc.anchor_cell or loc.value_offset_rc is None:
            return None, None
        anc_col_letter, anc_row = coordinate_from_string(loc.anchor_cell)
        anc_col = column_index_from_string(anc_col_letter)
        dy, dx = loc.value_offset_rc
        r, c = anc_row + dy, anc_col + dx
        return ws.cell(row=r, column=c).value, f"{get_column_letter(c)}{r}"

    if loc.pattern == LocationPattern.MERGED_PROPAGATING:
        if not loc.column:
            return None, None
        col_idx = column_index_from_string(loc.column)
        for mr in ws.merged_cells.ranges:
            if (mr.min_row <= pli_row <= mr.max_row
                    and mr.min_col <= col_idx <= mr.max_col):
                addr = f"{get_column_letter(mr.min_col)}{mr.min_row}"
                return ws.cell(row=mr.min_row, column=mr.min_col).value, addr
        return ws.cell(row=pli_row, column=col_idx).value, f"{loc.column}{pli_row}"

    return None, None


def _header_values_above_data(
    ctx: WorkbookCtx, sheet: str, field_map: FieldMap, data_start_row: int,
) -> dict[str, set[str]]:
    """Collect header values (rows 1..start-1) per canonical-field column.
    Used to detect repeat-header rows mid-data (NORTHERN REFLECTIONS pattern)."""
    ws = ctx.wb[sheet]
    out: dict[str, set[str]] = {}
    for loc in field_map.locations:
        if loc.pattern != LocationPattern.COLUMN or not loc.column:
            continue
        col_idx = column_index_from_string(loc.column)
        seen: set[str] = set()
        for r in range(1, data_start_row):
            v = ws.cell(row=r, column=col_idx).value
            if isinstance(v, str) and v.strip():
                seen.add(v.strip())
        if seen:
            out[loc.field] = seen
    return out


def _build_pli_tolerantly(values: dict) -> PLI:
    """Construct PLI; drop any field that fails validation."""
    attempt = dict(values)
    for _ in range(len(attempt) + 1):
        try:
            return PLI(**attempt)
        except ValidationError as e:
            dropped = [
                err["loc"][0] for err in e.errors()
                if err["loc"] and isinstance(err["loc"][0], str) and err["loc"][0] in attempt
            ]
            if not dropped:
                raise
            for k in dropped:
                log.warning("PLI dropped field %r: %s", k, e.errors()[0].get("msg", ""))
                attempt.pop(k, None)
    return PLI(source_sheet=values.get("source_sheet"))


def apply_field_map(
    ctx: WorkbookCtx, sheet: str,
    field_map: FieldMap, boundaries: PLIBoundaries,
) -> list[PLI]:
    """Iterate PLI rows; emit one PLI per row (subject to identity filter)."""
    plis: list[PLI] = []

    if boundaries.pattern == BoundaryPattern.ONE_SHEET_PER_PLI:
        for s in boundaries.sheet_iter:
            values: dict = {"source_sheet": s}
            metadata: dict = {}
            source_cells: dict = {}
            for loc in field_map.locations:
                pli_row = 1
                if loc.anchor_cell:
                    _, pli_row = coordinate_from_string(loc.anchor_cell)
                val, addr = _read_field_value(ctx, s, loc, pli_row=pli_row)
                if val is not None:
                    values[loc.field] = _coerce_for_field(loc.field, val)
                    if addr:
                        source_cells[loc.field] = addr
            for mloc in field_map.metadata_locations:
                pli_row = 1
                if mloc.anchor_cell:
                    _, pli_row = coordinate_from_string(mloc.anchor_cell)
                val, addr = _read_field_value(ctx, s, mloc, pli_row=pli_row)
                if val is not None:
                    metadata[mloc.key] = val
                    if addr:
                        source_cells[mloc.key] = addr
            values["metadata"] = metadata
            values["source_cells"] = source_cells
            plis.append(_build_pli_tolerantly(values))
        return plis

    handler = get_pattern_handler(boundaries.pattern.value if hasattr(boundaries.pattern, "value") else boundaries.pattern)
    pli_rows = handler(ctx, boundaries)
    propagate = boundaries.pattern == BoundaryPattern.VERTICAL_MERGE
    headers_by_field = _header_values_above_data(
        ctx, sheet, field_map, boundaries.data_start_row or 1,
    )

    for r in pli_rows:
        values: dict = {"source_sheet": sheet, "source_rows": [r]}
        metadata: dict = {}
        source_cells: dict = {}
        for loc in field_map.locations:
            val, addr = _read_field_value(ctx, sheet, loc, r, propagate_merges=propagate)
            if val is not None:
                values[loc.field] = _coerce_for_field(loc.field, val)
                if addr:
                    source_cells[loc.field] = addr
        for mloc in field_map.metadata_locations:
            val, addr = _read_field_value(ctx, sheet, mloc, r, propagate_merges=propagate)
            if val is not None:
                metadata[mloc.key] = val
                if addr:
                    source_cells[mloc.key] = addr

        # Strip identity on repeat-header rows.
        repeat_matches = [
            f for f, headers in headers_by_field.items()
            if isinstance(values.get(f), str) and values[f].strip() in headers
        ]
        if repeat_matches:
            for f in _PLI_IDENTITY_FIELDS:
                values.pop(f, None)

        values["metadata"] = metadata
        values["source_cells"] = source_cells
        plis.append(_build_pli_tolerantly(values))

    return plis

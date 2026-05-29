"""CanvasReconciler — assemble ExtractionResult from canvas-architecture outputs.

The legacy `Reconciler` consumes the legacy planner's `workflow_out`
plus per-verifier `ValidationFindings`. The canvas path produces a
different shape: `list[Finding]` (per-canonical findings),
`dict[int, list[FinalStage]]` (per-PLI stages), and `list[MetadataEntry]`
(SHEET / GROUP / PLI-scoped metadata). This component bridges that
shape to the public `ExtractionResult` schema.

Mapping rules:

  1. Group `findings` by PLI row (the finding's `value_coord[1]`).
  2. For each PLI row, build one `PLI`:
       - Identifier canonicals (io_number, style_code, etc.) → flat
         attributes on `PLI`. When multiple findings exist for the
         same canonical (rare; the arbiter should have deduplicated),
         the highest-confidence one wins.
       - Stages from `stages_per_row[row]` → `PLI.stages` (mapped from
         `FinalStage` to the `models.extraction.Stage` shape).
       - PLI-scoped metadata entries (`scope=PLI` matching this row) →
         `PLI.metadata` dict.
       - Per-field confidence from each finding's `Confidence` enum
         → `PLI.confidence` dict, mapped to 0.0/0.5/1.0.
       - `source.cells` populated from each finding's `value_coord`.
  3. SHEET-scoped metadata entries → top-level
     `ExtractionResult.detected_format` style metadata (currently
     attached as a JSON-compatible map on every PLI for parity with
     the legacy reconciler's behaviour).
  4. ValidationWarnings → `ExtractionResult.warnings` after mapping
     to the public `Warning` model.

PLI ordering: rows are returned in ascending order. Cluster identity
is not preserved at this layer — multi-cluster workbooks merge into
one PLI list. The service is responsible for calling this once per
cluster and merging if cluster boundaries need to be retained.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from haystack import component
from openpyxl.utils import get_column_letter

from app.artifacts.finding import Confidence, Finding, ValidationWarning
from app.components._base import Component
from app.models.extraction import ExtractionResult, PLI, Source, Stage, Warning
from app.specs.enums import FieldScope
from app.specs.schemas import FinalStage, MetadataEntry


# Canonical → PLI attribute (most are 1:1).
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

# Canonicals that DO produce findings but don't have a flat PLI field —
# they're stage-related dates and live in stage_metadata instead.
_NON_PLI_FINDING_CANONICALS: frozenset[str] = frozenset({
    "shipment_date", "ex_fty_date", "fabric_name",
})

_CONFIDENCE_TO_FLOAT: dict[Confidence, float] = {
    Confidence.HIGH:   1.0,
    Confidence.MEDIUM: 0.5,
    Confidence.LOW:    0.2,
}


@component
class CanvasReconciler(Component):
    """Assemble ExtractionResult from canvas-architecture extractor outputs."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(result=ExtractionResult)
    def run(
        self,
        findings:        list[Finding],
        stages_per_row:  dict[int, list[FinalStage]],
        metadata:        list[MetadataEntry],
        warnings:        list[ValidationWarning],
        source_file:     str,
        sheet:           str | None = None,
    ) -> dict:
        per_row_findings = _group_findings_by_row(findings)
        per_row_metadata = _group_metadata_by_row(metadata)
        sheet_metadata   = _sheet_scoped_metadata(metadata)

        pli_rows = sorted(
            set(per_row_findings) | set(stages_per_row) | set(per_row_metadata)
        )
        plis: list[PLI] = [
            _build_pli(
                row=row,
                findings=per_row_findings.get(row, []),
                stages=stages_per_row.get(row, []),
                pli_metadata=per_row_metadata.get(row, []),
                sheet_metadata=sheet_metadata,
                sheet=sheet,
            )
            for row in pli_rows
        ]

        result = ExtractionResult(
            plis=plis,
            warnings=[_warning_to_public(w) for w in warnings],
            source_file=source_file,
        )
        return {"result": result}


# ── private helpers ────────────────────────────────────────────────────


def _group_findings_by_row(findings: list[Finding]) -> dict[int, list[Finding]]:
    """Bucket findings by the row index in their `value_coord`."""
    by_row: dict[int, list[Finding]] = defaultdict(list)
    for f in findings:
        by_row[f.value_coord[1]].append(f)
    return by_row


def _group_metadata_by_row(metadata: list[MetadataEntry]) -> dict[int, list[MetadataEntry]]:
    """Bucket PLI-scoped MetadataEntries by their value cell's row."""
    by_row: dict[int, list[MetadataEntry]] = defaultdict(list)
    for entry in metadata:
        if entry.scope != FieldScope.PLI:
            continue
        row = _cell_row(entry.source)
        if row is not None:
            by_row[row].append(entry)
    return by_row


def _sheet_scoped_metadata(metadata: list[MetadataEntry]) -> dict[str, Any]:
    """Flatten SHEET-scoped MetadataEntries into a `{key_or_canonical: value}` map."""
    out: dict[str, Any] = {}
    for entry in metadata:
        if entry.scope != FieldScope.SHEET:
            continue
        key = entry.canonical or entry.key
        out[key] = entry.value
    return out


def _cell_row(source: str) -> int | None:
    """Parse the row index out of an A1-style cell reference like 'K4'."""
    idx = 0
    while idx < len(source) and source[idx].isalpha():
        idx += 1
    if idx == 0 or idx == len(source):
        return None
    try:
        return int(source[idx:])
    except ValueError:
        return None


def _build_pli(
    *,
    row: int,
    findings:       list[Finding],
    stages:         list[FinalStage],
    pli_metadata:   list[MetadataEntry],
    sheet_metadata: dict[str, Any],
    sheet:          str | None,
) -> PLI:
    """Assemble one PLI record from the findings + stages + metadata at one row."""
    best_finding_per_canonical = _best_finding_per_canonical(findings)
    flat_fields: dict[str, Any] = {
        _CANONICAL_TO_PLI_FIELD[c]: f.value
        for c, f in best_finding_per_canonical.items()
        if c in _CANONICAL_TO_PLI_FIELD
    }
    confidence_map = {
        _CANONICAL_TO_PLI_FIELD[c]: _CONFIDENCE_TO_FLOAT[f.confidence]
        for c, f in best_finding_per_canonical.items()
        if c in _CANONICAL_TO_PLI_FIELD
    }
    source_cells = {
        _CANONICAL_TO_PLI_FIELD[c]: f"{f.value_coord[0]}{f.value_coord[1]}"
        for c, f in best_finding_per_canonical.items()
        if c in _CANONICAL_TO_PLI_FIELD
    }
    metadata_map: dict[str, Any] = {**sheet_metadata}
    for entry in pli_metadata:
        key = entry.canonical or entry.key
        metadata_map[key] = entry.value

    return PLI(
        **flat_fields,
        stages=[_stage_from_final(s, sheet=sheet) for s in stages],
        confidence=confidence_map,
        metadata=metadata_map,
        source=Source(
            sheet=sheet, rows=[row],
            cells=source_cells,
        ),
    )


def _best_finding_per_canonical(findings: list[Finding]) -> dict[str, Finding]:
    """Pick one Finding per canonical — highest Confidence enum wins ties."""
    best: dict[str, Finding] = {}
    for f in findings:
        if f.canonical in _NON_PLI_FINDING_CANONICALS:
            continue
        existing = best.get(f.canonical)
        if existing is None or _CONFIDENCE_TO_FLOAT[f.confidence] > _CONFIDENCE_TO_FLOAT[existing.confidence]:
            best[f.canonical] = f
    return best


def _stage_from_final(s: FinalStage, *, sheet: str | None) -> Stage:
    """Map a canvas FinalStage to the public Stage shape."""
    name = s.canonical or s.name
    metadata = dict(s.stage_metadata) if s.stage_metadata else {}
    source_cells: dict[str, str] = {}
    if s.plan_date_col is not None:
        col_letter = get_column_letter(s.plan_date_col)
        # We don't have the row directly on a FinalStage in this shape, but
        # callers populate it via the per-row grouping. Leave the planned_date
        # cell unaddressed when row context isn't carried.
        source_cells["planned_date"] = f"{col_letter}?"
    return Stage(
        name=name,
        planned_date=s.plan_date,
        metadata=metadata,
        source=Source(sheet=sheet, rows=[], cells=source_cells),
    )


def _warning_to_public(w: ValidationWarning) -> Warning:
    """Convert a canvas ValidationWarning to the public Warning model."""
    return Warning(message=w.message, severity=w.severity, check=w.name)

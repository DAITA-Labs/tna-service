"""MetadataExtractor — open-vocabulary sheet metadata.

Runs AFTER the identifier and stage extractors. Metadata is the
leftover: every KvBlock on the sheet whose value cell hasn't already
been claimed by a stronger Finding becomes a `MetadataEntry`.

Each entry carries:

  - `key`            — the supplier's raw label text, verbatim. Novel
                       labels ("Treatment", "Booking Ref", "Bulk Pcs")
                       ship as-is without schema changes.
  - `value`          — the cell value (string / int / date / etc.)
  - `source`         — cell ref like "K4"
  - `canonical`      — OPTIONAL. Set when the raw label matches an alias
                       in `METADATA_SPECS` (e.g. "Buyer" → "buyer").
                       None for novel labels.
  - `scope`          — SHEET (this extractor's default — metadata
                       generally applies to all PLIs in the sheet).

The extractor consumes any prior `findings` list (combined output of
identifier + stage extractors) so it can skip KvBlocks whose value
position was already extracted as something stronger.
"""
from __future__ import annotations

from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import Finding
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._helpers import parse_date
from app.specs import METADATA_SPECS
from app.specs.enums import FieldScope, ValueDtype
from app.specs.schemas import MetadataEntry


@component
class MetadataExtractor(Component):
    """Emit a `MetadataEntry` per KvBlock not already claimed by a Finding.

    Inputs:
        bundle          — the ClusterAnchorBundle
        prior_findings  — combined Findings from identifier + stage extractors
                          (defaults to empty if metadata runs alone)
    Outputs:
        metadata        — list[MetadataEntry]
    """

    def __init__(self) -> None:
        Component.__init__(self)
        # Pre-build a lowercase alias → canonical lookup for cheap matching.
        self._alias_to_canonical: dict[str, str] = {
            alias.lower(): spec.canonical
            for spec in METADATA_SPECS
            for alias in spec.aliases
        }
        # canonical → expected dtype (used to decide between parse_date vs str)
        self._dtype_by_canonical: dict[str, ValueDtype] = {
            spec.canonical: spec.value_dtype for spec in METADATA_SPECS
        }

    @component.output_types(metadata=list[MetadataEntry])
    def run(self, bundle: ClusterAnchorBundle,
              prior_findings: list[Finding] | None = None) -> dict:
        claimed = {f.value_coord for f in (prior_findings or [])}

        entries: list[MetadataEntry] = []
        for kv in bundle.bag.kv_blocks:
            if kv.value_coord in claimed:
                continue   # identifier or stage extractor already claimed this cell

            raw = _read_cell(bundle, kv.value_coord)
            if raw is None:
                continue

            canonical = self._alias_to_canonical.get(_normalise_label(kv.label_text))
            value = _coerce_value(raw, canonical, self._dtype_by_canonical)

            col_letter, row = kv.value_coord
            entries.append(MetadataEntry(
                key=kv.label_text,
                value=value,
                source=f"{col_letter}{row}",
                canonical=canonical,
                scope=FieldScope.SHEET,
            ))
        return {"metadata": entries}


def _normalise_label(text: str) -> str:
    """Lowercase + replace hyphens/underscores with spaces (matches LayoutHint's
    label-matching convention)."""
    return text.lower().replace("-", " ").replace("_", " ").strip()


def _read_cell(bundle: ClusterAnchorBundle, coord: tuple[str, int]) -> Any:
    col_letter, row = coord
    col_idx = column_index_from_string(col_letter)
    raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
    if raw is None or raw == "":
        return None
    return raw


def _coerce_value(raw: Any, canonical: str | None,
                   dtype_by_canonical: dict[str, ValueDtype]) -> Any:
    """Coerce by canonical's expected dtype if known; else fall back to str.strip()."""
    if canonical is not None:
        expected = dtype_by_canonical.get(canonical)
        if expected == ValueDtype.DATE:
            parsed = parse_date(raw)
            return parsed if parsed is not None else raw
    if isinstance(raw, str):
        return raw.strip()
    return raw

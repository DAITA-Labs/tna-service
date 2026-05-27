"""StageExtractor — per-PLI stages from StageBands + SubfieldClusters.

Stages are an open vocabulary like metadata. Each `bag.stage_band` carries
a `name_text` (e.g. "PPS Submission") and a column rect. The matching
`SubfieldCluster` (looked up by `parent_band_id`) lists the sub-column
header coords — those headers identify Plan / Actual / Status / Remarks
sub-fields within the band.

Per (PLI row, band) the extractor builds a `FinalStage`:

  - `name`           — band.name_text verbatim
  - `canonical`      — set when name matches a `STAGE_SPECS` alias; else None
  - `plan_date`      — value at the planned_date sub-column (parsed via
                        parse_date)
  - `plan_date_col`  — int 1-indexed column carrying the plan date
  - `column_range`   — (band.rect.c0, band.rect.c1) for traceability
  - `stage_metadata` — dict of every other sub-column's value, keyed by:
                        * the sub-field's canonical name when its header
                          matched a SUBFIELD_SPECS alias (e.g.
                          "actual_date", "remarks", "status")
                        * the raw header text otherwise (open vocab)

A row + band with no plan_date AND no other populated sub-cells emits
no stage — the PLI simply doesn't carry data for that stage.

The single-column band case (no SubfieldCluster) is handled too: the
band itself IS the plan_date column; `stage_metadata` will be empty.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from haystack import component
from openpyxl.utils import column_index_from_string, get_column_letter

from app.artifacts.structure import StageBand, StructureBag, SubfieldCluster
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.components.field._helpers import parse_date
from app.specs import STAGE_SPECS, SUBFIELD_SPECS
from app.specs.enums import ValueDtype
from app.specs.schemas import FinalStage


_PLAN_DATE_CANONICAL = "planned_date"


@component
class StageExtractor(Component):
    """Emit `FinalStage` records per (PLI row, band).

    Inputs:
        bundle — the ClusterAnchorBundle

    Outputs:
        stages_per_row — dict[int, list[FinalStage]] keyed by PLI row index
    """

    def __init__(self) -> None:
        Component.__init__(self)
        self._stage_alias_to_canonical: dict[str, str] = {
            _normalise(alias): spec.canonical
            for spec in STAGE_SPECS for alias in spec.aliases
        }
        self._subfield_alias_to_spec: dict[str, tuple[str, ValueDtype]] = {
            _normalise(alias): (spec.canonical, spec.value_dtype)
            for spec in SUBFIELD_SPECS for alias in spec.aliases
        }

    @component.output_types(stages_per_row=dict[int, list[FinalStage]])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        bag = bundle.bag
        rows = _pli_rows(bundle)
        if not bag.stage_bands or not rows:
            return {"stages_per_row": {}}

        clusters_by_band_id = {c.parent_band_id: c for c in bag.subfield_clusters}

        stages_per_row: dict[int, list[FinalStage]] = defaultdict(list)
        for band_idx, band in enumerate(bag.stage_bands):
            stage_canonical = self._stage_alias_to_canonical.get(_normalise(band.name_text))
            sub_cols = self._resolve_sub_columns(
                bundle, band, clusters_by_band_id.get(band_idx),
            )

            for row in rows:
                stage = self._build_stage(
                    bundle, band, stage_canonical, sub_cols, row,
                )
                if stage is not None:
                    stages_per_row[row].append(stage)

        return {"stages_per_row": dict(stages_per_row)}

    # ─── per-band sub-column resolution ────────────────────────────────────

    def _resolve_sub_columns(self,
                                bundle: ClusterAnchorBundle,
                                band: StageBand,
                                cluster: SubfieldCluster | None,
                              ) -> list[tuple[int, str, ValueDtype]]:
        """Return one entry per sub-column inside the band.

        Each entry is `(col_idx, key, dtype)` where:
          - col_idx is the 1-indexed column carrying the sub-field
          - key is the subfield's canonical name when the header matched
            a SUBFIELD_SPECS alias; else the raw header text
          - dtype is the expected value dtype (helps with coercion)

        When the band has no SubfieldCluster, the band itself IS the
        plan_date column and we return a single entry covering its column.
        """
        if cluster is None or not cluster.subfield_coords:
            # Single-column band — band rect IS the plan_date column.
            return [(band.rect.c0, _PLAN_DATE_CANONICAL, ValueDtype.DATE)]

        out: list[tuple[int, str, ValueDtype]] = []
        for (row, col) in cluster.subfield_coords:
            header_text = bundle.canvas.cell_values[row - 1][col - 1]
            if not isinstance(header_text, str):
                header_text = ""
            match = self._subfield_alias_to_spec.get(_normalise(header_text))
            if match is not None:
                canonical, dtype = match
                out.append((col, canonical, dtype))
            elif header_text:
                # Open vocab: novel sub-header → use raw text as key, string dtype.
                out.append((col, header_text.strip(), ValueDtype.STR))
        return out

    # ─── per-row stage construction ────────────────────────────────────────

    def _build_stage(self,
                       bundle: ClusterAnchorBundle,
                       band: StageBand,
                       stage_canonical: str | None,
                       sub_cols: list[tuple[int, str, ValueDtype]],
                       row: int,
                     ) -> FinalStage | None:
        """Build one FinalStage for `(band, row)`, or None when no data present."""
        plan_date: Any = None
        plan_date_col: int | None = None
        stage_metadata: dict[str, Any] = {}

        for col_idx, key, dtype in sub_cols:
            raw = bundle.canvas.cell_values[row - 1][col_idx - 1]
            if raw is None or raw == "":
                continue

            value = _coerce(raw, dtype)
            if key == _PLAN_DATE_CANONICAL and value is not None:
                plan_date = value
                plan_date_col = col_idx
            else:
                stage_metadata[key] = value

        if plan_date is None and not stage_metadata:
            return None

        return FinalStage(
            name=band.name_text,
            canonical=stage_canonical,
            plan_date=plan_date,
            plan_date_col=plan_date_col,
            column_range=(band.rect.c0, band.rect.c1),
            stage_metadata=stage_metadata,
        )


# ─── helpers ───────────────────────────────────────────────────────────────


def _pli_rows(bundle: ClusterAnchorBundle) -> list[int]:
    """Flatten DataRowRanges from the hint into a list of 1-indexed row numbers."""
    rows: list[int] = []
    for rng in bundle.hint.data_row_ranges:
        rows.extend(range(rng.row_start, rng.row_end + 1))
    return rows


def _normalise(text: str) -> str:
    """Lower-case + collapse hyphens/underscores so alias matching is robust."""
    return text.lower().replace("-", " ").replace("_", " ").strip()


def _coerce(value: Any, dtype: ValueDtype) -> Any:
    """Coerce a raw cell value by expected dtype; return None when unparseable."""
    if dtype == ValueDtype.DATE:
        return parse_date(value)
    if dtype == ValueDtype.INT:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else value
        return None  # garbage strings drop; richer coercion belongs in a dedicated extractor
    if isinstance(value, str):
        return value.strip()
    return value

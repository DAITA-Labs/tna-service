"""StageStructureValidator — structural invariants of detected StageBands.

Five independent invariants, one helper each. The component's `run` is a
thin orchestrator that calls each helper and concatenates their findings.

  1. anchor_row_alignment       — all bands share `rect.r0`        (error)
  2. subheader_row_alignment    — sub-headers at `rect.r0 - 1`     (error)
  3. column_range_matches_merge — band cols backed by a horizontal
                                   merge at the name row           (warning)
  4. sub_field_count_consistency — bands share a sub-column count   (warning)
  5. sub_header_text_recognised  — sub-headers match SUBFIELD aliases (info)

A band is the smallest TNA "stage" unit — a name cell over a date arena
of sub-columns. These invariants come from the empirical observation
that real TNA sheets lay every stage side-by-side under one header
strip. When the structure phase produces bands that violate these
invariants, either the sheet is malformed or our detection is.
"""
from __future__ import annotations

from collections import Counter

from haystack import component
from openpyxl.utils import column_index_from_string

from app.artifacts.finding import ValidationWarning
from app.artifacts.structure import StructureBag
from app.artifacts.workbook import ClusterAnchorBundle
from app.components._base import Component
from app.specs import SUBFIELD_SPECS


# Pre-build the set of all sub-header aliases (lowercase) for O(1) matching.
_SUBFIELD_ALIASES: frozenset[str] = frozenset(
    alias.strip().lower()
    for spec in SUBFIELD_SPECS
    for alias in spec.aliases
)


@component
class StageStructureValidator(Component):
    """Emit warnings for structural-invariant violations across stage bands."""

    def __init__(self) -> None:
        Component.__init__(self)

    @component.output_types(warnings=list[ValidationWarning])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        warnings: list[ValidationWarning] = []
        warnings.extend(_check_anchor_row_alignment(bundle.bag))
        warnings.extend(_check_subheader_row_alignment(bundle.bag))
        warnings.extend(_check_column_range_matches_merge(bundle.bag))
        warnings.extend(_check_sub_field_count_consistency(bundle.bag))
        warnings.extend(_check_sub_header_text_recognised(bundle))
        return {"warnings": warnings}


def _check_anchor_row_alignment(bag: StructureBag) -> list[ValidationWarning]:
    """Every StageBand should anchor its data arena at the same row.

    Bands sit side-by-side under a shared header strip. If two bands
    report different `rect.r0` values, at least one was anchored to the
    wrong row — data extraction will read mismatched rows.
    """
    if len(bag.stage_bands) < 2:
        return []

    rows = [band.rect.r0 for band in bag.stage_bands]
    if len(set(rows)) == 1:
        return []

    expected = Counter(rows).most_common(1)[0][0]
    return [
        ValidationWarning(
            name="stage_band_anchor_row_misaligned",
            severity="error",
            message=(
                f"StageBand `{band.name_text}` anchors data at row "
                f"{band.rect.r0}, but the majority of bands anchor at row "
                f"{expected} — bands should share a data-anchor row."
            ),
        )
        for band in bag.stage_bands
        if band.rect.r0 != expected
    ]


def _check_subheader_row_alignment(bag: StructureBag) -> list[ValidationWarning]:
    """Sub-headers must sit on one row, equal to `parent_band.rect.r0 - 1`.

    Within a band, sub-columns (Plan / Actual / Status / Remarks) all
    sit on the row immediately above the data arena. Sub-headers
    spanning multiple rows mean either the band's arena is misshapen
    or the cluster captured cells outside the band.
    """
    warnings: list[ValidationWarning] = []
    for cluster in bag.subfield_clusters:
        if cluster.parent_band_id >= len(bag.stage_bands):
            continue
        parent = bag.stage_bands[cluster.parent_band_id]
        sub_rows = {row for (row, _col) in cluster.subfield_coords}

        if len(sub_rows) > 1:
            warnings.append(ValidationWarning(
                name="subheader_row_split",
                severity="error",
                message=(
                    f"StageBand `{parent.name_text}` has sub-headers across "
                    f"rows {sorted(sub_rows)} — expected a single row."
                ),
            ))
            continue

        if not sub_rows:
            continue

        actual_row = next(iter(sub_rows))
        expected_row = parent.rect.r0 - 1
        if actual_row != expected_row:
            warnings.append(ValidationWarning(
                name="subheader_row_offset",
                severity="error",
                message=(
                    f"StageBand `{parent.name_text}` sub-headers at row "
                    f"{actual_row}, but band.rect.r0={parent.rect.r0} "
                    f"expects sub-header row {expected_row}."
                ),
            ))
    return warnings


def _check_column_range_matches_merge(bag: StructureBag) -> list[ValidationWarning]:
    """A band's column range should be covered by a horizontal merge span.

    Stage names typically live in a horizontally-merged super-header
    spanning the band's sub-columns. A band whose name cell is NOT a
    merge anchor matching its column range was detected by fallback
    (single-cell text above the arena) — still usable, but less
    structurally backed.
    """
    warnings: list[ValidationWarning] = []
    horizontal = [m for m in bag.merge_spans if m.orientation == "horizontal"]

    for band in bag.stage_bands:
        name_col_letter, name_row = band.name_coord
        name_col = column_index_from_string(name_col_letter)
        if any(
            m.rect.r0 == name_row
            and m.rect.c0 == name_col
            and m.rect.c1 == band.rect.c1
            for m in horizontal
        ):
            continue
        warnings.append(ValidationWarning(
            name="stage_band_no_merge_anchor",
            severity="warning",
            message=(
                f"StageBand `{band.name_text}` (cols "
                f"{band.rect.c0}–{band.rect.c1}, name row {name_row}) "
                f"has no matching horizontal merge — name was inferred "
                f"from a single cell, not a merged super-header."
            ),
        ))
    return warnings


def _check_sub_field_count_consistency(bag: StructureBag) -> list[ValidationWarning]:
    """Stage bands should share a sub-column count; outliers warn.

    Real TNA sheets repeat the same sub-column shape (e.g. Plan/Actual)
    across every stage. A band whose sub-column count differs from the
    majority is usually a detection error — the band absorbed extra
    columns or missed one.
    """
    if len(bag.subfield_clusters) < 2:
        return []

    counts = Counter(len(c.subfield_coords) for c in bag.subfield_clusters)
    if len(counts) == 1:
        return []

    most_common, _ = counts.most_common(1)[0]
    warnings: list[ValidationWarning] = []
    for cluster in bag.subfield_clusters:
        if len(cluster.subfield_coords) == most_common:
            continue
        if cluster.parent_band_id >= len(bag.stage_bands):
            continue
        parent = bag.stage_bands[cluster.parent_band_id]
        warnings.append(ValidationWarning(
            name="stage_band_subfield_count_outlier",
            severity="warning",
            message=(
                f"StageBand `{parent.name_text}` has "
                f"{len(cluster.subfield_coords)} sub-columns; the majority "
                f"of bands have {most_common}."
            ),
        ))
    return warnings


def _check_sub_header_text_recognised(bundle: ClusterAnchorBundle) -> list[ValidationWarning]:
    """At least one sub-header per band should match a SUBFIELD alias.

    Bands whose sub-headers are entirely novel (no Plan/Actual/Status/
    Remarks-style label) may not actually be stage bands — they could
    be an arbitrary group of columns the resolver mistook for one.
    Emit `info` so the catalog can grow without blocking extraction.
    """
    warnings: list[ValidationWarning] = []
    canvas = bundle.canvas

    for cluster in bundle.bag.subfield_clusters:
        if cluster.parent_band_id >= len(bundle.bag.stage_bands):
            continue
        parent = bundle.bag.stage_bands[cluster.parent_band_id]

        seen: list[str] = []
        for (row, col) in cluster.subfield_coords:
            if not (1 <= row <= canvas.n_rows and 1 <= col <= canvas.n_cols):
                continue
            value = canvas.cell_values[row - 1][col - 1]
            if isinstance(value, str) and value.strip():
                seen.append(value.strip().lower())

        if not seen:
            continue
        if any(text in _SUBFIELD_ALIASES for text in seen):
            continue

        warnings.append(ValidationWarning(
            name="stage_band_unrecognised_subheaders",
            severity="info",
            message=(
                f"StageBand `{parent.name_text}` sub-headers {seen} match "
                f"no SUBFIELD_SPECS aliases — band may not be a real stage. "
                f"Consider adding to the catalog if these labels recur."
            ),
        ))
    return warnings

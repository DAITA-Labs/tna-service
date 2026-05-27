"""LayoutComposer — bundle StructureBag + LayoutAxes into a LayoutHint.

The LayoutHint is the artifact field components consume. It carries:
  - axes (PliAxis, StageAxis, SubfieldAxis + confidence)
  - all semantic records (header_band, data_row_ranges, stage_arenas,
    stage_bands, subfield_clusters, section_boundaries, kv_blocks)
  - candidate_columns / candidate_rows / candidate_kv_blocks dicts
    pre-narrowed by canonical name

Pre-narrowing the candidate dicts here means field components don't
re-scan the canvas for label cells — they consult the LayoutHint and
operate on the small candidate set.
"""
from __future__ import annotations

from collections import defaultdict

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutAxes, LayoutHint
from app.artifacts.structure import StructureBag
from app.tools.canvas.query import query_phase


def compose_layout_hint(canvas: GridCanvas,
                          bag: StructureBag,
                          axes: LayoutAxes,
                          cluster_id: str = "default") -> LayoutHint:
    """Bundle bag + axes into a LayoutHint with candidate dicts pre-narrowed."""
    overall_confidence = _overall_confidence(axes)

    candidate_columns = _candidate_columns_per_canonical(canvas, bag)
    candidate_rows = _candidate_rows_per_canonical(canvas, bag)
    candidate_kv_blocks = _candidate_kv_blocks_per_canonical(bag)

    return LayoutHint(
        axes=axes,
        cluster_id=cluster_id,
        confidence=overall_confidence,
        header_band=bag.header_band,
        data_row_ranges=list(bag.data_row_ranges),
        section_boundaries=list(bag.section_boundaries),
        stage_arenas=list(bag.stage_arenas),
        stage_bands=list(bag.stage_bands),
        subfield_clusters=list(bag.subfield_clusters),
        kv_blocks=list(bag.kv_blocks),
        candidate_columns=candidate_columns,
        candidate_rows=candidate_rows,
        candidate_kv_blocks=candidate_kv_blocks,
    )


def _overall_confidence(axes: LayoutAxes) -> float:
    """Average the per-axis confidence values; default 0.5 if empty."""
    if not axes.confidence:
        return 0.5
    return sum(axes.confidence.values()) / len(axes.confidence)


def _candidate_columns_per_canonical(canvas: GridCanvas,
                                       bag: StructureBag) -> dict[str, list[int]]:
    """Pre-narrow which columns are candidates for each canonical, **ranked best-first**.

    Each header-band cell that matches an identifier-spec alias contributes
    its `SpecMatch.weight` (from the alias's `label_match_mode`) to its
    column's aggregate score. Columns are returned per canonical sorted by
    that aggregate descending — so consumers can take `columns[0]` and get
    the strongest header match. Ties are broken by lower column index for
    stable ordering.
    """
    if bag.header_band is None:
        return {}
    band_rows = set(range(bag.header_band.rect.r0, bag.header_band.rect.r1 + 1))

    matches = query_phase(canvas, "identifier", restrict_rows=band_rows)

    # canonical → column_index → aggregate weight
    weights: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for m in matches:
        col_idx = _column_letter_to_index(m.col)
        weights[m.canonical][col_idx] += m.weight

    return {
        canonical: [col for col, _ in sorted(
            col_weights.items(),
            key=lambda item: (-item[1], item[0]),  # weight desc, col_idx asc
        )]
        for canonical, col_weights in weights.items()
    }


def _candidate_rows_per_canonical(canvas: GridCanvas,
                                    bag: StructureBag) -> dict[str, list[int]]:
    """Pre-narrow PLI data rows — same for every canonical when one tabular band exists."""
    rows: list[int] = []
    for r in bag.data_row_ranges:
        rows.extend(range(r.row_start, r.row_end + 1))
    # All identifier canonicals share the same data row set in tabular layouts.
    if not rows:
        return {}
    return {canonical: list(rows) for canonical in (
        "io_number", "style_code", "style_name",
        "color_code", "color_name",
        "fabric_code", "fabric_name",
        "quantity",
        "delivery_date", "shipment_date", "ex_fty_date",
    )}


def _candidate_kv_blocks_per_canonical(bag: StructureBag) -> dict[str, list]:
    """Pre-narrow which KvBlocks could carry each identifier canonical by label text.

    Cheap match: case-insensitive substring against a small alias table.
    Field components do the final alias resolution; this is a pre-filter
    so they don't iterate every KvBlock on every component.
    """
    label_hints: dict[str, tuple[str, ...]] = {
        "io_number":     ("io", "ion", "job", "po", "internal order"),
        "quantity":      ("qty", "quantity", "pcs", "pieces"),
        "delivery_date": ("delivery", "eta", "arrival"),
        "shipment_date": ("shipment", "ship", "dispatch", "ex con"),
        "ex_fty_date":   ("ex factory", "ex fty", "ex fac", "exf"),
        "style_code":    ("style", "sty"),
        "color_code":    ("color", "colour", "col"),
        "fabric_code":   ("fabric", "fab", "fbr"),
    }

    by_canon: dict[str, list] = defaultdict(list)
    for kv in bag.kv_blocks:
        # Normalise hyphens / underscores / multiple spaces — "Ex-Factory Date"
        # should match "ex factory" the same as "Ex Factory Date" does.
        haystack = kv.label_text.lower().replace("-", " ").replace("_", " ")
        for canon, hints in label_hints.items():
            if any(h in haystack for h in hints):
                by_canon[canon].append(kv)
    return dict(by_canon)


def _column_letter_to_index(letter: str) -> int:
    """Convert a column letter ('A', 'AB') to its 1-indexed integer position."""
    from openpyxl.utils import column_index_from_string  # noqa: PLC0415 — small util
    return column_index_from_string(letter)

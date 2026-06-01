"""Workbook-level artifacts — sheet signatures, PLI clusters, anchor bundles.

`SheetSignature` is a compact structural fingerprint of one sheet used
to decide which sheets share a template. `PliCluster` is the grouping
produced by the clusterer plus the role label produced downstream.
`ClusterAnchorBundle` is the structure-phase output for a cluster's
anchor sheet — the handoff artifact downstream field components consume.

These are pure data records; the algorithms that compute them live in
`app.components.workbook.{profiler,signature,clusterer,role_classifier,
anchor_picker,workbook_phase}`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.artifacts.canvas import GridCanvas
from app.artifacts.layout import LayoutHint
from app.artifacts.structure import StructureBag


# How many rows from the top of each sheet are sampled into the signature.
# Tight bound — structural pattern lives in the header region; deeper rows
# are dominated by data and add noise to similarity scoring.
SIGNATURE_SAMPLE_ROWS = 20

# How many rows from the top are scanned for label-text positions.
SIGNATURE_LABEL_ROWS = 5


@dataclass(frozen=True)
class DtypeHistogram:
    """Per-row count of cells in each dtype slot.

    Frozen + hashable so it composes inside `SheetSignature` (which is
    itself frozen and used as a dict key in clusterer tests).
    """

    n_blank: int
    n_str:   int
    n_int:   int
    n_float: int
    n_date:  int


@dataclass(frozen=True)
class LabelPosition:
    """A normalised label cell coordinate — (row, col, text)."""

    row:  int
    col:  int
    text: str


@dataclass(frozen=True)
class SheetSignature:
    """Compact structural fingerprint of a sheet used by the clusterer.

    Three orthogonal signals — caller decides how to weight them when
    scoring two signatures for similarity:

      non_blank_mask     — frozenset of (row, col) coordinates that hold a
                            non-blank cell, sampled from the first
                            `SIGNATURE_SAMPLE_ROWS` rows. Captures the
                            shape of the populated region.

      dtype_per_row      — tuple of `DtypeHistogram`, one per sampled row,
                            for the first `SIGNATURE_SAMPLE_ROWS` rows.
                            Captures the ordering of header rows vs data
                            rows.

      label_positions    — frozenset of `LabelPosition` for non-empty
                            string cells in the first `SIGNATURE_LABEL_ROWS`
                            rows. Captures shared header vocabulary even
                            when the data shape differs slightly.
    """

    sheet_name:      str
    n_rows:          int
    n_cols:          int
    non_blank_mask:  frozenset[tuple[int, int]] = field(default_factory=frozenset)
    dtype_per_row:   tuple[DtypeHistogram, ...] = ()
    label_positions: frozenset[LabelPosition] = field(default_factory=frozenset)


@dataclass
class PliCluster:
    """A group of sheets that share the same structural template.

    `cluster_id` is a stable identifier within the workbook (assigned in
    discovery order: "c0", "c1", ...). `sheet_names` carries every sheet
    grouped into this cluster; the anchor sheet (template) is chosen
    separately at structure-phase time.
    """

    cluster_id:  str
    sheet_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClusterAnchorBundle:
    """Structure-phase artifacts for one cluster, anchored to a chosen sheet.

    Carries the cluster identity plus the canvas / bag / hint computed
    from running `run_structure_phase` against the anchor sheet. The
    bundle is the handoff to field components: they read the hint to
    locate identifiers, the canvas for cell values, and the bag for any
    record the hint doesn't surface.

    `sibling_canvases` maps every *other* sheet in the cluster (i.e.
    cluster members minus the anchor) to its `GridCanvas`. Siblings
    share the cluster's plan with the anchor (that's what makes them a
    cluster) but carry their own cell data; the applier walks them to
    produce per-sibling PLIs in addition to the anchor's. Empty for
    singleton clusters.
    """

    cluster:     PliCluster
    anchor_sheet_name: str
    canvas:      GridCanvas
    bag:         StructureBag
    hint:        LayoutHint
    sibling_canvases: dict[str, GridCanvas] = field(default_factory=dict)

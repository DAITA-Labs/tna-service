"""Workbook-level artifacts — sheet signatures and PLI clusters.

`SheetSignature` is a compact structural fingerprint of one sheet used
to decide which sheets share a template. `PliCluster` is the grouping
produced by the clusterer plus the role label produced downstream.

These are pure data records; the algorithms that compute them live in
`app.components.workbook.{profiler,signature,clusterer,role_classifier}`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# How many rows from the top of each sheet are sampled into the signature.
# Tight bound — structural pattern lives in the header region; deeper rows
# are dominated by data and add noise to similarity scoring.
SIGNATURE_SAMPLE_ROWS = 20

# How many rows from the top are scanned for label-text positions.
SIGNATURE_LABEL_ROWS = 5


ClusterRole = Literal["pli_cluster", "other_sheets", "unknown"]


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

    `role` defaults to "unknown"; the role classifier sets it to
    "pli_cluster" or "other_sheets" once StructureBag signals are
    available.
    """

    cluster_id:  str
    sheet_names: list[str] = field(default_factory=list)
    role:        ClusterRole = "unknown"

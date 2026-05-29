"""CanvasPlan + supporting dataclasses — the deterministic recipe for one cluster.

A `CanvasPlan` is everything `CanvasApplier` needs to produce one cluster's
`list[PLI]`: where each PLI iterates, which column or KvBlock each canonical
lives in, where stage bands sit, and which unclaimed tabular columns ship
into per-PLI metadata.

The plan is the output of the planning pipeline (structure phase → workbook
phase → field pickers → cross-field pickers → plan assembler) and the input
to the apply step. Plan-time validators inspect it before apply; post-apply
validators inspect the resulting PLIs.

This module carries the pure data shapes only. Construction lives in
`app/components/plan/plan_assembler.py` (planned); consumption lives in
`app/components/plan/canvas_applier.py` (planned).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.artifacts.structure import KvBlock, SectionBoundary
from app.enums.field_location_mode import FieldLocationMode
from app.enums.pli_axis import PliAxis
from app.policies._base import PolicyVerdict


@dataclass(frozen=True)
class FieldLocation:
    """Where one canonical's value lives in a cluster.

    `mode` discriminates how `CanvasApplier` reads the value:
      COLUMN   — read from `column` per `pli_rows` row
      KV_BLOCK — read once from `kv_block.value_coord`; SHEET-scoped
      MISSING  — canonical not located in this cluster
    """

    canonical:   str
    mode:        FieldLocationMode
    column:      int | None             = None
    kv_block:    KvBlock | None         = None
    score:       float                  = 0.0
    verdicts:    list[PolicyVerdict]    = field(default_factory=list)


@dataclass(frozen=True)
class StageBandPlan:
    """One stage band entry of the plan.

    `column_range` covers the band's full column extent. `subfield_cols`
    maps each detected subfield (e.g. "planned_date", "actual_date") to
    its concrete column index inside the range.
    """

    name:          str
    canonical:     str | None
    column_range:  tuple[int, int]
    subfield_cols: dict[str, int]       = field(default_factory=dict)
    score:         float                = 0.0
    verdicts:      list[PolicyVerdict]  = field(default_factory=list)


@dataclass(frozen=True)
class MetadataColumn:
    """An unclaimed tabular column whose per-row values ship as PLI metadata.

    Enforces the no-data-loss principle: any column the field pickers did
    not consume becomes a per-row metadata entry on every PLI, keyed by
    the column's header text (or its `canonical` if a METADATA_SPECS alias
    matched).
    """

    column:      int
    header_text: str
    canonical:   str | None = None


@dataclass(frozen=True)
class CanvasPlan:
    """The complete deterministic recipe for extracting PLIs from one bundle.

    Produced by the planning pipeline; consumed by `CanvasApplier`. Frozen
    so plan-time validators and post-apply policies see the same object
    a planner committed to.
    """

    cluster_id:        str
    anchor_sheet_name: str
    pli_axis:          PliAxis

    # WHERE PLIs iterate.
    pli_rows:           list[int]                    = field(default_factory=list)
    section_boundaries: list[SectionBoundary]        = field(default_factory=list)

    # WHERE each PLI field lives.
    field_locations:    dict[str, FieldLocation]     = field(default_factory=dict)

    # WHERE stages live.
    stage_bands:        list[StageBandPlan]          = field(default_factory=list)

    # WHERE metadata lives — per no-data-loss principle.
    metadata_blocks:    list[KvBlock]                = field(default_factory=list)
    metadata_columns:   list[MetadataColumn]         = field(default_factory=list)

    # Audit trail + aggregate confidence.
    all_verdicts:       list[PolicyVerdict]          = field(default_factory=list)
    confidence:         float                        = 0.0


@dataclass(frozen=True)
class PliKey:
    """Identity tuple for a single PLI — all seven dimensions participate.

    A PLI is the unique combination of (io_number, style_code, color_code,
    fabric_code) intersected with one of (ex_fty_date, shipment_date,
    delivery_date). Equality is structural; instances are hashable so
    callers can dedupe.
    """

    io_number:     str | None
    style_code:    str | None
    color_code:    str | None
    fabric_code:   str | None
    ex_fty_date:   date | None
    shipment_date: date | None
    delivery_date: date | None

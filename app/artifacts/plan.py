"""CanvasPlan + supporting dataclasses — the deterministic recipe for one cluster.

A `CanvasPlan` is everything `CanvasApplier` needs to produce one cluster's
`list[PLI]`: where each PLI iterates, which column/row/kv each canonical
lives in, where stage bands sit, and which unclaimed metadata fields ship
on every PLI.

Every plan entry that names a field (identifier, stage, metadata) carries:
  - `mode` (COLUMN / ROW / KV_BLOCK / MISSING) — physical shape of the source
  - `scope` (SHEET / GROUP / PLI) — at what level the value applies
  - `read_direction` (SAME_ROW / SAME_COLUMN / OFFSET / FIXED) — how the
    applier walks from a PLI anchor to the value cell

The applier dispatches on these three; layout-specific reasoning lives in
the planner, not in the applier.

Construction lives in `app/components/plan/plan_assembler.py` (planned);
consumption lives in `app/components/plan/canvas_applier.py` (planned).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.artifacts.structure import KvBlock, Rect, SectionBoundary
from app.enums.field_location_mode import FieldLocationMode
from app.enums.field_scope import FieldScope
from app.enums.pli_axis import PliAxis
from app.enums.read_direction import ReadDirection
from app.enums.subfield_axis import SubfieldAxis
from app.policies._base import PolicyVerdict


@dataclass(frozen=True)
class FieldLocation:
    """Where one canonical identifier's value lives + how to read it.

    `mode` discriminates the physical source:
      COLUMN   — value at the intersection of `column` and a PLI-axis row
      ROW      — value at the intersection of `row` and a PLI-axis column
      KV_BLOCK — single value at `kv_block.value_coord` (SHEET-scoped)
      MISSING  — canonical not located in this cluster

    `read_direction` tells the applier how to combine the location with the
    PLI anchor.
    """

    canonical:       str
    mode:            FieldLocationMode
    scope:           FieldScope
    read_direction:  ReadDirection

    column:          int | None             = None    # for COLUMN mode
    row:             int | None             = None    # for ROW mode
    delta_row:       int                    = 0       # for OFFSET direction
    delta_col:       int                    = 0       # for OFFSET direction
    kv_block:        KvBlock | None         = None    # for KV_BLOCK mode

    score:           float                  = 0.0
    verdicts:        list[PolicyVerdict]    = field(default_factory=list)


@dataclass(frozen=True)
class StageBandPlan:
    """One named stage's plan entry.

    `anchor_coord` is the stage name cell. `subfield_indices` maps each
    detected subfield (planned_date, actual_date, qty, …) to either a
    column index (when `subfield_axis = HORIZONTAL`) or a row index
    (when `subfield_axis = VERTICAL`). The applier interprets per
    `subfield_axis` + `read_direction`.
    """

    name:             str
    canonical:        str | None
    anchor_coord:     tuple[int, int]
    anchor_rect:      Rect

    scope:            FieldScope
    subfield_axis:    SubfieldAxis
    read_direction:   ReadDirection
    subfield_indices: dict[str, int]        = field(default_factory=dict)

    score:            float                 = 0.0
    verdicts:         list[PolicyVerdict]   = field(default_factory=list)


@dataclass(frozen=True)
class MetadataPlan:
    """A metadata field's plan entry — covers column / row / kv shapes.

    Metadata is open-vocabulary: `header_text` is the key when no
    canonical match exists. `mode` selects which coord slot
    (`column` / `row` / `kv_block`) carries the source.
    """

    header_text:     str
    canonical:       str | None             = None

    mode:            FieldLocationMode      = FieldLocationMode.COLUMN
    scope:           FieldScope             = FieldScope.PLI
    read_direction:  ReadDirection          = ReadDirection.SAME_ROW

    column:          int | None             = None    # for COLUMN mode
    row:             int | None             = None    # for ROW mode
    delta_row:       int                    = 0       # for OFFSET direction
    delta_col:       int                    = 0       # for OFFSET direction
    kv_block:        KvBlock | None         = None    # for KV_BLOCK mode


@dataclass(frozen=True)
class CanvasPlan:
    """The complete deterministic recipe for extracting PLIs from one bundle.

    Produced by the planning pipeline; consumed by `CanvasApplier`. Frozen
    so plan-time validators and post-apply policies see the same object
    the planner committed to.
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

    # WHERE metadata lives — covers column / row / kv shapes uniformly.
    metadata_entries:   list[MetadataPlan]           = field(default_factory=list)

    # Audit trail + aggregate confidence.
    all_verdicts:       list[PolicyVerdict]          = field(default_factory=list)
    confidence:         float                        = 0.0


@dataclass(frozen=True)
class PliKey:
    """Identity tuple for a single PLI — all eight dimensions participate.

    A PLI is the unique combination of (io_number, style_code, color_code,
    fabric_code, quantity) intersected with one of (ex_fty_date,
    shipment_date, delivery_date). Equality is structural; instances are
    hashable so callers can dedupe.
    """

    io_number:     str | None
    style_code:    str | None
    color_code:    str | None
    fabric_code:   str | None
    quantity:      int | None
    ex_fty_date:   date | None
    shipment_date: date | None
    delivery_date: date | None

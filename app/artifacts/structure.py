"""Structure artifacts — typed records emitted by pattern detectors and resolvers.

Two record families:

  PATTERN RECORDS (from `app/tools/canvas/strips_*.py` and similar)
    DateStrip, IntStrip, FloatStrip, SameLengthStrip, LongTextStrip,
    ColorStrip, BoldStrip, BorderedBox, MergeSpan,
    NonMergedStrip, MergedColumnStrip, KvBlock, RepeatingRowGroup,
    PlanMarkerCluster

  SEMANTIC RECORDS (from `app/components/structure/resolvers/*.py`)
    HeaderBand, DataRowRange, SectionBoundary,
    StageArena, StageBand, SubfieldCluster

`StructureBag` is the carrier — pattern detectors append to it; resolvers
read it and append back. The bag is the input to `LayoutComposer` which
emits a `LayoutHint`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Direction = Literal["vertical", "horizontal", "block"]


@dataclass(frozen=True)
class Rect:
    """A bounding box on a canvas, 1-indexed inclusive on all four sides."""

    r0: int
    c0: int
    r1: int
    c1: int

    @property
    def area(self) -> int:
        """Number of cells the rectangle covers (inclusive both axes)."""
        return (self.r1 - self.r0 + 1) * (self.c1 - self.c0 + 1)


# ─── Pattern records ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DateStrip:
    """A contiguous line of date cells (≥3) — vertical or horizontal."""

    rect:        Rect
    orientation: Direction
    density:     float


@dataclass(frozen=True)
class IntStrip:
    """A vertical column whose cells are ≥80% int, magnitude-tagged."""

    rect:      Rect
    magnitude: Literal["small", "medium", "large"]
    density:   float


@dataclass(frozen=True)
class FloatStrip:
    """A vertical column whose cells are ≥80% float."""

    rect:    Rect
    density: float


@dataclass(frozen=True)
class SameLengthStrip:
    """A vertical column where >70% of string cells share the same char length."""

    rect:    Rect
    length:  int
    density: float


@dataclass(frozen=True)
class LongTextStrip:
    """A vertical column whose strings are predominantly ≥20 characters."""

    rect:        Rect
    mean_length: float


@dataclass(frozen=True)
class ColorStrip:
    """A run of ≥3 contiguous cells sharing one fill colour."""

    rect:        Rect
    orientation: Direction
    color:       str


@dataclass(frozen=True)
class BoldStrip:
    """A run of contiguous bold cells in one direction."""

    rect:        Rect
    orientation: Direction


@dataclass(frozen=True)
class BorderedBox:
    """A rectangle outlined by a complete 4-side border."""

    rect: Rect


@dataclass(frozen=True)
class MergeSpan:
    """A horizontal or vertical merge span (1-indexed inclusive)."""

    rect:        Rect
    orientation: Direction


@dataclass(frozen=True)
class NonMergedStrip:
    """A column or row whose data cells have zero merge participation."""

    rect:        Rect
    orientation: Direction


@dataclass(frozen=True)
class MergedColumnStrip:
    """A column whose data cells contain multiple vertical merges."""

    rect:        Rect
    merge_count: int


@dataclass(frozen=True)
class KvBlock:
    """A bold/filled label cell paired with an adjacent non-label value cell."""

    label_coord:  tuple[str, int]
    value_coord:  tuple[str, int]
    label_text:   str
    value_dtype:  int


@dataclass(frozen=True)
class RepeatingRowGroup:
    """A set of rows whose content signatures are identical."""

    row_indices: tuple[int, ...]
    signature:   str


@dataclass(frozen=True)
class PlanMarkerCluster:
    """A neighbourhood of cells matching 'Plan' / 'Planned' / 'Scheduled' text."""

    cells: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class RowDtypeProfile:
    """Per-row dtype distribution — counts of cells by dtype across one row.

    Used by AxisInferrer to identify text-dense rows (likely headers) vs
    numeric-dense rows (likely data) vs blank rows. Counts are absolute
    cell counts; densities can be derived by dividing by `n_cols`.
    """

    row_idx:        int
    n_cols:         int
    n_blank:        int
    n_date:         int
    n_int:          int
    n_float:        int
    n_str:          int
    n_formula:      int


@dataclass(frozen=True)
class ColDtypeProfile:
    """Per-column dtype distribution — counts of cells by dtype down one column."""

    col_idx:        int
    n_rows:         int
    n_blank:        int
    n_date:         int
    n_int:          int
    n_float:        int
    n_str:          int
    n_formula:      int


# ─── Semantic records ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class HeaderBand:
    """The contiguous rows of label-shaped cells anchoring a tabular layout."""

    rect:  Rect
    score: float


@dataclass(frozen=True)
class DataRowRange:
    """A contiguous run of PLI data rows under a header band."""

    row_start: int
    row_end:   int


@dataclass(frozen=True)
class SectionBoundary:
    """A repeating-header-driven section boundary in SECTION_PER_PLI layouts."""

    start_row:  int
    end_row:    int
    section_id: str


@dataclass(frozen=True)
class StageArena:
    """A rectangle of date-cluster cells with at least one plan marker nearby."""

    rect: Rect


@dataclass(frozen=True)
class StageBand:
    """A named stage band (date column or row group + its name cell)."""

    rect:       Rect
    name_coord: tuple[str, int]
    name_text:  str


@dataclass(frozen=True)
class SubfieldCluster:
    """Sub-columns (Plan/Actual/Status/Remarks) inside a single StageBand."""

    parent_band_id:    int
    subfield_coords:   tuple[tuple[int, int], ...]


# ─── Carrier ────────────────────────────────────────────────────────────────


@dataclass
class StructureBag:
    """The carrier for every pattern and semantic record emitted during structure phase.

    Pattern detectors append records here in parallel. Semantic resolvers
    read pattern records and append their own semantic records back. The
    bag is consumed by AxisInferrer and LayoutComposer to emit a `LayoutHint`.
    """

    # Pattern records
    date_strips:           list[DateStrip] = field(default_factory=list)
    int_strips:            list[IntStrip] = field(default_factory=list)
    float_strips:          list[FloatStrip] = field(default_factory=list)
    same_length_strips:    list[SameLengthStrip] = field(default_factory=list)
    long_text_strips:      list[LongTextStrip] = field(default_factory=list)
    color_strips:          list[ColorStrip] = field(default_factory=list)
    bold_strips:           list[BoldStrip] = field(default_factory=list)
    bordered_boxes:        list[BorderedBox] = field(default_factory=list)
    merge_spans:           list[MergeSpan] = field(default_factory=list)
    non_merged_strips:     list[NonMergedStrip] = field(default_factory=list)
    merged_column_strips:  list[MergedColumnStrip] = field(default_factory=list)
    kv_blocks:             list[KvBlock] = field(default_factory=list)
    repeating_groups:      list[RepeatingRowGroup] = field(default_factory=list)
    plan_marker_clusters:  list[PlanMarkerCluster] = field(default_factory=list)

    # Semantic records
    header_band:           HeaderBand | None = None
    data_row_ranges:       list[DataRowRange] = field(default_factory=list)
    section_boundaries:    list[SectionBoundary] = field(default_factory=list)
    stage_arenas:          list[StageArena] = field(default_factory=list)
    stage_bands:           list[StageBand] = field(default_factory=list)
    subfield_clusters:     list[SubfieldCluster] = field(default_factory=list)

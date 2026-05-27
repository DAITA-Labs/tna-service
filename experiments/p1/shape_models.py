"""Pydantic models capturing the shape of an opened worksheet.

Every value here is a deterministic derivative of openpyxl cell reads.
Row / column indices are 1-indexed everywhere (matching openpyxl).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from experiments.specs.enums import PliAxis, PliMode, ValuePattern


# =============================================================================
# Geometric primitives
# =============================================================================


class Rect(BaseModel):
    """An axis-aligned rectangle of cells, with density score."""
    r0:      int                      # top row, 1-indexed
    c0:      int                      # left col, 1-indexed
    r1:      int                      # bottom row, inclusive
    c1:      int                      # right col, inclusive
    density: float = Field(ge=0.0, le=1.0)
    area:    int                      # (r1-r0+1) * (c1-c0+1)


class BlankRun(BaseModel):
    """A contiguous run of mostly-blank rows (or cols), inclusive."""
    start: int
    end:   int
    axis:  str = "row"                # "row" | "col"


class HeaderCandidate(BaseModel):
    """A row that might be a header row, with a score and the source signal."""
    row:    int
    score:  float
    signal: str                       # "text_density" | "vocab" | "styled" | "merged"


class ColumnDtypeProfile(BaseModel):
    """Pct-of-data-rows breakdown per dtype, for one column."""
    column:    int
    date_pct:  float = 0.0
    int_pct:   float = 0.0
    str_pct:   float = 0.0
    blank_pct: float = 0.0
    n_rows:    int   = 0              # how many data rows the profile saw
    pattern:   ValuePattern = ValuePattern.BLANK


class CellRef(BaseModel):
    """A 1-indexed cell coordinate with optional A1 spelling."""
    row:    int
    col:    int
    a1:     str = ""

    @classmethod
    def from_rc(cls, row: int, col: int) -> "CellRef":
        from openpyxl.utils.cell import get_column_letter
        return cls(row=row, col=col, a1=f"{get_column_letter(col)}{row}")


class MergedRange(BaseModel):
    r0: int
    c0: int
    r1: int
    c1: int


class RepeatedLabelHit(BaseModel):
    row:   int
    col:   int
    text:  str
    pattern: str                      # which regex matched


# =============================================================================
# Top-level shape summary
# =============================================================================


class ShapeSummary(BaseModel):
    """All deterministic shape facts about a worksheet.

    The classifier reads this; tools that follow (Identifier/Stage/Metadata
    extractors) will also read this in later probes.

    Fields are populated by run_p1.py via shape_tools.* function calls.
    Anything missing should default to a safe empty (None/0/[]).
    """
    # Identifying info
    file:                str
    sheet_name:          str

    # Dimensions
    total_rows:          int
    total_cols:          int
    total_cells:         int           # rows * cols (logical)
    non_blank_cells:     int           # how many were non-blank

    # Row / col density (one entry per row/col)
    row_density:         list[float]   = Field(default_factory=list)
    col_density:         list[float]   = Field(default_factory=list)

    # Rectangle outputs (default variant; other variants live alongside)
    rectangles:          list[Rect]    = Field(default_factory=list)
    biggest_rect:        Rect | None   = None

    # Blank runs
    blank_runs_row:      list[BlankRun] = Field(default_factory=list)
    blank_runs_col:      list[BlankRun] = Field(default_factory=list)

    # Header candidates
    header_candidates:   list[HeaderCandidate] = Field(default_factory=list)
    best_header_row:     int | None   = None

    # Dtype profile per column inside biggest_rect
    col_profiles:        list[ColumnDtypeProfile] = Field(default_factory=list)

    # Cell-level signals
    merged_ranges:       list[MergedRange] = Field(default_factory=list)
    hyperlinks_count:    int           = 0
    formula_cells:       list[CellRef] = Field(default_factory=list)
    frozen_pane_anchor:  CellRef | None = None
    repeated_labels:     list[RepeatedLabelHit] = Field(default_factory=list)

    # Identifier / stage / metadata signal hits (cell-level vocab matches)
    identifier_hits:     list[dict]    = Field(default_factory=list)
    stage_hits:          list[dict]    = Field(default_factory=list)
    metadata_hits:       list[dict]    = Field(default_factory=list)
    # Adjacency-based KV pairs (label-text cell with a non-text value next to it)
    kv_adjacencies:      int           = 0

    # Bookkeeping
    notes:               list[str]     = Field(default_factory=list)


# =============================================================================
# Variant outputs (so the report can render them side-by-side)
# =============================================================================


class DensityVariants(BaseModel):
    """compute_density A/B/C side-by-side."""
    by_non_blank_row:        list[float] = Field(default_factory=list)
    by_non_blank_col:        list[float] = Field(default_factory=list)
    by_content_row:          list[float] = Field(default_factory=list)
    by_content_col:          list[float] = Field(default_factory=list)
    by_dtype_weighted_row:   list[float] = Field(default_factory=list)
    by_dtype_weighted_col:   list[float] = Field(default_factory=list)


class RectangleVariants(BaseModel):
    flood:    list[Rect] = Field(default_factory=list)
    threshold: list[Rect] = Field(default_factory=list)
    hybrid:   list[Rect] = Field(default_factory=list)


class BlankRunVariants(BaseModel):
    strict:    list[BlankRun] = Field(default_factory=list)
    relaxed:   list[BlankRun] = Field(default_factory=list)
    threshold: list[BlankRun] = Field(default_factory=list)


class HeaderCandidateVariants(BaseModel):
    text_density: list[HeaderCandidate] = Field(default_factory=list)
    vocab:        list[HeaderCandidate] = Field(default_factory=list)
    styled:       list[HeaderCandidate] = Field(default_factory=list)
    merged:       list[HeaderCandidate] = Field(default_factory=list)


# =============================================================================
# Classification output
# =============================================================================


class CheckResult(BaseModel):
    """One classification check's outcome."""
    name:       str
    passes:     bool
    vote:       str | None = None        # "row_per_pli" | ... | None
    confidence: float = 0.0
    evidence:   dict[str, Any] = Field(default_factory=dict)


class SheetClassification(BaseModel):
    """Aggregate classification across all checks."""
    is_relevant:           bool
    relevance_checks:      list[CheckResult] = Field(default_factory=list)
    pli_mode:              PliMode | None = None
    pli_axis:              PliAxis | None = None
    mode_votes:            dict[str, float] = Field(default_factory=dict)
    axis_votes:            dict[str, float] = Field(default_factory=dict)
    mode_check_results:    list[CheckResult] = Field(default_factory=list)
    axis_check_results:    list[CheckResult] = Field(default_factory=list)
    needs_classifier_judge: bool = False
    mode_margin:           float = 0.0
    axis_margin:           float = 0.0
    notes:                 list[str] = Field(default_factory=list)

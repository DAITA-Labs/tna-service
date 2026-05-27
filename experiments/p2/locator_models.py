"""Probe-internal Pydantic models for P2.

These are wider than the final SheetLevelPlan schemas — they carry every
deterministic signal the extractor produced so the report can audit each
decision. Re-export the canonical schemas (FieldLocator / ReadPattern) for
convenience.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Re-exports — anything consuming the probe should be able to import these
# without reaching into experiments.specs.
from experiments.specs.schemas import (  # noqa: F401
    FieldLocator,
    PliEnumerationPlan,
    PliGroup,
    ReadPattern,
    SheetLevelPlan,
)
from experiments.specs.enums import (  # noqa: F401
    FieldScope,
    PliAxis,
    PliMode,
    ReadDirection,
)


# =============================================================================
# Per-finding detection record
# =============================================================================


class DetectedFieldLocation(BaseModel):
    """One candidate the deterministic search emitted for a spec.

    `kind` is the structural shape the candidate represents:
      - "kv"             — a label cell next to a value cell (horizontal pair)
      - "kv_vertical"    — a label cell with the value below it
      - "column_header"  — header cell at top of a column; the column is the
                           value-bearing "anchor"; values live in the rows
                           below.
    """
    canonical:        str
    kind:             str                 # "kv" | "kv_vertical" | "column_header"
    label_cell:       str                 # A1 ref
    label_text:       str
    label_row:        int
    label_col:        int
    # For kv: a single value cell. For column_header: the anchor cell is the
    # header itself; the *column* is the value bearer.
    value_cell:       str | None = None   # A1 ref of the value (or anchor for column)
    value_row:        int | None = None
    value_col:        int | None = None
    value:            Any = None
    observed_dtype:   str = "blank"       # "int" | "date" | "str" | "blank"

    # Scoring
    label_score:      float = 0.0
    value_score:      float = 0.0
    combined_score:   float = 0.0
    label_signal:     str = ""            # "vocab" | "fuzzy" | "jaccard"

    # Column-header specifics — populated when kind=="column_header"
    column_values:    list[Any] = Field(default_factory=list)
    column_value_rows: list[int] = Field(default_factory=list)

    evidence:         list[str] = Field(default_factory=list)


class ScopeDecision(BaseModel):
    """The scope detector's output for one canonical."""
    canonical:        str
    scope:            FieldScope
    chosen:           DetectedFieldLocation | None = None
    competing:        list[DetectedFieldLocation] = Field(default_factory=list)
    reason:           str = ""
    confidence:       float = Field(ge=0.0, le=1.0, default=0.0)


class IdentifierExtractionResult(BaseModel):
    """The probe's per-file output bundle."""
    file:             str
    sheet_name:       str
    pli_mode:         PliMode | None = None
    pli_count_label:  int = 0             # from the labels file
    candidates_per_canonical: dict[str, list[DetectedFieldLocation]] = Field(
        default_factory=dict,
    )
    scope_decisions:  dict[str, ScopeDecision] = Field(default_factory=dict)
    field_locators:   dict[str, FieldLocator] = Field(default_factory=dict)
    warnings:         list[str] = Field(default_factory=list)

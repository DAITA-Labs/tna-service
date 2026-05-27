"""All enums for the three-area extraction design.

Single source of truth. Every component, tool, spec, judge, and prompt
references these. To add a new value: add it here first, then update specs
that should use it.
"""
from __future__ import annotations

from enum import Enum


# =============================================================================
# Pipeline-level enums
# =============================================================================


class PliMode(str, Enum):
    """How PLIs are distributed across a sheet.

    NOTE: PliMode is the COARSE classification (one of three). The finer
    structure — direction, scope, hybrid groupings — is captured by
    PliAxis + FieldScope + ReadDirection in the PliEnumerationPlan.
    """
    ROW_PER_PLI     = "row_per_pli"
    SHEET_IS_PLI    = "sheet_is_pli"
    SECTION_PER_PLI = "section_per_pli"


class PliAxis(str, Enum):
    """Direction along which PLIs are laid out in the sheet.

    Each value implies a different iteration pattern for apply_plan:
      ROW         — apply_plan iterates rows; each row anchors one PLI
      COLUMN      — apply_plan iterates columns; each column anchors one PLI
      WHOLE_SHEET — exactly one PLI; the entire sheet describes it
      SECTION     — multiple PLI sub-sheets; apply_plan recurses per section

    A sheet's PliAxis may differ from PliMode classification — e.g. a sheet
    classified as ROW_PER_PLI mode might still be COLUMN_WISE in direction
    (transposed table). The axis is the authoritative iteration signal.
    """
    ROW         = "row"
    COLUMN      = "column"
    WHOLE_SHEET = "whole_sheet"
    SECTION     = "section"


class FieldScope(str, Enum):
    """Scope at which a field's value applies across PLIs.

    SHEET — one value applies to ALL PLIs in the sheet. Read once; broadcast.
            Typical for buyer, season, ex_factory_date (when sheet-level).
    GROUP — one value applies to a GROUP of consecutive PLIs in the sheet.
            Typical for hybrid layouts: first 3 PLIs share an io_number;
            next 4 share a different io_number; etc. Groups are themselves
            detected and named (group_id).
    PLI   — one value per PLI. The default for most identifiers and stages.

    A single sheet can have fields at MULTIPLE scopes simultaneously.
    """
    SHEET = "sheet"
    GROUP = "group"
    PLI   = "pli"


class ReadDirection(str, Enum):
    """How apply_plan walks from a PLI anchor to a field's value cell.

    SAME_ROW    — value lives at (pli_anchor_row, fixed_col).
                  Used when axis=ROW and field is PLI-scoped.
    SAME_COLUMN — value lives at (fixed_row, pli_anchor_col).
                  Used when axis=COLUMN (transposed) and field is PLI-scoped.
    OFFSET      — value lives at (pli_anchor + delta_row, pli_anchor + delta_col).
                  Used when value is at a constant offset from the PLI anchor
                  (e.g. a SECTION_PER_PLI block where each section has
                  identifier cells at fixed (+1, +2) from the section header).
    FIXED       — value lives at a hard-coded cell, ignoring PLI anchor.
                  Used for SHEET-scoped fields.
    """
    SAME_ROW    = "same_row"
    SAME_COLUMN = "same_column"
    OFFSET      = "offset"
    FIXED       = "fixed"


class Area(str, Enum):
    """The three top-level areas of a SheetLevelPlan."""
    IDENTIFIERS = "identifiers"
    STAGES      = "stages"
    METADATA    = "metadata"


# =============================================================================
# Matching enums — used by FieldSpec to drive find_field_locations
# =============================================================================


class LabelMatchMode(str, Enum):
    """How loosely a field's label is allowed to match.

    HARD   = exact alias (case-insensitive, normalized whitespace)
    MEDIUM = HARD OR rapidfuzz ratio >= 90 OR token-jaccard >= 0.7
    SOFT   = MEDIUM OR rapidfuzz ratio >= 70 OR token-jaccard >= 0.5
    """
    HARD   = "hard"
    MEDIUM = "medium"
    SOFT   = "soft"


class ValueDtype(str, Enum):
    """Expected dtype of the adjacent value cell."""
    INT  = "int"
    DATE = "date"
    STR  = "str"
    ANY  = "any"


class ValueDtypeMode(str, Enum):
    """How strictly the value-dtype filter applies.

    HARD   = wrong dtype rejects the candidate
    MEDIUM = wrong dtype reduces the candidate's score
    SOFT   = dtype only used to break ties between equal label scores
    """
    HARD   = "hard"
    MEDIUM = "medium"
    SOFT   = "soft"


class ValuePattern(str, Enum):
    """Finer-grained value pattern (richer than dtype).

    Produced by ShapeSummary.value_pattern_per_col. Specs declare which
    patterns they ALLOW in `value_constraints.allowed_patterns`.
    """
    DATE       = "date"
    INT_SMALL  = "int_small"      # 0..10 — likely size or count
    INT_MEDIUM = "int_medium"     # 10..1000 — could be qty or short code
    INT_LARGE  = "int_large"      # 1000+ — likely large qty or numeric io
    CODE_ALNUM = "code_alnum"     # short alphanumeric tokens (ST-001, FA-12)
    NAME_TEXT  = "name_text"      # longer descriptive text
    BLANK      = "blank"
    MIXED      = "mixed"


# =============================================================================
# Judge enums
# =============================================================================


class Verdict(str, Enum):
    """Per-finding judge verdict — a RECOMMENDATION, not a final decision.

    The recommendation is fed into the phase judge alongside other findings;
    the phase judge is the arbiter that produces the final findings.
    """
    YES                = "yes"                  # deterministic match looks correct
    NO                 = "no"                   # deterministic match looks wrong
    SWAP               = "swap"                 # right cell, wrong canonical
    REFINE_SPEC        = "refine_spec"          # match holds, but spec needs strengthening
    NEEDS_MORE_CONTEXT = "needs_more_context"   # I can't decide alone — escalate


class PhaseAction(str, Enum):
    """Phase-judge action — the arbiter's decision for the whole component.

    ACCEPT     = final findings produced; ship them
    RE_EXTRACT = re-run the deterministic pass with refinement hints
    ESCALATE   = ship with warnings; needs human review
    """
    ACCEPT     = "accept"
    RE_EXTRACT = "re_extract"
    ESCALATE   = "escalate"


class FieldConfidence(str, Enum):
    """Discretised confidence band — used when rendering prompts.

    HIGH   = >= 0.85
    MEDIUM = 0.55 .. 0.85
    LOW    = < 0.55
    """
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class JudgeType(str, Enum):
    """Catalog of judge agents. Each has its own prompt template + schema."""
    FIELD_FINDING    = "field_finding"
    PHASE_IDENTIFIER = "phase_identifier"
    STAGE_BAND       = "stage_band"
    PHASE_STAGE      = "phase_stage"
    METADATA_KV      = "metadata_kv"
    PHASE_METADATA   = "phase_metadata"
    CLASSIFICATION   = "classification"


# =============================================================================
# Classification enums
# =============================================================================


class ClassificationCheck(str, Enum):
    """Named multi-vote classification checks (relevance + mode)."""
    # Relevance checks (required to pass)
    HAS_DATA_RECTANGLE       = "has_data_rectangle"
    NOT_NAVIGATION           = "not_navigation"
    NOT_SUMMARY              = "not_summary"
    HAS_IO_SIGNAL            = "has_io_signal"

    # Mode-decision checks (each votes for a PliMode)
    TALL_TABLE_SHAPE         = "tall_table_shape"
    DATE_ARENA_DOMINANCE     = "date_arena_dominance"
    HEADER_CONTINUITY        = "header_continuity"
    KV_ANCHOR_DENSITY        = "kv_anchor_density"
    KV_PAIR_COUNT            = "kv_pair_count"
    SECTION_SPLIT_BY_BLANKS  = "section_split_by_blanks"
    SECTION_REPEAT_PATTERN   = "section_repeat_pattern"
    STYLED_HEADER_DIST       = "styled_header_dist"
    FROZEN_PANE_BELOW_ROW_1  = "frozen_pane_below_row_1"


class CheckOutcome(str, Enum):
    """One classification check's outcome."""
    PASS      = "pass"
    FAIL      = "fail"
    AMBIGUOUS = "ambiguous"

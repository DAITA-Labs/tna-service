"""Pydantic schemas for judge inputs/outputs — structured JSON contract.

Every LLM judge agent returns one of these. Pydantic enforces the enum +
field constraints, so a malformed LLM response fails at parse time rather
than corrupting the plan.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import FieldScope, PhaseAction, PliAxis, PliMode, ReadDirection, Verdict


# =============================================================================
# Inputs (what each judge SEES)
# =============================================================================


class SheetSample(BaseModel):
    """A bounded slice of the sheet shown to a judge for visual context.

    Different judges receive different slices (see judge_type below). The
    slice is rendered as a fixed-width text grid with cell coordinates so
    the LLM can correlate it with the finding's cell references.

    Bounded to ~200 cells total to keep prompt cost under control.
    """
    judge_type:       str                          # "field_finding" | "stage_band" | ...
    rows:             list["SampleRow"]            # rendered rows; max ~20
    truncated:        bool                = False  # true if sheet was bigger than the slice
    full_row_count:   int                          # sheet height (for context)
    full_col_count:   int                          # sheet width


class SampleRow(BaseModel):
    """One row in a sheet sample. Row number is 1-indexed (matches openpyxl)."""
    row_number:  int
    cells:       list["SampleCell"]


class SampleCell(BaseModel):
    """One cell in a sheet sample. Empty cells included for layout fidelity."""
    column:    str                                  # "A", "B", ...
    value:     Any                                  # str/int/date/None
    is_merged: bool = False
    is_bold:   bool = False


class FindingForJudge(BaseModel):
    """A single finding presented to a judge."""
    canonical:               str
    pattern_used:            str
    label_cell:              str
    label_text:              str
    value_cell:              str
    value:                   Any
    value_dtype_observed:    str
    confidence:              float = Field(ge=0.0, le=1.0)
    evidence:                list[str] = Field(default_factory=list)
    competing_candidates:    list[str] = Field(default_factory=list)


class FieldFindingJudgeInput(BaseModel):
    """Input to FieldFindingJudge — one finding at a time."""
    finding:        FindingForJudge
    spec_summary:   "SpecSummary"          # rendered patterns/anti-patterns/etc.
    sheet_sample:   SheetSample | None = None   # local window around the finding


class JudgmentRec(BaseModel):
    """Per-finding judge OUTPUT — recommendation, not a final decision."""
    verdict:    Verdict
    reason:     str = Field(max_length=300)
    target:     str | None = None              # canonical name when verdict=SWAP
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class FindingWithJudgment(BaseModel):
    """A finding bundled with its per-finding judgment, fed to the phase judge."""
    finding:    FindingForJudge
    judgment:   JudgmentRec | None = None      # None if not reviewed


class PhaseIdentifierJudgeInput(BaseModel):
    """Input to IdentifierPhaseJudge — arbitrates all findings together."""
    pli_mode:                PliMode | None
    shape_brief:             str
    findings_with_judgments: list[FindingWithJudgment]
    mandatory_canonicals:    list[str]
    iteration:               int = 0           # which loop are we on (0-indexed)


# =============================================================================
# Outputs (what each judge RETURNS)
# =============================================================================


class FieldFindingJudgeOutput(BaseModel):
    """FieldFindingJudge structured JSON response. Pydantic forces enums."""
    verdict:    Verdict
    reason:     str = Field(max_length=300)
    target:     str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class FinalFinding(BaseModel):
    """A finding in the phase-judge's final-findings list."""
    canonical:      str
    cell:           str
    value:          Any
    confidence:     float = Field(ge=0.0, le=1.0)
    judge_action:   str   = ""                  # "approved" | "swapped_from_X" | "added_by_phase_judge"


class PhaseIdentifierJudgeOutput(BaseModel):
    """IdentifierPhaseJudge response — the arbiter's decision."""
    action:             PhaseAction
    final_findings:     list[FinalFinding] = Field(default_factory=list)
    refinement_hints:   dict[str, Any]     = Field(default_factory=dict)  # for RE_EXTRACT
    warnings:           list[str]          = Field(default_factory=list)  # for ESCALATE
    reason:             str                = Field(max_length=500)


# =============================================================================
# Stage / Metadata / Classification judges
# =============================================================================


class StageStrip(BaseModel):
    """A horizontal STRIP within a sheet that contains stage bands.

    Why STRIPS, not just COLUMNS:
        A sheet may have ONE strip (standard ROW_PER_PLI: a single header
        row + data rows below) — OR it may have MULTIPLE strips stacked
        vertically. Stacked layouts occur when stages can't all fit on one
        row, so the supplier splits them into multiple horizontal blocks,
        each with its own header row and its own data row range.

    Each strip is a self-contained mini-extraction context.
    """
    strip_index:     int
    name_row:        int                            # row with stage name cells
    sub_label_row:   int | None = None              # row with PLAN/ACT etc. (may be absent)
    data_row_range:  tuple[int, int]                # rows holding PLI dates for this strip
    bands:           list["DetectedBand"]           # bands found within this strip


class DetectedBand(BaseModel):
    """One stage band found within a strip.

    A band is the column-range under a single contiguous header cell
    (or merged header) that represents one stage. The band's parent strip
    contributes its name_row + data_row_range; the band itself contributes
    the column_range + the raw name text.
    """
    band_index:      int
    name:            str                            # supplier's stage text, verbatim
    canonical:       str | None = None              # set iff name matched a known StageSpec alias
    column_range:    tuple[int, int]                # cols (start, end) within the strip
    plan_date_col:   int | None = None              # which col holds the plan date (if any)
    sub_columns:     list["SubColumnRef"] = Field(default_factory=list)  # canonical sub-cols
    confidence:      float = Field(ge=0.0, le=1.0)
    evidence:        list[str] = Field(default_factory=list)


class SubColumnRef(BaseModel):
    """A sub-column within a band — e.g. the 'PLAN' column under 'Sewing'."""
    column:          int
    raw_label:       str                            # verbatim sub-row text (e.g. "PLAN")
    canonical:       str | None = None              # canonical sub-field (e.g. "planned_date")


class StageBandJudgeInput(BaseModel):
    """Input to StageBandJudge — one detected band, with its strip context."""
    strip:            StageStrip                    # parent strip (provides name_row etc.)
    band:             DetectedBand                  # the specific band under review
    competing:        list[str] = Field(default_factory=list)  # nearby canonical-matching hints
    sheet_sample:     SheetSample | None = None     # rows around band — header + a few data rows


class StageBandJudgeOutput(BaseModel):
    verdict:    Verdict
    reason:     str = Field(max_length=300)
    target:     str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class PhaseStageJudgeInput(BaseModel):
    pli_mode:           PliMode | None
    arena_bounds:       tuple[int, int, int, int] | None    # (upper, lower, left, right)
    bands_with_judgments: list[dict]                         # list of (band, judgment) bundles
    iteration:          int = 0


class FinalStage(BaseModel):
    """The simplified Stage shape — what gets shipped per detected stage.

    OPEN VOCABULARY: `name` is the supplier's stage text VERBATIM from the
    sheet. `canonical` is OPTIONAL — set only when `name` matched a known
    StageSpec alias; otherwise None. Downstream consumers MUST tolerate
    `canonical=None` (new TNAs produce new stages).

    Only `name` and `plan_date` are first-class. EVERY other sub-column the
    deterministic layer captured (actual_date, approval_date, received_date,
    remarks, sub-quantity, unknown supplier-specific sub-cols) gets folded
    into `stage_metadata`. This keeps the Stage schema stable across
    supplier variants — unknown sub-columns become metadata entries instead
    of schema mismatches.
    """
    name:            str                       # supplier's text, verbatim
    canonical:       str | None        = None  # known canonical iff matched; else None
    plan_date:       Any                       # ISO date or null
    plan_date_col:   int | None        = None  # which col held the plan date
    column_range:    tuple[int, int]   | None = None  # (start_col, end_col) of the band
    stage_metadata:  dict[str, Any]    = Field(default_factory=dict)
                                                # e.g. {"actual_date": "2026-03-05",
                                                #       "received_date": "2026-02-20",
                                                #       "remarks": "delayed",
                                                #       "<unknown_raw_label>": "..."}
    judge_action:    str               = ""    # "approved" | "swapped_from_X" | ...


class PhaseStageJudgeOutput(BaseModel):
    action:             PhaseAction
    final_stages:       list[FinalStage] = Field(default_factory=list)
    refinement_hints:   dict[str, Any]   = Field(default_factory=dict)
    warnings:           list[str]        = Field(default_factory=list)
    reason:             str              = Field(max_length=500)


class MetadataKVJudgeInput(BaseModel):
    label_cell:    str
    label_text:    str
    value_cell:    str
    value:         Any
    candidates:    list[str]                    # possible canonicals
    evidence:      list[str] = Field(default_factory=list)


class MetadataKVJudgeOutput(BaseModel):
    verdict:    Verdict
    reason:     str = Field(max_length=300)
    target:     str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class PhaseMetadataJudgeInput(BaseModel):
    kvs_with_judgments: list[dict]
    iteration:          int = 0


class PhaseMetadataJudgeOutput(BaseModel):
    action:             PhaseAction
    final_metadata:     list[MetadataEntry] = Field(default_factory=list)
    refinement_hints:   dict[str, Any]      = Field(default_factory=dict)
    warnings:           list[str]           = Field(default_factory=list)
    reason:             str                 = Field(max_length=500)


class ClassificationJudgeInput(BaseModel):
    """Input to ClassificationJudge — fires only on tied mode votes."""
    shape_brief:    str
    vote_breakdown: dict[str, float]            # {pli_mode: weighted_score}
    evidence_per_check: dict[str, str]


class ClassificationJudgeOutput(BaseModel):
    chosen_mode:    PliMode
    confidence:     float = Field(ge=0.0, le=1.0)
    reason:         str = Field(max_length=300)


# =============================================================================
# Helper schema used in prompts
# =============================================================================


class SpecSummary(BaseModel):
    """Compact rendering of a spec for in-prompt display.

    Built from FieldSpec / StageSpec / SubfieldSpec via render.spec_summary().
    """
    canonical:      str
    description:    str
    patterns:       list[str]
    anti_patterns:  list[str]
    examples:       list[str]
    mandatory:      bool = False


# =============================================================================
# PLI Enumeration Plan — HOW to walk the sheet
# =============================================================================


class ReadPattern(BaseModel):
    """How apply_plan reaches a value cell from a PLI anchor.

    Resolution rules (interpreted by apply_plan):
      direction=FIXED       → read at `fixed_cell`; ignore pli_anchor
      direction=SAME_ROW    → read at (pli_anchor_row, anchor_col)
      direction=SAME_COLUMN → read at (anchor_row, pli_anchor_col)
      direction=OFFSET      → read at (pli_anchor + offset_row,
                                       pli_anchor + offset_col)
    """
    direction:    ReadDirection
    anchor_col:   str | None = None   # required for SAME_ROW (e.g. "C")
    anchor_row:   int | None = None   # required for SAME_COLUMN
    offset_row:   int        = 0      # for OFFSET
    offset_col:   int        = 0
    fixed_cell:   str | None = None   # required for FIXED (e.g. "B2")


class FieldLocator(BaseModel):
    """Where a field's value is, plus how to read it for each PLI.

    Examples:

      buyer (sheet-scoped, single cell):
        FieldLocator(canonical="buyer", scope=SHEET,
                     read_pattern=ReadPattern(direction=FIXED, fixed_cell="C3"))

      io_number (group-scoped, varies by group):
        FieldLocator(canonical="io_number", scope=GROUP, group_resolved=True,
                     read_pattern=None)   # cell ref lives on PliGroup

      style_code (per-PLI, ROW direction):
        FieldLocator(canonical="style_code", scope=PLI,
                     read_pattern=ReadPattern(direction=SAME_ROW, anchor_col="A"))

      sewing.plan_date (per-PLI stage, ROW direction):
        FieldLocator(canonical="stages.sewing.plan_date", scope=PLI,
                     read_pattern=ReadPattern(direction=SAME_ROW, anchor_col="D"))

      io_number on a column-wise sheet (per-PLI, COLUMN direction):
        FieldLocator(canonical="io_number", scope=PLI,
                     read_pattern=ReadPattern(direction=SAME_COLUMN, anchor_row=2))
    """
    canonical:       str
    scope:           FieldScope
    read_pattern:    ReadPattern | None = None    # None when scope=GROUP (group resolves cell)
    group_id:        str | None = None             # set for scope=GROUP
    confidence:      float = Field(ge=0.0, le=1.0, default=1.0)
    notes:           str = ""


class PliGroup(BaseModel):
    """A group of PLIs sharing GROUP-scoped field values.

    Used when one or more identifier/metadata fields apply to a CONTIGUOUS
    subset of PLIs (e.g. first 3 PLIs share io_number 1063; next 4 share
    io_number 1064). Each GROUP-scoped field has a single value cell on
    the group, which apply_plan reads once and broadcasts to every PLI in
    the group.
    """
    group_id:      str
    pli_anchors:   list[int]                       # row OR col indices, axis-dependent
    shared_fields: dict[str, str] = Field(default_factory=dict)
                                                    # {canonical: cell_ref}


class PliEnumerationPlan(BaseModel):
    """The iteration contract for apply_plan.

    Tells apply_plan:
      - WHICH axis to walk (rows, columns, single, or sections)
      - WHICH positions are PLI anchors along that axis
      - HOW MANY PLIs to produce
      - WHICH groups (if any) carve up those anchors

    apply_plan walks pli_anchors in order. For each anchor, it reads each
    FieldLocator using the axis + locator's read_pattern + group membership.
    """
    axis:         PliAxis
    pli_anchors:  list[int]                         # axis-dependent (row idx for ROW etc.)
    pli_count:    int
    groups:       list[PliGroup] = Field(default_factory=list)
    confidence:   float = Field(ge=0.0, le=1.0, default=1.0)
    notes:        str = ""


class MetadataEntry(BaseModel):
    """One metadata k:v entry — OPEN SCHEMA.

    Metadata is genuinely flexible: ANY label-value pair found on the sheet
    that is NOT one of the 9 identifier canonicals and NOT a stage lands here.

    Design intent:
      - `key` = supplier's RAW label text, verbatim. New TNAs will produce
        entirely new keys without schema changes.
      - `canonical` = OPTIONAL. Set only when the raw label matched one of
        the METADATA_SPECS hint entries (e.g. "Buyer" → buyer). Most novel
        labels (e.g. "Treatment", "Country of Origin", "Bulk Pcs", "Buyer
        Po No") ship with canonical=None.
      - `source` = cell reference where the value was read.
      - `scope` = whether this k:v applies to ALL PLIs (SHEET), a subset
        (GROUP), or one PLI (PLI). Most metadata is SHEET-scoped.

    Downstream consumers MUST handle `canonical=None`. The key is the
    primary identity; canonical is sugar.
    """
    key:        str                                # raw label text, verbatim
    value:      Any                                # value cell contents
    source:     str                                # cell ref (e.g. "K4")
    canonical:  str | None = None                  # optional known-canonical match
    scope:      FieldScope = FieldScope.SHEET      # SHEET / GROUP / PLI
    group_id:   str | None = None                  # set for scope=GROUP
    confidence: float      = Field(ge=0.0, le=1.0, default=1.0)


class SheetLevelPlan(BaseModel):
    """The complete plan a SheetClassifier + extractors produce.

    A single artifact that captures:
      - WHERE PLIs are (PliEnumerationPlan)
      - WHERE each identifier field lives (FieldLocator per canonical)
      - WHICH stages exist + how to read their plan_date per PLI
      - All loose metadata k:v entries (MetadataEntry — open schema)
      - Any warnings the pipeline accumulated

    apply_plan consumes this and produces N PLIs by iterating per
    pli_enumeration.pli_anchors and resolving each field by its locator
    (or reading metadata once per scope-rule).
    """
    pli_mode:        PliMode
    pli_enumeration: PliEnumerationPlan
    identifiers:     dict[str, FieldLocator] = Field(default_factory=dict)
    stages:          list["StageLocator"]    = Field(default_factory=list)
    metadata:        list[MetadataEntry]     = Field(default_factory=list)
    warnings:        list[str]               = Field(default_factory=list)


class StageLocator(BaseModel):
    """Where a stage's data lives + how to read plan_date per PLI.

    Each stage has a NAME (verbatim from sheet) + a PLAN_DATE locator that
    apply_plan uses to read the per-PLI date. Sub-columns (actual_date,
    received_date, remarks) get their own locators inside sub_field_locators
    and apply_plan reads them at iteration time to populate stage_metadata.
    """
    name:                  str                       # supplier verbatim
    canonical:             str | None = None
    strip_index:           int                       # which strip the stage belongs to
    column_range:          tuple[int, int]
    plan_date_locator:     FieldLocator              # how to read plan_date per PLI
    sub_field_locators:    dict[str, FieldLocator] = Field(default_factory=dict)
                                                      # raw_label → locator for that sub-col
    confidence:            float = Field(ge=0.0, le=1.0, default=1.0)


# Pydantic forward-reference resolution
SheetSample.model_rebuild()
SampleRow.model_rebuild()
StageStrip.model_rebuild()
DetectedBand.model_rebuild()
FieldFindingJudgeInput.model_rebuild()
StageBandJudgeInput.model_rebuild()
MetadataEntry.model_rebuild()
SheetLevelPlan.model_rebuild()
StageLocator.model_rebuild()

"""Bridge artifact schemas — typed contracts between agents and Python.

Each artifact is produced by an agent (Inspector / BoundaryFinder /
Locators / Validators) or consumed by the appliers / reconciler.
extra="ignore" everywhere so envelope additions stay backward-compatible.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.stage_layout_mode import StageLayoutMode
from app.enums.location_pattern import LocationPattern
from app.enums.validation_severity import ValidationSeverity


# ===== Inspector / fingerprint =====


class WorkbookSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheet_count: int
    sheet_names: list[str]
    file_size_kb: int


class StructuralFingerprint(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheets_appear_parallel: bool
    has_scattered_metadata: bool
    has_tabular_header_band: bool
    multi_row_headers: bool
    has_vertical_merges_in_data: bool
    has_totals_rows: bool
    has_noise_sheets: bool
    multi_band_stages_per_pli: bool
    stage_layout_mode: StageLayoutMode
    sample_evidence: dict[str, Any] = Field(default_factory=dict)


class InspectorReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workbook_summary: WorkbookSummary
    fingerprint: StructuralFingerprint
    candidate_relevant_sheets: list[str] = Field(default_factory=list)
    notes: str | None = None


# ===== PLI Boundary Finder =====


class PLIBoundaries(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheet: str
    pattern: BoundaryPattern
    data_start_row: int | None = None
    data_end_row: int | None = None
    total_row_indicator_col: str | None = None
    total_row_indicator_value: str | None = None
    sheet_iter: list[str] = Field(default_factory=list)
    grouping_columns: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


# ===== Field Locator =====


class FieldLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    field: str
    pattern: LocationPattern
    column: str | None = None
    data_start_row: int | None = None
    data_end_row: int | None = None
    anchor_cell: str | None = None
    value_offset_rc: tuple[int, int] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class PLIMetadataLocation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    pattern: LocationPattern
    column: str | None = None
    data_start_row: int | None = None
    data_end_row: int | None = None
    anchor_cell: str | None = None
    value_offset_rc: tuple[int, int] | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class FieldMap(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheet: str
    locations: list[FieldLocation] = Field(default_factory=list)
    metadata_locations: list[PLIMetadataLocation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ===== Stage Locator =====


class StageColumn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    name_cell: str
    primary_col: str
    sub_columns: dict[str, str] = Field(default_factory=dict)


class StageBand(BaseModel):
    model_config = ConfigDict(extra="ignore")
    section_name: str | None = None
    section_anchor_cell: str | None = None
    name_row: int
    layout_mode: StageLayoutMode
    sub_header_row: int | None = None
    data_start_row: int | None = None
    data_end_row: int | None = None
    sub_rows: dict[str, int] = Field(default_factory=dict)
    stage_columns: list[StageColumn]
    confidence: float = Field(ge=0.0, le=1.0)


class StageBandSet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sheet: str
    bands: list[StageBand] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


# ===== Validation arm =====


class ValidationFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    check: str
    severity: ValidationSeverity
    message: str
    pli_index: int | None = None
    field: str | None = None


class ValidationFindings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    findings: list[ValidationFinding] = Field(default_factory=list)

    @property
    def warn_rate(self) -> float:
        if not self.findings:
            return 0.0
        n_warn = sum(
            1 for f in self.findings
            if f.severity in (ValidationSeverity.WARN, ValidationSeverity.ERROR)
        )
        return n_warn / len(self.findings)


# ===== SheetRowPlanner artifacts =====

from app.enums.row_role import RowRole, SubRowRole
from app.enums.pli_mode import PliMode
from app.enums.stage_scope import StageScope


class SheetSignals(BaseModel):
    """Raw structural signals collected by SheetSurveyor for a sheet."""
    model_config = ConfigDict(extra="ignore")
    sheet: str
    max_row: int
    max_col: int
    merges: list[tuple[int, int, int, int]] = Field(default_factory=list)
    identity_col_candidates: list[str] = Field(default_factory=list)
    header_vocab_hits: dict[str, list[str]] = Field(default_factory=dict)
    date_typed_cols: list[str] = Field(default_factory=list)
    blank_run_gaps: list[tuple[int, int]] = Field(default_factory=list)
    kv_label_hits: list[tuple[str, str]] = Field(default_factory=list)


class RowSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    idx: int
    role: RowRole
    anchor_idx: int | None = None
    group_id: int | None = None
    sub_row_role: SubRowRole | None = None


class KVAnchor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label_cell: str
    value_cell: str
    field: str


class StageBandSpec(BaseModel):
    """Where one stage band lives on a sheet.

    `sub_rows` keys are SubRowRole values (str); `stage_cols` maps a stage's
    display name to its column letter.
    """
    model_config = ConfigDict(extra="ignore")
    name: str
    name_cell: str
    sub_header_row: int
    sub_rows: dict[str, int] = Field(default_factory=dict)
    stage_cols: dict[str, str] = Field(default_factory=dict)
    layout_mode: str = "wide_sub_columns"


class PliBlock(BaseModel):
    """A sub-rectangle of a sheet representing one PLI in SECTION_PER_PLI mode."""
    model_config = ConfigDict(extra="ignore")
    id: int
    bbox: tuple[int, int]
    identity: list[KVAnchor] = Field(default_factory=list)
    stage_bands: list[StageBandSpec] = Field(default_factory=list)


class SheetPlan(BaseModel):
    """The unified plan produced by SheetRowPlanner.

    `rows` is populated when pli_mode = ROW_PER_PLI.
    `pli_blocks` is populated when pli_mode = SECTION_PER_PLI.
    `kv_anchors` is populated when pli_mode = SHEET_IS_PLI (and also on hybrid
    sheets where workbook-header KV applies to every PLI emitted from `rows`).
    """
    model_config = ConfigDict(extra="ignore")
    sheet: str
    pli_mode: PliMode
    identity_column: str | None = None
    header_rows: list[int] = Field(default_factory=list)
    rows: list[RowSpec] = Field(default_factory=list)
    pli_blocks: list[PliBlock] = Field(default_factory=list)
    kv_anchors: list[KVAnchor] = Field(default_factory=list)
    stage_bands: list[StageBandSpec] = Field(default_factory=list)
    stage_scope: StageScope = StageScope.SHEET_LEVEL
    confidence: float = 1.0

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

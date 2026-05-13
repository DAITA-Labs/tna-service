"""Tests for app/models/artifacts — bridge schemas."""
from app.enums.location_pattern import LocationPattern
from app.enums.validation_severity import ValidationSeverity
from app.models.artifacts import (
    WorkbookSummary, StructuralFingerprint, InspectorReport,
    PLIBoundaries, FieldLocation, PLIMetadataLocation, FieldMap,
    StageColumn, StageBand, StageBandSet,
    ValidationFinding, ValidationFindings,
)


def test_structural_fingerprint_stage_layout_mode_str():
    fp = StructuralFingerprint(
        sheets_appear_parallel=False, has_scattered_metadata=False,
        has_tabular_header_band=True, multi_row_headers=True,
        has_vertical_merges_in_data=False, has_totals_rows=False,
        has_noise_sheets=False, multi_band_stages_per_pli=False,
        stage_layout_mode="wide_sub_columns", sample_evidence={},
    )
    assert fp.stage_layout_mode == "wide_sub_columns"


def test_pli_boundaries_pattern_str():
    b = PLIBoundaries(sheet="S1", pattern="vertical_merge",
                     data_start_row=4, data_end_row=11,
                     grouping_columns=["B"], confidence=0.9)
    assert b.pattern == "vertical_merge"


def test_field_map_locations_and_metadata():
    fm = FieldMap(
        sheet="S1",
        locations=[FieldLocation(field="io_number", pattern=LocationPattern.COLUMN,
                                column="K", data_start_row=4, data_end_row=9,
                                confidence=0.95)],
        metadata_locations=[PLIMetadataLocation(key="cut_qty",
                                                pattern=LocationPattern.COLUMN,
                                                column="Y", data_start_row=4,
                                                data_end_row=9, confidence=0.9)],
    )
    assert fm.locations[0].field == "io_number"
    assert fm.metadata_locations[0].key == "cut_qty"


def test_stage_column_sub_columns():
    sc = StageColumn(name="Sewing", name_cell="Z2", primary_col="Z",
                    sub_columns={"end_planned": "AB", "qty": "AD"})
    assert sc.sub_columns["end_planned"] == "AB"


def test_validation_findings_warn_rate():
    fs = ValidationFindings(findings=[
        ValidationFinding(check="coverage", severity=ValidationSeverity.WARN,
                         message="low"),
        ValidationFinding(check="source_cell", severity=ValidationSeverity.INFO,
                         message="ok"),
    ])
    assert fs.warn_rate == 0.5

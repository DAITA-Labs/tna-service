"""Tests for app/services/agents/stage_locator."""
from unittest.mock import MagicMock
from app.models.artifacts import (
    StageBandSet, StageBand, StageColumn, PLIBoundaries, StructuralFingerprint,
)
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.stage_layout_mode import StageLayoutMode
from app.services.agents.stage_locator import StageLocator, SPEC


def test_spec_emits_stage_band_set():
    assert SPEC.name == "stage_locator"
    assert SPEC.output_schema is StageBandSet


def test_run_returns_stage_band_set():
    fake_set = StageBandSet(
        sheet="Sheet 1",
        bands=[StageBand(
            section_name=None, name_row=2,
            layout_mode=StageLayoutMode.WIDE_SUB_COLUMNS,
            sub_header_row=3, data_start_row=4, data_end_row=9,
            stage_columns=[StageColumn(
                name="Sewing", name_cell="Z2", primary_col="Z",
                sub_columns={"end_planned": "AB", "qty": "AD"},
            )],
            confidence=0.9,
        )],
        confidence=0.9,
    )
    fp = StructuralFingerprint(
        sheets_appear_parallel=False, has_scattered_metadata=False,
        has_tabular_header_band=True, multi_row_headers=True,
        has_vertical_merges_in_data=False, has_totals_rows=False,
        has_noise_sheets=False, multi_band_stages_per_pli=False,
        stage_layout_mode=StageLayoutMode.WIDE_SUB_COLUMNS, sample_evidence={},
    )
    boundaries = PLIBoundaries(sheet="Sheet 1", pattern=BoundaryPattern.ONE_ROW_PER_PLI,
                              data_start_row=4, data_end_row=9, confidence=0.9)
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_set
    sl = StageLocator(llm=MagicMock())
    sl.runner = fake_runner
    out = sl.run(workbook_ctx=MagicMock(), sheet="Sheet 1",
                fingerprint=fp, boundaries=boundaries)
    assert out["stage_band_set"].bands[0].stage_columns[0].name == "Sewing"

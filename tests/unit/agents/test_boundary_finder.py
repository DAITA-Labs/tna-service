"""Tests for app/services/agents/boundary_finder."""
from unittest.mock import MagicMock
from app.models.artifacts import PLIBoundaries, StructuralFingerprint
from app.enums.boundary_pattern import BoundaryPattern
from app.enums.stage_layout_mode import StageLayoutMode
from app.services.agents.boundary_finder import BoundaryFinder, SPEC


def test_spec_emits_pli_boundaries():
    assert SPEC.name == "boundary_finder"
    assert SPEC.output_schema is PLIBoundaries


def test_run_returns_boundaries():
    fake_b = PLIBoundaries(
        sheet="Sheet 1", pattern=BoundaryPattern.VERTICAL_MERGE,
        data_start_row=4, data_end_row=11,
        grouping_columns=["B"], confidence=0.9,
    )
    fp = StructuralFingerprint(
        sheets_appear_parallel=False, has_scattered_metadata=False,
        has_tabular_header_band=True, multi_row_headers=False,
        has_vertical_merges_in_data=True, has_totals_rows=False,
        has_noise_sheets=False, multi_band_stages_per_pli=False,
        stage_layout_mode=StageLayoutMode.WIDE_SUB_COLUMNS, sample_evidence={},
    )
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_b
    bf = BoundaryFinder(llm=MagicMock())
    bf.runner = fake_runner
    out = bf.run(workbook_ctx=MagicMock(), sheet="Sheet 1", fingerprint=fp)
    assert out["boundaries"].pattern == BoundaryPattern.VERTICAL_MERGE
    assert out["boundaries"].data_end_row == 11

"""Tests for app/services/agents/layout_fingerprinter."""
from unittest.mock import MagicMock
from app.models.artifacts import StructuralFingerprint
from app.enums.stage_layout_mode import StageLayoutMode
from app.services.agents.layout_fingerprinter import LayoutFingerprinter, SPEC


def test_spec_emits_structural_fingerprint():
    assert SPEC.name == "layout_fingerprinter"
    assert SPEC.output_schema is StructuralFingerprint


def test_run_returns_fingerprint():
    fake_fp = StructuralFingerprint(
        sheets_appear_parallel=False,
        has_scattered_metadata=False,
        has_tabular_header_band=True,
        multi_row_headers=True,
        has_vertical_merges_in_data=False,
        has_totals_rows=False,
        has_noise_sheets=False,
        multi_band_stages_per_pli=False,
        stage_layout_mode=StageLayoutMode.WIDE_SUB_COLUMNS,
        sample_evidence={},
    )
    fake_runner = MagicMock()
    fake_runner.run.return_value = fake_fp
    fp = LayoutFingerprinter(llm=MagicMock())
    fp.runner = fake_runner  # override
    out = fp.run(workbook_ctx=MagicMock(), sheet="Sheet 1")
    assert out["fingerprint"] is fake_fp

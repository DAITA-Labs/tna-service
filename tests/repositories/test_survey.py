"""Tests for app/repositories/workbook_tools/survey."""
from app.repositories.workbook_repo import register_workbook
from app.repositories.workbook_tools.survey import list_sheets, workbook_summary


def test_list_sheets_returns_sheet_meta(dkn_file):
    ctx = register_workbook(dkn_file)
    sheets = list_sheets(ctx)
    assert len(sheets) >= 1
    sheet = sheets[0]
    assert sheet.name
    assert sheet.max_row > 0
    assert sheet.max_col > 0


def test_workbook_summary_shape(dkn_file):
    ctx = register_workbook(dkn_file)
    s = workbook_summary(ctx)
    assert s.sheet_count >= 1
    assert "20260129 DKN" in dkn_file.name
    assert s.file_size_kb > 0

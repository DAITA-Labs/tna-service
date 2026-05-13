from datetime import datetime
from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet
from app.services.planner.stage_band_detector import detect_stage_bands


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_detect_tall_sub_rows_band(tmp_path):
    """Sheet with one stage band 'Pre-Prod' covering rows 8-11
    (header row, plan row, action row, deviation row)."""
    ctx = _ctx(tmp_path, {
        "A8": "Pre-Prod TNA",
        "C8": "L/D send", "D8": "Fit send", "E8": "AW send",
        "B9": "Plan",
        "C9": datetime(2026, 3, 1),
        "D9": datetime(2026, 3, 5),
        "E9": datetime(2026, 3, 10),
        "B10": "Action",
        "C10": datetime(2026, 3, 3),
        "B11": "Deviation",
    })
    sig = survey_sheet(ctx, "S")
    bands = detect_stage_bands(ctx, "S", sig)
    assert len(bands) == 1
    band = bands[0]
    assert band.name == "Pre-Prod TNA"
    assert band.name_cell == "A8"
    assert band.sub_rows.get("plan") == 9
    assert band.sub_rows.get("action") == 10
    assert band.sub_rows.get("deviation") == 11
    assert "L/D send" in band.stage_cols
    assert band.layout_mode == "tall_sub_rows"


def test_detect_wide_sub_columns_band(tmp_path):
    """Tabular sheet where stage 'Trims Inhouse' has primary (planned) and
    'actual' columns side-by-side, with data starting at row 4."""
    ctx = _ctx(tmp_path, {
        "R2": "Trims Inhouse",
        "R3": "Plan", "S3": "Actual",
        "R4": datetime(2026, 3, 25),
        "S4": datetime(2026, 3, 26),
        "R5": datetime(2026, 4, 1),
        "S5": datetime(2026, 4, 2),
    })
    sig = survey_sheet(ctx, "S")
    bands = detect_stage_bands(ctx, "S", sig)
    assert any(b.name_cell == "R2" and b.layout_mode == "wide_sub_columns"
               for b in bands)

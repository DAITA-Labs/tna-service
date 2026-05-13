from openpyxl import Workbook
from app.repositories.workbook_repo import register_workbook, clear_cache
from app.services.planner.surveyor import survey_sheet
from app.services.planner.kv_anchor_detector import detect_kv_anchors


def _ctx(tmp_path, cells):
    clear_cache()
    wb = Workbook(); ws = wb.active; ws.title = "S"
    for addr, val in cells.items():
        ws[addr] = val
    p = tmp_path / "x.xlsx"; wb.save(p)
    return register_workbook(p)


def test_kv_label_value_horizontal(tmp_path):
    ctx = _ctx(tmp_path, {
        "A3": "Date :", "B3": "2026-04-17",
        "A4": "Job No", "B4": 63315,
        "A5": "Quantity", "B5": 254886,
    })
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    by_lbl = {k.label_cell: k for k in kvs}
    assert by_lbl["A4"].value_cell == "B4"
    assert by_lbl["A5"].value_cell == "B5"


def test_kv_label_value_vertical(tmp_path):
    """Some sheets put labels above values rather than to the left."""
    ctx = _ctx(tmp_path, {
        "A3": "Job No", "A4": 63315,
        "B3": "Quantity", "B4": 254886,
    })
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    by_lbl = {k.label_cell: k for k in kvs}
    assert by_lbl["A3"].value_cell == "A4"
    assert by_lbl["B3"].value_cell == "B4"


def test_kv_skip_when_no_adjacent_value(tmp_path):
    ctx = _ctx(tmp_path, {"A1": "Job No"})  # nothing in B1 or A2
    sig = survey_sheet(ctx, "S")
    kvs = detect_kv_anchors(ctx, "S", sig)
    assert kvs == []

"""Title-row detection must not misfire when stage bands claim most columns.

The FA26 layout has a wide row 1 of column headers where stage_band_detector
claims most date-typed columns. Only a handful of non-claimed columns remain
for _collect_header_labels. The title-row detector previously compared a
labels-without-claimed-cols count against a populated-data-cols count that
INCLUDED claimed cols, falsely declaring row 1 a title row.
"""
import openpyxl

from app.enums.pli_mode import PliMode
from app.enums.row_role import RowRole
from app.models.artifacts import (
    HeaderLabel, RowSpec, SheetPlan, StageBandSpec, StageColumn,
)
from app.services.planner.plan import _detect_title_row_extra_header


def test_does_not_fire_when_stage_bands_claim_most_cols(tmp_path) -> None:
    """When stage bands already account for most data cols, the few
    non-claimed labels in row 1 must NOT trigger title-row correction.

    This reproduces the FA26 scenario: ~20 stage-band-claimed columns with data,
    only 7 non-claimed columns — but row 1 IS the true header. The pre-fix bug
    compared initial_labels_count=7 against populated_data_cols=25 (including
    claimed cols), tripping the threshold at 7 < 12.5 and falsely declaring
    row 1 a title row. After the fix the denominator excludes claimed cols, so
    the threshold is 7 < (5/2)=2.5, which is False — correctly no misfire.
    """
    from datetime import date

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    # Row 1 = full header row: 7 non-claimed identity labels + 20 stage-band cols.
    ws["A1"] = "PO DATE"
    ws["B1"] = "SEASON"
    ws["C1"] = "BRAND"
    ws["D1"] = "IO"
    ws["E1"] = "ARTICLE"
    ws["F1"] = "STYLE"
    ws["G1"] = "COLOR"
    # Cols H..AA (cols 8..27) are stage-band columns (20 columns).
    stage_headers = [
        "CUTTING", "SEWING", "FINISHING", "PACKING", "EX-FACTORY",
        "BOOKING", "FOB", "DELIVERY", "INSPECTION", "APPROVAL",
        "FABRIC CUT", "FABRIC WASH", "EMBROIDERY", "PRINTING", "BUTTON",
        "ZIPPER", "LABEL", "HANG TAG", "POLYBAG", "CARTON",
    ]
    for i, name in enumerate(stage_headers):
        ws.cell(row=1, column=8 + i, value=name)  # cols H..AA
    # Row 2 = data row: identity cols + all stage cols with dates.
    ws["A2"] = date(2026, 1, 10)
    ws["B2"] = "FA26"
    ws["C2"] = "YC"
    ws["D2"] = 1078
    ws["E2"] = "ART001"
    ws["F2"] = "W5BI42K49A1"
    ws["G2"] = "RGP REGAL PLUM"
    for i in range(20):
        ws.cell(row=2, column=8 + i, value=date(2026, 3, 12))  # date data in stage cols
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ws = openpyxl.load_workbook(p)["S"]

    # Stage band claims cols H..AA (20 columns).
    stage_cols = [
        StageColumn(
            name=name,
            name_cell=f"{chr(ord('H') + i)}1" if i < 18 else f"{'Z' if i == 18 else 'AA'}1",
            primary_col=chr(ord('H') + i) if i < 18 else ("Z" if i == 18 else "AA"),
        )
        for i, name in enumerate(stage_headers[:18])
    ]
    # Build two more stage cols for Z and AA using get_column_letter
    from openpyxl.utils import get_column_letter
    stage_cols += [
        StageColumn(name=stage_headers[18], name_cell="Z1", primary_col="Z"),
        StageColumn(name=stage_headers[19], name_cell="AA1", primary_col="AA"),
    ]
    band = StageBandSpec(
        name="stages", name_cell="H1", sub_header_row=1,
        stage_columns=stage_cols,
    )
    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[1], stage_bands=[band],
        rows=[RowSpec(idx=2, role=RowRole.ANCHOR)],
    )

    extra = _detect_title_row_extra_header(ws, plan)
    # row 1 IS the true header — must NOT detect a need to shift down to row 2.
    assert extra is None, f"Expected None, got {extra} (row 1 is the real header)"


def test_still_fires_when_row1_is_a_real_title_row(tmp_path) -> None:
    """Sanity: existing title-row detection still works when row 1 IS a title.

    The DKN-style layout has a wide merged title in row 1, followed by real column
    labels in row 2 and data in row 3. The title row contains only one string cell
    (the rest are merged-empty) while the data row has many populated columns, so
    initial_labels_count < populated_data_cols / 2 trips and the function returns 2.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    # Row 1: single merged title spanning columns.
    ws["A1"] = "DKN AW26 DROP 2 WOMEN NOSORDER PRODUCTION STATUS REPORT"
    ws.merge_cells("A1:H1")
    # Row 2: real column labels.
    ws["A2"] = "S.No"
    ws["B2"] = "IO No"
    ws["C2"] = "Style No"
    ws["D2"] = "Color"
    ws["E2"] = "Quantity"
    ws["F2"] = "Ex-Factory"
    ws["G2"] = "Delivery"
    ws["H2"] = "Status"
    # Row 3: data — all 8 columns populated so the threshold triggers.
    ws["A3"] = 1
    ws["B3"] = "1063"
    ws["C3"] = "STYLEA"
    ws["D3"] = "Navy"
    ws["E3"] = 500
    ws["F3"] = "2026-03-01"
    ws["G3"] = "2026-04-01"
    ws["H3"] = "On track"
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    ws = openpyxl.load_workbook(p)["S"]

    plan = SheetPlan(
        sheet="S", pli_mode=PliMode.ROW_PER_PLI,
        header_rows=[1],
        rows=[RowSpec(idx=3, role=RowRole.ANCHOR)],
    )
    extra = _detect_title_row_extra_header(ws, plan)
    assert extra == 2, f"Expected 2, got {extra} (row 1 is a title, true header is row 2)"

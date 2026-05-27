"""Generate mock xlsx files illustrating what each P3 test inspects.

Each file has multiple sheets, one per test. Cells are colour-coded:
  - dark red    (FF6666): the cells the test directly INSPECTS / its primary focus
  - light red   (FFCCCC): cells affected by the test (e.g. all plan-marker cells)
  - light yellow(FFFFCC): data cells (data rows / values)
  - light gray  (E0E0E0): header / non-test cells (context)
  - light green (CCFFCC): cells the test EMITS / outputs (e.g. detected names)
  - merge purple(D9C2F0): cells inside a vertical merge (visualising the merge)
"""
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import date as dt
from pathlib import Path

OUT_DIR = Path(__file__).parent
DARK_RED   = PatternFill(start_color="FF6666", end_color="FF6666", fill_type="solid")
LIGHT_RED  = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
YELLOW     = PatternFill(start_color="FFFFCC", end_color="FFFFCC", fill_type="solid")
GRAY       = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
GREEN      = PatternFill(start_color="CCFFCC", end_color="CCFFCC", fill_type="solid")
PURPLE     = PatternFill(start_color="D9C2F0", end_color="D9C2F0", fill_type="solid")
BOLD       = Font(bold=True, size=10)
border = Border(left=Side(border_style="thin", color="999999"),
                right=Side(border_style="thin", color="999999"),
                top=Side(border_style="thin", color="999999"),
                bottom=Side(border_style="thin", color="999999"))


def set_cell(ws, coord, value, fill=None, bold=False):
    c = ws[coord]
    c.value = value
    if fill: c.fill = fill
    if bold: c.font = BOLD
    c.border = border
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def add_legend(ws, start_row):
    """Drop a colour-key legend at the bottom of each sheet."""
    items = [
        ("dark red",     DARK_RED,   "test's PRIMARY inspection target"),
        ("light red",    LIGHT_RED,  "cells affected / scanned by the test"),
        ("light green",  GREEN,      "cells the test EMITS as output"),
        ("light yellow", YELLOW,     "data cells (context)"),
        ("light gray",   GRAY,       "header / non-test cells (context)"),
        ("purple",       PURPLE,     "cells inside a merge (top-left holds the actual value)"),
    ]
    set_cell(ws, f"A{start_row}", "LEGEND", bold=True)
    for i, (label, fill, desc) in enumerate(items):
        r = start_row + 1 + i
        set_cell(ws, f"A{r}", label, fill=fill)
        set_cell(ws, f"B{r}", desc)


# ============================================================
# FILE 1 — simple ROW_PER_PLI (DKN-like)
# ============================================================
def file1_simple_row_per_pli():
    wb = Workbook()
    wb.remove(wb.active)

    def setup_sheet(name):
        """Build the base sheet shape; tests will then highlight on top."""
        ws = wb.create_sheet(name)
        # Row 2 headers
        headers_r2 = [(1, "S.No"), (2, "Buyer"), (3, "Style No"),
                      (4, "Color"), (5, "Quantity"), (6, "Trims Inhouse"),
                      (8, "Fabric Inhouse"), (10, "Sewing Start"),
                      (12, "Sewing End"), (14, "Ex Factory Shipment")]
        for col, txt in headers_r2:
            set_cell(ws, f"{get_column_letter(col)}2", txt, fill=GRAY, bold=True)
        # Row 3 sub-headers
        sub3 = [(5, "Qty"),
                (6, "Planned"), (7, "Actual"),
                (8, "Planned"), (9, "Actual"),
                (10, "Planned"), (11, "Actual"),
                (12, "Planned"), (13, "Actual"),
                (14, "Planned"), (15, "Actual")]
        for col, txt in sub3:
            set_cell(ws, f"{get_column_letter(col)}3", txt, fill=GRAY, bold=True)
        # Data rows 4-6 — 3 PLIs
        for pli_idx, row in enumerate([4, 5, 6]):
            set_cell(ws, f"A{row}", pli_idx + 1, fill=YELLOW)
            set_cell(ws, f"B{row}", "DRYKORN", fill=YELLOW)
            set_cell(ws, f"C{row}", f"ST-{890 + pli_idx}", fill=YELLOW)
            set_cell(ws, f"D{row}", str(6602 + pli_idx), fill=YELLOW)
            set_cell(ws, f"E{row}", 500, fill=YELLOW)
            # Stage dates — only Planned shown for first PLI for clarity
            stage_plan_cols = ["F", "H", "J", "L", "N"]
            for i, c in enumerate(stage_plan_cols):
                set_cell(ws, f"{c}{row}", dt(2026, 4 + i, 1 + pli_idx*3), fill=YELLOW)
            stage_act_cols = ["G", "I", "K", "M", "O"]
            for i, c in enumerate(stage_act_cols):
                set_cell(ws, f"{c}{row}", dt(2026, 4 + i, 2 + pli_idx*3), fill=YELLOW)
        # Set column widths
        for col_i in range(1, 16):
            ws.column_dimensions[get_column_letter(col_i)].width = 13
        return ws

    # -------- Sheet 1: find_plan_marker_rows --------
    ws = setup_sheet("1_find_plan_markers")
    set_cell(ws, "A8", "TEST: find_plan_marker_rows", bold=True)
    set_cell(ws, "A9", "Goal: find rows containing 'Plan'/'Planned'/'Scheduled' text.")
    set_cell(ws, "A10", "Output (this file): [row 3]")
    # Highlight ALL cells in row 3 that contain Plan
    for col in ("F", "H", "J", "L", "N"):
        ws[f"{col}3"].fill = DARK_RED
    add_legend(ws, 13)

    # -------- Sheet 2: count_plan_cells_in_row --------
    ws = setup_sheet("2_count_plan_cells")
    set_cell(ws, "A8", "TEST: count_plan_cells_in_row(grid, row=3)", bold=True)
    set_cell(ws, "A9", "Goal: count 'Plan' cells in a given row to disambiguate Case A vs Case B")
    set_cell(ws, "A10", "Output: 5 (≥2 ⇒ Case A — distributed markers; ROW_PER_PLI shape)")
    for col in ("F", "H", "J", "L", "N"):
        ws[f"{col}3"].fill = DARK_RED
    add_legend(ws, 13)

    # -------- Sheet 3: find_text_above (stage names) --------
    ws = setup_sheet("3_find_text_above")
    set_cell(ws, "A8", "TEST: find_text_above(grid, row=3, col=<plan_col>)", bold=True)
    set_cell(ws, "A9", "Goal: for each Plan marker, scan row(s) above for the stage NAME verbatim.")
    set_cell(ws, "A10", "Output (this file): stage names captured verbatim from row 2:")
    set_cell(ws, "A11", "  ['Trims Inhouse', 'Fabric Inhouse', 'Sewing Start', 'Sewing End', 'Ex Factory Shipment']")
    # Plan markers in light red, names in green
    for col in ("F", "H", "J", "L", "N"):
        ws[f"{col}3"].fill = LIGHT_RED
        ws[f"{col}2"].fill = GREEN
    add_legend(ws, 14)

    # -------- Sheet 4: find_plan_date_subcol (per band) --------
    ws = setup_sheet("4_find_plan_date_subcol")
    set_cell(ws, "A8", "TEST: find_plan_date_subcol(grid, band_cols=[F,G], name_row=2)", bold=True)
    set_cell(ws, "A9", "Goal: within a stage band, find the sub-column whose row 3 says 'Plan'.")
    set_cell(ws, "A10", "Inspecting band 'Trims Inhouse' (cols F-G).")
    set_cell(ws, "A11", "Output: F (the Plan sub-col). G is Actual (goes to stage_metadata).")
    ws["F3"].fill = DARK_RED   # the Plan we're targeting
    ws["G3"].fill = LIGHT_RED  # the Actual we're noting
    ws["F2"].fill = GRAY       # the band name (context)
    add_legend(ws, 14)

    # -------- Sheet 5: find_actual_date_subcol --------
    ws = setup_sheet("5_find_actual_date_subcol")
    set_cell(ws, "A8", "TEST: find_actual_date_subcol(grid, band_cols=[F,G])", bold=True)
    set_cell(ws, "A9", "Goal: within a band, locate the Actual sub-col (typical: plan_col+1).")
    set_cell(ws, "A10", "Output: G — actual_date goes into stage_metadata bag")
    ws["F3"].fill = LIGHT_RED
    ws["G3"].fill = DARK_RED
    add_legend(ws, 13)

    # -------- Sheet 6: scoring per-PLI dates --------
    ws = setup_sheet("6_per_pli_plan_date_read")
    set_cell(ws, "A8", "TEST: per-PLI plan_date read via FieldLocator(SAME_ROW, anchor_col=F)", bold=True)
    set_cell(ws, "A9", "Goal: apply_plan iterates pli_anchor rows; reads (pli_row, F) for Trims Inhouse plan_date.")
    set_cell(ws, "A10", "Output: 3 plan_dates — F4, F5, F6 (one per PLI)")
    # Plan-date column data cells (F4, F5, F6) get green = emit
    for r in (4, 5, 6):
        ws[f"F{r}"].fill = GREEN
    ws["F2"].fill = LIGHT_RED   # the band name (context)
    ws["F3"].fill = LIGHT_RED   # the plan marker
    add_legend(ws, 13)

    wb.save(OUT_DIR / "01_simple_row_per_pli.xlsx")
    print(f"wrote: 01_simple_row_per_pli.xlsx")


# ============================================================
# FILE 2 — multi-band with sub-cols (CHRISTIAN BERG-like)
# ============================================================
def file2_multi_band():
    wb = Workbook()
    wb.remove(wb.active)

    def setup_sheet(name):
        ws = wb.create_sheet(name)
        # row 2: stage names spanning multiple cols
        set_cell(ws, "A2", "ID", fill=GRAY, bold=True)
        set_cell(ws, "B2", "Style", fill=GRAY, bold=True)
        set_cell(ws, "C2", "Color", fill=GRAY, bold=True)
        set_cell(ws, "D2", "Qty", fill=GRAY, bold=True)
        # FABRIC band (3 sub-cols: PLAN, RECVD, APPD)
        set_cell(ws, "E2", "FABRIC", fill=GRAY, bold=True)
        # SEWING band (3 sub-cols: PLAN, START, ACT)
        set_cell(ws, "H2", "SEWING", fill=GRAY, bold=True)
        # CUTTING band (2 sub-cols)
        set_cell(ws, "K2", "CUTTING", fill=GRAY, bold=True)
        # FI band (2 sub-cols)
        set_cell(ws, "M2", "FI", fill=GRAY, bold=True)
        # row 3 sub-headers
        for col, txt in [
            ("E", "PLAN"), ("F", "RECVD"), ("G", "APPD"),
            ("H", "PLAN"), ("I", "START"), ("J", "ACT"),
            ("K", "PLAN"), ("L", "ACT"),
            ("M", "PLAN"), ("N", "ACT"),
        ]:
            set_cell(ws, f"{col}3", txt, fill=GRAY, bold=True)
        # data rows 4-6 — 3 PLIs (with vertical merge in A: id 1063 spans rows 4-5)
        for row in (4, 5, 6, 7):
            set_cell(ws, f"A{row}", "1063" if row == 4 else "1064" if row == 6 else "", fill=YELLOW)
            set_cell(ws, f"B{row}", "ST-001", fill=YELLOW)
            set_cell(ws, f"C{row}", f"COL-{row}", fill=YELLOW)
            set_cell(ws, f"D{row}", 500, fill=YELLOW)
            for col in ("E", "F", "G", "H", "I", "J", "K", "L", "M", "N"):
                set_cell(ws, f"{col}{row}", dt(2026, 3, row), fill=YELLOW)
        # Mark merged cells visually (purple)
        ws.merge_cells("A4:A5")
        ws["A5"].fill = PURPLE
        for col_i in range(1, 16):
            ws.column_dimensions[get_column_letter(col_i)].width = 11
        return ws

    # -------- Sheet 1: find_plan_marker_rows on multi-band --------
    ws = setup_sheet("1_find_plan_markers")
    set_cell(ws, "A10", "TEST: find_plan_marker_rows — multi-band", bold=True)
    set_cell(ws, "A11", "Goal: row 3 has multiple 'PLAN' cells across multiple bands.")
    set_cell(ws, "A12", "Output: [row 3]; with count_plan_cells_in_row = 4 (one per band).")
    for col in ("E", "H", "K", "M"):
        ws[f"{col}3"].fill = DARK_RED
    add_legend(ws, 15)

    # -------- Sheet 2: per-band sub-col discovery --------
    ws = setup_sheet("2_band_subcols")
    set_cell(ws, "A10", "TEST: find_other_subcols(grid, band_cols=[E,F,G], name_row=2)", bold=True)
    set_cell(ws, "A11", "Goal: for band 'FABRIC' (cols E-G), find non-plan sub-cols (go to stage_metadata).")
    set_cell(ws, "A12", "Output: F='RECVD', G='APPD'")
    ws["E3"].fill = LIGHT_RED  # PLAN — first-class
    ws["F3"].fill = DARK_RED   # RECVD — goes to metadata
    ws["G3"].fill = DARK_RED   # APPD — goes to metadata
    ws["E2"].fill = GREEN      # band name verbatim
    add_legend(ws, 15)

    # -------- Sheet 3: merge resolution (vertical merge in identifier col) --------
    ws = setup_sheet("3_merge_resolution")
    set_cell(ws, "A10", "TEST: build_merge_resolved_grid", bold=True)
    set_cell(ws, "A11", "Goal: row 5's A cell is blank (merged with A4='1063').")
    set_cell(ws, "A12", "After merge resolution, grid[(5,'A')] = '1063' (top-left value).")
    ws["A4"].fill = DARK_RED
    ws["A5"].fill = LIGHT_RED   # value comes from merge resolution
    set_cell(ws, "A14", "Effective io_number per PLI row (after merge resolution):", bold=True)
    set_cell(ws, "A15", "  PLI at row 4: io='1063' (own value)", fill=GREEN)
    set_cell(ws, "A16", "  PLI at row 5: io='1063' (carried via merge)", fill=GREEN)
    set_cell(ws, "A17", "  PLI at row 6: io='1064' (own value)", fill=GREEN)
    add_legend(ws, 20)

    # -------- Sheet 4: stage emission per PLI per band --------
    ws = setup_sheet("4_emit_per_pli_per_band")
    set_cell(ws, "A10", "TEST: StageDetailExtractor — emit one Stage per (PLI × band)", bold=True)
    set_cell(ws, "A11", "Goal: for PLI 0 (row 4), emit Stage(name='FABRIC', plan_date=E4, metadata={RECVD: F4, APPD: G4})")
    set_cell(ws, "A12", "       and Stage(name='SEWING', plan_date=H4, metadata={START: I4, ACT: J4})")
    # Highlight per-band stage emission for PLI 0
    for col in ("E", "F", "G"):
        ws[f"{col}4"].fill = GREEN   # FABRIC stage data
    for col in ("H", "I", "J"):
        ws[f"{col}4"].fill = GREEN   # SEWING stage data
    for col in ("K", "L"):
        ws[f"{col}4"].fill = LIGHT_RED   # CUTTING stage data (not as primary focus here)
    for col in ("M", "N"):
        ws[f"{col}4"].fill = LIGHT_RED
    add_legend(ws, 15)

    wb.save(OUT_DIR / "02_multi_band_subcols.xlsx")
    print(f"wrote: 02_multi_band_subcols.xlsx")


# ============================================================
# FILE 3 — SHEET_IS_PLI (63261-like) — multi-strip
# ============================================================
def file3_sheet_is_pli():
    wb = Workbook()
    wb.remove(wb.active)

    def setup_sheet(name):
        ws = wb.create_sheet(name)
        # Identifier block at top (kv-style)
        set_cell(ws, "A3", "Date:", fill=GRAY, bold=True);  set_cell(ws, "B3", dt(2026, 4, 21), fill=YELLOW)
        set_cell(ws, "D3", "Order receipt", fill=GRAY, bold=True); set_cell(ws, "E3", dt(2026, 2, 6), fill=YELLOW)
        set_cell(ws, "D4", "Ex-Fty date", fill=GRAY, bold=True);   set_cell(ws, "E4", dt(2026, 5, 7), fill=YELLOW)
        set_cell(ws, "D5", "Delivery date", fill=GRAY, bold=True); set_cell(ws, "E5", dt(2026, 5, 17), fill=YELLOW)

        # Strip 1 — rows 8-9
        for col, txt in [("C", "L/D send"), ("D", "L/D appl"), ("E", "Fit send"),
                         ("F", "Fit appl"), ("G", "A/W send"), ("H", "A/W appl"),
                         ("I", "PP send"), ("J", "PP appl")]:
            set_cell(ws, f"{col}8", txt, fill=GRAY, bold=True)
        set_cell(ws, "B9", "Plan", fill=GRAY, bold=True)
        for col, d in [("C", dt(2026,2,13)), ("D", dt(2026,2,25)), ("E", dt(2026,2,13)),
                       ("F", dt(2026,3,2)),  ("G", dt(2026,2,18)), ("H", dt(2026,3,7)),
                       ("I", dt(2026,3,17)), ("J", dt(2026,3,25))]:
            set_cell(ws, f"{col}9", d, fill=YELLOW)

        # Strip 2 — rows 13-14
        for col, txt in [("C", "Job sheet"), ("D", "Costing"), ("E", "Yarn deadline"),
                         ("F", "Yarn I/H"), ("G", "Knit start"), ("H", "Knit complete"),
                         ("I", "Dyeing"), ("J", "Fabric I/H")]:
            set_cell(ws, f"{col}13", txt, fill=GRAY, bold=True)
        set_cell(ws, "B14", "Plan", fill=GRAY, bold=True)
        for col, d in [("C", dt(2026,2,7)), ("D", dt(2026,2,10)), ("E", dt(2026,2,12)),
                       ("F", dt(2026,2,18)), ("G", dt(2026,2,20)), ("H", dt(2026,3,1)),
                       ("I", dt(2026,3,2)), ("J", dt(2026,3,20))]:
            set_cell(ws, f"{col}14", d, fill=YELLOW)

        for col_i in range(1, 16):
            ws.column_dimensions[get_column_letter(col_i)].width = 13
        return ws

    # -------- Sheet 1: Plan-marker rows in SHEET_IS_PLI --------
    ws = setup_sheet("1_case_B_anchors")
    set_cell(ws, "A17", "TEST: find_plan_marker_rows (SHEET_IS_PLI)", bold=True)
    set_cell(ws, "A18", "Goal: 'Plan' anchor is at column B (single cell), not distributed across cols.")
    set_cell(ws, "A19", "Output: plan_rows = [9, 14]; each has count_plan_cells_in_row = 1 (Case B).")
    ws["B9"].fill = DARK_RED
    ws["B14"].fill = DARK_RED
    add_legend(ws, 22)

    # -------- Sheet 2: Case B horizontal dates --------
    ws = setup_sheet("2_case_B_horizontal_dates")
    set_cell(ws, "A17", "TEST: find_date_cells_in_row(grid, row=9)", bold=True)
    set_cell(ws, "A18", "Goal: in Case B, date cells live in the SAME row as the Plan anchor.")
    set_cell(ws, "A19", "Output: 8 date cells at C9..J9 (the planned dates for each stage).")
    ws["B9"].fill = LIGHT_RED   # anchor (context)
    for col in ("C", "D", "E", "F", "G", "H", "I", "J"):
        ws[f"{col}9"].fill = DARK_RED   # date cells we found
    # And names captured from row 8
    for col in ("C", "D", "E", "F", "G", "H", "I", "J"):
        ws[f"{col}8"].fill = GREEN   # names (test emits)
    add_legend(ws, 22)

    # -------- Sheet 3: multiple strips stacked --------
    ws = setup_sheet("3_stacked_strips")
    set_cell(ws, "A17", "TEST: StageArenaDetector — multiple Strip outputs", bold=True)
    set_cell(ws, "A18", "Goal: detect BOTH strips and emit them with their bands.")
    set_cell(ws, "A19", "Output: 2 StageStrip (rows 8-9, rows 13-14); 16 total Stages.")
    # Strip 1
    ws["B9"].fill = LIGHT_RED
    for col in ("C", "D", "E", "F", "G", "H", "I", "J"):
        ws[f"{col}8"].fill = GREEN
        ws[f"{col}9"].fill = DARK_RED
    # Strip 2
    ws["B14"].fill = LIGHT_RED
    for col in ("C", "D", "E", "F", "G", "H", "I", "J"):
        ws[f"{col}13"].fill = GREEN
        ws[f"{col}14"].fill = DARK_RED
    add_legend(ws, 22)

    # -------- Sheet 4: stage-wins-over-identifier (Principle 5) --------
    ws = setup_sheet("4_stage_wins_over_identifier")
    set_cell(ws, "A17", "TEST: stage-wins disambiguation (Principle D16#5)", bold=True)
    set_cell(ws, "A18", "Goal: D4='Ex-Fty date' produces ex_fty_date identifier (E4=2026-05-07).")
    set_cell(ws, "A19", "      D5='Delivery date' produces delivery_date identifier (E5=2026-05-17).")
    set_cell(ws, "A20", "      But NO 'Ex Factory Shipment' STAGE column exists in this strip — no conflict.")
    set_cell(ws, "A21", "If a strip stage WAS named 'Ex Factory', stage would win; identifier would be null.")
    ws["D4"].fill = GREEN   # ex_fty_date label
    ws["E4"].fill = GREEN   # ex_fty_date value
    ws["D5"].fill = GREEN   # delivery_date label
    ws["E5"].fill = GREEN   # delivery_date value
    add_legend(ws, 24)

    wb.save(OUT_DIR / "03_sheet_is_pli_stacked.xlsx")
    print(f"wrote: 03_sheet_is_pli_stacked.xlsx")


# ============================================================
# FILE 4 — guards / false positives
# ============================================================
def file4_guards():
    wb = Workbook()
    wb.remove(wb.active)

    # -------- Sheet 1: column_dtype_profile guard --------
    ws = wb.create_sheet("1_dtype_profile_guard")
    set_cell(ws, "A2", "ID", fill=GRAY, bold=True)
    set_cell(ws, "B2", "PO Date", fill=GRAY, bold=True)       # identifier date col (no Plan sub-header)
    set_cell(ws, "C2", "Ex Factory", fill=GRAY, bold=True)    # identifier date col (no Plan sub-header)
    set_cell(ws, "D2", "Trims Inhouse", fill=GRAY, bold=True) # STAGE
    set_cell(ws, "E2", "Sewing", fill=GRAY, bold=True)
    set_cell(ws, "D3", "Planned", fill=GRAY, bold=True)
    set_cell(ws, "E3", "Planned", fill=GRAY, bold=True)
    for row in (4, 5, 6):
        set_cell(ws, f"A{row}", row - 3, fill=YELLOW)
        set_cell(ws, f"B{row}", dt(2026, 2, 1 + row), fill=YELLOW)
        set_cell(ws, f"C{row}", dt(2026, 5, 1 + row), fill=YELLOW)
        set_cell(ws, f"D{row}", dt(2026, 3, 1 + row), fill=YELLOW)
        set_cell(ws, f"E{row}", dt(2026, 4, 1 + row), fill=YELLOW)
    # Description
    set_cell(ws, "A9", "TEST: column_dtype_profile + Plan-marker guard", bold=True)
    set_cell(ws, "A10", "Goal: NOT misclassify identifier-date columns (B, C) as stages.")
    set_cell(ws, "A11", "Mechanism: only cols where row 3 has 'Plan' become stage cols.")
    set_cell(ws, "A12", "Output: stage cols = [D, E]. Identifier date cols [B, C] are correctly skipped.")
    # Highlights
    ws["D3"].fill = DARK_RED
    ws["E3"].fill = DARK_RED
    ws["D2"].fill = GREEN
    ws["E2"].fill = GREEN
    # Reject markers
    ws["B2"].fill = LIGHT_RED  # would-be false positive
    ws["C2"].fill = LIGHT_RED  # would-be false positive
    for r in (4, 5, 6):
        ws[f"B{r}"].fill = LIGHT_RED
        ws[f"C{r}"].fill = LIGHT_RED
    add_legend(ws, 15)
    for col_i in range(1, 8):
        ws.column_dimensions[get_column_letter(col_i)].width = 14

    # -------- Sheet 2: is_total_row guard --------
    ws = wb.create_sheet("2_grand_total_guard")
    set_cell(ws, "A2", "ID", fill=GRAY, bold=True)
    set_cell(ws, "B2", "Style", fill=GRAY, bold=True)
    set_cell(ws, "C2", "Color", fill=GRAY, bold=True)
    set_cell(ws, "D2", "Qty", fill=GRAY, bold=True)
    set_cell(ws, "E2", "Sewing", fill=GRAY, bold=True)
    set_cell(ws, "E3", "Planned", fill=GRAY, bold=True)
    for row in (4, 5):
        set_cell(ws, f"A{row}", row - 3, fill=YELLOW)
        set_cell(ws, f"B{row}", f"ST-00{row-3}", fill=YELLOW)
        set_cell(ws, f"C{row}", f"RED-0{row-3}", fill=YELLOW)
        set_cell(ws, f"D{row}", 500 + (row-3)*100, fill=YELLOW)
        set_cell(ws, f"E{row}", dt(2026, 3, row), fill=YELLOW)
    # Grand Total row at row 6
    set_cell(ws, "A6", "Grand Total", fill=GRAY)
    set_cell(ws, "B6", "Grand Total", fill=GRAY)
    set_cell(ws, "C6", "Grand Total", fill=GRAY)
    set_cell(ws, "D6", 1100, fill=GRAY)
    set_cell(ws, "A9", "TEST: is_total_row guard", bold=True)
    set_cell(ws, "A10", "Goal: skip rows whose key cols contain 'Grand Total' / 'Total' / 'Subtotal'.")
    set_cell(ws, "A11", "Output: PLI rows = [4, 5]. Row 6 SKIPPED (would otherwise be phantom 3rd PLI).")
    # Highlight the rejected row
    for col in ("A", "B", "C", "D"):
        ws[f"{col}6"].fill = DARK_RED
    add_legend(ws, 14)
    for col_i in range(1, 8):
        ws.column_dimensions[get_column_letter(col_i)].width = 14

    # -------- Sheet 3: stage-name from supplier (open vocab in the wild) --------
    ws = wb.create_sheet("3_open_vocab_unknown_name")
    set_cell(ws, "A2", "ID", fill=GRAY, bold=True)
    set_cell(ws, "B2", "Style", fill=GRAY, bold=True)
    set_cell(ws, "C2", "BULK PACKING", fill=GRAY, bold=True)    # NEVER seen stage name
    set_cell(ws, "D2", "WEAVING START", fill=GRAY, bold=True)
    set_cell(ws, "E2", "FUSING", fill=GRAY, bold=True)
    set_cell(ws, "C3", "Planned", fill=GRAY, bold=True)
    set_cell(ws, "D3", "Planned", fill=GRAY, bold=True)
    set_cell(ws, "E3", "Planned", fill=GRAY, bold=True)
    for row in (4, 5):
        set_cell(ws, f"A{row}", row - 3, fill=YELLOW)
        set_cell(ws, f"B{row}", f"ST-00{row-3}", fill=YELLOW)
        for col in ("C", "D", "E"):
            set_cell(ws, f"{col}{row}", dt(2026, 3, row), fill=YELLOW)
    set_cell(ws, "A9", "TEST: open-vocabulary stage NAMES", bold=True)
    set_cell(ws, "A10", "Goal: novel stage names (never seen before) flow through verbatim.")
    set_cell(ws, "A11", "Output stages: [")
    set_cell(ws, "A12", "  Stage(name='BULK PACKING', canonical=None, plan_date=C4)")
    set_cell(ws, "A13", "  Stage(name='WEAVING START', canonical=None, plan_date=D4)")
    set_cell(ws, "A14", "  Stage(name='FUSING', canonical=None, plan_date=E4)")
    set_cell(ws, "A15", "]")
    set_cell(ws, "A16", "None of these are in STAGE_SPECS; canonical=None for all. Detection driven by row 3 'Planned'.")
    for col in ("C", "D", "E"):
        ws[f"{col}2"].fill = GREEN   # name verbatim
        ws[f"{col}3"].fill = DARK_RED  # plan marker
    add_legend(ws, 19)
    for col_i in range(1, 8):
        ws.column_dimensions[get_column_letter(col_i)].width = 18

    wb.save(OUT_DIR / "04_guards_and_open_vocab.xlsx")
    print(f"wrote: 04_guards_and_open_vocab.xlsx")


if __name__ == "__main__":
    file1_simple_row_per_pli()
    file2_multi_band()
    file3_sheet_is_pli()
    file4_guards()

"""Sheet with a stage band whose columns hold mostly strings, not dates.

Triggers Tier 2 date_band_density warning.
"""
from datetime import datetime
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "IO NO"; ws["B1"] = "STYLE"
    ws["A2"] = "1063"; ws["B2"] = "DWJE"
    ws["A3"] = "1064"; ws["B3"] = "DWJF"
    # Stage band with mostly non-date values
    ws["C5"] = "Pre-Prod"
    ws["D5"] = "L/D send"; ws["E5"] = "Fit send"
    ws["D6"] = "pending"; ws["E6"] = datetime(2026, 3, 5)
    ws["D7"] = "pending"; ws["E7"] = "tbd"

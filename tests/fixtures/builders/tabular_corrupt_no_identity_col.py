"""Tabular sheet whose header row has no IO/JOB/PO column.

Triggers planner ambiguity: no identity_col_candidates.
Has 10+ rows to trigger pli_count_sanity check (large sheet, 0 PLIs).
"""
from openpyxl import Workbook


def build(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ws = wb.create_sheet("S")
    ws["A1"] = "NAME"; ws["B1"] = "DESCRIPTION"; ws["C1"] = "NOTES"
    for i in range(1, 11):
        ws[f"A{i+1}"] = f"thing{i}"
        ws[f"B{i+1}"] = f"description for thing {i}"
        ws[f"C{i+1}"] = f"notes for thing {i}"

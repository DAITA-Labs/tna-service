"""Diagnostic: which columns get claimed as quantity per file?

For each file in extracted_2, list:
  - GT quantity column letter
  - Predicted columns (with the label text that triggered each claim,
    and the first few values in that column)

Tells us whether over-prediction is from:
  - Same column claimed across many rows (data-row aliasing — shouldn't happen)
  - Many columns claimed (legitimate alias matches; need single-column arbitration)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "p3_visual" / "canvas_probe"))

from openpyxl import load_workbook
from build_canvas import build_canvas
from spec_queries import find_tabular_identifiers, find_kv_identifiers


DATASET = ROOT / "dataset"
GT_PATH = Path("/Users/nagasai/Documents/DAITA/tna-service/dataset/extracted_2/dataset_plis_bulk.json")


def gt_io_col_for(file_name: str) -> str | None:
    with open(GT_PATH) as f:
        d = json.load(f)
    for e in d["results"]:
        if e["file_name"] == file_name:
            plan = e.get("plan") or {}
            if plan.get("quantity"): return plan["quantity"]
    return None


def main():
    files = sorted({p.name for p in DATASET.iterdir() if p.suffix == ".xlsx"})
    for name in files:
        xlsx = DATASET / name
        gt_col = gt_io_col_for(name)
        try:
            wb = load_workbook(xlsx, data_only=True)
            sh = wb.active
            canvas = build_canvas(sh)
            tab = find_tabular_identifiers(canvas, phase="identifier")
            kv  = find_kv_identifiers(canvas, phase="identifier")
        except Exception as e:
            print(f"\n{name[:55]}: ERROR {e}")
            continue

        # Group quantity findings by (label_coord, column)
        io_findings = [f for f in (tab + kv) if f.canonical == "quantity"]
        # Group by label_coord (=which header cell triggered the claim)
        by_label: dict[str, list] = defaultdict(list)
        for f in io_findings:
            by_label[f.label_coord].append(f)

        # Predicted columns
        from openpyxl.utils import column_index_from_string
        cols_claimed = set()
        for f in io_findings:
            col_letters = "".join(ch for ch in f.value_coord if ch.isalpha())
            cols_claimed.add(col_letters)

        gt_mark = lambda c: " ←GT" if c == gt_col else ""
        print(f"\n{name[:60]}")
        print(f"  GT quantity col: {gt_col or '(none)':<6}   predicted cols: {sorted(cols_claimed)}")
        for label_coord, fs in by_label.items():
            cols = sorted({"".join(ch for ch in f.value_coord if ch.isalpha()) for f in fs})
            # Read the label cell text
            from openpyxl.utils import column_index_from_string as cifs
            col_part = "".join(ch for ch in label_coord if ch.isalpha())
            row_part = int("".join(ch for ch in label_coord if ch.isdigit()))
            label_text = canvas.cell_values[row_part-1][cifs(col_part)-1]
            print(f"    {label_coord} = {str(label_text)[:30]!r:<32}  claims col(s) {cols}  ({len(fs)} findings)")


if __name__ == "__main__":
    main()

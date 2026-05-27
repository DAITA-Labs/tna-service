"""Header-detection diagnostic.

For each problem file (where tabular extraction returned 0 IDs), show:
  - Top 5 spec-scored rows (what find_header_rows_via_specs returns)
  - Whether text_dense_rows is excluding rows we'd expect to be headers
  - Sample cell contents of the first few rows
  - Header rows that the ground-truth plan claims

This tells us whether the failure is (a) the row not scoring high enough,
(b) the row being excluded by the text-dense pre-filter, or (c) the
spec-alias set genuinely missing this file's terminology.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "p3_visual" / "canvas_probe"))

from openpyxl import load_workbook
from build_canvas import build_canvas, DTYPE_STR
from spec_queries import (
    find_header_rows_via_specs, query_all, text_dense_rows, specs_for_phase,
)


DATASET = ROOT / "dataset"
GT_PATH = Path("/Users/nagasai/Documents/DAITA/tna-service/dataset/extracted_2/dataset_plis_bulk.json")


PROBLEM_FILES = [
    "CHRISTIAN BERG- T&A.xlsx",
    "MAIN FALL KIDS & MENS MASTER CHART #1.xlsx",
    "NORTHERN REFLECTIONS- T&a.xlsx",
    "new Eastman TnAs.xlsx",
]


def gt_header_rows_for(file_name: str) -> list[int]:
    with open(GT_PATH) as f:
        d = json.load(f)
    for e in d["results"]:
        if e["file_name"] == file_name and "header_rows" in (e.get("plan") or {}):
            return e["plan"]["header_rows"]
    return []


def diagnose(xlsx_path: Path):
    print(f"\n{'═'*100}")
    print(f"  {xlsx_path.name}")
    print(f"{'═'*100}")

    wb = load_workbook(xlsx_path, data_only=True)
    sh = wb.active
    canvas = build_canvas(sh)

    gt_rows = gt_header_rows_for(xlsx_path.name)
    print(f"GT header rows:  {gt_rows}")

    # Text-dense rows
    dense = text_dense_rows(canvas, min_str_count=2)
    print(f"text_dense_rows: {sorted(dense)[:30]}{'...' if len(dense)>30 else ''} (n={len(dense)})")
    for r in gt_rows:
        marker = "✓ in dense" if r in dense else "✗ EXCLUDED by pre-filter"
        print(f"  GT row {r}: {marker}")

    # Spec scoring
    scored = find_header_rows_via_specs(canvas, min_score=0.0)
    print(f"\nTop 5 spec-scored rows:")
    for r, score, breakdown in scored[:5]:
        marker = "←GT" if r in gt_rows else ""
        bd = ", ".join(f"{k}={v}" for k, v in breakdown.items() if v > 0)
        print(f"  row {r:>3}  score={score:<6}  ({bd})  {marker}")
    if not scored:
        print("  (no rows scored — entire spec-query returned nothing)")

    # Show what's in the GT header rows
    print(f"\nGT header-row contents:")
    for r in gt_rows:
        cells = []
        for c in range(min(canvas.n_cols, 40)):
            v = canvas.cell_values[r-1][c]
            if v not in (None, "") and isinstance(v, str):
                cells.append(f"{chr(ord('A')+c) if c<26 else 'A'+chr(ord('A')+c-26)}{r}={v.strip()[:18]!r}")
            if len(cells) >= 8: break
        print(f"  row {r}: {cells}")

    # Show spec matches across all rows (any phase)
    matches = query_all(canvas)
    rows_with_matches = sorted({m.row for m in matches})
    print(f"\nAll rows with ANY spec match: {rows_with_matches[:20]}{'...' if len(rows_with_matches)>20 else ''} "
          f"(total={len(rows_with_matches)})")


def main():
    for name in PROBLEM_FILES:
        p = DATASET / name
        if not p.exists():
            print(f"\n[skip] {name} not found")
            continue
        diagnose(p)


if __name__ == "__main__":
    main()

"""Stage-band detection USING ONLY find_around_cell / find_around_range.

Demonstrates the algorithm on 4 real files spanning all layout cases.
For each marker we show: (a) the 3×3 neighbourhood, (b) the decision logic,
(c) the band emitted. The detector body is < 80 lines — everything else is
the around-primitives doing the heavy lifting.
"""
from __future__ import annotations

from pathlib import Path
from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

# Reuse the find_around primitives from our earlier prototype
from find_around import (
    build_rich_grid, find_around_cell, find_around_range,
    CellInfo, CellNeighbourhood, RangeNeighbourhood,
)

PLAN_TOKENS = {"plan", "planned", "scheduled"}
ACTUAL_TOKENS = {"actual", "act"}
SKIP_NAMES = {"plan", "planned", "actual", "act", "approval", "approved",
              "qty", "quantity", "col", "scheduled", "extended", "remarks",
              "received", "rcvd", "recvd"}


def is_plan_text(v):
    if not isinstance(v, str): return False
    s = v.strip().lower()
    return s in PLAN_TOKENS or any(tok in s.split() for tok in PLAN_TOKENS)


def is_actual_text(v):
    if not isinstance(v, str): return False
    s = v.strip().lower()
    return s in ACTUAL_TOKENS


# ============================================================
# The detection algorithm — uses ONLY find_around_* primitives
# ============================================================

def detect_bands(grid, max_col=60, trace=False):
    """Return list of detected bands. With trace=True, prints decisions."""
    # Step 1: find all plan-marker cells across the entire grid
    plan_markers = []
    for (r, c), cell in grid.items():
        if is_plan_text(cell.value):
            plan_markers.append((r, c))

    # Step 2: group by row
    by_row = {}
    for r, c in plan_markers:
        by_row.setdefault(r, []).append(c)

    if trace:
        print(f"  Found {len(plan_markers)} plan-marker cells in {len(by_row)} rows: "
              f"{sorted(by_row.keys())}")

    bands = []
    for plan_row in sorted(by_row):
        markers_in_row = by_row[plan_row]
        n_markers = len(markers_in_row)

        # Step 3: classify Case A vs Case B
        if n_markers >= 2:
            case = "A"
        else:
            # Single marker — Case B IFF there are >= 2 date cells in the same row
            anchor_col = markers_in_row[0]
            n_dates = sum(
                1 for c_i in range(1, max_col + 1)
                if grid.get((plan_row, get_column_letter(c_i))) and
                   grid[(plan_row, get_column_letter(c_i))].dtype == "date"
            )
            case = "B" if n_dates >= 2 else "skip"

        if trace:
            print(f"\n  Row {plan_row}: {n_markers} plan marker(s) at {markers_in_row[:5]}"
                  f"{'...' if n_markers > 5 else ''} → Case {case}")

        if case == "skip":
            continue

        if case == "A":
            # Each marker = one stage. Use find_around_cell on each.
            for col in markers_in_row:
                nb = find_around_cell(grid, f"{col}{plan_row}")
                # Stage name: cell directly above
                name = _resolve_name_via_around(grid, plan_row, col)
                if not name: continue
                if name.strip().lower() in SKIP_NAMES: continue
                # Actual sub-col: cell directly to the right
                actual_col = nb.right.col if (nb.right and is_actual_text(nb.right.value)) else None
                if trace:
                    print(f"    plan_col={col}, name={name!r}, actual_col={actual_col}")
                bands.append({
                    "name": name,
                    "plan_col": col,
                    "plan_row": plan_row,
                    "name_row": plan_row - 1,
                    "actual_col": actual_col,
                    "case": "A",
                })

        elif case == "B":
            # Single anchor + horizontal dates. Iterate cells to the right of the anchor.
            anchor_col = markers_in_row[0]
            anchor_idx = column_index_from_string(anchor_col)
            # Walk right and collect date cells; their stage name is the cell above
            for c_i in range(anchor_idx + 1, max_col + 1):
                col = get_column_letter(c_i)
                cell = grid.get((plan_row, col))
                if cell is None or cell.dtype != "date":
                    continue
                # Use find_around_cell to grab the name above
                nb = find_around_cell(grid, f"{col}{plan_row}")
                name = nb.above.value if (nb.above and nb.above.value) else None
                if not name:
                    # Try 2 rows up if 1 above is blank
                    nb2 = grid.get((plan_row - 2, col))
                    name = nb2.value if nb2 else None
                if not name or not isinstance(name, str): continue
                if name.strip().lower() in SKIP_NAMES: continue
                if trace:
                    print(f"    date_col={col}, name={name!r}, value={cell.value}")
                bands.append({
                    "name": name.strip(),
                    "plan_col": col,
                    "plan_row": plan_row,
                    "name_row": plan_row - 1,
                    "actual_col": None,
                    "case": "B",
                })

    return bands


def _resolve_name_via_around(grid, row, col):
    """Use find_around_cell to look for the stage name above.

    Tries rows (row-1), (row-2), (row-3) until a non-skip text is found.
    Handles merged-cell stage headers via merge-resolved values.
    """
    for up in (1, 2, 3):
        cell = grid.get((row - up, col))
        if cell is None: continue
        v = cell.value
        if isinstance(v, str) and v.strip() and v.strip().lower() not in SKIP_NAMES:
            return v.strip()
    return None


# ============================================================
# Tracer demos
# ============================================================

def trace(label, xlsx_path):
    print(f"\n{'='*78}\n{label}\n{'='*78}")
    print(f"File: {xlsx_path}")
    wb = load_workbook(xlsx_path, data_only=True)
    sh = wb.active
    grid = build_rich_grid(sh)
    bands = detect_bands(grid, max_col=sh.max_column, trace=True)

    print(f"\n  → {len(bands)} band(s) emitted")
    for b in bands[:15]:
        print(f"      Case {b['case']}: name={b['name']!r:35} "
              f"plan_col={b['plan_col']}@row{b['plan_row']}, name_row={b['name_row']}, "
              f"actual_col={b['actual_col']}")
    if len(bands) > 15:
        print(f"      ... +{len(bands) - 15} more")


if __name__ == "__main__":
    trace("CASE 1 — DKN (Standard ROW_PER_PLI, distributed markers)",
          "dataset/20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx")
    trace("CASE 2 — CHRISTIAN BERG (Multi-band, vertical merges, multi-row sub-headers)",
          "dataset/CHRISTIAN BERG- T&A.xlsx")
    trace("CASE 3 — 63261-TNA (SHEET_IS_PLI, multiple stacked strips, Case B)",
          "dataset/63261-TNA.xlsx")
    trace("CASE 4 — MOPD FW26 (Multi-PLI with merged stage cells, Sizeset Submission)",
          "dataset/20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO.xlsx")

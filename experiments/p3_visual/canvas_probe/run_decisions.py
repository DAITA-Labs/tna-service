"""Harness: build canvas → run decisions → run validations → print findings.

Covers all 4 structural categories:
  ROW_PER_PLI single-band:    DKN
  ROW_PER_PLI multi-band:     CHRISTIAN BERG
  ROW_PER_PLI heavy-merges:   MOPD FW26
  SHEET_IS_PLI multi-strip:   63261, NEW
  SECTION-style large:        GUESS master #1
"""
from pathlib import Path
from openpyxl import load_workbook
from build_canvas import build_canvas, render_to_xlsx
from decisions import analyze, find_header_rows
from validations import validate_all


FILES = [
    ("DKN (ROW_PER_PLI baseline)",       "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS"),
    ("CHRISTIAN BERG (multi-band)",      "CHRISTIAN BERG- T&A"),
    ("MOPD FW26 (heavy merges)",         "20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO"),
    ("63261-TNA (multi-strip)",          "63261-TNA"),
    ("NEW (multi-strip variant)",        "NEW"),
    ("GUESS master #1 (section-like)",   "GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1"),
]


def fmt_rect(r):
    if r is None: return "—"
    return str(r)


def main():
    for label, base in FILES:
        xlsx = Path("dataset") / f"{base}.xlsx"
        if not xlsx.exists():
            print(f"\n=== {label}: NOT FOUND ===")
            continue
        print(f"\n{'='*80}")
        print(f"=== {label}: {base[:55]} ===")
        print('='*80)

        wb = load_workbook(xlsx, data_only=True)
        sh = wb.active
        canvas = build_canvas(sh)

        # Run decisions
        findings = analyze(canvas)

        print(f"sheet dims: {canvas.n_rows} × {canvas.n_cols}")
        print()
        print(f"HEADER ROWS (top 3 — score breakdown by phase):")
        for entry in findings["header_rows"][:3]:
            row, score, breakdown = entry
            parts = ", ".join(f"{k}={v}" for k, v in breakdown.items() if v > 0)
            print(f"  row {row:>3}  score={score:<5}  ({parts})")
        if not findings["header_rows"]:
            print("  (no rows scored above threshold)")

        print()
        print(f"DATA REGIONS (top 3):")
        for dr in findings["data_regions"][:3]:
            print(f"  {dr}")

        print()
        print(f"STAGE ARENAS ({len(findings['stage_arenas'])}):")
        for i, a in enumerate(findings["stage_arenas"]):
            direction = findings["arena_directions"].get(str(i), "?")
            print(f"  arena {i}: {a}  date_flow_direction={direction}")
        if not findings["stage_arenas"]:
            print("  (no arenas detected)")

        print()
        print(f"IDENTIFIER ZONE:  {fmt_rect(findings['identifier_zone'])}")

        print()
        if findings["empty_row_runs"]:
            print(f"EMPTY ROW RUNS ({len(findings['empty_row_runs'])}): {findings['empty_row_runs'][:8]}"
                  f"{'...' if len(findings['empty_row_runs']) > 8 else ''}")
        else:
            print("EMPTY ROW RUNS: none")

        # Repeating-row/col groups (header-rhythm signal)
        if "repeating_row_id" in canvas.channels:
            row_groups: dict[int, list[int]] = {}
            for r in range(canvas.n_rows):
                gid = canvas.channels["repeating_row_id"][r][0]
                if gid: row_groups.setdefault(gid, []).append(r + 1)
            col_groups: dict[int, list[int]] = {}
            for c in range(canvas.n_cols):
                gid = canvas.channels["repeating_col_id"][0][c]
                if gid: col_groups.setdefault(gid, []).append(c + 1)
            print()
            if row_groups or col_groups:
                print(f"REPEATING GROUPS:  rows={len(row_groups)}  cols={len(col_groups)}")
                for gid, rows in list(row_groups.items())[:3]:
                    sample = rows[:6] + (["..."] if len(rows) > 6 else [])
                    print(f"  row-group {gid}: {len(rows)} rows  e.g. {sample}")
            else:
                print("REPEATING GROUPS: none")

        # K:V identifier pairs (label + adjacent value, spec-driven)
        from spec_queries import find_kv_identifiers
        kv = find_kv_identifiers(canvas, phase="identifier")
        print()
        if kv:
            print(f"K:V IDENTIFIER PAIRS ({len(kv)}):")
            for f in kv[:8]:
                ok = "ok" if f.dtype_ok else "DTYPE_MISMATCH"
                vstr = str(f.value)[:30]
                print(f"  {f.label_coord:>5} → {f.value_coord:<5} ({f.direction:<5}) "
                      f"{f.canonical:<16} = {vstr!r}  [{ok}, w={f.weight}]")
            if len(kv) > 8: print(f"  ... +{len(kv) - 8} more")
        else:
            print("K:V IDENTIFIER PAIRS: none")

        # Run validations (pass kv to avoid recomputation)
        warnings = validate_all(canvas, findings["stage_arenas"], kv_findings=kv)
        print()
        print(f"VALIDATIONS ({len(warnings)}):")
        for w in warnings:
            print(f"  [{w.severity.upper():<7}] {w.name}: {w.message}")
        if not warnings:
            print("  (clean)")


if __name__ == "__main__":
    main()

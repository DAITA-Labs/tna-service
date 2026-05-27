"""Run canvas probe on 5 files spanning all layout modes."""
from pathlib import Path
from openpyxl import load_workbook
from build_canvas import build_canvas, render_to_xlsx, summarise_canvas, query_term_density
import json

FILES = [
    ("DKN (ROW_PER_PLI)",                "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS"),
    ("CHRISTIAN BERG (multi-band)",      "CHRISTIAN BERG- T&A"),
    ("MOPD FW26 (multi-PLI, merges)",    "20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO"),
    ("63261 (SHEET_IS_PLI, 3 strips)",   "63261-TNA"),
    ("NEW (SHEET_IS_PLI, multi-strip)",  "NEW"),
]


def main():
    out_dir = Path(__file__).parent
    summaries = {}
    for label, base in FILES:
        xlsx = Path("dataset") / f"{base}.xlsx"
        out_path = out_dir / f"{base.replace(' ', '_').replace('/', '_')}_canvas.xlsx"
        print(f"\n=== {label}: {base} ===")
        wb = load_workbook(xlsx, data_only=True)
        sh = wb.active
        canvas = build_canvas(sh)
        render_to_xlsx(canvas, base, out_path)
        s = summarise_canvas(canvas)
        summaries[label] = s

        print(f"  dims: {s['n_rows']}×{s['n_cols']} = {s['n_rows']*s['n_cols']} cells")
        print(f"  density:    {s['density']['non_blank']:>4} non-blank ({s['density']['density']*100:>4.1f}%)")
        print(f"  dtype:      " + ", ".join(f"{k}={v}" for k, v in s["dtype"]["distribution"].items() if v > 0))
        print(f"  plan_marker:{s['plan_marker']['count']:>4} cells across {s['plan_marker']['rows_with_plan']:>2} row(s)")
        print(f"  fill_color: {s['fill_color']['n_distinct']:>4} distinct colors, {s['fill_color']['cells_colored']:>4} cells colored")
        print(f"  border:     {s['border']['has_border']:>4} bordered, {s['border']['full_border']:>4} fully bordered")
        print(f"  merge:      {s['merge']['n_ranges']:>4} merge ranges, {s['merge']['cells_in_merges']:>4} cells affected")
        print(f"  date_like:  real={s['date_like']['real_dates']:>3}, parsed_string={s['date_like']['parsed_string_dates']:>3}")

        # ---- Demonstrate new direction + cluster channels ----
        # 1. Find max-run-col vs max-run-row on date cells → PLI iter axis hint
        date_ch = canvas.channels["date_like"]
        run_col_ch = canvas.channels["dtype_run_col"]
        run_row_ch = canvas.channels["dtype_run_row"]
        max_date_run_col = max(
            (run_col_ch[r][c] for r in range(canvas.n_rows) for c in range(canvas.n_cols)
             if date_ch[r][c] in (1, 2)),
            default=0
        )
        max_date_run_row = max(
            (run_row_ch[r][c] for r in range(canvas.n_rows) for c in range(canvas.n_cols)
             if date_ch[r][c] in (1, 2)),
            default=0
        )
        axis_hint = "ROW (Case A)" if max_date_run_col > max_date_run_row else \
                    "COL (Case B)" if max_date_run_row > max_date_run_col else "AMBIGUOUS"
        print(f"  PLI iter axis: max_date_run_col={max_date_run_col} vs max_date_run_row={max_date_run_row}  → {axis_hint}")

        # 2. Date cluster count
        date_clusters = max((max(row) for row in canvas.channels["date_cluster"]), default=0)
        density_clusters = max((max(row) for row in canvas.channels["density_cluster"]), default=0)
        print(f"  clusters:   date_regions={date_clusters}, density_regions={density_clusters}")

        # 3. Stage axis hint distribution
        axis_hints = {}
        for r in canvas.channels["stage_axis_hint"]:
            for v in r:
                if v: axis_hints[v] = axis_hints.get(v, 0) + 1
        label = {1: "A vertical", 2: "B horizontal", 3: "ambiguous"}
        print(f"  stage axis hints per plan-marker: " +
              ", ".join(f"{label[k]}={v}" for k, v in sorted(axis_hints.items())))

        # 4. Query identifier terms — demonstrates the custom-term-density tool
        ident_terms = ["io", "style", "color", "quantity", "qty", "fabric"]
        q = query_term_density(canvas, ident_terms)
        if q["total"]:
            top_row = max(q["row_density"].items(), key=lambda x: x[1])
            print(f"  query identifier terms {ident_terms}: {q['total']} matches; "
                  f"top row={top_row[0]} ({top_row[1]} hits) → candidate identifier-header row")

        print(f"  wrote: {out_path.name}")

    (out_dir / "summary.json").write_text(json.dumps(summaries, indent=2))
    print()
    print("=" * 70)
    print("KEY: each xlsx has 9 sheets — 0_reference + 8 channel sheets")


if __name__ == "__main__":
    main()

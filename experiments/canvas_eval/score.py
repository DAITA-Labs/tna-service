"""Score canvas extraction against dataset/extracted_1/ ground truth.

Ground truth comes from extracted_1/*.pli.json. Two schemas coexist:
  - Row-style:   pli.stages = [{name, planned_date: {value, source}, ...}]
                 sources are bare coords ("K4") or sheet-qualified ("Sheet1!K4")
  - Band-style:  pli.stages = [{band_name, stage_columns: [{col, planned_date,
                 ...}, ...]}]
                 SHEET_IS_PLI sheets; sources always sheet-qualified.

For each ground-truth field with a source, we check whether our canvas
extractor predicted a cell at the same coordinate. Scoring is exact
source-coord match — the strongest signal because it tests cell-level
location, not just textual value.

This is an EXPLORATORY harness, not a regression test — it tells us how
much of the ground truth the canvas currently covers, broken down by
phase (identifier / stage). Run after every change to find_kv_identifiers /
find_stage_arenas to see the bottom-line impact.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "p3_visual" / "canvas_probe"))

from openpyxl import load_workbook

from build_canvas import build_canvas, DTYPE_DATE
from decisions import analyze, find_stage_arenas
from spec_queries import find_kv_identifiers, find_tabular_identifiers


DATASET     = ROOT / "dataset"
# extracted_1 lives in the main repo (not copied into worktrees)
GROUND_TRUTH = Path("/Users/nagasai/Documents/DAITA/tna-service/dataset/extracted_1")

DATE_IDENTIFIERS = {"delivery_date", "shipment_date", "ex_fty_date"}
IDENTIFIER_CANONICALS = {
    "io_number", "style_code", "style_name", "color_code", "color_name",
    "fabric_code", "fabric_name", "delivery_date", "shipment_date",
    "ex_fty_date", "quantity",
}


def _strip_sheet(coord: str | None) -> str | None:
    """Sheet1!E5 → E5; K4 → K4; None → None."""
    if not coord: return None
    if "!" in coord: return coord.split("!", 1)[1]
    return coord


def _xlsx_for(gt_path: Path) -> Path | None:
    """Ground-truth filename is '<xlsx-stem>__<sheet>.pli.json'. Resolve back
    to the matching xlsx in dataset/. Strips '#1/#2/#3' variants — they all
    point at the same master file."""
    stem = gt_path.stem
    if "__" not in stem: return None
    xlsx_stem = stem.split("__", 1)[0] + ".xlsx"
    cand = DATASET / xlsx_stem
    if cand.exists(): return cand
    # Try without trailing space differences
    for f in DATASET.iterdir():
        if f.suffix.lower() == ".xlsx" and f.stem == xlsx_stem.rstrip(".xlsx"):
            return f
    return None


def _extract_predictions(xlsx: Path) -> dict:
    """Run canvas extractors on xlsx; return {identifier_coords, stage_date_coords}
    each as a set of 'A1'-style strings (canonical-agnostic for stages).
    """
    wb = load_workbook(xlsx, data_only=True)
    sh = wb.active
    canvas = build_canvas(sh)

    # Identifier predictions: union of k:v + tabular
    kv  = find_kv_identifiers(canvas, phase="identifier")
    tab = find_tabular_identifiers(canvas, phase="identifier")
    ident_coords: dict[str, set[str]] = defaultdict(set)
    for f in kv + tab:
        if f.canonical in IDENTIFIER_CANONICALS:
            ident_coords[f.canonical].add(f.value_coord)

    # Stage-date predictions: every date cell inside any stage arena
    arenas = find_stage_arenas(canvas)
    stage_date_coords: set[str] = set()
    from openpyxl.utils import get_column_letter
    dt = canvas.channels["dtype"]
    for a in arenas:
        for r in range(a.r0 - 1, a.r1):
            for c in range(a.c0 - 1, a.c1):
                if dt[r][c] == DTYPE_DATE:
                    stage_date_coords.add(f"{get_column_letter(c+1)}{r+1}")
    return {"identifiers": ident_coords, "stage_dates": stage_date_coords}


def _extract_ground_truth(gt_path: Path) -> dict:
    """Return {identifier_coords: {canonical: {coord, ...}}, stage_date_coords: {coord, ...}}."""
    with open(gt_path) as fh:
        d = json.load(fh)
    ident_coords: dict[str, set[str]] = defaultdict(set)
    stage_coords: set[str] = set()
    for pli in d.get("plis") or []:
        for canon in IDENTIFIER_CANONICALS:
            v = pli.get(canon)
            if v and isinstance(v, dict) and v.get("source"):
                ident_coords[canon].add(_strip_sheet(v["source"]))
        for stage in pli.get("stages") or []:
            # Row-style
            if "planned_date" in stage:
                pd = stage.get("planned_date")
                if pd and isinstance(pd, dict) and pd.get("source"):
                    stage_coords.add(_strip_sheet(pd["source"]))
            # Band-style
            for sub in stage.get("stage_columns") or []:
                pd = sub.get("planned_date")
                if pd and isinstance(pd, dict) and pd.get("source"):
                    stage_coords.add(_strip_sheet(pd["source"]))
    return {"identifiers": ident_coords, "stage_dates": stage_coords}


def _score_one(gt_path: Path) -> dict | None:
    xlsx = _xlsx_for(gt_path)
    if xlsx is None: return None
    try:
        pred = _extract_predictions(xlsx)
        truth = _extract_ground_truth(gt_path)
    except Exception as e:
        return {"file": gt_path.name, "error": str(e)}

    # Identifier scoring per canonical: hit / gt_total / pred_total
    id_hit = id_gt = id_pred = 0
    per_canon: dict[str, tuple[int, int, int]] = {}
    all_canons = set(truth["identifiers"]) | set(pred["identifiers"])
    for canon in all_canons:
        gt_set = truth["identifiers"].get(canon, set())
        pred_set = pred["identifiers"].get(canon, set())
        hit = len(gt_set & pred_set)
        per_canon[canon] = (hit, len(gt_set), len(pred_set))
        id_hit  += hit
        id_gt   += len(gt_set)
        id_pred += len(pred_set)

    # Stage-date scoring (canonical-agnostic, just coord match)
    st_gt   = len(truth["stage_dates"])
    st_hit  = len(truth["stage_dates"] & pred["stage_dates"])
    st_pred = len(pred["stage_dates"])

    return {
        "file":          gt_path.name,
        "xlsx":          xlsx.name,
        "id_recall":     round(id_hit / id_gt, 3) if id_gt else None,
        "id_precision":  round(id_hit / id_pred, 3) if id_pred else None,
        "id_hit":        id_hit, "id_gt": id_gt, "id_pred": id_pred,
        "stage_recall":   round(st_hit / st_gt, 3) if st_gt else None,
        "stage_precision":round(st_hit / st_pred, 3) if st_pred else None,
        "stage_hit": st_hit, "stage_gt": st_gt, "stage_pred": st_pred,
        "per_canon":     per_canon,
    }


def _pct(num: int, den: int) -> str:
    return f"{num/den*100:5.1f}%" if den else "  —  "


def main():
    files = sorted(GROUND_TRUTH.glob("*.json"))
    results = []
    for f in files:
        if f.name == ".DS_Store": continue
        r = _score_one(f)
        if r is None or "error" in r: continue
        results.append(r)

    # ── Per-file table (recall + precision, both phases)
    print(f"\n{'='*120}")
    print(f"{'file':<48}  {'ID rec':>9} {'ID pre':>9}  {'ST rec':>9} {'ST pre':>9}  pred:gt")
    print(f"{'='*120}")
    sum_ihit=sum_igt=sum_ipred=sum_shit=sum_sgt=sum_spred=0
    for r in results:
        print(f"{r['file'][:47]:<48}  "
              f"{_pct(r['id_hit'], r['id_gt']):>9} {_pct(r['id_hit'], r['id_pred']):>9}  "
              f"{_pct(r['stage_hit'], r['stage_gt']):>9} {_pct(r['stage_hit'], r['stage_pred']):>9}  "
              f"id:{r['id_pred']}/{r['id_gt']} st:{r['stage_pred']}/{r['stage_gt']}")
        sum_ihit += r['id_hit']; sum_igt += r['id_gt']; sum_ipred += r['id_pred']
        sum_shit += r['stage_hit']; sum_sgt += r['stage_gt']; sum_spred += r['stage_pred']
    print(f"{'-'*120}")
    print(f"{'TOTAL':<48}  "
          f"{_pct(sum_ihit, sum_igt):>9} {_pct(sum_ihit, sum_ipred):>9}  "
          f"{_pct(sum_shit, sum_sgt):>9} {_pct(sum_shit, sum_spred):>9}  "
          f"id:{sum_ipred}/{sum_igt} st:{sum_spred}/{sum_sgt}")

    # ── Per-canonical aggregate (identifier field-level)
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # hit, gt, pred
    for r in results:
        for canon, (hit, gt, pred) in r["per_canon"].items():
            agg[canon][0] += hit
            agg[canon][1] += gt
            agg[canon][2] += pred
    print(f"\n{'─'*60}")
    print(f"PER-CANONICAL IDENTIFIER BREAKDOWN (aggregate)")
    print(f"{'─'*60}")
    print(f"{'canonical':<18} {'recall':>9} {'precision':>11}  hits/gt/pred")
    for canon in sorted(agg):
        hit, gt, pred = agg[canon]
        print(f"{canon:<18} {_pct(hit, gt):>9} {_pct(hit, pred):>11}  {hit}/{gt}/{pred}")

    # ── Per-file × per-canonical wide table (R% / P%)
    CANON_ORDER = ["io_number", "style_code", "style_name", "color_code", "color_name",
                   "fabric_code", "fabric_name", "quantity",
                   "delivery_date", "shipment_date", "ex_fty_date"]
    SHORT = {"io_number":"io_num","style_code":"sty_c","style_name":"sty_n",
             "color_code":"col_c","color_name":"col_n","fabric_code":"fab_c",
             "fabric_name":"fab_n","quantity":"qty",
             "delivery_date":"dlv","shipment_date":"ship","ex_fty_date":"ex_fty"}

    def cell(per_canon, c):
        hit, gt, pred = per_canon.get(c, (0, 0, 0))
        if gt == 0 and pred == 0: return "  ·  "
        r = f"{hit/gt*100:.0f}" if gt else "—"
        p = f"{hit/pred*100:.0f}" if pred else "—"
        return f"{r:>3}/{p:<3}"

    print(f"\n{'─'*180}")
    print(f"PER-FILE × PER-CANONICAL  (recall% / precision%   ·=no GT & no pred   —=undefined)")
    print(f"{'─'*180}")
    header = f"{'file':<48} " + " ".join(f"{SHORT[c]:>7}" for c in CANON_ORDER)
    print(header)
    print("-" * len(header))
    for r in results:
        line = f"{r['file'][:47]:<48} "
        line += " ".join(f"{cell(r['per_canon'], c):>7}" for c in CANON_ORDER)
        print(line)


if __name__ == "__main__":
    main()

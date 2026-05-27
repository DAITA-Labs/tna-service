"""Corpus derivation for per-sheet sub-problem strategy comparison.

Pulls (input -> expected) pairs from three sources:

- dataset/extracted/*.json   — ground-truth labels (per-PLI canonical fields,
                               human-readable stage names per PLI)
- evals/runs/<run>/outputs/  — actual extracted outputs (canonical name +
                               cell address mapping in source.cells)
- dataset/*.xlsx             — raw header rows, used to crosswalk cell addr
                               -> raw label

The corpus is a plain dict, written to experiments/corpus.json. Strategies in
the other modules read this file. Keeping things JSON-serialisable lets us
also eyeball the corpus by hand.

Outputs five collections, one per sub-problem:

- field_pairs     [(raw_label, canonical_field, file, sheet)]            #6
- stage_pairs     [(raw_label, canonical_stage, file, sheet)]            #9
- subfield_pairs  [(raw_label, canonical_subfield, file, sheet)]         #10
- band_cases      [(file, sheet, expected_band_starts)]                   #4
- subcol_cases    [(file, sheet, band_name_row, expected_subcols)]       #5
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import openpyxl
from openpyxl.utils.cell import coordinate_from_string


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
EXTRACTED = DATASET / "extracted"
EVAL_RUN = ROOT / "evals" / "runs" / "20260520T114423Z" / "outputs"
OUT = Path(__file__).resolve().parent / "corpus.json"


# --- canonical alias seeds (for label-derived corpus where eval source is missing) ---

# Map common human-readable stage names from labels JSON -> canonical stage name.
# Used only to translate labels-side stage names to the canonical vocabulary
# (so labels-only files can still contribute stage_pairs).
LABEL_STAGE_CANONICALS: dict[str, str] = {
    "fabric": "fabric",
    "fabric inhouse": "in_house_fabric_send",
    "trims inhouse": "trims_inhouse",
    "size set": "size_set",
    "sizeset": "size_set",
    "sizeset submission": "size_set",
    "lot card": "lot_card",
    "cutting": "cutting",
    "feeding": "feeding",
    "sewing": "sewing",
    "sewing start": "sewing_start",
    "sewing end": "sewing_end",
    "fi": "final_inspection",
    "final inspection": "final_inspection",
    "inspection": "final_inspection",
    "ex factory shipment": "ex_factory",
    "ex factory": "ex_factory",
    "ex-factory": "ex_factory",
    "ex factory date": "ex_factory",
    "pps submission": "pre_production_send",
    "pp submission": "pre_production_send",
    "ppm": "pre_production_send",
    "vap 1 send": "art_work_send",
    "vap 1 rec": "art_work_approval",
    "vap 2 send": "art_work_send",
    "vap 2 rec": "art_work_approval",
    "art work": "art_work_send",
    "garment handwork start": "garment_pattern",
    "garment handwork end": "garment_pattern",
    "garment pattern": "garment_pattern",
    "first pattern": "first_pattern",
    "fit send": "fit_send",
    "fit approval": "fit_approval",
    "lab dip send": "lab_dip_send",
    "lab dip approval": "lab_dip_approval",
    "printing": "printing",
    "embroidery": "embroidery",
    "washing": "washing",
    "finishing": "finishing",
    "packing": "packing",
    "cuting start": "cutting",
    "cuting end": "cutting",
    "cut start": "cutting",
    "cut end": "cutting",
    "feeding start": "feeding",
    "feeding end": "feeding",
    # GUESS / MOP-style vocab
    "program submit on": "pre_production_send",
    "fabric eta plan": "in_house_fabric_send",
    "fabric in-housed on": "in_house_fabric_approval",
    "fabric in-housed plan": "in_house_fabric_send",
    "fabric in-house on": "in_house_fabric_approval",
    "ex con": "ex_factory",
    "ex fac": "ex_factory",
    "ss start plan": "sewing_start",
    "ss end plan": "sewing_end",
    "ss start act": "sewing_start",
    "ss end act": "sewing_end",
    "stitching start": "sewing_start",
    "stitching end": "sewing_end",
    "stitching": "sewing",
    "pp sent": "pre_production_send",
    "pp apvd": "pre_production_approval",
    "ss": "size_set",
    "cut": "cutting",
    "print/stone send plan": "art_work_send",
    "print/stone received plan": "art_work_approval",
    "emb send plan": "art_work_send",
    "emb recvd plan": "art_work_approval",
    "line": "sewing",
    "fi plan date": "final_inspection",
}


# Canonical sub-field aliases (when sub-column appears as a raw "PLAN"/"ACT"/etc.)
LABEL_SUBFIELD_CANONICALS: dict[str, str] = {
    "plan": "planned_date",
    "planned": "planned_date",
    "act": "actual_date",
    "actl": "actual_date",
    "actual": "actual_date",
    "action": "actual_date",
    "appd": "approval_date",
    "approved": "approval_date",
    "approval": "approval_date",
    "approved date": "approval_date",
    "recvd": "received_date",
    "received": "received_date",
    "rec": "received_date",
    "qty": "quantity",
    "quantity": "quantity",
    "approved qty": "approved_qty",
    "appd qty": "approved_qty",
    "remarks": "remarks",
    "remark": "remarks",
    "comment": "comments",
    "comments": "comments",
    "deviation": "deviation_days",
    "dev": "deviation_days",
    "sub": "remarks",
    "start plan": "planned_date",
    "start act": "actual_date",
    "end plan": "planned_date",
    "end act": "actual_date",
}


def _stage_pair_plausible(raw: str, canonical: str) -> bool:
    """Plausibility filter for eval-output-derived stage pairs.

    Accepts when:
    - LABEL_STAGE_CANONICALS already maps norm(raw) -> canonical, or
    - raw normalises to the canonical (e.g. 'Sewing' -> 'sewing'), or
    - raw shares at least one non-trivial token with the canonical's parts.

    Rejects e.g. 'Delivery date' -> 'lab_dip_approval' (no shared tokens),
    'Clear' -> 'planned_completion_date' (no overlap).
    """
    nr = _norm(raw)
    if LABEL_STAGE_CANONICALS.get(nr) == canonical:
        return True
    canon_tokens = set(canonical.replace("_", " ").split())
    raw_tokens = set(nr.replace("-", " ").replace("/", " ").split())
    # Filter trivial tokens
    raw_tokens -= {"date", "send", "appl", "appr", "approved", "rec", "in", "and"}
    return bool(canon_tokens & raw_tokens)


def _subfield_pair_plausible(raw: str, canonical: str) -> bool:
    """Plausibility filter for eval-output-derived subfield pairs.

    Subfield canonicals form a small set; LABEL_SUBFIELD_CANONICALS should
    cover the legitimate cases. We trust eval mapping only when it's in our
    alias table.
    """
    nr = _norm(raw)
    if LABEL_SUBFIELD_CANONICALS.get(nr) == canonical:
        return True
    # Date sub-fields are very common; accept when raw contains 'plan' or 'act' tokens
    canon_tokens = set(canonical.replace("_", " ").split())
    raw_tokens = set(nr.replace("-", " ").replace("/", " ").split())
    return bool(canon_tokens & raw_tokens)


_DATE_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,2}[-/]\w{3}[-/]\d{2,4}|"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r")\s*$",
    re.IGNORECASE,
)


def _is_date_value(v: object) -> bool:
    if isinstance(v, (date, datetime)):
        return True
    if isinstance(v, str):
        return bool(_DATE_RE.match(v))
    return False


@dataclass
class Corpus:
    field_pairs: list[dict] = field(default_factory=list)
    stage_pairs: list[dict] = field(default_factory=list)
    subfield_pairs: list[dict] = field(default_factory=list)
    band_cases: list[dict] = field(default_factory=list)
    subcol_cases: list[dict] = field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _find_label_for_cell(
    ws, cell_ref: str, max_probe_rows: int = 3
) -> str | None:
    """Walk up from the cell row to find a non-empty header label in the column."""
    col_letter, row = coordinate_from_string(cell_ref)
    col_idx = openpyxl.utils.column_index_from_string(col_letter)
    # search up to max_probe_rows rows above the data cell
    for r in range(row - 1, max(0, row - max_probe_rows - 1), -1):
        v = ws.cell(row=r, column=col_idx).value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _find_subcol_label(ws, cell_ref: str, stage_name_row: int) -> str | None:
    """Pick the sub-column label between stage_name_row+1 and data row.

    For wide_sub_columns layouts, the sub-label sits 1-2 rows below the
    stage name row. Walk down from stage_name_row+1.
    """
    col_letter, row = coordinate_from_string(cell_ref)
    col_idx = openpyxl.utils.column_index_from_string(col_letter)
    for r in range(stage_name_row + 1, min(stage_name_row + 3, row)):
        v = ws.cell(row=r, column=col_idx).value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _header_row_of(ws, source_row: int) -> int:
    """Estimate the header row above a given data row by walking up.

    For most files the header sits at row 1 or 2 (above the first data row).
    """
    # First non-empty row from the top whose cells are mostly strings.
    for r in range(1, source_row):
        non_empty = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        strs = sum(1 for v in non_empty if isinstance(v, str) and v.strip())
        nums = sum(1 for v in non_empty if isinstance(v, (int, float)) and not isinstance(v, bool))
        if strs >= 3 and strs >= nums:
            return r
    return max(1, source_row - 1)


# --- per-file extractors ----------------------------------------------------

def _harvest_eval_output(eval_path: Path, dataset_path: Path, corpus: Corpus) -> None:
    """Cross-reference eval output canonical names with raw header text in xlsx."""
    try:
        data = json.loads(eval_path.read_text())
    except Exception:
        return
    if not dataset_path.exists():
        return

    file_name = dataset_path.stem
    try:
        wb = openpyxl.load_workbook(dataset_path, data_only=True)
    except Exception:
        return

    plis = data.get("plis") or []
    # Dedup raw_label -> canonical by (file, sheet, column_letter).
    field_seen: set[tuple[str, str, str]] = set()
    stage_seen: set[tuple[str, str, str, str]] = set()  # (file, sheet, col, raw)
    subfield_seen: set[tuple[str, str, str, str]] = set()

    for pli in plis[:5]:  # 5 PLIs per file is plenty; headers repeat
        src = pli.get("source") or {}
        sheet_name = src.get("sheet")
        cells = src.get("cells") or {}
        if not sheet_name or sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]

        # === sub-problem #6: identity-field label mapping ===
        for canonical, cell_ref in cells.items():
            try:
                col_letter, _ = coordinate_from_string(cell_ref)
            except Exception:
                continue
            key = (file_name, sheet_name, col_letter)
            if key in field_seen:
                continue
            raw = _find_label_for_cell(ws, cell_ref, max_probe_rows=5)
            if not raw:
                continue
            field_seen.add(key)
            # Filter: skip canonicals that look raw (e.g. "Trims Inhouse"); those
            # are stage names accidentally placed in identity cells map. Only
            # accept snake_case lowercase canonicals.
            if not re.match(r"^[a-z][a-z0-9_]*$", canonical):
                continue
            # Sample up to 3 non-empty values from data rows (rows below the
            # header). For ROW_PER_PLI sheets this gives sample_value strategy
            # something to work with.
            try:
                _, header_row = coordinate_from_string(cell_ref)
            except Exception:
                header_row = 2
            col_idx = openpyxl.utils.column_index_from_string(col_letter)
            samples: list = []
            for r_probe in range(header_row, min(ws.max_row + 1, header_row + 12)):
                v = ws.cell(row=r_probe, column=col_idx).value
                if v is None:
                    continue
                if isinstance(v, str):
                    v_strip = v.strip()
                    if not v_strip:
                        continue
                    samples.append(v_strip[:60])
                else:
                    samples.append(v)
                if len(samples) >= 3:
                    break
            corpus.field_pairs.append({
                "raw": raw,
                "canonical": canonical,
                "file": file_name,
                "sheet": sheet_name,
                "col": col_letter,
                "samples": samples,
            })

        # === sub-problems #9 + #10: stage band name + sub-column label ===
        stages = pli.get("stages") or []
        for st in stages:
            canonical_stage = st.get("name") or ""
            section = st.get("section") or ""
            st_src = st.get("source") or {}
            st_cells = st_src.get("cells") or {}
            st_sheet = st_src.get("sheet")
            if not st_sheet or st_sheet not in wb.sheetnames:
                continue
            st_ws = wb[st_sheet]

            for subfield_canonical, cell_ref in st_cells.items():
                try:
                    col_letter, data_row = coordinate_from_string(cell_ref)
                except Exception:
                    continue
                col_idx = openpyxl.utils.column_index_from_string(col_letter)

                # Walk up to find non-empty strings. First non-empty above data row
                # is treated as sub-column label; the next non-empty above that is
                # the stage band name (it might be the same row for single-row
                # layouts).
                walked: list[tuple[int, str]] = []
                for r in range(data_row - 1, 0, -1):
                    v = st_ws.cell(row=r, column=col_idx).value
                    if isinstance(v, str) and v.strip():
                        walked.append((r, v.strip()))
                    if len(walked) >= 2:
                        break

                stage_raw: str | None = None
                subfield_raw: str | None = None
                if len(walked) == 1:
                    # Single header row -> it's the stage band name (no sub-col).
                    stage_raw = walked[0][1]
                elif len(walked) >= 2:
                    # Two rows: nearest is sub-col label, farther is stage name.
                    subfield_raw = walked[0][1]
                    stage_raw = walked[1][1]

                # Filter: only keep eval-output stage pairs where the canonical
                # is plausible given the raw label. Plausibility = the canonical
                # appears in our LABEL_STAGE_CANONICALS as the mapping for the
                # raw, or the raw normalises to the canonical, or they share
                # at least one token. Otherwise the eval output is just buggy
                # and we'd be feeding garbage into the comparator.
                if stage_raw and canonical_stage in _STAGE_CANONICAL_ALLOW:
                    if _stage_pair_plausible(stage_raw, canonical_stage):
                        key_s = (file_name, st_sheet, col_letter, stage_raw)
                        if key_s not in stage_seen:
                            stage_seen.add(key_s)
                            corpus.stage_pairs.append({
                                "raw": stage_raw,
                                "canonical": canonical_stage,
                                "file": file_name,
                                "sheet": st_sheet,
                                "col": col_letter,
                                "source": "eval_output",
                            })

                if subfield_raw and subfield_canonical in _SUBFIELD_CANONICAL_ALLOW:
                    if _subfield_pair_plausible(subfield_raw, subfield_canonical):
                        key_sf = (file_name, st_sheet, col_letter, subfield_raw)
                        if key_sf not in subfield_seen:
                            subfield_seen.add(key_sf)
                            corpus.subfield_pairs.append({
                                "raw": subfield_raw,
                                "canonical": subfield_canonical,
                                "file": file_name,
                                "sheet": st_sheet,
                                "col": col_letter,
                                "source": "eval_output",
                            })


def _harvest_label_stage_pairs(label_path: Path, dataset_path: Path, corpus: Corpus) -> None:
    """For files with no eval output, use labels JSON stage names as a proxy.

    Each unique stage name in the labels gets mapped to its canonical via the
    LABEL_STAGE_CANONICALS dict, and we look up the column in the xlsx where
    that string appears (approximate, but enough for fuzzy/vocab benchmarks).
    """
    try:
        data = json.loads(label_path.read_text())
    except Exception:
        return
    if not dataset_path.exists():
        return
    file_name = dataset_path.stem
    try:
        wb = openpyxl.load_workbook(dataset_path, data_only=True)
    except Exception:
        return

    # Collect unique raw stage names per file from the labels JSON.
    raw_stage_names: set[str] = set()
    for pli in data.get("plis") or []:
        for st in pli.get("stages") or []:
            n = st.get("name")
            if isinstance(n, str) and n.strip():
                raw_stage_names.add(n.strip())

    # Best-effort canonical mapping; skip when no canonical exists in our table.
    for raw in raw_stage_names:
        canonical = LABEL_STAGE_CANONICALS.get(_norm(raw))
        if not canonical:
            continue
        # Locate the column in the xlsx for this raw label (first sheet only).
        ws = wb.worksheets[0]
        col_letter: str | None = None
        for r in range(1, min(ws.max_row + 1, 10)):
            for c in range(1, ws.max_column + 1):
                v = ws.cell(row=r, column=c).value
                if isinstance(v, str) and _norm(v) == _norm(raw):
                    col_letter = openpyxl.utils.get_column_letter(c)
                    break
            if col_letter:
                break
        corpus.stage_pairs.append({
            "raw": raw,
            "canonical": canonical,
            "file": file_name,
            "sheet": ws.title,
            "col": col_letter or "",
            "source": "labels_json",
        })


def _harvest_band_case(dataset_path: Path, label_path: Path, corpus: Corpus) -> None:
    """Build (sheet -> expected stage bands) for #4.

    Expected band starts are derived by finding all columns that hold a stage
    name string (from LABEL_STAGE_CANONICALS) in the first 5 rows of the first
    sheet. This is a heuristic ground truth but it's close enough to score
    strategies relative to each other.
    """
    if not dataset_path.exists():
        return
    file_name = dataset_path.stem
    try:
        wb = openpyxl.load_workbook(dataset_path, data_only=True)
    except Exception:
        return
    ws = wb.worksheets[0]
    expected_cols: list[tuple[str, str, int]] = []  # (col_letter, stage_canonical, row)
    for r in range(1, min(ws.max_row + 1, 5)):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=r, column=c).value
            if isinstance(v, str):
                canonical = LABEL_STAGE_CANONICALS.get(_norm(v))
                if canonical:
                    expected_cols.append((openpyxl.utils.get_column_letter(c), canonical, r))
    corpus.band_cases.append({
        "file": file_name,
        "sheet": ws.title,
        "max_row": ws.max_row,
        "max_col": ws.max_column,
        "expected_stage_cols": [
            {"col": col, "canonical": can, "row": r}
            for (col, can, r) in expected_cols
        ],
    })


def _harvest_subcol_case(dataset_path: Path, corpus: Corpus) -> None:
    """For each xlsx, find rows that look like sub-column header rows.

    Heuristic ground truth: any cell in the first 5 rows whose normalised text
    is in LABEL_SUBFIELD_CANONICALS counts as an expected sub-col. We tag the
    row it sits on as the band's sub_label_row.
    """
    if not dataset_path.exists():
        return
    file_name = dataset_path.stem
    try:
        wb = openpyxl.load_workbook(dataset_path, data_only=True)
    except Exception:
        return
    ws = wb.worksheets[0]
    subcols_by_row: dict[int, list[dict]] = {}
    for r in range(1, min(ws.max_row + 1, 6)):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            canonical = LABEL_SUBFIELD_CANONICALS.get(_norm(v))
            if canonical:
                subcols_by_row.setdefault(r, []).append({
                    "col": openpyxl.utils.get_column_letter(c),
                    "raw": v.strip(),
                    "canonical": canonical,
                })
    # Only keep the row with the most matches (the "true" sub-header row).
    if subcols_by_row:
        best_row = max(subcols_by_row, key=lambda r: len(subcols_by_row[r]))
        corpus.subcol_cases.append({
            "file": file_name,
            "sheet": ws.title,
            "sub_label_row": best_row,
            "expected_subcols": subcols_by_row[best_row],
        })
    else:
        corpus.subcol_cases.append({
            "file": file_name,
            "sheet": ws.title,
            "sub_label_row": None,
            "expected_subcols": [],
        })


# Build allow-lists for canonicals so we don't pollute the corpus with garbage.
_STAGE_CANONICAL_ALLOW = {
    "fabric", "lab_dip_send", "lab_dip_approval", "fit_send", "fit_approval",
    "art_work_send", "art_work_approval", "in_house_fabric_send",
    "in_house_fabric_approval", "pre_production_send", "pre_production_approval",
    "first_pattern", "garment_pattern", "planned_completion_date",
    "size_set", "lot_card", "cutting", "feeding", "sewing", "sewing_start",
    "sewing_end", "final_inspection", "printing", "embroidery", "washing",
    "finishing", "packing", "ex_factory", "trims_inhouse",
}
_SUBFIELD_CANONICAL_ALLOW = {
    "planned_date", "actual_date", "approval_date", "received_date",
    "approved_qty", "quantity", "remarks", "comments", "deviation_days",
}


def _harvest_xlsx_subfield_pairs(dataset_path: Path, corpus: Corpus) -> None:
    """Scan rows 2-5 of each xlsx for cells that match known sub-field vocabulary.

    Augments subfield_pairs so we have more than one canonical represented.
    This is high-confidence: only accepts cells whose normalised text directly
    keys into LABEL_SUBFIELD_CANONICALS (i.e. already known aliases).
    """
    if not dataset_path.exists():
        return
    file_name = dataset_path.stem
    try:
        wb = openpyxl.load_workbook(dataset_path, data_only=True)
    except Exception:
        return
    ws = wb.worksheets[0]
    seen: set[tuple[str, str, str]] = set()
    for r in range(1, min(ws.max_row + 1, 6)):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            canonical = LABEL_SUBFIELD_CANONICALS.get(_norm(v))
            if not canonical:
                continue
            col_letter = openpyxl.utils.get_column_letter(c)
            key = (file_name, col_letter, v.strip())
            if key in seen:
                continue
            seen.add(key)
            corpus.subfield_pairs.append({
                "raw": v.strip(),
                "canonical": canonical,
                "file": file_name,
                "sheet": ws.title,
                "col": col_letter,
                "source": "xlsx_scan",
            })


def build() -> Corpus:
    corpus = Corpus()
    # All eval outputs first (best signal: canonical + cell address).
    for eval_path in sorted(EVAL_RUN.glob("*.json")):
        ds = DATASET / f"{eval_path.stem}.xlsx"
        _harvest_eval_output(eval_path, ds, corpus)

    # Labels JSON pass — supplements stage_pairs for files we couldn't cross-walk.
    for label_path in sorted(EXTRACTED.glob("*.json")):
        ds = DATASET / f"{label_path.stem}.xlsx"
        _harvest_label_stage_pairs(label_path, ds, corpus)

    # XLSX scan pass for subfield_pairs — pulls real sub-label vocab from headers.
    for ds in sorted(DATASET.glob("*.xlsx")):
        if ds.name.startswith("~$"):
            continue
        _harvest_xlsx_subfield_pairs(ds, corpus)

    # One band + subcol case per xlsx (heuristic ground truth).
    for ds in sorted(DATASET.glob("*.xlsx")):
        if ds.name.startswith("~$"):
            continue
        lp = EXTRACTED / f"{ds.stem}.json"
        _harvest_band_case(ds, lp, corpus)
        _harvest_subcol_case(ds, corpus)

    return corpus


def main() -> None:
    corpus = build()
    payload = {
        "field_pairs": corpus.field_pairs,
        "stage_pairs": corpus.stage_pairs,
        "subfield_pairs": corpus.subfield_pairs,
        "band_cases": corpus.band_cases,
        "subcol_cases": corpus.subcol_cases,
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {OUT}")
    print(f"  field_pairs:    {len(corpus.field_pairs)}")
    print(f"  stage_pairs:    {len(corpus.stage_pairs)}")
    print(f"  subfield_pairs: {len(corpus.subfield_pairs)}")
    print(f"  band_cases:     {len(corpus.band_cases)}")
    print(f"  subcol_cases:   {len(corpus.subcol_cases)}")


if __name__ == "__main__":
    main()

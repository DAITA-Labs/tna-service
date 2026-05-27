"""build_canvas — build the GridCanvas substrate from an openpyxl sheet.

The canvas is the shared spatial substrate for the canvas architecture.
A single pass over the sheet populates ~20 measurement channels (dtype,
density, plan_marker, fill_color, border, merge, date_like, dtype runs,
clusters, date_flow, bold, merge_shape, repeating_row/col_id, empty_row/col,
fill_color_cluster, column_dtype_dominant, text_density_per_row).

Channels are raw numeric matrices — pattern detectors and semantic
resolvers in `app/components/structure/` interpret them into typed records.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from openpyxl.cell.cell import MergedCell

from app.artifacts.canvas import GridCanvas
from app.tools._decorator import tool


# =============================================================================
# Encodings
# =============================================================================
DTYPE_BLANK, DTYPE_DATE, DTYPE_INT, DTYPE_FLOAT, DTYPE_STR, DTYPE_FORMULA = 0, 1, 2, 3, 4, 5
DTYPE_LABELS  = {0: "blank", 1: "date", 2: "int", 3: "float", 4: "str", 5: "formula"}

# Border bitmask
B_TOP, B_RIGHT, B_BOTTOM, B_LEFT = 1, 2, 4, 8

# Merge encoding
MERGE_NONE, MERGE_ANCHOR, MERGE_CONT = 0, 1, 2

# date_like encoding
DLIKE_NONE, DLIKE_REAL, DLIKE_PARSED = 0, 1, 2

# Render palettes
DTYPE_PALETTE = {
    DTYPE_BLANK:   "FFFFFF",
    DTYPE_DATE:    "B4D5FF",
    DTYPE_INT:     "C6EFCE",
    DTYPE_FLOAT:   "9EE0DA",
    DTYPE_STR:     "FFEB9C",
    DTYPE_FORMULA: "E1BEE7",
}
PLAN_MARKER_PALETTE = {0: "FFFFFF", 1: "FF6666"}
DENSITY_PALETTE     = {0: "FFFFFF", 1: "DDDDFF"}
DATE_LIKE_PALETTE   = {DLIKE_NONE: "FFFFFF", DLIKE_REAL: "4A8BC9", DLIKE_PARSED: "B4D5FF"}

# Merge ranges get cycled colours from this palette (one per range)
MERGE_PALETTE = [
    "FFFFFF",   # 0 = no merge
    "FFCDD2", "BBDEFB", "C8E6C9", "FFE0B2", "F8BBD0",
    "B3E5FC", "DCEDC8", "FFCC80", "E1BEE7", "B2EBF2",
    "D7CCC8", "FFE082", "F0F4C3", "B2DFDB", "FFAB91",
    "E6EE9C", "CE93D8", "FFAB40", "A5D6A7", "F48FB1",
]
TEXT_DENSITY_PALETTE = {
    # per-row count buckets — gradient from white to red
    0: "FFFFFF", 1: "FFE5CC", 2: "FFCC99", 3: "FFB266", 4: "FF9933",
    5: "FF6600", 6: "CC5200", 7: "993D00", 8: "662900", 9: "4D1F00",
}

PLAN_TOKENS = {"plan", "planned", "scheduled"}

# date-string patterns we'll recognise. All require day + month + year
# (or year + month + day) — bare "21/03" is intentionally NOT matched
# (ambiguous with non-date int pairs).
DATE_RE = re.compile(
    r"^\s*"
    r"("
    # dd-mm-yyyy / dd/mm/yyyy / dd.mm.yyyy / dd mm yyyy (any separator combo)
    r"\d{1,2}[-/.\s]+\d{1,2}[-/.\s]+\d{2,4}"
    r"|"
    # dd-MMM-yyyy / dd MMM yyyy / dd-MMM-yy / dd-MMMMMMMM-yyyy
    r"\d{1,2}[-/.\s,]*[A-Za-z]{3,9}[-/.\s,]*\d{2,4}"
    r"|"
    # yyyy-mm-dd / yyyy/mm/dd
    r"\d{4}[-/.\s]+\d{1,2}[-/.\s]+\d{1,2}"
    r"|"
    # MMM dd yyyy / MMM dd, yyyy / MMMMMMMMM dd yyyy
    r"[A-Za-z]{3,9}[-/.\s,]*\d{1,2}[-/.\s,]*\d{2,4}"
    r")"
    # optional trailing time (HH:MM or HH:MM:SS)
    r"(\s+\d{1,2}:\d{1,2}(:\d{1,2})?)?"
    r"\s*$",
    re.IGNORECASE,
)


def _is_date_string(s: str) -> bool:
    return bool(s and DATE_RE.match(s.strip()))


def _detect_dtype(v: Any) -> int:
    if v is None or v == "":              return DTYPE_BLANK
    if isinstance(v, (datetime, date)):   return DTYPE_DATE
    if isinstance(v, bool):               return DTYPE_INT
    if isinstance(v, int):                return DTYPE_INT
    if isinstance(v, float):              return DTYPE_FLOAT
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("="):             return DTYPE_FORMULA
        # Strings that LOOK like dates count as dates
        if _is_date_string(s):            return DTYPE_DATE
        return DTYPE_STR
    return DTYPE_STR


def _is_plan(v: Any) -> bool:
    if not isinstance(v, str): return False
    s = v.strip().lower()
    if s in PLAN_TOKENS: return True
    return any(tok in s.split() for tok in PLAN_TOKENS)


def _apply_tint(hex_color: str, tint: float) -> str:
    """Lighten (tint>0) or darken (tint<0). Matches Excel's theme-tint behaviour roughly."""
    if not tint: return hex_color
    try:
        r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
    except ValueError:
        return hex_color
    if tint > 0:
        r = int(r + (255 - r) * tint); g = int(g + (255 - g) * tint); b = int(b + (255 - b) * tint)
    else:
        r = int(r * (1 + tint)); g = int(g * (1 + tint)); b = int(b * (1 + tint))
    r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
    return f"{r:02X}{g:02X}{b:02X}"


# Office 2007+ standard theme palette (approximate; theme files override but
# these defaults are used by the vast majority of TNA spreadsheets)
THEME_PALETTE = {
    0: "FFFFFF", 1: "000000", 2: "EEECE1", 3: "1F497D",
    4: "4F81BD", 5: "C0504D", 6: "9BBB59", 7: "8064A2",
    8: "4BACC6", 9: "F79646",
}


def _norm_fill(cell) -> str | None:
    """Extract a normalised hex color from a cell's fill.

    Handles three openpyxl color types: rgb, theme (with tint), indexed.
    Returns None for white/no-fill.
    """
    if not cell.fill or not cell.fill.fgColor: return None
    fg = cell.fill.fgColor
    color_type = getattr(fg, "type", None)

    # Type "rgb" — explicit hex
    if color_type == "rgb" or color_type is None:
        rgb = getattr(fg, "rgb", None)
        if isinstance(rgb, str) and len(rgb) == 8 and rgb != "00000000":
            hex6 = rgb[2:].upper()
            if hex6 != "FFFFFF": return hex6

    # Type "theme" — workbook theme index + optional tint
    if color_type == "theme":
        theme = getattr(fg, "theme", None)
        tint  = float(getattr(fg, "tint", 0) or 0)
        if theme is not None and theme in THEME_PALETTE:
            base = THEME_PALETTE[theme]
            tinted = _apply_tint(base, tint)
            # Treat near-white as no-fill
            if tinted not in ("FFFFFF", "FEFEFE", "FDFDFD"):
                return tinted

    # Type "indexed" — legacy 0-63 palette
    if color_type == "indexed":
        try:
            from openpyxl.styles.colors import COLOR_INDEX
            idx = fg.indexed
            if idx is not None and 0 <= idx < len(COLOR_INDEX):
                rgb = COLOR_INDEX[idx]
                hex6 = rgb[2:].upper() if isinstance(rgb, str) and len(rgb) == 8 else rgb
                if hex6 and hex6 not in ("FFFFFF", "000000"):
                    return hex6
        except (ImportError, AttributeError):
            pass

    return None


def _border_bits(cell) -> int:
    """Return 4-bit value: 1=top, 2=right, 4=bottom, 8=left set."""
    if not cell.border: return 0
    bits = 0
    if cell.border.top    and cell.border.top.border_style:    bits |= B_TOP
    if cell.border.right  and cell.border.right.border_style:  bits |= B_RIGHT
    if cell.border.bottom and cell.border.bottom.border_style: bits |= B_BOTTOM
    if cell.border.left   and cell.border.left.border_style:   bits |= B_LEFT
    return bits


def _is_date_like(v: Any) -> int:
    """0=no, 1=real date dtype, 2=parseable date string (kept for diagnostics)."""
    if isinstance(v, (datetime, date)): return DLIKE_REAL
    if isinstance(v, str) and _is_date_string(v): return DLIKE_PARSED
    return DLIKE_NONE


def _connected_components(matrix: list[list[int]], predicate) -> list[list[int]]:
    """4-connectivity flood fill. Each cell where predicate(value) is True gets
    a cluster ID (1..N). Others get 0."""
    n_rows = len(matrix)
    n_cols = len(matrix[0]) if n_rows else 0
    out = [[0] * n_cols for _ in range(n_rows)]
    next_id = 0
    for r in range(n_rows):
        for c in range(n_cols):
            if not predicate(matrix[r][c]): continue
            if out[r][c] != 0: continue
            next_id += 1
            # BFS
            stack = [(r, c)]
            while stack:
                rr, cc = stack.pop()
                if rr < 0 or rr >= n_rows or cc < 0 or cc >= n_cols: continue
                if out[rr][cc] != 0: continue
                if not predicate(matrix[rr][cc]): continue
                out[rr][cc] = next_id
                stack.extend([(rr+1, cc), (rr-1, cc), (rr, cc+1), (rr, cc-1)])
    return out


@tool("build_canvas")
def build_canvas(sheet, max_row: int | None = None, max_col: int | None = None) -> GridCanvas:
    """Build a multi-channel GridCanvas from an openpyxl worksheet.

    Single pass over the sheet populates per-cell measurement channels
    (dtype, density, plan_marker, fill_color, border, merge, date_like,
    bold, merge_shape) plus derived channels (dtype runs, clusters,
    date_flow, repeating row/col IDs, empty row/col, fill cluster,
    column dtype dominant).

    Cell values are merge-resolved: every cell inside a merge range gets
    the anchor's value. Borders are read from every cell (including
    continuations) since Excel stores per-cell border sides even within
    merges. An "anchor-only outline" pattern (anchor has all 4 sides,
    continuations have none) is detected and the outline is projected
    onto the outer-edge cells of the merge box.
    """
    # allow-long: orchestrator inlines ~20 per-channel matrix writes;
    # splitting each into a helper would require either re-passing over
    # the sheet (multiplying I/O cost) or threading shared mutable state
    # through return tuples. Both options reduce readability without
    # changing complexity. The function reads top-to-bottom as a
    # measurement pipeline.
    n_rows = max_row or sheet.max_row
    n_cols = max_col or sheet.max_column

    dtype_ch    = [[DTYPE_BLANK] * n_cols for _ in range(n_rows)]
    density_ch  = [[0] * n_cols for _ in range(n_rows)]
    plan_ch     = [[0] * n_cols for _ in range(n_rows)]
    fill_ch     = [[0] * n_cols for _ in range(n_rows)]
    border_ch   = [[0] * n_cols for _ in range(n_rows)]
    merge_ch    = [[MERGE_NONE] * n_cols for _ in range(n_rows)]
    date_like_ch= [[DLIKE_NONE] * n_cols for _ in range(n_rows)]
    bold_ch     = [[0] * n_cols for _ in range(n_rows)]
    merge_shape_ch = [[0] * n_cols for _ in range(n_rows)]   # 0=alone, 1=horiz, 2=vert, 3=block
    raw         = [[None] * n_cols for _ in range(n_rows)]

    fill_groups: dict[str, int] = {}
    next_group = 1

    # Pass 1: read per-cell properties.
    # IMPORTANT: borders ARE read for merged-continuation cells too,
    # because Excel stores per-cell border sides even within merges
    # (outer-edge cells of a merge box have the outer borders set).
    # Other properties (value/dtype/plan/fill) are only read for non-merged
    # cells; pass 2 propagates the anchor's value/dtype/plan/fill.
    for row in sheet.iter_rows(min_row=1, max_row=n_rows, max_col=n_cols, values_only=False):
        for cell in row:
            r = cell.row - 1
            c = cell.column - 1
            # BORDERS: read for ALL cells (merged or not)
            border_ch[r][c] = _border_bits(cell)
            if isinstance(cell, MergedCell):
                # Continuation cells — value/fill/etc. come from anchor in pass 2
                # But borders are already captured above (line above).
                # ALSO try to capture per-cell fill if it differs from anchor's.
                fh = _norm_fill(cell)
                if fh:
                    if fh not in fill_groups:
                        fill_groups[fh] = next_group
                        next_group += 1
                    fill_ch[r][c] = fill_groups[fh]
                continue
            v = cell.value
            raw[r][c]        = v
            dtype_ch[r][c]   = _detect_dtype(v)
            density_ch[r][c] = 0 if v in (None, "") else 1
            plan_ch[r][c]    = 1 if _is_plan(v) else 0
            date_like_ch[r][c] = _is_date_like(v)
            bold_ch[r][c]    = 1 if (cell.font and cell.font.bold) else 0
            fh = _norm_fill(cell)
            if fh:
                if fh not in fill_groups:
                    fill_groups[fh] = next_group
                    next_group += 1
                fill_ch[r][c] = fill_groups[fh]

    # Pass 2: handle merges
    # merge_ch encodes a unique MERGE RANGE ID per merge. 0 = no merge.
    # Border handling: if the anchor has all 4 border sides AND continuation
    # cells have NO borders of their own, we project the anchor's outline
    # onto the appropriate outer-edge cells of the merge box. This makes
    # "outline-bordered merge" regions visible (some xlsx files store the
    # outline only on the anchor, leaving continuation cells empty).
    merge_ranges_list = []
    for mr_idx, mr in enumerate(sheet.merged_cells.ranges, start=1):
        anchor_r, anchor_c = mr.min_row - 1, mr.min_col - 1
        anchor_val   = raw[anchor_r][anchor_c]
        anchor_dtype = dtype_ch[anchor_r][anchor_c]
        anchor_plan  = plan_ch[anchor_r][anchor_c]
        anchor_fill  = fill_ch[anchor_r][anchor_c]
        anchor_dlike = date_like_ch[anchor_r][anchor_c]
        anchor_border= border_ch[anchor_r][anchor_c]

        # Merge shape classification
        n_rows_mr = mr.max_row - mr.min_row + 1
        n_cols_mr = mr.max_col - mr.min_col + 1
        if n_rows_mr == 1 and n_cols_mr >= 2:
            shape_class = 1   # horizontal banner (1×N)
        elif n_cols_mr == 1 and n_rows_mr >= 2:
            shape_class = 2   # vertical carry (M×1)
        elif n_rows_mr >= 2 and n_cols_mr >= 2:
            shape_class = 3   # block (M×N)
        else:
            shape_class = 0   # 1×1 (shouldn't happen for merges)

        # Detect "anchor-only outline" pattern: anchor has all 4 sides AND
        # the continuation cells of this merge have 0 borders. If so we'll
        # distribute the outline to the appropriate outer-edge cells.
        is_outline_only = False
        if anchor_border == 15:  # all 4 bits set
            # check at least one continuation cell has 0 border
            for rr in range(mr.min_row, mr.max_row + 1):
                for cc in range(mr.min_col, mr.max_col + 1):
                    if (rr, cc) == (mr.min_row, mr.min_col): continue
                    if border_ch[rr - 1][cc - 1] == 0:
                        is_outline_only = True
                        break
                if is_outline_only: break

        merge_ranges_list.append((mr.min_row, mr.min_col, mr.max_row, mr.max_col))
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                r, c = rr - 1, cc - 1
                if r >= n_rows or c >= n_cols: continue
                merge_ch[r][c] = mr_idx
                merge_shape_ch[r][c] = shape_class

                # If anchor-only outline → project outer-edge sides to this cell
                if is_outline_only:
                    bits = 0
                    if rr == mr.min_row: bits |= B_TOP
                    if rr == mr.max_row: bits |= B_BOTTOM
                    if cc == mr.min_col: bits |= B_LEFT
                    if cc == mr.max_col: bits |= B_RIGHT
                    border_ch[r][c] = bits

                if not (rr == mr.min_row and cc == mr.min_col):
                    # Propagate value/dtype/plan/fill to continuations
                    raw[r][c]        = anchor_val
                    dtype_ch[r][c]   = anchor_dtype
                    density_ch[r][c] = 1 if anchor_val not in (None, "") else 0
                    plan_ch[r][c]    = anchor_plan
                    date_like_ch[r][c] = anchor_dlike
                    if anchor_fill: fill_ch[r][c] = anchor_fill

    # Derived: text_density_per_row — count of non-blank cells per row, then repeat
    text_density_ch = [[0] * n_cols for _ in range(n_rows)]
    for r in range(n_rows):
        n = sum(1 for v in density_ch[r] if v == 1)
        bucket = min(n // max(1, (n_cols // 9)), 9)   # 0..9 buckets across the row width
        for c in range(n_cols):
            text_density_ch[r][c] = bucket

    # Derived: dtype_run_row — per cell, length of consecutive same-dtype run RIGHT
    dtype_run_row_ch = [[0] * n_cols for _ in range(n_rows)]
    for r in range(n_rows):
        c = n_cols - 1
        while c >= 0:
            if dtype_ch[r][c] in (DTYPE_BLANK,):
                dtype_run_row_ch[r][c] = 0
                c -= 1; continue
            # Find run starting at c going LEFT (we walk leftward for efficiency)
            run_end = c
            run_dt = dtype_ch[r][c]
            run_start = c
            while run_start - 1 >= 0 and dtype_ch[r][run_start - 1] == run_dt:
                run_start -= 1
            length = run_end - run_start + 1
            for cc in range(run_start, run_end + 1):
                dtype_run_row_ch[r][cc] = length
            c = run_start - 1

    # Derived: dtype_run_col — per cell, length of consecutive same-dtype run DOWN
    dtype_run_col_ch = [[0] * n_cols for _ in range(n_rows)]
    for c in range(n_cols):
        r = n_rows - 1
        while r >= 0:
            if dtype_ch[r][c] in (DTYPE_BLANK,):
                dtype_run_col_ch[r][c] = 0
                r -= 1; continue
            run_end = r
            run_dt = dtype_ch[r][c]
            run_start = r
            while run_start - 1 >= 0 and dtype_ch[run_start - 1][c] == run_dt:
                run_start -= 1
            length = run_end - run_start + 1
            for rr in range(run_start, run_end + 1):
                dtype_run_col_ch[rr][c] = length
            r = run_start - 1

    # Derived: connected-component cluster IDs (4-connectivity)
    date_cluster_ch    = _connected_components(dtype_ch, predicate=lambda v: v == DTYPE_DATE)
    density_cluster_ch = _connected_components(density_ch, predicate=lambda v: v == 1)

    # Derived: date_flow — per plan-marker, where dates extend.
    # NOT a mode classification; just a measurement of date-flow direction.
    # Encoding (kept simple for visualisation, but consumers should use the
    # raw extents from dtype_run_col / dtype_run_row directly):
    #   0 = no marker
    #   1 = dates extend mostly DOWN  (more dates in same col)
    #   2 = dates extend mostly RIGHT (more dates in same row)
    #   3 = dates extend in BOTH / extents comparable
    date_flow_ch = [[0] * n_cols for _ in range(n_rows)]
    for r in range(n_rows):
        for c in range(n_cols):
            if plan_ch[r][c] != 1: continue
            dates_right = sum(1 for cc in range(c + 1, n_cols) if dtype_ch[r][cc] == DTYPE_DATE)
            dates_below = sum(1 for rr in range(r + 1, n_rows) if dtype_ch[rr][c] == DTYPE_DATE)
            if dates_below >= 2 and dates_below > dates_right * 1.5:
                date_flow_ch[r][c] = 1
            elif dates_right >= 2 and dates_right > dates_below * 1.5:
                date_flow_ch[r][c] = 2
            elif dates_below + dates_right >= 2:
                date_flow_ch[r][c] = 3
            else:
                date_flow_ch[r][c] = 0

    canvas = GridCanvas(n_rows=n_rows, n_cols=n_cols, cell_values=raw)
    canvas.add_channel("dtype",       dtype_ch)
    canvas.add_channel("density",     density_ch)
    canvas.add_channel("plan_marker", plan_ch)
    canvas.add_channel("fill_color",  fill_ch)
    canvas.add_channel("border",      border_ch)
    canvas.add_channel("merge",       merge_ch)
    canvas.add_channel("date_like",   date_like_ch)
    canvas.add_channel("text_density_per_row", text_density_ch)
    canvas.add_channel("dtype_run_row",   dtype_run_row_ch)
    canvas.add_channel("dtype_run_col",   dtype_run_col_ch)
    canvas.add_channel("date_cluster",    date_cluster_ch)
    canvas.add_channel("density_cluster", density_cluster_ch)
    canvas.add_channel("date_flow",       date_flow_ch)
    canvas.add_channel("bold",            bold_ch)
    canvas.add_channel("merge_shape",     merge_shape_ch)

    # Derived: repeating_row_id — group rows that have IDENTICAL content
    # signatures. Each repeating group gets a unique ID; unique rows get 0.
    # Catches: section-header rows that recur (GUESS), banner rows, totals etc.
    def _sig(values):
        parts = []
        for v in values:
            if v in (None, ""): parts.append("")
            else: parts.append(str(v).strip().lower())
        return "\x01".join(parts)

    row_sigs: dict[str, list[int]] = {}
    for r in range(n_rows):
        sig = _sig([raw[r][c] for c in range(n_cols)])
        # Skip rows that are entirely blank
        if not sig.replace("\x01", ""): continue
        row_sigs.setdefault(sig, []).append(r)

    repeating_row_id_ch = [[0] * n_cols for _ in range(n_rows)]
    next_id = 0
    for sig, rows in row_sigs.items():
        if len(rows) < 2: continue
        next_id += 1
        for r in rows:
            for c in range(n_cols):
                repeating_row_id_ch[r][c] = next_id
    canvas.add_channel("repeating_row_id", repeating_row_id_ch)

    # Same for columns
    col_sigs: dict[str, list[int]] = {}
    for c in range(n_cols):
        sig = _sig([raw[r][c] for r in range(n_rows)])
        if not sig.replace("\x01", ""): continue
        col_sigs.setdefault(sig, []).append(c)

    repeating_col_id_ch = [[0] * n_cols for _ in range(n_rows)]
    next_id = 0
    for sig, cols in col_sigs.items():
        if len(cols) < 2: continue
        next_id += 1
        for c in cols:
            for r in range(n_rows):
                repeating_col_id_ch[r][c] = next_id
    canvas.add_channel("repeating_col_id", repeating_col_id_ch)

    # Derived: empty_row — broadcast per-row emptiness (1 if entire row is blank)
    empty_row_ch = [[0] * n_cols for _ in range(n_rows)]
    for r in range(n_rows):
        if all(density_ch[r][c] == 0 for c in range(n_cols)):
            for c in range(n_cols):
                empty_row_ch[r][c] = 1
    canvas.add_channel("empty_row", empty_row_ch)

    # Derived: empty_col — broadcast per-col emptiness
    empty_col_ch = [[0] * n_cols for _ in range(n_rows)]
    for c in range(n_cols):
        if all(density_ch[r][c] == 0 for r in range(n_rows)):
            for r in range(n_rows):
                empty_col_ch[r][c] = 1
    canvas.add_channel("empty_col", empty_col_ch)

    # Derived: fill_color_cluster — connected components by fill color group
    fill_cluster_ch = _connected_components(fill_ch, predicate=lambda v: v > 0)
    canvas.add_channel("fill_color_cluster", fill_cluster_ch)

    # Derived: column_dtype_dominant — per col, the dominant non-blank dtype, repeated down the col
    col_dom_ch = [[0] * n_cols for _ in range(n_rows)]
    for c in range(n_cols):
        cnt = Counter(dtype_ch[r][c] for r in range(n_rows) if dtype_ch[r][c] != DTYPE_BLANK)
        if not cnt: continue
        dom = cnt.most_common(1)[0][0]
        for r in range(n_rows):
            col_dom_ch[r][c] = dom
    canvas.add_channel("column_dtype_dominant", col_dom_ch)
    canvas.merge_ranges = set(merge_ranges_list)
    return canvas


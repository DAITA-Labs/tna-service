"""Decisions composed from canvas measurements.

No mode-classification. Each decision reads multiple channels and emits a
finding. New TNA layouts work if their measurements still trigger the
decision rules — extension means adding a new measurement, not a new case.
"""
from __future__ import annotations

from dataclasses import dataclass
from openpyxl.utils import column_index_from_string, get_column_letter
from build_canvas import GridCanvas, DTYPE_DATE, DTYPE_STR, query_term_density


@dataclass
class Rect:
    r0: int; c0: int; r1: int; c1: int   # 1-indexed inclusive
    @property
    def area(self) -> int: return (self.r1 - self.r0 + 1) * (self.c1 - self.c0 + 1)
    def __repr__(self) -> str:
        return f"Rect({get_column_letter(self.c0)}{self.r0}:{get_column_letter(self.c1)}{self.r1}, area={self.area})"


# =============================================================================
# Cluster utilities
# =============================================================================

def cluster_bboxes(canvas: GridCanvas, channel_name: str) -> dict[int, Rect]:
    """For each non-zero cluster ID in the channel, return its bounding box."""
    matrix = canvas.channels[channel_name]
    boxes: dict[int, list[int]] = {}
    for r in range(canvas.n_rows):
        for c in range(canvas.n_cols):
            cid = matrix[r][c]
            if cid == 0: continue
            if cid not in boxes:
                boxes[cid] = [r, c, r, c]
            else:
                b = boxes[cid]
                if r < b[0]: b[0] = r
                if c < b[1]: b[1] = c
                if r > b[2]: b[2] = r
                if c > b[3]: b[3] = c
    return {cid: Rect(b[0]+1, b[1]+1, b[2]+1, b[3]+1) for cid, b in boxes.items()}


# =============================================================================
# Decision 1 — Find header rows
# =============================================================================

DEFAULT_IDENTIFIER_TERMS = [
    "io", "ion", "po", "buyer", "style", "color", "colour",
    "fabric", "qty", "quantity", "season", "factory", "date",
    "delivery", "shipment", "ex factory", "ex-factory",
]


def find_header_rows(canvas: GridCanvas, min_score: float = 1.0) -> list[tuple[int, float, dict]]:
    """Score each row using spec-alias hits (per phase) + bold + fill density.

    Spec hits dominate the score (they tell us the row contains field labels).
    Bold + fill density act as tie-breakers / boosters.

    Returns: [(row_1idx, total_score, breakdown_dict), ...] sorted desc.
    """
    from spec_queries import find_header_rows_via_specs, query_all, aggregate_by_row
    n_rows, n_cols = canvas.n_rows, canvas.n_cols

    # Spec-driven scoring (this is the load-bearing signal)
    spec_scored = find_header_rows_via_specs(canvas, min_score=0.0)
    spec_by_row = {row: (score, breakdown) for row, score, breakdown in spec_scored}

    # Add bold + fill density as boosters
    bold_density = {
        r + 1: sum(canvas.channels["bold"][r][c] for c in range(n_cols)) / max(1, n_cols)
        for r in range(n_rows)
    }
    fill_density = {
        r + 1: sum(1 for c in range(n_cols) if canvas.channels["fill_color"][r][c] > 0) / max(1, n_cols)
        for r in range(n_rows)
    }

    scores = []
    for r in range(n_rows):
        row = r + 1
        if canvas.channels["empty_row"][r][0] == 1: continue
        spec_score, breakdown = spec_by_row.get(row, (0.0, {}))
        booster = 1.0 * bold_density.get(row, 0.0) + 1.0 * fill_density.get(row, 0.0)
        total = spec_score + booster
        if total > 0:
            full_breakdown = dict(breakdown)
            full_breakdown["bold"] = round(bold_density.get(row, 0.0), 3)
            full_breakdown["fill"] = round(fill_density.get(row, 0.0), 3)
            scores.append((row, round(total, 2), full_breakdown))
    scores.sort(key=lambda x: -x[1])
    return [s for s in scores if s[1] >= min_score]


# =============================================================================
# Decision 2 — Find data regions (any cluster of non-blank cells)
# =============================================================================

def find_data_regions(canvas: GridCanvas, min_area: int = 12) -> list[Rect]:
    boxes = cluster_bboxes(canvas, "density_cluster")
    return sorted([b for b in boxes.values() if b.area >= min_area], key=lambda b: -b.area)


# =============================================================================
# Decision 3 — Find stage arenas (date clusters that have a plan marker)
# =============================================================================

def _col_overlap(a: Rect, b: Rect) -> float:
    """Fraction of the narrower box's columns that overlap with the wider."""
    lo = max(a.c0, b.c0)
    hi = min(a.c1, b.c1)
    if hi < lo: return 0.0
    overlap = hi - lo + 1
    narrower = min(a.c1 - a.c0 + 1, b.c1 - b.c0 + 1)
    return overlap / max(1, narrower)


def _merge_rects_by_column(arenas: list[Rect], min_col_overlap: float = 0.7) -> list[Rect]:
    """Merge arenas that share most of their column footprint into vertical
    strips. Handles fragmented section-style layouts where the same physical
    column carries dates for many PLI blocks but blank rows between blocks
    break the date_cluster into pieces.
    """
    arenas = sorted(arenas, key=lambda b: (b.c0, b.r0))
    merged: list[Rect] = []
    for a in arenas:
        placed = False
        for i, m in enumerate(merged):
            if _col_overlap(a, m) >= min_col_overlap:
                merged[i] = Rect(min(a.r0, m.r0), min(a.c0, m.c0),
                                 max(a.r1, m.r1), max(a.c1, m.c1))
                placed = True; break
        if not placed:
            merged.append(a)
    return sorted(merged, key=lambda b: (b.r0, b.c0))


def find_stage_arenas(canvas: GridCanvas, max_plan_offset: int = 3) -> list[Rect]:
    """A stage arena = a date cluster with at least one plan-marker cell in
    its neighbourhood (within / above / left). Returns fragmented arenas as
    found — preserves per-block separation needed for per-PLI extraction in
    SHEET_IS_PLI / SECTION_PER_PLI layouts.
    """
    boxes = cluster_bboxes(canvas, "date_cluster")
    arenas = []
    plan_ch = canvas.channels["plan_marker"]
    for cid, box in boxes.items():
        r_start = max(0, box.r0 - 1 - max_plan_offset)
        r_end   = min(canvas.n_rows - 1, box.r1 - 1)
        c_start = max(0, box.c0 - 1 - max_plan_offset)
        c_end   = min(canvas.n_cols - 1, box.c1 - 1)
        has_plan = False
        for r in range(r_start, r_end + 1):
            for c in range(c_start, c_end + 1):
                if plan_ch[r][c] == 1:
                    has_plan = True
                    break
            if has_plan: break
        if has_plan and box.area >= 2:
            arenas.append(box)
    return sorted(arenas, key=lambda b: (b.r0, b.c0))


def find_arena_strips(arenas: list[Rect], min_col_overlap: float = 0.9) -> list[Rect]:
    """Logical column strips formed by collapsing arenas with near-identical
    column footprint into one. Distinct from `find_stage_arenas` — strips are
    for validation coverage (orphan-date check), not per-PLI extraction.
    """
    if not arenas: return []
    return _merge_rects_by_column(arenas, min_col_overlap=min_col_overlap)


# =============================================================================
# Decision 4 — Determine date-flow direction within an arena
# =============================================================================

def determine_arena_direction(canvas: GridCanvas, arena: Rect) -> str:
    """Returns 'row' (dates flow down per col), 'col' (dates flow right per row),
    or 'mixed'. Uses dtype_run_col / dtype_run_row maximums within the arena.
    """
    rrc = canvas.channels["dtype_run_col"]
    rrr = canvas.channels["dtype_run_row"]
    dt  = canvas.channels["dtype"]
    max_col_run, max_row_run = 0, 0
    for r in range(arena.r0 - 1, arena.r1):
        for c in range(arena.c0 - 1, arena.c1):
            if dt[r][c] != DTYPE_DATE: continue
            if rrc[r][c] > max_col_run: max_col_run = rrc[r][c]
            if rrr[r][c] > max_row_run: max_row_run = rrr[r][c]
    if max_col_run > max_row_run * 1.5: return "row"
    if max_row_run > max_col_run * 1.5: return "col"
    return "mixed"


# =============================================================================
# Decision 5 — Identifier zone (what's NOT in stage arenas)
# =============================================================================

def find_identifier_zone(canvas: GridCanvas,
                          data_region: Rect,
                          stage_arenas: list[Rect]) -> Rect | None:
    """Approximate identifier zone = data_region minus columns spanned by
    stage_arenas (we assume identifiers live to the LEFT of stage arenas in
    most layouts, but the channel approach lets either case work).
    """
    if not stage_arenas:
        return data_region
    # Take the leftmost stage arena; identifier zone is data_region clipped to
    # cols left of it (if non-empty).
    leftmost_arena_c = min(a.c0 for a in stage_arenas)
    if leftmost_arena_c <= data_region.c0:
        return None
    return Rect(data_region.r0, data_region.c0, data_region.r1, leftmost_arena_c - 1)


# =============================================================================
# Decision 6 — Empty-row sections (split data into sections separated by blank rows)
# =============================================================================

def find_empty_row_runs(canvas: GridCanvas, min_run: int = 1) -> list[tuple[int, int]]:
    """Return runs of consecutive empty rows (start, end) inclusive — 1-indexed."""
    runs = []
    in_run = False
    start = None
    for r in range(canvas.n_rows):
        is_empty = canvas.channels["empty_row"][r][0] == 1
        if is_empty and not in_run:
            in_run = True; start = r + 1
        elif not is_empty and in_run:
            end = r
            if end - start + 1 >= min_run:
                runs.append((start, end))
            in_run = False
    if in_run:
        runs.append((start, canvas.n_rows))
    return runs


# =============================================================================
# Composite — produce a Findings dict for a sheet
# =============================================================================

def analyze(canvas: GridCanvas, identifier_terms: list[str] = None) -> dict:
    headers       = find_header_rows(canvas)
    data_regions  = find_data_regions(canvas)
    stage_arenas  = find_stage_arenas(canvas)
    arena_dirs    = {f"{i}": determine_arena_direction(canvas, a)
                     for i, a in enumerate(stage_arenas)}
    biggest_dr    = data_regions[0] if data_regions else None
    identifier_zone = find_identifier_zone(canvas, biggest_dr, stage_arenas) if biggest_dr else None
    empty_runs    = find_empty_row_runs(canvas, min_run=1)
    return {
        "header_rows":      headers[:5],
        "data_regions":     data_regions[:5],
        "stage_arenas":     stage_arenas,
        "arena_directions": arena_dirs,
        "identifier_zone":  identifier_zone,
        "empty_row_runs":   empty_runs,
    }

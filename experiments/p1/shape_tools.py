"""Deterministic shape-inspection tools (with A/B/C variants).

The variants are SEPARATE FUNCTIONS so the harness can run them side-by-side
and the report can compare their outputs. There is no "switch flag" — to
swap a variant the caller picks a different function.

Conventions:
    - rows / cols are 1-indexed (openpyxl convention).
    - `cells_grid` is a 2-D list of openpyxl Cell objects, indexed
      cells_grid[r-1][c-1], shape (total_rows, total_cols).
      The harness materialises this ONCE per file (see `materialise_grid`).
"""
from __future__ import annotations

import datetime as _dt
import re
from collections import deque
from typing import Iterable

from openpyxl.utils.cell import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from experiments.specs.enums import ValuePattern
from experiments.specs.identifiers import IDENTIFIER_SPECS
from experiments.specs.metadata import METADATA_SPECS
from experiments.specs.stages import STAGE_SPECS

from .shape_models import (
    BlankRun,
    CellRef,
    ColumnDtypeProfile,
    HeaderCandidate,
    MergedRange,
    Rect,
    RepeatedLabelHit,
)


# =============================================================================
# Vocab — flat alias sets pulled from specs (lower-cased, stripped)
# =============================================================================


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


IDENTIFIER_ALIASES: set[str] = set()
for _spec in IDENTIFIER_SPECS:
    IDENTIFIER_ALIASES.add(_norm(_spec.canonical))
    for _a in _spec.aliases:
        IDENTIFIER_ALIASES.add(_norm(_a))

STAGE_ALIASES: set[str] = set()
for _spec in STAGE_SPECS:
    STAGE_ALIASES.add(_norm(_spec.canonical))
    for _a in _spec.aliases:
        STAGE_ALIASES.add(_norm(_a))

METADATA_ALIASES: set[str] = set()
for _spec in METADATA_SPECS:
    METADATA_ALIASES.add(_norm(_spec.canonical))
    for _a in _spec.aliases:
        METADATA_ALIASES.add(_norm(_a))

# IO-specific vocab — used by relevance gate
IO_VOCAB: set[str] = {
    "io", "io no", "io #", "io number", "io.no", "ionumber",
    "internal order", "internal order no", "io ref", "io reference",
    "internal ref", "tn no",
}


# =============================================================================
# Grid materialisation
# =============================================================================


def materialise_grid(sheet: Worksheet) -> list[list]:
    """Read the whole sheet once into a 2-D list of Cell objects.

    Calling sheet.iter_rows() repeatedly is expensive on large sheets, so
    each shape tool takes this pre-materialised grid.
    """
    return [list(row) for row in sheet.iter_rows(values_only=False)]


def grid_shape(grid: list[list]) -> tuple[int, int]:
    rows = len(grid)
    cols = max((len(r) for r in grid), default=0)
    return rows, cols


# =============================================================================
# Cell-level value helpers
# =============================================================================

_TRIVIAL_VALUES = {"", "-", "--", "—", "n/a", "na", "tbd", "tba", "?", "."}


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _is_trivial(value) -> bool:
    """True for blank, dashes, 'N/A', whitespace-only — anything that conveys
    'no data here' even if technically non-None."""
    if _is_blank(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in _TRIVIAL_VALUES
    return False


# Patterns for detecting dates stored as strings (frequently seen in
# supplier-exported TNAs where the export pipeline stringifies dates).
_DATE_STR_PATTERNS = [
    re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$"),                  # 29-04-2026 / 29/04/26
    re.compile(r"^\d{1,2}[-/. ][A-Za-z]{3,9}[-/. ]\d{2,4}$"),           # 29-APR-2026, 29 Apr 2026
    re.compile(r"^[A-Za-z]{3,9}[-/. ]\d{1,2}[-/. ]\d{2,4}$"),           # Apr 29 2026
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$"),                    # 2026-04-29
]


def _looks_like_date_string(s: str) -> bool:
    s = s.strip()
    if not s or len(s) > 24:
        return False
    return any(p.match(s) for p in _DATE_STR_PATTERNS)


def _dtype_of(value) -> str:
    """Coarse dtype tag for a cell value."""
    if _is_blank(value):
        return "blank"
    if isinstance(value, (_dt.date, _dt.datetime)):
        return "date"
    if isinstance(value, bool):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        # treat NaN-like as blank for our purposes
        if value != value:
            return "blank"
        if float(value).is_integer():
            return "int"
        return "int"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "blank"
        if _looks_like_date_string(s):
            return "date"
        return "str"
    return "str"


# =============================================================================
# Density — three variants
# =============================================================================


def density_by_non_blank(grid: list[list], axis: str = "row") -> list[float]:
    """Variant A — fraction of cells that are not None / not empty string."""
    rows, cols = grid_shape(grid)
    if axis == "row":
        out: list[float] = []
        for r in range(rows):
            row = grid[r]
            n = len(row) if row else cols
            if n == 0:
                out.append(0.0)
                continue
            non_blank = sum(1 for c in row if not _is_blank(c.value))
            out.append(non_blank / cols if cols else 0.0)
        return out
    # axis == "col"
    out_c: list[float] = [0.0] * cols
    for c in range(cols):
        cnt = 0
        for r in range(rows):
            row = grid[r]
            if c < len(row) and not _is_blank(row[c].value):
                cnt += 1
        out_c[c] = cnt / rows if rows else 0.0
    return out_c


def density_by_content(grid: list[list], axis: str = "row") -> list[float]:
    """Variant B — like A but trivial values ('-', '—', 'N/A', whitespace)
    count as blank.
    """
    rows, cols = grid_shape(grid)
    if axis == "row":
        out: list[float] = []
        for r in range(rows):
            row = grid[r]
            non_trivial = sum(1 for c in row if not _is_trivial(c.value))
            out.append(non_trivial / cols if cols else 0.0)
        return out
    out_c: list[float] = [0.0] * cols
    for c in range(cols):
        cnt = 0
        for r in range(rows):
            row = grid[r]
            if c < len(row) and not _is_trivial(row[c].value):
                cnt += 1
        out_c[c] = cnt / rows if rows else 0.0
    return out_c


_DTYPE_WEIGHT = {"date": 2.0, "int": 1.5, "str": 1.0, "blank": 0.0}


def density_by_dtype_weighted(grid: list[list], axis: str = "row") -> list[float]:
    """Variant C — sum of per-cell dtype weights, normalised to max possible.

    Max weight = total cells * 2.0 (if everything were dates). We rescale to
    [0,1] using that max so values stay comparable to other variants.
    """
    rows, cols = grid_shape(grid)
    max_w = 2.0  # date weight
    if axis == "row":
        out: list[float] = []
        for r in range(rows):
            row = grid[r]
            s = sum(_DTYPE_WEIGHT[_dtype_of(c.value)] for c in row)
            denom = (cols * max_w) if cols else 1.0
            out.append(s / denom)
        return out
    out_c: list[float] = [0.0] * cols
    for c in range(cols):
        s = 0.0
        for r in range(rows):
            row = grid[r]
            if c < len(row):
                s += _DTYPE_WEIGHT[_dtype_of(row[c].value)]
        denom = (rows * max_w) if rows else 1.0
        out_c[c] = s / denom
    return out_c


# =============================================================================
# Rectangle detection — three variants
# =============================================================================


def flood_fill_rectangles(grid: list[list], min_area: int = 9) -> list[Rect]:
    """Variant A — BFS over non-trivial cells (4-connectivity).

    Group every connected non-trivial cell; emit each region's bounding
    rectangle with its non-trivial density. Returns rects ordered by area
    descending. Skips singletons and tiny clusters (area < min_area).
    """
    rows, cols = grid_shape(grid)
    visited = [[False] * cols for _ in range(rows)]

    def is_filled(r: int, c: int) -> bool:
        if r < 0 or r >= rows:
            return False
        row = grid[r]
        if c < 0 or c >= len(row):
            return False
        return not _is_trivial(row[c].value)

    rects: list[Rect] = []
    for r in range(rows):
        for c in range(cols):
            if visited[r][c] or not is_filled(r, c):
                continue
            # BFS
            q = deque([(r, c)])
            visited[r][c] = True
            r0 = r1 = r
            c0 = c1 = c
            count = 0
            while q:
                cr, cc = q.popleft()
                count += 1
                if cr < r0: r0 = cr
                if cr > r1: r1 = cr
                if cc < c0: c0 = cc
                if cc > c1: c1 = cc
                for nr, nc in ((cr-1, cc), (cr+1, cc), (cr, cc-1), (cr, cc+1)):
                    if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and is_filled(nr, nc):
                        visited[nr][nc] = True
                        q.append((nr, nc))
            area = (r1 - r0 + 1) * (c1 - c0 + 1)
            if area < min_area:
                continue
            density = count / area
            rects.append(Rect(
                r0=r0 + 1, c0=c0 + 1, r1=r1 + 1, c1=c1 + 1,
                density=density, area=area,
            ))
    rects.sort(key=lambda x: x.area, reverse=True)
    return rects


def density_threshold_grid(
    grid: list[list],
    row_thresh: float = 0.2,
    col_thresh: float = 0.3,
    min_area: int = 16,
) -> list[Rect]:
    """Variant B — intersect dense rows × dense cols; emit merged rects.

    Two-pass:
        1. Group consecutive ROWS with density >= row_thresh into row-bands.
        2. For EACH row band, compute col-density restricted to those rows
           and group consecutive cols with density >= col_thresh into col-bands.
        3. Emit (row_band × col_band) intersection rects.

    The second step is critical: in TNA sheets, the global col-density is
    diluted by many empty rows above/below the data band, so the band-local
    col-density gives a much cleaner signal.
    """
    rows, cols = grid_shape(grid)
    row_dens = density_by_content(grid, "row")

    def runs(values: list[float], threshold: float) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        start: int | None = None
        for i, v in enumerate(values):
            if v >= threshold:
                if start is None:
                    start = i
            else:
                if start is not None:
                    out.append((start, i - 1))
                    start = None
        if start is not None:
            out.append((start, len(values) - 1))
        return out

    def _merge_close_bands(
        bands: list[tuple[int, int]], gap: int = 2
    ) -> list[tuple[int, int]]:
        """Merge bands separated by gaps <= `gap` indices apart.

        Without this, a header row with sparse sub-labels splits the
        col-band into many fragments. Dilation+erosion semantics.
        """
        if not bands:
            return bands
        out = [bands[0]]
        for start, end in bands[1:]:
            ps, pe = out[-1]
            if start - pe <= gap + 1:
                out[-1] = (ps, end)
            else:
                out.append((start, end))
        return out

    row_bands = _merge_close_bands(runs(row_dens, row_thresh), gap=1)

    def _col_density_in_band(r0: int, r1: int) -> list[float]:
        n_band_rows = r1 - r0 + 1
        out: list[float] = [0.0] * cols
        if n_band_rows <= 0:
            return out
        for c in range(cols):
            cnt = 0
            for r in range(r0, r1 + 1):
                row = grid[r]
                if c < len(row) and not _is_trivial(row[c].value):
                    cnt += 1
            out[c] = cnt / n_band_rows
        return out

    rects: list[Rect] = []
    for r0, r1 in row_bands:
        band_col_dens = _col_density_in_band(r0, r1)
        col_bands = _merge_close_bands(runs(band_col_dens, col_thresh), gap=5)
        for c0, c1 in col_bands:
            n_cells = (r1 - r0 + 1) * (c1 - c0 + 1)
            if n_cells < min_area:
                continue
            non_trivial = 0
            for rr in range(r0, r1 + 1):
                row = grid[rr]
                for cc in range(c0, c1 + 1):
                    if cc < len(row) and not _is_trivial(row[cc].value):
                        non_trivial += 1
            density = non_trivial / n_cells if n_cells else 0.0
            if density < 0.25:
                continue
            rects.append(Rect(
                r0=r0 + 1, c0=c0 + 1, r1=r1 + 1, c1=c1 + 1,
                density=density, area=n_cells,
            ))
    rects.sort(key=lambda x: x.area, reverse=True)
    return rects


def hybrid_rectangles(grid: list[list]) -> list[Rect]:
    """Variant C — start with threshold rects, shrink boundaries inward
    while edge density drops sharply.

    Concretely: take each rect from density_threshold_grid, then on each
    edge, trim the outermost row/col if its local density < 0.5 of the
    rect interior's density.
    """
    seed = density_threshold_grid(grid)
    rows, cols = grid_shape(grid)
    refined: list[Rect] = []
    for rect in seed:
        r0, r1 = rect.r0 - 1, rect.r1 - 1
        c0, c1 = rect.c0 - 1, rect.c1 - 1
        interior_density = rect.density

        def _row_density(rr: int) -> float:
            row = grid[rr]
            n = c1 - c0 + 1
            if n == 0:
                return 0.0
            cnt = sum(
                1 for cc in range(c0, c1 + 1)
                if cc < len(row) and not _is_trivial(row[cc].value)
            )
            return cnt / n

        def _col_density(cc: int) -> float:
            n = r1 - r0 + 1
            if n == 0:
                return 0.0
            cnt = sum(
                1 for rr in range(r0, r1 + 1)
                if cc < len(grid[rr]) and not _is_trivial(grid[rr][cc].value)
            )
            return cnt / n

        # trim top
        while r0 < r1 and _row_density(r0) < 0.5 * interior_density:
            r0 += 1
        # trim bottom
        while r1 > r0 and _row_density(r1) < 0.5 * interior_density:
            r1 -= 1
        # trim left
        while c0 < c1 and _col_density(c0) < 0.5 * interior_density:
            c0 += 1
        # trim right
        while c1 > c0 and _col_density(c1) < 0.5 * interior_density:
            c1 -= 1
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        if area < 9:
            continue
        non_trivial = 0
        for rr in range(r0, r1 + 1):
            row = grid[rr]
            for cc in range(c0, c1 + 1):
                if cc < len(row) and not _is_trivial(row[cc].value):
                    non_trivial += 1
        density = non_trivial / area if area else 0.0
        refined.append(Rect(
            r0=r0 + 1, c0=c0 + 1, r1=r1 + 1, c1=c1 + 1,
            density=density, area=area,
        ))
    refined.sort(key=lambda x: x.area, reverse=True)
    return refined


# =============================================================================
# Blank-run detection — three variants
# =============================================================================


def strict_blank(grid: list[list], axis: str = "row", min_len: int = 2) -> list[BlankRun]:
    """Variant A — runs of >= min_len rows/cols that are ALL blank."""
    rows, cols = grid_shape(grid)
    runs: list[BlankRun] = []
    if axis == "row":
        start: int | None = None
        for r in range(rows):
            row = grid[r]
            all_blank = all(_is_blank(c.value) for c in row)
            if all_blank:
                if start is None:
                    start = r
            else:
                if start is not None and (r - 1 - start + 1) >= min_len:
                    runs.append(BlankRun(start=start + 1, end=r, axis="row"))
                start = None
        if start is not None and (rows - 1 - start + 1) >= min_len:
            runs.append(BlankRun(start=start + 1, end=rows, axis="row"))
        return runs
    # axis == "col"
    start_c: int | None = None
    for c in range(cols):
        all_blank = all(
            (c >= len(grid[r])) or _is_blank(grid[r][c].value)
            for r in range(rows)
        )
        if all_blank:
            if start_c is None:
                start_c = c
        else:
            if start_c is not None and (c - 1 - start_c + 1) >= min_len:
                runs.append(BlankRun(start=start_c + 1, end=c, axis="col"))
            start_c = None
    if start_c is not None and (cols - 1 - start_c + 1) >= min_len:
        runs.append(BlankRun(start=start_c + 1, end=cols, axis="col"))
    return runs


def relaxed_blank(grid: list[list], axis: str = "row", min_len: int = 2) -> list[BlankRun]:
    """Variant B — runs where AT MOST 1 cell has content (per row/col)."""
    rows, cols = grid_shape(grid)
    runs: list[BlankRun] = []
    if axis == "row":
        start: int | None = None
        for r in range(rows):
            row = grid[r]
            non_blank = sum(1 for c in row if not _is_trivial(c.value))
            mostly_blank = non_blank <= 1
            if mostly_blank:
                if start is None:
                    start = r
            else:
                if start is not None and (r - 1 - start + 1) >= min_len:
                    runs.append(BlankRun(start=start + 1, end=r, axis="row"))
                start = None
        if start is not None and (rows - 1 - start + 1) >= min_len:
            runs.append(BlankRun(start=start + 1, end=rows, axis="row"))
        return runs
    start_c: int | None = None
    for c in range(cols):
        non_blank = 0
        for r in range(rows):
            if c < len(grid[r]) and not _is_trivial(grid[r][c].value):
                non_blank += 1
        mostly_blank = non_blank <= 1
        if mostly_blank:
            if start_c is None:
                start_c = c
        else:
            if start_c is not None and (c - 1 - start_c + 1) >= min_len:
                runs.append(BlankRun(start=start_c + 1, end=c, axis="col"))
            start_c = None
    if start_c is not None and (cols - 1 - start_c + 1) >= min_len:
        runs.append(BlankRun(start=start_c + 1, end=cols, axis="col"))
    return runs


def density_below_threshold(
    grid: list[list], axis: str = "row", threshold: float = 0.1, min_len: int = 2
) -> list[BlankRun]:
    """Variant C — runs where row/col density < threshold."""
    rows, cols = grid_shape(grid)
    if axis == "row":
        dens = density_by_content(grid, "row")
        runs: list[BlankRun] = []
        start: int | None = None
        for i, v in enumerate(dens):
            if v < threshold:
                if start is None:
                    start = i
            else:
                if start is not None and (i - 1 - start + 1) >= min_len:
                    runs.append(BlankRun(start=start + 1, end=i, axis="row"))
                start = None
        if start is not None and (len(dens) - 1 - start + 1) >= min_len:
            runs.append(BlankRun(start=start + 1, end=len(dens), axis="row"))
        return runs
    dens = density_by_content(grid, "col")
    runs: list[BlankRun] = []
    start_c: int | None = None
    for i, v in enumerate(dens):
        if v < threshold:
            if start_c is None:
                start_c = i
        else:
            if start_c is not None and (i - 1 - start_c + 1) >= min_len:
                runs.append(BlankRun(start=start_c + 1, end=i, axis="col"))
            start_c = None
    if start_c is not None and (len(dens) - 1 - start_c + 1) >= min_len:
        runs.append(BlankRun(start=start_c + 1, end=len(dens), axis="col"))
    return runs


# =============================================================================
# Header-row candidate detection — four variants
# =============================================================================


def _text_score_for_row(row: list, c0: int, c1: int) -> float:
    """Fraction of non-blank cells (in the col range) that are strings."""
    n = 0
    s = 0
    for c in range(c0, c1 + 1):
        if c < len(row):
            v = row[c].value
            if _is_blank(v):
                continue
            n += 1
            if isinstance(v, str):
                s += 1
    return (s / n) if n else 0.0


def text_density_above_data(
    grid: list[list], biggest_rect: Rect, min_score: float = 0.5
) -> list[HeaderCandidate]:
    """Variant A — for each row from r0 going up, score = text_pct.

    Includes the first few rows of the biggest_rect itself (header may BE
    the top of the rect).
    """
    candidates: list[HeaderCandidate] = []
    r0 = biggest_rect.r0 - 1
    c0 = biggest_rect.c0 - 1
    c1 = biggest_rect.c1 - 1
    start_search = max(0, r0 - 5)
    end_search = min(len(grid) - 1, r0 + 2)  # also consider rows inside the rect
    for r in range(start_search, end_search + 1):
        row = grid[r]
        score = _text_score_for_row(row, c0, c1)
        if score >= min_score:
            candidates.append(HeaderCandidate(
                row=r + 1, score=score, signal="text_density",
            ))
    return candidates


def vocab_match_count(grid: list[list], min_hits: int = 3) -> list[HeaderCandidate]:
    """Variant B — count cells whose text matches identifier OR stage vocab.

    Pull aliases from IDENTIFIER_ALIASES + STAGE_ALIASES. Score = number of
    distinct alias hits (we don't dedupe by canonical here; raw hit count is
    the signal). Use rapidfuzz for partial matching.
    """
    try:
        from rapidfuzz import fuzz
        have_fuzz = True
    except Exception:
        have_fuzz = False

    vocab = IDENTIFIER_ALIASES | STAGE_ALIASES
    rows = len(grid)
    candidates: list[HeaderCandidate] = []
    for r in range(rows):
        row = grid[r]
        hits = 0
        for cell in row:
            v = cell.value
            if not isinstance(v, str):
                continue
            s = _norm(v)
            if not s:
                continue
            if s in vocab:
                hits += 1
                continue
            if have_fuzz:
                # check substring containment for short labels
                if any(a in s or s in a for a in vocab if len(a) >= 3 and len(s) >= 3):
                    hits += 1
        if hits >= min_hits:
            candidates.append(HeaderCandidate(
                row=r + 1, score=float(hits), signal="vocab",
            ))
    return candidates


def styled_row(grid: list[list], min_pct: float = 0.5) -> list[HeaderCandidate]:
    """Variant C — rows where >= min_pct of non-blank cells are bold."""
    rows = len(grid)
    candidates: list[HeaderCandidate] = []
    for r in range(rows):
        row = grid[r]
        non_blank = 0
        bold = 0
        for cell in row:
            if _is_blank(cell.value):
                continue
            non_blank += 1
            try:
                if cell.font and cell.font.bold:
                    bold += 1
            except Exception:
                pass
        if non_blank == 0:
            continue
        pct = bold / non_blank
        if pct >= min_pct and non_blank >= 3:
            candidates.append(HeaderCandidate(
                row=r + 1, score=pct, signal="styled",
            ))
    return candidates


def merged_cell_anchor(sheet: Worksheet) -> list[HeaderCandidate]:
    """Variant D — rows containing at least one merged-cell anchor."""
    seen_rows: dict[int, int] = {}
    for rng in sheet.merged_cells.ranges:
        for r in range(rng.min_row, rng.max_row + 1):
            seen_rows[r] = seen_rows.get(r, 0) + 1
    candidates = [
        HeaderCandidate(row=r, score=float(n), signal="merged")
        for r, n in sorted(seen_rows.items())
    ]
    return candidates


# =============================================================================
# Pure tools (no variants)
# =============================================================================


def column_dtype_profile(
    grid: list[list], col_index: int, header_row: int | None = None,
    bottom_row: int | None = None,
) -> ColumnDtypeProfile:
    """Pct of date/int/str/blank in `col_index` across data rows.

    col_index, header_row, bottom_row are 1-indexed. Data rows are
    [header_row+1 .. bottom_row] inclusive. If header_row is None, we scan
    all rows starting at row 1.
    """
    rows = len(grid)
    h = (header_row or 0)
    b = (bottom_row or rows)
    start = h  # because h=row index in 1-based, data rows start at h+1 -> 0-based index = h
    end = min(b, rows)
    counts = {"date": 0, "int": 0, "str": 0, "blank": 0}
    n = 0
    c0 = col_index - 1
    for r in range(start, end):
        row = grid[r]
        if c0 < len(row):
            counts[_dtype_of(row[c0].value)] += 1
        else:
            counts["blank"] += 1
        n += 1
    if n == 0:
        return ColumnDtypeProfile(column=col_index, pattern=ValuePattern.BLANK)
    profile = ColumnDtypeProfile(
        column=col_index,
        date_pct=counts["date"] / n,
        int_pct=counts["int"] / n,
        str_pct=counts["str"] / n,
        blank_pct=counts["blank"] / n,
        n_rows=n,
        pattern=value_pattern_per_col(grid, col_index, header_row, bottom_row),
    )
    return profile


def value_pattern_per_col(
    grid: list[list], col_index: int, header_row: int | None = None,
    bottom_row: int | None = None,
) -> ValuePattern:
    """Coarse ValuePattern enum for a column."""
    rows = len(grid)
    h = header_row or 0
    b = min(bottom_row or rows, rows)
    c0 = col_index - 1
    counts = {"date": 0, "int_small": 0, "int_med": 0, "int_large": 0,
              "code_alnum": 0, "name_text": 0, "blank": 0}
    total = 0
    for r in range(h, b):
        row = grid[r]
        if c0 >= len(row):
            counts["blank"] += 1
            total += 1
            continue
        v = row[c0].value
        total += 1
        if _is_blank(v):
            counts["blank"] += 1
            continue
        if isinstance(v, (_dt.date, _dt.datetime)):
            counts["date"] += 1
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            iv = float(v)
            if iv != iv:  # NaN
                counts["blank"] += 1
                continue
            if -10 <= iv <= 10:
                counts["int_small"] += 1
            elif iv < 1000:
                counts["int_med"] += 1
            else:
                counts["int_large"] += 1
            continue
        if isinstance(v, str):
            s = v.strip()
            if not s:
                counts["blank"] += 1
                continue
            if _looks_like_date_string(s):
                counts["date"] += 1
                continue
            # alphanumeric tokens (short) → CODE_ALNUM; longer text → NAME_TEXT
            has_alpha = any(ch.isalpha() for ch in s)
            has_digit = any(ch.isdigit() for ch in s)
            if has_alpha and has_digit and len(s) <= 15:
                counts["code_alnum"] += 1
            elif len(s) <= 4 and not has_digit:
                counts["code_alnum"] += 1
            else:
                counts["name_text"] += 1
    if total == 0:
        return ValuePattern.BLANK

    # majority wins
    top = max(counts.items(), key=lambda kv: kv[1])
    if top[1] == 0:
        return ValuePattern.BLANK

    name, _ = top
    mapping = {
        "date": ValuePattern.DATE,
        "int_small": ValuePattern.INT_SMALL,
        "int_med": ValuePattern.INT_MEDIUM,
        "int_large": ValuePattern.INT_LARGE,
        "code_alnum": ValuePattern.CODE_ALNUM,
        "name_text": ValuePattern.NAME_TEXT,
        "blank": ValuePattern.BLANK,
    }
    # detect MIXED — no single category > 60%
    if top[1] / total < 0.6 and name != "blank":
        return ValuePattern.MIXED
    return mapping[name]


def detect_merge_patterns(sheet: Worksheet) -> list[MergedRange]:
    """All merged ranges on the sheet."""
    out: list[MergedRange] = []
    for rng in sheet.merged_cells.ranges:
        out.append(MergedRange(
            r0=rng.min_row, c0=rng.min_col,
            r1=rng.max_row, c1=rng.max_col,
        ))
    return out


def count_distinct_values_per_col(grid: list[list], col_index: int) -> int:
    seen = set()
    c0 = col_index - 1
    for row in grid:
        if c0 < len(row):
            v = row[c0].value
            if not _is_trivial(v):
                seen.add(v)
    return len(seen)


def count_hyperlinks(sheet: Worksheet) -> int:
    cnt = 0
    for row in sheet.iter_rows():
        for cell in row:
            if cell.hyperlink is not None:
                cnt += 1
    return cnt


def find_formula_cells(grid: list[list]) -> list[CellRef]:
    out: list[CellRef] = []
    for r, row in enumerate(grid, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell.value
            if isinstance(v, str) and v.startswith("="):
                out.append(CellRef.from_rc(r, c))
    return out


def detect_frozen_pane_anchor(sheet: Worksheet) -> CellRef | None:
    fp = getattr(sheet, "freeze_panes", None)
    if not fp:
        return None
    # fp is something like "B3" or a Cell reference
    try:
        # accept either a string or a cell
        if hasattr(fp, "coordinate"):
            coord = fp.coordinate
        else:
            coord = str(fp)
        from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
        col_str, row = coordinate_from_string(coord)
        col = column_index_from_string(col_str)
        return CellRef.from_rc(row, col)
    except Exception:
        return None


_DEFAULT_REPEAT_PATTERNS = (
    r"^PLI\s*\d+$",
    r"^Style\s*[#:.]?\s*\w+$",
    r"^Order\s+No\.?$",
    r"^Order\s*#$",
    r"^Buyer\s+Style\s+\w+$",
)


def find_repeated_label_pattern(
    grid: list[list], patterns: Iterable[str] = _DEFAULT_REPEAT_PATTERNS
) -> list[RepeatedLabelHit]:
    compiled = [(p, re.compile(p, re.IGNORECASE)) for p in patterns]
    out: list[RepeatedLabelHit] = []
    for r, row in enumerate(grid, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell.value
            if not isinstance(v, str):
                continue
            for raw, rx in compiled:
                if rx.search(v):
                    out.append(RepeatedLabelHit(
                        row=r, col=c, text=v[:60], pattern=raw,
                    ))
                    break
    return out


# =============================================================================
# Cell-level identifier / stage vocab hits — used by classification checks
# =============================================================================


def scan_identifier_hits(grid: list[list]) -> list[dict]:
    """Return list of {row, col, alias_matched, type='identifier'}."""
    out: list[dict] = []
    for r, row in enumerate(grid, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell.value
            if not isinstance(v, str):
                continue
            s = _norm(v).rstrip(":.").strip()
            if not s:
                continue
            if s in IDENTIFIER_ALIASES:
                out.append({"row": r, "col": c, "alias": s, "type": "identifier"})
    return out


def scan_stage_hits(grid: list[list]) -> list[dict]:
    out: list[dict] = []
    for r, row in enumerate(grid, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell.value
            if not isinstance(v, str):
                continue
            s = _norm(v)
            if not s:
                continue
            if s in STAGE_ALIASES:
                out.append({"row": r, "col": c, "alias": s, "type": "stage"})
    return out


def scan_metadata_hits(grid: list[list]) -> list[dict]:
    """Strip trailing punctuation like ':' before alias-matching so labels
    like 'Date :', 'Job No:', 'Quantity :' match.
    """
    out: list[dict] = []
    for r, row in enumerate(grid, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell.value
            if not isinstance(v, str):
                continue
            s = _norm(v).rstrip(":.").strip()
            if not s:
                continue
            if s in METADATA_ALIASES:
                out.append({"row": r, "col": c, "alias": s, "type": "metadata"})
    return out


def count_kv_adjacencies(grid: list[list]) -> int:
    """Count cells where a TEXT cell ending in ':' (or known-label) sits
    immediately left of a NON-TEXT (or date-string) value cell.

    This is the bottom-up KV signal: independent of vocab matching, it
    catches 'Date :', 'Job No', 'Ex-Fty date' style labels.
    """
    rows = len(grid)
    n = 0
    for r in range(rows):
        row = grid[r]
        for c in range(len(row) - 1):
            v = row[c].value
            nxt = row[c + 1].value if (c + 1) < len(row) else None
            if not isinstance(v, str):
                continue
            s = v.strip()
            if not s or len(s) > 30:
                continue
            looks_like_label = (
                s.endswith(":") or
                s.endswith(" :") or
                _norm(s).rstrip(":.").strip() in (IDENTIFIER_ALIASES | METADATA_ALIASES)
            )
            if not looks_like_label:
                continue
            # value must be non-blank and not itself a long text string
            if _is_blank(nxt):
                continue
            if isinstance(nxt, str):
                # accept short strings (codes) or date-strings as values; reject longer prose
                ns = nxt.strip()
                if len(ns) > 30 and not _looks_like_date_string(ns):
                    continue
            n += 1
    return n


def has_io_vocab(grid: list[list]) -> bool:
    for row in grid:
        for cell in row:
            v = cell.value
            if not isinstance(v, str):
                continue
            s = _norm(v)
            if s in IO_VOCAB:
                return True
            for token in IO_VOCAB:
                if token in s and len(token) >= 3:
                    return True
    return False


# =============================================================================
# First-relevant-sheet picker
# =============================================================================


def pick_first_relevant_sheet(wb) -> str | None:
    """Return the name of the first sheet with > 10 rows × > 2 cols of content.

    We use density_by_content to filter out instruction / template / cover
    sheets that contain a few cells of text but no actual TNA data.
    """
    for ws_name in wb.sheetnames:
        ws = wb[ws_name]
        grid = materialise_grid(ws)
        rows, cols = grid_shape(grid)
        if rows < 10 or cols < 3:
            continue
        # require at least ONE row with at least 3 non-trivial cells
        non_trivial_rows = 0
        non_trivial_cells = 0
        for row in grid:
            row_nt = sum(1 for c in row if not _is_trivial(c.value))
            non_trivial_cells += row_nt
            if row_nt >= 3:
                non_trivial_rows += 1
        if non_trivial_rows < 5:
            continue
        if non_trivial_cells < 30:
            continue
        return ws_name
    # fallback — first non-empty sheet
    for ws_name in wb.sheetnames:
        ws = wb[ws_name]
        grid = materialise_grid(ws)
        if any(not _is_trivial(c.value) for r in grid for c in r):
            return ws_name
    return None

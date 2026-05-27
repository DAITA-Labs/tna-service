"""Classification checks + multi-vote aggregator.

Each check is a pure function over a ShapeSummary. It returns a CheckResult
with:
    passes:     bool (always meaningful; relevance checks use this; mode/
                axis checks use it as "vote cast?")
    vote:       str | None — the PliMode/PliAxis it votes for (None = abstain)
    confidence: float — vote weight in [0..1]
    evidence:   dict — debug context (counts, ratios, cell refs)
"""
from __future__ import annotations

import statistics

from experiments.specs.enums import PliAxis, PliMode

from .shape_models import CheckResult, ShapeSummary, SheetClassification


# =============================================================================
# Relevance checks
# =============================================================================


def check_has_data_rectangle(shape: ShapeSummary) -> CheckResult:
    """Pass if at least one rect with area > 25 AND at least one col with
    date_pct > 0 (i.e. there's a date-bearing column somewhere)."""
    rect_ok = any(r.area > 25 for r in shape.rectangles)
    date_col_ok = any(p.date_pct > 0 for p in shape.col_profiles)
    passes = rect_ok and date_col_ok
    return CheckResult(
        name="has_data_rectangle",
        passes=passes,
        confidence=1.0 if passes else 0.0,
        evidence={
            "biggest_area": shape.biggest_rect.area if shape.biggest_rect else 0,
            "date_col_count": sum(1 for p in shape.col_profiles if p.date_pct > 0),
        },
    )


def check_not_navigation(shape: ShapeSummary) -> CheckResult:
    """Pass if hyperlink ratio < 10%."""
    ratio = shape.hyperlinks_count / shape.total_cells if shape.total_cells else 0.0
    passes = ratio < 0.10
    return CheckResult(
        name="not_navigation", passes=passes, confidence=1.0 if passes else 0.0,
        evidence={"ratio": ratio, "n": shape.hyperlinks_count},
    )


def check_not_summary(shape: ShapeSummary) -> CheckResult:
    """Pass if formula-cell ratio < 20%."""
    ratio = len(shape.formula_cells) / shape.total_cells if shape.total_cells else 0.0
    passes = ratio < 0.20
    return CheckResult(
        name="not_summary", passes=passes, confidence=1.0 if passes else 0.0,
        evidence={"ratio": ratio, "n": len(shape.formula_cells)},
    )


def check_has_io_signal(shape: ShapeSummary) -> CheckResult:
    """Pass if identifier_hits is non-empty OR has_io_vocab fired."""
    n_id = len(shape.identifier_hits)
    passes = n_id >= 1
    return CheckResult(
        name="has_io_signal", passes=passes, confidence=1.0 if passes else 0.0,
        evidence={"identifier_hits": n_id, "stage_hits": len(shape.stage_hits)},
    )


RELEVANCE_CHECKS = (
    check_has_data_rectangle,
    check_not_navigation,
    check_not_summary,
    check_has_io_signal,
)


# =============================================================================
# Mode-decision checks
# =============================================================================


def check_tall_table_shape(shape: ShapeSummary) -> CheckResult:
    """Tall biggest rect (h/w >= 2) AND high density AND NOT stripey → ROW_PER_PLI.

    The 'not stripey' filter rejects SHEET_IS_PLI sheets that happen to
    have a tall combined rect (multiple horizontal strips with gaps).
    """
    r = shape.biggest_rect
    if r is None:
        return CheckResult(name="tall_table_shape", passes=False, evidence={"reason": "no biggest_rect"})
    h = r.r1 - r.r0 + 1
    w = r.c1 - r.c0 + 1
    aspect = h / w if w else 0.0
    # detect stripeyness — alternating dense/sparse rows inside the rect
    in_rect = shape.row_density[r.r0 - 1 : r.r1]
    transitions = 0
    if in_rect:
        prev = in_rect[0] >= 0.3
        for v in in_rect[1:]:
            cur = v >= 0.3
            if cur != prev:
                transitions += 1
            prev = cur
    stripey = transitions >= 3
    passes = aspect >= 2.0 and r.density >= 0.5 and not stripey
    vote = PliMode.ROW_PER_PLI.value if passes else None
    conf = min(1.0, 0.5 + (aspect - 2.0) * 0.1) if passes else 0.0
    return CheckResult(
        name="tall_table_shape", passes=passes, vote=vote, confidence=conf,
        evidence={"h": h, "w": w, "aspect": round(aspect, 2),
                  "density": round(r.density, 2), "transitions": transitions,
                  "stripey": stripey},
    )


def check_date_arena_dominance(shape: ShapeSummary) -> CheckResult:
    """>=3 cols with date_pct > 0.5 inside biggest rect → ROW_PER_PLI.

    The biggest rect is where stage dates live in ROW_PER_PLI sheets, so a
    dense date arena is the canonical signal.
    """
    r = shape.biggest_rect
    if r is None:
        return CheckResult(name="date_arena_dominance", passes=False, evidence={"reason": "no biggest_rect"})
    cols_in_rect = [
        p for p in shape.col_profiles
        if r.c0 <= p.column <= r.c1
    ]
    n_date_cols = sum(1 for p in cols_in_rect if p.date_pct > 0.5)
    passes = n_date_cols >= 3
    vote = PliMode.ROW_PER_PLI.value if passes else None
    conf = min(1.0, n_date_cols / 5.0) if passes else 0.0
    return CheckResult(
        name="date_arena_dominance", passes=passes, vote=vote, confidence=conf,
        evidence={"date_cols": n_date_cols},
    )


def check_header_continuity(shape: ShapeSummary) -> CheckResult:
    """Best header row covers >= 70% of biggest_rect width AND sits at/just
    above rect.r0 AND has >= 5 data rows below → ROW_PER_PLI.

    The data-row floor (>= 5) rejects short strips: a 3-row block under a
    header row is a STAGE STRIP inside a SHEET_IS_PLI layout, not a
    ROW_PER_PLI table.
    """
    r = shape.biggest_rect
    if r is None or shape.best_header_row is None:
        return CheckResult(name="header_continuity", passes=False,
                           evidence={"reason": "no header"})
    if not (r.r0 - 2 <= shape.best_header_row <= r.r0 + 1):
        return CheckResult(
            name="header_continuity", passes=False,
            evidence={"header_row": shape.best_header_row, "rect_r0": r.r0,
                      "reason": "header_row not adjacent to rect.r0"},
        )
    # how many data rows below the header within the biggest rect?
    data_rows_below = r.r1 - max(shape.best_header_row, r.r0) + 1
    if data_rows_below < 4:
        return CheckResult(
            name="header_continuity", passes=False,
            evidence={"header_row": shape.best_header_row, "rect_r0": r.r0,
                      "rect_r1": r.r1, "data_rows_below": data_rows_below,
                      "reason": "too few data rows"},
        )
    cand = next((c for c in shape.header_candidates if c.row == shape.best_header_row), None)
    if cand is None:
        return CheckResult(name="header_continuity", passes=False)
    coverage = cand.score if cand.signal == "text_density" else min(1.0, cand.score / 5.0)
    # Header repetition guard: if MANY identifier-bearing rows exist below the
    # putative header row (i.e. the "header" repeats deep into the rect),
    # the layout is SECTION_PER_PLI, not ROW_PER_PLI. Count alias-bearing rows
    # below `best_header_row` (>= 3 spaced rows means repetition).
    alias_rows_below: set[int] = set()
    for h in shape.identifier_hits + shape.metadata_hits:
        if h["row"] > shape.best_header_row:
            alias_rows_below.add(h["row"])
    if len(alias_rows_below) >= 3:
        return CheckResult(
            name="header_continuity", passes=False,
            evidence={"header_row": shape.best_header_row,
                      "alias_rows_below": len(alias_rows_below),
                      "reason": "header repeats in body — not row_per_pli"},
        )
    passes = coverage >= 0.7
    vote = PliMode.ROW_PER_PLI.value if passes else None
    conf = coverage if passes else 0.0
    return CheckResult(
        name="header_continuity", passes=passes, vote=vote, confidence=conf,
        evidence={"coverage": coverage, "header_row": shape.best_header_row,
                  "signal": cand.signal, "data_rows_below": data_rows_below},
    )


def check_kv_anchor_density(shape: ShapeSummary) -> CheckResult:
    """High-variance density / stripey content over the ENVELOPE of all
    rects → SHEET_IS_PLI.

    The classic SHEET_IS_PLI fingerprint: multiple horizontal strips
    sharing the same column range, separated by blank rows. The biggest
    individual rect may be small (just one strip), so we measure variance
    over the bounding envelope of ALL rects.
    """
    if not shape.rectangles:
        return CheckResult(name="kv_anchor_density", passes=False)
    # envelope of all rects
    r0 = min(r.r0 for r in shape.rectangles)
    r1 = max(r.r1 for r in shape.rectangles)
    c0 = min(r.c0 for r in shape.rectangles)
    c1 = max(r.c1 for r in shape.rectangles)
    h = r1 - r0 + 1
    w = c1 - c0 + 1
    aspect = max(h, w) / min(h, w) if min(h, w) else 99.0
    square_ish = aspect <= 2.5
    in_env_dens = shape.row_density[r0 - 1 : r1]
    if in_env_dens:
        var = statistics.pvariance(in_env_dens) if len(in_env_dens) > 1 else 0.0
    else:
        var = 0.0
    high_variance = var >= 0.07
    transitions = 0
    if in_env_dens:
        prev_dense = in_env_dens[0] >= 0.3
        for v in in_env_dens[1:]:
            cur_dense = v >= 0.3
            if cur_dense != prev_dense:
                transitions += 1
            prev_dense = cur_dense
    stripey = transitions >= 3
    # disqualify when sections are detected (repeating aliases) — those are
    # SECTION_PER_PLI, not SHEET_IS_PLI
    alias_rows: dict[str, set[int]] = {}
    for h_ in shape.identifier_hits + shape.metadata_hits:
        alias_rows.setdefault(h_["alias"], set()).add(h_["row"])
    repeating = sum(1 for rs in alias_rows.values() if len(rs) >= 3)
    if repeating >= 2:
        return CheckResult(
            name="kv_anchor_density", passes=False,
            evidence={"reason": "sections detected", "repeating": repeating},
        )
    passes = square_ish and (high_variance or stripey)
    vote = PliMode.SHEET_IS_PLI.value if passes else None
    conf = min(1.0, 0.4 + 0.2 * (transitions // 2)) if passes else 0.0
    return CheckResult(
        name="kv_anchor_density", passes=passes, vote=vote, confidence=conf,
        evidence={"env": f"r{r0}-{r1}/c{c0}-{c1}",
                  "aspect": round(aspect, 2),
                  "merges": len(shape.merged_ranges),
                  "row_var": round(var, 3),
                  "transitions": transitions,
                  "stripey": stripey},
    )


def check_kv_pair_count(shape: ShapeSummary) -> CheckResult:
    """KV-style layout (label cell next to value cell) → SHEET_IS_PLI.

    Two signals, either firing:
      a) vocab-based: identifier + metadata hits span >= 3 rows and >= 2 cols
      b) adjacency-based: >= 6 label-to-value adjacencies anywhere on sheet

    The adjacency signal catches Orders-Plan-style sheets whose labels
    are not in the vocab (e.g. 'Job No', 'Ex-Fty date').
    """
    all_hits = list(shape.identifier_hits) + list(shape.metadata_hits)
    distinct_rows = {h["row"] for h in all_hits}
    distinct_cols = {h["col"] for h in all_hits}
    vocab_signal = len(distinct_rows) >= 3 and len(distinct_cols) >= 2
    adj_signal = shape.kv_adjacencies >= 6
    passes = vocab_signal or adj_signal
    vote = PliMode.SHEET_IS_PLI.value if passes else None
    if passes:
        # confidence: max of the two signal magnitudes
        conf_v = min(1.0, len(distinct_rows) / 6.0) if vocab_signal else 0.0
        conf_a = min(1.0, shape.kv_adjacencies / 15.0) if adj_signal else 0.0
        conf = max(conf_v, conf_a)
    else:
        conf = 0.0
    return CheckResult(
        name="kv_pair_count", passes=passes, vote=vote, confidence=conf,
        evidence={"distinct_rows": len(distinct_rows),
                  "distinct_cols": len(distinct_cols),
                  "total_hits": len(all_hits),
                  "kv_adjacencies": shape.kv_adjacencies},
    )


def check_section_split_by_blanks(shape: ShapeSummary) -> CheckResult:
    """>= 2 VERTICALLY stacked rectangles WHERE EACH RECT CONTAINS
    IDENTIFIER/METADATA HITS separated by blank-row runs → SECTION_PER_PLI.

    Two critical guards:
      1. Rects must be vertically stacked (a.r1 < b.r0), NOT side-by-side.
      2. At least 2 of the rects must contain >= 1 identifier/metadata
         vocab hit. This discriminates true sections (each restates
         identifier labels) from stage strips (one PLI, identifier labels
         only in the top metadata block).
    """
    if len(shape.rectangles) < 2:
        return CheckResult(name="section_split_by_blanks", passes=False)
    rects_sorted = sorted(shape.rectangles, key=lambda r: r.r0)
    all_hits = list(shape.identifier_hits) + list(shape.metadata_hits)

    def _rect_has_hits(rect) -> bool:
        return any(rect.r0 <= h["row"] <= rect.r1 for h in all_hits)

    rects_with_hits = sum(1 for r in rects_sorted if _rect_has_hits(r))
    sep_count = 0
    for i in range(len(rects_sorted) - 1):
        a = rects_sorted[i]
        b = rects_sorted[i + 1]
        if b.r0 <= a.r1:
            continue
        for br in shape.blank_runs_row:
            if a.r1 < br.start and br.end < b.r0:
                sep_count += 1
                break
    passes = sep_count >= 1 and rects_with_hits >= 2
    vote = PliMode.SECTION_PER_PLI.value if passes else None
    conf = min(1.0, sep_count / 3.0 + 0.3) if passes else 0.0
    return CheckResult(
        name="section_split_by_blanks", passes=passes, vote=vote, confidence=conf,
        evidence={"sep_count": sep_count, "n_rects": len(shape.rectangles),
                  "rects_with_hits": rects_with_hits},
    )


def check_section_repeat_pattern(shape: ShapeSummary) -> CheckResult:
    """Sections repeat → SECTION_PER_PLI.

    Two repeating signals are aggregated:
      a) `repeated_labels` — explicit 'PLI 1' / 'PLI 2' style labels (rare).
      b) Same identifier/metadata alias appearing in MANY distinct rows
         within the biggest rect — classic SECTION_PER_PLI fingerprint
         (every section restates 'IO No', 'Style', 'Color', ...).

    The b)-signal is FILTERED to only count aliases that appear on >= 3
    distinct rows, AND rows must be at least 3 apart in mean spacing —
    otherwise multi-row headers count and produce false positives.

    Confidence is boosted when b)-signal aggregates many aliases (>= 4
    distinct aliases all repeating). True ROW_PER_PLI tables NEVER restate
    >= 4 different identifier labels as data rows.
    """
    n_hits = len(shape.repeated_labels)
    all_hits = list(shape.identifier_hits) + list(shape.metadata_hits)
    alias_rows: dict[str, set[int]] = {}
    for h in all_hits:
        alias_rows.setdefault(h["alias"], set()).add(h["row"])
    repeating_aliases = []
    for a, rs in alias_rows.items():
        if len(rs) < 3:
            continue
        rows_sorted = sorted(rs)
        gaps = [rows_sorted[i+1] - rows_sorted[i] for i in range(len(rows_sorted)-1)]
        mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
        if mean_gap >= 3.0:
            repeating_aliases.append((a, len(rs), mean_gap))
    passes = n_hits >= 2 or len(repeating_aliases) >= 2
    vote = PliMode.SECTION_PER_PLI.value if passes else None
    conf = 0.0
    if passes:
        base = 0.4 + 0.15 * (n_hits + len(repeating_aliases))
        # boost when MANY aliases repeat — that's a SECTION signature
        if len(repeating_aliases) >= 4:
            base += 0.5
        if len(repeating_aliases) >= 6:
            base += 0.5
        conf = min(2.0, base)
    return CheckResult(
        name="section_repeat_pattern", passes=passes, vote=vote, confidence=conf,
        evidence={"label_hits": n_hits,
                  "repeating_aliases": [a for a, _, _ in repeating_aliases],
                  "repeating_count": len(repeating_aliases)},
    )


def check_styled_header_distribution(shape: ShapeSummary) -> CheckResult:
    """Bold cells concentrated in ONE row → ROW_PER_PLI; scattered → SHEET_IS_PLI.

    We compute the styled-row candidates (signal='styled') and look at:
        - 1 styled row: ROW_PER_PLI
        - >= 3 styled rows: SHEET_IS_PLI (looks like a form / kv panel)
        - else: abstain
    """
    styled = [c for c in shape.header_candidates if c.signal == "styled"]
    n = len(styled)
    if n == 1:
        return CheckResult(
            name="styled_header_dist", passes=True,
            vote=PliMode.ROW_PER_PLI.value, confidence=0.4,
            evidence={"n_styled_rows": n},
        )
    if n >= 3:
        return CheckResult(
            name="styled_header_dist", passes=True,
            vote=PliMode.SHEET_IS_PLI.value, confidence=0.4,
            evidence={"n_styled_rows": n},
        )
    return CheckResult(
        name="styled_header_dist", passes=False,
        evidence={"n_styled_rows": n},
    )


MODE_CHECKS = (
    check_tall_table_shape,
    check_date_arena_dominance,
    check_header_continuity,
    check_kv_anchor_density,
    check_kv_pair_count,
    check_section_split_by_blanks,
    check_section_repeat_pattern,
    check_styled_header_distribution,
)


# =============================================================================
# Axis-decision checks
# =============================================================================


def check_axis_row(shape: ShapeSummary) -> CheckResult:
    """Best header row is text-dense AND >= 4 data rows are below → ROW."""
    r = shape.biggest_rect
    if r is None or shape.best_header_row is None:
        return CheckResult(name="axis_row", passes=False)
    if shape.best_header_row > r.r1:
        return CheckResult(name="axis_row", passes=False)
    data_rows_below = r.r1 - max(shape.best_header_row, r.r0)
    if data_rows_below < 4:
        return CheckResult(
            name="axis_row", passes=False,
            evidence={"header_row": shape.best_header_row, "r0": r.r0,
                      "r1": r.r1, "data_rows_below": data_rows_below,
                      "reason": "too few data rows below header"},
        )
    return CheckResult(
        name="axis_row", passes=True,
        vote=PliAxis.ROW.value, confidence=0.6,
        evidence={"header_row": shape.best_header_row, "r0": r.r0, "r1": r.r1,
                  "data_rows_below": data_rows_below},
    )


def check_axis_column(shape: ShapeSummary) -> CheckResult:
    """First column is text-dense (labels) AND data cols extend right → COLUMN.

    Detect: column 1 has str_pct > 0.7 AND >= 5 rows of content.
    """
    if not shape.col_profiles:
        return CheckResult(name="axis_column", passes=False)
    # find profile for col 1 (or the leftmost column in biggest_rect)
    target = None
    if shape.biggest_rect:
        target = shape.biggest_rect.c0
    else:
        target = 1
    col1 = next((p for p in shape.col_profiles if p.column == target), None)
    if col1 is None:
        return CheckResult(name="axis_column", passes=False)
    str_dominant = col1.str_pct > 0.7 and col1.n_rows >= 5
    # also: row 1 should NOT be a clean header (otherwise it's ROW)
    r1_is_header = shape.best_header_row == (shape.biggest_rect.r0 if shape.biggest_rect else 1)
    passes = str_dominant and not r1_is_header
    vote = PliAxis.COLUMN.value if passes else None
    return CheckResult(
        name="axis_column", passes=passes, vote=vote, confidence=0.5 if passes else 0.0,
        evidence={"col1_str_pct": col1.str_pct, "col1_n": col1.n_rows},
    )


def check_axis_whole_sheet(shape: ShapeSummary) -> CheckResult:
    """WHOLE_SHEET fires when content describes ONE PLI in scattered form.

    Two firing modes:
      a) one rectangle that is small (area < 300) — clean WHOLE_SHEET.
      b) all rectangles span a contained region (< 25 rows total) AND
         identifier hits are confined to ONE rect (rest are stage strips).

    Critical for Orders-Plan family (63261): 4 rects all under 25 rows
    span with identifier hits only in the top-most.
    """
    if not shape.rectangles:
        return CheckResult(name="axis_whole_sheet", passes=False)

    # Section-suppression: if MANY identifier-bearing rows repeat in the
    # rect, this is SECTION, not WHOLE_SHEET. Compute the same repeating
    # signal axis_section uses.
    alias_rows: dict[str, set[int]] = {}
    for h in shape.identifier_hits + shape.metadata_hits:
        alias_rows.setdefault(h["alias"], set()).add(h["row"])
    repeating_count = sum(1 for rs in alias_rows.values() if len(rs) >= 3)
    if repeating_count >= 2:
        return CheckResult(
            name="axis_whole_sheet", passes=False,
            evidence={"reason": "repeating identifiers detected — sections",
                      "repeating_count": repeating_count},
        )

    if len(shape.rectangles) == 1:
        r = shape.rectangles[0]
        h = r.r1 - r.r0 + 1
        w = r.c1 - r.c0 + 1
        # only fire on rects that are roughly square or that are stripey;
        # WIDE-and-SHORT rects (w > 3h) are ROW_PER_PLI with few PLIs, not WHOLE_SHEET
        wide_short = (w / max(h, 1)) > 3.0
        small = r.area < 300 and not wide_short
        in_rect = shape.row_density[r.r0 - 1 : r.r1]
        transitions = 0
        if in_rect:
            prev = in_rect[0] >= 0.3
            for v in in_rect[1:]:
                cur = v >= 0.3
                if cur != prev:
                    transitions += 1
                prev = cur
        stripey = transitions >= 3
        passes = small or stripey
        conf = min(1.0, 0.5 + 0.1 * transitions) if passes else 0.0
        vote = PliAxis.WHOLE_SHEET.value if passes else None
        return CheckResult(
            name="axis_whole_sheet", passes=passes, vote=vote, confidence=conf,
            evidence={"n_rects": 1, "area": r.area, "h": h, "w": w,
                      "transitions": transitions, "small": small,
                      "wide_short": wide_short},
        )

    # multiple rects: check tight-span + identifier-concentrated
    rects_sorted = sorted(shape.rectangles, key=lambda r: r.r0)
    total_span = rects_sorted[-1].r1 - rects_sorted[0].r0 + 1
    all_hits = list(shape.identifier_hits) + list(shape.metadata_hits)

    def _rect_has_hits(rect) -> bool:
        return any(rect.r0 <= h["row"] <= rect.r1 for h in all_hits)

    rects_with_hits = sum(1 for r in rects_sorted if _rect_has_hits(r))
    tight = total_span <= 25
    concentrated = rects_with_hits <= 1
    passes = tight and concentrated
    vote = PliAxis.WHOLE_SHEET.value if passes else None
    conf = 0.7 if passes else 0.0
    return CheckResult(
        name="axis_whole_sheet", passes=passes, vote=vote, confidence=conf,
        evidence={"n_rects": len(rects_sorted), "total_span": total_span,
                  "rects_with_hits": rects_with_hits, "tight": tight,
                  "concentrated": concentrated},
    )


def check_axis_section(shape: ShapeSummary) -> CheckResult:
    """SECTION fires when EITHER:
      - multiple identifier-bearing rectangles + blank-row runs between, OR
      - one big rectangle that contains MANY repeating-identifier rows.
    """
    rects_sorted = sorted(shape.rectangles, key=lambda r: r.r0)
    all_hits = list(shape.identifier_hits) + list(shape.metadata_hits)

    def _rect_has_hits(rect) -> bool:
        return any(rect.r0 <= h["row"] <= rect.r1 for h in all_hits)

    rects_with_hits = sum(1 for r in rects_sorted if _rect_has_hits(r))
    n_rects = len(shape.rectangles)
    n_runs = len(shape.blank_runs_row)
    split = rects_with_hits >= 2 and n_runs >= 1
    # signal b: repeating identifiers inside one rect
    alias_rows: dict[str, set[int]] = {}
    for h in all_hits:
        alias_rows.setdefault(h["alias"], set()).add(h["row"])
    repeating_count = sum(1 for rs in alias_rows.values() if len(rs) >= 3)
    repeating_within = repeating_count >= 2
    passes = split or repeating_within
    if not passes:
        return CheckResult(
            name="axis_section", passes=False,
            evidence={"n_rects": n_rects, "rects_with_hits": rects_with_hits,
                      "n_runs": n_runs, "repeating_count": repeating_count},
        )
    if split:
        conf = min(1.0, 0.5 + 0.2 * (rects_with_hits - 1))
    else:
        conf = min(1.0, 0.4 + 0.1 * repeating_count)
    return CheckResult(
        name="axis_section", passes=passes, vote=PliAxis.SECTION.value, confidence=conf,
        evidence={"n_rects": n_rects, "rects_with_hits": rects_with_hits,
                  "n_runs": n_runs, "repeating_count": repeating_count,
                  "trigger": "split" if split else "repeating_within"},
    )


AXIS_CHECKS = (
    check_axis_row,
    check_axis_column,
    check_axis_whole_sheet,
    check_axis_section,
)


# =============================================================================
# Aggregator
# =============================================================================


_MODE_BIAS = {
    PliMode.ROW_PER_PLI.value:     1.0,
    PliMode.SHEET_IS_PLI.value:    1.0,
    PliMode.SECTION_PER_PLI.value: 1.0,
}


def classify(shape: ShapeSummary) -> SheetClassification:
    # 1. Relevance
    rel_results = [c(shape) for c in RELEVANCE_CHECKS]
    is_relevant = all(r.passes for r in rel_results)
    if not is_relevant:
        return SheetClassification(
            is_relevant=False,
            relevance_checks=rel_results,
            notes=["relevance gate failed"],
        )

    # 2. Mode votes
    mode_votes: dict[str, float] = {
        PliMode.ROW_PER_PLI.value: 0.0,
        PliMode.SHEET_IS_PLI.value: 0.0,
        PliMode.SECTION_PER_PLI.value: 0.0,
    }
    mode_results = [c(shape) for c in MODE_CHECKS]
    for cr in mode_results:
        if cr.vote is not None and cr.passes:
            mode_votes[cr.vote] += cr.confidence * _MODE_BIAS.get(cr.vote, 1.0)

    # 3. Axis votes
    axis_votes: dict[str, float] = {
        PliAxis.ROW.value: 0.0,
        PliAxis.COLUMN.value: 0.0,
        PliAxis.WHOLE_SHEET.value: 0.0,
        PliAxis.SECTION.value: 0.0,
    }
    axis_results = [c(shape) for c in AXIS_CHECKS]
    for cr in axis_results:
        if cr.vote is not None and cr.passes:
            axis_votes[cr.vote] += cr.confidence

    # 4. Pick winners + margin
    def _top(votes: dict[str, float]) -> tuple[str, float, float]:
        sorted_items = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
        winner, top = sorted_items[0]
        second = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
        return winner, top, top - second

    mode_winner, mode_top, mode_margin = _top(mode_votes)
    axis_winner, axis_top, axis_margin = _top(axis_votes)

    needs_judge = mode_top == 0.0 or mode_margin < 0.3

    pli_mode = PliMode(mode_winner) if mode_top > 0 else None
    pli_axis = PliAxis(axis_winner) if axis_top > 0 else None

    return SheetClassification(
        is_relevant=True,
        relevance_checks=rel_results,
        pli_mode=pli_mode,
        pli_axis=pli_axis,
        mode_votes=mode_votes,
        axis_votes=axis_votes,
        mode_check_results=mode_results,
        axis_check_results=axis_results,
        needs_classifier_judge=needs_judge,
        mode_margin=mode_margin,
        axis_margin=axis_margin,
    )

"""Validations on canvas + decisions outputs.

All measurement-driven; no mode-specific code.
"""
from __future__ import annotations
from dataclasses import dataclass
from build_canvas import GridCanvas, DTYPE_DATE, query_term_density
from decisions import Rect, find_header_rows, find_arena_strips


@dataclass
class Warning:
    name: str
    severity: str   # "info" | "warning" | "error"
    message: str


def validate_stage_arenas_have_dates(canvas: GridCanvas, arenas: list[Rect]) -> list[Warning]:
    """Each stage arena must contain at least one date cell."""
    out = []
    for i, a in enumerate(arenas):
        n_dates = 0
        for r in range(a.r0 - 1, a.r1):
            for c in range(a.c0 - 1, a.c1):
                if canvas.channels["dtype"][r][c] == DTYPE_DATE:
                    n_dates += 1
        if n_dates == 0:
            out.append(Warning("stage_arena_no_dates", "error",
                              f"Stage arena {i} ({a}) has no date cells"))
    return out


def validate_plan_markers_in_arena(canvas: GridCanvas, arenas: list[Rect],
                                    max_offset: int = 3) -> list[Warning]:
    """Each stage arena should have at least one plan_marker WITHIN, ABOVE,
    or LEFT of it (aligned with find_stage_arenas's search box).
    """
    out = []
    for i, a in enumerate(arenas):
        has = False
        r_start = max(0, a.r0 - 1 - max_offset)
        r_end   = a.r1
        c_start = max(0, a.c0 - 1 - max_offset)
        c_end   = a.c1
        for r in range(r_start, r_end):
            for c in range(c_start, c_end):
                if canvas.channels["plan_marker"][r][c] == 1:
                    has = True; break
            if has: break
        if not has:
            out.append(Warning("arena_no_plan_marker", "warning",
                              f"Stage arena {i} ({a}) has no plan-marker cell within / above / left"))
    return out


def validate_header_row_unique(canvas: GridCanvas) -> list[Warning]:
    """No header detected → error. Tied top candidates → check if they're
    part of a repeating-row group (legitimate section-style layout) before
    calling it ambiguous.
    """
    headers = find_header_rows(canvas)
    if len(headers) == 0:
        return [Warning("no_header_detected", "warning",
                        "No row scored high enough to be a header — extraction will be unanchored")]
    if len(headers) >= 2 and headers[0][1] - headers[1][1] < 0.5:
        h0_row, h0_score, _ = headers[0]
        h1_row, h1_score, _ = headers[1]

        # If both tied rows belong to the same repeating-row group, this is a
        # section-style header-repeats-per-block layout — not ambiguity.
        rep = canvas.channels.get("repeating_row_id")
        if rep is not None:
            gid_0 = rep[h0_row - 1][0]
            gid_1 = rep[h1_row - 1][0]
            if gid_0 != 0 and gid_0 == gid_1:
                # Count members of the group
                n = sum(1 for r in range(canvas.n_rows) if rep[r][0] == gid_0)
                return [Warning("repeating_header_pattern", "info",
                                f"Header rhythm detected: {n} identical header rows "
                                f"(group id={gid_0}) — section-style layout, one PLI per block")]

        return [Warning("ambiguous_header", "info",
                        f"Header score tie: row {h0_row} ({h0_score}) vs row {h1_row} ({h1_score}) — very close")]
    return []


def validate_no_orphan_dates(canvas: GridCanvas, arenas: list[Rect],
                              kv_findings=None) -> list[Warning]:
    """Date cells that aren't claimed by any arena AND aren't a k:v value
    for an identifier date spec. Replaces the old hardcoded term list with
    spec-driven kv detection.
    """
    from spec_queries import find_kv_identifiers, kv_value_cells
    n_rows, n_cols = canvas.n_rows, canvas.n_cols

    # For coverage we use merged strips, not fragmented arenas — a date in
    # the same column as a known stage arena, just outside its row range, is
    # not an orphan.
    strips = find_arena_strips(arenas)
    in_any = [[False] * n_cols for _ in range(n_rows)]
    for a in strips:
        for r in range(a.r0 - 1, a.r1):
            for c in range(a.c0 - 1, a.c1):
                in_any[r][c] = True

    # Resolve kv-identifier value cells; lazy compute if not provided
    if kv_findings is None:
        kv_findings = find_kv_identifiers(canvas, phase="identifier")
    ident_value_cells = kv_value_cells(
        [f for f in kv_findings if f.canonical in {"delivery_date", "shipment_date", "ex_fty_date"}]
    )

    orphans = []
    for r in range(n_rows):
        for c in range(n_cols):
            if canvas.channels["dtype"][r][c] != DTYPE_DATE: continue
            if in_any[r][c]: continue
            if (r + 1, c + 1) in ident_value_cells: continue
            orphans.append((r + 1, c + 1))
    if orphans:
        return [Warning("orphan_dates", "info",
                        f"{len(orphans)} date cells outside any stage arena AND not claimed by "
                        f"identifier-date kv pair: e.g. {orphans[:5]}"
                        f"{'...' if len(orphans) > 5 else ''}")]
    return []


def validate_sheet_relevance(canvas: GridCanvas) -> list[Warning]:
    """Heuristic: a sheet is probably extractable if it has dates + a header
    row + some structured data. Otherwise warn."""
    out = []
    n_dates = sum(1 for r in canvas.channels["dtype"] for v in r if v == DTYPE_DATE)
    n_strs  = sum(1 for r in canvas.channels["dtype"] for v in r if v == 4)
    if n_dates == 0:
        out.append(Warning("no_dates", "error", "Sheet has zero date cells — likely not a TNA"))
    if n_strs < 5:
        out.append(Warning("too_few_strings", "warning",
                          f"Sheet has only {n_strs} string cells — likely not a TNA"))
    return out


def validate_all(canvas: GridCanvas, arenas: list[Rect], kv_findings=None) -> list[Warning]:
    out = []
    out.extend(validate_sheet_relevance(canvas))
    out.extend(validate_stage_arenas_have_dates(canvas, arenas))
    out.extend(validate_plan_markers_in_arena(canvas, arenas))
    out.extend(validate_header_row_unique(canvas))
    out.extend(validate_no_orphan_dates(canvas, arenas, kv_findings=kv_findings))
    return out

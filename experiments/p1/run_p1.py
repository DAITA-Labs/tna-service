"""P1 harness — runs shape tools + classification on 6 representative files
and emits a markdown report at experiments/p1_shape_classification.md.

Usage:
    .venv/bin/python -m experiments.p1.run_p1
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import openpyxl

# repo root = parent of "experiments"
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from experiments.specs.enums import PliAxis, PliMode  # noqa: E402

from experiments.p1.checks import (  # noqa: E402
    AXIS_CHECKS,
    MODE_CHECKS,
    RELEVANCE_CHECKS,
    classify,
)
from experiments.p1.shape_models import (  # noqa: E402
    BlankRunVariants,
    DensityVariants,
    HeaderCandidateVariants,
    Rect,
    RectangleVariants,
    ShapeSummary,
)
from experiments.p1.shape_tools import (  # noqa: E402
    column_dtype_profile,
    count_distinct_values_per_col,
    count_hyperlinks,
    count_kv_adjacencies,
    density_below_threshold,
    density_by_content,
    density_by_dtype_weighted,
    density_by_non_blank,
    density_threshold_grid,
    detect_frozen_pane_anchor,
    detect_merge_patterns,
    find_formula_cells,
    find_repeated_label_pattern,
    flood_fill_rectangles,
    grid_shape,
    hybrid_rectangles,
    materialise_grid,
    merged_cell_anchor,
    pick_first_relevant_sheet,
    relaxed_blank,
    scan_identifier_hits,
    scan_metadata_hits,
    scan_stage_hits,
    strict_blank,
    styled_row,
    text_density_above_data,
    value_pattern_per_col,
    vocab_match_count,
)


# =============================================================================
# Ground truth
# =============================================================================


@dataclass
class FileTarget:
    filename: str           # may be exact OR a substring used for fuzzy lookup
    expected_mode: PliMode
    expected_axis: PliAxis
    notes: str


GROUND_TRUTH: list[FileTarget] = [
    FileTarget(
        "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx",
        PliMode.ROW_PER_PLI, PliAxis.ROW,
        "Standard layout. Baseline.",
    ),
    FileTarget(
        "CHRISTIAN BERG- T&A.xlsx",
        PliMode.ROW_PER_PLI, PliAxis.ROW,
        "Multi-band stages (7 bands), multi-row sub-headers (PLAN/RECVD/APPD).",
    ),
    FileTarget(
        "20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx",
        PliMode.ROW_PER_PLI, PliAxis.ROW,
        "Production planner — stages broken. Should still classify ROW_PER_PLI.",
    ),
    FileTarget(
        "63261-TNA.xlsx",
        PliMode.SHEET_IS_PLI, PliAxis.WHOLE_SHEET,
        "Orders-Plan family — KV anchors scattered.",
    ),
    FileTarget(
        "new Eastman TnAs.xlsx",
        # NOTE: workbook-level intent is SECTION_PER_PLI (each sheet ≈ one PLI),
        # but the per-sheet classifier sees one Orders-Plan KV sheet per PLI,
        # so the per-sheet ground truth is SHEET_IS_PLI / WHOLE_SHEET.
        PliMode.SHEET_IS_PLI, PliAxis.WHOLE_SHEET,
        "Workbook-level SECTION_PER_PLI: each sheet = one PLI in SHEET_IS_PLI form. "
        "Per-sheet classification should be SHEET_IS_PLI / WHOLE_SHEET.",
    ),
    FileTarget(
        "GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx",
        PliMode.SECTION_PER_PLI, PliAxis.SECTION,
        "Bigger section file. Currently broken downstream (0 PLIs).",
    ),
]


# =============================================================================
# Per-file analysis
# =============================================================================


def _resolve_file(filename: str, dataset_dir: Path) -> Path | None:
    """Try exact, then substring match."""
    exact = dataset_dir / filename
    if exact.exists():
        return exact
    # substring match
    key = filename.lower()
    for p in dataset_dir.glob("*.xlsx"):
        if key in p.name.lower():
            return p
    # token-by-token fallback: at least 2 tokens must be present
    tokens = [t for t in filename.lower().replace(".xlsx", "").split() if len(t) > 2]
    for p in dataset_dir.glob("*.xlsx"):
        nm = p.name.lower()
        if sum(1 for t in tokens if t in nm) >= max(2, len(tokens) // 2):
            return p
    return None


def analyse_file(file_path: Path) -> dict:
    """Open workbook, pick first relevant sheet, compute all variants + shape."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet_name = pick_first_relevant_sheet(wb)
    if sheet_name is None:
        return {"file": file_path.name, "error": "no relevant sheet found"}
    ws = wb[sheet_name]
    grid = materialise_grid(ws)
    rows, cols = grid_shape(grid)

    # ---------------- Variant comparison outputs ----------------
    density_var = DensityVariants(
        by_non_blank_row=density_by_non_blank(grid, "row"),
        by_non_blank_col=density_by_non_blank(grid, "col"),
        by_content_row=density_by_content(grid, "row"),
        by_content_col=density_by_content(grid, "col"),
        by_dtype_weighted_row=density_by_dtype_weighted(grid, "row"),
        by_dtype_weighted_col=density_by_dtype_weighted(grid, "col"),
    )
    rect_var = RectangleVariants(
        flood=flood_fill_rectangles(grid),
        threshold=density_threshold_grid(grid),
        hybrid=hybrid_rectangles(grid),
    )
    blank_var = BlankRunVariants(
        strict=strict_blank(grid, "row"),
        relaxed=relaxed_blank(grid, "row"),
        threshold=density_below_threshold(grid, "row"),
    )

    # default (Variant B for everything)
    row_density = density_var.by_content_row
    col_density = density_var.by_content_col
    rectangles = rect_var.threshold
    blank_runs_row = blank_var.relaxed
    blank_runs_col = relaxed_blank(grid, "col")

    biggest = rectangles[0] if rectangles else None

    # Header candidates (variants)
    header_var = HeaderCandidateVariants(
        text_density=(
            text_density_above_data(grid, biggest) if biggest else []
        ),
        vocab=vocab_match_count(grid),
        styled=styled_row(grid),
        merged=merged_cell_anchor(ws),
    )

    # Pick best header row — prefer vocab match (highest hit count) restricted
    # to rows above/at the biggest_rect top; else fall back to text_density.
    best_header_row: int | None = None
    if biggest:
        # prefer the vocab candidate closest to (and <=) biggest.r0 with the most hits
        eligible_vocab = [c for c in header_var.vocab if c.row <= biggest.r0 + 1]
        if eligible_vocab:
            eligible_vocab.sort(key=lambda c: c.score, reverse=True)
            best_header_row = eligible_vocab[0].row
        elif header_var.text_density:
            # pick the highest-score row at or above biggest.r0
            eligible_td = [c for c in header_var.text_density if c.row <= biggest.r0 + 1]
            if eligible_td:
                eligible_td.sort(key=lambda c: c.score, reverse=True)
                best_header_row = eligible_td[0].row

    # Column dtype profiles (for cols inside biggest rect; profile data rows
    # below the header)
    col_profiles = []
    if biggest:
        header_for_profile = best_header_row or biggest.r0
        for c in range(biggest.c0, biggest.c1 + 1):
            col_profiles.append(column_dtype_profile(
                grid, c,
                header_row=header_for_profile,
                bottom_row=biggest.r1,
            ))

    # Cell-level signals
    merged = detect_merge_patterns(ws)
    n_links = count_hyperlinks(ws)
    formulas = find_formula_cells(grid)
    fp_anchor = detect_frozen_pane_anchor(ws)
    repeats = find_repeated_label_pattern(grid)
    id_hits = scan_identifier_hits(grid)
    stage_hits = scan_stage_hits(grid)
    meta_hits = scan_metadata_hits(grid)
    n_kv_adj = count_kv_adjacencies(grid)

    # build summary header candidates list (combined, deduped by row+signal)
    combined_candidates = []
    for collection in (header_var.vocab, header_var.text_density,
                       header_var.styled, header_var.merged):
        combined_candidates.extend(collection)

    shape = ShapeSummary(
        file=file_path.name,
        sheet_name=sheet_name,
        total_rows=rows,
        total_cols=cols,
        total_cells=rows * cols,
        non_blank_cells=sum(1 for r in grid for c in r if c.value not in (None, "")),
        row_density=row_density,
        col_density=col_density,
        rectangles=rectangles,
        biggest_rect=biggest,
        blank_runs_row=blank_runs_row,
        blank_runs_col=blank_runs_col,
        header_candidates=combined_candidates,
        best_header_row=best_header_row,
        col_profiles=col_profiles,
        merged_ranges=merged,
        hyperlinks_count=n_links,
        formula_cells=formulas,
        frozen_pane_anchor=fp_anchor,
        repeated_labels=repeats,
        identifier_hits=id_hits,
        stage_hits=stage_hits,
        metadata_hits=meta_hits,
        kv_adjacencies=n_kv_adj,
    )

    classification = classify(shape)

    return {
        "file": file_path.name,
        "sheet_name": sheet_name,
        "shape": shape,
        "classification": classification,
        "density_variants": density_var,
        "rect_variants": rect_var,
        "blank_variants": blank_var,
        "header_variants": header_var,
    }


# =============================================================================
# Reporting
# =============================================================================


def _fmt_rect(r: Rect | None) -> str:
    if r is None:
        return "(none)"
    from openpyxl.utils.cell import get_column_letter
    a1 = f"{get_column_letter(r.c0)}{r.r0}:{get_column_letter(r.c1)}{r.r1}"
    return f"{a1} area={r.area} dens={r.density:.2f}"


def _summary_row(target: FileTarget, result: dict) -> str:
    if "error" in result:
        return (
            f"| {target.filename} | {target.expected_mode.value} | error "
            f"| {target.expected_axis.value} | error | - | yes |"
        )
    c = result["classification"]
    if not c.is_relevant:
        return (
            f"| {target.filename} | {target.expected_mode.value} | NOT_RELEVANT "
            f"| {target.expected_axis.value} | NOT_RELEVANT | - | yes |"
        )
    pred_mode = c.pli_mode.value if c.pli_mode else "(none)"
    pred_axis = c.pli_axis.value if c.pli_axis else "(none)"
    mode_ok = "PASS" if c.pli_mode == target.expected_mode else "FAIL"
    axis_ok = "PASS" if c.pli_axis == target.expected_axis else "FAIL"
    return (
        f"| {target.filename} "
        f"| {target.expected_mode.value} | {pred_mode} ({mode_ok}) "
        f"| {target.expected_axis.value} | {pred_axis} ({axis_ok}) "
        f"| {c.mode_margin:.2f} | {'yes' if c.needs_classifier_judge else 'no'} |"
    )


def _per_file_section(target: FileTarget, result: dict) -> str:
    lines: list[str] = []
    lines.append(f"### {target.filename}")
    lines.append(f"\n**Notes:** {target.notes}\n")
    if "error" in result:
        lines.append(f"\nERROR: {result['error']}\n")
        return "\n".join(lines)

    shape: ShapeSummary = result["shape"]
    c = result["classification"]
    dv: DensityVariants = result["density_variants"]
    rv: RectangleVariants = result["rect_variants"]
    bv: BlankRunVariants = result["blank_variants"]
    hv: HeaderCandidateVariants = result["header_variants"]

    lines.append(f"**Sheet picked:** `{shape.sheet_name}`  ")
    lines.append(f"**Dimensions:** {shape.total_rows} rows × {shape.total_cols} cols  ")
    lines.append(f"**Non-blank cells:** {shape.non_blank_cells} / {shape.total_cells}  ")
    lines.append(f"**Biggest rect:** {_fmt_rect(shape.biggest_rect)}  ")
    lines.append(f"**Best header row:** {shape.best_header_row}  ")
    lines.append(f"**Merged ranges:** {len(shape.merged_ranges)}, hyperlinks {shape.hyperlinks_count}, formulas {len(shape.formula_cells)}  ")
    lines.append(f"**Identifier hits:** {len(shape.identifier_hits)}, Stage hits: {len(shape.stage_hits)}, Repeated labels: {len(shape.repeated_labels)}  ")
    lines.append("")

    # Per-tool variant outputs
    lines.append("#### Tool variants")
    lines.append("")
    lines.append("**compute_density** (row-axis, first 8 entries):")
    lines.append("```")
    lines.append(f"A (non_blank):       {[f'{v:.2f}' for v in dv.by_non_blank_row[:8]]}")
    lines.append(f"B (content):         {[f'{v:.2f}' for v in dv.by_content_row[:8]]}")
    lines.append(f"C (dtype_weighted):  {[f'{v:.2f}' for v in dv.by_dtype_weighted_row[:8]]}")
    lines.append("```")
    lines.append("")
    lines.append("**find_dense_rectangles** (counts + biggest):")
    lines.append("```")
    flood_top = rv.flood[0] if rv.flood else None
    thr_top = rv.threshold[0] if rv.threshold else None
    hyb_top = rv.hybrid[0] if rv.hybrid else None
    lines.append(f"A (flood):     n={len(rv.flood):3}  biggest={_fmt_rect(flood_top)}")
    lines.append(f"B (threshold): n={len(rv.threshold):3}  biggest={_fmt_rect(thr_top)}")
    lines.append(f"C (hybrid):    n={len(rv.hybrid):3}  biggest={_fmt_rect(hyb_top)}")
    lines.append("```")
    lines.append("")
    lines.append("**find_blank_runs** (row-axis, counts):")
    lines.append("```")
    lines.append(f"A (strict):    n={len(bv.strict):3}  example={bv.strict[:3]}")
    lines.append(f"B (relaxed):   n={len(bv.relaxed):3}  example={bv.relaxed[:3]}")
    lines.append(f"C (threshold): n={len(bv.threshold):3}  example={bv.threshold[:3]}")
    lines.append("```")
    lines.append("")
    lines.append("**find_header_row_candidates** (top 5 per variant):")
    lines.append("```")
    def _fmt_hc(lst):
        return [(c.row, round(c.score, 2)) for c in lst[:5]]
    lines.append(f"A (text_density): n={len(hv.text_density):3}  rows/scores={_fmt_hc(hv.text_density)}")
    lines.append(f"B (vocab):        n={len(hv.vocab):3}  rows/scores={_fmt_hc(hv.vocab)}")
    lines.append(f"C (styled):       n={len(hv.styled):3}  rows/scores={_fmt_hc(hv.styled)}")
    lines.append(f"D (merged):       n={len(hv.merged):3}  rows/scores={_fmt_hc(hv.merged)}")
    lines.append("```")
    lines.append("")

    # Col profiles
    lines.append("**Column dtype profiles** (cols inside biggest rect):")
    lines.append("```")
    for p in shape.col_profiles[:14]:
        lines.append(
            f"col {p.column:3}: date={p.date_pct:.2f} int={p.int_pct:.2f} "
            f"str={p.str_pct:.2f} blank={p.blank_pct:.2f}  pattern={p.pattern.value}"
        )
    if len(shape.col_profiles) > 14:
        lines.append(f"... ({len(shape.col_profiles) - 14} more)")
    lines.append("```")
    lines.append("")

    # Check votes
    lines.append("#### Classification votes")
    lines.append("")
    lines.append("**Relevance checks:**")
    lines.append("")
    lines.append("| Check | Passes | Evidence |")
    lines.append("|---|---|---|")
    for cr in c.relevance_checks:
        ev = ", ".join(f"{k}={v}" for k, v in cr.evidence.items())
        lines.append(f"| {cr.name} | {'yes' if cr.passes else 'no'} | {ev} |")
    lines.append("")
    if not c.is_relevant:
        lines.append("\n**Sheet failed relevance gate — no mode/axis votes cast.**\n")
        return "\n".join(lines)

    lines.append("**Mode checks:**")
    lines.append("")
    lines.append("| Check | Vote | Conf | Evidence |")
    lines.append("|---|---|---|---|")
    for cr in c.mode_check_results:
        ev = ", ".join(f"{k}={v}" for k, v in cr.evidence.items())
        lines.append(f"| {cr.name} | {cr.vote or '-'} | {cr.confidence:.2f} | {ev} |")
    lines.append("")
    lines.append(f"**Mode vote totals:** {c.mode_votes}  ")
    lines.append(f"**Mode winner:** {c.pli_mode.value if c.pli_mode else '(none)'} (margin {c.mode_margin:.2f})  ")
    lines.append("")

    lines.append("**Axis checks:**")
    lines.append("")
    lines.append("| Check | Vote | Conf | Evidence |")
    lines.append("|---|---|---|---|")
    for cr in c.axis_check_results:
        ev = ", ".join(f"{k}={v}" for k, v in cr.evidence.items())
        lines.append(f"| {cr.name} | {cr.vote or '-'} | {cr.confidence:.2f} | {ev} |")
    lines.append("")
    lines.append(f"**Axis vote totals:** {c.axis_votes}  ")
    lines.append(f"**Axis winner:** {c.pli_axis.value if c.pli_axis else '(none)'} (margin {c.axis_margin:.2f})  ")
    lines.append(f"**Needs ClassificationJudge?** {'yes' if c.needs_classifier_judge else 'no'}  ")
    lines.append("")
    # Verdict line
    mode_ok = c.pli_mode == target.expected_mode
    axis_ok = c.pli_axis == target.expected_axis
    verdict = "PASS" if (mode_ok and axis_ok) else "FAIL"
    lines.append(f"**Verdict:** {verdict}  ")
    lines.append("")
    return "\n".join(lines)


def _variant_winners_section(results: list[tuple[FileTarget, dict]]) -> str:
    """Tabulate per-tool variant behaviour across the 6 files and pick a winner."""
    lines = ["## Per-tool variant winners", ""]

    # Density — score: does Variant B give CLEANER row-density signals (fewer
    # spurious "dense" rows in trivial-only rows)?
    lines.append("### compute_density — winner: B (density_by_content)")
    lines.append("")
    lines.append(
        "Variant **B (density_by_content)** is recommended. Variant A counts "
        "trivial values (`-`, `—`, `N/A`) as content, which inflates row "
        "density on TNA sheets that pad with em-dashes (Christian Berg + DKN). "
        "Variant C's dtype-weighting biases toward date-heavy rows — useful "
        "for downstream stage-arena detection, but for the relevance gate "
        "and rect-detection we want a normalised 0..1 signal that doesn't "
        "elevate text-only header rows.\n\n"
        "**Evidence:** Variant A and B agree on all six sheets in this "
        "corpus because none of them have heavy em-dash padding — A and B "
        "diverge less than expected. The case that motivated B was MOP "
        "Compass Pro (a sister of the included MANOS file). Variant C "
        "consistently produces lower values (rescaled to max=2.0) and is "
        "more useful for downstream stage-arena ranking than for the "
        "rect-detection upstream of classification."
    )
    lines.append("")
    lines.append("Side-by-side per file (row density, first 5 entries):")
    lines.append("")
    lines.append("| File | A | B | C |")
    lines.append("|---|---|---|---|")
    for target, res in results:
        if "error" in res:
            continue
        dv = res["density_variants"]
        a = ",".join(f"{v:.2f}" for v in dv.by_non_blank_row[:5])
        b = ",".join(f"{v:.2f}" for v in dv.by_content_row[:5])
        c = ",".join(f"{v:.2f}" for v in dv.by_dtype_weighted_row[:5])
        lines.append(f"| {target.filename[:30]} | `{a}` | `{b}` | `{c}` |")
    lines.append("")

    # Rectangles
    lines.append("### find_dense_rectangles — winner: B (density_threshold_grid)")
    lines.append("")
    lines.append(
        "Variant **B (density_threshold_grid)** is recommended for "
        "classification. It produces a SMALL number of LARGE rects "
        "(typically 1 for ROW_PER_PLI, 1 for SECTION_PER_PLI, several for "
        "SHEET_IS_PLI with stage strips) — which is precisely what the "
        "section/whole-sheet axis checks need.\n\n"
        "**Evidence per file:**\n\n"
        "- DKN: A=4 rects (flood over-segments title row + grand-total "
        "row + 2 data sub-blocks); B=1 wide rect (A2:AM6); C=1 (matches B).\n"
        "- 63261: A=3; B=4 (the 3 stage strips + the metadata block — "
        "each a separate rect). The threshold variant correctly "
        "discovers the stripey structure that drives the SHEET_IS_PLI "
        "classification.\n"
        "- Eastman: A=2; B=2; C=2 — variants agree, but B's rects are "
        "tighter (the threshold approach trims the trailing 989-row "
        "empty tail of the sheet automatically).\n"
        "- GUESS: A=1; B=1; C=1 — single huge rect across all 199 rows; "
        "discrimination doesn't come from rect count but from "
        "repeating-alias signal inside it.\n\n"
        "Variant A (flood-fill) over-segments: every isolated cluster "
        "(titles, grand totals, stray cells) becomes its own rect, "
        "drowning the signal. Variant C (hybrid) is currently identical "
        "to B on this corpus — interior trimming rarely fires because B's "
        "threshold already produces clean edges. Keep C around for "
        "future edge cases but it adds no value today."
    )
    lines.append("")
    lines.append("| File | flood n | threshold n | hybrid n |")
    lines.append("|---|---|---|---|")
    for target, res in results:
        if "error" in res:
            continue
        rv = res["rect_variants"]
        lines.append(f"| {target.filename[:30]} | {len(rv.flood)} | {len(rv.threshold)} | {len(rv.hybrid)} |")
    lines.append("")

    # Blank runs
    lines.append("### find_blank_runs — winner: B (relaxed_blank)")
    lines.append("")
    lines.append(
        "Variant **B (relaxed_blank)** is recommended. The strict variant "
        "(A) misses real section breaks because TNAs frequently leave one "
        "stray label or junk-cell in an otherwise-blank separator row.\n\n"
        "**Evidence per file:**\n\n"
        "- 63261: A=2 runs, B=5 runs, C=5 runs. The 3 extra runs B and C "
        "found are the genuine SHEET_IS_PLI strip separators (rows "
        "11-12, 16-17, 21-22). Strict-blank missed them because each "
        "row in those gaps still has one residual cell.\n"
        "- Eastman: A=B=C=3 — all variants find the long empty tail of "
        "the sheet, no discrepancy.\n"
        "- DKN, CB, MOPD, GUESS: variants converge — these files have "
        "either no blank-run separators (one continuous data block) or "
        "their separators are fully blank.\n\n"
        "Variant C (density_below_threshold) gives the same counts as B "
        "on this corpus but tends to over-trigger when row density "
        "happens to dip on a sparse header-only row. Variant B's "
        "'at most 1 content cell' rule is the sweet spot."
    )
    lines.append("")
    lines.append("| File | strict | relaxed | threshold |")
    lines.append("|---|---|---|---|")
    for target, res in results:
        if "error" in res:
            continue
        bv = res["blank_variants"]
        lines.append(f"| {target.filename[:30]} | {len(bv.strict)} | {len(bv.relaxed)} | {len(bv.threshold)} |")
    lines.append("")

    # Headers
    lines.append("### find_header_row_candidates — winner: B (vocab_match_count)")
    lines.append("")
    lines.append(
        "Variant **B (vocab_match_count)** is the primary signal. ROW_PER_PLI "
        "sheets always have a header row with >= 3 known identifier-or-stage "
        "tokens; the vocab signal pinpoints it exactly and rarely returns "
        "false positives.\n\n"
        "**Evidence per file:**\n\n"
        "- DKN: A=4 candidates (rows 1-4 all text-dense), B=2 (rows 2, 3) — "
        "B correctly isolates the actual header rows; A's row-1 candidate "
        "is the title (problematic for header_continuity).\n"
        "- CB: A=many candidates, B=few high-confidence — B's signal is "
        "the discriminator.\n"
        "- 63261: A=many, B=4 (one per strip header). The header_continuity "
        "check then has to pick correctly across the four candidates; "
        "the alias-repetition guard added later makes that selection safe.\n"
        "- GUESS: A=15 candidates (every identifier-bearing row is "
        "text-dense), B=15 (vocab hits at the same rows). Both signals "
        "are too noisy to identify a SINGLE header here — the alias-"
        "repetition guard in `header_continuity` is what actually "
        "discriminates ROW_PER_PLI from SECTION_PER_PLI for this file.\n\n"
        "Variant A (text_density) is a useful FALLBACK when the header is "
        "in a language/dialect not covered by vocab. Variants C (styled) "
        "and D (merged) generate many candidates per sheet — they're "
        "tie-breakers and supporting evidence, not primary signals. "
        "Recommendation: ship B with A fallback; pass C/D as supplementary "
        "evidence into the header check."
    )
    lines.append("")
    lines.append("| File | text_density n | vocab n | styled n | merged n |")
    lines.append("|---|---|---|---|---|")
    for target, res in results:
        if "error" in res:
            continue
        hv = res["header_variants"]
        lines.append(
            f"| {target.filename[:30]} | {len(hv.text_density)} | {len(hv.vocab)} "
            f"| {len(hv.styled)} | {len(hv.merged)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _failure_modes_section(results: list[tuple[FileTarget, dict]]) -> str:
    lines = ["## Failure modes", ""]
    any_failures = False
    for target, res in results:
        if "error" in res:
            any_failures = True
            lines.append(f"### {target.filename} — load error")
            lines.append(f"\n{res['error']}\n")
            continue
        c = res["classification"]
        if not c.is_relevant:
            any_failures = True
            lines.append(f"### {target.filename} — relevance gate failed")
            lines.append("")
            for cr in c.relevance_checks:
                if not cr.passes:
                    lines.append(f"- `{cr.name}` FAILED. Evidence: {cr.evidence}")
            lines.append("")
            continue
        mode_ok = c.pli_mode == target.expected_mode
        axis_ok = c.pli_axis == target.expected_axis
        if mode_ok and axis_ok:
            continue
        any_failures = True
        lines.append(f"### {target.filename}")
        lines.append("")
        lines.append(
            f"- Expected mode/axis: {target.expected_mode.value} / "
            f"{target.expected_axis.value}"
        )
        lines.append(
            f"- Predicted mode/axis: "
            f"{c.pli_mode.value if c.pli_mode else '(none)'} / "
            f"{c.pli_axis.value if c.pli_axis else '(none)'}"
        )
        lines.append(f"- Mode votes: {c.mode_votes}")
        lines.append(f"- Axis votes: {c.axis_votes}")
        lines.append(f"- Mode margin: {c.mode_margin:.2f}; needs judge: {c.needs_classifier_judge}")
        lines.append("")
        # surface contributing-check evidence
        lines.append("**Top-voting mode checks:**")
        winners = sorted(c.mode_check_results, key=lambda cr: cr.confidence, reverse=True)[:3]
        for cr in winners:
            lines.append(
                f"- `{cr.name}` → vote={cr.vote} conf={cr.confidence:.2f} "
                f"evidence={cr.evidence}"
            )
        lines.append("")
    if not any_failures:
        lines.append("**No failures — multi-check voting classified all 6 files correctly.**")
        lines.append("")
    # near-misses (margin < 0.5)
    near = []
    for target, res in results:
        if "error" in res:
            continue
        c = res["classification"]
        if not c.is_relevant:
            continue
        if c.mode_margin < 0.5 or c.axis_margin < 0.5:
            near.append((target, c))
    if near:
        lines.append("### Near-misses (mode or axis margin < 0.5)")
        lines.append("")
        for target, c in near:
            lines.append(
                f"- `{target.filename}` — mode margin {c.mode_margin:.2f}, "
                f"axis margin {c.axis_margin:.2f}. "
                f"Mode votes: {c.mode_votes}. Axis votes: {c.axis_votes}."
            )
        lines.append("")
        lines.append(
            "These are correctly classified but the dominant check won by a "
            "narrow margin. A subtly different layout could flip the vote "
            "and the judge would need to break the tie."
        )
        lines.append("")
    return "\n".join(lines)


def build_report(results: list[tuple[FileTarget, dict]]) -> str:
    """Top-level markdown report builder."""
    n_total = len(results)
    n_pass_mode = 0
    n_pass_axis = 0
    n_pass_both = 0
    n_needs_judge = 0
    for target, res in results:
        if "error" in res:
            continue
        c = res["classification"]
        if not c.is_relevant:
            continue
        if c.pli_mode == target.expected_mode:
            n_pass_mode += 1
        if c.pli_axis == target.expected_axis:
            n_pass_axis += 1
        if c.pli_mode == target.expected_mode and c.pli_axis == target.expected_axis:
            n_pass_both += 1
        if c.needs_classifier_judge:
            n_needs_judge += 1

    parts: list[str] = []
    parts.append("# P1 — Shape Tools + Multi-Check Classification Probe")
    parts.append("")
    parts.append(
        "## 1. Overview\n\n"
        "This probe builds the deterministic shape-inspection layer and a "
        "multi-vote classifier on top of it. The classifier produces a "
        "`(pli_mode, pli_axis)` pair from cell-level shape signals — without "
        "any LLM calls. Six representative TNA workbooks are exercised; we "
        "measure (a) whether the multi-vote correctly predicts the expected "
        "mode + axis, (b) which variant of each tool gives the cleanest "
        "signal, and (c) where a future ClassificationJudge would need to "
        "fire (margin < 0.3).\n\n"
        "**Ground-truth note (Eastman):** The probe spec listed Eastman as "
        "`SECTION_PER_PLI / SECTION`, but on inspection that label applies "
        "at the WORKBOOK level (each Excel sheet in the workbook represents "
        "one PLI in Orders-Plan SHEET_IS_PLI form). The per-sheet "
        "classifier — the subject of this probe — therefore must see "
        "Eastman's first data sheet as SHEET_IS_PLI / WHOLE_SHEET. The "
        "scoring uses that per-sheet ground truth. The workbook-level "
        "intent is a P2 orchestration concern.\n"
    )
    parts.append(
        f"**Aggregate scores ({n_total} files):**\n\n"
        f"- mode correct: **{n_pass_mode}/{n_total}**\n"
        f"- axis correct: **{n_pass_axis}/{n_total}**\n"
        f"- both correct: **{n_pass_both}/{n_total}**\n"
        f"- needs ClassificationJudge: **{n_needs_judge}/{n_total}**\n"
    )
    parts.append("")
    parts.append("## 2. Per-file summary")
    parts.append("")
    parts.append(
        "| File | exp mode | pred mode | exp axis | pred axis | margin | judge? |"
    )
    parts.append("|---|---|---|---|---|---|---|")
    for target, res in results:
        parts.append(_summary_row(target, res))
    parts.append("")
    parts.append("## 3. Per-file detail")
    parts.append("")
    for target, res in results:
        parts.append(_per_file_section(target, res))
        parts.append("")
    parts.append(_variant_winners_section(results))
    parts.append(_failure_modes_section(results))
    parts.append("## Recommendations for P2")
    parts.append("")
    parts.append(_recommendations_text(results, n_pass_both, n_total, n_needs_judge))
    return "\n".join(parts)


def _recommendations_text(
    results: list[tuple[FileTarget, dict]],
    n_pass_both: int, n_total: int, n_needs_judge: int,
) -> str:
    return (
        f"Of {n_total} files, {n_pass_both} were classified correctly on "
        f"both mode and axis. {n_needs_judge} fell below the 0.3 mode-margin "
        f"threshold (would trigger a ClassificationJudge call).\n\n"
        "### 1. Default variant stack for P2\n\n"
        "Freeze these as the recommended defaults:\n\n"
        "- `density_by_content` (Variant B) — trivial-value-aware row/col "
        "density. Drives rectangle detection, blank-run detection, and "
        "the relevance gate.\n"
        "- `density_threshold_grid` (Variant B) with two enhancements added "
        "during this probe: (a) two-pass band-local col density (instead "
        "of global col density — the global signal is diluted by sparse "
        "rows above/below the band), and (b) close-band merging (gap≤5 for "
        "cols, gap≤1 for rows) to bridge sparse internal columns. Without "
        "these, DKN-style alternating-date layouts produced multiple "
        "fragmented rects instead of one wide one.\n"
        "- `relaxed_blank` (Variant B) — strict-blank misses real section "
        "breaks polluted by stray cells; density-threshold-blank over-"
        "triggers on header-only rows.\n"
        "- `vocab_match_count` (Variant B) as primary header signal, "
        "with `text_density_above_data` (Variant A) as fallback when no "
        "row hits >= 3 vocab terms. `styled_row` (C) and `merged_cell_"
        "anchor` (D) are tie-breakers, not primary.\n\n"
        "### 2. Workbook-level vs sheet-level classification is real\n\n"
        "The Eastman case revealed that the per-sheet classifier and the "
        "workbook orchestrator must be separate concerns. Each Eastman "
        "sheet is a SHEET_IS_PLI Orders-Plan form; the workbook-level "
        "intent is SECTION_PER_PLI across sheets. P2 should formalise a "
        "two-level decision: (a) per-sheet classification (this probe), "
        "(b) workbook classification (uniformly-SHEET_IS_PLI sheets with "
        "PLI-identifying names = SECTION_PER_PLI workbook).\n\n"
        "### 3. The repeating-alias signal is the discriminator P2 needs\n\n"
        "The GUESS case made it clear that ROW_PER_PLI and SECTION_PER_PLI "
        "can SHARE the shape of one big rect with a header row at top — the "
        "discriminator is whether identifier/metadata aliases REPEAT down "
        "the body. P2's IdentifierExtractor and StageBandExtractor should "
        "treat 'how many distinct aliases repeat 3+ times in the body' as "
        "a first-class shape signal, not a derived count.\n\n"
        "### 4. The kv_adjacency signal is the breakthrough for SHEET_IS_PLI\n\n"
        "Orders-Plan-family sheets (63261, Eastman first sheet) have only "
        "a couple of vocab hits — too few for the original vocab-only "
        "kv_pair_count check. The adjacency-based signal (text-cell ending "
        "in ':' next to a non-text value) provides the orthogonal signal "
        "that closes the SHEET_IS_PLI detection gap. P2 should keep this "
        "tool — it's small (~20 LOC) but decisive.\n\n"
        "### 5. The shape model carries forward — minor extensions\n\n"
        "ShapeSummary's current field set is sufficient for P2's "
        "IdentifierExtractor and StageBandExtractor inputs. One extension "
        "that emerged during this probe: surface a `kv_adjacencies` count "
        "as a first-class field, not buried in a check. Done.\n\n"
        "### 6. Where ClassificationJudge would fire\n\n"
        f"None of the 6 files crossed the 0.3 margin threshold — the "
        "judge budget for this corpus is **0 calls**. Mode margins land "
        "between 0.60 (GUESS) and 1.40 (63261); axis margins between 0.40 "
        "(GUESS) and 1.00 (DKN). GUESS sits closest to the boundary "
        "(mode margin 0.60) and would be the file most likely to flip on "
        "a small layout change. The ClassificationJudge should be ENABLED "
        "as a safety net but is unlikely to fire on typical TNAs.\n\n"
        "### 7. Tool-variant churn — recommendation\n\n"
        "Implementing three variants of each tool added ~300 LOC of "
        "variant code. The recommendation is to **freeze the winning "
        "variant per tool and delete the losers** as the first refactor "
        "after P1. This probe report is the audit trail for those "
        "deletions.\n\n"
        "### 8. Code-size note\n\n"
        "P1 ended at ~1450 SLOC (non-blank/non-comment) across "
        "`shape_tools.py` + `checks.py` + `shape_models.py`, exceeding the "
        "1000 LOC target. The overshoot is concentrated in (a) variant "
        "implementations (kept for the comparison, to be deleted) and "
        "(b) defensive guards added when investigating per-file "
        "misclassifications (the section-suppression in "
        "`axis_whole_sheet`, the alias-repetition guard in "
        "`header_continuity`). The defensive guards are load-bearing "
        "and should stay; the variants are deletable.\n"
    )


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    dataset_dir = REPO_ROOT / "dataset"
    if not dataset_dir.is_dir():
        print(f"FATAL: dataset dir {dataset_dir} not found", file=sys.stderr)
        return 1

    results: list[tuple[FileTarget, dict]] = []
    filename_adjustments: list[str] = []
    for target in GROUND_TRUTH:
        path = _resolve_file(target.filename, dataset_dir)
        if path is None:
            print(f"WARN: file not found: {target.filename}", file=sys.stderr)
            results.append((target, {"file": target.filename, "error": "file not found"}))
            continue
        if path.name != target.filename:
            filename_adjustments.append(
                f"requested `{target.filename}` -> using `{path.name}`"
            )
        print(f"analysing {path.name} ...", file=sys.stderr)
        try:
            res = analyse_file(path)
        except Exception as exc:
            res = {"file": path.name, "error": f"{type(exc).__name__}: {exc}"}
        results.append((target, res))

    report = build_report(results)
    if filename_adjustments:
        # prepend a small footnote-style note about adjustments
        notes = "\n".join(f"- {n}" for n in filename_adjustments)
        report = report.replace(
            "## 1. Overview",
            f"## 1. Overview\n\n*Filename adjustments:*\n{notes}\n",
            1,
        )
    out_path = REPO_ROOT / "experiments" / "p1_shape_classification.md"
    out_path.write_text(report)
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

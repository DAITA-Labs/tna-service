"""P2 harness — drives the 6 corpus files and emits the markdown report.

Usage:
    .venv/bin/python -m experiments.p2.run_p2
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from experiments.p1.run_p1 import GROUND_TRUTH as P1_GT, _resolve_file, analyse_file  # noqa: E402
from experiments.p1.shape_tools import materialise_grid  # noqa: E402
from experiments.specs.enums import PliMode  # noqa: E402
from experiments.specs.identifiers import IDENTIFIER_SPECS  # noqa: E402

from experiments.p2.extractor import run_identifier_extractor  # noqa: E402
from experiments.p2.locator_models import (  # noqa: E402
    DetectedFieldLocation,
    IdentifierExtractionResult,
)
from experiments.p2.scorer import score_file  # noqa: E402


# =============================================================================
# Variant combinations to evaluate
# =============================================================================


LABEL_STRATEGIES = ["vocab_only", "vocab_plus_fuzzy", "combined_weighted"]
DTYPE_STRATEGIES = ["strict", "soft"]
SCOPE_STRATEGIES = ["cardinality_only", "region_based", "combined"]


# =============================================================================
# Per-file driver
# =============================================================================


@dataclass
class P2FileTarget:
    filename: str
    pli_mode: PliMode
    notes: str


P2_GROUND_TRUTH = [
    P2FileTarget(t.filename, t.expected_mode, t.notes) for t in P1_GT
]


def run_one_file(file_path: Path) -> dict:
    """Run shape analysis + every variant combo for one file."""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    p1_result = analyse_file(file_path)
    if "error" in p1_result:
        return {"error": p1_result["error"], "file": file_path.name}

    sheet_name = p1_result["sheet_name"]
    ws = wb[sheet_name]
    grid = materialise_grid(ws)
    shape = p1_result["shape"]
    classification = p1_result["classification"]
    pli_mode = classification.pli_mode

    # Load labels file & infer pli_count for THIS sheet
    label_path = REPO_ROOT / "dataset" / "extracted" / (
        file_path.stem + ".json"
    )
    pli_count_for_sheet = 1
    n_label_plis = 0
    if label_path.exists():
        labels = json.loads(label_path.read_text())
        n_label_plis = len(labels.get("plis", []))
        sheet_plis = [
            p for p in labels.get("plis", [])
            if p.get("source_sheet") == sheet_name
        ]
        pli_count_for_sheet = max(1, len(sheet_plis))

    # Run all variant combinations
    combos: dict[str, IdentifierExtractionResult] = {}
    for ls in LABEL_STRATEGIES:
        for ds in DTYPE_STRATEGIES:
            for ss in SCOPE_STRATEGIES:
                key = f"{ls}|{ds}|{ss}"
                res = run_identifier_extractor(
                    file_name=file_path.name,
                    sheet_name=sheet_name,
                    grid=grid,
                    shape=shape,
                    pli_mode=pli_mode,
                    pli_count_label=pli_count_for_sheet,
                    label_strategy=ls,
                    dtype_strategy=ds,
                    scope_strategy=ss,
                )
                combos[key] = res

    # Score every combo
    scores: dict[str, dict] = {}
    for key, res in combos.items():
        scores[key] = score_file(res, label_path, grid)

    return {
        "file": file_path.name,
        "sheet_name": sheet_name,
        "pli_mode": pli_mode.value if pli_mode else None,
        "n_label_plis": n_label_plis,
        "pli_count_for_sheet": pli_count_for_sheet,
        "combos": combos,
        "scores": scores,
        "shape": shape,
    }


# =============================================================================
# Reporting
# =============================================================================


DEFAULT_COMBO = "combined_weighted|strict|combined"


def _fmt_value(v):
    if v is None:
        return "null"
    s = str(v)
    if len(s) > 30:
        return s[:27] + "..."
    return s


def _per_file_section(target: P2FileTarget, file_result: dict) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {target.filename}")
    if "error" in file_result:
        lines.append(f"\nERROR: {file_result['error']}")
        return lines
    lines.append(f"\n**Notes:** {target.notes}")
    lines.append(f"**Sheet:** `{file_result['sheet_name']}` — "
                 f"label_plis={file_result['n_label_plis']} "
                 f"(this sheet={file_result['pli_count_for_sheet']})")
    lines.append(f"**Pli mode (P1 classifier):** `{file_result['pli_mode']}`")

    default = file_result["scores"].get(DEFAULT_COMBO, {})
    res: IdentifierExtractionResult = file_result["combos"][DEFAULT_COMBO]
    if "error" in default:
        lines.append(f"\n{default['error']}\n")
        return lines

    lines.append("")
    lines.append(f"**Default combo:** `{DEFAULT_COMBO}` — "
                 f"scope-correct {default['n_scope_correct']}/{default['n_with_label']}, "
                 f"value matches {default['n_matched']}/{default['n_predicted']}, "
                 f"e2e PLI estimate {default['e2e_pli_count']}")
    lines.append("")
    lines.append("**Per-canonical findings:**")
    lines.append("")
    lines.append("| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for canonical in [s.canonical for s in IDENTIFIER_SPECS]:
        rec = default["per_canonical"][canonical]
        has = "yes" if rec["has_label"] else "no"
        ok = "yes" if rec["scope_correct"] else "no"
        cell_anchor = rec.get("chosen_cell") or rec.get("chosen_anchor_col") or "—"
        sample = ""
        if rec.get("samples"):
            s = rec["samples"][0]
            if isinstance(s, dict) and "expected" in s:
                sample = (f"row {s.get('anchor_row', '-')} exp={_fmt_value(s['expected'])} "
                          f"obs={_fmt_value(s['observed'])} {'OK' if s['match'] else 'MISS'}")
        lines.append(
            f"| `{canonical}` | {has} | {rec['expected_scope']} | "
            f"{rec['predicted_scope']} | {ok} | `{cell_anchor}` | "
            f"{rec['confidence']:.2f} | {rec['matches']}/{rec['predictions']} | "
            f"{sample} |"
        )
    lines.append("")

    # Notable misses
    misses: list[str] = []
    for canonical, rec in default["per_canonical"].items():
        if not rec["has_label"]:
            continue
        if not rec["has_locator"]:
            misses.append(f"- `{canonical}`: no locator produced (label values exist)")
        elif rec["predictions"] and rec["matches"] == 0:
            s = rec["samples"][0] if rec["samples"] else {}
            misses.append(f"- `{canonical}`: predictions={rec['predictions']} but matches=0 "
                          f"(expected `{_fmt_value(s.get('expected'))}` got `{_fmt_value(s.get('observed'))}`)")
        elif not rec["scope_correct"]:
            misses.append(f"- `{canonical}`: scope mismatch (exp {rec['expected_scope']}, got {rec['predicted_scope']})")
    if misses:
        lines.append("**Notable misses / surprises:**")
        lines.append("")
        lines.extend(misses)
        lines.append("")

    # Top candidates per canonical (for transparency)
    lines.append("**Top 1-2 candidates per canonical (default combo):**")
    lines.append("")
    lines.append("```")
    for canonical in [s.canonical for s in IDENTIFIER_SPECS]:
        cands = res.candidates_per_canonical.get(canonical, [])
        if not cands:
            lines.append(f"{canonical:14}: (no candidates)")
            continue
        for cand in cands[:2]:
            v = _fmt_value(cand.value)
            lines.append(
                f"{canonical:14}: kind={cand.kind:13} label={cand.label_cell:>4} "
                f"val={cand.value_cell or '-':>4} dt={cand.observed_dtype:5} "
                f"label_score={cand.label_score:.2f} value_score={cand.value_score:.2f} "
                f"combined={cand.combined_score:.2f} sig={cand.label_signal} "
                f"v={v}"
            )
    lines.append("```")
    lines.append("")
    return lines


def _aggregate_table(results: list[tuple[P2FileTarget, dict]]) -> list[str]:
    lines = []
    lines.append("## Aggregate scoring")
    lines.append("")
    lines.append("**Default combo:** `" + DEFAULT_COMBO + "`")
    lines.append("")
    lines.append("| file | label PLIs | sheet PLIs | scope_correct | value_matches | e2e_plis |")
    lines.append("|---|---|---|---|---|---|")
    total_scope_correct = 0
    total_with_label = 0
    total_matches = 0
    total_predictions = 0
    for target, fr in results:
        if "error" in fr:
            lines.append(f"| {target.filename[:30]} | - | - | err | err | - |")
            continue
        sc = fr["scores"][DEFAULT_COMBO]
        total_scope_correct += sc["n_scope_correct"]
        total_with_label += sc["n_with_label"]
        total_matches += sc["n_matched"]
        total_predictions += sc["n_predicted"]
        lines.append(
            f"| {target.filename[:30]} | {fr['n_label_plis']} | "
            f"{fr['pli_count_for_sheet']} | "
            f"{sc['n_scope_correct']}/{sc['n_with_label']} | "
            f"{sc['n_matched']}/{sc['n_predicted']} | {sc['e2e_pli_count']} |"
        )
    lines.append("")
    lines.append(
        f"**Totals:** scope_correct={total_scope_correct}/{total_with_label} "
        f"({100.0*total_scope_correct/total_with_label if total_with_label else 0:.0f}%), "
        f"value_matches={total_matches}/{total_predictions} "
        f"({100.0*total_matches/total_predictions if total_predictions else 0:.0f}%)"
    )
    lines.append("")

    # Per-canonical aggregate
    lines.append("**Per-canonical aggregate (default combo):**")
    lines.append("")
    lines.append("| canonical | label_present (files) | locator_built | scope_correct | value matches / preds | recall |")
    lines.append("|---|---|---|---|---|---|")
    for spec in IDENTIFIER_SPECS:
        n_files_with_label = 0
        n_files_locator = 0
        n_files_scope_correct = 0
        sum_matches = 0
        sum_predictions = 0
        sum_label_present = 0
        for target, fr in results:
            if "error" in fr:
                continue
            rec = fr["scores"][DEFAULT_COMBO]["per_canonical"].get(spec.canonical, {})
            if rec.get("has_label"):
                n_files_with_label += 1
                sum_label_present += rec.get("label_present", 0)
            if rec.get("has_locator"):
                n_files_locator += 1
            if rec.get("scope_correct"):
                n_files_scope_correct += 1
            sum_matches += rec.get("matches", 0)
            sum_predictions += rec.get("predictions", 0)
        recall = (100.0 * sum_matches / sum_label_present) if sum_label_present else 0
        lines.append(
            f"| `{spec.canonical}` | {n_files_with_label} | {n_files_locator} | "
            f"{n_files_scope_correct} | {sum_matches}/{sum_predictions} | {recall:.0f}% |"
        )
    lines.append("")
    return lines


def _variant_comparison(results: list[tuple[P2FileTarget, dict]]) -> list[str]:
    """Compare every (label, dtype, scope) variant on key metrics."""
    lines = []
    lines.append("## Variant comparison")
    lines.append("")
    lines.append("Each cell = total value-matches / total predictions across the 6 files.")
    lines.append("")
    # Label strategy axis
    lines.append("### Variant axis 1 — label match strategy")
    lines.append("")
    lines.append("| label_strategy | dtype=strict | dtype=soft |")
    lines.append("|---|---|---|")
    for ls in LABEL_STRATEGIES:
        cells = [f"`{ls}`"]
        for ds in DTYPE_STRATEGIES:
            key = f"{ls}|{ds}|combined"
            m = p = 0
            for _, fr in results:
                if "error" in fr:
                    continue
                sc = fr["scores"][key]
                m += sc["n_matched"]
                p += sc["n_predicted"]
            cells.append(f"{m}/{p}")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Scope strategy axis
    lines.append("### Variant axis 2 — scope detection strategy (label=combined_weighted, dtype=strict)")
    lines.append("")
    lines.append("| scope_strategy | scope_correct | value_matches |")
    lines.append("|---|---|---|")
    for ss in SCOPE_STRATEGIES:
        key = f"combined_weighted|strict|{ss}"
        sc_correct = 0
        with_label = 0
        m = p = 0
        for _, fr in results:
            if "error" in fr:
                continue
            sc = fr["scores"][key]
            sc_correct += sc["n_scope_correct"]
            with_label += sc["n_with_label"]
            m += sc["n_matched"]
            p += sc["n_predicted"]
        lines.append(f"| `{ss}` | {sc_correct}/{with_label} | {m}/{p} |")
    lines.append("")

    # Dtype strategy axis
    lines.append("### Variant axis 3 — dtype enforcement (label=combined_weighted, scope=combined)")
    lines.append("")
    lines.append("| dtype_strategy | scope_correct | value_matches | locator-built |")
    lines.append("|---|---|---|---|")
    for ds in DTYPE_STRATEGIES:
        key = f"combined_weighted|{ds}|combined"
        sc_correct = 0
        with_label = 0
        m = p = 0
        locator_count = 0
        for _, fr in results:
            if "error" in fr:
                continue
            sc = fr["scores"][key]
            sc_correct += sc["n_scope_correct"]
            with_label += sc["n_with_label"]
            m += sc["n_matched"]
            p += sc["n_predicted"]
            for rec in sc["per_canonical"].values():
                if rec.get("has_locator"):
                    locator_count += 1
        lines.append(f"| `{ds}` | {sc_correct}/{with_label} | {m}/{p} | {locator_count} |")
    lines.append("")

    # Per-file impact of label strategy
    lines.append("### Per-file value-match impact (default scope=combined, dtype=strict)")
    lines.append("")
    lines.append("| file | vocab_only | vocab_plus_fuzzy | combined_weighted |")
    lines.append("|---|---|---|---|")
    for target, fr in results:
        if "error" in fr:
            lines.append(f"| {target.filename[:30]} | err | err | err |")
            continue
        cells = [target.filename[:30]]
        for ls in LABEL_STRATEGIES:
            sc = fr["scores"][f"{ls}|strict|combined"]
            cells.append(f"{sc['n_matched']}/{sc['n_predicted']}")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _spec_coverage_section(results: list[tuple[P2FileTarget, dict]]) -> list[str]:
    lines = []
    lines.append("## Spec coverage analysis")
    lines.append("")
    lines.append("For each spec, what fraction of files (a) had the canonical in labels and "
                 "(b) the extractor produced a locator. When (a) > (b), the spec needs more "
                 "aliases or a different match strategy.")
    lines.append("")
    lines.append("| spec | files w/ label | files w/ locator | success | aliases |")
    lines.append("|---|---|---|---|---|")
    for spec in IDENTIFIER_SPECS:
        n_label = 0
        n_locator = 0
        for _, fr in results:
            if "error" in fr:
                continue
            rec = fr["scores"][DEFAULT_COMBO]["per_canonical"].get(spec.canonical, {})
            if rec.get("has_label"):
                n_label += 1
            if rec.get("has_locator"):
                n_locator += 1
        ratio = f"{n_locator}/{n_label}" if n_label else f"-/0"
        aliases = ", ".join(spec.aliases[:6])
        lines.append(f"| `{spec.canonical}` | {n_label} | {n_locator} | {ratio} | {aliases} |")
    lines.append("")

    # Per-spec refinement proposals
    lines.append("### Refinement proposals")
    lines.append("")
    proposals: list[str] = []

    # examine each spec for systematic failures
    for spec in IDENTIFIER_SPECS:
        n_label = 0
        n_no_locator = 0
        n_value_fail = 0
        examples_missed: list[str] = []
        examples_no_loc: list[str] = []
        for target, fr in results:
            if "error" in fr:
                continue
            rec = fr["scores"][DEFAULT_COMBO]["per_canonical"].get(spec.canonical, {})
            if rec.get("has_label"):
                n_label += 1
                if not rec.get("has_locator"):
                    n_no_locator += 1
                    examples_no_loc.append(target.filename[:25])
                elif rec.get("predictions") and rec.get("matches", 0) == 0:
                    n_value_fail += 1
                    if rec.get("samples"):
                        s = rec["samples"][0]
                        examples_missed.append(
                            f"{target.filename[:25]}: exp={_fmt_value(s.get('expected'))} obs={_fmt_value(s.get('observed'))}"
                        )
        if n_no_locator or n_value_fail:
            line = (
                f"- `{spec.canonical}`: missing locator in {n_no_locator}/{n_label} files"
                f"{' ('+', '.join(examples_no_loc)+')' if examples_no_loc else ''}; "
                f"wrong value in {n_value_fail}/{n_label}"
            )
            if examples_missed:
                line += " — " + "; ".join(examples_missed[:2])
            proposals.append(line)
    if proposals:
        lines.extend(proposals)
    else:
        lines.append("(All specs converged on default combo.)")
    lines.append("")
    return lines


def _judge_firing_section(results: list[tuple[P2FileTarget, dict]]) -> list[str]:
    lines = []
    lines.append("## Where IdentifierPhaseJudge would fire")
    lines.append("")
    lines.append("Triggers: (a) mid-confidence locator (0.30 <= conf < 0.70), "
                 "(b) multiple competing candidates with similar scores, "
                 "(c) mandatory field missing.")
    lines.append("")
    for target, fr in results:
        if "error" in fr:
            continue
        res: IdentifierExtractionResult = fr["combos"][DEFAULT_COMBO]
        triggers: list[str] = []
        for canonical, decision in res.scope_decisions.items():
            if 0.30 <= decision.confidence < 0.70:
                triggers.append(
                    f"- `{canonical}`: conf={decision.confidence:.2f} — {decision.reason}"
                )
            if len(decision.competing) >= 1 and decision.chosen is not None:
                top = decision.chosen.combined_score
                rival = decision.competing[0].combined_score
                if top - rival < 0.05:
                    triggers.append(
                        f"- `{canonical}`: top score {top:.2f} vs rival {rival:.2f} (gap < 0.05)"
                    )
        for w in res.warnings:
            triggers.append(f"- WARNING: {w}")
        if triggers:
            lines.append(f"### {target.filename}")
            lines.append("")
            for t in triggers[:8]:
                lines.append(t)
            lines.append("")
    return lines


def build_report(results: list[tuple[P2FileTarget, dict]]) -> str:
    parts: list[str] = []
    parts.append("# P2 — Identifier Extraction Probe")
    parts.append("")
    parts.append(
        "## 1. Overview\n\n"
        "This probe builds the identifier-extraction layer of the three-area "
        "design. The core primitive is `find_field_locations(grid, shape, spec)` "
        "— a parametric workhorse called once per FieldSpec (9 identifier "
        "canonicals). On top of it sits a scope detector (SHEET / GROUP / PLI) "
        "that converts the candidates into `FieldLocator` objects "
        "consumable by apply_plan.\n\n"
        "**Ground-truth methodology:** For each file we load "
        "`dataset/extracted/<filename>.json`, infer the expected scope per "
        "canonical from the per-PLI value vector "
        "(`all-same -> SHEET`, `partition into runs -> GROUP`, `distinct -> PLI`), "
        "and then compare the extractor's chosen FieldLocator against the "
        "labels by reading values through the locator (per-PLI for PLI-scoped "
        "fields, once for SHEET-scoped, group-by-group for GROUP).\n\n"
        "**Variants evaluated:** 3 label strategies × 2 dtype strategies × "
        "3 scope strategies = 18 combos per file. Default = "
        f"`{DEFAULT_COMBO}`.\n"
    )

    parts.extend(_aggregate_table(results))
    parts.append("## Per-file detail")
    parts.append("")
    for target, fr in results:
        parts.extend(_per_file_section(target, fr))
    parts.extend(_variant_comparison(results))
    parts.extend(_spec_coverage_section(results))
    parts.extend(_judge_firing_section(results))

    parts.append("## Recommendations for P3 + P4")
    parts.append("")
    parts.append(_recommendations_text(results))
    return "\n".join(parts)


def _recommendations_text(results: list[tuple[P2FileTarget, dict]]) -> str:
    # Compute per-spec stats
    spec_loc_count: dict[str, int] = {}
    spec_label_count: dict[str, int] = {}
    for target, fr in results:
        if "error" in fr:
            continue
        for canonical, rec in fr["scores"][DEFAULT_COMBO]["per_canonical"].items():
            if rec.get("has_label"):
                spec_label_count[canonical] = spec_label_count.get(canonical, 0) + 1
            if rec.get("has_locator"):
                spec_loc_count[canonical] = spec_loc_count.get(canonical, 0) + 1
    return (
        "### 1. Parametric workhorse works across all three pli_modes\n\n"
        "The single `find_field_locations(grid, shape, spec)` function handles "
        "ROW_PER_PLI (column-header path: DKN, CB, MOPD), SHEET_IS_PLI "
        "(KV path with top-of-sheet labels: 63261, Eastman), and "
        "SECTION_PER_PLI (KV path with repeating in-rect labels: GUESS) "
        "without per-mode branching. The branch happens INSIDE the function "
        "(column-header vs KV) and is driven by SHAPE signals "
        "(`r in header_rows` + `r <= biggest_rect.r1`) rather than the "
        "pli_mode classification. Empirically: pli_mode is NOT used by "
        "find_field_locations at all. So a mis-classification of pli_mode "
        "is not catastrophic — the extractor still emits candidates because "
        "candidate-shape is what gates which path runs.\n\n"
        "### 2. Variant winners — modest discrimination on this corpus\n\n"
        "The 3×2×3 variant matrix shows that **label_strategy** has small "
        "absolute impact on value-match counts (within 1%): on this corpus "
        "vocab-only finds nearly all the high-quality matches by itself — "
        "the SOFT mode of `combined_weighted` adds noisy candidates that "
        "cross-spec-dedupe then prunes. The interesting effect is at the "
        "*spec coverage* level: SOFT-mode label matching is what lets "
        "`fabric_name` find I2 in DKN/MOPD (label 'Fabric Quality' with "
        "fuzzy_soft score 0.35) — vocab-only misses it. **Verdict: keep "
        "`combined_weighted` as default; the spec's `label_match_mode` (HARD/"
        "MEDIUM/SOFT) inside the spec is the real lever.**\n\n"
        "**dtype_strategy** is the biggest mover. `strict` produces 33 "
        "locators with 551 value matches; `soft` produces 37 locators and "
        "734 value matches. The 33% match-bump comes mostly from style_code "
        "in MOPD — the spec's `max_len=20` rejects valid 35-char codes in "
        "strict mode. The cost: soft also accepts e.g. fabric_name in DKN at "
        "I2 where the labels file has fabric_code there. **Verdict: keep "
        "`strict` as the safe default. Where mandatory fields aren't found "
        "in strict mode, RE_EXTRACT with `soft` is the natural escalation.**\n\n"
        "**scope_strategy** moves nothing on this corpus: all three strategies "
        "(cardinality_only / region_based / combined) produce identical scope "
        "decisions, because most decisions are dominated by the "
        "`is_column_anchored(cand)` signal that all three respect. **Verdict: "
        "the variants converge here; keep `combined` as the most defensible.**\n\n"
        "### 3. Cross-spec dedupe is essential\n\n"
        "Many specs share aliases by design (`color_code` and `color_name` "
        "both have 'color' / 'colour'; `fabric_code` and `fabric_name` both "
        "have 'fabric'). The cross-spec dedupe in the extractor takes the "
        "highest-scoring canonical at each value cell, and dtype-aware "
        "constraints (color_code allows INT_LARGE, color_name does not) "
        "break the tie deterministically. The L2 candidate in DKN (value "
        "'6602') goes to color_code at combined=1.00 and demotes color_name "
        "(combined=0.44) → correct.\n\n"
        "### 4. Spec coverage gaps — refinement proposals\n\n"
        f"- `io_number`: locator built in only {spec_loc_count.get('io_number', 0)}/"
        f"{spec_label_count.get('io_number', 0)} files. The label files in DKN/"
        "MOPD/GUESS conflate `io_number` with `buyer_po_no` (the labels' "
        "io_number value matches the PO column, not any IO column). The spec "
        "is correct to reject 'Buyer Po No' as buyer_po_no; this is a "
        "**labels-data discrepancy**, not a spec bug. To match the label "
        "files literally, the labelling convention would need to change. "
        "63261 uses 'Job No' for io_number — that alias is NOT in the spec; "
        "adding 'job no' would close 1 file's gap.\n"
        "- `quantity`: locator built in "
        f"{spec_loc_count.get('quantity', 0)}/{spec_label_count.get('quantity', 0)} "
        "files. GUESS misses because quantity = ROW SUM of size columns; "
        "there is no single 'Quantity' column. This needs a derived-value "
        "step (post-extraction summation), not a spec addition.\n"
        "- `style_code` value max_len=20 rejects MOPD/CB long codes "
        "('DWJE MANOS 08 1000000099 5000007827' is 35 chars). Either bump "
        "max_len to 40 OR introduce a 'compound code' value_pattern that "
        "still classifies as code_alnum.\n"
        "- `delivery_date` MEDIUM mode misses 'Etd Ex factory as per P.O' "
        "(token-jaccard with 'etd' is 1/6). Note: the spec's anti_patterns "
        "EXPLICITLY exclude 'Ex Factory' (says it's metadata.ex_factory_date), "
        "so this is intentional — the labels file disagrees with the spec on "
        "where delivery_date lives.\n"
        "- `fabric_name` strict mode finds I2 column-headers in CB/MOPD/DKN "
        "(values are long fabric compositions) but those don't match any "
        "spec for fabric_code OR fabric_name — they're a single-column "
        "supplier convention. **The judge fires here** (single fabric "
        "column where labels conflate code+name).\n"
        "- `color_code` in GUESS — column 13 is 'CODE' (just the word), "
        "not in color_code aliases. Add 'code' as a SOFT alias OR rely on "
        "judge to identify the column from row-1 context.\n\n"
        "### 5. End-to-end PLI count\n\n"
        "Walking the highest-quality PLI-anchored locator (preferring "
        "io_number → style_code → quantity → style_name → color_name) gives "
        "PLI count estimates close to label counts:\n\n"
        + "\n".join(
            f"  - {target.filename[:34]}: predicted "
            f"{fr['scores'][DEFAULT_COMBO]['e2e_pli_count']} vs label "
            f"{fr['pli_count_for_sheet']}"
            for target, fr in results if "error" not in fr
        ) + "\n\n"
        "GUESS's 169 vs 170 gap = the 170th PLI is at row 200 which is past "
        "the natural blank-run trim. CB's 1 vs 7 gap = io_number column "
        "(B) has merged-cell pattern (1063 at B4, blanks at B5-B8, 1064 at "
        "B9 etc.) and the trailing-blank trim stops counting after row 4. "
        "If P4's apply_plan iterates ALL data rows (not just those with "
        "io values), it'll get the right PLI count. For Eastman the "
        "per-sheet PLI count is 1 (SHEET_IS_PLI); the workbook-level "
        "35-PLI total comes from iterating all 36 sheets.\n\n"
        "### 6. Where IdentifierPhaseJudge should fire\n\n"
        "Concrete triggers on this corpus:\n\n"
        "- **Mandatory missing**: io_number is mandatory but absent in 5/6 "
        "files (label-file conflation issue). The phase judge sees this and "
        "should propose an alternative (use buyer_po_no?) or ESCALATE.\n"
        "- **Single-fabric-column** (CB, MOPD, GUESS): one 'Fabric' label "
        "with a long-text value, spec requires either fabric_code (short) "
        "or fabric_name (long descriptive). The deterministic layer picks "
        "fabric_name in soft mode, none in strict. The judge resolves by "
        "looking at the actual value.\n"
        "- **GUESS color_code (column 13 'CODE')**: not in aliases. Judge "
        "sees the column-header row and proposes color_code from positional "
        "evidence.\n"
        "- **GUESS section scope mismatch** for color_code / fabric_code: "
        "the scope detector says GROUP (15 sections → 15 candidates) but "
        "labels expect PLI. The phase judge can override scope based on "
        "row-uniqueness of the per-section data rows.\n\n"
        "### 7. What P3 + P4 need from P2\n\n"
        "- P3 (StageBandDetector): reuse `find_field_locations` parametric "
        "over StageSpec. The same column-header path applies to stage names "
        "(e.g. 'Sewing Start' at row 2 with date values below). Pass `shape` "
        "so the same header-row detection works.\n"
        "- P4 (apply_plan): consume FieldLocator directly. For PLI-scoped "
        "column-anchored locators the read is `(pli_anchor_row, anchor_col)`. "
        "For SHEET-scoped FIXED-cell locators it's a one-time read. For "
        "GROUP-scoped locators apply_plan needs PliGroup; P2 produces "
        "`group_id='auto'` but doesn't resolve the group's PLI anchors — "
        "that's a P4 wiring concern (or a small follow-up component that "
        "consumes the candidate set).\n\n"
        "### 8. Code-size note\n\n"
        "P2 ended at ~2100 LOC across the 6 files in `experiments/p2/` — "
        "exceeds the 1200 target. The bulk is harness (`run_p2.py` ~640 "
        "LOC reporting) and the scorer (~340 LOC). The actual workhorse "
        "(`find_field_locations` + `scope_detection`) is ~900 LOC; trim "
        "candidate during refactor: remove variant strategies kept for the "
        "comparison (similar to P1's recommendation #7).\n"
    )


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    dataset_dir = REPO_ROOT / "dataset"
    if not dataset_dir.is_dir():
        print(f"FATAL: dataset dir {dataset_dir} not found", file=sys.stderr)
        return 1

    results: list[tuple[P2FileTarget, dict]] = []
    for target in P2_GROUND_TRUTH:
        path = _resolve_file(target.filename, dataset_dir)
        if path is None:
            print(f"WARN: file not found: {target.filename}", file=sys.stderr)
            results.append((target, {"error": "file not found"}))
            continue
        print(f"P2: analysing {path.name} ...", file=sys.stderr)
        try:
            fr = run_one_file(path)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            fr = {"error": f"{type(exc).__name__}: {exc}", "file": path.name}
        results.append((target, fr))

    report = build_report(results)
    out_path = REPO_ROOT / "experiments" / "p2_identifier_extraction.md"
    out_path.write_text(report)
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

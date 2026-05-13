# SheetRowPlanner — design

**Date:** 2026-05-13
**Status:** Implemented

## Problem

The current pipeline routes iteration responsibility through an LLM agent (`BoundaryFinder`), which emits a `PLIBoundaries` artifact: a single `(data_start_row, data_end_row)` range plus a pattern enum and a string-matched total-row filter. This breaks on real workbooks:

- **CHRISTIAN BERG- T&A.xlsx** has 7 PLIs across two anchor-grouped sections (rows 4-7 and 9-11) separated by unmarked total rows (8, 12, 13). The current system returns 3. The single-range artifact cannot express the two groups; the total filter requires a string marker the sheet doesn't have.
- **new job-TNA.xlsx**, **TNA DETAILS.xlsx**, and **NEW.xlsx** use scattered key-value identity blocks plus stacked Plan/Action/Deviation stage bands — a layout family (`SHEET_IS_PLI`) that the row-based iteration model does not represent naturally.
- The four `BoundaryPattern` enum values (`one_row_per_pli`, `vertical_merge`, `data_then_total`, `one_sheet_per_pli`) only cover four points in a much larger layout space. Every new layout family currently means a prompt tweak in `BoundaryFinder`.

Row arithmetic is exactly the thing LLMs are bad at; vocabulary interpretation (mapping supplier labels to canonical field names) is exactly the thing they are good at. The current split is inverted.

## Goal

Replace the LLM-led iteration system with a deterministic `SheetRowPlanner` that emits a unified `SheetPlan` artifact covering all observed layout families. Use the LLM as a **reviewer/judge** of the plan, not a producer.

## Non-goals

- Changing how PLIs aggregate across sheets (orchestrator behaviour stays).
- Changing the 4 extraction-time validators (`SourceCellVerifier`, `HeaderMatchVerifier`, `CoverageVerifier`, `FieldDropoutVerifier`) — they validate the final `ExtractionResult` and remain.
- Changing the API surface (`POST /extract` shape stays).
- Adding new field types to `PLI` / `Stage` — the output schema is unchanged.

## Design

### Unified artifact: `SheetPlan`

```
SheetPlan(
  sheet:           str,
  pli_mode:        ROW_PER_PLI | SECTION_PER_PLI | SHEET_IS_PLI,
  identity_column: str | None,                    # ROW_PER_PLI
  header_rows:     list[int],
  rows:            list[RowSpec],                 # ROW_PER_PLI
  pli_blocks:      list[PliBlock],                # SECTION_PER_PLI
  kv_anchors:      list[KVAnchor],                # SHEET_IS_PLI
  stage_bands:     list[StageBandSpec],           # sheet-level when stage_scope=SHEET_LEVEL
  stage_scope:     SHEET_LEVEL | SECTION_LOCAL | PLI_LOCAL,
  confidence:      float,
)

RowSpec(
  idx:          int,
  role:         TITLE | HEADER | ANCHOR | CHILD | TOTAL | GRAND_TOTAL
              | REPEAT_HEADER | BLANK | SEPARATOR,
  anchor_idx:   int | None,
  group_id:     int | None,
  sub_row_role: PLAN | ACTION | ACTUAL | DEVIATION | None,
)

PliBlock(
  id:            int,
  bbox:          (start_row, end_row),
  identity:      list[KVAnchor],
  stage_bands:   list[StageBandSpec],
)

KVAnchor(label_cell, value_cell, field)

StageBandSpec(
  name, name_cell, sub_header_row,
  sub_rows:     dict[role → row],
  stage_cols:   dict[stage_name → col],
  layout_mode:  WIDE_SUB_COLUMNS | TALL_SUB_ROWS,
)
```

The three axes are orthogonal:

| PLI scope | Stage scope | PLI height |
| --- | --- | --- |
| `ROW_PER_PLI` | `SHEET_LEVEL` | `SINGLE_ROW` |
| `SECTION_PER_PLI` | `SECTION_LOCAL` | `MULTI_ROW` (sub-rows: PLAN/ACTION/DEVIATION) |
| `SHEET_IS_PLI` | `PLI_LOCAL` | — |

Any combination is valid. The six observed layout families are six points in this space; future families fit by adding rules to the deterministic detector, not new enum cases.

#### Robustness — every cell of the 3-axis cube must be expressible

This is a hard requirement on `SheetPlan`: any combination of (PLI scope × Stage scope × PLI height) — including combinations we haven't seen yet — must round-trip through the artifact with no special cases at apply time. The following invariants make that hold:

- **PLI scope and PLI height are independent.** `RowSpec.sub_row_role` works the same way for `ROW_PER_PLI` and for `PliBlock`-embedded sub-grids. A 3-row tall multi-row PLI inside a tabular grid is represented identically to a 3-row tall sub-row inside a `PliBlock`.
- **Stage scope decoupled from PLI scope via where bands live, not how they're shaped.** `SHEET_LEVEL` → `SheetPlan.stage_bands`. `SECTION_LOCAL` → also `SheetPlan.stage_bands`, with each band's bbox associated to a section via row range. `PLI_LOCAL` → `PliBlock.stage_bands`. The `StageBandSpec` shape is identical in all three; only its container differs.
- **Hybrid sheets supported.** A sheet can populate `kv_anchors` (workbook-header KV like a delivery date that applies to every PLI) *and* `rows` (tabular grid below it) — the resolver merges them: KV anchors become per-PLI metadata applied to every emitted PLI; the grid generates the PLIs themselves.
- **Recursive structure.** A `PliBlock` may contain an internal multi-color sub-grid (e.g., one block per IO with 3 color child rows). The planner emits these as `RowSpec`s with `anchor_idx` pointing inside the block's bbox — apply_plan treats the block as a mini-sheet.
- **No mode tribrid required.** Sheets never mix `ROW_PER_PLI` and `SECTION_PER_PLI` *as PLI scope at the same level* — a sheet picks one. Mixing happens only across sheets in a workbook (handled by the orchestrator), or via the recursive case above (where the block's interior runs as ROW_PER_PLI).
- **Forward compatibility.** New `RowSpec.role` values, new `sub_row_role` values, and new `StageBandSpec.layout_mode` values can be added without breaking apply_plan — the resolver dispatches on these enums; unknown values produce a deterministic warning rather than crashing.

The acceptance test for robustness: every observed layout family + every plausible future family (listed under "Acceptance criteria") must produce a `SheetPlan` that `apply_plan` reads without needing any out-of-band logic.

### Pipeline

```
WORKBOOK-LEVEL
  Phase 0  workbook_summary()                        [det tool]
  Phase 1  SheetClassifier  → relevant_sheets[]       [LLM]

PER-SHEET (parallel across sheets is allowed)
  Phase 2  SheetSurveyor    → SheetSignals            [det]
  Phase 3  SheetRowPlanner  → SheetPlan (draft)       [det]
  Phase 3a validate_plan (T1+T2) → Findings           [det]
  Phase 3b LayoutHinter (conditional) → LayoutHints   [LLM]
  Phase 3c PlanReviewer (conditional) → PlanVerdict   [LLM judge]
            → re-plan if reviewer rejects
  Phase 4  FieldNamer       → CanonicalNameMap        [LLM]
  Phase 5  apply_plan       → list[PLI]               [det, 100% LLM-free]

WORKBOOK-LEVEL (aggregation)
  Phase 6  Validators (4 existing) → ValidationFindings [det]
  Phase 7  Reconciler       → ExtractionResult        [det]
```

### Stages

| Stage | Kind | Input | Output | Tools used |
| --- | --- | --- | --- | --- |
| `workbook_summary` | tool (det) | WorkbookCtx | WorkbookSummary | — |
| `SheetClassifier` | agent (LLM) | WorkbookSummary | relevant_sheets[] | `list_sheets`, `workbook_summary` |
| `SheetSurveyor` | component (det) | sheet | SheetSignals | `get_merged_regions`, `sample_rows`, `read_range` |
| `SheetRowPlanner` | component (det) | SheetSignals | SheetPlan (draft) | `read_row`, `get_cell_at`, `get_merged_regions` |
| `validate_plan` (T1+T2) | component (det) | SheetPlan | Findings | `read_row`, `read_range`, `find_value` |
| `LayoutHinter` (cond.) | agent (LLM) | SheetSignals + ambiguities | LayoutHints | `peek_sheet`, `sample_rows`, `get_merged_regions` |
| `PlanReviewer` (cond.) | agent (LLM judge) | SheetPlan + samples + warnings | PlanVerdict | `peek_sheet`, `read_row`, `find_value` |
| `FieldNamer` | agent (LLM) | SheetPlan (labels + stage cols) | CanonicalNameMap | `peek_sheet`, `read_relative` |
| `apply_plan` | component (det, 100% LLM-free) | SheetPlan + NameMap | list[PLI] | `read_range`, `get_merged_regions` |
| `SourceCellVerifier`, `HeaderMatchVerifier`, `CoverageVerifier`, `FieldDropoutVerifier` | validators (det) | ExtractionResult | Findings | `get_cell_at`, `read_range` (or none) |
| `Reconciler` | component (det) | PLIs + Findings | ExtractionResult | — |

### `apply_plan` — locked contract

`apply_plan` is the pure resolver from `SheetPlan + CanonicalNameMap → list[PLI]`. Its contract:

- **100% deterministic.** Same inputs produce identical outputs on every run. No randomness, no time-dependent behaviour, no environment dependencies.
- **Zero LLM calls.** Not directly, not indirectly via tool calls, not via fallback paths. If an LLM is needed to resolve something at apply time, it indicates the `SheetPlan` was incomplete — the planner must be fixed, not apply_plan.
- **No external state beyond openpyxl reads via `WorkbookCtx`.** No HTTP, no disk writes, no telemetry side effects that affect output.
- **No silent fallbacks.** If a `SheetPlan` references a row, cell, or stage column that doesn't exist in the workbook, apply_plan raises a typed error caught by the orchestrator (which logs and emits a Warning on the ExtractionResult); it does not invent a default.
- **Dispatches on enums only.** apply_plan's body is a switch over `pli_mode`, `stage_scope`, and `RowSpec.role` / `sub_row_role`. New enum values are added as new branches; unknown values produce a deterministic warning. No string-keyed pattern matching, no name-based logic.
- **One pass, no agent loop.** apply_plan is straight-line code; it does not re-call any LLM agent if its output looks wrong. Output correctness is the planner's responsibility (Tier 1+2+3 validation). apply_plan trusts the plan.
- **Handles every cell of the 3-axis cube.** The dispatch table covers all 3×3×2 = 18 combinations (some collapse — e.g., `SHEET_IS_PLI` ignores PLI height). Each combination is a unit test.

Pseudocode shape:

```
def apply_plan(ctx, plan: SheetPlan, name_map: CanonicalNameMap) -> list[PLI]:
    match plan.pli_mode:
        case ROW_PER_PLI:        return _apply_row_per_pli(ctx, plan, name_map)
        case SECTION_PER_PLI:    return _apply_section_per_pli(ctx, plan, name_map)
        case SHEET_IS_PLI:       return _apply_sheet_is_pli(ctx, plan, name_map)

def _apply_row_per_pli(ctx, plan, name_map):
    plis = []
    for group_id, group_rows in groupby(plan.rows, by=group_id):
        if all_rows_have_sub_row_role(group_rows):
            # MULTI_ROW: one PLI per group, fold sub-rows into stage metadata
            plis.append(_emit_multi_row_pli(group_rows, plan, name_map, ctx))
        else:
            # SINGLE_ROW per row in the group (multi-color child rows)
            for row in group_rows:
                plis.append(_emit_single_row_pli(row, plan, name_map, ctx))
    return plis

# … similar for the other two pli_modes; SECTION_PER_PLI recursively dispatches
# back into row-per-pli inside each block when the block has internal child rows.
```

Concretely: nothing in apply_plan looks at supplier names, sheet names, or layout heuristics. Everything it needs is already in the plan + the name_map. If something is missing, it's a planner bug.

### Validation tiers for `SheetPlan`

**Tier 1 — Structural invariants (det, mandatory)**
- `ReferenceIntegrity`: every CHILD has an existing ANCHOR via `anchor_idx`.
- `RowUniqueness`: no row appears in both `data_rows` and `skipped_rows`; no duplicates.
- `HeaderContiguity`: header rows contiguous, precede all data rows.
- `PliBlockNonOverlap`: `PliBlock.bbox` ranges don't overlap.
- `StageBandFit`: stage band rectangles fit within sheet bounds; non-overlapping with each other and with KV anchor cells.
- `CoveragePartition`: every populated row classified; rows partitioned across data/skipped/ignored.
- `SubRowConsistency`: within a `group_id`, `sub_row_role` is either set on all CHILDs or none.

**Tier 2 — Statistical sanity (det, mandatory)**
- `SequenceMatch`: when an S.NO-like column exists, its max value matches ANCHOR row count.
- `TotalArithmetic`: for each TOTAL row, the quantity column value equals the sum of its scope's quantity column (±1 tolerance).
- `DateBandDensity`: stage band date columns are ≥50% date-typed across data rows.
- `KvAnchorAdjacency`: each KV anchor's value cell sits at offset (0,+1) or (+1,0) of its label and is non-empty.
- `PliCountSanity`: non-trivial sheet (max_row ≥ 10) produces ≥1 PLI; flag if PLI count > 2× distinct identity values.
- `IdentityColumnCoverage`: ≥80% of data-range rows have an identity value (directly or via merge anchor).
- `VocabularyOverlap`: header rows match ≥3 canonical vocabulary terms.

**Tier 3 — Semantic review (LLM, conditional)**

`PlanReviewer` fires when:
- Tier 1 or Tier 2 produced warnings (not errors — errors trigger re-plan instead), OR
- `plan.confidence` < 0.85, OR
- `pli_mode ∈ {SECTION_PER_PLI, SHEET_IS_PLI}` (rarer modes — extra safety).

Otherwise the plan goes straight to `apply_plan`.

Input: plan summary + 3-5 sample rows (header, first/last data row, one TOTAL) + Tier 2 warnings. Output: `PlanVerdict` with verdict (`looks_correct` | `needs_fix`), specific row corrections, identity-column suggestion, warnings, confidence.

**Reaction loop:**
- Tier 1 errors → re-plan with hints (identity_column override, mode lock); no LLM call.
- Tier 1/2 warnings only → fire `PlanReviewer`.
- Reviewer says `needs_fix` with row corrections → apply corrections, re-validate.
- Reviewer says `looks_correct` → proceed to apply_plan.
- LLM call failure → continue with original plan, record telemetry.

**Det wins on disagreement.** If `PlanReviewer` contradicts a strong det signal (e.g., sum-of-children matches but reviewer says it's data), log the discrepancy and keep the det classification. Reviewer is advisory; we use telemetry to learn which det rules need improvement.

### Tool registry — sharing primitives

The 10 existing workbook tools (`list_sheets`, `workbook_summary`, `peek_sheet`, `sample_rows`, `read_range`, `read_row`, `read_relative`, `get_cell_at`, `get_merged_regions`, `find_value`) stay unchanged. They register at import via `@tool` into a process-wide `TOOL_REGISTRY`.

Both deterministic components and LLM agents go through this registry — det components import the function and call it directly; LLM agents are handed JSON schemas via `AnthropicProvider` and the model calls by name. Single source of truth per primitive: adding a new tool (e.g. "find date-typed runs in a row") makes it available to every consumer at once.

### Shared infrastructure (unchanged)

- `WorkbookCtx` — single openpyxl handle per workbook, cached via `register_workbook(path)`.
- `LLMProvider` — Anthropic adapter with $ref-style JSON-schema inlining and tool-call loop.
- `AgentSpec` + `AgentRunner` + `RetryPolicy` — uniform agent shape (name, system prompt, output schema, build_user_input fn).
- Prompt loader — `.md` files under `app/prompts/workflow/` with `_shared.md` fragment.
- Prometheus telemetry — counters per agent, validator, extraction.

### Code layout

```
app/
  core/                  (unchanged: logging, telemetry, prompt loader)
  enums/                 (BoundaryPattern + StageLayoutMode deleted; PliMode/RowRole/SubRowRole/StageScope added)
  models/
    extraction.py        (unchanged: PLI, Stage, ExtractionResult, Source)
    workbook.py          (unchanged)
    artifacts.py         (add SheetPlan, PliBlock, RowSpec, KVAnchor, StageBandSpec,
                          CanonicalNameMap, LayoutHints, PlanVerdict)
  repositories/
    workbook_repo.py     (unchanged)
    workbook_tools/      (unchanged: 10 @tool functions + registry)
  services/
    llm_provider.py      (unchanged)
    agents/
      _base.py           (unchanged: AgentSpec/AgentRunner)
      sheet_classifier.py (unchanged)
      layout_hinter.py   (NEW)
      plan_reviewer.py   (NEW)
      field_namer.py     (NEW)
    planner/             (NEW subsystem)
      surveyor.py
      row_classifier.py
      block_segmenter.py
      kv_anchor_detector.py
      stage_band_detector.py
      plan.py            (SheetRowPlanner — orchestrates the above)
    applier/
      apply_plan.py      (NEW — replaces field_applier + stage_applier + patterns)
    validation/
      plan_invariants.py (NEW — Tier 1)
      plan_statistics.py (NEW — Tier 2)
      source_cell_verifier.py, header_match_verifier.py,
      coverage_verifier.py, field_dropout_verifier.py (unchanged)
    reconciler.py        (unchanged)
    extraction.py        (rewritten orchestration flow)
  prompts/
    _shared.md           (unchanged)
    workflow/
      sheet_classifier.md  (unchanged)
      layout_hinter.md     (NEW)
      plan_reviewer.md     (NEW)
      field_namer.md       (NEW)
  schemas/               (unchanged)
```

### Migration delta

**Delete:**
- `app/services/agents/{layout_fingerprinter,boundary_finder,identity_locator,quantity_date_locator,stage_locator}.py`
- `app/services/applier/patterns/` (entire directory: 4 handlers + registry)
- `app/services/applier/{field_applier,stage_applier}.py`
- `app/enums/{boundary_pattern,stage_layout_mode}.py` (the latter folds into `RowSpec.sub_row_role` + `StageBandSpec.layout_mode`)

**Add:** see code layout above.

**Keep:** tool registry + 10 tools, AgentSpec/AgentRunner, SheetClassifier, 4 extraction validators, Reconciler, models, telemetry, API surface, prompts.

## How it fixes the known failures

- **CHRISTIAN BERG (3 → 7 PLIs):** SheetRowPlanner detects two `ANCHOR` rows (4, 9) via identity-column population + merge map. CHILDren (5,6,7 → 4; 10,11 → 9) inherit identity via `anchor_idx`. Total rows (8, 12, 13) classified `TOTAL` / `GRAND_TOTAL` deterministically via blank identity + sum-of-children match. `SequenceMatch` validates A4=1, A9=2 = 2 anchors. Tier 3 skipped (plan is clean).
- **new job-TNA.xlsx (scattered KV + stacked sub-rows):** Each sheet is `pli_mode=SHEET_IS_PLI` with `stage_scope=SHEET_LEVEL`. `KVAnchorDetector` finds label→value pairs ("Job No"@A4 → B4, "Quantity"@A5 → B5, …). `StageBandDetector` finds three TALL_SUB_ROWS bands (Pre-Prod, Fabric, Production). `FieldNamer` maps labels to canonical fields. `PlanReviewer` fires (rarer mode + low vocab overlap) and confirms.
- **Future families:** A new layout adds rules in `app/services/planner/*.py`, not new prompts or enum cases. The artifact's three orthogonal axes absorb the variation.

## Acceptance criteria

- All 7 PLIs from CHRISTIAN BERG- T&A.xlsx are emitted with correct anchor/child structure.
- All 5 sheets of `new job-TNA.xlsx` are processed; each emits 1 PLI with full identity + 3 stage bands' values.
- Existing dataset extraction quality is preserved or improved (regression test against `dataset/extracted/*.json` labels).
- LLM call count per sheet drops from ~5 to ~1-2 in the median case.
- Unit tests for each planner sub-component (row_classifier, block_segmenter, kv_anchor_detector, stage_band_detector) covering each of the six observed layout families.
- Plan invariants and statistics validators have unit tests for both passing and failing cases.
- `apply_plan` has a unit test per cell of the 3-axis cube — at minimum one synthetic fixture per (pli_mode × stage_scope) and one with `sub_row_role` populated. Static analysis check: `apply_plan` and its callees must not import `app.services.agents` or `app.services.llm_provider`.
- Documentation updated as the final step (after impl + tests + evals are green): `ARCHITECTURE.md`, `docs/SPEC.md`, `README.md` if user-facing, and this design doc's *Status* line flipped to `Implemented`.

## Open questions deferred to the implementation plan

- Exact confidence-threshold tuning for `PlanReviewer` firing — start at 0.85, iterate based on telemetry.
- Caching of `FieldNamer` output across sheets within a workbook and across workbooks from the same supplier — design after first pass works.
- How aggressively `apply_plan` should propagate merges when CHILD rows have partial overrides (e.g., one stage value present, others inherit). Current proposal: cell-by-cell — if cell is empty AND inside a merge, use anchor's value; else use the row's own value.

# 0006 — Symmetric planner→agent contract

**Date:** 2026-05-19 (design); 2026-05-19 (implemented)
**Status:** Accepted

## Context

After SheetRowPlanner shipped (ADR-0003), an empirical probe across 9
representative files showed eight had broken extraction: ROW_PER_PLI files
returned empty canonical fields; SECTION_PER_PLI returned empty PLI husks;
only SHEET_IS_PLI partially worked (3-4/8 canonical fields, no confidence).
Root cause: the `SheetPlan` artifact was designed around the SHEET_IS_PLI case
and under-specified the identity channel for ROW_PER_PLI (column headers lived
only as cell values in `header_rows`, never lifted into the artifact) and the
`stage_columns` structure for wide_sub_columns layouts (one column per stage,
no sub-column representation).

`FieldNamer` consumed the plan asymmetrically — for SHEET_IS_PLI it read
`kv_anchors`; for ROW_PER_PLI the equivalent (`header_labels`) did not exist,
so the agent received no identity labels and produced an empty `CanonicalNameMap`.
`apply_plan` consequently emitted PLIs with no fields populated. `extraction_confidence`
was always 0.0 because no per-field confidence was ever written.

## Decision

Extend `SheetPlan` symmetrically across the three pli_modes. New fields, all
defaulted (additive, no breaking change):

- `HeaderLabel` type; `SheetPlan.header_labels: list[HeaderLabel]` populated for
  ROW_PER_PLI from `_collect_header_labels`.
- `StageColumn` (resurrected from artifacts.py); `StageBandSpec.stage_columns:
  list[StageColumn]` carries primary_col + sub_columns per stage for
  wide_sub_columns layouts. `stage_cols` flat dict is retained as a deprecated
  alias for one release.
- `KVAnchor.confidence: float = 0.95` default.
- `CanonicalNameMap.stage_subfield_labels`, `field_confidence`, `stage_confidence`
  added as optional LLM outputs.

`apply_plan` writes per-field `PLI.confidence`; the reconciler's formula
(`0.7·mean(workflow_per_field_confidence) + 0.3·(1−warn_rate)`) now produces
real numbers instead of always 0.0.

Two new Tier 1 invariants in `validate_plan` enforce mode↔channel exclusivity:
- `exactly_one_identity_channel` — only one of `header_labels`/`kv_anchors`/
  `pli_blocks` may be populated per plan.
- `mode_channel_consistency` — `pli_mode` must match the populated channel.

`FieldNamer._build_user_input` (renamed to `_build_user_input` from
`_collect_header_labels` on the agent side) reads symmetrically across all three
identity channels and includes a small sample of values (k=3 per label) so the
LLM can name unfamiliar labels by inferring from values rather than vocabulary
alone.

Three planner bugs were uncovered and fixed via fixture-driven TDD during
the rollout:
1. `_decide_pli_mode`'s hardcoded `row <= 2` threshold — failed for files with
   headers at row 3+ (DKN, NR).
2. `_classify_single_row`'s HEADER detection scanning all string cells —
   produced false-positive HEADER classification on data rows.
3. `stage_band_detector`'s sub-col acceptance of any string — data cell values
   were mis-classified as sub-column names.

ADR-0003 invariants are preserved: `apply_plan` is zero-LLM, statically
asserted; LLM-as-namer; det planner produces all row arithmetic.

## Consequences

**Easier:**
- All three pli_mode files feed FieldNamer and apply_plan symmetrically.
- Novel supplier vocabulary is supplemented by value-sample inference in the
  FieldNamer prompt, reducing dependency on a maintained vocab list.
- `extraction_confidence` now reflects actual extraction quality instead of
  always emitting 0.0.
- Christian Berg, DKN, and Northern Reflections live regression now pass —
  proving the architectural fix across three different layout families.

**Harder / constrained:**
- `stage_cols` flat dict remains as a deprecated alias for one release; to
  delete after Phase 1 stabilises in production.
- `_find_sub_header_row` carries an explicit `# allow-long` marker for its
  dual-probe sub-label fallthrough — one nameable concept but exceeds the 40-line
  function length limit.

**What we gave up:**
- The `stage_cols` flat representation; transitional alias period only.

**Known deferred items:**
- FA26 (Family 5, TOTAL-footers): mode misclassified as SECTION_PER_PLI when
  ROW_PER_PLI is correct. Currently `xfail` in the live regression suite. Fix
  belongs to a follow-up that addresses planner mode-decision for tabular files
  with TOTAL footers — related to the MOP Compass Pro "1 PLI" misclassification
  deferred in ADR-0003.

## Alternatives considered

- **LabelScout agent** (LLM-pull with new tools) — rejected for Phase 1: would
  double LLM cost per sheet for a fix that is mostly a missing artifact slot.
  Retained as a Phase 4 escape hatch if novel-layout vocab continues to drift
  beyond what value-sample inference can cover.
- **Per-family classifier** — rejected; violates ADR-0001 routing principle.
  Routing on supplier identity instead of structural signals would require a
  new branch per new supplier.

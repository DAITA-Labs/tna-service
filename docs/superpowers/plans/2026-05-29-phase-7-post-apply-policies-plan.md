# Phase 7 — Migrate Tier 5 Validators to Post-Apply Policies

> **Scaffold plan.** Full bite-sized steps land after Phase 6 merges.

**Goal:** Repurpose every Tier 5 validator (`CardinalityValidator`, `DateTrioValidator`, `StageStructureValidator`, `RowAlignmentValidator`, `StageWinsValidator`, `QuantityDtypeValidator`) into post-apply policies that score / eliminate PLIs (or attach `ValidationWarning`s) after `CanvasApplier` produces them.

**Architecture:** A `PostApplyPolicyApplier` runs over `list[PLI]`. Each former validator becomes one or more policies; an "eliminate" verdict drops the PLI, a `score_delta` adjusts confidence, and the `message` becomes a `ValidationWarning`.

**Spec sections:** §3 layer 7 (Post-apply), §9 layer 7 picker list.

**Depends on:** Phase 6 merged.

---

## File map

**Create:**
- `app/components/post_apply/policy_applier.py` — `PostApplyPolicyApplier` component
- `app/policies/post_apply/` — one file per former validator (`cardinality.py`, `date_trio.py`, `stage_structure.py`, `row_alignment.py`, `stage_wins.py`, `quantity_dtype.py`)

**Retire (after parity):**
- `app/components/validators/cardinality.py`
- `app/components/validators/date_trio.py`
- `app/components/validators/stage_structure.py`
- `app/components/validators/row_alignment.py`
- `app/components/validators/stage_wins.py`
- `app/components/validators/quantity_dtype.py`
- `app/components/validators/canvas_warning_aggregator.py` (replaced by policy applier's warning emission)
- `app/pipelines/canvas_validators.py` (folds into the post-apply pipeline)

**Modify:**
- `app/pipelines/extract_canvas_v2.py` — wire `PostApplyPolicyApplier` after `CanvasApplier`

---

## Task outline

1. **`PostApplyPolicyApplier` component** — takes `list[PLI]` + policy list, returns `(list[PLI], list[ValidationWarning])`.
2. **One policy migration per task** — start with cardinality (smallest), end with date-trio (largest).
3. **Parity check per policy** — same warnings emitted on the same fixtures.
4. **Delete validators** after every migration green.

---

## Validation

- Same warnings emitted for every labelled family.
- No warning regression on the canvas eval.
- `extract_canvas_v2` `ExtractionResult.warnings` matches legacy on all fixtures.

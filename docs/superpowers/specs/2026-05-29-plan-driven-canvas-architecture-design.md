# Plan-Driven Canvas Architecture — Design

**Status:** Draft v1
**Date:** 2026-05-29
**Branch:** `canvas-plan-arch` (new — runs alongside `canvas-architecture`)
**Builds on:** ADR-0008 (canvas substrate), ADR-0009 (judges)
**Supersedes:** none — coexists with the current canvas path until parity is reached

---

## 1. Why this design

The current canvas-architecture path (`canvas-architecture` branch, Tiers 0-6) built rich measurement (canvas channels, structural records, LayoutHint), per-canonical extractors, validators, and LLM judges. It works — but every "smart decision" lives inside ad-hoc procedural code: each extractor reimplements column scoring, each validator re-encodes one invariant, and PLI identity gets reconstructed post-hoc by the reconciler. There is no central artifact that says **"here is how to extract PLIs from this sheet"**.

The intent — going back to the original `apply_plan` pattern — was that we'd combine specs, structural information, and per-field properties to **finalize one reliable plan**, then **apply it** in one deterministic pass. That plan is what's missing today.

We're not throwing the existing work away. The tools, structure resolvers, workbook routing, LLM-call infrastructure, and field knowledge all stay. What changes is **the shape of every decision-making step** and **the central artifact**.

## 2. Core principles

1. **One central artifact: the `CanvasPlan`.** Every decision (where the io_number column is, which rows are PLIs, which date strip is a stage band, which kv-block is metadata) ends up encoded in the plan. The plan is what gets applied.

2. **Every decision is a picker.** Wherever there's a choice among candidates, the code follows one uniform shape: generate candidates → run policies → score/eliminate → emit winner(s). This applies to header-row detection, axis inference, anchor-sheet picking, column scoring, everything.

3. **Policies are plain functions.** No decorator. No registry. No protocol class. A policy is `name_policy(...) -> PolicyVerdict` — pure, testable, importable. Each policy reads the inputs it needs; signatures differ.

4. **LLM judges review the plan, not the sheet.** The plan is compact (a few hundred lines for any sheet, however large). Judges receive the plan + policy verdict trail and decide whether the assembled plan is sound. They never see the raw 1000-row × 30-column sheet — only the structured plan derived from it.

5. **Apply is deterministic.** Once the plan is finalized, `CanvasApplier` walks it row-by-row and reads cells per the plan's instructions. No LLM. No retries. No discoveries.

6. **Three patterns, not one.** Sensors observe (Tier 1 strip detectors, profiler — unchanged). Pickers decide using policies (the new uniform layer — most of Tiers 2-5). Synthesis/apply combines deterministically (LayoutComposer, plan assembler, applier).

7. **Policies refine during iteration.** The initial policy list per picker (§9) is a starting point. We will add, drop, and re-weight policies as real workbooks expose new failure modes. The architecture admits this without restructuring.

## 3. The layered architecture

```
LAYER 1 — STRUCTURE (sensors + picker-driven resolvers)
  Tier 1 sensors observe the canvas; output typed records.
  Tier 2 pickers consume records, decide structural questions:
    header band? data rows? stage arenas? axes?
  Output: LayoutHint (synthesized by LayoutComposer).

LAYER 2 — WORKBOOK (picker-driven routing)
  Pickers decide: which sheets cluster, which is the anchor, which
  cluster is a pli_cluster.
  Output: list[ClusterAnchorBundle].

LAYER 3 — FIELD LOCATING (picker-driven, per-canonical)
  For each canonical: a picker scores candidate columns using
  field-level policies; the winner becomes a FieldLocation.
  Stage-band picker outputs sub-column layouts.
  Metadata picker outputs unclaimed kv-blocks.

LAYER 4 — PLAN ASSEMBLY (synthesis + picker-driven cross-field)
  Plan-assembler collects all FieldLocations + stage layouts +
  metadata into a DraftCanvasPlan.
  Cross-field picker runs group policies on the draft (trio dates,
  code-over-name priority, etc.) and adjusts scores.

LAYER 5 — PLAN FINALIZATION (LLM judge, optional)
  PlanReviewerJudge consumes the draft plan + the full verdict trail
  and decides: approve, modify (specific field), or escalate.
  If it modifies, the picker that owns that field re-runs with the
  judge's hint as additional context.
  Output: CanvasPlan (final).

LAYER 6 — APPLY (deterministic)
  CanvasApplier(plan, canvas) → list[PLI].
  One loop. No LLM. No policies. Reads cells per plan; emits PLIs.

LAYER 7 — POST-APPLY VALIDATION
  Pickers run PLI-level policies on the assembled output.
  Verdicts roll up into the per-PLI / per-field confidence.
  Mandatory violations escalate to per-PLI judges (Tier 6 today).

LAYER 8 — RECONCILIATION
  Per-bundle ExtractionResults merge into one. Service-layer responsibility.
  No new components needed; existing extract_canvas service is structurally fine.
```

## 4. Core types

```python
# app/policies/_base.py
@dataclass(frozen=True)
class PolicyVerdict:
    """One policy's vote on one candidate."""
    name:        str
    candidate:   Any                 # column / row / kv_block / canonical / row+col tuple
    score_delta: float               # positive boosts, negative penalizes
    eliminate:   bool                # True → this candidate is disqualified
    message:    str                  # debug + audit trail
```

`PolicyVerdict` is the universal return type. Whatever a policy looks at, this is what it produces.

```python
# app/artifacts/plan.py
@dataclass(frozen=True)
class FieldLocation:
    """Where one canonical's value lives in the bundle."""
    canonical:   str
    mode:        Literal["column", "kv_block", "missing"]
    column:      int | None = None        # set when mode == "column"
    kv_block:    KvBlock | None = None    # set when mode == "kv_block"
    score:       float = 0.0              # aggregate from policies
    verdicts:    list[PolicyVerdict] = field(default_factory=list)


@dataclass(frozen=True)
class StageBandPlan:
    """One stage band, with its sub-column mapping."""
    name:           str                       # supplier text verbatim
    canonical:      str | None                # set if matched to STAGE_SPECS
    column_range:   tuple[int, int]
    subfield_cols:  dict[str, int]            # "planned_date" → col, "actual_date" → col, ...
    score:          float = 0.0
    verdicts:       list[PolicyVerdict] = field(default_factory=list)


@dataclass(frozen=True)
class CanvasPlan:
    """The complete, deterministic recipe for extracting PLIs from one bundle."""
    cluster_id:         str
    anchor_sheet_name:  str
    pli_axis:           Literal["vertical", "sectional", "sheet"]

    # WHERE PLIs iterate
    pli_rows:           list[int]                       # for vertical/sectional
    section_boundaries: list[SectionBoundary]           # for SECTION_PER_PLI

    # WHERE each PLI field lives
    field_locations:    dict[str, FieldLocation]        # one entry per canonical attempted

    # WHERE stages live
    stage_bands:        list[StageBandPlan]

    # WHERE metadata lives (unclaimed kv blocks)
    metadata_blocks:    list[KvBlock]

    # Audit trail
    all_verdicts:       list[PolicyVerdict] = field(default_factory=list)
    confidence:         float = 0.0


@dataclass(frozen=True)
class PliKey:
    """Identity tuple — all 7 fields participate in equality."""
    io_number:     str | None
    style_code:    str | None
    color_code:    str | None
    fabric_code:   str | None
    ex_fty_date:   date | None
    shipment_date: date | None
    delivery_date: date | None
```

## 5. The picker template

Every picker — structural, workbook, field, post-apply — wears the same shape. The picker is a thin Haystack `@component` that owns its policy list as data and runs the candidate loop:

```python
# app/components/pickers/_base.py
@component
class Picker(Component):
    """Generic picker: candidates × policies → survivors → winner.

    Concrete pickers subclass and supply:
      • a `_candidates(...)` method that produces the list of candidates
      • a `_policies` list (plain functions)
      • signature-specific run wrapper that calls the right inputs
    """
    _policies: list[Callable[..., PolicyVerdict]]

    def _score_candidates(
        self, candidates: list[Any], policy_args: dict[Any, dict],
    ) -> tuple[Any | None, dict[Any, float], list[PolicyVerdict]]:
        scores: dict[Any, float] = {c: 0.0 for c in candidates}
        eliminated: set[Any] = set()
        verdicts: list[PolicyVerdict] = []
        for c in candidates:
            for policy_fn in self._policies:
                verdict = policy_fn(**policy_args[c])
                verdicts.append(verdict)
                if verdict.eliminate:
                    eliminated.add(c)
                scores[c] += verdict.score_delta
        survivors = [c for c in candidates if c not in eliminated]
        winner = max(survivors, key=lambda c: scores[c]) if survivors else None
        return winner, scores, verdicts
```

Subclasses are short:

```python
@component
class QuantityColumnPicker(Picker):
    _policies = [
        quantity_int_float_policy,
        quantity_not_merged_policy,
        quantity_value_in_range_policy,
        quantity_header_alias_match_policy,
    ]

    @component.output_types(location=FieldLocation, verdicts=list[PolicyVerdict])
    def run(self, bundle: ClusterAnchorBundle) -> dict:
        pli_rows = _pli_rows(bundle.hint)
        candidates = bundle.hint.candidate_columns.get("quantity", [])
        args = {col: dict(column=col, canvas=bundle.canvas,
                          bag=bundle.bag, pli_rows=pli_rows,
                          header_row=bundle.hint.header_band.rect.r0)
                for col in candidates}
        winner, scores, verdicts = self._score_candidates(candidates, args)
        return {
            "location": FieldLocation(
                canonical="quantity",
                mode="column" if winner else "missing",
                column=winner, score=scores.get(winner, 0.0), verdicts=verdicts,
            ),
            "verdicts": verdicts,
        }
```

The unified loop is one place; per-picker variability is its policy list + how it wires policy args.

## 6. The `CanvasApplier` (deterministic walk)

After the plan is finalized, the applier walks it once:

```python
def apply_canvas_plan(plan: CanvasPlan, canvas: GridCanvas) -> list[PLI]:
    plis = []
    for row in plan.pli_rows:
        # Read each canonical's value at this row, per the plan
        flat_fields = _read_flat_fields(plan.field_locations, canvas, row)
        # Walk each stage band, read planned_date / actual_date / status / remarks
        stages = _read_stages(plan.stage_bands, canvas, row)
        # Attach metadata (scope-aware)
        metadata = _read_metadata(plan.metadata_blocks, canvas, plan.cluster_id, row)
        plis.append(_assemble_pli(row, flat_fields, stages, metadata, canvas))
    return plis
```

- One iteration loop. Merged-cell values flow naturally because the canvas's `cell_values` already carries merge-expanded values, and the plan tells us which column to read at each row.
- PLI identity is the iteration plus the `PliKey` derivation — if two rows share the same `PliKey`, they collapse into one `PLI` with combined stages and metadata.
- No policies. No LLM. No retries. The applier never decides; it executes.

## 7. The `PolicyApplier` component (a.k.a. the picker)

The component template in §5 is the policy applier. There is one `PolicyApplier` per decision point, configured by its `_policies` list. The codebase ends up with one base class and ~20 thin subclasses.

For phase-level work (cross-canonical / cross-finding), the same base class is parameterized with an input shape that takes the whole draft plan instead of one canonical's candidates:

```python
@component
class PlanCrossFieldPicker(Picker):
    """Cross-canonical adjuster: runs group policies on a draft plan,
    adjusts per-canonical scores in place."""
    _policies = [
        trio_date_at_least_one_located_policy,
        code_over_name_priority_policy,
        cross_canonical_column_collision_policy,
    ]
    # custom run that operates on a DraftCanvasPlan, not on candidates
```

The base class abstraction stops at "candidate loop"; phase-level pickers add their own thin `run` instead of inheriting the candidate loop.

## 8. Confidence model

Each picker emits a winner (one finding / one band / one canonical pick) AND its full verdict trail. The verdict trail aggregates into structured confidence:

- **Per-candidate score** = sum of `score_delta` from all policies on that candidate
- **Field location confidence** = `sigmoid(winner_score)` clamped to `[0, 1]`
- **Plan-level confidence** = mean of field confidences, weighted by `mandatory` flag
- **PLI confidence dict** = inherited from plan + adjusted by post-apply policies

All verdicts ride along on the `CanvasPlan.all_verdicts` field for downstream audit and for the LLM judge.

## 9. Pickers — full enumeration

This is the initial picker + policy inventory. Each policy is a starting point; we'll add/refine as real workbooks expose failure modes (per principle 7 in §2).

### Layer 1 (Structure)

**`HeaderBandPicker`** — picks the row(s) that constitute the header band.
- Candidates: top N rows
- `header_band_no_numeric_dtype_policy` — eliminate rows with >30% int/date dtype
- `header_band_no_date_dtype_policy` — eliminate rows with >30% date dtype
- `header_band_text_dense_policy` — boost rows where most non-blank cells are str
- `header_band_bold_or_filled_policy` — boost rows overlapping bold_strips / color_strips
- `header_band_label_alias_match_policy` — boost rows containing known field aliases

**`DataRowsPicker`** — picks which rows are PLI data rows.
- Candidates: rows between header_band.r1 + 1 and canvas.n_rows
- `data_row_not_totals_policy` — eliminate "TOTAL" / "GRAND TOTAL" / "SUM" rows
- `data_row_not_blank_policy` — eliminate fully blank rows
- `data_row_dtype_consistent_policy` — boost rows whose dtype pattern matches surrounding rows

**`StageArenaPicker`** — picks which date strips qualify as stage arenas.
- Candidates: `bag.date_strips`
- `stage_arena_has_plan_marker_nearby_policy` — boost strips with PlanMarkerCluster within ±3 cells
- `stage_arena_inside_bordered_box_policy` — boost strips wholly inside a `BorderedBox`
- `stage_arena_min_length_policy` — eliminate strips with <3 cells

**`StageBandPicker`** — picks the name cell for each arena.
- Candidates: cells above each arena (closest merge anchor + non-merged fallbacks)
- `stage_band_merged_anchor_preferred_policy` — boost merge anchors
- `stage_band_closest_above_policy` — boost cells closer to the arena
- `stage_band_text_dense_policy` — boost cells with non-blank str content

**`SubfieldClusterPicker`** — picks sub-column labels for each band.
- Candidates: cells in the row above each band's arena
- `subfield_alias_match_policy` — match against `SUBFIELD_SPECS.aliases` (Plan/Actual/Status/Remarks)
- `subfield_text_dense_policy` — boost non-blank str cells

**`SectionBoundaryPicker`** — picks repeating-header section breaks (for SECTION_PER_PLI).
- Candidates: `bag.repeating_groups`
- `section_boundary_complete_repeat_policy` — boost full-row repeats over partial
- `section_boundary_min_section_size_policy` — eliminate boundaries <2 rows apart

**`PliAxisPicker`** — picks `pli_axis` for the sheet.
- Candidates: `["vertical", "sectional", "sheet"]`
- `pli_axis_vertical_evidence_policy` — boost if tabular DataRowRange exists
- `pli_axis_sectional_evidence_policy` — boost if SectionBoundaries exist
- `pli_axis_sheet_evidence_policy` — boost if KvBlocks dominate and no tabular range

(`StageAxisPicker` and `SubfieldAxisPicker` follow the same shape.)

### Layer 2 (Workbook)

**`ClustererPicker`** — groups sheets by signature similarity.
- Candidates: pairs of sheet signatures
- `signature_similarity_policy` — threshold on signature distance
- `signature_dimension_weight_policy` — weight individual signature dimensions

**`AnchorPicker`** — picks anchor sheet per cluster.
- Candidates: sheets in the cluster
- `anchor_most_complete_policy` — boost sheets with the largest data_row_range
- `anchor_highest_pli_density_policy` — boost sheets with the densest tabular content

**`RoleClassifierPicker`** — classifies each cluster as pli_cluster vs other.
- Candidates: `["pli_cluster", "metadata_only", "summary", "other"]`
- `role_pli_signal_policy` — boost pli_cluster if PLI candidates detected
- `role_metadata_only_policy` — boost metadata_only if only kv_blocks found

### Layer 3 (Field locating)

**`IdentifierColumnPicker`** — parameterized by canonical, used for all 11.
- Candidates: `bundle.hint.candidate_columns[canonical]`
- Per-canonical policy list (defined in `app/policies/<canonical>.py`):

  **io_number:**
  - `io_number_present_on_all_pli_rows_policy` — boost columns with high row coverage
  - `io_number_can_be_duplicate_policy` — informational, no penalty
  - `io_number_header_alias_match_policy` — boost on IO NO / JOB NO / BUYER PO
  - `io_number_same_length_strip_policy` — boost columns overlapping SameLengthStrip

  **quantity:**
  - `quantity_int_float_policy` — eliminate if <30% numeric
  - `quantity_not_merged_policy` — penalize columns in vertical merges
  - `quantity_value_in_range_policy` — boost if numerics cluster in [1, 100k]
  - `quantity_header_alias_match_policy` — boost on QTY / QUANTITY / PCS

  **style_code:**
  - `style_code_same_length_policy` — boost columns overlapping SameLengthStrip
  - `style_code_header_alias_match_policy` — boost on STYLE / STYLE CODE / DESIGN
  - `style_code_dtype_str_policy` — boost columns with str-dense content

  **style_name:**
  - `style_name_long_text_policy` — boost columns overlapping LongTextStrip
  - `style_name_header_alias_match_policy` — boost on STYLE NAME / DESCRIPTION

  **color_code:**
  - `color_code_short_code_policy` — boost columns with short str values (≤4 chars)
  - `color_code_header_alias_match_policy` — boost on COLOR / COLOR CODE

  **color_name:**
  - `color_name_long_text_policy`
  - `color_name_header_alias_match_policy`

  **fabric_code:**
  - `fabric_code_same_length_policy`
  - `fabric_code_header_alias_match_policy`

  **fabric_name:**
  - `fabric_name_long_text_policy`
  - `fabric_name_header_alias_match_policy`

  **delivery_date / shipment_date / ex_fty_date:**
  - `date_dtype_policy` — eliminate columns with <50% date dtype
  - `date_header_alias_match_policy` — match per-canonical aliases
  - `date_not_inside_stage_arena_policy` — eliminate columns inside StageArenas

**`StageColumnsPicker`** — fills in the sub-column mapping per stage band.
- Candidates: columns in the band's arena range
- `stage_subfield_alias_match_policy` — match against SUBFIELD_SPECS aliases
- `stage_subfield_dtype_match_policy` — match planned_date column dtype = date, etc.

**`MetadataKvPicker`** — picks which KvBlocks are metadata (not claimed by identifiers).
- Candidates: `bag.kv_blocks`
- `metadata_not_claimed_policy` — eliminate kv blocks whose value cells were claimed by IdentifierColumnPicker output
- `metadata_alias_match_policy` — informational, attempts canonical assignment

### Layer 4 (Plan assembly cross-field)

**`PlanCrossFieldPicker`** — adjusts per-canonical scores after individual picks.
- Operates on the draft plan (not on candidates)
- `trio_date_at_least_one_located_policy` — penalize draft if none of the three date canonicals located
- `code_over_name_priority_policy` — demote name location when code is also located (for style/color/fabric)
- `cross_canonical_column_collision_policy` — when two canonicals picked the same column, demote the lower-scoring one
- `mandatory_canonical_located_policy` — penalize draft if io_number / quantity not located

### Layer 5 (Plan finalization)

LLM judge — see §10. No picker here; the judge consumes the draft plan + verdict trail.

### Layer 7 (Post-apply)

**`PostApplyPolicyApplier`** — runs policies on the assembled PLI list.
- Not a picker (no candidates) — a pure applier that emits verdicts for downstream judges
- Field-level policies: `quantity_mandatory_policy(plis)`, `io_number_mandatory_policy(plis)`
- Cross-field policies: `trio_date_at_least_one_present_policy(plis)`, `chronological_date_order_policy(plis)`
- Distribution policies: `io_number_consistency_across_plis_policy(plis)` (informational)

## 10. LLM judge integration — judges review the plan, with bounded sheet access

The judge gets a **compact default context**: the plan (a few hundred lines of structured data) + the policy verdict trail (a few dozen entries). That's enough to read the planner's decisions, but a judge can't responsibly evaluate plan correctness without ever seeing the underlying data. So the judge ALSO gets **tools to peek at the sheet and at structural info** — with hard limits per call.

### Judge tool set

Each judge agent receives a tool bundle, registered in `TOOL_REGISTRY` and exposed via the existing `@tool` decorator pattern. Per-call limits enforced by the tool implementation:

| Tool | What it returns | Per-call limit |
|---|---|---|
| `peek_range(sheet, r0, c0, r1, c1)` | Raw cell values in a rectangle | max 20 rows × 10 cols (200 cells) per call |
| `get_column_profile(sheet, col)` | `ColDtypeProfile` — dtype counts down the column | cheap, no rate limit |
| `get_row_profile(sheet, row)` | `RowDtypeProfile` — dtype counts across the row | cheap, no rate limit |
| `get_strips_at(strip_type, col_or_row)` | Pre-computed strips (`DateStrip`, `IntStrip`, `SameLengthStrip`, `ColorStrip`, etc.) intersecting the location | pre-computed, no rate limit |
| `get_merge_spans_in(r0, c0, r1, c1)` | `MergeSpan` records overlapping the rectangle | pre-computed, no rate limit |
| `get_kv_blocks_near(coord)` | KvBlocks within a small window of `coord` | pre-computed, no rate limit |

Per-judge-call upper bound on tool use: **max 5 `peek_range` calls + unlimited structural lookups**. Structural lookups are cheap because they read pre-computed records, not raw cells. The peek limit caps the total fresh-cell exposure at ~1000 cells per judge invocation — small even against 1000+ row sheets.

### What the judge does

The judge's contract:

1. **Receives** the plan + verdict trail.
2. **Optionally calls tools** to gather evidence — peek at suspicious columns, fetch dtype profiles, inspect strips around flagged locations.
3. **Returns** one of:
   - `approve` — the plan looks sound; finalize as-is
   - `modify(field, new_location, evidence)` — a specific field's location is wrong; the relevant picker re-runs with the judge's hint
   - `escalate(reason)` — the plan has issues the judge can't resolve; flag for human review (high-severity warning in `ExtractionResult.warnings`)

The `evidence` field on `modify` cites which tool calls / observations led to the decision, so the rerun picker has grounded context.

### Token economics

| Source | Typical size |
|---|---|
| Plan | ~200 lines |
| Verdict trail | ~30-50 verdicts |
| Default context (plan + verdicts) | ~1500 tokens |
| One `peek_range` call result | ~150-300 tokens |
| One structural-lookup result | ~50-100 tokens |
| Judge prompt + responses (worst case, 5 peeks + a few lookups) | ~5000-7000 tokens |
| Judge prompt (typical case, 1-2 peeks) | ~2000-3000 tokens |

The architectural payoff of the plan-driven shape: **LLM cost is bounded by plan + bounded tool budget, not by sheet size**. A 1000-row sheet and a 50-row sheet have nearly the same judge cost.

### What the judge sees vs what it doesn't

- ✅ Plan, verdict trail (always)
- ✅ Peek of cell ranges it explicitly requests (bounded)
- ✅ Structural records (dtype profiles, strips, merges, kv blocks) on demand
- ❌ The full sheet contents
- ❌ Arbitrary cross-sheet correlations (judges are per-bundle)

### Reshaping the existing Tier 6 judges

Existing per-finding / phase judges (PR #80-#83) get reshaped into this single plan-reviewer model. The judge agent class becomes `CanvasPlanReviewer`; the gate component is `CanvasPlanReviewerGate`. Verdicts apply at the plan level, not per finding.

Post-apply judges (escalations from Layer 7 policies) remain useful for the cases where the apply step produces suspicious PLIs (e.g., out-of-range quantity values that survived planning). These are per-PLI judges; same tool set + per-PLI scope.

## 11. Migration plan — fresh branch, parallel work

The existing canvas-architecture branch keeps working. Tiers 0-6 stay merged. We create a new branch:

```
canvas-architecture (current main)
  ├── /extract     — legacy planner path (untouched)
  └── /extract_canvas — current per-canonical-extractor chain (Tiers 4-6)

canvas-plan-arch (new branch off canvas-architecture)
  └── /extract_canvas_v2 — new plan-driven chain (this design)
```

Phasing:

1. **Branch from canvas-architecture, add the new shape alongside**. Most of Tier 1 (sensors) is reused unchanged. The canvas, LayoutHint, and structural records are all reusable substrate.

2. **Build the picker base + first picker (HeaderBandPicker)**. Validate the shape end-to-end on one structural decision.

3. **Migrate Tier 2 structural resolvers to pickers**, one at a time. Each migration: extract candidate generation → write policies → swap the resolver out. Existing structure-phase tests adapt.

4. **Migrate Tier 3 workbook routing similarly**.

5. **Build IdentifierColumnPicker + its 11-canonical policy list**. Retire Tier 4 extractors. Build StagesPicker + MetadataKvPicker.

6. **Build PlanAssembler + PlanCrossFieldPicker + the CanvasPlan artifact + CanvasApplier**. Wire /extract_canvas_v2 end-to-end.

7. **Migrate Tier 5 validators to post-apply policies**. Wire PostApplyPolicyApplier.

8. **Build CanvasPlanReviewer judge** + retire the per-finding / phase judge gates (PR #80-#83).

9. **Run canvas eval on /extract_canvas_v2 vs /extract_canvas**. When v2 matches or beats v1, switch the canonical /extract_canvas endpoint to the new chain; deprecate v1.

10. **Cleanup PR**: remove the old per-canonical extractors, the per-finding judges, the row-grain reconciler. Update ADR-0008 / ADR-0009 with the new architecture as the canonical canvas-arch.

Throughout, the policy lists in §9 are starting points. Adding a policy = a new function + one line in the picker. Removing one = delete the import + line.

## 12. Out of scope

- The legacy `/extract` path stays untouched. No coupling to this design.
- Open-vocab metadata stays open — no attempt to force novel labels into a canonical taxonomy beyond the existing METADATA_SPECS hints.
- Multi-cluster reconciliation (when a workbook has multiple clusters that share an io_number across them) is per-cluster as today; the service layer merges. No cross-cluster identity matching.
- Eval harness rewrite — `evals/runner.py` still scores against labels regardless of which `/extract*` endpoint produced the output. No changes expected to evals/.
- Tools (`app/tools/canvas/*`) stay as-is. Sensors are not in scope for restructuring.

## 13. Open questions to refine during implementation

These are deliberately left fuzzy. We'll converge as the build proceeds.

1. **Exact policy weighting.** The `score_delta` magnitudes in §9 (boost +0.15, penalize -0.30, etc.) are placeholders. Calibrate by running each picker on the dataset and tuning until the top survivor is correct on ≥80% of cases.

2. **When does a picker invoke a judge vs accept its best survivor?** Threshold: invoke the judge when (a) `winner_score < some_floor`, OR (b) `score(winner) - score(runner_up) < some_margin`. Both numbers calibrated during implementation.

3. **Cross-field picker ordering.** Does `code_over_name_priority` run before or after `cross_canonical_column_collision`? Both adjust scores; order can matter. Try one ordering, evaluate, swap if needed.

4. **Stage subfield aliases.** SUBFIELD_SPECS lists a small set today (Plan/Actual/Status/Remarks/Date). Real sheets carry many more (Sample, Approved, Received, etc.). Catalog growth is iterative.

5. **Metadata GROUP scope.** When does a MetadataEntry get `scope=GROUP` vs `scope=PLI`? Today's metadata extractor doesn't emit GROUP at all. The picker version may surface this gap.

6. **Plan reviewer prompt patterns.** What format works best for the judge? JSON-rendered plan, markdown bullet list, ASCII grid of field locations? Try and iterate; capture in ADR-0009 update.

7. **Backward compatibility of `ExtractionResult`.** The new chain might want richer per-field provenance (which policies fired, which judge intervened). Either extend the public PLI schema or add an opt-in `extras` field. Decide when we have real consumers.

8. **Judge tool limits.** §10 proposes `peek_range` max 20×10 cells per call, max 5 peeks per judge invocation. These are placeholders. Measure actual judge token usage on the dataset and tune — could go tighter (cost discipline) or looser (better evidence quality). The tool implementation enforces whatever number we settle on.

9. **Judge tool prompt design.** How does the judge LEARN to use the tools effectively? Few-shot examples in the SHARED prompt block? Per-tool description strings in the tool registry? Trial-and-error during real judge calls and capture the patterns in ADR-0009 update.

10. **What triggers a judge call.** Not every plan needs a judge review. Candidate triggers: (a) any mandatory policy verdict failed; (b) any picker emitted `winner_score < threshold`; (c) any pair of candidates had `score_delta < margin`. Calibrate which conditions actually warrant the LLM cost — too aggressive and we pay for trivial reviews; too lax and we miss the catches.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Policy weighting takes longer than expected to tune | Phase 9 (eval comparison) builds in iteration time; we won't ship v2 until eval matches v1 |
| The picker abstraction is too rigid for some structural decisions (e.g., resolvers that need two-stage lookahead) | The base `Picker` class is intentionally thin; subclasses can override `run` entirely when the candidate-loop isn't enough |
| Plan-driven extraction misses workbooks where the legacy planner did fine | Parallel branch keeps the legacy path alive; users can hit /extract on the legacy endpoint indefinitely |
| LLM plan-reviewer hallucinates fixes | Schema-enforced output (`PlanReviewVerdict`); judge's "modify" suggestions trigger a picker re-run with the new context — the picker still decides via its policies |
| Per-canonical policies multiply uncontrollably | One file per canonical caps the surface area; reviewer audits new policy files against the property sheet defined in §9 |

## 15. Definition of done

For this design:
- Layered architecture is canonical (Layers 1-8 from §3 are stable concept-level boundaries).
- `Picker` base class + at least 3 worked subclasses exist on `canvas-plan-arch`.
- `CanvasPlan` artifact is defined and consumed by at least one apply test.
- One end-to-end smoke test passes: an xlsx fixture → CanvasPlan → CanvasApplier → list[PLI].

For the migration (covered by the implementation plan, not this design):
- /extract_canvas_v2 endpoint exists and runs the plan-driven chain.
- Canvas eval shows v2 ≥ v1 on identifier recall + precision.
- Legacy extractor chain retired.
- ADR-0008 and ADR-0009 updated with the new architecture as canonical.

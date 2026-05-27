# Experiment Journal — 3-Area Pipeline Architecture

Working journal of the design decisions behind the new TNA extraction pipeline. Each entry captures what was considered, what was rejected, what was adopted, and the empirical evidence behind the choice. Append to this file as the work progresses; never overwrite earlier entries.

---

## Progression map (visual)

```
PHASE 0  ─ STARTING POINT
           Monolithic FieldNamer (5 jobs in one LLM call)
           Symptoms: stg_rec=0.180, MOP files extract zero stages,
                     CHRISTIAN BERG extracts "PLAN/ACT" as stage names
           Eval headlined the pain.
              │
              ▼
PHASE 1  ─ FIRST EXPERIMENT (5 strategies × 5 sub-problems)
           strategies_visual_guide.md + per_sheet_subproblems_compare.md
           Outcome: vocab dominates label mapping; sample_value alone is noise.
              │
              ▼
PHASE 2  ─ THREE-AREA DECOMPOSITION
           identifiers / stages / metadata as independent areas
           three_area_decomposition.md
              │
              ▼
PHASE 3  ─ CLOSED vs OPEN VOCABULARY
           Identifiers: CLOSED 9 canonicals; mandatory io_number + quantity
           Stages:      OPEN (any name allowed; STAGE_SPECS = hints only)
           Sub-fields:  CLOSED-ish (small set + raw fallback)
           Metadata:    OPEN (known + raw fallback)
              │
              ▼
PHASE 4  ─ SPEC INFRASTRUCTURE
           experiments/specs/  — single source of truth per field
           Spec drives BOTH matcher AND judge prompt rendering
              │
              ▼
PHASE 5  ─ TWO-TIER JUDGE
           Per-finding judge = RECOMMENDER
           Phase judge       = ARBITER (sees all findings + recommendations)
           Bounded re-extract loop (max 2 iterations)
              │
              ▼
PHASE 6  ─ SHEET PEEK + STACKED BANDS
           Per-judge sheet sample bounded ~200 cells
           Bands → Strip + Band (handles stacked stage layouts)
              │
              ▼
PHASE 7  ─ PLI ENUMERATION + FIELD SCOPE
           PliAxis (ROW/COLUMN/WHOLE_SHEET/SECTION)
           FieldScope (SHEET/GROUP/PLI)
           ReadDirection per locator
           SheetLevelPlan as iteration contract for apply_plan
              │
              ▼
PHASE 8  ─ PROBE P1 — SHAPE TOOLS + CLASSIFICATION
           experiments/p1/
           OUTCOME: 6/6 mode + 6/6 axis correct; 0 judge calls
              │
              ▼
PHASE 9  ─ PROBE P2 — IDENTIFIER EXTRACTION
           experiments/p2/
           OUTCOME: 96.8% value precision; recall gaps from labels-bugs+spec refinements
              │
              ▼
PHASE 9.5 ─ LABELS AUDIT
            experiments/labels_audit.md
            OUTCOME: 4/6 files have label errors; 2/6 clean
            253 correction proposals across 57 PLIs
              │
              ▼
PHASE 9.6 ─ OPEN METADATA SCHEMA
            schemas.MetadataEntry(key, value, source, canonical?, scope)
            Sheet.metadata is list[MetadataEntry] now
            buyer_po_no NOT promoted to identifier (stays in metadata as raw k:v)
              │
              ▼
PHASE 10 ─ LABELS INSPECTION + SELECTIVE EDITS (in progress)
           Per-file review; agree-then-edit; start with DKN
              │
              ▼
PHASE 11 ─ PROBE P3 (UPCOMING) — STAGE EXTRACTION (strip + band, open vocab)
              │
              ▼
PHASE 12 ─ PROBE P4 (UPCOMING) — apply_plan INTEGRATION
              │
              ▼
[FUTURE]  ─ Production wiring into app/  (only after P4 lands clean)
```

---

## Decision log

Each decision below answers: **Context → Considered → Rejected → Adopted → Status → Evidence**.

### D1. Decompose the monolithic FieldNamer

- **Context** — Current FieldNamer does 5 logical jobs in one LLM call: (a) identifier label mapping, (b) metadata label mapping, (c) stage name mapping, (d) sub-field label mapping, (e) confidence reporting. Eval showed stage_recall=0.180; diagnosis traced to FieldNamer's bundled prompt failing on edge cases.
- **Considered**
  - Option A: 3 LLM agents per output channel (FieldLabelMapper / StageNameMapper / StageSubfieldMapper)
  - Option B: 2 LLM + 2 deterministic tools (label-finder LLMs; sub-field matcher + confidence as deterministic tools)
  - Option C: keep monolithic, restructure the prompt
- **Rejected**
  - Option C — still bundles 5 jobs in one call; doesn't fix the diagnostics or cost problem
  - Option A (pure 3-LLM) — costs 3× per sheet; doesn't promote any work to deterministic
- **Adopted** — Option B-shape, generalised: build a deterministic substrate first; LLM only judges (ADR-0003 LLM-as-reviewer principle).
- **Status** — Validated by P1 + P2.
- **Evidence** — strategies_visual_guide.md, per_sheet_subproblems_compare.md.

### D2. Three-area decomposition

- **Context** — Need a clean problem split for the new pipeline.
- **Considered** — Per-`pli_mode` decomposition (ROW/SHEET/SECTION as the top level), or per-extraction-area.
- **Rejected** — Per-pli_mode top-level: bakes the layout assumption in; doesn't generalize for hybrid layouts.
- **Adopted** — Areas = identifiers / stages / metadata. Each is a component (or set) with its own tools and judges. Pli_mode becomes a hint inside the shape data, not a top-level dispatcher.
- **Status** — Validated by P1 + P2 (parametric tools work across all pli_modes).
- **Evidence** — three_area_decomposition.md.

### D3. Closed vs open vocabulary axis

- **Context** — Stage names vary wildly across suppliers. Hard-coding canonicals fails on new TNAs.
- **Considered**
  - Closed set for everything (small, controllable)
  - Open for everything (no canonicalization)
  - Mixed
- **Rejected**
  - Closed-everything — new supplier with `"BULK PACKING"` falls through silently
  - Open-everything — no way to enforce mandatory io_number + quantity
- **Adopted** —
  - **Identifiers: CLOSED** (9 canonicals; io_number + quantity mandatory)
  - **Stages: OPEN** (STAGE_SPECS = advisory hints; novel names ship with `canonical=null`)
  - **Sub-fields: CLOSED-ish** (small set + unknown sub-cols become raw keys in `stage_metadata{}`)
  - **Metadata: OPEN** (known canonicals + raw fallback k:v)
- **Status** — Locked in; reflected in schemas + prompts.
- **Evidence** — stages.py docstring; schemas.FinalStage.canonical=Optional.

### D4. Parametric specs as single source of truth

- **Context** — Multiple tools (matcher, judge prompt, validator) all need per-field knowledge.
- **Considered**
  - Per-tool hardcoded vocab tables
  - JSON config files
  - Dataclass-based specs in code
- **Rejected**
  - Hardcoded vocab — fragmentation; same alias updated in multiple places
  - JSON config — typed wrappers add boilerplate; loses IDE autocomplete
- **Adopted** — `FieldSpec` / `StageSpec` / `SubfieldSpec` Python dataclasses in `experiments/specs/`. Each spec carries `aliases`, `label_match_mode`, `value_dtype`, `value_dtype_mode`, `value_constraints`, `patterns`, `anti_patterns`, `examples`, `mandatory`. **One spec → matcher AND prompt rendering both consume it.**
- **Status** — Built. 9 identifier + 12 stage + 9 sub-field + 6 metadata specs registered.
- **Evidence** — `experiments/specs/`; render.py builds prompts from spec data.

### D5. Tools / Components / Pipelines hierarchy

- **Context** — Need a clean composition story. Was tempted to add a `signals/` package.
- **Considered**
  - signals → tools → components → pipelines (4 layers)
  - tools → components → pipelines (3 layers)
- **Rejected** — Extra `signals` layer was over-abstraction. Tools ARE the signal emitters; components compose them.
- **Adopted** — Strict hierarchy: `pipeline → component → tools` (uses); no reverse imports. Tools are reusable, components do "small meaningful work" running tools in parallel, pipelines orchestrate components.
- **Status** — Reflected in the experimental code structure (`experiments/p1/`, `experiments/p2/`).
- **Evidence** — Verified by P1 + P2: each probe is a small set of files cleanly layered.

### D6. Two-tier judge (recommender + arbiter)

- **Context** — How does the LLM judgment actually CHANGE the plan?
- **Considered**
  - Per-finding judge applies verdict directly (PR-style: yes/no/swap → mutate plan)
  - Phase judge alone (one big call per area)
  - Two-tier
- **Rejected** — Per-finding-only: loses cross-finding context (color_code + color_name on same cell can't be resolved by either judge alone).
- **Adopted** — **Per-finding judges = RECOMMENDERS** (verdict + reason). **Phase judge = ARBITER** (sees all findings + per-finding judgments + shape together; emits final findings or RE_EXTRACT directives). Bounded loop: max 2 iterations; ESCALATE on third.
- **Status** — Designed; prompts written; mock-judge integration is part of P4.
- **Evidence** — prompts.py (FIELD_FINDING_JUDGE_PROMPT, PHASE_IDENTIFIER_JUDGE_PROMPT); schemas (JudgmentRec, PhaseIdentifierJudgeOutput).

### D7. Open-vocab stage names + Strip+Band model

- **Context** — TNAs have arbitrary stage names AND can stack stages vertically (wrap-around layouts).
- **Considered**
  - Closed-vocab stages with vocab-only detection (rejected — see D3)
  - Bands as pure column ranges (single horizontal strip assumption)
  - Bands as 2D rectangles in a Strip
- **Rejected** — Bands as pure column ranges: breaks on stacked layouts (top row has Fab/Sew/Cut; rows below have Pack/Ship/Inspect after a blank-row break).
- **Adopted** — `StageStrip{name_row, sub_label_row, data_row_range, bands}` containing `DetectedBand{name, canonical, column_range, plan_date_col, sub_columns}`. A sheet can have multiple strips. Identifier-based PLI correlation across strips via io_number.
- **Status** — Designed in schemas.py; P3 validates.
- **Evidence** — schemas.py StageStrip + DetectedBand; STAGE_BAND_JUDGE_PROMPT explicitly handles novel-name examples.

### D8. PLI enumeration + Field scope

- **Context** — Real sheets have hybrid scoping: io_number is one cell at the top (shared across 3 PLIs), style_code is per-row, delivery_date may share across a group then differ across the next group.
- **Considered**
  - Stick with pli_mode trichotomy (too coarse; fails hybrid layouts)
  - Per-field scope + axis-aware iteration contract
- **Rejected** — Pli_mode-only: forces uniform structure; breaks for hybrid sheets; can't handle COLUMN-direction PLIs.
- **Adopted** — `PliAxis` (ROW/COLUMN/WHOLE_SHEET/SECTION), `FieldScope` (SHEET/GROUP/PLI), `ReadDirection` (SAME_ROW/SAME_COLUMN/OFFSET/FIXED). Single `apply_plan` loop consults `axis + scope + read_pattern + group` to read each field. `SheetLevelPlan` carries the iteration contract.
- **Status** — Designed; P4 validates apply_plan with this model.
- **Evidence** — enums.py PliAxis/FieldScope/ReadDirection; schemas.py PliEnumerationPlan / FieldLocator / SheetLevelPlan; verified end-to-end on hybrid example in the smoke test.

### D9. Sheet peek for judges

- **Context** — Judges need some sheet visibility but full-sheet sample is expensive.
- **Considered**
  - No peek (judges work on metadata only)
  - Full sheet
  - Bounded window per judge
- **Rejected** — No peek (judge can't catch contextual errors). Full sheet (cost blow-up).
- **Adopted** — Per-judge bounded slice (~200 cells max). Per-judge strategy:
  - FieldFinding: 3×8 window around the label cell
  - StageBand: strip's name_row + sub_label_row + 3 data rows × band cols ±2
  - MetadataKV: 3×5 window around kv cell
  - Classification: 20×12 whole-sheet shape view
  - Phase judges: NO raw sheet sample (aggregated context instead)
- **Status** — SheetSample model + renderer built. Wired into FieldFindingJudgeInput + StageBandJudgeInput.
- **Evidence** — schemas.SheetSample; render._render_sheet_sample.

### D10. Probe P1 — shape tools + classification

- **Context** — Validate the shape-inspection + multi-vote classification design empirically.
- **Considered** — One agent vs many smaller probes.
- **Rejected** — Single-agent monolithic probe (too much for one agent).
- **Adopted** — 4 small probes; P1 validates classification only.
- **Status** — COMPLETED. 6/6 mode + 6/6 axis correct.
- **Evidence** — experiments/p1_shape_classification.md.

### D11. Probe P2 — identifier extraction

- **Context** — Validate parametric find_field_locations + scope detection.
- **Considered** — Per-field tool vs parametric workhorse.
- **Rejected** — Per-field tools (9 separate functions → duplication).
- **Adopted** — Single `find_field_locations(sheet, shape, spec)` driven by FieldSpec.
- **Status** — COMPLETED. 96.8% precision; recall gaps surfaced.
- **Evidence** — experiments/p2_identifier_extraction.md.

### D12. Labels audit — ground-truth validation

- **Context** — P2's "low recall" numbers smelled systemic. We audited the dataset/extracted/*.json labels against the source xlsx files.
- **Considered** — Trust labels as-is; partial fix; full audit.
- **Rejected** — Trusting as-is (P2 recall numbers were misleading; scoring rewarded extractors that reproduced label conflations).
- **Adopted** — Full audit on 6 files. 4/6 have label errors; 2/6 are clean.
- **Status** — COMPLETED. 253 correction proposals across 57 PLIs.
- **Evidence** — experiments/labels_audit.md + experiments/labels_audit_corrections.json.
- **Key systematic findings** —
  - io_number / buyer_po_no conflation in 3/6 files (DKN, MOPD, GUESS)
  - delivery_date / ex_factory_date conflation in 4/6 files
  - fabric_code holds long composition text in 4/6 files (should be fabric_name)
  - CHRISTIAN BERG stage labels drop END dates + per-stage qty
  - GUESS labels point to wrong column for io_number (real io_number is in column E "ION")

### D13. Open MetadataEntry schema — drop buyer_po_no identifier proposal

- **Context** — Labels audit surfaced "PO No" values labeled as io_number. Initial instinct: add `buyer_po_no` as a 10th identifier canonical. User pushback: `io_number` IS the identifier; if a supplier doesn't have an IO column, io_number is just absent for that file. Anything else useful goes into metadata.
- **Considered**
  - Add `buyer_po_no` as a 10th identifier canonical
  - Keep `metadata` as a fixed dict[canonical → FieldLocator]
  - Open `metadata` to a list of `MetadataEntry(key, value, source, canonical?)`
- **Rejected**
  - 10th identifier canonical — bloats the identifier set; "PO No" is informational but not identifying
  - Fixed-canonical metadata dict — fails on novel labels (Treatment, Country of Origin, etc.)
- **Adopted** —
  - `Sheet.metadata` is now `list[MetadataEntry]` (open schema)
  - `MetadataEntry(key, value, source, canonical?, scope, group_id?, confidence)`
  - `key` is supplier's raw label text verbatim
  - `canonical` is OPTIONAL — set iff matched a known METADATA_SPEC hint
  - `METADATA_SPECS` becomes purely advisory (same role as STAGE_SPECS)
- **Status** — IMPLEMENTED. Schema updated; prompts updated; smoke-test passing.
- **Evidence** — experiments/specs/schemas.py MetadataEntry; metadata.py docstring updated; PHASE_METADATA + METADATA_KV prompts updated.

### D14. Labels editing principle — inspect before touching

- **Context** — After the audit, instinct was to apply corrections programmatically (253 proposals).
- **Considered**
  - Apply all corrections from labels_audit_corrections.json now
  - Inspect file-by-file, agree on what's correct, edit selectively
  - Defer until P3+P4 validate the extractor more fully
- **Rejected** — Mass auto-apply (risk of bad mass-edit; loses continuity with historical eval baseline).
- **Adopted** — Inspect-before-edit. Per-file review; agree on the correct label structure; apply selectively (likely starting with DKN as the simplest case).
- **Status** — PENDING. Inspection step ahead before any label edits.
- **Evidence** — design decision; no code yet.

### D16b. *_code is the PRIMARY slot (clarification on principle 2)

- **Context** — Inspecting DKN clarified what "`*_code > *_name` priority" actually means. Initially I read it as "use value-dtype to decide which spec fits"; that was wrong.
- **Correct interpretation**
  - `*_code` is the PRIMARY slot for the concept (fabric/color/style).
  - `*_name` is the SECONDARY slot, used ONLY when the sheet has BOTH a code-leaning column AND a separately-labelled descriptive column.
  - When a sheet has a SINGLE column for the concept (e.g., DKN's "Fabric Quality" is the only fabric column), the value lands in `*_code` regardless of length or format.
  - A long composition string `"2X2 RIB/100% COTTON/..."` is a valid `fabric_code` value under this rule.
- **Spec impact**
  - `STYLE_CODE_SPEC`, `COLOR_CODE_SPEC`, `FABRIC_CODE_SPEC` — `value_dtype_mode` relaxed from HARD → SOFT; `max_len` and pattern constraints removed; aliases expanded to absorb "name-leaning" variants (e.g., `FABRIC_CODE_SPEC` now includes `fabric quality`, `composition`, `fabric description`).
  - `STYLE_NAME_SPEC`, `COLOR_NAME_SPEC`, `FABRIC_NAME_SPEC` — descriptions rewritten as "SECONDARY slot — only used when both code AND name columns exist"; anti-patterns updated; constraints relaxed.
  - The "two columns present" detection becomes the IdentifierExtractor's job (post-find_field_locations dedupe), not a spec constraint.
- **Status** — IMPLEMENTED at spec layer. Extractor-level "both-columns" detection logic is a P2-revision concern.
- **Evidence** — `experiments/specs/identifiers.py` updated specs; smoke test confirms all six relaxed.

### D16c. Stages require a planned_date — "Fabric Quality Mockup" + "Shipment Samples" are NOT stages

- **Context** — DKN has columns `Fabric Quality Mock up` (AL) and `Shipment samples` (AM) with single sub-column "Approval" (no Planned column). I had initially planned to treat them as stages.
- **Correction (per user)** — Stages REQUIRE a planned_date. Approval-only columns without a planned_date are not stages; they're per-PLI remarks/metadata.
- **Implication** — When extracting stages, the detector should:
  1. Identify candidate stage bands (header row + date-bearing data below)
  2. Within each band, locate a `planned_date` sub-column (PLAN / Planned / Scheduled / etc.)
  3. If no planned_date sub-column is found, the band is NOT a stage — it's per-PLI metadata
  4. Cells that look stage-shaped but lack a planned_date become metadata entries
- **Status** — Documented; implementation pending in P3 stage detector.

### D16. Six hard principles after labels inspection

- **Context** — Inspecting DKN (3 PLIs, ROW_PER_PLI) surfaced multiple labels-vs-spec inconsistencies and clarified the deeper schema requirements. Promoted to project-wide hard principles.
- **The six hard principles**
  1. **One planned_date ⇒ one stage.** "Sewing Start" and "Sewing End" are separate stages with separate planned_date columns; never collapsed. Non-plan sub-columns (actual, received, approved, qty) still fold into the same stage's `stage_metadata` bag.
  2. **`*_code > *_name` priority.** When a single ambiguous label like "Color" / "Fabric" / "Style" appears, the `_code` spec is tried FIRST. `_name` only wins when `_code` doesn't fit (value too long, wrong dtype). Enforced by spec ordering in `IDENTIFIER_SPECS`.
  3. **All non-identifier/non-stage/non-subfield fields go into PER-PLI METADATA.** No exceptions. Buyer/Factory/Season/PriceTreatment/all sheet-level fields appear in each PLI's metadata list. Already started for GUESS (PO entry); broader pickup is pending per-file.
  4. **Three distinct date identifiers** replacing the single `delivery_date`:
     - `delivery_date`   — date goods reach the buyer (ETA, in-store, arrival)
     - `shipment_date`   — date goods are in transit (ship date, dispatch, transport)
     - `ex_fty_date`     — date goods leave the factory (ex-factory, EXF, ETD Ex Factory)
  5. **Stage-wins over identifier** for date cells. If a cell could be either a stage's planned_date OR one of the three date identifiers, the stage band consumes it. Example: an "Ex Factory Shipment" stage column with per-PLI dates is captured by the stage; the PLI's `ex_fty_date` identifier comes from a different sheet-level / PLI-level cell (or stays null).
  6. **MANDATORY: every PLI must have at least ONE of the three date identifiers.** Enforced post-extraction (validator or phase judge). At-least-one rule because every PLI needs a timeline anchor downstream.
- **Implementation**
  - `experiments/specs/identifiers.py` — added `SHIPMENT_DATE_SPEC` and `EX_FTY_DATE_SPEC`; refined `DELIVERY_DATE_SPEC` description and anti-patterns; added `DATE_IDENTIFIERS_AT_LEAST_ONE` tuple. Total identifier canonicals: 9 → **11**.
  - `experiments/specs/metadata.py` — `EX_FACTORY_DATE_SPEC` removed (concept now lives as identifier `ex_fty_date`).
  - `experiments/specs/__init__.py` — exports updated.
  - `experiments/specs/stages.py` — docstring captures "one planned_date ⇒ one stage" principle.
  - `IDENTIFIER_SPECS` ordering: `*_code` precedes `*_name` (priority enforced by cross-spec dedupe taking ties in order).
- **Status** — IMPLEMENTED at the spec layer. Smoke test passes (11 identifier canonicals; 3 date canonicals; mandatory still io_number + quantity; at-least-one applies to dates).
- **Evidence** — `experiments/specs/identifiers.py` (new 2 date specs); D17 will apply to DKN labels.

### D15. `io_number` is a FUNCTIONAL ROLE — PO No / Job No are aliases

- **Context** — Audit revealed 3/6 files use the buyer's PO column as their per-PLI identifier (no separate IO column exists). Initial framing tried to handle this as "metadata + missing io_number". User reframed: io_number is whatever the supplier USES as the per-PLI identifier on this sheet.
- **Considered**
  - Keep io_number narrow ("internal order ID only"); buyer_po_no as separate canonical
  - Drop buyer_po_no from identifier set; mark as metadata
  - Expand io_number aliases to cover PO / Job-No / Buyer-Ref labels (functional-role definition)
- **Rejected**
  - Narrow io_number — gives io_number 4% recall; spec-correct extractor scores as broken even though labels agree the PO column IS the identifier
  - PO as metadata — fails the "every PLI must have an io_number" mandatory requirement when no separate IO column exists
- **Adopted** —
  - `IO_NUMBER_SPEC.aliases` expanded with `"buyer po no"`, `"po no"`, `"po #"`, `"job no"`, `"buyer ref"`, etc. (29 aliases total)
  - Anti-pattern that excluded "PO No" REMOVED. Replaced with priority rule: internal-order aliases come EARLIER in the list and outrank PO aliases — if both columns exist, internal-order wins; otherwise the PO column IS io_number.
  - `BUYER_PO_NO_SPEC` REMOVED from `METADATA_SPECS`. Comment block left at the removed-spec position explaining the reasoning.
  - `IO_NUMBER_SPEC.value_constraints.max_len` bumped 20 → 30 (some PO numbers are longer than the original IO-only assumption).
- **Status** — IMPLEMENTED. Smoke test passes; 29 aliases registered; METADATA_CANONICALS now 5 (was 6).
- **Evidence** — experiments/specs/identifiers.py IO_NUMBER_SPEC; experiments/specs/metadata.py BUYER_PO_NO removal note.
- **Expected impact on P2 re-score** — io_number recall jumps from 4% (1/6 files) to likely 100% (6/6 files). The "io_number conflated with buyer_po_no" labels-bug stops being a bug — it was the right call all along.

---

## Empirical findings — summary so far

### Per-probe top-line

| Probe | Topic | Headline |
|---|---|---|
| Strategy comparison (pre-P1) | 5 sub-problems × strategies | vocab F1 92–100% on label mapping |
| P1 | Shape tools + classification | 6/6 mode + 6/6 axis correct, 0 judge calls |
| P2 | Identifier extraction | 96.8% value precision; per-canonical recall gaps |
| P3 | Stage extraction | (pending) |
| P4 | apply_plan integration | (pending) |

### Per-field precision (from P2 across 6 files)

| canonical | precision | recall (label_present → locator_built) | notes |
|---|---|---|---|
| `io_number` | 100% (7/7) | 1/6 files | labels-file conflates with buyer_po_no in 5 files |
| `quantity` | 89% (16/18) | 5/6 files | GUESS quantity is row-sum of size cols |
| `style_code` | 96% (173/180) | 3/4 files | spec max_len=20 rejects MOPD's 35-char codes |
| `style_name` | 97% (180/186) | 4/4 files | over-detection (6 locators built) |
| `color_code` | 50% (3/6) | 1/4 files | MOPD label/spec disagreement |
| `color_name` | 100% (170/170) | 1/1 file | over-detection (4 locators built) |
| `fabric_code` | N/A (0/0) | 0/4 files | spec needs more aliases |
| `fabric_name` | N/A (0/0) | 0/0 files | labels don't carry this canonical |
| `delivery_date` | 100% (2/2) | 2/6 files | spec anti-pattern excludes "Ex Factory" deliberately |

**Aggregate value precision: 96.8% across 7 canonicals with predictions.**

### Per-stage precision

(pending — emit in P3 report)

### Variant winners (frozen defaults for P3+)

| layer | tool | winning variant |
|---|---|---|
| Shape | `compute_density` | B: `density_by_content` |
| Shape | `find_dense_rectangles` | B: `density_threshold_grid` + band-local col density + close-band merging |
| Shape | `find_blank_runs` | B: `relaxed_blank` (≤1 stray cell) |
| Shape | `find_header_row_candidates` | B: `vocab_match_count` (with A as fallback, C/D as tiebreakers) |
| Identifier | `find_field_locations` label_strategy | `combined_weighted` (spec's `label_match_mode` is the real lever) |
| Identifier | `find_field_locations` dtype_strategy | `strict` default; `soft` as RE_EXTRACT escalation when mandatory missing |
| Identifier | scope detector | `combined` (all 3 variants converge on this corpus) |

### Surfaced signals (added during probes)

| signal | added in | discriminates |
|---|---|---|
| `count_kv_adjacencies` | P1 | SHEET_IS_PLI vs others (63261, Eastman) |
| `repeating_alias` count | P1 | SECTION_PER_PLI vs ROW_PER_PLI when shape looks identical (GUESS) |
| two-pass band-local col-density | P1 | sparse-column tables (DKN) — fixes fragmented rects |
| close-band merging (gap ≤ 5 cols, gap ≤ 1 row) | P1 | bridges internal sparse columns in band detection |

---

## Pending decisions / open threads

1. **Per-sheet precision reporting** — current P2 scoring is per-file; Eastman has 36 sheets aggregated under one file label. Need per-sheet AND per-file granularity in P3+ AND a small augmentation to P2.
2. **Per-stage precision** — first reported in P3.
3. **Workbook-vs-sheet classification orchestration** — Eastman is SECTION_PER_PLI workbook but SHEET_IS_PLI per sheet. P3+/P4 need a two-level decision.
4. **CB vertical-merge iteration** — apply_plan must iterate `data_row_range` from strip, not "rows with id values." P4 design concern.
5. **Spec refinements identified by P2**:
   - `io_number`: add `"job no"` alias
   - `style_code`: bump `max_len` 20 → 40 OR add compound-code pattern
   - `color_code`: handle GUESS's `"CODE"` header (judge or alias addition)
   - `quantity`: GUESS needs derived-value (row sum of size cols) — needs a derived-field mechanism beyond aliases
   - `delivery_date`: deliberate anti-pattern vs labels-file disagreement
6. **Labels-file cleanup** — io_number / buyer_po_no conflation in 5/6 files. Separate from spec work.
7. **ClassificationJudge wire-up** — design says enable as safety net even though P1 didn't fire it. Wire in P4.
8. **Spec refinement loop** — phase judge can emit `SpecRefinementProposal`s; we need a curation process and a way to apply approved proposals back to the spec files.

---

## How to append to this journal

Each new probe / brainstorm / decision becomes:

1. A new entry in the **Progression map** (one box in the chain)
2. A new entry in the **Decision log** with Context / Considered / Rejected / Adopted / Status / Evidence
3. New numbers in the **Empirical findings** section
4. Resolved threads removed from **Pending**; new threads added

Never delete past entries — earlier decisions inform later ones, and the chain of reasoning is part of the value.

---

## Provenance of this journal

Authored alongside the P1 + P2 probe reports. Compiled from:
- `experiments/strategies_visual_guide.md` (pre-P1 strategy comparison)
- `experiments/strategies_by_layout.md` (architectural framework)
- `experiments/per_sheet_subproblems_compare.md` (empirical strategy F1 scores)
- `experiments/three_area_decomposition.md` (3-area design)
- `experiments/p1_shape_classification.md` (P1 results)
- `experiments/p2_identifier_extraction.md` (P2 results)
- The conversation thread of design brainstorms (no separate transcript file)

Last updated after: P2 complete; P3 not yet dispatched.

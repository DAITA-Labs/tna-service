# Canvas Architecture

**Status:** Draft for review
**Date:** 2026-05-27
**Scope:** Replace the current single-pipeline extraction with a layered canvas substrate, per-canonical field components, two-tier LLM judges, and workbook-level sheet routing. Lands across eight tiers / ~28 PRs into a long-lived `canvas-architecture` integration branch.
**Author:** Nagasai
**Related:** ADR-0007 (Pipeline Architecture Redesign), CLAUDE.md (LLM-as-reviewer principle), CODING_STANDARD.md

---

## 1. Goal

Replace the current TNA extractor — a single SheetRowPlanner + Applier path that struggles with multi-sheet workbooks, non-tabular layouts, and per-canonical disambiguation — with a **canvas-as-substrate architecture** where:

- **Channels** measure every sheet
- **Patterns** derived from channels expose structural facts (strips, merges, bordered boxes, k:v blocks)
- **Semantic resolvers** interpret patterns into typed roles (header bands, stage arenas, data row ranges)
- **Per-canonical components** encapsulate each field's policy in its own small module
- **Two-tier LLM judges** arbitrate only when det is unsure
- **Workbook routing** clusters sheets by template and runs each cluster independently

The current architecture passes its tests and lifts the eval matrix on most files. It cannot reliably handle SHEET_IS_PLI layouts, section-style layouts, multi-sheet workbooks, or sheets with absent plan-marker text. It also conflates all 11 identifier canonicals into one mega-function whose disambiguation logic has grown to ~400 lines with cross-canonical interactions that resist isolated testing.

This redesign moves us to a measurement-driven architecture where each structural fact has one resolver, each canonical has one component, each LLM judgement has one agent, and the hierarchy `pipeline → components → tools` is enforced by directory layout and import contract.

## 2. Four pain points this addresses

1. **One mega-extractor handles 11 canonicals.** `find_tabular_identifiers` mixes spec-alias matching, word-boundary rules, anti-pattern rejection, sibling resolution, bare-CODE positional logic, single-column arbitration, and dtype gating. Any single fix requires reasoning about all 11 canonicals together. We've patched it ~five times in one session; the next supplier-specific quirk will require another patch. Each canonical needs its own home with its own tests, its own confidence policy, and its own anti-patterns.
2. **Channels are too raw for extractors to use.** Today's extractors reach directly into `canvas.channels["fill_color"][r][c]` for spatial decisions. There's no intermediate layer between "what colour is this cell" and "this column is part of a stage band". The semantic gap forces every component to redo the same pattern-detection work.
3. **Workbook-level structure is invisible.** The pipeline runs against `wb.active` and treats each sheet as a standalone problem. Workbooks like new Eastman TnAs (17 PLIs across 17 sheets) and 63261-TNA (1 PLI Sheet 1 + 19 PLIs Sheet 2) need workbook-level routing — clustering sheets by template, deciding which clusters carry PLIs, dispatching extraction per cluster. None of this exists.
4. **LLM judgement is missing where det disagrees with itself.** Today's LayoutHinter / PlanReviewer / FieldNamer agents run on a per-sheet basis as producers, not reviewers. There is no "I have two competing column claims for io_number; which is right?" path. Per-finding arbitration is exactly what an LLM is good at, but only as a reviewer over typed evidence, not as a free-form producer.

## 3. Core concept

```
                              ┌─────────────────────────────┐
                              │       GridCanvas             │
                              │   (raw measurement channels) │
                              └──────────────┬───────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Pattern Detectors                                   │
                  │   channels → typed structural records                │
                  │   (DateStrip, IntStrip, ColorStrip, MergeSpan,        │
                  │    BorderedBox, KvBlock, RepeatingRowGroup, ...)      │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Semantic Resolvers                                  │
                  │   patterns → typed semantic roles                    │
                  │   (HeaderBand, DataRowRange, StageArena, StageBand,   │
                  │    SubfieldCluster, SectionBoundary)                  │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                                             ▼
                  ┌──────────────────────────────────────────────────────┐
                  │   AxisInferrer + LayoutComposer                       │
                  │   → LayoutHint (PliAxis, StageAxis, SubfieldAxis,     │
                  │      candidate_columns, candidate_rows, ...)          │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Per-Canonical Field Components (parallel)          │
                  │   each: locate → filter → claim → arbitrate → emit   │
                  │   IoNumberComponent, StyleCodeComponent, ...          │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Cross-Cutting Arbiters                              │
                  │   (sibling resolution, single-canonical-per-PLI,      │
                  │    stage-wins, cardinality, merge-alignment)          │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Validators (structural queries over typed records) │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                  ┌──────────────────────────┴───────────────────────────┐
                  │   Judges (LLM-as-reviewer)                            │
                  │   PerFindingJudge per ambiguous finding               │
                  │   PhaseJudge per phase when conflicts unresolved      │
                  └──────────────────────────┬───────────────────────────┘
                                             │
                                             ▼
                                  Reconciler → PLI JSON
```

Above this whole picture sits the **WorkbookPipeline**: it clusters sheets by template similarity, classifies each cluster as `pli_cluster` or `other_sheets`, and runs the SheetPipeline (the diagram above) once per sheet in each `pli_cluster`. The aggregator unions findings across clusters and emits the workbook's final PLI list.

## 4. Workbook layer — sheet routing

Today's pipeline operates per-sheet on `wb.active`. The new layer operates per-workbook and routes per-cluster.

### 4.1 WorkbookProfiler

For every sheet in the workbook, compute a **structural signature**:

```python
@dataclass
class SheetSignature:
    non_blank_mask:        frozenset[tuple[int, int]]   # cells with non-blank value
    dtype_fingerprint:     tuple[tuple[int, ...], ...]  # dtype matrix
    label_text_positions:  dict[tuple[int, int], str]   # cells matching spec aliases
    kv_block_count:        int
    header_band_score:     float
    date_cell_count:       int
    int_large_cell_count:  int
    density:               float                         # non_blank / total_cells
```

`non_blank_mask` is the highest-signal field — if two sheets have the same cells filled in the same positions, they share a template.

### 4.2 SheetClusterer

Pairwise similarity between sheet signatures, grouped via union-find:

```python
similarity(a, b) =
    0.5 * jaccard(a.non_blank_mask, b.non_blank_mask)
  + 0.3 * dtype_cosine(a.dtype_fingerprint, b.dtype_fingerprint)
  + 0.2 * label_text_overlap(a.label_text_positions, b.label_text_positions)

cluster_threshold = 0.8     # similarity ≥ this → same cluster
inherit_threshold = 0.95    # ≥ this → safe to inherit anchor's LayoutHint
```

Sheets that match nothing well form singleton clusters. Clusters group sheets transitively (`A~B`, `B~C` → `{A, B, C}`).

### 4.3 ClusterRoleClassifier

Each cluster gets one role, independent of other clusters:

```
ClusterRole = pli_cluster | other_sheets
```

A cluster is `pli_cluster` if and only if:

```
has_date_cells(cluster) >= 1
AND has_numeric_value_cells(cluster) >= 1
AND (has_kv_blocks(cluster) >= 1 OR has_header_band_with_id_aliases(cluster))
```

Three signals together. Any missing → `other_sheets`. This is intentionally permissive: a borderline summary sheet that happens to have identifier-like labels gets extracted; validators downstream catch low-confidence findings, and the judge layer can drop them.

We do not classify `other_sheets` further (no summary/cover/scratch sub-distinctions). The extractor's job is to find PLIs, not classify sheets.

### 4.4 SheetSelector + Aggregator

Selector drops `other_sheets` clusters; only `pli_cluster` clusters proceed. Aggregator unions per-sheet findings across all `pli_cluster` runs, source-prefixing coords with sheet names. A **`(io_number, style_code)` composite-key dedup** runs at the aggregator — if the same PLI somehow appears in two clusters, the one with stronger evidence wins, the other is flagged.

### 4.5 Workbook composition patterns the architecture handles

| Workbook shape | Example | Routing result |
|---|---|---|
| Single template, many sheets | new Eastman TnAs (17 sheets, 1 template) | 1 pli_cluster of size 17 → 17 PLIs |
| Multiple templates, all PLI | hypothetical men's + women's TNAs | 2 pli_clusters → sum of PLIs |
| Independent sheets, mixed layouts | 63261-TNA (Sheet 1 SHEET_IS_PLI + Sheet 2 tabular) | 2 pli_clusters of size 1 each → 1 + 19 = 20 PLIs |
| One PLI cluster + outliers | DKN with a cover sheet | 1 pli_cluster + 1 other_sheets → ignore cover |
| Multi-sheet GT mismatch (MAIN FALL #1) | Three sheets, three different plans | 3 pli_clusters → each scored independently |

The "MAIN FALL #1 multi-sheet GT mismatch" eval problem dissolves at this layer — each sheet's cluster is scored against the GT entry for that sheet.

## 5. Structure phase — per cluster

For each `pli_cluster`, StructurePhase runs once on the cluster's **template anchor** and produces a `LayoutHint` that the whole cluster shares.

### 5.1 Anchor picker

```
score(sheet) =
    0.4 * non_blank_density
    + 0.3 * spec_match_count
    + 0.2 * (kv_block_count or header_band_score)
    + 0.1 * (1 / sheet_index)
```

Highest score wins; ties broken by lowest sheet index. For singleton clusters, the lone sheet is the anchor by default.

### 5.2 Pattern detectors — raw channels to typed records

All detectors read the canvas and emit records into a `StructureBag`. They are parallel-safe (no dependencies between detectors).

```
Pattern                       Direction            Detection rule
─────────────────────────────────────────────────────────────────
DateStrip                     vertical | horiz     ≥3 contiguous date cells in a line
IntStrip (small|medium|large) vertical             ≥80% int cells in column, magnitude-gated
FloatStrip                    vertical             ≥80% float cells
SameLengthStrip               vertical             >70% string cells share character length
LongTextStrip                 vertical             ≥20-char strings predominantly
ColorStrip                    vertical | horiz     ≥3 contiguous cells same fill colour
BoldStrip                     vertical | horiz     contiguous bold cells
BorderedBox                   rectangle            complete 4-side border outline
MergeSpan                     horizontal | vertical extends merge_shape with explicit direction
NonMergedStrip                vertical | horiz     zero merge participation in data rows
MergedColumnStrip             vertical             ≥2 vertical merges in data rows
KvBlock                       cell-pair            bold/filled label + adjacent value (non-label)
RepeatingRowGroup             —                    rows with identical content signatures
PlanMarkerCluster             cell-cluster         cells matching "Plan/Planned/Scheduled" text
```

Every detector:
1. Reads the canvas (channels + cell_values + merge_ranges)
2. Emits typed records into `StructureBag`
3. Writes a corresponding cluster_id channel back onto the canvas (e.g., `date_strip_id` channel)

The dual representation matters: spatial queries use the channel (`what date_strip_id is at (r, c)?`), iteration uses the records (`for strip in structure_bag.date_strips`).

### 5.3 Semantic resolvers — patterns to typed roles

A DAG ordered by dependencies:

```
StructureBag
    │
    ▼
HeaderBandResolver           ← BoldStrip, ColorStrip-Horiz, spec matches
    │
    ├──→ DataRowRangeResolver
    │
    └──→ SectionBoundaryResolver   ← RepeatingRowGroup + HeaderBand
                │
                ▼
       StageArenaResolver           ← DateStrip-Vert + PlanMarkerCluster +
                │                     BorderedBox + ColorStrip-Vert
                ▼
       StageBandResolver            ← StageArena + MergeSpan-Horiz above
                │
                ▼
       SubfieldClusterResolver      ← StageBand + per-col/per-row dtype distribution
```

Each resolver runs once. Output adds to the `StructureBag` (now richer): `HeaderBand`, `DataRowRange`, `StageArena`, `StageBand`, `SubfieldCluster`, `SectionBoundary`.

### 5.4 AxisInferrer — three axes from one pass

```python
@dataclass
class LayoutAxes:
    pli_axis:       Direction   # vertical | horizontal | sheet | sectional
    stage_axis:     Direction   # vertical | horizontal | none
    subfield_axis:  Direction   # vertical | horizontal | implicit
    confidence:     dict[str, float]
```

**PliAxis decision tree:**
```
if kv_block_count >= 3 AND n_data_rows < 5 AND sheet_size < 600:
    PliAxis = sheet
elif n_repeating_groups >= 3 AND n_data_rows >= 10:
    PliAxis = sectional
elif n_data_rows > n_data_cols * 2:
    PliAxis = vertical
elif n_data_cols > n_data_rows * 2:
    PliAxis = horizontal
else:
    PliAxis = vertical (default; conservative bias)
```

**StageAxis decision tree:**
```
if PliAxis == sheet:
    if horiz_date_strips >= 2:   StageAxis = horizontal (stages span cols in bands)
    elif vert_date_strips >= 2:  StageAxis = vertical
    else:                        StageAxis = none
elif PliAxis in (vertical, sectional):
    if vert_date_strips >= 3:    StageAxis = horizontal (stage columns)
    elif horiz_date_strips >= 3: StageAxis = vertical
    else:                        StageAxis = none
```

**SubfieldAxis:** inspect inside one StageBand:
- MergeSpan-Horiz with 2-4 sub-columns of differing dtype → horizontal
- Adjacent rows with alternating dtypes (string row above date row) → vertical

### 5.5 LayoutHint composition

The cluster's final layout artifact:

```python
@dataclass
class LayoutHint:
    axes:                LayoutAxes
    header_band:         HeaderBand | None
    data_row_ranges:     list[DataRowRange]
    section_boundaries:  list[SectionBoundary]
    stage_arenas:        list[StageArena]
    stage_bands:         list[StageBand]
    subfield_clusters:   list[SubfieldCluster]
    kv_blocks:           list[KvBlock]

    pli_iterator:        Callable[[], Iterator[PliSlot]]
    stage_iterator:      Callable[[PliSlot], Iterator[StageSlot]]

    candidate_columns:   dict[str, list[int]]
    candidate_rows:      dict[str, list[int]]
    candidate_kv_blocks: dict[str, list[KvBlock]]

    cluster_id:          str
    confidence:          float
```

`candidate_*` dicts pre-narrow the search space for field components. By the time `IoNumberComponent` runs, the LayoutHint has already identified which columns / kv blocks the io_number alias matches. The component does arbitration + validation, not search.

### 5.6 Layout inheritance

For non-anchor sheets in a cluster:
1. Build canvas (required — values vary per sheet).
2. Run inheritance verifier: confirm that ≥90% of anchor's header-band coordinates have non-blank string values on this sheet.
3. If verifier passes: inherit the cluster's LayoutHint directly. No re-detection.
4. If verifier fails: fall back to full StructurePhase on this sheet (expensive but correct).

For high-similarity clusters (≥0.95) inheritance succeeds nearly always.

## 6. Per-canonical field components

### 6.1 The five-step contract

Every per-canonical component implements the same internal pipeline:

```
                    ┌──────────────────────────────────┐
                    │   <Canonical>Component             │
                    │                                    │
   LayoutHint ────► │  1. Locate                         │  spec aliases +
   canvas ────────► │     candidate cells                │  word-boundary rules +
                    │                                    │  reject phrases
                    │                                    │
                    │  2. Filter                         │  visual gate, dtype gate,
                    │     drop non-label cells           │  bold/fill, header band only
                    │                                    │
                    │  3. Claim columns                  │  tabular vs k:v decision
                    │     which cols feed which rows     │  + merge expansion
                    │                                    │
                    │  4. Arbitrate (intra-canonical)    │  single column per section
                    │                                    │  by spec alias position
                    │                                    │
                    │  5. Emit Findings + Confidence     │  per-row Finding +
                    │                                    │  evidence trail
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                          List[Finding]
                          channel `finding_<canonical>` on canvas
                          decision_notes for judge layer
```

### 6.2 Canonical inventory

The 11 identifier canonicals fall into five families:

| Family | Canonicals | Cardinality | Cross-cutting rule |
|---|---|---|---|
| Anchor pair | io_number, quantity | both mandatory (1 / PLI) | io_number anchors PLI rows |
| Style siblings | style_code, style_name | code mandatory, name optional | siblings under merged STYLE |
| Color siblings | color_code, color_name | code usual, name optional | siblings under merged COLOR; bare-CODE rule |
| Fabric siblings | fabric_code, fabric_name | both optional | siblings under merged FABRIC |
| Date trio | delivery_date, shipment_date, ex_fty_date | conditional: ≥1 of three / PLI | stage-wins (not inside StageArena) |

Plus: `stages` (open vocabulary, see §7) and `metadata` (open vocabulary, see §8).

### 6.3 Per-canonical specifications

#### IoNumberComponent

- **Cardinality:** mandatory; exactly 1 per PLI
- **Value dtype:** ANY (alphanumeric; int IDs or codes)
- **Spec alias priority:** internal-order > buyer-PO (by spec position)
- **Tools used:** query_spec with word-boundary on `io`, `ion`, `po`
- **Reject phrases:** `description`, `submission`, `inspection`, `consumption`, `deviation`
- **Structural extractions:** HeaderBand, DataRowRange (or KvBlock for SHEET_IS_PLI), SameLengthStrip on candidate column, IntStrip if numeric IDs, ColorStrip-Vert
- **Validators:** cardinality = PLI count; uniqueness ≥ 80% of values
- **Role:** anchor — other identifiers constrain to its row set

#### QuantityComponent

- **Cardinality:** mandatory; exactly 1 per PLI
- **Value dtype:** INT/FLOAT, range 1-100000
- **Spec alias priority:** most-specific first (`order qty` > `qty`)
- **Reject phrases:** `cut qty`, `shipped qty`, `sewn qty`, `received qty`, `approved qty`, `mats qty`
- **Structural extractions:** IntStrip-Large on candidate column (distinguishes quantity from size columns INT_SMALL)
- **Validators:** ≥80% int/float in column; ≥80% of values in [1, 100000]; signal density when PLI count is large

#### Date trio: DeliveryDate / ShipmentDate / ExFtyDate

Shared shape:
- **Cardinality:** conditional — exactly ≥1 of three per PLI
- **Value dtype:** DATE (HARD)
- **Stage-wins rule:** drop any finding whose cell is inside a StageArena
- **Structural extractions:** DateStrip-Vert (tabular) or KvBlock (SHEET_IS_PLI); negative StageArena
- **Validators:** combined cardinality, mutual exclusivity per row, ≥80% date cells in claimed column

Per-canonical aliases:
- delivery_date: `delivery`, `eta`, `arrival`
- shipment_date: `shipment`, `ship`, `dispatch`, `ex con`, `transport`
- ex_fty_date: `ex factory`, `ex fac`, `ex fty`, `exf`

Reject phrases (each rejects the others' family):
- shipment_date rejects: `ex factory shipment` (stage)
- ex_fty_date rejects: nothing per se; stage-wins handles "Ex Factory Shipment" stage
- delivery_date rejects: nothing per se

#### Code/name sibling triples

Each `<family>_code` + `<family>_name` pair:

- 1st column under merged FAMILY band → `*_code`
- 2nd column under merged FAMILY band → `*_name`
- 3rd+ columns → metadata
- Single-column-per-canonical arbitration uses spec alias position
- Sibling resolution lives in `IdentifierArbiter` (cross-cutting; see §6.5)

Style:
- aliases: `style`, `style no`, `style #`, `style code`, `sty`
- reject: `style description`
- value: alphanumeric, often same-length within sheet → SameLengthStrip reinforces

Color:
- aliases: `color`, `colour`, `color code`, `col`
- reject: `color description`
- value: alphanumeric Pantone codes or numeric → SameLengthStrip + bare-CODE positional rule
- Bare-CODE rule: header cell with text "CODE" (no qualifier) within ±2 cols of a `color`-aliased header → inherit color_code

Fabric:
- aliases: `fabric`, `fab`, `fbr`
- reject: `fabric description`, `fabric #`
- value: composite descriptive strings, LongTextStrip reinforces

### 6.4 BaseCanonicalComponent

Every component subclasses one base:

```python
@component
class BaseCanonicalComponent(Component):
    """Base contract for per-canonical extractors. Five-step pipeline:
    locate → filter → claim → arbitrate → emit."""

    canonical: ClassVar[str]                     # subclass declares
    spec: ClassVar[FieldSpec]                    # spec for this canonical
    supports: ClassVar[set[PliMode]] = ...       # which layouts this handles

    @component.output_types(findings=list[Finding])
    def run(self, canvas: GridCanvas, layout: LayoutHint) -> dict:
        if layout.axes.pli_axis not in self.supports:
            return {"findings": []}
        candidates = self._locate(canvas, layout)
        filtered = self._filter(candidates, canvas, layout)
        claims = self._claim(filtered, canvas, layout)
        arbitrated = self._arbitrate(claims, layout)
        findings = self._emit(arbitrated, canvas, layout)
        return {"findings": findings}

    # Subclasses override these:
    def _locate(self, canvas, layout) -> list[SpecMatch]: ...
    def _filter(self, candidates, canvas, layout) -> list[SpecMatch]: ...
    def _claim(self, filtered, canvas, layout) -> dict[int, SpecMatch]: ...
    def _arbitrate(self, claims, layout) -> dict[int, SpecMatch]: ...
    def _emit(self, arbitrated, canvas, layout) -> list[Finding]: ...
```

Most subclasses override only `_filter` and `_arbitrate` (where canonical-specific policy lives). `_locate` and `_claim` defer to shared tools.

### 6.5 IdentifierArbiter — cross-cutting concerns

Three cross-canonical concerns live in one arbiter that runs after all per-canonical components:

1. **Sibling resolution** under merged code-family bands (style, color, fabric — 1st = code, 2nd = name, 3rd+ = metadata).
2. **Single-canonical-per-PLI invariant** — if two canonicals claim the same column, arbiter resolves by spec priority.
3. **Stage-wins rule** — date identifier findings whose cells lie inside a StageArena are dropped.

The arbiter also enforces **cardinality** for mandatory canonicals: count of findings for `io_number` and `quantity` must equal len(PliRowSet). Mismatch → emit warning for validator + judge consumption.

### 6.6 KvBlock vs tabular routing inside each component

A canonical's component branches internally by `layout.axes.pli_axis`:

```
if layout.axes.pli_axis == sheet:
    use KvBlock extraction       (find_kv_identifiers logic)
elif layout.axes.pli_axis in (vertical, sectional):
    use tabular extraction       (find_tabular_identifiers logic)
```

Both code paths emit the same `Finding` artifact shape. The router branch lives inside the component, not at the pipeline level.

## 7. Stage extraction

Stages are open vocabulary — any TNA can have any stage names. The extractor decomposes by detection layer, not by canonical:

```
StagesPhase pipeline:
  StageArenaComponent       — date_cluster + plan_marker → arenas
  StageBandComponent        — MergeSpan above arena → band names; ColorStrip
                              + BorderedBox as alternative band delimiters
                              when plan_marker absent (the FA26 case)
  StageColumnTypingComponent — within each band, type each column as
                              plan_date | actual_date | status | remarks | approved_qty
                              using subfield specs
  StagePerPliComponent      — for each (band, PLI) emit one Stage record
                              for ROW_PER_PLI: per-PLI-row × per-band
                              for SHEET_IS_PLI: per-band × per-column-in-band
  StageJudge                — arbitrates ambiguous band boundaries
```

Stage subfields (defined by SubfieldSpec):
- `planned_date` — mandatory per stage
- `actual_date` — optional
- `received_date` — optional
- `approval_date` — optional
- `start_date`, `end_date` — optional
- `approved_qty`, `quantity` — optional numeric
- `remarks` — optional string
- `status` — optional string (newly added: `status`, `action`, `progress` aliases)

The new stage specs added: `vap`, `line_plan`, `feeding`.

## 8. Metadata extraction

Metadata is residual — header-band cells not claimed by any identifier or stage. Per-canonical metadata canonicals (`buyer`, `season`, `factory`, `order_received_date`) are tagged when possible; otherwise raw `(key, value)` pairs.

```
MetadataPhase:
  MetadataCollectorComponent  — unclaimed header-band labels
  MetadataClassifierComponent — closed-vocab tags where possible
  MetadataPerPliBinderComponent — link sheet-level metadata to each PLI
  MetadataJudge — open-vocab classification arbitration
```

## 9. Validators — structural queries

Validators read typed records (findings + structural facts), not raw cells. They emit `ValidationWarning` records:

```
CardinalityValidator
  invariant: count(mandatory_canonical_findings) == count(PliRowSet)
  triggers on: io_number, quantity, style_code missing rows

RowAlignmentValidator
  invariant: per PLI row, claims from different canonicals align
  triggers on: row has io_number but no quantity (or vice versa)

DateTrioValidator
  invariant: every PLI row has ≥1 of {delivery, shipment, ex_fty}
  triggers on: PLI row with zero date identifiers

StageWinsValidator
  invariant: no date identifier finding inside a StageArena rectangle
  triggers on: cell in StageArena claimed by date identifier component

MergeAlignmentValidator
  invariant: if io_number column has merges, sibling identifier columns
             should respect the same row-group partition
  triggers on: io_number merged 4-6 but style_code split 4, 5, 6

QuantityDtypeValidator
  invariant: ≥80% of quantity column cells are int/float, ≥80% in [1, 100000]
  triggers on: quantity column with low numeric density

StyleCodeLengthValidator
  invariant: style_code values have low character-length variance
  triggers on: style_code column with high length variance (likely style_name claimed)
```

Validators are pure functions over Findings + StructureBag — no LLM, no I/O.

## 10. LLM-as-judge — two-tier

Per CLAUDE.md principle: **LLM as reviewer, not producer.** Det extraction runs first; validators run; judges fire only when det disagrees with itself or confidence is low.

### 10.1 PerFindingJudge

Fires per individual `Finding` when:
- Confidence < `judge.confidence_threshold` (default 0.7)
- Any validator warning affects this finding
- Multiple candidate columns/cells competed for this canonical
- Anti-pattern partially matches

Input:
```python
@dataclass
class FindingForJudge:
    finding:                Finding
    sheet_excerpt:          str               # rendered grid around the cells
    spec_snippet:           str               # canonical's spec doc
    alternative_candidates: list[Finding]     # competing claims
    validator_warnings:     list[ValidationWarning]
    cluster_context:        ClusterContext    # workbook position
```

Output:
```python
@dataclass
class Verdict:
    decision:           Literal["keep", "drop", "rewrite"]
    alternative_coord:  Coord | None
    reason:             str
    confidence:         Confidence
```

### 10.2 PhaseJudge

Fires per phase (Identifiers, Stages, Metadata) when:
- Multiple PerFinding verdicts disagree on the same column
- Cross-canonical conflicts unresolved by arbiter
- Cardinality violation persists after PerFindingJudge

Input: all phase Findings + all Verdicts + cross-field validator warnings.
Output: `ArbitratedBag` (final Findings) + phase `decision_notes`.

### 10.3 Judge as Agent

Each judge inherits from `Agent` per the framework primitives:

```
app/agents/identifier_finding_judge/
  __init__.py
  agent.py             # class IdentifierFindingJudge(Agent)
  schema.py            # FindingForJudge, Verdict pydantic models
  tuning.py            # model selection, retries, decision_notes flag
  validators.py        # input/output validators

app/prompts/judges/
  identifier_finding.py    # IDENTIFIER_FINDING_JUDGE_PROMPT constant
  identifier_phase.py
  stage_finding.py
  stage_phase.py
  metadata.py
```

### 10.4 Judge gate component

Pipelines invoke a JudgeGateComponent, not an Agent directly:

```python
@component
class IdentifierFindingGate:
    """Route ambiguous identifier findings to the per-finding judge."""

    def __init__(self, judge: IdentifierFindingJudge,
                 confidence_threshold: float = 0.7):
        Component.__init__(self)
        self.judge = judge
        self.confidence_threshold = confidence_threshold

    @component.output_types(findings=list[Finding])
    def run(self, findings: list[Finding],
            warnings: list[ValidationWarning]) -> dict:
        ambiguous = [f for f in findings
                     if f.confidence < self.confidence_threshold
                     or any(w.affects(f) for w in warnings)]
        clean = [f for f in findings if f not in ambiguous]
        verdicts = [self.judge.run(self._build_input(f, findings, warnings))
                    for f in ambiguous]
        kept = [f.apply_verdict(v) for f, v in zip(ambiguous, verdicts)
                if v.decision != "drop"]
        return {"findings": clean + kept}
```

This way pipelines never import agents directly — that's the hierarchy contract.

### 10.5 Cost control

Expected distribution per sheet:
- ~80% findings: high-confidence det, no judge fired
- ~15% findings: ambiguous → PerFindingJudge
- ~5%: cross-field conflicts → PhaseJudge

Tuning knobs (per agent tuning.py):
- `confidence_threshold` — when to invoke
- `max_concurrent_findings` — batch size limit
- `decision_notes_enabled` — capture full reasoning

## 11. Hierarchy enforcement

The seven framework primitives from ADR-0007 are the structural contract. Per CODING_STANDARD Section 11:

| Primitive | Home | Role | Imports allowed |
|---|---|---|---|
| pipeline | `app/pipelines/<name>.py` | Haystack `Pipeline` orchestration. No business logic. | components, artifacts, prompts |
| component | `app/components/<name>.py` | Single `run()` entry, typed I/O, `@component`. | tools, agents (when wrapping), artifacts |
| agent | `app/agents/<name>/` | One narrow LLM mapping job. | inferencing, prompts, schemas, tools |
| tool | `app/tools/<name>.py` | Stateless `@tool`. | stdlib, third-party, specs, artifacts |
| inferencing | `app/inferencing/<provider>.py` | Single LLM-call boundary. | provider SDK, capture helpers |
| prompts | `app/prompts/<name>.py` | One module per prompt. | stdlib only |
| tuning | `app/<owner>/tuning.py` | pydantic-settings blocks. | pydantic_settings |

**Import-graph test** enforces the contract:

```python
# tests/architecture/test_import_hierarchy.py
def test_tools_dont_import_components_or_pipelines():
    for module in iter_modules("app.tools"):
        assert not imports_anything_under(module, "app.components")
        assert not imports_anything_under(module, "app.pipelines")
        assert not imports_anything_under(module, "app.agents")

def test_pipelines_dont_invoke_agents_directly():
    for module in iter_modules("app.pipelines"):
        assert not imports_anything_under(module, "app.agents")

def test_components_dont_import_pipelines():
    for module in iter_modules("app.components"):
        assert not imports_anything_under(module, "app.pipelines")
```

Runs in CI on every PR. Cheap; high-signal.

## 12. Pipeline composition — Style B

**Primary public entry:**

```python
# app/pipelines/canvas/main.py
def make_canvas_pipeline() -> Pipeline:
    """End-to-end canvas pipeline: workbook → structure → fields → judges → reconcile."""
    p = Pipeline()
    _add_workbook_components(p)
    _add_structure_components(p)
    _add_identifier_components(p)
    _add_stage_components(p)
    _add_metadata_components(p)
    _add_validators(p)
    _add_judges(p)
    _add_reconciler(p)
    _wire_edges(p)
    return p
```

**Sub-factories for testability:**

```python
# app/pipelines/canvas/structure.py
def make_structure_pipeline() -> Pipeline:
    """Standalone structure pipeline — testable in isolation."""
    p = Pipeline()
    p.add_component("canvas",       CanvasBuilder())
    p.add_component("date_strips",  DateStripDetector())
    p.add_component("int_strips",   IntStripDetector())
    # ... etc.
    return p

# app/pipelines/canvas/identifiers.py
def make_identifier_phase_pipeline() -> Pipeline:
    """Standalone identifier phase — all 11 per-canonical components."""
    p = Pipeline()
    for canon in IDENTIFIER_CANONICALS:
        p.add_component(f"id_{canon}", COMPONENT_REGISTRY[canon]())
    p.add_component("arbiter", IdentifierArbiter())
    p.add_component("judge_gate", IdentifierFindingGate(IdentifierFindingJudge()))
    return p

# app/pipelines/canvas/workbook.py
def make_workbook_pipeline() -> Pipeline:
    """Workbook-level routing pipeline — clusters and routes sheets."""
    p = Pipeline()
    p.add_component("profile",  WorkbookProfiler())
    p.add_component("cluster",  SheetClusterer())
    p.add_component("classify", RoleClassifier())
    p.add_component("select",   SheetSelector())
    p.add_component("dispatch", PerClusterDispatcher())
    p.add_component("aggregate",WorkbookAggregator())
    return p
```

The mega-factory `make_canvas_pipeline()` is the canonical entry point used in production. Sub-factories exist for unit-level pipeline testing without spinning up the whole canvas.

### Naming convention

```
make_<scope>_pipeline()       returns a Pipeline (factory)
build_<thing>()               returns a non-pipeline artifact (e.g. GridCanvas)
extract_<canonical>()         function-style, used inside a Component's run()
```

Verb-first per CODING_STANDARD Section 1.

## 13. Eval contract

The eval scorecard IS the contract. Each PR runs:

1. **All existing tests pass** (252 today; doesn't decrease)
2. **Canvas eval against `dataset/extracted_2`** — no regression on (id_recall, id_precision, stage_recall, stage_precision)
3. **CODING_STANDARD Section 10 self-review** — all checklist items ticked or noted

Per-canonical recall/precision matrix is the primary feedback signal. Per-file ID and stage recall is the secondary.

**Final merge bar (canvas-architecture → main):**
Canvas path matches or beats SheetRowPlanner path on `dataset/extracted_2` by ≥5pts identifier recall AND ≥5pts identifier precision AND no stage regression.

## 14. Migration path

Three rules for the integration period:

1. **Legacy SheetRowPlanner path stays running** in parallel until Tier 7 router lands. Removes regression risk during canvas development. Both paths run; tuning controls which is the source of truth per sheet.
2. **`experiments/p3_visual/canvas_probe/` stays untouched** until the corresponding `app/` code lands and passes parity tests. Retired in Tier 8.
3. **Weekly rebase from `main`** keeps `canvas-architecture` aligned. Long-lived integration branches drift; rebase cadence is non-negotiable.

## 15. PR map (28 PRs across 8 tiers)

```
TIER 0 — FOUNDATIONS + DESIGN DOCUMENT          [4 PRs]
  PR 0a:  docs — ADR-0008 + this design doc + ARCHITECTURE.md section
  PR 0b:  docs — master plan + 8 tier plan files
  PR 0c:  refactor — promote experiments/specs → app/specs
  PR 0d:  feat(artifacts) — GridCanvas, StructureBag, LayoutHint, Finding, Verdict

TIER 1 — TOOLS                                  [4 PRs]
  PR 1a:  feat(tools/canvas) — build + around + query
  PR 1b:  feat(tools/canvas) — strip detectors (date, numeric, text)
  PR 1c:  feat(tools/canvas) — strip detectors (visual, merge, kv, repeating)
  PR 1d:  feat(tools/canvas) — plan_marker + dtype profiles

TIER 2 — STRUCTURE PHASE                        [3 PRs]
  PR 2a:  feat(structure) — pattern→semantic resolvers
  PR 2b:  feat(structure) — axis_inferrer + layout_composer
  PR 2c:  feat(structure) — phase orchestrator + anchor_picker

TIER 3 — WORKBOOK PHASE                         [2 PRs]
  PR 3a:  feat(workbook) — profiler + clusterer + role_classifier
  PR 3b:  feat(workbook) — phase orchestrator + aggregator

TIER 4 — FIELD COMPONENTS                       [7 PRs]
  PR 4a:  feat(components) — BaseCanonicalComponent
  PR 4b:  feat(components/identifiers) — io_number + quantity
  PR 4c:  feat(components/identifiers) — code trio + name trio + siblings
  PR 4d:  feat(components/identifiers) — date trio + stage-wins
  PR 4e:  feat(components/identifiers) — IdentifierArbiter
  PR 4f:  feat(components/stages) — Arena → Band → ColumnTyping → PerPli
  PR 4g:  feat(components/metadata) — Collector + Classifier + PerPliBinder

TIER 5 — VALIDATORS                             [2 PRs]
  PR 5a:  feat(validators) — cardinality + row_alignment + date_trio
  PR 5b:  feat(validators) — stage_wins + merge_alignment + dtype + orchestrator

TIER 6 — JUDGES                                 [3 PRs]
  PR 6a:  feat(agents/judges) — judge-spike end-to-end + ADR-0009
  PR 6b:  feat(agents/judges) — full finding + phase judges
  PR 6c:  feat(pipelines) — judge gating (confidence + validator triggers)

TIER 7 — PIPELINES                              [2 PRs]
  PR 7a:  feat(pipelines/canvas) — make_*_pipeline factories + router
  PR 7b:  feat(pipelines) — reconciler + canvas vs legacy switch

TIER 8 — EVAL + DELIVERY                        [2 PRs]
  PR 8a:  feat(eval) + test(integration) — canvas_eval in app/, smoke tests
  PR 8b:  chore — retire experiments, journey entry, final merge
```

Each tier delivers a coherent story. The eval scorecard moves forward at known checkpoints:

| Tier | Eval expectation |
|---|---|
| 0 | no change (artifacts only) |
| 1 | no change (tools only) |
| 2 | LayoutHints visualisable; no extraction yet |
| 3 | multi-sheet workbooks correctly clustered |
| 4 | identifier recall ≥ 68%, precision ≥ 65% (parity with experiments) |
| 5 | validator warnings visible per finding |
| 6 | identifier recall +5pts from judge arbitration on ambiguous canonicals |
| 7 | end-to-end PLI JSON output via canvas path |
| 8 | canvas beats legacy by ≥5pts on both metrics |

## 16. Out of scope

Explicitly NOT in this design:

- **API contract changes** — `POST /extract` shape stays the same.
- **New ground-truth labels** — `dataset/extracted_2` is the eval target; we don't relabel.
- **Infrastructure changes** — Docker, SigNoz, CI runner unchanged.
- **Frontend / UI changes** — none in this branch.
- **Performance benchmarks** — canvas path should be no slower than legacy; not formally measured.
- **Multi-workbook batch extraction** — one xlsx at a time, same as today.

## 17. Open questions deferred to implementation

These are flagged for resolution during the respective tier, not now:

1. **Re-run vs inherit threshold** (Tier 2). Initial heuristic: 90% header-cell verification.
2. **Two-pass AxisInferrer overhead** (Tier 2). May need memoization on large GUESS-style sheets.
3. **Per-cluster confidence budget** (Tier 3). Low-confidence clusters might route directly to judge for layout review before field extraction.
4. **Judge prompt patterns** (Tier 6 spike). Discovered during 6a; documented in ADR-0009.
5. **Cluster threshold tuning** (Tier 3). Start at 0.8 similarity; tune against extracted_2.
6. **Multi-language sheet names** (Tier 3). Defer to v2; rely on structural signals.

## 18. References

- **ADR-0007** (Pipeline Architecture Redesign) — the seven framework primitives this design builds on
- **CLAUDE.md** — LLM-as-reviewer principle, four extensibility axes
- **CODING_STANDARD.md** — Section 11 framework primitives, Section 10 self-review
- **docs/PRINCIPLES.md** — Faithful extraction, route on structural signals
- **docs/SPEC.md** — API contract (unchanged)
- **experiments/p3_visual/canvas_probe/** — current canvas probe implementation; reference until Tier 8
- **dataset/extracted_2/dataset_plis_bulk.json** — ground truth for eval scoring

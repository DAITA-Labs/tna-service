# Three-Area Decomposition of SheetLevelPlan Extraction

The problem statement, broken cleanly. The per-sheet extraction job splits into
**three independent areas**, each with its own component (group of tools) and
its own LLM judge. No new abstraction layer beyond what the codebase already
has — `tool`, `component`, `pipeline`.

## Hierarchy

```
pipeline  →  component  →  tool      (uses)
   ▲           ▲
   │           │
   │           └── group of tools, "small meaningful work",
   │               can run multiple tools in parallel
   │
   └── orchestrates components

   No reverse imports. A component never imports a pipeline.
   A tool never imports a component.
```

## The three areas

```
              ┌────────────────────────────────────────────────┐
              │              SHEET                             │
              │                                                │
              │  ┌──────────────┐  ┌────────────────────────┐  │
              │  │ IDENTIFIERS  │  │       STAGES           │  │
              │  │              │  │                        │  │
              │  │  io_number*  │  │  arena bounds          │  │
              │  │  quantity*   │  │  stage bands           │  │
              │  │  style_code  │  │  per-stage:            │  │
              │  │  style_name  │  │     name + plan_date   │  │
              │  │  fabric_code │  │     stage_metadata{}   │  │
              │  │  fabric_name │  │                        │  │
              │  │  color_code  │  │                        │  │
              │  │  color_name  │  │                        │  │
              │  │  delivery_dt │  │                        │  │
              │  └──────────────┘  └────────────────────────┘  │
              │                                                │
              │  ┌──────────────────────────────────────────┐  │
              │  │ METADATA — anything else useful          │  │
              │  │ free-form k:v                            │  │
              │  └──────────────────────────────────────────┘  │
              │                                                │
              └────────────────────────────────────────────────┘
                  * mandatory
```

## Area 1 — Identifiers

### Goal

Extract the 9 identifier fields. `io_number` and `quantity` are mandatory and
also serve as **bootstrap signals** for layout mode (see §"bootstrap" below).

| Field | Optional? | Notes |
|---|---|---|
| `io_number` | NO | user-defined; can be anything; can repeat |
| `quantity` | NO | numeric; total or breakdown |
| `style_code` | yes | code (often alphanumeric) |
| `style_name` | yes | descriptive string |
| `fabric_code` | yes | |
| `fabric_name` | yes | |
| `color_code` | yes | |
| `color_name` | yes | |
| `delivery_date` | yes | date |

### Tools (deterministic units)

| Tool | Job |
|---|---|
| `find_io_locations` | scan for cells labeled `"IO No"`, `"IO #"`, `"Internal Order"`, etc. Return cell refs of labels + adjacent value cells. **Label-driven, not value-driven** (io_number values can be anything). |
| `find_quantity_locations` | scan for cells labeled `"Qty"`, `"Order Qty"`, etc. + value cells. |
| `scan_headers_for_identifiers` | for ROW_PER_PLI: vocab-match every cell of the header row(s) against identifier canonicals. |
| `scan_kv_for_identifiers` | for SHEET_IS_PLI / SECTION_PER_PLI: scan label-value pairs (vocab on label, capture adjacent value). |
| `infer_field_from_dtype` | tiebreaker when label is ambiguous: `Color` + value `"6602"` (int) → `color_code`; `Color` + value `"RED"` (str) → `color_name`. |

### Component: `IdentifierExtractor`

```
inputs:  sheet (rows × cells)
outputs: IdentifierFindings {
            io_locations:        [(label_cell, value_cell, score), ...]
            quantity_locations:  [(label_cell, value_cell, score), ...]
            style_code:          (cell, value, score) | null
            style_name:          (cell, value, score) | null
            fabric_code:         (cell, value, score) | null
            ...
            warnings:            [str]
         }

does:
    1. Run find_io_locations + find_quantity_locations IN PARALLEL
       (these are independent; both scan the whole sheet)
    2. Run scan_headers_for_identifiers + scan_kv_for_identifiers IN PARALLEL
    3. Reconcile findings; use infer_field_from_dtype for ambiguity
    4. Emit IdentifierFindings
```

### Bootstrap insight: io_number locations → pli_mode hint

| io_number found at | Hint |
|---|---|
| one column header + many values down → `ROW_PER_PLI` |
| one label cell + one value cell → `SHEET_IS_PLI` |
| multiple label-value pairs in distinct regions → `SECTION_PER_PLI` |

This means identifier extraction also yields a free signal for layout mode.
Layout mode then refines stage detection (different combiners per mode).

---

## Area 2 — Stages

### Goal

1. Find the stage arena (continuous date-bearing region) and its bounds.
2. Split into stage bands if multi-band.
3. For each stage: extract (name, plan_date) + everything else into `stage_metadata{}`.

### Why this is simpler than the current model

Current `SheetPlan`: `stage_bands[]` with first-class `sub_columns` (PLAN/ACT/RECVD/APPD/...).
Proposed: `stage = { name, plan_date, stage_metadata{k:v} }`.

- `name + plan_date` are the only required fields per stage.
- `actual_date`, `received_date`, `approval_date`, `remarks`, etc. all collapse into `stage_metadata{}`.
- New supplier-specific sub-fields (`"DEVIATION"`, `"START_PLAN"`, ...) are NOT a schema problem — they go into metadata too.

### Tools

| Tool | Job |
|---|---|
| `column_date_density` | per column, fraction of cells parsing as dates |
| `vocab_row_scan` | per header row, find stage-vocab matches |
| `find_arena_bounds` | combine the above → (upper_row, lower_row, left_col, right_col) of stage data region |
| `find_bands_within_arena` | within arena, group adjacent stage-vocab-matching columns into bands |
| `extract_stage_name` | per band: vocab on name_row cells (with vote across band columns) |
| `extract_plan_date_column` | per band: find the sub-column whose label matches `plan` vocab; remember it |
| `collect_stage_metadata` | per band, per PLI row: every column except plan_date → metadata{} |

### Components (two — split for clarity)

#### `StageArenaDetector` (structural)

```
inputs:  sheet, IdentifierFindings (to exclude identifier date columns from arena)
outputs: StageArenaFindings {
            bounds:  (upper_row, lower_row, left_col, right_col)
            bands:   [(start_col, end_col, name_row, score), ...]
            warnings:[str]
         }

does:
    1. Run column_date_density + vocab_row_scan IN PARALLEL
    2. Run find_arena_bounds (depends on both)
    3. Run find_bands_within_arena
    4. Emit StageArenaFindings
```

#### `StageDetailExtractor` (per-band)

```
inputs:  sheet, StageArenaFindings, IdentifierFindings (for PLI row anchors)
outputs: StageFindings {
            stages_per_pli: dict[pli_row_index, [
                Stage {
                    name:           str
                    plan_date_col:  cell_ref | null
                    plan_date:      date | null   (per PLI row)
                    metadata:       dict[sub_label, value]
                }, ...
            ]]
         }

does:
    For each band, in parallel:
        1. extract_stage_name
        2. extract_plan_date_column
    Then for each (band, pli_row), in parallel:
        3. collect_stage_metadata
    Emit StageFindings
```

### Multi-band example (CHRISTIAN BERG — 7 stages)

```
              ┌──────────────────── stage arena ────────────────────────┐
              ▼                                                          ▼
row 1   ID  ST  CLR QTY FAB FAB FAB SEW SEW SEW CUT CUT FI  FI  PACK PACK
row 2                   PLN RCV APP PLN STR ACT PLN ACT PLN ACT PLN  ACT
row 3+  ...
              ├ FAB ─┤├── SEW ──┤├ CUT ┤├ FI ┤├ PACK ┤
```

`StageArenaDetector` returns:
- bounds: rows 1..N, cols 5..16
- bands: [(5-7, FAB), (8-10, SEW), (11-12, CUT), (13-14, FI), (15-16, PACK)]

`StageDetailExtractor` per band: name + plan_date column + metadata bag for the rest.

---

## Area 3 — Metadata

### Goal

Sweep up everything useful that's NOT an identifier or stage value.
Free-form k:v — buyer, season, factory, PO number, ex-factory date, special instructions, ...

### Tools

| Tool | Job |
|---|---|
| `scan_unclaimed_cells` | enumerate cells not in identifier zones or stage arena |
| `find_kv_pairs` | detect label-value patterns (label adjacent to value cell with dtype) |
| `categorize_label` | try vocab on label; if hit, attach canonical; if miss, keep raw |

### Component: `MetadataSweeper`

```
inputs:  sheet, IdentifierFindings, StageArenaFindings
outputs: MetadataFindings {
            kv: dict[label_canonical | raw_label, value]
            warnings: [str]
         }

does:
    1. scan_unclaimed_cells → list of candidate (label_cell, value_cell)
    2. find_kv_pairs IN PARALLEL with categorize_label (over the unclaimed set)
    3. Reconcile, emit MetadataFindings
```

---

## Pipeline shape

```
                 ┌───────────────────────────┐
                 │   sheet (rows × cells)    │
                 └─────────────┬─────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │  parallel:                                  │
        │   IdentifierExtractor   StageArenaDetector  │
        └──────────────────────┬──────────────────────┘
                               │
                  IdentifierFindings + StageArenaFindings
                               │
                               ▼
                  ┌─────────────────────────┐
                  │  StageDetailExtractor   │
                  │  (uses arena + ids)     │
                  └─────────────┬───────────┘
                                │
                  +StageFindings
                                │
                                ▼
                  ┌─────────────────────────┐
                  │   MetadataSweeper       │
                  │   (uses ids + arena to  │
                  │    skip claimed cells)  │
                  └─────────────┬───────────┘
                                │
                                ▼
                  ┌─────────────────────────┐
                  │   SheetLevelPlan        │
                  │   {identifiers, stages, │
                  │    metadata, warnings}  │
                  └─────────────────────────┘
```

## LLM judges (per phase, per field)

Each component's output is auditable independently. The pipeline supports judges
at TWO granularities:

```
phase judge:  given a component's full output + the sheet samples, is this correct?
              (used when component returned anything ambiguous or partial)

field judge:  given one finding (label, value, candidates), pick the right canonical
              (used for individual ambiguous mappings within a phase)
```

Both judges are LLM agents. They fire only when the component's deterministic
combiner can't make a confident call. **The judges DON'T extract** — they
adjudicate. This matches the LLM-as-judge pattern (vs LLM-as-provider).

Wire-up: each component emits `confidence` per finding. Threshold drives
whether the judge gets called.

---

## Experiment shape

Validate the decomposition on 6 representative files spanning all 3 modes:

| File | Mode | What we expect to learn |
|---|---|---|
| `20260129 DKN AW26 ...` | ROW_PER_PLI | Baseline; all 3 areas should succeed cleanly |
| `CHRISTIAN BERG- T&A` | ROW_PER_PLI multi-band | Does StageArenaDetector handle 7 bands? Multi-row header? |
| `20260304 MOPD W26(1) MANOS COMPASS PRO` | ROW_PER_PLI | Does the arena detector find what current planner misses? |
| `63261-TNA` | SHEET_IS_PLI | Does kv-based identifier scanning work? Stage area is kv-shaped too. |
| `new Eastman TnAs #N` | SECTION_PER_PLI | Section detection + per-section processing |
| `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1` | SECTION_PER_PLI | Bigger sections; bigger boundary signal |

Per file, per area, the experiment reports:

- **Identifier coverage**: of the 9 fields, how many did `IdentifierExtractor` find correctly? Where did individual tools contribute / disagree?
- **Stage arena boundaries**: did `StageArenaDetector` find the right (upper, lower, left, right)? How many bands?
- **Per-stage detail**: did `StageDetailExtractor` get the right (name, plan_date)? What landed in metadata?
- **Metadata sweep**: did `MetadataSweeper` find anything the labels file expects (buyer, season, etc.)?
- **Bootstrap check**: does io_number's location pattern correctly predict `pli_mode`?

### What we'll learn

1. Does the 3-area decomposition carve cleanly, or do areas overlap (e.g. a date column is both an identifier `delivery_date` and a stage `plan_date`)?
2. Is the stage simplification `(name, plan_date, metadata{})` enough, or do we lose load-bearing fields the labels file expects?
3. Does io_number bootstrap correctly identify pli_mode for all 6 files?
4. Where do components need to share information they don't currently share (e.g. arena detector needs identifier columns to EXCLUDE them)?
5. Where would an LLM judge most improve coverage?

### Out of scope (deferred)

- Embeddings (revisit once vocab+fuzzy combiners are proven)
- Production wiring (`app/tools/` migrations) — only after this experiment validates the decomposition
- Schema change to `Stage` (current schema keeps `actual_date` etc. first-class; if we want metadata bag we need a follow-up ADR)

---

## Why this is the right next step

- **No new abstractions** — we use `tool`/`component`/`pipeline` as defined; no `signals/` package
- **Each component is small and meaningful** — extracts one of 3 areas; runs its tools in parallel
- **Clean hierarchy** — components never reach up to pipelines
- **Bootstraps from mandatory fields** — io_number + quantity locations free the layout-mode decision
- **Stage simplification reduces over-modeling** — fewer first-class fields, more flexibility for new suppliers
- **Validates BEFORE production wiring** — we measure coverage per area per file before swapping anything into `app/`

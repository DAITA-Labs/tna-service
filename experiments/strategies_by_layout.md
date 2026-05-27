# Strategies × Layout Modes — composition framework

This doc reframes the experiment's findings into a compositional architecture:
**strategies are independent signal emitters; sub-problems combine signals**.
The same strategies work across all three `pli_mode`s (`ROW_PER_PLI`,
`SHEET_IS_PLI`, `SECTION_PER_PLI`) — only the combiner logic varies per mode.

Companion to `strategies_visual_guide.md` (mechanics on small examples) and
`per_sheet_subproblems_compare.md` (empirical scores).

---

## 1. The mental model

### Old model (what we shipped)

One big agent does everything for a sheet: pli_mode, header, bands, names, sub-fields.
Failure modes blur together; tuning is monolithic.

### New model (where we're heading)

```
                      ┌──────────────────────────────────┐
                      │       Signal emitters            │
                      │  (each is independent + reusable)│
                      │                                  │
                      │  vocab        → "label→canonical"│
                      │  fuzzy        → "similar to X"   │
                      │  jaccard      → "tokens overlap" │
                      │  date_density → "col is dates"   │
                      │  sample_value → "col is int/str" │
                      │  embedder     → "semantic close" │
                      │  position     → "row N from X"   │
                      │  block_split  → "blank-row break"│
                      └────────────┬─────────────────────┘
                                   │
                                   ▼
                      ┌──────────────────────────────────┐
                      │     Mode-aware combiners         │
                      │ (one per (sub-problem, mode) pair)│
                      │                                  │
                      │  detect_stage_bands[ROW_PER_PLI] │
                      │  detect_kv_anchors[SHEET_IS_PLI] │
                      │  detect_sections[SECTION_PER_PLI]│
                      │  match_identity_field[ALL]       │
                      │  match_stage_name[ALL]           │
                      │  match_subfield_label[ALL]       │
                      └────────────┬─────────────────────┘
                                   │
                                   ▼
                            SheetPlan artifact
```

Two things this buys us:

1. **Signals are reusable.** `vocab.match(label)` is one function used by 6 different sub-problems. The same `date_density(col)` measurement informs `#4 stage_bands`, `#11 kv_anchor` ranking, and even `#2 header_row` (rows with no dates are likely headers).
2. **Sub-problems are diagnosable.** When stage_recall drops, we trace the signal chain: "vocab said yes, date_density said yes, but combiner rejected because position said the row was wrong." Today's monolithic agent only emits "I extracted no stages."

---

## 2. Signal emitters (independent, reusable)

| Signal | Input | Output | Cost |
|---|---|---|---|
| `vocab(label)` | text | `MatchResult{canonical, score}` | O(1) |
| `fuzzy(label, vocab)` | text + alias set | `MatchResult` | O(N aliases) |
| `jaccard(label, vocab)` | text + alias set | `MatchResult` | O(N tokens) |
| `embedder(label, concept_vectors)` | text + cached vectors | `MatchResult` | O(1) at runtime |
| `date_density(col, data_rows)` | cells | float `[0,1]` | O(rows) |
| `sample_value_dtype(col, data_rows)` | cells | `{int,date,str,blank}` ratio | O(rows) |
| `position(target_row, anchor_row)` | int, int | int offset | O(1) |
| `block_split(rows)` | row range | list of (start,end) | O(rows) |

Each emitter returns evidence + confidence. None of them DECIDES — they report.

### Where embedder fits (your idea)

Embedder produces a vector for each canonical concept (`sewing`, `cutting`,
`fabric`, `io_number`, ...) computed **once at build time** from the canonical
name + 2-3 prototype phrases. At runtime, embed the input label and cosine-compare
against all concept vectors.

```
canonical: sewing
  prototypes: ["sewing", "sewing start", "stitch", "sew"]
  vector: avg(embed(prototype) for prototype)
```

Cost: tiny (a few hundred vectors, in-memory). No LLM at runtime.

When this helps:
- **Tail vocab**: `"PROGRAM SUBMIT ON"` not in vocab table — embedder says it's close to `pps_submission` concept (~0.78 cos sim).
- **Cross-supplier variants**: `"FAB ETA PLAN"` → close to `fabric` (~0.85).
- **Disambiguation**: combine with sample_value — `"Color"` + value `"6602"` → vocab returns `{color_code, color_name}` candidates; embedder of "6602" leans numeric → tips to `color_code`.

When it doesn't:
- Short cryptic labels (`"START"`, `"END"`) — embedder needs context.
- Dtype-overloaded canonicals (`style_name` vs `style_code` — both close to "style").

---

## 3. Composition: signals → decision per sub-problem

### Example: `#4 detect_stage_bands` (ROW_PER_PLI mode)

```
Input: sheet (rows × cols)

Step 1: For each column, compute signals
  vocab_row_hit[c]     = vocab match on header_row[c]      (e.g. "SEWING" → sewing@1.0)
  date_density[c]      = fraction of date cells in data rows
  sample_dtype[c]      = dominant dtype in data rows
  embedder_concept[c]  = cosine of header[c] to nearest stage concept vector

Step 2: Score each column as "stage-band-y"
  stage_score[c] = 0.5·vocab_row_hit[c]
                 + 0.3·date_density[c]
                 + 0.2·embedder_concept[c]
  (sample_dtype excluded — confirms but doesn't drive)

Step 3: Threshold + group adjacent columns by canonical match
  Cols where stage_score > 0.7 AND vocab/embedder agree on same canonical
  → group into bands

Step 4: Return bands = [(start_col, end_col, stage_canonical, name_row, score), ...]
```

Same combiner shape for other sub-problems; weights and thresholds differ.

### Example: `#9 match_stage_name`

```
Input: raw_label (e.g. "FABRIC ETA PLAN")

scores = {}
for canonical in STAGE_CANONICALS:
  v = vocab(raw_label, canonical)
  f = fuzzy(raw_label, canonical.aliases)
  e = embedder(raw_label, canonical.vector)
  scores[canonical] = max(v, 0.7·f, 0.6·e)   # vocab wins when it fires;
                                              # fuzzy/embedder are weighted backups

if max(scores.values()) > 0.85:  return MatchResult.confident(argmax)
if max(scores.values()) > 0.5:   return MatchResult.ambiguous(top_3)
else:                            return MatchResult.unknown()
```

The judge (LLM) only sees `ambiguous` / `unknown`.

---

## 4. Mode-by-mode walkthrough

The same 8 signals serve all three modes — but the **combiners** are different
because the input shape is different.

### Mode A: `ROW_PER_PLI`

(DKN, CHRISTIAN BERG, MOP/MOPD, FA26, NORTHERN REFLECTIONS, all Eastman families)

```
         ┌────┬────┬────┬────┬────┬────┬────┬────┐
row 1    │ IO │ ST │CLR │QTY │SEW │SEW │CUT │CUT │   ← header row
row 2    │    │    │    │    │PLAN│ACT │PLAN│ACT │   ← sub-header row
row 3..N │1063│ST-1│RED │ 500│2026│2026│2026│2026│   ← PLI data
         └────┴────┴────┴────┴────┴────┴────┴────┘
         identity cols ─┘ ├ Sewing band ┤├Cutting band┤
```

Signals invoked:
| Signal | Used by |
|---|---|
| vocab | header_row, sub-header_row labels |
| date_density | per-column over data rows |
| embedder | header_row labels (concept similarity) |
| sample_dtype | per-column (int vs date vs str) |
| position | sub-header = header_row + 1 (most files); +2 on CHRISTIAN BERG |

Sub-problems active: #2, #3, #4, #5, #6, #9, #10.

### Mode B: `SHEET_IS_PLI`

(Orders-Plan family — 63261-TNA, NEW, TNA DETAILS, new job-TNA)

```
        ┌──────────────────────────────────────────────────┐
row 3   │ Buyer:    XYZ      │   Season:    SS-26          │
row 4   │ PO:       12345    │   Style:     ST-001         │
row 5   │ Color:    RED      │   Qty:       500            │
row 6   │ (blank)                                          │
row 8   │ Sewing Plan:    2026-03-01                       │
row 9   │ Sewing Actual:  2026-02-28                       │
row 10  │ Cutting Plan:   2026-02-15                       │
        └──────────────────────────────────────────────────┘
        KV anchors scattered; no header row; no column structure
```

Signals invoked:
| Signal | Used by |
|---|---|
| vocab | label-cell text ("Buyer", "Sewing Plan", ...) |
| position | label cell adjacent (right OR below) to value cell |
| sample_dtype | value cell (date → stage; int → quantity; string → name) |
| embedder | label-cell text concept similarity |

Sub-problems active: #1 (mode_decision), #11 (kv_anchor detection), #6, #9, #10.

Key difference: there's no `#4 stage_bands` because data isn't columnar.
Stage detection becomes "find label cells whose vocab/embedder hits a stage
canonical and whose adjacent cell is a date". That's a different combiner over
the SAME signals.

```
detect_stage_kv (combiner for SHEET_IS_PLI):
  for each non-empty cell:
    if vocab(text) hits stage_canonical OR embedder(text) ≥ 0.8 to stage:
      v = value cell (try right, then below, then below-right)
      if sample_dtype(v) == date:
        emit StageKV(label_cell, value_cell, canonical)
```

### Mode C: `SECTION_PER_PLI`

(new Eastman TnAs, GUESS master files)

```
        ┌────────────────────────────────────────────────┐
row 5   │ PLI 1: Style ST-001                            │  ← section header
row 6   │   Buyer: XYZ        PO: 12345                  │  ← KV anchors
row 7   │   Color: RED        Qty: 500                   │
row 8   │   Sewing: 2026-03-01                           │
row 9   │   Cutting: 2026-02-15                          │
row 10  │   (blank row)                                  │  ← section break
row 11  │                                                │
        ├────────────────────────────────────────────────┤
row 12  │ PLI 2: Style ST-002                            │
row 13  │   Buyer: XYZ        PO: 12346                  │
row 14  │   Color: BLU        Qty: 300                   │
row 15  │   Sewing: 2026-03-05                           │
        └────────────────────────────────────────────────┘
```

Signals invoked:
| Signal | Used by |
|---|---|
| block_split | partition rows by blank-row / repeated-marker patterns |
| (everything from Mode B above, applied PER section) | per-PLI processing |

```
detect_sections (combiner for SECTION_PER_PLI):
  blank_rows = rows where ≤1 cell has content
  separators = consecutive_blank_runs OR repeated_label_rows ("PLI 1", "PLI 2")
  sections = partition_by(separators)
  for each section:
    apply SHEET_IS_PLI combiners scoped to that section
```

Sub-problems active: #12 (section detection), then per section all of Mode B's.

---

## 5. Multi-band sheet (CHRISTIAN BERG — 7 stages stacked)

CHRISTIAN BERG has 7 stage bands on ONE sheet, each with 2–3 sub-columns:

```
         ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
row 1    │ ID │STY │CLR │QTY │FAB │FAB │FAB │SEW │SEW │SEW │CUT │CUT │FI  │FI  │
row 2    │    │    │    │    │PLN │RCV │APP │PLN │STR │ACT │PLN │ACT │PLN │ACT │
row 3+   │data│data│data│data│date│date│date│date│date│date│date│date│date│date│
         └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
         identity ──┘├── FAB ───┤├──── SEW ────┤├─ CUT ─┤├─ FI ─┤
                          (3-wide)    (3-wide)    (2-wide)  (2-wide)
```

The combiner handles multi-band naturally:

```
detect_stage_bands_multi (ROW_PER_PLI, multi-band):
  Step 1: compute stage_score[c] per column (as in §3)
  Step 2: collect runs of adjacent columns with score > threshold
  Step 3: for each run, vote on the band's canonical (vocab agreement across cols)
  Step 4: detect sub-columns INSIDE each band (signals on row 2 OR row 3)

  Output: [
    Band(cols=5-7, canonical=fabric, sub_label_row=2),
    Band(cols=8-10, canonical=sewing, sub_label_row=2),
    Band(cols=11-12, canonical=cutting, sub_label_row=2),
    Band(cols=13-14, canonical=final_inspection, sub_label_row=2),
  ]
```

**Multi-band is not a different problem class** — it's the natural output of the
column-by-column scan + run-grouping. Single-band sheets (DKN with just
sewing+cutting+fabric+ex_factory) and multi-band sheets (CHRISTIAN BERG with 7)
go through the same combiner.

Empirical result from the experiment: `vocab_row` already scores F1 85.2% across
this corpus, including CHRISTIAN BERG. The 15% loss is **alias gaps**, not
algorithmic limitation. Adding embedder as a tiebreaker for novel labels closes
most of that gap.

---

## 6. Multi-header system (CHRISTIAN BERG also; some MOP variants)

"Multi-header" = the stage NAME row and the sub-FIELD row are separated by
blank rows or other structural rows. Example:

```
row 2    │  FABRIC                         SEWING                  CUTTING        │ ← stage names
row 3    │   (blank merged row)                                                   │
row 4    │  PLAN   RECVD  APPD     PLAN   START   ACT       PLAN    ACT           │ ← sub-fields
```

The `single_row` strategy in the experiment scored F1 92.9% because
`stage_name_row + N` (with N=1 or 2) catches the sub-label row for these layouts.
The honest signal here is `position` + `vocab on candidate rows`:

```
detect_subcolumn_row (signals composition):
  candidates = [stage_name_row + 1, +2, +3]
  for r in candidates:
    score[r] = sum(vocab_hit(cell) for cell in row r within band columns)
  return argmax(score)  if max > 0 else None
```

The combiner finds the row WITH THE MOST VOCAB MATCHES — robust to blank rows
between stage and sub-field rows.

---

## 7. Multi-PLI sections (SECTION_PER_PLI)

The hard part of SECTION_PER_PLI is **boundary detection**. Once a section is
isolated, it's just SHEET_IS_PLI or ROW_PER_PLI within.

Section boundary signals:

| Signal | Detail |
|---|---|
| blank-run | ≥2 consecutive rows where ≤1 cell has content |
| repeated-label | rows matching a pattern like `"PLI N"`, `"Style \d+"`, `"Order \d+"` |
| identity-restart | re-occurrence of identity labels (`"Buyer:"`, `"Color:"`) that already appeared above |
| visual-marker | bold borders / merged cells / different bg color (via openpyxl style data) |

Composition:

```
detect_sections:
  blank_runs = find runs of ≥2 blank rows
  repeated_labels = find row patterns that repeat ≥2 times
  identity_restarts = find rows where vocab matches an identity canonical that already appeared

  if blank_runs found → partition by blank_runs
  elif repeated_labels → partition between matches
  elif identity_restarts → partition between restarts
  else → single section (fall back to SHEET_IS_PLI or ROW_PER_PLI as a whole)
```

After partition, each section is processed independently. **All other signals
reuse without modification** — vocab, fuzzy, embedder, date_density all work the
same on a section as on a whole sheet.

---

## 8. Implications for what to build

The empirical experiment's "ship-first" picks (#10 sub-field, #9 stage-name)
still hold, but the architecture shifts:

### Don't ship as monolithic tools

```python
# Wrong — bundles signal + decision
@tool("match_stage_name")
def match_stage_name(raw_label): ...
```

### Ship signals + combiners separately

```python
# Right — signals are reusable, combiners are mode/sub-problem aware
@signal("vocab")
def vocab_match(label, canonicals) -> MatchResult: ...

@signal("embedder")
def embedder_match(label, concept_vectors) -> MatchResult: ...

@combiner("stage_name", mode="*")
def match_stage_name(raw_label, signals) -> MatchResult:
    v = signals.vocab(raw_label, STAGE_CANONICALS)
    f = signals.fuzzy(raw_label, STAGE_VOCAB.aliases)
    e = signals.embedder(raw_label, STAGE_CONCEPT_VECTORS)
    return combine_weighted(v=0.5, f=0.3, e=0.2)
```

### Modes select combiners; share signals

```python
PIPELINE_BY_MODE = {
    "ROW_PER_PLI":     [detect_header, detect_bands, detect_subcols, match_fields, match_stages, match_subfields],
    "SHEET_IS_PLI":    [detect_kv_anchors, match_fields, match_stages, match_subfields],
    "SECTION_PER_PLI": [detect_sections, fan_out_per_section(SHEET_IS_PLI or ROW_PER_PLI)],
}
```

All combiners use the same 8 signal emitters. Adding a new signal (e.g. an
embedder) makes EVERY combiner stronger automatically.

---

## 9. Concrete first slice (proposal)

Build the signal/combiner split with the smallest viable surface area:

1. **`app/signals/vocab.py`** — `vocab_match(label, canonicals)` returns MatchResult
2. **`app/signals/fuzzy.py`** — `fuzzy_match(label, aliases)`
3. **`app/signals/date_density.py`** — `column_date_density(col, rows)`
4. **`app/signals/sample_dtype.py`** — `column_dtype(col, rows)`
5. **`app/signals/position.py`** — small positional helpers
6. **`app/tools/match_subfield_label.py`** — first combiner (vocab-only); ship now
7. **`app/tools/match_stage_name.py`** — second combiner (vocab + fuzzy fallback);
    ships with `stage_judge` agent for `ambiguous`/`unknown` cases

Embedder added in a second slice **after** the above ships and we measure the
delta on the eval. Don't pre-build the embedder layer without empirical proof
it changes anything.

After these are in `app/`, swap them into the current FieldNamer for #9/#10
behavior. Measure eval impact. THEN consider #4 and #6.

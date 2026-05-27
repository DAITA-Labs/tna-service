# Strategies Visual Guide

Companion to `per_sheet_subproblems_compare.md`. That report measures **how well**
each strategy works on real data. This doc shows **how each strategy thinks** on
small worked examples — so you can read the empirical results with a clear
picture of the mechanics.

Five sub-problems, each with the same worked example run through every strategy.

---

## Sub-problem #6 — `match_identity_field`

**Worked input:** raw label = `"Order Qty"`, sample values = `[1500, 800, 1200]`
**Expected canonical:** `quantity`

### Strategy A — Vocab table (exact alias lookup)

```
Canonical          Aliases (case-insensitive)
─────────────────  ──────────────────────────────────────────────
io_number          [io, io_no, io#, ionumber, io number]
style_code         [style, style#, style_no, style code, sty]
color_code         [color, colour, color code, col]
fabric_code        [fabric, fab, fabric code, fbc]
quantity           [qty, order qty, ord qty, total qty]      ★
delivery_date      [delivery, eta, etd, ship date, del date]
```

Normalise input → `"order qty"` → scan aliases → hit on `quantity`.

```
Result: canonical=quantity   score=1.00   candidates=[]
```

### Strategy B — Fuzzy (rapidfuzz ratio)

Compute similarity of input vs every canonical + alias, take max per canonical:

```
canonical        best_alias_for_match    ratio  bar
─────────────    ────────────────────    ─────  ──────────────────
quantity         "order qty"             100    ██████████████████  ★
style_code       "style code"             52    █████████
color_code       "color code"             47    █████████
io_number        "io_no"                  18    ███
fabric_code      "fbc"                    12    ██
delivery_date    "ship date"               8    █
```

Threshold ≥80 → confident.

```
Result: canonical=quantity   score=1.00
```

### Strategy C — Token Jaccard

Tokenise input + alias sets; compute |A∩B| / |A∪B|.

```
input tokens:  {order, qty}

quantity     tokens: {qty, order, ord, total}     ∩={order,qty}  ∪=4   Jaccard=0.50 ★
style_code   tokens: {style, code, no, sty}       ∩={}           ∪=6   Jaccard=0.00
io_number    tokens: {io, no, number, ionumber}   ∩={}           ∪=6   Jaccard=0.00
```

Result: `canonical=quantity score=0.50`.  Jaccard struggles with small token
overlap; reliable for re-ordered multi-word labels but weak otherwise.

### Strategy D — Sample-value patterns

Inspect the sample values, not the label:

```
samples = [1500, 800, 1200]

rules in order:
  all int?              ✓
  date-like?            ✗
  4-digit?              partial (1500✓, 800✗, 1200✓)
  in quantity range?    ✓ (100..100000)
  → fits quantity profile

Result: canonical=quantity   score=0.70
```

Pattern alone is noisy (an `io_number` column also holds 4-digit ints), but it
**disambiguates** when label is ambiguous (e.g. "Code" → could be style/color/fabric).

### Strategy E — Combined-weighted

```
score(canonical) = vocab × 0.40
                 + fuzzy × 0.30
                 + jaccard × 0.15
                 + sample × 0.15

quantity:  1.00·0.40 + 1.00·0.30 + 0.50·0.15 + 0.70·0.15 = 0.880 ★
style_code: 0   ·0.40 + 0.52·0.30 + 0   ·0.15 + 0   ·0.15 = 0.156
```

Combined helps most when no single signal is strong (vocab miss + medium fuzzy +
strong sample pattern can still cross threshold).

---

## Sub-problem #9 — `match_stage_name`

**Worked input:** raw stage header = `"FAB PLAN"`
**Expected canonical:** `fabric`

Canonical stage set is small (~10–12). Some examples: `fabric`, `sewing`,
`cutting`, `sizeset`, `ppsubmission`, `trims_inhouse`, `fabric_inhouse`,
`ex_factory_shipment`, `inspection`.

### Strategy A — Vocab table

```
Canonical                Aliases
─────────────────────    ──────────────────────────────────────────
fabric                   [fabric, fab, fab plan, fabric inhouse, fbc] ★
sewing                   [sewing, sew, sewing plan, sewing start]
cutting                  [cutting, cut, cutting plan, cutting start]
sizeset                  [size set, sizeset, ss, sizeset submission]
ex_factory_shipment      [ex-factory, exf, shipment, ex factory]
```

```
Result: canonical=fabric   score=1.00
```

### Strategy B — Fuzzy

```
canonical       best_alias        ratio  bar
────────────    ──────────────    ─────  ──────────────────
fabric          "fab plan"        100    ██████████████████  ★
sewing          "sewing plan"      45    █████████
cutting         "cutting plan"     42    ████████
sizeset         "ss"               12    ██
```

```
Result: canonical=fabric   score=1.00
```

### Strategy C — Token Jaccard

```
input tokens: {fab, plan}

fabric    tokens: {fabric, fab, plan, inhouse, fbc}   Jaccard=2/6=0.33 ★
sewing    tokens: {sewing, sew, plan, start}          Jaccard=1/5=0.20
cutting   tokens: {cutting, cut, plan, start}         Jaccard=1/5=0.20
```

Note: `plan` is shared with sewing/cutting too — Jaccard fights here because
"PLAN" is a sub-field cue, not a stage cue.

---

## Sub-problem #10 — `match_subfield_label`

**Worked input:** raw sub-column = `"PLAN"`
**Expected canonical:** `planned_date`

Canonical sub-field set is tiny (~6–9): `planned_date`, `actual_date`,
`approval_date`, `received_date`, `start_date`, `approved_qty`, `quantity`,
`remarks`, `deviation_days`.

### Strategy A — Vocab table

```
Canonical          Aliases
─────────────────  ──────────────────────────────────
planned_date       [plan, plan date, planned, pln]  ★
actual_date        [act, actual, actual date, done]
approval_date      [appd, approved, approval, app]
received_date      [recvd, received, rcvd, rec]
start_date         [start, start date, sd]
```

```
Result: canonical=planned_date   score=1.00
```

Sub-fields are the **best fit for vocab-only**: small fixed set, suppliers use
the same handful of abbreviations.

### Strategy B — Fuzzy

```
canonical       best_alias   ratio
planned_date    "plan"       100  ★
actual_date     "act"         25
approval_date   "appd"        25
```

Only useful as a fallback (typos / unseen abbreviations).

---

## Sub-problem #4 — `detect_stage_bands`

**Worked input:** a sheet snippet (10 cols × 6 rows):

```
       Col A    B       C       D     E        F        G        H        I       J
Row 1: IO No   Style   Color   Qty   Sewing   Sewing   Cutting  Cutting  Fabric  Fabric
Row 2: (blank) (blank) (blank) (-)   PLAN     ACT      PLAN     ACT      PLAN    ACT
Row 3: 1063    ST-001  RED     500   2026-03-01 2026-02-28 2026-02-15 2026-02-14 2026-01-20 2026-01-22
Row 4: 1064    ST-002  BLUE    300   2026-03-05 2026-03-04 2026-02-18 2026-02-17 2026-01-25 2026-01-25
Row 5: 1065    ST-003  GREEN   750   2026-03-08 2026-03-08 2026-02-22 2026-02-20 2026-01-28 2026-01-30
```

**Expected output:** 3 bands — (E-F, "Sewing"), (G-H, "Cutting"), (I-J, "Fabric")

### Strategy A — Date-density per column

For each column, fraction of data-row cells that parse as dates:

```
Col:         A    B    C    D    E    F    G    H    I    J
% dates:     0    0    0    0   100  100  100  100  100  100
                                  ↓    ↓    ↓    ↓    ↓    ↓
Threshold:   ──────── 30% ──────────────────────────────────
Above:                          ✓    ✓    ✓    ✓    ✓    ✓

Group adjacent ✓ columns:        └─────── ONE BIG BAND ──────┘
```

**Failure mode:** date-density alone **conflates** 3 logical stages into 1 band.
Detects "where the stage data lives" but not stage boundaries.

```
Result: 1 band (cols E-J), no stage names    ✗ WRONG
```

### Strategy B — Vocab-row scan

Scan each header row for known stage vocabulary (case-insensitive):

```
Row 1: │ IO No │ Style │ Color │ Qty │ ★Sewing │ ★Sewing │ ★Cutting │ ★Cutting │ ★Fabric │ ★Fabric │
Row 2: │       │       │       │     │   PLAN   │   ACT    │   PLAN    │   ACT    │   PLAN   │   ACT   │

         ─────── non-stage cols ────────  ─── Sewing ────   ─── Cutting ───   ─── Fabric ───
```

Group adjacent same-name columns:

```
Band 1:  cols E-F  →  "Sewing"   name_row=1  sub_label_row=2
Band 2:  cols G-H  →  "Cutting"  name_row=1  sub_label_row=2
Band 3:  cols I-J  →  "Fabric"   name_row=1  sub_label_row=2

Result: 3 bands, names attached    ✓ CORRECT
```

**Failure mode:** silent on supplier-specific names not in vocab
(e.g. CHRISTIAN BERG's `Lot Card`, MOP/MOPD if it lacks vocab-matching headers).

### Strategy C — Hybrid

```
1. Run vocab-row → produces 0-N bands with names
2. Run date-density → produces 0-1 big bands (column ranges that hold dates)
3. Reconcile:
     - If vocab gave bands fully covering the date range → trust vocab
     - If vocab gave 0 bands but date-density found a range → emit one
       anonymous band over the date range; flag for naming
     - If vocab partially covers → use vocab boundaries + extend by date-density
```

```
Result for example: vocab covers all date columns → 3 bands ★
Result for MOP if vocab fails: 1 anonymous band over date range,
  needs naming (judge candidate)
```

---

## Sub-problem #5 — `detect_stage_subcolumns`

**Standard case** — single-row sub-header just below stage name row:

```
Row 1: Sewing  | Sewing      ← stage name
Row 2: PLAN    | ACT          ← sub-header (assumed)
Row 3: 2026-03-01 | 2026-02-28
Row 4: 2026-03-05 | 2026-03-04
```

### Strategy A — Single-row (always pick row directly below)

```
Pick: row 2
Sub-columns: [(E, "PLAN"), (F, "ACT")]   ✓
```

### Strategy B — Multi-row (CHRISTIAN BERG style)

CHRISTIAN BERG has TWO header rows between stage name and data:

```
Row 1: Fabric  | Fabric  | Fabric  | Sewing  | Sewing  | Sewing
Row 2: (blank) | (blank) | (blank) | (blank) | (blank) | (blank)    ← single-row picks THIS
Row 3: PLAN    | RECVD   | APPD    | PLAN    | START   | ACT          ← the real sub-header
Row 4: 2026-03-01 | 2026-03-01 | 2026-03-02 | 2026-04-10 | 2026-04-08 | 2026-04-15
```

Single-row picks row 2 → all blanks → returns `[(col, "")]` → downstream
can't map → stages emitted but with anonymous sub-columns → planned_date / actual_date
never populated.

Multi-row scans rows 2–4, picks the row with **vocabulary matches** (PLAN/ACT/RECVD/APPD):

```
Row 2: 0 vocab hits  → score 0
Row 3: 6 vocab hits  → score 6  ★  ← picked
Row 4: 0 vocab hits  → score 0

Sub-columns: [(E,"PLAN"), (F,"RECVD"), (G,"APPD"), (H,"PLAN"), (I,"START"), (J,"ACT")]   ✓
```

### Strategy C — Cell-value pattern (fallback)

When neither row has vocab hits, infer from data:

```
Column where most values are dates in the FUTURE  → likely "PLAN"
Column where most values are dates in the PAST    → likely "ACT"
Column where most values are blank                → likely "ACT" or "RECVD"
Column where most values are int (quantity)       → likely a qty sub-field
```

Lower confidence than B; useful when supplier uses unique sub-labels.

---

## What to look for in the empirical report

When the comparison report comes back, these are the cells that matter most:

| Sub-problem | Look for | Decision rule |
|---|---|---|
| #6 match_identity_field | Vocab precision ≥ 0.95 across files | If yes → ship vocab-only + judge for `score<threshold` cases. If <0.95 → expand vocab or add Combined-E. |
| #9 match_stage_name | Vocab recall on MOP/MOPD/CHRISTIAN BERG | If vocab returns ≥80% canonicals for these → ship. If not → judge necessary for these families. |
| #10 match_subfield_label | Vocab precision = 1.0, recall ≥ 0.95 | This is the most deterministic sub-problem; if vocab doesn't dominate, our canonical set may be wrong. |
| #4 detect_stage_bands | Hybrid recall on MOP/MOPD | If hybrid finds bands MOP/MOPD doesn't → confirms vocab gap, not data gap. If still 0 → MOP genuinely lacks signal; needs LLM. |
| #5 detect_stage_subcolumns | Multi-row precision on CHRISTIAN BERG | If multi-row picks row 3 (PLAN/ACT/RECVD) over row 2 (blanks) → ship. This is the load-bearing test for that file. |

## Decision criteria (after report lands)

For each sub-problem we'll classify into one of:

- **Ship deterministic-only** — best strategy reaches ~95% precision with ≥80% recall. Build as `@tool`, no LLM needed.
- **Ship deterministic + judge** — deterministic handles 70%+ confidently; judge picks among candidates for the rest. Most likely outcome for #6/#9.
- **Needs more strategies** — no current strategy clears the bar; brainstorm a new signal (e.g. embedding similarity, supplier-provenance hint).
- **Defer** — current monolithic agent is fine for this corner; pick another sub-problem first.

After we read both this doc and the empirical report side-by-side, we'll pick
1–2 sub-problems to productionize into `app/tools/` as the first concrete step
of Task #94 (TOOL_REGISTRY growth).

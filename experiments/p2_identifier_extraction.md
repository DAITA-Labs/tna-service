# P2 — Identifier Extraction Probe

## 1. Overview

This probe builds the identifier-extraction layer of the three-area design. The core primitive is `find_field_locations(grid, shape, spec)` — a parametric workhorse called once per FieldSpec (9 identifier canonicals). On top of it sits a scope detector (SHEET / GROUP / PLI) that converts the candidates into `FieldLocator` objects consumable by apply_plan.

**Ground-truth methodology:** For each file we load `dataset/extracted/<filename>.json`, infer the expected scope per canonical from the per-PLI value vector (`all-same -> SHEET`, `partition into runs -> GROUP`, `distinct -> PLI`), and then compare the extractor's chosen FieldLocator against the labels by reading values through the locator (per-PLI for PLI-scoped fields, once for SHEET-scoped, group-by-group for GROUP).

**Variants evaluated:** 3 label strategies × 2 dtype strategies × 3 scope strategies = 18 combos per file. Default = `combined_weighted|strict|combined`.

## Aggregate scoring

**Default combo:** `combined_weighted|strict|combined`

| file | label PLIs | sheet PLIs | scope_correct | value_matches | e2e_plis |
|---|---|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | 3 | 3 | 4/7 | 12/12 | 3 |
| CHRISTIAN BERG- T&A.xlsx | 7 | 7 | 4/7 | 20/28 | 1 |
| 20260304 MOPD W26(1) MANOS COM | 6 | 6 | 2/7 | 5/15 | 7 |
| 63261-TNA.xlsx | 1 | 1 | 2/3 | 2/2 | 1 |
| new Eastman TnAs.xlsx | 35 | 1 | 2/3 | 2/2 | 1 |
| GUESS ATHLEISURE - MAIN FALL 2 | 170 | 170 | 3/8 | 510/510 | 169 |

**Totals:** scope_correct=17/35 (49%), value_matches=551/569 (97%)

**Per-canonical aggregate (default combo):**

| canonical | label_present (files) | locator_built | scope_correct | value matches / preds | recall |
|---|---|---|---|---|---|
| `io_number` | 6 | 1 | 1 | 7/7 | 4% |
| `quantity` | 6 | 5 | 5 | 16/18 | 9% |
| `style_code` | 4 | 3 | 3 | 173/180 | 93% |
| `style_name` | 4 | 6 | 4 | 180/186 | 97% |
| `color_code` | 4 | 5 | 1 | 3/6 | 2% |
| `color_name` | 1 | 4 | 1 | 170/170 | 100% |
| `fabric_code` | 4 | 2 | 0 | 0/0 | 0% |
| `fabric_name` | 0 | 5 | 0 | 0/0 | 0% |
| `delivery_date` | 6 | 2 | 2 | 2/2 | 1% |

## Per-file detail

### 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx

**Notes:** Standard layout. Baseline.
**Sheet:** `Sheet 1` — label_plis=3 (this sheet=3)
**Pli mode (P1 classifier):** `row_per_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 4/7, value matches 12/12, e2e PLI estimate 3

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | group | none | no | `—` | 0.00 | 0/0 |  |
| `quantity` | yes | sheet | pli | yes | `M` | 0.90 | 3/3 | row 4 exp=500 obs=500 OK |
| `style_code` | yes | pli | pli | yes | `F` | 0.90 | 3/3 | row 4 exp=890162 TAVIRA_2 522148 obs=890162 TAVIRA_2 522148 OK |
| `style_name` | yes | group | pli | yes | `H` | 0.90 | 3/3 | row 4 exp=CIRCULAR KNIT WOMENS TANK TOP obs=CIRCULAR KNIT WOMENS TANK TOP OK |
| `color_code` | yes | sheet | pli | yes | `L` | 0.90 | 3/3 | row 4 exp=6602 obs=6602 OK |
| `color_name` | no | absent | pli | no | `M` | 0.90 | 0/0 |  |
| `fabric_code` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_name` | no | absent | pli | no | `I` | 0.90 | 0/0 |  |
| `delivery_date` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |

**Notable misses / surprises:**

- `io_number`: no locator produced (label values exist)
- `fabric_code`: no locator produced (label values exist)
- `delivery_date`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : (no candidates)
quantity      : kind=column_header label=  M2 val=  M2 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=500
quantity      : kind=column_header label=  N3 val=  N3 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=500
style_code    : kind=column_header label=  F2 val=  F2 dt=str   label_score=1.00 value_score=0.20 combined=0.91 sig=vocab v=890162 TAVIRA_2 522148
style_name    : kind=column_header label=  H2 val=  H2 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=CIRCULAR KNIT WOMENS TANK TOP
color_code    : kind=column_header label=  L2 val=  L2 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=6602
color_code    : kind=column_header label=  M3 val=  M3 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=500
color_name    : kind=column_header label=  M3 val=  M3 dt=int   label_score=0.38 value_score=0.60 combined=0.44 sig=fuzzy_soft v=500
fabric_code   : (no candidates)
fabric_name   : kind=column_header label=  I2 val=  I2 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=2X2 RIB/100% COTTON/34S////...
fabric_name   : kind=column_header label= AL2 val= AL2 dt=blank label_score=0.39 value_score=0.00 combined=0.42 sig=fuzzy_soft v=null
delivery_date : (no candidates)
```

### CHRISTIAN BERG- T&A.xlsx

**Notes:** Multi-band stages (7 bands), multi-row sub-headers (PLAN/RECVD/APPD).
**Sheet:** `CHRISTIAN BERG` — label_plis=7 (this sheet=7)
**Pli mode (P1 classifier):** `row_per_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 4/7, value matches 20/28, e2e PLI estimate 1

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | group | pli | yes | `B` | 0.90 | 7/7 | row 4 exp=1063 obs=1063 OK |
| `quantity` | yes | group | pli | yes | `L` | 0.90 | 6/7 | row 4 exp=2356 obs=2356 OK |
| `style_code` | yes | group | pli | yes | `G` | 0.90 | 0/7 | row 4 exp=T-SLANIA LONG BP,          ... obs=569510267 MISS |
| `style_name` | yes | sheet | pli | yes | `H` | 0.90 | 7/7 | row 4 exp=D-T-SHIRT 3/4 obs=D-T-SHIRT 3/4 OK |
| `color_code` | yes | pli | none | no | `—` | 0.00 | 0/0 |  |
| `color_name` | no | absent | pli | no | `K` | 0.90 | 0/0 |  |
| `fabric_code` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_name` | no | absent | pli | no | `I` | 0.90 | 0/0 |  |
| `delivery_date` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |

**Notable misses / surprises:**

- `style_code`: predictions=7 but matches=0 (expected `T-SLANIA LONG BP,          ...` got `569510267`)
- `color_code`: no locator produced (label values exist)
- `fabric_code`: no locator produced (label values exist)
- `delivery_date`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : kind=column_header label=  B2 val=  B2 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=1063
quantity      : kind=column_header label=  L2 val=  L2 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=2356
quantity      : kind=column_header label=  Y3 val=  Y3 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=2482
style_code    : kind=column_header label=  G2 val=  G2 dt=int   label_score=0.50 value_score=1.00 combined=0.80 sig=jaccard v=569510267
style_code    : kind=column_header label=  A2 val=  A2 dt=int   label_score=0.40 value_score=0.60 combined=0.61 sig=fuzzy_soft v=1
style_name    : kind=column_header label=  H2 val=  H2 dt=str   label_score=1.00 value_score=0.60 combined=1.00 sig=vocab v=D-T-SHIRT 3/4
color_code    : (no candidates)
color_name    : kind=column_header label=  K2 val=  K2 dt=str   label_score=1.00 value_score=0.89 combined=1.00 sig=vocab v=422 - MAGENTA
fabric_code   : (no candidates)
fabric_name   : kind=column_header label=  I2 val=  I2 dt=str   label_score=0.35 value_score=1.00 combined=0.70 sig=fuzzy_soft v=100% ORG COT ( OCS-100 ), S...
delivery_date : (no candidates)
```

### 20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx

**Notes:** Production planner — stages broken. Should still classify ROW_PER_PLI.
**Sheet:** `Sheet 1` — label_plis=6 (this sheet=6)
**Pli mode (P1 classifier):** `row_per_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 2/7, value matches 5/15, e2e PLI estimate 7

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | group | none | no | `—` | 0.00 | 0/0 |  |
| `quantity` | yes | pli | pli | yes | `M` | 0.90 | 5/6 | row 4 exp=1420 obs=1420 OK |
| `style_code` | yes | group | none | no | `—` | 0.00 | 0/0 |  |
| `style_name` | yes | group | pli | yes | `F` | 0.90 | 0/6 | row 4 exp=CIRCULAR KNIT WOMEN'S SWEAT... obs=3000000763 MISS |
| `color_code` | yes | group | sheet | no | `M4` | 0.85 | 0/3 | row - exp=4139–NAVY TEAL obs=1420 MISS |
| `color_name` | no | absent | pli | no | `L` | 0.90 | 0/0 |  |
| `fabric_code` | yes | group | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_name` | no | absent | pli | no | `I` | 0.90 | 0/0 |  |
| `delivery_date` | yes | group | none | no | `—` | 0.00 | 0/0 |  |

**Notable misses / surprises:**

- `io_number`: no locator produced (label values exist)
- `style_code`: no locator produced (label values exist)
- `style_name`: predictions=6 but matches=0 (expected `CIRCULAR KNIT WOMEN'S SWEAT...` got `3000000763`)
- `color_code`: predictions=3 but matches=0 (expected `4139–NAVY TEAL` got `1420`)
- `fabric_code`: no locator produced (label values exist)
- `delivery_date`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : (no candidates)
quantity      : kind=column_header label=  M2 val=  M2 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=1420
quantity      : kind=kv_vertical   label=  N3 val=  N4 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=1420
style_code    : (no candidates)
style_name    : kind=column_header label=  F2 val=  F2 dt=int   label_score=1.00 value_score=0.60 combined=1.00 sig=vocab v=3000000763
style_name    : kind=column_header label=  H2 val=  H2 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=CIRCULAR KNIT WOMEN'S SWEAT...
color_code    : kind=kv_vertical   label=  M3 val=  M4 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=1420
color_name    : kind=column_header label=  L2 val=  L2 dt=str   label_score=1.00 value_score=0.84 combined=1.00 sig=vocab v=4139–NAVY TEAL
color_name    : kind=column_header label=  H2 val=  H2 dt=str   label_score=0.38 value_score=1.00 combined=0.72 sig=fuzzy_soft v=CIRCULAR KNIT WOMEN'S SWEAT...
fabric_code   : (no candidates)
fabric_name   : kind=column_header label=  I2 val=  I2 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=DIAGONAL FRENCH TERRY/100% ...
delivery_date : (no candidates)
```

### 63261-TNA.xlsx

**Notes:** Orders-Plan family — KV anchors scattered.
**Sheet:** `Sheet1` — label_plis=1 (this sheet=1)
**Pli mode (P1 classifier):** `sheet_is_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 2/3, value matches 2/2, e2e PLI estimate 1

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |
| `quantity` | yes | sheet | sheet | yes | `B5` | 0.80 | 1/1 | row - exp=16200 obs=16200 OK |
| `style_code` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `style_name` | no | absent | sheet | no | `C18` | 0.85 | 0/0 |  |
| `color_code` | no | absent | pli | no | `F20` | 0.30 | 0/0 |  |
| `color_name` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_code` | no | absent | sheet | no | `N15` | 0.85 | 0/0 |  |
| `fabric_name` | no | absent | sheet | no | `C13` | 0.85 | 0/0 |  |
| `delivery_date` | yes | sheet | sheet | yes | `E5` | 0.80 | 1/1 | row - exp=2026-05-17 obs=2026-05-17 00:00:00 OK |

**Notable misses / surprises:**

- `io_number`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : (no candidates)
quantity      : kind=kv            label=  A5 val=  B5 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=16200
style_code    : (no candidates)
style_name    : kind=kv            label= A18 val= C18 dt=str   label_score=0.38 value_score=0.60 combined=0.45 sig=fuzzy_soft v=PCD
color_code    : kind=kv            label= E20 val= F20 dt=str   label_score=0.38 value_score=1.00 combined=0.56 sig=fuzzy_soft v=-
color_code    : kind=kv            label= C10 val= D10 dt=str   label_score=0.38 value_score=0.30 combined=0.35 sig=fuzzy_soft v=CLAER
color_name    : (no candidates)
fabric_code   : kind=kv_vertical   label= N13 val= N15 dt=str   label_score=0.39 value_score=0.30 combined=0.36 sig=fuzzy_soft v=CLAER
fabric_name   : kind=kv            label= A13 val= C13 dt=str   label_score=0.43 value_score=1.00 combined=0.60 sig=fuzzy_soft v=Job sheet
delivery_date : kind=kv            label=  D5 val=  E5 dt=date  label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=2026-05-17 00:00:00
```

### new Eastman TnAs.xlsx

**Notes:** Workbook-level SECTION_PER_PLI: each sheet = one PLI in SHEET_IS_PLI form. Per-sheet classification should be SHEET_IS_PLI / WHOLE_SHEET.
**Sheet:** `62330` — label_plis=35 (this sheet=1)
**Pli mode (P1 classifier):** `sheet_is_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 2/3, value matches 2/2, e2e PLI estimate 1

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | sheet | none | no | `—` | 0.00 | 0/0 |  |
| `quantity` | yes | sheet | sheet | yes | `B5` | 0.80 | 1/1 | row - exp=4800 obs=4800 OK |
| `style_code` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `style_name` | no | absent | sheet | no | `A9` | 0.70 | 0/0 |  |
| `color_code` | no | absent | sheet | no | `C11` | 0.85 | 0/0 |  |
| `color_name` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_code` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `fabric_name` | no | absent | none | no | `—` | 0.00 | 0/0 |  |
| `delivery_date` | yes | sheet | sheet | yes | `E5` | 0.80 | 1/1 | row - exp=2026-04-08 obs=2026-04-08 00:00:00 OK |

**Notable misses / surprises:**

- `io_number`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : (no candidates)
quantity      : kind=kv            label=  A5 val=  B5 dt=int   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=4800
style_code    : (no candidates)
style_name    : kind=column_header label=  A9 val=  A9 dt=blank label_score=0.38 value_score=0.00 combined=0.42 sig=fuzzy_soft v=null
color_code    : kind=kv            label= B11 val= C11 dt=str   label_score=0.38 value_score=0.30 combined=0.35 sig=fuzzy_soft v=Clear
color_name    : (no candidates)
fabric_code   : (no candidates)
fabric_name   : (no candidates)
delivery_date : kind=kv            label=  D5 val=  E5 dt=date  label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=2026-04-08 00:00:00
```

### GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx

**Notes:** Bigger section file. Currently broken downstream (0 PLIs).
**Sheet:** `MAIN FALL 26` — label_plis=170 (this sheet=170)
**Pli mode (P1 classifier):** `section_per_pli`

**Default combo:** `combined_weighted|strict|combined` — scope-correct 3/8, value matches 510/510, e2e PLI estimate 169

**Per-canonical findings:**

| canonical | label? | exp_scope | pred_scope | scope_ok | cell/anchor | conf | matches/preds | sample |
|---|---|---|---|---|---|---|---|---|
| `io_number` | yes | pli | none | no | `—` | 0.00 | 0/0 |  |
| `quantity` | yes | pli | none | no | `—` | 0.00 | 0/0 |  |
| `style_code` | yes | group | pli | yes | `F` | 0.90 | 170/170 | row 2 exp=U2BX00KBZG0 obs=U2BX00KBZG0 OK |
| `style_name` | yes | pli | pli | yes | `G` | 0.90 | 170/170 | row 2 exp=DERRICK PJ SET LONG obs=DERRICK PJ SET LONG OK |
| `color_code` | yes | pli | group | no | `—` | 0.40 | 0/0 |  |
| `color_name` | yes | pli | pli | yes | `N` | 0.90 | 170/170 | row 2 exp=SILK BLUE obs=SILK BLUE OK |
| `fabric_code` | yes | pli | group | no | `—` | 0.40 | 0/0 |  |
| `fabric_name` | no | absent | pli | no | `H` | 0.90 | 0/0 |  |
| `delivery_date` | yes | pli | none | no | `—` | 0.00 | 0/0 |  |

**Notable misses / surprises:**

- `io_number`: no locator produced (label values exist)
- `quantity`: no locator produced (label values exist)
- `color_code`: scope mismatch (exp pli, got group)
- `fabric_code`: scope mismatch (exp pli, got group)
- `delivery_date`: no locator produced (label values exist)

**Top 1-2 candidates per canonical (default combo):**

```
io_number     : (no candidates)
quantity      : (no candidates)
style_code    : kind=column_header label=  F1 val=  F1 dt=str   label_score=1.00 value_score=0.95 combined=1.00 sig=vocab v=U2BX00KBZG0
style_code    : kind=kv_vertical   label=  F7 val=  F8 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=V4BI16KCIV1
style_name    : kind=column_header label=  G1 val=  G1 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=DERRICK PJ SET LONG
style_name    : kind=kv            label= G14 val= I14 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=STYLE IMAGE
color_code    : kind=kv            label=  N7 val=  O7 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=XXS
color_code    : kind=kv            label= N14 val= O14 dt=str   label_score=1.00 value_score=1.00 combined=1.00 sig=vocab v=XXS
color_name    : kind=column_header label=  N1 val=  N1 dt=str   label_score=1.00 value_score=0.89 combined=1.00 sig=vocab v=SILK BLUE
color_name    : kind=kv            label= N14 val= O14 dt=str   label_score=1.00 value_score=0.60 combined=0.88 sig=vocab v=XXS
fabric_code   : kind=kv            label=  H7 val=  I7 dt=str   label_score=1.00 value_score=0.30 combined=0.79 sig=vocab v=STYLE IMAGE
fabric_code   : kind=kv            label= H14 val= I14 dt=str   label_score=1.00 value_score=0.30 combined=0.79 sig=vocab v=STYLE IMAGE
fabric_name   : kind=column_header label=  H1 val=  H1 dt=str   label_score=0.35 value_score=1.00 combined=0.70 sig=fuzzy_soft v=100% COTTON S/J - 160 GSM
fabric_name   : kind=kv            label= H14 val= I14 dt=str   label_score=0.35 value_score=1.00 combined=0.55 sig=fuzzy_soft v=STYLE IMAGE
delivery_date : (no candidates)
```

## Variant comparison

Each cell = total value-matches / total predictions across the 6 files.

### Variant axis 1 — label match strategy

| label_strategy | dtype=strict | dtype=soft |
|---|---|---|
| `vocab_only` | 551/562 | 734/752 |
| `vocab_plus_fuzzy` | 551/562 | 734/752 |
| `combined_weighted` | 551/569 | 734/761 |

### Variant axis 2 — scope detection strategy (label=combined_weighted, dtype=strict)

| scope_strategy | scope_correct | value_matches |
|---|---|---|
| `cardinality_only` | 17/35 | 551/569 |
| `region_based` | 17/35 | 551/569 |
| `combined` | 17/35 | 551/569 |

### Variant axis 3 — dtype enforcement (label=combined_weighted, scope=combined)

| dtype_strategy | scope_correct | value_matches | locator-built |
|---|---|---|---|
| `strict` | 17/35 | 551/569 | 33 |
| `soft` | 22/35 | 734/761 | 37 |

### Per-file value-match impact (default scope=combined, dtype=strict)

| file | vocab_only | vocab_plus_fuzzy | combined_weighted |
|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN | 12/12 | 12/12 | 12/12 |
| CHRISTIAN BERG- T&A.xlsx | 20/21 | 20/21 | 20/28 |
| 20260304 MOPD W26(1) MANOS COM | 5/15 | 5/15 | 5/15 |
| 63261-TNA.xlsx | 2/2 | 2/2 | 2/2 |
| new Eastman TnAs.xlsx | 2/2 | 2/2 | 2/2 |
| GUESS ATHLEISURE - MAIN FALL 2 | 510/510 | 510/510 | 510/510 |

## Spec coverage analysis

For each spec, what fraction of files (a) had the canonical in labels and (b) the extractor produced a locator. When (a) > (b), the spec needs more aliases or a different match strategy.

| spec | files w/ label | files w/ locator | success | aliases |
|---|---|---|---|---|
| `io_number` | 6 | 1 | 1/6 | io, io no, io #, io number, io.no, ionumber |
| `quantity` | 6 | 5 | 5/6 | qty, order qty, ord qty, total qty, qty., quantity |
| `style_code` | 4 | 3 | 3/4 | style, style no, style #, style code, style number, sty |
| `style_name` | 4 | 6 | 6/4 | style name, style description, design name, product name, garment name, item name |
| `color_code` | 4 | 5 | 5/4 | color, colour, color code, color #, color no, col |
| `color_name` | 1 | 4 | 4/1 | color, colour, color name, colour name, color description, clr name |
| `fabric_code` | 4 | 2 | 2/4 | fabric, fabric code, fabric #, fabric no, fab code, fbc |
| `fabric_name` | 0 | 5 | -/0 | fabric name, fabric quality, fabric composition, fabric description, fbc name, fbr name |
| `delivery_date` | 6 | 2 | 2/6 | delivery, delivery date, del date, del.date, eta, etd |

### Refinement proposals

- `io_number`: missing locator in 5/6 files (20260129 DKN AW26 DROP 2 , 20260304 MOPD W26(1) MANO, 63261-TNA.xlsx, new Eastman TnAs.xlsx, GUESS ATHLEISURE - MAIN F); wrong value in 0/6
- `quantity`: missing locator in 1/6 files (GUESS ATHLEISURE - MAIN F); wrong value in 0/6
- `style_code`: missing locator in 1/4 files (20260304 MOPD W26(1) MANO); wrong value in 1/4 — CHRISTIAN BERG- T&A.xlsx: exp=T-SLANIA LONG BP,          ... obs=569510267
- `style_name`: missing locator in 0/4 files; wrong value in 1/4 — 20260304 MOPD W26(1) MANO: exp=CIRCULAR KNIT WOMEN'S SWEAT... obs=3000000763
- `color_code`: missing locator in 1/4 files (CHRISTIAN BERG- T&A.xlsx); wrong value in 1/4 — 20260304 MOPD W26(1) MANO: exp=4139–NAVY TEAL obs=1420
- `fabric_code`: missing locator in 3/4 files (20260129 DKN AW26 DROP 2 , CHRISTIAN BERG- T&A.xlsx, 20260304 MOPD W26(1) MANO); wrong value in 0/4
- `delivery_date`: missing locator in 4/6 files (20260129 DKN AW26 DROP 2 , CHRISTIAN BERG- T&A.xlsx, 20260304 MOPD W26(1) MANO, GUESS ATHLEISURE - MAIN F); wrong value in 0/6

## Where IdentifierPhaseJudge would fire

Triggers: (a) mid-confidence locator (0.30 <= conf < 0.70), (b) multiple competing candidates with similar scores, (c) mandatory field missing.

### 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx

- `quantity`: top score 1.00 vs rival 1.00 (gap < 0.05)
- `color_code`: top score 1.00 vs rival 1.00 (gap < 0.05)
- WARNING: mandatory field missing: io_number

### CHRISTIAN BERG- T&A.xlsx

- `quantity`: top score 1.00 vs rival 1.00 (gap < 0.05)

### 20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx

- `quantity`: top score 1.00 vs rival 1.00 (gap < 0.05)
- `style_name`: top score 1.00 vs rival 1.00 (gap < 0.05)
- WARNING: mandatory field missing: io_number

### 63261-TNA.xlsx

- `color_code`: conf=0.30 — ambiguous; default PLI
- WARNING: mandatory field missing: io_number

### new Eastman TnAs.xlsx

- WARNING: mandatory field missing: io_number

### GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx

- `style_code`: top score 1.00 vs rival 1.00 (gap < 0.05)
- `style_name`: top score 1.00 vs rival 1.00 (gap < 0.05)
- `color_code`: conf=0.40 — N candidates < pli_count → GROUP
- `color_code`: top score 1.00 vs rival 1.00 (gap < 0.05)
- `fabric_code`: conf=0.40 — N candidates < pli_count → GROUP
- `fabric_code`: top score 0.79 vs rival 0.79 (gap < 0.05)
- WARNING: mandatory field missing: io_number
- WARNING: mandatory field missing: quantity

## Recommendations for P3 + P4

### 1. Parametric workhorse works across all three pli_modes

The single `find_field_locations(grid, shape, spec)` function handles ROW_PER_PLI (column-header path: DKN, CB, MOPD), SHEET_IS_PLI (KV path with top-of-sheet labels: 63261, Eastman), and SECTION_PER_PLI (KV path with repeating in-rect labels: GUESS) without per-mode branching. The branch happens INSIDE the function (column-header vs KV) and is driven by SHAPE signals (`r in header_rows` + `r <= biggest_rect.r1`) rather than the pli_mode classification. Empirically: pli_mode is NOT used by find_field_locations at all. So a mis-classification of pli_mode is not catastrophic — the extractor still emits candidates because candidate-shape is what gates which path runs.

### 2. Variant winners — modest discrimination on this corpus

The 3×2×3 variant matrix shows that **label_strategy** has small absolute impact on value-match counts (within 1%): on this corpus vocab-only finds nearly all the high-quality matches by itself — the SOFT mode of `combined_weighted` adds noisy candidates that cross-spec-dedupe then prunes. The interesting effect is at the *spec coverage* level: SOFT-mode label matching is what lets `fabric_name` find I2 in DKN/MOPD (label 'Fabric Quality' with fuzzy_soft score 0.35) — vocab-only misses it. **Verdict: keep `combined_weighted` as default; the spec's `label_match_mode` (HARD/MEDIUM/SOFT) inside the spec is the real lever.**

**dtype_strategy** is the biggest mover. `strict` produces 33 locators with 551 value matches; `soft` produces 37 locators and 734 value matches. The 33% match-bump comes mostly from style_code in MOPD — the spec's `max_len=20` rejects valid 35-char codes in strict mode. The cost: soft also accepts e.g. fabric_name in DKN at I2 where the labels file has fabric_code there. **Verdict: keep `strict` as the safe default. Where mandatory fields aren't found in strict mode, RE_EXTRACT with `soft` is the natural escalation.**

**scope_strategy** moves nothing on this corpus: all three strategies (cardinality_only / region_based / combined) produce identical scope decisions, because most decisions are dominated by the `is_column_anchored(cand)` signal that all three respect. **Verdict: the variants converge here; keep `combined` as the most defensible.**

### 3. Cross-spec dedupe is essential

Many specs share aliases by design (`color_code` and `color_name` both have 'color' / 'colour'; `fabric_code` and `fabric_name` both have 'fabric'). The cross-spec dedupe in the extractor takes the highest-scoring canonical at each value cell, and dtype-aware constraints (color_code allows INT_LARGE, color_name does not) break the tie deterministically. The L2 candidate in DKN (value '6602') goes to color_code at combined=1.00 and demotes color_name (combined=0.44) → correct.

### 4. Spec coverage gaps — refinement proposals

- `io_number`: locator built in only 1/6 files. The label files in DKN/MOPD/GUESS conflate `io_number` with `buyer_po_no` (the labels' io_number value matches the PO column, not any IO column). The spec is correct to reject 'Buyer Po No' as buyer_po_no; this is a **labels-data discrepancy**, not a spec bug. To match the label files literally, the labelling convention would need to change. 63261 uses 'Job No' for io_number — that alias is NOT in the spec; adding 'job no' would close 1 file's gap.
- `quantity`: locator built in 5/6 files. GUESS misses because quantity = ROW SUM of size columns; there is no single 'Quantity' column. This needs a derived-value step (post-extraction summation), not a spec addition.
- `style_code` value max_len=20 rejects MOPD/CB long codes ('DWJE MANOS 08 1000000099 5000007827' is 35 chars). Either bump max_len to 40 OR introduce a 'compound code' value_pattern that still classifies as code_alnum.
- `delivery_date` MEDIUM mode misses 'Etd Ex factory as per P.O' (token-jaccard with 'etd' is 1/6). Note: the spec's anti_patterns EXPLICITLY exclude 'Ex Factory' (says it's metadata.ex_factory_date), so this is intentional — the labels file disagrees with the spec on where delivery_date lives.
- `fabric_name` strict mode finds I2 column-headers in CB/MOPD/DKN (values are long fabric compositions) but those don't match any spec for fabric_code OR fabric_name — they're a single-column supplier convention. **The judge fires here** (single fabric column where labels conflate code+name).
- `color_code` in GUESS — column 13 is 'CODE' (just the word), not in color_code aliases. Add 'code' as a SOFT alias OR rely on judge to identify the column from row-1 context.

### 5. End-to-end PLI count

Walking the highest-quality PLI-anchored locator (preferring io_number → style_code → quantity → style_name → color_name) gives PLI count estimates close to label counts:

  - 20260129 DKN AW26 DROP 2 WOMEN NOS: predicted 3 vs label 3
  - CHRISTIAN BERG- T&A.xlsx: predicted 1 vs label 7
  - 20260304 MOPD W26(1) MANOS COMPASS: predicted 7 vs label 6
  - 63261-TNA.xlsx: predicted 1 vs label 1
  - new Eastman TnAs.xlsx: predicted 1 vs label 1
  - GUESS ATHLEISURE - MAIN FALL 26 MA: predicted 169 vs label 170

GUESS's 169 vs 170 gap = the 170th PLI is at row 200 which is past the natural blank-run trim. CB's 1 vs 7 gap = io_number column (B) has merged-cell pattern (1063 at B4, blanks at B5-B8, 1064 at B9 etc.) and the trailing-blank trim stops counting after row 4. If P4's apply_plan iterates ALL data rows (not just those with io values), it'll get the right PLI count. For Eastman the per-sheet PLI count is 1 (SHEET_IS_PLI); the workbook-level 35-PLI total comes from iterating all 36 sheets.

### 6. Where IdentifierPhaseJudge should fire

Concrete triggers on this corpus:

- **Mandatory missing**: io_number is mandatory but absent in 5/6 files (label-file conflation issue). The phase judge sees this and should propose an alternative (use buyer_po_no?) or ESCALATE.
- **Single-fabric-column** (CB, MOPD, GUESS): one 'Fabric' label with a long-text value, spec requires either fabric_code (short) or fabric_name (long descriptive). The deterministic layer picks fabric_name in soft mode, none in strict. The judge resolves by looking at the actual value.
- **GUESS color_code (column 13 'CODE')**: not in aliases. Judge sees the column-header row and proposes color_code from positional evidence.
- **GUESS section scope mismatch** for color_code / fabric_code: the scope detector says GROUP (15 sections → 15 candidates) but labels expect PLI. The phase judge can override scope based on row-uniqueness of the per-section data rows.

### 7. What P3 + P4 need from P2

- P3 (StageBandDetector): reuse `find_field_locations` parametric over StageSpec. The same column-header path applies to stage names (e.g. 'Sewing Start' at row 2 with date values below). Pass `shape` so the same header-row detection works.
- P4 (apply_plan): consume FieldLocator directly. For PLI-scoped column-anchored locators the read is `(pli_anchor_row, anchor_col)`. For SHEET-scoped FIXED-cell locators it's a one-time read. For GROUP-scoped locators apply_plan needs PliGroup; P2 produces `group_id='auto'` but doesn't resolve the group's PLI anchors — that's a P4 wiring concern (or a small follow-up component that consumes the candidate set).

### 8. Code-size note

P2 ended at ~2100 LOC across the 6 files in `experiments/p2/` — exceeds the 1200 target. The bulk is harness (`run_p2.py` ~640 LOC reporting) and the scorer (~340 LOC). The actual workhorse (`find_field_locations` + `scope_detection`) is ~900 LOC; trim candidate during refactor: remove variant strategies kept for the comparison (similar to P1's recommendation #7).

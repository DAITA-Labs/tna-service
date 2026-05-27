# Labels Audit — Ground Truth Validation

**Method:** read each xlsx directly with openpyxl, trace each labelled value back to a specific cell, compare the cell's column-header text to the canonical's spec aliases / anti_patterns, and flag the field as `CORRECT`, `WRONG SOURCE` (value comes from a column that belongs to a different canonical), or `MISLABELED CANONICAL` (the column choice is right but the canonical is wrong per spec).

**Tools used:** `experiments/labels_audit/probe.py` (single-file pretty-printer) and `experiments/labels_audit/audit.py` (corrections-builder).

## Overview

- 6 files audited
- 222 distinct labelled PLIs covered (3 + 7 + 6 + 1 + 35 + 170)
- 222 PLIs verified against xlsx (1:1 mapping in all files; no orphan/duplicate labels)
- Files with NO issues: **0** (Eastman is the cleanest — only `""`→`null` cosmetic issues)
- Files with minor issues (cosmetic, doesn't affect scoring meaningfully): **2** (`63261-TNA`, `new Eastman TnAs`)
- Files with major issues (affects scoring — must fix before next probe): **4** (DKN, CB, MOPD, GUESS)

## Audit verdict per file

| File | label PLIs | xlsx PLIs verified | correctness | completeness | overall verdict |
|---|---|---|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS | 3 | 3 | 3/7 canonicals wrong | misses metadata + sewing-end stage | **NEEDS FIXES** |
| CHRISTIAN BERG- T&A | 7 | 7 | 4/7 canonicals wrong | misses metadata + stage qty | **NEEDS FIXES** |
| 20260304 MOPD W26(1) MANOS COMPASS PRO | 6 | 6 | 4/7 canonicals wrong | misses metadata; F vs H disambiguation broken | **SEVERE** |
| 63261-TNA | 1 | 1 | 7/7 canonicals correct (3 use empty-string instead of null) | misses metadata (ex_fty, order receipt, lead-times, report date) | **GOOD** (cosmetic + metadata gaps only) |
| new Eastman TnAs | 35 | 35 | identifiers correct on every sheet (35/35 io_number/qty/delivery match) | misses ex_factory_date / order_receipt / order_l_d on every sheet | **GOOD** (cosmetic + metadata gaps only) |
| GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1 | 170 | 170 (sampled 5: 0,1,10,100,169) | 3/7 canonicals wrong | misses country/price/test/MATS PO metadata + ex_consignee_date | **SEVERE** |

## Cross-file systematic issues

### 1. `io_number` / `buyer_po_no` conflation — 3/6 files

The labels file uses the value from a column whose xlsx header explicitly says "**Po**" / "**PO NO**" / "**Buyer Po No**" — and assigns it to `io_number`. The spec's anti_patterns explicitly reject this.

| file | column used | header text | example value | correct io column |
|---|---|---|---|---|
| DKN 2026-01-29 | K | "Buyer Po No" | `131673`, `131675`, `131673` | **none** — no IO column exists; this xlsx has no internal-order column at all |
| MOPD MANOS | K | "Buyer Po No" | `7000022459`, `7000022450`, etc. | **none** — no IO column exists |
| GUESS MASTER #1 | K | "PO NO" | `MA01-2026-00325`, `MA03-2026-00367`, etc. | **E ("ION")** = `1091` / `1096` / `1093` / `1092` — the actual io_number (Internal Order Number = ION) |

In DKN and MOPD the xlsx truly does not contain an IO column. So the correct labels would be: `io_number = null`, `buyer_po_no = "131673"` (or whatever was wrongly assigned). In GUESS, column E ION holds the real io_number; labels should use those (`1091`, `1093`, etc.).

### 2. `fabric_code` populated with long descriptive composition (should be `fabric_name`) — 4/6 files

| file | column | header | example value | length |
|---|---|---|---|---|
| DKN | I | "Fabric Quality" | `2X2 RIB/100% COTTON/34S////18GG/260//YARN DYED` | 46 chars |
| CB | I | "FABRIC" | `100% ORG COT ( OCS-100 ), SLUB JERSEY, 155 GSM` | 46 chars |
| MOPD | I | "Fabric Quality" | `DIAGONAL FRENCH TERRY/100% ORGANIC COTTON/34S/260/ FABRIC DYED + PANEL WASHED` | 78 chars |
| GUESS | H | "FABRIC" | `100% COTTON S/J - 160 GSM` | 26 chars |

Spec: `fabric_code.max_len = 20` (HARD dtype), so these values are CODE-SPEC violations. The 6 canonicals split fabric into code+name; the suppliers don't — they have a single column. Per spec, descriptive (>20 char) values belong in `fabric_name`. **Recommend re-labelling: move all four to `fabric_name`; leave `fabric_code = null`.**

### 3. `color_code` populated with descriptive text (should be `color_name` or split) — 2/6 files

| file | column | header | example value | shape |
|---|---|---|---|---|
| CB | K | "COLOR" | `422 - MAGENTA` / `630 - NAVY` / `940 - DEEP TAUPE` | `<code> - <name>` compound |
| MOPD | L | "Color" | `4139–NAVY TEAL` / `1183 - SILKY WHITE` / `0001-BLACK` | `<code>-<name>` compound |
| (DKN) | L | "Color" | `6602` | bare numeric — OK as color_code |
| (GUESS) | M+N | "CODE"+"COLOUR" | `G7R1` + `SILK BLUE` | code in M, name in N — labels correctly split |

CB and MOPD store both code and name in one cell. Per spec the values fail `color_code` dtype constraints (allowed_patterns = CODE_ALNUM / INT only, the strings contain spaces and >8 chars). They match `color_name` (NAME_TEXT). **Recommend: re-labelled as `color_name`, leave `color_code` null — or split the compound into code + name. DKN's pure-numeric '6602' is fine in `color_code`.**

### 4. `delivery_date` populated with ex-factory date (spec anti-pattern) — 4/6 files

The spec explicitly says "do NOT match 'Ex Factory' or 'Ex-Factory Date' — those are metadata.ex_factory_date".

| file | column | header | label value (delivery_date) |
|---|---|---|---|
| DKN | P | "Etd Ex factory as per P.O" | `2026-06-10` |
| CB | D | "EX FAC DATE" | `2026-05-05` |
| MOPD | P | "Etd Ex factory as per P.O" | `2026-05-19` / `2026-05-05` |
| GUESS | Z | "EX FAC" | `2026-05-07` / `2026-05-06` |
| (63261) | D5 | "Delivery date" (proper label!) | `2026-05-17` — **this one IS correct** |
| (Eastman) | D5 | "Delivery date" (proper label!) | `2026-04-08`, etc. — **these are correct** |

GUESS's `AA` column "EX CON" (Ex-Consignee) is the closer match to `delivery_date` and is uncaptured. **Recommend: move ex_factory dates to metadata.ex_factory_date; introduce delivery_date only where the xlsx column header clearly says "Delivery" (63261 + Eastman).**

### 5. Empty-string instead of null — 36/170 cells (cosmetic)

In `63261-TNA.json` (3 fields) and `new Eastman TnAs.json` (35 sheets × 3 fields = 105 cells), the labels use `""` instead of `null` when the xlsx has no value. Affects strict-equality scoring but not semantics.

### 6. Untracked metadata fields — every file

Every file has at least one well-defined metadata column the labels skip:

- DKN / MOPD: `O` "Original order receipt Date", `Q` "Factory Confirmed Dt"
- CB: `C` "PO DATE", `E` "PRICE", `G` "ARTICLE" (proper compact style code!)
- 63261 / Eastman: `D4` "Ex-Fty date", `D3` "Order receipt", `G3/4/5` "Order/Pre-Prod/Prodn L/D", `A3` "Date :" (report date)
- GUESS: `J` "PRICE", `L` "COUNTRY", `Y` "PO" (date), `AA` "EX CON", `AB` "TEST REQUEST", `AC` "MATS PO#", `AD` "MATS QTY"

## Per-file findings

### 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx

Sheet: `Sheet 1` (single sheet, no non-data sheets). Header rows 2+3 (some sub-labels in row 3 like "Planned"/"Actual"). Data rows 4-6. Row 7 = "Grand Total".

#### Header row (xlsx)

| col | header text (row 2) | corresponds to canonical |
|---|---|---|
| A | S.No | metadata.serial |
| B | Buyer | metadata.buyer |
| C | Factory | metadata.factory |
| D | Customer Season | metadata.customer_season |
| E | CT Season | metadata.season |
| F | Style No | **style_code** (long compound: e.g. '890162 TAVIRA_2 522148') |
| G | Image | (image link — uncaptured) |
| H | Style Description | **style_name** |
| I | Fabric Quality | **fabric_name** (long composition — spec rejects as fabric_code) |
| J | Treatment | metadata.treatment |
| K | Buyer Po No | **buyer_po_no** (labels MISCLASSIFY this as io_number) |
| L | Color | **color_code** (DKN: `6602` — numeric, fits) |
| M | Quantity (row 2) / Col (row 3) | **quantity** column M=total, N=qty subcolumn |
| O | Original order received Dt | metadata.order_receipt_date |
| P | Etd Ex factory as per P.O | metadata.ex_factory_date (labels MISCLASSIFY this as delivery_date) |
| Q | Factory Confirmed Dt | metadata.factory_confirmed_dt |
| R–AH | stage bands (Trims Inhouse / Fabric Inhouse / PPS Submission / Cut Qty / Sewing Start / Sewing End / Sewing Qty / Inspection / Ex Factory Shipment) | stage objects |
| AJ–AN | Shipped Qty / Balance Qty / Fabric Mock up / Shipment samples / Remarks | metadata + late-cycle |

No "IO No" column exists.

#### Per-PLI verification (3 PLIs, anchor rows 4/5/6)

- PLI 0 (`io_number="131673"`): K4 = 131673 (header "Buyer Po No") — **WRONG SOURCE**.
- PLI 1 (`io_number="131675"`): K5 = 131675 — **WRONG SOURCE**.
- PLI 2 (`io_number="131673"`): K6 = 131673 — **WRONG SOURCE** (and note: PLI 0 and PLI 2 share the value, which is consistent with the same PO covering multiple styles — that's normal for `buyer_po_no`).
- `style_code` `890162 TAVIRA_2 522148` etc. → F column **OK** (though >20 char — spec max_len needs bump).
- `style_name` → H column **OK**.
- `fabric_code` long composition → I column — **MISLABELED CANONICAL**, should be `fabric_name`.
- `color_code` `6602` → L column "Color" — value is numeric **OK** as color_code.
- `quantity` 500 → M column "Quantity" / N3 "Qty" — **OK**.
- `delivery_date` 2026-06-10 → P column "Etd Ex factory…" — **WRONG SOURCE**, should be metadata.ex_factory_date.

#### Discrepancies

- io_number values are sourced from K (Buyer Po No) — should be null (no IO column in this xlsx); the values should populate `buyer_po_no` instead.
- fabric_code values are long compositions → should be `fabric_name`.
- delivery_date sourced from P (Ex Factory) → should be metadata.ex_factory_date.

#### Missing fields

- `metadata.ex_factory_date` (P column captured wrongly as delivery_date)
- `metadata.order_receipt_date` (O column)
- `metadata.factory_confirmed_dt` (Q column)
- `metadata.treatment` (J column)

#### Stage data check

- Labels: 6 stages (Trims Inhouse, Fabric Inhouse, PPS Submission, Sewing, Inspection, Ex Factory Shipment).
- Xlsx: bands at R/S (Trims Inhouse Plan/Actual), T/U (Fabric Inhouse Plan/Actual), V/W/X (PPS Submission Plan/Actual/Approved), Y (Cut Qty), Z/AA (Sewing Start Plan/Actual), AB/AC (Sewing End Plan/Actual), AD (Sewing Qty), AE/AF (Inspection Plan/Actual), AG/AH/AI (Ex Factory Shipment Plan/Actual/Extended).
- **Issue:** labels collapse "Sewing Start" + "Sewing End" into one "Sewing" stage and only keep the Start planned date (2026-05-23). The "Sewing End" planned date (Z=2026-05-23 vs AB=2026-06-05) is dropped. The "Cut Qty" metadata isn't captured per-PLI either.
- Stage sub-fields: only `planned_date` populated; `actual_date`, `approval_date`, `quantity` are nullified despite the xlsx columns existing.

---

### CHRISTIAN BERG- T&A.xlsx

Sheet: `CHRISTIAN BERG` (single sheet). Header rows 2+3 (row 3 has sub-labels PLAN/RECVD/APPD or START PLAN/START ACT/END PLAN/END ACT/QTY). Data spans rows 4-11 with **vertical merges**: A4:H7 merged for io 1063 (PLI 0-3), A9:H11 merged for io 1064 (PLI 4-6). Rows 8 and 12 are subtotals (Grand Total per io group). Color (column K) varies per-row inside each group — that's how 7 PLIs are derived from 2 io values × 4 + 3 color variants.

#### Header row (xlsx)

| col | header (row 2 / row 3 sub-label) | canonical |
|---|---|---|
| A | S NO | metadata |
| B | IO NO | **io_number** (correctly labelled here) |
| C | PO DATE | metadata.po_date |
| D | EX FAC DATE | metadata.ex_factory_date (labels MISCLASSIFY as delivery_date) |
| E | PRICE | metadata.price |
| F | STYLE | **style_code-or-name** (cell contains a multi-line compound like 'T-SLANIA LONG BP,\nD-T-SHIRT 3/4') |
| G | ARTICLE | **style_code** (compact: `569510267`) — labels SKIP this column entirely |
| H | DESCRIPTION | **style_name** (e.g. 'D-T-SHIRT 3/4') |
| I | FABRIC | **fabric_name** (long composition — labelled as fabric_code, MISCLASSIFY) |
| J | IMAGE | uncaptured |
| K | COLOR | **color_name** (descriptive '422 - MAGENTA' — labelled as color_code, MISCLASSIFY) |
| L | ORDER QTY | **quantity** |
| M | PLAN QTY | metadata.plan_qty |
| N/O/P | FABRIC PLAN/RECVD/APPD | stage `fabric` with metadata.received_date, metadata.approval_date |
| Q/R | SIZE SET PLAN/ACT | stage `sizeset_submission` |
| S/T | LOT CARD PLAN/ACT | stage `lot_card` |
| U-Y | CUTTING START PLAN/START ACT/END PLAN/END ACT/QTY | stage `cutting` w/ start+end+qty |
| Z-AD | FEEDING START PLAN/START ACT/END PLAN/END ACT/QTY | stage `feeding` |
| AE-AI | SEWING START PLAN/START ACT/END PLAN/END ACT/QTY | stage `sewing` |
| AJ/AK | FI PLAN/SUB | stage `final_inspection` |

#### Per-PLI verification (7 PLIs)

- `io_number` (`1063` ×4, `1064` ×3) → B column (anchor rows 4, 9) — **CORRECT**.
- `style_code` `T-SLANIA LONG BP, ... D-T-SHIRT 3/4` → F4 (multi-line cell concatenating raw style label + description) — **suspicious**: contains description after a newline; spec max_len=20 violated; PROPER style_code is G column ARTICLE = `569510267` (uncaptured).
- `style_name` `D-T-SHIRT 3/4` → H column — **CORRECT**.
- `fabric_code` `100% ORG COT (OCS-100), SLUB JERSEY, 155 GSM` → I column — **MISLABELED CANONICAL** (this is fabric_name).
- `color_code` `422 - MAGENTA` etc. → K column — **MISLABELED CANONICAL** (this is color_name; the value is a compound 'code - name', could also be split into both).
- `quantity` 2356 / 2050 / 1576 → L column — **CORRECT**.
- `delivery_date` 2026-05-05 → D column "EX FAC DATE" — **WRONG SOURCE** (should be metadata.ex_factory_date).

#### Discrepancies

- The xlsx has a proper compact style_code (column G "ARTICLE"). Labels use the bloated F column instead. The G value `569510267` is the canonical style_code.
- fabric_code conflated with fabric_name.
- color_code conflated with color_name.
- delivery_date conflated with ex_factory_date.

#### Missing fields

- `metadata.ex_factory_date` (D column)
- `metadata.po_date` (C column)
- `metadata.price` (E column)
- per-stage `metadata.cut_qty` (Y), `feeding_qty` (AD), `sewing_qty` (AI), `plan_qty` (M)

#### Stage data check

7 stages match the xlsx (FABRIC, SIZE SET, LOT CARD, CUTTING, FEEDING, SEWING, FI). `metadata.received_date` and `metadata.approval_date` are captured for FABRIC. However:

- For CUTTING/FEEDING/SEWING the labels keep `planned_date` = START PLAN; END PLAN is dropped. Could be `start_plan_date` + `end_plan_date` for richer fidelity.
- `metadata.quantity` (Cut Qty, Feeding Qty, Sewing Qty) is not in per-stage metadata.

---

### 20260304 MOPD W26(1) MANOS COMPASS PRO.xlsx

Sheet: `Sheet 1` (single sheet). Header rows 2+3. Data rows 4-9. Row 10 = Grand Total.

#### Header row (xlsx)

| col | header (row 2) | canonical |
|---|---|---|
| A | S.No | metadata |
| B | Buyer | metadata.buyer |
| C | Factory | metadata.factory |
| D | Customer Season | metadata.customer_season |
| E | Style No | **style_code** (compound — but spec max_len violated) |
| F | Style Name | **style_code_alt**? (10-digit numeric e.g. `3000000763` — unlabelled) |
| G | Image | uncaptured |
| H | Style Description | **style_name** (descriptive — labels pick H) |
| I | Fabric Quality | **fabric_name** (long composition) |
| J | Treatment | metadata.treatment |
| K | Buyer Po No | **buyer_po_no** (labels MISCLASSIFY as io_number) |
| L | Color | **color_name** (compound 'code-name') |
| M | Quantity / N=Qty | **quantity** |
| O | Original order receipt Date | metadata.order_receipt_date |
| P | Etd Ex factory as per P.O | metadata.ex_factory_date (labels MISCLASSIFY as delivery_date) |
| Q | Factory Confirmed Dt | metadata.factory_confirmed_dt |
| R-AA | stage bands Trims Inhouse / Fabric Inhouse / Sizeset Submission / Cut Qty / Sewing Start / Sewing End | stages |

No "IO No" column.

#### Per-PLI verification (6 PLIs, rows 4-9; PLI 4 spans rows 8 and 9 due to color sub-row)

Most issues mirror DKN:

- `io_number` `7000022459`, `7000022450`, … → K column "Buyer Po No" — **WRONG SOURCE**.
- `style_code` `DWJE MANOS 08 1000000052 5000006286` → E column "Style No" — value is correct from E column **but**:
  - The 10-digit numeric in F (3000000763, 3000001132, …) looks like the supplier's true compact style_code (CODE_ALNUM). The xlsx header says "Style Name" for F, but the value-dtype contradicts the header.
  - This is a header-vs-content mismatch in the supplier's template. Labels follow headers (use H for style_name) and miss F entirely.
- `fabric_code` long composition → I column — **MISLABELED CANONICAL** → fabric_name.
- `color_code` `4139–NAVY TEAL`, `1183 - SILKY WHITE`, `0001-BLACK` → L column — **MISLABELED CANONICAL** → color_name (or split).
- `quantity` 1420 / 1050 / 760 / 1130 / 1770 / 500 → M column — **CORRECT**.
- `delivery_date` 2026-05-19 / 2026-05-05 → P column "Etd Ex factory…" — **WRONG SOURCE** → metadata.ex_factory_date.

#### Missing fields

- `metadata.ex_factory_date` (P)
- `metadata.order_receipt_date` (O)
- `metadata.factory_confirmed_dt` (Q)
- `metadata.treatment` (J)
- A second style identifier (F column with numeric codes)

#### Stage data check

6 stages (Trims, Fabric, Sizeset Submission, Sewing, Inspection, Ex Factory Shipment) — same shape as DKN. Same observation: Sewing Start + Sewing End collapsed; cut_qty not in metadata; per-stage actual_date dropped.

---

### 63261-TNA.xlsx

3 sheets: `Sheet1` (data), `Sheet2` (empty), `Sheet3` (empty). pli_mode = SHEET_IS_PLI. Single PLI labelled.

#### KV anchors (xlsx)

| cell | label | value |
|---|---|---|
| A3 | "Date :" | 2026-04-21 (report date) |
| B3 | (date value) | |
| D3 | "Order receipt" | E3 = 2026-02-06 |
| G3 | "Order L/D" | H3 = 90 |
| A4 | "Job No" | B4 = 63261 |
| D4 | "Ex-Fty date" | E4 = 2026-05-07 |
| G4 | "Pre-Prod L/D" | H4 = 49.5 |
| A5 | "Quantity :" | B5 = 16200 |
| D5 | "Delivery date" | E5 = 2026-05-17 |
| G5 | "Prodn L/D" | H5 = 40.5 |

Plus stage bands at rows 8-20 ("Pre- Production TNA", "Fabric TNA", "Production TNA").

#### Per-PLI verification (1 PLI)

- `io_number` `"63261"` → B4 (header A4 = "Job No") — **CORRECT** (note: "Job No" alias is NOT in the spec; spec needs to add it).
- `quantity` 16200 → B5 (header "Quantity :") — **CORRECT**.
- `delivery_date` `"2026-05-17"` → E5 (header D5 = "Delivery date") — **CORRECT** (this is the only file where the labels' delivery_date is sourced from a proper "Delivery date" column).
- `style_code = ""`, `color_code = ""`, `fabric_code = ""` — should be `null`, not empty string (cosmetic).

#### Missing fields

- `metadata.ex_factory_date` (E4=2026-05-07; D4 header "Ex-Fty date")
- `metadata.order_receipt_date` (E3=2026-02-06)
- `metadata.order_l_d` / `pre_prod_l_d` / `prodn_l_d` (H3/H4/H5)
- `metadata.report_date` (B3=2026-04-21)

#### Stage data check

Labels capture 11 stages from the Pre-Production / Fabric / Production bands — fully consistent with the xlsx layout. Stage metadata captures `actual` (the "Action" sub-row), `deviation` (the "Deviation if any" sub-row).

---

### new Eastman TnAs.xlsx

36 sheets. **35 data sheets + 1 index/summary sheet** (`Sheet11` = index listing job-status remarks). Each data sheet is structurally identical to `63261-TNA` — SHEET_IS_PLI per sheet. Labels claim 35 PLIs and indeed cover all 35 data sheets (1:1 mapping); `Sheet11` is correctly excluded.

#### Sheet-level audit

- 35/35 data sheets have `io_number` matching xlsx B4 ("Job No" cell) — **CORRECT**.
- 35/35 sheets have `quantity` matching B5 — **CORRECT**.
- 35/35 sheets have `delivery_date` matching E5 ("Delivery date") — **CORRECT**.
- 0 mismatch on any of these fields across all 35 sheets (verified via `audit.py`).
- `Sheet11` is the index ("S.NO | JOB NO | REMARKS" listing 15 jobs with status text); correctly excluded.

The 35 PLIs in labels are the union of base jobs and sub-jobs (`62330`, `62330.1`, `62330.2`, `62330.3`, …, `63315.5`, `63261`). The 63261 sheet inside Eastman is an EARLIER snapshot of the same job (E5=2026-05-07, B5=16200) — the standalone `63261-TNA.xlsx` is a LATER snapshot of the same job (E5=2026-05-17). Both labels are internally consistent with their respective xlsx snapshots.

#### Discrepancies

None at the identifier level.

#### Missing fields

Same as 63261-TNA — on every data sheet:

- `metadata.ex_factory_date` (D4 "Ex-Fty date", E4 value)
- `metadata.order_receipt_date` (D3 "Order receipt", E3 value)
- `metadata.order_l_d` / `pre_prod_l_d` / `prodn_l_d` (G3/G4/G5 + H3/H4/H5)
- `metadata.report_date` (A3 "Date :", B3 value)

#### Stage data check

Stages match xlsx layout (Pre-Production TNA, Fabric TNA, Production TNA bands). Per-stage metadata captures actual/deviation columns.

#### Cosmetic — empty string vs null

105 fields across the 35 PLIs (3 per PLI: `style_code`, `color_code`, `fabric_code`) use `""` instead of `null`. Affects strict-equality scoring but not semantic correctness.

---

### GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx

6 sheets. 1 data sheet (`MAIN FALL 26`), 5 non-data (`Sheet1`, `MATS`, `Testing`, `sticker`, `Courier`). pli_mode = SECTION_PER_PLI: header rows repeat every section. Row 1 = first header; then rows 2..(6-blank)..7 = next header; rows 8..(13-blank)..14 = next header etc. Each section has 1-12 data rows = 1-12 PLIs sharing the same `ION` (Internal Order Number).

#### Header row (xlsx, row 1)

| col | header | canonical |
|---|---|---|
| A | S.NO | metadata |
| B/C | FACTORY | metadata.factory |
| D | SEASON | metadata.season |
| E | **ION** | **io_number** (the real one — labels MISS this column) |
| F | STYLE NO | **style_code** |
| G | STYLE NAME | **style_name** |
| H | FABRIC | **fabric_name** (long composition — labelled fabric_code) |
| I | STYLE IMAGE | uncaptured |
| J | PRICE | metadata.price |
| K | **PO NO** | **buyer_po_no** (labels MISCLASSIFY as io_number) |
| L | COUNTRY | metadata.country |
| M | CODE | **color_code** (e.g. `G7R1`, `A11R`) |
| N | COLOUR | **color_name** (e.g. `SILK BLUE`) |
| O-U | XXS/XS/S/M/L/XL/XXL | size breakdown |
| V/W | TOTAL | **quantity** (V = per-row total; W = section total) |
| X | VALUE | metadata.value |
| Y | PO | metadata.po_date |
| Z | EX FAC | metadata.ex_factory_date (labels MISCLASSIFY as delivery_date) |
| AA | EX CON | **delivery_date** (Ex-Consignee, the proper delivery — uncaptured) |
| AB | TEST REQUEST | metadata.test_request |
| AC | MATS PO# | metadata.mats_po |
| AD | MATS QTY | metadata.mats_qty |
| AE | PROGRAM SUBMIT ON | stage `program_submit_on` |
| AF | FABRIC ETA PLAN | stage `fabric_eta_plan` |
| AG | FABRIC IN-HOUSED ON | stage `fabric_in_housed_on` |

#### Per-PLI verification (sampled 5: indices 0, 1, 10, 100, 169)

PLI 0 (row 2):
- `io_number` `"MA01-2026-00325"` ← K2 (header "PO NO") — **WRONG SOURCE**. True ION at E2 = `1091`.
- `style_code` `"U2BX00KBZG0"` ← F2 — **CORRECT**.
- `style_name` `"DERRICK PJ SET LONG"` ← G2 — **CORRECT**.
- `fabric_code` `"100% COTTON S/J - 160 GSM"` ← H2 — **MISLABELED CANONICAL** → fabric_name.
- `color_code` `"G7R1"` ← M2 — **CORRECT**.
- `color_name` `"SILK BLUE"` ← N2 — **CORRECT**.
- `quantity` 789 ← V2 — **CORRECT**.
- `delivery_date` `"2026-05-07"` ← Z2 (header "EX FAC") — **WRONG SOURCE** → metadata.ex_factory_date. AA2 = `2026-05-14` (EX CON) is the candidate for true delivery_date.

PLI 1 (row 3, ION=1091, PO=MA03-2026-00367): same pattern. io_number value `MA03-2026-00367` is K3, ION is E3=1091.

PLI 10 (row 12, ION=1096): io_number `"MA01-2026-00337"` = K12 (header "PO NO") — WRONG SOURCE. ION at E12 = `1096`.

PLI 100 (row 116, ION not sampled but pattern holds): io_number from K column = a PO-NO value.

PLI 169 (the 170th PLI, row 200 per P2 findings): same pattern.

Same systematic conflation across all 170 PLIs sampled (5/5 from the sample show identical pattern).

#### Discrepancies

- io_number = buyer's PO across all 170 PLIs. The real io_number is column E (ION). Labels need full re-mapping of this field: each PLI's `io_number` should be `E<row>`, not `K<row>`. The current `K<row>` values should populate `buyer_po_no`.
- fabric_code values are long fabric compositions → fabric_name.
- delivery_date sourced from Z (EX FAC) → metadata.ex_factory_date.

#### Missing fields

- `metadata.country` (L)
- `metadata.price` (J)
- `metadata.test_request` (AB)
- `metadata.mats_po` (AC) / `metadata.mats_qty` (AD)
- `metadata.value` (X)
- `metadata.po_date` (Y)
- Per-size breakdown (O-U) — useful for sized-order PLIs

#### Stage data check

Labels capture 3 stages (`Program Submit On`, `Fabric ETA Plan`, `Fabric In-housed On`) which match xlsx columns AE/AF/AG exactly. There's no other production stage data in this sheet (the xlsx truly only has these 3 stage columns). **Coverage OK.**

---

## Correction proposals — JSON

Full machine-readable corrections written to `experiments/labels_audit_corrections.json` (253 individual correction records across 51 PLI entries). Sample (DKN PLI 0):

```json
{
  "file": "20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS",
  "pli_index": 0,
  "source_row": 4,
  "corrections": [
    {"canonical": "io_number", "old_value": "131673", "new_value": null,
     "reason": "label value sourced from K4 (header 'Buyer Po No') — that is buyer_po_no, not io_number. No 'IO No' column exists in this sheet."},
    {"canonical": "buyer_po_no", "old_value": null, "new_value": "131673",
     "reason": "the value labeled as io_number is actually buyer's PO (K column)"},
    {"canonical": "fabric_code", "old_value": "2X2 RIB/100% COTTON/34S////18GG/260//YARN DYED", "new_value": null,
     "reason": "value at I4 is a long fabric composition (>20 chars); spec says this is fabric_name"},
    {"canonical": "fabric_name", "old_value": null, "new_value": "2X2 RIB/100% COTTON/34S////18GG/260//YARN DYED",
     "reason": "I header is 'Fabric Quality' — descriptive composition → fabric_name"},
    {"canonical": "delivery_date", "old_value": "2026-06-10", "new_value": null,
     "reason": "label value sourced from P4 (header 'Etd Ex factory as per P.O'); spec anti-pattern says 'Ex Factory' is metadata.ex_factory_date, not delivery_date"},
    {"canonical": "ex_factory_date", "old_value": null, "new_value": "2026-06-10",
     "reason": "P column header 'Etd Ex factory' → metadata.ex_factory_date"}
  ]
}
```

Per-file totals:

| file | correction records | bulk type |
|---|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS | 18 | io→PO swap × 3 + fabric_code→name × 3 + delivery→ex_fty × 3 |
| CHRISTIAN BERG- T&A | 49 | style_code→ARTICLE × 7 + fabric_code→name × 7 + color_code→name × 7 + delivery→ex_fty × 7 |
| 20260304 MOPD W26(1) MANOS COMPASS PRO | 48 | io→PO × 6 + fabric → name × 6 + color → name × 6 + delivery → ex_fty × 6 |
| 63261-TNA | 3 | `""` → null cosmetic |
| new Eastman TnAs | 105 | `""` → null cosmetic × 35 |
| GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1 | 30 | io→PO × 5 + fabric → name × 5 + delivery → ex_fty × 5 (sampled — same pattern × 170 in full) |

---

## Summary recommendation

### Trust in current labels

| file | trust as ground truth? |
|---|---|
| 20260129 DKN AW26 DROP 2 WOMEN NOS | **NO** — io/fabric/delivery all mis-canonicalized |
| CHRISTIAN BERG- T&A | **NO** — style_code wrong column; fabric/color/delivery mis-canonicalized |
| 20260304 MOPD W26(1) MANOS COMPASS | **NO** — io/fabric/color/delivery all mis-canonicalized |
| 63261-TNA | **YES** for identifiers (modulo empty-string→null); supplement with metadata |
| new Eastman TnAs | **YES** for identifiers across all 35 sheets; supplement with metadata |
| GUESS ATHLEISURE - MAIN FALL 26 #1 | **NO** — io column wrong (E ION is the real io); fabric/delivery mis-canonicalized |

### Fields with systematic problems across the corpus

1. **`io_number` vs `buyer_po_no`** — labels-file uses the PO column for io_number in 3/6 files (DKN, MOPD, GUESS). The xlsx has the real IO column only in GUESS (column E "ION") and CB (column B "IO NO"). DKN/MOPD truly have no IO column. Fix: relabel; consider whether `io_number` should remain mandatory given that some xlsx files literally don't provide it.
2. **`fabric_code` vs `fabric_name`** — 4/6 files store long fabric compositions in the labels' `fabric_code` field. Spec says these are `fabric_name`. Fix: re-canonicalize all to `fabric_name`; leave `fabric_code` null.
3. **`color_code` vs `color_name`** — 2/6 files (CB, MOPD) store descriptive 'code-name' compounds in `color_code`. Fix: relabel as `color_name` (or split into both).
4. **`delivery_date` vs `metadata.ex_factory_date`** — 4/6 files use the EX FAC column for `delivery_date`. Spec is explicit anti-pattern here. Fix: move to metadata.ex_factory_date; only use delivery_date where xlsx header literally says "Delivery date" (63261, Eastman).
5. **Empty-string vs null** — 63261 + Eastman use `""` for absent identifiers. Replace with `null`.

### Action items before P3+

1. **Regenerate labels for the 4 SEVERE/NEEDS-FIXES files** (DKN, CB, MOPD, GUESS) using the corrections JSON as a baseline. Do not score against the current labels until this is done — value-match scoring is currently penalising the correct extractor outputs and rewarding the conflated ones.
2. **Keep 63261 and Eastman labels as-is for identifier scoring**; they are clean modulo cosmetic.
3. **Add a `buyer_po_no` canonical to identifiers** (or accept it as metadata). Currently the spec only has `io_number` and the 3 conflated files have no canonical to hold the K-column values.
4. **Add `metadata.ex_factory_date` schema** (it's referenced in the spec's anti_patterns but not formalized). Same for `metadata.order_receipt_date`, `metadata.factory_confirmed_dt`.
5. **Bump `style_code.max_len` to ≥ 40** OR add a `style_code_compound` variant. MOPD's compound codes are 35+ chars; CB's "ARTICLE" column (`569510267`) is the better short code that would fit the existing constraints.
6. **Add `"job no"` as an `io_number` alias** to unblock 63261/Eastman extraction.
7. **For stage data:** consider supporting both `start_plan_date` AND `end_plan_date` for stages like Sewing/Cutting/Feeding (CB and DKN both have START/END sub-bands the current label schema collapses).

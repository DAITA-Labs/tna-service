# Canonical Stage Name Audit

**Purpose:** Map every unique Title-Case stage name found in `dataset/extracted/*.json` labels to a
canonical snake_case name from the FieldNamer prompt vocab (`app/prompts/workflow/field_namer.md`).
Sub-PR G2 will apply this mapping to the labels.

---

## 1. Summary

| Metric | Count |
|---|---|
| Label files audited | 23 |
| Total unique stage names | 68 |
| (A) Direct matches — canonical exists, obvious abbreviated or case-only variant | 27 |
| (B) Vocab stretches — closest existing canonical, semantically close enough | 31 |
| (C) Proposed new canonicals — no good existing fit, flagged for review | 10 |

**Existing FieldNamer vocab (24 stage names):**
`fabric, lab_dip_send, lab_dip_approval, fit_send, fit_approval, art_work_send, art_work_approval,
in_house_fabric_send, in_house_fabric_approval, pre_production_send, pre_production_approval,
first_pattern, garment_pattern, planned_completion_date, size_set, lot_card, cutting, feeding,
sewing, final_inspection, printing, embroidery, washing, finishing, packing`

---

## 2. Direct Matches (A) — 27 names

No controversy. Trivial case conversion, typo fix, or standard industry abbreviation.

| Label Stage Name | Canonical | Notes |
|---|---|---|
| A/W Appl | `art_work_approval` | A/W = Artwork abbreviation |
| A/W Send | `art_work_send` | A/W = Artwork abbreviation |
| Cut | `cutting` | Shortened form |
| Cuting | `cutting` | Typo (missing 't') in FA26 YC file |
| Cutting | `cutting` | Direct |
| Fabric | `fabric` | Direct |
| Feeding | `feeding` | Direct |
| FI | `final_inspection` | Standard acronym |
| Final Inspection | `final_inspection` | Direct |
| Finishing | `finishing` | Direct |
| Fit Appl | `fit_approval` | Appl = Approval abbreviation |
| Fit Send | `fit_send` | Direct |
| FPT | `first_pattern` | FPT = First Pattern Trial; appears after PP Appl, before GPT |
| GPT | `garment_pattern` | GPT = Garment Pattern Trial |
| I/B Fab Appl | `in_house_fabric_approval` | I/B Fab = In-house Fabric abbreviation |
| I/B Fab Send | `in_house_fabric_send` | I/B Fab = In-house Fabric abbreviation |
| L/D Appl | `lab_dip_approval` | L/D = Lab Dip abbreviation |
| L/D Send | `lab_dip_send` | L/D = Lab Dip abbreviation |
| Lot Card | `lot_card` | Direct |
| PCD | `planned_completion_date` | PCD = Planned Completion Date, standard TNA acronym |
| PP Appl | `pre_production_approval` | PP = Pre-Production abbreviation |
| PP Send | `pre_production_send` | PP = Pre-Production abbreviation |
| Printing | `printing` | Direct |
| Sewing | `sewing` | Direct |
| Size Set | `size_set` | Direct |
| Sizeset | `size_set` | Variant spelling |
| SS | `size_set` | SS = Size Set acronym (context: appears in GUESS files alongside Cut, PP Sent, PP APVD) |

---

## 3. Vocab Stretches (B) — 31 names

These map to an existing canonical but require judgment. One-line rationale per row.

| Label Stage Name | Canonical | Rationale |
|---|---|---|
| Consumption Locking | `planned_completion_date` | Milestone at which BOM consumption is frozen; represents a planning gate date, closest to planned_completion_date |
| Costing Freezed | `planned_completion_date` | Costing freeze is a planning milestone with a target date; no cost-specific canonical exists |
| EMB RECVD Plan | `embroidery` | "EMB" = Embroidery; the "Send Plan / RECVD Plan" pair tracks the embroidery sub-process send/return; collapsing to `embroidery` as the covering stage |
| EMB Send Plan | `embroidery` | Same as EMB RECVD Plan — embroidery send leg |
| Fabric ETA Plan | `in_house_fabric_send` | ETA Plan = planned date for fabric to arrive at factory; semantically equivalent to in_house_fabric_send target date |
| Fabric I/H | `in_house_fabric_send` | I/H = In-house; direct variant of in_house_fabric_send |
| Fabric In-housed On | `in_house_fabric_approval` | "In-housed On" = actual date fabric arrived (confirmed receipt), mapping to the approval/receipt-confirmed side |
| Fabric Inhouse | `in_house_fabric_send` | Same as Fabric I/H — represents fabric arrival target at factory |
| FI Plan Date | `final_inspection` | Plan date for Final Inspection — the same stage with a planning qualifier |
| File | `pre_production_send` | Appears at start of FA26 production flow after PPS Com, before Ppm; in apparel context a "File" at this position is the pre-production file/package submitted to factory |
| Garment Handwork | `finishing` | Hand embellishment work (beading, hand-stitch) applied post-sewing; finishing is the closest existing stage |
| Inspection | `final_inspection` | Appears as the penultimate stage before Ex Factory Shipment in 9 DKN/MOP files; unambiguously the final quality inspection |
| Job Sheet | `planned_completion_date` | Job Sheet issue date is a planning milestone in knitwear flows; captured as a dated gate |
| Line | `sewing` | Appears in GUESS files in position matching sewing production line start; "Line" in garment manufacturing context = sewing line feeding |
| Line Plan | `sewing` | "Line Plan" = planned date for sewing line feeding start in MAIN FALL KIDS files |
| Line Plan Sewing | `sewing` | Explicit variant of Line Plan with "Sewing" suffix — directly mapped |
| PP APVD | `pre_production_approval` | PP = Pre-Production, APVD = Approved |
| PP Sample | `pre_production_send` | PP Sample submission; represents same stage as PP Send — the pre-production sample sent for approval |
| PP Sent | `pre_production_send` | Sent = dispatched variant of PP Send |
| PPS Com | `pre_production_send` | PPS = Pre-Production Sample; Com = Completion/Submission; same stage as PPS Submission |
| PPS Submission | `pre_production_send` | Pre-Production Sample submission to buyer — this is the primary label in 7 DKN/MOP files |
| Ppm | `pre_production_send` | PPM = Pre-Production Meeting; appears in FA26 flow at the pre-production milestone position |
| Print/stone Received Plan | `printing` | Print/stone = printing or stone-washing embellishment; Received = return from the print/embellishment vendor; `printing` is the covering stage |
| Print/stone Send Plan | `printing` | Same process, Send leg — covered by `printing` |
| Prnt/EMB | `printing` | Print/Embroidery combined stage in Eastman files; `printing` chosen over `embroidery` as print is listed first; acceptable stretch since both are value-adding embellishment steps |
| Program Submit On | `pre_production_send` | GUESS files: "Program Submit On" = date the production program (pre-production package) was submitted to factory; equivalent to PP Send in meaning |
| Sizeset Submission | `size_set` | Size set sample submission — the sending leg of the size_set stage |
| Vap 1 Rec | `value_added_processing_1` | Receive leg of VAP slot 1 (return from subcontractor); maps to the base VAP-1 canonical (proposed new) |
| Vap 2 Rec | `value_added_processing_2` | Receive leg of VAP slot 2; maps to base VAP-2 canonical (proposed new) |
| Yarn I/H | `in_house_fabric_send` | Yarn In-house = yarn arrival at knitting factory; semantically equivalent to fabric in-house for knitwear flows |
| Yarn Req. Deadline | `planned_completion_date` | Yarn requisition deadline — a planning gate date for raw material procurement |

---

## 4. Proposed New Canonicals (C) — 10 names

**These are flagged for user review before G2 applies the mapping.**
If any proposal is rejected, the alternative is to use the closest (B) stretch shown.

| Raw Label | Proposed Canonical | Why No Existing Fit | Fallback (B) Option | Occurrences | Files |
|---|---|---|---|---|---|
| CIP | `in_process_inspection` | Appears AFTER Sewing, BEFORE Final Inspection across all 5 files. CIP = Cutting/Checking In Process — an inline QA gate distinct from the terminal FI. Mapping to `final_inspection` would create a false duplicate with the subsequent "Final Inspection" stage in the same PLI. | `final_inspection` (but duplicates) | 56 | 63261-TNA, NEW, TNA DETAILS, new Eastman TnAs, new job-TNA |
| Dyeing | `dyeing` | Distinct wet-processing step (coloring yarn or knitted fabric) in knitwear flow: Yarn I/H → Knit → **Dyeing** → Finishing. Semantically different from `washing` (which removes impurities / finishes fabric post-sewing). | `washing` (wrong semantics) | 21 | 63261-TNA, NEW, TNA DETAILS, new job-TNA |
| Ex Factory Shipment | `ex_factory` | Tracks actual departure of goods from factory for export — the last stage in 9 DKN/MOP files. The PLI field `ex_factory_date` exists but that is a PLI-level date, not a stage. As a stage it captures both planned and actual departure. No existing stage canonical covers this. | `final_inspection` (wrong semantics) | 281 | All 9 DKN/MOP files |
| Knit | `knitting` | The knitting manufacturing step in knitwear flow, after Yarn I/H. Mapping to `fabric` would conflate material-receipt with manufacturing. | `fabric` (wrong semantics) | 21 | 63261-TNA, NEW, TNA DETAILS, new job-TNA |
| Trims Inhouse | `trims_inhouse` | Tracks arrival of trims (buttons, zippers, labels, interlining) at factory — a distinct supply-chain milestone separate from fabric inhouse. Appears in 9 files at 281 occurrences. Mapping to `in_house_fabric_send` would conflate two different procurement streams that buyers track independently. | `in_house_fabric_send` (wrong semantics) | 281 | All 9 DKN/MOP files |
| VAP-1 | `value_added_processing_1` | Generic numbered VAP slot — could be printing, embroidery, stone-wash, heat transfer, etc., determined per-style. Three numbered slots (VAP-1, VAP-2, VAP-3) always appear together; numbering must be preserved to distinguish slots. Using `printing` or `embroidery` would be a guess. | `printing` (loses slot identity) | 244 | MAIN FALL KIDS & MENS MASTER CHART #1, #2, #3 |
| VAP-2 | `value_added_processing_2` | Second VAP slot — same rationale as VAP-1. | `printing` | 244 | MAIN FALL KIDS & MENS MASTER CHART #1, #2, #3 |
| VAP-3 | `value_added_processing_3` | Third VAP slot — same rationale as VAP-1. | `printing` | 244 | MAIN FALL KIDS & MENS MASTER CHART #1, #2, #3 |
| Vap 1 Send | `value_added_processing_1_send` | FA26 explicitly tracks Send vs Received as separate stage entries per VAP slot. Send = dispatch of cut panels to VAP subcontractor. Collapsing to `value_added_processing_1` loses the Send/Rec distinction. | `value_added_processing_1` (loses direction) | 16 | FA26 YC & EUROPE T&A #1 |
| Vap 2 Send | `value_added_processing_2_send` | Same as Vap 1 Send — second VAP slot Send sub-step. | `value_added_processing_2` (loses direction) | 16 | FA26 YC & EUROPE T&A #1 |

**Note on Vap 1 Rec / Vap 2 Rec:** These are mapped to the base `value_added_processing_1` /
`value_added_processing_2` canonicals (themselves proposed new). If the VAP canonicals are
accepted, Rec variants collapse into the base. If rejected and fallback `printing` is used,
the Send/Rec distinction is still lost but consistently.

---

## 5. Open Questions

1. **CIP vs two Final Inspection entries:** In 63261-TNA / new job-TNA, the stage sequence ends with
   `... Sewing → CIP → Final Inspection`. If `in_process_inspection` is not added to vocab, CIP
   must be mapped to `final_inspection` which will create two stages named `final_inspection` per
   PLI — the scorer would see duplicates. Recommend accepting the new canonical or investigating
   whether CIP rows should be dropped.

2. **Prnt/EMB → `printing` vs `embroidery`:** This abbreviation covers both printing and embroidery.
   In Eastman files the order in TNA column headers may favor one; choosing `printing` is
   conservative. If the extractor already disaggregates print and embroidery steps separately
   downstream, this stretch may lose the embroidery half. Confirm whether `embroidery` rows
   appear elsewhere in these files under a separate header.

3. **VAP Send vs VAP base:** The FA26 file tracks `Vap 1 Send` + `Vap 1 Rec` as two separate
   stages. The MAIN FALL files track only `VAP-1` (single combined stage). If both file families
   end up in the same scorer pass, `value_added_processing_1_send` and `value_added_processing_1`
   are distinct canonicals for what is functionally the same VAP slot. This may inflate cardinality.
   Consider whether to unify as `value_added_processing_1` (with Send/Rec as sub-fields) or keep
   separate canonicals.

4. **`Program Submit On` (GUESS files):** Mapped to `pre_production_send`. The GUESS #1 file has
   only three stages: `Program Submit On`, `Fabric ETA Plan`, `Fabric In-housed On` — no sewing /
   cutting stages. This may mean the GUESS #1 file is a pre-production tracking sheet only, and the
   mapping is correct. But if G2 scoring compares against extractor output that uses `pre_production_send`,
   verify the extractor actually labels this column the same way.

5. **`File` (FA26) → `pre_production_send`:** Single-file occurrence (FA26, 16 rows). The sequence
   is `PPS Com → File → Ppm → Sizeset → Cuting → ...`. "File" at this position likely means
   "File Submission" (pre-production paperwork). If the label is ambiguous, `pre_production_send`
   may score incorrectly. Low risk given single-file occurrence.

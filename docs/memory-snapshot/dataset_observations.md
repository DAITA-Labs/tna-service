---
name: TNA dataset observed layouts (as of 2026-05-08)
description: Six distinct TNA layout families observed in the project dataset, used as the eval-coverage baseline
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
Six distinct layout families observed in `F:\DAITA\ARENA\TNA\dataset` as of 2026-05-08. 23 .xlsx files total.

1. **Orders Plan** — one PLI per sheet, sheets named by Job No (e.g. 62329), scattered KV pairs in rows 3-5 (Date/Quantity/Job No on left, Order receipt/Ex-Fty date/Delivery date middle, lead-time numbers right). **Three stacked stage bands** with section names in merged col A (`Pre-Production TNA` at R8/A8:A11, `Fabric TNA` at R13/A13:A16, `Production TNA` at R18/A18:A21). Each band uses **tall sub-rows**: stage header row, then Plan / Action / Deviation as rows beneath. Files: `63261-TNA.xlsx`, `TNA DETAILS.xlsx`, `new job-TNA.xlsx`, `NEW.xlsx`. Confirmed by deep inspection 2026-05-08.

2. **DKN columnar 2-row header** — single sheet, ~40 cols, 2-row stage headers, IO col labeled "Buyer Po No". File: `20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS.xlsx`. **Wide sub-columns** (Plan/Actual/Approved as cols).

3. **Compass Pro / Marc O'Polo columnar** — single sheet "Sheet 1", ~38 cols, ~60 merged regions, R1 has buyer/season title row, R2 has columnar headers (S.No / Buyer / Factory / Customer Season / Style No / Style Name / ...). PLIs in subsequent rows (3-40+). Files: `20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO`, `20260304 MOPD W26(1) MANOS COMPASS PRO`, `20260420 MOP W26(1) 608-609 COMPASS PRO`, `20260420 MOP W26(1) CE08-MA08-MA09 COMPASS PRO`, `20260420 MOP W26(1) MANOS07-08 COMPASS PRO`, `20260420 MOPD MEN W26(1) MA09 COMPASS PRO`. **Variant of DKN columnar family** — both share "tabular columnar with multi-row header" shape; differences are in column conventions and which fields are concatenated.

4. **Christian Berg vertical-merge** — one logical PLI = N visual rows (one per color), 46 merged regions. File: `CHRISTIAN BERG- T&A.xlsx`.

5. **Flat with TOTAL footers** — each PLI = data row + "TOTAL" row beneath. File: `FA26 YC & EUROPE T&A #1.xlsx`.

6. **Master file with noise sheets** — multi-sheet, only "MAIN FALL 26" is the actual TNA; other sheets are sample tracking / SKU maps. Files: `GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1/2/3.xlsx`, `MAIN FALL KIDS & MENS MASTER CHART #1/2/3.xlsx`. Often 1000+ rows in the main sheet.

**Why:** This variety is what motivated the multi-agent + structural-signal architecture (see `feedback_routing_principle.md`). The 6th family (Compass Pro) was missed in the original 2026-05-07 inspection and surfaced 2026-05-08 via the user's existing labels in `dataset/extracted/`.

**How to apply:**
- The labeled evaluation set should include **one representative from each family** — user has labeled DKN (family 2), Compass Pro x6 (family 3), GUESS x3 (family 6). Still missing: Orders Plan (family 1, user said incoming), Christian Berg (family 4), FA26 TOTAL (family 5).
- New files later may exhibit novel signal combinations — fingerprints should be logged so recurring novel patterns become future capabilities.
- The 23 .xlsx files in dataset cover the families above. Remaining unfiled may reveal more.

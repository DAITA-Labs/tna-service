---
name: TNA parser — labels location and schema
description: Where hand-labeled ground truth JSON for TNA files lives, and the canonical schema
type: project
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
Hand-labeled ground truth JSON for TNA files lives at `F:\DAITA\ARENA\TNA\dataset\extracted\<filename>.json`, where `<filename>` matches the source `.xlsx` (without extension).

User maintains these labels by hand. As of 2026-05-08, labeled files include: `20260129 DKN AW26 DROP 2 WOMEN NOS CK PRO STATUS`, `20260213 MOPD FW26(1) MA08 MA09 COMPASS PRO`, `20260304 MOPD W26(1) MANOS COMPASS PRO`, `20260420 MOP W26(1) 608-609 COMPASS PRO`, `20260420 MOP W26(1) CE08-MA08-MA09 COMPASS PRO`, `20260420 MOP W26(1) MANOS07-08 COMPASS PRO`, `20260420 MOPD MEN W26(1) MA09 COMPASS PRO`, all three GUESS ATHLEISURE master files. More incoming.

## Canonical schema (matches user's labels — these are authoritative)

```json
{
  "total_plis": 3,
  "plis": [
    {
      "io_number": "131673",
      "style_code": "890162 TAVIRA_2 522148",
      "style_name": "CIRCULAR KNIT WOMENS TANK TOP",
      "color_code": "6602",
      "fabric_code": "2X2 RIB/100% COTTON/34S////18GG/260//YARN DYED",
      "delivery_date": "2026-06-10",
      "quantity": 500,
      "stages": [
        {"name": "Trims Inhouse", "planned_date": "2026-04-29", "quantity": null, "metadata": {}}
      ],
      "confidence": {"io_number": 1.0, "style_code": 1.0, "style_name": 1.0, "color_code": 0.85, "fabric_code": 0.9, "delivery_date": 1.0, "quantity": 0.9},
      "source_sheet": "Sheet 1",
      "source_rows": [4]
    }
  ],
  "warnings": []
}
```

**Diffs from the design doc / spec:**
- PLI uses `quantity` (not `order_quantity`)
- No separate `color_name` / `fabric_name` — `color_code` and `fabric_code` carry the full descriptive text
- Envelope has `total_plis` (redundant with `len(plis)` but informative)
- Stages omit `confidence` field (treated as 1.0 by convention since labels are ground truth)
- Stages omit `section` field (multi-band layouts not yet labeled)

**How to apply:**
- The Pydantic models in `tna_parser/models.py` must match this schema with `model_config = ConfigDict(extra="ignore")` so user labels parse cleanly
- Use these labels (not hand-crafted ones) for the eval harness — they are authoritative
- The 63261-TNA Orders Plan label is forthcoming from user; do not hand-craft a competing one
- Update the design doc + ADR-003's PLI schema to match this when the user confirms — the design's `order_quantity` and `*_name` fields are stale

{{SHARED}}

# StageLocator — role

Identify stage bands and emit one `StageColumn` per LOGICAL stage with the
canonical name. Variants (Start/End, Plan/Actual, Send/Appl) go into
`sub_columns` of the same canonical stage.

## What IS a stage

A phase of manufacturing where physical work happens: Trims Inhouse, Fabric
Inhouse, PPS Sample, L/D, Fit, A/W, PP, Cutting, Sewing, Knitting, Dyeing,
Finishing, Inspection, Ex Factory Shipment, PCD, CIP.

## What is NOT a stage (HARD rule)

- Lifecycle / order events: Original Order Received, Factory Confirmed,
  PO Date, Etd Ex factory as per P.O, ETD Ex Factory date, Delivery Date.
- Lead-time numbers: Order L/D, Pre-Prod L/D, Prodn L/D.
- Context fields: Customer Season, CT Season, Buyer, Factory, Treatment.
- Quantity columns: Cut Qty, Sewing Qty, Shipped Qty, Balance Qty, Color Qty,
  Order Qty.

## Canonicalization (CRITICAL)

A stage's variants roll up under ONE canonical name. Examples:

- "Sewing Start" (Z) + "Sewing End" (AB) + "Sewing Qty" (AD):
  → ONE StageColumn{name="Sewing", primary_col="Z",
                    sub_columns={"end_planned": "AB", "qty": "AD"}}
  (Compass Pro)

- "L/D send" (C) + "L/D appl" (D):
  → ONE StageColumn{name="L/D", primary_col="C",
                    sub_columns={"appl": "D"}}
  (Orders Plan / 63261)

## Layout modes

- `wide_sub_columns` — stage name row + sub-cols (Plan / Actual / Approved).
- `tall_sub_rows` — stage name + sub-rows (Plan / Action / Deviation) beneath.

## Multi-band sheets (Orders Plan)

When sheet has stacked sections — "Pre-Production TNA" at A8, "Fabric TNA" at
A13, "Production TNA" at A18 — emit ONE `StageBand` per section with its own
`section_name`. Emitting only the first band is wrong.

## Output

Emit a `StageBandSet` with one `StageBand` per visible section, via
`emit_stage_locator`.

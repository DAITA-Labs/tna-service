---
name: TNA parser — faithful extraction principle (cell content is source of truth)
description: Core extraction stance set by the user 2026-05-09 — preserve cell content, don't split fields, distinguish stages from PLI metadata
type: feedback
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
When extracting from TNA Excel files, treat the source cells as the **source of truth**. Don't trim, split, or reformat cell content during extraction.

## The principles (load-bearing)

1. **Faithful extraction.** A cell's content IS the field's value. If a `style_code` cell contains `"890162 TAVIRA_2 522148"`, that whole string is `style_code` — never split it into `"890162"` + `"TAVIRA_2 522148"`.
2. **One cell → one field.** No splitting one cell across multiple canonical fields, no concatenating multiple cells into one field.
3. **Null over fabrication.** Fields you can't find are null. Add a Warning, don't make up a value.
4. **One PO can place many PLIs.** Two PLIs may legitimately share the same `io_number` (a single buyer PO often produces multiple style/color combinations). Don't dedupe by io_number anywhere.

## Stage vs PLI metadata

- **Stages** are PRODUCTION milestones (Cutting, Sewing, Washing, Inspection, Ex Factory, Trims Inhouse, PPS sample, etc.).
- **PLI metadata** holds non-canonical PLI-level fields: "Original Order Received", "Factory Confirmed", "Order L/D" lead-time numbers, "Customer Season", "PO Date", etc. These have dates but they're not production milestones — they describe the order's lifecycle/admin context. The `PLI.metadata: dict[str, Any]` field added 2026-05-09 holds these.

## Stage canonicalization

When a TNA has multiple columns or rows for ONE logical stage (e.g. `"Sewing Start"` + `"Sewing End"`, or `"Sewing Plan"` + `"Sewing Actual"` + `"Sewing Approved"`), they belong to ONE stage:
- Canonical `name` is the root: `"Sewing"`.
- The "Start" or "Plan" date becomes the stage `planned_date`.
- All other sub-fields ("End", "Actual", "Approved", "Submission", "Deviation", status text) go in the stage `metadata` dict.

## Why this matters

Discovered during M0 baseline analysis that the model was splitting `style_code` at the first numeric token — costing ~30% field precision on DKN. After rewriting `baseline.SYSTEM_PROMPT` to encode these principles, field precision/recall jumped from 71% → 100% on the DKN file.

Stage canonicalization remains hard for the generalist baseline — even with explicit prompt instructions, the model still emitted `Sewing Start` + `Sewing End` as two stages. This is exactly the failure mode a dedicated Stage Locator agent (in the multi-agent plan) is designed to fix: focused prompt + narrow output schema beats long-prompt-with-many-rules.

## How to apply

- The 4 principles + stage rules are encoded in `baseline.SYSTEM_PROMPT` as of 2026-05-09 — see `tna_parser/src/tna_parser/baseline.py`.
- Multi-agent specialists (Field Locator, Stage Locator) must inherit these. The bridge artifact `FieldLocation` should NOT have a `concatenated` pattern — that's anti-pattern under faithful extraction.
- `PLI.metadata` is the bucket for non-canonical extracted fields. Use snake_case keys derived from source labels (`"Original Order Received"` → `"original_order_received"`).
- The eval harness (`tna_parser/src/tna_parser/eval.py`) uses compound-key one-to-one matching as of 2026-05-09 so duplicate io_numbers don't collapse.
